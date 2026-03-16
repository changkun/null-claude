"""Tests for the Grid class."""
import random
import pytest
from life.grid import Grid


class TestGridBasics:
    def setup_method(self):
        self.grid = Grid(10, 10)

    def test_initial_state(self):
        assert self.grid.rows == 10
        assert self.grid.cols == 10
        assert self.grid.generation == 0
        assert self.grid.population == 0
        assert self.grid.birth == {3}
        assert self.grid.survival == {2, 3}

    def test_set_alive(self):
        self.grid.set_alive(0, 0)
        assert self.grid.cells[0][0] == 1
        assert self.grid.population == 1

    def test_set_alive_idempotent(self):
        """Setting an already-alive cell alive doesn't double-count population."""
        self.grid.set_alive(3, 3)
        self.grid.set_alive(3, 3)
        assert self.grid.population == 1
        assert self.grid.cells[3][3] == 1

    def test_set_alive_out_of_bounds(self):
        """Out-of-bounds set_alive is silently ignored."""
        self.grid.set_alive(-1, 0)
        self.grid.set_alive(0, -1)
        self.grid.set_alive(10, 0)
        self.grid.set_alive(0, 10)
        assert self.grid.population == 0

    def test_set_dead(self):
        self.grid.set_alive(0, 0)
        self.grid.set_dead(0, 0)
        assert self.grid.cells[0][0] == 0
        assert self.grid.population == 0

    def test_set_dead_already_dead(self):
        """Setting an already-dead cell dead doesn't decrement population."""
        self.grid.set_dead(0, 0)
        assert self.grid.population == 0

    def test_set_dead_out_of_bounds(self):
        self.grid.set_dead(-1, 0)
        self.grid.set_dead(0, 100)
        assert self.grid.population == 0

    def test_is_alive(self):
        assert not self.grid.is_alive(0, 0)
        self.grid.set_alive(0, 0)
        assert self.grid.is_alive(0, 0)
        assert not self.grid.is_alive(-1, 0)
        assert not self.grid.is_alive(0, 100)

    def test_toggle(self):
        self.grid.toggle(5, 5)
        assert self.grid.cells[5][5] > 0
        self.grid.toggle(5, 5)
        assert self.grid.cells[5][5] == 0

    def test_clear(self):
        self.grid.set_alive(1, 1)
        self.grid.set_alive(2, 2)
        self.grid.clear()
        assert self.grid.population == 0
        assert self.grid.generation == 0

    def test_clear_resets_all_cells(self):
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                self.grid.set_alive(r, c)
        self.grid.clear()
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                assert self.grid.cells[r][c] == 0

    def test_load_pattern(self):
        self.grid.load_pattern("block")
        assert self.grid.population == 4

    def test_load_pattern_unknown(self):
        self.grid.load_pattern("nonexistent_pattern")
        assert self.grid.population == 0

    def test_load_pattern_with_offset_and_wrapping(self):
        """Pattern loaded with large offset wraps via modulo."""
        g = Grid(5, 5)
        # Block is 4 cells at (0,0),(0,1),(1,0),(1,1)
        g.load_pattern("block", offset_r=4, offset_c=4)
        assert g.population == 4
        # (0+4)%5=4, (1+4)%5=0 -- wraps around
        assert g.cells[4][4] > 0
        assert g.cells[4][0] > 0
        assert g.cells[0][4] > 0
        assert g.cells[0][0] > 0


# ── Neighbor counting tests ─────────────────────────────────────────────────

