"""Tests for life.modes.ray_marching — SDF Ray Marching mode."""
import curses
import math
from unittest.mock import patch

from tests.conftest import make_mock_app
from life.modes.ray_marching import register


def _make_app():
    app = make_mock_app()
    app.raymarch_mode = False
    app.raymarch_menu = False
    app.raymarch_menu_sel = 0
    app.raymarch_running = False
    app.raymarch_generation = 0
    app.raymarch_scene_name = ""
    app.raymarch_scene = ""
    app.raymarch_cam_theta = 0.0
    app.raymarch_cam_phi = 0.4
    app.raymarch_cam_dist = 4.0
    app.raymarch_auto_rotate = True
    app.raymarch_rotate_speed = 0.03
    app.raymarch_light_theta = 0.8
    app.raymarch_light_phi = 0.6
    app.raymarch_shadows = True
    app.raymarch_mandelbulb_power = 8.0
    type(app).RAYMARCH_PRESETS = [
        ("Sphere", "Perfect sphere with Phong shading", "sphere"),
        ("Torus", "Donut-shaped torus", "torus"),
        ("Multi-Object", "Sphere + torus + box scene", "multi"),
        ("Mandelbulb", "3D Mandelbrot fractal", "mandelbulb"),
        ("Infinite Spheres", "Repeating spheres via domain repetition", "infinite"),
        ("Smooth Blend", "Two spheres with smooth union", "blend"),
    ]
    type(app).RAYMARCH_SHADE_CHARS = " .:-=+*#%@"
    register(type(app))
    return app


# ── Enter / Exit ─────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_raymarch_mode()
    assert app.raymarch_menu is True
    assert app.raymarch_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._raymarch_init(0)
    app._exit_raymarch_mode()
    assert app.raymarch_mode is False
    assert app.raymarch_menu is False
    assert app.raymarch_running is False


# ── Init presets ─────────────────────────────────────────────────────────────

def test_init_all_presets():
    """Every scene preset initializes without error."""
    app = _make_app()
    for idx in range(len(type(app).RAYMARCH_PRESETS)):
        app._raymarch_init(idx)
        assert app.raymarch_mode is True
        assert app.raymarch_menu is False
        assert app.raymarch_running is True
        assert app.raymarch_scene == type(app).RAYMARCH_PRESETS[idx][2]


# ── SDF evaluation ───────────────────────────────────────────────────────────

def test_sdf_sphere_at_surface():
    """Sphere SDF is ~0 at radius 1."""
    app = _make_app()
    app._raymarch_init(0)  # sphere
    d = app._raymarch_sdf(1.0, 0.0, 0.0)
    assert abs(d) < 0.01


def test_sdf_sphere_inside():
    """Sphere SDF is negative inside."""
    app = _make_app()
    app._raymarch_init(0)
    d = app._raymarch_sdf(0.0, 0.0, 0.0)
    assert d < 0.0


def test_sdf_sphere_outside():
    """Sphere SDF is positive outside."""
    app = _make_app()
    app._raymarch_init(0)
    d = app._raymarch_sdf(2.0, 0.0, 0.0)
    assert d > 0.0


def test_sdf_torus_at_surface():
    """Torus SDF is ~0 on the surface ring."""
    app = _make_app()
    app.raymarch_scene = "torus"
    # Point on ring: (1, 0, 0) is on the major circle, offset by minor radius 0.4
    d = app._raymarch_sdf(1.4, 0.0, 0.0)
    assert abs(d) < 0.01


def test_sdf_torus_center():
    """Torus SDF at origin should be positive (hole in the middle)."""
    app = _make_app()
    app.raymarch_scene = "torus"
    d = app._raymarch_sdf(0.0, 0.0, 0.0)
    # Distance from origin to ring: sqrt(0+0) - 1 = -1, then sqrt(1+0)-0.4 = 0.6
    assert d > 0.0


def test_sdf_multi_objects():
    """Multi scene has sphere at (1.5,0,0) and box at (0,0,1.5)."""
    app = _make_app()
    app.raymarch_scene = "multi"
    # Near the sphere
    d_near_sphere = app._raymarch_sdf(1.5, 0.0, 0.0)
    assert d_near_sphere < 0  # inside sphere
    # Far away
    d_far = app._raymarch_sdf(10.0, 10.0, 10.0)
    assert d_far > 0


def test_sdf_mandelbulb():
    """Mandelbulb SDF returns finite values."""
    app = _make_app()
    app.raymarch_scene = "mandelbulb"
    app.raymarch_mandelbulb_power = 8.0
    d = app._raymarch_sdf(0.0, 0.0, 0.0)
    assert math.isfinite(d)
    d2 = app._raymarch_sdf(5.0, 5.0, 5.0)
    assert d2 > 0


