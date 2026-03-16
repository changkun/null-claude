"""Mode: Butterfly Effect — fork a simulation, perturb one cell, visualize divergence.

Pause any running simulation, mark a "what-if" point, flip a single cell, then
watch both timelines evolve in parallel with a real-time divergence heatmap
overlay showing exactly how and where the perturbation cascades.

Keys:
  Ctrl+B            — enter Butterfly Effect mode (snapshot current state)
  Click / arrows+Enter — select the cell to perturb
  Space              — play/pause both timelines
  n / .              — single-step both timelines
  d                  — cycle divergence view: heatmap / side-by-side / overlay
  h                  — toggle cumulative heatmap vs instantaneous diff
  c                  — toggle color scale (linear / log)
  r                  — reset and pick a new perturbation cell
  </> , .            — adjust speed
  Ctrl+B             — exit Butterfly Effect mode
"""

import curses
import math
import time

from life.colors import color_for_age, truecolor_available
from life.constants import CELL_CHAR, SPEED_LABELS
from life.grid import Grid
from life.utils import sparkline


# ── Divergence view modes ──

VIEW_HEATMAP = 0      # full-screen original with heatmap overlay
VIEW_SIDE_BY_SIDE = 1  # split-screen original vs perturbed
VIEW_OVERLAY = 2       # blended overlay showing both states
VIEW_NAMES = ["Heatmap Overlay", "Side-by-Side", "Dual Overlay"]


# ── State initialization ──

def _butterfly_init(self):
    """Initialize butterfly-effect state variables."""
    self.butterfly_mode = False          # whether butterfly mode is active
    self.butterfly_picking = False       # whether user is picking perturbation cell
    self.butterfly_running = False       # whether both timelines are advancing
    self.butterfly_grid: Grid | None = None  # the perturbed timeline grid
    self.butterfly_pop_history: list[int] = []
    self.butterfly_origin_gen = 0        # generation at fork point
    self.butterfly_perturb_r = -1        # row of perturbed cell
    self.butterfly_perturb_c = -1        # col of perturbed cell
    self.butterfly_perturb_was_alive = False  # original state of perturbed cell
    self.butterfly_view = VIEW_HEATMAP   # current visualization mode
    self.butterfly_cumulative = True     # cumulative vs instantaneous heatmap
    self.butterfly_log_scale = False     # log vs linear color scaling
    self.butterfly_heat = None           # cumulative divergence heatmap (2D list)
    self.butterfly_pick_r = 0            # cursor row during picking
    self.butterfly_pick_c = 0            # cursor col during picking
    self.butterfly_divergence_pct = 0.0  # current divergence percentage
    self.butterfly_max_divergence = 0.0  # peak divergence seen
    self.butterfly_steps_since_fork = 0  # generations since perturbation


# ── Entry / exit ──

def _enter_butterfly_mode(self):
    """Enter butterfly effect mode: snapshot current grid, enter cell-picking."""
    # Snapshot the current grid into the butterfly grid (deep copy)
    self.butterfly_grid = Grid(self.grid.rows, self.grid.cols)
    for r in range(self.grid.rows):
        for c in range(self.grid.cols):
            self.butterfly_grid.cells[r][c] = self.grid.cells[r][c]
    self.butterfly_grid.generation = self.grid.generation
    self.butterfly_grid.population = self.grid.population
    self.butterfly_grid.birth = set(self.grid.birth)
    self.butterfly_grid.survival = set(self.grid.survival)
    self.butterfly_grid.hex_mode = self.grid.hex_mode
    self.butterfly_grid.topology = self.grid.topology

    self.butterfly_pop_history = list(self.pop_history)
    self.butterfly_origin_gen = self.grid.generation
    self.butterfly_steps_since_fork = 0
    self.butterfly_divergence_pct = 0.0
    self.butterfly_max_divergence = 0.0

    # Initialize heatmap
    self.butterfly_heat = [[0.0] * self.grid.cols for _ in range(self.grid.rows)]

    # Enter picking mode
    self.butterfly_mode = True
    self.butterfly_picking = True
    self.butterfly_running = False
    self.butterfly_pick_r = self.cursor_r
    self.butterfly_pick_c = self.cursor_c
    self.butterfly_view = VIEW_HEATMAP
    self.butterfly_cumulative = True
    self.butterfly_log_scale = False

    # Pause primary sim
    self.running = False

    self._flash("Butterfly Effect — pick a cell to perturb (arrows + Enter)")


