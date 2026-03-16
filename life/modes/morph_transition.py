"""Smooth mode-morphing crossfade transitions.

When switching between modes, captures the outgoing mode's screen content
and crossfades it with the incoming mode over a configurable number of frames.
Old mode fades out while the new mode fades in, creating a visually seamless
transition instead of a hard cut.

Works with all 130+ modes via the truecolor pipeline without modifying any
individual mode logic.  Hooks into _exit_current_modes (capture) and
_tc_refresh (blend).

Toggle with 'G' (Shift+G).  Adjust duration with '[' / ']'.
Cycle easing curve with Ctrl+T.
"""

import curses
import sys


# ── Easing functions ─────────────────────────────────────────────────────

def _ease_linear(t):
    return t

def _ease_smooth(t):
    """Smooth-step (ease-in-out cubic)."""
    return t * t * (3.0 - 2.0 * t)

def _ease_in_out(t):
    """Ease-in-out quintic for a more dramatic curve."""
    if t < 0.5:
        return 16.0 * t * t * t * t * t
    u = 1.0 - t
    return 1.0 - 16.0 * u * u * u * u * u

EASING_FUNCS = [
    ("linear", _ease_linear),
    ("smooth", _ease_smooth),
    ("ease-in-out", _ease_in_out),
]


# ── State initialisation ────────────────────────────────────────────────

def _morph_transition_init(self):
    """Initialise morph transition state variables."""
    self.morph_enabled = False          # global toggle for crossfade transitions
    self.morph_duration = 45            # frames for the crossfade (30-60 typical)
    self.morph_easing_idx = 1           # index into EASING_FUNCS (default: smooth)
    self._morph_active = False          # currently mid-transition?
    self._morph_progress = 0            # current frame counter (0..morph_duration)
    self._morph_old_frame = {}          # captured frame: (y,x) -> (char, r, g, b)
    self._morph_old_curses = {}         # captured curses-only cells: (y,x) -> char


# ── Frame capture ────────────────────────────────────────────────────────

def _morph_capture_frame(self):
    """Capture the current screen content as the outgoing frame.

    Called just before _exit_current_modes clears the old mode.
    Captures both truecolor buffer cells and curses screen content.
    """
    my, mx = self.stdscr.getmaxyx()
    safe_mx = mx - 1
    frame = {}

    # 1) Truecolor cells (full RGB)
    for y, x, text, r, g, b, _bold, _dim in self.tc_buf.cells:
        frame[(y, x)] = (text[:1] if text else " ", r, g, b)

    # 2) Curses screen cells
    for y in range(my):
        for x in range(safe_mx):
            if (y, x) in frame:
                continue
            try:
                ch = self.stdscr.inch(y, x)
                c = ch & 0xFF
                if c != ord(" ") and c != 0:
                    frame[(y, x)] = (chr(c), None, None, None)
            except curses.error:
                pass

    self._morph_old_frame = frame
    self._morph_progress = 0
    self._morph_active = True


# ── Crossfade rendering ─────────────────────────────────────────────────

def _morph_render_crossfade(self):
    """Blend the old captured frame with the new mode's current output.

    Called during _tc_refresh while a transition is active.
    The old frame fades out (alpha decreasing) while new content is
    already being drawn normally by the new mode.
    """
    if not self._morph_active:
        return

    self._morph_progress += 1
    if self._morph_progress >= self.morph_duration:
        # Transition complete
        self._morph_active = False
        self._morph_old_frame.clear()
        return

    # Calculate alpha for the OLD frame (1.0 = fully visible, 0.0 = gone)
    t = self._morph_progress / self.morph_duration
    _name, easing_fn = EASING_FUNCS[self.morph_easing_idx]
    alpha_old = 1.0 - easing_fn(t)

    if alpha_old <= 0.01:
        # Negligible — skip rendering old frame
        self._morph_active = False
        self._morph_old_frame.clear()
        return

    # Build set of positions occupied by the NEW mode's current frame
    new_occupied = set()
    for y, x, _t, _r, _g, _b, _bo, _di in self.tc_buf.cells:
        new_occupied.add((y, x))

    my, mx = self.stdscr.getmaxyx()
    safe_mx = mx - 1

    # Also check curses screen for new mode content
    # (skip this if too expensive — tc_buf cells are the main indicator)

    # Render old frame cells with faded alpha
    parts = []
    for (y, x), (char, r, g, b) in self._morph_old_frame.items():
        if y >= my or x >= safe_mx:
            continue
        if (y, x) in new_occupied:
            # Both old and new have content here — blend by dimming old
            # The new mode's content takes priority but we tint behind it
            continue

        if r is not None:
            # Original RGB — scale by alpha
            dr = max(0, int(r * alpha_old))
            dg = max(0, int(g * alpha_old))
            db = max(0, int(b * alpha_old))
        else:
            # Curses-only cell — use a dim grey based on alpha
            grey = max(0, int(180 * alpha_old))
            dr = dg = db = grey

        # Emit directly as ANSI escape (after curses refresh, before tc_buf render)
        pos = f'\033[{y + 1};{x + 1}H'
        color = f'\033[38;2;{dr};{dg};{db}m'
        dim_attr = '\033[2m' if alpha_old < 0.5 else ''
        parts.append(f'{pos}{color}{dim_attr}{char}')

    if parts:
        parts.append('\033[0m')
        sys.stdout.write(''.join(parts))
        sys.stdout.flush()


