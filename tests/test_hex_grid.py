"""Tests for hex_grid mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.hex_grid import register
from life.grid import Grid
from life.constants import HEX_NEIGHBORS_EVEN, HEX_NEIGHBORS_ODD


class TestHexGrid:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_hex_browser()
        assert self.app.hex_mode is True
        assert self.app.grid.hex_mode is True
        assert self.app.grid.birth == {2}
        assert self.app.grid.survival == {3, 4}

    def test_step_no_crash(self):
        self.app._enter_hex_browser()
        # The hex mode uses the grid's step, seed some cells
        self.app.grid.set_alive(5, 5)
        self.app.grid.set_alive(5, 6)
        self.app.grid.set_alive(6, 5)
        for _ in range(10):
            self.app.grid.step()

    def test_exit_cleanup(self):
        self.app._enter_hex_browser()
        self.app._exit_hex_browser()
        assert self.app.hex_mode is False
        assert self.app.grid.hex_mode is False
        assert self.app.grid.birth == {3}
        assert self.app.grid.survival == {2, 3}

    def test_hex_mode_initialized_on_mock_app(self):
        """hex_mode should be pre-initialized to False on the mock app."""
        assert self.app.hex_mode is False


class TestHexNeighborConstants:
    """Verify the hex neighbor offset tables have proper 6-neighbor topology."""

    def test_even_row_has_six_neighbors(self):
        assert len(HEX_NEIGHBORS_EVEN) == 6

    def test_odd_row_has_six_neighbors(self):
        assert len(HEX_NEIGHBORS_ODD) == 6

    def test_even_row_offsets_are_unique(self):
        assert len(set(HEX_NEIGHBORS_EVEN)) == 6

    def test_odd_row_offsets_are_unique(self):
        assert len(set(HEX_NEIGHBORS_ODD)) == 6

    def test_no_self_offset(self):
        """(0,0) must not appear in either offset list."""
        assert (0, 0) not in HEX_NEIGHBORS_EVEN
        assert (0, 0) not in HEX_NEIGHBORS_ODD

    def test_offsets_are_adjacent(self):
        """All offsets should be within Manhattan distance 2 (dr,dc each -1..1)."""
        for dr, dc in HEX_NEIGHBORS_EVEN + HEX_NEIGHBORS_ODD:
            assert -1 <= dr <= 1, f"Unexpected dr={dr}"
            assert -1 <= dc <= 1, f"Unexpected dc={dc}"


class TestHexCountNeighbours:
    """Verify _count_neighbours returns correct counts in hex mode."""

    def setup_method(self):
        self.grid = Grid(20, 20)
        self.grid.hex_mode = True
        self.grid.birth = {2}
        self.grid.survival = {3, 4}

    def test_isolated_cell_zero_neighbors(self):
        """A lone cell at (10,10) should have 0 neighbors."""
        self.grid.set_alive(10, 10)
        assert self.grid._count_neighbours(10, 10) == 0

    def test_even_row_neighbor_count(self):
        """Place all 6 neighbors of an even-row cell, verify count is 6."""
        r, c = 10, 10  # even row
        for dr, dc in HEX_NEIGHBORS_EVEN:
            self.grid.set_alive(r + dr, c + dc)
        assert self.grid._count_neighbours(r, c) == 6

    def test_odd_row_neighbor_count(self):
        """Place all 6 neighbors of an odd-row cell, verify count is 6."""
        r, c = 11, 10  # odd row
        for dr, dc in HEX_NEIGHBORS_ODD:
            self.grid.set_alive(r + dr, c + dc)
        assert self.grid._count_neighbours(r, c) == 6

    def test_even_row_partial_neighbors(self):
        """Place 3 of 6 neighbors for an even-row cell."""
        r, c = 10, 10
        for dr, dc in HEX_NEIGHBORS_EVEN[:3]:
            self.grid.set_alive(r + dr, c + dc)
        assert self.grid._count_neighbours(r, c) == 3

    def test_odd_row_partial_neighbors(self):
        """Place 2 of 6 neighbors for an odd-row cell."""
        r, c = 11, 10
        for dr, dc in HEX_NEIGHBORS_ODD[:2]:
            self.grid.set_alive(r + dr, c + dc)
        assert self.grid._count_neighbours(r, c) == 2

    def test_non_hex_neighbor_not_counted(self):
        """A diagonal cell that is a Moore neighbor but NOT a hex neighbor
        should not be counted."""
        r, c = 10, 10  # even row
        # (-1, -1) is NOT in HEX_NEIGHBORS_EVEN (it IS in ODD)
        self.grid.set_alive(r - 1, c - 1)
        assert self.grid._count_neighbours(r, c) == 0

    def test_hex_vs_moore_different_counts(self):
        """With all 8 Moore neighbors alive, hex mode should count exactly 6."""
        r, c = 10, 10
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                self.grid.set_alive(r + dr, c + dc)
        # Hex mode sees only 6 of the 8 Moore neighbors
        count = self.grid._count_neighbours(r, c)
        assert count == 6

    def test_wrapping_at_edges(self):
        """Hex neighbors should wrap at grid boundaries (torus topology)."""
        r, c = 0, 0  # corner cell, even row
        for dr, dc in HEX_NEIGHBORS_EVEN:
            nr = (r + dr) % self.grid.rows
            nc = (c + dc) % self.grid.cols
            self.grid.set_alive(nr, nc)
        assert self.grid._count_neighbours(r, c) == 6


class TestHexSimulation:
    """Integration tests: verify hex simulation dynamics."""

    def setup_method(self):
        self.grid = Grid(20, 20)
        self.grid.hex_mode = True
        self.grid.birth = {2}
        self.grid.survival = {3, 4}

    def test_isolated_cell_dies(self):
        """A single cell with 0 neighbors should die (0 not in survival={3,4})."""
        self.grid.set_alive(10, 10)
        self.grid.step()
        assert self.grid.cells[10][10] == 0

    def test_pair_births_common_neighbors(self):
        """Two adjacent hex cells should birth into cells that see exactly 2 neighbors."""
        r, c = 10, 10  # even row
        self.grid.set_alive(r, c)
        self.grid.set_alive(r, c + 1)
        self.grid.step()
        # The pair each had 1 neighbor, not in survival={3,4}, so they die.
        # Cells adjacent to both of them had 2 neighbors -> birth.
        assert self.grid.population > 0

    def test_empty_grid_stays_empty(self):
        """An empty grid should remain empty after stepping."""
        self.grid.step()
        assert self.grid.population == 0

    def test_generation_increments(self):
        """Generation counter should increment each step."""
        self.grid.set_alive(10, 10)
        self.grid.step()
        assert self.grid.generation == 1
        self.grid.step()
        assert self.grid.generation == 2

    def test_many_steps_no_crash(self):
        """Run 50 steps with a random seed -- should not crash."""
        random.seed(123)
        for _ in range(30):
            r = random.randint(0, 19)
            c = random.randint(0, 19)
            self.grid.set_alive(r, c)
        for _ in range(50):
            self.grid.step()

    def test_symmetry_even_odd_row_reciprocal(self):
        """If B is a hex-neighbor of A, then A is a hex-neighbor of B.
        This verifies the even/odd offset tables are reciprocal."""
        # Check every cell in a 10x10 interior region
        for r in range(2, 12):
            for c in range(2, 12):
                offsets = HEX_NEIGHBORS_EVEN if r % 2 == 0 else HEX_NEIGHBORS_ODD
                for dr, dc in offsets:
                    nr, nc = r + dr, c + dc
                    # nr's offset table
                    nb_offsets = HEX_NEIGHBORS_EVEN if nr % 2 == 0 else HEX_NEIGHBORS_ODD
                    reverse = (r - nr, c - nc)
                    assert reverse in nb_offsets, (
                        f"Cell ({r},{c}) -> ({nr},{nc}) via ({dr},{dc}), "
                        f"but reverse ({reverse}) not in offsets for row {nr}"
                    )
