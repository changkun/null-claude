"""Color schemes, colormaps, and truecolor rendering for the terminal UI."""
import curses
import os
import sys

# Age-based colour tiers (pair indices 1–5)
AGE_COLORS = [
    (curses.COLOR_GREEN, 1),   # newborn
    (curses.COLOR_CYAN, 2),    # young
    (curses.COLOR_YELLOW, 3),  # mature
    (curses.COLOR_MAGENTA, 4), # old
    (curses.COLOR_RED, 5),     # ancient
]


# ── Truecolor detection ──────────────────────────────────────────────────────

_TRUECOLOR = None  # cached result


def truecolor_available():
    """Return True if the terminal supports 24-bit (truecolor) output."""
    global _TRUECOLOR
    if _TRUECOLOR is None:
        ct = os.environ.get('COLORTERM', '')
        _TRUECOLOR = ct in ('truecolor', '24bit')
    return _TRUECOLOR


# ── Perceptually uniform colormaps ────────────────────────────────────────────
# Each colormap is defined by control points and interpolated to 256 entries.

def _lerp_color(c0, c1, t):
    """Linear interpolate between two (R,G,B) tuples at parameter t in [0,1]."""
    return (
        int(c0[0] + (c1[0] - c0[0]) * t + 0.5),
        int(c0[1] + (c1[1] - c0[1]) * t + 0.5),
        int(c0[2] + (c1[2] - c0[2]) * t + 0.5),
    )


def _build_colormap(control_points):
    """Build a 256-entry colormap from a list of (position, R, G, B) control points."""
    cmap = [(0, 0, 0)] * 256
    for i in range(256):
        t = i / 255.0
        # Find surrounding control points
        lo = control_points[0]
        hi = control_points[-1]
        for j in range(len(control_points) - 1):
            if control_points[j][0] <= t <= control_points[j + 1][0]:
                lo = control_points[j]
                hi = control_points[j + 1]
                break
        seg_len = hi[0] - lo[0]
        seg_t = (t - lo[0]) / seg_len if seg_len > 0 else 0.0
        cmap[i] = _lerp_color(lo[1:], hi[1:], seg_t)
    return cmap


# Viridis: dark purple → blue → teal → green → yellow
_VIRIDIS_PTS = [
    (0.00, 68, 1, 84), (0.07, 72, 23, 105), (0.13, 72, 36, 117),
    (0.20, 64, 67, 135), (0.25, 56, 88, 140), (0.32, 46, 111, 142),
    (0.38, 39, 130, 142), (0.44, 33, 145, 140), (0.50, 31, 158, 137),
    (0.56, 40, 170, 126), (0.63, 53, 183, 121), (0.69, 80, 196, 106),
    (0.75, 110, 206, 88), (0.81, 147, 215, 63), (0.88, 181, 222, 43),
    (0.94, 217, 229, 31), (1.00, 253, 231, 37),
]

# Magma: black → deep purple → magenta → orange → pale yellow
_MAGMA_PTS = [
    (0.00, 0, 0, 4), (0.07, 10, 7, 39), (0.13, 28, 16, 68),
    (0.20, 56, 15, 101), (0.25, 79, 18, 123), (0.32, 106, 25, 127),
    (0.38, 129, 37, 129), (0.44, 155, 44, 126), (0.50, 181, 54, 122),
    (0.56, 206, 70, 112), (0.63, 229, 89, 100), (0.69, 243, 113, 98),
    (0.75, 251, 135, 97), (0.81, 253, 165, 118), (0.88, 254, 194, 140),
    (0.94, 254, 225, 167), (1.00, 252, 253, 191),
]

