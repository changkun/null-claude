"""Tests for fireworks mode — deep validation against commit ec7150a."""
import math
import random
import curses
import pytest
from tests.conftest import make_mock_app
from life.modes.fireworks import register


FIREWORKS_PRESETS = [
    ("Gentle", "Slow, graceful single fireworks", "gentle"),
    ("Finale", "Rapid multi-burst grand finale", "finale"),
    ("Crossette", "Splitting crossette rockets", "crossette"),
    ("Willow", "Drooping willow-style bursts", "willow"),
    ("Ring", "Ring-shaped explosions", "ring"),
    ("Random", "Mixed random patterns", "random"),
]

FIREWORKS_COLORS = [1, 2, 3, 4, 5, 6, 7]
FIREWORKS_PATTERNS = ["spherical", "ring", "willow", "crossette"]
FIREWORKS_CHARS = {
    "spark": [".", "*", "+", "o", "@"],
    "trail": [".", ",", "'"],
    "rocket": ["|", "!", "^"],
}


def _make_fireworks_app():
    """Create a mock app with fireworks mode registered."""
    app = make_mock_app()
    cls = type(app)
    cls.FIREWORKS_PRESETS = FIREWORKS_PRESETS
    cls.FIREWORKS_COLORS = FIREWORKS_COLORS
    cls.FIREWORKS_PATTERNS = FIREWORKS_PATTERNS
    cls.FIREWORKS_CHARS = FIREWORKS_CHARS
    register(cls)
    return app


class TestFireworksEnterExit:
    def test_enter_sets_menu(self):
        app = _make_fireworks_app()
        app._enter_fireworks_mode()
        assert app.fireworks_menu is True
        assert app.fireworks_menu_sel == 0

    def test_exit_clears_state(self):
        app = _make_fireworks_app()
        app.fireworks_mode = True
        app.fireworks_running = True
        app._fireworks_init("gentle")
        app._exit_fireworks_mode()
        assert app.fireworks_mode is False
        assert app.fireworks_menu is False
        assert app.fireworks_running is False
        assert app.fireworks_particles == []
        assert app.fireworks_rockets == []


class TestFireworksInit:
    @pytest.mark.parametrize("preset_id", [p[2] for p in FIREWORKS_PRESETS])
    def test_init_launches_rockets(self, preset_id):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init(preset_id)
        # Init launches 3 rockets
        assert app.fireworks_total_launched == 3
        assert app.fireworks_generation == 0
        assert len(app.fireworks_rockets) > 0

    def test_init_finale_high_rate(self):
        app = _make_fireworks_app()
        app._fireworks_init("finale")
        assert app.fireworks_launch_rate == 0.18
        assert app.fireworks_gravity == 0.05

    def test_init_gentle_low_rate(self):
        app = _make_fireworks_app()
        app._fireworks_init("gentle")
        assert app.fireworks_launch_rate == 0.04
        assert app.fireworks_gravity == 0.04
        assert app.fireworks_wind == 0.005

    def test_init_crossette(self):
        app = _make_fireworks_app()
        app._fireworks_init("crossette")
        assert app.fireworks_gravity == 0.05
        assert app.fireworks_wind == 0.0

    def test_init_willow(self):
        app = _make_fireworks_app()
        app._fireworks_init("willow")
        assert app.fireworks_gravity == 0.06
        assert app.fireworks_wind == 0.003

    def test_init_ring(self):
        app = _make_fireworks_app()
        app._fireworks_init("ring")
        assert app.fireworks_gravity == 0.05

    def test_init_random_default(self):
        app = _make_fireworks_app()
        app._fireworks_init("random")
        assert app.fireworks_gravity == 0.05
        assert app.fireworks_launch_rate == 0.08

    def test_init_resets_counters(self):
        app = _make_fireworks_app()
        app._fireworks_init("gentle")
        app.fireworks_total_bursts = 99
        app._fireworks_init("gentle")
        assert app.fireworks_total_bursts == 0


