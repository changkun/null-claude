"""Tests for life.modes.time_travel — Universal Time-Travel History Scrubber."""
from tests.conftest import make_mock_app
from life.modes.time_travel import register


def _make_app():
    app = make_mock_app()
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    # Time travel is a cross-cutting feature, no enter menu.
    # Test that methods are bound.
    assert hasattr(app, '_tt_push')
    assert hasattr(app, '_tt_rewind')
    assert hasattr(app, '_tt_handle_key')


def test_step_no_crash():
    app = _make_app()
    # Push some snapshots, rewind, step forward
    # Simulate no active mode prefix (GoL-like), should do nothing
    for _ in range(10):
        app._tt_auto_record()
    # No mode prefix → no recording happens
    assert len(app.tt_history) == 0


def test_exit_cleanup():
    app = _make_app()
    # Time travel has no exit, just clear history
    app.tt_history = [{"_prefix": "test", "test_val": i} for i in range(5)]
    app.tt_pos = 2
    app._tt_restore(app.tt_history[0])
    # History remains, pos remains
    assert app.tt_pos == 2
    # Clear manually
    app.tt_history.clear()
    app.tt_pos = None
    assert app.tt_history == []
    assert app.tt_pos is None


def test_snapshot_and_restore_round_trip():
    """Snapshotting then restoring should preserve mode state."""
    app = _make_app()
    # Set up a fake mode prefix with attributes
    app.test_generation = 42
    app.test_grid = [[1, 2], [3, 4]]
    app.test_score = 99.5
    snapshot = app._tt_snapshot("test")
    assert "test_generation" in snapshot
    assert "test_grid" in snapshot
    assert "test_score" in snapshot
    # Modify state
    app.test_generation = 999
    app.test_grid = [[0, 0], [0, 0]]
    # Restore
    app._tt_restore(snapshot)
    assert app.test_generation == 42
    assert app.test_grid == [[1, 2], [3, 4]]
    assert app.test_score == 99.5


def test_snapshot_is_deep_copy():
    """Snapshot should be a deep copy -- modifying original shouldn't affect snapshot."""
    app = _make_app()
    app.test_data = [[1, 2], [3, 4]]
    snapshot = app._tt_snapshot("test")
    app.test_data[0][0] = 999
    assert snapshot["test_data"][0][0] == 1


def test_rewind_and_step_forward():
    """Push multiple snapshots, rewind, then step forward through history."""
    app = _make_app()
    # Simulate a mode with test_generation
    app.test_mode = True
    app.test_running = True
    app.test_generation = 0
    # Manually push snapshots (bypassing auto_record which needs MODE_REGISTRY)
    for i in range(5):
        app.test_generation = i
        snapshot = app._tt_snapshot("test")
        snapshot["_prefix"] = "test"
        app.tt_history.append(snapshot)
    assert len(app.tt_history) == 5
    # Rewind
    app.tt_pos = 4
    app._tt_restore(app.tt_history[2])
    assert app.test_generation == 2
    # Check position navigation
    app.tt_pos = 2
    app._tt_step_forward()
    assert app.tt_pos == 3


def test_scrub_back_clamps_at_zero():
    """Scrubbing back beyond the beginning should clamp to position 0."""
    app = _make_app()
    app.test_mode = True
    app.test_generation = 0
    for i in range(3):
        app.test_generation = i
        snapshot = app._tt_snapshot("test")
        snapshot["_prefix"] = "test"
        app.tt_history.append(snapshot)
    app.tt_pos = 1
    app._tt_scrub_back(100)  # way past beginning
    assert app.tt_pos == 0
