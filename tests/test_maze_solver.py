"""Tests for life.modes.maze_solver — Maze Solver Visualizer mode."""
import curses
import time

from tests.conftest import make_mock_app
from life.modes.maze_solver import register, MAZESOLVER_PRESETS


def _make_app():
    app = make_mock_app()
    app.mazesolver_mode = False
    app.mazesolver_menu = False
    app.mazesolver_menu_sel = 0
    app.mazesolver_running = False
    app.mazesolver_speed = 3
    app.mazesolver_grid = []
    app.mazesolver_solve_queue = []
    app.mazesolver_solve_visited = set()
    app.mazesolver_solve_parent = {}
    app.mazesolver_solve_path = []
    app.mazesolver_frontier_set = set()
    app.mazesolver_wf_trail = []
    app.mazesolver_wf_pos = (1, 1)
    app.mazesolver_wf_dir = 0
    app.mazesolver_gen_stack = []
    app.mazesolver_gen_visited = set()
    register(type(app))
    return app


# ── Constants / presets ──


def test_presets_exist():
    assert len(MAZESOLVER_PRESETS) >= 8


def test_preset_algos():
    algos = {p[2] for p in MAZESOLVER_PRESETS}
    assert "astar" in algos
    assert "bfs" in algos
    assert "dfs" in algos
    assert "wall_follower" in algos


def test_preset_sizes():
    sizes = {p[3] for p in MAZESOLVER_PRESETS}
    assert "small" in sizes
    assert "medium" in sizes
    assert "large" in sizes


# ── Enter / Exit ──


def test_enter():
    app = _make_app()
    app._enter_mazesolver_mode()
    assert app.mazesolver_mode is True
    assert app.mazesolver_menu is True
    assert app.mazesolver_running is False


def test_exit_cleanup():
    app = _make_app()
    app.mazesolver_mode = True
    app._mazesolver_init(0)
    app._exit_mazesolver_mode()
    assert app.mazesolver_mode is False
    assert app.mazesolver_running is False
    assert app.mazesolver_grid == []
    assert app.mazesolver_solve_queue == []
    assert app.mazesolver_solve_visited == set()
    assert app.mazesolver_solve_parent == {}
    assert app.mazesolver_solve_path == []
    assert app.mazesolver_frontier_set == set()
    assert app.mazesolver_wf_trail == []
    assert app.mazesolver_gen_stack == []
    assert app.mazesolver_gen_visited == set()


# ── Init ──


def test_init_astar_medium():
    app = _make_app()
    app._mazesolver_init(0)  # A* Medium
    assert app.mazesolver_algo == "astar"
    assert app.mazesolver_phase == "solving"
    assert app.mazesolver_rows % 2 == 1  # odd
    assert app.mazesolver_cols % 2 == 1  # odd
    assert len(app.mazesolver_grid) == app.mazesolver_rows
    assert len(app.mazesolver_grid[0]) == app.mazesolver_cols


def test_init_bfs():
    app = _make_app()
    app._mazesolver_init(1)  # BFS Medium
    assert app.mazesolver_algo == "bfs"
    assert len(app.mazesolver_solve_queue) > 0


def test_init_dfs():
    app = _make_app()
    app._mazesolver_init(2)  # DFS Medium
    assert app.mazesolver_algo == "dfs"
    assert len(app.mazesolver_solve_queue) > 0


def test_init_wall_follower():
    app = _make_app()
    app._mazesolver_init(3)  # Wall Follower Medium
    assert app.mazesolver_algo == "wall_follower"
    assert app.mazesolver_wf_pos == (1, 1)
    assert len(app.mazesolver_wf_trail) == 1


def test_init_small():
    app = _make_app()
    app._mazesolver_init(4)  # A* Small
    assert app.mazesolver_maze_size == "small"
    assert app.mazesolver_rows <= 21
    assert app.mazesolver_cols <= 21


def test_init_large():
    app = _make_app()
    app._mazesolver_init(5)  # A* Large
    assert app.mazesolver_maze_size == "large"


