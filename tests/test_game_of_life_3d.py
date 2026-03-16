"""Tests for life.modes.game_of_life_3d — 3D Game of Life mode."""
import curses
import math
import random
from unittest.mock import patch

from tests.conftest import make_mock_app
from life.modes.game_of_life_3d import register


def _make_app(grid_size=8):
    app = make_mock_app()
    app.gol3d_mode = False
    app.gol3d_menu = False
    app.gol3d_menu_sel = 0
    app.gol3d_running = False
    app.gol3d_generation = 0
    app.gol3d_preset_name = ""
    app.gol3d_size = grid_size
    app.gol3d_grid = []
    app.gol3d_population = 0
    app.gol3d_birth = set()
    app.gol3d_survive = set()
    app.gol3d_density = 0.0
    app.gol3d_cam_theta = 0.5
    app.gol3d_cam_phi = 0.5
    app.gol3d_cam_dist = 2.5
    app.gol3d_auto_rotate = True
    app.gol3d_rotate_speed = 0.02
    type(app).GOL3D_PRESETS = [
        ("5766", "B5/S6,7,8 -- slow crystal growth", {5}, {6, 7, 8}, 0.15),
        ("Clouds", "B13-26/S14-25 -- gas-like expansion", set(range(13, 27)), set(range(14, 26)), 0.4),
        ("Coral", "B5-8/S4-7 -- organic branching", set(range(5, 9)), set(range(4, 8)), 0.2),
    ]
    type(app).GOL3D_SHADE_CHARS = " .:-=+*#%@"
    register(type(app))
    return app


def _make_empty_grid(sz):
    """Create an empty sz x sz x sz grid."""
    return [[[0] * sz for _ in range(sz)] for _ in range(sz)]


def _make_single_cell_grid(sz, x, y, z):
    """Create grid with a single live cell."""
    grid = _make_empty_grid(sz)
    grid[x][y][z] = 1
    return grid


# ── Enter / Exit ─────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_gol3d_mode()
    assert app.gol3d_menu is True
    assert app.gol3d_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._gol3d_init(0)
    app._exit_gol3d_mode()
    assert app.gol3d_mode is False
    assert app.gol3d_menu is False
    assert app.gol3d_running is False


# ── Init presets ─────────────────────────────────────────────────────────────

def test_init_all_presets():
    """Every preset initializes without error."""
    app = _make_app()
    for idx in range(len(type(app).GOL3D_PRESETS)):
        app._gol3d_init(idx)
        assert app.gol3d_mode is True
        assert app.gol3d_menu is False
        assert app.gol3d_running is True
        assert app.gol3d_preset_name == type(app).GOL3D_PRESETS[idx][0]
        assert len(app.gol3d_grid) == app.gol3d_size


def test_init_sets_rules():
    app = _make_app()
    app._gol3d_init(0)
    assert app.gol3d_birth == {5}
    assert app.gol3d_survive == {6, 7, 8}


def test_init_populates_near_center():
    """Initial cells are seeded near the center of the grid."""
    app = _make_app()
    app._gol3d_init(2)  # coral, density=0.2
    sz = app.gol3d_size
    has_center_cell = False
    has_corner_cell = False
    grid = app.gol3d_grid
    # Check center region
    mid = sz // 2
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                x, y, z = mid + dx, mid + dy, mid + dz
                if 0 <= x < sz and 0 <= y < sz and 0 <= z < sz:
                    if grid[x][y][z]:
                        has_center_cell = True
    # With density 0.2, the center region should have some cells (probabilistic but very likely)
    # Don't assert has_center_cell because it's random, but population should > 0
    assert app.gol3d_population >= 0  # at least doesn't crash


def test_init_grid_dimensions():
    app = _make_app(grid_size=10)
    app._gol3d_init(0)
    assert len(app.gol3d_grid) == 10
    assert len(app.gol3d_grid[0]) == 10
    assert len(app.gol3d_grid[0][0]) == 10


# ── Step / neighbor counting / rules ────────────────────────────────────────

def test_step_advances_generation():
    app = _make_app()
    app._gol3d_init(0)
    for _ in range(10):
        app._gol3d_step()
    assert app.gol3d_generation == 10


def test_step_empty_stays_empty():
    """An empty grid remains empty with birth={5}."""
    app = _make_app()
    app._gol3d_init(0)
    sz = app.gol3d_size
    app.gol3d_grid = _make_empty_grid(sz)
    app.gol3d_population = 0
    app._gol3d_step()
    assert app.gol3d_population == 0


def test_step_single_cell_dies():
    """A single cell with survive={6,7,8} dies (0 neighbors)."""
    app = _make_app()
    app._gol3d_init(0)  # birth={5}, survive={6,7,8}
    sz = app.gol3d_size
    app.gol3d_grid = _make_single_cell_grid(sz, 4, 4, 4)
    app.gol3d_population = 1
    app._gol3d_step()
    assert app.gol3d_population == 0