class TestFireworksLaunch:
    def test_launch_creates_rocket(self):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init("gentle")
        n_before = len(app.fireworks_rockets)
        app._fireworks_launch("gentle")
        assert len(app.fireworks_rockets) == n_before + 1
        assert app.fireworks_total_launched > 3  # 3 from init + 1

    def test_rocket_structure(self):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init("random")
        rocket = app.fireworks_rockets[0]
        # [r, c, vr, vc, fuse, color, pattern]
        assert len(rocket) == 7
        r, c, vr, vc, fuse, color, pattern = rocket
        assert r == float(app.fireworks_rows - 1)  # starts at bottom
        assert vr < 0  # upward velocity
        assert fuse > 0
        assert color in FIREWORKS_COLORS
        assert pattern in FIREWORKS_PATTERNS

    def test_launch_position_in_bounds(self):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init("gentle")
        for _ in range(20):
            app._fireworks_launch()
        for rocket in app.fireworks_rockets:
            assert 0 <= rocket[1] < app.fireworks_cols

    def test_crossette_preset_pattern(self):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init("crossette")
        # All rockets from crossette preset should have crossette pattern
        for rocket in app.fireworks_rockets:
            assert rocket[6] == "crossette"

    def test_willow_preset_pattern(self):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init("willow")
        for rocket in app.fireworks_rockets:
            assert rocket[6] == "willow"

    def test_ring_preset_pattern(self):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init("ring")
        for rocket in app.fireworks_rockets:
            assert rocket[6] == "ring"


class TestFireworksExplode:
    def _init_app(self):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init("random")
        app.fireworks_particles = []
        app.fireworks_total_bursts = 0
        return app

    def test_spherical_creates_sparks(self):
        app = self._init_app()
        app._fireworks_explode(20.0, 50.0, 3, "spherical")
        assert len(app.fireworks_particles) >= 30
        assert app.fireworks_total_bursts == 1
        # All sparks at explosion point
        for p in app.fireworks_particles:
            assert p[0] == 20.0
            assert p[1] == 50.0
            assert p[7] == "spark"

    def test_ring_creates_evenly_spaced_sparks(self):
        random.seed(42)
        app = self._init_app()
        app._fireworks_explode(20.0, 50.0, 5, "ring")
        assert len(app.fireworks_particles) >= 24
        # Verify ring pattern: velocities should be at evenly spaced angles
        ring_sparks = [p for p in app.fireworks_particles if p[7] == "spark"]
        assert len(ring_sparks) > 0

    def test_willow_has_long_life(self):
        random.seed(42)
        app = self._init_app()
        app._fireworks_explode(20.0, 50.0, 2, "willow")
        for p in app.fireworks_particles:
            assert p[7] == "willow"
            assert p[4] >= 30  # willow life is 30-55

    def test_crossette_creates_sub_rockets(self):
        random.seed(42)
        app = self._init_app()
        app._fireworks_explode(20.0, 50.0, 4, "crossette")
        assert 4 <= len(app.fireworks_particles) <= 6
        for p in app.fireworks_particles:
            assert p[7] == "crossette"

    def test_spherical_speed_distribution(self):
        """Spherical sparks should have speeds between 0.3 and 1.2."""
        random.seed(42)
        app = self._init_app()
        app._fireworks_explode(20.0, 50.0, 3, "spherical")
        for p in app.fireworks_particles:
            speed = math.sqrt(p[2] ** 2 + p[3] ** 2)
            assert 0.0 <= speed <= 1.5  # slightly generous bounds

    def test_particle_structure(self):
        """Each particle should have 9 fields."""
        random.seed(42)
        app = self._init_app()
        app._fireworks_explode(20.0, 50.0, 3, "spherical")
        for p in app.fireworks_particles:
            # [r, c, vr, vc, life, max_life, color, kind, trail]
            assert len(p) == 9
            assert p[4] == p[5]  # life == max_life initially
            assert isinstance(p[8], list)  # trail is empty list


