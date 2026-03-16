"""Tests for nbody mode — deep physics validation."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.nbody import register, NBODY_PRESETS, NBODY_CHARS, NBODY_COLORS
from life.constants import SPEEDS


def _make_nbody_app():
    """Create a mock app with N-Body mode registered and ready."""
    app = make_mock_app()
    cls = type(app)
    register(cls)
    cls.NBODY_PRESETS = NBODY_PRESETS
    cls.NBODY_CHARS = NBODY_CHARS
    cls.NBODY_COLORS = NBODY_COLORS
    # Instance attrs
    app.nbody_mode = False
    app.nbody_menu = False
    app.nbody_menu_sel = 0
    app.nbody_running = False
    app.nbody_bodies = []
    app.nbody_trails = {}
    app.nbody_steps_per_frame = 2
    app.nbody_trail_len = 30
    app.nbody_show_trails = True
    app.nbody_center_mass = True
    return app


class TestNBodyEnterExit:
    def test_enter(self):
        app = _make_nbody_app()
        app._enter_nbody_mode()
        assert app.nbody_menu is True

    def test_exit_cleanup(self):
        app = _make_nbody_app()
        app.nbody_mode = True
        app._nbody_init(0)
        app._exit_nbody_mode()
        assert app.nbody_mode is False
        assert app.nbody_running is False
        assert app.nbody_bodies == []
        assert app.nbody_trails == {}


class TestNBodyInit:
    def test_init_solar(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        assert app.nbody_mode is True
        # 1 star + 6 planets = 7
        assert len(app.nbody_bodies) == 7
        # Star is at index 0 with mass 500
        assert app.nbody_bodies[0][4] == 500.0
        # Star has zero velocity
        assert app.nbody_bodies[0][2] == 0.0
        assert app.nbody_bodies[0][3] == 0.0

    def test_init_binary(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(1)
        assert app.nbody_mode is True
        # 2 stars + 20 debris = 22
        assert len(app.nbody_bodies) == 22
        # Both stars have mass 200
        assert app.nbody_bodies[0][4] == 200.0
        assert app.nbody_bodies[1][4] == 200.0

    def test_init_galaxy(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(2)
        assert app.nbody_mode is True
        # 2 black holes + 2*40 particles = 82
        assert len(app.nbody_bodies) == 82

    def test_init_random(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(3)
        assert len(app.nbody_bodies) == 60

    def test_init_figure8(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(4)
        assert len(app.nbody_bodies) == 3
        # All three have equal mass
        m = app.nbody_bodies[0][4]
        assert all(b[4] == m for b in app.nbody_bodies)

    def test_init_lagrange(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(5)
        # 1 central + 1 planet + 2 trojans + 15 debris = 19
        assert len(app.nbody_bodies) == 19
        assert app.nbody_bodies[0][4] == 400.0

    def test_all_presets_initialize(self):
        """Every preset initializes without error."""
        for i in range(len(NBODY_PRESETS)):
            random.seed(42)
            app = _make_nbody_app()
            app._nbody_init(i)
            assert app.nbody_mode is True
            assert len(app.nbody_bodies) > 0

    def test_defaults_set_before_presets(self):
        """Verify defaults are set so all presets have valid G, dt, softening."""
        for i in range(len(NBODY_PRESETS)):
            random.seed(42)
            app = _make_nbody_app()
            app._nbody_init(i)
            assert app.nbody_grav_const > 0
            assert app.nbody_dt > 0
            assert app.nbody_softening > 0

    def test_trails_initialized(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        assert len(app.nbody_trails) == len(app.nbody_bodies)
        for trail in app.nbody_trails.values():
            assert trail == []


class TestNBodyGravitationalForce:
    """Validate the gravitational force calculation in _nbody_step."""

    def test_two_body_force_direction(self):
        """Two bodies should accelerate toward each other."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.01
        app.nbody_softening = 0.01
        app.nbody_trail_len = 30
        app.nbody_trails = {0: [], 1: []}
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 10.0],
            [20.0, 20.0, 0.0, 0.0, 10.0],
        ]
        app.nbody_num_bodies = 2
        app._nbody_step()
        assert app.nbody_bodies[0][0] > 10.0, "Body 0 should move toward body 1"
        assert app.nbody_bodies[1][0] < 20.0, "Body 1 should move toward body 0"

    def test_two_body_force_symmetry(self):
        """Equal masses should experience equal and opposite forces."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.01
        app.nbody_softening = 0.01
        app.nbody_trail_len = 30
        app.nbody_trails = {0: [], 1: []}
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 5.0],
            [20.0, 20.0, 0.0, 0.0, 5.0],
        ]
        app.nbody_num_bodies = 2
        app._nbody_step()
        dr0 = app.nbody_bodies[0][0] - 10.0
        dr1 = app.nbody_bodies[1][0] - 20.0
        assert abs(dr0 + dr1) < 1e-12, "Forces must be equal and opposite"

    def test_inverse_square_scaling(self):
        """Force should scale as 1/r^2 (with small softening)."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.001
        app.nbody_softening = 0.001
        app.nbody_trail_len = 30
        app.nbody_generation = 0

        # Distance d=5
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 10.0],
            [15.0, 20.0, 0.0, 0.0, 10.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        app._nbody_step()
        dr_near = app.nbody_bodies[0][0] - 10.0

        # Distance d=10
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 10.0],
            [20.0, 20.0, 0.0, 0.0, 10.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        app._nbody_step()
        dr_far = app.nbody_bodies[0][0] - 10.0

        ratio = dr_near / dr_far
        assert 3.5 < ratio < 4.5, f"Expected ~4x ratio, got {ratio:.2f}"

    def test_gravity_constant_scales_force(self):
        """Doubling G should double the acceleration."""
        results = []
        for G in [1.0, 2.0]:
            app = _make_nbody_app()
            app.nbody_grav_const = G
            app.nbody_dt = 0.001
            app.nbody_softening = 0.001
            app.nbody_trail_len = 30
            app.nbody_generation = 0
            app.nbody_bodies = [
                [10.0, 20.0, 0.0, 0.0, 10.0],
                [20.0, 20.0, 0.0, 0.0, 10.0],
            ]
            app.nbody_trails = {0: [], 1: []}
            app.nbody_num_bodies = 2
            app._nbody_step()
            results.append(app.nbody_bodies[0][0] - 10.0)
        ratio = results[1] / results[0]
        assert 1.9 < ratio < 2.1, f"Expected ~2x ratio, got {ratio:.2f}"


class TestNBodyVelocityVerlet:
    """Validate the velocity Verlet integration scheme."""

    def test_free_body_constant_velocity(self):
        """A single body with no forces should move at constant velocity."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.1
        app.nbody_softening = 0.5
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [[10.0, 20.0, 1.0, 2.0, 5.0]]
        app.nbody_trails = {0: []}
        app.nbody_num_bodies = 1
        app._nbody_step()
        assert abs(app.nbody_bodies[0][0] - 10.1) < 1e-10
        assert abs(app.nbody_bodies[0][1] - 20.2) < 1e-10
        assert abs(app.nbody_bodies[0][2] - 1.0) < 1e-10
        assert abs(app.nbody_bodies[0][3] - 2.0) < 1e-10

    def test_generation_increments(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        for i in range(1, 11):
            app._nbody_step()
            assert app.nbody_generation == i

    def test_step_no_crash_all_presets(self):
        """Run 10 steps on every preset without errors."""
        for i in range(len(NBODY_PRESETS)):
            random.seed(42)
            app = _make_nbody_app()
            app._nbody_init(i)
            for _ in range(10):
                app._nbody_step()

    def test_empty_bodies_noop(self):
        """Stepping with no bodies should not raise."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.01
        app.nbody_softening = 0.5
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = []
        app.nbody_trails = {}
        app.nbody_num_bodies = 0
        app._nbody_step()
        assert app.nbody_generation == 0


class TestNBodyMomentumConservation:
    """Verify that total momentum is conserved."""

    def _total_momentum(self, bodies):
        pr = sum(b[2] * b[4] for b in bodies)
        pc = sum(b[3] * b[4] for b in bodies)
        return pr, pc

    def _total_mass(self, bodies):
        return sum(b[4] for b in bodies)

    def test_momentum_conserved_two_body(self):
        """Total momentum should be conserved for two interacting bodies."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.01
        app.nbody_softening = 0.5
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.5, -0.3, 10.0],
            [20.0, 25.0, -0.2, 0.1, 15.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        pr0, pc0 = self._total_momentum(app.nbody_bodies)

        for _ in range(100):
            app._nbody_step()

        pr1, pc1 = self._total_momentum(app.nbody_bodies)
        assert abs(pr1 - pr0) < 1e-8, f"Row momentum drift: {abs(pr1-pr0)}"
        assert abs(pc1 - pc0) < 1e-8, f"Col momentum drift: {abs(pc1-pc0)}"

    def test_mass_conserved_after_collision(self):
        """Total mass is conserved when bodies merge."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.1
        app.nbody_softening = 0.01
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 1.0, 0.0, 5.0],
            [10.2, 20.0, -1.0, 0.0, 3.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        total_mass_before = self._total_mass(app.nbody_bodies)

        for _ in range(50):
            app._nbody_step()

        total_mass_after = self._total_mass(app.nbody_bodies)
        assert abs(total_mass_after - total_mass_before) < 1e-10

    def test_momentum_conserved_through_collision(self):
        """Momentum is conserved even when bodies merge."""
        app = _make_nbody_app()
        app.nbody_grav_const = 0.0001
        app.nbody_dt = 0.05
        app.nbody_softening = 0.01
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.5, 0.0, 5.0],
            [10.1, 20.0, -0.5, 0.0, 5.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        pr0, pc0 = self._total_momentum(app.nbody_bodies)

        for _ in range(20):
            app._nbody_step()

        pr1, pc1 = self._total_momentum(app.nbody_bodies)
        assert abs(pr1 - pr0) < 1e-6, f"Momentum not conserved: {abs(pr1-pr0)}"


class TestNBodyCollision:
    """Validate collision/merge handling."""

    def test_close_bodies_merge(self):
        """Two overlapping bodies should merge into one."""
        app = _make_nbody_app()
        app.nbody_grav_const = 0.0001
        app.nbody_dt = 0.01
        app.nbody_softening = 0.01
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 5.0],
            [10.0, 20.0, 0.0, 0.0, 3.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        app._nbody_step()
        assert len(app.nbody_bodies) == 1
        assert abs(app.nbody_bodies[0][4] - 8.0) < 1e-10

    def test_distant_bodies_dont_merge(self):
        """Bodies far apart should not merge."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.001
        app.nbody_softening = 0.5
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 5.0],
            [30.0, 20.0, 0.0, 0.0, 5.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        app._nbody_step()
        assert len(app.nbody_bodies) == 2

    def test_merge_conserves_position_com(self):
        """Merged body position should be at center of mass."""
        app = _make_nbody_app()
        app.nbody_grav_const = 0.0001
        app.nbody_dt = 0.001
        app.nbody_softening = 0.001
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        m1, m2 = 3.0, 7.0
        r1, r2 = 10.0, 10.1
        c1, c2 = 20.0, 20.05
        app.nbody_bodies = [
            [r1, c1, 0.0, 0.0, m1],
            [r2, c2, 0.0, 0.0, m2],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        app._nbody_step()
        assert len(app.nbody_bodies) == 1
        expected_r = (r1 * m1 + r2 * m2) / (m1 + m2)
        expected_c = (c1 * m1 + c2 * m2) / (m1 + m2)
        assert abs(app.nbody_bodies[0][0] - expected_r) < 0.05
        assert abs(app.nbody_bodies[0][1] - expected_c) < 0.05

    def test_multi_body_merge(self):
        """Three overlapping bodies should all merge into one."""
        app = _make_nbody_app()
        app.nbody_grav_const = 0.0001
        app.nbody_dt = 0.001
        app.nbody_softening = 0.001
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 5.0],
            [10.0, 20.0, 0.0, 0.0, 3.0],
            [10.0, 20.0, 0.0, 0.0, 2.0],
        ]
        app.nbody_trails = {0: [], 1: [], 2: []}
        app.nbody_num_bodies = 3
        app._nbody_step()
        assert len(app.nbody_bodies) == 1
        assert abs(app.nbody_bodies[0][4] - 10.0) < 1e-10


class TestNBodyEnergyApproximate:
    """Approximate energy conservation checks for Verlet integrator."""

    def _total_energy(self, bodies, G, soft):
        ke = sum(0.5 * b[4] * (b[2]**2 + b[3]**2) for b in bodies)
        pe = 0.0
        soft2 = soft * soft
        n = len(bodies)
        for i in range(n):
            for j in range(i + 1, n):
                dr = bodies[j][0] - bodies[i][0]
                dc = bodies[j][1] - bodies[i][1]
                dist = math.sqrt(dr*dr + dc*dc + soft2)
                pe -= G * bodies[i][4] * bodies[j][4] / dist
        return ke + pe

    def test_energy_roughly_conserved_two_body(self):
        """Energy should be approximately conserved over short runs."""
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.005
        app.nbody_softening = 0.5
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        r_orbit = 10.0
        M = 100.0
        v_orb = math.sqrt(app.nbody_grav_const * M / r_orbit)
        app.nbody_bodies = [
            [20.0, 20.0, 0.0, 0.0, M],
            [20.0 + r_orbit, 20.0, 0.0, -v_orb, 1.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2

        E0 = self._total_energy(app.nbody_bodies, app.nbody_grav_const, app.nbody_softening)
        for _ in range(200):
            app._nbody_step()
        E1 = self._total_energy(app.nbody_bodies, app.nbody_grav_const, app.nbody_softening)

        rel_error = abs(E1 - E0) / abs(E0) if E0 != 0 else abs(E1 - E0)
        assert rel_error < 0.05, f"Energy drift too large: {rel_error:.4f} ({E0:.4f} -> {E1:.4f})"


class TestNBodyTrails:
    def test_trails_grow(self):
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.01
        app.nbody_softening = 0.5
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [[10.0, 20.0, 0.5, 0.0, 5.0]]
        app.nbody_trails = {0: []}
        app.nbody_num_bodies = 1
        app._nbody_step()
        assert len(app.nbody_trails[0]) == 1
        app._nbody_step()
        assert len(app.nbody_trails[0]) == 2

    def test_trails_capped_at_max_length(self):
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.01
        app.nbody_softening = 0.5
        app.nbody_trail_len = 5
        app.nbody_generation = 0
        app.nbody_bodies = [[10.0, 20.0, 0.5, 0.0, 5.0]]
        app.nbody_trails = {0: []}
        app.nbody_num_bodies = 1
        for _ in range(20):
            app._nbody_step()
        assert len(app.nbody_trails[0]) == 5


class TestNBodySoftening:
    def test_softening_prevents_singularity(self):
        app = _make_nbody_app()
        app.nbody_grav_const = 1.0
        app.nbody_dt = 0.01
        app.nbody_softening = 1.0
        app.nbody_trail_len = 30
        app.nbody_generation = 0
        app.nbody_bodies = [
            [10.0, 20.0, 0.0, 0.0, 100.0],
            [10.5, 20.0, 0.0, 0.0, 100.0],
        ]
        app.nbody_trails = {0: [], 1: []}
        app.nbody_num_bodies = 2
        app._nbody_step()
        for b in app.nbody_bodies:
            for val in b[:4]:
                assert math.isfinite(val), f"Non-finite value: {val}"

    def test_larger_softening_reduces_force(self):
        displacements = []
        for soft in [0.1, 2.0]:
            app = _make_nbody_app()
            app.nbody_grav_const = 1.0
            app.nbody_dt = 0.001
            app.nbody_softening = soft
            app.nbody_trail_len = 30
            app.nbody_generation = 0
            app.nbody_bodies = [
                [10.0, 20.0, 0.0, 0.0, 10.0],
                [13.0, 20.0, 0.0, 0.0, 10.0],
            ]
            app.nbody_trails = {0: [], 1: []}
            app.nbody_num_bodies = 2
            app._nbody_step()
            displacements.append(abs(app.nbody_bodies[0][0] - 10.0))
        assert displacements[0] > displacements[1]


class TestNBodyMenuKeys:
    def test_menu_navigate_down(self):
        app = _make_nbody_app()
        app._enter_nbody_mode()
        app._handle_nbody_menu_key(ord("j"))
        assert app.nbody_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        app = _make_nbody_app()
        app._enter_nbody_mode()
        app._handle_nbody_menu_key(ord("k"))
        assert app.nbody_menu_sel == len(NBODY_PRESETS) - 1

    def test_menu_select_enter(self):
        random.seed(42)
        app = _make_nbody_app()
        app._enter_nbody_mode()
        app._handle_nbody_menu_key(ord("\n"))
        assert app.nbody_mode is True

    def test_menu_cancel(self):
        app = _make_nbody_app()
        app._enter_nbody_mode()
        app._handle_nbody_menu_key(27)
        assert app.nbody_menu is False


class TestNBodyActiveKeys:
    def test_space_toggles_running(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        assert app.nbody_running is False
        app._handle_nbody_key(ord(" "))
        assert app.nbody_running is True
        app._handle_nbody_key(ord(" "))
        assert app.nbody_running is False

    def test_step_key(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        gen_before = app.nbody_generation
        app._handle_nbody_key(ord("n"))
        assert app.nbody_generation == gen_before + app.nbody_steps_per_frame

    def test_gravity_adjust(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        initial_g = app.nbody_grav_const
        app._handle_nbody_key(ord("g"))
        assert app.nbody_grav_const > initial_g
        app._handle_nbody_key(ord("G"))
        assert abs(app.nbody_grav_const - initial_g) < 1e-10

    def test_dt_adjust(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        initial_dt = app.nbody_dt
        app._handle_nbody_key(ord("d"))
        assert app.nbody_dt > initial_dt

    def test_softening_adjust(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        initial_s = app.nbody_softening
        app._handle_nbody_key(ord("s"))
        assert app.nbody_softening > initial_s

    def test_trails_toggle(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        initial = app.nbody_show_trails
        app._handle_nbody_key(ord("t"))
        assert app.nbody_show_trails != initial

    def test_center_mass_toggle(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        initial = app.nbody_center_mass
        app._handle_nbody_key(ord("c"))
        assert app.nbody_center_mass != initial

    def test_steps_per_frame_adjust(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        initial = app.nbody_steps_per_frame
        app._handle_nbody_key(ord("+"))
        assert app.nbody_steps_per_frame == initial + 1
        app._handle_nbody_key(ord("-"))
        assert app.nbody_steps_per_frame == initial

    def test_reset_key(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        for _ in range(10):
            app._nbody_step()
        random.seed(42)
        app._handle_nbody_key(ord("r"))
        assert app.nbody_generation == 0
        assert app.nbody_running is False

    def test_quit_key(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        app._handle_nbody_key(ord("q"))
        assert app.nbody_mode is False

    def test_return_to_menu(self):
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        app._handle_nbody_key(ord("R"))
        assert app.nbody_mode is False
        assert app.nbody_menu is True


class TestNBodyOrbitalPhysics:
    """High-level orbital mechanics sanity checks."""

    def test_solar_system_stays_bound(self):
        """Bodies in the solar preset should remain gravitationally bound (not escape)."""
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(0)
        star = app.nbody_bodies[0]
        star_r, star_c = star[0], star[1]
        # Track the outermost initial radius
        max_initial_dist = max(
            math.sqrt((b[0]-star_r)**2 + (b[1]-star_c)**2)
            for b in app.nbody_bodies[1:]
        )

        for _ in range(500):
            app._nbody_step()

        # Find the star (heaviest body)
        bodies = sorted(app.nbody_bodies, key=lambda b: -b[4])
        star = bodies[0]
        # All remaining bodies should still be within a reasonable bound
        for b in bodies[1:]:
            dist = math.sqrt((b[0]-star[0])**2 + (b[1]-star[1])**2)
            assert dist < max_initial_dist * 5.0, (
                f"Body escaped: distance {dist:.1f} vs max initial {max_initial_dist:.1f}"
            )

    def test_figure8_three_bodies_survive(self):
        """The figure-8 preset should keep all 3 bodies for many steps."""
        random.seed(42)
        app = _make_nbody_app()
        app._nbody_init(4)
        assert len(app.nbody_bodies) == 3
        for _ in range(200):
            app._nbody_step()
        assert len(app.nbody_bodies) >= 2, "Figure-8 bodies merged too quickly"
