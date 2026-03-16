"""Tests for falling_sand mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.falling_sand import register


# Sand element type constants
SAND_EMPTY = 0
SAND_SAND = 1
SAND_WATER = 2
SAND_FIRE = 3
SAND_STONE = 4
SAND_PLANT = 5
SAND_OIL = 6
SAND_STEAM = 7

SAND_PRESETS = [
    ("Empty", "Start with an empty grid", "empty"),
    ("Hourglass", "Sand flowing through a narrow gap", "hourglass"),
    ("Rainfall", "Water flowing over stone platforms", "rainfall"),
    ("Bonfire", "Fire spreading through a forest", "bonfire"),
    ("Lava Lamp", "Layered sand and water", "lavalamp"),
    ("Forest", "Dense plant growth with fire", "forest"),
    ("Oil Rig", "Oil floating on water with fire", "oilrig"),
    ("Waterfall", "Water cascading over ledges", "waterfall"),
]

SAND_ELEM_NAMES = {
    0: "empty", 1: "sand", 2: "water", 3: "fire",
    4: "stone", 5: "plant", 6: "oil", 7: "steam",
}
SAND_ELEM_COLORS = {
    0: 0, 1: 3, 2: 4, 3: 1, 4: 6, 5: 2, 6: 5, 7: 7,
}
SAND_ELEM_CHARS = {
    1: "\u2591\u2591", 2: "\u2248\u2248", 3: "\u2588\u2588",
    4: "\u2588\u2588", 5: "\u2663\u2663", 6: "\u2592\u2592",
    7: "\u00b0\u00b0",
}


def _make_sand_app():
    """Create a mock app with sand mode registered."""
    app = make_mock_app()
    cls = type(app)
    cls.SAND_EMPTY = SAND_EMPTY
    cls.SAND_SAND = SAND_SAND
    cls.SAND_WATER = SAND_WATER
    cls.SAND_FIRE = SAND_FIRE
    cls.SAND_STONE = SAND_STONE
    cls.SAND_PLANT = SAND_PLANT
    cls.SAND_OIL = SAND_OIL
    cls.SAND_STEAM = SAND_STEAM
    cls.SAND_PRESETS = SAND_PRESETS
    cls.SAND_ELEM_NAMES = SAND_ELEM_NAMES
    cls.SAND_ELEM_COLORS = SAND_ELEM_COLORS
    cls.SAND_ELEM_CHARS = SAND_ELEM_CHARS
    register(cls)
    return app


class TestFallingSand:
    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()

    def test_enter(self):
        self.app._enter_sand_mode()
        assert self.app.sand_menu is True
        assert self.app.sand_menu_sel == 0

    def test_init_empty(self):
        self.app.sand_mode = True
        self.app.sand_running = False
        self.app._sand_init("empty")
        assert self.app.sand_grid == {}
        assert self.app.sand_generation == 0

    def test_init_with_preset(self):
        self.app.sand_mode = True
        self.app.sand_running = False
        self.app._sand_init("hourglass")
        assert len(self.app.sand_grid) > 0

    def test_step_no_crash(self):
        self.app.sand_mode = True
        self.app.sand_running = False
        self.app._sand_init("empty")
        # Place some sand particles
        self.app.sand_grid[(5, 10)] = (SAND_SAND, 0)
        self.app.sand_grid[(5, 11)] = (SAND_SAND, 0)
        self.app.sand_grid[(5, 12)] = (SAND_SAND, 0)
        for _ in range(10):
            self.app._sand_step()
        assert self.app.sand_generation == 10

    def test_sand_falls(self):
        self.app.sand_mode = True
        self.app._sand_init("empty")
        self.app.sand_grid[(5, 10)] = (SAND_SAND, 0)
        self.app._sand_step()
        # Sand should have moved down
        assert (5, 10) not in self.app.sand_grid
        assert (6, 10) in self.app.sand_grid

    def test_stone_stays(self):
        self.app.sand_mode = True
        self.app._sand_init("empty")
        self.app.sand_grid[(5, 10)] = (SAND_STONE, 0)
        self.app._sand_step()
        assert self.app.sand_grid.get((5, 10)) == (SAND_STONE, 0)

    def test_paint(self):
        self.app.sand_mode = True
        self.app._sand_init("empty")
        self.app.sand_brush = SAND_SAND
        self.app.sand_brush_size = 1
        self.app.sand_cursor_r = 10
        self.app.sand_cursor_c = 10
        self.app._sand_paint()
        assert (10, 10) in self.app.sand_grid

    def test_exit_cleanup(self):
        self.app.sand_mode = True
        self.app._sand_init("empty")
        self.app.sand_grid[(5, 5)] = (SAND_SAND, 0)
        self.app._exit_sand_mode()
        assert self.app.sand_mode is False
        assert self.app.sand_menu is False
        assert self.app.sand_running is False
        assert self.app.sand_grid == {}


# ---------------------------------------------------------------------------
# Physics logic tests
# ---------------------------------------------------------------------------

class TestSandGravity:
    """Sand particle gravity and pile formation."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_sand_falls_one_cell_per_tick(self):
        self.app.sand_grid[(3, 10)] = (SAND_SAND, 0)
        self.app._sand_step()
        assert self.app.sand_grid.get((4, 10), (None,))[0] == SAND_SAND
        assert (3, 10) not in self.app.sand_grid

    def test_sand_stops_at_bottom(self):
        """Sand at the bottom row stays put."""
        bottom = self.app.sand_rows - 1
        self.app.sand_grid[(bottom, 10)] = (SAND_SAND, 0)
        self.app._sand_step()
        assert self.app.sand_grid.get((bottom, 10), (None,))[0] == SAND_SAND

    def test_sand_stops_on_stone(self):
        """Sand rests on top of a stone block when diagonals are also blocked."""
        self.app.sand_grid[(8, 10)] = (SAND_SAND, 0)
        self.app.sand_grid[(9, 10)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        assert self.app.sand_grid.get((8, 10), (None,))[0] == SAND_SAND
        assert self.app.sand_grid.get((9, 10), (None,))[0] == SAND_STONE

    def test_sand_diagonal_slide(self):
        """Sand slides diagonally when directly below is blocked."""
        self.app.sand_grid[(8, 10)] = (SAND_SAND, 0)
        self.app.sand_grid[(9, 10)] = (SAND_STONE, 0)
        # Leave (9, 9) and (9, 11) open so sand can slide
        self.app._sand_step()
        # Sand either stays at (8, 10) or moved to (9, 9) or (9, 11)
        sand_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_SAND]
        assert len(sand_cells) == 1
        r, c = sand_cells[0]
        assert r == 9 and c in (9, 11), f"Sand should slide diagonally, got ({r}, {c})"

    def test_sand_piles_form(self):
        """Multiple sand grains form a pile on a flat surface."""
        # Stone floor
        for c in range(5, 16):
            self.app.sand_grid[(20, c)] = (SAND_STONE, 0)
        # Drop sand from same column
        self.app.sand_grid[(10, 10)] = (SAND_SAND, 0)
        for _ in range(15):
            self.app._sand_step()
        # Sand should be resting on the stone floor
        sand_positions = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_SAND]
        assert len(sand_positions) == 1
        assert sand_positions[0][0] == 19  # One row above stone

    def test_sand_sinks_through_water(self):
        """Sand displaces water when water is resting on stone."""
        # Water must be blocked from moving so it stays for the swap
        self.app.sand_grid[(5, 10)] = (SAND_SAND, 0)
        self.app.sand_grid[(6, 10)] = (SAND_WATER, 0)
        self.app.sand_grid[(7, 10)] = (SAND_STONE, 0)
        # Block water's diagonals and sides so it stays at (6, 10)
        self.app.sand_grid[(7, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(7, 11)] = (SAND_STONE, 0)
        self.app.sand_grid[(6, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(6, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        # Sand should swap with water
        assert self.app.sand_grid.get((6, 10), (None,))[0] == SAND_SAND
        assert self.app.sand_grid.get((5, 10), (None,))[0] == SAND_WATER

    def test_sand_sinks_through_oil(self):
        """Sand displaces oil when oil is resting on stone."""
        self.app.sand_grid[(5, 10)] = (SAND_SAND, 0)
        self.app.sand_grid[(6, 10)] = (SAND_OIL, 0)
        self.app.sand_grid[(7, 10)] = (SAND_STONE, 0)
        self.app.sand_grid[(7, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(7, 11)] = (SAND_STONE, 0)
        self.app.sand_grid[(6, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(6, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        assert self.app.sand_grid.get((6, 10), (None,))[0] == SAND_SAND
        assert self.app.sand_grid.get((5, 10), (None,))[0] == SAND_OIL

    def test_sand_age_increments(self):
        """Sand age increases each tick it moves."""
        self.app.sand_grid[(5, 10)] = (SAND_SAND, 0)
        self.app._sand_step()
        _, age = self.app.sand_grid[(6, 10)]
        assert age == 1


class TestWaterPhysics:
    """Water flow, gravity, and liquid interactions."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_water_falls_down(self):
        self.app.sand_grid[(5, 10)] = (SAND_WATER, 0)
        self.app._sand_step()
        assert (5, 10) not in self.app.sand_grid
        assert self.app.sand_grid.get((6, 10), (None,))[0] == SAND_WATER

    def test_water_flows_sideways(self):
        """Water spreads horizontally when it can't fall."""
        # Stone floor
        for c in range(8, 13):
            self.app.sand_grid[(10, c)] = (SAND_STONE, 0)
        # Water sitting on stone
        self.app.sand_grid[(9, 10)] = (SAND_WATER, 0)
        # Block below and both diagonals below
        self.app.sand_grid[(10, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(10, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        # Water should have moved sideways (to 9,9 or 9,11)
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        assert len(water_cells) == 1
        r, c = water_cells[0]
        assert r == 9, "Water should stay at same row"
        assert c != 10, "Water should have moved sideways"

    def test_water_stops_at_bottom(self):
        bottom = self.app.sand_rows - 1
        self.app.sand_grid[(bottom, 10)] = (SAND_WATER, 0)
        self.app._sand_step()
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        assert len(water_cells) == 1

    def test_water_sinks_below_oil(self):
        """Water swaps with oil below it (water is denser)."""
        # Oil must be blocked from moving so it stays for the swap
        self.app.sand_grid[(5, 10)] = (SAND_WATER, 0)
        self.app.sand_grid[(6, 10)] = (SAND_OIL, 0)
        self.app.sand_grid[(7, 10)] = (SAND_STONE, 0)
        self.app.sand_grid[(7, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(7, 11)] = (SAND_STONE, 0)
        self.app.sand_grid[(6, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(6, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        assert self.app.sand_grid.get((6, 10), (None,))[0] == SAND_WATER
        assert self.app.sand_grid.get((5, 10), (None,))[0] == SAND_OIL

    def test_water_diagonal_flow(self):
        """Water tries diagonals before sideways."""
        self.app.sand_grid[(5, 10)] = (SAND_WATER, 0)
        self.app.sand_grid[(6, 10)] = (SAND_STONE, 0)
        # Leave diagonals open
        self.app._sand_step()
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        assert len(water_cells) == 1
        r, c = water_cells[0]
        # Should have gone diagonal down (6, 9 or 6, 11)
        assert r == 6 and c in (9, 11), f"Water should flow diagonally, got ({r}, {c})"

    def test_water_fills_container(self):
        """Water fills up within stone walls."""
        # Build a simple container: floor + walls
        for c in range(8, 13):
            self.app.sand_grid[(12, c)] = (SAND_STONE, 0)
        self.app.sand_grid[(10, 8)] = (SAND_STONE, 0)
        self.app.sand_grid[(11, 8)] = (SAND_STONE, 0)
        self.app.sand_grid[(10, 12)] = (SAND_STONE, 0)
        self.app.sand_grid[(11, 12)] = (SAND_STONE, 0)
        # Drop water inside
        self.app.sand_grid[(5, 10)] = (SAND_WATER, 0)
        for _ in range(20):
            self.app._sand_step()
        # Water should be inside the container
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        assert len(water_cells) == 1
        r, c = water_cells[0]
        assert r == 11, f"Water should settle at row 11, got row {r}"


class TestOilPhysics:
    """Oil buoyancy and flow behavior."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_oil_falls_into_empty(self):
        self.app.sand_grid[(5, 10)] = (SAND_OIL, 0)
        self.app._sand_step()
        assert (5, 10) not in self.app.sand_grid
        assert self.app.sand_grid.get((6, 10), (None,))[0] == SAND_OIL

    def test_oil_does_not_sink_through_water(self):
        """Oil floats on water -- it must NOT swap down through water."""
        # Oil on top, water below, stone floor
        self.app.sand_grid[(9, 10)] = (SAND_OIL, 0)
        self.app.sand_grid[(10, 10)] = (SAND_WATER, 0)
        self.app.sand_grid[(11, 10)] = (SAND_STONE, 0)
        # Block diagonals and sides to force oil to stay
        self.app.sand_grid[(10, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(10, 11)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        # Oil should still be on top of water
        oil_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_OIL]
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        assert len(oil_cells) == 1
        assert len(water_cells) == 1
        assert oil_cells[0][0] <= water_cells[0][0], "Oil should remain above water"

    def test_oil_flows_sideways(self):
        """Oil spreads sideways like water."""
        for c in range(8, 13):
            self.app.sand_grid[(10, c)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 10)] = (SAND_OIL, 0)
        self.app.sand_grid[(10, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(10, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        oil_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_OIL]
        assert len(oil_cells) == 1
        r, c = oil_cells[0]
        assert r == 9 and c != 10, "Oil should flow sideways"

    def test_oil_stops_at_bottom(self):
        bottom = self.app.sand_rows - 1
        self.app.sand_grid[(bottom, 10)] = (SAND_OIL, 0)
        self.app._sand_step()
        oil_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_OIL]
        assert len(oil_cells) == 1


class TestFirePhysics:
    """Fire behavior: rising, lifetime, ignition."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_fire_rises(self):
        """Fire moves upward."""
        self.app.sand_grid[(10, 10)] = (SAND_FIRE, 0)
        # Run several ticks; fire should move upward on average
        positions = []
        for _ in range(5):
            random.seed(0)  # bias toward rising
            self.app._sand_step()
            fire_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_FIRE]
            if fire_cells:
                positions.append(fire_cells[0][0])
        # At least one tick should show upward movement
        if positions:
            assert positions[-1] <= 10, "Fire should have risen or stayed"

    def test_fire_has_finite_lifetime(self):
        """Fire eventually dies out after enough ticks."""
        self.app.sand_grid[(10, 10)] = (SAND_FIRE, 0)
        for _ in range(50):
            self.app._sand_step()
        fire_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_FIRE]
        # After 50 ticks, fire with max age ~20 should be dead
        assert len(fire_cells) == 0, "Fire should have died out"

    def test_fire_ignites_plant(self):
        """Fire spreads to adjacent plant cells."""
        # Place fire surrounded by plants -- run many ticks
        self.app.sand_grid[(10, 10)] = (SAND_FIRE, 0)
        self.app.sand_grid[(10, 11)] = (SAND_PLANT, 0)
        self.app.sand_grid[(10, 9)] = (SAND_PLANT, 0)
        self.app.sand_grid[(9, 10)] = (SAND_PLANT, 0)
        self.app.sand_grid[(11, 10)] = (SAND_PLANT, 0)
        ignited = False
        for _ in range(30):
            random.seed(random.randint(0, 100))
            self.app._sand_step()
            fire_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_FIRE]
            if len(fire_cells) > 1:
                ignited = True
                break
        # With 40% chance per adj plant per tick, should ignite quickly
        assert ignited, "Fire should spread to adjacent plants"

    def test_fire_ignites_oil(self):
        """Fire spreads to adjacent oil cells."""
        self.app.sand_grid[(10, 10)] = (SAND_FIRE, 0)
        self.app.sand_grid[(10, 11)] = (SAND_OIL, 0)
        ignited = False
        for _ in range(30):
            random.seed(random.randint(0, 100))
            self.app._sand_step()
            fire_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_FIRE]
            if len(fire_cells) > 1:
                ignited = True
                break
        assert ignited, "Fire should ignite adjacent oil"

    def test_fire_produces_steam_on_death(self):
        """Fire can produce steam when it dies (20% chance)."""
        steam_produced = False
        for trial in range(20):
            app = _make_sand_app()
            app.sand_mode = True
            app._sand_init("empty")
            # Set fire with high age so it dies next tick
            app.sand_grid[(10, 10)] = (SAND_FIRE, 25)
            random.seed(trial)
            app._sand_step()
            steam_cells = [(r, c) for (r, c), (e, _) in app.sand_grid.items() if e == SAND_STEAM]
            if steam_cells:
                steam_produced = True
                break
        assert steam_produced, "Fire should sometimes produce steam on death"

    def test_fire_evaporates_water_to_steam(self):
        """Fire near water can turn water into steam (8% chance)."""
        steam_produced = False
        for trial in range(100):
            app = _make_sand_app()
            app.sand_mode = True
            app._sand_init("empty")
            app.sand_grid[(10, 10)] = (SAND_FIRE, 0)
            app.sand_grid[(10, 11)] = (SAND_WATER, 0)
            random.seed(trial)
            app._sand_step()
            steam_cells = [(r, c) for (r, c), (e, _) in app.sand_grid.items() if e == SAND_STEAM]
            if steam_cells:
                steam_produced = True
                break
        assert steam_produced, "Fire should sometimes evaporate water to steam"


class TestSteamPhysics:
    """Steam rising and condensation."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_steam_rises(self):
        """Steam moves upward."""
        self.app.sand_grid[(15, 10)] = (SAND_STEAM, 0)
        random.seed(0)
        self.app._sand_step()
        steam_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_STEAM]
        assert len(steam_cells) == 1
        r, _ = steam_cells[0]
        assert r <= 15, "Steam should rise or drift, not fall"

    def test_steam_condenses_to_water(self):
        """Old steam condenses back to water (40% chance)."""
        water_produced = False
        for trial in range(20):
            app = _make_sand_app()
            app.sand_mode = True
            app._sand_init("empty")
            # Set steam with high age so it condenses next tick
            app.sand_grid[(10, 10)] = (SAND_STEAM, 30)
            random.seed(trial)
            app._sand_step()
            water_cells = [(r, c) for (r, c), (e, _) in app.sand_grid.items() if e == SAND_WATER]
            if water_cells:
                water_produced = True
                break
        assert water_produced, "Old steam should sometimes condense to water"

    def test_steam_vanishes_on_old_age(self):
        """Steam eventually disappears."""
        self.app.sand_grid[(10, 10)] = (SAND_STEAM, 0)
        for _ in range(60):
            self.app._sand_step()
        steam_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_STEAM]
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        # Either turned to water or vanished -- no steam left
        assert len(steam_cells) == 0, "Steam should have condensed or vanished"

    def test_steam_stops_at_top(self):
        """Steam at row 0 doesn't crash."""
        self.app.sand_grid[(0, 10)] = (SAND_STEAM, 0)
        self.app._sand_step()
        # Should not crash; steam stays or drifts sideways
        total = sum(1 for (_, _), (e, _) in self.app.sand_grid.items() if e == SAND_STEAM)
        assert total <= 1


class TestPlantPhysics:
    """Plant growth and interactions."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_plant_stays_in_place(self):
        """Plants don't fall -- they are static."""
        self.app.sand_grid[(10, 10)] = (SAND_PLANT, 0)
        self.app._sand_step()
        assert self.app.sand_grid.get((10, 10), (None,))[0] == SAND_PLANT

    def test_plant_grows_near_water(self):
        """Plant grows into adjacent empty cells when water is nearby."""
        grew = False
        for trial in range(50):
            app = _make_sand_app()
            app.sand_mode = True
            app._sand_init("empty")
            app.sand_grid[(10, 10)] = (SAND_PLANT, 0)
            app.sand_grid[(10, 11)] = (SAND_WATER, 0)
            random.seed(trial)
            app._sand_step()
            plant_cells = [(r, c) for (r, c), (e, _) in app.sand_grid.items() if e == SAND_PLANT]
            if len(plant_cells) > 1:
                grew = True
                break
        assert grew, "Plant should sometimes grow when adjacent to water"

    def test_plant_does_not_grow_without_water(self):
        """Plant does not grow when no water is adjacent."""
        self.app.sand_grid[(10, 10)] = (SAND_PLANT, 0)
        initial_plants = 1
        for _ in range(20):
            self.app._sand_step()
        plant_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_PLANT]
        assert len(plant_cells) == initial_plants, "Plant should not grow without water"


class TestStonePhysics:
    """Stone (static wall) behavior."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_stone_immovable(self):
        """Stone never moves."""
        self.app.sand_grid[(10, 10)] = (SAND_STONE, 0)
        for _ in range(10):
            self.app._sand_step()
        assert self.app.sand_grid.get((10, 10)) == (SAND_STONE, 0)

    def test_stone_blocks_sand(self):
        """Stone blocks sand from falling through."""
        self.app.sand_grid[(8, 10)] = (SAND_SAND, 0)
        self.app.sand_grid[(9, 10)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        # Sand should stay at (8, 10) since all below is blocked
        assert self.app.sand_grid.get((8, 10), (None,))[0] == SAND_SAND

    def test_stone_blocks_water(self):
        """Stone blocks water from falling through."""
        self.app.sand_grid[(8, 10)] = (SAND_WATER, 0)
        self.app.sand_grid[(9, 10)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 9)] = (SAND_STONE, 0)
        self.app.sand_grid[(9, 11)] = (SAND_STONE, 0)
        self.app._sand_step()
        # Water should flow sideways, not pass through stone
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        assert len(water_cells) == 1
        r, c = water_cells[0]
        assert r <= 9, "Water should not pass through stone"


class TestDensityLayering:
    """Test density-based layering: sand > water > oil."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_sand_sinks_through_water_layer(self):
        """Sand placed above water in a container sinks to the bottom."""
        # Build a container: walls + floor
        for r in range(9, 16):
            self.app.sand_grid[(r, 8)] = (SAND_STONE, 0)
            self.app.sand_grid[(r, 12)] = (SAND_STONE, 0)
        for c in range(8, 13):
            self.app.sand_grid[(16, c)] = (SAND_STONE, 0)
        # Fill container with water
        for r in range(12, 16):
            for c in range(9, 12):
                self.app.sand_grid[(r, c)] = (SAND_WATER, 0)
        # Drop sand on top
        self.app.sand_grid[(9, 10)] = (SAND_SAND, 0)
        for _ in range(30):
            self.app._sand_step()
        sand_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_SAND]
        water_cells = [(r, c) for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        assert len(sand_cells) >= 1
        # Sand should be at or near the bottom of the container
        sand_r = max(r for r, _ in sand_cells)
        assert sand_r >= 14, f"Sand should have sunk near the bottom, got row {sand_r}"

    def test_oil_water_separation(self):
        """Oil and water separate with oil floating on top."""
        # Interleave oil and water in a container
        for c in range(8, 13):
            self.app.sand_grid[(15, c)] = (SAND_STONE, 0)
        self.app.sand_grid[(10, 8)] = (SAND_STONE, 0)
        self.app.sand_grid[(11, 8)] = (SAND_STONE, 0)
        self.app.sand_grid[(12, 8)] = (SAND_STONE, 0)
        self.app.sand_grid[(13, 8)] = (SAND_STONE, 0)
        self.app.sand_grid[(14, 8)] = (SAND_STONE, 0)
        self.app.sand_grid[(10, 12)] = (SAND_STONE, 0)
        self.app.sand_grid[(11, 12)] = (SAND_STONE, 0)
        self.app.sand_grid[(12, 12)] = (SAND_STONE, 0)
        self.app.sand_grid[(13, 12)] = (SAND_STONE, 0)
        self.app.sand_grid[(14, 12)] = (SAND_STONE, 0)
        # Place water and oil mixed
        self.app.sand_grid[(12, 10)] = (SAND_OIL, 0)
        self.app.sand_grid[(13, 10)] = (SAND_WATER, 0)
        self.app.sand_grid[(14, 10)] = (SAND_OIL, 0)
        for _ in range(30):
            self.app._sand_step()
        oil_rows = [r for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_OIL]
        water_rows = [r for (r, c), (e, _) in self.app.sand_grid.items() if e == SAND_WATER]
        if oil_rows and water_rows:
            # On average, oil should be above water
            avg_oil = sum(oil_rows) / len(oil_rows)
            avg_water = sum(water_rows) / len(water_rows)
            assert avg_oil <= avg_water, f"Oil (avg row {avg_oil}) should float above water (avg row {avg_water})"


class TestParticleConservation:
    """Verify that particles are conserved (not created or destroyed unexpectedly)."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_sand_count_conserved(self):
        """Number of sand particles stays constant."""
        for c in range(8, 13):
            self.app.sand_grid[(5, c)] = (SAND_SAND, 0)
        initial = 5
        for _ in range(20):
            self.app._sand_step()
        sand_count = sum(1 for (_, _), (e, _) in self.app.sand_grid.items() if e == SAND_SAND)
        assert sand_count == initial, f"Expected {initial} sand, got {sand_count}"

    def test_stone_count_conserved(self):
        """Number of stone blocks stays constant."""
        for c in range(5, 15):
            self.app.sand_grid[(20, c)] = (SAND_STONE, 0)
        initial = 10
        for _ in range(10):
            self.app._sand_step()
        stone_count = sum(1 for (_, _), (e, _) in self.app.sand_grid.items() if e == SAND_STONE)
        assert stone_count == initial

    def test_water_count_conserved_no_fire(self):
        """Water count stays constant when no fire is present."""
        for c in range(8, 13):
            self.app.sand_grid[(5, c)] = (SAND_WATER, 0)
        initial = 5
        for _ in range(20):
            self.app._sand_step()
        water_count = sum(1 for (_, _), (e, _) in self.app.sand_grid.items() if e == SAND_WATER)
        assert water_count == initial, f"Expected {initial} water, got {water_count}"

    def test_oil_count_conserved_no_fire(self):
        """Oil count stays constant when no fire is present."""
        for c in range(8, 13):
            self.app.sand_grid[(5, c)] = (SAND_OIL, 0)
        initial = 5
        for _ in range(20):
            self.app._sand_step()
        oil_count = sum(1 for (_, _), (e, _) in self.app.sand_grid.items() if e == SAND_OIL)
        assert oil_count == initial, f"Expected {initial} oil, got {oil_count}"


class TestPresets:
    """Test that all presets build without error."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True

    @pytest.mark.parametrize("preset_id", [
        "empty", "hourglass", "rainfall", "bonfire", "lavalamp",
        "forest", "oilrig", "waterfall",
    ])
    def test_preset_builds(self, preset_id):
        self.app._sand_init(preset_id)
        if preset_id == "empty":
            assert len(self.app.sand_grid) == 0
        else:
            assert len(self.app.sand_grid) > 0

    @pytest.mark.parametrize("preset_id", [
        "hourglass", "rainfall", "bonfire", "lavalamp",
        "forest", "oilrig", "waterfall",
    ])
    def test_preset_runs_10_ticks(self, preset_id):
        """Each preset runs 10 ticks without crashing."""
        self.app._sand_init(preset_id)
        for _ in range(10):
            self.app._sand_step()
        assert self.app.sand_generation == 10


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_sand_app()
        self.app.sand_mode = True
        self.app._sand_init("empty")

    def test_empty_grid_step(self):
        """Stepping an empty grid doesn't crash."""
        self.app._sand_step()
        assert self.app.sand_generation == 1
        assert len(self.app.sand_grid) == 0

    def test_particle_at_corner(self):
        """Particles at grid corners don't crash."""
        corners = [
            (0, 0), (0, self.app.sand_cols - 1),
            (self.app.sand_rows - 1, 0),
            (self.app.sand_rows - 1, self.app.sand_cols - 1),
        ]
        for r, c in corners:
            self.app.sand_grid[(r, c)] = (SAND_SAND, 0)
        self.app._sand_step()
        # Should not crash
        assert self.app.sand_generation == 1

    def test_all_element_types_simultaneous(self):
        """All element types can coexist without crashing."""
        self.app.sand_grid[(3, 10)] = (SAND_SAND, 0)
        self.app.sand_grid[(3, 12)] = (SAND_WATER, 0)
        self.app.sand_grid[(3, 14)] = (SAND_FIRE, 0)
        self.app.sand_grid[(5, 10)] = (SAND_STONE, 0)
        self.app.sand_grid[(3, 16)] = (SAND_PLANT, 0)
        self.app.sand_grid[(3, 18)] = (SAND_OIL, 0)
        self.app.sand_grid[(3, 20)] = (SAND_STEAM, 0)
        for _ in range(20):
            self.app._sand_step()
        assert self.app.sand_generation == 20

    def test_paint_eraser(self):
        """Eraser brush removes elements."""
        self.app.sand_grid[(10, 10)] = (SAND_SAND, 0)
        self.app.sand_brush = SAND_EMPTY
        self.app.sand_brush_size = 1
        self.app.sand_cursor_r = 10
        self.app.sand_cursor_c = 10
        self.app._sand_paint()
        assert (10, 10) not in self.app.sand_grid

    def test_paint_brush_size(self):
        """Larger brush size paints multiple cells."""
        self.app.sand_brush = SAND_STONE
        self.app.sand_brush_size = 3
        self.app.sand_cursor_r = 15
        self.app.sand_cursor_c = 15
        self.app._sand_paint()
        # Brush size 3 paints a 5x5 area (from -2 to +2)
        painted = sum(1 for (_, _), (e, _) in self.app.sand_grid.items() if e == SAND_STONE)
        assert painted == 25, f"Brush size 3 should paint 25 cells, got {painted}"

    def test_generation_counter(self):
        """Generation counter increments correctly."""
        assert self.app.sand_generation == 0
        for i in range(5):
            self.app._sand_step()
            assert self.app.sand_generation == i + 1

    def test_dense_grid(self):
        """A densely populated grid doesn't crash or lose particles."""
        # Fill a 10x10 region with sand
        for r in range(5, 15):
            for c in range(5, 15):
                self.app.sand_grid[(r, c)] = (SAND_SAND, 0)
        initial_sand = 100
        for _ in range(5):
            self.app._sand_step()
        sand_count = sum(1 for (_, _), (e, _) in self.app.sand_grid.items() if e == SAND_SAND)
        assert sand_count == initial_sand, f"Expected {initial_sand} sand, got {sand_count}"
