"""Mode: split_screen — dual simulation side-by-side with independent state."""
import curses
import math
import random
import time

from life.constants import SPEEDS

# Reuse the mini-simulation engines from mashup mode
from life.modes.mashup import MASHUP_SIMS, _ENGINES

_DENSITY = " ░▒▓█"

_SIM_BY_ID = {s["id"]: s for s in MASHUP_SIMS}

# Color pairs for left and right panes
_LEFT_COLOR = 6   # cyan-ish
_RIGHT_COLOR = 3  # green-ish

# Curated presets for quick launch
SPLIT_PRESETS = [
    ("Game of Life vs Lenia-style RD", "gol", "rd",
     "Classic discrete CA alongside continuous reaction-diffusion"),
    ("Boids vs N-Body (Physarum)", "boids", "physarum",
     "Flocking swarm next to slime mold network"),
    ("Wave Equation vs Ising Model", "wave", "ising",
     "Continuous waves beside magnetic spin dynamics"),
    ("Forest Fire vs Rock-Paper-Scissors", "fire", "rps",
     "Ecosystem burn-regrow next to cyclic competition"),
    ("Game of Life vs Boids", "gol", "boids",
     "Grid-based automaton beside free-roaming agents"),
    ("Reaction-Diffusion vs Physarum", "rd", "physarum",
     "Two different pattern-forming systems compared"),
    ("Wave vs Game of Life", "wave", "gol",
     "Continuous vs discrete dynamics side by side"),
    ("Ising vs Rock-Paper-Scissors", "ising", "rps",
     "Two spatial competition models compared"),
]


# ════════════════════════════════════════════════════════════════════
#  Mode entry / exit
# ════════════════════════════════════════════════════════════════════

def _enter_split_mode(self):
    """Enter split-screen mode — show preset/custom selection menu."""
    self.split_menu = True
    self.split_menu_sel = 0
    self.split_menu_phase = 0  # 0=presets, 1=pick left, 2=pick right
    self.split_pick_left = None
    self._flash("Split-Screen Mode — pick a preset or choose two simulations")


def _exit_split_mode(self):
    """Exit split-screen mode and clean up."""
    self.split_mode = False
    self.split_menu = False
    self.split_running = False
    self.split_left = None
    self.split_right = None
    self.split_focus = 0
    self._flash("Split-Screen OFF")


# ════════════════════════════════════════════════════════════════════
#  Initialization
# ════════════════════════════════════════════════════════════════════