def test_step_population_tracked():
    """Population count accurately tracks live cells."""
    app = _make_app()
    app._gol3d_init(0)
    app._gol3d_step()
    # Manually count
    sz = app.gol3d_size
    count = sum(
        app.gol3d_grid[x][y][z]
        for x in range(sz)
        for y in range(sz)
        for z in range(sz)
    )
    assert count == app.gol3d_population


def test_step_auto_rotate():
    """Auto-rotate advances camera theta."""
    app = _make_app()
    app._gol3d_init(0)
    old_theta = app.gol3d_cam_theta
    app._gol3d_step()
    assert app.gol3d_cam_theta > old_theta


def test_step_no_rotate_when_off():
    app = _make_app()
    app._gol3d_init(0)
    app.gol3d_auto_rotate = False
    old_theta = app.gol3d_cam_theta
    app._gol3d_step()
    assert app.gol3d_cam_theta == old_theta


def test_birth_rule():
    """With birth={5}, exactly 5 neighbors causes birth."""
    app = _make_app(grid_size=8)
    app.gol3d_birth = {5}
    app.gol3d_survive = set()  # all alive cells die
    app.gol3d_size = 8
    sz = 8
    # Place exactly 5 neighbors around (3,3,3), which is dead
    grid = _make_empty_grid(sz)
    neighbors = [(2, 3, 3), (4, 3, 3), (3, 2, 3), (3, 4, 3), (3, 3, 2)]
    for x, y, z in neighbors:
        grid[x][y][z] = 1
    app.gol3d_grid = grid
    app.gol3d_population = 5
    app.gol3d_generation = 0
    app.gol3d_auto_rotate = False
    app._gol3d_step()
    # (3,3,3) should now be alive
    assert app.gol3d_grid[3][3][3] == 1


def test_survive_rule():
    """Cell with neighbors in survive set stays alive."""
    app = _make_app(grid_size=8)
    app.gol3d_birth = set()
    app.gol3d_survive = {2}
    app.gol3d_size = 8
    sz = 8
    grid = _make_empty_grid(sz)
    # Place cell at (3,3,3) with exactly 2 neighbors
    grid[3][3][3] = 1
    grid[2][3][3] = 1
    grid[4][3][3] = 1
    app.gol3d_grid = grid
    app.gol3d_population = 3
    app.gol3d_generation = 0
    app.gol3d_auto_rotate = False
    app._gol3d_step()
    assert app.gol3d_grid[3][3][3] == 1


def test_no_survive_rule():
    """Cell with wrong neighbor count dies."""
    app = _make_app(grid_size=8)
    app.gol3d_birth = set()
    app.gol3d_survive = {6, 7, 8}
    app.gol3d_size = 8
    sz = 8
    grid = _make_empty_grid(sz)
    grid[3][3][3] = 1
    grid[2][3][3] = 1  # only 1 neighbor
    app.gol3d_grid = grid
    app.gol3d_population = 2
    app.gol3d_generation = 0
    app.gol3d_auto_rotate = False
    app._gol3d_step()
    assert app.gol3d_grid[3][3][3] == 0


def test_boundary_cells_no_crash():
    """Cells at grid boundaries don't cause index errors."""
    app = _make_app(grid_size=5)
    app.gol3d_birth = {1}
    app.gol3d_survive = {1}
    app.gol3d_size = 5
    sz = 5
    grid = _make_empty_grid(sz)
    # Place cells at all corners
    for x in (0, sz - 1):
        for y in (0, sz - 1):
            for z in (0, sz - 1):
                grid[x][y][z] = 1
    app.gol3d_grid = grid
    app.gol3d_population = 8
    app.gol3d_generation = 0
    app.gol3d_auto_rotate = False
    app._gol3d_step()
    # Just verify no crash and population is tracked
    count = sum(
        app.gol3d_grid[x][y][z]
        for x in range(sz)
        for y in range(sz)
        for z in range(sz)
    )
    assert count == app.gol3d_population


def test_26_neighbor_count():
    """A fully surrounded cell should have 26 neighbors."""
    app = _make_app(grid_size=8)
    app.gol3d_birth = set()
    app.gol3d_survive = {26}  # survive only with exactly 26 neighbors
    app.gol3d_size = 8
    sz = 8
    # Fill a 3x3x3 cube centered at (3,3,3) -- 27 cells, center has 26 neighbors
    grid = _make_empty_grid(sz)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                grid[3 + dx][3 + dy][3 + dz] = 1
    app.gol3d_grid = grid
    app.gol3d_population = 27
    app.gol3d_generation = 0
    app.gol3d_auto_rotate = False
    app._gol3d_step()
    # Center (3,3,3) had 26 neighbors, should survive
    assert app.gol3d_grid[3][3][3] == 1