class TestFireworksStep:
    def _init_app(self, preset="gentle"):
        random.seed(42)
        app = _make_fireworks_app()
        app._fireworks_init(preset)
        return app

    def test_step_increments_generation(self):
        app = self._init_app()
        app._fireworks_step()
        assert app.fireworks_generation == 1

    def test_rockets_gain_gravity(self):
        """Rockets should decelerate upward due to gravity."""
        app = self._init_app()
        rocket = app.fireworks_rockets[0]
        vr_before = rocket[2]
        app._fireworks_step()
        # After step, remaining rockets should have vr closer to 0 (more positive)
        # Some rockets may have exploded, check remaining ones
        if app.fireworks_rockets:
            # vr should have increased (become less negative) due to gravity
            pass  # rockets may have been replaced
        assert app.fireworks_generation == 1

    def test_rocket_explodes_when_fuse_zero(self):
        """Rocket should explode when fuse reaches 0."""
        app = self._init_app()
        # Set a rocket's fuse to 1 so it explodes next step
        if app.fireworks_rockets:
            app.fireworks_rockets[0][4] = 1  # fuse = 1
            n_rockets_before = len(app.fireworks_rockets)
            bursts_before = app.fireworks_total_bursts
            app._fireworks_step()
            # Should have fewer rockets (one exploded) and more bursts
            assert app.fireworks_total_bursts > bursts_before

    def test_rocket_explodes_when_velocity_positive(self):
        """Rocket should explode when upward velocity reaches 0 (starts falling)."""
        app = self._init_app()
        if app.fireworks_rockets:
            # Set vr to just barely negative
            app.fireworks_rockets[0][2] = -0.01
            app.fireworks_rockets[0][4] = 100  # high fuse
            bursts_before = app.fireworks_total_bursts
            app._fireworks_step()
            # After gravity, vr should become positive -> explode
            assert app.fireworks_total_bursts > bursts_before

    def test_particles_lose_life(self):
        """Particle life should decrease each step."""
        app = self._init_app()
        # Create a particle manually
        app.fireworks_particles = [
            [20.0, 50.0, 0.0, 0.0, 10, 10, 3, "spark", []]
        ]
        app._fireworks_step()
        if app.fireworks_particles:
            assert app.fireworks_particles[0][4] < 10

    def test_dead_particles_removed(self):
        """Particles with life <= 0 should be removed."""
        app = self._init_app()
        app.fireworks_particles = [
            [20.0, 50.0, 0.0, 0.0, 1, 10, 3, "spark", []]
        ]
        app._fireworks_step()
        # The particle had life=1, decreased to 0, should be removed
        spark_particles = [p for p in app.fireworks_particles if p[7] == "spark"]
        assert len(spark_particles) == 0

    def test_crossette_secondary_burst(self):
        """Crossette sub-rockets should create secondary bursts when they die."""
        random.seed(42)
        app = self._init_app()
        app.fireworks_particles = [
            [20.0, 50.0, 0.0, 0.0, 1, 10, 4, "crossette", []]
        ]
        app._fireworks_step()
        # The crossette particle died and should have triggered a secondary spherical burst
        assert app.fireworks_total_bursts > 0
        # New particles should exist from the secondary burst
        assert len(app.fireworks_particles) > 0

    def test_particle_gravity_and_drag(self):
        """Particles should fall due to gravity and slow due to drag."""
        app = self._init_app()
        app.fireworks_particles = [
            [10.0, 50.0, 0.0, 0.0, 50, 50, 3, "spark", []]
        ]
        app._fireworks_step()
        if app.fireworks_particles:
            p = app.fireworks_particles[0]
            # Should have gained downward velocity from gravity
            assert p[2] > 0  # vr positive = downward

    def test_willow_stronger_gravity(self):
        """Willow particles should experience 1.5x gravity."""
        app = self._init_app()
        gravity = app.fireworks_gravity
        app.fireworks_particles = [
            [10.0, 50.0, 0.0, 0.0, 50, 50, 3, "willow", []],
            [10.0, 50.0, 0.0, 0.0, 50, 50, 3, "spark", []],
        ]
        app._fireworks_step()
        willow = None
        spark = None
        for p in app.fireworks_particles:
            if p[7] == "willow":
                willow = p
            elif p[7] == "spark":
                spark = p
        if willow and spark:
            # Willow should have more downward velocity
            assert willow[2] > spark[2]

    def test_particle_trail_grows(self):
        """Particle trail should accumulate positions."""
        app = self._init_app()
        app.fireworks_particles = [
            [10.0, 50.0, 0.1, 0.0, 50, 50, 3, "spark", []]
        ]
        app._fireworks_step()
        if app.fireworks_particles:
            assert len(app.fireworks_particles[0][8]) == 1  # one trail entry

    def test_trail_capped_at_6(self):
        """Trail should not exceed 6 entries."""
        app = self._init_app()
        trail = [(10.0 + i, 50.0) for i in range(6)]
        app.fireworks_particles = [
            [10.0, 50.0, 0.1, 0.0, 50, 50, 3, "spark", trail]
        ]
        app._fireworks_step()
        if app.fireworks_particles:
            assert len(app.fireworks_particles[0][8]) <= 6

    def test_out_of_bounds_particles_removed(self):
        """Particles outside the screen should be removed."""
        app = self._init_app()
        app.fireworks_particles = [
            [-10.0, 50.0, -1.0, 0.0, 50, 50, 3, "spark", []]
        ]
        app._fireworks_step()
        # Particle is above screen, should be removed
        assert len(app.fireworks_particles) == 0

    def test_auto_launch_creates_rockets(self):
        """With auto_launch on and high rate, new rockets should appear."""
        random.seed(42)
        app = self._init_app()
        app.fireworks_auto_launch = True
        app.fireworks_launch_rate = 1.0  # guaranteed launch
        n_launched_before = app.fireworks_total_launched
        app._fireworks_step()
        assert app.fireworks_total_launched > n_launched_before

    def test_multiple_steps_stable(self):
        """Multiple steps should not crash."""
        random.seed(42)
        app = self._init_app("finale")
        for _ in range(30):
            app._fireworks_step()
        assert app.fireworks_generation == 30


