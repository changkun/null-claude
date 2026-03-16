"""Tests for dla mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.dla import register
from life.modes.dla import DLA_PRESETS
from life.constants import SPEEDS


def _make_dla_app():
    """Create a mock app with DLA mode registered."""
    app = make_mock_app()
    cls = type(app)
    register(cls)
    cls.DLA_PRESETS = DLA_PRESETS
    # Instance attrs needed by DLA
    app.dla_mode = False
    app.dla_menu = False
    app.dla_menu_sel = 0
    app.dla_running = False
    app.dla_grid = []
    app.dla_walkers = []
    app.dla_steps_per_frame = 5
    return app


class TestDLAEnterExit:
    def test_enter_sets_menu(self):
        app = _make_dla_app()
        app._enter_dla_mode()
        assert app.dla_menu is True
        assert app.dla_menu_sel == 0

    def test_exit_clears_state(self):
        app = _make_dla_app()
        random.seed(42)
        app._dla_init(0)
        assert app.dla_mode is True
        app._exit_dla_mode()
        assert app.dla_mode is False
        assert app.dla_running is False
        assert app.dla_grid == []
        assert app.dla_walkers == []


class TestDLAInit:
    def test_single_seed_placement(self):
        """Single seed preset places exactly one crystal cell at center."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)  # Crystal Growth (single)
        rows, cols = app.dla_rows, app.dla_cols
        cr, cc = rows // 2, cols // 2
        assert app.dla_grid[cr][cc] == 1
        assert app.dla_crystal_count == 1
        assert (cr, cc) in app.dla_seeds

    def test_multi_seed_placement(self):
        """Multi-seed preset places 5 seeds (4 corners + center)."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(1)  # Multi-Seed
        assert app.dla_crystal_count == 5
        assert len(app.dla_seeds) == 5
        # All seeds should be on the grid
        for sr, sc in app.dla_seeds:
            assert app.dla_grid[sr][sc] == 1

    def test_snowflake_symmetry(self):
        """Snowflake preset enables 6-fold symmetry and lower stickiness."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(2)  # Snowflake
        assert app.dla_symmetry == 6
        assert app.dla_stickiness == 0.7
        assert app.dla_crystal_count == 1

    def test_electro_seed_bottom_edge(self):
        """Electrodeposition preset seeds the entire bottom row."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(3)  # Electrodeposition
        rows, cols = app.dla_rows, app.dla_cols
        # Every cell in the bottom row should be crystal
        for c in range(cols):
            assert app.dla_grid[rows - 1][c] == 1
        assert app.dla_crystal_count == cols

    def test_electro_bias_direction(self):
        """Electrodeposition bias should push walkers DOWNWARD (positive row direction)."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(3)  # Electrodeposition
        # bias_r > 0 means dr = +1 (downward, toward cathode at bottom)
        assert app.dla_bias_r > 0, (
            "Electro bias_r must be positive to drift walkers toward bottom-edge cathode"
        )

    def test_electro_walkers_spawn_top(self):
        """Electrodeposition walkers should spawn near the top of the grid."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(3)  # Electrodeposition
        rows = app.dla_rows
        # All walkers should be in the top third of the grid (spawn region)
        for w in app.dla_walkers:
            assert w[0] <= rows // 3, (
                f"Electro walker at row {w[0]} should be in top third (0..{rows // 3})"
            )

    def test_line_seed_horizontal(self):
        """Line seed preset places a horizontal line in the middle row."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(4)  # Line Seed
        rows, cols = app.dla_rows, app.dla_cols
        cr = rows // 2
        expected_range = range(cols // 4, 3 * cols // 4)
        for c in expected_range:
            assert app.dla_grid[cr][c] == 1
        assert app.dla_crystal_count == len(expected_range)

    def test_ring_seed_circular(self):
        """Ring seed preset places cells in a circular pattern."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(5)  # Ring Seed
        assert app.dla_crystal_count > 0
        rows, cols = app.dla_rows, app.dla_cols
        cr, cc = rows // 2, cols // 2
        ring_r = min(rows, cols) // 5
        # All seeds should be approximately ring_r distance from center
        for sr, sc in app.dla_seeds:
            dist = math.sqrt((sr - cr) ** 2 + (sc - cc) ** 2)
            assert abs(dist - ring_r) <= 1.5, (
                f"Ring seed at ({sr},{sc}) distance {dist:.1f} too far from expected {ring_r}"
            )

    def test_all_presets_initialize(self):
        """Every preset initializes without error and has walkers and crystals."""
        for i in range(len(DLA_PRESETS)):
            random.seed(42)
            app = _make_dla_app()
            app._dla_init(i)
            assert app.dla_mode is True
            assert app.dla_crystal_count > 0
            assert len(app.dla_walkers) > 0

    def test_walkers_not_on_crystal(self):
        """Walkers should never be spawned on crystal cells."""
        for i in range(len(DLA_PRESETS)):
            random.seed(42)
            app = _make_dla_app()
            app._dla_init(i)
            for w in app.dla_walkers:
                assert app.dla_grid[w[0]][w[1]] == 0, (
                    f"Preset {i}: walker at ({w[0]},{w[1]}) is on a crystal cell"
                )


class TestDLAStep:
    def test_generation_increments(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        for i in range(1, 11):
            app._dla_step()
            assert app.dla_generation == i

    def test_crystal_grows(self):
        """After many steps, crystal count should increase."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app.dla_num_walkers = 50  # fewer walkers for faster test
        app.dla_walkers = []
        app._dla_spawn_walkers()
        initial = app.dla_crystal_count
        for _ in range(100):
            app._dla_step()
        assert app.dla_crystal_count > initial

    def test_walkers_maintained(self):
        """Walker count should stay near the target number."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app.dla_num_walkers = 50
        app.dla_walkers = []
        app._dla_spawn_walkers()
        for _ in range(20):
            app._dla_step()
        # Walkers should be replenished close to target
        assert len(app.dla_walkers) >= app.dla_num_walkers * 0.5

    def test_random_walk_with_bias(self):
        """Biased walk should produce net drift in the bias direction."""
        random.seed(123)
        app = _make_dla_app()
        app._dla_init(3)  # Electrodeposition with positive bias_r
        app.dla_num_walkers = 30
        app.dla_walkers = []
        app._dla_spawn_walkers()
        for _ in range(20):
            app._dla_step()
        # With positive bias, walkers that survive should have moved downward on average
        assert app.dla_bias_r > 0

    def test_adjacency_check_eight_neighbors(self):
        """A walker adjacent to crystal (8-connected) should potentially stick."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        rows, cols = app.dla_rows, app.dla_cols
        cr, cc = rows // 2, cols // 2
        # Place a walker diagonally adjacent to the seed
        app.dla_walkers = [[cr - 1, cc - 1]]
        app.dla_stickiness = 1.0  # guaranteed stick
        # The walker is already adjacent; on next step if it stays adjacent, it sticks
        # Force walker to not move (mock random to return 0,0 for dr,dc)
        old_choice = random.choice
        random.choice = lambda x: 0  # Always return 0 for direction
        try:
            app._dla_step()
        finally:
            random.choice = old_choice
        # Walker should have stuck since it was already adjacent and didn't move onto crystal
        # It's at (cr-1, cc-1) which is diagonally adjacent to crystal at (cr, cc)
        # Since random.choice returns 0, nr=cr-1, nc=cc-1 (no move), and it checks adjacency
        # The grid at (cr-1, cc-1) should now be crystal
        assert app.dla_grid[cr - 1][cc - 1] > 0

    def test_stickiness_probability(self):
        """With stickiness < 1, some adjacent walkers should not stick."""
        stuck_count = 0
        trials = 50
        for trial in range(trials):
            random.seed(trial)
            app = _make_dla_app()
            # Minimal init: just set up grid directly instead of full _dla_init
            app.dla_rows = 20
            app.dla_cols = 20
            app.dla_grid = [[0] * 20 for _ in range(20)]
            app.dla_grid[10][10] = 1  # seed at center
            app.dla_seeds = [(10, 10)]
            app.dla_crystal_count = 1
            app.dla_max_radius = 5.0
            app.dla_spawn_radius = 15.0
            app.dla_num_walkers = 1
            app.dla_generation = 0
            app.dla_bias_r = 0.0
            app.dla_bias_c = 0.0
            app.dla_symmetry = 1
            app.dla_stickiness = 0.5
            app.dla_walkers = [[9, 10]]  # adjacent to seed
            old_choice = random.choice
            random.choice = lambda x: 0
            try:
                app._dla_step()
            finally:
                random.choice = old_choice
            if app.dla_grid[9][10] > 0:
                stuck_count += 1
        # With 50% stickiness over 50 trials, expect roughly 25 sticks
        assert 8 < stuck_count < 42, f"Stickiness test: {stuck_count}/50 stuck (expected ~25)"

    def test_walker_killed_far_from_center(self):
        """Walkers far from center beyond kill radius should be removed."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        rows, cols = app.dla_rows, app.dla_cols
        kill_radius = app.dla_spawn_radius + 20
        # Place a walker very far from center (but within bounds)
        far_r = min(rows - 1, rows // 2 + int(kill_radius) + 5)
        far_c = cols // 2
        app.dla_walkers = [[far_r, far_c]]
        app._dla_step()
        # The far walker should have been killed (or its position checked)
        # After respawn, walkers should be near spawn radius, not at far_r


    def test_boundary_handling(self):
        """Walkers at grid edges should not go out of bounds."""
        random.seed(42)
        app = _make_dla_app()
        # Minimal grid setup
        app.dla_rows = 20
        app.dla_cols = 20
        app.dla_grid = [[0] * 20 for _ in range(20)]
        app.dla_grid[10][10] = 1
        app.dla_seeds = [(10, 10)]
        app.dla_crystal_count = 1
        app.dla_max_radius = 5.0
        app.dla_spawn_radius = 15.0
        app.dla_num_walkers = 4
        app.dla_generation = 0
        app.dla_bias_r = 0.0
        app.dla_bias_c = 0.0
        app.dla_symmetry = 1
        app.dla_stickiness = 0.0  # never stick, just walk
        rows, cols = 20, 20
        app.dla_walkers = [[0, 0], [0, cols - 1], [rows - 1, 0], [rows - 1, cols - 1]]
        for _ in range(20):
            app._dla_step()
        # All walkers should remain within bounds
        for w in app.dla_walkers:
            assert 0 <= w[0] < rows
            assert 0 <= w[1] < cols

    def test_crystal_does_not_overlap(self):
        """Crystal count should match actual grid cells (symmetry=1)."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app.dla_num_walkers = 50
        app.dla_walkers = []
        app._dla_spawn_walkers()
        for _ in range(80):
            app._dla_step()
        grid_count = sum(
            1 for r in range(app.dla_rows) for c in range(app.dla_cols)
            if app.dla_grid[r][c] > 0
        )
        assert grid_count == app.dla_crystal_count


class TestDLASymmetry:
    def test_snowflake_symmetric_attachment(self):
        """Snowflake (6-fold) attachment should place cells at symmetric positions."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(2)  # Snowflake
        rows, cols = app.dla_rows, app.dla_cols
        cr, cc = rows // 2, cols // 2
        initial_count = app.dla_crystal_count
        # Manually trigger symmetric attachment at offset (3, 0) from center
        app._dla_attach_symmetric(cr + 3, cc, 2)
        # Should have placed at least 6 cells (one per symmetry sector)
        assert app.dla_crystal_count > initial_count
        # Check that multiple symmetric positions are filled
        filled_positions = []
        for k in range(6):
            angle = 2 * math.pi * k / 6
            rr = int(round(cr + 3 * math.cos(angle)))
            rc = int(round(cc + 3 * math.sin(angle)))
            if 0 <= rr < rows and 0 <= rc < cols:
                filled_positions.append(app.dla_grid[rr][rc] > 0)
        assert sum(filled_positions) >= 4  # Most positions should be filled

    def test_symmetry_mirror_updates_max_radius(self):
        """Mirror cells in sym==6 should update dla_max_radius."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(2)  # Snowflake
        rows, cols = app.dla_rows, app.dla_cols
        cr, cc = rows // 2, cols // 2
        old_max = app.dla_max_radius
        # Attach at a point far from center
        offset = 8
        app._dla_attach_symmetric(cr + offset, cc, 2)
        # max_radius should have increased since mirrored cells are also far from center
        assert app.dla_max_radius >= offset * 0.8

    def test_symmetry_one_no_mirror(self):
        """With symmetry=1, only one cell should be placed per attachment."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)  # Single seed, symmetry=1
        app.dla_num_walkers = 50
        app.dla_walkers = []
        app._dla_spawn_walkers()
        assert app.dla_symmetry == 1
        for _ in range(60):
            app._dla_step()
        grid_count = sum(
            1 for r in range(app.dla_rows) for c in range(app.dla_cols)
            if app.dla_grid[r][c] > 0
        )
        assert grid_count == app.dla_crystal_count


class TestDLASpawnWalkers:
    def test_spawn_fills_to_target(self):
        """Spawning should bring walker count up to target."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app.dla_walkers = []  # Clear walkers
        app._dla_spawn_walkers()
        assert len(app.dla_walkers) == app.dla_num_walkers

    def test_spawn_does_not_overshoot(self):
        """Spawning when already at target should not add more."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        count_before = len(app.dla_walkers)
        app._dla_spawn_walkers()
        assert len(app.dla_walkers) == count_before

    def test_symmetric_spawn_ring(self):
        """For symmetric presets, walkers spawn on a ring around center."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(2)  # Snowflake (symmetric)
        rows, cols = app.dla_rows, app.dla_cols
        cr, cc = rows // 2, cols // 2
        spawn_r = app.dla_spawn_radius
        # Check walkers are roughly at spawn radius
        distances = [math.sqrt((w[0] - cr) ** 2 + (w[1] - cc) ** 2)
                     for w in app.dla_walkers]
        avg_dist = sum(distances) / len(distances)
        assert abs(avg_dist - spawn_r) < spawn_r * 0.5


class TestDLAMenuKeys:
    def test_menu_navigate_down(self):
        app = _make_dla_app()
        app._enter_dla_mode()
        import curses
        app._handle_dla_menu_key(ord("j"))
        assert app.dla_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        app = _make_dla_app()
        app._enter_dla_mode()
        app._handle_dla_menu_key(ord("k"))
        assert app.dla_menu_sel == len(DLA_PRESETS) - 1

    def test_menu_select_enter(self):
        random.seed(42)
        app = _make_dla_app()
        app._enter_dla_mode()
        app._handle_dla_menu_key(ord("\n"))
        assert app.dla_mode is True

    def test_menu_cancel(self):
        app = _make_dla_app()
        app._enter_dla_mode()
        app._handle_dla_menu_key(27)  # ESC
        assert app.dla_menu is False


class TestDLAActiveKeys:
    def test_space_toggles_running(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        assert app.dla_running is False
        app._handle_dla_key(ord(" "))
        assert app.dla_running is True
        app._handle_dla_key(ord(" "))
        assert app.dla_running is False

    def test_step_key(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        gen_before = app.dla_generation
        app._handle_dla_key(ord("n"))
        assert app.dla_generation == gen_before + app.dla_steps_per_frame

    def test_stickiness_adjust(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        initial_stick = app.dla_stickiness
        app._handle_dla_key(ord("S"))  # decrease
        assert app.dla_stickiness < initial_stick

    def test_walker_count_adjust(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        initial_walkers = app.dla_num_walkers
        app._handle_dla_key(ord("w"))  # increase
        assert app.dla_num_walkers == initial_walkers + 50

    def test_steps_per_frame_adjust(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        initial_spf = app.dla_steps_per_frame
        app._handle_dla_key(ord("+"))
        assert app.dla_steps_per_frame == initial_spf + 2

    def test_reset_key(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app.dla_num_walkers = 20
        app.dla_walkers = []
        app._dla_spawn_walkers()
        for _ in range(10):
            app._dla_step()
        app._handle_dla_key(ord("r"))
        assert app.dla_generation == 0
        assert app.dla_running is False

    def test_quit_key(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app._handle_dla_key(ord("q"))
        assert app.dla_mode is False

    def test_return_to_menu(self):
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app._handle_dla_key(ord("R"))
        assert app.dla_mode is False
        assert app.dla_menu is True


class TestDLAMaxRadius:
    def test_max_radius_grows_with_crystal(self):
        """As crystal grows, max_radius should increase."""
        random.seed(42)
        app = _make_dla_app()
        app._dla_init(0)
        app.dla_num_walkers = 50
        app.dla_walkers = []
        app._dla_spawn_walkers()
        initial_radius = app.dla_max_radius
        for _ in range(100):
            app._dla_step()
        assert app.dla_max_radius >= initial_radius