class TestNeighborCounting:
    """Deep tests for _count_neighbours with toroidal wrapping."""

    def test_center_cell_all_eight_neighbors(self):
        """Cell in center with all 8 neighbors alive."""
        g = Grid(5, 5)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                g.set_alive(2 + dr, 2 + dc)
        assert g._count_neighbours(2, 2) == 8

    def test_center_cell_no_neighbors(self):
        g = Grid(5, 5)
        g.set_alive(2, 2)  # itself doesn't count
        assert g._count_neighbours(2, 2) == 0

    def test_corner_wraps_toroidal(self):
        """Top-left corner (0,0) neighbors wrap around all edges on a torus."""
        g = Grid(5, 5)
        # Neighbor at bottom-right via wrapping: (4,4)
        g.set_alive(4, 4)
        assert g._count_neighbours(0, 0) == 1
        # Neighbor at bottom via wrapping: (4,0)
        g.set_alive(4, 0)
        assert g._count_neighbours(0, 0) == 2
        # Neighbor at right via wrapping: (0,4)
        g.set_alive(0, 4)
        assert g._count_neighbours(0, 0) == 3

    def test_corner_top_right_wraps(self):
        g = Grid(6, 6)
        # (0,5) top-right corner; neighbor (5,0) wraps from bottom-left
        g.set_alive(5, 0)
        assert g._count_neighbours(0, 5) == 1

    def test_edge_cell_wraps(self):
        """Cell on top edge wraps to bottom row for neighbor."""
        g = Grid(5, 5)
        g.set_alive(4, 2)  # bottom row, same col
        assert g._count_neighbours(0, 2) == 1

    def test_self_not_counted(self):
        """A cell never counts itself as a neighbor."""
        g = Grid(3, 3)
        g.set_alive(1, 1)
        assert g._count_neighbours(1, 1) == 0

    def test_all_corners_wrap_symmetrically(self):
        """Each corner of the grid should count 3 neighbors when its
        three toroidal-adjacent corners are alive."""
        g = Grid(4, 4)
        # Set all four corners alive
        for r in (0, 3):
            for c in (0, 3):
                g.set_alive(r, c)
        # Each corner should see the other 3 corners as neighbors
        assert g._count_neighbours(0, 0) == 3
        assert g._count_neighbours(0, 3) == 3
        assert g._count_neighbours(3, 0) == 3
        assert g._count_neighbours(3, 3) == 3

    def test_1x1_grid_wraps_all_directions(self):
        """On a 1x1 toroidal grid, all 8 directional offsets wrap to (0,0).
        The count_neighbours method counts each offset independently (no
        deduplication), and only skips (dr=0,dc=0). So an alive cell at
        (0,0) counts 8 -- this matches the original commit behavior."""
        g = Grid(1, 1)
        g.set_alive(0, 0)
        # All 8 offsets wrap to (0,0) which is alive -> count = 8
        assert g._count_neighbours(0, 0) == 8

    def test_2x2_grid_wraps_count(self):
        """On a 2x2 fully alive grid with toroidal wrapping, each offset
        direction maps to one of the 4 cells (with repeats). All 8
        directions land on alive cells, so count is 8."""
        g = Grid(2, 2)
        for r in range(2):
            for c in range(2):
                g.set_alive(r, c)
        # Every offset lands on an alive cell -> count = 8
        for r in range(2):
            for c in range(2):
                assert g._count_neighbours(r, c) == 8

    def test_neighbor_count_matches_manual(self):
        """Manually verify neighbor count for a specific configuration."""
        g = Grid(5, 5)
        # L-shaped pattern around (2,2)
        g.set_alive(1, 1)
        g.set_alive(1, 2)
        g.set_alive(2, 1)
        # (2,2) neighbors: (1,1)=alive, (1,2)=alive, (1,3)=dead,
        # (2,1)=alive, (2,3)=dead, (3,1)=dead, (3,2)=dead, (3,3)=dead
        assert g._count_neighbours(2, 2) == 3


# ── Step behavior tests ─────────────────────────────────────────────────────

