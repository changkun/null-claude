"""Tests for life.modes.fluid_rope — Fluid Rope / Honey Coiling mode."""
import curses
import math

from tests.conftest import make_mock_app
from life.modes.fluid_rope import (
    register,
    FLUIDROPE_PRESETS,
    _FLUIDROPE_POOL_CHARS,
    _FLUIDROPE_COIL_CHARS,
    _FLUIDROPE_SPLASH_CHARS,
)


def _make_app():
    app = make_mock_app()
    app.fluidrope_mode = False
    app.fluidrope_menu = False
    app.fluidrope_menu_sel = 0
    app.fluidrope_running = False
    app.fluidrope_dt = 0.02
    app.fluidrope_rope_segments = []
    app.fluidrope_pool = []
    app.fluidrope_trail = []
    register(type(app))
    return app


# ── Constants / presets ──


def test_presets_exist():
    assert len(FLUIDROPE_PRESETS) >= 4


def test_preset_keys_unique():
    keys = [p[2] for p in FLUIDROPE_PRESETS]
    assert len(keys) == len(set(keys))


def test_char_sets_non_empty():
    assert len(_FLUIDROPE_POOL_CHARS) > 0
    assert len(_FLUIDROPE_COIL_CHARS) > 0
    assert len(_FLUIDROPE_SPLASH_CHARS) > 0


# ── Enter / Exit ──


def test_enter():
    app = _make_app()
    app._enter_fluidrope_mode()
    assert app.fluidrope_mode is True
    assert app.fluidrope_menu is True
    assert app.fluidrope_running is False


def test_exit_cleanup():
    app = _make_app()
    app.fluidrope_mode = True
    app._fluidrope_init("honey")
    app._exit_fluidrope_mode()
    assert app.fluidrope_mode is False
    assert app.fluidrope_running is False
    assert app.fluidrope_rope_segments == []
    assert app.fluidrope_pool == []
    assert app.fluidrope_trail == []


# ── Init all presets ──


def test_init_honey():
    app = _make_app()
    app._fluidrope_init("honey")
    assert app.fluidrope_preset_name == "Honey"
    assert app.fluidrope_viscosity == 1.0
    assert app.fluidrope_running is True
    assert app.fluidrope_generation == 0
    assert app.fluidrope_dt == 0.02
    assert len(app.fluidrope_pool) == 120  # cols from mock


def test_init_chocolate():
    app = _make_app()
    app._fluidrope_init("chocolate")
    assert app.fluidrope_preset_name == "Chocolate"
    assert app.fluidrope_viscosity == 0.7
    assert app.fluidrope_flow_rate == 1.3


def test_init_shampoo():
    app = _make_app()
    app._fluidrope_init("shampoo")
    assert app.fluidrope_preset_name == "Shampoo"
    assert app.fluidrope_viscosity == 0.5
    assert app.fluidrope_coil_speed == 5.0


def test_init_lava():
    app = _make_app()
    app._fluidrope_init("lava")
    assert app.fluidrope_preset_name == "Lava"
    assert app.fluidrope_viscosity == 2.0
    assert app.fluidrope_coil_radius == 4.5


def test_init_sets_dt():
    """Regression: _fluidrope_init must set fluidrope_dt itself."""
    app = _make_app()
    # Remove any pre-set dt to verify init sets it
    del app.fluidrope_dt
    app._fluidrope_init("honey")
    assert hasattr(app, 'fluidrope_dt')
    assert app.fluidrope_dt == 0.02


def test_init_rope_segments_created():
    app = _make_app()
    app._fluidrope_init("honey")
    assert len(app.fluidrope_rope_segments) > 0
    # Each segment should be [x, y, vx, speed]
    seg = app.fluidrope_rope_segments[0]
    assert len(seg) == 4


def test_init_pool_size_matches_cols():
    app = _make_app()
    app._fluidrope_init("honey")
    assert len(app.fluidrope_pool) == app.fluidrope_cols


# ── Step physics ──


def test_step_no_crash():
    app = _make_app()
    app.fluidrope_mode = True
    app._fluidrope_init("honey")
    for _ in range(10):
        app._fluidrope_step()
    assert app.fluidrope_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._fluidrope_init("honey")
    t0 = app.fluidrope_time
    app._fluidrope_step()
    assert app.fluidrope_time > t0


def test_step_updates_coil_angle():
    app = _make_app()
    app._fluidrope_init("honey")
    angle0 = app.fluidrope_coil_angle
    app._fluidrope_step()
    assert app.fluidrope_coil_angle != angle0


