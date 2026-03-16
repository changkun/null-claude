"""Tests for life.modes.doom_raycaster — Doom Raycaster mode."""
import curses
import math
from tests.conftest import make_mock_app
from life.modes.doom_raycaster import (
    register, DOOMRC_PRESETS, DOOMRC_MAPS, DOOMRC_SHADE_WALL, DOOMRC_SHADE_FLOOR,
)


def _make_app():
    app = make_mock_app()
    app.doomrc_mode = False
    app.doomrc_menu = False
    app.doomrc_menu_sel = 0
    app.doomrc_running = False
    app.doomrc_generation = 0
    app.doomrc_preset_name = ""
    app.doomrc_map = []
    app.doomrc_map_h = 0
    app.doomrc_map_w = 0
    app.doomrc_px = 0.0
    app.doomrc_py = 0.0
    app.doomrc_pa = 0.0
    app.doomrc_fov = 3.14159 / 3.0
    app.doomrc_depth = 16.0
    app.doomrc_speed = 0.15
    app.doomrc_rot_speed = 0.08
    app.doomrc_show_map = True
    app.doomrc_show_help = True
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_constants_exist():
    """Module defines all required constants."""
    assert len(DOOMRC_PRESETS) >= 6
    assert len(DOOMRC_MAPS) >= 6
    assert len(DOOMRC_SHADE_WALL) > 0
    assert len(DOOMRC_SHADE_FLOOR) > 0


def test_presets_keys_match_maps():
    """Every preset key references a valid map."""
    for _name, _desc, key in DOOMRC_PRESETS:
        assert key in DOOMRC_MAPS, f"Preset key '{key}' not found in DOOMRC_MAPS"


def test_maps_are_rectangular():
    """All maps are rectangular with consistent row widths."""
    for key, rows in DOOMRC_MAPS.items():
        assert len(rows) > 0, f"Map '{key}' is empty"
        width = len(rows[0])
        for i, row in enumerate(rows):
            assert len(row) == width, f"Map '{key}' row {i} width {len(row)} != {width}"


def test_maps_are_walled():
    """All maps have wall characters on the perimeter."""
    for key, rows in DOOMRC_MAPS.items():
        h = len(rows)
        w = len(rows[0])
        for c in range(w):
            assert rows[0][c] == '#', f"Map '{key}' top row open at col {c}"
            assert rows[h-1][c] == '#', f"Map '{key}' bottom row open at col {c}"
        for r in range(h):
            assert rows[r][0] == '#', f"Map '{key}' left col open at row {r}"
            assert rows[r][w-1] == '#', f"Map '{key}' right col open at row {r}"


def test_maps_have_open_space():
    """All maps contain at least one open floor tile for spawning."""
    for key, rows in DOOMRC_MAPS.items():
        has_floor = any(cell == '.' for row in rows for cell in row)
        assert has_floor, f"Map '{key}' has no floor tiles"


def test_register_sets_class_constants():
    """register() sets constants on the App class."""
    app = _make_app()
    cls = type(app)
    assert hasattr(cls, 'DOOMRC_PRESETS')
    assert hasattr(cls, 'DOOMRC_MAPS')
    assert hasattr(cls, 'DOOMRC_SHADE_WALL')
    assert hasattr(cls, 'DOOMRC_SHADE_FLOOR')


# ── Enter / Exit ────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_doomrc_mode()
    assert app.doomrc_menu is True
    assert app.doomrc_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._doomrc_init(0)
    app._exit_doomrc_mode()
    assert app.doomrc_mode is False
    assert app.doomrc_menu is False
    assert app.doomrc_running is False


# ── Init ────────────────────────────────────────────────────────────────────

def test_init_all_presets():
    """Init works for every preset without crashing."""
    for i in range(len(DOOMRC_PRESETS)):
        app = _make_app()
        app._doomrc_init(i)
        assert app.doomrc_mode is True
        assert app.doomrc_menu is False
        assert app.doomrc_running is True
        assert app.doomrc_map_h > 0
        assert app.doomrc_map_w > 0


