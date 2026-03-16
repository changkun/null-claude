"""Long-Exposure Photography mode.

Composites hundreds of simulation frames into a single artistic still image,
revealing the full trajectory and flow patterns of any simulation — like
astrophotography for cellular automata.

Blends frame data over a configurable time window (50–500 generations) using
accumulation buffers, producing luminance trails, flow lines, and density maps
rendered as a single high-detail truecolor frame.

Keybindings:
    Ctrl+E      Start/stop long-exposure capture
    Ctrl+F      Freeze/unfreeze the current composite (view result)
    [/]         Decrease/increase exposure window length
    {/}         Cycle blend mode (additive / max / average)
    Ctrl+]      Export frozen composite to file
"""

import curses
import json
import os
import time

from life.colors import colormap_rgb, COLORMAP_NAMES

# Blend modes
BLEND_MODES = ["additive", "max", "average"]

# Density glyphs: increasing visual weight
_DENSITY_GLYPHS = [" ", "·", "░", "▒", "▓", "█"]

# Default exposure window sizes
_EXPOSURE_PRESETS = [50, 100, 150, 200, 300, 500]


# ── state initialisation ─────────────────────────────────────────────────

def _long_exposure_init(self):
    """Initialise long-exposure state variables (called from App.__init__)."""
    self.long_exp_active = False       # currently accumulating frames
    self.long_exp_frozen = False       # viewing frozen composite
    self.long_exp_window = 200         # target number of frames to accumulate
    self.long_exp_blend = "additive"   # blend mode
    self.long_exp_frames_captured = 0  # frames accumulated so far
    # Accumulation buffers: (y, x) -> [total_r, total_g, total_b, hit_count, max_r, max_g, max_b]
    self._long_exp_accum: dict[tuple[int, int], list] = {}
    # Frozen composite: (y, x) -> (r, g, b, density_fraction)
    self._long_exp_composite: dict[tuple[int, int], tuple[int, int, int, float]] = {}
    self._long_exp_max_hits = 0        # max hit count across all cells
    self._long_exp_start_time = 0.0    # when capture started


# ── accumulation ──────────────────────────────────────────────────────────

def _long_exposure_accumulate(self):
    """Capture one frame into the accumulation buffer.

    Reads from tc_buf (truecolor cells) and stdscr (curses cells) to gather
    all visible content, similar to ghost trail capture but accumulating
    rather than storing discrete frames.
    """
    if not self.long_exp_active or self.long_exp_frozen:
        return

    my, mx = self.stdscr.getmaxyx()
    safe_mx = mx - 1
    accum = self._long_exp_accum

    # 1) Truecolor cells (full RGB)
    seen = set()
    for y, x, text, r, g, b, _bold, _dim in self.tc_buf.cells:
        if r is None:
            continue
        key = (y, x)
        seen.add(key)
        if key not in accum:
            accum[key] = [0, 0, 0, 0, 0, 0, 0]
        buf = accum[key]
        buf[0] += r
        buf[1] += g
        buf[2] += b
        buf[3] += 1
        buf[4] = max(buf[4], r)
        buf[5] = max(buf[5], g)
        buf[6] = max(buf[6], b)

    # 2) Curses screen cells (fallback — use colormap to derive RGB)
    cmap = getattr(self, 'tc_colormap', 'viridis')
    for y in range(min(my, my - 2)):  # skip status lines
        for x in range(safe_mx):
            key = (y, x)
            if key in seen:
                continue
            try:
                ch = self.stdscr.inch(y, x)
                c = ch & 0xFF
                if c != ord(" ") and c != 0:
                    r, g, b = colormap_rgb(cmap, 0.7)
                    if key not in accum:
                        accum[key] = [0, 0, 0, 0, 0, 0, 0]
                    buf = accum[key]
                    buf[0] += r
                    buf[1] += g
                    buf[2] += b
                    buf[3] += 1
                    buf[4] = max(buf[4], r)
                    buf[5] = max(buf[5], g)
                    buf[6] = max(buf[6], b)
            except curses.error:
                pass

    self.long_exp_frames_captured += 1
    # Update max hits
    for buf in accum.values():
        if buf[3] > self._long_exp_max_hits:
            self._long_exp_max_hits = buf[3]

    # Auto-freeze when window is reached
    if self.long_exp_frames_captured >= self.long_exp_window:
        _long_exposure_freeze(self)


# ── composite generation ──────────────────────────────────────────────────

