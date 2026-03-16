"""Mode: reverse_life — Constraint-solver that runs the Game of Life backwards.

Given any GoL configuration, this mode uses constraint propagation and
backtracking to find predecessor states — configurations that produce the
current pattern when stepped forward one generation.  It effectively runs
time in reverse.

The solver's search process is visualized live: candidate cells flicker as
the algorithm explores possibilities, dead-ends flash red, and solutions
cascade in green.  The mode also detects **Garden of Eden** patterns
(configurations with no possible predecessor), one of the deepest results
in cellular automaton theory.

Keys:
    SPC     Start/pause the solver
    Enter   Accept current solution & step backwards again
    n       Find next alternative predecessor (if one exists)
    r       Reset solver, keep current pattern
    g       Check if current pattern is a Garden of Eden
    s       Cycle solver speed (slow/medium/fast/instant)
    v       Cycle view mode (solver / solution / overlay / diff)
    c       Toggle constraint-propagation visualization
    d       Cycle display (cells / search-tree / stats)
    p       Place a preset pattern to solve
    +/-     Grow/shrink search region
    h       Toggle help overlay
    q       Quit mode
"""
import curses
import math
import random
import time

from life.grid import Grid
from life.rules import rule_string

# ── Constants ────────────────────────────────────────────────────────

_SPARKLINE = "▁▂▃▄▅▆▇█"

# Solver speed presets: (label, cells-per-frame)
_SPEEDS = [
    ("slow", 1),
    ("medium", 5),
    ("fast", 25),
    ("instant", 0),  # 0 = run to completion
]

_VIEW_MODES = ["solver", "solution", "overlay", "diff"]
_DISPLAY_MODES = ["cells", "search-tree", "stats"]

# Color pair offsets (we'll use pairs 80-89)
_CP_DEAD = 0        # default
_CP_ALIVE = 1       # current pattern cell
_CP_CANDIDATE = 2   # solver is considering this cell
_CP_CONFIRMED = 3   # cell confirmed alive in predecessor
_CP_REJECTED = 4    # cell ruled out (dead-end)
_CP_SOLUTION = 5    # final solution cell
_CP_GARDEN = 6      # Garden of Eden indicator
_CP_HEADER = 7      # header text
_CP_DIM = 8         # dimmed text

_PAIR_BASE = 80

# Preset patterns to try reverse-solving
_PRESETS = [
    ("Block", [(0, 0), (0, 1), (1, 0), (1, 1)]),
    ("Blinker (phase 1)", [(0, -1), (0, 0), (0, 1)]),
    ("Blinker (phase 2)", [(-1, 0), (0, 0), (1, 0)]),
    ("Glider", [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]),
    ("Beehive", [(0, 1), (0, 2), (1, 0), (1, 3), (2, 1), (2, 2)]),
    ("Loaf", [(0, 1), (0, 2), (1, 0), (1, 3), (2, 1), (2, 3), (3, 2)]),
    ("Toad", [(0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2)]),
    ("Beacon", [(0, 0), (0, 1), (1, 0), (2, 3), (3, 2), (3, 3)]),
    ("R-pentomino result", []),  # filled dynamically
]


# ── Constraint Propagation Solver ────────────────────────────────────

class _CellState:
    """Tri-state for a predecessor cell: UNKNOWN, ALIVE, or DEAD."""
    UNKNOWN = 0
    ALIVE = 1
    DEAD = 2


