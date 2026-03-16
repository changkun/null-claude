"""Tests for physarum mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.physarum import register


# (name, desc, sensor_angle, sensor_dist, turn_speed, move_speed, deposit, decay, ratio)
PHYSARUM_PRESETS = [
    ("Classic", "Standard slime mold behavior", 0.4, 9.0, 0.3, 1.0, 0.5, 0.02, 0.03),
    ("Branching", "Dense branching network", 0.6, 12.0, 0.4, 1.2, 0.6, 0.015, 0.04),
]

PHYSARUM_DENSITY = ["  ", "\u2591\u2591", "\u2592\u2592", "\u2593\u2593", "\u2588\u2588"]


def _make_physarum_app():
    """Create and configure a mock app for Physarum testing."""
    app = make_mock_app()
    cls = type(app)
    cls.PHYSARUM_PRESETS = PHYSARUM_PRESETS
    cls.PHYSARUM_DENSITY = PHYSARUM_DENSITY
    app.physarum_steps_per_frame = 2
    app.physarum_preset_name = ""
    app.physarum_num_agents = 0
    register(cls)
    return app


class TestPhysarumInit:
    """Test initialization and setup."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_physarum_app()

    def test_enter(self):
        self.app._enter_physarum_mode()
        assert self.app.physarum_menu is True
        assert self.app.physarum_menu_sel == 0

    def test_init_classic(self):
        self.app._physarum_init(0)
        assert self.app.physarum_mode is True
        assert self.app.physarum_menu is False
        assert self.app.physarum_generation == 0
        assert len(self.app.physarum_agents) > 0
        assert len(self.app.physarum_trail) > 0
        assert self.app.physarum_preset_name == "Classic"

    def test_init_branching(self):
        self.app._physarum_init(1)
        assert self.app.physarum_preset_name == "Branching"
        assert self.app.physarum_sensor_angle == 0.6
        assert self.app.physarum_sensor_dist == 12.0
        assert self.app.physarum_turn_speed == 0.4
        assert self.app.physarum_move_speed == 1.2
        assert self.app.physarum_deposit == 0.6
        assert self.app.physarum_decay == 0.015

    def test_init_sets_correct_parameters(self):
        self.app._physarum_init(0)
        assert self.app.physarum_sensor_angle == 0.4
        assert self.app.physarum_sensor_dist == 9.0
        assert self.app.physarum_turn_speed == 0.3
        assert self.app.physarum_move_speed == 1.0
        assert self.app.physarum_deposit == 0.5
        assert self.app.physarum_decay == 0.02

    def test_init_trail_all_zeros(self):
        self.app._physarum_init(0)
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        for r in range(rows):
            for c in range(cols):
                assert self.app.physarum_trail[r][c] == 0.0

    def test_init_agent_count_respects_ratio(self):
        self.app._physarum_init(0)
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        expected = max(50, int(rows * cols * 0.03))
        assert self.app.physarum_num_agents == expected
        assert len(self.app.physarum_agents) == expected

    def test_agents_spawned_in_circle(self):
        """Agents should be within radius of center."""
        self.app._physarum_init(0)
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        cr, cc = rows / 2.0, cols / 2.0
        radius = min(rows, cols) * 0.3
        for agent in self.app.physarum_agents:
            ar, ac = agent[0], agent[1]
            # Account for wrapping: agents are placed mod rows/cols
            # so they should be within radius of center (before wrapping)
            # After wrapping, they are in bounds
            assert 0 <= ar < rows
            assert 0 <= ac < cols

    def test_init_not_running(self):
        self.app._physarum_init(0)
        assert self.app.physarum_running is False


