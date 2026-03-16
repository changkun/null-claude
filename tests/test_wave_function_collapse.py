"""Tests for wave_function_collapse mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.wave_function_collapse import register


def _make_wfc_app():
    """Create and configure a mock app with WFC registered."""
    app = make_mock_app()
    cls = type(app)
    register(cls)
    cls.WFC_PRESETS = [
        ("Island", "Land masses surrounded by ocean",
         5, ["water", "sand", "grass", "forest", "mountain"],
         {
             0: {"N": {0, 1}, "S": {0, 1}, "E": {0, 1}, "W": {0, 1}},
             1: {"N": {0, 1, 2}, "S": {0, 1, 2}, "E": {0, 1, 2}, "W": {0, 1, 2}},
             2: {"N": {1, 2, 3}, "S": {1, 2, 3}, "E": {1, 2, 3}, "W": {1, 2, 3}},
             3: {"N": {2, 3, 4}, "S": {2, 3, 4}, "E": {2, 3, 4}, "W": {2, 3, 4}},
             4: {"N": {3, 4}, "S": {3, 4}, "E": {3, 4}, "W": {3, 4}},
         }),
        ("SimpleTwoTile", "Only two tiles that can be anywhere",
         2, ["A", "B"],
         {
             0: {"N": {0, 1}, "S": {0, 1}, "E": {0, 1}, "W": {0, 1}},
             1: {"N": {0, 1}, "S": {0, 1}, "E": {0, 1}, "W": {0, 1}},
         }),
    ]
    cls.WFC_TILE_CHARS = [
        ("..", 2), ("##", 4), ("~~", 3), ("^^", 1), ("MM", 6),
        ("~~", 4), ("##", 5), ("HH", 7), ("==", 4), ("..", 2),
    ]
    cls.WFC_PRESET_TILES = [
        [1, 2, 0, 3, 4],  # Island
        [0, 1],            # SimpleTwoTile
    ]
    cls.WFC_UNCOLLAPSED_CHAR = "??"
    # Instance attrs
    app.wfc_mode = False
    app.wfc_menu = False
    app.wfc_menu_sel = 0
    app.wfc_running = False
    app.wfc_grid = []
    app.wfc_collapsed = []
    app.wfc_steps_per_frame = 1
    return app


class TestWFCEntryExit:
    """Tests for entering and exiting WFC mode."""

    def test_enter_sets_menu_flag(self):
        app = _make_wfc_app()
        app._enter_wfc_mode()
        assert app.wfc_menu is True
        assert app.wfc_menu_sel == 0

    def test_exit_clears_all_state(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        assert app.wfc_mode is True
        assert len(app.wfc_grid) > 0
        app._exit_wfc_mode()
        assert app.wfc_mode is False
        assert app.wfc_menu is False
        assert app.wfc_running is False
        assert app.wfc_grid == []
        assert app.wfc_collapsed == []


class TestWFCInit:
    """Tests for _wfc_init initialization logic."""

    def test_grid_dimensions(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        rows, cols = app.wfc_rows, app.wfc_cols
        assert rows >= 5
        assert cols >= 5
        assert len(app.wfc_grid) == rows
        assert len(app.wfc_grid[0]) == cols
        assert len(app.wfc_collapsed) == rows
        assert len(app.wfc_collapsed[0]) == cols

    def test_all_cells_start_uncollapsed(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        for r in range(app.wfc_rows):
            for c in range(app.wfc_cols):
                assert app.wfc_collapsed[r][c] == -1

    def test_all_cells_start_with_full_possibilities(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        all_tiles = set(range(app.wfc_num_tiles))
        for r in range(app.wfc_rows):
            for c in range(app.wfc_cols):
                assert app.wfc_grid[r][c] == all_tiles

    def test_adjacency_is_symmetric(self):
        """If tile A allows tile B to its North, tile B must allow A to its South."""
        app = _make_wfc_app()
        app._wfc_init(0)
        adj = app.wfc_adjacency
        opposites = {"N": "S", "S": "N", "E": "W", "W": "E"}
        for t in range(app.wfc_num_tiles):
            for d in ("N", "S", "E", "W"):
                od = opposites[d]
                for neighbor in adj[t][d]:
                    assert t in adj[neighbor][od], (
                        f"Asymmetry: tile {t} allows {neighbor} to its {d}, "
                        f"but tile {neighbor} does not allow {t} to its {od}"
                    )

    def test_generation_starts_at_zero(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        assert app.wfc_generation == 0
        assert app.wfc_contradiction is False
        assert app.wfc_complete is False

    def test_second_preset_init(self):
        app = _make_wfc_app()
        app._wfc_init(1)
        assert app.wfc_preset_name == "SimpleTwoTile"
        assert app.wfc_num_tiles == 2
        all_tiles = {0, 1}
        for r in range(app.wfc_rows):
            for c in range(app.wfc_cols):
                assert app.wfc_grid[r][c] == all_tiles


class TestWFCStep:
    """Tests for _wfc_step collapse logic."""

    def test_step_collapses_one_cell(self):
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)
        app._wfc_step()
        assert app.wfc_generation == 1
        # At least one cell should now be collapsed
        collapsed_count = sum(
            1 for r in range(app.wfc_rows)
            for c in range(app.wfc_cols)
            if app.wfc_collapsed[r][c] != -1
        )
        assert collapsed_count >= 1

    def test_step_picks_lowest_entropy(self):
        """Manually set up a grid where one cell has lower entropy, verify it gets picked."""
        random.seed(99)
        app = _make_wfc_app()
        app._wfc_init(1)  # SimpleTwoTile: all tiles compatible
        rows, cols = app.wfc_rows, app.wfc_cols
        # Set one specific cell to have only 1 possibility (lowest entropy)
        app.wfc_grid[0][0] = {0}
        # All other cells still have {0, 1}
        app._wfc_step()
        # Cell (0,0) should be collapsed since it had lowest entropy (1)
        assert app.wfc_collapsed[0][0] == 0

    def test_step_noop_when_complete(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        app.wfc_complete = True
        gen_before = app.wfc_generation
        app._wfc_step()
        assert app.wfc_generation == gen_before

    def test_step_noop_when_contradiction(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        app.wfc_contradiction = True
        gen_before = app.wfc_generation
        app._wfc_step()
        assert app.wfc_generation == gen_before

    def test_collapsed_tile_is_valid(self):
        """Every collapsed tile must be within the valid tile range."""
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)
        for _ in range(20):
            app._wfc_step()
            if app.wfc_contradiction:
                break
        for r in range(app.wfc_rows):
            for c in range(app.wfc_cols):
                t = app.wfc_collapsed[r][c]
                if t != -1:
                    assert 0 <= t < app.wfc_num_tiles

    def test_run_to_completion_simple_preset(self):
        """SimpleTwoTile (all compatible) should always complete without contradiction."""
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(1)
        max_steps = app.wfc_rows * app.wfc_cols + 10
        for _ in range(max_steps):
            if app.wfc_complete or app.wfc_contradiction:
                break
            app._wfc_step()
        assert app.wfc_complete is True
        assert app.wfc_contradiction is False


class TestWFCPropagation:
    """Tests for _wfc_propagate constraint propagation."""

    def test_propagation_reduces_neighbors(self):
        """After collapsing a cell, its neighbors' possibilities should be reduced."""
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)  # Island preset
        rows, cols = app.wfc_rows, app.wfc_cols
        # Force-collapse cell (2, 2) to tile 4 (mountain)
        app.wfc_grid[2][2] = {4}
        app.wfc_collapsed[2][2] = 4
        app._wfc_propagate(2, 2)
        # Mountain (tile 4) only allows {3, 4} as neighbors
        # So neighbors of (2,2) should not contain tiles 0, 1, 2
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = 2 + dr, 2 + dc
            if 0 <= nr < rows and 0 <= nc < cols and app.wfc_collapsed[nr][nc] == -1:
                assert app.wfc_grid[nr][nc].issubset({3, 4}), (
                    f"Cell ({nr},{nc}) has tiles {app.wfc_grid[nr][nc]} "
                    f"but should only have {{3, 4}} next to mountain"
                )

    def test_propagation_detects_contradiction(self):
        """Force a contradiction: set a cell's possibilities to empty."""
        app = _make_wfc_app()
        app._wfc_init(0)
        # Set up an impossible situation: collapse cell to mountain (4),
        # but manually set a neighbor to only allow water (0) -- incompatible
        app.wfc_grid[2][2] = {4}
        app.wfc_collapsed[2][2] = 4
        # Neighbor only allows water -- mountain can't be next to water
        app.wfc_grid[2][3] = {0}
        app._wfc_propagate(2, 2)
        # Mountain allows {3,4} as East neighbor, intersecting with {0} = empty
        assert app.wfc_contradiction is True

    def test_propagation_auto_collapses_single_option(self):
        """If propagation reduces a cell to 1 tile, it auto-collapses."""
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)
        # Force cell to mountain (tile 4), which allows {3,4} as neighbors.
        app.wfc_grid[2][2] = {4}
        app.wfc_collapsed[2][2] = 4
        # Set neighbor to {3, 4} (2 options). Mountain allows {3,4} to its East.
        # Intersection of {3,4} & {3,4} = {3,4} -- no reduction, so no auto-collapse.
        # Instead, set neighbor to {2, 4}: intersection with allowed {3,4} = {4} -> auto-collapse.
        app.wfc_grid[2][3] = {2, 4}
        app._wfc_propagate(2, 2)
        if not app.wfc_contradiction:
            # {2,4} intersected with allowed {3,4} = {4}, which is size 1 -> auto-collapse
            assert app.wfc_collapsed[2][3] == 4

    def test_propagation_cascades(self):
        """Propagation should cascade through multiple cells."""
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)
        # Collapse corner to mountain
        app.wfc_grid[0][0] = {4}
        app.wfc_collapsed[0][0] = 4
        app._wfc_propagate(0, 0)
        if not app.wfc_contradiction:
            # Cell (0,1) should have reduced possibilities
            assert len(app.wfc_grid[0][1]) < 5
            # Cell (1,0) should also have reduced possibilities
            assert len(app.wfc_grid[1][0]) < 5

    def test_propagation_respects_boundaries(self):
        """Propagation should not crash at grid edges."""
        app = _make_wfc_app()
        app._wfc_init(0)
        rows, cols = app.wfc_rows, app.wfc_cols
        # Collapse corner cells
        app.wfc_grid[0][0] = {2}
        app.wfc_collapsed[0][0] = 2
        app._wfc_propagate(0, 0)
        # Collapse opposite corner
        if not app.wfc_contradiction:
            app.wfc_grid[rows - 1][cols - 1] = {2}
            app.wfc_collapsed[rows - 1][cols - 1] = 2
            app._wfc_propagate(rows - 1, cols - 1)
        # No crash means boundaries are handled


