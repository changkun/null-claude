"""Visual Post-Processing Pipeline — composable ASCII visual effects.

Provides stackable terminal-space effects (scanlines, bloom, motion trails,
edge detection, color cycling, CRT distortion) that layer on top of ANY
simulation mode.  Toggle via Ctrl+V; combine effects freely.
"""

import curses
import math

# Effects in the order they are applied and displayed in the menu.
EFFECT_LIST = [
    ("scanlines", "Scanlines"),
    ("bloom", "Bloom / Glow"),
    ("trails", "Motion Trails"),
    ("edge_detect", "Edge Detection"),
    ("color_cycle", "Color Cycling"),
    ("crt", "CRT Distortion"),
]

# ── helpers ────────────────────────────────────────────────────────────────

_A_NOT_COLOR = curses.A_ATTRIBUTES & ~curses.A_COLOR if hasattr(curses, "A_COLOR") else curses.A_ATTRIBUTES


def _cell_attr_with(ch_int, extra):
    """Return chgat-ready attr that preserves the cell's color pair and adds *extra*."""
    pair = curses.pair_number(ch_int)
    old = ch_int & _A_NOT_COLOR
    return old | extra | curses.color_pair(pair)


def _is_occupied(ch_int):
    """True if the chtype represents a visible (non-space) character."""
    c = ch_int & 0xFF
    return c != ord(" ") and c != 0


# ── per-effect implementations ────────────────────────────────────────────

def _pp_apply_scanlines(self, my, mx):
    """Darken every other row for a retro scanline look."""
    safe_mx = mx - 1
    for y in range(0, my, 2):
        for x in range(safe_mx):
            try:
                ch = self.stdscr.inch(y, x)
                self.stdscr.chgat(y, x, 1, _cell_attr_with(ch, curses.A_DIM))
            except curses.error:
                pass


def _pp_apply_bloom(self, my, mx):
    """Make every visible cell BOLD and paint a dim glow halo in empty neighbors."""
    safe_mx = mx - 1
    # Single pass: collect occupied cells and their color pairs
    occupied = []
    for y in range(my):
        for x in range(safe_mx):
            try:
                ch = self.stdscr.inch(y, x)
                if _is_occupied(ch):
                    pair = curses.pair_number(ch)
                    old = ch & _A_NOT_COLOR
                    self.stdscr.chgat(y, x, 1, old | curses.A_BOLD | curses.color_pair(pair))
                    occupied.append((y, x, pair))
            except curses.error:
                pass

    # Glow halo — only draw into empty cells
    glow_char = "\u2591"  # ░
    for oy, ox, pair in occupied:
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = oy + dy, ox + dx
            if 0 <= ny < my and 0 <= nx < safe_mx:
                try:
                    nch = self.stdscr.inch(ny, nx)
                    if not _is_occupied(nch):
                        self.stdscr.addstr(
                            ny, nx, glow_char,
                            curses.color_pair(pair) | curses.A_DIM,
                        )
                except curses.error:
                    pass


def _pp_apply_trails(self, my, mx):
    """Draw faded echoes from previous frames where the current cell is empty."""
    trail_glyphs = ["\u2593", "\u2592", "\u2591"]  # ▓ ▒ ░

    for fidx, frame in enumerate(reversed(self.pp_trail_buf)):
        glyph = trail_glyphs[min(fidx, len(trail_glyphs) - 1)]
        rows = min(my, len(frame))
        for y in range(rows):
            cols = min(mx - 1, len(frame[y]))
            for x in range(cols):
                occ, pair = frame[y][x]
                if not occ:
                    continue
                try:
                    ch = self.stdscr.inch(y, x)
                    if not _is_occupied(ch):
                        self.stdscr.addstr(
                            y, x, glyph,
                            curses.color_pair(pair) | curses.A_DIM,
                        )
                except curses.error:
                    pass


def _pp_apply_edge_detect(self, my, mx):
    """Remove interior cells so only edges/borders remain."""
    safe_mx = mx - 1
    # Build occupancy bitmap
    occ = []
    for y in range(my):
        row = []
        for x in range(safe_mx):
            try:
                ch = self.stdscr.inch(y, x)
                row.append(_is_occupied(ch))
            except curses.error:
                row.append(False)
        occ.append(row)

    # Erase interior cells (all 4 cardinal neighbors occupied)
    for y in range(my):
        for x in range(safe_mx):
            if not occ[y][x]:
                continue
            interior = True
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < my and 0 <= nx < safe_mx:
                    if not occ[ny][nx]:
                        interior = False
                        break
                else:
                    interior = False
                    break
            if interior:
                try:
                    self.stdscr.addstr(y, x, " ")
                except curses.error:
                    pass


