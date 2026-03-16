"""Tests for life.modes.kaleidoscope — Kaleidoscope mode."""
import curses
import math
from tests.conftest import make_mock_app
from life.modes.kaleidoscope import (
    register,
    KALEIDO_PRESETS,
    KALEIDO_PALETTES,
    KALEIDO_CHARS,
)


def _make_app():
    app = make_mock_app()
    app.kaleido_mode = False
    app.kaleido_menu = False
    app.kaleido_menu_sel = 0
    app.kaleido_running = False
    app.kaleido_canvas = {}
    app.kaleido_seeds = []
    register(type(app))
    return app


# ── enter / exit ──────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_kaleido_mode()
    assert app.kaleido_menu is True
    assert app.kaleido_mode is True
    assert app.kaleido_running is False


def test_exit_cleanup():
    app = _make_app()
    app.kaleido_mode = True
    app._kaleido_init("snowflake")
    assert len(app.kaleido_seeds) > 0
    app._exit_kaleido_mode()
    assert app.kaleido_mode is False
    assert app.kaleido_canvas == {}
    assert app.kaleido_seeds == []


# ── init presets ──────────────────────────────────────────────────────────

def test_init_snowflake():
    app = _make_app()
    app._kaleido_init("snowflake")
    assert app.kaleido_symmetry == 6
    assert app.kaleido_palette_idx == 1  # Ice
    assert app.kaleido_running is True
    assert len(app.kaleido_seeds) == 8


def test_init_mandala():
    app = _make_app()
    app._kaleido_init("mandala")
    assert app.kaleido_symmetry == 8
    assert len(app.kaleido_seeds) == 6


def test_init_diamond():
    app = _make_app()
    app._kaleido_init("diamond")
    assert app.kaleido_symmetry == 4


def test_init_starburst():
    app = _make_app()
    app._kaleido_init("starburst")
    assert app.kaleido_symmetry == 12
    assert app.kaleido_palette_idx == 4  # Neon


def test_init_flower():
    app = _make_app()
    app._kaleido_init("flower")
    assert app.kaleido_symmetry == 6
    assert app.kaleido_palette_idx == 3  # Forest


def test_init_vortex():
    app = _make_app()
    app._kaleido_init("vortex")
    assert app.kaleido_symmetry == 8
    assert app.kaleido_palette_idx == 2  # Fire


def test_init_hypnotic():
    app = _make_app()
    app._kaleido_init("hypnotic")
    assert app.kaleido_symmetry == 4
    assert app.kaleido_palette_idx == 5  # Monochrome


def test_init_paint():
    app = _make_app()
    app._kaleido_init("paint")
    assert app.kaleido_auto_mode is False
    assert app.kaleido_painting is True
    assert app.kaleido_fade is False
    assert len(app.kaleido_seeds) == 0


def test_init_all_presets():
    for _name, _desc, key in KALEIDO_PRESETS:
        app = _make_app()
        app._kaleido_init(key)
        assert app.kaleido_generation == 0
        assert app.kaleido_running is True


# ── step ──────────────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._kaleido_init("snowflake")
    app._kaleido_step()
    assert app.kaleido_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.kaleido_mode = True
    app._kaleido_init("snowflake")
    for _ in range(10):
        app._kaleido_step()
    assert app.kaleido_generation == 10


def test_step_populates_canvas():
    """Auto-mode seeds should produce canvas entries."""
    app = _make_app()
    app._kaleido_init("snowflake")
    for _ in range(5):
        app._kaleido_step()
    assert len(app.kaleido_canvas) > 0


def test_step_fade_removes_old():
    """With fade on, canvas entries should decay."""
    app = _make_app()
    app._kaleido_init("snowflake")
    app.kaleido_fade = True
    # Fill canvas with low intensity
    app.kaleido_canvas = {(5, 5): (0.02, 0), (6, 6): (0.02, 1)}
    app._kaleido_step()
    # The low-intensity entries should be removed by fade
    assert (5, 5) not in app.kaleido_canvas
    assert (6, 6) not in app.kaleido_canvas


def test_step_paint_mode_no_auto():
    """In paint mode with auto off, step should not add canvas entries from seeds."""
    app = _make_app()
    app._kaleido_init("paint")
    assert app.kaleido_auto_mode is False
    app._kaleido_step()
    # paint mode starts with no seeds, no auto — canvas should remain empty
    assert len(app.kaleido_canvas) == 0


def test_step_all_presets():
    for _name, _desc, key in KALEIDO_PRESETS:
        app = _make_app()
        app._kaleido_init(key)
        for _ in range(20):
            app._kaleido_step()
        assert app.kaleido_generation == 20


def test_step_all_seed_styles():
    """Each seed style should run without error and most produce canvas entries."""
    styles = ["crystal", "wave", "line", "burst", "petal", "spiral", "ring"]
    for style in styles:
        app = _make_app()
        app._kaleido_init("snowflake")
        app.kaleido_seeds = []
        app._kaleido_spawn_seeds(3, style)
        for _ in range(20):
            app._kaleido_step()
        # All styles should run without error; most produce visible output
        assert app.kaleido_generation == 20, f"Style '{style}' did not advance"


# ── plot_symmetric ────────────────────────────────────────────────────────

def test_plot_symmetric_populates_canvas():
    app = _make_app()
    app._kaleido_init("snowflake")
    app.kaleido_canvas = {}
    cy = app.kaleido_rows / 2.0
    cx = app.kaleido_cols / 2.0
    app._kaleido_plot_symmetric(cy + 5, cx + 10, 0.8, 0)
    # Should have multiple symmetric points
    assert len(app.kaleido_canvas) >= app.kaleido_symmetry


# ── paint_at ──────────────────────────────────────────────────────────────