def test_init_maze_is_valid():
    """Generated maze should have walls on border and passages inside."""
    app = _make_app()
    app._mazesolver_init(0)
    rows, cols = app.mazesolver_rows, app.mazesolver_cols
    grid = app.mazesolver_grid
    # Top and bottom borders should be walls
    for c in range(cols):
        assert grid[0][c] == 0, f"Top border at col {c} should be wall"
        assert grid[rows - 1][c] == 0, f"Bottom border at col {c} should be wall"
    # Left and right borders should be walls
    for r in range(rows):
        assert grid[r][0] == 0, f"Left border at row {r} should be wall"
        assert grid[r][cols - 1] == 0, f"Right border at row {r} should be wall"
    # Start and end should be passages
    sr, sc = app.mazesolver_start
    er, ec = app.mazesolver_end
    assert grid[sr][sc] == 1
    assert grid[er][ec] == 1


def test_init_start_visited():
    """Start cell should be in visited set after init."""
    app = _make_app()
    app._mazesolver_init(0)
    assert app.mazesolver_start in app.mazesolver_solve_visited


def test_init_speed_preserved():
    """Regression: _mazesolver_init should preserve or initialize speed."""
    app = _make_app()
    app.mazesolver_speed = 5
    app._mazesolver_init(0)
    assert app.mazesolver_speed == 5


def test_init_speed_defaults():
    """If speed wasn't set, init should default to 3."""
    app = _make_app()
    del app.mazesolver_speed
    app._mazesolver_init(0)
    assert app.mazesolver_speed == 3


def test_init_wf_attrs_always_set():
    """Regression: wf_pos, wf_dir, wf_trail should always be initialized."""
    app = _make_app()
    app._mazesolver_init(0)  # astar, not wall_follower
    assert hasattr(app, 'mazesolver_wf_pos')
    assert hasattr(app, 'mazesolver_wf_dir')
    assert hasattr(app, 'mazesolver_wf_trail')


def test_init_all_presets():
    """All presets should initialize without error."""
    for idx in range(len(MAZESOLVER_PRESETS)):
        app = _make_app()
        app._mazesolver_init(idx)
        assert app.mazesolver_phase == "solving"


# ── Step / solving ──


def test_step_no_crash():
    app = _make_app()
    app.mazesolver_mode = True
    app._mazesolver_init(0)
    app.mazesolver_running = True
    for _ in range(10):
        app._mazesolver_step()
    assert app.mazesolver_generation >= 0


def test_step_advances_generation():
    app = _make_app()
    app._mazesolver_init(0)
    gen0 = app.mazesolver_generation
    app._mazesolver_step()
    # If not done, generation should advance
    if not app.mazesolver_solve_done:
        assert app.mazesolver_generation > gen0


def test_step_increases_visited():
    app = _make_app()
    app._mazesolver_init(1)  # BFS
    v0 = len(app.mazesolver_solve_visited)
    for _ in range(10):
        app._mazesolver_step()
    assert len(app.mazesolver_solve_visited) >= v0


def test_step_noop_when_done():
    app = _make_app()
    app._mazesolver_init(0)
    app.mazesolver_solve_done = True
    gen0 = app.mazesolver_generation
    app._mazesolver_step()
    assert app.mazesolver_generation == gen0


def test_step_noop_wrong_phase():
    app = _make_app()
    app._mazesolver_init(0)
    app.mazesolver_phase = "generating"
    gen0 = app.mazesolver_generation
    app._mazesolver_step()
    assert app.mazesolver_generation == gen0


def test_astar_finds_path():
    """A* should eventually find a path."""
    app = _make_app()
    app._mazesolver_init(0)  # A* Medium
    for _ in range(5000):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
    assert app.mazesolver_solve_done is True
    assert len(app.mazesolver_solve_path) > 0
    # Path should start at start and end at end
    assert app.mazesolver_solve_path[0] == app.mazesolver_start
    assert app.mazesolver_solve_path[-1] == app.mazesolver_end


def test_bfs_finds_path():
    """BFS should find the shortest path."""
    app = _make_app()
    app._mazesolver_init(1)  # BFS Medium
    for _ in range(5000):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
    assert app.mazesolver_solve_done is True
    assert len(app.mazesolver_solve_path) > 0


def test_dfs_finds_path():
    """DFS should eventually find a path."""
    app = _make_app()
    app._mazesolver_init(2)  # DFS Medium
    for _ in range(5000):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
    assert app.mazesolver_solve_done is True
    assert len(app.mazesolver_solve_path) > 0


def test_wall_follower_finds_path():
    """Wall follower should eventually reach the end."""
    app = _make_app()
    app._mazesolver_init(3)  # Wall Follower Medium
    for _ in range(10000):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
    assert app.mazesolver_solve_done is True
    assert len(app.mazesolver_solve_path) > 0