# Inferno: black → indigo → red → orange → pale yellow
_INFERNO_PTS = [
    (0.00, 0, 0, 4), (0.07, 16, 7, 43), (0.13, 40, 11, 84),
    (0.20, 73, 3, 104), (0.25, 101, 0, 110), (0.32, 132, 18, 106),
    (0.38, 159, 42, 99), (0.44, 185, 55, 82), (0.50, 212, 72, 66),
    (0.56, 231, 96, 44), (0.63, 245, 125, 21), (0.69, 250, 153, 12),
    (0.75, 250, 175, 5), (0.81, 240, 203, 24), (0.88, 226, 228, 40),
    (0.94, 236, 248, 95), (1.00, 252, 255, 164),
]

# Plasma: blue → purple → red → orange → yellow
_PLASMA_PTS = [
    (0.00, 13, 8, 135), (0.07, 43, 4, 150), (0.13, 75, 3, 161),
    (0.20, 103, 0, 167), (0.25, 126, 3, 168), (0.32, 148, 16, 160),
    (0.38, 168, 34, 150), (0.44, 186, 52, 137), (0.50, 203, 70, 121),
    (0.56, 216, 87, 107), (0.63, 229, 107, 93), (0.69, 239, 128, 77),
    (0.75, 248, 149, 64), (0.81, 252, 174, 50), (0.88, 253, 195, 40),
    (0.94, 248, 222, 35), (1.00, 240, 249, 33),
]

# Ocean: deep navy → blue → cyan → teal → aqua (custom for water/fluid modes)
_OCEAN_PTS = [
    (0.00, 3, 4, 30), (0.12, 8, 18, 65), (0.25, 15, 42, 110),
    (0.37, 20, 80, 145), (0.50, 30, 130, 170), (0.62, 50, 170, 185),
    (0.75, 80, 200, 200), (0.87, 140, 225, 220), (1.00, 200, 245, 240),
]

# Thermal: cool blue → purple → red → orange → white hot
_THERMAL_PTS = [
    (0.00, 10, 10, 60), (0.14, 30, 20, 120), (0.28, 80, 15, 150),
    (0.42, 160, 30, 100), (0.57, 210, 50, 50), (0.71, 240, 120, 20),
    (0.85, 255, 200, 50), (1.00, 255, 255, 220),
]

# Terrain: ocean → beach → forest → mountain → snow
_TERRAIN_PTS = [
    (0.00, 10, 20, 80), (0.12, 20, 60, 140), (0.22, 40, 110, 170),
    (0.30, 210, 200, 140), (0.35, 60, 150, 60), (0.45, 40, 120, 40),
    (0.55, 30, 90, 30), (0.65, 130, 120, 70), (0.78, 140, 130, 110),
    (0.88, 190, 190, 190), (1.00, 250, 250, 255),
]

# Amber: dark brown → amber → gold → bright yellow (for bio/physarum)
_AMBER_PTS = [
    (0.00, 20, 15, 5), (0.14, 50, 30, 5), (0.28, 90, 50, 5),
    (0.42, 140, 80, 10), (0.57, 190, 120, 15), (0.71, 220, 160, 20),
    (0.85, 245, 200, 40), (1.00, 255, 240, 120),
]

# Build all colormaps once at import time
COLORMAPS = {
    'viridis': _build_colormap(_VIRIDIS_PTS),
    'magma': _build_colormap(_MAGMA_PTS),
    'inferno': _build_colormap(_INFERNO_PTS),
    'plasma': _build_colormap(_PLASMA_PTS),
    'ocean': _build_colormap(_OCEAN_PTS),
    'thermal': _build_colormap(_THERMAL_PTS),
    'terrain': _build_colormap(_TERRAIN_PTS),
    'amber': _build_colormap(_AMBER_PTS),
}

COLORMAP_NAMES = list(COLORMAPS.keys())


def colormap_rgb(name, fraction):
    """Sample a colormap at position fraction (0.0–1.0), returning (R, G, B)."""
    cmap = COLORMAPS.get(name)
    if cmap is None:
        return (255, 255, 255)
    idx = max(0, min(255, int(fraction * 255)))
    return cmap[idx]