def _long_exposure_freeze(self):
    """Generate the final composite from the accumulation buffer."""
    self.long_exp_frozen = True
    self.long_exp_active = False

    accum = self._long_exp_accum
    max_hits = max(1, self._long_exp_max_hits)
    blend = self.long_exp_blend
    composite = {}

    for (y, x), buf in accum.items():
        total_r, total_g, total_b, hits, max_r, max_g, max_b = buf
        if hits == 0:
            continue

        density = hits / max_hits  # 0.0 to 1.0

        if blend == "additive":
            # Additive: scale by density, brighter where more activity
            scale = min(1.0, density * 2.0)  # boost low-density areas
            r = min(255, int(total_r / hits * (0.3 + 0.7 * scale)))
            g = min(255, int(total_g / hits * (0.3 + 0.7 * scale)))
            b = min(255, int(total_b / hits * (0.3 + 0.7 * scale)))
            # Add luminance boost for high-traffic areas
            boost = min(80, int(density * 80))
            r = min(255, r + boost)
            g = min(255, g + boost)
            b = min(255, b + boost)
        elif blend == "max":
            # Max: peak intensity at each pixel
            r, g, b = max_r, max_g, max_b
        else:
            # Average: simple mean colour
            r = total_r // hits
            g = total_g // hits
            b = total_b // hits

        composite[(y, x)] = (r, g, b, density)

    self._long_exp_composite = composite
    elapsed = time.monotonic() - self._long_exp_start_time
    self._flash(
        f"Long Exposure frozen: {self.long_exp_frames_captured} frames, "
        f"{elapsed:.1f}s — press Ctrl+] to export, Ctrl+F to unfreeze"
    )


# ── rendering ─────────────────────────────────────────────────────────────

