"""Tests for life.modes.matrix_rain — Matrix Digital Rain mode."""
import curses
from tests.conftest import make_mock_app
from life.modes.matrix_rain import (
    register,
    MATRIX_PRESETS,
    _MATRIX_KATAKANA,
    _MATRIX_DIGITS,
    _MATRIX_LATIN,
    _MATRIX_SYMBOLS,
)


def _make_app():
    app = make_mock_app()
    app.matrix_mode = False
    app.matrix_menu = False
    app.matrix_menu_sel = 0
    app.matrix_running = False
    app.matrix_show_info = False
    app.matrix_columns = []
    register(type(app))
    return app


# ── enter / exit ──────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_matrix_mode()
    assert app.matrix_menu is True
    assert app.matrix_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.matrix_mode = True
    app.matrix_preset_name = "classic"
    app._matrix_init("classic")
    assert len(app.matrix_columns) > 0
    app._exit_matrix_mode()
    assert app.matrix_mode is False
    assert app.matrix_running is False
    assert app.matrix_columns == []


# ── init presets ──────────────────────────────────────────────────────────

def test_init_classic():
    app = _make_app()
    app._matrix_init("classic")
    assert app.matrix_density == 0.4
    assert app.matrix_color_mode == "green"
    assert app.matrix_speed == 2
    assert _MATRIX_KATAKANA[0] in app.matrix_char_pool


def test_init_dense():
    app = _make_app()
    app._matrix_init("dense")
    assert app.matrix_density == 0.75
    assert app.matrix_speed == 3


def test_init_sparse():
    app = _make_app()
    app._matrix_init("sparse")
    assert app.matrix_density == 0.15
    assert app.matrix_speed == 1
    # sparse doesn't include symbols
    assert "$" not in app.matrix_char_pool


def test_init_katakana():
    app = _make_app()
    app._matrix_init("katakana")
    assert app.matrix_char_pool == _MATRIX_KATAKANA
    assert "A" not in app.matrix_char_pool


def test_init_binary():
    app = _make_app()
    app._matrix_init("binary")
    assert app.matrix_char_pool == "01"
    assert app.matrix_density == 0.5


def test_init_rainbow():
    app = _make_app()
    app._matrix_init("rainbow")
    assert app.matrix_color_mode == "rainbow"


def test_init_all_presets():
    """Every preset key in MATRIX_PRESETS initializes without error."""
    for _name, _desc, key in MATRIX_PRESETS:
        app = _make_app()
        app._matrix_init(key)
        assert app.matrix_generation == 0
        assert len(app.matrix_columns) == app.grid.cols


# ── step ──────────────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._matrix_init("classic")
    app._matrix_step()
    assert app.matrix_generation == 1


def test_step_advances_time():
    app = _make_app()
    app._matrix_init("classic")
    old_time = app.matrix_time
    app._matrix_step()
    assert app.matrix_time > old_time


def test_step_streams_move_down():
    """After stepping, stream y values should increase."""
    app = _make_app()
    app._matrix_init("classic")
    # Force a stream in column 0
    app.matrix_columns[0] = [{
        "y": 5.0, "speed": 1.0, "length": 4, "chars": ["a", "b", "c", "d"],
        "age": 0, "mutate_rate": 0.0,
    }]
    app._matrix_step()
    assert app.matrix_columns[0][0]["y"] == 6.0
    assert app.matrix_columns[0][0]["age"] == 1


def test_step_removes_offscreen_streams():
    """Streams whose tail passes below the grid are removed."""
    app = _make_app()
    app._matrix_init("classic")
    rows = app.matrix_rows
    app.matrix_columns[0] = [{
        "y": float(rows + 100), "speed": 1.0, "length": 4,
        "chars": ["a", "b", "c", "d"], "age": 0, "mutate_rate": 0.0,
    }]
    app._matrix_step()
    assert len(app.matrix_columns[0]) == 0


def test_step_no_crash():
    app = _make_app()
    app.matrix_mode = True
    app.matrix_preset_name = "classic"
    app._matrix_init("classic")
    for _ in range(10):
        app._matrix_step()
    assert app.matrix_generation == 10


def test_step_multiple_runs():
    """Run 50 steps on each preset without error."""
    for _name, _desc, key in MATRIX_PRESETS:
        app = _make_app()
        app._matrix_init(key)
        for _ in range(50):
            app._matrix_step()
        assert app.matrix_generation == 50


# ── spawn_stream ──────────────────────────────────────────────────────────

def test_spawn_stream():
    app = _make_app()
    app._matrix_init("classic")
    before = len(app.matrix_columns[0])
    app._matrix_spawn_stream(0, initial=False)
    assert len(app.matrix_columns[0]) == before + 1
    stream = app.matrix_columns[0][-1]
    assert stream["y"] < 0  # starts above screen
    assert stream["speed"] > 0
    assert len(stream["chars"]) == stream["length"]