# ── Nearest xterm-256 color lookup (for fallback) ────────────────────────────

# The standard 6x6x6 color cube occupies indices 16–231 in xterm-256.
# Grayscale ramp occupies 232–255.

def _nearest_256(r, g, b):
    """Map an (R, G, B) triple to the nearest xterm-256 color index."""
    # Try the 6x6x6 cube (indices 16–231)
    ri = round(r / 255.0 * 5)
    gi = round(g / 255.0 * 5)
    bi = round(b / 255.0 * 5)
    cube_idx = 16 + 36 * ri + 6 * gi + bi
    # Reconstruct the cube colour
    cube_r, cube_g, cube_b = ri * 51, gi * 51, bi * 51
    cube_dist = (r - cube_r) ** 2 + (g - cube_g) ** 2 + (b - cube_b) ** 2

    # Try the grayscale ramp (indices 232–255)
    gray = round((r * 0.299 + g * 0.587 + b * 0.114 - 8) / 10.0)
    gray = max(0, min(23, gray))
    gray_idx = 232 + gray
    gray_val = 8 + gray * 10
    gray_dist = (r - gray_val) ** 2 + (g - gray_val) ** 2 + (b - gray_val) ** 2

    return gray_idx if gray_dist < cube_dist else cube_idx


# ── TrueColor screen buffer ──────────────────────────────────────────────────
# Collects truecolor cell writes during a frame, then batch-renders them
# after curses refresh to avoid conflicts with curses' internal buffer.

class TrueColorBuffer:
    """Buffer for 24-bit truecolor terminal output.

    Modes call put() or put_mapped() during their draw phase.
    After curses refresh(), call render() to overlay truecolor cells.
    """

    __slots__ = ('cells', 'enabled')

    def __init__(self):
        self.cells = []
        self.enabled = truecolor_available()

    def put(self, y, x, text, r, g, b, bold=False, dim=False):
        """Queue a truecolor cell for rendering."""
        self.cells.append((y, x, text, r, g, b, bold, dim))

    def put_mapped(self, y, x, text, colormap, fraction, bold=False, dim=False):
        """Queue a cell coloured by sampling a named colormap at fraction."""
        r, g, b = colormap_rgb(colormap, fraction)
        self.cells.append((y, x, text, r, g, b, bold, dim))

    def render(self):
        """Flush buffered cells to the terminal using ANSI 24-bit escapes.

        Call this AFTER stdscr.refresh() so curses has already sent its
        buffer; we write on top using direct escape sequences.
        """
        if not self.cells:
            return
        parts = []
        for y, x, text, r, g, b, bold, dim in self.cells:
            pos = f'\033[{y + 1};{x + 1}H'
            color = f'\033[38;2;{r};{g};{b}m'
            attrs = ''
            if bold:
                attrs += '\033[1m'
            if dim:
                attrs += '\033[2m'
            parts.append(f'{pos}{color}{attrs}{text}')
        parts.append('\033[0m')
        sys.stdout.write(''.join(parts))
        sys.stdout.flush()
        self.cells.clear()

    def clear(self):
        """Discard any buffered cells."""
        self.cells.clear()


# ── Convenience drawing functions for modes ───────────────────────────────────

def tc_addstr(stdscr, y, x, text, r, g, b, bold=False, dim=False, tc_buf=None):
    """Write text with 24-bit colour if a TrueColorBuffer is provided, else nearest 256."""
    if tc_buf is not None and tc_buf.enabled:
        tc_buf.put(y, x, text, r, g, b, bold, dim)
    else:
        pair_idx = _nearest_256(r, g, b)
        # Dynamically init a pair in the high range (200+)
        slot = 200 + (hash((r, g, b)) % 55)  # pairs 200–254
        try:
            curses.init_pair(slot, pair_idx, -1)
        except curses.error:
            slot = 6  # fallback to white
        attr = curses.color_pair(slot)
        if bold:
            attr |= curses.A_BOLD
        if dim:
            attr |= curses.A_DIM
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass


