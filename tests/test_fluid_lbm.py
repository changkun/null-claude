"""Tests for fluid_lbm mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.fluid_lbm import (
    register,
    FLUID_PRESETS, FLUID_EX, FLUID_EY, FLUID_W, FLUID_OPP,
    FLUID_SPEED_CHARS, FLUID_VORT_POS, FLUID_VORT_NEG,
)


def _make_fluid_app():
    """Create a mock app with fluid mode registered and initialized."""
    app = make_mock_app()
    cls = type(app)
    register(cls)
    # Instance attributes that _fluid_init expects to exist
    app.fluid_mode = False
    app.fluid_menu = False
    app.fluid_menu_sel = 0
    app.fluid_running = False
    app.fluid_f = []
    app.fluid_obstacle = []
    app.fluid_steps_per_frame = 3
    return app


class TestFluidLBMConstants:
    """Validate D2Q9 lattice constants for physical correctness."""

    def test_weights_sum_to_one(self):
        total = sum(FLUID_W)
        assert abs(total - 1.0) < 1e-12, f"Weights sum to {total}, expected 1.0"

    def test_nine_directions(self):
        assert len(FLUID_EX) == 9
        assert len(FLUID_EY) == 9
        assert len(FLUID_W) == 9
        assert len(FLUID_OPP) == 9

    def test_opposite_directions_symmetric(self):
        """opp[opp[i]] == i for all i."""
        for i in range(9):
            assert FLUID_OPP[FLUID_OPP[i]] == i, f"opp[opp[{i}]] != {i}"

    def test_opposite_velocity_negation(self):
        """Opposite direction has negated velocity vector."""
        for i in range(9):
            j = FLUID_OPP[i]
            assert FLUID_EX[j] == -FLUID_EX[i], f"EX: opp({i})={j} mismatch"
            assert FLUID_EY[j] == -FLUID_EY[i], f"EY: opp({i})={j} mismatch"

    def test_rest_direction_is_self_opposite(self):
        assert FLUID_OPP[0] == 0
        assert FLUID_EX[0] == 0
        assert FLUID_EY[0] == 0

    def test_lattice_isotropy_second_moment(self):
        """Sum_i w_i * e_ix * e_iy == 0  (off-diagonal of lattice tensor)."""
        s = sum(FLUID_W[i] * FLUID_EX[i] * FLUID_EY[i] for i in range(9))
        assert abs(s) < 1e-12, f"Off-diagonal moment = {s}, expected 0"

    def test_lattice_isotropy_diagonal(self):
        """Sum_i w_i * e_ix^2 == 1/3  (D2Q9 cs^2 = 1/3)."""
        sxx = sum(FLUID_W[i] * FLUID_EX[i] ** 2 for i in range(9))
        syy = sum(FLUID_W[i] * FLUID_EY[i] ** 2 for i in range(9))
        assert abs(sxx - 1.0 / 3.0) < 1e-12, f"sxx = {sxx}"
        assert abs(syy - 1.0 / 3.0) < 1e-12, f"syy = {syy}"

    def test_first_moment_zero(self):
        """Sum_i w_i * e_ix == 0, Sum_i w_i * e_iy == 0."""
        sx = sum(FLUID_W[i] * FLUID_EX[i] for i in range(9))
        sy = sum(FLUID_W[i] * FLUID_EY[i] for i in range(9))
        assert abs(sx) < 1e-12
        assert abs(sy) < 1e-12

    def test_presets_have_valid_omega(self):
        """omega must be in (0, 2) for stability."""
        for name, _desc, omega, _inflow, _obs in FLUID_PRESETS:
            assert 0 < omega < 2.0, f"Preset '{name}': omega={omega} out of range"

    def test_presets_have_positive_inflow(self):
        for name, _desc, _omega, inflow, _obs in FLUID_PRESETS:
            assert inflow > 0.0, f"Preset '{name}': inflow={inflow} <= 0"


class TestEquilibrium:
    """Test the equilibrium distribution function computation."""

    def test_equilibrium_at_rest(self):
        """At zero velocity, feq_i = w_i * rho."""
        rho = 1.0
        ux, uy = 0.0, 0.0
        usq = 0.0
        for i in range(9):
            eu = FLUID_EX[i] * ux + FLUID_EY[i] * uy
            feq = FLUID_W[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * usq)
            assert abs(feq - FLUID_W[i] * rho) < 1e-12

    def test_equilibrium_conserves_density(self):
        """Sum of equilibrium distributions equals rho."""
        rho = 2.5
        ux, uy = 0.05, -0.03
        usq = ux * ux + uy * uy
        total = 0.0
        for i in range(9):
            eu = FLUID_EX[i] * ux + FLUID_EY[i] * uy
            total += FLUID_W[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * usq)
        assert abs(total - rho) < 1e-10, f"Sum of feq = {total}, expected {rho}"

    def test_equilibrium_conserves_momentum(self):
        """Sum of e_i * feq_i equals rho * u."""
        rho = 1.3
        ux, uy = 0.08, 0.04
        usq = ux * ux + uy * uy
        mom_x, mom_y = 0.0, 0.0
        for i in range(9):
            eu = FLUID_EX[i] * ux + FLUID_EY[i] * uy
            feq = FLUID_W[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * usq)
            mom_x += FLUID_EX[i] * feq
            mom_y += FLUID_EY[i] * feq
        assert abs(mom_x - rho * ux) < 1e-10, f"mom_x={mom_x}, expected {rho * ux}"
        assert abs(mom_y - rho * uy) < 1e-10, f"mom_y={mom_y}, expected {rho * uy}"


class TestFluidLBMLifecycle:
    """Test mode enter/exit/init lifecycle."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()

    def test_enter(self):
        self.app._enter_fluid_mode()
        assert self.app.fluid_menu is True

    def test_init_all_presets(self):
        """Every preset initializes without error."""
        for idx in range(len(FLUID_PRESETS)):
            self.app._fluid_init(idx)
            assert self.app.fluid_mode is True
            assert self.app.fluid_menu is False
            assert len(self.app.fluid_f) == self.app.fluid_rows
            assert len(self.app.fluid_f[0]) == self.app.fluid_cols
            assert len(self.app.fluid_f[0][0]) == 9

    def test_exit_cleanup(self):
        self.app._fluid_init(0)
        self.app._exit_fluid_mode()
        assert self.app.fluid_mode is False
        assert self.app.fluid_f == []
        assert self.app.fluid_obstacle == []


