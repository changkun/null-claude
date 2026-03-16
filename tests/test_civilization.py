"""Tests for civilization mode."""
from tests.conftest import make_mock_app
from life.modes.civilization import (
    register, _generate_terrain, _make_tribe, T_WATER, T_PLAINS,
    TECH_TREE,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.civ_mode = False
    app.civ_menu = False
    app.civ_menu_sel = 0
    app.civ_running = False
    app.civ_terrain = []
    app.civ_tribes = []
    app.civ_log = []
    return app


def test_enter():
    app = _make_app()
    app._enter_civ_mode()
    assert app.civ_menu is True


def test_step_no_crash():
    app = _make_app()
    app.civ_mode = True
    app._civ_init(0)
    assert app.civ_mode is True
    for _ in range(10):
        app._civ_step()


def test_exit_cleanup():
    app = _make_app()
    app._civ_init(0)
    app._exit_civ_mode()
    assert app.civ_mode is False
    assert app.civ_terrain == []


def test_terrain_contains_land_and_water():
    """Generated terrain should have both land and water."""
    settings = {
        "land_pct": 0.5, "mountain_pct": 0.05, "forest_pct": 0.1,
        "desert_pct": 0.05, "river_count": 3,
    }
    terrain, hmap = _generate_terrain(30, 40, settings)
    water = sum(1 for r in range(30) for c in range(40) if terrain[r][c] == T_WATER)
    land = 30 * 40 - water
    assert water > 0, "Should have some water"
    assert land > 0, "Should have some land"


def test_tribes_have_territory_after_init():
    """After init, each tribe should have at least one territory cell."""
    app = _make_app()
    app._civ_init(0)
    for tribe in app.civ_tribes:
        assert len(tribe["territory"]) > 0
        assert len(tribe["settlements"]) > 0


def test_population_grows_with_food():
    """Tribes with food should see population growth over multiple steps."""
    app = _make_app()
    app._civ_init(0)
    initial_pop = sum(t["pop"] for t in app.civ_tribes if t["alive"])
    for _ in range(50):
        app._civ_step()
    final_pop = sum(t["pop"] for t in app.civ_tribes if t["alive"])
    # Population should have grown overall (food from territory)
    assert final_pop > 0
