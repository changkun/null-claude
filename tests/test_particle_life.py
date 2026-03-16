"""Tests for particle_life mode."""
import random
import math
import pytest
from tests.conftest import make_mock_app
from life.modes.particle_life import register


# (name, desc, num_types, density, max_radius, friction, force_scale, seed)
PLIFE_PRESETS = [
    ("Primordial Soup", "Random rules", 6, 0.06, 15.0, 0.5, 0.05, None),
    ("Symbiosis", "Orbiting species", 4, 0.05, 18.0, 0.4, 0.04, 42),
    ("Clusters", "Self-organizing clumps", 3, 0.08, 12.0, 0.6, 0.06, 123),
]

PLIFE_CHARS = ["\u25cf", "\u25c6", "\u25a0", "\u25b2", "\u2605", "\u25c9", "\u2666", "\u2726"]
PLIFE_COLORS = [1, 2, 3, 4, 5, 6, 7, 1]


def _make_plife_app():
    """Create a mock app wired for particle life testing."""
    app = make_mock_app()
    cls = type(app)
    cls.PLIFE_PRESETS = PLIFE_PRESETS
    cls.PLIFE_CHARS = PLIFE_CHARS
    cls.PLIFE_COLORS = PLIFE_COLORS
    app.plife_steps_per_frame = 1
    app.plife_preset_name = ""
    app.plife_num_particles = 0
    app.plife_num_types = 6
    app.plife_rules = []
    app.plife_particles = []
    app.plife_max_radius = 15.0
    app.plife_friction = 0.5
    app.plife_force_scale = 0.05
    register(cls)
    return app


class TestParticleLifeBasics:
    """Basic lifecycle tests: enter, init, exit."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_plife_app()

    def test_enter(self):
        self.app._enter_plife_mode()
        assert self.app.plife_menu is True
        assert self.app.plife_menu_sel == 0

    def test_init(self):
        self.app._plife_init(0)
        assert self.app.plife_mode is True
        assert self.app.plife_menu is False
        assert self.app.plife_generation == 0
        assert len(self.app.plife_particles) > 0
        assert len(self.app.plife_rules) > 0
        assert self.app.plife_preset_name == "Primordial Soup"

    def test_init_with_seed(self):
        """Preset with seed=42 should produce deterministic results."""
        self.app._plife_init(1)
        particles_1 = [p[:] for p in self.app.plife_particles]
        self.app._plife_init(1)
        particles_2 = [p[:] for p in self.app.plife_particles]
        assert len(particles_1) == len(particles_2)
        for p1, p2 in zip(particles_1, particles_2):
            assert p1 == p2

    def test_exit_cleanup(self):
        self.app._plife_init(0)
        self.app._plife_step()
        self.app._exit_plife_mode()
        assert self.app.plife_mode is False
        assert self.app.plife_menu is False
        assert self.app.plife_running is False
        assert self.app.plife_particles == []
        assert self.app.plife_rules == []


class TestRulesMatrix:
    """Validate the attraction/repulsion rule matrix."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_plife_app()

    def test_rules_dimensions(self):
        """Rules matrix must be num_types x num_types."""
        self.app._plife_init(0)
        nt = self.app.plife_num_types
        rules = self.app.plife_rules
        assert len(rules) == nt
        for row in rules:
            assert len(row) == nt

    def test_rules_range(self):
        """All attraction values must be in [-1, 1]."""
        self.app._plife_init(0)
        for row in self.app.plife_rules:
            for val in row:
                assert -1.0 <= val <= 1.0

    def test_rules_deterministic_with_seed(self):
        """Same seed should produce identical rule matrices."""
        self.app._plife_init(1)  # seed=42
        rules_a = [row[:] for row in self.app.plife_rules]
        self.app._plife_init(1)
        rules_b = [row[:] for row in self.app.plife_rules]
        assert rules_a == rules_b

    def test_rules_vary_between_presets(self):
        """Different presets (with different seeds) should give different rules."""
        self.app._plife_init(1)  # seed=42
        rules_a = [row[:] for row in self.app.plife_rules]
        self.app._plife_init(2)  # seed=123
        rules_b = [row[:] for row in self.app.plife_rules]
        assert rules_a != rules_b