def _split_init(self, left_id, right_id):
    """Initialize dual panes with the given simulations."""
    max_y, max_x = self.stdscr.getmaxyx()

    # Each pane gets half the terminal width (minus divider)
    pane_w = max(10, (max_x - 3) // 2)  # -3 for divider column + margins
    pane_h = max(5, max_y - 3)           # -3 for title bar + hint bar

    # Simulation grid dimensions per pane
    sim_rows = max(4, pane_h - 2)        # -2 for pane title + padding
    sim_cols = max(4, (pane_w - 1) // 2) # each cell = 2 chars wide

    def make_pane(sim_id, pane_idx):
        init_fn, _, dens_fn = _ENGINES[sim_id]
        state = init_fn(sim_rows, sim_cols)
        density = dens_fn(state)
        return {
            "sim_id": sim_id,
            "name": _SIM_BY_ID[sim_id]["name"],
            "state": state,
            "density": density,
            "sim_rows": sim_rows,
            "sim_cols": sim_cols,
            "generation": 0,
        }

    self.split_left = make_pane(left_id, 0)
    self.split_right = make_pane(right_id, 1)
    self.split_generation = 0
    self.split_running = False
    self.split_focus = 0       # 0=left, 1=right
    self.split_menu = False
    self.split_mode = True
    self._flash(f"Split: {self.split_left['name']}  vs  {self.split_right['name']} — Tab to swap focus, Space to start")


# ════════════════════════════════════════════════════════════════════
#  Simulation step
# ════════════════════════════════════════════════════════════════════

def _split_step(self):
    """Advance both panes by one generation (independent, no coupling)."""
    for pane in (self.split_left, self.split_right):
        if pane is None:
            continue
        _, step_fn, dens_fn = _ENGINES[pane["sim_id"]]
        step_fn(pane["state"], None, 0.0)
        pane["density"] = dens_fn(pane["state"])
        pane["generation"] += 1
    self.split_generation += 1


# ════════════════════════════════════════════════════════════════════
#  Menu drawing
# ════════════════════════════════════════════════════════════════════

def _draw_split_menu(self, max_y, max_x):
    """Draw the split-screen mode selection menu."""
    self.stdscr.erase()
    phase = self.split_menu_phase

    title = "── Split-Screen Dual Simulation ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    if phase == 0:
        # ── Preset selection ──
        subtitle = "Choose a preset pairing or pick your own:"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                               curses.color_pair(6))
        except curses.error:
            pass

        for i, (name, _, _, desc) in enumerate(SPLIT_PRESETS):
            y = 5 + i
            if y >= max_y - 3:
                break
            sel = i == self.split_menu_sel
            marker = "▸ " if sel else "  "
            attr = curses.color_pair(7) | curses.A_BOLD if sel else curses.color_pair(6)
            line = f"{marker}{name}"
            try:
                self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
            except curses.error:
                pass
            if sel:
                try:
                    self.stdscr.addstr(y, 2 + len(line) + 2,
                                       desc[:max_x - len(line) - 6],
                                       curses.color_pair(6) | curses.A_DIM)
                except curses.error:
                    pass

        # Custom option
        ci = len(SPLIT_PRESETS)
        y = 5 + ci
        if y < max_y - 3:
            sel = self.split_menu_sel == ci
            marker = "▸ " if sel else "  "
            attr = curses.color_pair(7) | curses.A_BOLD if sel else curses.color_pair(3)
            try:
                self.stdscr.addstr(y, 2, f"{marker}Custom pairing..."[:max_x - 4], attr)
            except curses.error:
                pass

    elif phase == 1:
        # ── Pick left simulation ──
        which = "LEFT" if self.split_pick_left is None else "RIGHT"
        subtitle = f"Select {which} pane simulation:"
        if self.split_pick_left is not None:
            subtitle += f"  (left: {_SIM_BY_ID[self.split_pick_left]['name']})"
        try:
            self.stdscr.addstr(3, 2, subtitle[:max_x - 4], curses.color_pair(6))
        except curses.error:
            pass
        for i, sim in enumerate(MASHUP_SIMS):
            y = 5 + i
            if y >= max_y - 3:
                break
            sel = i == self.split_menu_sel
            marker = "▸ " if sel else "  "
            attr = curses.color_pair(7) | curses.A_BOLD if sel else curses.color_pair(6)
            try:
                self.stdscr.addstr(y, 2, f"{marker}{sim['name']}"[:max_x - 4], attr)
                self.stdscr.addstr(y, 30, sim["desc"][:max_x - 32],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [Up/Down]=navigate  [Enter]=select  [Esc]=back/exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ════════════════════════════════════════════════════════════════════
#  Menu key handling
# ════════════════════════════════════════════════════════════════════

def _handle_split_menu_key(self, key):
    """Handle input in the split-screen selection menu."""
    if key == -1:
        return True
    phase = self.split_menu_phase

    if phase == 0:
        n = len(SPLIT_PRESETS) + 1
    else:
        n = len(MASHUP_SIMS)

    if key == curses.KEY_UP or key == ord("k"):
        self.split_menu_sel = (self.split_menu_sel - 1) % max(1, n)
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.split_menu_sel = (self.split_menu_sel + 1) % max(1, n)
        return True
    if key == 27:  # Esc
        if phase > 0:
            self.split_menu_phase = 0
            self.split_menu_sel = 0
            self.split_pick_left = None
        else:
            self.split_menu = False
            self._flash("Split-Screen cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER):
        if phase == 0:
            sel = self.split_menu_sel
            if sel < len(SPLIT_PRESETS):
                _, left_id, right_id, _ = SPLIT_PRESETS[sel]
                self._split_init(left_id, right_id)
            else:
                # Custom: go to sim picker
                self.split_menu_phase = 1
                self.split_menu_sel = 0
                self.split_pick_left = None
        elif phase == 1:
            sim_id = MASHUP_SIMS[self.split_menu_sel]["id"]
            if self.split_pick_left is None:
                # First pick → left pane
                self.split_pick_left = sim_id
                self.split_menu_sel = 0
                # Stay in phase 1 for right pick
            else:
                # Second pick → right pane, launch!
                self._split_init(self.split_pick_left, sim_id)
        return True
    return True


# ════════════════════════════════════════════════════════════════════
#  Main simulation drawing
# ════════════════════════════════════════════════════════════════════

def _draw_split(self, max_y, max_x):
    """Draw dual-pane split-screen view."""
    self.stdscr.erase()

    if self.split_left is None or self.split_right is None:
        return

    # ── Title bar ──
    state = "\u25b6 RUNNING" if self.split_running else "\u23f8 PAUSED"
    focus_label = "LEFT" if self.split_focus == 0 else "RIGHT"
    title = (f" SPLIT-SCREEN"
             f"  |  gen {self.split_generation}"
             f"  |  {state}"
             f"  |  focus: {focus_label}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # ── Layout calculations ──
    divider_x = max_x // 2
    pane_h = max(5, max_y - 3)  # -1 title, -1 hint, -1 padding

    # Draw the vertical divider
    for y in range(1, min(1 + pane_h, max_y - 1)):
        try:
            self.stdscr.addstr(y, divider_x, "\u2502",
                               curses.color_pair(7) | curses.A_DIM)
        except curses.error:
            pass

    # ── Draw left pane ──
    left_w = divider_x
    _draw_split_pane(self, self.split_left, 0,
                     1, 0, pane_h, left_w, max_y, max_x,
                     self.split_focus == 0)

    # ── Draw right pane ──
    right_w = max_x - divider_x - 1
    _draw_split_pane(self, self.split_right, 1,
                     1, divider_x + 1, pane_h, right_w, max_y, max_x,
                     self.split_focus == 1)

    # ── Hint bar ──
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [Tab]=swap focus [r]=reset pane [R]=menu [s]=swap sims [q]=exit [>/<]=speed"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_split_pane(self, pane, pane_idx, oy, ox, pane_h, pane_w, max_y, max_x, is_focused):
    """Draw a single simulation pane."""
    color = _LEFT_COLOR if pane_idx == 0 else _RIGHT_COLOR

    # Pane title with focus indicator
    focus_marker = "\u25c6" if is_focused else "\u25c7"
    label = f" {focus_marker} {pane['name']}  gen:{pane['generation']} "
    if oy < max_y:
        title_attr = curses.color_pair(color) | curses.A_BOLD
        if is_focused:
            title_attr |= curses.A_REVERSE
        try:
            self.stdscr.addstr(oy, ox, label[:pane_w], title_attr)
            remaining = pane_w - len(label)
            if remaining > 0:
                self.stdscr.addstr(oy, ox + len(label),
                                   "\u2500" * remaining, title_attr)
        except curses.error:
            pass

    # Draw density grid
    density = pane["density"]
    sim_rows = pane["sim_rows"]
    sim_cols = pane["sim_cols"]
    view_rows = min(sim_rows, pane_h - 1)  # -1 for pane title
    view_cols = min(sim_cols, (pane_w - 1) // 2)

    for r in range(view_rows):
        sy = oy + 1 + r
        if sy >= max_y - 1:
            break
        d_row = density[r] if r < len(density) else []
        for c in range(view_cols):
            sx = ox + c * 2
            if sx + 1 >= max_x:
                break
            val = d_row[c] if c < len(d_row) else 0.0
            if val < 0.01:
                continue
            di = max(1, min(4, int(val * 4.0)))
            ch = _DENSITY[di]
            if val > 0.7:
                attr = curses.color_pair(color) | curses.A_BOLD
            elif val > 0.3:
                attr = curses.color_pair(color)
            else:
                attr = curses.color_pair(color) | curses.A_DIM
            try:
                self.stdscr.addstr(sy, sx, ch + " ", attr)
            except curses.error:
                pass


# ════════════════════════════════════════════════════════════════════
#  Simulation key handling
# ════════════════════════════════════════════════════════════════════

def _handle_split_key(self, key):
    """Handle input during active split-screen simulation."""
    if key == -1:
        return True
    if key == ord("q") or key == 27:
        self._exit_split_mode()
        return True
    if key == ord(" "):
        self.split_running = not self.split_running
        self._flash("Playing" if self.split_running else "Paused")
        return True
    if key == ord("n") or key == ord("."):
        self.split_running = False
        self._split_step()
        return True
    # Tab: swap focus between panes
    if key == 9:  # Tab
        self.split_focus = 1 - self.split_focus
        label = "LEFT" if self.split_focus == 0 else "RIGHT"
        pane = self.split_left if self.split_focus == 0 else self.split_right
        if pane:
            self._flash(f"Focus: {label} ({pane['name']})")
        return True
    # s: swap the two simulations (left<->right)
    if key == ord("s"):
        self.split_left, self.split_right = self.split_right, self.split_left
        self._flash("Swapped left and right panes")
        return True
    # r: reset the focused pane
    if key == ord("r"):
        pane = self.split_left if self.split_focus == 0 else self.split_right
        if pane:
            max_y, max_x = self.stdscr.getmaxyx()
            divider_x = max_x // 2
            pane_w = max(10, divider_x - 1)
            pane_h = max(5, max_y - 3)
            sim_rows = max(4, pane_h - 2)
            sim_cols = max(4, (pane_w - 1) // 2)
            init_fn, _, dens_fn = _ENGINES[pane["sim_id"]]
            pane["state"] = init_fn(sim_rows, sim_cols)
            pane["density"] = dens_fn(pane["state"])
            pane["generation"] = 0
            label = "Left" if self.split_focus == 0 else "Right"
            self._flash(f"{label} pane reset")
        return True
    # R: back to menu
    if key == ord("R"):
        self.split_mode = False
        self.split_running = False
        self.split_menu = True
        self.split_menu_phase = 0
        self.split_menu_sel = 0
        return True
    if key == ord(">"):
        if self.speed_idx < len(SPEEDS) - 1:
            self.speed_idx += 1
        return True
    if key == ord("<"):
        if self.speed_idx > 0:
            self.speed_idx -= 1
        return True
    return True


# ════════════════════════════════════════════════════════════════════
#  Registration
# ════════════════════════════════════════════════════════════════════

def register(App):
    """Register split-screen mode methods on the App class."""
    App._enter_split_mode = _enter_split_mode
    App._exit_split_mode = _exit_split_mode
    App._split_init = _split_init
    App._split_step = _split_step
    App._handle_split_menu_key = _handle_split_menu_key
    App._handle_split_key = _handle_split_key
    App._draw_split_menu = _draw_split_menu
    App._draw_split = _draw_split