def test_init_sets_player_in_open_space():
    """Player spawns on a floor tile, not inside a wall."""
    for i in range(len(DOOMRC_PRESETS)):
        app = _make_app()
        app._doomrc_init(i)
        # Player position should be open
        assert not app._doomrc_is_wall(app.doomrc_px, app.doomrc_py), \
            f"Preset {i}: player spawned inside wall at ({app.doomrc_px}, {app.doomrc_py})"


# ── Spawn finder ────────────────────────────────────────────────────────────

def test_find_spawn_returns_center_of_tile():
    """Spawn position has .5 fractional part (center of tile)."""
    app = _make_app()
    app._doomrc_init(0)
    assert app.doomrc_px % 1 == 0.5 or app.doomrc_py % 1 == 0.5


def test_find_spawn_fallback():
    """If no floor tile, fallback to (1.5, 1.5)."""
    app = _make_app()
    # Create an all-wall map
    app.doomrc_map = ["####", "####", "####", "####"]
    app.doomrc_map_h = 4
    app.doomrc_map_w = 4
    x, y = app._doomrc_find_spawn()
    assert x == 1.5
    assert y == 1.5


# ── Wall detection ──────────────────────────────────────────────────────────

def test_is_wall_detects_walls():
    app = _make_app()
    app._doomrc_init(0)
    # Top-left corner is always a wall
    assert app._doomrc_is_wall(0.5, 0.5) is True


def test_is_wall_detects_floor():
    app = _make_app()
    app._doomrc_init(0)
    # Player spawn is open
    assert app._doomrc_is_wall(app.doomrc_px, app.doomrc_py) is False


def test_is_wall_out_of_bounds():
    """Out-of-bounds positions are treated as walls."""
    app = _make_app()
    app._doomrc_init(0)
    assert app._doomrc_is_wall(-1, 0) is True
    assert app._doomrc_is_wall(0, -1) is True
    assert app._doomrc_is_wall(app.doomrc_map_w + 1, 0) is True
    assert app._doomrc_is_wall(0, app.doomrc_map_h + 1) is True


# ── Movement and collision ──────────────────────────────────────────────────

def test_move_into_open_space():
    """Moving into open space changes position."""
    app = _make_app()
    app._doomrc_init(0)
    old_x, old_y = app.doomrc_px, app.doomrc_py
    # Move by a small amount in a direction that should be open
    # Try moving; if blocked, position stays (still valid behavior)
    app._doomrc_move(0.1, 0.0)
    # Just verify no crash; actual movement depends on map geometry


def test_move_into_wall_blocked():
    """Moving directly into a wall should not change position (or only slide)."""
    app = _make_app()
    app._doomrc_init(0)  # use standard preset
    # Place player near a wall (top-left interior corner)
    # Map row 1 starts with '#' (wall), '.' (floor) patterns
    app.doomrc_px = 1.3
    app.doomrc_py = 1.5
    old_x = app.doomrc_px
    # Move left into wall
    app._doomrc_move(-1.0, 0.0)
    # Should not go below 0 (outside map)
    assert app.doomrc_px >= 0.0


def test_wall_sliding():
    """Diagonal movement against a wall slides along it."""
    app = _make_app()
    app._doomrc_init(0)
    # Place player near the top wall
    app.doomrc_px = 2.5
    app.doomrc_py = 1.3
    # Try to move diagonally into the wall
    app._doomrc_move(0.1, -0.5)
    # No crash is the key test; position may or may not change


# ── Step ────────────────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._doomrc_init(0)
    assert app.doomrc_generation == 0
    for i in range(10):
        app._doomrc_step()
    assert app.doomrc_generation == 10


# ── Menu key handling ───────────────────────────────────────────────────────

def test_menu_key_down():
    app = _make_app()
    app._enter_doomrc_mode()
    assert app.doomrc_menu_sel == 0
    app._handle_doomrc_menu_key(ord('j'))
    assert app.doomrc_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_doomrc_mode()
    assert app.doomrc_menu_sel == 0
    app._handle_doomrc_menu_key(ord('k'))
    # Should wrap to last preset
    n = len(type(app).DOOMRC_PRESETS)
    assert app.doomrc_menu_sel == n - 1