class _ReverseSolver:
    """SAT-lite solver for GoL predecessor finding.

    For each cell (r,c) in the predecessor grid, we have a variable that
    is ALIVE or DEAD.  The constraint for each cell (r,c) in the *target*
    is determined by GoL rules applied to the predecessor's (r,c) and its
    8 neighbors.

    We use constraint propagation to prune, then backtrack on remaining
    unknowns.
    """

    def __init__(self, target, rows, cols, birth=None, survival=None):
        self.target = target  # target[r][c] = True/False
        self.rows = rows
        self.cols = cols
        self.birth = birth or {3}
        self.survival = survival or {2, 3}

        # Predecessor state: rows x cols of _CellState
        self.pred = [[_CellState.UNKNOWN] * cols for _ in range(rows)]

        # Search statistics
        self.backtracks = 0
        self.propagations = 0
        self.cells_decided = 0
        self.total_cells = rows * cols
        self.start_time = 0.0

        # For visualization
        self.current_cell = None      # (r, c) being considered
        self.last_backtrack = None    # (r, c) of last dead-end
        self.confirmed_cells = set()  # cells confirmed so far
        self.rejected_cells = set()   # cells that flashed red (dead-end)
        self.exploring = set()        # cells currently being explored

        # Solution storage
        self.solutions = []
        self.is_garden_of_eden = False
        self.solved = False
        self.failed = False

        # Generator-based solver for incremental execution
        self._solver_gen = None
        self._paused = False

    def _neighbors(self, r, c):
        """Return list of neighbor coordinates (with wrapping)."""
        nbrs = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr = (r + dr) % self.rows
                nc = (c + dc) % self.cols
                nbrs.append((nr, nc))
        return nbrs

    def _count_neighbor_states(self, r, c):
        """Count alive, dead, unknown among neighbors of (r,c) in predecessor."""
        alive = dead = unknown = 0
        for nr, nc in self._neighbors(r, c):
            s = self.pred[nr][nc]
            if s == _CellState.ALIVE:
                alive += 1
            elif s == _CellState.DEAD:
                dead += 1
            else:
                unknown += 1
        return alive, dead, unknown

    def _is_consistent(self, r, c):
        """Check if predecessor assignments around (r,c) are consistent
        with target[r][c] given GoL rules.

        Returns True if still possibly consistent, False if violated.
        """
        alive_n, dead_n, unknown_n = self._count_neighbor_states(r, c)
        cell_state = self.pred[r][c]
        target_alive = self.target[r][c]

        # Can't check if the cell itself is unknown
        if cell_state == _CellState.UNKNOWN:
            return True

        max_alive_n = alive_n + unknown_n
        min_alive_n = alive_n

        if target_alive:
            # Target cell is alive => predecessor cell was alive & survived,
            # OR predecessor cell was dead & born
            if cell_state == _CellState.ALIVE:
                # Need neighbor count in survival set
                # Check if any count in [min_alive_n, max_alive_n] is in survival
                possible = any(n in self.survival
                               for n in range(min_alive_n, max_alive_n + 1))
                if not possible:
                    return False
            else:
                # Dead cell that becomes alive => birth
                possible = any(n in self.birth
                               for n in range(min_alive_n, max_alive_n + 1))
                if not possible:
                    return False
        else:
            # Target cell is dead => predecessor cell was alive & didn't survive,
            # OR predecessor cell was dead & wasn't born
            if cell_state == _CellState.ALIVE:
                # Need neighbor count NOT in survival set
                # If all possible counts are in survival, inconsistent
                if all(n in self.survival
                       for n in range(min_alive_n, max_alive_n + 1)):
                    return False
            else:
                # Dead cell stays dead => count NOT in birth set
                if all(n in self.birth
                       for n in range(min_alive_n, max_alive_n + 1)):
                    return False

        return True

    def _propagate(self):
        """Run constraint propagation.  Returns False if contradiction found."""
        changed = True
        while changed:
            changed = False
            self.propagations += 1
            for r in range(self.rows):
                for c in range(self.cols):
                    if not self._is_consistent(r, c):
                        return False

                    # Try to force unknown neighbors
                    if self.pred[r][c] != _CellState.UNKNOWN:
                        continue

                    # Try setting to ALIVE
                    self.pred[r][c] = _CellState.ALIVE
                    alive_ok = all(
                        self._is_consistent(nr, nc)
                        for nr, nc in self._neighbors(r, c) + [(r, c)]
                    )

                    # Try setting to DEAD
                    self.pred[r][c] = _CellState.DEAD
                    dead_ok = all(
                        self._is_consistent(nr, nc)
                        for nr, nc in self._neighbors(r, c) + [(r, c)]
                    )

                    self.pred[r][c] = _CellState.UNKNOWN

                    if not alive_ok and not dead_ok:
                        return False
                    elif alive_ok and not dead_ok:
                        self.pred[r][c] = _CellState.ALIVE
                        self.confirmed_cells.add((r, c))
                        self.cells_decided += 1
                        changed = True
                    elif dead_ok and not alive_ok:
                        self.pred[r][c] = _CellState.DEAD
                        self.cells_decided += 1
                        changed = True
        return True

    def _pick_variable(self):
        """Choose next unknown cell to branch on (most-constrained heuristic)."""
        best = None
        best_score = -1
        for r in range(self.rows):
            for c in range(self.cols):
                if self.pred[r][c] != _CellState.UNKNOWN:
                    continue
                # Score: number of decided neighbors (higher = more constrained)
                score = sum(1 for nr, nc in self._neighbors(r, c)
                            if self.pred[nr][nc] != _CellState.UNKNOWN)
                if score > best_score:
                    best_score = score
                    best = (r, c)
        return best

    def _snapshot(self):
        """Save current predecessor state."""
        return [row[:] for row in self.pred]

    def _restore(self, snap):
        """Restore predecessor state from snapshot."""
        for r in range(self.rows):
            for c in range(self.cols):
                self.pred[r][c] = snap[r][c]

    def _verify_solution(self):
        """Verify that the predecessor, when stepped forward, produces the target."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.pred[r][c] == _CellState.UNKNOWN:
                    return False

        # Step forward and compare
        for r in range(self.rows):
            for c in range(self.cols):
                alive_n = sum(1 for nr, nc in self._neighbors(r, c)
                              if self.pred[nr][nc] == _CellState.ALIVE)
                cell_alive = self.pred[r][c] == _CellState.ALIVE

                if cell_alive:
                    next_alive = alive_n in self.survival
                else:
                    next_alive = alive_n in self.birth

                if next_alive != self.target[r][c]:
                    return False
        return True

    def solve_step(self):
        """Execute one step of the solver generator.  Returns True if still running."""
        if self._solver_gen is None:
            self._solver_gen = self._solve_generator()
            self.start_time = time.time()

        try:
            next(self._solver_gen)
            return True
        except StopIteration:
            return False

    def _solve_generator(self):
        """Generator that yields after each significant solver step for visualization."""
        # Initial propagation
        if not self._propagate():
            self.is_garden_of_eden = True
            self.failed = True
            return

        yield  # show propagation results

        # Backtracking search
        stack = []

        while True:
            var = self._pick_variable()
            if var is None:
                # All variables assigned — verify
                if self._verify_solution():
                    sol = [row[:] for row in self.pred]
                    self.solutions.append(sol)
                    self.solved = True
                    return
                else:
                    # Should not happen if propagation is correct, but backtrack
                    if not stack:
                        self.is_garden_of_eden = True
                        self.failed = True
                        return

            if var is None:
                return

            r, c = var
            self.current_cell = (r, c)
            self.exploring.add((r, c))
            yield  # show which cell we're exploring

            # Try ALIVE first, then DEAD
            snap = self._snapshot()
            tried_alive = False

            for try_state in (_CellState.ALIVE, _CellState.DEAD):
                self.pred[r][c] = try_state
                self.cells_decided += 1

                if try_state == _CellState.ALIVE:
                    self.confirmed_cells.add((r, c))
                    tried_alive = True

                # Check local consistency
                consistent = self._is_consistent(r, c)
                if consistent:
                    for nr, nc in self._neighbors(r, c):
                        if not self._is_consistent(nr, nc):
                            consistent = False
                            break

                if consistent and self._propagate():
                    # Push to stack and continue
                    stack.append((r, c, try_state, snap))
                    self.exploring.discard((r, c))
                    yield
                    break
                else:
                    # Restore and try next value
                    self._restore(snap)
                    self.pred[r][c] = _CellState.UNKNOWN
                    self.cells_decided -= 1
                    if try_state == _CellState.ALIVE:
                        self.confirmed_cells.discard((r, c))
                        self.rejected_cells.add((r, c))
                    self.backtracks += 1
                    self.last_backtrack = (r, c)
                    yield  # show backtrack
            else:
                # Both values failed — need to backtrack further
                self.exploring.discard((r, c))
                self.rejected_cells.add((r, c))

                backtracked = False
                while stack:
                    prev_r, prev_c, prev_state, prev_snap = stack.pop()
                    self._restore(prev_snap)
                    self.backtracks += 1
                    self.last_backtrack = (prev_r, prev_c)

                    if prev_state == _CellState.ALIVE:
                        # Try DEAD instead
                        self.pred[prev_r][prev_c] = _CellState.DEAD
                        self.cells_decided += 1
                        self.confirmed_cells.discard((prev_r, prev_c))

                        consistent = self._is_consistent(prev_r, prev_c)
                        if consistent:
                            for nr, nc in self._neighbors(prev_r, prev_c):
                                if not self._is_consistent(nr, nc):
                                    consistent = False
                                    break

                        if consistent and self._propagate():
                            stack.append((prev_r, prev_c, _CellState.DEAD, prev_snap))
                            backtracked = True
                            yield
                            break
                        else:
                            self._restore(prev_snap)
                            self.cells_decided -= 1

                    yield  # show backtrack progress

                if not backtracked and not stack:
                    self.is_garden_of_eden = True
                    self.failed = True
                    return

    def get_solution_grid(self):
        """Return the solution as a 2D list of 0/1."""
        if not self.solutions:
            return None
        sol = self.solutions[-1]
        return [[1 if sol[r][c] == _CellState.ALIVE else 0
                 for c in range(self.cols)]
                for r in range(self.rows)]

    def progress(self):
        """Return solver progress as fraction 0..1."""
        if self.total_cells == 0:
            return 1.0
        decided = sum(1 for r in range(self.rows) for c in range(self.cols)
                      if self.pred[r][c] != _CellState.UNKNOWN)
        return decided / self.total_cells


# ── Mode functions ───────────────────────────────────────────────────

def _enter_reverse_life_mode(self):
    """Initialize Reverse Life mode."""
    self.reverse_life_mode = True
    self.reverse_life_running = False
    self.reverse_life_help = False
    self.reverse_life_speed_idx = 1  # medium
    self.reverse_life_view_idx = 0   # solver view
    self.reverse_life_display_idx = 0  # cells display
    self.reverse_life_show_constraints = True
    self.reverse_life_preset_idx = 0
    self.reverse_life_search_pad = 2  # extra rows/cols around pattern
    self.reverse_life_steps_back = 0  # how many times we've reversed
    self.reverse_life_history = []    # list of solution grids

    # Initialize color pairs
    try:
        curses.init_pair(_PAIR_BASE + _CP_ALIVE, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(_PAIR_BASE + _CP_CANDIDATE, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(_PAIR_BASE + _CP_CONFIRMED, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(_PAIR_BASE + _CP_REJECTED, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(_PAIR_BASE + _CP_SOLUTION, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(_PAIR_BASE + _CP_GARDEN, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(_PAIR_BASE + _CP_HEADER, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(_PAIR_BASE + _CP_DIM, curses.COLOR_WHITE, curses.COLOR_BLACK)
    except curses.error:
        pass

    # Capture current grid state as target
    _capture_target(self)

    # Create solver
    _init_solver(self)


def _capture_target(self):
    """Capture the current grid as the target pattern."""
    g = self.grid
    rows, cols = g.rows, g.cols
    self.reverse_life_target = [
        [g.cells[r][c] > 0 for c in range(cols)]
        for r in range(rows)
    ]
    self.reverse_life_target_rows = rows
    self.reverse_life_target_cols = cols


def _init_solver(self):
    """Create a fresh solver for the current target."""
    rows = self.reverse_life_target_rows
    cols = self.reverse_life_target_cols
    self.reverse_life_solver = _ReverseSolver(
        self.reverse_life_target, rows, cols,
        birth=self.grid.birth, survival=self.grid.survival,
    )
    self.reverse_life_running = False


def _exit_reverse_life_mode(self):
    """Clean up Reverse Life mode."""
    self.reverse_life_mode = False
    self.reverse_life_solver = None


def _handle_reverse_life_key(self, key):
    """Handle keyboard input for Reverse Life mode."""
    if key == ord('q'):
        _exit_reverse_life_mode(self)
        return True

    if key == ord('h'):
        self.reverse_life_help = not self.reverse_life_help
        return True

    if self.reverse_life_help:
        return True  # consume all keys while help is shown

    solver = self.reverse_life_solver

    if key == ord(' '):
        if solver and (solver.solved or solver.failed):
            pass  # can't resume finished solver
        else:
            self.reverse_life_running = not self.reverse_life_running
        return True

    if key == 10:  # Enter — accept solution and reverse again
        if solver and solver.solved:
            sol_grid = solver.get_solution_grid()
            if sol_grid:
                # Save current target to history
                self.reverse_life_history.append(self.reverse_life_target)
                # Set solution as new target
                self.reverse_life_target = [
                    [sol_grid[r][c] > 0 for c in range(len(sol_grid[0]))]
                    for r in range(len(sol_grid))
                ]
                # Update grid display
                for r in range(min(self.grid.rows, len(sol_grid))):
                    for c in range(min(self.grid.cols, len(sol_grid[0]))):
                        self.grid.cells[r][c] = sol_grid[r][c]
                self.reverse_life_steps_back += 1
                _init_solver(self)
        return True

    if key == ord('n'):  # find next alternative
        if solver and solver.solved:
            # Reset and find another solution (simplified: just restart)
            _init_solver(self)
            self.reverse_life_running = True
        return True

    if key == ord('r'):
        _init_solver(self)
        return True

    if key == ord('g'):
        # Quick Garden of Eden check — run solver to completion
        if solver and not solver.solved and not solver.failed:
            while solver.solve_step():
                pass
            self.reverse_life_running = False
        return True

    if key == ord('s'):
        self.reverse_life_speed_idx = (
            (self.reverse_life_speed_idx + 1) % len(_SPEEDS)
        )
        return True

    if key == ord('v'):
        self.reverse_life_view_idx = (
            (self.reverse_life_view_idx + 1) % len(_VIEW_MODES)
        )
        return True

    if key == ord('c'):
        self.reverse_life_show_constraints = not self.reverse_life_show_constraints
        return True

    if key == ord('d'):
        self.reverse_life_display_idx = (
            (self.reverse_life_display_idx + 1) % len(_DISPLAY_MODES)
        )
        return True

    if key == ord('p'):
        # Cycle preset patterns
        self.reverse_life_preset_idx = (
            (self.reverse_life_preset_idx + 1) % len(_PRESETS)
        )
        _load_preset(self)
        return True

    if key in (ord('+'), ord('=')):
        self.reverse_life_search_pad = min(self.reverse_life_search_pad + 1, 10)
        return True

    if key == ord('-'):
        self.reverse_life_search_pad = max(self.reverse_life_search_pad - 1, 0)
        return True

    return False


def _load_preset(self):
    """Load a preset pattern into the grid and set as target."""
    name, cells = _PRESETS[self.reverse_life_preset_idx]

    # Handle special dynamic presets
    if name == "R-pentomino result":
        # Run R-pentomino forward 50 gens
        g = Grid(self.grid.rows, self.grid.cols)
        cr, cc = g.rows // 2, g.cols // 2
        for dr, dc in [(-1, 0), (0, -1), (0, 0), (0, 1), (1, -1)]:
            r, c = cr + dr, cc + dc
            if 0 <= r < g.rows and 0 <= c < g.cols:
                g.cells[r][c] = 1
        for _ in range(50):
            g.step()
        for r in range(g.rows):
            for c in range(g.cols):
                self.grid.cells[r][c] = g.cells[r][c]
    else:
        # Clear grid and place pattern centered
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                self.grid.cells[r][c] = 0
        cr, cc = self.grid.rows // 2, self.grid.cols // 2
        for dr, dc in cells:
            r, c = cr + dr, cc + dc
            if 0 <= r < self.grid.rows and 0 <= c < self.grid.cols:
                self.grid.cells[r][c] = 1

    _capture_target(self)
    _init_solver(self)


def _reverse_life_step(self):
    """Advance the solver by the configured number of steps per frame."""
    solver = self.reverse_life_solver
    if solver is None or solver.solved or solver.failed:
        self.reverse_life_running = False
        return

    speed_label, cells_per_frame = _SPEEDS[self.reverse_life_speed_idx]

    if cells_per_frame == 0:
        # Instant: run to completion
        while solver.solve_step():
            pass
        self.reverse_life_running = False
    else:
        for _ in range(cells_per_frame):
            if not solver.solve_step():
                self.reverse_life_running = False
                break


def _is_reverse_life_auto_stepping(self):
    """Check if solver is actively running."""
    return getattr(self, 'reverse_life_running', False)


def _draw_reverse_life(self):
    """Render the Reverse Life mode display."""
    scr = self.stdscr
    scr.erase()
    max_y, max_x = scr.getmaxyx()
    if max_y < 5 or max_x < 20:
        return

    solver = self.reverse_life_solver
    view = _VIEW_MODES[self.reverse_life_view_idx]
    display = _DISPLAY_MODES[self.reverse_life_display_idx]

    # ── Header ──
    hdr_pair = curses.color_pair(_PAIR_BASE + _CP_HEADER)
    dim_pair = curses.color_pair(_PAIR_BASE + _CP_DIM)

    status = "SOLVING" if self.reverse_life_running else "PAUSED"
    if solver and solver.solved:
        status = "SOLVED"
    elif solver and solver.failed:
        status = "GARDEN OF EDEN" if solver.is_garden_of_eden else "FAILED"

    hdr = f" REVERSE LIFE — {status} "
    try:
        scr.addstr(0, max(0, (max_x - len(hdr)) // 2), hdr, hdr_pair | curses.A_BOLD)
    except curses.error:
        pass

    # ── Info bar ──
    row = 1
    speed_label = _SPEEDS[self.reverse_life_speed_idx][0]
    info = (
        f" View: {view}  Speed: {speed_label}  "
        f"Steps back: {self.reverse_life_steps_back}  "
        f"Rule: {rule_string(self.grid.birth, self.grid.survival)}"
    )
    try:
        scr.addstr(row, 0, info[:max_x - 1], dim_pair)
    except curses.error:
        pass

    # ── Solver stats ──
    row = 2
    if solver:
        prog = solver.progress()
        bar_w = 20
        filled = int(prog * bar_w)
        bar = "█" * filled + "░" * (bar_w - filled)
        elapsed = time.time() - solver.start_time if solver.start_time else 0
        stats = (
            f" Progress: [{bar}] {prog:.0%}  "
            f"Backtracks: {solver.backtracks}  "
            f"Propagations: {solver.propagations}  "
            f"Time: {elapsed:.1f}s"
        )
        try:
            scr.addstr(row, 0, stats[:max_x - 1], dim_pair)
        except curses.error:
            pass

    # ── Help overlay ──
    if self.reverse_life_help:
        _draw_help(self, scr, max_y, max_x)
        return

    # ── Main grid display ──
    grid_top = 4
    grid_rows = min(self.grid.rows, max_y - grid_top - 3)
    grid_cols = min(self.grid.cols, (max_x - 1) // 2)

    if display == "cells":
        _draw_grid_view(self, scr, grid_top, grid_rows, grid_cols, view)
    elif display == "search-tree":
        _draw_search_tree(self, scr, grid_top, max_y, max_x)
    elif display == "stats":
        _draw_stats_panel(self, scr, grid_top, max_y, max_x)

    # ── Garden of Eden message ──
    if solver and solver.is_garden_of_eden:
        msg = " ★ GARDEN OF EDEN — No predecessor exists! ★ "
        gy = min(max_y - 2, grid_top + grid_rows + 1)
        gx = max(0, (max_x - len(msg)) // 2)
        try:
            scr.addstr(gy, gx, msg,
                       curses.color_pair(_PAIR_BASE + _CP_GARDEN) | curses.A_BOLD)
        except curses.error:
            pass

    # ── Solution found message ──
    elif solver and solver.solved:
        msg = " ✓ Predecessor found! Press Enter to reverse, n for alternative "
        gy = min(max_y - 2, grid_top + grid_rows + 1)
        gx = max(0, (max_x - len(msg)) // 2)
        try:
            scr.addstr(gy, gx, msg,
                       curses.color_pair(_PAIR_BASE + _CP_SOLUTION) | curses.A_BOLD)
        except curses.error:
            pass

    # ── Bottom bar ──
    bot = f" [SPC] {'Pause' if self.reverse_life_running else 'Start'}  [h] Help  [v] View  [s] Speed  [p] Preset  [q] Quit "
    try:
        scr.addstr(max_y - 1, 0, bot[:max_x - 1], dim_pair)
    except curses.error:
        pass


def _draw_grid_view(self, scr, top, rows, cols, view):
    """Draw the grid with solver visualization."""
    solver = self.reverse_life_solver
    target = self.reverse_life_target

    for r in range(rows):
        for c in range(cols):
            sx = c * 2
            sy = top + r

            # Determine what to show based on view mode
            ch = "  "
            pair = 0

            target_alive = (r < len(target) and c < len(target[0])
                            and target[r][c])

            if view == "solver" and solver:
                cell_state = solver.pred[r][c] if r < solver.rows and c < solver.cols else _CellState.UNKNOWN

                if cell_state == _CellState.ALIVE:
                    if (r, c) in solver.confirmed_cells:
                        ch = "██"
                        pair = _PAIR_BASE + _CP_CONFIRMED
                    else:
                        ch = "██"
                        pair = _PAIR_BASE + _CP_SOLUTION
                elif cell_state == _CellState.DEAD:
                    if (r, c) in solver.rejected_cells:
                        ch = "░░"
                        pair = _PAIR_BASE + _CP_REJECTED
                    else:
                        ch = "  "
                        pair = 0
                else:  # UNKNOWN
                    if solver.current_cell == (r, c):
                        ch = "▓▓"
                        pair = _PAIR_BASE + _CP_CANDIDATE
                    elif (r, c) in solver.exploring:
                        ch = "░░"
                        pair = _PAIR_BASE + _CP_CANDIDATE
                    else:
                        ch = "··"
                        pair = _PAIR_BASE + _CP_DIM

            elif view == "solution" and solver and solver.solved:
                sol = solver.get_solution_grid()
                if sol and r < len(sol) and c < len(sol[0]) and sol[r][c]:
                    ch = "██"
                    pair = _PAIR_BASE + _CP_SOLUTION
                else:
                    ch = "  "

            elif view == "overlay":
                if target_alive:
                    ch = "██"
                    pair = _PAIR_BASE + _CP_ALIVE
                if solver and r < solver.rows and c < solver.cols:
                    if solver.pred[r][c] == _CellState.ALIVE:
                        ch = "▓▓" if target_alive else "░░"
                        pair = _PAIR_BASE + _CP_CONFIRMED

            elif view == "diff" and solver and solver.solved:
                sol = solver.get_solution_grid()
                sol_alive = (sol and r < len(sol) and c < len(sol[0])
                             and sol[r][c])
                if target_alive and sol_alive:
                    ch = "██"
                    pair = _PAIR_BASE + _CP_ALIVE
                elif target_alive and not sol_alive:
                    ch = "▓▓"
                    pair = _PAIR_BASE + _CP_REJECTED  # born this step
                elif sol_alive and not target_alive:
                    ch = "░░"
                    pair = _PAIR_BASE + _CP_CANDIDATE  # died this step
                else:
                    ch = "  "
            else:
                # Default: show target
                if target_alive:
                    ch = "██"
                    pair = _PAIR_BASE + _CP_ALIVE

            try:
                scr.addstr(sy, sx, ch, curses.color_pair(pair) if pair else 0)
            except curses.error:
                pass


def _draw_search_tree(self, scr, top, max_y, max_x):
    """Draw a visualization of the solver's search progress."""
    solver = self.reverse_life_solver
    if not solver:
        return

    row = top
    try:
        scr.addstr(row, 1, "Search Tree Visualization", curses.A_BOLD)
        row += 1

        # Show a sparkline of progress over the grid
        if solver.rows > 0 and solver.cols > 0:
            for r in range(min(solver.rows, max_y - row - 3)):
                line = ""
                for c in range(min(solver.cols, max_x - 2)):
                    s = solver.pred[r][c]
                    if s == _CellState.ALIVE:
                        line += "█"
                    elif s == _CellState.DEAD:
                        line += "·"
                    else:
                        line += "?"
                scr.addstr(row, 1, line[:max_x - 2])
                row += 1
                if row >= max_y - 2:
                    break
    except curses.error:
        pass


