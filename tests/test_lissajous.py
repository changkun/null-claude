"""Tests for life.modes.lissajous — Lissajous Curve / Harmonograph mode."""
import curses
import math

from tests.conftest import make_mock_app
from life.modes.lissajous import (
    register,
    LISSAJOUS_PRESETS,
    LISSAJOUS_CHARS,
    _lissajous_preview_art,
)


def _make_app():
    app = make_mock_app()
    app.lissajous_mode = False
    app.lissajous_menu = False
    app.lissajous_menu_sel = 0
    app.lissajous_running = False
    app.lissajous_show_info = False
    app.lissajous_trail = []
    app.lissajous_canvas = {}
    register(type(app))
    return app


# ── Constants / presets ──


def test_presets_exist():
    assert len(LISSAJOUS_PRESETS) >= 8


def test_preset_keys_unique():
    keys = [p[2] for p in LISSAJOUS_PRESETS]
    assert len(keys) == len(set(keys))


def test_chars_non_empty():
    assert len(LISSAJOUS_CHARS) > 0


# ── Enter / Exit ──


def test_enter():
    app = _make_app()
    app._enter_lissajous_mode()
    assert app.lissajous_mode is True
    assert app.lissajous_menu is True
    assert app.lissajous_running is False


def test_exit_cleanup():
    app = _make_app()
    app.lissajous_mode = True
    app._lissajous_init("classic_3_2")
    app._exit_lissajous_mode()
    assert app.lissajous_mode is False
    assert app.lissajous_running is False
    assert app.lissajous_trail == []
    assert app.lissajous_canvas == {}


# ── Init all presets ──


def test_init_classic():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    assert app.lissajous_freq_a == 3.0
    assert app.lissajous_freq_b == 2.0
    assert app.lissajous_phase == math.pi / 4
    assert app.lissajous_damping == 0.0
    assert app.lissajous_running is True


def test_init_figure_eight():
    app = _make_app()
    app._lissajous_init("figure_eight")
    assert app.lissajous_freq_a == 2.0
    assert app.lissajous_freq_b == 1.0
    assert app.lissajous_phase == math.pi / 2


def test_init_star():
    app = _make_app()
    app._lissajous_init("star")
    assert app.lissajous_freq_a == 5.0
    assert app.lissajous_freq_b == 4.0


def test_init_harmonograph():
    app = _make_app()
    app._lissajous_init("harmonograph")
    assert app.lissajous_damping == 0.003
    assert app.lissajous_max_trail == 8000


def test_init_lateral():
    app = _make_app()
    app._lissajous_init("lateral")
    assert app.lissajous_freq_c != 0.0
    assert app.lissajous_freq_d != 0.0
    assert app.lissajous_phase2 != 0.0
    assert app.lissajous_max_trail == 10000


def test_init_rose():
    app = _make_app()
    app._lissajous_init("rose")
    assert app.lissajous_freq_a == 7.0
    assert app.lissajous_freq_b == 4.0
    assert app.lissajous_phase == 0.0


def test_init_decay_spiral():
    app = _make_app()
    app._lissajous_init("decay_spiral")
    assert app.lissajous_freq_a == 10.0
    assert app.lissajous_damping == 0.008


def test_init_knot():
    app = _make_app()
    app._lissajous_init("knot")
    assert app.lissajous_freq_a == 5.0
    assert app.lissajous_freq_b == 3.0
    assert app.lissajous_damping == 0.001


def test_init_all_presets():
    """All presets should initialize without error."""
    for _name, _desc, key in LISSAJOUS_PRESETS:
        app = _make_app()
        app._lissajous_init(key)
        assert app.lissajous_running is True


# ── Step physics ──


def test_step_no_crash():
    app = _make_app()
    app.lissajous_mode = True
    app._lissajous_init("classic_3_2")
    for _ in range(10):
        app._lissajous_step()
    assert app.lissajous_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    t0 = app.lissajous_time
    app._lissajous_step()
    assert app.lissajous_time > t0
    assert abs(app.lissajous_time - t0 - app.lissajous_dt) < 1e-10


def test_step_adds_trail():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app._lissajous_step()
    assert len(app.lissajous_trail) == 1


def test_step_trail_capped():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app.lissajous_max_trail = 50
    for _ in range(100):
        app._lissajous_step()
    assert len(app.lissajous_trail) <= 50


def test_step_updates_canvas():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    for _ in range(10):
        app._lissajous_step()
    assert len(app.lissajous_canvas) > 0


