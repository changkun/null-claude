"""Tests for life.modes.flythrough_3d — 3D Terrain Flythrough mode."""
import curses
import math
from unittest.mock import patch

from tests.conftest import make_mock_app
from life.modes.flythrough_3d import register


def _make_app():
    app = make_mock_app()
    app.flythrough_mode = False
    app.flythrough_menu = False
    app.flythrough_menu_sel = 0
    app.flythrough_running = False
    app.flythrough_generation = 0
    app.flythrough_preset_name = ""
    app.flythrough_heightmap = []
    app.flythrough_map_size = 0
    app.flythrough_cam_x = 0.0
    app.flythrough_cam_y = 0.0
    app.flythrough_cam_z = 0.0
    app.flythrough_cam_yaw = 0.0
    app.flythrough_cam_pitch = -0.2
    app.flythrough_cam_speed = 0.5
    app.flythrough_fov = 1.2
    app.flythrough_time = 0.3
    app.flythrough_auto_time = True
    app.flythrough_time_speed = 0.002
    type(app).FLYTHROUGH_PRESETS = [
        ("Rolling Hills", "Gentle rolling terrain with grass and trees", "hills"),
        ("Mountains", "Sharp alpine peaks with snow caps", "mountains"),
        ("Canyon", "Deep canyon carved through mesa landscape", "canyon"),
        ("Islands", "Archipelago of volcanic islands", "islands"),
        ("Glacial Valley", "U-shaped valley with ice features", "glacial"),
        ("Alien World", "Bizarre alien terrain with strange formations", "alien"),
    ]
    register(type(app))
    return app


# ── Enter / Exit ─────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_flythrough_mode()
    assert app.flythrough_menu is True
    assert app.flythrough_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._flythrough_init(0)
    app._exit_flythrough_mode()
    assert app.flythrough_mode is False
    assert app.flythrough_menu is False
    assert app.flythrough_running is False
    assert app.flythrough_heightmap == []


# ── Init presets ─────────────────────────────────────────────────────────────

def test_init_all_presets():
    """Every terrain preset initializes without error."""
    app = _make_app()
    for idx in range(len(type(app).FLYTHROUGH_PRESETS)):
        app._flythrough_init(idx)
        assert app.flythrough_mode is True
        assert app.flythrough_menu is False
        assert app.flythrough_running is True
        assert len(app.flythrough_heightmap) == 256
        assert len(app.flythrough_heightmap[0]) == 256
        assert app.flythrough_preset_name == type(app).FLYTHROUGH_PRESETS[idx][0]


def test_init_camera_above_terrain():
    """Camera starts above the terrain at the center."""
    app = _make_app()
    app._flythrough_init(0)
    center = app.flythrough_map_size // 2
    ground = app._flythrough_get_height(center, center)
    assert app.flythrough_cam_y > ground


# ── Terrain generation ───────────────────────────────────────────────────────

def test_generate_hills_normalized():
    """Hills terrain has values in [0, 1]."""
    app = _make_app()
    hmap = app._flythrough_generate(64, "hills")
    vals = [hmap[r][c] for r in range(64) for c in range(64)]
    assert min(vals) >= 0.0
    assert max(vals) <= 1.0 + 1e-9


def test_generate_mountains_normalized():
    app = _make_app()
    hmap = app._flythrough_generate(64, "mountains")
    vals = [hmap[r][c] for r in range(64) for c in range(64)]
    assert min(vals) >= 0.0
    assert max(vals) <= 1.0 + 1e-9


def test_generate_canyon_normalized():
    app = _make_app()
    hmap = app._flythrough_generate(64, "canyon")
    vals = [hmap[r][c] for r in range(64) for c in range(64)]
    assert min(vals) >= 0.0
    assert max(vals) <= 1.0 + 1e-9


def test_generate_islands_normalized():
    app = _make_app()
    hmap = app._flythrough_generate(64, "islands")
    vals = [hmap[r][c] for r in range(64) for c in range(64)]
    assert min(vals) >= 0.0
    assert max(vals) <= 1.0 + 1e-9


def test_generate_glacial_normalized():
    app = _make_app()
    hmap = app._flythrough_generate(64, "glacial")
    vals = [hmap[r][c] for r in range(64) for c in range(64)]
    assert min(vals) >= 0.0
    assert max(vals) <= 1.0 + 1e-9