class TestFluidLBMStreaming:
    """Test the streaming step mechanics."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()
        self.app._fluid_init(0)

    def test_step_increments_generation(self):
        self.app._fluid_step()
        assert self.app.fluid_generation == 1
        self.app._fluid_step()
        assert self.app.fluid_generation == 2

    def test_multiple_steps_no_crash(self):
        for _ in range(10):
            self.app._fluid_step()
        assert self.app.fluid_generation == 10

    def test_streaming_periodic_boundary(self):
        """After streaming, distributions should have been pulled from neighbors."""
        rows = self.app.fluid_rows
        cols = self.app.fluid_cols
        f_before = [
            [list(self.app.fluid_f[r][c]) for c in range(cols)]
            for r in range(rows)
        ]
        self.app._fluid_step()
        # The new distributions should differ from original (collision modifies them)
        any_changed = False
        for r in range(rows):
            for c in range(cols):
                if not self.app.fluid_obstacle[r][c]:
                    if self.app.fluid_f[r][c] != f_before[r][c]:
                        any_changed = True
                        break
            if any_changed:
                break
        assert any_changed, "Distributions unchanged after a step"


class TestFluidLBMMacros:
    """Test macroscopic field extraction."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()
        self.app._fluid_init(0)  # Wind Tunnel

    def test_get_macros_shape(self):
        rho, ux, uy = self.app._fluid_get_macros()
        assert len(rho) == self.app.fluid_rows
        assert len(ux) == self.app.fluid_rows
        assert len(uy) == self.app.fluid_rows
        assert len(rho[0]) == self.app.fluid_cols
        assert len(ux[0]) == self.app.fluid_cols
        assert len(uy[0]) == self.app.fluid_cols

    def test_initial_density_near_one(self):
        """At initialization, density should be ~1.0 in non-obstacle cells."""
        rho, _, _ = self.app._fluid_get_macros()
        for r in range(self.app.fluid_rows):
            for c in range(self.app.fluid_cols):
                if not self.app.fluid_obstacle[r][c]:
                    assert abs(rho[r][c] - 1.0) < 0.01, \
                        f"rho[{r}][{c}]={rho[r][c]}, expected ~1.0"

    def test_initial_velocity_matches_inflow(self):
        """At initialization, ux should be ~inflow speed in non-obstacle cells."""
        _, ux, uy = self.app._fluid_get_macros()
        inflow = self.app.fluid_inflow_speed
        for r in range(self.app.fluid_rows):
            for c in range(self.app.fluid_cols):
                if not self.app.fluid_obstacle[r][c]:
                    assert abs(ux[r][c] - inflow) < 0.01, \
                        f"ux[{r}][{c}]={ux[r][c]}, expected ~{inflow}"
                    assert abs(uy[r][c]) < 0.01, \
                        f"uy[{r}][{c}]={uy[r][c]}, expected ~0"

    def test_obstacle_cells_default_values(self):
        """Obstacle cells should have default rho=1, u=(0,0)."""
        rho, ux, uy = self.app._fluid_get_macros()
        for r in range(self.app.fluid_rows):
            for c in range(self.app.fluid_cols):
                if self.app.fluid_obstacle[r][c]:
                    assert rho[r][c] == 1.0
                    assert ux[r][c] == 0.0
                    assert uy[r][c] == 0.0