def test_sdf_infinite():
    """Infinite spheres: SDF is periodic."""
    app = _make_app()
    app.raymarch_scene = "infinite"
    d1 = app._raymarch_sdf(0.0, 0.0, 0.0)
    d2 = app._raymarch_sdf(3.0, 0.0, 0.0)
    d3 = app._raymarch_sdf(6.0, 0.0, 0.0)
    assert abs(d1 - d2) < 0.01
    assert abs(d1 - d3) < 0.01


def test_sdf_blend():
    """Smooth blend at midpoint should be inside (merged)."""
    app = _make_app()
    app.raymarch_scene = "blend"
    d_mid = app._raymarch_sdf(0.0, 0.0, 0.0)
    # With smooth union, the midpoint should be closer/inside
    assert d_mid < 0.5


def test_sdf_unknown_scene():
    """Unknown scene returns large distance."""
    app = _make_app()
    app.raymarch_scene = "nonexistent"
    d = app._raymarch_sdf(0.0, 0.0, 0.0)
    assert d >= 1e10


# ── Normals ──────────────────────────────────────────────────────────────────

def test_normal_sphere_top():
    """Normal at top of sphere should point up."""
    app = _make_app()
    app.raymarch_scene = "sphere"
    nx, ny, nz = app._raymarch_normal(0.0, 1.0, 0.0)
    assert ny > 0.9  # mostly pointing up


def test_normal_sphere_right():
    """Normal on right of sphere should point +x."""
    app = _make_app()
    app.raymarch_scene = "sphere"
    nx, ny, nz = app._raymarch_normal(1.0, 0.0, 0.0)
    assert nx > 0.9


def test_normal_is_unit():
    """Normal should be approximately unit length."""
    app = _make_app()
    app.raymarch_scene = "sphere"
    nx, ny, nz = app._raymarch_normal(0.0, 0.0, 1.0)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    assert abs(length - 1.0) < 0.01


# ── Shadow ───────────────────────────────────────────────────────────────────

def test_shadow_unoccluded():
    """Point with clear path to light gives shadow ~1.0."""
    app = _make_app()
    app.raymarch_scene = "sphere"
    # Point above sphere, light from above
    s = app._raymarch_shadow(0.0, 1.5, 0.0, 0.0, 1.0, 0.0)
    assert s > 0.8


def test_shadow_occluded():
    """Point behind sphere from light should be in shadow."""
    app = _make_app()
    app.raymarch_scene = "sphere"
    # Point below sphere, light from above
    s = app._raymarch_shadow(0.0, -1.1, 0.0, 0.0, 1.0, 0.0)
    assert s < 0.3