def test_bfs_path_is_shortest():
    """BFS path should be no longer than A* path for same maze."""
    import random
    random.seed(42)
    app_bfs = _make_app()
    app_bfs._mazesolver_init(1)  # BFS
    grid_copy = [row[:] for row in app_bfs.mazesolver_grid]
    for _ in range(5000):
        if app_bfs.mazesolver_solve_done:
            break
        app_bfs._mazesolver_step()

    # Use same maze for A*
    random.seed(42)
    app_astar = _make_app()
    app_astar._mazesolver_init(0)  # A*
    # Replace grid with the same one
    app_astar.mazesolver_grid = grid_copy
    # Re-init solver with same start/end
    app_astar.mazesolver_start = app_bfs.mazesolver_start
    app_astar.mazesolver_end = app_bfs.mazesolver_end
    for _ in range(5000):
        if app_astar.mazesolver_solve_done:
            break
        app_astar._mazesolver_step()

    if app_bfs.mazesolver_solve_done and app_astar.mazesolver_solve_done:
        # Both BFS and A* should find optimal paths
        assert len(app_bfs.mazesolver_solve_path) <= len(app_astar.mazesolver_solve_path) + 1


def test_path_cells_are_passages():
    """Every cell in the solution path should be a passage (1), not a wall (0)."""
    app = _make_app()
    app._mazesolver_init(0)
    for _ in range(5000):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
    for r, c in app.mazesolver_solve_path:
        assert app.mazesolver_grid[r][c] == 1, f"Path cell ({r},{c}) is a wall"


def test_path_is_connected():
    """Each cell in the path should be adjacent to the next."""
    app = _make_app()
    app._mazesolver_init(0)
    for _ in range(5000):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
    path = app.mazesolver_solve_path
    for i in range(len(path) - 1):
        r1, c1 = path[i]
        r2, c2 = path[i + 1]
        assert abs(r1 - r2) + abs(c1 - c2) == 1, f"Path gap between {path[i]} and {path[i+1]}"


def test_reconstruct_path():
    """_mazesolver_reconstruct_path should build valid path from parent dict."""
    app = _make_app()
    app._mazesolver_init(0)
    # Manually set up parent chain: (1,1) -> (1,2) -> (1,3)
    app.mazesolver_start = (1, 1)
    app.mazesolver_end = (1, 3)
    app.mazesolver_solve_parent = {(1, 2): (1, 1), (1, 3): (1, 2)}
    app._mazesolver_reconstruct_path()
    assert app.mazesolver_solve_path == [(1, 1), (1, 2), (1, 3)]
    assert app.mazesolver_solve_done is True
    assert app.mazesolver_phase == "done"


# ── Menu key handling ──


def test_menu_navigate_down():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._handle_mazesolver_menu_key(curses.KEY_DOWN)
    assert app.mazesolver_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._handle_mazesolver_menu_key(curses.KEY_UP)
    assert app.mazesolver_menu_sel == len(MAZESOLVER_PRESETS) - 1


def test_menu_j_k():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._handle_mazesolver_menu_key(ord('j'))
    assert app.mazesolver_menu_sel == 1
    app._handle_mazesolver_menu_key(ord('k'))
    assert app.mazesolver_menu_sel == 0


def test_menu_enter_selects():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._handle_mazesolver_menu_key(ord('\n'))
    assert app.mazesolver_menu is False
    assert app.mazesolver_phase == "solving"


def test_menu_quit():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._handle_mazesolver_menu_key(ord('q'))
    assert app.mazesolver_mode is False


def test_menu_escape():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._handle_mazesolver_menu_key(27)
    assert app.mazesolver_mode is False


# ── Simulation key handling ──


def test_key_space_toggles():
    app = _make_app()
    app._mazesolver_init(0)
    assert app.mazesolver_running is False
    app._handle_mazesolver_key(ord(' '))
    assert app.mazesolver_running is True
    app._handle_mazesolver_key(ord(' '))
    assert app.mazesolver_running is False


def test_key_n_steps():
    app = _make_app()
    app._mazesolver_init(0)
    steps0 = app.mazesolver_solve_steps
    app._handle_mazesolver_key(ord('n'))
    assert app.mazesolver_solve_steps >= steps0


