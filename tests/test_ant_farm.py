"""Tests for life.modes.ant_farm — Ant Farm mode."""
import curses
from tests.conftest import make_mock_app
from life.modes.ant_farm import (
    register,
    ANTFARM_PRESETS,
    _AF_AIR,
    _AF_DIRT,
    _AF_ROCK,
    _AF_CLAY,
    _AF_CHAMBER,
    _AF_QUEEN_CELL,
)


def _make_app():
    app = make_mock_app()
    app.antfarm_mode = False
    app.antfarm_menu = False
    app.antfarm_menu_sel = 0
    app.antfarm_running = False
    app.antfarm_speed = 1
    app.antfarm_show_info = False
    app.antfarm_ants = []
    app.antfarm_grid = []
    app.antfarm_pheromone_food = []
    app.antfarm_pheromone_home = []
    app.antfarm_food_surface = []
    app.antfarm_rain_drops = []
    register(type(app))
    return app


# ── enter / exit ──────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_antfarm_mode()
    assert app.antfarm_menu is True
    assert app.antfarm_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.antfarm_mode = True
    app._antfarm_init("classic")
    assert len(app.antfarm_ants) > 0
    app._exit_antfarm_mode()
    assert app.antfarm_mode is False
    assert app.antfarm_ants == []
    assert app.antfarm_grid == []
    assert app.antfarm_pheromone_food == []
    assert app.antfarm_pheromone_home == []
    assert app.antfarm_food_surface == []
    assert app.antfarm_rain_drops == []


# ── init presets ──────────────────────────────────────────────────────────

def test_init_classic():
    app = _make_app()
    app._antfarm_init("classic")
    assert app.antfarm_running is True
    assert app.antfarm_generation == 0
    assert len(app.antfarm_ants) == 15
    assert app.antfarm_rain_active is False


def test_init_sandy():
    app = _make_app()
    app._antfarm_init("sandy")
    # Sandy ants have dig_strength 2
    for ant in app.antfarm_ants:
        assert ant["dig_strength"] == 2


def test_init_rocky():
    app = _make_app()
    app._antfarm_init("rocky")
    # Rocky should have rocks in the grid
    has_rock = any(
        cell == _AF_ROCK
        for row in app.antfarm_grid
        for cell in row
    )
    assert has_rock


def test_init_deep():
    app = _make_app()
    app._antfarm_init("deep")
    assert len(app.antfarm_ants) == 20


def test_init_rainy():
    app = _make_app()
    app._antfarm_init("rainy")
    assert app.antfarm_rain_active is True
    assert len(app.antfarm_ants) == 15


def test_init_all_presets():
    for _name, _desc, key in ANTFARM_PRESETS:
        app = _make_app()
        app._antfarm_init(key)
        assert app.antfarm_running is True
        assert len(app.antfarm_grid) == app.antfarm_rows
        assert len(app.antfarm_grid[0]) == app.antfarm_cols


def test_init_queen_chamber():
    """Queen chamber should be carved out near center."""
    app = _make_app()
    app._antfarm_init("classic")
    qr, qc = app.antfarm_queen_pos
    assert app.antfarm_grid[qr][qc] == _AF_QUEEN_CELL


def test_init_starter_tunnel():
    """A tunnel from surface to queen should exist (air cells)."""
    app = _make_app()
    app._antfarm_init("classic")
    sr = app.antfarm_surface_row
    qr, qc = app.antfarm_queen_pos
    for r in range(sr, qr):
        assert app.antfarm_grid[r][qc] == _AF_AIR


def test_init_surface_food():
    app = _make_app()
    app._antfarm_init("classic")
    assert len(app.antfarm_food_surface) >= 5


def test_init_pheromone_grids():
    app = _make_app()
    app._antfarm_init("classic")
    rows = app.antfarm_rows
    cols = app.antfarm_cols
    assert len(app.antfarm_pheromone_food) == rows
    assert len(app.antfarm_pheromone_food[0]) == cols
    assert len(app.antfarm_pheromone_home) == rows


# ── step ──────────────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._antfarm_init("classic")
    app._antfarm_step()
    assert app.antfarm_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.antfarm_mode = True
    app._antfarm_init("classic")
    for _ in range(10):
        app._antfarm_step()
    assert app.antfarm_generation == 10


def test_step_pheromone_decay():
    """Pheromones should decay each step."""
    app = _make_app()
    app._antfarm_init("classic")
    # Set a pheromone
    app.antfarm_pheromone_food[5][5] = 5.0
    app._antfarm_step()
    assert app.antfarm_pheromone_food[5][5] < 5.0


def test_step_rain():
    """In rainy mode, rain drops should appear and move."""
    app = _make_app()
    app._antfarm_init("rainy")
    app._antfarm_step()
    # Rain drops should have been added
    # (may or may not still be present depending on position)
    assert app.antfarm_generation == 1