def test_shadow_range():
    """Shadow value is in [0, 1]."""
    app = _make_app()
    app.raymarch_scene = "sphere"
    for ox, oy, oz in [(2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (-1.0, -1.0, 0.0)]:
        s = app._raymarch_shadow(ox, oy, oz, 0.5, 0.8, 0.3)
        assert 0.0 <= s <= 1.0


# ── Step ─────────────────────────────────────────────────────────────────────

def test_step_advances_generation():
    app = _make_app()
    app._raymarch_init(0)
    for _ in range(10):
        app._raymarch_step()
    assert app.raymarch_generation == 10


def test_step_auto_rotate():
    """Auto-rotate changes camera theta."""
    app = _make_app()
    app._raymarch_init(0)
    old_theta = app.raymarch_cam_theta
    app._raymarch_step()
    assert app.raymarch_cam_theta > old_theta


def test_step_no_rotate_when_off():
    app = _make_app()
    app._raymarch_init(0)
    app.raymarch_auto_rotate = False
    old_theta = app.raymarch_cam_theta
    app._raymarch_step()
    assert app.raymarch_cam_theta == old_theta


# ── Menu key handling ────────────────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_raymarch_mode()
    app._handle_raymarch_menu_key(ord("j"))
    assert app.raymarch_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_raymarch_mode()
    app._handle_raymarch_menu_key(ord("k"))
    n = len(type(app).RAYMARCH_PRESETS)
    assert app.raymarch_menu_sel == n - 1


def test_menu_select():
    app = _make_app()
    app._enter_raymarch_mode()
    app._handle_raymarch_menu_key(ord("\n"))
    assert app.raymarch_mode is True
    assert app.raymarch_menu is False


def test_menu_cancel():
    app = _make_app()
    app._enter_raymarch_mode()
    app._handle_raymarch_menu_key(ord("q"))
    assert app.raymarch_menu is False


# ── Active mode key handling ─────────────────────────────────────────────────

def test_key_space_toggles():
    app = _make_app()
    app._raymarch_init(0)
    was_running = app.raymarch_running
    app._handle_raymarch_key(ord(" "))
    assert app.raymarch_running != was_running


def test_key_orbit():
    app = _make_app()
    app._raymarch_init(0)
    old_theta = app.raymarch_cam_theta
    app._handle_raymarch_key(curses.KEY_LEFT)
    assert app.raymarch_cam_theta < old_theta


def test_key_phi_clamped():
    app = _make_app()
    app._raymarch_init(0)
    for _ in range(50):
        app._handle_raymarch_key(curses.KEY_UP)
    assert app.raymarch_cam_phi <= 1.5
    for _ in range(100):
        app._handle_raymarch_key(curses.KEY_DOWN)
    assert app.raymarch_cam_phi >= -1.5


def test_key_zoom():
    app = _make_app()
    app._raymarch_init(0)
    d0 = app.raymarch_cam_dist
    app._handle_raymarch_key(ord("+"))
    assert app.raymarch_cam_dist < d0  # zoom in = smaller dist


def test_key_zoom_clamped():
    app = _make_app()
    app._raymarch_init(0)
    app.raymarch_cam_dist = 1.5
    app._handle_raymarch_key(ord("+"))
    assert app.raymarch_cam_dist >= 1.5
    app.raymarch_cam_dist = 12.0
    app._handle_raymarch_key(ord("-"))
    assert app.raymarch_cam_dist <= 12.0


def test_key_auto_rotate_toggle():
    app = _make_app()
    app._raymarch_init(0)
    old = app.raymarch_auto_rotate
    app._handle_raymarch_key(ord("a"))
    assert app.raymarch_auto_rotate != old


def test_key_shadows_toggle():
    app = _make_app()
    app._raymarch_init(0)
    old = app.raymarch_shadows
    app._handle_raymarch_key(ord("s"))
    assert app.raymarch_shadows != old


def test_key_light_rotate():
    app = _make_app()
    app._raymarch_init(0)
    old = app.raymarch_light_theta
    app._handle_raymarch_key(ord("l"))
    assert app.raymarch_light_theta > old


def test_key_mandelbulb_power():
    app = _make_app()
    app._raymarch_init(3)  # mandelbulb
    p0 = app.raymarch_mandelbulb_power
    app._handle_raymarch_key(ord("P"))
    assert app.raymarch_mandelbulb_power > p0
    app._handle_raymarch_key(ord("p"))
    assert app.raymarch_mandelbulb_power == p0


def test_key_mandelbulb_power_clamped():
    app = _make_app()
    app._raymarch_init(3)
    app.raymarch_mandelbulb_power = 16.0
    app._handle_raymarch_key(ord("P"))
    assert app.raymarch_mandelbulb_power <= 16.0
    app.raymarch_mandelbulb_power = 2.0
    app._handle_raymarch_key(ord("p"))
    assert app.raymarch_mandelbulb_power >= 2.0


def test_key_power_ignored_non_mandelbulb():
    """Power key does nothing for non-mandelbulb scenes."""
    app = _make_app()
    app._raymarch_init(0)  # sphere
    p0 = app.raymarch_mandelbulb_power
    app._handle_raymarch_key(ord("P"))
    assert app.raymarch_mandelbulb_power == p0


def test_key_reset():
    app = _make_app()
    app._raymarch_init(0)
    app.raymarch_generation = 100
    app._handle_raymarch_key(ord("r"))
    assert app.raymarch_generation == 0


def test_key_back_to_menu():
    app = _make_app()
    app._raymarch_init(0)
    app._handle_raymarch_key(ord("m"))
    assert app.raymarch_menu is True
    assert app.raymarch_mode is False


def test_key_quit():
    app = _make_app()
    app._raymarch_init(0)
    app._handle_raymarch_key(ord("q"))
    assert app.raymarch_mode is False


# ── Draw functions (smoke tests) ─────────────────────────────────────────────

@patch("curses.color_pair", return_value=0)
def test_draw_menu_no_crash(_mock_cp):
    app = _make_app()
    app._enter_raymarch_mode()
    app._draw_raymarch_menu(40, 120)


@patch("curses.color_pair", return_value=0)
def test_draw_raymarch_no_crash(_mock_cp):
    """Full render with small viewport doesn't crash."""
    app = _make_app()
    app._raymarch_init(0)
    # Use tiny viewport for speed
    app._draw_raymarch(10, 20)


@patch("curses.color_pair", return_value=0)
def test_draw_tiny_viewport(_mock_cp):
    app = _make_app()
    app._raymarch_init(0)
    app._draw_raymarch(3, 5)  # too small, early return
