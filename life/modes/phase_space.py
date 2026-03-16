"""Mode: phase_space — Phase Space Navigator.

Maps the behavioral landscape of cellular automaton rule-space as an
interactive, real-time bifurcation explorer.  The user sweeps across two
rule parameters while the simulator runs hundreds of micro-simulations in
parallel behind the scenes, plotting a live 2D heatmap of where complexity,
chaos, oscillation, and death occur.

Click any point on the phase portrait to teleport into that simulation
running full-screen.  A "map of all possible universes."
"""
import curses
import math
import random
import time

from life.analytics import PeriodicityDetector, shannon_entropy, classify_stability
from life.grid import Grid
from life.rules import rule_string

# ── Constants ────────────────────────────────────────────────────────

_SPARKLINE = "▁▂▃▄▅▆▇█"

# Micro-simulation parameters
_SIM_ROWS = 16
_SIM_COLS = 16
_EVAL_STEPS = 80
_SIMS_PER_FRAME = 4       # how many sims to advance per step call
_INITIAL_DENSITY = 0.35

# Behavioral classification colors
# Each classification maps to (color_pair, char, extra_attr)
_CLASS_COLORS = {
    "dead":        (0, "  ", curses.A_DIM),
    "static":      (5, "░░", 0),           # cyan
    "oscillating": (7, "▒▒", 0),           # white/grey
    "complex":     (4, "▓▓", curses.A_BOLD),  # yellow — edge of chaos
    "chaotic":     (2, "██", 0),            # red
    "explosive":   (6, "██", curses.A_BOLD),  # magenta
    "growing":     (3, "▓▓", 0),           # green
    "dying":       (1, "░░", curses.A_DIM), # blue
    "starting":    (0, "··", curses.A_DIM),
    "pending":     (0, "··", curses.A_DIM),
}

# Axis sweep modes
_AXIS_MODES = [
    {
        "name": "Birth vs Survival",
        "x_label": "Birth neighbor count",
        "y_label": "Survival neighbor count",
        "x_range": (0, 8),
        "y_range": (0, 8),
        "desc": "Single birth/survival thresholds B{x}/S{y}",
    },
    {
        "name": "Birth Range vs Survival Range",
        "x_label": "Birth center",
        "y_label": "Survival center",
        "x_range": (0.0, 8.0),
        "y_range": (0.0, 8.0),
        "desc": "Birth/survival centered ranges with configurable width",
    },
    {
        "name": "Density vs Birth Threshold",
        "x_label": "Initial density",
        "y_label": "Birth threshold",
        "x_range": (0.02, 0.8),
        "y_range": (0, 8),
        "desc": "How initial density affects outcomes across birth rules",
    },
    {
        "name": "Lambda vs Mu",
        "x_label": "Lambda (birth fraction)",
        "y_label": "Mu (survival fraction)",
        "x_range": (0.0, 1.0),
        "y_range": (0.0, 1.0),
        "desc": "Langton's lambda-like parameters for birth/survival",
    },
]

# Complexity score: weighted combination for the heatmap intensity
_COMPLEXITY_WEIGHTS = {
    "dead": 0.0,
    "static": 0.1,
    "dying": 0.15,
    "oscillating": 0.5,
    "complex": 0.9,
    "growing": 0.6,
    "chaotic": 0.7,
    "explosive": 0.3,
    "starting": 0.0,
    "pending": 0.0,
}


# ── Helpers ──────────────────────────────────────────────────────────

def _make_rule_for_point(x_val, y_val, axis_mode, range_width=1.5):
    """Generate a B/S rule + density for a given (x, y) point and axis mode."""
    density = _INITIAL_DENSITY

    if axis_mode == 0:
        # Birth vs Survival: single thresholds
        b = int(round(x_val))
        s = int(round(y_val))
        birth = {b} if 0 <= b <= 8 else set()
        survival = {s} if 0 <= s <= 8 else set()
        if not birth:
            birth = {3}

    elif axis_mode == 1:
        # Birth/survival ranges centered at (x, y) with width
        birth = set()
        survival = set()
        hw = range_width / 2.0
        for n in range(9):
            if abs(n - x_val) <= hw:
                birth.add(n)
            if abs(n - y_val) <= hw:
                survival.add(n)
        if not birth:
            birth = {int(round(x_val))}

    elif axis_mode == 2:
        # Density vs birth threshold
        density = max(0.02, min(0.8, x_val))
        b = int(round(y_val))
        birth = {b} if 0 <= b <= 8 else {3}
        survival = {2, 3}  # fixed Conway survival

    elif axis_mode == 3:
        # Lambda (birth fraction) vs Mu (survival fraction)
        birth = set()
        survival = set()
        for n in range(9):
            if random.random() < x_val:
                birth.add(n)
            if random.random() < y_val:
                survival.add(n)
        if not birth:
            birth.add(random.randint(1, 5))

    else:
        birth = {3}
        survival = {2, 3}

    return birth, survival, density


def _seed_micro_grid(grid, density):
    """Seed a micro grid with random initial state."""
    rows, cols = grid.rows, grid.cols
    pop = 0
    for r in range(rows):
        for c in range(cols):
            if random.random() < density:
                grid.cells[r][c] = 1
                pop += 1
            else:
                grid.cells[r][c] = 0
    grid.population = pop