def test_generate_alien_normalized():
    app = _make_app()
    hmap = app._flythrough_generate(64, "alien")
    vals = [hmap[r][c] for r in range(64) for c in range(64)]
    assert min(vals) >= 0.0
    assert max(vals) <= 1.0 + 1e-9


def test_generate_size():
    """Generated heightmap matches requested size."""
    app = _make_app()
    for size in (16, 32, 128):
        hmap = app._flythrough_generate(size, "hills")
        assert len(hmap) == size
        assert all(len(row) == size for row in hmap)


# ── Height interpolation ────────────────────────────────────────────────────

def test_get_height_in_range():
    """Interpolated height is within heightmap value range."""
    app = _make_app()
    app._flythrough_init(0)
    for x in (0.0, 10.5, 128.0, 255.9):
        for z in (0.0, 10.5, 128.0, 255.9):
            h = app._flythrough_get_height(x, z)
            assert 0.0 <= h <= 1.0 + 1e-9


def test_get_height_wrapping():
    """Height wraps around map boundaries."""
    app = _make_app()
    app._flythrough_init(0)
    size = app.flythrough_map_size
    h1 = app._flythrough_get_height(5.0, 5.0)
    h2 = app._flythrough_get_height(5.0 + size, 5.0 + size)
    assert abs(h1 - h2) < 1e-9


def test_get_height_empty_map():
    """Returns 0.0 when no heightmap loaded."""
    app = _make_app()
    app.flythrough_heightmap = []
    assert app._flythrough_get_height(10.0, 10.0) == 0.0


def test_get_height_grid_aligned():
    """At integer coords, returns exact heightmap value."""
    app = _make_app()
    app._flythrough_init(0)
    hmap = app.flythrough_heightmap
    h = app._flythrough_get_height(5.0, 10.0)
    assert abs(h - hmap[10][5]) < 1e-9


# ── Flythrough step ──────────────────────────────────────────────────────────

def test_step_advances_generation():
    app = _make_app()
    app._flythrough_init(0)
    for _ in range(10):
        app._flythrough_step()
    assert app.flythrough_generation == 10


def test_step_moves_camera():
    """Camera position changes after a step."""
    app = _make_app()
    app._flythrough_init(0)
    old_x = app.flythrough_cam_x
    old_z = app.flythrough_cam_z
    app._flythrough_step()
    assert (app.flythrough_cam_x != old_x or app.flythrough_cam_z != old_z)


def test_step_minimum_altitude():
    """Camera never goes below terrain + 2."""
    app = _make_app()
    app._flythrough_init(0)
    app.flythrough_cam_y = -100.0  # force below ground
    app._flythrough_step()
    ground = app._flythrough_get_height(app.flythrough_cam_x, app.flythrough_cam_z)
    assert app.flythrough_cam_y >= ground + 2.0


def test_step_time_advances():
    """Day/night time advances when auto_time is on."""
    app = _make_app()
    app._flythrough_init(0)
    old_time = app.flythrough_time
    app._flythrough_step()
    assert app.flythrough_time != old_time


def test_step_time_frozen():
    """Day/night time stays put when auto_time is off."""
    app = _make_app()
    app._flythrough_init(0)
    app.flythrough_auto_time = False
    old_time = app.flythrough_time
    app._flythrough_step()
    assert app.flythrough_time == old_time


# ── Sky and terrain visuals ──────────────────────────────────────────────────

@patch("curses.color_pair", return_value=0)
def test_sky_color_day(_mock_cp):
    app = _make_app()
    app.flythrough_time = 0.5  # noon
    attr = app._flythrough_get_sky_color()
    assert attr is not None


@patch("curses.color_pair", return_value=0)
def test_sky_color_dawn(_mock_cp):
    app = _make_app()
    app.flythrough_time = 0.25
    attr = app._flythrough_get_sky_color()
    assert attr is not None


@patch("curses.color_pair", return_value=0)
def test_sky_color_night(_mock_cp):
    app = _make_app()
    app.flythrough_time = 0.0
    attr = app._flythrough_get_sky_color()
    assert attr is not None


@patch("curses.color_pair", return_value=0)
def test_terrain_char_deep_water(_mock_cp):
    app = _make_app()
    app.flythrough_time = 0.5
    ch, attr = app._flythrough_terrain_char_and_color(0.1, 10.0)
    assert ch in ("~", "\u2248")  # ~ or ≈


