"""Tests for strange_attractors mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.strange_attractors import register, QWALK_PRESETS


class TestStrangeAttractors:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))
        # attractor_num_particles is normally set in app.__init__
        self.app.attractor_num_particles = 20

    def test_enter(self):
        self.app._enter_attractor_mode()
        assert self.app.attractor_menu is True
        assert self.app.attractor_menu_sel == 0

    def test_step_no_crash(self):
        self.app.attractor_mode = True
        self.app.attractor_menu_sel = 0
        self.app._attractor_init(0)
        for _ in range(10):
            self.app._attractor_step()
        assert self.app.attractor_generation == 10

    def test_exit_cleanup(self):
        self.app.attractor_mode = True
        self.app.attractor_menu_sel = 0
        self.app._attractor_init(0)
        self.app._attractor_step()
        self.app._exit_attractor_mode()
        assert self.app.attractor_mode is False
        assert self.app.attractor_menu is False
        assert self.app.attractor_running is False
        assert self.app.attractor_density == []
        assert self.app.attractor_trails == []

    # ── ODE correctness tests ──

    def test_lorenz_ode(self):
        """Verify Lorenz attractor ODE: dx=sigma*(y-x), dy=x*(rho-z)-y, dz=x*y-beta*z."""
        self.app._attractor_init(0)  # Lorenz preset
        self.app.attractor_type = "lorenz"
        self.app.attractor_params = {"sigma": 10.0, "rho": 28.0, "beta": 8.0 / 3.0}
        x, y, z = 1.0, 2.0, 3.0
        dx, dy, dz = self.app._attractor_ode(x, y, z)
        assert dx == 10.0 * (2.0 - 1.0)  # sigma * (y - x) = 10
        assert dy == 1.0 * (28.0 - 3.0) - 2.0  # x*(rho-z) - y = 23
        assert dz == 1.0 * 2.0 - (8.0 / 3.0) * 3.0  # x*y - beta*z = -6

    def test_rossler_ode(self):
        """Verify Rossler ODE: dx=-y-z, dy=x+a*y, dz=b+z*(x-c)."""
        self.app._attractor_init(0)
        self.app.attractor_type = "rossler"
        self.app.attractor_params = {"a": 0.2, "b": 0.2, "c": 5.7}
        x, y, z = 1.0, 2.0, 0.5
        dx, dy, dz = self.app._attractor_ode(x, y, z)
        assert dx == -2.0 - 0.5  # -y - z
        assert dy == 1.0 + 0.2 * 2.0  # x + a*y
        assert abs(dz - (0.2 + 0.5 * (1.0 - 5.7))) < 1e-10  # b + z*(x-c)

    def test_thomas_ode(self):
        """Verify Thomas attractor ODE: dx=sin(y)-b*x, dy=sin(z)-b*y, dz=sin(x)-b*z."""
        self.app._attractor_init(0)
        self.app.attractor_type = "thomas"
        self.app.attractor_params = {"b": 0.208186}
        x, y, z = 1.0, 2.0, 3.0
        dx, dy, dz = self.app._attractor_ode(x, y, z)
        assert abs(dx - (math.sin(2.0) - 0.208186 * 1.0)) < 1e-10
        assert abs(dy - (math.sin(3.0) - 0.208186 * 2.0)) < 1e-10
        assert abs(dz - (math.sin(1.0) - 0.208186 * 3.0)) < 1e-10

    def test_aizawa_ode(self):
        """Verify Aizawa attractor ODE."""
        self.app._attractor_init(0)
        self.app.attractor_type = "aizawa"
        params = {"a": 0.95, "b": 0.7, "c": 0.6, "d": 3.5, "e": 0.25, "f": 0.1}
        self.app.attractor_params = params
        x, y, z = 0.1, 0.0, 0.0
        dx, dy, dz = self.app._attractor_ode(x, y, z)
        a, b, c, d, e, f = 0.95, 0.7, 0.6, 3.5, 0.25, 0.1
        expected_dx = (z - b) * x - d * y
        expected_dy = d * x + (z - b) * y
        expected_dz = c + a * z - z**3 / 3.0 - (x**2 + y**2) * (1.0 + e * z) + f * z * x**3
        assert abs(dx - expected_dx) < 1e-10
        assert abs(dy - expected_dy) < 1e-10
        assert abs(dz - expected_dz) < 1e-10

    def test_halvorsen_ode(self):
        """Verify Halvorsen attractor ODE."""
        self.app._attractor_init(0)
        self.app.attractor_type = "halvorsen"
        self.app.attractor_params = {"a": 1.89}
        x, y, z = 1.0, 2.0, 3.0
        dx, dy, dz = self.app._attractor_ode(x, y, z)
        a = 1.89
        assert abs(dx - (-a * x - 4.0 * y - 4.0 * z - y * y)) < 1e-10
        assert abs(dy - (-a * y - 4.0 * z - 4.0 * x - z * z)) < 1e-10
        assert abs(dz - (-a * z - 4.0 * x - 4.0 * y - x * x)) < 1e-10

    def test_chen_ode(self):
        """Verify Chen attractor ODE: dx=a*(y-x), dy=(c-a)*x - x*z + c*y, dz=x*y - b*z."""
        self.app._attractor_init(0)
        self.app.attractor_type = "chen"
        self.app.attractor_params = {"a": 35.0, "b": 3.0, "c": 28.0}
        x, y, z = 1.0, 2.0, 3.0
        dx, dy, dz = self.app._attractor_ode(x, y, z)
        assert abs(dx - 35.0 * (2.0 - 1.0)) < 1e-10
        assert abs(dy - ((28.0 - 35.0) * 1.0 - 1.0 * 3.0 + 28.0 * 2.0)) < 1e-10
        assert abs(dz - (1.0 * 2.0 - 3.0 * 3.0)) < 1e-10

    def test_unknown_type_returns_zero(self):
        """Unknown attractor type returns zero derivatives."""
        self.app._attractor_init(0)
        self.app.attractor_type = "nonexistent"
        dx, dy, dz = self.app._attractor_ode(1.0, 2.0, 3.0)
        assert dx == 0.0
        assert dy == 0.0
        assert dz == 0.0

    # ── Integration tests ──

    def test_rk2_step_no_density(self):
        """Warm-up step uses RK2 (midpoint) integration and particles stay bounded."""
        self.app._attractor_init(0)
        self.app.attractor_trails = [(1.0, 1.0, 1.0)]
        old = self.app.attractor_trails[0]
        self.app._attractor_step_no_density()
        new = self.app.attractor_trails[0]
        # Particle should have moved
        assert new != old
        # Clamped within +-500
        for coord in new:
            assert -500.0 <= coord <= 500.0

    def test_rk2_step_with_density(self):
        """Main step accumulates density on the grid."""
        self.app._attractor_init(0)
        self.app._attractor_step()
        density = self.app.attractor_density
        total = sum(density[r][c] for r in range(self.app.attractor_rows)
                    for c in range(self.app.attractor_cols))
        # Should have accumulated some density from the particles
        assert total > 0.0

    def test_particle_clamping(self):
        """Particles at extreme positions get clamped."""
        self.app._attractor_init(0)
        self.app.attractor_trails = [(999.0, 999.0, 999.0)]
        self.app._attractor_step_no_density()
        for coord in self.app.attractor_trails[0]:
            assert -500.0 <= coord <= 500.0

    # ── All presets init without crash ──

    def test_all_presets_init(self):
        """Every preset initializes without error."""
        for idx in range(len(self.app.ATTRACTOR_PRESETS)):
            random.seed(42)
            self.app._attractor_init(idx)
            assert self.app.attractor_mode is True
            assert len(self.app.attractor_trails) == self.app.attractor_num_particles

    def test_all_presets_step(self):
        """Every preset can run steps without error."""
        for idx in range(len(self.app.ATTRACTOR_PRESETS)):
            random.seed(42)
            self.app._attractor_init(idx)
            for _ in range(5):
                self.app._attractor_step()
            assert self.app.attractor_generation == 5

    # ── Density normalization ──

    def test_max_density_tracking(self):
        """Max density tracks correctly and decays."""
        self.app._attractor_init(0)
        for _ in range(20):
            self.app._attractor_step()
        assert self.app.attractor_max_density >= 1.0

    def test_density_clear_on_reinit(self):
        """Density grid is fresh after re-initialization."""
        self.app._attractor_init(0)
        for _ in range(10):
            self.app._attractor_step()
        # Re-init should produce fresh density
        self.app._attractor_init(0)
        density = self.app.attractor_density
        total = sum(density[r][c] for r in range(self.app.attractor_rows)
                    for c in range(self.app.attractor_cols))
        assert total == 0.0

    # ── Projection and rotation ──

    def test_rotation_affects_projection(self):
        """Changing angles affects where density lands."""
        random.seed(42)
        self.app._attractor_init(0)
        self.app.attractor_angle_z = 0.0
        for _ in range(10):
            self.app._attractor_step()
        d1 = [row[:] for row in self.app.attractor_density]

        random.seed(42)
        self.app._attractor_init(0)
        self.app.attractor_angle_z = 1.5
        for _ in range(10):
            self.app._attractor_step()
        d2 = self.app.attractor_density

        # Density distributions should differ
        diff = sum(abs(d1[r][c] - d2[r][c])
                   for r in range(min(len(d1), len(d2)))
                   for c in range(min(len(d1[0]), len(d2[0]))))
        assert diff > 0.0

    # ── QWALK_PRESETS is exported ──

    def test_qwalk_presets_exported(self):
        """QWALK_PRESETS list is available in this module."""
        assert len(QWALK_PRESETS) > 0
        for preset in QWALK_PRESETS:
            assert len(preset) == 5  # (name, desc, coin, init, boundary)