def test_step_accumulates_pool():
    app = _make_app()
    app._fluidrope_init("honey")
    for _ in range(20):
        app._fluidrope_step()
    # Some pool columns should have accumulated fluid
    assert any(h > 0 for h in app.fluidrope_pool)


def test_step_pool_height_capped():
    app = _make_app()
    app._fluidrope_init("honey")
    for _ in range(500):
        app._fluidrope_step()
    max_pool = app.fluidrope_rows * 0.35
    assert all(h <= max_pool for h in app.fluidrope_pool)


def test_step_trail_limited():
    app = _make_app()
    app._fluidrope_init("honey")
    for _ in range(200):
        app._fluidrope_step()
    assert len(app.fluidrope_trail) <= 80


def test_step_pool_spreads():
    """Viscous spreading should make neighbors non-zero after depositing."""
    app = _make_app()
    app._fluidrope_init("honey")
    for _ in range(50):
        app._fluidrope_step()
    nonzero = sum(1 for h in app.fluidrope_pool if h > 0.01)
    assert nonzero > 1  # should spread to multiple columns


def test_step_surface_movement():
    app = _make_app()
    app._fluidrope_init("honey")
    app.fluidrope_surface_move = 1.0
    off0 = app.fluidrope_surface_offset
    app._fluidrope_step()
    assert app.fluidrope_surface_offset != off0


def test_step_all_presets():
    """All presets should step without error."""
    for _name, _desc, key in FLUIDROPE_PRESETS:
        app = _make_app()
        app._fluidrope_init(key)
        for _ in range(10):
            app._fluidrope_step()
        assert app.fluidrope_generation == 10


# ── Menu key handling ──


def test_menu_navigate_down():
    app = _make_app()
    app._enter_fluidrope_mode()
    app._handle_fluidrope_menu_key(curses.KEY_DOWN)
    assert app.fluidrope_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_fluidrope_mode()
    app._handle_fluidrope_menu_key(curses.KEY_UP)
    assert app.fluidrope_menu_sel == len(FLUIDROPE_PRESETS) - 1


def test_menu_navigate_j_k():
    app = _make_app()
    app._enter_fluidrope_mode()
    app._handle_fluidrope_menu_key(ord('j'))
    assert app.fluidrope_menu_sel == 1
    app._handle_fluidrope_menu_key(ord('k'))
    assert app.fluidrope_menu_sel == 0


def test_menu_enter_selects():
    app = _make_app()
    app._enter_fluidrope_mode()
    app._handle_fluidrope_menu_key(10)  # Enter key
    assert app.fluidrope_running is True
    assert app.fluidrope_menu is False


def test_menu_quit():
    app = _make_app()
    app._enter_fluidrope_mode()
    app._handle_fluidrope_menu_key(ord('q'))
    assert app.fluidrope_mode is False


# ── Simulation key handling ──


def test_key_space_toggles_running():
    app = _make_app()
    app._fluidrope_init("honey")
    assert app.fluidrope_running is True
    app._handle_fluidrope_key(ord(' '))
    assert app.fluidrope_running is False
    app._handle_fluidrope_key(ord(' '))
    assert app.fluidrope_running is True


def test_key_n_steps():
    app = _make_app()
    app._fluidrope_init("honey")
    gen0 = app.fluidrope_generation
    app._handle_fluidrope_key(ord('n'))
    assert app.fluidrope_generation == gen0 + 1


def test_key_plus_increases_speed():
    app = _make_app()
    app._fluidrope_init("honey")
    s0 = app.fluidrope_speed
    app._handle_fluidrope_key(ord('+'))
    assert app.fluidrope_speed == s0 + 1


def test_key_minus_decreases_speed():
    app = _make_app()
    app._fluidrope_init("honey")
    s0 = app.fluidrope_speed
    app._handle_fluidrope_key(ord('-'))
    assert app.fluidrope_speed == s0 - 1


def test_key_speed_min_max():
    app = _make_app()
    app._fluidrope_init("honey")
    app.fluidrope_speed = 1
    app._handle_fluidrope_key(ord('-'))
    assert app.fluidrope_speed == 1  # clamped at 1
    app.fluidrope_speed = 10
    app._handle_fluidrope_key(ord('+'))
    assert app.fluidrope_speed == 10  # clamped at 10


def test_key_h_increases_pour_height():
    app = _make_app()
    app._fluidrope_init("honey")
    h0 = app.fluidrope_pour_height
    app._handle_fluidrope_key(ord('h'))
    assert app.fluidrope_pour_height > h0