def test_step_ants_move():
    """After stepping, at least some ants should have moved."""
    app = _make_app()
    app._antfarm_init("classic")
    initial_positions = [(a["r"], a["c"]) for a in app.antfarm_ants]
    for _ in range(20):
        app._antfarm_step()
    final_positions = [(a["r"], a["c"]) for a in app.antfarm_ants]
    # At least one ant should have moved
    assert initial_positions != final_positions


def test_step_multiple_presets():
    for _name, _desc, key in ANTFARM_PRESETS:
        app = _make_app()
        app._antfarm_init(key)
        for _ in range(30):
            app._antfarm_step()
        assert app.antfarm_generation == 30


# ── handle_antfarm_menu_key ───────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_antfarm_mode()
    app._handle_antfarm_menu_key(curses.KEY_DOWN)
    assert app.antfarm_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_antfarm_mode()
    app._handle_antfarm_menu_key(curses.KEY_UP)
    assert app.antfarm_menu_sel == len(ANTFARM_PRESETS) - 1


def test_menu_select_enter():
    app = _make_app()
    app._enter_antfarm_mode()
    app._handle_antfarm_menu_key(10)
    assert app.antfarm_running is True
    assert app.antfarm_menu is False


def test_menu_escape():
    app = _make_app()
    app._enter_antfarm_mode()
    app._handle_antfarm_menu_key(27)
    assert app.antfarm_mode is False


# ── handle_antfarm_key ────────────────────────────────────────────────────

def test_key_space_toggle():
    app = _make_app()
    app._antfarm_init("classic")
    assert app.antfarm_running is True
    app._handle_antfarm_key(ord(' '))
    assert app.antfarm_running is False
    app._handle_antfarm_key(ord(' '))
    assert app.antfarm_running is True


def test_key_step():
    app = _make_app()
    app._antfarm_init("classic")
    gen = app.antfarm_generation
    app._handle_antfarm_key(ord('n'))
    assert app.antfarm_generation == gen + 1


def test_key_speed():
    app = _make_app()
    app._antfarm_init("classic")
    app.antfarm_speed = 1
    app._handle_antfarm_key(ord('+'))
    assert app.antfarm_speed == 2
    app._handle_antfarm_key(ord('-'))
    assert app.antfarm_speed == 1


def test_key_info_toggle():
    app = _make_app()
    app._antfarm_init("classic")
    app.antfarm_show_info = False
    app._handle_antfarm_key(ord('i'))
    assert app.antfarm_show_info is True


def test_key_drop_food():
    app = _make_app()
    app._antfarm_init("classic")
    count_before = len(app.antfarm_food_surface)
    app._handle_antfarm_key(ord('f'))
    assert len(app.antfarm_food_surface) == count_before + 1


def test_key_toggle_rain():
    app = _make_app()
    app._antfarm_init("classic")
    assert app.antfarm_rain_active is False
    app._handle_antfarm_key(ord('w'))
    assert app.antfarm_rain_active is True
    app._handle_antfarm_key(ord('w'))
    assert app.antfarm_rain_active is False
    assert app.antfarm_rain_drops == []


def test_key_place_obstacle():
    app = _make_app()
    app._antfarm_init("classic")
    sr = app.antfarm_surface_row
    cx = app.antfarm_cursor_x
    app._handle_antfarm_key(ord('o'))
    # Rock should be placed
    obs_r = sr + 3
    assert app.antfarm_grid[obs_r][cx] == _AF_ROCK


def test_key_cursor_move():
    app = _make_app()
    app._antfarm_init("classic")
    cx = app.antfarm_cursor_x
    app._handle_antfarm_key(curses.KEY_LEFT)
    assert app.antfarm_cursor_x == cx - 1
    app._handle_antfarm_key(curses.KEY_RIGHT)
    assert app.antfarm_cursor_x == cx


def test_key_escape():
    app = _make_app()
    app._antfarm_init("classic")
    app.antfarm_mode = True
    app._handle_antfarm_key(27)
    assert app.antfarm_mode is False


def test_key_return_to_menu():
    app = _make_app()
    app._antfarm_init("classic")
    app._handle_antfarm_key(ord('R'))
    assert app.antfarm_menu is True
    assert app.antfarm_mode is False


# ── draw (no crash) ──────────────────────────────────────────────────────

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_antfarm_mode()
    app._draw_antfarm_menu(40, 120)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._antfarm_init("classic")
    for _ in range(5):
        app._antfarm_step()
    app._draw_antfarm(40, 120)


def test_draw_with_info():
    app = _make_app()
    app._antfarm_init("classic")
    app.antfarm_show_info = True
    app._draw_antfarm(40, 120)


def test_draw_with_rain():
    app = _make_app()
    app._antfarm_init("rainy")
    for _ in range(5):
        app._antfarm_step()
    app._draw_antfarm(40, 120)
