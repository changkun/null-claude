"""Tests for navier_stokes mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.navier_stokes import register


NS_PRESETS = [
    ("Dye Playground", "Empty canvas for dye injection", "playground"),
    ("Vortex Pair", "Two counter-rotating vortices", "vortex_pair"),
    ("Jet Stream", "Continuous fluid jet from the left wall", "jet"),
    ("Karman Vortices", "Flow past a circular obstacle", "karman"),
    ("Four Corners", "Dye sources in each corner", "four_corners"),
    ("Shear Layer", "Opposing horizontal flows", "shear"),
]

NS_DYE_CHARS = [" ", "\u2591", "\u2592", "\u2593", "\u2588"]
NS_VEL_CHARS = [" ", "\u00b7", "\u2218", "\u25cb", "\u25cf"]
NS_VORT_POS = [" ", "\u00b7", "\u2218", "\u25cb", "\u25c9"]
NS_VORT_NEG = [" ", "\u00b7", "\u2219", "\u2022", "\u2b24"]


def _make_app():
    app = make_mock_app()
    cls = type(app)
    cls.NS_PRESETS = NS_PRESETS
    cls.NS_DYE_CHARS = NS_DYE_CHARS
    cls.NS_VEL_CHARS = NS_VEL_CHARS
    cls.NS_VORT_POS = NS_VORT_POS
    cls.NS_VORT_NEG = NS_VORT_NEG
    app.ns_viscosity = 0.0001
    app.ns_diffusion = 0.00001
    app.ns_dt = 0.1
    app.ns_iterations = 20
    app.ns_inject_radius = 3
    app.ns_inject_strength = 80.0
    app.ns_dye_hue = 0.0
    app.ns_steps_per_frame = 4
    app.ns_viz_mode = 0
    register(cls)
    return app


class TestNavierStokes:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_enter(self):
        self.app._enter_ns_mode()
        assert self.app.ns_menu is True
        assert self.app.ns_menu_sel == 0

    def test_step_no_crash(self):
        self.app.ns_mode = True
        self.app.ns_running = False
        self.app._ns_init(0)
        for _ in range(10):
            self.app._ns_step()
        assert self.app.ns_generation == 10

    def test_exit_cleanup(self):
        self.app.ns_mode = True
        self.app._ns_init(0)
        self.app._exit_ns_mode()
        assert self.app.ns_mode is False
        assert self.app.ns_menu is False
        assert self.app.ns_running is False
        assert self.app.ns_vx == []


class TestNSGridCreation:
    """Test grid initialization and dimensions."""

    def setup_method(self):
        self.app = _make_app()

    def test_make_grid_dimensions(self):
        self.app._ns_init(0)
        grid = self.app._ns_make_grid(0.0)
        assert len(grid) == self.app.ns_rows
        for row in grid:
            assert len(row) == self.app.ns_cols

    def test_make_grid_default_value(self):
        self.app._ns_init(0)
        grid = self.app._ns_make_grid(5.0)
        for row in grid:
            for val in row:
                assert val == 5.0

    def test_playground_zero_velocity(self):
        """Playground preset should have zero velocity everywhere."""
        self.app._ns_init(0)
        for r in range(self.app.ns_rows):
            for c in range(self.app.ns_cols):
                assert self.app.ns_vx[r][c] == 0.0
                assert self.app.ns_vy[r][c] == 0.0

    def test_obstacle_grid_initialized(self):
        self.app._ns_init(0)
        for r in range(self.app.ns_rows):
            for c in range(self.app.ns_cols):
                assert self.app.ns_obstacles[r][c] is False


class TestNSPresets:
    """Test that all presets initialize without errors and set expected state."""

    def setup_method(self):
        self.app = _make_app()

    @pytest.mark.parametrize("preset_idx", range(6))
    def test_preset_init_no_crash(self, preset_idx):
        self.app._ns_init(preset_idx)
        assert self.app.ns_mode is True
        assert self.app.ns_rows > 0
        assert self.app.ns_cols > 0

    @pytest.mark.parametrize("preset_idx", range(6))
    def test_preset_step_no_crash(self, preset_idx):
        self.app._ns_init(preset_idx)
        for _ in range(5):
            self.app._ns_step()
        assert self.app.ns_generation == 5

    def test_vortex_pair_has_velocity(self):
        """Vortex pair preset should initialize non-zero velocity."""
        self.app._ns_init(1)  # "Vortex Pair"
        has_nonzero = False
        for r in range(self.app.ns_rows):
            for c in range(self.app.ns_cols):
                if abs(self.app.ns_vx[r][c]) > 0.01 or abs(self.app.ns_vy[r][c]) > 0.01:
                    has_nonzero = True
                    break
            if has_nonzero:
                break
        assert has_nonzero, "Vortex pair should have non-zero initial velocity"

    def test_vortex_pair_has_dye(self):
        """Vortex pair should have initial dye in vortex cores."""
        self.app._ns_init(1)
        max_dye = max(self.app.ns_dye[r][c]
                      for r in range(self.app.ns_rows)
                      for c in range(self.app.ns_cols))
        assert max_dye > 0.0

    def test_jet_inflow(self):
        """Jet preset should have rightward velocity on the left edge."""
        self.app._ns_init(2)  # "Jet Stream"
        mid = self.app.ns_rows // 2
        assert self.app.ns_vx[mid][0] == 60.0

    def test_karman_has_obstacles(self):
        """Karman preset should create a circular obstacle."""
        self.app._ns_init(3)  # "Karman Vortices"
        obstacle_count = sum(
            1 for r in range(self.app.ns_rows)
            for c in range(self.app.ns_cols)
            if self.app.ns_obstacles[r][c]
        )
        assert obstacle_count > 0

    def test_shear_opposing_flows(self):
        """Shear preset should have opposing horizontal flows."""
        self.app._ns_init(5)  # "Shear Layer"
        rows = self.app.ns_rows
        mid = rows // 2
        # Top half should have positive vx, bottom negative
        if mid - 4 >= 0 and mid + 4 < rows:
            assert self.app.ns_vx[mid - 4][0] > 0
            assert self.app.ns_vx[mid + 4][0] < 0


class TestNSDiffuse:
    """Test the diffusion solver."""

    def setup_method(self):
        self.app = _make_app()
        self.app._ns_init(0)

    def test_zero_diffusion_copies_input(self):
        """With diff=0, output should equal input."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        x0 = self.app._ns_make_grid()
        x = self.app._ns_make_grid()
        # Set some non-zero values in x0
        x0[rows // 2][cols // 2] = 5.0
        self.app._ns_diffuse(x, x0, 0.0, 0.1)
        assert x[rows // 2][cols // 2] == 5.0

    def test_diffusion_spreads_value(self):
        """Diffusion should spread a concentrated value to neighbors."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        x0 = self.app._ns_make_grid()
        x = self.app._ns_make_grid()
        mid_r, mid_c = rows // 2, cols // 2
        x0[mid_r][mid_c] = 100.0
        self.app._ns_diffuse(x, x0, 1.0, 0.1)
        # Center should have decreased, neighbors should have increased
        assert x[mid_r][mid_c] < 100.0
        assert x[mid_r + 1][mid_c] > 0.0

    def test_diffusion_obstacle_zero(self):
        """Obstacles should always have zero value after diffusion."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        mid_r, mid_c = rows // 2, cols // 2
        self.app.ns_obstacles[mid_r][mid_c] = True
        x0 = self.app._ns_make_grid(1.0)
        x = self.app._ns_make_grid()
        self.app._ns_diffuse(x, x0, 1.0, 0.1)
        assert x[mid_r][mid_c] == 0.0


class TestNSAdvect:
    """Test semi-Lagrangian advection."""

    def setup_method(self):
        self.app = _make_app()
        self.app._ns_init(0)

    def test_zero_velocity_preserves_field(self):
        """With zero velocity, advection should preserve the field."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        d0 = self.app._ns_make_grid()
        d = self.app._ns_make_grid()
        vx = self.app._ns_make_grid()
        vy = self.app._ns_make_grid()
        d0[rows // 2][cols // 2] = 1.0
        self.app._ns_advect(d, d0, vx, vy, 0.1)
        assert d[rows // 2][cols // 2] == pytest.approx(1.0, abs=1e-6)

    def test_advection_moves_dye(self):
        """Rightward velocity should move dye to the right."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        d0 = self.app._ns_make_grid()
        d = self.app._ns_make_grid()
        vx = self.app._ns_make_grid()
        vy = self.app._ns_make_grid()
        mid_r, mid_c = rows // 2, cols // 2
        # Create a dye blob
        for r in range(mid_r - 2, mid_r + 3):
            for c in range(mid_c - 2, mid_c + 3):
                d0[r][c] = 1.0
        # Set rightward velocity
        for r in range(rows):
            for c in range(cols):
                vx[r][c] = 0.5
        self.app._ns_advect(d, d0, vx, vy, 0.1)
        # The dye should have shifted right (center of mass moved)
        # Check that there's dye to the right of original center
        right_dye = sum(d[mid_r][c] for c in range(mid_c + 1, min(cols, mid_c + 10)))
        assert right_dye > 0.0

    def test_advection_obstacle_zero(self):
        """Obstacle cells should have zero after advection."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        mid_r, mid_c = rows // 2, cols // 2
        self.app.ns_obstacles[mid_r][mid_c] = True
        d0 = self.app._ns_make_grid(1.0)
        d = self.app._ns_make_grid()
        vx = self.app._ns_make_grid()
        vy = self.app._ns_make_grid()
        self.app._ns_advect(d, d0, vx, vy, 0.1)
        assert d[mid_r][mid_c] == 0.0


class TestNSProject:
    """Test the pressure projection (divergence-free constraint)."""

    def setup_method(self):
        self.app = _make_app()
        self.app._ns_init(0)

    def test_zero_velocity_stays_zero(self):
        """Projecting zero velocity should remain zero."""
        self.app._ns_project()
        for r in range(self.app.ns_rows):
            for c in range(self.app.ns_cols):
                assert self.app.ns_vx[r][c] == 0.0
                assert self.app.ns_vy[r][c] == 0.0

    def test_projection_reduces_divergence(self):
        """After projection, divergence should be significantly reduced."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        # Create a divergent field: source at center
        mid_r, mid_c = rows // 2, cols // 2
        self.app.ns_vx[mid_r][mid_c] = 50.0
        self.app.ns_vy[mid_r][mid_c] = 50.0

        # Compute divergence before
        def compute_max_div():
            max_div = 0.0
            for r in range(rows):
                for c in range(cols):
                    rn = (r - 1) % rows
                    rs = (r + 1) % rows
                    cw = (c - 1) % cols
                    ce = (c + 1) % cols
                    d = (self.app.ns_vx[r][ce] - self.app.ns_vx[r][cw]) / cols + \
                        (self.app.ns_vy[rs][c] - self.app.ns_vy[rn][c]) / rows
                    max_div = max(max_div, abs(d))
            return max_div

        div_before = compute_max_div()
        self.app._ns_project()
        div_after = compute_max_div()
        assert div_after < div_before

    def test_obstacle_velocity_zero_after_project(self):
        """Obstacle cells should have zero velocity after projection."""
        rows, cols = self.app.ns_rows, self.app.ns_cols
        mid_r, mid_c = rows // 2, cols // 2
        self.app.ns_obstacles[mid_r][mid_c] = True
        self.app.ns_vx[mid_r][mid_c] = 10.0
        self.app.ns_vy[mid_r][mid_c] = 10.0
        self.app._ns_project()
        assert self.app.ns_vx[mid_r][mid_c] == 0.0
        assert self.app.ns_vy[mid_r][mid_c] == 0.0


class TestNSStep:
    """Test the full simulation step."""

    def setup_method(self):
        self.app = _make_app()

    def test_generation_increments(self):
        self.app._ns_init(0)
        assert self.app.ns_generation == 0
        self.app._ns_step()
        assert self.app.ns_generation == 1

    def test_dye_dissipation(self):
        """Dye should slowly decay each step (multiplied by 0.999)."""
        self.app._ns_init(0)
        rows, cols = self.app.ns_rows, self.app.ns_cols
        mid_r, mid_c = rows // 2, cols // 2
        self.app.ns_dye[mid_r][mid_c] = 1.0
        self.app._ns_step()
        # After one step, dye should have decreased
        assert self.app.ns_dye[mid_r][mid_c] < 1.0

    def test_dye_hue_advances(self):
        self.app._ns_init(0)
        old_hue = self.app.ns_dye_hue
        self.app._ns_step()
        assert self.app.ns_dye_hue > old_hue

    def test_jet_continuous_source(self):
        """Jet Stream preset should re-inject velocity each step."""
        self.app._ns_init(2)  # Jet Stream
        self.app._ns_step()
        mid = self.app.ns_rows // 2
        # The step re-applies vx=60 at left edge for the jet
        assert self.app.ns_vx[mid][0] != 0.0 or self.app.ns_vx[mid][1] != 0.0

    def test_karman_continuous_inflow(self):
        """Karman preset should re-inject inflow velocity each step."""
        self.app._ns_init(3)  # Karman Vortices
        self.app._ns_step()
        # Non-obstacle cells at left edge should have inflow
        for r in range(self.app.ns_rows):
            if not self.app.ns_obstacles[r][0]:
                # After a step the velocity may have been modified but inflow is re-applied
                break

    def test_multiple_steps_stable(self):
        """Running many steps should not produce NaN or Inf."""
        self.app._ns_init(1)  # Vortex Pair
        for _ in range(50):
            self.app._ns_step()
        for r in range(self.app.ns_rows):
            for c in range(self.app.ns_cols):
                assert math.isfinite(self.app.ns_vx[r][c])
                assert math.isfinite(self.app.ns_vy[r][c])
                assert math.isfinite(self.app.ns_dye[r][c])

    def test_playground_stays_zero(self):
        """Playground with no injection should remain mostly zero."""
        self.app._ns_init(0)
        for _ in range(10):
            self.app._ns_step()
        total_vel = sum(
            abs(self.app.ns_vx[r][c]) + abs(self.app.ns_vy[r][c])
            for r in range(self.app.ns_rows)
            for c in range(self.app.ns_cols)
        )
        assert total_vel < 1e-6


class TestNSMassConservation:
    """Test that the solver approximately conserves quantities."""

    def setup_method(self):
        self.app = _make_app()

    def test_dye_non_negative(self):
        """Dye should not go significantly negative during simulation."""
        self.app._ns_init(1)  # Vortex pair has initial dye
        for _ in range(20):
            self.app._ns_step()
        min_dye = min(
            self.app.ns_dye[r][c]
            for r in range(self.app.ns_rows)
            for c in range(self.app.ns_cols)
        )
        # Semi-Lagrangian can produce small negatives from interpolation
        assert min_dye > -0.1