def test_paint_at():
    app = _make_app()
    app._kaleido_init("paint")
    app.kaleido_canvas = {}
    app._kaleido_paint_at(20, 60)
    assert len(app.kaleido_canvas) > 0


def test_paint_at_brush_size():
    app = _make_app()
    app._kaleido_init("paint")
    app.kaleido_brush_size = 2
    app.kaleido_canvas = {}
    app._kaleido_paint_at(20, 60)
    # Larger brush should produce more points
    count_2 = len(app.kaleido_canvas)
    app.kaleido_canvas = {}
    app.kaleido_brush_size = 1
    app._kaleido_paint_at(20, 60)
    count_1 = len(app.kaleido_canvas)
    assert count_2 >= count_1


# ── handle_kaleido_menu_key ───────────────────────────────────────────────

def test_menu_navigate():
    app = _make_app()
    app._enter_kaleido_mode()
    app._handle_kaleido_menu_key(curses.KEY_DOWN)
    assert app.kaleido_menu_sel == 1
    app._handle_kaleido_menu_key(curses.KEY_UP)
    assert app.kaleido_menu_sel == 0


def test_menu_wrap_up():
    app = _make_app()
    app._enter_kaleido_mode()
    app._handle_kaleido_menu_key(curses.KEY_UP)
    assert app.kaleido_menu_sel == len(KALEIDO_PRESETS) - 1


def test_menu_select():
    app = _make_app()
    app._enter_kaleido_mode()
    app._handle_kaleido_menu_key(10)
    assert app.kaleido_running is True
    assert app.kaleido_menu is False


def test_menu_escape():
    app = _make_app()
    app._enter_kaleido_mode()
    app._handle_kaleido_menu_key(27)
    assert app.kaleido_mode is False


# ── handle_kaleido_key ────────────────────────────────────────────────────

def test_key_space_toggle():
    app = _make_app()
    app._kaleido_init("snowflake")
    assert app.kaleido_running is True
    app._handle_kaleido_key(ord(' '))
    assert app.kaleido_running is False


def test_key_speed():
    app = _make_app()
    app._kaleido_init("snowflake")
    s = app.kaleido_speed
    app._handle_kaleido_key(ord('+'))
    assert app.kaleido_speed == s + 1
    app._handle_kaleido_key(ord('-'))
    assert app.kaleido_speed == s


def test_key_symmetry_cycle():
    app = _make_app()
    app._kaleido_init("snowflake")
    assert app.kaleido_symmetry == 6
    app._handle_kaleido_key(ord('s'))
    assert app.kaleido_symmetry == 8
    app._handle_kaleido_key(ord('s'))
    assert app.kaleido_symmetry == 12
    app._handle_kaleido_key(ord('s'))
    assert app.kaleido_symmetry == 4


def test_key_color_cycle():
    app = _make_app()
    app._kaleido_init("snowflake")
    p = app.kaleido_palette_idx
    app._handle_kaleido_key(ord('c'))
    assert app.kaleido_palette_idx == (p + 1) % len(KALEIDO_PALETTES)


def test_key_fade_toggle():
    app = _make_app()
    app._kaleido_init("snowflake")
    assert app.kaleido_fade is True
    app._handle_kaleido_key(ord('f'))
    assert app.kaleido_fade is False


def test_key_reset():
    app = _make_app()
    app._kaleido_init("snowflake")
    for _ in range(5):
        app._kaleido_step()
    app._handle_kaleido_key(ord('r'))
    assert app.kaleido_canvas == {}
    assert app.kaleido_generation == 0


def test_key_info():
    app = _make_app()
    app._kaleido_init("snowflake")
    app._handle_kaleido_key(ord('i'))
    assert app.kaleido_show_info is True


def test_key_paint_toggle():
    app = _make_app()
    app._kaleido_init("snowflake")
    assert app.kaleido_painting is False
    app._handle_kaleido_key(ord('p'))
    assert app.kaleido_painting is True


def test_key_brush_cycle():
    app = _make_app()
    app._kaleido_init("snowflake")
    app.kaleido_brush_size = 1
    app._handle_kaleido_key(ord('b'))
    assert app.kaleido_brush_size == 2
    app._handle_kaleido_key(ord('b'))
    assert app.kaleido_brush_size == 3
    app._handle_kaleido_key(ord('b'))
    assert app.kaleido_brush_size == 1


def test_key_escape_to_menu():
    app = _make_app()
    app._kaleido_init("snowflake")
    app._handle_kaleido_key(27)
    assert app.kaleido_menu is True
    assert app.kaleido_running is False


def test_key_paint_cursor_movement():
    app = _make_app()
    app._kaleido_init("paint")
    cr = app.kaleido_cursor_r
    app._handle_kaleido_key(curses.KEY_DOWN)
    assert app.kaleido_cursor_r == cr + 1
    app._handle_kaleido_key(curses.KEY_UP)
    assert app.kaleido_cursor_r == cr


# ── draw (no crash) ──────────────────────────────────────────────────────

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_kaleido_mode()
    app._draw_kaleido_menu(40, 120)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._kaleido_init("snowflake")
    for _ in range(5):
        app._kaleido_step()
    app._draw_kaleido(40, 120)


def test_draw_with_info():
    app = _make_app()
    app._kaleido_init("snowflake")
    app.kaleido_show_info = True
    app._draw_kaleido(40, 120)


def test_draw_paint_mode():
    app = _make_app()
    app._kaleido_init("paint")
    app._kaleido_paint_at(20, 60)
    app._draw_kaleido(40, 120)


def test_draw_all_presets():
    for _name, _desc, key in KALEIDO_PRESETS:
        app = _make_app()
        app._kaleido_init(key)
        for _ in range(3):
            app._kaleido_step()
        app._draw_kaleido(40, 120)