def _step_micro(grid):
    """Step a micro simulation (fast, no age tracking beyond alive/dead)."""
    rows, cols = grid.rows, grid.cols
    cells = grid.cells
    birth = grid.birth
    survival = grid.survival
    new = [[0] * cols for _ in range(rows)]
    pop = 0
    for r in range(rows):
        for c in range(cols):
            # Count Moore neighbors with wrapping
            n = 0
            for dr in (-1, 0, 1):
                rr = (r + dr) % rows
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    if cells[rr][(c + dc) % cols] > 0:
                        n += 1
            alive = cells[r][c] > 0
            if alive and n in survival:
                new[r][c] = min(cells[r][c] + 1, 200)
                pop += 1
            elif not alive and n in birth:
                new[r][c] = 1
                pop += 1
    grid.cells = new
    grid.generation += 1
    grid.population = pop


def _classify_micro(grid, pop_history):
    """Classify a micro-simulation's behavior."""
    if not pop_history or len(pop_history) < 5:
        return "starting"

    total = grid.rows * grid.cols
    final_pop = pop_history[-1]

    if final_pop == 0:
        return "dead"

    pop_frac = final_pop / total

    if pop_frac > 0.85:
        return "explosive"

    # Check for static
    recent = pop_history[-20:]
    if len(recent) >= 10:
        if max(recent) == min(recent):
            return "static"

    # Check variance
    if len(recent) >= 5:
        mean = sum(recent) / len(recent)
        if mean > 0:
            variance = sum((x - mean) ** 2 for x in recent) / len(recent)
            cv = math.sqrt(variance) / mean

            if cv < 0.01:
                return "static"
            elif cv < 0.05:
                return "oscillating"
            elif cv < 0.15:
                return "complex"
            elif cv < 0.3:
                return "chaotic"
            else:
                return "chaotic"

    # Check trend
    if len(recent) >= 10:
        first = sum(recent[:5]) / 5
        last = sum(recent[-5:]) / 5
        if first > 0:
            ratio = last / first
            if ratio > 1.3:
                return "growing"
            elif ratio < 0.7:
                return "dying"

    return "complex"


def _compute_complexity_score(grid, pop_history, classification):
    """Compute a 0-1 complexity score for heatmap intensity."""
    base = _COMPLEXITY_WEIGHTS.get(classification, 0.0)
    if not pop_history or len(pop_history) < 5:
        return base

    total = grid.rows * grid.cols
    if total == 0:
        return base

    # Entropy bonus
    ent = shannon_entropy(grid)
    ent_score = min(ent / 1.0, 1.0)

    # Population fraction bonus (not too sparse, not too dense)
    pop_frac = grid.population / total
    pop_score = 1.0 - abs(pop_frac - 0.3) * 2.0
    pop_score = max(0.0, min(1.0, pop_score))

    # Population variability
    recent = pop_history[-20:]
    mean = sum(recent) / len(recent) if recent else 1
    if mean > 0:
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)
        cv = math.sqrt(variance) / mean
        var_score = min(cv / 0.2, 1.0)
    else:
        var_score = 0.0

    score = base * 0.4 + ent_score * 0.25 + pop_score * 0.15 + var_score * 0.2
    return max(0.0, min(1.0, score))


def _sparkline(data, width):
    """Render a sparkline string."""
    if not data or width <= 0:
        return ""
    vals = list(data[-width:])
    lo, hi = min(vals), max(vals)
    span = hi - lo if hi != lo else 1
    out = []
    for v in vals:
        idx = int((v - lo) / span * (len(_SPARKLINE) - 1))
        idx = max(0, min(idx, len(_SPARKLINE) - 1))
        out.append(_SPARKLINE[idx])
    return "".join(out)


# ── Mode functions ───────────────────────────────────────────────────

def _phasespace_init(self):
    """Initialize state variables."""
    self.phasespace_mode = False
    self.phasespace_menu = False
    self.phasespace_menu_sel = 0
    self.phasespace_running = False
    # Grid of simulations
    self.phasespace_grid_w = 30       # heatmap width in cells
    self.phasespace_grid_h = 20       # heatmap height in cells
    self.phasespace_sims = {}         # {(gx, gy): Grid}
    self.phasespace_pop_hists = {}    # {(gx, gy): [int]}
    self.phasespace_classes = {}      # {(gx, gy): str}
    self.phasespace_scores = {}       # {(gx, gy): float}
    self.phasespace_completed = {}    # {(gx, gy): bool}
    # Sweep parameters
    self.phasespace_axis_mode = 0     # index into _AXIS_MODES
    self.phasespace_range_width = 1.5 # for range-based axes
    self.phasespace_eval_steps = _EVAL_STEPS
    self.phasespace_sim_size = _SIM_ROWS
    # Cursor
    self.phasespace_cx = 0
    self.phasespace_cy = 0
    # Display
    self.phasespace_view = 0          # 0=classification, 1=complexity, 2=entropy
    self.phasespace_show_labels = True
    # Stats
    self.phasespace_total_done = 0
    self.phasespace_total_cells = 0
    self.phasespace_scan_queue = []   # queue of (gx, gy) to simulate
    self.phasespace_scan_idx = 0
    # Teleport preview
    self.phasespace_preview_mode = False
    self.phasespace_preview_grid = None
    self.phasespace_preview_pop_hist = []
    self.phasespace_preview_running = False


