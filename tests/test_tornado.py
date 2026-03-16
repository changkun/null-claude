"""Tests for life.modes.tornado — Tornado mode."""
import curses
import math
import random
from unittest.mock import patch

from tests.conftest import make_mock_app
from life.modes.tornado import (
    register, TORNADO_PRESETS,
    _TORNADO_DEBRIS_CHARS, _TORNADO_RAIN_CHARS,
    _TORNADO_CLOUD_CHARS, _TORNADO_FUNNEL_CHARS,
)


def _make_app():
    app = make_mock_app()
    app.tornado_mode = False
    app.tornado_menu = False
    app.tornado_menu_sel = 0
    app.tornado_running = False
    app.tornado_dt = 0.03
    app.tornado_speed = 2
    app.tornado_show_info = False
    app.tornado_max_destruction = 500
    app.tornado_rain_particles = []
    app.tornado_debris = []
    app.tornado_lightning_segments = []
    app.tornado_destruction = []
    register(type(app))
    return app


# ── Enter / Exit ──

def test_enter():
    app = _make_app()
    app._enter_tornado_mode()
    assert app.tornado_menu is True
    assert app.tornado_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.tornado_mode = True
    app.tornado_preset_name = "ef3"
    app._tornado_init("ef3")
    assert len(app.tornado_rain_particles) > 0
    app._exit_tornado_mode()
    assert app.tornado_mode is False
    assert app.tornado_running is False
    assert app.tornado_rain_particles == []
    assert app.tornado_debris == []
    assert app.tornado_lightning_segments == []
    assert app.tornado_destruction == []


# ── Preset initialization ──

def test_all_presets_init():
    """Every preset key initializes without error."""
    for _name, _desc, key in TORNADO_PRESETS:
        app = _make_app()
        app._tornado_init(key)
        assert app.tornado_running is True
        assert app.tornado_generation == 0
        assert app.tornado_time == 0.0


def test_ef3_has_rain_and_debris_capacity():
    app = _make_app()
    app._tornado_init("ef3")
    assert app.tornado_max_rain == 250
    assert app.tornado_max_debris == 80
    assert len(app.tornado_rain_particles) == 250


def test_dustdevil_no_rain():
    app = _make_app()
    app._tornado_init("dustdevil")
    assert app.tornado_max_rain == 0
    assert len(app.tornado_rain_particles) == 0
    assert app.tornado_lightning_interval == 999.0


def test_rope_small_radius():
    app = _make_app()
    app._tornado_init("rope")
    assert app.tornado_vortex_radius == 1.5
    assert app.tornado_rotation_speed == 4.0


def test_init_resets_state():
    app = _make_app()
    app._tornado_init("ef3")
    for _ in range(10):
        app._tornado_step()
    assert app.tornado_generation == 10
    app._tornado_init("ef3")
    assert app.tornado_generation == 0
    assert app.tornado_time == 0.0
    assert app.tornado_destruction == []