class TestFluidLBMCollision:
    """Test BGK collision properties."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()
        self.app._fluid_init(0)

    def test_mass_conservation_single_step(self):
        """Total mass should be conserved across a step (closed or inflow/outflow balanced)."""
        # For a non-cavity preset, total mass may shift due to boundary conditions.
        # Use cavity preset which is enclosed.
        self.app._fluid_init(2)  # Lid-Driven Cavity

        def total_mass():
            m = 0.0
            for r in range(self.app.fluid_rows):
                for c in range(self.app.fluid_cols):
                    if not self.app.fluid_obstacle[r][c]:
                        m += sum(self.app.fluid_f[r][c])
            return m

        m_before = total_mass()
        self.app._fluid_step()
        m_after = total_mass()
        # Cavity has lid BC that resets distributions, so allow small deviation
        rel_err = abs(m_after - m_before) / max(abs(m_before), 1e-10)
        assert rel_err < 0.05, f"Mass changed by {rel_err*100:.2f}%"

    def test_equilibrium_is_fixed_point(self):
        """If f == feq, collision should not change f (omega * (feq - f) = 0)."""
        # Initialize a small grid manually with exact equilibrium
        app = _make_fluid_app()
        cls = type(app)
        app.fluid_mode = True
        app.fluid_preset_name = "Wind Tunnel"
        app.fluid_omega = 1.0
        app.fluid_inflow_speed = 0.0  # zero inflow so BCs don't perturb
        app.fluid_generation = 0
        app.fluid_viz_mode = 0
        rows, cols = 5, 5
        app.fluid_rows = rows
        app.fluid_cols = cols
        app.fluid_obstacle = [[False] * cols for _ in range(rows)]

        # Set f = feq for rho=1, u=(0,0)
        app.fluid_f = []
        for r in range(rows):
            row = []
            for c in range(cols):
                row.append([FLUID_W[i] for i in range(9)])
            app.fluid_f.append(row)

        f_before = [[list(app.fluid_f[r][c]) for c in range(cols)] for r in range(rows)]
        app._fluid_step()
        # After one step with zero velocity everywhere and periodic boundaries,
        # streaming of a uniform field is identity, and collision of equilibrium
        # is identity, so f should be unchanged.
        for r in range(rows):
            for c in range(cols):
                for i in range(9):
                    assert abs(app.fluid_f[r][c][i] - f_before[r][c][i]) < 1e-10, \
                        f"f[{r}][{c}][{i}] changed from {f_before[r][c][i]} to {app.fluid_f[r][c][i]}"


class TestFluidLBMBounceBack:
    """Test obstacle bounce-back boundary condition."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()

    def test_obstacle_cells_stay_zero_velocity(self):
        """Obstacle cells should never develop non-zero macroscopic velocity."""
        self.app._fluid_init(0)
        for _ in range(5):
            self.app._fluid_step()
        _, ux, uy = self.app._fluid_get_macros()
        for r in range(self.app.fluid_rows):
            for c in range(self.app.fluid_cols):
                if self.app.fluid_obstacle[r][c]:
                    assert ux[r][c] == 0.0
                    assert uy[r][c] == 0.0

    def test_obstacle_exists_in_wind_tunnel(self):
        """Wind Tunnel preset should have at least one obstacle cell."""
        self.app._fluid_init(0)
        has_obs = any(
            self.app.fluid_obstacle[r][c]
            for r in range(self.app.fluid_rows)
            for c in range(self.app.fluid_cols)
        )
        assert has_obs, "Wind Tunnel should have obstacle cells"


