"""Tests for cyclic_ca mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.cyclic_ca import register, CYCLIC_PRESETS, CYCLIC_COLORS


class TestCyclicCA:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        # Instance attrs
        self.app.cyclic_mode = False
        self.app.cyclic_menu = False
        self.app.cyclic_menu_sel = 0
        self.app.cyclic_running = False
        self.app.cyclic_grid = []
        self.app.cyclic_steps_per_frame = 1

    def test_enter(self):
        self.app._enter_cyclic_mode()
        assert self.app.cyclic_menu is True

    def test_init(self):
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)  # Classic Spirals
        assert self.app.cyclic_mode is True
        assert len(self.app.cyclic_grid) > 0
        assert self.app.cyclic_n_states == 8

    def test_step_no_crash(self):
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        for _ in range(10):
            self.app._cyclic_step()
        assert self.app.cyclic_generation == 10

    def test_von_neumann_preset(self):
        """Test Von Neumann neighborhood preset."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(4)  # Von Neumann
        assert self.app.cyclic_neighborhood == "von_neumann"
        self.app._cyclic_step()
        assert self.app.cyclic_generation == 1

    def test_all_presets(self):
        """Ensure all presets initialize without error."""
        for i in range(len(CYCLIC_PRESETS)):
            random.seed(42)
            self.app._cyclic_init(i)
            assert self.app.cyclic_mode is True
            self.app._cyclic_step()

    def test_exit_cleanup(self):
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app._exit_cyclic_mode()
        assert self.app.cyclic_mode is False

    # ── Deep logic tests ──────────────────────────────────────────────

    def test_register_sets_class_constants(self):
        """register() must set CYCLIC_PRESETS and CYCLIC_COLORS on App."""
        cls = type(self.app)
        assert hasattr(cls, "CYCLIC_PRESETS")
        assert hasattr(cls, "CYCLIC_COLORS")
        assert cls.CYCLIC_PRESETS is CYCLIC_PRESETS
        assert cls.CYCLIC_COLORS is CYCLIC_COLORS

    def test_successor_consumed_by_next_state(self):
        """A cell in state s with enough successor neighbors becomes s+1."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        # Build a small controlled 3x3 grid, n_states=4, threshold=1, moore
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "moore"
        # Center cell is 0, surround it with one neighbor that is 1 (its successor)
        self.app.cyclic_grid = [
            [2, 2, 2],
            [2, 0, 2],
            [2, 1, 2],
        ]
        self.app._cyclic_step()
        # Cell (1,1) was 0 with neighbor (2,1)=1 (successor), threshold=1 => becomes 1
        assert self.app.cyclic_grid[1][1] == 1

    def test_cell_stays_if_no_successor_neighbors(self):
        """A cell should NOT advance if no neighbor holds the successor state."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "moore"
        # All cells are 0 — successor is 1 but no neighbor has 1
        self.app.cyclic_grid = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]
        self.app._cyclic_step()
        # Nothing should change
        assert self.app.cyclic_grid == [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

    def test_threshold_prevents_advance(self):
        """Cell should NOT advance if successor count < threshold."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 3
        self.app.cyclic_neighborhood = "moore"
        # Center is 0, only 2 neighbors are 1 (successor), threshold requires 3
        self.app.cyclic_grid = [
            [2, 1, 2],
            [2, 0, 2],
            [2, 1, 2],
        ]
        self.app._cyclic_step()
        # Not enough successors — cell stays at 0
        assert self.app.cyclic_grid[1][1] == 0

    def test_threshold_allows_advance(self):
        """Cell advances when successor count >= threshold."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 3
        self.app.cyclic_neighborhood = "moore"
        # Center is 0, exactly 3 neighbors are 1
        self.app.cyclic_grid = [
            [1, 1, 2],
            [2, 0, 2],
            [2, 1, 2],
        ]
        self.app._cyclic_step()
        assert self.app.cyclic_grid[1][1] == 1

    def test_state_wraps_around(self):
        """State n_states-1 should advance to 0 (modular wrapping)."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "moore"
        # Center is 3 (max state), successor is 0
        self.app.cyclic_grid = [
            [2, 2, 2],
            [2, 3, 2],
            [2, 0, 2],
        ]
        self.app._cyclic_step()
        # Cell (1,1) was 3, neighbor (2,1)=0 is successor, should wrap to 0
        assert self.app.cyclic_grid[1][1] == 0

    def test_von_neumann_only_4_neighbors(self):
        """Von Neumann neighborhood counts only 4 orthogonal neighbors."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "von_neumann"
        # Center is 0; only diagonal neighbors have 1 (successor)
        # Von Neumann should NOT count diagonals
        self.app.cyclic_grid = [
            [1, 2, 1],
            [2, 0, 2],
            [1, 2, 1],
        ]
        self.app._cyclic_step()
        # No orthogonal neighbor has 1, so center stays 0
        assert self.app.cyclic_grid[1][1] == 0

    def test_von_neumann_orthogonal_triggers(self):
        """Von Neumann: orthogonal successor neighbor triggers advance."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "von_neumann"
        # Successor 1 placed at orthogonal neighbor (0,1)
        self.app.cyclic_grid = [
            [2, 1, 2],
            [2, 0, 2],
            [2, 2, 2],
        ]
        self.app._cyclic_step()
        assert self.app.cyclic_grid[1][1] == 1

    def test_toroidal_wrapping(self):
        """Grid wraps toroidally — edges connect to opposite side."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "moore"
        # Cell (0,0) is 0, its successor 1 is at (2,2) — a wrapped diagonal neighbor
        self.app.cyclic_grid = [
            [0, 2, 2],
            [2, 2, 2],
            [2, 2, 1],
        ]
        self.app._cyclic_step()
        # (0,0)'s Moore neighborhood includes (2,2) via wrapping
        assert self.app.cyclic_grid[0][0] == 1

    def test_grid_all_values_in_range(self):
        """After stepping, all grid values stay within [0, n_states)."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        for _ in range(20):
            self.app._cyclic_step()
        n = self.app.cyclic_n_states
        for row in self.app.cyclic_grid:
            for val in row:
                assert 0 <= val < n

    def test_generation_counter_increments(self):
        """Each step increments the generation counter by 1."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        assert self.app.cyclic_generation == 0
        self.app._cyclic_step()
        assert self.app.cyclic_generation == 1
        self.app._cyclic_step()
        assert self.app.cyclic_generation == 2

    def test_non_successor_neighbor_ignored(self):
        """Only successor state (s+1)%n triggers; other states do not."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 3
        self.app.cyclic_cols = 3
        self.app.cyclic_n_states = 4
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "moore"
        # Center is 0, successor is 1, but all neighbors are 2 or 3
        self.app.cyclic_grid = [
            [2, 3, 2],
            [3, 0, 3],
            [2, 3, 2],
        ]
        self.app._cyclic_step()
        assert self.app.cyclic_grid[1][1] == 0

    def test_simultaneous_update(self):
        """All cells update based on the SAME previous generation (synchronous)."""
        self.app.cyclic_mode = True
        self.app._cyclic_init(0)
        self.app.cyclic_rows = 1
        self.app.cyclic_cols = 4
        self.app.cyclic_n_states = 3
        self.app.cyclic_threshold = 1
        self.app.cyclic_neighborhood = "moore"
        # Row: [0, 1, 2, 0]  (wrapping 1D ring via moore on 1-row grid)
        # Cell 0: state=0, successor=1, neighbor at index 1 has 1 => advance to 1
        # Cell 1: state=1, successor=2, neighbor at index 2 has 2 => advance to 2
        # Cell 2: state=2, successor=0, neighbor at index 3 has 0 => advance to 0
        # Cell 3: state=0, successor=1, neighbor at index 0 has 0... but wait,
        #   for 1-row grid with moore, neighbors of (0,3) include (0,2)=2 and (0,0)=0
        #   only successor=1 matters; neighbor (0,2)=2 is not 1, (0,0)=0 is not 1
        #   so cell 3 stays 0
        self.app.cyclic_grid = [[0, 1, 2, 0]]
        self.app._cyclic_step()
        assert self.app.cyclic_grid == [[1, 2, 0, 0]]