def test_step_canvas_intensity_capped():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    for _ in range(1000):
        app._lissajous_step()
    for intensity in app.lissajous_canvas.values():
        assert intensity <= 1.0


def test_step_pen_position_within_bounds():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    for _ in range(50):
        app._lissajous_step()
    # Pen should be within screen bounds (roughly)
    assert 0 <= app.lissajous_pen_x <= app.lissajous_cols
    assert 0 <= app.lissajous_pen_y <= app.lissajous_rows


def test_step_damped_decay():
    """Damped presets should have decaying amplitude over time."""
    app = _make_app()
    app._lissajous_init("decay_spiral")
    positions = []
    for _ in range(200):
        app._lissajous_step()
        positions.append((app.lissajous_pen_x, app.lissajous_pen_y))
    # Center of screen
    cx = app.lissajous_cols / 2
    cy = app.lissajous_rows / 2
    # Early points should be farther from center than late points
    early_dist = sum(math.sqrt((x - cx)**2 + (y - cy)**2) for x, y in positions[:20]) / 20
    late_dist = sum(math.sqrt((x - cx)**2 + (y - cy)**2) for x, y in positions[-20:]) / 20
    assert late_dist < early_dist


def test_step_harmonograph_secondary_oscillators():
    """Lateral preset uses secondary oscillators that affect position."""
    app = _make_app()
    app._lissajous_init("lateral")
    app._lissajous_step()
    # With secondary oscillators, position should differ from simple case
    assert app.lissajous_freq_c != 0.0
    assert app.lissajous_freq_d != 0.0


def test_step_interpolation_smooths_lines():
    """When pen moves far between steps, intermediate points should be filled."""
    app = _make_app()
    app._lissajous_init("classic_3_2")
    # Run enough steps for trail to have at least 2 points
    for _ in range(20):
        app._lissajous_step()
    # Canvas should have more points than trail due to interpolation
    assert len(app.lissajous_canvas) >= len(app.lissajous_trail)


def test_step_all_presets():
    """All presets should step without error."""
    for _name, _desc, key in LISSAJOUS_PRESETS:
        app = _make_app()
        app._lissajous_init(key)
        for _ in range(20):
            app._lissajous_step()
        assert app.lissajous_generation == 20


# ── Menu key handling ──


def test_menu_navigate_down():
    app = _make_app()
    app._enter_lissajous_mode()
    app._handle_lissajous_menu_key(curses.KEY_DOWN)
    assert app.lissajous_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_lissajous_mode()
    app._handle_lissajous_menu_key(curses.KEY_UP)
    assert app.lissajous_menu_sel == len(LISSAJOUS_PRESETS) - 1


def test_menu_j_k():
    app = _make_app()
    app._enter_lissajous_mode()
    app._handle_lissajous_menu_key(ord('j'))
    assert app.lissajous_menu_sel == 1
    app._handle_lissajous_menu_key(ord('k'))
    assert app.lissajous_menu_sel == 0


def test_menu_enter_selects():
    app = _make_app()
    app._enter_lissajous_mode()
    app._handle_lissajous_menu_key(10)
    assert app.lissajous_running is True
    assert app.lissajous_menu is False


def test_menu_quit():
    app = _make_app()
    app._enter_lissajous_mode()
    app._handle_lissajous_menu_key(ord('q'))
    assert app.lissajous_mode is False


# ── Simulation key handling ──


def test_key_space_toggles():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    assert app.lissajous_running is True
    app._handle_lissajous_key(ord(' '))
    assert app.lissajous_running is False
    app._handle_lissajous_key(ord(' '))
    assert app.lissajous_running is True


def test_key_n_steps():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    gen0 = app.lissajous_generation
    app._handle_lissajous_key(ord('n'))
    assert app.lissajous_generation == gen0 + 1


def test_key_plus_minus_speed():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    s0 = app.lissajous_speed
    app._handle_lissajous_key(ord('+'))
    assert app.lissajous_speed == s0 + 1
    app._handle_lissajous_key(ord('-'))
    assert app.lissajous_speed == s0


def test_key_speed_clamped():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app.lissajous_speed = 1
    app._handle_lissajous_key(ord('-'))
    assert app.lissajous_speed == 1
    app.lissajous_speed = 10
    app._handle_lissajous_key(ord('+'))
    assert app.lissajous_speed == 10


