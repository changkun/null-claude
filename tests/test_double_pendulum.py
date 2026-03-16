"""Tests for double_pendulum mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.double_pendulum import register


DPEND_PRESETS = [
    ("Classic", "Standard double pendulum at 135 degrees", "classic"),
    ("Gentle", "Small-angle near-periodic motion", "gentle"),
    ("Heavy Lower", "Heavy lower bob — more inertia", "heavy_lower"),
    ("Heavy Upper", "Heavy upper bob", "heavy_upper"),
    ("Max Chaos", "Near-vertical start — maximum chaos", "max_chaos"),
    ("Near Identical", "Two pendulums differ by 0.001 deg", "near_identical"),
    ("Butterfly", "Ultra-small perturbation", "butterfly"),
    ("Long Arms", "Asymmetric arm lengths", "long_arms"),
]


def _make_app():
    app = make_mock_app()
    cls = type(app)
    cls.DPEND_PRESETS = DPEND_PRESETS
    app.dpend_steps_per_frame = 5
    register(cls)
    return app


class TestDoublePendulum:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_enter(self):
        self.app._enter_dpend_mode()
        assert self.app.dpend_menu is True
        assert self.app.dpend_menu_sel == 0

    def test_step_no_crash(self):
        self.app.dpend_mode = True
        self.app.dpend_running = False
        self.app._dpend_init(0)
        for _ in range(10):
            self.app._dpend_step()
        assert self.app.dpend_generation == 10

    def test_exit_cleanup(self):
        self.app.dpend_mode = True
        self.app._dpend_init(0)
        self.app._exit_dpend_mode()
        assert self.app.dpend_mode is False
        assert self.app.dpend_menu is False
        assert self.app.dpend_running is False
        assert self.app.dpend_trail1 == []


class TestDPendPresets:
    """Test all preset configurations."""

    def setup_method(self):
        self.app = _make_app()

    @pytest.mark.parametrize("preset_idx", range(8))
    def test_preset_init_no_crash(self, preset_idx):
        self.app._dpend_init(preset_idx)
        assert self.app.dpend_mode is True
        assert len(self.app.dpend_p1) == 4
        assert len(self.app.dpend_p2) == 4

    @pytest.mark.parametrize("preset_idx", range(8))
    def test_preset_step_no_crash(self, preset_idx):
        self.app._dpend_init(preset_idx)
        for _ in range(20):
            self.app._dpend_step()
        assert self.app.dpend_generation == 20

    def test_classic_initial_angles(self):
        self.app._dpend_init(0)  # Classic
        assert self.app.dpend_p1[0] == pytest.approx(math.pi * 0.75)
        assert self.app.dpend_p1[1] == pytest.approx(math.pi * 0.75)
        assert self.app.dpend_p1[2] == 0.0  # zero angular velocity
        assert self.app.dpend_p1[3] == 0.0

    def test_gentle_small_angles(self):
        self.app._dpend_init(1)  # Gentle
        assert self.app.dpend_p1[0] == pytest.approx(math.pi * 0.15)
        assert self.app.dpend_p1[1] == pytest.approx(math.pi * 0.15)

    def test_heavy_lower_mass(self):
        self.app._dpend_init(2)  # Heavy Lower
        assert self.app.dpend_m1 == 1.0
        assert self.app.dpend_m2 == 3.0

    def test_heavy_upper_mass(self):
        self.app._dpend_init(3)  # Heavy Upper
        assert self.app.dpend_m1 == 3.0
        assert self.app.dpend_m2 == 1.0

    def test_max_chaos_near_vertical(self):
        self.app._dpend_init(4)  # Max Chaos
        assert self.app.dpend_p1[0] == pytest.approx(math.pi * 0.99)
        assert self.app.dpend_p1[1] == pytest.approx(math.pi * 0.99)

    def test_long_arms_asymmetric(self):
        self.app._dpend_init(7)  # Long Arms
        assert self.app.dpend_l1 == 0.8
        assert self.app.dpend_l2 == 1.5


class TestDPendPerturbation:
    """Test that pendulum 2 is initialized with the correct perturbation."""

    def setup_method(self):
        self.app = _make_app()

    def test_p2_perturbed_from_p1(self):
        self.app._dpend_init(0)  # Classic
        # p2 theta1 should differ from p1 theta1 by perturb
        diff = abs(self.app.dpend_p2[0] - self.app.dpend_p1[0])
        assert diff == pytest.approx(self.app.dpend_perturb)

    def test_p2_same_theta2(self):
        """p2 should share the same theta2 as p1."""
        self.app._dpend_init(0)
        assert self.app.dpend_p2[1] == self.app.dpend_p1[1]

    def test_p2_same_angular_velocities(self):
        """p2 should share the same initial angular velocities as p1."""
        self.app._dpend_init(0)
        assert self.app.dpend_p2[2] == self.app.dpend_p1[2]
        assert self.app.dpend_p2[3] == self.app.dpend_p1[3]

    def test_near_identical_tiny_perturb(self):
        self.app._dpend_init(5)  # Near Identical
        diff = abs(self.app.dpend_p2[0] - self.app.dpend_p1[0])
        assert diff == pytest.approx(math.radians(0.001))

    def test_butterfly_ultra_small_perturb(self):
        self.app._dpend_init(6)  # Butterfly
        diff = abs(self.app.dpend_p2[0] - self.app.dpend_p1[0])
        assert diff == pytest.approx(1e-6)


class TestDPendDerivatives:
    """Test the equations of motion derivatives."""

    def setup_method(self):
        self.app = _make_app()
        self.app._dpend_init(0)

    def test_derivs_returns_four_values(self):
        derivs = self.app._dpend_derivs(self.app.dpend_p1)
        assert len(derivs) == 4

    def test_derivs_at_rest_hanging_down(self):
        """Pendulum at rest hanging straight down (theta=0) should have zero derivatives."""
        state = [0.0, 0.0, 0.0, 0.0]
        derivs = self.app._dpend_derivs(state)
        # dtheta1/dt = w1 = 0, dtheta2/dt = w2 = 0
        assert derivs[0] == 0.0
        assert derivs[1] == 0.0
        # dw1/dt and dw2/dt should be 0 (no torque when hanging straight down)
        assert abs(derivs[2]) < 1e-10
        assert abs(derivs[3]) < 1e-10

    def test_derivs_at_small_angle(self):
        """Small angle displacement should produce restoring torque."""
        state = [0.1, 0.0, 0.0, 0.0]  # theta1 displaced slightly
        derivs = self.app._dpend_derivs(state)
        # dw1/dt should be negative (restoring toward 0)
        assert derivs[2] < 0

    def test_derivs_theta_rates_equal_omega(self):
        """First two derivatives should be the angular velocities."""
        state = [1.0, 0.5, 2.0, -1.0]  # arbitrary state with nonzero omega
        derivs = self.app._dpend_derivs(state)
        assert derivs[0] == 2.0   # dtheta1/dt = w1
        assert derivs[1] == -1.0  # dtheta2/dt = w2

    def test_derivs_finite(self):
        """Derivatives should always be finite, even for extreme angles."""
        states = [
            [math.pi, math.pi, 0.0, 0.0],
            [0.0, math.pi, 10.0, -10.0],
            [math.pi, 0.0, -5.0, 5.0],
            [3.0, 3.0, 3.0, 3.0],
        ]
        for state in states:
            derivs = self.app._dpend_derivs(state)
            for d in derivs:
                assert math.isfinite(d), f"Non-finite derivative for state {state}"


class TestDPendRK4:
    """Test the Runge-Kutta 4th order integrator."""

    def setup_method(self):
        self.app = _make_app()
        self.app._dpend_init(0)

    def test_rk4_step_returns_four_values(self):
        result = self.app._dpend_rk4_step(self.app.dpend_p1)
        assert len(result) == 4

    def test_rk4_preserves_state_length(self):
        state = [1.0, 2.0, 0.5, -0.5]
        result = self.app._dpend_rk4_step(state)
        assert len(result) == 4

    def test_rk4_equilibrium_stays(self):
        """Pendulum at equilibrium (hanging down, no velocity) should stay."""
        state = [0.0, 0.0, 0.0, 0.0]
        result = self.app._dpend_rk4_step(state)
        for val in result:
            assert abs(val) < 1e-8

    def test_rk4_time_step_effect(self):
        """Smaller dt should produce smaller state changes."""
        state = [math.pi * 0.5, math.pi * 0.3, 0.0, 0.0]
        self.app.dpend_dt = 0.01
        result_small = self.app._dpend_rk4_step(state)
        self.app.dpend_dt = 0.001
        result_tiny = self.app._dpend_rk4_step(state)
        # Change with smaller dt should be smaller
        change_small = sum(abs(result_small[i] - state[i]) for i in range(4))
        change_tiny = sum(abs(result_tiny[i] - state[i]) for i in range(4))
        assert change_tiny < change_small

    def test_rk4_many_steps_finite(self):
        """Many RK4 steps should stay finite."""
        state = list(self.app.dpend_p1)
        for _ in range(1000):
            state = self.app._dpend_rk4_step(state)
        for val in state:
            assert math.isfinite(val), f"Non-finite value after 1000 steps: {state}"


class TestDPendTipPos:
    """Test tip position calculation."""

    def setup_method(self):
        self.app = _make_app()
        self.app._dpend_init(0)

    def test_hanging_down_tip(self):
        """Both arms hanging straight down: tip at (0, l1+l2)."""
        state = [0.0, 0.0, 0.0, 0.0]
        x, y = self.app._dpend_tip_pos(state)
        assert abs(x) < 1e-10
        assert y == pytest.approx(self.app.dpend_l1 + self.app.dpend_l2)

    def test_horizontal_right(self):
        """Both arms pointing right (theta = pi/2)."""
        state = [math.pi / 2, math.pi / 2, 0.0, 0.0]
        x, y = self.app._dpend_tip_pos(state)
        l1, l2 = self.app.dpend_l1, self.app.dpend_l2
        assert x == pytest.approx(l1 + l2, abs=1e-10)
        assert abs(y) < 1e-10

    def test_straight_up(self):
        """Both arms straight up (theta = pi): tip at (0, -(l1+l2))."""
        state = [math.pi, math.pi, 0.0, 0.0]
        x, y = self.app._dpend_tip_pos(state)
        l1, l2 = self.app.dpend_l1, self.app.dpend_l2
        assert abs(x) < 1e-10
        assert y == pytest.approx(-(l1 + l2), abs=1e-10)

    def test_max_distance(self):
        """Tip should never be farther than l1 + l2 from origin."""
        state = list(self.app.dpend_p1)
        for _ in range(100):
            state = self.app._dpend_rk4_step(state)
            x, y = self.app._dpend_tip_pos(state)
            dist = math.sqrt(x * x + y * y)
            max_dist = self.app.dpend_l1 + self.app.dpend_l2
            assert dist <= max_dist + 1e-6


class TestDPendStep:
    """Test the full step function."""

    def setup_method(self):
        self.app = _make_app()

    def test_generation_increments(self):
        self.app._dpend_init(0)
        assert self.app.dpend_generation == 0
        self.app._dpend_step()
        assert self.app.dpend_generation == 1

    def test_trail_grows(self):
        self.app._dpend_init(0)
        self.app._dpend_step()
        assert len(self.app.dpend_trail1) == 1
        self.app._dpend_step()
        assert len(self.app.dpend_trail1) == 2

    def test_dual_trail_grows(self):
        """When dual mode is on, both trails should grow."""
        self.app._dpend_init(0)
        assert self.app.dpend_dual is True
        self.app._dpend_step()
        assert len(self.app.dpend_trail1) == 1
        assert len(self.app.dpend_trail2) == 1

    def test_single_mode_no_trail2(self):
        """When dual mode is off, trail2 should not grow."""
        self.app._dpend_init(0)
        self.app.dpend_dual = False
        self.app._dpend_step()
        assert len(self.app.dpend_trail1) == 1
        assert len(self.app.dpend_trail2) == 0

    def test_trail_capped_at_max(self):
        """Trail should not exceed max_trail."""
        self.app._dpend_init(0)
        self.app.dpend_max_trail = 10
        for _ in range(20):
            self.app._dpend_step()
        assert len(self.app.dpend_trail1) == 10

    def test_trail_entries_are_tuples(self):
        self.app._dpend_init(0)
        self.app._dpend_step()
        tip = self.app.dpend_trail1[0]
        assert isinstance(tip, tuple)
        assert len(tip) == 2
        assert math.isfinite(tip[0])
        assert math.isfinite(tip[1])


class TestDPendEnergyConservation:
    """Test that RK4 approximately conserves energy.

    Uses the 'Gentle' preset (small angles) where RK4 is most accurate
    and the dynamics are well-behaved.
    """

    def setup_method(self):
        self.app = _make_app()
        self.app._dpend_init(1)  # Gentle preset — small angles

    def _energy(self, state):
        """Compute total energy of the double pendulum."""
        t1, t2, w1, w2 = state
        m1, m2 = self.app.dpend_m1, self.app.dpend_m2
        l1, l2 = self.app.dpend_l1, self.app.dpend_l2
        g = self.app.dpend_g

        # Kinetic energy
        T = 0.5 * (m1 + m2) * l1**2 * w1**2 + \
            0.5 * m2 * l2**2 * w2**2 + \
            m2 * l1 * l2 * w1 * w2 * math.cos(t1 - t2)

        # Potential energy (y-axis points down, reference at pivot)
        V = -(m1 + m2) * g * l1 * math.cos(t1) - \
            m2 * g * l2 * math.cos(t2)

        return T + V

    def test_energy_conserved_short_run(self):
        """Energy should be approximately conserved over 200 steps (1s of sim time)."""
        state = list(self.app.dpend_p1)
        E0 = self._energy(state)
        for _ in range(200):
            state = self.app._dpend_rk4_step(state)
        E1 = self._energy(state)
        rel_error = abs(E1 - E0) / (abs(E0) + 1e-10)
        assert rel_error < 0.001, f"Energy drift: E0={E0:.6f}, E1={E1:.6f}, rel={rel_error:.6f}"

    def test_energy_conserved_long_run(self):
        """Energy should be approximately conserved over 2000 steps (10s of sim time)."""
        state = list(self.app.dpend_p1)
        E0 = self._energy(state)
        for _ in range(2000):
            state = self.app._dpend_rk4_step(state)
        E1 = self._energy(state)
        rel_error = abs(E1 - E0) / (abs(E0) + 1e-10)
        assert rel_error < 0.01, f"Energy drift over 2000 steps: rel={rel_error:.6f}"


class TestDPendChaos:
    """Test sensitive dependence on initial conditions (chaos)."""

    def setup_method(self):
        self.app = _make_app()

    def test_divergence_from_perturbation(self):
        """Two nearly identical initial conditions should diverge over time."""
        self.app._dpend_init(0)  # Classic
        state1 = list(self.app.dpend_p1)
        state2 = list(self.app.dpend_p2)  # differs by 0.001 in theta1

        # Run both for many steps
        for _ in range(2000):
            state1 = self.app._dpend_rk4_step(state1)
            state2 = self.app._dpend_rk4_step(state2)

        # After enough time, the states should diverge significantly
        angle_diff = abs(state1[0] - state2[0]) + abs(state1[1] - state2[1])
        assert angle_diff > 0.1, f"Expected divergence but got diff={angle_diff:.6f}"

    def test_gentle_stays_close_initially(self):
        """With gentle (small angle) preset, divergence should be slow initially."""
        self.app._dpend_init(1)  # Gentle
        state1 = list(self.app.dpend_p1)
        state2 = list(self.app.dpend_p2)

        # After just a few steps, they should still be close
        for _ in range(10):
            state1 = self.app._dpend_rk4_step(state1)
            state2 = self.app._dpend_rk4_step(state2)

        angle_diff = abs(state1[0] - state2[0]) + abs(state1[1] - state2[1])
        assert angle_diff < 0.1


class TestDPendDrawLine:
    """Test Bresenham line drawing utility."""

    def setup_method(self):
        self.app = _make_app()
        self.app._dpend_init(0)

    def test_draw_line_no_crash(self):
        """Drawing a line should not crash."""
        self.app._dpend_draw_line(10, 10, 20, 15, "-", 0, 40, 120)

    def test_draw_line_zero_length(self):
        """Drawing a zero-length line (point) should not crash."""
        self.app._dpend_draw_line(10, 10, 10, 10, "*", 0, 40, 120)

    def test_draw_line_vertical(self):
        """Vertical line should not crash."""
        self.app._dpend_draw_line(10, 5, 10, 25, "|", 0, 40, 120)

    def test_draw_line_horizontal(self):
        """Horizontal line should not crash."""
        self.app._dpend_draw_line(5, 10, 25, 10, "-", 0, 40, 120)