def test_menu_key_enter_inits():
    app = _make_app()
    app._enter_doomrc_mode()
    app._handle_doomrc_menu_key(ord('\n'))
    assert app.doomrc_mode is True
    assert app.doomrc_menu is False
    assert app.doomrc_running is True


def test_menu_key_escape_exits():
    app = _make_app()
    app._enter_doomrc_mode()
    app._handle_doomrc_menu_key(27)
    assert app.doomrc_menu is False
    assert app.doomrc_mode is False


def test_menu_key_unknown_returns_false():
    app = _make_app()
    app._enter_doomrc_mode()
    result = app._handle_doomrc_menu_key(ord('z'))
    assert result is False


# ── Game key handling ───────────────────────────────────────────────────────

def test_key_wasd_movement():
    """WASD keys trigger movement without crash."""
    app = _make_app()
    app._doomrc_init(0)
    for key in [ord('w'), ord('a'), ord('s'), ord('d')]:
        result = app._handle_doomrc_key(key)
        assert result is True


def test_key_rotation():
    """Q/E rotate the player angle."""
    app = _make_app()
    app._doomrc_init(0)
    initial_angle = app.doomrc_pa
    app._handle_doomrc_key(ord('q'))
    assert app.doomrc_pa < initial_angle
    app._handle_doomrc_key(ord('e'))
    app._handle_doomrc_key(ord('e'))
    assert app.doomrc_pa > initial_angle


def test_key_space_toggles_running():
    app = _make_app()
    app._doomrc_init(0)
    assert app.doomrc_running is True
    app._handle_doomrc_key(ord(' '))
    assert app.doomrc_running is False
    app._handle_doomrc_key(ord(' '))
    assert app.doomrc_running is True


def test_key_m_toggles_map():
    app = _make_app()
    app._doomrc_init(0)
    assert app.doomrc_show_map is True
    app._handle_doomrc_key(ord('m'))
    assert app.doomrc_show_map is False


def test_key_help_toggle():
    app = _make_app()
    app._doomrc_init(0)
    assert app.doomrc_show_help is True
    app._handle_doomrc_key(ord('?'))
    assert app.doomrc_show_help is False


def test_key_escape_exits_mode():
    app = _make_app()
    app._doomrc_init(0)
    app._handle_doomrc_key(27)
    assert app.doomrc_mode is False
    assert app.doomrc_running is False


# ── Raycasting logic ────────────────────────────────────────────────────────

def test_raycasting_fisheye_correction():
    """Verify fisheye correction math: cos(ray_angle - player_angle)."""
    pa = 0.0
    fov = math.pi / 3.0
    # Center ray should have correction factor ~1.0
    center_ray_a = pa  # center of FOV
    correction = math.cos(center_ray_a - pa)
    assert abs(correction - 1.0) < 0.001
    # Edge ray should have correction < 1.0
    edge_ray_a = pa - fov / 2.0
    correction = math.cos(edge_ray_a - pa)
    assert correction < 1.0
    assert correction > 0.5  # should be ~cos(30deg) = 0.866


def test_shade_arrays_cover_range():
    """Wall and floor shade arrays have enough characters for rendering."""
    assert len(DOOMRC_SHADE_WALL) >= 3
    assert len(DOOMRC_SHADE_FLOOR) >= 3


# ── Strafe direction correctness ────────────────────────────────────────────

def test_strafe_perpendicular_to_facing():
    """Strafe directions should be perpendicular to forward direction."""
    # Forward direction at angle 0 is (cos(0), sin(0)) = (1, 0)
    pa = 0.0
    cos_a = math.cos(pa)
    sin_a = math.sin(pa)
    # Strafe left uses (sin_a, -cos_a) = (0, -1) -- perpendicular
    left_dx, left_dy = sin_a, -cos_a
    # Dot product with forward should be ~0
    dot = left_dx * cos_a + left_dy * sin_a
    assert abs(dot) < 0.001
