"""Mode: cinematic_demo — auto-playing director that sequences through simulations
with smooth crossfade transitions, parameter animations, and camera moves."""
import curses
import math
import random
import time

from life.constants import SPEEDS
from life.modes.mashup import MASHUP_SIMS, _ENGINES

_DENSITY = " ░▒▓█"

# ── Curated demo reel acts ────────────────────────────────────────
# Each act defines a simulation, duration, camera path, and parameter sweeps.
# camera: {"zoom_start", "zoom_end", "pan_x_start", "pan_x_end",
#           "pan_y_start", "pan_y_end"}  (all floats, zoom 1.0 = normal)
# params: dict of {param_key: (start_val, end_val)} to interpolate over duration

_DEFAULT_CAM = {
    "zoom_start": 1.0, "zoom_end": 1.0,
    "pan_x_start": 0.5, "pan_x_end": 0.5,
    "pan_y_start": 0.5, "pan_y_end": 0.5,
}

_ZOOM_IN_CAM = {
    "zoom_start": 1.0, "zoom_end": 2.0,
    "pan_x_start": 0.5, "pan_x_end": 0.5,
    "pan_y_start": 0.5, "pan_y_end": 0.5,
}

_PAN_RIGHT_CAM = {
    "zoom_start": 1.3, "zoom_end": 1.3,
    "pan_x_start": 0.3, "pan_x_end": 0.7,
    "pan_y_start": 0.5, "pan_y_end": 0.5,
}

_SLOW_ZOOM_OUT = {
    "zoom_start": 1.8, "zoom_end": 1.0,
    "pan_x_start": 0.5, "pan_x_end": 0.5,
    "pan_y_start": 0.5, "pan_y_end": 0.5,
}

_DIAGONAL_PAN = {
    "zoom_start": 1.5, "zoom_end": 1.5,
    "pan_x_start": 0.2, "pan_x_end": 0.8,
    "pan_y_start": 0.2, "pan_y_end": 0.8,
}

DEMO_ACTS = [
    {
        "name": "Emergence",
        "desc": "Game of Life — zooming into the chaos",
        "sim": "gol",
        "duration": 12.0,
        "camera": _ZOOM_IN_CAM,
        "color": 1,
    },
    {
        "name": "Ripples",
        "desc": "Wave Equation — interfering pulses",
        "sim": "wave",
        "duration": 10.0,
        "camera": _DEFAULT_CAM,
        "color": 2,
    },
    {
        "name": "Morphogenesis",
        "desc": "Reaction-Diffusion — Turing patterns form",
        "sim": "rd",
        "duration": 14.0,
        "camera": _SLOW_ZOOM_OUT,
        "color": 3,
    },
    {
        "name": "Wildfire",
        "desc": "Forest Fire — burns and regrows",
        "sim": "fire",
        "duration": 10.0,
        "camera": _PAN_RIGHT_CAM,
        "color": 4,
    },
    {
        "name": "Murmuration",
        "desc": "Boids Flocking — collective motion",
        "sim": "boids",
        "duration": 10.0,
        "camera": _DEFAULT_CAM,
        "color": 5,
    },
    {
        "name": "Phase Transition",
        "desc": "Ising Model — spins align and break",
        "sim": "ising",
        "duration": 10.0,
        "camera": _ZOOM_IN_CAM,
        "color": 6,
    },
    {
        "name": "Dominance Spirals",
        "desc": "Rock-Paper-Scissors — cyclic invasion waves",
        "sim": "rps",
        "duration": 10.0,
        "camera": _DIAGONAL_PAN,
        "color": 7,
    },
    {
        "name": "Slime Intelligence",
        "desc": "Physarum — solving mazes with chemistry",
        "sim": "physarum",
        "duration": 12.0,
        "camera": _SLOW_ZOOM_OUT,
        "color": 1,
    },
]

# Curated playlists (sequences of act indices)
DEMO_PLAYLISTS = [
    {
        "name": "The Grand Tour",
        "desc": "All 8 simulation engines in cinematic sequence",
        "acts": list(range(len(DEMO_ACTS))),
        "loop": True,
    },
    {
        "name": "Fluid Dreams",
        "desc": "Wave, Reaction-Diffusion, Physarum — fluid-like phenomena",
        "acts": [1, 2, 7],
        "loop": True,
    },
    {
        "name": "Life & Death",
        "desc": "Game of Life, Forest Fire, Ising — creation and destruction",
        "acts": [0, 3, 5],
        "loop": True,
    },
    {
        "name": "Swarm Logic",
        "desc": "Boids, Physarum, RPS — collective behavior emerges",
        "acts": [4, 7, 6],
        "loop": True,
    },
    {
        "name": "Random Director",
        "desc": "Shuffled acts, never the same show twice",
        "acts": None,  # sentinel for random
        "loop": True,
    },
]

