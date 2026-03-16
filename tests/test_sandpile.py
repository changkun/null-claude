"""Tests for sandpile mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.sandpile import register
from life.modes.dla import SANDPILE_PRESETS, SANDPILE_CHARS, SANDPILE_OVERFLOW_CHAR
from life.constants import SPEEDS


def _setup_app():
    """Create and configure a mock app with sandpile mode registered."""
    app = make_mock_app()
    cls = type(app)
    register(cls)
    cls.SANDPILE_PRESETS = SANDPILE_PRESETS
    cls.SANDPILE_CHARS = SANDPILE_CHARS
    cls.SANDPILE_OVERFLOW_CHAR = SANDPILE_OVERFLOW_CHAR
    app.sandpile_mode = False
    app.sandpile_menu = False
    app.sandpile_menu_sel = 0
    app.sandpile_running = False
    app.sandpile_grid = []
    app.sandpile_steps_per_frame = 1
    return app


def _make_sandpile_grid(app, rows, cols):
    """Set up a minimal sandpile grid on the app with given dimensions."""
    app.sandpile_rows = rows
    app.sandpile_cols = cols
    app.sandpile_grid = [[0] * cols for _ in range(rows)]
    app.sandpile_total_grains = 0
    app.sandpile_topples = 0
    app.sandpile_generation = 0
    app.sandpile_auto_drop = False
    app.sandpile_drop_mode = "center"
    app.sandpile_drop_amount = 0
    app.sandpile_cursor_r = rows // 2
    app.sandpile_cursor_c = cols // 2
    app.sandpile_mode = True


def _sum_grid(grid):
    """Return total grains on the grid."""
    return sum(cell for row in grid for cell in row)


def _is_stable(grid):
    """Return True if no cell has >= 4 grains."""
    return all(cell < 4 for row in grid for cell in row)


class TestSandpile:
    def setup_method(self):
        random.seed(42)
        self.app = _setup_app()

    def test_enter(self):
        self.app._enter_sandpile_mode()
        assert self.app.sandpile_menu is True

    def test_init_single_tower(self):
        self.app.sandpile_mode = True
        self.app._sandpile_init(0)  # Single Tower
        assert self.app.sandpile_mode is True
        assert len(self.app.sandpile_grid) > 0

    def test_init_big_pile(self):
        self.app.sandpile_mode = True
        self.app._sandpile_init(1)  # Big Pile
        assert self.app.sandpile_mode is True
        cr = self.app.sandpile_rows // 2
        cc = self.app.sandpile_cols // 2
        assert self.app.sandpile_grid[cr][cc] == 10000

    def test_step_no_crash(self):
        self.app.sandpile_mode = True
        self.app._sandpile_init(0)  # Single Tower
        for _ in range(10):
            self.app._sandpile_step()
        assert self.app.sandpile_generation == 10

    def test_toppling(self):
        """Verify grains topple correctly."""
        self.app.sandpile_mode = True
        self.app._sandpile_init(1)  # Big Pile (10000 grains)
        self.app._sandpile_step()
        assert self.app.sandpile_topples > 0

    def test_exit_cleanup(self):
        self.app.sandpile_mode = True
        self.app._sandpile_init(0)
        self.app._exit_sandpile_mode()
        assert self.app.sandpile_mode is False


class TestSandpileToppling:
    """Verify the toppling rule distributes grains correctly."""

    def setup_method(self):
        random.seed(42)
        self.app = _setup_app()

    def test_single_cell_topple_interior(self):
        """A cell with 4 grains in the interior should distribute 1 to each
        of its 4 neighbours and leave 0 on itself."""
        _make_sandpile_grid(self.app, 5, 5)
        self.app.sandpile_grid[2][2] = 4
        self.app.sandpile_total_grains = 4
        self.app._sandpile_step()

        g = self.app.sandpile_grid
        assert g[2][2] == 0, "toppled cell should be empty"
        assert g[1][2] == 1, "north neighbour gets 1 grain"
        assert g[3][2] == 1, "south neighbour gets 1 grain"
        assert g[2][1] == 1, "west neighbour gets 1 grain"
        assert g[2][3] == 1, "east neighbour gets 1 grain"
        assert _sum_grid(g) == 4, "grain total preserved for interior topple"
        assert self.app.sandpile_total_grains == 4

    def test_single_cell_topple_edge(self):
        """A cell with 4 grains on the top edge should lose 1 grain off-grid."""
        _make_sandpile_grid(self.app, 5, 5)
        self.app.sandpile_grid[0][2] = 4
        self.app.sandpile_total_grains = 4
        self.app._sandpile_step()

        g = self.app.sandpile_grid
        # 1 grain lost off the top edge
        assert _sum_grid(g) == 3, "1 grain falls off the top edge"
        assert self.app.sandpile_total_grains == 3
        assert g[0][2] == 0
        assert g[1][2] == 1
        assert g[0][1] == 1
        assert g[0][3] == 1

    def test_single_cell_topple_corner(self):
        """A cell with 4 grains at a corner should lose 2 grains off-grid."""
        _make_sandpile_grid(self.app, 5, 5)
        self.app.sandpile_grid[0][0] = 4
        self.app.sandpile_total_grains = 4
        self.app._sandpile_step()

        g = self.app.sandpile_grid
        assert _sum_grid(g) == 2, "2 grains fall off at a corner"
        assert self.app.sandpile_total_grains == 2
        assert g[0][0] == 0
        assert g[1][0] == 1
        assert g[0][1] == 1

    def test_cascade_topple(self):
        """When a topple causes a neighbour to reach >=4, it should cascade."""
        _make_sandpile_grid(self.app, 5, 5)
        # Center = 4, east neighbour = 3 -> after topple, east neighbour = 4 -> cascades
        self.app.sandpile_grid[2][2] = 4
        self.app.sandpile_grid[2][3] = 3
        self.app.sandpile_total_grains = 7
        self.app._sandpile_step()

        g = self.app.sandpile_grid
        assert _is_stable(g), "grid should be fully stable after step"
        assert _sum_grid(g) == 7, "all grains preserved (no edge topple in this case)"

    def test_high_pile_topple(self):
        """A cell with 8 grains should topple twice (in successive passes)."""
        _make_sandpile_grid(self.app, 7, 7)
        self.app.sandpile_grid[3][3] = 8
        self.app.sandpile_total_grains = 8
        self.app._sandpile_step()

        g = self.app.sandpile_grid
        assert _is_stable(g), "grid should be stable after step"
        assert _sum_grid(g) == 8, "all grains preserved for interior pile"
        assert self.app.sandpile_total_grains == 8

    def test_stability_after_step(self):
        """After _sandpile_step the grid should always be stable (no cell >= 4),
        as long as max_iterations is not exceeded."""
        _make_sandpile_grid(self.app, 10, 10)
        self.app.sandpile_grid[5][5] = 100
        self.app.sandpile_total_grains = 100
        self.app._sandpile_step()

        assert _is_stable(self.app.sandpile_grid)

    def test_grain_count_tracking_with_edge_loss(self):
        """sandpile_total_grains should equal the actual grid sum after toppling,
        accounting for grains lost off edges."""
        _make_sandpile_grid(self.app, 5, 5)
        self.app.sandpile_grid[2][2] = 50
        self.app.sandpile_total_grains = 50
        self.app._sandpile_step()

        actual = _sum_grid(self.app.sandpile_grid)
        assert self.app.sandpile_total_grains == actual, (
            f"tracked grains ({self.app.sandpile_total_grains}) != actual ({actual})"
        )

    def test_grain_count_tracking_big_pile(self):
        """Grain count tracking for a larger initial pile on a small grid."""
        _make_sandpile_grid(self.app, 10, 10)
        self.app.sandpile_grid[5][5] = 200
        self.app.sandpile_total_grains = 200
        self.app._sandpile_step()

        actual = _sum_grid(self.app.sandpile_grid)
        assert self.app.sandpile_total_grains == actual

    def test_topple_count_single(self):
        """A single interior topple should report exactly 1 topple."""
        _make_sandpile_grid(self.app, 5, 5)
        self.app.sandpile_grid[2][2] = 4
        self.app.sandpile_total_grains = 4
        self.app._sandpile_step()
        assert self.app.sandpile_topples == 1

    def test_no_topple_below_threshold(self):
        """Cells with < 4 grains should never topple."""
        _make_sandpile_grid(self.app, 5, 5)
        self.app.sandpile_grid[2][2] = 3
        self.app.sandpile_total_grains = 3
        self.app._sandpile_step()
        assert self.app.sandpile_topples == 0
        assert self.app.sandpile_grid[2][2] == 3

    def test_empty_grid_no_topple(self):
        """An empty grid should produce zero topples."""
        _make_sandpile_grid(self.app, 5, 5)
        self.app._sandpile_step()
        assert self.app.sandpile_topples == 0
        assert self.app.sandpile_generation == 1

    def test_max_stable_all_threes(self):
        """A grid filled with 3s should not topple (max stable configuration)."""
        _make_sandpile_grid(self.app, 5, 5)
        for r in range(5):
            for c in range(5):
                self.app.sandpile_grid[r][c] = 3
        self.app.sandpile_total_grains = 75
        self.app._sandpile_step()
        assert self.app.sandpile_topples == 0
        assert _sum_grid(self.app.sandpile_grid) == 75

    def test_two_adjacent_topples(self):
        """Two adjacent cells both with 4 grains should topple simultaneously."""
        _make_sandpile_grid(self.app, 7, 7)
        self.app.sandpile_grid[3][3] = 4
        self.app.sandpile_grid[3][4] = 4
        self.app.sandpile_total_grains = 8
        self.app._sandpile_step()

        g = self.app.sandpile_grid
        assert _is_stable(g)
        # Both cells exchange grains: each gives 1 to the other
        # so net result: each gets -4+1 = -3, but also receives from the other
        assert _sum_grid(g) == 8, "interior cells, no grain loss"
        assert self.app.sandpile_total_grains == 8


class TestSandpilePresets:
    """Test all preset initializations."""

    def setup_method(self):
        random.seed(42)
        self.app = _setup_app()

    @pytest.mark.parametrize("idx", range(len(SANDPILE_PRESETS)))
    def test_preset_init(self, idx):
        """Each preset should initialize without error and produce a valid grid."""
        self.app._sandpile_init(idx)
        assert self.app.sandpile_mode is True
        assert len(self.app.sandpile_grid) == self.app.sandpile_rows
        assert len(self.app.sandpile_grid[0]) == self.app.sandpile_cols
        # Grain count tracking should match actual grid contents
        actual = _sum_grid(self.app.sandpile_grid)
        assert self.app.sandpile_total_grains == actual, (
            f"Preset {SANDPILE_PRESETS[idx][0]}: tracked={self.app.sandpile_total_grains} != actual={actual}"
        )

    @pytest.mark.parametrize("idx", range(len(SANDPILE_PRESETS)))
    def test_preset_step(self, idx):
        """Each preset should survive 5 steps without crashing."""
        self.app._sandpile_init(idx)
        for _ in range(5):
            self.app._sandpile_step()
        assert self.app.sandpile_generation == 5
        # After steps, tracked grains should still match actual
        actual = _sum_grid(self.app.sandpile_grid)
        assert self.app.sandpile_total_grains == actual, (
            f"Preset {SANDPILE_PRESETS[idx][0]} after 5 steps: tracked={self.app.sandpile_total_grains} != actual={actual}"
        )

    def test_checkerboard_pattern(self):
        """Checkerboard preset should place 3 grains on cells where (r+c) is even."""
        idx = next(i for i, p in enumerate(SANDPILE_PRESETS) if p[2] == "checkerboard")
        self.app._sandpile_init(idx)
        g = self.app.sandpile_grid
        rows, cols = self.app.sandpile_rows, self.app.sandpile_cols
        for r in range(rows):
            for c in range(cols):
                if (r + c) % 2 == 0:
                    assert g[r][c] == 3, f"cell ({r},{c}) should be 3"
                else:
                    assert g[r][c] == 0, f"cell ({r},{c}) should be 0"

    def test_max_stable_preset(self):
        """Max Stable preset should fill all cells with 3, except center = 4."""
        idx = next(i for i, p in enumerate(SANDPILE_PRESETS) if p[2] == "max_stable")
        self.app._sandpile_init(idx)
        g = self.app.sandpile_grid
        rows, cols = self.app.sandpile_rows, self.app.sandpile_cols
        cr, cc = rows // 2, cols // 2
        for r in range(rows):
            for c in range(cols):
                if r == cr and c == cc:
                    assert g[r][c] == 4
                else:
                    assert g[r][c] == 3

    def test_diamond_seed(self):
        """Diamond preset should place grains in a diamond shape."""
        idx = next(i for i, p in enumerate(SANDPILE_PRESETS) if p[2] == "diamond")
        self.app._sandpile_init(idx)
        g = self.app.sandpile_grid
        rows, cols = self.app.sandpile_rows, self.app.sandpile_cols
        cr, cc = rows // 2, cols // 2
        radius = min(rows, cols) // 6
        # Center of diamond should have 3 grains
        assert g[cr][cc] == 3
        # A cell well outside the diamond should have 0
        far_r = min(rows - 1, cr + radius + 5)
        far_c = min(cols - 1, cc + radius + 5)
        if abs(far_r - cr) + abs(far_c - cc) > radius:
            assert g[far_r][far_c] == 0

    def test_identity_preset_stable(self):
        """Identity Element preset should produce a stable configuration (all cells < 4)."""
        idx = next(i for i, p in enumerate(SANDPILE_PRESETS) if p[2] == "identity")
        self.app._sandpile_init(idx)
        assert _is_stable(self.app.sandpile_grid), "identity preset should be fully stable"

    def test_random_fill_center_perturbed(self):
        """Random Fill preset should set center cell to 4."""
        idx = next(i for i, p in enumerate(SANDPILE_PRESETS) if p[2] == "random_fill")
        self.app._sandpile_init(idx)
        cr = self.app.sandpile_rows // 2
        cc = self.app.sandpile_cols // 2
        assert self.app.sandpile_grid[cr][cc] == 4


class TestSandpileDrop:
    """Test grain dropping modes."""

    def setup_method(self):
        random.seed(42)
        self.app = _setup_app()

    def test_center_drop(self):
        _make_sandpile_grid(self.app, 10, 10)
        self.app.sandpile_drop_mode = "center"
        self.app.sandpile_drop_amount = 1
        self.app._sandpile_drop()
        cr, cc = 5, 5
        assert self.app.sandpile_grid[cr][cc] == 1
        assert self.app.sandpile_total_grains == 1

    def test_random_drop(self):
        _make_sandpile_grid(self.app, 10, 10)
        self.app.sandpile_drop_mode = "random"
        self.app.sandpile_drop_amount = 1
        self.app._sandpile_drop()
        assert _sum_grid(self.app.sandpile_grid) == 1
        assert self.app.sandpile_total_grains == 1

    def test_corners_drop(self):
        _make_sandpile_grid(self.app, 10, 10)
        self.app.sandpile_drop_mode = "corners"
        self.app.sandpile_drop_amount = 1
        self.app._sandpile_drop()
        assert _sum_grid(self.app.sandpile_grid) == 4  # 4 corners
        assert self.app.sandpile_total_grains == 4

    def test_cursor_drop(self):
        _make_sandpile_grid(self.app, 10, 10)
        self.app.sandpile_drop_mode = "cursor"
        self.app.sandpile_drop_amount = 3
        self.app.sandpile_cursor_r = 2
        self.app.sandpile_cursor_c = 3
        self.app._sandpile_drop()
        assert self.app.sandpile_grid[2][3] == 3
        assert self.app.sandpile_total_grains == 3

    def test_auto_drop_in_step(self):
        """When auto_drop is True, _sandpile_step should call _sandpile_drop."""
        _make_sandpile_grid(self.app, 10, 10)
        self.app.sandpile_auto_drop = True
        self.app.sandpile_drop_mode = "center"
        self.app.sandpile_drop_amount = 1
        self.app._sandpile_step()
        # Center should have received a grain
        assert self.app.sandpile_total_grains >= 1


class TestSandpileGrainConservation:
    """Verify that grain counting is always consistent with actual grid state."""

    def setup_method(self):
        random.seed(42)
        self.app = _setup_app()

    def test_conservation_center_drops(self):
        """After many center drops and topples, tracked count should match grid."""
        _make_sandpile_grid(self.app, 15, 15)
        self.app.sandpile_auto_drop = True
        self.app.sandpile_drop_mode = "center"
        self.app.sandpile_drop_amount = 1
        for _ in range(50):
            self.app._sandpile_step()
        actual = _sum_grid(self.app.sandpile_grid)
        assert self.app.sandpile_total_grains == actual

    def test_conservation_random_drops(self):
        """After many random drops and topples, tracked count should match grid."""
        _make_sandpile_grid(self.app, 15, 15)
        self.app.sandpile_auto_drop = True
        self.app.sandpile_drop_mode = "random"
        self.app.sandpile_drop_amount = 1
        for _ in range(50):
            self.app._sandpile_step()
        actual = _sum_grid(self.app.sandpile_grid)
        assert self.app.sandpile_total_grains == actual

    def test_conservation_corners(self):
        """After corner drops, tracked count should match grid."""
        _make_sandpile_grid(self.app, 15, 15)
        self.app.sandpile_auto_drop = True
        self.app.sandpile_drop_mode = "corners"
        self.app.sandpile_drop_amount = 1
        for _ in range(30):
            self.app._sandpile_step()
        actual = _sum_grid(self.app.sandpile_grid)
        assert self.app.sandpile_total_grains == actual