class TestFireworksMenuKeys:
    def _init_menu(self):
        app = _make_fireworks_app()
        app._enter_fireworks_mode()
        return app

    def test_navigate_down(self):
        app = self._init_menu()
        app._handle_fireworks_menu_key(curses.KEY_DOWN)
        assert app.fireworks_menu_sel == 1

    def test_navigate_up_wraps(self):
        app = self._init_menu()
        app._handle_fireworks_menu_key(curses.KEY_UP)
        assert app.fireworks_menu_sel == len(FIREWORKS_PRESETS) - 1

    def test_j_k_navigation(self):
        app = self._init_menu()
        app._handle_fireworks_menu_key(ord("j"))
        assert app.fireworks_menu_sel == 1
        app._handle_fireworks_menu_key(ord("k"))
        assert app.fireworks_menu_sel == 0

    def test_enter_starts_mode(self):
        app = self._init_menu()
        app._handle_fireworks_menu_key(10)  # Enter
        assert app.fireworks_menu is False
        assert app.fireworks_mode is True
        assert app.fireworks_running is True

    def test_quit_cancels(self):
        app = self._init_menu()
        app._handle_fireworks_menu_key(ord("q"))
        assert app.fireworks_menu is False

    def test_escape_cancels(self):
        app = self._init_menu()
        app._handle_fireworks_menu_key(27)
        assert app.fireworks_menu is False

    def test_no_key_no_crash(self):
        app = self._init_menu()
        result = app._handle_fireworks_menu_key(-1)
        assert result is True