# ── Crossfade transition duration ──
_CROSSFADE_DURATION = 1.5  # seconds


# ════════════════════════════════════════════════════════════════════
#  Mode entry / exit
# ════════════════════════════════════════════════════════════════════

def _enter_cinematic_demo_mode(self):
    """Enter Cinematic Demo Reel mode — show playlist selection menu."""
    self.cinem_menu = True
    self.cinem_menu_sel = 0
    self._flash("Cinematic Demo Reel — choose a playlist")


def _exit_cinematic_demo_mode(self):
    """Exit Cinematic Demo Reel mode and clean up."""
    self.cinem_mode = False
    self.cinem_menu = False
    self.cinem_running = False
    self.cinem_sim_state = None
    self.cinem_prev_density = None
    self._flash("Cinematic Demo Reel OFF")


# ════════════════════════════════════════════════════════════════════
#  Initialization
# ════════════════════════════════════════════════════════════════════

def _cinematic_init(self, playlist_idx):
    """Initialize the demo reel from a chosen playlist."""
    playlist = DEMO_PLAYLISTS[playlist_idx]
    self.cinem_menu = False
    self.cinem_mode = True
    self.cinem_running = True
    self.cinem_paused = False

    # Playlist state
    if playlist["acts"] is None:
        # Random director — shuffle all acts
        acts = list(range(len(DEMO_ACTS)))
        random.shuffle(acts)
        self.cinem_act_sequence = acts
    else:
        self.cinem_act_sequence = list(playlist["acts"])
    self.cinem_loop = playlist["loop"]
    self.cinem_act_idx = 0
    self.cinem_playlist_name = playlist["name"]

    # Simulation grid — use generous internal resolution
    max_y, max_x = self.stdscr.getmaxyx()
    self.cinem_sim_rows = max(30, max_y)
    self.cinem_sim_cols = max(40, (max_x // 2))

    # Crossfade state
    self.cinem_crossfade = 0.0  # 0 = no crossfade, >0 = fading in
    self.cinem_prev_density = None

    # Title card state
    self.cinem_title_alpha = 1.0

    # Launch first act
    _cinematic_launch_act(self)


def _cinematic_launch_act(self):
    """Launch the current act in the sequence."""
    if not self.cinem_act_sequence:
        return

    idx = self.cinem_act_idx % len(self.cinem_act_sequence)
    act_id = self.cinem_act_sequence[idx]
    act = DEMO_ACTS[act_id]

    # Capture previous density for crossfade
    if hasattr(self, 'cinem_density') and self.cinem_density is not None:
        self.cinem_prev_density = [row[:] for row in self.cinem_density]
    else:
        self.cinem_prev_density = None

    # Initialize the new simulation engine
    sim_id = act["sim"]
    init_fn, _, dens_fn = _ENGINES[sim_id]
    self.cinem_sim_state = init_fn(self.cinem_sim_rows, self.cinem_sim_cols)
    self.cinem_sim_id = sim_id
    self.cinem_density = dens_fn(self.cinem_sim_state)

    # Act timing
    self.cinem_act_start = time.monotonic()
    self.cinem_act_duration = act["duration"]
    self.cinem_act = act
    self.cinem_generation = 0

    # Crossfade begins
    self.cinem_crossfade = 1.0
    self.cinem_title_alpha = 1.0


def _cinematic_advance(self):
    """Advance to the next act."""
    self.cinem_act_idx += 1
    if self.cinem_act_idx >= len(self.cinem_act_sequence):
        if self.cinem_loop:
            # Reshuffle if random director
            if DEMO_PLAYLISTS and any(p["acts"] is None for p in DEMO_PLAYLISTS):
                for p in DEMO_PLAYLISTS:
                    if p["name"] == self.cinem_playlist_name and p["acts"] is None:
                        random.shuffle(self.cinem_act_sequence)
                        break
            self.cinem_act_idx = 0
        else:
            self.cinem_running = False
            return
    _cinematic_launch_act(self)


# ════════════════════════════════════════════════════════════════════
#  Simulation step
# ════════════════════════════════════════════════════════════════════

def _cinematic_step(self):
    """Advance the demo reel — step simulation, update transitions."""
    if not self.cinem_running or self.cinem_paused:
        return

    now = time.monotonic()
    elapsed = now - self.cinem_act_start

    # Step the simulation engine
    _, step_fn, dens_fn = _ENGINES[self.cinem_sim_id]
    step_fn(self.cinem_sim_state, None, 0.0)
    self.cinem_density = dens_fn(self.cinem_sim_state)
    self.cinem_generation += 1

    # Crossfade decay
    if self.cinem_crossfade > 0:
        self.cinem_crossfade = max(0.0, self.cinem_crossfade - 1.0 / (
            _CROSSFADE_DURATION * 20))  # ~20 steps per second assumed

    # Title card fade: visible 3s, then fade over 1s
    if elapsed < 3.0:
        self.cinem_title_alpha = 1.0
    elif elapsed < 4.0:
        self.cinem_title_alpha = max(0.0, 1.0 - (elapsed - 3.0))
    else:
        self.cinem_title_alpha = 0.0

    # Check if act is finished
    if elapsed >= self.cinem_act_duration:
        _cinematic_advance(self)


# ════════════════════════════════════════════════════════════════════
#  Camera math
# ════════════════════════════════════════════════════════════════════

def _cinematic_camera(self, max_y, max_x):
    """Compute current camera viewport based on act progress.

    Returns (src_r, src_c, view_rows, view_cols) — the region of the
    simulation grid to render.
    """
    act = self.cinem_act
    cam = act.get("camera", _DEFAULT_CAM)
    now = time.monotonic()
    t = min(1.0, (now - self.cinem_act_start) / max(0.1, self.cinem_act_duration))

    # Smooth ease-in-out
    t = t * t * (3.0 - 2.0 * t)

    zoom = cam["zoom_start"] + (cam["zoom_end"] - cam["zoom_start"]) * t
    pan_x = cam["pan_x_start"] + (cam["pan_x_end"] - cam["pan_x_start"]) * t
    pan_y = cam["pan_y_start"] + (cam["pan_y_end"] - cam["pan_y_start"]) * t

    sim_rows = self.cinem_sim_rows
    sim_cols = self.cinem_sim_cols

    # View size based on zoom (higher zoom = smaller view = more zoomed in)
    view_rows = max(5, int(sim_rows / zoom))
    view_cols = max(5, int(sim_cols / zoom))

    # Ensure view doesn't exceed sim bounds
    view_rows = min(view_rows, sim_rows)
    view_cols = min(view_cols, sim_cols)

    # Pan center
    center_r = int(pan_y * sim_rows)
    center_c = int(pan_x * sim_cols)

    # Clamp to keep view within bounds
    src_r = max(0, min(sim_rows - view_rows, center_r - view_rows // 2))
    src_c = max(0, min(sim_cols - view_cols, center_c - view_cols // 2))

    return src_r, src_c, view_rows, view_cols


# ════════════════════════════════════════════════════════════════════
#  Drawing
# ════════════════════════════════════════════════════════════════════

def _draw_cinematic_menu(self, max_y, max_x):
    """Draw the playlist selection menu."""
    self.stdscr.erase()

    # Title
    title = "━━━ CINEMATIC DEMO REEL ━━━"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(2) | curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Autonomous director with crossfades, camera moves & parameter sweeps"
    try:
        self.stdscr.addstr(2, max(0, (max_x - len(subtitle)) // 2),
                           subtitle[:max_x - 2],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass

    # Playlist list
    menu_y = 5
    for i, pl in enumerate(DEMO_PLAYLISTS):
        y = menu_y + i * 3
        if y >= max_y - 3:
            break
        selected = i == self.cinem_menu_sel
        marker = "▸ " if selected else "  "
        attr = (curses.color_pair(2) | curses.A_REVERSE | curses.A_BOLD
                if selected else curses.color_pair(6))
        line = f"{marker}{pl['name']}"
        try:
            self.stdscr.addstr(y, 4, line[:max_x - 6], attr)
        except curses.error:
            pass
        # Description
        if y + 1 < max_y - 3:
            try:
                self.stdscr.addstr(y + 1, 8, pl["desc"][:max_x - 10],
                                   curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass
        # Act count
        if y + 2 < max_y - 3:
            n_acts = len(DEMO_ACTS) if pl["acts"] is None else len(pl["acts"])
            info = f"{n_acts} acts, {'looping' if pl['loop'] else 'one-shot'}"
            try:
                self.stdscr.addstr(y + 2, 8, info[:max_x - 10],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # Footer
    footer = " ↑↓ Select │ Enter Launch │ Esc Back "
    try:
        self.stdscr.addstr(max_y - 1, 0, footer[:max_x - 1].ljust(max_x - 1),
                           curses.color_pair(6) | curses.A_REVERSE)
    except curses.error:
        pass


def _draw_cinematic(self, max_y, max_x):
    """Draw the cinematic demo reel — simulation with camera and transitions."""
    self.stdscr.erase()
    act = self.cinem_act
    color = act.get("color", 6)

    # Get camera viewport
    src_r, src_c, view_rows, view_cols = _cinematic_camera(self, max_y, max_x)

    # Screen rendering area (leave room for status bar)
    screen_rows = max_y - 2
    screen_cols = (max_x - 1) // 2

    density = self.cinem_density
    prev = self.cinem_prev_density
    cf = self.cinem_crossfade  # crossfade amount (1.0 = fully old, 0.0 = fully new)

    for sy in range(min(screen_rows, view_rows)):
        if 1 + sy >= max_y - 1:
            break
        # Map screen row to simulation row
        sim_r = src_r + int(sy * view_rows / max(1, screen_rows))
        if sim_r >= self.cinem_sim_rows:
            continue
        d_row = density[sim_r] if sim_r < len(density) else []
        p_row = prev[sim_r] if prev and sim_r < len(prev) else None

        for sx in range(min(screen_cols, view_cols)):
            px = sx * 2
            if px + 1 >= max_x:
                break
            # Map screen col to simulation col
            sim_c = src_c + int(sx * view_cols / max(1, screen_cols))
            if sim_c >= self.cinem_sim_cols:
                continue

            val = d_row[sim_c] if sim_c < len(d_row) else 0.0

            # Crossfade blending
            if cf > 0 and p_row is not None and sim_c < len(p_row):
                old_val = p_row[sim_c]
                val = old_val * cf + val * (1.0 - cf)

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
                self.stdscr.addstr(1 + sy, px, ch + " ", attr)
            except curses.error:
                pass

    # ── Title card overlay ──
    if self.cinem_title_alpha > 0:
        _draw_cinematic_title_card(self, max_y, max_x)

    # ── Status bar ──
    _draw_cinematic_status(self, max_y, max_x)


def _draw_cinematic_title_card(self, max_y, max_x):
    """Draw the act title card overlay."""
    act = self.cinem_act
    alpha = self.cinem_title_alpha

    attr_bright = curses.color_pair(2) | curses.A_BOLD
    attr_dim = curses.color_pair(7) | curses.A_DIM
    if alpha < 0.5:
        attr_bright = curses.color_pair(7) | curses.A_DIM
        attr_dim = curses.color_pair(7) | curses.A_DIM

    name = act["name"]
    desc = act["desc"]
    act_num = (self.cinem_act_idx % len(self.cinem_act_sequence)) + 1
    total = len(self.cinem_act_sequence)

    box_w = max(len(name), len(desc), 20) + 6
    box_h = 5
    bx = max(0, (max_x - box_w) // 2)
    by = max(0, (max_y - box_h) // 2 - 2)

    if by + box_h < max_y and bx + box_w < max_x:
        try:
            top = "╔" + "═" * (box_w - 2) + "╗"
            self.stdscr.addstr(by, bx, top[:max_x - bx - 1], attr_dim)

            act_line = f"║ ACT {act_num}/{total}".ljust(box_w - 1) + "║"
            self.stdscr.addstr(by + 1, bx, act_line[:max_x - bx - 1], attr_dim)

            name_line = f"║ {name}".ljust(box_w - 1) + "║"
            self.stdscr.addstr(by + 2, bx, name_line[:max_x - bx - 1], attr_bright)

            desc_line = f"║ {desc}".ljust(box_w - 1) + "║"
            self.stdscr.addstr(by + 3, bx, desc_line[:max_x - bx - 1], attr_dim)

            bot = "╚" + "═" * (box_w - 2) + "╝"
            self.stdscr.addstr(by + 4, bx, bot[:max_x - bx - 1], attr_dim)
        except curses.error:
            pass


def _draw_cinematic_status(self, max_y, max_x):
    """Draw the thin status bar at the bottom."""
    act = self.cinem_act
    now = time.monotonic()
    elapsed = now - self.cinem_act_start
    remaining = max(0, self.cinem_act_duration - elapsed)
    act_num = (self.cinem_act_idx % len(self.cinem_act_sequence)) + 1
    total = len(self.cinem_act_sequence)
    paused_str = " PAUSED" if self.cinem_paused else ""

    # Progress bar for current act
    pct = min(1.0, elapsed / max(0.1, self.cinem_act_duration))
    bar_w = 20
    filled = int(pct * bar_w)
    bar = "█" * filled + "░" * (bar_w - filled)

    status = (f" {self.cinem_playlist_name}"
              f" │ {act['name']} [{act_num}/{total}]"
              f" │ {bar} {int(remaining)}s"
              f" │ gen {self.cinem_generation}"
              f"{paused_str}"
              f" │ n/p Skip │ Space Pause │ Esc Exit ")

    if max_y > 0:
        try:
            self.stdscr.addstr(max_y - 1, 0, status[:max_x - 1].ljust(max_x - 1),
                               curses.color_pair(6) | curses.A_REVERSE)
        except curses.error:
            pass


# ════════════════════════════════════════════════════════════════════
#  Key handling
# ════════════════════════════════════════════════════════════════════

def _handle_cinematic_menu_key(self, key):
    """Handle keys in the playlist selection menu."""
    if key == -1:
        return True

    n = len(DEMO_PLAYLISTS)

    if key in (curses.KEY_DOWN, ord("j")):
        self.cinem_menu_sel = (self.cinem_menu_sel + 1) % n
        return True
    if key in (curses.KEY_UP, ord("k")):
        self.cinem_menu_sel = (self.cinem_menu_sel - 1) % n
        return True
    if key in (27, ord("q")):
        self.cinem_menu = False
        self.cinem_mode = False
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _cinematic_init(self, self.cinem_menu_sel)
        return True
    return True


def _handle_cinematic_key(self, key):
    """Handle keys during cinematic playback."""
    if key == -1:
        return True

    # Escape / q = exit
    if key == 27 or key == ord("q"):
        _exit_cinematic_demo_mode(self)
        return True

    # Space = pause/resume
    if key == ord(" "):
        self.cinem_paused = not self.cinem_paused
        if not self.cinem_paused:
            # Adjust act start time to account for pause
            self.cinem_act_start = time.monotonic() - (
                self.cinem_act_duration - max(0, self.cinem_act_duration - (
                    time.monotonic() - self.cinem_act_start)))
        return True

    # n / Right = next act
    if key == ord("n") or key == curses.KEY_RIGHT:
        _cinematic_advance(self)
        return True

    # p / Left = previous act
    if key == ord("p") or key == curses.KEY_LEFT:
        self.cinem_act_idx = max(0, self.cinem_act_idx - 1)
        _cinematic_launch_act(self)
        return True

    # r = restart current act
    if key == ord("r"):
        _cinematic_launch_act(self)
        return True

    return True


# ════════════════════════════════════════════════════════════════════
#  Registration
# ════════════════════════════════════════════════════════════════════

def register(App):
    """Register cinematic demo reel mode methods on the App class."""
    App._enter_cinematic_demo_mode = _enter_cinematic_demo_mode
    App._exit_cinematic_demo_mode = _exit_cinematic_demo_mode
    App._cinematic_init = _cinematic_init
    App._cinematic_step = _cinematic_step
    App._cinematic_launch_act = _cinematic_launch_act
    App._cinematic_advance = _cinematic_advance
    App._cinematic_camera = _cinematic_camera
    App._handle_cinematic_menu_key = _handle_cinematic_menu_key
    App._handle_cinematic_key = _handle_cinematic_key
    App._draw_cinematic_menu = _draw_cinematic_menu
    App._draw_cinematic = _draw_cinematic
    App._draw_cinematic_title_card = _draw_cinematic_title_card
    App._draw_cinematic_status = _draw_cinematic_status