class TestForceProfile:
    """Test the force calculation logic from _plife_step directly."""

    def _compute_force(self, rel_dist, attraction):
        """Replicate the force profile from _plife_step."""
        if rel_dist < 0.3:
            return rel_dist / 0.3 - 1.0
        else:
            force = attraction * (1.0 - abs(2.0 * rel_dist - 1.3) / 0.7)
            return max(-1.0, min(1.0, force))

    def test_short_range_repulsion_at_zero(self):
        """At rel_dist=0, force should be maximally repulsive (-1)."""
        force = self._compute_force(0.0, 1.0)
        assert force == pytest.approx(-1.0)

    def test_short_range_repulsion_at_boundary(self):
        """At rel_dist=0.3, repulsion should be exactly 0 (transition)."""
        force = self._compute_force(0.3, 1.0)
        assert force == pytest.approx(0.0)

    def test_short_range_repulsion_midway(self):
        """At rel_dist=0.15, repulsion should be -0.5."""
        force = self._compute_force(0.15, 1.0)
        assert force == pytest.approx(-0.5)

    def test_short_range_independent_of_attraction(self):
        """Short range repulsion ignores the attraction rule."""
        f_attract = self._compute_force(0.1, 1.0)
        f_repel = self._compute_force(0.1, -1.0)
        assert f_attract == f_repel

    def test_attraction_peak(self):
        """Peak attraction should occur at rel_dist=0.65 (where 2*0.65-1.3=0)."""
        force = self._compute_force(0.65, 1.0)
        assert force == pytest.approx(1.0)

    def test_repulsion_peak(self):
        """With attraction=-1, peak repulsion at rel_dist=0.65."""
        force = self._compute_force(0.65, -1.0)
        assert force == pytest.approx(-1.0)

    def test_force_at_max_radius(self):
        """At rel_dist=1.0, force should be 0 (fades out)."""
        force = self._compute_force(1.0, 1.0)
        assert force == pytest.approx(0.0)

    def test_force_at_max_radius_repulsive(self):
        """At rel_dist=1.0, force should be 0 regardless of attraction."""
        force = self._compute_force(1.0, -1.0)
        assert force == pytest.approx(0.0)

    def test_force_clamped_positive(self):
        """Force is clamped to [-1, 1]."""
        force = self._compute_force(0.65, 5.0)
        assert force <= 1.0

    def test_force_clamped_negative(self):
        force = self._compute_force(0.65, -5.0)
        assert force >= -1.0


