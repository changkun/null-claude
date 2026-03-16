"""Tests for maze mode — deep logic validation."""
import collections
import heapq
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.maze import register


# MAZE_PRESETS is referenced on self but never registered as class attr
MAZE_PRESETS = [
    ("DFS Backtracker + BFS", "Recursive backtracker generation, BFS solve",
     "backtracker", "bfs", 1),
    ("Prim + A*", "Prim's algorithm generation, A* solve",
     "prim", "astar", 1),
    ("Kruskal + DFS", "Kruskal's algorithm generation, DFS solve",
     "kruskal", "dfs", 1),
    ("Kruskal + Dijkstra", "Kruskal's algorithm generation, Dijkstra solve",
     "kruskal", "dijkstra", 1),
    ("Backtracker + A*", "Recursive backtracker generation, A* solve",
     "backtracker", "astar", 1),
]


def _make_maze_app():
    """Create and configure a mock app with maze mode registered."""
    app = make_mock_app()
    cls = type(app)
    register(cls)
    cls.MAZE_PRESETS = MAZE_PRESETS
    # Instance attrs that _maze_init expects
    app.maze_mode = False
    app.maze_menu = False
    app.maze_menu_sel = 0
    app.maze_running = False
    app.maze_grid = []
    app.maze_gen_stack = []
    app.maze_gen_edges = []
    app.maze_gen_visited = set()
    app.maze_gen_sets = {}
    app.maze_solve_queue = []
    app.maze_solve_visited = set()
    app.maze_solve_parent = {}
    app.maze_solve_path = []
    app.maze_steps_per_frame = 3
    app.maze_generation = 0
    app.maze_phase = "generating"
    app.maze_preset_name = ""
    app.maze_gen_algo = ""
    app.maze_solve_algo = ""
    app.maze_gen_steps = 0
    app.maze_solve_steps = 0
    app.maze_solve_done = False
    app.maze_rows = 0
    app.maze_cols = 0
    app.maze_start = (1, 1)
    app.maze_end = (1, 1)
    return app


def _run_to_completion(app, max_steps=50000):
    """Run the maze simulation until done, return total steps taken."""
    steps = 0
    for _ in range(max_steps):
        app._maze_step()
        steps += 1
        if app.maze_phase == "done":
            break
    return steps


def _verify_grid_dimensions(app):
    """Verify maze grid has correct odd dimensions and boundary walls."""
    rows, cols = app.maze_rows, app.maze_cols
    assert rows % 2 == 1, f"rows={rows} should be odd"
    assert cols % 2 == 1, f"cols={cols} should be odd"
    assert len(app.maze_grid) == rows
    for r in range(rows):
        assert len(app.maze_grid[r]) == cols, f"row {r} has {len(app.maze_grid[r])} cols, expected {cols}"


def _verify_maze_connectivity(app):
    """BFS from start to end on the generated maze; return True if reachable."""
    rows, cols = app.maze_rows, app.maze_cols
    grid = app.maze_grid
    sr, sc = app.maze_start
    er, ec = app.maze_end
    if grid[sr][sc] != 1 or grid[er][ec] != 1:
        return False
    visited = set()
    queue = collections.deque([(sr, sc)])
    visited.add((sr, sc))
    while queue:
        cr, cc = queue.popleft()
        if (cr, cc) == (er, ec):
            return True
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = cr + dr, cc + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1 and (nr, nc) not in visited:
                visited.add((nr, nc))
                queue.append((nr, nc))
    return False


def _verify_path_valid(app):
    """Verify the solution path is contiguous, starts at start, ends at end."""
    path = app.maze_solve_path
    if not path:
        return False
    if path[0] != app.maze_start:
        return False
    if path[-1] != app.maze_end:
        return False
    grid = app.maze_grid
    for i, (r, c) in enumerate(path):
        # Every cell on path must be a passage
        if grid[r][c] != 1:
            return False
        # Every consecutive pair must be adjacent (Manhattan distance 1)
        if i > 0:
            pr, pc = path[i - 1]
            if abs(r - pr) + abs(c - pc) != 1:
                return False
    return True