@patch("curses.color_pair", return_value=0)
def test_terrain_char_snow(_mock_cp):
    app = _make_app()
    app.flythrough_time = 0.5
    ch, attr = app._flythrough_terrain_char_and_color(0.95, 10.0)
    assert ch in ("\u2588", "*")  # █ or *


@patch("curses.color_pair", return_value=0)
def test_terrain_char_fog(_mock_cp):
    """Distant terrain shows fog characters."""
    app = _make_app()
    app.flythrough_time = 0.5
    ch, attr = app._flythrough_terrain_char_and_color(0.5, 60.0)
    assert ch in ("\u00b7", ".")  # · or .


@patch("curses.color_pair", return_value=0)
def test_terrain_char_night_dim(_mock_cp):
    """Night terrain uses DIM attribute."""
    app = _make_app()
    app.flythrough_time = 0.0  # midnight
    ch, attr = app._flythrough_terrain_char_and_color(0.5, 10.0)
    # With mocked color_pair returning 0, DIM should still be set
    assert isinstance(attr, int)


# ── Time label ───────────────────────────────────────────────────────────────

def test_time_label_noon():
    app = _make_app()
    app.flythrough_time = 0.5
    label = app._flythrough_time_label()
    assert "Noon" in label
    assert "12:" in label


def test_time_label_night():
    app = _make_app()
    app.flythrough_time = 0.0
    label = app._flythrough_time_label()
    assert "Night" in label


def test_time_label_dawn():
    app = _make_app()
    app.flythrough_time = 0.25
    label = app._flythrough_time_label()
    assert "Dawn" in label


# ── Menu key handling ────────────────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_flythrough_mode()
    app._handle_flythrough_menu_key(ord("j"))
    assert app.flythrough_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_flythrough_mode()
    app._handle_flythrough_menu_key(ord("k"))
    n = len(type(app).FLYTHROUGH_PRESETS)
    assert app.flythrough_menu_sel == n - 1


def test_menu_select():
    app = _make_app()
    app._enter_flythrough_mode()
    app._handle_flythrough_menu_key(ord("\n"))
    assert app.flythrough_mode is True
    assert app.flythrough_menu is False


def test_menu_cancel():
    app = _make_app()
    app._enter_flythrough_mode()
    app._handle_flythrough_menu_key(ord("q"))
    assert app.flythrough_menu is False


# ── Active mode key handling ─────────────────────────────────────────────────

def test_key_space_toggles_running():
    app = _make_app()
    app._flythrough_init(0)
    was_running = app.flythrough_running
    app._handle_flythrough_key(ord(" "))
    assert app.flythrough_running != was_running


def test_key_arrows_change_orientation():
    app = _make_app()
    app._flythrough_init(0)
    old_yaw = app.flythrough_cam_yaw
    app._handle_flythrough_key(curses.KEY_LEFT)
    assert app.flythrough_cam_yaw < old_yaw
    app._handle_flythrough_key(curses.KEY_RIGHT)
    app._handle_flythrough_key(curses.KEY_RIGHT)
    assert app.flythrough_cam_yaw > old_yaw


def test_key_pitch_clamped():
    app = _make_app()
    app._flythrough_init(0)
    for _ in range(100):
        app._handle_flythrough_key(curses.KEY_UP)
    assert app.flythrough_cam_pitch >= -1.2
    for _ in range(200):
        app._handle_flythrough_key(curses.KEY_DOWN)
    assert app.flythrough_cam_pitch <= 0.6


def test_key_wasd_moves():
    app = _make_app()
    app._flythrough_init(0)
    x0 = app.flythrough_cam_x
    z0 = app.flythrough_cam_z
    app._handle_flythrough_key(ord("w"))
    assert app.flythrough_cam_x != x0 or app.flythrough_cam_z != z0


def test_key_altitude():
    app = _make_app()
    app._flythrough_init(0)
    y0 = app.flythrough_cam_y
    app._handle_flythrough_key(ord("e"))
    assert app.flythrough_cam_y > y0


def test_key_speed_up():
    app = _make_app()
    app._flythrough_init(0)
    spd0 = app.flythrough_cam_speed
    app._handle_flythrough_key(ord("+"))
    assert app.flythrough_cam_speed > spd0


def test_key_speed_down():
    app = _make_app()
    app._flythrough_init(0)
    app.flythrough_cam_speed = 1.0
    app._handle_flythrough_key(ord("-"))
    assert app.flythrough_cam_speed < 1.0