class TestFluidLBMBoundaryConditions:
    """Test inflow/outflow and lid-driven cavity boundary conditions."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()

    def test_inflow_maintained(self):
        """After steps, left boundary should still have ~inflow velocity."""
        self.app._fluid_init(0)  # Wind Tunnel
        for _ in range(5):
            self.app._fluid_step()
        _, ux, _ = self.app._fluid_get_macros()
        inflow = self.app.fluid_inflow_speed
        # Check a few rows at column 0
        checked = 0
        for r in range(self.app.fluid_rows):
            if not self.app.fluid_obstacle[r][0]:
                assert abs(ux[r][0] - inflow) < 0.05, \
                    f"Inflow ux[{r}][0]={ux[r][0]}, expected ~{inflow}"
                checked += 1
        assert checked > 0, "No non-obstacle cells at left boundary"

    def test_cavity_lid_velocity(self):
        """Lid-Driven Cavity: top row should have rightward velocity."""
        self.app._fluid_init(2)  # Lid-Driven Cavity
        for _ in range(3):
            self.app._fluid_step()
        _, ux, _ = self.app._fluid_get_macros()
        inflow = self.app.fluid_inflow_speed
        checked = 0
        cols = self.app.fluid_cols
        for c in range(1, cols - 1):
            if not self.app.fluid_obstacle[0][c]:
                assert abs(ux[0][c] - inflow) < 0.05, \
                    f"Lid ux[0][{c}]={ux[0][c]}, expected ~{inflow}"
                checked += 1
        assert checked > 0

    def test_cavity_walls_are_obstacles(self):
        """Lid-Driven Cavity should have left, right, and bottom walls."""
        self.app._fluid_init(2)
        rows = self.app.fluid_rows
        cols = self.app.fluid_cols
        # Left wall
        for r in range(rows):
            assert self.app.fluid_obstacle[r][0] is True
        # Right wall
        for r in range(rows):
            assert self.app.fluid_obstacle[r][cols - 1] is True
        # Bottom wall
        for c in range(cols):
            assert self.app.fluid_obstacle[rows - 1][c] is True


class TestFluidLBMStability:
    """Test numerical stability over multiple steps."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()

    def test_no_nan_after_steps(self):
        """Distributions should not become NaN after several steps."""
        self.app._fluid_init(0)
        for _ in range(20):
            self.app._fluid_step()
        for r in range(self.app.fluid_rows):
            for c in range(self.app.fluid_cols):
                for i in range(9):
                    val = self.app.fluid_f[r][c][i]
                    assert not math.isnan(val), f"NaN at [{r}][{c}][{i}]"
                    assert not math.isinf(val), f"Inf at [{r}][{c}][{i}]"

    def test_no_negative_density(self):
        """Density should remain positive after multiple steps."""
        self.app._fluid_init(0)
        for _ in range(20):
            self.app._fluid_step()
        rho, _, _ = self.app._fluid_get_macros()
        for r in range(self.app.fluid_rows):
            for c in range(self.app.fluid_cols):
                if not self.app.fluid_obstacle[r][c]:
                    assert rho[r][c] > 0, f"Negative density at [{r}][{c}]: {rho[r][c]}"

    def test_velocity_bounded(self):
        """Velocity magnitude should stay reasonable in lattice units.

        In LBM, the incompressible limit requires Ma << 1 (u << cs = 1/sqrt(3)),
        but transient excursions near obstacles are common. We check that speed
        stays below a generous upper bound to catch true blow-ups.
        """
        self.app._fluid_init(0)
        for _ in range(20):
            self.app._fluid_step()
        _, ux, uy = self.app._fluid_get_macros()
        for r in range(self.app.fluid_rows):
            for c in range(self.app.fluid_cols):
                if not self.app.fluid_obstacle[r][c]:
                    speed = math.sqrt(ux[r][c] ** 2 + uy[r][c] ** 2)
                    assert speed < 2.0, f"Speed={speed} at [{r}][{c}], blow-up detected"