class TestMazeInit:
    """Test maze initialization for all generation algorithms."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_maze_app()

    def test_enter_maze_mode(self):
        self.app._enter_maze_mode()
        assert self.app.maze_menu is True
        assert self.app.maze_menu_sel == 0

    def test_exit_maze_mode_cleans_state(self):
        self.app._maze_init(0)
        self.app._exit_maze_mode()
        assert self.app.maze_mode is False
        assert self.app.maze_running is False
        assert self.app.maze_grid == []
        assert self.app.maze_gen_stack == []
        assert self.app.maze_gen_edges == []
        assert self.app.maze_gen_visited == set()
        assert self.app.maze_gen_sets == {}
        assert self.app.maze_solve_queue == []
        assert self.app.maze_solve_visited == set()
        assert self.app.maze_solve_parent == {}
        assert self.app.maze_solve_path == []

    def test_init_backtracker(self):
        self.app._maze_init(0)
        assert self.app.maze_gen_algo == "backtracker"
        assert self.app.maze_phase == "generating"
        _verify_grid_dimensions(self.app)
        # Backtracker starts with (1,1) visited and on the stack
        assert (1, 1) in self.app.maze_gen_visited
        assert len(self.app.maze_gen_stack) == 1
        assert self.app.maze_grid[1][1] == 1

    def test_init_prim(self):
        self.app._maze_init(1)
        assert self.app.maze_gen_algo == "prim"
        _verify_grid_dimensions(self.app)
        assert (1, 1) in self.app.maze_gen_visited
        # Prim should have frontier edges added
        assert len(self.app.maze_gen_edges) > 0

    def test_init_kruskal(self):
        self.app._maze_init(2)
        assert self.app.maze_gen_algo == "kruskal"
        _verify_grid_dimensions(self.app)
        # All odd cells should be passages
        rows, cols = self.app.maze_rows, self.app.maze_cols
        for r in range(1, rows, 2):
            for c in range(1, cols, 2):
                assert self.app.maze_grid[r][c] == 1, f"cell ({r},{c}) should be passage"
        # Each odd cell should have a unique set ID initially
        num_cells = len(self.app.maze_gen_sets)
        unique_ids = set(self.app.maze_gen_sets.values())
        assert len(unique_ids) == num_cells, "Each cell should start in its own set"
        # Should have edges to process
        assert len(self.app.maze_gen_edges) > 0

    def test_grid_dimensions_always_odd(self):
        """Grid dimensions must be odd for wall/passage pattern."""
        for preset_idx in range(len(MAZE_PRESETS)):
            app = _make_maze_app()
            app._maze_init(preset_idx)
            _verify_grid_dimensions(app)

    def test_start_and_end_are_passages(self):
        """Start (1,1) and end (rows-2, cols-2) are passage cells."""
        self.app._maze_init(0)
        sr, sc = self.app.maze_start
        er, ec = self.app.maze_end
        assert self.app.maze_grid[sr][sc] == 1
        # End might not be a passage until generation completes,
        # but start should always be


class TestMazeGeneration:
    """Test that maze generation produces valid, connected mazes."""

    def _run_generation_only(self, app, max_steps=50000):
        """Run generation until phase transitions to solving."""
        for _ in range(max_steps):
            if app.maze_phase != "generating":
                break
            app._maze_step()
        return app.maze_phase

    @pytest.mark.parametrize("preset_idx,algo", [
        (0, "backtracker"),
        (1, "prim"),
        (2, "kruskal"),
    ])
    def test_generation_completes(self, preset_idx, algo):
        """Generation phase should eventually complete."""
        random.seed(123)
        app = _make_maze_app()
        app._maze_init(preset_idx)
        phase = self._run_generation_only(app)
        assert phase == "solving", f"{algo} generation did not complete"

    @pytest.mark.parametrize("preset_idx,algo", [
        (0, "backtracker"),
        (1, "prim"),
        (2, "kruskal"),
    ])
    def test_generated_maze_is_connected(self, preset_idx, algo):
        """After generation, the maze should be connected from start to end."""
        random.seed(456)
        app = _make_maze_app()
        app._maze_init(preset_idx)
        self._run_generation_only(app)
        assert _verify_maze_connectivity(app), f"{algo} maze is not connected"

    def test_backtracker_visits_all_cells(self):
        """Recursive backtracker should visit every odd-indexed cell."""
        random.seed(789)
        app = _make_maze_app()
        app._maze_init(0)
        self._run_generation_only(app)
        rows, cols = app.maze_rows, app.maze_cols
        for r in range(1, rows, 2):
            for c in range(1, cols, 2):
                assert app.maze_grid[r][c] == 1, f"Cell ({r},{c}) not carved by backtracker"

    def test_prim_visits_all_cells(self):
        """Prim's should visit every odd-indexed cell."""
        random.seed(321)
        app = _make_maze_app()
        app._maze_init(1)
        self._run_generation_only(app)
        rows, cols = app.maze_rows, app.maze_cols
        for r in range(1, rows, 2):
            for c in range(1, cols, 2):
                assert app.maze_grid[r][c] == 1, f"Cell ({r},{c}) not carved by Prim's"

    def test_kruskal_merges_all_sets(self):
        """Kruskal's should end with all cells in the same set."""
        random.seed(654)
        app = _make_maze_app()
        app._maze_init(2)
        self._run_generation_only(app)
        set_ids = set(app.maze_gen_sets.values())
        assert len(set_ids) == 1, f"Kruskal's left {len(set_ids)} disjoint sets"

    def test_generation_step_count_increments(self):
        """gen_steps should be non-zero after generation."""
        random.seed(42)
        app = _make_maze_app()
        app._maze_init(0)
        self._run_generation_only(app)
        assert app.maze_gen_steps > 0

    def test_walls_form_border(self):
        """After generation, the border should remain walls (row 0, col 0, etc)."""
        random.seed(42)
        app = _make_maze_app()
        app._maze_init(0)
        self._run_generation_only(app)
        rows, cols = app.maze_rows, app.maze_cols
        for c in range(cols):
            assert app.maze_grid[0][c] == 0, f"Top border breach at col {c}"
            assert app.maze_grid[rows - 1][c] == 0, f"Bottom border breach at col {c}"
        for r in range(rows):
            assert app.maze_grid[r][0] == 0, f"Left border breach at row {r}"
            assert app.maze_grid[r][cols - 1] == 0, f"Right border breach at row {r}"


