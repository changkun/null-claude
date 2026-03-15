"""Mode: hyperbolic_ca — Game of Life on the Poincaré disk.

Runs cellular automata on hyperbolic tilings ({5,4}, {7,3}, {4,5}, etc.)
rendered as a Poincaré disk model in the terminal. Cells tile with
exponentially growing neighborhoods, producing emergent behavior impossible
on flat grids.
"""
import curses
import math
import random
import time

# ── Hyperbolic geometry helpers ────────────────────────────────────

# Möbius transformation: translate point z by a in the Poincaré disk
def _mob_translate(z, a):
    """Apply Möbius translation by a to complex point z in the disk."""
    num = z + a
    den = 1.0 + _conj(a) * z
    if abs(den) < 1e-15:
        return complex(0, 0)
    return num / den


def _conj(z):
    return complex(z.real, -z.imag)


def _hyp_dist(z1, z2):
    """Hyperbolic distance between two points in the Poincaré disk."""
    diff = z1 - z2
    denom = 1.0 - _conj(z1) * z2
    if abs(denom) < 1e-15:
        return 0.0
    ratio = abs(diff / denom)
    if ratio >= 1.0:
        return 20.0  # cap
    return math.acosh(1.0 + 2.0 * ratio * ratio / ((1.0 - ratio * ratio) + 1e-15))


# ── Tiling generation ─────────────────────────────────────────────

# Presets: (name, description, p, q) where {p,q} = Schläfli symbol
# p = polygon sides, q = polygons meeting at each vertex
HYPERBOLIC_TILINGS = [
    ("Pentagonal {5,4}", "Order-4 pentagonal — 4 pentagons per vertex", 5, 4),
    ("Heptagonal {7,3}", "Order-3 heptagonal — 3 heptagons per vertex", 7, 3),
    ("Square {4,5}", "Order-5 square — 5 squares per vertex", 4, 5),
    ("Triangular {3,7}", "Order-7 triangular — 7 triangles per vertex", 3, 7),
    ("Hexagonal {6,4}", "Order-4 hexagonal — 4 hexagons per vertex", 6, 4),
    ("Octagonal {8,3}", "Order-3 octagonal — 3 octagons per vertex", 8, 3),
]

HYPERBOLIC_RULES = [
    ("B3/S23 (Life)", "Classic Life — sparse in hyperbolic space", {3}, {2, 3}),
    ("B2/S34 (Pulse)", "Pulsing growth adapted to high-neighbor tilings", {2}, {3, 4}),
    ("B3/S234 (Coral)", "Slow coral growth — stable structures", {3}, {2, 3, 4}),
    ("B35/S2345 (Bloom)", "Lush expansion — fills the disk", {3, 5}, {2, 3, 4, 5}),
    ("B2/S23 (Spread)", "Fast-spreading with classic survival", {2}, {2, 3}),
    ("B3/S345 (Hardy)", "Tough survivors — high-neighbor adapted", {3}, {3, 4, 5}),
    ("B23/S34 (Wave)", "Wave-like expansion and contraction", {2, 3}, {3, 4}),
    ("B2/S (Seeds)", "Explosive chaotic growth, no survival", {2}, set()),
]