class TestGridStep:
    def test_blinker_oscillates(self):
        g = Grid(5, 5)
        # Horizontal blinker at center
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        g.step()
        # Should become vertical
        assert g.cells[1][2] > 0
        assert g.cells[2][2] > 0
        assert g.cells[3][2] > 0
        assert g.cells[2][1] == 0
        assert g.cells[2][3] == 0
        assert g.generation == 1

    def test_blinker_period2(self):
        """Blinker returns to original state after 2 steps."""
        g = Grid(5, 5)
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        g.step()
        g.step()
        assert g.cells[2][1] > 0
        assert g.cells[2][2] > 0
        assert g.cells[2][3] > 0
        assert g.cells[1][2] == 0
        assert g.cells[3][2] == 0
        assert g.generation == 2

    def test_block_stable(self):
        g = Grid(5, 5)
        g.set_alive(1, 1)
        g.set_alive(1, 2)
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        g.step()
        assert g.population == 4
        assert g.cells[1][1] > 0

    def test_block_stable_many_generations(self):
        """Block is a still life -- stays identical for many generations."""
        g = Grid(6, 6)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        g.set_alive(3, 2)
        g.set_alive(3, 3)
        for _ in range(50):
            g.step()
        assert g.population == 4
        assert g.cells[2][2] > 0
        assert g.cells[2][3] > 0
        assert g.cells[3][2] > 0
        assert g.cells[3][3] > 0

    def test_cell_aging(self):
        g = Grid(5, 5)
        # Block stays alive, ages
        g.set_alive(1, 1)
        g.set_alive(1, 2)
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        g.step()
        assert g.cells[1][1] == 2  # age increments

    def test_cell_aging_accumulates(self):
        """After N steps on a still life, age should be N+1."""
        g = Grid(6, 6)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        g.set_alive(3, 2)
        g.set_alive(3, 3)
        for i in range(10):
            g.step()
            assert g.cells[2][2] == i + 2

    def test_newborn_cell_has_age_1(self):
        """A cell born from 3 neighbors gets age 1."""
        g = Grid(5, 5)
        g.set_alive(0, 1)
        g.set_alive(1, 0)
        g.set_alive(1, 1)
        # (0,0) has 3 neighbors: (0,1), (1,0), (1,1) -> born
        g.step()
        assert g.cells[0][0] == 1

    def test_step_updates_generation(self):
        g = Grid(5, 5)
        g.step()
        assert g.generation == 1
        g.step()
        assert g.generation == 2

    def test_step_updates_population(self):
        """Population count is accurate after step."""
        g = Grid(5, 5)
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        g.step()
        # Blinker always has pop 3
        assert g.population == 3

    def test_empty_grid_stays_empty(self):
        g = Grid(5, 5)
        g.step()
        assert g.population == 0
        assert g.generation == 1

    def test_single_cell_dies(self):
        """A lone cell with 0 neighbors dies (underpopulation)."""
        g = Grid(10, 10)
        g.set_alive(5, 5)
        g.step()
        assert g.cells[5][5] == 0
        assert g.population == 0

    def test_two_adjacent_cells_die(self):
        """Two adjacent cells each have only 1 neighbor, so both die."""
        g = Grid(10, 10)
        g.set_alive(5, 5)
        g.set_alive(5, 6)
        g.step()
        assert g.population == 0

    def test_overcrowding(self):
        """A cell with 4+ neighbors dies from overcrowding."""
        g = Grid(5, 5)
        # Cross pattern: center cell has 4 neighbors
        g.set_alive(2, 2)
        g.set_alive(1, 2)
        g.set_alive(3, 2)
        g.set_alive(2, 1)
        g.set_alive(2, 3)
        g.step()
        # Center had 4 neighbors -> dies
        assert g.cells[2][2] == 0

    def test_survival_with_2_neighbors(self):
        """An alive cell with exactly 2 neighbors survives."""
        g = Grid(5, 5)
        # Horizontal line of 3
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        # Center cell (2,2) has 2 neighbors -> survives
        g.step()
        assert g.cells[2][2] > 0

    def test_survival_with_3_neighbors(self):
        """An alive cell with exactly 3 neighbors survives."""
        g = Grid(5, 5)
        g.set_alive(1, 1)
        g.set_alive(1, 2)
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        # (1,1) has neighbors: (1,2), (2,1), (2,2) = 3 -> survives
        g.step()
        assert g.cells[1][1] > 0

    def test_birth_with_exactly_3(self):
        """A dead cell with exactly 3 neighbors is born."""
        g = Grid(5, 5)
        g.set_alive(1, 1)
        g.set_alive(1, 2)
        g.set_alive(2, 1)
        # (2,2) has neighbors (1,1), (1,2), (2,1) = 3 -> born
        g.step()
        assert g.cells[2][2] == 1

    def test_no_birth_with_2_neighbors(self):
        """A dead cell with exactly 2 neighbors stays dead."""
        g = Grid(10, 10)
        g.set_alive(5, 5)
        g.set_alive(5, 6)
        # (5,7) has neighbor (5,6) = 1; (4,5) has neighbors (5,5) = 1
        # (4,6) has neighbors (5,5),(5,6) = 2 -> stays dead
        g.step()
        assert g.cells[4][6] == 0

    def test_glider_moves(self):
        """Glider pattern moves one cell diagonally after 4 generations."""
        g = Grid(10, 10)
        # Standard glider
        g.set_alive(0, 1)
        g.set_alive(1, 2)
        g.set_alive(2, 0)
        g.set_alive(2, 1)
        g.set_alive(2, 2)
        for _ in range(4):
            g.step()
        # After 4 steps, glider moves down 1, right 1
        assert g.cells[1][2] > 0
        assert g.cells[2][3] > 0
        assert g.cells[3][1] > 0
        assert g.cells[3][2] > 0
        assert g.cells[3][3] > 0
        assert g.population == 5

    def test_glider_wraps_on_torus(self):
        """Glider wraps around edges on a toroidal grid."""
        g = Grid(6, 6)
        # Place glider near bottom-right
        g.set_alive(4, 4)
        g.set_alive(4, 5)
        g.set_alive(4, 3)
        g.set_alive(3, 5)
        g.set_alive(2, 4)
        # Run enough steps for it to wrap
        for _ in range(20):
            g.step()
        # Should still have 5 cells (glider is preserved on torus)
        assert g.population == 5

    def test_beehive_still_life(self):
        """Beehive is a still life."""
        g = Grid(6, 6)
        g.set_alive(1, 2)
        g.set_alive(1, 3)
        g.set_alive(2, 1)
        g.set_alive(2, 4)
        g.set_alive(3, 2)
        g.set_alive(3, 3)
        pop_before = g.population
        g.step()
        assert g.population == pop_before

    def test_toad_oscillator(self):
        """Toad is a period-2 oscillator."""
        g = Grid(6, 6)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        g.set_alive(2, 4)
        g.set_alive(3, 1)
        g.set_alive(3, 2)
        g.set_alive(3, 3)
        h0 = g.state_hash()
        g.step()
        h1 = g.state_hash()
        assert h0 != h1
        g.step()
        h2 = g.state_hash()
        assert h0 == h2  # period 2