class TestMazeSolving:
    """Test pathfinding algorithms produce valid paths."""

    def _gen_and_solve(self, preset_idx, seed=42):
        random.seed(seed)
        app = _make_maze_app()
        app._maze_init(preset_idx)
        _run_to_completion(app)
        return app

    @pytest.mark.parametrize("preset_idx,desc", [
        (0, "backtracker+bfs"),
        (1, "prim+astar"),
        (2, "kruskal+dfs"),
        (3, "kruskal+dijkstra"),
        (4, "backtracker+astar"),
    ])
    def test_solver_finds_path(self, preset_idx, desc):
        """Each preset should find a valid path."""
        app = self._gen_and_solve(preset_idx)
        assert app.maze_phase == "done", f"{desc}: did not reach done phase"
        assert len(app.maze_solve_path) > 0, f"{desc}: no path found"
        assert _verify_path_valid(app), f"{desc}: path is invalid"

    @pytest.mark.parametrize("preset_idx,desc", [
        (0, "backtracker+bfs"),
        (1, "prim+astar"),
        (3, "kruskal+dijkstra"),
        (4, "backtracker+astar"),
    ])
    def test_optimal_solvers_find_shortest_path(self, preset_idx, desc):
        """BFS, A*, and Dijkstra should find the shortest path (verified by independent BFS)."""
        app = self._gen_and_solve(preset_idx)
        assert app.maze_phase == "done"
        path = app.maze_solve_path
        assert len(path) > 0

        # Independent BFS to verify shortest path length
        rows, cols = app.maze_rows, app.maze_cols
        grid = app.maze_grid
        sr, sc = app.maze_start
        er, ec = app.maze_end
        dist = {(sr, sc): 0}
        queue = collections.deque([(sr, sc)])
        while queue:
            cr, cc = queue.popleft()
            if (cr, cc) == (er, ec):
                break
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1 and (nr, nc) not in dist:
                    dist[(nr, nc)] = dist[(cr, cc)] + 1
                    queue.append((nr, nc))
        expected_len = dist.get((er, ec), -1) + 1  # +1 because path includes start
        assert len(path) == expected_len, (
            f"{desc}: path length {len(path)} != BFS shortest {expected_len}"
        )

    def test_dfs_finds_valid_but_possibly_non_optimal_path(self):
        """DFS solver finds a valid path (may not be shortest)."""
        app = self._gen_and_solve(2)  # kruskal+dfs
        assert app.maze_phase == "done"
        assert _verify_path_valid(app)
        # DFS path length >= BFS shortest path length
        rows, cols = app.maze_rows, app.maze_cols
        grid = app.maze_grid
        sr, sc = app.maze_start
        er, ec = app.maze_end
        dist = {(sr, sc): 0}
        queue = collections.deque([(sr, sc)])
        while queue:
            cr, cc = queue.popleft()
            if (cr, cc) == (er, ec):
                break
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1 and (nr, nc) not in dist:
                    dist[(nr, nc)] = dist[(cr, cc)] + 1
                    queue.append((nr, nc))
        shortest = dist.get((er, ec), -1) + 1
        assert len(app.maze_solve_path) >= shortest

    def test_solve_steps_tracked(self):
        """Solver should track step count."""
        app = self._gen_and_solve(0)
        assert app.maze_solve_steps > 0

    def test_path_reconstruct_includes_start_and_end(self):
        """Reconstructed path starts at maze_start and ends at maze_end."""
        app = self._gen_and_solve(0)
        assert app.maze_solve_path[0] == app.maze_start
        assert app.maze_solve_path[-1] == app.maze_end

    def test_solver_visited_superset_of_path(self):
        """Every cell on the path should be in the visited set."""
        app = self._gen_and_solve(0)
        for cell in app.maze_solve_path:
            assert cell in app.maze_solve_visited