def _long_exposure_draw_composite(self):
    """Render the frozen composite as a full-screen truecolor image."""
    if not self._long_exp_composite:
        return

    my, mx = self.stdscr.getmaxyx()
    self.stdscr.erase()
    self.tc_buf.clear()

    for (y, x), (r, g, b, density) in self._long_exp_composite.items():
        if y >= my - 1 or x >= mx - 1:
            continue
        # Select glyph based on density
        gi = min(len(_DENSITY_GLYPHS) - 1, int(density * (len(_DENSITY_GLYPHS) - 1)))
        glyph = _DENSITY_GLYPHS[gi]
        if glyph == " ":
            # Very low density: still show a faint dot
            if density > 0.01:
                glyph = "·"
                r = max(20, r // 3)
                g = max(20, g // 3)
                b = max(20, b // 3)
            else:
                continue
        self.tc_buf.put(y, x, glyph, r, g, b)

    # Draw title bar
    frames = self.long_exp_frames_captured
    blend_tag = self.long_exp_blend.upper()[:3]
    title = f" LONG EXPOSURE — {frames}f {blend_tag} — Ctrl+F:unfreeze Ctrl+]:export "
    try:
        self.stdscr.addstr(0, max(0, (mx - len(title)) // 2), title,
                           curses.color_pair(3) | curses.A_BOLD)
    except curses.error:
        pass


# ── indicator overlay ─────────────────────────────────────────────────────

def _long_exposure_draw_indicator(self):
    """Draw capture progress badge while accumulating."""
    if not self.long_exp_active and not self.long_exp_frozen:
        return

    my, mx = self.stdscr.getmaxyx()
    if self.long_exp_active:
        pct = min(100, int(self.long_exp_frames_captured / max(1, self.long_exp_window) * 100))
        # Build a mini progress bar
        bar_w = 10
        filled = int(pct / 100 * bar_w)
        bar = "█" * filled + "░" * (bar_w - filled)
        blend_tag = self.long_exp_blend.upper()[:3]
        label = f" ◉ EXPOSURE {self.long_exp_frames_captured}/{self.long_exp_window} [{bar}] {blend_tag} "
    else:
        label = f" ◎ EXPOSED {self.long_exp_frames_captured}f (frozen) "

    col = max(0, mx - len(label) - 1)
    if col < 0 or len(label) >= mx:
        return
    try:
        self.stdscr.addstr(0, col, label, curses.color_pair(3) | curses.A_BOLD)
    except curses.error:
        pass
    self.stdscr.refresh()


# ── export ────────────────────────────────────────────────────────────────

def _long_exposure_export(self):
    """Export the frozen composite to a JSON file and a viewable text file."""
    if not self.long_exp_frozen or not self._long_exp_composite:
        self._flash("No frozen composite to export")
        return

    from life.constants import SAVE_DIR
    exp_dir = os.path.join(SAVE_DIR, "long_exposure")
    os.makedirs(exp_dir, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    base = f"exposure_{ts}"

    # Export as JSON (machine-readable, can be re-loaded)
    data = {
        "frames": self.long_exp_frames_captured,
        "window": self.long_exp_window,
        "blend": self.long_exp_blend,
        "timestamp": time.time(),
        "width": 0,
        "height": 0,
        "pixels": [],
    }
    max_y = max_x = 0
    for (y, x), (r, g, b, d) in self._long_exp_composite.items():
        data["pixels"].append({"y": y, "x": x, "r": r, "g": g, "b": b, "d": round(d, 4)})
        max_y = max(max_y, y)
        max_x = max(max_x, x)
    data["height"] = max_y + 1
    data["width"] = max_x + 1

    json_path = os.path.join(exp_dir, base + ".json")
    try:
        with open(json_path, "w") as f:
            json.dump(data, f)
    except OSError as e:
        self._flash(f"Export error: {e}")
        return

    # Export as ANSI art text file (viewable in terminal with cat)
    ansi_path = os.path.join(exp_dir, base + ".ans")
    try:
        lines: dict[int, list[tuple[int, str]]] = {}
        for (y, x), (r, g, b, density) in self._long_exp_composite.items():
            gi = min(len(_DENSITY_GLYPHS) - 1, int(density * (len(_DENSITY_GLYPHS) - 1)))
            glyph = _DENSITY_GLYPHS[gi]
            if glyph == " " and density > 0.01:
                glyph = "·"
            elif glyph == " ":
                continue
            if y not in lines:
                lines[y] = []
            lines[y].append((x, f"\033[38;2;{r};{g};{b}m{glyph}\033[0m"))

        with open(ansi_path, "w") as f:
            for y in range(max_y + 1):
                if y in lines:
                    cells = sorted(lines[y], key=lambda t: t[0])
                    prev_x = 0
                    for cx, s in cells:
                        if cx > prev_x:
                            f.write(" " * (cx - prev_x))
                        f.write(s)
                        prev_x = cx + 1
                f.write("\n")
    except OSError:
        pass  # ANSI export is best-effort

    self._flash(f"Exported: {base}.json + .ans")


# ── key handling ──────────────────────────────────────────────────────────

def _long_exposure_handle_key(self, key):
    """Handle long-exposure key bindings.  Returns True if key was consumed."""
    # Ctrl+E (5) — toggle capture start/stop
    if key == 5:
        if self.long_exp_frozen:
            # If frozen, Ctrl+E starts a new capture (discards old)
            self.long_exp_frozen = False
            self._long_exp_composite.clear()
        if self.long_exp_active:
            # Stop and freeze what we have
            if self.long_exp_frames_captured > 0:
                _long_exposure_freeze(self)
            else:
                self.long_exp_active = False
                self._flash("Long Exposure cancelled (no frames)")
        else:
            # Start new capture
            self.long_exp_active = True
            self.long_exp_frames_captured = 0
            self._long_exp_accum.clear()
            self._long_exp_max_hits = 0
            self._long_exp_start_time = time.monotonic()
            self._flash(
                f"Long Exposure started — {self.long_exp_window} frame window, "
                f"{self.long_exp_blend} blend"
            )
        return True

    # Ctrl+F (6) — freeze/unfreeze composite view
    if key == 6:
        if self.long_exp_frozen:
            # Unfreeze — return to normal view
            self.long_exp_frozen = False
            self._flash("Long Exposure unfrozen — simulation visible")
        elif self.long_exp_active and self.long_exp_frames_captured > 0:
            _long_exposure_freeze(self)
        elif self._long_exp_composite:
            # Re-freeze (show previous composite)
            self.long_exp_frozen = True
            self._flash("Long Exposure re-frozen")
        else:
            self._flash("No exposure data to freeze")
        return True

    # '[' — decrease exposure window
    if key == ord("["):
        old = self.long_exp_window
        self.long_exp_window = max(10, self.long_exp_window - 50)
        if self.long_exp_window != old:
            self._flash(f"Exposure window: {self.long_exp_window} frames")
        return True

    # ']' — increase exposure window
    if key == ord("]"):
        old = self.long_exp_window
        self.long_exp_window = min(1000, self.long_exp_window + 50)
        if self.long_exp_window != old:
            self._flash(f"Exposure window: {self.long_exp_window} frames")
        return True

    # '{' — cycle blend mode backward
    if key == ord("{"):
        idx = BLEND_MODES.index(self.long_exp_blend)
        self.long_exp_blend = BLEND_MODES[(idx - 1) % len(BLEND_MODES)]
        self._flash(f"Exposure blend: {self.long_exp_blend}")
        return True

    # '}' — cycle blend mode forward
    if key == ord("}"):
        idx = BLEND_MODES.index(self.long_exp_blend)
        self.long_exp_blend = BLEND_MODES[(idx + 1) % len(BLEND_MODES)]
        self._flash(f"Exposure blend: {self.long_exp_blend}")
        return True

    # Ctrl+] (29) — export frozen composite
    if key == 29:
        _long_exposure_export(self)
        return True

    return False


# ── main hook ─────────────────────────────────────────────────────────────

def _long_exposure_process(self):
    """Accumulate current frame if capture is active.  Called once per draw cycle."""
    if self.long_exp_active and not self.long_exp_frozen:
        _long_exposure_accumulate(self)


# ── registration ──────────────────────────────────────────────────────────

def register(App):
    """Attach long-exposure methods and state initialiser to App."""
    App._long_exposure_init = _long_exposure_init
    App._long_exposure_process = _long_exposure_process
    App._long_exposure_draw_composite = _long_exposure_draw_composite
    App._long_exposure_draw_indicator = _long_exposure_draw_indicator
    App._long_exposure_handle_key = _long_exposure_handle_key
    App._long_exposure_export = _long_exposure_export