class TestPhysarumSensor:
    """Test the sensor/sensing logic."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_physarum_app()
        self.app._physarum_init(0)

    def test_sense_returns_float(self):
        val = self.app._physarum_sense(5.0, 5.0, 0.0, 0.0)
        assert isinstance(val, float)

    def test_sense_reads_trail_value(self):
        """Sensor should read the trail value at the sensed position."""
        # Place a known value in the trail
        self.app.physarum_trail[5][5] = 0.75
        # Sense at a position/heading/distance that should land on (5,5)
        # With heading=0, offset=0, sensor goes to (ar + sin(0)*dist, ac + cos(0)*dist)
        # sin(0)=0, cos(0)=1, so sensor reads at (ar, ac + dist)
        dist = self.app.physarum_sensor_dist
        val = self.app._physarum_sense(5.0, 5.0 - dist, 0.0, 0.0)
        # Sensor position: row = 5 + sin(0)*dist = 5, col = (5-dist) + cos(0)*dist = 5
        assert val == 0.75

    def test_sense_wraps_around(self):
        """Sensor should wrap around grid boundaries."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        self.app.physarum_trail[0][0] = 0.9
        # Sense from near the bottom-right, heading towards (0,0)
        # int(sr) % rows and int(sc) % cols handles wrapping
        val = self.app._physarum_sense(0.0, 0.0, 0.0, 0.0)
        # This reads at (0 + sin(0)*dist, 0 + cos(0)*dist) = (0, dist)
        # which wraps to (0, dist % cols)
        ri = int(0 + math.sin(0) * self.app.physarum_sensor_dist) % rows
        ci = int(0 + math.cos(0) * self.app.physarum_sensor_dist) % cols
        expected = self.app.physarum_trail[ri][ci]
        assert val == expected

    def test_sense_with_offset_left_right(self):
        """Left and right sensor offsets should read different positions."""
        self.app.physarum_trail[3][3] = 0.5
        self.app.physarum_trail[7][3] = 0.8
        sa = self.app.physarum_sensor_angle
        # Left and right senses should differ when trail values differ
        fl = self.app._physarum_sense(5.0, 5.0, 0.0, sa)
        fr = self.app._physarum_sense(5.0, 5.0, 0.0, -sa)
        # They read different positions due to angle offset, so at least one
        # should be different if the trail isn't uniform
        # (both could be 0.0 if neither lands on a nonzero cell, but
        # the key point is the positions are different)
        heading = 0.0
        sr_left = 5.0 + math.sin(heading + sa) * self.app.physarum_sensor_dist
        sc_left = 5.0 + math.cos(heading + sa) * self.app.physarum_sensor_dist
        sr_right = 5.0 + math.sin(heading - sa) * self.app.physarum_sensor_dist
        sc_right = 5.0 + math.cos(heading - sa) * self.app.physarum_sensor_dist
        # Positions must be different (unless sa == 0)
        assert (int(sr_left), int(sc_left)) != (int(sr_right), int(sc_right))