def _build_tiling(p, q, max_layers):
    """Build a {p,q} hyperbolic tiling as a graph.

    Uses proximity-based deduplication to handle floating-point imprecision
    when the same cell is reached from different parents.

    Returns:
        cells: list of complex positions (center of each polygon)
        adjacency: dict mapping cell_index -> list of neighbor indices
    """
    # Center-to-center hyperbolic distance for adjacent polygons
    # cosh(d_midpoint) = cos(pi/q) / sin(pi/p)
    # center-to-center = 2 * d_midpoint
    cos_pi_q = math.cos(math.pi / q)
    sin_pi_p = math.sin(math.pi / p)
    cosh_dm = cos_pi_q / sin_pi_p
    if cosh_dm <= 1.0:
        cosh_dm = 1.001
    d_mid = math.acosh(cosh_dm)
    # Poincaré disk Euclidean radius for center-to-center distance
    r_center = math.tanh(d_mid)

    # Merge tolerance scales with how close cells get near the boundary
    merge_tol = r_center * 0.15

    cells = [complex(0, 0)]
    adjacency = {0: []}

    # Spatial grid for fast proximity lookup
    grid_size = merge_tol * 2
    spatial = {}  # grid_key -> list of cell indices

    def _grid_key(z):
        return (int(math.floor(z.real / grid_size)),
                int(math.floor(z.imag / grid_size)))

    def _find_near(z):
        """Find existing cell near z, or return -1."""
        gk = _grid_key(z)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (gk[0] + dx, gk[1] + dy)
                for ci in spatial.get(key, []):
                    if abs(cells[ci] - z) < merge_tol:
                        return ci
        return -1

    def _add_cell(z):
        idx = len(cells)
        cells.append(z)
        adjacency[idx] = []
        gk = _grid_key(z)
        spatial.setdefault(gk, []).append(idx)
        return idx

    # Register cell 0
    spatial.setdefault(_grid_key(complex(0, 0)), []).append(0)

    def _find_or_add(z):
        if abs(z) > 0.96:
            return -1
        existing = _find_near(z)
        if existing >= 0:
            return existing
        return _add_cell(z)

    # BFS expansion
    frontier = [0]
    visited_for_expand = {0}

    for _layer in range(max_layers):
        next_frontier = []
        for ci in frontier:
            center = cells[ci]
            for k in range(p):
                angle = 2.0 * math.pi * k / p
                direction = complex(math.cos(angle), math.sin(angle))
                local_nb = direction * r_center
                nb_pos = _mob_translate(local_nb, center)

                if abs(nb_pos) > 0.96:
                    continue

                ni = _find_or_add(nb_pos)
                if ni < 0:
                    continue

                if ni not in adjacency[ci]:
                    adjacency[ci].append(ni)
                if ci not in adjacency[ni]:
                    adjacency[ni].append(ci)

                if ni not in visited_for_expand:
                    visited_for_expand.add(ni)
                    next_frontier.append(ni)

        frontier = next_frontier
        if not frontier:
            break

    return cells, adjacency


# ── ASCII Poincaré disk rendering ──────────────────────────────────

# Characters for cell states by age
_ALIVE_CHARS = "●◉◎⊙○"
_ALIVE_ASCII = "@#O*o."
_DEAD_CHAR = " "
_DISK_BORDER = "·"


def _disk_render(cells, states, ages, cx, cy, radius, max_age):
    """Render cells onto a character grid as a Poincaré disk.

    Returns dict mapping (screen_row, screen_col) -> (char, color_idx)
    where color_idx 0=dead, 1-6=alive by age
    """
    output = {}
    r2 = radius * radius

    # Draw disk boundary
    for angle_step in range(int(radius * 8)):
        a = 2.0 * math.pi * angle_step / (radius * 8)
        bx = cx + radius * math.cos(a)
        by = cy + radius * 0.5 * math.sin(a)  # Squash for terminal aspect ratio
        sr, sc = int(round(by)), int(round(bx))
        if (sr, sc) not in output:
            output[(sr, sc)] = (_DISK_BORDER, 0)

    # Draw each cell
    for i, pos in enumerate(cells):
        if abs(pos) > 0.96:
            continue
        # Map from Poincaré disk [-1,1]x[-1,1] to screen
        sx = cx + pos.real * radius
        sy = cy + pos.imag * radius * 0.5  # terminal aspect ratio correction
        sr, sc = int(round(sy)), int(round(sx))

        alive = states[i]
        age = ages[i]

        if alive:
            # Size/brightness decreases toward edge (conformal shrinking)
            dist = abs(pos)
            if dist < 0.3:
                ch = "@"
            elif dist < 0.6:
                ch = "#"
            elif dist < 0.8:
                ch = "*"
            else:
                ch = "."
            color_idx = min(age, max_age) if max_age > 0 else 1
            output[(sr, sc)] = (ch, color_idx)
        else:
            # Only show dead cells near center for visual clarity
            dist = abs(pos)
            if dist < 0.7 and (sr, sc) not in output:
                output[(sr, sc)] = ("·", 0)

    return output


# ── Mode functions ────────────────────────────────────────────────

def _enter_hyp_mode(self):
    """Enter Hyperbolic CA mode — show tiling selection menu."""
    self.hyp_menu = True
    self.hyp_menu_phase = "tiling"
    self.hyp_menu_sel = 0
    self.hyp_rule_sel = 0
    self._flash("Hyperbolic Cellular Automata — select a tiling")


def _exit_hyp_mode(self):
    """Exit Hyperbolic CA mode."""
    self.hyp_mode = False
    self.hyp_menu = False
    self.hyp_running = False
    self.hyp_cells = []
    self.hyp_adj = {}
    self.hyp_states = []
    self.hyp_ages = []
    self._flash("Hyperbolic CA OFF")