# ── Wrap-around edge case tests ─────────────────────────────────────────────

class TestWrapAround:
    def test_blinker_at_top_edge_wraps(self):
        """Horizontal blinker at row 0 wraps neighbor counting to bottom."""
        g = Grid(5, 5)
        g.set_alive(0, 1)
        g.set_alive(0, 2)
        g.set_alive(0, 3)
        g.step()
        # Becomes vertical: (4,2), (0,2), (1,2)
        assert g.cells[4][2] > 0  # wrapped to bottom
        assert g.cells[0][2] > 0
        assert g.cells[1][2] > 0
        assert g.population == 3

    def test_blinker_at_left_edge_wraps(self):
        """Vertical blinker at col 0 wraps to right edge."""
        g = Grid(5, 5)
        g.set_alive(1, 0)
        g.set_alive(2, 0)
        g.set_alive(3, 0)
        g.step()
        # Becomes horizontal: (2,4), (2,0), (2,1)
        assert g.cells[2][4] > 0  # wrapped to right
        assert g.cells[2][0] > 0
        assert g.cells[2][1] > 0
        assert g.population == 3

    def test_block_at_corner_wraps(self):
        """Block spanning grid corners is still stable via wrapping."""
        g = Grid(4, 4)
        # Place block at top-left corner, wrapping around all edges
        g.set_alive(0, 0)
        g.set_alive(0, 3)  # wraps to left of (0,0)
        g.set_alive(3, 0)  # wraps to above (0,0)
        g.set_alive(3, 3)  # wraps to diagonal
        # Each cell has exactly 3 neighbors (the other 3 corners)
        # This forms a stable block on a 4x4 torus
        g.step()
        assert g.population == 4
        assert g.cells[0][0] > 0
        assert g.cells[0][3] > 0
        assert g.cells[3][0] > 0
        assert g.cells[3][3] > 0


# ── Topology tests ───────────────────────────────────────────────────────────