class TestWFCAdjacencyConstraints:
    """Tests verifying adjacency rules are enforced in final output."""

    def test_completed_grid_respects_adjacency(self):
        """After full collapse, every pair of adjacent cells must satisfy adjacency rules."""
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(1)  # SimpleTwoTile: guaranteed to complete
        max_steps = app.wfc_rows * app.wfc_cols + 10
        for _ in range(max_steps):
            if app.wfc_complete or app.wfc_contradiction:
                break
            app._wfc_step()
        if app.wfc_complete:
            adj = app.wfc_adjacency
            rows, cols = app.wfc_rows, app.wfc_cols
            dirs = [(-1, 0, "N"), (1, 0, "S"), (0, 1, "E"), (0, -1, "W")]
            for r in range(rows):
                for c in range(cols):
                    tile = app.wfc_collapsed[r][c]
                    assert tile != -1, f"Cell ({r},{c}) not collapsed but wfc_complete is True"
                    for dr, dc, d in dirs:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            neighbor_tile = app.wfc_collapsed[nr][nc]
                            assert neighbor_tile in adj[tile][d], (
                                f"Adjacency violation: tile {tile} at ({r},{c}) "
                                f"has neighbor {neighbor_tile} at ({nr},{nc}) "
                                f"in direction {d}, but allowed = {adj[tile][d]}"
                            )