def _enter_phasespace_mode(self):
    """Enter Phase Space Navigator — show settings menu."""
    _phasespace_init(self)
    self.phasespace_menu = True
    self.phasespace_menu_sel = 0
    self._flash("Phase Space Navigator — map of all possible universes")


def _exit_phasespace_mode(self):
    """Clean up and exit."""
    self.phasespace_mode = False
    self.phasespace_menu = False
    self.phasespace_running = False
    self.phasespace_preview_mode = False
    self.phasespace_sims = {}
    self.phasespace_pop_hists = {}
    self.phasespace_classes = {}
    self.phasespace_scores = {}
    self.phasespace_completed = {}
    self.phasespace_scan_queue = []
    self._flash("Phase Space Navigator OFF")


def _phasespace_start_scan(self):
    """Initialize the phase space scan with micro-simulations."""
    max_y, max_x = self.stdscr.getmaxyx()

    # Compute grid dimensions based on terminal size
    # Each heatmap cell is 2 chars wide, 1 char tall
    panel_w = 38
    usable_w = max_x - panel_w - 2
    usable_h = max_y - 5  # leave room for status

    self.phasespace_grid_w = max(8, min(60, usable_w // 2))
    self.phasespace_grid_h = max(6, min(40, usable_h - 2))

    # Clear previous state
    self.phasespace_sims = {}
    self.phasespace_pop_hists = {}
    self.phasespace_classes = {}
    self.phasespace_scores = {}
    self.phasespace_completed = {}
    self.phasespace_total_done = 0
    self.phasespace_total_cells = self.phasespace_grid_w * self.phasespace_grid_h

    # Create scan queue (spiral from center for visual effect)
    cx, cy = self.phasespace_grid_w // 2, self.phasespace_grid_h // 2
    queue = []
    for gx in range(self.phasespace_grid_w):
        for gy in range(self.phasespace_grid_h):
            dist = abs(gx - cx) + abs(gy - cy)
            queue.append((dist, gx, gy))
    queue.sort()
    self.phasespace_scan_queue = [(gx, gy) for _, gx, gy in queue]
    self.phasespace_scan_idx = 0

    # Create all micro-simulations
    axis = _AXIS_MODES[self.phasespace_axis_mode]
    x_lo, x_hi = axis["x_range"]
    y_lo, y_hi = axis["y_range"]

    for gx in range(self.phasespace_grid_w):
        for gy in range(self.phasespace_grid_h):
            x_val = x_lo + (x_hi - x_lo) * gx / max(1, self.phasespace_grid_w - 1)
            y_val = y_lo + (y_hi - y_lo) * gy / max(1, self.phasespace_grid_h - 1)

            birth, survival, density = _make_rule_for_point(
                x_val, y_val, self.phasespace_axis_mode,
                self.phasespace_range_width,
            )

            sz = self.phasespace_sim_size
            g = Grid(sz, sz)
            g.birth = birth
            g.survival = survival
            _seed_micro_grid(g, density)
            self.phasespace_sims[(gx, gy)] = g
            self.phasespace_pop_hists[(gx, gy)] = [g.population]
            self.phasespace_classes[(gx, gy)] = "pending"
            self.phasespace_scores[(gx, gy)] = 0.0
            self.phasespace_completed[(gx, gy)] = False

    self.phasespace_cx = cx
    self.phasespace_cy = cy
    self.phasespace_mode = True
    self.phasespace_menu = False
    self.phasespace_running = True
    self.phasespace_preview_mode = False


def _phasespace_step(self):
    """Advance micro-simulations. Process several per frame for speed."""
    if not self.phasespace_running:
        return
    if self.phasespace_preview_mode:
        _phasespace_preview_step(self)
        return

    processed = 0
    while processed < _SIMS_PER_FRAME and self.phasespace_scan_idx < len(self.phasespace_scan_queue):
        gx, gy = self.phasespace_scan_queue[self.phasespace_scan_idx]
        key = (gx, gy)

        if key not in self.phasespace_sims:
            self.phasespace_scan_idx += 1
            continue

        grid = self.phasespace_sims[key]

        if self.phasespace_completed.get(key, False):
            self.phasespace_scan_idx += 1
            continue

        # Run this sim for all eval steps at once
        for _ in range(self.phasespace_eval_steps - grid.generation):
            _step_micro(grid)
            self.phasespace_pop_hists[key].append(grid.population)

        # Classify
        classification = _classify_micro(grid, self.phasespace_pop_hists[key])
        self.phasespace_classes[key] = classification
        self.phasespace_scores[key] = _compute_complexity_score(
            grid, self.phasespace_pop_hists[key], classification,
        )
        self.phasespace_completed[key] = True
        self.phasespace_total_done += 1
        self.phasespace_scan_idx += 1
        processed += 1

    # Check if all done
    if self.phasespace_scan_idx >= len(self.phasespace_scan_queue):
        if self.phasespace_total_done >= self.phasespace_total_cells:
            self.phasespace_running = False


def _phasespace_preview_step(self):
    """Step the preview/teleport simulation."""
    if self.phasespace_preview_grid is None:
        return
    if not self.phasespace_preview_running:
        return
    self.phasespace_preview_grid.step()
    self.phasespace_preview_pop_hist.append(self.phasespace_preview_grid.population)
    if len(self.phasespace_preview_pop_hist) > 200:
        self.phasespace_preview_pop_hist = self.phasespace_preview_pop_hist[-200:]


def _phasespace_teleport(self):
    """Teleport into the simulation at the cursor position."""
    key = (self.phasespace_cx, self.phasespace_cy)
    if key not in self.phasespace_sims:
        return

    src = self.phasespace_sims[key]
    axis = _AXIS_MODES[self.phasespace_axis_mode]
    x_lo, x_hi = axis["x_range"]
    y_lo, y_hi = axis["y_range"]
    x_val = x_lo + (x_hi - x_lo) * self.phasespace_cx / max(1, self.phasespace_grid_w - 1)
    y_val = y_lo + (y_hi - y_lo) * self.phasespace_cy / max(1, self.phasespace_grid_h - 1)

    birth, survival, density = _make_rule_for_point(
        x_val, y_val, self.phasespace_axis_mode,
        self.phasespace_range_width,
    )

    # Create a larger simulation with the same rule
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max_y - 4
    cols = (max_x - 2) // 2
    g = Grid(rows, cols)
    g.birth = birth
    g.survival = survival
    _seed_micro_grid(g, density)

    self.phasespace_preview_mode = True
    self.phasespace_preview_grid = g
    self.phasespace_preview_pop_hist = [g.population]
    self.phasespace_preview_running = True
    self.phasespace_running = True

    rs = rule_string(birth, survival)
    self._flash(f"Teleported into {rs} — Space:pause  Backspace:return")


def _phasespace_adopt(self):
    """Adopt the current cursor's rule into the main simulation."""
    key = (self.phasespace_cx, self.phasespace_cy)
    if key not in self.phasespace_sims:
        return

    axis = _AXIS_MODES[self.phasespace_axis_mode]
    x_lo, x_hi = axis["x_range"]
    y_lo, y_hi = axis["y_range"]
    x_val = x_lo + (x_hi - x_lo) * self.phasespace_cx / max(1, self.phasespace_grid_w - 1)
    y_val = y_lo + (y_hi - y_lo) * self.phasespace_cy / max(1, self.phasespace_grid_h - 1)

    birth, survival, density = _make_rule_for_point(
        x_val, y_val, self.phasespace_axis_mode,
        self.phasespace_range_width,
    )

    self.grid.birth = set(birth)
    self.grid.survival = set(survival)
    rs = rule_string(birth, survival)
    _exit_phasespace_mode(self)
    self._flash(f"Adopted rule: {rs}")


def _phasespace_rescan(self):
    """Rescan with new random seeds (same rules, new initial conditions)."""
    self.phasespace_total_done = 0
    self.phasespace_scan_idx = 0

    axis = _AXIS_MODES[self.phasespace_axis_mode]
    x_lo, x_hi = axis["x_range"]
    y_lo, y_hi = axis["y_range"]

    for gx in range(self.phasespace_grid_w):
        for gy in range(self.phasespace_grid_h):
            key = (gx, gy)
            x_val = x_lo + (x_hi - x_lo) * gx / max(1, self.phasespace_grid_w - 1)
            y_val = y_lo + (y_hi - y_lo) * gy / max(1, self.phasespace_grid_h - 1)

            birth, survival, density = _make_rule_for_point(
                x_val, y_val, self.phasespace_axis_mode,
                self.phasespace_range_width,
            )

            sz = self.phasespace_sim_size
            g = Grid(sz, sz)
            g.birth = birth
            g.survival = survival
            _seed_micro_grid(g, density)
            self.phasespace_sims[key] = g
            self.phasespace_pop_hists[key] = [g.population]
            self.phasespace_classes[key] = "pending"
            self.phasespace_scores[key] = 0.0
            self.phasespace_completed[key] = False

    self.phasespace_running = True
    self._flash("Rescanning phase space with new seeds...")


# ── Key handlers ─────────────────────────────────────────────────────

def _handle_phasespace_menu_key(self, key):
    """Handle keys in the Phase Space Navigator settings menu."""
    if key == -1:
        return True

    menu_items = [
        "axis_mode", "range_width", "eval_steps", "sim_size",
        "start",
    ]
    n = len(menu_items)

    if key in (curses.KEY_UP, ord("k")):
        self.phasespace_menu_sel = (self.phasespace_menu_sel - 1) % n
        return True
    if key in (curses.KEY_DOWN, ord("j")):
        self.phasespace_menu_sel = (self.phasespace_menu_sel + 1) % n
        return True
    if key == 27 or key == ord("q"):
        self.phasespace_menu = False
        self._flash("Phase Space Navigator cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER, ord(" ")):
        item = menu_items[self.phasespace_menu_sel]
        if item == "axis_mode":
            self.phasespace_axis_mode = (self.phasespace_axis_mode + 1) % len(_AXIS_MODES)
            self._flash(f"Axis: {_AXIS_MODES[self.phasespace_axis_mode]['name']}")
        elif item == "range_width":
            val = self._prompt_text(f"Range width 0.5-4.0 (current: {self.phasespace_range_width:.1f})")
            if val:
                try:
                    v = float(val)
                    if 0.5 <= v <= 4.0:
                        self.phasespace_range_width = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "eval_steps":
            val = self._prompt_text(f"Eval steps 20-300 (current: {self.phasespace_eval_steps})")
            if val:
                try:
                    v = int(val)
                    if 20 <= v <= 300:
                        self.phasespace_eval_steps = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "sim_size":
            val = self._prompt_text(f"Sim grid size 8-32 (current: {self.phasespace_sim_size})")
            if val:
                try:
                    v = int(val)
                    if 8 <= v <= 32:
                        self.phasespace_sim_size = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "start":
            _phasespace_start_scan(self)
        return True

    # Left/Right to cycle axis mode on that item
    if key in (curses.KEY_LEFT, curses.KEY_RIGHT):
        item = menu_items[self.phasespace_menu_sel]
        if item == "axis_mode":
            delta = 1 if key == curses.KEY_RIGHT else -1
            self.phasespace_axis_mode = (self.phasespace_axis_mode + delta) % len(_AXIS_MODES)
        return True

    return True


def _handle_phasespace_key(self, key):
    """Handle keys during active Phase Space exploration."""
    if key == -1:
        return True

    # Preview mode keys
    if self.phasespace_preview_mode:
        return _handle_phasespace_preview_key(self, key)

    if key == 27 or key == ord("q"):
        _exit_phasespace_mode(self)
        return True

    gw = self.phasespace_grid_w
    gh = self.phasespace_grid_h

    # Cursor navigation
    if key == curses.KEY_UP or key == ord("k"):
        self.phasespace_cy = max(0, self.phasespace_cy - 1)
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.phasespace_cy = min(gh - 1, self.phasespace_cy + 1)
        return True
    if key == curses.KEY_LEFT or key == ord("h"):
        self.phasespace_cx = max(0, self.phasespace_cx - 1)
        return True
    if key == curses.KEY_RIGHT or key == ord("l"):
        self.phasespace_cx = min(gw - 1, self.phasespace_cx + 1)
        return True

    # Fast cursor movement
    if key == ord("H"):
        self.phasespace_cx = max(0, self.phasespace_cx - 5)
        return True
    if key == ord("L"):
        self.phasespace_cx = min(gw - 1, self.phasespace_cx + 5)
        return True
    if key == ord("K"):
        self.phasespace_cy = max(0, self.phasespace_cy - 5)
        return True
    if key == ord("J"):
        self.phasespace_cy = min(gh - 1, self.phasespace_cy + 5)
        return True

    # Teleport into simulation
    if key in (10, 13, curses.KEY_ENTER):
        _phasespace_teleport(self)
        return True

    # Adopt rule
    if key == ord("a"):
        _phasespace_adopt(self)
        return True

    # Cycle view mode
    if key == ord("v"):
        self.phasespace_view = (self.phasespace_view + 1) % 3
        labels = ["Classification", "Complexity", "Entropy"]
        self._flash(f"View: {labels[self.phasespace_view]}")
        return True

    # Toggle labels
    if key == ord("t"):
        self.phasespace_show_labels = not self.phasespace_show_labels
        return True

    # Rescan with new random seeds
    if key == ord("r"):
        _phasespace_rescan(self)
        return True

    # Cycle axis mode (requires rescan)
    if key == ord("m"):
        self.phasespace_axis_mode = (self.phasespace_axis_mode + 1) % len(_AXIS_MODES)
        self._flash(f"Axis: {_AXIS_MODES[self.phasespace_axis_mode]['name']} — press r to rescan")
        return True

    # Return to menu
    if key == ord("R"):
        self.phasespace_mode = False
        self.phasespace_running = False
        self.phasespace_menu = True
        self.phasespace_menu_sel = 0
        return True

    # Play/pause
    if key == ord(" "):
        self.phasespace_running = not self.phasespace_running
        self._flash("Running" if self.phasespace_running else "Paused")
        return True

    return True


def _handle_phasespace_preview_key(self, key):
    """Handle keys in the teleport preview."""
    if key == 127 or key == curses.KEY_BACKSPACE or key == ord("b"):
        # Return to heatmap
        self.phasespace_preview_mode = False
        self.phasespace_preview_grid = None
        self.phasespace_preview_pop_hist = []
        self.phasespace_preview_running = False
        # Resume scan if not done
        if self.phasespace_total_done < self.phasespace_total_cells:
            self.phasespace_running = True
        else:
            self.phasespace_running = False
        self._flash("Returned to phase space map")
        return True

    if key == ord(" "):
        self.phasespace_preview_running = not self.phasespace_preview_running
        self.phasespace_running = self.phasespace_preview_running
        return True

    if key == ord("a"):
        _phasespace_adopt(self)
        return True

    if key == 27 or key == ord("q"):
        _exit_phasespace_mode(self)
        return True

    return True


# ── Auto-stepping ────────────────────────────────────────────────────

def _is_phasespace_auto_stepping(self):
    """Check if Phase Space Navigator should auto-step."""
    return self.phasespace_running


# ── Drawing ──────────────────────────────────────────────────────────

def _draw_phasespace_menu(self, max_y, max_x):
    """Draw the Phase Space Navigator settings menu."""
    self.stdscr.erase()

    title = "═══ Phase Space Navigator ═══"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Map the behavioral landscape of all possible CA universes"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2),
                           subtitle[:max_x - 2], curses.A_DIM)
    except curses.error:
        pass

    axis = _AXIS_MODES[self.phasespace_axis_mode]

    items = [
        ("Sweep Axes", axis["name"], axis["desc"]),
        ("Range Width", f"{self.phasespace_range_width:.1f}",
         "Width of birth/survival range (for range-based axes)"),
        ("Eval Steps", str(self.phasespace_eval_steps),
         "Generations per micro-simulation (20-300)"),
        ("Sim Grid Size", str(self.phasespace_sim_size),
         "NxN grid size for micro-simulations (8-32)"),
        (">>> START SCAN <<<", "", "Begin mapping phase space"),
    ]

    y = 6
    for i, (label, value, hint) in enumerate(items):
        if y >= max_y - 4:
            break
        prefix = "▸ " if i == self.phasespace_menu_sel else "  "
        if i == 4:  # action item
            attr = curses.A_BOLD | curses.A_REVERSE if i == self.phasespace_menu_sel else curses.A_BOLD
            line = f"{prefix}{label}"
            try:
                self.stdscr.addstr(y, 4, line[:max_x - 8], attr)
            except curses.error:
                pass
        else:
            attr = curses.A_BOLD | curses.A_REVERSE if i == self.phasespace_menu_sel else 0
            line = f"{prefix}{label}: {value}"
            try:
                self.stdscr.addstr(y, 4, line[:max_x - 8], attr)
            except curses.error:
                pass
            if i == self.phasespace_menu_sel:
                y += 1
                try:
                    self.stdscr.addstr(y, 8, hint[:max_x - 12], curses.A_DIM)
                except curses.error:
                    pass
        y += 2

    # Axis preview
    y += 1
    if y < max_y - 6:
        try:
            self.stdscr.addstr(y, 4, "Axis Preview:", curses.A_BOLD)
            y += 1
            self.stdscr.addstr(y, 6, f"X: {axis['x_label']} ({axis['x_range'][0]}-{axis['x_range'][1]})")
            y += 1
            self.stdscr.addstr(y, 6, f"Y: {axis['y_label']} ({axis['y_range'][0]}-{axis['y_range'][1]})")
        except curses.error:
            pass

    # Help
    try:
        help_text = "Up/Down:navigate  Enter/Space:select  Left/Right:cycle  q:cancel"
        self.stdscr.addstr(max_y - 2, 4, help_text[:max_x - 8], curses.A_DIM)
    except curses.error:
        pass


def _draw_phasespace(self, max_y, max_x):
    """Render the Phase Space Navigator heatmap or preview."""
    if self.phasespace_preview_mode:
        _draw_phasespace_preview(self, max_y, max_x)
        return

    self.stdscr.erase()

    gw = self.phasespace_grid_w
    gh = self.phasespace_grid_h
    axis = _AXIS_MODES[self.phasespace_axis_mode]

    # ── Draw heatmap ──
    heatmap_x_offset = 5  # space for Y-axis labels
    heatmap_y_offset = 2  # space for title

    view_labels = ["Classification", "Complexity Heatmap", "Entropy Heatmap"]

    # Title
    pct = self.phasespace_total_done / max(1, self.phasespace_total_cells) * 100
    title = f"Phase Space: {axis['name']} — {view_labels[self.phasespace_view]} [{pct:.0f}%]"
    try:
        self.stdscr.addstr(0, max(0, (heatmap_x_offset + gw) // 2 - len(title) // 2),
                           title[:max_x - 2], curses.A_BOLD)
    except curses.error:
        pass

    # Draw Y-axis labels
    y_lo, y_hi = axis["y_range"]
    if self.phasespace_show_labels:
        for gy in range(gh):
            py = heatmap_y_offset + gy
            if py >= max_y - 3:
                break
            y_val = y_lo + (y_hi - y_lo) * gy / max(1, gh - 1)
            if gy % max(1, gh // 6) == 0 or gy == gh - 1:
                label = f"{y_val:4.1f}"
                try:
                    self.stdscr.addstr(py, 0, label[:4], curses.A_DIM)
                except curses.error:
                    pass

    # Draw X-axis labels
    x_lo, x_hi = axis["x_range"]
    if self.phasespace_show_labels:
        label_y = heatmap_y_offset + min(gh, max_y - heatmap_y_offset - 3)
        for gx in range(gw):
            px = heatmap_x_offset + gx * 2
            if px + 1 >= max_x - 40:
                break
            if gx % max(1, gw // 8) == 0 or gx == gw - 1:
                x_val = x_lo + (x_hi - x_lo) * gx / max(1, gw - 1)
                label = f"{x_val:.1f}"
                try:
                    self.stdscr.addstr(label_y, px, label[:4], curses.A_DIM)
                except curses.error:
                    pass

    # Draw heatmap cells
    for gy in range(gh):
        py = heatmap_y_offset + gy
        if py >= max_y - 3:
            break
        for gx in range(gw):
            px = heatmap_x_offset + gx * 2
            if px + 1 >= max_x - 40:
                break

            key = (gx, gy)
            is_cursor = (gx == self.phasespace_cx and gy == self.phasespace_cy)

            if self.phasespace_view == 0:
                # Classification view
                classification = self.phasespace_classes.get(key, "pending")
                pair, char, extra = _CLASS_COLORS.get(
                    classification, (0, "··", curses.A_DIM)
                )
                attr = 0
                if curses.has_colors() and pair > 0:
                    attr = curses.color_pair(pair) | extra
                else:
                    attr = extra
            elif self.phasespace_view == 1:
                # Complexity heatmap
                score = self.phasespace_scores.get(key, 0.0)
                char, attr = _complexity_to_char(score)
            else:
                # Entropy heatmap (compute from final state)
                score = self.phasespace_scores.get(key, 0.0)
                char, attr = _complexity_to_char(score)

            if is_cursor:
                attr = curses.A_REVERSE | curses.A_BOLD
                char = "▐▌"

            try:
                self.stdscr.addstr(py, px, char, attr)
            except curses.error:
                pass

    # ── Draw info panel ──
    panel_x = heatmap_x_offset + gw * 2 + 2
    if panel_x < max_x - 10:
        panel_w = max_x - panel_x - 1
        _draw_phasespace_panel(self, max_y, max_x, panel_x, panel_w)

    # ── Status bar ──
    _draw_phasespace_status(self, max_y, max_x)


def _complexity_to_char(score):
    """Convert a 0-1 complexity score to a colored block character."""
    if score < 0.05:
        return "  ", curses.A_DIM
    elif score < 0.15:
        pair = 5  # cyan
        char = "░░"
    elif score < 0.3:
        pair = 7  # white
        char = "░░"
    elif score < 0.45:
        pair = 3  # green
        char = "▒▒"
    elif score < 0.6:
        pair = 4  # yellow
        char = "▒▒"
    elif score < 0.75:
        pair = 4  # yellow
        char = "▓▓"
    elif score < 0.85:
        pair = 2  # red
        char = "▓▓"
    else:
        pair = 2  # red
        char = "██"

    attr = curses.color_pair(pair) if curses.has_colors() else 0
    return char, attr


def _draw_phasespace_panel(self, max_y, max_x, px, panel_w):
    """Draw the info panel on the right side of the heatmap."""
    py = 0
    axis = _AXIS_MODES[self.phasespace_axis_mode]

    try:
        self.stdscr.addstr(py, px, "Phase Space Navigator", curses.A_BOLD)
        py += 1

        # Progress
        pct = self.phasespace_total_done / max(1, self.phasespace_total_cells) * 100
        if pct < 100:
            bar_w = min(panel_w - 8, 20)
            filled = int(pct / 100 * bar_w)
            bar = "█" * filled + "░" * (bar_w - filled)
            self.stdscr.addstr(py, px, f"Scan [{bar}] {pct:.0f}%"[:panel_w - 1])
        else:
            self.stdscr.addstr(py, px, "Scan complete", curses.color_pair(3) if curses.has_colors() else 0)
        py += 1

        self.stdscr.addstr(py, px, f"Grid: {self.phasespace_grid_w}x{self.phasespace_grid_h} = {self.phasespace_total_cells} sims")
        py += 2

        # Axes info
        self.stdscr.addstr(py, px, f"X: {axis['x_label']}", curses.A_DIM)
        py += 1
        self.stdscr.addstr(py, px, f"Y: {axis['y_label']}", curses.A_DIM)
        py += 2

        # Cursor info
        gx, gy = self.phasespace_cx, self.phasespace_cy
        x_lo, x_hi = axis["x_range"]
        y_lo, y_hi = axis["y_range"]
        x_val = x_lo + (x_hi - x_lo) * gx / max(1, self.phasespace_grid_w - 1)
        y_val = y_lo + (y_hi - y_lo) * gy / max(1, self.phasespace_grid_h - 1)

        self.stdscr.addstr(py, px, "── Cursor ──", curses.A_BOLD)
        py += 1
        self.stdscr.addstr(py, px, f"Position: ({gx}, {gy})")
        py += 1
        self.stdscr.addstr(py, px, f"X={x_val:.2f}  Y={y_val:.2f}")
        py += 1

        key = (gx, gy)
        if key in self.phasespace_sims:
            grid = self.phasespace_sims[key]
            classification = self.phasespace_classes.get(key, "pending")
            score = self.phasespace_scores.get(key, 0.0)

            rs = rule_string(grid.birth, grid.survival)
            self.stdscr.addstr(py, px, f"Rule: {rs}"[:panel_w - 1])
            py += 1
            self.stdscr.addstr(py, px, f"Class: {classification}")
            py += 1
            self.stdscr.addstr(py, px, f"Complexity: {score:.3f}")
            py += 1

            total = grid.rows * grid.cols
            pop_pct = grid.population / total * 100 if total > 0 else 0
            self.stdscr.addstr(py, px, f"Pop: {grid.population} ({pop_pct:.0f}%)")
            py += 1

            # Population sparkline
            pop_hist = self.phasespace_pop_hists.get(key, [])
            if pop_hist and len(pop_hist) > 2:
                py += 1
                self.stdscr.addstr(py, px, "── Population ──", curses.A_BOLD)
                py += 1
                spark = _sparkline(pop_hist, min(panel_w - 2, 30))
                self.stdscr.addstr(py, px, spark, curses.A_DIM)
                py += 1

            # Mini preview of micro-sim
            py += 1
            if py < max_y - 8:
                self.stdscr.addstr(py, px, "── Micro Preview ──", curses.A_BOLD)
                py += 1
                preview_h = min(grid.rows, max_y - py - 4, 12)
                preview_w = min(grid.cols, (panel_w - 1) // 2, 16)
                for r in range(preview_h):
                    for c in range(preview_w):
                        ppx = px + c * 2
                        ppy = py + r
                        if ppy >= max_y - 2 or ppx + 1 >= max_x:
                            continue
                        if grid.cells[r][c] > 0:
                            v = grid.cells[r][c]
                            if v <= 2:
                                pair = 1
                            elif v <= 5:
                                pair = 4
                            elif v <= 15:
                                pair = 6
                            else:
                                pair = 3
                            cattr = curses.color_pair(pair) if curses.has_colors() else 0
                            self.stdscr.addstr(ppy, ppx, "██", cattr)
                py += preview_h

        # Classification legend
        py += 1
        if py < max_y - 8:
            self.stdscr.addstr(py, px, "── Legend ──", curses.A_BOLD)
            py += 1
            legend = [
                ("dead", "Extinction"),
                ("static", "Still life"),
                ("oscillating", "Oscillation"),
                ("complex", "Edge of chaos"),
                ("chaotic", "Chaos"),
                ("explosive", "Explosion"),
            ]
            for cls, desc in legend:
                if py >= max_y - 3:
                    break
                pair, char, extra = _CLASS_COLORS.get(cls, (0, "··", 0))
                attr = 0
                if curses.has_colors() and pair > 0:
                    attr = curses.color_pair(pair) | extra
                else:
                    attr = extra
                try:
                    self.stdscr.addstr(py, px, char, attr)
                    self.stdscr.addstr(py, px + 3, desc[:panel_w - 5], curses.A_DIM)
                except curses.error:
                    pass
                py += 1

    except curses.error:
        pass


def _draw_phasespace_status(self, max_y, max_x):
    """Draw status bar at bottom."""
    try:
        state = "▶ SCAN" if self.phasespace_running else "⏸ DONE" if self.phasespace_total_done >= self.phasespace_total_cells else "⏸ STOP"
        bar = (f" {state} │ Arrows:move  Enter:teleport  a:adopt  "
               f"v:view  r:rescan  m:axes  R:menu  q:quit ")
        self.stdscr.addstr(max_y - 1, 0, bar[:max_x - 1], curses.A_REVERSE)
    except curses.error:
        pass


def _draw_phasespace_preview(self, max_y, max_x):
    """Draw the teleported full-screen simulation preview."""
    self.stdscr.erase()

    grid = self.phasespace_preview_grid
    if grid is None:
        return

    rs = rule_string(grid.birth, grid.survival)

    # Draw grid cells
    display_rows = min(grid.rows, max_y - 3)
    display_cols = min(grid.cols, (max_x - 1) // 2)
    for r in range(display_rows):
        for c in range(display_cols):
            v = grid.cells[r][c]
            if v > 0:
                px = c * 2
                py = r
                if py >= max_y - 3 or px + 1 >= max_x:
                    continue
                if v <= 2:
                    pair = 1
                elif v <= 5:
                    pair = 4
                elif v <= 15:
                    pair = 6
                elif v <= 30:
                    pair = 7
                else:
                    pair = 3
                cattr = curses.color_pair(pair) if curses.has_colors() else 0
                try:
                    self.stdscr.addstr(py, px, "██", cattr)
                except curses.error:
                    pass

    # Population sparkline
    if self.phasespace_preview_pop_hist:
        spark_w = min(max_x - 2, 40)
        spark = _sparkline(self.phasespace_preview_pop_hist, spark_w)
        try:
            self.stdscr.addstr(max_y - 3, 0, spark, curses.A_DIM)
        except curses.error:
            pass

    # Info bar
    pop = grid.population
    gen = grid.generation
    total = grid.rows * grid.cols
    pct = pop / total * 100 if total > 0 else 0
    state = "▶" if self.phasespace_preview_running else "⏸"
    info = f" {state} {rs}  Gen:{gen}  Pop:{pop} ({pct:.0f}%) "
    try:
        self.stdscr.addstr(max_y - 2, 0, info[:max_x - 1],
                           curses.color_pair(6) if curses.has_colors() else 0)
    except curses.error:
        pass

    # Status bar
    try:
        bar = " Space:play/pause  Backspace/b:return  a:adopt  q:quit "
        self.stdscr.addstr(max_y - 1, 0, bar[:max_x - 1], curses.A_REVERSE)
    except curses.error:
        pass


# ── Registration ─────────────────────────────────────────────────────

def register(App):
    """Register Phase Space Navigator mode methods on the App class."""
    App._phasespace_init = _phasespace_init
    App._enter_phasespace_mode = _enter_phasespace_mode
    App._exit_phasespace_mode = _exit_phasespace_mode
    App._phasespace_step = _phasespace_step
    App._handle_phasespace_menu_key = _handle_phasespace_menu_key
    App._handle_phasespace_key = _handle_phasespace_key
    App._draw_phasespace_menu = _draw_phasespace_menu
    App._draw_phasespace = _draw_phasespace
    App._is_phasespace_auto_stepping = _is_phasespace_auto_stepping