class TestGridTopology:
    def test_torus_wrap(self):
        g = Grid(5, 5)
        assert g._wrap(-1, -1) == (4, 4)
        assert g._wrap(5, 5) == (0, 0)

    def test_torus_wrap_large_negative(self):
        g = Grid(5, 5)
        assert g._wrap(-6, -6) == (4, 4)

    def test_plane_no_wrap(self):
        g = Grid(5, 5)
        g.topology = Grid.TOPO_PLANE
        assert g._wrap(-1, 0) is None
        assert g._wrap(0, 0) == (0, 0)

    def test_plane_all_edges(self):
        g = Grid(5, 5)
        g.topology = Grid.TOPO_PLANE
        assert g._wrap(0, -1) is None
        assert g._wrap(5, 0) is None
        assert g._wrap(0, 5) is None
        assert g._wrap(4, 4) == (4, 4)

    def test_plane_corner_cell_fewer_neighbors(self):
        """On a plane, corner cell should have at most 3 neighbors."""
        g = Grid(5, 5)
        g.topology = Grid.TOPO_PLANE
        # Fill all cells
        for r in range(5):
            for c in range(5):
                g.set_alive(r, c)
        # Corner (0,0) has only 3 in-bounds neighbors
        assert g._count_neighbours(0, 0) == 3

    def test_plane_edge_cell_fewer_neighbors(self):
        """On a plane, edge cell should have at most 5 neighbors."""
        g = Grid(5, 5)
        g.topology = Grid.TOPO_PLANE
        for r in range(5):
            for c in range(5):
                g.set_alive(r, c)
        # Edge (0,2) has 5 in-bounds neighbors
        assert g._count_neighbours(0, 2) == 5

    def test_klein_bottle(self):
        g = Grid(5, 5)
        g.topology = Grid.TOPO_KLEIN
        coord = g._wrap(-1, 2)
        assert coord is not None
        assert coord[0] == 4  # wrapped row

    def test_klein_bottle_column_flip(self):
        """Klein bottle flips column when row wraps."""
        g = Grid(5, 5)
        g.topology = Grid.TOPO_KLEIN
        # Row wraps from -1 to 4, col 2 flips to 4-2=2 -> (4,2)
        coord = g._wrap(-1, 2)
        assert coord == (4, 2)
        # Row wraps from 5 to 0, col 1 flips to 4-1=3 -> (0,3)
        coord2 = g._wrap(5, 1)
        assert coord2 == (0, 3)

    def test_mobius_strip(self):
        g = Grid(5, 5)
        g.topology = Grid.TOPO_MOBIUS
        assert g._wrap(-1, 2) is None  # rows don't wrap
        coord = g._wrap(2, -1)
        assert coord is not None

    def test_mobius_vertical_flip(self):
        """Mobius strip flips row when column wraps."""
        g = Grid(5, 5)
        g.topology = Grid.TOPO_MOBIUS
        # col -1 wraps to 4, row 2 flips to 4-2=2 -> (2,4)
        coord = g._wrap(2, -1)
        assert coord == (2, 4)
        # col 5 wraps to 0, row 1 flips to 4-1=3 -> (3,0)
        coord2 = g._wrap(1, 5)
        assert coord2 == (3, 0)

    def test_projective_plane(self):
        g = Grid(5, 5)
        g.topology = Grid.TOPO_PROJECTIVE
        coord = g._wrap(-1, 2)
        assert coord is not None
        coord2 = g._wrap(2, -1)
        assert coord2 is not None


class TestGridHex:
    def test_hex_neighbour_count(self):
        g = Grid(10, 10)
        g.hex_mode = True
        # Set some neighbors for cell (4, 4)
        g.set_alive(3, 4)
        g.set_alive(3, 5)
        n = g._count_neighbours(4, 4)
        assert n == 2

    def test_hex_max_six_neighbors(self):
        """Hex mode has at most 6 neighbors."""
        g = Grid(10, 10)
        g.hex_mode = True
        # Fill all cells
        for r in range(10):
            for c in range(10):
                g.set_alive(r, c)
        # Center cell should have exactly 6 neighbors
        assert g._count_neighbours(5, 5) == 6

    def test_hex_even_vs_odd_row(self):
        """Even and odd rows have different neighbor offsets in hex mode."""
        g = Grid(10, 10)
        g.hex_mode = True
        # For even row (4): neighbors include (3,4),(3,5),(4,3),(4,5),(5,4),(5,5)
        g.set_alive(3, 5)
        assert g._count_neighbours(4, 4) == 1
        g.clear()
        # For odd row (5): neighbors include (4,3),(4,4),(5,3),(5,5),(6,3),(6,4)  -- different offsets
        g.set_alive(4, 4)
        assert g._count_neighbours(5, 4) == 1