class TestFluidLBMKeyHandling:
    """Test keyboard input handling."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_fluid_app()

    def test_menu_navigation(self):
        self.app._enter_fluid_mode()
        self.app._handle_fluid_menu_key(ord("j"))
        assert self.app.fluid_menu_sel == 1
        self.app._handle_fluid_menu_key(ord("k"))
        assert self.app.fluid_menu_sel == 0

    def test_menu_select(self):
        self.app._enter_fluid_mode()
        self.app._handle_fluid_menu_key(ord("\n"))
        assert self.app.fluid_mode is True
        assert self.app.fluid_menu is False

    def test_menu_cancel(self):
        self.app._enter_fluid_mode()
        self.app._handle_fluid_menu_key(ord("q"))
        assert self.app.fluid_menu is False

    def test_space_toggles_running(self):
        self.app._fluid_init(0)
        assert self.app.fluid_running is False
        self.app._handle_fluid_key(ord(" "))
        assert self.app.fluid_running is True
        self.app._handle_fluid_key(ord(" "))
        assert self.app.fluid_running is False

    def test_viz_mode_cycles(self):
        self.app._fluid_init(0)
        assert self.app.fluid_viz_mode == 0
        self.app._handle_fluid_key(ord("v"))
        assert self.app.fluid_viz_mode == 1
        self.app._handle_fluid_key(ord("v"))
        assert self.app.fluid_viz_mode == 2
        self.app._handle_fluid_key(ord("v"))
        assert self.app.fluid_viz_mode == 0

    def test_omega_adjustment(self):
        self.app._fluid_init(0)
        omega_before = self.app.fluid_omega
        self.app._handle_fluid_key(ord("w"))
        assert self.app.fluid_omega == pytest.approx(omega_before + 0.05, abs=1e-6)

    def test_omega_clamped(self):
        self.app._fluid_init(0)
        self.app.fluid_omega = 1.97
        self.app._handle_fluid_key(ord("w"))
        assert self.app.fluid_omega <= 1.99

    def test_inflow_adjustment(self):
        self.app._fluid_init(0)
        inflow_before = self.app.fluid_inflow_speed
        self.app._handle_fluid_key(ord("u"))
        assert self.app.fluid_inflow_speed == pytest.approx(inflow_before + 0.01, abs=1e-6)

    def test_steps_per_frame(self):
        self.app._fluid_init(0)
        spf_before = self.app.fluid_steps_per_frame
        self.app._handle_fluid_key(ord("+"))
        assert self.app.fluid_steps_per_frame == spf_before + 1
        self.app._handle_fluid_key(ord("-"))
        assert self.app.fluid_steps_per_frame == spf_before

    def test_quit_exits(self):
        self.app._fluid_init(0)
        self.app._handle_fluid_key(ord("q"))
        assert self.app.fluid_mode is False

    def test_reset_to_menu(self):
        self.app._fluid_init(0)
        self.app._handle_fluid_key(ord("R"))
        assert self.app.fluid_menu is True
        assert self.app.fluid_mode is False