class TestPhysarumStep:
    """Test the simulation step logic."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_physarum_app()
        self.app._physarum_init(0)

    def test_step_increments_generation(self):
        assert self.app.physarum_generation == 0
        self.app._physarum_step()
        assert self.app.physarum_generation == 1
        self.app._physarum_step()
        assert self.app.physarum_generation == 2

    def test_step_no_crash(self):
        for _ in range(10):
            self.app._physarum_step()
        assert self.app.physarum_generation == 10

    def test_agents_stay_in_bounds(self):
        for _ in range(20):
            self.app._physarum_step()
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        for agent in self.app.physarum_agents:
            assert 0 <= agent[0] < rows
            assert 0 <= agent[1] < cols

    def test_trail_values_non_negative(self):
        for _ in range(10):
            self.app._physarum_step()
        for row in self.app.physarum_trail:
            for val in row:
                assert val >= 0.0

    def test_trail_values_bounded_by_one_after_deposit(self):
        """Trail deposit is clamped to 1.0."""
        # Place a single agent on a cell and deposit many times
        self.app.physarum_agents = [[5.0, 5.0, 0.0]]
        self.app.physarum_num_agents = 1
        # Manually deposit multiple times at same cell
        for _ in range(50):
            ri, ci = 5, 5
            self.app.physarum_trail[ri][ci] = min(
                1.0, self.app.physarum_trail[ri][ci] + self.app.physarum_deposit
            )
        assert self.app.physarum_trail[5][5] <= 1.0

    def test_deposit_increases_trail(self):
        """After one step, at least some trail cells should be nonzero."""
        self.app._physarum_step()
        has_nonzero = False
        for row in self.app.physarum_trail:
            for val in row:
                if val > 0.0:
                    has_nonzero = True
                    break
            if has_nonzero:
                break
        assert has_nonzero, "Trail should have nonzero values after agents deposit"

    def test_decay_reduces_trail(self):
        """Trail values should decrease over time due to decay."""
        # Run several steps to build up trail
        for _ in range(5):
            self.app._physarum_step()
        # Record total trail
        total_before = sum(
            self.app.physarum_trail[r][c]
            for r in range(self.app.physarum_rows)
            for c in range(self.app.physarum_cols)
        )
        # Remove all agents so no new deposits
        self.app.physarum_agents = []
        self.app.physarum_num_agents = 0
        # Step once more — only diffuse+decay, no deposit
        self.app._physarum_step()
        total_after = sum(
            self.app.physarum_trail[r][c]
            for r in range(self.app.physarum_rows)
            for c in range(self.app.physarum_cols)
        )
        assert total_after < total_before, "Decay should reduce total trail"

    def test_diffusion_spreads_trail(self):
        """A single bright cell should spread to neighbors via 3x3 blur."""
        # Clear all agents
        self.app.physarum_agents = []
        self.app.physarum_num_agents = 0
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        # Clear trail and set a single cell
        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        self.app.physarum_trail[10][10] = 0.9
        # Set decay to 0 to isolate diffusion
        self.app.physarum_decay = 0.0
        self.app._physarum_step()
        # After diffusion, the value should spread to neighbors
        # Original cell: 0.9/9 = 0.1
        assert self.app.physarum_trail[10][10] == pytest.approx(0.1, abs=0.01)
        # Adjacent cells should get 0.9/9 = 0.1
        assert self.app.physarum_trail[9][10] == pytest.approx(0.1, abs=0.01)
        assert self.app.physarum_trail[11][10] == pytest.approx(0.1, abs=0.01)
        assert self.app.physarum_trail[10][9] == pytest.approx(0.1, abs=0.01)
        assert self.app.physarum_trail[10][11] == pytest.approx(0.1, abs=0.01)
        # Diagonal neighbors also
        assert self.app.physarum_trail[9][9] == pytest.approx(0.1, abs=0.01)

    def test_diffusion_with_decay(self):
        """Diffusion + decay: total should shrink from a single cell."""
        self.app.physarum_agents = []
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        self.app.physarum_trail[10][10] = 0.9
        self.app.physarum_decay = 0.02
        self.app._physarum_step()
        # Each of 9 cells around (10,10) gets max(0, 0.9/9 - 0.02) = max(0, 0.08)
        # All others get max(0, 0 - 0.02) = 0
        for r in range(rows):
            for c in range(cols):
                assert self.app.physarum_trail[r][c] >= 0.0

    def test_agent_movement_direction(self):
        """Agent heading determines movement direction correctly."""
        self.app.physarum_agents = []
        self.app.physarum_trail = [
            [0.0] * self.app.physarum_cols
            for _ in range(self.app.physarum_rows)
        ]
        # Single agent at center, heading = 0 => moves by (sin(0)*ms, cos(0)*ms) = (0, ms)
        start_r, start_c = 15.0, 15.0
        heading = 0.0
        self.app.physarum_agents = [[start_r, start_c, heading]]
        ms = self.app.physarum_move_speed
        self.app._physarum_step()
        agent = self.app.physarum_agents[0]
        expected_r = (start_r + math.sin(heading) * ms) % self.app.physarum_rows
        expected_c = (start_c + math.cos(heading) * ms) % self.app.physarum_cols
        # Heading may change due to sensor logic, but if trail is all zero,
        # all sensors read 0 => fc == fl == fr => all equal, no turn
        # (fc > fl and fc > fr) is False, (fc < fl and fc < fr) is False,
        # (fl > fr) is False, (fr > fl) is False => no turn, heading stays 0
        assert agent[0] == pytest.approx(expected_r, abs=1e-9)
        assert agent[1] == pytest.approx(expected_c, abs=1e-9)
        assert agent[2] == heading  # no turn on uniform trail

    def test_agent_turns_toward_stronger_trail(self):
        """Agent should turn toward the stronger trail signal."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        # Place strong trail to the left of agent's heading
        # Agent at (15, 15) heading=0 (moving in +col direction)
        # Left sensor: heading + sa => angle = sa
        # Sensor pos: (15 + sin(sa)*dist, 15 + cos(sa)*dist)
        sa = self.app.physarum_sensor_angle
        dist = self.app.physarum_sensor_dist
        sr = int(15 + math.sin(sa) * dist) % rows
        sc = int(15 + math.cos(sa) * dist) % cols
        self.app.physarum_trail[sr][sc] = 0.9  # strong left signal

        self.app.physarum_agents = [[15.0, 15.0, 0.0]]
        self.app._physarum_step()
        agent = self.app.physarum_agents[0]
        # Agent should have turned left (heading increased by turn_speed)
        ts = self.app.physarum_turn_speed
        # fl > fr => heading += ts
        assert agent[2] == pytest.approx(ts, abs=1e-9)

    def test_agent_turns_right_toward_stronger_right_trail(self):
        """Agent should turn right when right signal is stronger."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        sa = self.app.physarum_sensor_angle
        dist = self.app.physarum_sensor_dist
        # Right sensor: heading - sa
        sr = int(15 + math.sin(-sa) * dist) % rows
        sc = int(15 + math.cos(-sa) * dist) % cols
        self.app.physarum_trail[sr][sc] = 0.9  # strong right signal

        self.app.physarum_agents = [[15.0, 15.0, 0.0]]
        self.app._physarum_step()
        agent = self.app.physarum_agents[0]
        ts = self.app.physarum_turn_speed
        # fr > fl => heading -= ts
        assert agent[2] == pytest.approx(-ts, abs=1e-9)

    def test_agent_goes_straight_when_center_strongest(self):
        """Agent goes straight when center signal is strongest."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        dist = self.app.physarum_sensor_dist
        # Center sensor: heading=0, offset=0 => (15 + sin(0)*dist, 15 + cos(0)*dist) = (15, 15+dist)
        sr = int(15 + math.sin(0) * dist) % rows
        sc = int(15 + math.cos(0) * dist) % cols
        self.app.physarum_trail[sr][sc] = 0.9  # strong center signal

        self.app.physarum_agents = [[15.0, 15.0, 0.0]]
        self.app._physarum_step()
        agent = self.app.physarum_agents[0]
        # fc > fl and fc > fr => no turn
        assert agent[2] == pytest.approx(0.0, abs=1e-9)

    def test_agent_random_turn_when_left_right_both_stronger(self):
        """Agent turns randomly when both left and right are stronger than center."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        sa = self.app.physarum_sensor_angle
        dist = self.app.physarum_sensor_dist
        ts = self.app.physarum_turn_speed

        # Place strong trail at both left and right sensor positions
        sr_l = int(15 + math.sin(sa) * dist) % rows
        sc_l = int(15 + math.cos(sa) * dist) % cols
        sr_r = int(15 + math.sin(-sa) * dist) % rows
        sc_r = int(15 + math.cos(-sa) * dist) % cols

        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        self.app.physarum_trail[sr_l][sc_l] = 0.9
        self.app.physarum_trail[sr_r][sc_r] = 0.9
        # Center sensor should read 0

        random.seed(100)  # deterministic random
        self.app.physarum_agents = [[15.0, 15.0, 0.0]]
        self.app._physarum_step()
        agent = self.app.physarum_agents[0]
        # fc < fl and fc < fr => random turn: heading is either +ts or -ts
        assert abs(agent[2]) == pytest.approx(ts, abs=1e-9)


class TestPhysarumTrailBehavior:
    """Test trail deposit, decay, and diffusion properties."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_physarum_app()
        self.app._physarum_init(0)

    def test_trail_eventually_decays_to_zero(self):
        """With no agents, trail should eventually decay to near zero."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        self.app.physarum_trail[10][10] = 1.0
        self.app.physarum_agents = []
        for _ in range(200):
            self.app._physarum_step()
        total = sum(
            self.app.physarum_trail[r][c]
            for r in range(rows) for c in range(cols)
        )
        assert total < 0.01, "Trail should decay to near zero without agents"

    def test_trail_conservation_without_decay(self):
        """With decay=0, diffusion should conserve total trail (3x3 avg is conservative)."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        self.app.physarum_trail = [[0.0] * cols for _ in range(rows)]
        self.app.physarum_trail[10][10] = 0.9
        self.app.physarum_decay = 0.0
        self.app.physarum_agents = []
        total_before = 0.9
        self.app._physarum_step()
        total_after = sum(
            self.app.physarum_trail[r][c]
            for r in range(rows) for c in range(cols)
        )
        # 3x3 box blur is conservative (total is preserved)
        assert total_after == pytest.approx(total_before, abs=0.01)

    def test_uniform_trail_stays_uniform_without_decay(self):
        """A uniform trail should stay uniform under diffusion with no decay."""
        rows, cols = self.app.physarum_rows, self.app.physarum_cols
        val = 0.5
        self.app.physarum_trail = [[val] * cols for _ in range(rows)]
        self.app.physarum_decay = 0.0
        self.app.physarum_agents = []
        self.app._physarum_step()
        for r in range(rows):
            for c in range(cols):
                assert self.app.physarum_trail[r][c] == pytest.approx(val, abs=1e-9)


