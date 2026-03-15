"""Mode: param_explorer — Parameter Space Explorer.

Displays a grid of live simulation thumbnails, each running the same mode
but with slightly varied parameters.  Click on the most interesting tile
to re-center the grid around its parameters and explore the neighborhood.

Currently supports exploring parameter spaces for:
  - Reaction-Diffusion (Gray-Scott): feed rate vs kill rate
  - Lenia: mu vs sigma
  - Boids: separation vs cohesion
  - Physarum: sensor angle vs sensor distance
  - Ising Model: temperature vs external field
  - And any other mode with 2 tunable numeric parameters
"""
import curses
import math
import random
import time

from life.constants import SPEEDS, SPEED_LABELS

# ── Explorable mode definitions ────────────────────────────────────────
# Each entry defines how to create and step a mini-simulation for a mode.
# Fields:
#   name        — display name
#   param_x     — (label, default_min, default_max) for horizontal axis
#   param_y     — (label, default_min, default_max) for vertical axis
#   init        — callable(rows, cols, px, py) -> state dict
#   step        — callable(state, n_steps) -> None  (mutates state in place)
#   sample      — callable(state, r, c) -> float 0..1  (for rendering)
#   presets     — list of (name, px, py) interesting starting points

def _rd_mini_init(rows, cols, feed, kill):
    """Create a mini Reaction-Diffusion simulation state."""
    U = [[1.0] * cols for _ in range(rows)]
    V = [[0.0] * cols for _ in range(rows)]
    # Seed V with a few circular patches
    num_seeds = max(1, (rows * cols) // 150)
    for _ in range(num_seeds):
        sr = random.randint(1, rows - 2)
        sc = random.randint(1, cols - 2)
        radius = max(1, min(rows, cols) // 5)
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                dist = math.sqrt(dr * dr + dc * dc)
                if dist <= radius:
                    r2 = (sr + dr) % rows
                    c2 = (sc + dc) % cols
                    falloff = max(0.0, 1.0 - dist / radius)
                    U[r2][c2] = 0.5 + random.random() * 0.02
                    V[r2][c2] = 0.25 * falloff + random.random() * 0.02
    return {"U": U, "V": V, "rows": rows, "cols": cols,
            "feed": feed, "kill": kill, "Du": 0.16, "Dv": 0.08, "dt": 1.0,
            "gen": 0}


def _rd_mini_step(state, n_steps=1):
    """Advance a mini RD simulation by n_steps."""
    rows, cols = state["rows"], state["cols"]
    U, V = state["U"], state["V"]
    Du, Dv = state["Du"], state["Dv"]
    f, k = state["feed"], state["kill"]
    dt = state["dt"]

    for _ in range(n_steps):
        newU = [[0.0] * cols for _ in range(rows)]
        newV = [[0.0] * cols for _ in range(rows)]
        for r in range(rows):
            rp = (r + 1) % rows
            rm = r - 1  # Python negative indexing wraps
            Ur = U[r]; Vr = V[r]
            Uu = U[rm]; Ud = U[rp]
            Vu = V[rm]; Vd = V[rp]
            for c in range(cols):
                cp = (c + 1) % cols
                cm = c - 1
                u = Ur[c]; v = Vr[c]
                lap_u = Uu[c] + Ud[c] + Ur[cm] + Ur[cp] - 4.0 * u
                lap_v = Vu[c] + Vd[c] + Vr[cm] + Vr[cp] - 4.0 * v
                uvv = u * v * v
                nu = u + dt * (Du * lap_u - uvv + f * (1.0 - u))
                nv = v + dt * (Dv * lap_v + uvv - (f + k) * v)
                if nu < 0.0: nu = 0.0
                elif nu > 1.0: nu = 1.0
                if nv < 0.0: nv = 0.0
                elif nv > 1.0: nv = 1.0
                newU[r][c] = nu
                newV[r][c] = nv
        U = newU; V = newV
    state["U"] = U; state["V"] = V
    state["gen"] += n_steps


def _rd_mini_sample(state, r, c):
    return min(1.0, state["V"][r][c])


def _smooth_ca_init(rows, cols, mu, sigma):
    """Continuous-valued CA with Gaussian growth function."""
    grid = [[0.0] * cols for _ in range(rows)]
    # Seed with random blobs
    num_seeds = max(2, (rows * cols) // 80)
    for _ in range(num_seeds):
        sr = random.randint(0, rows - 1)
        sc = random.randint(0, cols - 1)
        radius = max(1, min(rows, cols) // 6)
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                dist = math.sqrt(dr * dr + dc * dc)
                if dist <= radius:
                    r2 = (sr + dr) % rows
                    c2 = (sc + dc) % cols
                    grid[r2][c2] = max(grid[r2][c2], random.random() * (1.0 - dist / radius))
    return {"grid": grid, "rows": rows, "cols": cols,
            "mu": mu, "sigma": sigma, "dt": 0.1, "gen": 0}


def _smooth_ca_step(state, n_steps=1):
    """Step a smooth (continuous) CA — simplified Lenia-like dynamics."""
    rows, cols = state["rows"], state["cols"]
    grid = state["grid"]
    mu = state["mu"]
    sigma = max(0.001, state["sigma"])
    dt = state["dt"]
    for _ in range(n_steps):
        new = [[0.0] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                # Simple 8-neighbor average
                total = 0.0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        total += grid[(r + dr) % rows][(c + dc) % cols]
                avg = total / 8.0
                # Gaussian growth function
                growth = math.exp(-((avg - mu) ** 2) / (2.0 * sigma * sigma)) * 2.0 - 1.0
                val = grid[r][c] + dt * growth
                if val < 0.0:
                    val = 0.0
                elif val > 1.0:
                    val = 1.0
                new[r][c] = val
        grid = new
    state["grid"] = grid
    state["gen"] += n_steps


def _smooth_ca_sample(state, r, c):
    return min(1.0, state["grid"][r][c])


# ── Explorable modes catalog ──────────────────────────────────────────

EXPLORABLE_MODES = [
    {
        "name": "Reaction-Diffusion (Gray-Scott)",
        "param_x": ("feed", 0.01, 0.08),
        "param_y": ("kill", 0.04, 0.07),
        "init": _rd_mini_init,
        "step": _rd_mini_step,
        "sample": _rd_mini_sample,
        "presets": [
            ("Coral Growth", 0.0545, 0.062),
            ("Mitosis", 0.0367, 0.0649),
            ("Fingerprints", 0.025, 0.060),
            ("Spots", 0.035, 0.065),
            ("Worms", 0.078, 0.061),
            ("Spirals", 0.014, 0.054),
            ("Maze", 0.029, 0.057),
            ("Chaos", 0.026, 0.051),
        ],
    },
    {
        "name": "Smooth Life (continuous CA)",
        "param_x": ("mu", 0.05, 0.45),
        "param_y": ("sigma", 0.01, 0.15),
        "init": _smooth_ca_init,
        "step": _smooth_ca_step,
        "sample": _smooth_ca_sample,
        "presets": [
            ("Orbium", 0.15, 0.015),
            ("Geminium", 0.12, 0.020),
            ("Stable Blobs", 0.25, 0.050),
            ("Oscillators", 0.18, 0.035),
            ("Chaos", 0.30, 0.080),
        ],
    },
]

# ── Density glyphs and color helpers ──────────────────────────────────

_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]

_TILE_BORDER_H = "─"
_TILE_BORDER_V = "│"
_TILE_CORNER_TL = "┌"
_TILE_CORNER_TR = "┐"
_TILE_CORNER_BL = "└"
_TILE_CORNER_BR = "┘"
_TILE_CROSS = "┼"
_TILE_T_DOWN = "┬"
_TILE_T_UP = "┴"
_TILE_T_RIGHT = "├"
_TILE_T_LEFT = "┤"

# Color tiers for mini-sim rendering (8 levels)
_COLOR_TIERS = [
    (1, curses.A_DIM), (1, 0), (4, curses.A_DIM), (4, 0),
    (6, curses.A_DIM), (6, 0), (7, 0), (7, curses.A_BOLD),
]


# ── Mode functions ────────────────────────────────────────────────────

def _enter_param_explorer_mode(self):
    """Enter parameter space explorer — show mode selection menu."""
    self.pexplorer_menu = True
    self.pexplorer_menu_sel = 0
    self._flash("Parameter Space Explorer — select a mode to explore")


def _exit_param_explorer_mode(self):
    """Exit parameter space explorer."""
    self.pexplorer_mode = False
    self.pexplorer_menu = False
    self.pexplorer_running = False
    self.pexplorer_sims = []
    self._flash("Parameter Space Explorer OFF")


def _pexplorer_init(self, mode_idx=0, center_x=None, center_y=None):
    """Initialize the parameter explorer grid.

    Creates a grid_rows x grid_cols array of mini-simulations, each with
    parameters linearly interpolated across the grid.
    """
    max_y, max_x = self.stdscr.getmaxyx()

    mode_def = EXPLORABLE_MODES[mode_idx]
    self.pexplorer_mode_idx = mode_idx
    self.pexplorer_mode_name = mode_def["name"]

    # Determine grid dimensions based on terminal size
    # Each tile needs at least 6 rows and 10 cols (5 char-cells = 10 screen cols)
    # Reserve: 2 rows title, 2 rows status/hint, and border chars
    usable_h = max_y - 4
    usable_w = max_x - 1

    # Tile inner dimensions (characters)
    tile_inner_h = max(3, min(8, (usable_h - 2) // 4 - 1))
    tile_inner_w = max(4, min(12, (usable_w - 2) // 4 - 1))

    # Grid dimensions (how many tiles fit)
    self.pexplorer_grid_rows = max(2, min(5, (usable_h - 1) // (tile_inner_h + 1)))
    self.pexplorer_grid_cols = max(2, min(6, (usable_w - 1) // (tile_inner_w * 2 + 1)))

    # Recalculate tile size to fill available space
    self.pexplorer_tile_h = max(3, (usable_h - 1) // self.pexplorer_grid_rows - 1)
    self.pexplorer_tile_w = max(3, (usable_w - 1) // (self.pexplorer_grid_cols * 2) - 1)

    # Sim dimensions = tile inner area
    sim_rows = self.pexplorer_tile_h
    sim_cols = self.pexplorer_tile_w

    # Parameter ranges
    px_label, px_min, px_max = mode_def["param_x"]
    py_label, py_min, py_max = mode_def["param_y"]

    # If center provided, create a neighborhood around it
    px_span = (px_max - px_min) * 0.4  # zoom to 40% of full range
    py_span = (py_max - py_min) * 0.4

    if center_x is not None and center_y is not None:
        # Clamp center so the range stays within bounds
        px_lo = max(px_min, center_x - px_span / 2)
        px_hi = min(px_max, center_x + px_span / 2)
        py_lo = max(py_min, center_y - py_span / 2)
        py_hi = min(py_max, center_y + py_span / 2)
        # Ensure minimum span
        if px_hi - px_lo < (px_max - px_min) * 0.05:
            px_lo = center_x - (px_max - px_min) * 0.025
            px_hi = center_x + (px_max - px_min) * 0.025
        if py_hi - py_lo < (py_max - py_min) * 0.05:
            py_lo = center_y - (py_max - py_min) * 0.025
            py_hi = center_y + (py_max - py_min) * 0.025
    else:
        px_lo, px_hi = px_min, px_max
        py_lo, py_hi = py_min, py_max

    self.pexplorer_px_range = (px_lo, px_hi)
    self.pexplorer_py_range = (py_lo, py_hi)
    self.pexplorer_px_label = px_label
    self.pexplorer_py_label = py_label
    self.pexplorer_px_full = (px_min, px_max)
    self.pexplorer_py_full = (py_min, py_max)

    # Cursor position (selected tile)
    self.pexplorer_sel_r = self.pexplorer_grid_rows // 2
    self.pexplorer_sel_c = self.pexplorer_grid_cols // 2

    # Create mini-simulations
    gr = self.pexplorer_grid_rows
    gc = self.pexplorer_grid_cols
    init_fn = mode_def["init"]

    self.pexplorer_sims = []
    self.pexplorer_params = []  # (px, py) for each tile
    for row in range(gr):
        sim_row = []
        param_row = []
        for col in range(gc):
            # Interpolate parameters
            if gc > 1:
                px = px_lo + (px_hi - px_lo) * col / (gc - 1)
            else:
                px = (px_lo + px_hi) / 2
            if gr > 1:
                py = py_lo + (py_hi - py_lo) * row / (gr - 1)
            else:
                py = (py_lo + py_hi) / 2
            param_row.append((px, py))
            sim_row.append(init_fn(sim_rows, sim_cols, px, py))
        self.pexplorer_sims.append(sim_row)
        self.pexplorer_params.append(param_row)

    self.pexplorer_step_fn = mode_def["step"]
    self.pexplorer_sample_fn = mode_def["sample"]
    self.pexplorer_generation = 0
    self.pexplorer_steps_per_frame = 2

    self.pexplorer_mode = True
    self.pexplorer_menu = False
    self.pexplorer_running = False
    self._flash(f"Parameter Explorer: {mode_def['name']} — Space to start, arrows to select, Enter to zoom")


def _pexplorer_step(self):
    """Advance all mini-simulations by one batch of steps."""
    step_fn = self.pexplorer_step_fn
    spf = self.pexplorer_steps_per_frame
    for row in self.pexplorer_sims:
        for sim in row:
            step_fn(sim, spf)
    self.pexplorer_generation += spf


def _handle_pexplorer_menu_key(self, key):
    """Handle keys in the parameter explorer mode selection menu."""
    if key == -1:
        return True
    n = len(EXPLORABLE_MODES)
    if key == curses.KEY_UP or key == ord("k"):
        self.pexplorer_menu_sel = (self.pexplorer_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.pexplorer_menu_sel = (self.pexplorer_menu_sel + 1) % n
        return True
    if key == ord("q") or key == 27:
        self.pexplorer_menu = False
        self._flash("Parameter Explorer cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER):
        self._pexplorer_init(self.pexplorer_menu_sel)
        return True
    return True


def _handle_pexplorer_key(self, key):
    """Handle keys while in parameter explorer mode."""
    if key == -1:
        return True
    if key == ord("q") or key == 27:
        self._exit_param_explorer_mode()
        return True
    if key == ord(" "):
        self.pexplorer_running = not self.pexplorer_running
        self._flash("Playing" if self.pexplorer_running else "Paused")
        return True
    if key == ord("n") or key == ord("."):
        self.pexplorer_running = False
        self._pexplorer_step()
        return True
    # Navigate tile selection
    if key == curses.KEY_UP or key == ord("w"):
        self.pexplorer_sel_r = max(0, self.pexplorer_sel_r - 1)
        px, py = self.pexplorer_params[self.pexplorer_sel_r][self.pexplorer_sel_c]
        self._flash(f"Selected: {self.pexplorer_px_label}={px:.4f} {self.pexplorer_py_label}={py:.4f}")
        return True
    if key == curses.KEY_DOWN or key == ord("s"):
        self.pexplorer_sel_r = min(self.pexplorer_grid_rows - 1, self.pexplorer_sel_r + 1)
        px, py = self.pexplorer_params[self.pexplorer_sel_r][self.pexplorer_sel_c]
        self._flash(f"Selected: {self.pexplorer_px_label}={px:.4f} {self.pexplorer_py_label}={py:.4f}")
        return True
    if key == curses.KEY_LEFT or key == ord("a"):
        self.pexplorer_sel_c = max(0, self.pexplorer_sel_c - 1)
        px, py = self.pexplorer_params[self.pexplorer_sel_r][self.pexplorer_sel_c]
        self._flash(f"Selected: {self.pexplorer_px_label}={px:.4f} {self.pexplorer_py_label}={py:.4f}")
        return True
    if key == curses.KEY_RIGHT or key == ord("d"):
        self.pexplorer_sel_c = min(self.pexplorer_grid_cols - 1, self.pexplorer_sel_c + 1)
        px, py = self.pexplorer_params[self.pexplorer_sel_r][self.pexplorer_sel_c]
        self._flash(f"Selected: {self.pexplorer_px_label}={px:.4f} {self.pexplorer_py_label}={py:.4f}")
        return True
    # Enter/click: zoom into selected tile's parameters
    if key in (10, 13, curses.KEY_ENTER):
        px, py = self.pexplorer_params[self.pexplorer_sel_r][self.pexplorer_sel_c]
        self._flash(f"Zooming into {self.pexplorer_px_label}={px:.4f} {self.pexplorer_py_label}={py:.4f}")
        self._pexplorer_init(self.pexplorer_mode_idx, center_x=px, center_y=py)
        self.pexplorer_running = True
        return True
    # Zoom out: widen parameter range back toward full
    if key == ord("z") or key == ord("-"):
        px_lo, px_hi = self.pexplorer_px_range
        py_lo, py_hi = self.pexplorer_py_range
        px_full_lo, px_full_hi = self.pexplorer_px_full
        py_full_lo, py_full_hi = self.pexplorer_py_full
        # Expand range by 50%
        cx = (px_lo + px_hi) / 2
        cy = (py_lo + py_hi) / 2
        new_span_x = min((px_hi - px_lo) * 1.5, px_full_hi - px_full_lo)
        new_span_y = min((py_hi - py_lo) * 1.5, py_full_hi - py_full_lo)
        self._pexplorer_init(self.pexplorer_mode_idx, center_x=cx, center_y=cy)
        # Override ranges with wider ones
        self.pexplorer_px_range = (max(px_full_lo, cx - new_span_x / 2),
                                    min(px_full_hi, cx + new_span_x / 2))
        self.pexplorer_py_range = (max(py_full_lo, cy - new_span_y / 2),
                                    min(py_full_hi, cy + new_span_y / 2))
        # Reinit with new ranges
        self._pexplorer_init(self.pexplorer_mode_idx, center_x=cx, center_y=cy)
        self._flash("Zoomed out")
        return True
    # Reset to full range
    if key == ord("R") or key == ord("m"):
        self.pexplorer_mode = False
        self.pexplorer_running = False
        self.pexplorer_menu = True
        self.pexplorer_menu_sel = 0
        return True
    if key == ord("r"):
        self._pexplorer_init(self.pexplorer_mode_idx)
        self._flash("Reset to full parameter range")
        return True
    # Jump to a preset
    if key == ord("p"):
        mode_def = EXPLORABLE_MODES[self.pexplorer_mode_idx]
        presets = mode_def.get("presets", [])
        if presets:
            # Cycle to next preset
            idx = getattr(self, '_pexplorer_preset_idx', -1) + 1
            if idx >= len(presets):
                idx = 0
            self._pexplorer_preset_idx = idx
            name, px, py = presets[idx]
            self._pexplorer_init(self.pexplorer_mode_idx, center_x=px, center_y=py)
            self.pexplorer_running = True
            self._flash(f"Preset: {name} ({self.pexplorer_px_label}={px:.4f} {self.pexplorer_py_label}={py:.4f})")
        return True
    # Steps per frame
    if key == ord("+") or key == ord("="):
        self.pexplorer_steps_per_frame = min(self.pexplorer_steps_per_frame + 1, 10)
        self._flash(f"Steps/frame: {self.pexplorer_steps_per_frame}")
        return True
    if key == ord("_"):
        self.pexplorer_steps_per_frame = max(self.pexplorer_steps_per_frame - 1, 1)
        self._flash(f"Steps/frame: {self.pexplorer_steps_per_frame}")
        return True
    # Global speed
    if key == ord(">"):
        if self.speed_idx < len(SPEEDS) - 1:
            self.speed_idx += 1
        self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True
    if key == ord("<"):
        if self.speed_idx > 0:
            self.speed_idx -= 1
        self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True
    # Mouse click to select tile
    if key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            # Map screen position to tile
            tile_r, tile_c = _screen_to_tile(self, mx, my)
            if tile_r is not None:
                self.pexplorer_sel_r = tile_r
                self.pexplorer_sel_c = tile_c
                px, py = self.pexplorer_params[tile_r][tile_c]
                # Double-click or button-press to zoom
                if bstate & (curses.BUTTON1_DOUBLE_CLICKED if hasattr(curses, 'BUTTON1_DOUBLE_CLICKED') else 0):
                    self._pexplorer_init(self.pexplorer_mode_idx, center_x=px, center_y=py)
                    self.pexplorer_running = True
                    self._flash(f"Zooming into {self.pexplorer_px_label}={px:.4f}")
                else:
                    self._flash(f"Selected: {self.pexplorer_px_label}={px:.4f} {self.pexplorer_py_label}={py:.4f}")
        except curses.error:
            pass
        return True
    return True


def _screen_to_tile(self, mx, my):
    """Convert screen coordinates to tile grid position, or (None, None)."""
    # Account for title row offset
    draw_y_start = 2
    gr = self.pexplorer_grid_rows
    gc = self.pexplorer_grid_cols
    th = self.pexplorer_tile_h
    tw = self.pexplorer_tile_w

    # Each tile occupies (th + 1) rows and (tw * 2 + 1) columns (including border)
    # Plus left axis labels
    label_w = 8
    rel_y = my - draw_y_start
    rel_x = mx - label_w

    if rel_y < 0 or rel_x < 0:
        return None, None

    tile_r = rel_y // (th + 1)
    tile_c = rel_x // (tw * 2 + 1)

    if 0 <= tile_r < gr and 0 <= tile_c < gc:
        return tile_r, tile_c
    return None, None


def _draw_pexplorer_menu(self, max_y, max_x):
    """Draw the parameter explorer mode selection menu."""
    self.stdscr.erase()

    title = "── Parameter Space Explorer ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Explore parameter landscapes with a grid of live simulations"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.color_pair(6))
    except curses.error:
        pass

    y = 5
    for i, mode_def in enumerate(EXPLORABLE_MODES):
        if y >= max_y - 8:
            break
        marker = ">" if i == self.pexplorer_menu_sel else " "
        attr = curses.color_pair(7) | curses.A_BOLD if i == self.pexplorer_menu_sel else curses.color_pair(6)
        px_label, px_min, px_max = mode_def["param_x"]
        py_label, py_min, py_max = mode_def["param_y"]
        line = (f" {marker} {mode_def['name']:<35s}"
                f" {px_label}=[{px_min:.3f}..{px_max:.3f}]"
                f"  {py_label}=[{py_min:.3f}..{py_max:.3f}]")
        line = line[:max_x - 2]
        try:
            self.stdscr.addstr(y, 1, line, attr)
        except curses.error:
            pass
        # Show presets on next line for selected mode
        if i == self.pexplorer_menu_sel:
            y += 1
            presets = mode_def.get("presets", [])
            if presets and y < max_y - 8:
                preset_names = ", ".join(p[0] for p in presets[:6])
                pline = f"     Presets: {preset_names}"
                pline = pline[:max_x - 2]
                try:
                    self.stdscr.addstr(y, 1, pline, curses.color_pair(3))
                except curses.error:
                    pass
        y += 1

    # Info box
    info_y = max(y + 1, max_y - 8)
    info_lines = [
        "The Parameter Space Explorer displays a grid of live simulations,",
        "each running with slightly different parameter values.  Navigate",
        "to interesting tiles and press Enter to zoom in and explore the",
        "neighborhood.  Press 'p' to jump to known interesting presets.",
        "",
        "Use arrow keys to select tiles, Enter to zoom in, 'z' to zoom out,",
        "'r' to reset to full range, 'p' to cycle presets.",
    ]
    for i, info in enumerate(info_lines):
        iy = info_y + i
        if iy >= max_y - 2:
            break
        try:
            self.stdscr.addstr(iy, 2, info[:max_x - 3], curses.color_pair(1))
        except curses.error:
            pass

    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [j/k]=navigate  [Enter]=select  [q/Esc]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_pexplorer(self, max_y, max_x):
    """Draw the parameter explorer grid of live simulations."""
    self.stdscr.erase()

    gr = self.pexplorer_grid_rows
    gc = self.pexplorer_grid_cols
    th = self.pexplorer_tile_h
    tw = self.pexplorer_tile_w
    sample_fn = self.pexplorer_sample_fn

    # Title bar
    sel_r, sel_c = self.pexplorer_sel_r, self.pexplorer_sel_c
    sel_px, sel_py = self.pexplorer_params[sel_r][sel_c]
    state = "▶" if self.pexplorer_running else "‖"
    px_lo, px_hi = self.pexplorer_px_range
    py_lo, py_hi = self.pexplorer_py_range
    title = (f" {state} Parameter Explorer: {self.pexplorer_mode_name}"
             f"  |  gen {self.pexplorer_generation}"
             f"  |  {self.pexplorer_px_label}={sel_px:.4f}"
             f"  {self.pexplorer_py_label}={sel_py:.4f}"
             f"  |  {self.pexplorer_steps_per_frame}x")
    title = title[:max_x - 1]
    try:
        self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Layout: y-axis label on left, grid of tiles, x-axis label on bottom
    label_w = 8  # width for y-axis labels
    draw_y_start = 2
    draw_x_start = label_w

    # Draw y-axis label (parameter name, vertical)
    py_label = self.pexplorer_py_label
    label_mid_y = draw_y_start + (gr * (th + 1)) // 2
    for ci, ch in enumerate(py_label):
        ly = label_mid_y - len(py_label) // 2 + ci
        if 0 <= ly < max_y - 2:
            try:
                self.stdscr.addstr(ly, 0, ch, curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass

    # Draw y-axis tick values
    for row in range(gr):
        _, py = self.pexplorer_params[row][0]
        ty = draw_y_start + row * (th + 1) + th // 2
        if ty < max_y - 2:
            label = f"{py:.3f}"
            try:
                self.stdscr.addstr(ty, max(2, label_w - len(label) - 1), label,
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # Draw tiles
    for row in range(gr):
        for col in range(gc):
            sim = self.pexplorer_sims[row][col]
            is_selected = (row == sel_r and col == sel_c)

            # Tile position on screen
            tile_y = draw_y_start + row * (th + 1)
            tile_x = draw_x_start + col * (tw * 2 + 1)

            if tile_y + th >= max_y - 2 or tile_x + tw * 2 >= max_x:
                continue

            # Draw border (highlight selected tile)
            border_attr = (curses.color_pair(7) | curses.A_BOLD) if is_selected else (curses.color_pair(6) | curses.A_DIM)

            # Top border
            if row == 0:
                corner_l = _TILE_CORNER_TL if col == 0 else _TILE_T_DOWN
                corner_r = _TILE_CORNER_TR
                border_str = corner_l + _TILE_BORDER_H * (tw * 2) + corner_r
                try:
                    self.stdscr.addstr(tile_y - 1, tile_x, border_str[:max_x - tile_x], border_attr)
                except curses.error:
                    pass

            # Left border for each row of the tile
            for tr in range(th):
                sy = tile_y + tr
                if sy >= max_y - 2:
                    break
                try:
                    self.stdscr.addstr(sy, tile_x, _TILE_BORDER_V, border_attr)
                except curses.error:
                    pass

            # Right border
            rx = tile_x + tw * 2
            if rx < max_x:
                for tr in range(th):
                    sy = tile_y + tr
                    if sy >= max_y - 2:
                        break
                    try:
                        self.stdscr.addstr(sy, rx, _TILE_BORDER_V, border_attr)
                    except curses.error:
                        pass

            # Bottom border
            by = tile_y + th
            if by < max_y - 2:
                corner_l = _TILE_CORNER_BL if col == 0 else _TILE_T_UP if row == gr - 1 else _TILE_CROSS
                if col == 0:
                    corner_l = _TILE_T_RIGHT if row < gr - 1 else _TILE_CORNER_BL
                else:
                    corner_l = _TILE_CROSS if row < gr - 1 else _TILE_T_UP
                border_str = corner_l + _TILE_BORDER_H * (tw * 2)
                if col == gc - 1:
                    corner_r = _TILE_T_LEFT if row < gr - 1 else _TILE_CORNER_BR
                    border_str += corner_r
                try:
                    self.stdscr.addstr(by, tile_x, border_str[:max_x - tile_x], border_attr)
                except curses.error:
                    pass

            # Draw simulation content inside tile
            sim_rows = min(th, sim["rows"])
            sim_cols = min(tw, sim["cols"])
            for sr in range(sim_rows):
                sy = tile_y + sr
                if sy >= max_y - 2:
                    break
                for sc in range(sim_cols):
                    sx = tile_x + 1 + sc * 2
                    if sx + 1 >= max_x:
                        break
                    v = sample_fn(sim, sr, sc)
                    if v < 0.005:
                        continue
                    # Density glyph
                    di = int(v * 4.0)
                    if di < 1:
                        di = 1
                    elif di > 4:
                        di = 4
                    ch = _DENSITY[di]
                    # Color tier
                    ci = int(v * 7.99)
                    if ci > 7:
                        ci = 7
                    pair_idx, extra = _COLOR_TIERS[ci]
                    attr = curses.color_pair(pair_idx) | extra
                    # Dim non-selected tiles slightly
                    if not is_selected:
                        attr |= curses.A_DIM
                    try:
                        self.stdscr.addstr(sy, sx, ch, attr)
                    except curses.error:
                        pass

            # Draw selection indicator
            if is_selected:
                # Bright corner markers
                try:
                    self.stdscr.addstr(tile_y, tile_x, "┌", curses.color_pair(3) | curses.A_BOLD)
                    self.stdscr.addstr(tile_y, tile_x + tw * 2, "┐", curses.color_pair(3) | curses.A_BOLD)
                    self.stdscr.addstr(tile_y + th - 1, tile_x, "└", curses.color_pair(3) | curses.A_BOLD)
                    self.stdscr.addstr(tile_y + th - 1, tile_x + tw * 2, "┘", curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass

    # Draw x-axis labels below grid
    axis_y = draw_y_start + gr * (th + 1)
    if axis_y < max_y - 1:
        # Parameter values for each column
        for col in range(gc):
            px, _ = self.pexplorer_params[0][col]
            lx = draw_x_start + col * (tw * 2 + 1) + 1
            label = f"{px:.3f}"
            if lx + len(label) < max_x:
                try:
                    self.stdscr.addstr(axis_y, lx, label, curses.color_pair(6) | curses.A_DIM)
                except curses.error:
                    pass
        # X-axis label
        px_label_str = f"← {self.pexplorer_px_label} →"
        px_label_x = draw_x_start + (gc * (tw * 2 + 1)) // 2 - len(px_label_str) // 2
        if axis_y + 1 < max_y - 1 and px_label_x > 0:
            try:
                self.stdscr.addstr(axis_y + 1, px_label_x, px_label_str,
                                   curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass

    # Status bar
    status_y = max_y - 2
    if status_y > 0:
        range_info = (f" Range: {self.pexplorer_px_label}=[{px_lo:.4f}..{px_hi:.4f}]"
                      f"  {self.pexplorer_py_label}=[{py_lo:.4f}..{py_hi:.4f}]"
                      f"  |  Grid: {gr}×{gc}={gr*gc} sims"
                      f"  |  Speed: {SPEED_LABELS[self.speed_idx]}")
        range_info = range_info[:max_x - 1]
        try:
            self.stdscr.addstr(status_y, 0, range_info, curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [←→↑↓]=select [Enter]=zoom in [z]=zoom out [p]=preset [r]=reset [+/-]=steps [R]=menu [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def register(App):
    """Register parameter explorer mode methods on the App class."""
    App._enter_param_explorer_mode = _enter_param_explorer_mode
    App._exit_param_explorer_mode = _exit_param_explorer_mode
    App._pexplorer_init = _pexplorer_init
    App._pexplorer_step = _pexplorer_step
    App._handle_pexplorer_menu_key = _handle_pexplorer_menu_key
    App._handle_pexplorer_key = _handle_pexplorer_key
    App._draw_pexplorer_menu = _draw_pexplorer_menu
    App._draw_pexplorer = _draw_pexplorer
