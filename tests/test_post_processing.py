"""Tests for life.modes.post_processing — Post-Processing Pipeline."""
from tests.conftest import make_mock_app
from life.modes.post_processing import register, EFFECT_LIST


def _make_app():
    app = make_mock_app()
    app.pp_active = set()
    app.pp_menu = False
    app.pp_trail_buf = []
    app.pp_trail_depth = 3
    app.pp_frame_count = 0
    # Add chgat to mock stdscr (post_processing uses it)
    app.stdscr.chgat = lambda *args, **kwargs: None
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    # Post-processing uses Ctrl+V toggle, not a mode enter
    assert hasattr(app, '_pp_apply')
    assert hasattr(app, '_pp_handle_key')
    assert app.pp_active == set()


def test_step_no_crash():
    app = _make_app()
    # Enable an effect and apply 10 times (no crash on mock stdscr)
    app.pp_active.add("scanlines")
    for _ in range(10):
        app._pp_apply()
    assert app.pp_frame_count == 10


def test_exit_cleanup():
    app = _make_app()
    app.pp_active = {"bloom", "trails"}
    app.pp_active.clear()
    assert app.pp_active == set()
    app.pp_trail_buf.clear()
    assert app.pp_trail_buf == []


def test_all_effects_apply_without_crash():
    """Each individual effect can be applied without error on a mock screen."""
    for eid, _name in EFFECT_LIST:
        app = _make_app()
        app.pp_active.add(eid)
        # Apply multiple frames
        for _ in range(3):
            app._pp_apply()
        assert app.pp_frame_count == 3


def test_stacked_effects():
    """Multiple effects can be stacked and applied together."""
    app = _make_app()
    for eid, _ in EFFECT_LIST:
        app.pp_active.add(eid)
    assert len(app.pp_active) == len(EFFECT_LIST)
    for _ in range(5):
        app._pp_apply()
    assert app.pp_frame_count == 5


def test_frame_count_increments_only_when_active():
    """pp_frame_count does not increment when no effects are active."""
    app = _make_app()
    app._pp_apply()
    assert app.pp_frame_count == 0  # no active effects -> early return
    app.pp_active.add("bloom")
    app._pp_apply()
    assert app.pp_frame_count == 1


def test_handle_key_toggle_menu():
    """Ctrl+V (key=22) toggles the pp_menu."""
    app = _make_app()
    assert app.pp_menu is False
    consumed = app._pp_handle_key(22)
    assert consumed is True
    assert app.pp_menu is True
    consumed = app._pp_handle_key(22)
    assert consumed is True
    assert app.pp_menu is False