def colormap_addstr(stdscr, y, x, text, colormap, fraction,
                    bold=False, dim=False, tc_buf=None):
    """Draw text coloured by a named colormap at the given fraction (0.0–1.0)."""
    r, g, b = colormap_rgb(colormap, fraction)
    tc_addstr(stdscr, y, x, text, r, g, b, bold=bold, dim=dim, tc_buf=tc_buf)


# ── Color pair initialization ─────────────────────────────────────────────────

# Track next available colour index for init_color() redefinitions.
_next_color_id = [16]


def _alloc_color(r, g, b):
    """Allocate a curses colour index with the given RGB (0–255 scale).

    Only useful when curses.can_change_color() is True.
    """
    cid = _next_color_id[0]
    if cid >= curses.COLORS:
        return cid - 1  # reuse last if out of slots
    _next_color_id[0] += 1
    curses.init_color(cid, r * 1000 // 255, g * 1000 // 255, b * 1000 // 255)
    return cid


def _init_gradient_pairs(pair_base, count, colormap_name):
    """Allocate colour indices from a colourmap and bind them to a pair range.

    Used when can_change_color() is True to replace the hard-coded 256-colour
    indices with precise colourmap samples.
    """
    for i in range(count):
        frac = i / max(1, count - 1)
        r, g, b = colormap_rgb(colormap_name, frac)
        cid = _alloc_color(r, g, b)
        curses.init_pair(pair_base + i, cid, -1)


def _init_colors():
    curses.start_color()
    curses.use_default_colors()
    for fg, idx in AGE_COLORS:
        curses.init_pair(idx, fg, -1)
    # Pair 6: dim border / info text
    curses.init_pair(6, curses.COLOR_WHITE, -1)
    # Pair 7: highlight / title
    curses.init_pair(7, curses.COLOR_CYAN, -1)

    # ── Enhanced colour initialization with colourmap gradients ──
    # When the terminal supports redefining colours (can_change_color), we
    # allocate fresh colour indices with precise RGB values sampled from
    # perceptually uniform colormaps.  This automatically upgrades every mode
    # that uses these pair ranges — no per-mode changes needed.
    _can_redefine = False
    try:
        _can_redefine = curses.can_change_color() and curses.COLORS >= 256
    except Exception:
        pass

    if _can_redefine:
        _next_color_id[0] = 16  # reset allocator

        # Age colours: redefine with richer RGB
        _age_rgbs = [
            (30, 200, 60),   # green - newborn
            (40, 200, 200),  # cyan - young
            (220, 200, 40),  # yellow - mature
            (200, 60, 200),  # magenta - old
            (220, 40, 40),   # red - ancient
        ]
        for i, (r, g, b) in enumerate(_age_rgbs):
            cid = _alloc_color(r, g, b)
            curses.init_pair(i + 1, cid, -1)

        # Pair 6: white
        cid_white = _alloc_color(200, 200, 200)
        curses.init_pair(6, cid_white, -1)
        # Pair 7: cyan highlight
        cid_cyan = _alloc_color(80, 220, 230)
        curses.init_pair(7, cid_cyan, -1)

        # Heatmap (pairs 10–17): thermal colormap
        _init_gradient_pairs(10, 8, 'thermal')

        # Fallback heatmap (pairs 18–22): basic colours (still needed for logic)
        curses.init_pair(18, curses.COLOR_BLUE, -1)
        curses.init_pair(19, curses.COLOR_CYAN, -1)
        curses.init_pair(20, curses.COLOR_YELLOW, -1)
        curses.init_pair(21, curses.COLOR_RED, -1)
        curses.init_pair(22, curses.COLOR_WHITE, -1)

        # Pattern search highlights (30–33): keep simple named colours
        curses.init_pair(30, curses.COLOR_CYAN, -1)
        curses.init_pair(31, curses.COLOR_YELLOW, -1)
        curses.init_pair(32, curses.COLOR_MAGENTA, -1)
        curses.init_pair(33, curses.COLOR_WHITE, -1)
        # Blueprint (40)
        curses.init_pair(40, curses.COLOR_GREEN, -1)

        # Multiplayer (pairs 50–58): blue & red gradients
        _mp_blue = [(50, 120, 220), (80, 160, 240), (40, 80, 200), (20, 40, 160)]
        _mp_red = [(220, 50, 50), (240, 120, 80), (180, 30, 30), (140, 20, 20)]
        for i, (r, g, b) in enumerate(_mp_blue):
            cid = _alloc_color(r, g, b)
            curses.init_pair(50 + i, cid, -1)
        for i, (r, g, b) in enumerate(_mp_red):
            cid = _alloc_color(r, g, b)
            curses.init_pair(54 + i, cid, -1)
        curses.init_pair(58, curses.COLOR_YELLOW, -1)

        # Reaction-diffusion (pairs 60–67): ocean colormap
        _init_gradient_pairs(60, 8, 'ocean')

        # Lenia (pairs 70–77): magma colormap
        _init_gradient_pairs(70, 8, 'magma')

        # Physarum (pairs 80–87): amber colormap
        _init_gradient_pairs(80, 8, 'amber')

        # Hydraulic Erosion (pairs 90–99): terrain colormap
        _init_gradient_pairs(90, 10, 'terrain')

        # Voronoi Crystal Growth (pairs 100–115): distinct hues via plasma
        for i in range(16):
            frac = i / 15.0
            # Use plasma but rotate hue to give maximally distinct colours
            r, g, b = colormap_rgb('plasma', (frac * 0.85 + 0.08) % 1.0)
            cid = _alloc_color(r, g, b)
            curses.init_pair(100 + i, cid, -1)

        # Terrain Generation (pairs 120–131): terrain colormap
        _init_gradient_pairs(120, 12, 'terrain')

    elif curses.COLORS >= 256:
        # ── Original 256-colour palette (unchanged) ──
        # Heatmap colour tiers (pairs 10–16): cool to hot
        curses.init_pair(10, 17, -1)
        curses.init_pair(11, 19, -1)
        curses.init_pair(12, 27, -1)
        curses.init_pair(13, 51, -1)
        curses.init_pair(14, 226, -1)
        curses.init_pair(15, 208, -1)
        curses.init_pair(16, 196, -1)
        curses.init_pair(17, 231, -1)
        curses.init_pair(18, curses.COLOR_BLUE, -1)
        curses.init_pair(19, curses.COLOR_CYAN, -1)
        curses.init_pair(20, curses.COLOR_YELLOW, -1)
        curses.init_pair(21, curses.COLOR_RED, -1)
        curses.init_pair(22, curses.COLOR_WHITE, -1)
        curses.init_pair(30, curses.COLOR_CYAN, -1)
        curses.init_pair(31, curses.COLOR_YELLOW, -1)
        curses.init_pair(32, curses.COLOR_MAGENTA, -1)
        curses.init_pair(33, curses.COLOR_WHITE, -1)
        curses.init_pair(40, curses.COLOR_GREEN, -1)
        curses.init_pair(50, 33, -1)
        curses.init_pair(51, 39, -1)
        curses.init_pair(52, 27, -1)
        curses.init_pair(53, 21, -1)
        curses.init_pair(54, 196, -1)
        curses.init_pair(55, 209, -1)
        curses.init_pair(56, 160, -1)
        curses.init_pair(57, 124, -1)
        curses.init_pair(58, curses.COLOR_YELLOW, -1)
        curses.init_pair(60, 17, -1)
        curses.init_pair(61, 19, -1)
        curses.init_pair(62, 27, -1)
        curses.init_pair(63, 45, -1)
        curses.init_pair(64, 51, -1)
        curses.init_pair(65, 48, -1)
        curses.init_pair(66, 226, -1)
        curses.init_pair(67, 231, -1)
        curses.init_pair(70, 22, -1)
        curses.init_pair(71, 28, -1)
        curses.init_pair(72, 34, -1)
        curses.init_pair(73, 148, -1)
        curses.init_pair(74, 214, -1)
        curses.init_pair(75, 208, -1)
        curses.init_pair(76, 196, -1)
        curses.init_pair(77, 231, -1)
        curses.init_pair(80, 22, -1)
        curses.init_pair(81, 58, -1)
        curses.init_pair(82, 100, -1)
        curses.init_pair(83, 142, -1)
        curses.init_pair(84, 178, -1)
        curses.init_pair(85, 214, -1)
        curses.init_pair(86, 220, -1)
        curses.init_pair(87, 231, -1)
        curses.init_pair(90, 17, -1)
        curses.init_pair(91, 22, -1)
        curses.init_pair(92, 28, -1)
        curses.init_pair(93, 34, -1)
        curses.init_pair(94, 142, -1)
        curses.init_pair(95, 178, -1)
        curses.init_pair(96, 130, -1)
        curses.init_pair(97, 231, -1)
        curses.init_pair(98, 33, -1)
        curses.init_pair(99, 21, -1)
        curses.init_pair(100, 196, -1)
        curses.init_pair(101, 46, -1)
        curses.init_pair(102, 33, -1)
        curses.init_pair(103, 226, -1)
        curses.init_pair(104, 201, -1)
        curses.init_pair(105, 51, -1)
        curses.init_pair(106, 208, -1)
        curses.init_pair(107, 141, -1)
        curses.init_pair(108, 118, -1)
        curses.init_pair(109, 197, -1)
        curses.init_pair(110, 87, -1)
        curses.init_pair(111, 220, -1)
        curses.init_pair(112, 69, -1)
        curses.init_pair(113, 168, -1)
        curses.init_pair(114, 35, -1)
        curses.init_pair(115, 240, -1)
        curses.init_pair(120, 17, -1)
        curses.init_pair(121, 27, -1)
        curses.init_pair(122, 33, -1)
        curses.init_pair(123, 229, -1)
        curses.init_pair(124, 34, -1)
        curses.init_pair(125, 28, -1)
        curses.init_pair(126, 22, -1)
        curses.init_pair(127, 142, -1)
        curses.init_pair(128, 130, -1)
        curses.init_pair(129, 245, -1)
        curses.init_pair(130, 231, -1)
        curses.init_pair(131, 40, -1)
    else:
        # ── 8-colour fallback (unchanged) ──
        curses.init_pair(10, curses.COLOR_BLUE, -1)
        curses.init_pair(11, curses.COLOR_BLUE, -1)
        curses.init_pair(12, curses.COLOR_CYAN, -1)
        curses.init_pair(13, curses.COLOR_CYAN, -1)
        curses.init_pair(14, curses.COLOR_YELLOW, -1)
        curses.init_pair(15, curses.COLOR_RED, -1)
        curses.init_pair(16, curses.COLOR_RED, -1)
        curses.init_pair(17, curses.COLOR_WHITE, -1)
        curses.init_pair(18, curses.COLOR_BLUE, -1)
        curses.init_pair(19, curses.COLOR_CYAN, -1)
        curses.init_pair(20, curses.COLOR_YELLOW, -1)
        curses.init_pair(21, curses.COLOR_RED, -1)
        curses.init_pair(22, curses.COLOR_WHITE, -1)
        curses.init_pair(30, curses.COLOR_CYAN, -1)
        curses.init_pair(31, curses.COLOR_YELLOW, -1)
        curses.init_pair(32, curses.COLOR_MAGENTA, -1)
        curses.init_pair(33, curses.COLOR_WHITE, -1)
        curses.init_pair(40, curses.COLOR_GREEN, -1)
        curses.init_pair(50, curses.COLOR_BLUE, -1)
        curses.init_pair(51, curses.COLOR_CYAN, -1)
        curses.init_pair(52, curses.COLOR_BLUE, -1)
        curses.init_pair(53, curses.COLOR_BLUE, -1)
        curses.init_pair(54, curses.COLOR_RED, -1)
        curses.init_pair(55, curses.COLOR_MAGENTA, -1)
        curses.init_pair(56, curses.COLOR_RED, -1)
        curses.init_pair(57, curses.COLOR_RED, -1)
        curses.init_pair(58, curses.COLOR_YELLOW, -1)
        curses.init_pair(60, curses.COLOR_BLUE, -1)
        curses.init_pair(61, curses.COLOR_BLUE, -1)
        curses.init_pair(62, curses.COLOR_CYAN, -1)
        curses.init_pair(63, curses.COLOR_CYAN, -1)
        curses.init_pair(64, curses.COLOR_GREEN, -1)
        curses.init_pair(65, curses.COLOR_YELLOW, -1)
        curses.init_pair(66, curses.COLOR_MAGENTA, -1)
        curses.init_pair(67, curses.COLOR_WHITE, -1)
        curses.init_pair(70, curses.COLOR_GREEN, -1)
        curses.init_pair(71, curses.COLOR_GREEN, -1)
        curses.init_pair(72, curses.COLOR_YELLOW, -1)
        curses.init_pair(73, curses.COLOR_YELLOW, -1)
        curses.init_pair(74, curses.COLOR_RED, -1)
        curses.init_pair(75, curses.COLOR_RED, -1)
        curses.init_pair(76, curses.COLOR_MAGENTA, -1)
        curses.init_pair(77, curses.COLOR_WHITE, -1)
        curses.init_pair(80, curses.COLOR_GREEN, -1)
        curses.init_pair(81, curses.COLOR_GREEN, -1)
        curses.init_pair(82, curses.COLOR_YELLOW, -1)
        curses.init_pair(83, curses.COLOR_YELLOW, -1)
        curses.init_pair(84, curses.COLOR_YELLOW, -1)
        curses.init_pair(85, curses.COLOR_RED, -1)
        curses.init_pair(86, curses.COLOR_MAGENTA, -1)
        curses.init_pair(87, curses.COLOR_WHITE, -1)
        curses.init_pair(90, curses.COLOR_BLUE, -1)
        curses.init_pair(91, curses.COLOR_GREEN, -1)
        curses.init_pair(92, curses.COLOR_GREEN, -1)
        curses.init_pair(93, curses.COLOR_GREEN, -1)
        curses.init_pair(94, curses.COLOR_YELLOW, -1)
        curses.init_pair(95, curses.COLOR_YELLOW, -1)
        curses.init_pair(96, curses.COLOR_RED, -1)
        curses.init_pair(97, curses.COLOR_WHITE, -1)
        curses.init_pair(98, curses.COLOR_CYAN, -1)
        curses.init_pair(99, curses.COLOR_BLUE, -1)
        curses.init_pair(100, curses.COLOR_RED, -1)
        curses.init_pair(101, curses.COLOR_GREEN, -1)
        curses.init_pair(102, curses.COLOR_BLUE, -1)
        curses.init_pair(103, curses.COLOR_YELLOW, -1)
        curses.init_pair(104, curses.COLOR_MAGENTA, -1)
        curses.init_pair(105, curses.COLOR_CYAN, -1)
        curses.init_pair(106, curses.COLOR_RED, -1)
        curses.init_pair(107, curses.COLOR_MAGENTA, -1)
        curses.init_pair(108, curses.COLOR_GREEN, -1)
        curses.init_pair(109, curses.COLOR_RED, -1)
        curses.init_pair(110, curses.COLOR_CYAN, -1)
        curses.init_pair(111, curses.COLOR_YELLOW, -1)
        curses.init_pair(112, curses.COLOR_BLUE, -1)
        curses.init_pair(113, curses.COLOR_RED, -1)
        curses.init_pair(114, curses.COLOR_GREEN, -1)
        curses.init_pair(115, curses.COLOR_WHITE, -1)
        curses.init_pair(120, curses.COLOR_BLUE, -1)
        curses.init_pair(121, curses.COLOR_BLUE, -1)
        curses.init_pair(122, curses.COLOR_CYAN, -1)
        curses.init_pair(123, curses.COLOR_YELLOW, -1)
        curses.init_pair(124, curses.COLOR_GREEN, -1)
        curses.init_pair(125, curses.COLOR_GREEN, -1)
        curses.init_pair(126, curses.COLOR_GREEN, -1)
        curses.init_pair(127, curses.COLOR_YELLOW, -1)
        curses.init_pair(128, curses.COLOR_RED, -1)
        curses.init_pair(129, curses.COLOR_WHITE, -1)
        curses.init_pair(130, curses.COLOR_WHITE, -1)
        curses.init_pair(131, curses.COLOR_GREEN, -1)


def color_for_age(age: int) -> int:
    """Return a curses colour pair attribute based on cell age."""
    if age <= 1:
        return curses.color_pair(1)
    if age <= 3:
        return curses.color_pair(2)
    if age <= 8:
        return curses.color_pair(3)
    if age <= 20:
        return curses.color_pair(4)
    return curses.color_pair(5)


# Multiplayer player colour pairs: P1 → 50-53, P2 → 54-57, neutral → 58
_MP_P1_PAIRS = [50, 51, 52, 53]  # newborn → old
_MP_P2_PAIRS = [54, 55, 56, 57]



def color_for_mp(age: int, owner: int) -> int:
    """Return a curses colour pair for a multiplayer cell based on owner (1 or 2) and age."""
    if owner == 1:
        pairs = _MP_P1_PAIRS
    elif owner == 2:
        pairs = _MP_P2_PAIRS
    else:
        return curses.color_pair(58)
    if age <= 1:
        return curses.color_pair(pairs[0])
    if age <= 5:
        return curses.color_pair(pairs[1])
    if age <= 15:
        return curses.color_pair(pairs[2])
    return curses.color_pair(pairs[3])


# Heatmap 256-color tiers (pair indices 10–17) and 8-color fallback (18–22)
HEAT_PAIRS_256 = [10, 11, 12, 13, 14, 15, 16, 17]
HEAT_PAIRS_8 = [18, 18, 19, 19, 20, 20, 21, 22]



def color_for_heat(fraction: float) -> int:
    """Return a curses colour pair attribute for a heatmap fraction 0.0–1.0.
    0 = coolest (dim blue), 1 = hottest (white)."""
    if curses.COLORS >= 256:
        pairs = HEAT_PAIRS_256
    else:
        pairs = HEAT_PAIRS_8
    idx = min(int(fraction * len(pairs)), len(pairs) - 1)
    return curses.color_pair(pairs[idx])


# ── GIF encoder (pure Python, no external dependencies) ─────────────────────

# Color palette for GIF: index 0 = background, 1–5 = age tiers
_GIF_PALETTE = [
    (18, 18, 24),     # 0: background (dark)
    (0, 200, 0),      # 1: newborn (green)
    (0, 200, 200),    # 2: young (cyan)
    (200, 200, 0),    # 3: mature (yellow)
    (200, 0, 200),    # 4: old (magenta)
    (200, 0, 0),      # 5: ancient (red)
    (100, 100, 100),  # 6: grid lines (subtle)
    (255, 255, 255),  # 7: spare (white)
]


def _gif_age_index(age: int) -> int:
    """Map cell age to palette index (mirrors color_for_age tiers)."""
    if age <= 0:
        return 0
    if age <= 1:
        return 1
    if age <= 3:
        return 2
    if age <= 8:
        return 3
    if age <= 20:
        return 4
    return 5