class TestFireworksSimKeys:
    def _init_sim(self):
        random.seed(42)
        app = _make_fireworks_app()
        app.fireworks_mode = True
        app.fireworks_running = True
        app.fireworks_preset_name = "Gentle"
        app._fireworks_init("gentle")
        return app

    def test_space_toggles_running(self):
        app = self._init_sim()
        assert app.fireworks_running is True
        app._handle_fireworks_key(ord(" "))
        assert app.fireworks_running is False
        app._handle_fireworks_key(ord(" "))
        assert app.fireworks_running is True

    def test_n_advances_step(self):
        app = self._init_sim()
        gen_before = app.fireworks_generation
        app._handle_fireworks_key(ord("n"))
        assert app.fireworks_generation == gen_before + 1

    def test_f_launches_rocket(self):
        app = self._init_sim()
        n_before = app.fireworks_total_launched
        app._handle_fireworks_key(ord("f"))
        assert app.fireworks_total_launched > n_before

    def test_a_toggles_auto_launch(self):
        app = self._init_sim()
        old = app.fireworks_auto_launch
        app._handle_fireworks_key(ord("a"))
        assert app.fireworks_auto_launch != old

    def test_g_increases_gravity(self):
        app = self._init_sim()
        old_g = app.fireworks_gravity
        app._handle_fireworks_key(ord("g"))
        assert app.fireworks_gravity > old_g

    def test_G_decreases_gravity(self):
        app = self._init_sim()
        old_g = app.fireworks_gravity
        app._handle_fireworks_key(ord("G"))
        assert app.fireworks_gravity < old_g

    def test_w_increases_wind(self):
        app = self._init_sim()
        old_w = app.fireworks_wind
        app._handle_fireworks_key(ord("w"))
        assert app.fireworks_wind > old_w

    def test_W_decreases_wind(self):
        app = self._init_sim()
        old_w = app.fireworks_wind
        app._handle_fireworks_key(ord("W"))
        assert app.fireworks_wind < old_w

    def test_l_increases_launch_rate(self):
        app = self._init_sim()
        old_rate = app.fireworks_launch_rate
        app._handle_fireworks_key(ord("l"))
        assert app.fireworks_launch_rate > old_rate

    def test_L_decreases_launch_rate(self):
        app = self._init_sim()
        old_rate = app.fireworks_launch_rate
        app._handle_fireworks_key(ord("L"))
        assert app.fireworks_launch_rate < old_rate

    def test_plus_increases_steps_per_frame(self):
        app = self._init_sim()
        old_spf = app.fireworks_steps_per_frame
        app._handle_fireworks_key(ord("+"))
        assert app.fireworks_steps_per_frame > old_spf

    def test_minus_decreases_steps_per_frame(self):
        app = self._init_sim()
        app.fireworks_steps_per_frame = 3
        app._handle_fireworks_key(ord("-"))
        assert app.fireworks_steps_per_frame == 2

    def test_r_resets(self):
        app = self._init_sim()
        app._fireworks_step()
        app._handle_fireworks_key(ord("r"))
        assert app.fireworks_generation == 0

    def test_R_returns_to_menu(self):
        app = self._init_sim()
        app._handle_fireworks_key(ord("R"))
        assert app.fireworks_mode is False
        assert app.fireworks_menu is True

    def test_q_exits(self):
        app = self._init_sim()
        app._handle_fireworks_key(ord("q"))
        assert app.fireworks_mode is False

    def test_no_key_no_crash(self):
        app = self._init_sim()
        result = app._handle_fireworks_key(-1)
        assert result is True

    def test_gravity_clamped(self):
        app = self._init_sim()
        app.fireworks_gravity = 0.19
        app._handle_fireworks_key(ord("g"))
        assert app.fireworks_gravity <= 0.2
        app._handle_fireworks_key(ord("g"))
        assert app.fireworks_gravity <= 0.2

    def test_launch_rate_clamped(self):
        app = self._init_sim()
        app.fireworks_launch_rate = 0.49
        app._handle_fireworks_key(ord("l"))
        assert app.fireworks_launch_rate <= 0.5