def _hyp_init(self, tiling_idx, rule_idx):
    """Initialize the hyperbolic tiling and seed cells."""
    name, _desc, p, q = HYPERBOLIC_TILINGS[tiling_idx]
    rname, _rdesc, birth, survive = HYPERBOLIC_RULES[rule_idx]

    self.hyp_tiling_name = name
    self.hyp_rule_name = rname
    self.hyp_p = p
    self.hyp_q = q
    self.hyp_birth = birth
    self.hyp_survive = survive
    self.hyp_generation = 0
    self.hyp_population = 0

    # Build tiling graph
    max_layers = 6
    self.hyp_cells, self.hyp_adj = _build_tiling(p, q, max_layers)
    n = len(self.hyp_cells)
    self.hyp_states = [False] * n
    self.hyp_ages = [0] * n

    # Seed: randomly activate ~25% of central cells
    seed_count = 0
    for i in range(n):
        dist = abs(self.hyp_cells[i])
        if dist < 0.5 and random.random() < 0.3:
            self.hyp_states[i] = True
            self.hyp_ages[i] = 1
            seed_count += 1

    self.hyp_population = seed_count
    self.hyp_running = True
    self.hyp_menu = False
    self.hyp_mode = True
    self.hyp_view_cx = 0.0
    self.hyp_view_cy = 0.0
    self.hyp_speed_mult = 1
    self._flash(f"Hyperbolic CA: {name} / {rname} — {n} cells, space=pause, q=quit")


def _hyp_step(self):
    """Advance one generation of the hyperbolic CA."""
    n = len(self.hyp_cells)
    new_states = [False] * n
    new_ages = [0] * n
    pop = 0

    for i in range(n):
        # Count live neighbors
        live_nb = 0
        for ni in self.hyp_adj.get(i, []):
            if self.hyp_states[ni]:
                live_nb += 1

        if self.hyp_states[i]:
            # Currently alive — check survival
            if live_nb in self.hyp_survive:
                new_states[i] = True
                new_ages[i] = self.hyp_ages[i] + 1
                pop += 1
            # else dies
        else:
            # Currently dead — check birth
            if live_nb in self.hyp_birth:
                new_states[i] = True
                new_ages[i] = 1
                pop += 1

    self.hyp_states = new_states
    self.hyp_ages = new_ages
    self.hyp_generation += 1
    self.hyp_population = pop


def _hyp_randomize(self, density=0.3):
    """Randomize cells within the central region."""
    n = len(self.hyp_cells)
    pop = 0
    for i in range(n):
        dist = abs(self.hyp_cells[i])
        if dist < 0.6 and random.random() < density:
            self.hyp_states[i] = True
            self.hyp_ages[i] = 1
            pop += 1
        else:
            self.hyp_states[i] = False
            self.hyp_ages[i] = 0
    self.hyp_population = pop
    self.hyp_generation = 0


def _hyp_clear(self):
    """Clear all cells."""
    n = len(self.hyp_cells)
    self.hyp_states = [False] * n
    self.hyp_ages = [0] * n
    self.hyp_population = 0
    self.hyp_generation = 0


# ── Key handling ──────────────────────────────────────────────────

def _handle_hyp_menu_key(self, key):
    """Handle keys in the tiling/rule selection menu."""
    if key == 27:  # ESC
        self.hyp_menu = False
        return True

    if self.hyp_menu_phase == "tiling":
        n_items = len(HYPERBOLIC_TILINGS)
        if key == curses.KEY_UP:
            self.hyp_menu_sel = (self.hyp_menu_sel - 1) % n_items
        elif key == curses.KEY_DOWN:
            self.hyp_menu_sel = (self.hyp_menu_sel + 1) % n_items
        elif key in (10, 13, curses.KEY_ENTER):
            self.hyp_menu_phase = "rule"
            self.hyp_rule_sel = 0
        elif key == ord("q"):
            self.hyp_menu = False
        return True
    elif self.hyp_menu_phase == "rule":
        n_items = len(HYPERBOLIC_RULES)
        if key == curses.KEY_UP:
            self.hyp_rule_sel = (self.hyp_rule_sel - 1) % n_items
        elif key == curses.KEY_DOWN:
            self.hyp_rule_sel = (self.hyp_rule_sel + 1) % n_items
        elif key in (10, 13, curses.KEY_ENTER):
            self._hyp_init(self.hyp_menu_sel, self.hyp_rule_sel)
        elif key == ord("q") or key == 27:
            self.hyp_menu_phase = "tiling"
        return True

    return True