class TestToroidalDistance:
    """Test that toroidal wrapping works correctly in _plife_step."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_plife_app()

    def test_particles_wrap_toroidally(self):
        """A particle with positive velocity near the edge should wrap."""
        self.app._plife_init(1)
        rows, cols = self.app.plife_rows, self.app.plife_cols
        # Place a single particle near the top-right edge with velocity pushing it out
        self.app.plife_particles = [
            [0.5, cols - 0.5, -1.5, 1.5, 0.0],  # near (0, cols), moving up-right
        ]
        self.app.plife_num_particles = 1
        self.app._plife_step()
        p = self.app.plife_particles[0]
        assert 0 <= p[0] < rows, f"Row {p[0]} out of bounds [0, {rows})"
        assert 0 <= p[1] < cols, f"Col {p[1]} out of bounds [0, {cols})"

    def test_two_particles_across_boundary_interact(self):
        """Two particles across the toroidal boundary should interact."""
        self.app._plife_init(1)
        rows, cols = self.app.plife_rows, self.app.plife_cols
        # Place particles at row 1 and row (rows-1), which are distance 2 apart toroidally
        # With max_r=18 they should interact
        self.app.plife_particles = [
            [1.0, 10.0, 0.0, 0.0, 0.0],
            [rows - 1.0, 10.0, 0.0, 0.0, 0.0],
        ]
        self.app.plife_num_particles = 2
        self.app._plife_step()
        # After one step, particles should have non-zero velocity (they interacted)
        p0, p1 = self.app.plife_particles
        has_velocity = (abs(p0[2]) > 1e-10 or abs(p0[3]) > 1e-10 or
                        abs(p1[2]) > 1e-10 or abs(p1[3]) > 1e-10)
        assert has_velocity, "Particles across toroidal boundary should interact"


class TestSimulationStep:
    """Integration tests for _plife_step."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_plife_app()

    def test_step_increments_generation(self):
        self.app._plife_init(1)
        self.app._plife_step()
        assert self.app.plife_generation == 1
        self.app._plife_step()
        assert self.app.plife_generation == 2

    def test_step_preserves_particle_count(self):
        self.app._plife_init(1)
        n_before = len(self.app.plife_particles)
        for _ in range(10):
            self.app._plife_step()
        assert len(self.app.plife_particles) == n_before

    def test_particles_stay_in_bounds(self):
        self.app._plife_init(1)
        for _ in range(20):
            self.app._plife_step()
        rows, cols = self.app.plife_rows, self.app.plife_cols
        for p in self.app.plife_particles:
            assert 0 <= p[0] < rows
            assert 0 <= p[1] < cols

    def test_velocity_clamped(self):
        self.app._plife_init(1)
        for _ in range(20):
            self.app._plife_step()
        for p in self.app.plife_particles:
            spd = math.sqrt(p[2] ** 2 + p[3] ** 2)
            assert spd <= 2.0 + 1e-9, f"Speed {spd} exceeds max 2.0"

    def test_particle_types_preserved(self):
        """Particle types should not change during simulation."""
        self.app._plife_init(1)
        types_before = [p[4] for p in self.app.plife_particles]
        for _ in range(10):
            self.app._plife_step()
        types_after = [p[4] for p in self.app.plife_particles]
        assert types_before == types_after

    def test_friction_damps_velocity(self):
        """With high friction, a moving particle should slow down when alone."""
        self.app._plife_init(1)
        # Single particle with initial velocity, no neighbors to exert force
        self.app.plife_particles = [
            [10.0, 10.0, 1.0, 1.0, 0.0],
        ]
        self.app.plife_num_particles = 1
        self.app.plife_friction = 0.5
        self.app._plife_step()
        p = self.app.plife_particles[0]
        # velocity should be (1.0 + 0) * (1 - 0.5) = 0.5 each component
        assert p[2] == pytest.approx(0.5)
        assert p[3] == pytest.approx(0.5)

    def test_friction_exponential_decay(self):
        """Repeated steps with friction should exponentially decay velocity."""
        self.app._plife_init(1)
        self.app.plife_particles = [
            [10.0, 10.0, 1.0, 0.0, 0.0],
        ]
        self.app.plife_num_particles = 1
        self.app.plife_friction = 0.5
        for _ in range(5):
            self.app._plife_step()
        p = self.app.plife_particles[0]
        # After 5 steps: vr = 1.0 * (0.5)^5 = 0.03125
        assert p[2] == pytest.approx(0.03125)

    def test_close_particles_repel(self):
        """Two very close particles of any type should repel each other."""
        self.app._plife_init(1)
        rows, cols = self.app.plife_rows, self.app.plife_cols
        # Place two particles very close together (within 0.3 * max_r)
        center_r, center_c = rows / 2.0, cols / 2.0
        self.app.plife_particles = [
            [center_r, center_c, 0.0, 0.0, 0.0],
            [center_r + 0.5, center_c, 0.0, 0.0, 0.0],  # very close
        ]
        self.app.plife_num_particles = 2
        self.app.plife_friction = 0.0  # no friction, so force effect is pure
        self.app._plife_step()
        p0, p1 = self.app.plife_particles
        # Particle 0 should be pushed up (negative row direction)
        # Particle 1 should be pushed down (positive row direction)
        # The short-range repulsion pushes them apart
        assert p0[2] < 0, "First particle should be repelled upward"
        assert p1[2] > 0, "Second particle should be repelled downward"

    def test_distant_particles_no_interaction(self):
        """Particles farther than max_r should not interact."""
        self.app._plife_init(1)
        rows, cols = self.app.plife_rows, self.app.plife_cols
        # Use a small max_r so both direct and toroidal distances exceed it
        self.app.plife_max_radius = 5.0
        max_r = self.app.plife_max_radius
        # Direct distance = separation; toroidal distance = rows - separation.
        # Both must exceed max_r: max_r < separation < rows - max_r
        separation = max_r + 2.0  # 7.0
        assert rows - separation > max_r, "Grid too small for this test"
        self.app.plife_particles = [
            [rows / 2.0 - separation / 2.0, 5.0, 0.0, 0.0, 0.0],
            [rows / 2.0 + separation / 2.0, 5.0, 0.0, 0.0, 0.0],
        ]
        self.app.plife_num_particles = 2
        self.app.plife_friction = 0.0
        self.app._plife_step()
        p0, p1 = self.app.plife_particles
        assert p0[2] == pytest.approx(0.0)
        assert p0[3] == pytest.approx(0.0)
        assert p1[2] == pytest.approx(0.0)
        assert p1[3] == pytest.approx(0.0)