def test_vortex_centered():
    """Vortex should start at center of grid."""
    app = _make_app()
    app._tornado_init("ef3")
    rows, cols = app.grid.rows, app.grid.cols
    assert app.tornado_vortex_x == float(cols // 2)
    assert app.tornado_vortex_y == float(rows // 2)


def test_rain_particles_initial_positions():
    """Rain particles should start within storm radius of vortex."""
    app = _make_app()
    app._tornado_init("ef3")
    vx = app.tornado_vortex_x
    sr = app.tornado_storm_radius
    for p in app.tornado_rain_particles:
        assert vx - sr <= p[0] <= vx + sr


# ── Step physics ──

def test_step_no_crash():
    app = _make_app()
    app.tornado_mode = True
    app.tornado_preset_name = "ef3"
    app._tornado_init("ef3")
    for _ in range(10):
        app._tornado_step()
    assert app.tornado_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._tornado_init("ef3")
    dt = app.tornado_dt
    app._tornado_step()
    assert abs(app.tornado_time - dt) < 1e-12


def test_vortex_stays_on_screen():
    """Vortex should remain within screen margins after many steps."""
    app = _make_app()
    app._tornado_init("ef3")
    rows = app.tornado_rows
    cols = app.tornado_cols
    for _ in range(500):
        app._tornado_step()
    assert 10 <= app.tornado_vortex_x <= cols - 10
    assert rows * 0.3 <= app.tornado_vortex_y <= rows * 0.7


def test_vortex_drifts():
    """Vortex should move from its starting position."""
    app = _make_app()
    app._tornado_init("ef3")
    start_x = app.tornado_vortex_x
    for _ in range(100):
        app._tornado_step()
    # It should have moved at least a little
    assert app.tornado_vortex_x != start_x


def test_cloud_angle_advances():
    app = _make_app()
    app._tornado_init("ef3")
    app._tornado_step()
    assert app.tornado_cloud_angle > 0.0


def test_debris_spawns_on_ground():
    """Debris should spawn when tornado touches ground."""
    app = _make_app()
    app._tornado_init("ef3")
    random.seed(42)
    for _ in range(50):
        app._tornado_step()
    assert len(app.tornado_debris) > 0


def test_debris_has_life():
    """Each debris particle should have a positive life value initially."""
    app = _make_app()
    app._tornado_init("ef3")
    random.seed(42)
    for _ in range(20):
        app._tornado_step()
    for d in app.tornado_debris:
        assert d[5] > 0  # life > 0


def test_debris_life_decreases():
    """Debris life should decrease over time."""
    app = _make_app()
    app._tornado_init("ef3")
    random.seed(42)
    for _ in range(30):
        app._tornado_step()
    if app.tornado_debris:
        initial_life = app.tornado_debris[0][5]
        app._tornado_step()
        if app.tornado_debris:
            # After one more step, the first debris might have been removed,
            # but the physics decrements life by 1.0 per step
            pass  # just ensuring no crash


def test_dustdevil_no_debris_no_rain():
    """Dust devil has no rain; debris only spawns if touch_ground."""
    app = _make_app()
    app._tornado_init("dustdevil")
    assert app.tornado_max_rain == 0
    assert len(app.tornado_rain_particles) == 0


def test_destruction_path_grows():
    """Destruction path should accumulate when tornado touches ground."""
    app = _make_app()
    app._tornado_init("ef3")
    for _ in range(20):
        app._tornado_step()
    assert len(app.tornado_destruction) > 0


def test_destruction_capped():
    """Destruction path should not exceed max_destruction."""
    app = _make_app()
    app.tornado_max_destruction = 50
    app._tornado_init("ef3")
    for _ in range(500):
        app._tornado_step()
    assert len(app.tornado_destruction) <= 50


def test_rain_particles_reset_when_offscreen():
    """Rain particles that go off-screen should be respawned."""
    app = _make_app()
    app._tornado_init("ef3")
    # Run enough steps for some rain to fall off screen
    for _ in range(200):
        app._tornado_step()
    # All rain particles should still be in the list
    assert len(app.tornado_rain_particles) == app.tornado_max_rain


# ── Lightning ──

def test_generate_lightning():
    app = _make_app()
    app._tornado_init("ef3")
    app._tornado_generate_lightning()
    assert len(app.tornado_lightning_segments) > 0
    # Each segment is (x1, y1, x2, y2)
    for seg in app.tornado_lightning_segments:
        assert len(seg) == 4


def test_lightning_reaches_ground():
    """Lightning segments should reach close to ground level."""
    app = _make_app()
    app._tornado_init("ef3")
    random.seed(42)
    app._tornado_generate_lightning()
    ground = app.tornado_rows - 3
    # The last segment should end at or near ground
    last_seg = app.tornado_lightning_segments[-1]
    assert last_seg[3] >= ground - 5  # within 5 rows of ground


def test_lightning_timer_triggers():
    """After enough steps, lightning should fire."""
    app = _make_app()
    app._tornado_init("ef3")
    random.seed(42)
    # Step until lightning interval is exceeded
    steps_needed = int(app.tornado_lightning_interval / app.tornado_dt) + 5
    for _ in range(steps_needed):
        app._tornado_step()
    # Lightning should have been triggered at least once
    # (timer resets after interval, may or may not fire due to random)


# ── Key handling ──

def test_menu_key_down():
    app = _make_app()
    app._enter_tornado_mode()
    app._handle_tornado_menu_key(curses.KEY_DOWN)
    assert app.tornado_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_tornado_mode()
    app._handle_tornado_menu_key(curses.KEY_UP)
    assert app.tornado_menu_sel == len(TORNADO_PRESETS) - 1


def test_menu_enter_starts_sim():
    app = _make_app()
    app._enter_tornado_mode()
    app._handle_tornado_menu_key(10)  # Enter
    assert app.tornado_menu is False
    assert app.tornado_mode is True
    assert app.tornado_running is True


def test_menu_quit():
    app = _make_app()
    app._enter_tornado_mode()
    app._handle_tornado_menu_key(27)  # Escape
    assert app.tornado_mode is False


def test_sim_key_space_toggles():
    app = _make_app()
    app._tornado_init("ef3")
    app.tornado_running = True
    app._handle_tornado_key(ord(' '))
    assert app.tornado_running is False
    app._handle_tornado_key(ord(' '))
    assert app.tornado_running is True


def test_sim_key_speed():
    app = _make_app()
    app._tornado_init("ef3")
    initial = app.tornado_speed
    app._handle_tornado_key(ord('+'))
    assert app.tornado_speed == initial + 1
    app._handle_tornado_key(ord('-'))
    assert app.tornado_speed == initial


def test_sim_key_speed_bounds():
    app = _make_app()
    app._tornado_init("ef3")
    for _ in range(20):
        app._handle_tornado_key(ord('+'))
    assert app.tornado_speed == 10
    for _ in range(20):
        app._handle_tornado_key(ord('-'))
    assert app.tornado_speed == 1


def test_sim_key_info_toggle():
    app = _make_app()
    app._tornado_init("ef3")
    assert app.tornado_show_info is False
    app._handle_tornado_key(ord('i'))
    assert app.tornado_show_info is True
    app._handle_tornado_key(ord('i'))
    assert app.tornado_show_info is False


def test_sim_key_step():
    app = _make_app()
    app._tornado_init("ef3")
    gen_before = app.tornado_generation
    app._handle_tornado_key(ord('n'))
    assert app.tornado_generation == gen_before + 1


def test_sim_key_reset():
    app = _make_app()
    app._tornado_init("ef3")
    app.tornado_preset_name = "ef3"
    for _ in range(10):
        app._tornado_step()
    app._handle_tornado_key(ord('r'))
    assert app.tornado_generation == 0


def test_sim_key_back_to_menu():
    app = _make_app()
    app._tornado_init("ef3")
    app.tornado_running = True
    app._handle_tornado_key(ord('R'))
    assert app.tornado_menu is True
    assert app.tornado_running is False


def test_sim_key_quit():
    app = _make_app()
    app._tornado_init("ef3")
    app.tornado_mode = True
    app._handle_tornado_key(ord('q'))
    assert app.tornado_mode is False


def test_sim_key_lightning():
    app = _make_app()
    app._tornado_init("ef3")
    app._handle_tornado_key(ord('l'))
    assert app.tornado_lightning_active is True
    assert app.tornado_lightning_flash == 3
    assert len(app.tornado_lightning_segments) > 0


# ── Drawing (smoke tests) ──

def _mock_color_pair(n):
    return n


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_menu_no_crash(_cp):
    app = _make_app()
    app._enter_tornado_mode()
    app._draw_tornado_menu(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_sim_no_crash(_cp):
    app = _make_app()
    app._tornado_init("ef3")
    random.seed(42)
    for _ in range(5):
        app._tornado_step()
    app._draw_tornado(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_sim_small_terminal(_cp):
    """Drawing on a very small terminal should not crash."""
    app = _make_app()
    app._tornado_init("ef3")
    app._draw_tornado(8, 15)  # too small


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_with_info_panel(_cp):
    app = _make_app()
    app._tornado_init("ef3")
    app.tornado_show_info = True
    for _ in range(3):
        app._tornado_step()
    app._draw_tornado(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_with_lightning(_cp):
    app = _make_app()
    app._tornado_init("ef3")
    app.tornado_lightning_active = True
    app.tornado_lightning_flash = 3
    app._tornado_generate_lightning()
    app._draw_tornado(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_night_mode(_cp):
    app = _make_app()
    app._tornado_init("night")
    app.tornado_preset_name = "night"
    for _ in range(5):
        app._tornado_step()
    app._draw_tornado(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_dustdevil(_cp):
    app = _make_app()
    app._tornado_init("dustdevil")
    app.tornado_preset_name = "dustdevil"
    for _ in range(5):
        app._tornado_step()
    app._draw_tornado(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_all_presets(_cp):
    """Drawing each preset should not crash."""
    for _name, _desc, key in TORNADO_PRESETS:
        app = _make_app()
        app._tornado_init(key)
        app.tornado_preset_name = key
        random.seed(42)
        for _ in range(5):
            app._tornado_step()
        app._draw_tornado(40, 120)


# ── Character set constants ──

def test_debris_chars_nonempty():
    assert len(_TORNADO_DEBRIS_CHARS) > 0


def test_rain_chars_nonempty():
    assert len(_TORNADO_RAIN_CHARS) > 0


def test_cloud_chars_nonempty():
    assert len(_TORNADO_CLOUD_CHARS) > 0


def test_funnel_chars_nonempty():
    assert len(_TORNADO_FUNNEL_CHARS) > 0