def _pp_apply_color_cycle(self, my, mx):
    """Rotate the age-based color pairs (1-5) over time."""
    offset = self.pp_frame_count % 5
    if offset == 0:
        return
    safe_mx = mx - 1
    for y in range(my):
        for x in range(safe_mx):
            try:
                ch = self.stdscr.inch(y, x)
                if not _is_occupied(ch):
                    continue
                pair = curses.pair_number(ch)
                if 1 <= pair <= 5:
                    new_pair = ((pair - 1 + offset) % 5) + 1
                    old = ch & _A_NOT_COLOR
                    self.stdscr.chgat(y, x, 1, old | curses.color_pair(new_pair))
            except curses.error:
                pass


def _pp_apply_crt(self, my, mx):
    """CRT monitor effect: vignette darkening, scanlines, and bezel border."""
    safe_mx = mx - 1
    if safe_mx < 4 or my < 4:
        return

    # Vignette — dim the outer band of rows/columns
    v_rows = max(1, my // 6)
    v_cols = max(2, mx // 6)

    def _dim_cell(y, x):
        try:
            ch = self.stdscr.inch(y, x)
            self.stdscr.chgat(y, x, 1, _cell_attr_with(ch, curses.A_DIM))
        except curses.error:
            pass

    # Top / bottom bands
    for y in list(range(v_rows)) + list(range(my - v_rows, my)):
        for x in range(safe_mx):
            _dim_cell(y, x)

    # Left / right bands (excluding corners already processed)
    for y in range(v_rows, my - v_rows):
        for x in list(range(v_cols)) + list(range(max(0, safe_mx - v_cols), safe_mx)):
            _dim_cell(y, x)

    # Scanlines on odd rows
    for y in range(1, my, 2):
        for x in range(safe_mx):
            _dim_cell(y, x)

    # CRT bezel frame
    try:
        h_line = "\u2500"  # ─
        v_line = "\u2502"  # │
        dim6 = curses.color_pair(6) | curses.A_DIM
        for x in range(safe_mx):
            self.stdscr.addstr(0, x, h_line, dim6)
            self.stdscr.addstr(my - 1, x, h_line, dim6)
        for y in range(my):
            self.stdscr.addstr(y, 0, v_line, dim6)
            if safe_mx > 1:
                self.stdscr.addstr(y, safe_mx - 1, v_line, dim6)
        self.stdscr.addstr(0, 0, "\u256d", dim6)               # ╭
        self.stdscr.addstr(0, safe_mx - 1, "\u256e", dim6)     # ╮
        self.stdscr.addstr(my - 1, 0, "\u2570", dim6)          # ╰
        self.stdscr.addstr(my - 1, safe_mx - 1, "\u256f", dim6)  # ╯
    except curses.error:
        pass


# ── capture / apply / indicator ──────────────────────────────────────────

def _pp_capture_frame(self, my, mx):
    """Snapshot which cells are occupied (for trail effect next frame)."""
    safe_mx = mx - 1
    frame = []
    for y in range(my):
        row = []
        for x in range(safe_mx):
            try:
                ch = self.stdscr.inch(y, x)
                row.append((_is_occupied(ch), curses.pair_number(ch)))
            except curses.error:
                row.append((False, 0))
        frame.append(row)
    self.pp_trail_buf.append(frame)
    if len(self.pp_trail_buf) > self.pp_trail_depth:
        self.pp_trail_buf = self.pp_trail_buf[-self.pp_trail_depth:]


def _pp_apply(self):
    """Run every active effect in the canonical order."""
    if not self.pp_active:
        return
    my, mx = self.stdscr.getmaxyx()
    if my < 3 or mx < 6:
        return

    self.pp_frame_count += 1

    for eid, _name in EFFECT_LIST:
        if eid not in self.pp_active:
            continue
        if eid == "scanlines":
            _pp_apply_scanlines(self, my, mx)
        elif eid == "bloom":
            _pp_apply_bloom(self, my, mx)
        elif eid == "trails":
            _pp_apply_trails(self, my, mx)
        elif eid == "edge_detect":
            _pp_apply_edge_detect(self, my, mx)
        elif eid == "color_cycle":
            _pp_apply_color_cycle(self, my, mx)
        elif eid == "crt":
            _pp_apply_crt(self, my, mx)

    # Capture frame for trails (after effects so trails include processed look)
    if "trails" in self.pp_active:
        _pp_capture_frame(self, my, mx)

    self.stdscr.refresh()


# ── menu drawing ─────────────────────────────────────────────────────────

def _pp_draw_menu(self):
    """Draw the effect toggle overlay centered on screen."""
    my, mx = self.stdscr.getmaxyx()
    box_w = 38
    box_h = len(EFFECT_LIST) + 6
    if my < box_h + 2 or mx < box_w + 2:
        return

    sy = (my - box_h) // 2
    sx = (mx - box_w) // 2
    attr_border = curses.color_pair(7) | curses.A_BOLD
    attr_title = curses.color_pair(3) | curses.A_BOLD
    attr_on = curses.color_pair(2) | curses.A_BOLD
    attr_off = curses.color_pair(6) | curses.A_DIM
    attr_hint = curses.color_pair(6) | curses.A_DIM

    # Background fill
    blank = " " * (box_w - 2)
    for row in range(box_h):
        try:
            self.stdscr.addstr(sy + row, sx, " " * box_w, curses.color_pair(0))
        except curses.error:
            pass

    # Border
    try:
        self.stdscr.addstr(sy, sx, "\u2554" + "\u2550" * (box_w - 2) + "\u2557", attr_border)
        for row in range(1, box_h - 1):
            self.stdscr.addstr(sy + row, sx, "\u2551", attr_border)
            self.stdscr.addstr(sy + row, sx + box_w - 1, "\u2551", attr_border)
        self.stdscr.addstr(sy + box_h - 1, sx, "\u255a" + "\u2550" * (box_w - 2) + "\u255d", attr_border)
    except curses.error:
        pass

    # Title
    title = " Visual FX Pipeline "
    tx = sx + (box_w - len(title)) // 2
    try:
        self.stdscr.addstr(sy, tx, title, attr_title)
    except curses.error:
        pass

    # Effect list
    for i, (eid, name) in enumerate(EFFECT_LIST):
        row = sy + 2 + i
        is_on = eid in self.pp_active
        marker = "\u2714" if is_on else " "  # ✔ or space
        line_attr = attr_on if is_on else attr_off
        try:
            self.stdscr.addstr(row, sx + 2, f" [{marker}] {i + 1}  {name}", line_attr)
        except curses.error:
            pass

    # Hint bar
    hint = "1-6: toggle   Ctrl+V / Esc: close"
    hx = sx + (box_w - len(hint)) // 2
    try:
        self.stdscr.addstr(sy + box_h - 2, hx, hint, attr_hint)
    except curses.error:
        pass

    self.stdscr.refresh()


def _pp_draw_indicator(self):
    """Draw a small status tag when effects are active but menu is closed."""
    if not self.pp_active:
        return
    my, mx = self.stdscr.getmaxyx()

    shorts = {
        "scanlines": "SL",
        "bloom": "BL",
        "trails": "TR",
        "edge_detect": "ED",
        "color_cycle": "CC",
        "crt": "CRT",
    }
    tags = [shorts[eid] for eid, _ in EFFECT_LIST if eid in self.pp_active]
    label = " FX:" + "+".join(tags) + " "
    col = mx - len(label) - 1
    if col < 0:
        return
    try:
        self.stdscr.addstr(0, col, label, curses.color_pair(3) | curses.A_BOLD)
    except curses.error:
        pass
    self.stdscr.refresh()


# ── key handling ─────────────────────────────────────────────────────────

def _pp_handle_key(self, key):
    """Handle post-processing hotkeys.  Returns True if the key was consumed."""
    # Ctrl+V toggles the menu
    if key == 22:  # Ctrl+V
        self.pp_menu = not self.pp_menu
        if not self.pp_menu:
            if self.pp_active:
                names = [n for eid, n in EFFECT_LIST if eid in self.pp_active]
                self._flash("Visual FX: " + ", ".join(names))
            else:
                self._flash("Visual FX OFF")
        return True

    if not self.pp_menu:
        return False

    # While menu is open, 1-6 toggle effects
    if ord("1") <= key <= ord("6"):
        idx = key - ord("1")
        eid = EFFECT_LIST[idx][0]
        if eid in self.pp_active:
            self.pp_active.discard(eid)
            if eid == "trails":
                self.pp_trail_buf.clear()
        else:
            self.pp_active.add(eid)
        return True

    if key == 27:  # Esc closes menu
        self.pp_menu = False
        if self.pp_active:
            names = [n for eid, n in EFFECT_LIST if eid in self.pp_active]
            self._flash("Visual FX: " + ", ".join(names))
        else:
            self._flash("Visual FX OFF")
        return True

    # Consume all other keys while menu is open to prevent mode changes
    return True


# ── registration ─────────────────────────────────────────────────────────

def register(App):
    """Attach post-processing methods and state initializer to App."""
    App._pp_apply = _pp_apply
    App._pp_draw_menu = _pp_draw_menu
    App._pp_draw_indicator = _pp_draw_indicator
    App._pp_handle_key = _pp_handle_key