def test_key_dot_steps():
    app = _make_app()
    app._mazesolver_init(0)
    steps0 = app.mazesolver_solve_steps
    app._handle_mazesolver_key(ord('.'))
    assert app.mazesolver_solve_steps >= steps0


def test_key_s_increases_speed():
    app = _make_app()
    app._mazesolver_init(0)
    s0 = app.mazesolver_speed
    app._handle_mazesolver_key(ord('s'))
    assert app.mazesolver_speed == s0 + 1


def test_key_S_decreases_speed():
    app = _make_app()
    app._mazesolver_init(0)
    s0 = app.mazesolver_speed
    app._handle_mazesolver_key(ord('S'))
    assert app.mazesolver_speed == s0 - 1


def test_key_speed_clamped():
    app = _make_app()
    app._mazesolver_init(0)
    app.mazesolver_speed = 1
    app._handle_mazesolver_key(ord('S'))
    assert app.mazesolver_speed >= 1
    app.mazesolver_speed = 30
    app._handle_mazesolver_key(ord('s'))
    assert app.mazesolver_speed <= 30


def test_key_r_regenerates():
    app = _make_app()
    app._mazesolver_init(0)
    for _ in range(50):
        app._mazesolver_step()
    app._handle_mazesolver_key(ord('r'))
    # Should have reset the solver
    assert app.mazesolver_solve_done is False
    assert app.mazesolver_running is False


def test_key_R_returns_to_menu():
    """Regression: R should keep mazesolver_mode True while showing menu."""
    app = _make_app()
    app._mazesolver_init(0)
    app._handle_mazesolver_key(ord('R'))
    assert app.mazesolver_menu is True
    assert app.mazesolver_running is False
    assert app.mazesolver_mode is True  # mode should stay true


def test_key_q_exits():
    app = _make_app()
    app._mazesolver_init(0)
    app._handle_mazesolver_key(ord('q'))
    assert app.mazesolver_mode is False


def test_key_escape_exits():
    app = _make_app()
    app._mazesolver_init(0)
    app._handle_mazesolver_key(27)
    assert app.mazesolver_mode is False


# ── Draw functions ──


def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._draw_mazesolver_menu(40, 120)


def test_draw_menu_small_terminal():
    app = _make_app()
    app._enter_mazesolver_mode()
    app._draw_mazesolver_menu(10, 40)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._mazesolver_init(0)
    for _ in range(20):
        app._mazesolver_step()
    app._draw_mazesolver(40, 120)


def test_draw_after_solve_no_crash():
    app = _make_app()
    app._mazesolver_init(0)
    for _ in range(5000):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
    app._draw_mazesolver(40, 120)


def test_draw_wall_follower_no_crash():
    app = _make_app()
    app._mazesolver_init(3)  # Wall Follower
    for _ in range(50):
        app._mazesolver_step()
    app._draw_mazesolver(40, 120)


def test_draw_with_flash_message():
    app = _make_app()
    app._mazesolver_init(0)
    app.message = "Test message"
    app.message_time = time.monotonic()
    app._draw_mazesolver(40, 120)


# ── Wall follower direction logic ──


def test_wall_follower_direction_changes():
    """Wall follower should change direction as it navigates."""
    app = _make_app()
    app._mazesolver_init(3)
    initial_dir = app.mazesolver_wf_dir
    dirs_seen = {initial_dir}
    for _ in range(100):
        if app.mazesolver_solve_done:
            break
        app._mazesolver_step()
        dirs_seen.add(app.mazesolver_wf_dir)
    # Should have turned at least once
    assert len(dirs_seen) > 1


def test_wall_follower_trail_grows():
    app = _make_app()
    app._mazesolver_init(3)
    trail0 = len(app.mazesolver_wf_trail)
    for _ in range(10):
        app._mazesolver_step()
    assert len(app.mazesolver_wf_trail) > trail0


# ── Edge cases ──


def test_empty_queue_marks_no_path():
    """If BFS queue empties without finding end, should report no path."""
    app = _make_app()
    app._mazesolver_init(1)  # BFS
    # Clear the queue to simulate no path
    app.mazesolver_solve_queue = []
    app._mazesolver_step()
    assert app.mazesolver_solve_done is True
    assert app.mazesolver_phase == "done"


def test_astar_empty_queue_marks_no_path():
    app = _make_app()
    app._mazesolver_init(0)  # A*
    app.mazesolver_solve_queue = []
    app._mazesolver_step()
    assert app.mazesolver_solve_done is True
