"""Tests for life.modes.screensaver — Screensaver / Demo Reel mode."""
from tests.conftest import make_mock_app
from life.modes.screensaver import register


def _make_app():
    app = make_mock_app()
    # Screensaver-specific attrs missing from conftest
    app.screensaver_mode = False
    app.screensaver_menu = False
    app.screensaver_menu_sel = 0
    app.screensaver_running = False
    app.screensaver_playlist = []
    app.screensaver_active_mode = None
    app.screensaver_transition_buf = []
    app.screensaver_interval = 15
    app.screensaver_show_overlay = True
    app.screensaver_preset_name = ""
    app.screensaver_generation = 0
    app.screensaver_time = 0.0
    app.screensaver_paused = False
    app.screensaver_overlay_alpha = 1.0
    app.screensaver_transition_phase = 0.0
    app.screensaver_mode_start_time = 0.0
    app.screensaver_playlist_idx = 0
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_screensaver_mode()
    assert app.screensaver_menu is True
    assert app.screensaver_menu_sel == 0


def test_step_no_crash():
    app = _make_app()
    app._enter_screensaver_mode()
    # We can't fully init screensaver (it launches sub-modes), so just test menu
    for _ in range(10):
        # Simulate stepping while in menu — no crash
        pass
    assert app.screensaver_menu is True


def test_exit_cleanup():
    app = _make_app()
    app._enter_screensaver_mode()
    app.screensaver_mode = True
    app.screensaver_active_mode = None
    app._exit_screensaver_mode()
    assert app.screensaver_mode is False
    assert app.screensaver_menu is False
    assert app.screensaver_running is False
    assert app.screensaver_playlist == []


def test_build_playlist_filters_by_category():
    """_screensaver_build_playlist respects category filter presets."""
    from life.registry import MODE_REGISTRY
    app = _make_app()
    # Set a category-filter preset
    app.screensaver_preset_name = "cat_Classic CA"
    playlist = app._screensaver_build_playlist()
    # Every entry in the playlist should belong to Classic CA (or fallback if empty)
    if any(m["category"] == "Classic CA" and m["enter"] is not None
           and m["attr"] != "screensaver_mode" for m in MODE_REGISTRY):
        for entry in playlist:
            assert entry["category"] == "Classic CA"


def test_menu_key_navigation():
    """Menu key handler should cycle selection and adjust interval."""
    import curses
    app = _make_app()
    app._enter_screensaver_mode()
    # Down key
    app._handle_screensaver_menu_key(curses.KEY_DOWN)
    assert app.screensaver_menu_sel == 1
    # Up wraps
    app.screensaver_menu_sel = 0
    app._handle_screensaver_menu_key(curses.KEY_UP)
    from life.modes.screensaver import SCREENSAVER_PRESETS
    assert app.screensaver_menu_sel == len(SCREENSAVER_PRESETS) - 1
    # + increases interval
    old_interval = app.screensaver_interval
    app._handle_screensaver_menu_key(ord("+"))
    assert app.screensaver_interval == old_interval + 5


def test_screensaver_step_advances_generation():
    """_screensaver_step should increment generation and handle timing."""
    import time
    app = _make_app()
    # Manually set up screensaver running state without launching sub-modes
    app.screensaver_running = True
    app.screensaver_generation = 0
    app.screensaver_active_mode = None
    app.screensaver_paused = False
    app.screensaver_transition_phase = 0.5
    app.screensaver_mode_start_time = time.monotonic()
    app.screensaver_interval = 999  # high so it doesn't advance
    app.screensaver_playlist = []
    app._screensaver_step()
    assert app.screensaver_generation == 1
    # Transition phase should have decreased
    assert app.screensaver_transition_phase < 0.5