def _exit_butterfly_mode(self):
    """Exit butterfly effect mode, clean up."""
    self.butterfly_mode = False
    self.butterfly_picking = False
    self.butterfly_running = False
    self.butterfly_grid = None
    self.butterfly_pop_history.clear()
    self.butterfly_heat = None
    self._flash("Butterfly Effect OFF")


def _butterfly_apply_perturbation(self):
    """Apply the single-cell perturbation to the butterfly grid."""
    r, c = self.butterfly_pick_r, self.butterfly_pick_c
    self.butterfly_perturb_r = r
    self.butterfly_perturb_c = c
    self.butterfly_perturb_was_alive = self.butterfly_grid.cells[r][c] > 0

    # Flip the cell
    if self.butterfly_perturb_was_alive:
        self.butterfly_grid.set_dead(r, c)
    else:
        self.butterfly_grid.set_alive(r, c)

    self.butterfly_picking = False
    action = "killed" if self.butterfly_perturb_was_alive else "spawned"
    self._flash(f"Perturbed ({r},{c}) — {action} cell. Space to play, n to step.")


# ── Key handling ──

def _butterfly_handle_key(self, key: int) -> bool:
    """Handle Ctrl+B to toggle butterfly mode. Returns True if consumed."""
    # Ctrl+B = 2
    if key == 2:
        if self.butterfly_mode:
            self._exit_butterfly_mode()
            return True
        else:
            # Only enter from base Game of Life mode (grid-based)
            self._enter_butterfly_mode()
            return True
    # Consume all keys while in butterfly mode
    if not self.butterfly_mode:
        return False

    if self.butterfly_picking:
        return self._butterfly_handle_pick_key(key)
    return self._butterfly_handle_run_key(key)


def _butterfly_handle_pick_key(self, key: int) -> bool:
    """Handle keys during cell-picking phase."""
    if key == -1:
        return True

    # Arrow keys to move pick cursor
    if key == curses.KEY_UP or key == ord("k"):
        self.butterfly_pick_r = max(0, self.butterfly_pick_r - 1)
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.butterfly_pick_r = min(self.grid.rows - 1, self.butterfly_pick_r + 1)
        return True
    if key == curses.KEY_LEFT or key == ord("h"):
        self.butterfly_pick_c = max(0, self.butterfly_pick_c - 1)
        return True
    if key == curses.KEY_RIGHT or key == ord("l"):
        self.butterfly_pick_c = min(self.grid.cols - 1, self.butterfly_pick_c + 1)
        return True

    # Enter to confirm pick
    if key in (10, 13, curses.KEY_ENTER):
        self._butterfly_apply_perturbation()
        return True

    # ESC or q to cancel
    if key == 27 or key == ord("q"):
        self._exit_butterfly_mode()
        return True

    return True