class TestGridSerialization:
    def test_to_dict_load_dict_roundtrip(self):
        g = Grid(10, 10)
        g.set_alive(1, 2)
        g.set_alive(3, 4)
        g.generation = 42
        d = g.to_dict()
        g2 = Grid(10, 10)
        g2.load_dict(d)
        assert g2.generation == 42
        assert g2.population == 2
        assert g2.cells[1][2] > 0
        assert g2.cells[3][4] > 0

    def test_to_dict_preserves_ages(self):
        """Serialization preserves cell ages."""
        g = Grid(6, 6)
        g.set_alive(2, 2)
        g.set_alive(2, 3)
        g.set_alive(3, 2)
        g.set_alive(3, 3)
        for _ in range(5):
            g.step()
        d = g.to_dict()
        g2 = Grid(6, 6)
        g2.load_dict(d)
        assert g2.cells[2][2] == 6  # age = initial 1 + 5 steps

    def test_to_dict_preserves_rule(self):
        """Serialization preserves custom rules."""
        g = Grid(5, 5)
        g.birth = {3, 6}
        g.survival = {2, 3}
        d = g.to_dict()
        g2 = Grid(5, 5)
        g2.load_dict(d)
        assert g2.birth == {3, 6}
        assert g2.survival == {2, 3}

    def test_load_dict_out_of_bounds_cells_ignored(self):
        """Loading cells that exceed grid dimensions are safely ignored."""
        g = Grid(5, 5)
        data = {
            "rows": 5, "cols": 5, "generation": 0,
            "cells": [(10, 10, 1), (2, 2, 1)],
        }
        g.load_dict(data)
        assert g.population == 1
        assert g.cells[2][2] == 1

    def test_state_hash_deterministic(self):
        g = Grid(5, 5)
        g.set_alive(1, 1)
        h1 = g.state_hash()
        h2 = g.state_hash()
        assert h1 == h2

    def test_state_hash_changes(self):
        g = Grid(5, 5)
        g.set_alive(1, 1)
        h1 = g.state_hash()
        g.set_alive(2, 2)
        h2 = g.state_hash()
        assert h1 != h2

    def test_state_hash_empty_grid(self):
        g = Grid(5, 5)
        h = g.state_hash()
        assert isinstance(h, str) and len(h) > 0

    def test_state_hash_position_sensitive(self):
        """Different positions produce different hashes."""
        g1 = Grid(5, 5)
        g1.set_alive(1, 2)
        g2 = Grid(5, 5)
        g2.set_alive(2, 1)
        assert g1.state_hash() != g2.state_hash()


# ── Custom rules tests ──────────────────────────────────────────────────────

class TestCustomRules:
    def test_highlife_replicator_rule(self):
        """HighLife (B36/S23) allows birth on 6 neighbors too."""
        g = Grid(10, 10)
        g.birth = {3, 6}
        g.survival = {2, 3}
        # Simple test: 3-neighbor birth still works
        g.set_alive(4, 4)
        g.set_alive(4, 5)
        g.set_alive(5, 4)
        g.step()
        assert g.cells[5][5] == 1  # born with 3 neighbors

    def test_seeds_rule(self):
        """Seeds (B2/S) -- cells are born with 2 neighbors, none survive."""
        g = Grid(10, 10)
        g.birth = {2}
        g.survival = set()
        g.set_alive(5, 5)
        g.set_alive(5, 6)
        g.step()
        # All alive cells die (no survival); cells with 2 neighbors born
        assert g.cells[5][5] == 0
        assert g.cells[5][6] == 0
        # (4,5) and (6,5) each had 2 neighbors -> born? Let's check:
        # (4,5) neighbors: (5,5)=alive,(5,6)=alive -> 2, born!
        assert g.cells[4][5] == 1 or g.cells[4][6] == 1

    def test_day_and_night_rule(self):
        """Day and Night (B3678/S34678)."""
        g = Grid(10, 10)
        g.birth = {3, 6, 7, 8}
        g.survival = {3, 4, 6, 7, 8}
        # Just verify step runs without error
        g.set_alive(5, 5)
        g.step()
        assert g.generation == 1


# ── Population tracking accuracy ─────────────────────────────────────────────

class TestPopulationTracking:
    def test_population_matches_cell_count(self):
        """grid.population always matches actual count of alive cells."""
        random.seed(42)
        g = Grid(20, 20)
        for r in range(20):
            for c in range(20):
                if random.random() < 0.3:
                    g.set_alive(r, c)
        for _ in range(10):
            g.step()
            actual = sum(1 for r in range(20) for c in range(20) if g.cells[r][c] > 0)
            assert g.population == actual, f"gen {g.generation}: pop={g.population}, actual={actual}"

    def test_population_after_clear_and_reload(self):
        g = Grid(10, 10)
        g.load_pattern("glider")
        assert g.population == 5
        g.clear()
        assert g.population == 0
        g.load_pattern("blinker")
        assert g.population == 3