# ── Indicator overlay ────────────────────────────────────────────────────

def _morph_draw_indicator(self):
    """Draw a compact status badge when morph transitions are enabled."""
    if not self.morph_enabled:
        return
    my, mx = self.stdscr.getmaxyx()
    easing_name = EASING_FUNCS[self.morph_easing_idx][0]
    if self._morph_active:
        pct = int(100 * self._morph_progress / max(1, self.morph_duration))
        label = f" MORPH:{self.morph_duration}f {easing_name} [{pct}%] "
    else:
        label = f" MORPH:{self.morph_duration}f {easing_name} "
    # Place to the right of ghost trail indicator if present
    col = 1
    if self.ghost_trail_active:
        col += 22  # skip past ghost trail badge
    if col + len(label) >= mx:
        return
    try:
        self.stdscr.addstr(0, col, label, curses.color_pair(3) | curses.A_BOLD)
    except curses.error:
        pass
    self.stdscr.refresh()


# ── Key handling ─────────────────────────────────────────────────────────

def _morph_handle_key(self, key):
    """Handle morph transition key bindings.  Returns True if consumed."""
    # 'G' (Shift+G) — toggle morph transitions on/off
    if key == ord("G"):
        self.morph_enabled = not self.morph_enabled
        if not self.morph_enabled:
            self._morph_active = False
            self._morph_old_frame.clear()
        msg = "Mode Morphing ON" if self.morph_enabled else "Mode Morphing OFF"
        if self.morph_enabled:
            easing_name = EASING_FUNCS[self.morph_easing_idx][0]
            msg += f" ({self.morph_duration} frames, {easing_name})"
        self._flash(msg)
        return True

    if not self.morph_enabled:
        return False

    # '[' — decrease transition duration
    if key == ord("["):
        self.morph_duration = max(10, self.morph_duration - 5)
        self._flash(f"Morph duration: {self.morph_duration} frames")
        return True

    # ']' — increase transition duration
    if key == ord("]"):
        self.morph_duration = min(120, self.morph_duration + 5)
        self._flash(f"Morph duration: {self.morph_duration} frames")
        return True

    # Ctrl+T (20) — cycle easing curve
    if key == 20:
        self.morph_easing_idx = (self.morph_easing_idx + 1) % len(EASING_FUNCS)
        easing_name = EASING_FUNCS[self.morph_easing_idx][0]
        self._flash(f"Morph easing: {easing_name}")
        return True

    return False


# ── Hooks ────────────────────────────────────────────────────────────────

def _morph_on_mode_exit(self):
    """Hook called just before _exit_current_modes.

    If morph transitions are enabled, captures the current screen content
    so it can be crossfaded with the incoming mode.
    """
    if self.morph_enabled:
        _morph_capture_frame(self)


def _morph_on_refresh(self):
    """Hook called during _tc_refresh to render the crossfade overlay.

    Should be called AFTER stdscr.refresh() and AFTER tc_buf.render(),
    so the old frame's fading remnants overlay on top of the new mode.
    """
    if self._morph_active:
        _morph_render_crossfade(self)


# ── Registration ─────────────────────────────────────────────────────────

def register(App):
    """Attach morph transition methods and state initialiser to App."""
    App._morph_transition_init = _morph_transition_init
    App._morph_capture_frame = _morph_capture_frame
    App._morph_render_crossfade = _morph_render_crossfade
    App._morph_draw_indicator = _morph_draw_indicator
    App._morph_handle_key = _morph_handle_key
    App._morph_on_mode_exit = _morph_on_mode_exit
    App._morph_on_refresh = _morph_on_refresh