def _draw_stats_panel(self, scr, top, max_y, max_x):
    """Draw detailed solver statistics."""
    solver = self.reverse_life_solver
    if not solver:
        return

    row = top
    stats = [
        ("Grid size", f"{solver.rows} × {solver.cols} = {solver.total_cells} cells"),
        ("Progress", f"{solver.progress():.1%}"),
        ("Cells decided", f"{solver.cells_decided}"),
        ("Backtracks", f"{solver.backtracks}"),
        ("Propagation passes", f"{solver.propagations}"),
        ("Solutions found", f"{len(solver.solutions)}"),
        ("Garden of Eden", "YES" if solver.is_garden_of_eden else "No (so far)"),
        ("Status", "Solved" if solver.solved else "Failed" if solver.failed else "In progress"),
        ("", ""),
        ("Rule", rule_string(solver.birth, solver.survival)),
        ("Birth set", str(solver.birth)),
        ("Survival set", str(solver.survival)),
        ("", ""),
        ("Elapsed",
         f"{time.time() - solver.start_time:.1f}s" if solver.start_time else "—"),
        ("Steps reversed", str(self.reverse_life_steps_back)),
    ]

    hdr_pair = curses.color_pair(_PAIR_BASE + _CP_HEADER)
    dim_pair = curses.color_pair(_PAIR_BASE + _CP_DIM)

    try:
        scr.addstr(row, 1, "Solver Statistics", hdr_pair | curses.A_BOLD)
        row += 1
        scr.addstr(row, 1, "─" * min(40, max_x - 2), dim_pair)
        row += 1

        for label, value in stats:
            if row >= max_y - 2:
                break
            if not label:
                row += 1
                continue
            line = f"  {label:.<24s} {value}"
            scr.addstr(row, 1, line[:max_x - 2], dim_pair)
            row += 1
    except curses.error:
        pass