class TestWFCMenuKeys:
    """Tests for menu and key handling."""

    def test_menu_navigate_down(self):
        app = _make_wfc_app()
        app._enter_wfc_mode()
        app._handle_wfc_menu_key(ord("j"))
        assert app.wfc_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        app = _make_wfc_app()
        app._enter_wfc_mode()
        app._handle_wfc_menu_key(ord("k"))
        assert app.wfc_menu_sel == len(type(app).WFC_PRESETS) - 1

    def test_menu_enter_selects(self):
        app = _make_wfc_app()
        app._enter_wfc_mode()
        app._handle_wfc_menu_key(ord("\n"))
        assert app.wfc_mode is True
        assert app.wfc_menu is False

    def test_menu_quit(self):
        app = _make_wfc_app()
        app._enter_wfc_mode()
        app._handle_wfc_menu_key(ord("q"))
        assert app.wfc_menu is False

    def test_wfc_key_space_toggles_running(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        assert app.wfc_running is False
        app._handle_wfc_key(ord(" "))
        assert app.wfc_running is True
        app._handle_wfc_key(ord(" "))
        assert app.wfc_running is False

    def test_wfc_key_space_noop_when_complete(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        app.wfc_complete = True
        app._handle_wfc_key(ord(" "))
        assert app.wfc_running is False

    def test_wfc_key_n_steps(self):
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)
        app._handle_wfc_key(ord("n"))
        assert app.wfc_generation >= 1

    def test_wfc_key_r_restarts(self):
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)
        app._wfc_step()
        app._wfc_step()
        gen_before = app.wfc_generation
        assert gen_before >= 1
        app._handle_wfc_key(ord("r"))
        assert app.wfc_generation == 0

    def test_wfc_key_s_adjusts_speed(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        assert app.wfc_steps_per_frame == 1
        app._handle_wfc_key(ord("s"))
        assert app.wfc_steps_per_frame == 2
        app._handle_wfc_key(ord("S"))
        assert app.wfc_steps_per_frame == 1

    def test_wfc_key_s_max_speed(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        app.wfc_steps_per_frame = 50
        app._handle_wfc_key(ord("s"))
        assert app.wfc_steps_per_frame == 50  # capped at 50

    def test_wfc_key_S_min_speed(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        app.wfc_steps_per_frame = 1
        app._handle_wfc_key(ord("S"))
        assert app.wfc_steps_per_frame == 1  # floor at 1

    def test_wfc_key_q_exits(self):
        app = _make_wfc_app()
        app._wfc_init(0)
        app._handle_wfc_key(ord("q"))
        assert app.wfc_mode is False


class TestWFCDeterminism:
    """Verify deterministic behavior with fixed random seed."""

    def test_same_seed_same_result(self):
        results = []
        for _ in range(2):
            random.seed(123)
            app = _make_wfc_app()
            app._wfc_init(1)
            for _ in range(50):
                if app.wfc_complete or app.wfc_contradiction:
                    break
                app._wfc_step()
            snapshot = tuple(
                tuple(app.wfc_collapsed[r][c] for c in range(app.wfc_cols))
                for r in range(app.wfc_rows)
            )
            results.append(snapshot)
        assert results[0] == results[1]


class TestWFCEdgeCases:
    """Edge case and regression tests."""

    def test_generation_increments_even_if_propagation_auto_collapses(self):
        """Each call to _wfc_step should increment generation by exactly 1."""
        random.seed(42)
        app = _make_wfc_app()
        app._wfc_init(0)
        for i in range(1, 6):
            if app.wfc_complete or app.wfc_contradiction:
                break
            app._wfc_step()
            assert app.wfc_generation == i

    def test_grid_cells_are_independent_sets(self):
        """Each cell's possibility set should be a distinct object."""
        app = _make_wfc_app()
        app._wfc_init(0)
        # Mutating one cell should not affect another
        app.wfc_grid[0][0].discard(0)
        assert 0 in app.wfc_grid[0][1]

    def test_multiple_restarts(self):
        """Restarting multiple times should not accumulate state."""
        random.seed(42)
        app = _make_wfc_app()
        for _ in range(5):
            app._wfc_init(0)
            app._wfc_step()
            app._wfc_step()
        app._wfc_init(0)
        assert app.wfc_generation == 0
        assert app.wfc_contradiction is False
        assert app.wfc_complete is False
        # All cells should be uncollapsed
        for r in range(app.wfc_rows):
            for c in range(app.wfc_cols):
                assert app.wfc_collapsed[r][c] == -1