def _handle_hyp_key(self, key):
    """Handle keys during hyperbolic CA simulation."""
    if key == ord("q") or key == 27:
        self._exit_hyp_mode()
        return True
    if key == ord(" "):
        self.hyp_running = not self.hyp_running
        return True
    if key == ord("r"):
        self._hyp_randomize()
        return True
    if key == ord("c"):
        self._hyp_clear()
        return True
    if key == ord("s"):
        # Single step
        self._hyp_step()
        return True
    if key == ord("n"):
        # Cycle to next rule
        idx = 0
        for i, (rn, _, _, _) in enumerate(HYPERBOLIC_RULES):
            if rn == self.hyp_rule_name:
                idx = i
                break
        idx = (idx + 1) % len(HYPERBOLIC_RULES)
        rname, _, birth, survive = HYPERBOLIC_RULES[idx]
        self.hyp_birth = birth
        self.hyp_survive = survive
        self.hyp_rule_name = rname
        self._flash(f"Rule: {rname}")
        return True
    if key == ord("t"):
        # Cycle to next tiling (rebuild)
        idx = 0
        for i, (tn, _, tp, tq) in enumerate(HYPERBOLIC_TILINGS):
            if tn == self.hyp_tiling_name:
                idx = i
                break
        idx = (idx + 1) % len(HYPERBOLIC_TILINGS)
        # Find current rule index
        rule_idx = 0
        for i, (rn, _, _, _) in enumerate(HYPERBOLIC_RULES):
            if rn == self.hyp_rule_name:
                rule_idx = i
                break
        self._hyp_init(idx, rule_idx)
        return True
    if key in (ord("+"), ord("=")):
        self.hyp_speed_mult = min(self.hyp_speed_mult + 1, 10)
        return True
    if key in (ord("-"), ord("_")):
        self.hyp_speed_mult = max(self.hyp_speed_mult - 1, 1)
        return True

    return True


# ── Drawing ───────────────────────────────────────────────────────

def _draw_hyp_menu(self, max_y, max_x):
    """Draw the tiling/rule selection menu."""
    self.stdscr.erase()
    title = "╔══════════════════════════════════════════╗"
    mid =   "║     HYPERBOLIC CELLULAR AUTOMATA         ║"
    sub =   "║     Game of Life on the Poincaré Disk    ║"
    bot =   "╚══════════════════════════════════════════╝"

    cy = max_y // 2
    cx = max_x // 2

    # Title box
    for i, line in enumerate([title, mid, sub, bot]):
        r = cy - 10 + i
        c = cx - len(line) // 2
        if 0 <= r < max_y:
            try:
                self.stdscr.addstr(r, max(0, c), line[:max_x - 1],
                                   curses.A_BOLD | curses.color_pair(4))
            except curses.error:
                pass

    if self.hyp_menu_phase == "tiling":
        hdr = "Select Tiling (↑/↓, Enter):"
        r = cy - 5
        try:
            self.stdscr.addstr(r, cx - len(hdr) // 2, hdr,
                               curses.A_BOLD | curses.color_pair(3))
        except curses.error:
            pass

        for i, (name, desc, p, q) in enumerate(HYPERBOLIC_TILINGS):
            r = cy - 3 + i * 2
            if r >= max_y - 1:
                break
            sel = "▸ " if i == self.hyp_menu_sel else "  "
            attr = curses.A_BOLD | curses.color_pair(2) if i == self.hyp_menu_sel else curses.A_DIM
            line = f"{sel}{name}"
            try:
                self.stdscr.addstr(r, cx - 20, line[:max_x - 1], attr)
                self.stdscr.addstr(r + 1, cx - 18, desc[:max_x - 1],
                                   curses.A_DIM | curses.color_pair(6))
            except curses.error:
                pass

        # Draw small tiling preview
        _draw_mini_tiling(self.stdscr, cx + 16, cy - 2,
                          HYPERBOLIC_TILINGS[self.hyp_menu_sel][2],
                          HYPERBOLIC_TILINGS[self.hyp_menu_sel][3],
                          max_y, max_x)

    elif self.hyp_menu_phase == "rule":
        hdr = "Select Rule (↑/↓, Enter):"
        r = cy - 5
        try:
            self.stdscr.addstr(r, cx - len(hdr) // 2, hdr,
                               curses.A_BOLD | curses.color_pair(3))
        except curses.error:
            pass

        for i, (name, desc, _, _) in enumerate(HYPERBOLIC_RULES):
            r = cy - 3 + i * 2
            if r >= max_y - 1:
                break
            sel = "▸ " if i == self.hyp_rule_sel else "  "
            attr = curses.A_BOLD | curses.color_pair(2) if i == self.hyp_rule_sel else curses.A_DIM
            line = f"{sel}{name}"
            try:
                self.stdscr.addstr(r, cx - 20, line[:max_x - 1], attr)
                self.stdscr.addstr(r + 1, cx - 18, desc[:max_x - 1],
                                   curses.A_DIM | curses.color_pair(6))
            except curses.error:
                pass

    # Footer
    foot = "[ESC] back  [q] cancel"
    try:
        self.stdscr.addstr(max_y - 1, cx - len(foot) // 2, foot[:max_x - 1],
                           curses.A_DIM)
    except curses.error:
        pass


