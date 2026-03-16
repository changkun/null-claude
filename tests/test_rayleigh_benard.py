"""Tests for rayleigh_benard mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.rayleigh_benard import register


RBC_PRESETS = [
    ("Classic", "Standard Rayleigh-Benard convection rolls", "classic"),
    ("Gentle", "Low Rayleigh number gentle convection", "gentle"),
    ("Turbulent", "High Rayleigh number turbulence", "turbulent"),
    ("Hexagons", "Hexagonal convection cells", "hexagons"),
    ("Mantle", "Earth mantle convection", "mantle"),
    ("Solar", "Solar convection", "solar"),
    ("Asymmetric", "Asymmetric heating", "asymmetric"),
    ("Random", "Random perturbation", "random"),
]


class TestRayleighBenard:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        cls.RBC_PRESETS = RBC_PRESETS
        self.app.rbc_menu_sel = 0
        register(cls)

    def test_enter(self):
        self.app._enter_rbc_mode()
        assert self.app.rbc_menu is True
        assert self.app.rbc_menu_sel == 0

    def test_step_no_crash(self):
        self.app.rbc_mode = True
        self.app.rbc_running = False
        self.app._rbc_init(0)
        for _ in range(10):
            self.app._rbc_step()
        assert self.app.rbc_generation == 10

    def test_exit_cleanup(self):
        self.app.rbc_mode = True
        self.app._rbc_init(0)
        self.app._exit_rbc_mode()
        assert self.app.rbc_mode is False
        assert self.app.rbc_menu is False
        assert self.app.rbc_running is False
        assert self.app.rbc_T == []

    # ── Init tests for all presets ──

    @pytest.mark.parametrize("idx", range(len(RBC_PRESETS)))
    def test_init_all_presets(self, idx):
        """Every preset should initialize without error."""
        random.seed(42)
        self.app._rbc_init(idx)
        assert self.app.rbc_mode is True
        assert self.app.rbc_menu is False
        assert self.app.rbc_generation == 0
        assert len(self.app.rbc_T) == self.app.rbc_rows
        assert len(self.app.rbc_T[0]) == self.app.rbc_cols
        assert len(self.app.rbc_vx) == self.app.rbc_rows
        assert len(self.app.rbc_vy) == self.app.rbc_rows

    # ── Temperature field validation ──

    def test_temperature_boundary_conditions_preserved(self):
        """Top row must remain cold, bottom row must remain hot after stepping."""
        self.app._rbc_init(0)
        for _ in range(20):
            self.app._rbc_step()
        T = self.app.rbc_T
        rows = self.app.rbc_rows
        # Top row = cold
        for c in range(self.app.rbc_cols):
            assert T[0][c] == self.app.rbc_T_cold, "Top boundary must stay cold"
        # Bottom row = hot
        for c in range(self.app.rbc_cols):
            assert T[rows - 1][c] == self.app.rbc_T_hot, "Bottom boundary must stay hot"

    def test_initial_temperature_gradient(self):
        """Before stepping, temperature should increase from top to bottom."""
        self.app._rbc_init(1)  # gentle preset
        T = self.app.rbc_T
        rows = self.app.rbc_rows
        # Check the overall gradient direction (average temperature should increase with row)
        avg_top = sum(T[1]) / len(T[1])
        avg_bottom = sum(T[rows - 2]) / len(T[rows - 2])
        assert avg_bottom > avg_top, "Bottom should be warmer than top initially"

    def test_temperature_field_dimensions(self):
        """Temperature field must match declared rows x cols."""
        self.app._rbc_init(0)
        assert len(self.app.rbc_T) == self.app.rbc_rows
        for row in self.app.rbc_T:
            assert len(row) == self.app.rbc_cols

    # ── Velocity field validation ──

    def test_velocity_boundary_conditions(self):
        """No-slip: velocity must be zero at top and bottom boundaries after step."""
        self.app._rbc_init(0)
        for _ in range(15):
            self.app._rbc_step()
        rows = self.app.rbc_rows
        cols = self.app.rbc_cols
        for c in range(cols):
            assert self.app.rbc_vx[0][c] == 0.0, "Top vx must be 0"
            assert self.app.rbc_vy[0][c] == 0.0, "Top vy must be 0"
            assert self.app.rbc_vx[rows - 1][c] == 0.0, "Bottom vx must be 0"
            assert self.app.rbc_vy[rows - 1][c] == 0.0, "Bottom vy must be 0"

    def test_velocity_clamped(self):
        """All velocities must be within [-5.0, 5.0] after stepping."""
        self.app._rbc_init(2)  # turbulent preset
        for _ in range(30):
            self.app._rbc_step()
        max_v = 5.0
        for r in range(self.app.rbc_rows):
            for c in range(self.app.rbc_cols):
                assert -max_v <= self.app.rbc_vx[r][c] <= max_v
                assert -max_v <= self.app.rbc_vy[r][c] <= max_v

    def test_velocity_initially_zero(self):
        """All velocity fields should start at zero."""
        self.app._rbc_init(0)
        for r in range(self.app.rbc_rows):
            for c in range(self.app.rbc_cols):
                assert self.app.rbc_vx[r][c] == 0.0
                assert self.app.rbc_vy[r][c] == 0.0

    # ── Buoyancy physics ──

    def test_buoyancy_develops_velocity(self):
        """After several steps, the temperature gradient should drive nonzero velocities."""
        self.app._rbc_init(0)
        for _ in range(30):
            self.app._rbc_step()
        # At least some interior cell should have non-zero velocity
        has_nonzero = False
        for r in range(1, self.app.rbc_rows - 1):
            for c in range(self.app.rbc_cols):
                if abs(self.app.rbc_vx[r][c]) > 1e-10 or abs(self.app.rbc_vy[r][c]) > 1e-10:
                    has_nonzero = True
                    break
            if has_nonzero:
                break
        assert has_nonzero, "Buoyancy should produce nonzero interior velocities"

    # ── Stability test ──

    def test_no_nan_or_inf_after_many_steps(self):
        """Temperature and velocity should not diverge to NaN/Inf."""
        self.app._rbc_init(2)  # turbulent
        for _ in range(50):
            self.app._rbc_step()
        for r in range(self.app.rbc_rows):
            for c in range(self.app.rbc_cols):
                assert math.isfinite(self.app.rbc_T[r][c]), f"T[{r}][{c}] not finite"
                assert math.isfinite(self.app.rbc_vx[r][c]), f"vx[{r}][{c}] not finite"
                assert math.isfinite(self.app.rbc_vy[r][c]), f"vy[{r}][{c}] not finite"

    # ── Preset-specific parameters ──

    def test_classic_parameters(self):
        self.app._rbc_init(0)
        assert self.app.rbc_Ra == 2000.0
        assert self.app.rbc_dt == 0.004
        assert self.app.rbc_steps_per_frame == 3

    def test_gentle_parameters(self):
        self.app._rbc_init(1)
        assert self.app.rbc_Ra == 500.0
        assert self.app.rbc_dt == 0.006

    def test_turbulent_parameters(self):
        self.app._rbc_init(2)
        assert self.app.rbc_Ra == 8000.0
        assert self.app.rbc_dt == 0.002

    def test_mantle_high_prandtl(self):
        self.app._rbc_init(4)  # mantle
        assert self.app.rbc_Pr == 10.0, "Mantle should have high Prandtl number"

    def test_solar_low_prandtl(self):
        self.app._rbc_init(5)  # solar
        assert self.app.rbc_Pr == 0.025, "Solar should have low Prandtl number"

    # ── Step advances generation ──

    def test_step_increments_generation(self):
        self.app._rbc_init(0)
        assert self.app.rbc_generation == 0
        self.app._rbc_step()
        assert self.app.rbc_generation == 1
        self.app._rbc_step()
        assert self.app.rbc_generation == 2

    # ── Periodic horizontal boundary ──

    def test_horizontal_periodicity(self):
        """Temperature advection uses periodic boundary in x (cols wrap)."""
        self.app._rbc_init(0)
        # Manually set a temperature spike at column 0, interior row
        r = self.app.rbc_rows // 2
        self.app.rbc_T[r][0] = 0.9
        self.app.rbc_vx[r][0] = -0.5  # flow to the left
        self.app._rbc_step()
        # After step, column cols-1 should be influenced (periodic wrap)
        # This is a weak check: just verify no crash and field is finite
        assert math.isfinite(self.app.rbc_T[r][self.app.rbc_cols - 1])

    # ── Key handling ──

    def test_handle_menu_key_up_down(self):
        self.app.rbc_menu = True
        self.app.rbc_menu_sel = 0
        import curses
        self.app._handle_rbc_menu_key(curses.KEY_DOWN)
        assert self.app.rbc_menu_sel == 1
        self.app._handle_rbc_menu_key(curses.KEY_UP)
        assert self.app.rbc_menu_sel == 0
        # Wrap around
        self.app._handle_rbc_menu_key(curses.KEY_UP)
        assert self.app.rbc_menu_sel == len(RBC_PRESETS) - 1

    def test_handle_rbc_key_space_toggle(self):
        self.app._rbc_init(0)
        self.app.rbc_running = False
        self.app._handle_rbc_key(ord(" "))
        assert self.app.rbc_running is True
        self.app._handle_rbc_key(ord(" "))
        assert self.app.rbc_running is False

    def test_handle_rbc_key_quit(self):
        self.app._rbc_init(0)
        self.app._handle_rbc_key(ord("q"))
        assert self.app.rbc_mode is False

    def test_handle_rbc_key_viz_cycle(self):
        self.app._rbc_init(0)
        assert self.app.rbc_viz_mode == 0
        self.app._handle_rbc_key(ord("v"))
        assert self.app.rbc_viz_mode == 1
        self.app._handle_rbc_key(ord("v"))
        assert self.app.rbc_viz_mode == 2
        self.app._handle_rbc_key(ord("v"))
        assert self.app.rbc_viz_mode == 0

    def test_handle_rbc_key_ra_adjust(self):
        self.app._rbc_init(0)
        ra_before = self.app.rbc_Ra
        self.app._handle_rbc_key(ord("+"))
        assert self.app.rbc_Ra > ra_before
        self.app._handle_rbc_key(ord("-"))
        assert abs(self.app.rbc_Ra - ra_before) < 1.0  # roughly back

    def test_handle_rbc_key_speed(self):
        self.app._rbc_init(0)
        spf = self.app.rbc_steps_per_frame
        self.app._handle_rbc_key(ord(">"))
        assert self.app.rbc_steps_per_frame == spf + 1
        self.app._handle_rbc_key(ord("<"))
        assert self.app.rbc_steps_per_frame == spf

    def test_handle_rbc_key_reset(self):
        self.app._rbc_init(0)
        for _ in range(5):
            self.app._rbc_step()
        self.app._handle_rbc_key(ord("r"))
        assert self.app.rbc_generation == 0

    def test_handle_rbc_key_menu_return(self):
        self.app._rbc_init(0)
        self.app._handle_rbc_key(ord("R"))
        assert self.app.rbc_menu is True
        assert self.app.rbc_mode is False

    def test_handle_rbc_key_single_step(self):
        self.app._rbc_init(0)
        gen_before = self.app.rbc_generation
        self.app._handle_rbc_key(ord("n"))
        assert self.app.rbc_generation == gen_before + 1