def test_key_a_increases_freq_a():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    fa0 = app.lissajous_freq_a
    app._handle_lissajous_key(ord('a'))
    assert app.lissajous_freq_a > fa0


def test_key_A_decreases_freq_a():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    fa0 = app.lissajous_freq_a
    app._handle_lissajous_key(ord('A'))
    assert app.lissajous_freq_a < fa0


def test_key_freq_a_min():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app.lissajous_freq_a = 0.1
    app._handle_lissajous_key(ord('A'))
    assert app.lissajous_freq_a >= 0.1


def test_key_b_adjusts_freq_b():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    fb0 = app.lissajous_freq_b
    app._handle_lissajous_key(ord('b'))
    assert app.lissajous_freq_b > fb0
    app._handle_lissajous_key(ord('B'))
    assert abs(app.lissajous_freq_b - fb0) < 0.001


def test_key_p_adjusts_phase():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    p0 = app.lissajous_phase
    app._handle_lissajous_key(ord('p'))
    assert app.lissajous_phase > p0
    app._handle_lissajous_key(ord('P'))
    assert abs(app.lissajous_phase - p0) < 0.001


def test_key_d_adjusts_damping():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    assert app.lissajous_damping == 0.0
    app._handle_lissajous_key(ord('d'))
    assert app.lissajous_damping == 0.001
    app._handle_lissajous_key(ord('D'))
    assert app.lissajous_damping == 0.0


def test_key_damping_clamped():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app.lissajous_damping = 0.1
    app._handle_lissajous_key(ord('d'))
    assert app.lissajous_damping <= 0.1
    app.lissajous_damping = 0.0
    app._handle_lissajous_key(ord('D'))
    assert app.lissajous_damping >= 0.0


def test_key_c_clears():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    for _ in range(50):
        app._lissajous_step()
    assert len(app.lissajous_canvas) > 0
    app._handle_lissajous_key(ord('c'))
    assert app.lissajous_canvas == {}
    assert app.lissajous_trail == []
    assert app.lissajous_time == 0.0
    assert app.lissajous_generation == 0


def test_key_i_toggles_info():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    assert app.lissajous_show_info is False
    app._handle_lissajous_key(ord('i'))
    assert app.lissajous_show_info is True
    app._handle_lissajous_key(ord('i'))
    assert app.lissajous_show_info is False


def test_key_r_resets():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    for _ in range(20):
        app._lissajous_step()
    app._handle_lissajous_key(ord('r'))
    assert app.lissajous_generation == 0
    assert app.lissajous_time == 0.0


def test_key_R_returns_to_menu():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app._handle_lissajous_key(ord('R'))
    assert app.lissajous_menu is True
    assert app.lissajous_running is False


def test_key_q_exits():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app._handle_lissajous_key(ord('q'))
    assert app.lissajous_mode is False


# ── Preview art ──


def test_preview_art_returns_lines():
    lines = _lissajous_preview_art("classic_3_2")
    assert isinstance(lines, list)
    assert len(lines) == 12  # h = 12


def test_preview_art_all_presets():
    for _name, _desc, key in LISSAJOUS_PRESETS:
        lines = _lissajous_preview_art(key)
        assert len(lines) == 12
        for line in lines:
            assert len(line) == 30  # w = 30


def test_preview_art_has_content():
    """Preview should have some non-space characters."""
    lines = _lissajous_preview_art("classic_3_2")
    total = "".join(lines)
    assert any(c != ' ' for c in total)


def test_preview_art_callable_as_staticmethod():
    """Regression: _lissajous_preview_art registered as staticmethod should work."""
    app = _make_app()
    # Should be callable via the class without passing self
    result = type(app)._lissajous_preview_art("classic_3_2")
    assert isinstance(result, list)


# ── Draw functions ──


def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_lissajous_mode()
    app._draw_lissajous_menu(40, 120)


def test_draw_menu_small_terminal():
    app = _make_app()
    app._enter_lissajous_mode()
    app._draw_lissajous_menu(10, 30)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    for _ in range(10):
        app._lissajous_step()
    app._draw_lissajous(40, 120)


def test_draw_simulation_with_info():
    app = _make_app()
    app._lissajous_init("lateral")
    for _ in range(10):
        app._lissajous_step()
    app.lissajous_show_info = True
    app._draw_lissajous(40, 120)


def test_draw_simulation_paused():
    app = _make_app()
    app._lissajous_init("classic_3_2")
    app.lissajous_running = False
    app._draw_lissajous(40, 120)
