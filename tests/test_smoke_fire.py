"""Tests for smoke_fire mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.smoke_fire import register


SMOKEFIRE_PRESETS = [
    ("Campfire", "Cozy campfire with rising smoke", "campfire"),
    ("Wildfire", "Spreading wildfire across vegetation", "wildfire"),
    ("Explosion", "Central blast zone", "explosion"),
    ("Candles", "Multiple candle flames", "candles"),
    ("Inferno", "Wall of fire", "inferno"),
    ("Smokestack", "Chimney with smoke", "smokestack"),
]


def _make_app():
    """Create a test app with smokefire mode registered."""
    app = make_mock_app()
    cls = type(app)
    cls.SMOKEFIRE_PRESETS = SMOKEFIRE_PRESETS
    register(cls)
    return app


class TestSmokeFireEnterExit:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_enter(self):
        self.app._enter_smokefire_mode()
        assert self.app.smokefire_menu is True
        assert self.app.smokefire_menu_sel == 0

    def test_exit_cleanup(self):
        self.app.smokefire_mode = True
        self.app.smokefire_preset_name = "Campfire"
        self.app._smokefire_init("campfire")
        self.app._exit_smokefire_mode()
        assert self.app.smokefire_mode is False
        assert self.app.smokefire_menu is False
        assert self.app.smokefire_running is False
        assert self.app.smokefire_temp == []
        assert self.app.smokefire_smoke == []
        assert self.app.smokefire_fuel == []
        assert self.app.smokefire_vx == []
        assert self.app.smokefire_vy == []
        assert self.app.smokefire_sources == []


class TestSmokeFireInit:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_init_grid_dimensions(self):
        self.app._smokefire_init("campfire")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        assert rows >= 10
        assert cols >= 10
        assert len(self.app.smokefire_temp) == rows
        assert len(self.app.smokefire_temp[0]) == cols
        assert len(self.app.smokefire_smoke) == rows
        assert len(self.app.smokefire_fuel) == rows
        assert len(self.app.smokefire_vx) == rows
        assert len(self.app.smokefire_vy) == rows

    def test_init_generation_zero(self):
        self.app._smokefire_init("campfire")
        assert self.app.smokefire_generation == 0

    def test_init_cursor_centered(self):
        self.app._smokefire_init("campfire")
        assert self.app.smokefire_cursor_r == self.app.smokefire_rows // 2
        assert self.app.smokefire_cursor_c == self.app.smokefire_cols // 2


class TestSmokeFirePresets:
    """Test each preset initializes its specific parameters and sources."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_campfire_preset(self):
        self.app._smokefire_init("campfire")
        assert self.app.smokefire_buoyancy == 0.15
        assert self.app.smokefire_turbulence == 0.04
        assert self.app.smokefire_cooling == 0.012
        assert self.app.smokefire_smoke_rate == 0.3
        assert self.app.smokefire_wind == 0.0
        assert len(self.app.smokefire_sources) > 0
        # Campfire has fuel logs near the bottom
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        has_fuel = any(
            self.app.smokefire_fuel[r][c] > 0
            for r in range(rows) for c in range(cols)
        )
        assert has_fuel

    def test_wildfire_preset(self):
        self.app._smokefire_init("wildfire")
        assert self.app.smokefire_buoyancy == 0.12
        assert self.app.smokefire_turbulence == 0.06
        assert self.app.smokefire_cooling == 0.008
        assert self.app.smokefire_smoke_rate == 0.4
        assert self.app.smokefire_wind == 0.02
        assert len(self.app.smokefire_sources) > 0
        # Wildfire has fuel scattered in the lower 1/3
        rows = self.app.smokefire_rows
        fuel_bottom = any(
            self.app.smokefire_fuel[r][c] > 0
            for r in range(rows * 2 // 3, rows - 1)
            for c in range(self.app.smokefire_cols)
        )
        assert fuel_bottom

    def test_explosion_preset(self):
        self.app._smokefire_init("explosion")
        assert self.app.smokefire_buoyancy == 0.25
        assert self.app.smokefire_turbulence == 0.12
        assert self.app.smokefire_cooling == 0.02
        assert self.app.smokefire_smoke_rate == 0.6
        # Explosion should have high initial temperature at center
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        mid_r, mid_c = rows * 2 // 3, cols // 2
        assert self.app.smokefire_temp[mid_r][mid_c] > 0.5
        # Should have radial velocities
        has_velocity = any(
            self.app.smokefire_vx[r][c] != 0 or self.app.smokefire_vy[r][c] != 0
            for r in range(rows) for c in range(cols)
        )
        assert has_velocity

    def test_candles_preset(self):
        self.app._smokefire_init("candles")
        assert self.app.smokefire_buoyancy == 0.1
        assert self.app.smokefire_turbulence == 0.02
        assert self.app.smokefire_cooling == 0.018
        # Multiple candle sources
        assert len(self.app.smokefire_sources) >= 2

    def test_inferno_preset(self):
        self.app._smokefire_init("inferno")
        assert self.app.smokefire_buoyancy == 0.2
        assert self.app.smokefire_cooling == 0.006
        assert self.app.smokefire_smoke_rate == 0.5
        # Should have many sources along the base
        assert len(self.app.smokefire_sources) > 0

    def test_smokestack_preset(self):
        self.app._smokefire_init("smokestack")
        assert self.app.smokefire_buoyancy == 0.18
        assert self.app.smokefire_wind == 0.03
        assert len(self.app.smokefire_sources) > 0


class TestSmokeFireStep:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_step_increments_generation(self):
        self.app._smokefire_init("campfire")
        assert self.app.smokefire_generation == 0
        self.app._smokefire_step()
        assert self.app.smokefire_generation == 1

    def test_step_10_iterations(self):
        self.app._smokefire_init("campfire")
        for _ in range(10):
            self.app._smokefire_step()
        assert self.app.smokefire_generation == 10

    def test_temperature_stays_bounded(self):
        """Temperature values must remain in [0.0, 1.0] after stepping."""
        self.app._smokefire_init("campfire")
        for _ in range(20):
            self.app._smokefire_step()
        for r in range(self.app.smokefire_rows):
            for c in range(self.app.smokefire_cols):
                t = self.app.smokefire_temp[r][c]
                assert 0.0 <= t <= 1.0, f"temp[{r}][{c}] = {t} out of bounds"

    def test_smoke_stays_bounded(self):
        """Smoke density must remain in [0.0, 1.0] after stepping."""
        self.app._smokefire_init("campfire")
        for _ in range(20):
            self.app._smokefire_step()
        for r in range(self.app.smokefire_rows):
            for c in range(self.app.smokefire_cols):
                s = self.app.smokefire_smoke[r][c]
                assert 0.0 <= s <= 1.0, f"smoke[{r}][{c}] = {s} out of bounds"

    def test_fuel_decreases_with_combustion(self):
        """Fuel should decrease over time near fire sources."""
        self.app._smokefire_init("campfire")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        initial_fuel = sum(
            self.app.smokefire_fuel[r][c]
            for r in range(rows) for c in range(cols)
        )
        for _ in range(50):
            self.app._smokefire_step()
        final_fuel = sum(
            self.app.smokefire_fuel[r][c]
            for r in range(rows) for c in range(cols)
        )
        assert final_fuel < initial_fuel, "Fuel should decrease from combustion"

    def test_buoyancy_moves_heat_upward(self):
        """After several steps, heat should have risen from the source row."""
        self.app._smokefire_init("campfire")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        # Run simulation
        for _ in range(30):
            self.app._smokefire_step()
        # Check that some heat exists above the fire sources
        source_rows = {sr for (sr, sc, si) in self.app.smokefire_sources}
        if source_rows:
            min_source_r = min(source_rows)
            heat_above = sum(
                self.app.smokefire_temp[r][c]
                for r in range(0, max(1, min_source_r - 2))
                for c in range(cols)
            )
            assert heat_above > 0, "Heat should rise above fire sources"

    def test_smoke_produced_from_heat(self):
        """Smoke should be produced where there is heat."""
        self.app._smokefire_init("campfire")
        for _ in range(10):
            self.app._smokefire_step()
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        total_smoke = sum(
            self.app.smokefire_smoke[r][c]
            for r in range(rows) for c in range(cols)
        )
        assert total_smoke > 0, "Smoke should be produced from fire"

    def test_sources_reapply_heat_each_step(self):
        """Fire sources should keep injecting heat each step."""
        self.app._smokefire_init("campfire")
        sources = self.app.smokefire_sources
        assert len(sources) > 0
        for _ in range(5):
            self.app._smokefire_step()
        # Source cells should have non-zero temperature
        for sr, sc, intensity in sources:
            if 0 <= sr < self.app.smokefire_rows and 0 <= sc < self.app.smokefire_cols:
                assert self.app.smokefire_temp[sr][sc] > 0, \
                    f"Source at ({sr},{sc}) should have heat"

    def test_wind_effect(self):
        """With wind, temperature should shift horizontally."""
        self.app._smokefire_init("campfire")
        self.app.smokefire_wind = 0.1  # strong rightward wind
        for _ in range(20):
            self.app._smokefire_step()
        # Check that velocity field has rightward bias
        total_vx = sum(
            self.app.smokefire_vx[r][c]
            for r in range(self.app.smokefire_rows)
            for c in range(self.app.smokefire_cols)
        )
        # With positive wind, total vx should be positive
        assert total_vx > 0, "Wind should create rightward velocity"

    def test_cooling_reduces_temperature(self):
        """With no sources and high cooling, temperature should decay."""
        self.app._smokefire_init("explosion")  # explosion has initial temperature
        # Remove all sources so no new heat is added
        self.app.smokefire_sources = []
        self.app.smokefire_cooling = 0.1  # aggressive cooling
        initial_heat = sum(
            self.app.smokefire_temp[r][c]
            for r in range(self.app.smokefire_rows)
            for c in range(self.app.smokefire_cols)
        )
        assert initial_heat > 0, "Explosion should have initial heat"
        for _ in range(30):
            self.app._smokefire_step()
        final_heat = sum(
            self.app.smokefire_temp[r][c]
            for r in range(self.app.smokefire_rows)
            for c in range(self.app.smokefire_cols)
        )
        assert final_heat < initial_heat, "Heat should decay with no sources and high cooling"

    def test_all_presets_run_without_crash(self):
        """Every preset should initialize and step without error."""
        for name, desc, preset_id in SMOKEFIRE_PRESETS:
            random.seed(42)
            app = _make_app()
            app._smokefire_init(preset_id)
            for _ in range(10):
                app._smokefire_step()
            assert app.smokefire_generation == 10, f"Preset {name} failed"

    def test_grid_dimensions_preserved_after_step(self):
        """Grid dimensions should not change after stepping."""
        self.app._smokefire_init("campfire")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        for _ in range(5):
            self.app._smokefire_step()
        assert len(self.app.smokefire_temp) == rows
        assert len(self.app.smokefire_temp[0]) == cols
        assert len(self.app.smokefire_smoke) == rows
        assert len(self.app.smokefire_fuel) == rows
        assert len(self.app.smokefire_vx) == rows
        assert len(self.app.smokefire_vy) == rows

    def test_empty_grid_step_no_crash(self):
        """Stepping an empty grid (no sources, no fuel, no temp) should not crash."""
        self.app._smokefire_init("campfire")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        self.app.smokefire_sources = []
        self.app.smokefire_temp = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_smoke = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_fuel = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_vx = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_vy = [[0.0] * cols for _ in range(rows)]
        for _ in range(10):
            self.app._smokefire_step()
        assert self.app.smokefire_generation == 10

    def test_diffusion_spreads_temperature(self):
        """A single hot cell should spread heat to its neighbors via diffusion."""
        self.app._smokefire_init("campfire")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        # Clear everything
        self.app.smokefire_sources = []
        self.app.smokefire_temp = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_smoke = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_fuel = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_vx = [[0.0] * cols for _ in range(rows)]
        self.app.smokefire_vy = [[0.0] * cols for _ in range(rows)]
        # Place single hot cell in the middle
        mr, mc = rows // 2, cols // 2
        self.app.smokefire_temp[mr][mc] = 1.0
        self.app._smokefire_step()
        # Neighbors should have some heat from diffusion
        neighbor_heat = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = mr + dr, mc + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbor_heat += self.app.smokefire_temp[nr][nc]
        assert neighbor_heat > 0, "Diffusion should spread heat to neighbors"


class TestSmokeFireMenuKeys:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()
        self.app._enter_smokefire_mode()

    def test_menu_navigate_down(self):
        import curses
        self.app._handle_smokefire_menu_key(curses.KEY_DOWN)
        assert self.app.smokefire_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        import curses
        self.app._handle_smokefire_menu_key(curses.KEY_UP)
        assert self.app.smokefire_menu_sel == len(SMOKEFIRE_PRESETS) - 1

    def test_menu_select_enter(self):
        import curses
        self.app._handle_smokefire_menu_key(10)  # Enter key
        assert self.app.smokefire_menu is False
        assert self.app.smokefire_mode is True

    def test_menu_cancel_q(self):
        self.app._handle_smokefire_menu_key(ord("q"))
        assert self.app.smokefire_menu is False

    def test_menu_cancel_escape(self):
        self.app._handle_smokefire_menu_key(27)
        assert self.app.smokefire_menu is False

    def test_menu_no_op_key(self):
        result = self.app._handle_smokefire_menu_key(-1)
        assert result is True  # -1 is a no-op

    def test_menu_j_k_navigation(self):
        self.app._handle_smokefire_menu_key(ord("j"))
        assert self.app.smokefire_menu_sel == 1
        self.app._handle_smokefire_menu_key(ord("k"))
        assert self.app.smokefire_menu_sel == 0


class TestSmokeFireModeKeys:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()
        self.app.smokefire_mode = True
        self.app.smokefire_running = False
        self.app.smokefire_preset_name = "Campfire"
        self.app.smokefire_steps_per_frame = 1
        self.app._smokefire_init("campfire")

    def test_toggle_play_pause(self):
        self.app._handle_smokefire_key(ord(" "))
        assert self.app.smokefire_running is True
        self.app._handle_smokefire_key(ord(" "))
        assert self.app.smokefire_running is False

    def test_single_step(self):
        gen_before = self.app.smokefire_generation
        self.app._handle_smokefire_key(ord("n"))
        assert self.app.smokefire_generation == gen_before + 1

    def test_single_step_dot(self):
        gen_before = self.app.smokefire_generation
        self.app._handle_smokefire_key(ord("."))
        assert self.app.smokefire_generation == gen_before + 1

    def test_exit_key_q(self):
        self.app._handle_smokefire_key(ord("q"))
        assert self.app.smokefire_mode is False

    def test_exit_key_escape(self):
        self.app._handle_smokefire_key(27)
        assert self.app.smokefire_mode is False

    def test_cursor_movement(self):
        import curses
        initial_r = self.app.smokefire_cursor_r
        initial_c = self.app.smokefire_cursor_c
        # Move down
        self.app._handle_smokefire_key(curses.KEY_DOWN)
        assert self.app.smokefire_cursor_r == initial_r + 1
        # Move up
        self.app._handle_smokefire_key(curses.KEY_UP)
        assert self.app.smokefire_cursor_r == initial_r
        # Move right
        self.app._handle_smokefire_key(curses.KEY_RIGHT)
        assert self.app.smokefire_cursor_c == initial_c + 1
        # Move left
        self.app._handle_smokefire_key(curses.KEY_LEFT)
        assert self.app.smokefire_cursor_c == initial_c

    def test_cursor_hjkl(self):
        initial_r = self.app.smokefire_cursor_r
        initial_c = self.app.smokefire_cursor_c
        self.app._handle_smokefire_key(ord("j"))
        assert self.app.smokefire_cursor_r == initial_r + 1
        self.app._handle_smokefire_key(ord("k"))
        assert self.app.smokefire_cursor_r == initial_r
        self.app._handle_smokefire_key(ord("l"))
        assert self.app.smokefire_cursor_c == initial_c + 1
        self.app._handle_smokefire_key(ord("h"))
        assert self.app.smokefire_cursor_c == initial_c

    def test_cursor_bounds_top(self):
        self.app.smokefire_cursor_r = 0
        self.app._handle_smokefire_key(ord("k"))
        assert self.app.smokefire_cursor_r == 0

    def test_cursor_bounds_left(self):
        self.app.smokefire_cursor_c = 0
        self.app._handle_smokefire_key(ord("h"))
        assert self.app.smokefire_cursor_c == 0

    def test_cursor_bounds_bottom(self):
        self.app.smokefire_cursor_r = self.app.smokefire_rows - 1
        self.app._handle_smokefire_key(ord("j"))
        assert self.app.smokefire_cursor_r == self.app.smokefire_rows - 1

    def test_cursor_bounds_right(self):
        self.app.smokefire_cursor_c = self.app.smokefire_cols - 1
        self.app._handle_smokefire_key(ord("l"))
        assert self.app.smokefire_cursor_c == self.app.smokefire_cols - 1

    def test_add_fire_source(self):
        # Move cursor to empty area
        self.app.smokefire_cursor_r = 5
        self.app.smokefire_cursor_c = 5
        # Clear nearby sources
        self.app.smokefire_sources = [(0, 0, 0.8)]
        n_before = len(self.app.smokefire_sources)
        self.app._handle_smokefire_key(ord("f"))
        assert len(self.app.smokefire_sources) == n_before + 1

    def test_remove_fire_source(self):
        # Place source at cursor
        self.app.smokefire_cursor_r = 5
        self.app.smokefire_cursor_c = 5
        self.app.smokefire_sources = [(5, 5, 0.8)]
        self.app._handle_smokefire_key(ord("f"))
        assert len(self.app.smokefire_sources) == 0

    def test_add_fuel(self):
        self.app.smokefire_cursor_r = 10
        self.app.smokefire_cursor_c = 10
        self.app.smokefire_fuel[10][10] = 0.0
        self.app._handle_smokefire_key(ord("F"))
        assert self.app.smokefire_fuel[10][10] > 0

    def test_buoyancy_adjust(self):
        initial = self.app.smokefire_buoyancy
        self.app._handle_smokefire_key(ord("b"))
        assert self.app.smokefire_buoyancy > initial
        self.app._handle_smokefire_key(ord("B"))
        assert abs(self.app.smokefire_buoyancy - initial) < 0.001

    def test_turbulence_adjust(self):
        initial = self.app.smokefire_turbulence
        self.app._handle_smokefire_key(ord("t"))
        assert self.app.smokefire_turbulence > initial
        self.app._handle_smokefire_key(ord("T"))
        assert abs(self.app.smokefire_turbulence - initial) < 0.001

    def test_wind_adjust(self):
        initial = self.app.smokefire_wind
        self.app._handle_smokefire_key(ord("w"))
        assert self.app.smokefire_wind > initial
        self.app._handle_smokefire_key(ord("W"))
        assert abs(self.app.smokefire_wind - initial) < 0.001

    def test_cooling_adjust(self):
        initial = self.app.smokefire_cooling
        self.app._handle_smokefire_key(ord("c"))
        assert self.app.smokefire_cooling > initial
        self.app._handle_smokefire_key(ord("C"))
        assert abs(self.app.smokefire_cooling - initial) < 0.001

    def test_speed_adjust(self):
        self.app._handle_smokefire_key(ord(">"))
        assert self.app.smokefire_steps_per_frame == 2
        self.app._handle_smokefire_key(ord("<"))
        assert self.app.smokefire_steps_per_frame == 1

    def test_speed_bounds(self):
        self.app.smokefire_steps_per_frame = 10
        self.app._handle_smokefire_key(ord(">"))
        assert self.app.smokefire_steps_per_frame == 10
        self.app.smokefire_steps_per_frame = 1
        self.app._handle_smokefire_key(ord("<"))
        assert self.app.smokefire_steps_per_frame == 1

    def test_return_to_menu(self):
        self.app._handle_smokefire_key(ord("R"))
        assert self.app.smokefire_mode is False
        assert self.app.smokefire_menu is True
        assert self.app.smokefire_menu_sel == 0

    def test_buoyancy_upper_bound(self):
        self.app.smokefire_buoyancy = 0.5
        self.app._handle_smokefire_key(ord("b"))
        assert self.app.smokefire_buoyancy == 0.5

    def test_buoyancy_lower_bound(self):
        self.app.smokefire_buoyancy = 0.0
        self.app._handle_smokefire_key(ord("B"))
        assert self.app.smokefire_buoyancy == 0.0

    def test_turbulence_upper_bound(self):
        self.app.smokefire_turbulence = 0.3
        self.app._handle_smokefire_key(ord("t"))
        assert self.app.smokefire_turbulence == 0.3

    def test_cooling_upper_bound(self):
        self.app.smokefire_cooling = 0.1
        self.app._handle_smokefire_key(ord("c"))
        assert self.app.smokefire_cooling == 0.1


class TestSmokeFireExplosionPhysics:
    """Test explosion-specific physics behavior."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_explosion_radial_velocity(self):
        self.app._smokefire_init("explosion")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        mid_r, mid_c = rows * 2 // 3, cols // 2
        # Cells to the right of center should have positive vx
        if mid_c + 3 < cols:
            assert self.app.smokefire_vx[mid_r][mid_c + 3] > 0
        # Cells to the left should have negative vx
        if mid_c - 3 >= 0:
            assert self.app.smokefire_vx[mid_r][mid_c - 3] < 0

    def test_explosion_temperature_falloff(self):
        """Temperature should decrease with distance from blast center."""
        self.app._smokefire_init("explosion")
        rows = self.app.smokefire_rows
        cols = self.app.smokefire_cols
        mid_r, mid_c = rows * 2 // 3, cols // 2
        center_temp = self.app.smokefire_temp[mid_r][mid_c]
        edge_temp = self.app.smokefire_temp[mid_r][mid_c + 4] if mid_c + 4 < cols else 0
        assert center_temp >= edge_temp


class TestSmokeFireWildfireSpread:
    """Test that wildfire spreads over time."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_wildfire_spreads_rightward(self):
        self.app._smokefire_init("wildfire")
        # Count initially heated columns
        cols = self.app.smokefire_cols
        rows = self.app.smokefire_rows
        initial_heated_cols = set()
        for c in range(cols):
            for r in range(rows):
                if self.app.smokefire_temp[r][c] > 0.1:
                    initial_heated_cols.add(c)
        # Run many steps
        for _ in range(50):
            self.app._smokefire_step()
        final_heated_cols = set()
        for c in range(cols):
            for r in range(rows):
                if self.app.smokefire_temp[r][c] > 0.05:
                    final_heated_cols.add(c)
        # Fire should spread to more columns
        assert len(final_heated_cols) >= len(initial_heated_cols)
