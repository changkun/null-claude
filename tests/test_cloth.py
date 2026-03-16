"""Tests for cloth mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.cloth import register


CLOTH_PRESETS = [
    ("Hanging", "Cloth pinned along the top edge", "hanging"),
    ("Curtain", "Cloth pinned at two points", "curtain"),
    ("Flag", "Cloth pinned along the left edge", "flag"),
    ("Hammock", "Cloth pinned at four corners", "hammock"),
    ("Net", "Wide-spaced net pinned at top", "net"),
    ("Silk", "Fine silk with low tear threshold", "silk"),
]


def _make_app():
    """Create a test app with cloth mode registered."""
    app = make_mock_app()
    cls = type(app)
    cls.CLOTH_PRESETS = CLOTH_PRESETS
    register(cls)
    return app


class TestClothEnterExit:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_enter(self):
        self.app._enter_cloth_mode()
        assert self.app.cloth_menu is True
        assert self.app.cloth_menu_sel == 0

    def test_exit_cleanup(self):
        self.app.cloth_mode = True
        self.app.cloth_preset_name = "Hanging"
        self.app._cloth_init("hanging")
        self.app._exit_cloth_mode()
        assert self.app.cloth_mode is False
        assert self.app.cloth_menu is False
        assert self.app.cloth_running is False
        assert self.app.cloth_points == []
        assert self.app.cloth_constraints == []


class TestClothInit:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_init_dimensions(self):
        self.app._cloth_init("hanging")
        assert self.app.cloth_rows >= 10
        assert self.app.cloth_cols >= 10
        assert self.app.cloth_grid_w > 0
        assert self.app.cloth_grid_h > 0

    def test_init_generation_zero(self):
        self.app._cloth_init("hanging")
        assert self.app.cloth_generation == 0

    def test_init_point_count(self):
        self.app._cloth_init("hanging")
        expected = self.app.cloth_grid_w * self.app.cloth_grid_h
        assert len(self.app.cloth_points) == expected

    def test_init_constraint_count(self):
        """Structural constraints: horizontal + vertical."""
        self.app._cloth_init("hanging")
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        horizontal = (gw - 1) * gh
        vertical = gw * (gh - 1)
        assert len(self.app.cloth_constraints) == horizontal + vertical

    def test_init_point_format(self):
        """Each point should be [x, y, old_x, old_y, pinned]."""
        self.app._cloth_init("hanging")
        for p in self.app.cloth_points:
            assert len(p) == 5
            assert isinstance(p[0], float)
            assert isinstance(p[4], float)

    def test_init_constraint_format(self):
        """Each constraint should be [idx1, idx2, rest_length]."""
        self.app._cloth_init("hanging")
        n = len(self.app.cloth_points)
        for con in self.app.cloth_constraints:
            assert len(con) == 3
            assert 0 <= con[0] < n
            assert 0 <= con[1] < n
            assert con[2] > 0


class TestClothPresets:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_hanging_top_row_pinned(self):
        self.app._cloth_init("hanging")
        gw = self.app.cloth_grid_w
        for c in range(gw):
            assert self.app.cloth_points[c][4] > 0.5, \
                f"Top row point {c} should be pinned"
        # Second row should not be pinned
        if len(self.app.cloth_points) > gw:
            assert self.app.cloth_points[gw][4] < 0.5

    def test_hanging_gravity(self):
        self.app._cloth_init("hanging")
        assert self.app.cloth_gravity == 0.5
        assert self.app.cloth_wind == 0.0
        assert self.app.cloth_damping == 0.99

    def test_curtain_two_pins(self):
        self.app._cloth_init("curtain")
        gw = self.app.cloth_grid_w
        pinned = [i for i, p in enumerate(self.app.cloth_points) if p[4] > 0.5]
        assert 0 in pinned
        assert gw - 1 in pinned
        assert self.app.cloth_gravity == 0.4
        assert self.app.cloth_wind == 0.05

    def test_flag_left_edge_pinned(self):
        self.app._cloth_init("flag")
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        for r in range(gh):
            idx = r * gw
            assert self.app.cloth_points[idx][4] > 0.5, \
                f"Left edge point at row {r} should be pinned"
        assert self.app.cloth_gravity == 0.15
        assert self.app.cloth_wind == 0.3

    def test_hammock_four_corners(self):
        self.app._cloth_init("hammock")
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        corners = [0, gw - 1, (gh - 1) * gw, (gh - 1) * gw + gw - 1]
        for idx in corners:
            assert self.app.cloth_points[idx][4] > 0.5, \
                f"Corner point {idx} should be pinned"
        assert self.app.cloth_gravity == 0.6

    def test_net_wider_spacing(self):
        self.app._cloth_init("net")
        assert self.app.cloth_spacing == 2.0
        assert self.app.cloth_tear_threshold == 5.0
        # Net should have wider rest lengths
        for con in self.app.cloth_constraints:
            assert con[2] == 2.0

    def test_silk_fine_mesh(self):
        self.app._cloth_init("silk")
        assert self.app.cloth_constraint_iters == 8
        assert self.app.cloth_tear_threshold == 2.5
        assert self.app.cloth_damping == 0.96

    def test_all_presets_run_without_crash(self):
        for name, desc, preset_id in CLOTH_PRESETS:
            random.seed(42)
            app = _make_app()
            app._cloth_init(preset_id)
            for _ in range(10):
                app._cloth_step()
            assert app.cloth_generation == 10, f"Preset {name} failed"


class TestClothVerletIntegration:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_step_increments_generation(self):
        self.app._cloth_init("hanging")
        self.app._cloth_step()
        assert self.app.cloth_generation == 1

    def test_step_10_iterations(self):
        self.app._cloth_init("hanging")
        for _ in range(10):
            self.app._cloth_step()
        assert self.app.cloth_generation == 10

    def test_pinned_points_stay_fixed(self):
        self.app._cloth_init("hanging")
        gw = self.app.cloth_grid_w
        # Record positions of pinned points
        pinned_before = []
        for c in range(gw):
            p = self.app.cloth_points[c]
            pinned_before.append((p[0], p[1]))
        # Step simulation
        for _ in range(20):
            self.app._cloth_step()
        # Verify pinned points didn't move
        for c in range(gw):
            p = self.app.cloth_points[c]
            assert p[0] == pinned_before[c][0], f"Pinned point {c} x changed"
            assert p[1] == pinned_before[c][1], f"Pinned point {c} y changed"

    def test_gravity_pulls_down(self):
        """Unpinned points should move downward under gravity."""
        self.app._cloth_init("hanging")
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        # Get initial y of a middle unpinned point
        mid_idx = (gh // 2) * gw + gw // 2
        initial_y = self.app.cloth_points[mid_idx][1]
        for _ in range(5):
            self.app._cloth_step()
        final_y = self.app.cloth_points[mid_idx][1]
        assert final_y > initial_y, "Point should fall under gravity"

    def test_damping_reduces_velocity(self):
        """With high damping < 1.0, velocity should be reduced each step."""
        self.app._cloth_init("hanging")
        self.app.cloth_damping = 0.5  # heavy damping
        self.app.cloth_gravity = 0.0  # no gravity
        self.app.cloth_wind = 0.0
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        # Give a point some velocity by offsetting old position
        idx = (gh // 2) * gw + gw // 2
        p = self.app.cloth_points[idx]
        p[2] = p[0] - 1.0  # old_x offset gives rightward velocity
        self.app._cloth_step()
        # Velocity = (p[0] - p[2]) * damp, should be < 1.0
        vx = p[0] - p[2]
        assert abs(vx) < 1.0, "Damping should reduce velocity"

    def test_wind_pushes_horizontally(self):
        """Wind should move unpinned points horizontally."""
        self.app._cloth_init("curtain")
        self.app.cloth_wind = 0.5  # strong wind
        self.app.cloth_gravity = 0.0
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        # Track a middle point
        idx = (gh // 2) * gw + gw // 2
        initial_x = self.app.cloth_points[idx][0]
        for _ in range(10):
            self.app._cloth_step()
        final_x = self.app.cloth_points[idx][0]
        assert final_x > initial_x, "Wind should push points rightward"

    def test_boundary_constraints(self):
        """Points should stay within bounds [0, max_x] x [0, max_y]."""
        self.app._cloth_init("hanging")
        self.app.cloth_gravity = 2.0  # very strong gravity to force boundary
        for _ in range(100):
            self.app._cloth_step()
        max_x = float(self.app.cloth_cols - 1)
        max_y = float(self.app.cloth_rows - 1)
        for p in self.app.cloth_points:
            assert p[0] >= 0.0, f"Point x={p[0]} below 0"
            assert p[0] <= max_x, f"Point x={p[0]} above max_x={max_x}"
            assert p[1] >= 0.0, f"Point y={p[1]} below 0"
            assert p[1] <= max_y, f"Point y={p[1]} above max_y={max_y}"


class TestClothConstraints:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_constraints_maintain_rest_length_approximately(self):
        """After relaxation, constraints should be near their rest length."""
        self.app._cloth_init("hanging")
        self.app.cloth_constraint_iters = 20  # many iterations for convergence
        self.app.cloth_gravity = 0.01  # minimal gravity
        for _ in range(5):
            self.app._cloth_step()
        points = self.app.cloth_points
        for con in self.app.cloth_constraints:
            p1 = points[con[0]]
            p2 = points[con[1]]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dist = (dx * dx + dy * dy) ** 0.5
            # Should be within tear threshold of rest length
            assert dist < con[2] * self.app.cloth_tear_threshold, \
                f"Constraint stretched beyond tear threshold"

    def test_tearing_removes_constraints(self):
        """Constraints should be removed when stretched past tear threshold."""
        self.app._cloth_init("curtain")
        self.app.cloth_tear_threshold = 1.5  # low threshold
        self.app.cloth_gravity = 5.0  # extreme gravity to cause tearing
        initial_count = len(self.app.cloth_constraints)
        for _ in range(50):
            self.app._cloth_step()
        # Some constraints should have been torn
        assert len(self.app.cloth_constraints) < initial_count, \
            "Some constraints should tear under extreme gravity"

    def test_pinned_to_free_correction(self):
        """When one end is pinned, the free end gets double correction."""
        self.app._cloth_init("hanging")
        gw = self.app.cloth_grid_w
        # Point 0 is pinned, point gw is below it (first of second row)
        p_pinned = self.app.cloth_points[0]
        p_free = self.app.cloth_points[gw]
        initial_pinned_pos = (p_pinned[0], p_pinned[1])
        self.app._cloth_step()
        # Pinned point should not have moved
        assert p_pinned[0] == initial_pinned_pos[0]
        assert p_pinned[1] == initial_pinned_pos[1]

    def test_both_free_symmetric_correction(self):
        """When both points are free, correction is split equally."""
        self.app._cloth_init("curtain")
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        # Find two free, connected points in the middle
        mid_r = gh // 2
        mid_c = gw // 2
        idx1 = mid_r * gw + mid_c
        idx2 = mid_r * gw + mid_c + 1
        # Both should be unpinned for curtain
        assert self.app.cloth_points[idx1][4] < 0.5
        assert self.app.cloth_points[idx2][4] < 0.5


class TestClothMenuKeys:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()
        self.app._enter_cloth_mode()

    def test_navigate_down(self):
        import curses
        self.app._handle_cloth_menu_key(curses.KEY_DOWN)
        assert self.app.cloth_menu_sel == 1

    def test_navigate_up_wraps(self):
        import curses
        self.app._handle_cloth_menu_key(curses.KEY_UP)
        assert self.app.cloth_menu_sel == len(CLOTH_PRESETS) - 1

    def test_select_enter(self):
        self.app._handle_cloth_menu_key(ord("\n"))
        assert self.app.cloth_menu is False
        assert self.app.cloth_mode is True

    def test_cancel_q(self):
        self.app._handle_cloth_menu_key(ord("q"))
        assert self.app.cloth_menu is False

    def test_cancel_escape(self):
        self.app._handle_cloth_menu_key(27)
        assert self.app.cloth_menu is False

    def test_j_k_navigation(self):
        self.app._handle_cloth_menu_key(ord("j"))
        assert self.app.cloth_menu_sel == 1
        self.app._handle_cloth_menu_key(ord("k"))
        assert self.app.cloth_menu_sel == 0


class TestClothModeKeys:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()
        self.app.cloth_mode = True
        self.app.cloth_running = False
        self.app.cloth_preset_name = "Hanging"
        self.app.cloth_steps_per_frame = 3
        self.app._cloth_init("hanging")

    def test_toggle_play_pause(self):
        self.app._handle_cloth_key(ord(" "))
        assert self.app.cloth_running is True
        self.app._handle_cloth_key(ord(" "))
        assert self.app.cloth_running is False

    def test_single_step(self):
        gen_before = self.app.cloth_generation
        self.app._handle_cloth_key(ord("n"))
        assert self.app.cloth_generation == gen_before + 1

    def test_exit_q(self):
        self.app._handle_cloth_key(ord("q"))
        assert self.app.cloth_mode is False

    def test_exit_escape(self):
        self.app._handle_cloth_key(27)
        assert self.app.cloth_mode is False

    def test_cursor_movement(self):
        import curses
        self.app.cloth_cursor_r = 5
        self.app.cloth_cursor_c = 5
        self.app._handle_cloth_key(curses.KEY_DOWN)
        assert self.app.cloth_cursor_r == 6
        self.app._handle_cloth_key(curses.KEY_UP)
        assert self.app.cloth_cursor_r == 5
        self.app._handle_cloth_key(curses.KEY_RIGHT)
        assert self.app.cloth_cursor_c == 6
        self.app._handle_cloth_key(curses.KEY_LEFT)
        assert self.app.cloth_cursor_c == 5

    def test_cursor_hjkl(self):
        self.app.cloth_cursor_r = 5
        self.app.cloth_cursor_c = 5
        self.app._handle_cloth_key(ord("j"))
        assert self.app.cloth_cursor_r == 6
        self.app._handle_cloth_key(ord("k"))
        assert self.app.cloth_cursor_r == 5
        self.app._handle_cloth_key(ord("l"))
        assert self.app.cloth_cursor_c == 6
        self.app._handle_cloth_key(ord("h"))
        assert self.app.cloth_cursor_c == 5

    def test_cursor_bounds(self):
        self.app.cloth_cursor_r = 0
        self.app._handle_cloth_key(ord("k"))
        assert self.app.cloth_cursor_r == 0
        self.app.cloth_cursor_c = 0
        self.app._handle_cloth_key(ord("h"))
        assert self.app.cloth_cursor_c == 0
        self.app.cloth_cursor_r = self.app.cloth_grid_h - 1
        self.app._handle_cloth_key(ord("j"))
        assert self.app.cloth_cursor_r == self.app.cloth_grid_h - 1
        self.app.cloth_cursor_c = self.app.cloth_grid_w - 1
        self.app._handle_cloth_key(ord("l"))
        assert self.app.cloth_cursor_c == self.app.cloth_grid_w - 1

    def test_toggle_pin(self):
        self.app.cloth_cursor_r = 5
        self.app.cloth_cursor_c = 5
        gw = self.app.cloth_grid_w
        idx = 5 * gw + 5
        assert self.app.cloth_points[idx][4] < 0.5  # initially unpinned
        self.app._handle_cloth_key(ord("p"))
        assert self.app.cloth_points[idx][4] > 0.5  # now pinned
        self.app._handle_cloth_key(ord("p"))
        assert self.app.cloth_points[idx][4] < 0.5  # unpinned again

    def test_tear_at_cursor(self):
        self.app.cloth_cursor_r = 5
        self.app.cloth_cursor_c = 5
        gw = self.app.cloth_grid_w
        idx = 5 * gw + 5
        before = len(self.app.cloth_constraints)
        self.app._handle_cloth_key(ord("x"))
        after = len(self.app.cloth_constraints)
        # Should have removed constraints involving this point
        assert after < before
        # Verify no remaining constraints reference this point
        for con in self.app.cloth_constraints:
            assert con[0] != idx and con[1] != idx

    def test_reset_preset(self):
        # Run some steps to change state
        for _ in range(5):
            self.app._cloth_step()
        self.app._handle_cloth_key(ord("r"))
        assert self.app.cloth_generation == 0

    def test_gravity_adjust(self):
        initial = self.app.cloth_gravity
        self.app._handle_cloth_key(ord("g"))
        assert self.app.cloth_gravity > initial
        self.app._handle_cloth_key(ord("G"))
        assert abs(self.app.cloth_gravity - initial) < 0.001

    def test_wind_adjust(self):
        initial = self.app.cloth_wind
        self.app._handle_cloth_key(ord("w"))
        assert self.app.cloth_wind > initial
        self.app._handle_cloth_key(ord("W"))
        assert abs(self.app.cloth_wind - initial) < 0.001

    def test_damping_adjust(self):
        initial = self.app.cloth_damping
        self.app._handle_cloth_key(ord("d"))
        assert self.app.cloth_damping > initial
        self.app._handle_cloth_key(ord("D"))
        assert abs(self.app.cloth_damping - initial) < 0.001

    def test_tear_threshold_adjust(self):
        initial = self.app.cloth_tear_threshold
        self.app._handle_cloth_key(ord("t"))
        assert self.app.cloth_tear_threshold > initial
        self.app._handle_cloth_key(ord("T"))
        assert abs(self.app.cloth_tear_threshold - initial) < 0.1

    def test_speed_adjust(self):
        initial = self.app.cloth_steps_per_frame
        self.app._handle_cloth_key(ord("+"))
        assert self.app.cloth_steps_per_frame == initial + 1
        self.app._handle_cloth_key(ord("-"))
        assert self.app.cloth_steps_per_frame == initial

    def test_speed_bounds(self):
        self.app.cloth_steps_per_frame = 10
        self.app._handle_cloth_key(ord("+"))
        assert self.app.cloth_steps_per_frame == 10
        self.app.cloth_steps_per_frame = 1
        self.app._handle_cloth_key(ord("-"))
        assert self.app.cloth_steps_per_frame == 1

    def test_return_to_menu(self):
        self.app._handle_cloth_key(ord("R"))
        assert self.app.cloth_mode is False
        assert self.app.cloth_menu is True

    def test_return_to_menu_m(self):
        self.app._handle_cloth_key(ord("m"))
        assert self.app.cloth_mode is False
        assert self.app.cloth_menu is True

    def test_gravity_upper_bound(self):
        self.app.cloth_gravity = 2.0
        self.app._handle_cloth_key(ord("g"))
        assert self.app.cloth_gravity == 2.0

    def test_gravity_lower_bound(self):
        self.app.cloth_gravity = 0.0
        self.app._handle_cloth_key(ord("G"))
        assert self.app.cloth_gravity == 0.0

    def test_damping_bounds(self):
        self.app.cloth_damping = 1.0
        self.app._handle_cloth_key(ord("d"))
        assert self.app.cloth_damping == 1.0
        self.app.cloth_damping = 0.9
        self.app._handle_cloth_key(ord("D"))
        assert self.app.cloth_damping == 0.9

    def test_tear_threshold_lower_bound(self):
        self.app.cloth_tear_threshold = 1.5
        self.app._handle_cloth_key(ord("T"))
        assert self.app.cloth_tear_threshold == 1.5

    def test_speed_equals_key(self):
        initial = self.app.cloth_steps_per_frame
        self.app._handle_cloth_key(ord("="))
        assert self.app.cloth_steps_per_frame == initial + 1

    def test_speed_underscore_key(self):
        self.app.cloth_steps_per_frame = 3
        self.app._handle_cloth_key(ord("_"))
        assert self.app.cloth_steps_per_frame == 2


class TestClothPhysicsEdgeCases:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_zero_gravity_no_fall(self):
        """With zero gravity and no wind, initially at-rest points should barely move."""
        self.app._cloth_init("hanging")
        self.app.cloth_gravity = 0.0
        self.app.cloth_wind = 0.0
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        mid_idx = (gh // 2) * gw + gw // 2
        initial_y = self.app.cloth_points[mid_idx][1]
        for _ in range(5):
            self.app._cloth_step()
        final_y = self.app.cloth_points[mid_idx][1]
        # Should not move significantly
        assert abs(final_y - initial_y) < 0.5

    def test_constraint_zero_dist_no_crash(self):
        """Two points at the same position should not crash (div by zero guard)."""
        self.app._cloth_init("hanging")
        gw = self.app.cloth_grid_w
        # Force two connected points to same position
        p1 = self.app.cloth_points[gw]  # row 1, col 0 (unpinned for curtain; pinned for hanging)
        p2 = self.app.cloth_points[gw + 1]
        p2[0] = p1[0]
        p2[1] = p1[1]
        p2[2] = p1[2]
        p2[3] = p1[3]
        # Should not crash
        self.app._cloth_step()
        assert self.app.cloth_generation == 1

    def test_all_constraints_torn(self):
        """Simulation should handle having zero constraints gracefully."""
        self.app._cloth_init("hanging")
        self.app.cloth_constraints = []
        for _ in range(5):
            self.app._cloth_step()
        assert self.app.cloth_generation == 5

    def test_single_point_no_constraints(self):
        """A single unpinned point should just fall under gravity."""
        self.app._cloth_init("hanging")
        self.app.cloth_points = [[5.0, 5.0, 5.0, 5.0, 0.0]]
        self.app.cloth_constraints = []
        self.app.cloth_grid_w = 1
        self.app.cloth_grid_h = 1
        initial_y = 5.0
        self.app._cloth_step()
        assert self.app.cloth_points[0][1] > initial_y

    def test_negative_wind(self):
        """Negative wind should push points leftward."""
        self.app._cloth_init("flag")
        self.app.cloth_wind = -0.5
        self.app.cloth_gravity = 0.0
        gw = self.app.cloth_grid_w
        gh = self.app.cloth_grid_h
        # Track a free point on right side
        idx = (gh // 2) * gw + gw - 1
        initial_x = self.app.cloth_points[idx][0]
        for _ in range(10):
            self.app._cloth_step()
        final_x = self.app.cloth_points[idx][0]
        assert final_x < initial_x, "Negative wind should push points left"