def test_key_H_decreases_pour_height():
    app = _make_app()
    app._fluidrope_init("honey")
    h0 = app.fluidrope_pour_height
    app._handle_fluidrope_key(ord('H'))
    assert app.fluidrope_pour_height < h0


def test_key_pour_height_clamped():
    app = _make_app()
    app._fluidrope_init("honey")
    app.fluidrope_pour_height = 0.85
    app._handle_fluidrope_key(ord('h'))
    assert app.fluidrope_pour_height <= 0.85
    app.fluidrope_pour_height = 0.3
    app._handle_fluidrope_key(ord('H'))
    assert app.fluidrope_pour_height >= 0.3


def test_key_f_increases_flow_rate():
    app = _make_app()
    app._fluidrope_init("honey")
    f0 = app.fluidrope_flow_rate
    app._handle_fluidrope_key(ord('f'))
    assert app.fluidrope_flow_rate > f0


def test_key_v_increases_viscosity():
    app = _make_app()
    app._fluidrope_init("honey")
    v0 = app.fluidrope_viscosity
    app._handle_fluidrope_key(ord('v'))
    assert app.fluidrope_viscosity > v0


def test_key_s_surface_move():
    app = _make_app()
    app._fluidrope_init("honey")
    app._handle_fluidrope_key(ord('s'))
    assert app.fluidrope_surface_move == 0.5
    app._handle_fluidrope_key(ord('S'))
    assert app.fluidrope_surface_move == 0.0


def test_key_0_resets_surface():
    app = _make_app()
    app._fluidrope_init("honey")
    app.fluidrope_surface_move = 2.0
    app.fluidrope_surface_offset = 5.0
    app._handle_fluidrope_key(ord('0'))
    assert app.fluidrope_surface_move == 0.0
    assert app.fluidrope_surface_offset == 0.0


def test_key_i_toggles_info():
    app = _make_app()
    app._fluidrope_init("honey")
    assert app.fluidrope_show_info is False
    app._handle_fluidrope_key(ord('i'))
    assert app.fluidrope_show_info is True
    app._handle_fluidrope_key(ord('i'))
    assert app.fluidrope_show_info is False


def test_key_r_resets_preset():
    app = _make_app()
    app._fluidrope_init("honey")
    for _ in range(20):
        app._fluidrope_step()
    app._handle_fluidrope_key(ord('r'))
    assert app.fluidrope_generation == 0
    assert app.fluidrope_time == 0.0


def test_key_R_returns_to_menu():
    app = _make_app()
    app._fluidrope_init("honey")
    app._handle_fluidrope_key(ord('R'))
    assert app.fluidrope_menu is True
    assert app.fluidrope_running is False


def test_key_m_returns_to_menu():
    app = _make_app()
    app._fluidrope_init("honey")
    app._handle_fluidrope_key(ord('m'))
    assert app.fluidrope_menu is True


def test_key_q_exits():
    app = _make_app()
    app._fluidrope_init("honey")
    app._handle_fluidrope_key(ord('q'))
    assert app.fluidrope_mode is False


# ── Draw functions ──


def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_fluidrope_mode()
    app._draw_fluidrope_menu(40, 120)


def test_draw_menu_small_terminal():
    app = _make_app()
    app._enter_fluidrope_mode()
    # Should not crash with very small terminal
    app._draw_fluidrope_menu(3, 15)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._fluidrope_init("honey")
    for _ in range(5):
        app._fluidrope_step()
    app._draw_fluidrope(40, 120)


def test_draw_simulation_small_terminal():
    app = _make_app()
    app._fluidrope_init("honey")
    # Should bail out gracefully for tiny terminals
    app._draw_fluidrope(3, 5)


# ── Rope segment physics ──


def test_rope_segments_reconstruct_on_resize():
    """If segment count doesn't match, segments should be rebuilt."""
    app = _make_app()
    app._fluidrope_init("honey")
    original_count = len(app.fluidrope_rope_segments)
    assert original_count > 0
    # Corrupt segment count
    app.fluidrope_rope_segments = app.fluidrope_rope_segments[:2]
    app._fluidrope_step()
    # Step should rebuild segments
    assert len(app.fluidrope_rope_segments) > 2


def test_rope_segments_have_gravity_acceleration():
    """Speed should increase along the stream (gravity effect)."""
    app = _make_app()
    app._fluidrope_init("honey")
    segs = app.fluidrope_rope_segments
    if len(segs) >= 2:
        assert segs[-1][3] >= segs[0][3]  # bottom faster than top