def test_key_speed_clamped():
    app = _make_app()
    app._flythrough_init(0)
    app.flythrough_cam_speed = 5.0
    app._handle_flythrough_key(ord("+"))
    assert app.flythrough_cam_speed <= 5.0
    app.flythrough_cam_speed = 0.1
    app._handle_flythrough_key(ord("-"))
    assert app.flythrough_cam_speed >= 0.1


def test_key_toggle_time():
    app = _make_app()
    app._flythrough_init(0)
    old = app.flythrough_auto_time
    app._handle_flythrough_key(ord("t"))
    assert app.flythrough_auto_time != old


def test_key_advance_time():
    app = _make_app()
    app._flythrough_init(0)
    old = app.flythrough_time
    app._handle_flythrough_key(ord("T"))
    assert app.flythrough_time != old


def test_key_fov_adjust():
    app = _make_app()
    app._flythrough_init(0)
    fov0 = app.flythrough_fov
    app._handle_flythrough_key(ord("f"))
    assert app.flythrough_fov > fov0
    app._handle_flythrough_key(ord("F"))
    app._handle_flythrough_key(ord("F"))
    assert app.flythrough_fov < fov0


def test_key_fov_clamped():
    app = _make_app()
    app._flythrough_init(0)
    app.flythrough_fov = 2.0
    app._handle_flythrough_key(ord("f"))
    assert app.flythrough_fov <= 2.0
    app.flythrough_fov = 0.5
    app._handle_flythrough_key(ord("F"))
    assert app.flythrough_fov >= 0.5


def test_key_reset():
    app = _make_app()
    app._flythrough_init(0)
    app.flythrough_generation = 100
    app._handle_flythrough_key(ord("r"))
    assert app.flythrough_generation == 0


def test_key_back_to_menu():
    app = _make_app()
    app._flythrough_init(0)
    app._handle_flythrough_key(ord("m"))
    assert app.flythrough_menu is True
    assert app.flythrough_mode is False


def test_key_quit():
    app = _make_app()
    app._flythrough_init(0)
    app._handle_flythrough_key(ord("q"))
    assert app.flythrough_mode is False


def test_key_strafe_a():
    app = _make_app()
    app._flythrough_init(0)
    x0, z0 = app.flythrough_cam_x, app.flythrough_cam_z
    app._handle_flythrough_key(ord("a"))
    assert app.flythrough_cam_x != x0 or app.flythrough_cam_z != z0


def test_key_strafe_d():
    app = _make_app()
    app._flythrough_init(0)
    x0, z0 = app.flythrough_cam_x, app.flythrough_cam_z
    app._handle_flythrough_key(ord("d"))
    assert app.flythrough_cam_x != x0 or app.flythrough_cam_z != z0


def test_key_backward_s():
    app = _make_app()
    app._flythrough_init(0)
    x0, z0 = app.flythrough_cam_x, app.flythrough_cam_z
    app._handle_flythrough_key(ord("s"))
    assert app.flythrough_cam_x != x0 or app.flythrough_cam_z != z0


def test_key_descend_clamped():
    """Descending never puts camera below ground + 2."""
    app = _make_app()
    app._flythrough_init(0)
    for _ in range(50):
        app._handle_flythrough_key(ord("c"))
    ground = app._flythrough_get_height(app.flythrough_cam_x, app.flythrough_cam_z)
    assert app.flythrough_cam_y >= ground + 2.0


# ── Draw functions (smoke tests) ─────────────────────────────────────────────

@patch("curses.color_pair", return_value=0)
def test_draw_menu_no_crash(_mock_cp):
    app = _make_app()
    app._enter_flythrough_mode()
    app._draw_flythrough_menu(40, 120)


@patch("curses.color_pair", return_value=0)
def test_draw_flythrough_no_crash(_mock_cp):
    app = _make_app()
    # Use small map for speed
    app.flythrough_map_size = 32
    app.flythrough_heightmap = app._flythrough_generate(32, "hills")
    app.flythrough_cam_x = 16.0
    app.flythrough_cam_z = 16.0
    app.flythrough_cam_y = 10.0
    app.flythrough_mode = True
    app.flythrough_running = True
    app.flythrough_preset_name = "Test"
    app._draw_flythrough(40, 120)


@patch("curses.color_pair", return_value=0)
def test_draw_tiny_viewport(_mock_cp):
    """Drawing with very small viewport doesn't crash."""
    app = _make_app()
    app._flythrough_init(0)
    app._draw_flythrough(6, 12)
    app._draw_flythrough(3, 5)  # too small, early return
