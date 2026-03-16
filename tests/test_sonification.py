"""Tests for life.modes.sonification — Sonification Layer."""
from tests.conftest import make_mock_app
from life.modes.sonification import register


def _make_app():
    app = make_mock_app()
    register(type(app))
    # sonify_play_cmd is set as class attr by register; override for testing
    app.sonify_play_cmd = None  # no audio playback in tests
    return app


def test_enter():
    app = _make_app()
    # Sonification is a toggle, not a mode with enter/menu
    assert hasattr(app, '_sonify_toggle')
    assert hasattr(app, '_sonify_frame')
    assert app.sonify_enabled is False


def test_step_no_crash():
    app = _make_app()
    # Toggle on then call frame 10 times — should not crash even with no player
    app.sonify_enabled = True
    for _ in range(10):
        app._sonify_frame()
    # No crash, metrics extraction may return None (no running mode)
    assert app.sonify_enabled is True


def test_exit_cleanup():
    app = _make_app()
    app.sonify_enabled = True
    result = app._sonify_toggle()
    assert result is False
    assert app.sonify_enabled is False


def test_extract_metrics_from_grid():
    """Metrics extraction from a standard Grid should return correct structure."""
    from life.modes.sonification import _extract_grid_data
    from life.grid import Grid
    g = Grid(20, 20)
    # Set some cells alive
    for r in range(5):
        for c in range(5):
            g.set_alive(r, c)
    result = _extract_grid_data(g)
    assert result is not None
    rows, cols, density, activity, cx, cy, entropy, symmetry, col_profile, quad, edge_ratio = result
    assert rows == 20
    assert cols == 20
    assert 0 < density < 1  # 25 alive out of 400
    assert len(col_profile) == 20
    assert len(quad) == 4
    # Center of mass should be in the top-left quadrant
    assert cx < 0.5
    assert cy < 0.5


def test_chord_voicing_scales_with_density():
    """Higher density should produce richer (more notes) chord voicings."""
    from life.modes.sonification import _select_chord_voicing
    sparse = _select_chord_voicing(0.03)
    medium = _select_chord_voicing(0.25)
    dense = _select_chord_voicing(0.7)
    assert len(sparse) <= len(medium) <= len(dense)


def test_rhythm_pattern_scales_with_entropy():
    """Higher entropy should select denser rhythm patterns."""
    from life.modes.sonification import _select_rhythm_pattern
    low = _select_rhythm_pattern(0.1)
    high = _select_rhythm_pattern(0.9)
    # Count active beats
    low_beats = sum(1 for x in low if x > 0)
    high_beats = sum(1 for x in high if x > 0)
    assert high_beats >= low_beats


def test_melody_extraction_from_profile():
    """Melody notes should be extracted from column density profile."""
    from life.modes.sonification import _extract_melody_notes
    col_profile = [0.0] * 20
    col_profile[5] = 0.8
    col_profile[10] = 0.6
    col_profile[15] = 0.4
    scale = [0, 2, 4, 7, 9]
    base_freq = 220.0
    notes = _extract_melody_notes(col_profile, scale, base_freq, n_notes=3)
    assert len(notes) == 3
    assert all(120 <= n <= 3000 for n in notes), "All notes should be in audible range"


def test_synthesize_produces_audio():
    """The synthesizer should produce non-empty PCM audio bytes."""
    from life.modes.sonification import _sonify_synthesize, _DEFAULT_PROFILE
    metrics = {
        "density": 0.3,
        "activity": 0.5,
        "entropy": 0.6,
        "center_x": 0.5,
        "center_y": 0.5,
        "symmetry": 0.7,
        "delta": 0.01,
        "col_profile": [0.1] * 20,
        "quadrant_densities": [0.25, 0.25, 0.25, 0.25],
        "cluster_estimate": 3,
        "edge_ratio": 0.5,
        "profile": _DEFAULT_PROFILE,
        "rows": 20,
        "cols": 20,
    }
    pcm, state = _sonify_synthesize(metrics, 0.05, {})
    assert len(pcm) > 0
    assert "frame_count" in state
    assert state["frame_count"] == 1