class TestNewtonThird:
    """Verify approximate Newton's 3rd law (equal and opposite forces)."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_plife_app()

    def test_equal_opposite_forces_same_type(self):
        """Two same-type particles should experience equal and opposite forces."""
        self.app._plife_init(1)
        rows, cols = self.app.plife_rows, self.app.plife_cols
        center_r, center_c = rows / 2.0, cols / 2.0
        sep = 5.0  # within max_r
        self.app.plife_particles = [
            [center_r, center_c - sep / 2, 0.0, 0.0, 0.0],
            [center_r, center_c + sep / 2, 0.0, 0.0, 0.0],
        ]
        self.app.plife_num_particles = 2
        self.app.plife_friction = 0.0
        self.app._plife_step()
        p0, p1 = self.app.plife_particles
        # Forces should be equal and opposite
        assert p0[2] == pytest.approx(-p1[2], abs=1e-10)
        assert p0[3] == pytest.approx(-p1[3], abs=1e-10)


class TestKeyHandlers:
    """Test keyboard input handling."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_plife_app()
        self.app._plife_init(1)

    def test_space_toggles_running(self):
        assert self.app.plife_running is False
        self.app._handle_plife_key(ord(" "))
        assert self.app.plife_running is True
        self.app._handle_plife_key(ord(" "))
        assert self.app.plife_running is False

    def test_friction_increase(self):
        orig = self.app.plife_friction
        self.app._handle_plife_key(ord("f"))
        assert self.app.plife_friction == pytest.approx(orig + 0.05)

    def test_friction_decrease(self):
        orig = self.app.plife_friction
        self.app._handle_plife_key(ord("F"))
        assert self.app.plife_friction == pytest.approx(orig - 0.05)

    def test_friction_clamped_low(self):
        self.app.plife_friction = 0.05
        self.app._handle_plife_key(ord("F"))
        assert self.app.plife_friction >= 0.05

    def test_friction_clamped_high(self):
        self.app.plife_friction = 0.95
        self.app._handle_plife_key(ord("f"))
        assert self.app.plife_friction <= 0.95

    def test_radius_increase(self):
        orig = self.app.plife_max_radius
        self.app._handle_plife_key(ord("d"))
        assert self.app.plife_max_radius == pytest.approx(orig + 1.0)

    def test_radius_decrease(self):
        orig = self.app.plife_max_radius
        self.app._handle_plife_key(ord("D"))
        assert self.app.plife_max_radius == pytest.approx(orig - 1.0)

    def test_force_scale_increase(self):
        orig = self.app.plife_force_scale
        self.app._handle_plife_key(ord("g"))
        assert self.app.plife_force_scale == pytest.approx(orig + 0.01)

    def test_steps_per_frame_increase(self):
        assert self.app.plife_steps_per_frame == 1
        self.app._handle_plife_key(ord("+"))
        assert self.app.plife_steps_per_frame == 2

    def test_steps_per_frame_decrease_clamped(self):
        assert self.app.plife_steps_per_frame == 1
        self.app._handle_plife_key(ord("-"))
        assert self.app.plife_steps_per_frame == 1  # clamped at 1

    def test_quit_exits(self):
        self.app._handle_plife_key(ord("q"))
        assert self.app.plife_mode is False

    def test_randomize_rules(self):
        old_rules = [row[:] for row in self.app.plife_rules]
        self.app._handle_plife_key(ord("x"))
        new_rules = self.app.plife_rules
        # Extremely unlikely to be identical after re-randomization
        assert new_rules != old_rules

    def test_menu_navigation(self):
        self.app.plife_menu = True
        self.app.plife_menu_sel = 0
        self.app._handle_plife_menu_key(ord("j"))
        assert self.app.plife_menu_sel == 1
        self.app._handle_plife_menu_key(ord("k"))
        assert self.app.plife_menu_sel == 0

    def test_menu_wrap_around(self):
        self.app.plife_menu = True
        self.app.plife_menu_sel = 0
        self.app._handle_plife_menu_key(ord("k"))
        assert self.app.plife_menu_sel == len(PLIFE_PRESETS) - 1

    def test_menu_select(self):
        self.app.plife_menu = True
        self.app.plife_menu_sel = 2
        self.app._handle_plife_menu_key(ord("\n"))
        assert self.app.plife_mode is True
        assert self.app.plife_preset_name == "Clusters"

    def test_menu_cancel(self):
        self.app.plife_menu = True
        self.app._handle_plife_menu_key(ord("q"))
        assert self.app.plife_menu is False

    def test_n_key_steps(self):
        gen_before = self.app.plife_generation
        self.app._handle_plife_key(ord("n"))
        assert self.app.plife_generation == gen_before + 1

    def test_return_to_menu(self):
        self.app._handle_plife_key(ord("R"))
        assert self.app.plife_mode is False
        assert self.app.plife_menu is True


class TestModuleOrganization:
    """Verify that N-Body constants are NOT in particle_life module."""

    def test_no_nbody_constants_in_particle_life(self):
        import life.modes.particle_life as plmod
        assert not hasattr(plmod, "NBODY_CHARS")
        assert not hasattr(plmod, "NBODY_COLORS")
        assert not hasattr(plmod, "NBODY_PRESETS")

    def test_nbody_constants_in_nbody(self):
        import life.modes.nbody as nbmod
        assert hasattr(nbmod, "NBODY_CHARS")
        assert hasattr(nbmod, "NBODY_COLORS")
        assert hasattr(nbmod, "NBODY_PRESETS")