def _butterfly_handle_run_key(self, key: int) -> bool:
    """Handle keys during simulation phase."""
    if key == -1:
        return True

    # Space = play/pause
    if key == ord(" "):
        self.butterfly_running = not self.butterfly_running
        self._flash("Playing" if self.butterfly_running else "Paused")
        return True

    # n or . = single step
    if key == ord("n") or key == ord("."):
        self.butterfly_running = False
        _butterfly_step_once(self)
        return True

    # d = cycle divergence view
    if key == ord("d"):
        self.butterfly_view = (self.butterfly_view + 1) % 3
        self._flash(f"View: {VIEW_NAMES[self.butterfly_view]}")
        return True

    # h = toggle cumulative vs instantaneous
    if key == ord("h"):
        self.butterfly_cumulative = not self.butterfly_cumulative
        if not self.butterfly_cumulative:
            # Clear cumulative heatmap when switching to instantaneous
            self.butterfly_heat = [[0.0] * self.grid.cols for _ in range(self.grid.rows)]
        self._flash("Cumulative heatmap" if self.butterfly_cumulative else "Instantaneous diff")
        return True

    # c = toggle log scale
    if key == ord("c"):
        self.butterfly_log_scale = not self.butterfly_log_scale
        self._flash("Log scale" if self.butterfly_log_scale else "Linear scale")
        return True

    # r = reset perturbation
    if key == ord("r"):
        # Re-snapshot and go back to picking
        self._enter_butterfly_mode()
        return True

    # Speed controls
    if key == ord("<") or key == ord(","):
        if self.speed_idx > 0:
            self.speed_idx -= 1
            self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True
    if key == ord(">"):
        from life.constants import SPEEDS
        if self.speed_idx < len(SPEEDS) - 1:
            self.speed_idx += 1
            self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True

    # Arrow keys for scrolling viewport
    if key == curses.KEY_UP:
        self.cursor_r = max(0, self.cursor_r - 1)
        return True
    if key == curses.KEY_DOWN:
        self.cursor_r = min(self.grid.rows - 1, self.cursor_r + 1)
        return True
    if key == curses.KEY_LEFT:
        self.cursor_c = max(0, self.cursor_c - 1)
        return True
    if key == curses.KEY_RIGHT:
        self.cursor_c = min(self.grid.cols - 1, self.cursor_c + 1)
        return True

    # q = quit app
    if key == ord("q"):
        import sys
        sys.exit(0)

    return True  # consume all keys in butterfly mode


# ── Stepping ──

def _butterfly_step_once(self):
    """Step both grids one generation and update divergence tracking."""
    if not self.butterfly_mode or not self.butterfly_grid:
        return

    # Step primary grid
    self._push_history()
    self.grid.step()
    self._record_pop()

    # Step perturbed grid
    self.butterfly_grid.step()
    self.butterfly_pop_history.append(self.butterfly_grid.population)
    self.butterfly_steps_since_fork += 1

    # Update divergence heatmap
    _butterfly_update_heat(self)


def _butterfly_step(self):
    """Called from main loop when butterfly_running is True."""
    if not self.butterfly_mode or not self.butterfly_grid or not self.butterfly_running:
        return
    if self.butterfly_picking:
        return
    _butterfly_step_once(self)


def _butterfly_update_heat(self):
    """Recompute divergence metrics and update heatmap."""
    if not self.butterfly_grid or not self.butterfly_heat:
        return

    rows, cols = self.grid.rows, self.grid.cols
    diff_count = 0

    for r in range(rows):
        for c in range(cols):
            a = 1 if self.grid.cells[r][c] > 0 else 0
            b = 1 if self.butterfly_grid.cells[r][c] > 0 else 0
            diff = abs(a - b)
            if diff:
                diff_count += 1
            if self.butterfly_cumulative:
                self.butterfly_heat[r][c] += diff
            else:
                self.butterfly_heat[r][c] = float(diff)

    total = rows * cols
    self.butterfly_divergence_pct = diff_count / max(1, total) * 100
    self.butterfly_max_divergence = max(self.butterfly_max_divergence,
                                         self.butterfly_divergence_pct)


# ── Drawing: cell picking ──