def _draw_mini_tiling(scr, cx, cy, p, q, max_y, max_x):
    """Draw a tiny Poincaré disk preview of the {p,q} tiling."""
    radius = 8
    # Draw disk circle
    for step in range(64):
        a = 2.0 * math.pi * step / 64
        px = cx + int(round(radius * math.cos(a)))
        py = cy + int(round(radius * 0.5 * math.sin(a)))
        if 0 <= py < max_y and 0 <= px < max_x - 1:
            try:
                scr.addstr(py, px, "·", curses.A_DIM)
            except curses.error:
                pass

    # Draw a few polygon outlines
    cos_pq = math.cos(math.pi / q)
    sin_pp = math.sin(math.pi / p)
    cosh_h = cos_pq / sin_pp if sin_pp > 0 else 1.5
    if cosh_h <= 1.0:
        cosh_h = 1.5
    r_nb = math.tanh(math.acosh(cosh_h))

    # Draw center polygon
    for k in range(p):
        a1 = 2.0 * math.pi * k / p
        a2 = 2.0 * math.pi * ((k + 1) % p) / p
        for t in range(8):
            frac = t / 8.0
            a = a1 + frac * (a2 - a1)
            # Vertex radius
            cos_pp = math.cos(math.pi / p)
            r_v = r_nb * 0.6
            px = cx + int(round(r_v * radius * math.cos(a)))
            py = cy + int(round(r_v * radius * 0.5 * math.sin(a)))
            if 0 <= py < max_y and 0 <= px < max_x - 1:
                try:
                    scr.addstr(py, px, "*", curses.A_BOLD | curses.color_pair(3))
                except curses.error:
                    pass


def _draw_hyp(self, max_y, max_x):
    """Draw the Poincaré disk with live hyperbolic CA state."""
    self.stdscr.erase()

    # Calculate disk dimensions
    disk_radius = min(max_x // 2 - 2, (max_y - 3) - 1)
    if disk_radius < 5:
        disk_radius = 5
    cx = max_x // 2
    cy = (max_y - 2) // 2

    # Render cells to screen
    max_age = 8
    render_map = _disk_render(
        self.hyp_cells, self.hyp_states, self.hyp_ages,
        cx, cy, disk_radius, max_age
    )

    for (sr, sc), (ch, color_idx) in render_map.items():
        if 0 <= sr < max_y - 2 and 0 <= sc < max_x - 1:
            if color_idx > 0:
                # Alive — color by age
                age_clamped = min(color_idx, 6)
                attr = curses.A_BOLD | curses.color_pair(age_clamped)
            else:
                attr = curses.A_DIM
            try:
                self.stdscr.addstr(sr, sc, ch, attr)
            except curses.error:
                pass

    # Status bar
    status_parts = [
        f" {self.hyp_tiling_name}",
        f"Rule: {self.hyp_rule_name}",
        f"Gen: {self.hyp_generation}",
        f"Pop: {self.hyp_population}/{len(self.hyp_cells)}",
        "PAUSED" if not self.hyp_running else "RUNNING",
    ]
    status = "  │  ".join(status_parts)
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1],
                           curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass

    # Help bar
    help_text = " [space]pause [r]andomize [c]lear [s]tep [n]ext rule [t]iling [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 0, help_text[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass


# ── Registration ──────────────────────────────────────────────────

def register(App):
    """Register Hyperbolic CA mode methods on the App class."""
    App._enter_hyp_mode = _enter_hyp_mode
    App._exit_hyp_mode = _exit_hyp_mode
    App._hyp_init = _hyp_init
    App._hyp_step = _hyp_step
    App._hyp_randomize = _hyp_randomize
    App._hyp_clear = _hyp_clear
    App._handle_hyp_menu_key = _handle_hyp_menu_key
    App._handle_hyp_key = _handle_hyp_key
    App._draw_hyp_menu = _draw_hyp_menu
    App._draw_hyp = _draw_hyp