def _draw_help(self, scr, max_y, max_x):
    """Draw the help overlay."""
    lines = [
        "",
        "  REVERSE LIFE — Constraint Solver",
        "  ─────────────────────────────────",
        "",
        "  Finds predecessor states that produce the",
        "  current pattern when stepped forward.",
        "",
        "  Controls:",
        "    SPC     Start / pause solver",
        "    Enter   Accept solution, reverse again",
        "    n       Find next alternative predecessor",
        "    r       Reset solver",
        "    g       Run to completion (Garden of Eden check)",
        "    s       Cycle speed (slow/med/fast/instant)",
        "    v       Cycle view (solver/solution/overlay/diff)",
        "    c       Toggle constraint visualization",
        "    d       Cycle display (cells/search-tree/stats)",
        "    p       Place preset pattern",
        "    +/-     Adjust search padding",
        "    h       Close this help",
        "    q       Quit mode",
        "",
        "  Legend:",
        "    ██ green   Confirmed alive in predecessor",
        "    ▓▓ yellow  Currently exploring",
        "    ░░ red     Dead-end / rejected",
        "    ··         Unknown (not yet decided)",
        "",
        "  Garden of Eden patterns have NO predecessor —",
        "  they can only appear as initial conditions.",
        "",
    ]

    hdr_pair = curses.color_pair(_PAIR_BASE + _CP_HEADER)

    for i, line in enumerate(lines):
        if i + 3 >= max_y:
            break
        try:
            scr.addstr(3 + i, 1, line[:max_x - 2], hdr_pair)
        except curses.error:
            pass


# ── Registration ─────────────────────────────────────────────────────

def register(App):
    """Attach Reverse Life mode methods to the App class."""
    App._enter_reverse_life_mode = _enter_reverse_life_mode
    App._exit_reverse_life_mode = _exit_reverse_life_mode
    App._handle_reverse_life_key = _handle_reverse_life_key
    App._draw_reverse_life = _draw_reverse_life
    App._reverse_life_step = _reverse_life_step
    App._is_reverse_life_auto_stepping = _is_reverse_life_auto_stepping