def _butterfly_draw_pick(self, max_y: int, max_x: int):
    """Draw grid with cell-picking cursor for perturbation selection."""
    self.stdscr.erase()

    vis_rows = max_y - 4
    vis_cols = (max_x - 1) // 2
    zoom = self.zoom_level

    grid_vis_rows = vis_rows * zoom
    grid_vis_cols = vis_cols * zoom

    # Centre viewport on pick cursor
    view_r = self.butterfly_pick_r - grid_vis_rows // 2
    view_c = self.butterfly_pick_c - grid_vis_cols // 2

    # Draw grid cells
    for sy in range(min(vis_rows, max_y - 4)):
        for sx in range(min(vis_cols, (max_x - 1) // 2)):
            gr = (view_r + sy * zoom) % self.grid.rows
            gc = (view_c + sx * zoom) % self.grid.cols
            px = sx * 2
            py = sy
            if py >= max_y - 4 or px + 1 >= max_x:
                continue
            age = self.grid.cells[gr][gc]
            if age > 0:
                try:
                    self.stdscr.addstr(py, px, CELL_CHAR, color_for_age(age))
                except curses.error:
                    pass

    # Draw pick cursor (blinking crosshair)
    pick_sy = self.butterfly_pick_r - view_r
    pick_sx = self.butterfly_pick_c - view_c
    pick_py = pick_sy // zoom if zoom > 0 else pick_sy
    pick_px = (pick_sx // zoom if zoom > 0 else pick_sx) * 2

    blink = int(time.monotonic() * 4) % 2
    if 0 <= pick_py < vis_rows and 0 <= pick_px < max_x - 1:
        cell_val = self.grid.cells[self.butterfly_pick_r][self.butterfly_pick_c]
        ch = "X" if blink else ("O" if cell_val > 0 else "+")
        attr = curses.color_pair(5) | curses.A_BOLD
        try:
            self.stdscr.addstr(pick_py, pick_px, ch, attr)
        except curses.error:
            pass

        # Crosshair arms
        for delta in range(1, 4):
            for dy, dx in [(-1, 0), (1, 0), (0, -2), (0, 2)]:
                hy = pick_py + dy * delta
                hx = pick_px + dx * delta
                if 0 <= hy < vis_rows and 0 <= hx < max_x - 1:
                    try:
                        ch2 = "|" if dx == 0 else "-"
                        self.stdscr.addstr(hy, hx, ch2,
                                           curses.color_pair(5) | curses.A_DIM)
                    except curses.error:
                        pass

    # Info line
    cell_state = "ALIVE" if self.grid.cells[self.butterfly_pick_r][self.butterfly_pick_c] > 0 else "DEAD"
    info_y = max_y - 3
    if info_y > 0:
        info = f" Cell ({self.butterfly_pick_r},{self.butterfly_pick_c}) = {cell_state} | Gen {self.grid.generation} | Pop {self.grid.population}"
        try:
            self.stdscr.addstr(info_y, 0, info[:max_x - 1],
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

    # Title
    title_y = max_y - 2
    if title_y > 0:
        title = " BUTTERFLY EFFECT — Select cell to perturb"
        try:
            self.stdscr.addstr(title_y, 0, title[:max_x - 1],
                               curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

    # Hints
    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [Arrows/hjkl]=move  [Enter]=perturb  [Esc/q]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ── Drawing: heatmap color helpers ──

_HEAT_CHARS = " .:-=+*#%@"
_HEAT_RAMP = [
    (0, 0, 40),       # dark blue (no divergence)
    (0, 20, 100),      # blue
    (0, 80, 160),      # cyan-blue
    (0, 160, 160),     # cyan
    (40, 200, 80),     # green
    (160, 220, 0),     # yellow-green
    (220, 180, 0),     # yellow
    (240, 100, 0),     # orange
    (240, 40, 0),      # red-orange
    (220, 0, 0),       # red
    (255, 60, 180),    # hot pink (maximum)
]


def _heat_color_idx(val: float, max_val: float, log_scale: bool) -> int:
    """Map a heat value to a 0-10 index into the color ramp."""
    if max_val <= 0:
        return 0
    if log_scale:
        norm = math.log1p(val) / math.log1p(max_val)
    else:
        norm = val / max_val
    norm = max(0.0, min(1.0, norm))
    return min(10, int(norm * 10))


# ── Drawing: heatmap overlay view ──

def _butterfly_draw_heatmap(self, max_y: int, max_x: int):
    """Draw original grid with divergence heatmap overlay."""
    self.stdscr.erase()

    vis_rows = max_y - 6
    vis_cols = (max_x - 1) // 2
    zoom = self.zoom_level

    grid_vis_rows = vis_rows * zoom
    grid_vis_cols = vis_cols * zoom

    # Centre viewport on cursor
    view_r = self.cursor_r - grid_vis_rows // 2
    view_c = self.cursor_c - grid_vis_cols // 2

    # Find max heat for normalization
    max_heat = 0.0
    if self.butterfly_heat:
        for row in self.butterfly_heat:
            for v in row:
                if v > max_heat:
                    max_heat = v

    use_tc = truecolor_available()

    for sy in range(min(vis_rows, max_y - 6)):
        for sx in range(min(vis_cols, (max_x - 1) // 2)):
            gr = (view_r + sy * zoom) % self.grid.rows
            gc = (view_c + sx * zoom) % self.grid.cols
            px = sx * 2
            py = sy
            if py >= max_y - 6 or px + 1 >= max_x:
                continue

            age = self.grid.cells[gr][gc]
            heat = self.butterfly_heat[gr][gc] if self.butterfly_heat else 0.0

            if heat > 0:
                ci = _heat_color_idx(heat, max_heat, self.butterfly_log_scale)
                if use_tc and ci > 0:
                    rr, gg, bb = _HEAT_RAMP[ci]
                    # Use truecolor escape
                    ch = CELL_CHAR if age > 0 else _HEAT_CHARS[min(ci, len(_HEAT_CHARS) - 1)]
                    tc_str = f"\033[38;2;{rr};{gg};{bb}m{ch}\033[0m"
                    try:
                        self.stdscr.addstr(py, px, ch, curses.color_pair(
                            1 + min(ci // 2, 4)) | curses.A_BOLD)
                    except curses.error:
                        pass
                else:
                    # Fallback: use curses color pairs 1-5 (green→red age ramp)
                    pair = 1 + min(ci // 2, 4)
                    ch = CELL_CHAR if age > 0 else _HEAT_CHARS[min(ci, len(_HEAT_CHARS) - 1)]
                    try:
                        self.stdscr.addstr(py, px, ch,
                                           curses.color_pair(pair) | curses.A_BOLD)
                    except curses.error:
                        pass
            elif age > 0:
                try:
                    self.stdscr.addstr(py, px, CELL_CHAR, color_for_age(age) | curses.A_DIM)
                except curses.error:
                    pass

    # Draw perturbation marker
    if self.butterfly_perturb_r >= 0:
        pr_sy = self.butterfly_perturb_r - view_r
        pr_sx = self.butterfly_perturb_c - view_c
        pr_py = pr_sy // zoom if zoom > 0 else pr_sy
        pr_px = (pr_sx // zoom if zoom > 0 else pr_sx) * 2
        if 0 <= pr_py < vis_rows and 0 <= pr_px < max_x - 1:
            blink = int(time.monotonic() * 2) % 2
            if blink:
                try:
                    self.stdscr.addstr(pr_py, pr_px, "X",
                                       curses.color_pair(5) | curses.A_BOLD | curses.A_BLINK)
                except curses.error:
                    pass

    _butterfly_draw_status(self, max_y, max_x)


# ── Drawing: side-by-side view ──

def _butterfly_draw_split(self, max_y: int, max_x: int):
    """Draw original (left) vs perturbed (right) with divergence indicators."""
    self.stdscr.erase()

    half_x = max_x // 2
    divider_x = half_x
    vis_rows = max_y - 6

    left_cell_cols = divider_x // 2
    right_cell_cols = (max_x - divider_x - 1) // 2

    # Centre viewport on cursor
    view_r = self.cursor_r - vis_rows // 2
    view_c = self.cursor_c - left_cell_cols // 2

    # Draw left panel (original)
    for sy in range(min(vis_rows, self.grid.rows)):
        gr = (view_r + sy) % self.grid.rows
        for sx in range(min(left_cell_cols, self.grid.cols)):
            gc = (view_c + sx) % self.grid.cols
            age = self.grid.cells[gr][gc]
            px = sx * 2
            py = sy
            if py >= max_y - 6 or px + 1 >= divider_x:
                continue
            if age > 0:
                try:
                    self.stdscr.addstr(py, px, CELL_CHAR, color_for_age(age))
                except curses.error:
                    pass

    # Vertical divider
    for sy in range(min(vis_rows, max_y - 6)):
        try:
            self.stdscr.addstr(sy, divider_x, "│", curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    # Draw right panel (perturbed) with diff highlighting
    right_start = divider_x + 1
    for sy in range(min(vis_rows, self.butterfly_grid.rows)):
        gr = (view_r + sy) % self.butterfly_grid.rows
        for sx in range(min(right_cell_cols, self.butterfly_grid.cols)):
            gc = (view_c + sx) % self.butterfly_grid.cols
            age = self.butterfly_grid.cells[gr][gc]
            px = right_start + sx * 2
            py = sy
            if py >= max_y - 6 or px + 1 >= max_x:
                continue

            # Check if this cell differs from original
            orig_alive = self.grid.cells[gr][gc] > 0
            pert_alive = age > 0
            differs = orig_alive != pert_alive

            if age > 0:
                attr = curses.color_pair(5) | curses.A_BOLD if differs else color_for_age(age)
                try:
                    self.stdscr.addstr(py, px, CELL_CHAR, attr)
                except curses.error:
                    pass
            elif differs:
                # Dead in perturbed but alive in original — show dim marker
                try:
                    self.stdscr.addstr(py, px, ".", curses.color_pair(5) | curses.A_DIM)
                except curses.error:
                    pass

    # Panel labels
    label_y = max_y - 6
    if label_y > 0:
        l1 = f" ORIGINAL  Gen:{self.grid.generation}  Pop:{self.grid.population}"
        l2 = f" PERTURBED  Gen:{self.butterfly_grid.generation}  Pop:{self.butterfly_grid.population}"
        try:
            self.stdscr.addstr(label_y, 0, l1[:divider_x],
                               curses.color_pair(7) | curses.A_BOLD)
            self.stdscr.addstr(label_y, right_start, l2[:max_x - right_start - 1],
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

    # Dual sparklines
    spark_y = max_y - 5
    if spark_y > 0:
        spark_w = divider_x - 2
        if spark_w > 0 and len(self.pop_history) > 1:
            try:
                s1 = sparkline(self.pop_history, spark_w)
                self.stdscr.addstr(spark_y, 0, " " + s1, curses.color_pair(1))
            except curses.error:
                pass
        spark_w2 = max_x - right_start - 1
        if spark_w2 > 0 and len(self.butterfly_pop_history) > 1:
            try:
                s2 = sparkline(self.butterfly_pop_history, spark_w2)
                self.stdscr.addstr(spark_y, right_start, " " + s2, curses.color_pair(1))
            except curses.error:
                pass

    _butterfly_draw_status(self, max_y, max_x)


# ── Drawing: overlay view ──

def _butterfly_draw_overlay(self, max_y: int, max_x: int):
    """Draw blended overlay: green = only original, red = only perturbed, yellow = both."""
    self.stdscr.erase()

    vis_rows = max_y - 6
    vis_cols = (max_x - 1) // 2
    zoom = self.zoom_level

    grid_vis_rows = vis_rows * zoom
    grid_vis_cols = vis_cols * zoom

    view_r = self.cursor_r - grid_vis_rows // 2
    view_c = self.cursor_c - grid_vis_cols // 2

    for sy in range(min(vis_rows, max_y - 6)):
        for sx in range(min(vis_cols, (max_x - 1) // 2)):
            gr = (view_r + sy * zoom) % self.grid.rows
            gc = (view_c + sx * zoom) % self.grid.cols
            px = sx * 2
            py = sy
            if py >= max_y - 6 or px + 1 >= max_x:
                continue

            orig = self.grid.cells[gr][gc] > 0
            pert = self.butterfly_grid.cells[gr][gc] > 0

            if orig and pert:
                # Both alive — white/normal (agreement)
                try:
                    self.stdscr.addstr(py, px, CELL_CHAR, curses.color_pair(3))
                except curses.error:
                    pass
            elif orig and not pert:
                # Only original alive — green (perturbed killed it)
                try:
                    self.stdscr.addstr(py, px, CELL_CHAR, curses.color_pair(1))
                except curses.error:
                    pass
            elif not orig and pert:
                # Only perturbed alive — red (perturbation created it)
                try:
                    self.stdscr.addstr(py, px, CELL_CHAR, curses.color_pair(5) | curses.A_BOLD)
                except curses.error:
                    pass
            # Both dead — leave blank

    _butterfly_draw_status(self, max_y, max_x)


# ── Drawing: shared status bar ──

def _butterfly_draw_status(self, max_y: int, max_x: int):
    """Draw status, divergence bar, and hints at the bottom."""
    # Divergence bar
    div_y = max_y - 4
    if div_y > 0:
        pct = self.butterfly_divergence_pct
        bar_w = max(0, max_x - 40)
        if bar_w > 2:
            filled = max(0, min(bar_w, int(pct / max(0.1, 100.0) * bar_w)))
            bar = "█" * filled + "░" * (bar_w - filled)
            div_str = f" Divergence: {pct:5.1f}%  Peak: {self.butterfly_max_divergence:5.1f}%  {bar}"
        else:
            div_str = f" Divergence: {pct:5.1f}%  Peak: {self.butterfly_max_divergence:5.1f}%"
        try:
            # Color based on divergence level
            if pct < 5:
                pair = 1  # green — minimal
            elif pct < 20:
                pair = 3  # yellow — moderate
            elif pct < 50:
                pair = 4  # magenta — significant
            else:
                pair = 5  # red — massive
            self.stdscr.addstr(div_y, 0, div_str[:max_x - 1], curses.color_pair(pair))
        except curses.error:
            pass

    # Perturbation info
    info_y = max_y - 3
    if info_y > 0:
        action = "killed" if self.butterfly_perturb_was_alive else "spawned"
        info = (
            f" Perturbation: ({self.butterfly_perturb_r},{self.butterfly_perturb_c}) "
            f"{action}  |  +{self.butterfly_steps_since_fork} gens  |  "
            f"Pop delta: {self.butterfly_grid.population - self.grid.population:+d}  |  "
            f"View: {VIEW_NAMES[self.butterfly_view]}"
        )
        try:
            self.stdscr.addstr(info_y, 0, info[:max_x - 1],
                               curses.color_pair(6))
        except curses.error:
            pass

    # Status bar
    status_y = max_y - 2
    if status_y > 0:
        state = "▶ PLAY" if self.butterfly_running else "⏸ PAUSE"
        speed = SPEED_LABELS[self.speed_idx]
        hm = "cumulative" if self.butterfly_cumulative else "instantaneous"
        sc = "log" if self.butterfly_log_scale else "linear"
        status = f" BUTTERFLY EFFECT  |  {state}  |  Speed: {speed}  |  Heat: {hm}  |  Scale: {sc}"
        try:
            self.stdscr.addstr(status_y, 0, status[:max_x - 1],
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

    # Hints
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if hasattr(self, 'message') and self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [d]=view [h]=heat [c]=scale [r]=reset [Ctrl+B]=exit [q]=quit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ── Main draw dispatch ──

def _butterfly_draw(self, max_y: int, max_x: int):
    """Main draw entry point for butterfly mode."""
    if self.butterfly_picking:
        _butterfly_draw_pick(self, max_y, max_x)
        return

    if self.butterfly_view == VIEW_HEATMAP:
        _butterfly_draw_heatmap(self, max_y, max_x)
    elif self.butterfly_view == VIEW_SIDE_BY_SIDE:
        _butterfly_draw_split(self, max_y, max_x)
    elif self.butterfly_view == VIEW_OVERLAY:
        _butterfly_draw_overlay(self, max_y, max_x)


# ── Registration ──

def register(App):
    """Register butterfly-effect methods on the App class."""
    App._butterfly_init = _butterfly_init
    App._enter_butterfly_mode = _enter_butterfly_mode
    App._exit_butterfly_mode = _exit_butterfly_mode
    App._butterfly_apply_perturbation = _butterfly_apply_perturbation
    App._butterfly_handle_key = _butterfly_handle_key
    App._butterfly_handle_pick_key = _butterfly_handle_pick_key
    App._butterfly_handle_run_key = _butterfly_handle_run_key
    App._butterfly_step = _butterfly_step
    App._butterfly_draw = _butterfly_draw