def test_spawn_stream_initial():
    app = _make_app()
    app._matrix_init("binary")
    app._matrix_spawn_stream(5, initial=True)
    stream = app.matrix_columns[5][-1]
    # initial streams can start further up
    assert stream["y"] < 0


# ── handle_matrix_menu_key ────────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_matrix_mode()
    app._handle_matrix_menu_key(curses.KEY_DOWN)
    assert app.matrix_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_matrix_mode()
    app._handle_matrix_menu_key(curses.KEY_UP)
    assert app.matrix_menu_sel == len(MATRIX_PRESETS) - 1


def test_menu_select_enter():
    app = _make_app()
    app._enter_matrix_mode()
    app._handle_matrix_menu_key(10)  # Enter
    assert app.matrix_menu is False
    assert app.matrix_mode is True
    assert app.matrix_running is True


def test_menu_quit():
    app = _make_app()
    app._enter_matrix_mode()
    app._handle_matrix_menu_key(27)  # ESC
    assert app.matrix_mode is False


# ── handle_matrix_key ─────────────────────────────────────────────────────

def test_key_space_toggle():
    app = _make_app()
    app._matrix_init("classic")
    app.matrix_running = True
    app._handle_matrix_key(ord(' '))
    assert app.matrix_running is False
    app._handle_matrix_key(ord(' '))
    assert app.matrix_running is True


def test_key_step():
    app = _make_app()
    app._matrix_init("classic")
    gen_before = app.matrix_generation
    app._handle_matrix_key(ord('n'))
    assert app.matrix_generation == gen_before + 1


def test_key_speed_up():
    app = _make_app()
    app._matrix_init("classic")
    old_speed = app.matrix_speed
    app._handle_matrix_key(ord('+'))
    assert app.matrix_speed == old_speed + 1


def test_key_speed_down():
    app = _make_app()
    app._matrix_init("classic")
    app.matrix_speed = 5
    app._handle_matrix_key(ord('-'))
    assert app.matrix_speed == 4


def test_key_speed_min():
    app = _make_app()
    app._matrix_init("classic")
    app.matrix_speed = 1
    app._handle_matrix_key(ord('-'))
    assert app.matrix_speed == 1


def test_key_density_up():
    app = _make_app()
    app._matrix_init("classic")
    old_density = app.matrix_density
    app._handle_matrix_key(ord('d'))
    assert app.matrix_density > old_density


def test_key_density_down():
    app = _make_app()
    app._matrix_init("classic")
    old_density = app.matrix_density
    app._handle_matrix_key(ord('D'))
    assert app.matrix_density < old_density


def test_key_color_cycle():
    app = _make_app()
    app._matrix_init("classic")
    assert app.matrix_color_mode == "green"
    app._handle_matrix_key(ord('c'))
    assert app.matrix_color_mode == "blue"
    app._handle_matrix_key(ord('c'))
    assert app.matrix_color_mode == "rainbow"
    app._handle_matrix_key(ord('c'))
    assert app.matrix_color_mode == "green"


def test_key_info_toggle():
    app = _make_app()
    app._matrix_init("classic")
    assert app.matrix_show_info is False
    app._handle_matrix_key(ord('i'))
    assert app.matrix_show_info is True


def test_key_reset():
    app = _make_app()
    app.matrix_preset_name = "binary"
    app._matrix_init("binary")
    for _ in range(10):
        app._matrix_step()
    app._handle_matrix_key(ord('r'))
    assert app.matrix_generation == 0


def test_key_return_to_menu():
    app = _make_app()
    app.matrix_preset_name = "classic"
    app._matrix_init("classic")
    app.matrix_running = True
    app._handle_matrix_key(ord('R'))
    assert app.matrix_menu is True
    assert app.matrix_running is False


def test_key_quit():
    app = _make_app()
    app._matrix_init("classic")
    app.matrix_mode = True
    app._handle_matrix_key(27)  # ESC
    assert app.matrix_mode is False


# ── draw (no crash) ──────────────────────────────────────────────────────

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_matrix_mode()
    app._draw_matrix_menu(40, 120)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._matrix_init("classic")
    for _ in range(5):
        app._matrix_step()
    app._draw_matrix(40, 120)


def test_draw_with_info():
    app = _make_app()
    app._matrix_init("classic")
    app.matrix_show_info = True
    app._draw_matrix(40, 120)


def test_draw_small_terminal():
    app = _make_app()
    app._matrix_init("classic")
    app._draw_matrix(3, 5)  # very small terminal


def test_draw_all_color_modes():
    for mode in ("green", "blue", "rainbow"):
        app = _make_app()
        app._matrix_init("classic")
        app.matrix_color_mode = mode
        for _ in range(3):
            app._matrix_step()
        app._draw_matrix(40, 120)