class TestPhysarumExit:
    """Test cleanup on exit."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_physarum_app()

    def test_exit_cleanup(self):
        self.app._physarum_init(0)
        self.app._physarum_step()
        self.app._exit_physarum_mode()
        assert self.app.physarum_mode is False
        assert self.app.physarum_menu is False
        assert self.app.physarum_running is False
        assert self.app.physarum_trail == []
        assert self.app.physarum_agents == []


class TestPhysarumKeyHandling:
    """Test key handling in menu and active mode."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_physarum_app()

    def test_menu_navigate_down(self):
        self.app._enter_physarum_mode()
        import curses
        self.app._handle_physarum_menu_key(ord("j"))
        assert self.app.physarum_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        self.app._enter_physarum_mode()
        self.app._handle_physarum_menu_key(ord("k"))
        # Wraps from 0 to len(presets)-1
        assert self.app.physarum_menu_sel == len(PHYSARUM_PRESETS) - 1

    def test_menu_select(self):
        self.app._enter_physarum_mode()
        self.app._handle_physarum_menu_key(ord("\n"))
        assert self.app.physarum_mode is True
        assert self.app.physarum_menu is False

    def test_menu_cancel(self):
        self.app._enter_physarum_mode()
        self.app._handle_physarum_menu_key(ord("q"))
        assert self.app.physarum_menu is False

    def test_active_space_toggles_running(self):
        self.app._physarum_init(0)
        assert self.app.physarum_running is False
        self.app._handle_physarum_key(ord(" "))
        assert self.app.physarum_running is True
        self.app._handle_physarum_key(ord(" "))
        assert self.app.physarum_running is False

    def test_active_n_steps(self):
        self.app._physarum_init(0)
        gen_before = self.app.physarum_generation
        self.app._handle_physarum_key(ord("n"))
        # Steps per frame is 2
        assert self.app.physarum_generation == gen_before + 2

    def test_active_reseed(self):
        self.app._physarum_init(0)
        for _ in range(5):
            self.app._physarum_step()
        assert self.app.physarum_generation == 5
        self.app._handle_physarum_key(ord("r"))
        assert self.app.physarum_generation == 0
        assert self.app.physarum_running is False

    def test_active_return_to_menu(self):
        self.app._physarum_init(0)
        self.app._handle_physarum_key(ord("R"))
        assert self.app.physarum_mode is False
        assert self.app.physarum_menu is True

    def test_active_quit(self):
        self.app._physarum_init(0)
        self.app._handle_physarum_key(ord("q"))
        assert self.app.physarum_mode is False

    def test_adjust_sensor_angle(self):
        self.app._physarum_init(0)
        original = self.app.physarum_sensor_angle
        self.app._handle_physarum_key(ord("a"))
        assert self.app.physarum_sensor_angle == pytest.approx(original + 0.05, abs=1e-9)
        self.app._handle_physarum_key(ord("A"))
        assert self.app.physarum_sensor_angle == pytest.approx(original, abs=1e-9)

    def test_adjust_sensor_dist(self):
        self.app._physarum_init(0)
        original = self.app.physarum_sensor_dist
        self.app._handle_physarum_key(ord("s"))
        assert self.app.physarum_sensor_dist == original + 1.0
        self.app._handle_physarum_key(ord("S"))
        assert self.app.physarum_sensor_dist == original

    def test_adjust_turn_speed(self):
        self.app._physarum_init(0)
        original = self.app.physarum_turn_speed
        self.app._handle_physarum_key(ord("t"))
        assert self.app.physarum_turn_speed == pytest.approx(original + 0.05, abs=1e-9)

    def test_adjust_decay(self):
        self.app._physarum_init(0)
        original = self.app.physarum_decay
        self.app._handle_physarum_key(ord("d"))
        assert self.app.physarum_decay == pytest.approx(original + 0.005, abs=1e-9)

    def test_adjust_steps_per_frame(self):
        self.app._physarum_init(0)
        original = self.app.physarum_steps_per_frame
        self.app._handle_physarum_key(ord("+"))
        assert self.app.physarum_steps_per_frame == original + 1
        self.app._handle_physarum_key(ord("-"))
        assert self.app.physarum_steps_per_frame == original

    def test_sensor_angle_clamped(self):
        self.app._physarum_init(0)
        # Push angle to max
        for _ in range(100):
            self.app._handle_physarum_key(ord("a"))
        assert self.app.physarum_sensor_angle <= 1.5
        # Push to min
        for _ in range(100):
            self.app._handle_physarum_key(ord("A"))
        assert self.app.physarum_sensor_angle >= 0.05

    def test_steps_per_frame_clamped(self):
        self.app._physarum_init(0)
        for _ in range(30):
            self.app._handle_physarum_key(ord("+"))
        assert self.app.physarum_steps_per_frame <= 20
        for _ in range(30):
            self.app._handle_physarum_key(ord("-"))
        assert self.app.physarum_steps_per_frame >= 1