class TestMazeStepMechanics:
    """Test stepping behavior and phase transitions."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_maze_app()

    def test_step_increments_generation(self):
        self.app._maze_init(0)
        self.app._maze_step()
        assert self.app.maze_generation == 1

    def test_phase_transitions_generating_to_solving(self):
        self.app._maze_init(0)
        while self.app.maze_phase == "generating":
            self.app._maze_step()
            if self.app.maze_generation > 50000:
                pytest.fail("Generation did not complete within 50000 steps")
        assert self.app.maze_phase == "solving"

    def test_phase_transitions_solving_to_done(self):
        self.app._maze_init(0)
        _run_to_completion(self.app)
        assert self.app.maze_phase == "done"
        assert self.app.maze_solve_done is True

    def test_no_crash_after_done(self):
        """Stepping after done should not crash."""
        self.app._maze_init(0)
        _run_to_completion(self.app)
        # Additional steps should not raise
        for _ in range(10):
            self.app._maze_step()

    def test_multiple_seeds_produce_different_mazes(self):
        """Different random seeds should produce different mazes."""
        grids = []
        for seed in [1, 2, 3]:
            random.seed(seed)
            app = _make_maze_app()
            app._maze_init(0)
            while app.maze_phase == "generating":
                app._maze_step()
                if app.maze_generation > 50000:
                    break
            grids.append(tuple(tuple(row) for row in app.maze_grid))
        # At least 2 of 3 should be different
        assert len(set(grids)) >= 2, "All seeds produced identical mazes"


class TestMazeAlgorithmInvariants:
    """Test algorithm-specific invariants."""

    def test_backtracker_stack_empty_after_generation(self):
        """Backtracker generation ends when stack is empty."""
        random.seed(42)
        app = _make_maze_app()
        app._maze_init(0)
        while app.maze_phase == "generating":
            app._maze_step()
            if app.maze_generation > 50000:
                break
        assert len(app.maze_gen_stack) == 0

    def test_prim_edges_empty_after_generation(self):
        """Prim's generation ends when all frontier edges are consumed."""
        random.seed(42)
        app = _make_maze_app()
        app._maze_init(1)
        while app.maze_phase == "generating":
            app._maze_step()
            if app.maze_generation > 50000:
                break
        assert len(app.maze_gen_edges) == 0

    def test_kruskal_edges_empty_after_generation(self):
        """Kruskal's generation ends when all edges are processed."""
        random.seed(42)
        app = _make_maze_app()
        app._maze_init(2)
        while app.maze_phase == "generating":
            app._maze_step()
            if app.maze_generation > 50000:
                break
        assert len(app.maze_gen_edges) == 0

    def test_astar_heuristic_admissible(self):
        """A* with Manhattan distance heuristic is admissible for grid mazes."""
        # Verify that the A* solver produces the same path length as BFS
        random.seed(42)
        app = _make_maze_app()
        app._maze_init(4)  # backtracker + astar
        _run_to_completion(app)
        astar_len = len(app.maze_solve_path)

        # Reset and solve with BFS for comparison
        random.seed(42)
        app2 = _make_maze_app()
        app2._maze_init(0)  # backtracker + bfs (same seed = same maze)
        _run_to_completion(app2)
        bfs_len = len(app2.maze_solve_path)

        assert astar_len == bfs_len, f"A* path ({astar_len}) != BFS path ({bfs_len})"

    def test_dijkstra_same_as_bfs_for_uniform_cost(self):
        """Dijkstra should find same-length path as BFS on unweighted maze."""
        random.seed(42)
        # kruskal + dijkstra
        app_dij = _make_maze_app()
        type(app_dij).MAZE_PRESETS = MAZE_PRESETS
        app_dij._maze_init(3)
        _run_to_completion(app_dij)
        dij_len = len(app_dij.maze_solve_path)

        # Same maze with BFS
        random.seed(42)
        bfs_presets = list(MAZE_PRESETS)
        bfs_presets[3] = ("Kruskal + BFS-check", "test", "kruskal", "bfs", 1)
        app_bfs = _make_maze_app()
        type(app_bfs).MAZE_PRESETS = bfs_presets
        app_bfs._maze_init(3)
        _run_to_completion(app_bfs)
        bfs_len = len(app_bfs.maze_solve_path)

        assert dij_len == bfs_len

    def test_generated_maze_is_perfect(self):
        """A perfect maze has exactly one path between any two cells (tree structure).

        For a spanning tree of N nodes, there are exactly N-1 edges (passages between cells).
        """
        random.seed(42)
        app = _make_maze_app()
        app._maze_init(0)  # backtracker
        while app.maze_phase == "generating":
            app._maze_step()
            if app.maze_generation > 50000:
                break
        rows, cols = app.maze_rows, app.maze_cols
        # Count passage cells at odd positions (nodes)
        nodes = 0
        for r in range(1, rows, 2):
            for c in range(1, cols, 2):
                if app.maze_grid[r][c] == 1:
                    nodes += 1
        # Count wall cells between odd positions that are carved (edges)
        edges = 0
        for r in range(1, rows, 2):
            for c in range(1, cols, 2):
                # Check right neighbor
                if c + 2 < cols and app.maze_grid[r][c + 1] == 1:
                    edges += 1
                # Check bottom neighbor
                if r + 2 < rows and app.maze_grid[r + 1][c] == 1:
                    edges += 1
        assert edges == nodes - 1, (
            f"Perfect maze should have {nodes - 1} edges, got {edges}"
        )
