"""Tests for Hodgepodge Machine mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.hodgepodge import register


class TestHodgepodge:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._hodge_init(0)
        assert self.app.hodge_mode is True
        assert self.app.hodge_generation == 0
        assert len(self.app.hodge_grid) > 0
        assert self.app.hodge_steps_per_frame == 1

    def test_step_no_crash(self):
        self.app._hodge_init(0)
        for _ in range(10):
            self.app._hodge_step()
        assert self.app.hodge_generation == 10

    def test_exit_cleanup(self):
        self.app._hodge_init(0)
        assert self.app.hodge_mode is True
        self.app._exit_hodge_mode()
        assert self.app.hodge_mode is False
        assert self.app.hodge_running is False

    # ── Ill cell rule: state n-1 becomes 0 ──

    def test_ill_cell_becomes_healthy(self):
        """An ill cell (state == n-1) must become 0 on the next step."""
        self.app._hodge_init(0)
        n = self.app.hodge_n_states
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        # Set entire grid to 0 except one cell which is ill
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        self.app.hodge_grid[5][5] = n - 1
        self.app._hodge_step()
        assert self.app.hodge_grid[5][5] == 0

    # ── Healthy cell rule: floor(a/k1 + b/k2) ──

    def test_healthy_cell_no_neighbors(self):
        """A healthy cell with all-zero neighbors stays healthy."""
        self.app._hodge_init(0)
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        self.app._hodge_step()
        # All cells should remain 0
        for r in range(rows):
            for c in range(cols):
                assert self.app.hodge_grid[r][c] == 0

    def test_healthy_cell_with_infected_neighbors(self):
        """Healthy cell infection from infected (not ill) neighbors.

        With k1=2, k2=3: if 3 infected neighbors and 0 ill neighbors,
        new_state = floor(3/2 + 0/3) = floor(1.5) = 1.
        """
        self.app._hodge_init(0)
        n = self.app.hodge_n_states  # 100
        k1, k2 = self.app.hodge_k1, self.app.hodge_k2  # 2, 3
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        # Place 3 infected neighbors (state 1..n-2) around (5,5)
        self.app.hodge_grid[4][4] = 1
        self.app.hodge_grid[4][5] = 1
        self.app.hodge_grid[4][6] = 1
        self.app._hodge_step()
        # floor(3/2 + 0/3) = floor(1.5) = 1
        assert self.app.hodge_grid[5][5] == 1

    def test_healthy_cell_with_ill_neighbors(self):
        """Healthy cell infection from ill neighbors only.

        With k1=2, k2=3 (Classic preset): if 0 infected, 4 ill neighbors,
        new_state = floor(0/2 + 4/3) = floor(1.333) = 1.
        """
        self.app._hodge_init(0)
        n = self.app.hodge_n_states
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        ill = n - 1
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        # Place 4 ill neighbors around (5,5)
        self.app.hodge_grid[4][4] = ill
        self.app.hodge_grid[4][5] = ill
        self.app.hodge_grid[4][6] = ill
        self.app.hodge_grid[5][4] = ill
        self.app._hodge_step()
        # floor(0/2 + 4/3) = floor(1.333) = 1
        assert self.app.hodge_grid[5][5] == 1

    def test_healthy_cell_floor_sum_not_separate_floors(self):
        """Verify floor(a/k1 + b/k2), NOT floor(a/k1) + floor(b/k2).

        This is the key correctness test. With k1=2, k2=3:
        a=1, b=1 -> floor(1/2 + 1/3) = floor(0.5 + 0.333) = floor(0.833) = 0
        But separate floors would give: 0 + 0 = 0 (same in this case).

        a=1, b=2 -> floor(1/2 + 2/3) = floor(0.5 + 0.666) = floor(1.166) = 1
        Separate floors: 0 + 0 = 0  (WRONG!)
        """
        self.app._hodge_init(0)
        n = self.app.hodge_n_states  # 100
        ill = n - 1
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        # a=1 infected neighbor, b=2 ill neighbors around (5,5)
        self.app.hodge_grid[4][4] = 1   # infected
        self.app.hodge_grid[4][5] = ill  # ill
        self.app.hodge_grid[4][6] = ill  # ill
        self.app._hodge_step()
        # k1=2, k2=3: floor(1/2 + 2/3) = floor(1.166) = 1
        assert self.app.hodge_grid[5][5] == 1

    def test_healthy_cell_clamped_to_ill(self):
        """Healthy cell new value is clamped to n-1 (ill)."""
        self.app._hodge_init(0)
        n = self.app.hodge_n_states
        ill = n - 1
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        # Use very small n_states so it's easy to exceed
        self.app.hodge_n_states = 3
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        # All 8 neighbors are ill (state 2)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                self.app.hodge_grid[5 + dr][5 + dc] = 2  # ill
        self.app._hodge_step()
        # floor(0/k1 + 8/k2) could exceed n-1=2, should be clamped
        assert self.app.hodge_grid[5][5] <= 2

    # ── Infected cell rule: min(n-1, floor(S/C + g)) ──

    def test_infected_cell_progression(self):
        """An infected cell with no infected neighbors progresses by g.

        For an isolated infected cell (state s) with all healthy neighbors:
        S = s (self only), C = 1 (self only).
        new_state = min(n-1, s//1 + g) = min(n-1, s + g).
        """
        self.app._hodge_init(0)
        n = self.app.hodge_n_states  # 100
        g = self.app.hodge_g  # 28
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        self.app.hodge_grid[5][5] = 10  # infected
        self.app._hodge_step()
        # S=10, C=1 -> min(99, 10//1 + 28) = min(99, 38) = 38
        assert self.app.hodge_grid[5][5] == 38

    def test_infected_cell_includes_self_in_average(self):
        """The infected cell calculation includes the cell itself in S and C."""
        self.app._hodge_init(0)
        n = self.app.hodge_n_states  # 100
        g = self.app.hodge_g  # 28
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        self.app.hodge_grid[5][5] = 10  # infected, self
        self.app.hodge_grid[4][5] = 20  # infected neighbor
        self.app._hodge_step()
        # S = 10 + 20 = 30, C = 2
        # min(99, 30//2 + 28) = min(99, 15 + 28) = 43
        assert self.app.hodge_grid[5][5] == 43

    def test_infected_cell_clamped_to_ill(self):
        """Infected cell cannot exceed n-1."""
        self.app._hodge_init(0)
        n = self.app.hodge_n_states  # 100
        ill = n - 1
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        # High state infected cell with high g => would exceed n-1
        self.app.hodge_grid[5][5] = 90  # close to ill
        self.app._hodge_step()
        # S=90, C=1 -> min(99, 90 + 28) = 99
        assert self.app.hodge_grid[5][5] == ill

    def test_infected_cell_averages_only_nonzero_neighbors(self):
        """Infected cell only counts non-zero neighbors in the average."""
        self.app._hodge_init(0)
        n = self.app.hodge_n_states  # 100
        g = self.app.hodge_g  # 28
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        self.app.hodge_grid[5][5] = 10   # self
        self.app.hodge_grid[4][5] = 50   # neighbor 1
        self.app.hodge_grid[6][5] = 50   # neighbor 2
        # Other 6 neighbors are 0 (healthy) -> not counted
        self.app._hodge_step()
        # S = 10 + 50 + 50 = 110, C = 3
        # min(99, 110//3 + 28) = min(99, 36 + 28) = 64
        assert self.app.hodge_grid[5][5] == 64

    # ── Toroidal wrapping ──

    def test_toroidal_wrapping(self):
        """Cells at edges wrap around (toroidal grid)."""
        self.app._hodge_init(0)
        n = self.app.hodge_n_states
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        ill = n - 1
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        # Put ill cells at top-left corner neighbors that wrap
        self.app.hodge_grid[rows - 1][cols - 1] = ill  # wraps to be neighbor of (0,0)
        self.app.hodge_grid[rows - 1][0] = ill
        self.app.hodge_grid[0][cols - 1] = ill
        self.app._hodge_step()
        # Cell (0,0) should detect 3 ill neighbors via wrapping
        # floor(0/2 + 3/3) = floor(1.0) = 1
        assert self.app.hodge_grid[0][0] == 1

    # ── All presets initialize and step without error ──

    def test_all_presets_init_and_step(self):
        """Every preset initializes and runs 5 steps without error."""
        for i in range(len(self.app.HODGE_PRESETS)):
            self.app._hodge_init(i)
            for _ in range(5):
                self.app._hodge_step()
            assert self.app.hodge_generation == 5

    # ── State space invariant ──

    def test_states_within_bounds(self):
        """After many steps, all cell states remain in [0, n-1]."""
        self.app._hodge_init(0)
        for _ in range(20):
            self.app._hodge_step()
        n = self.app.hodge_n_states
        for row in self.app.hodge_grid:
            for val in row:
                assert 0 <= val < n, f"State {val} out of range [0, {n-1}]"

    # ── Stable all-zero grid ──

    def test_all_zero_grid_stays_zero(self):
        """A grid of all healthy cells remains all healthy forever."""
        self.app._hodge_init(0)
        rows, cols = self.app.hodge_rows, self.app.hodge_cols
        self.app.hodge_grid = [[0] * cols for _ in range(rows)]
        for _ in range(5):
            self.app._hodge_step()
        for row in self.app.hodge_grid:
            for val in row:
                assert val == 0

    # ── Generation counter ──

    def test_generation_increments(self):
        """Each step increments generation by 1."""
        self.app._hodge_init(0)
        assert self.app.hodge_generation == 0
        self.app._hodge_step()
        assert self.app.hodge_generation == 1
        self.app._hodge_step()
        assert self.app.hodge_generation == 2