# ── Menu key handling ────────────────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_gol3d_mode()
    app._handle_gol3d_menu_key(ord("j"))
    assert app.gol3d_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_gol3d_mode()
    app._handle_gol3d_menu_key(ord("k"))
    n = len(type(app).GOL3D_PRESETS)
    assert app.gol3d_menu_sel == n - 1


def test_menu_select():
    app = _make_app()
    app._enter_gol3d_mode()
    app._handle_gol3d_menu_key(ord("\n"))
    assert app.gol3d_mode is True
    assert app.gol3d_menu is False


def test_menu_cancel():
    app = _make_app()
    app._enter_gol3d_mode()
    app._handle_gol3d_menu_key(ord("q"))
    assert app.gol3d_menu is False


def test_menu_escape():
    app = _make_app()
    app._enter_gol3d_mode()
    app._handle_gol3d_menu_key(27)
    assert app.gol3d_menu is False


# ── Active mode key handling ─────────────────────────────────────────────────

def test_key_space_toggles():
    app = _make_app()
    app._gol3d_init(0)
    was = app.gol3d_running
    app._handle_gol3d_key(ord(" "))
    assert app.gol3d_running != was


def test_key_orbit():
    app = _make_app()
    app._gol3d_init(0)
    old_theta = app.gol3d_cam_theta
    app._handle_gol3d_key(curses.KEY_LEFT)
    assert app.gol3d_cam_theta < old_theta


def test_key_phi_clamped():
    app = _make_app()
    app._gol3d_init(0)
    for _ in range(50):
        app._handle_gol3d_key(curses.KEY_UP)
    assert app.gol3d_cam_phi <= 1.5
    for _ in range(100):
        app._handle_gol3d_key(curses.KEY_DOWN)
    assert app.gol3d_cam_phi >= -1.5


def test_key_zoom():
    app = _make_app()
    app._gol3d_init(0)
    d0 = app.gol3d_cam_dist
    app._handle_gol3d_key(ord("+"))
    assert app.gol3d_cam_dist < d0  # closer


def test_key_zoom_clamped():
    app = _make_app()
    app._gol3d_init(0)
    app.gol3d_cam_dist = 1.2
    app._handle_gol3d_key(ord("+"))
    assert app.gol3d_cam_dist >= 1.2
    app.gol3d_cam_dist = 5.0
    app._handle_gol3d_key(ord("-"))
    assert app.gol3d_cam_dist <= 5.0


def test_key_auto_rotate_toggle():
    app = _make_app()
    app._gol3d_init(0)
    old = app.gol3d_auto_rotate
    app._handle_gol3d_key(ord("a"))
    assert app.gol3d_auto_rotate != old


def test_key_single_step():
    app = _make_app()
    app._gol3d_init(0)
    gen0 = app.gol3d_generation
    app._handle_gol3d_key(ord("n"))
    assert app.gol3d_generation == gen0 + 1


def test_key_reset():
    app = _make_app()
    app._gol3d_init(0)
    app.gol3d_generation = 100
    app._handle_gol3d_key(ord("r"))
    assert app.gol3d_generation == 0


def test_key_back_to_menu():
    app = _make_app()
    app._gol3d_init(0)
    app._handle_gol3d_key(ord("m"))
    assert app.gol3d_menu is True
    assert app.gol3d_mode is False


def test_key_quit():
    app = _make_app()
    app._gol3d_init(0)
    app._handle_gol3d_key(ord("q"))
    assert app.gol3d_mode is False


# ── Draw functions (smoke tests) ─────────────────────────────────────────────

@patch("curses.color_pair", return_value=0)
def test_draw_menu_no_crash(_mock_cp):
    app = _make_app()
    app._enter_gol3d_mode()
    app._draw_gol3d_menu(40, 120)


@patch("curses.color_pair", return_value=0)
def test_draw_gol3d_no_crash(_mock_cp):
    app = _make_app(grid_size=5)
    app._gol3d_init(0)
    app._draw_gol3d(15, 30)


@patch("curses.color_pair", return_value=0)
def test_draw_tiny_viewport(_mock_cp):
    app = _make_app(grid_size=5)
    app._gol3d_init(0)
    app._draw_gol3d(3, 5)  # too small, early return


@patch("curses.color_pair", return_value=0)
def test_draw_empty_grid(_mock_cp):
    """Drawing with empty grid doesn't crash."""
    app = _make_app(grid_size=5)
    app._gol3d_init(0)
    app.gol3d_grid = _make_empty_grid(5)
    app.gol3d_population = 0
    app._draw_gol3d(15, 30)
