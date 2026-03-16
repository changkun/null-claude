"""Mode: qgol — Quantum Game of Life.

Each cell holds a complex amplitude (|1⟩/|0⟩ superposition).  The classical
Game-of-Life birth/survival rules are lifted to a unitary operator that
creates superpositions.  Neighbouring cells become entangled through the
rule application.  Clicking a cell measures it, collapsing it probabilistically
and propagating decoherence to entangled neighbours.

Visualization:
  - Brightness / density char ↔ probability of being alive (|1⟩ amplitude²)
  - Hue ↔ phase of the alive-amplitude
  - Entanglement links shown as dim lines between strongly correlated cells
"""
import curses
import math
import random
import time

# ── Presets ──────────────────────────────────────────────────────────────────

QGOL_PRESETS = [
    ("Quantum Glider",
     "Superposition of glider at two translated positions — interference fringes as it moves",
     "glider"),
    ("Schrödinger's Blinker",
     "Period-2 oscillator in superposition of both phases simultaneously",
     "blinker"),
    ("Entangled Gosper Gun",
     "Gosper glider gun with entangled birth events producing correlated streams",
     "gosper"),
    ("Quantum Soup",
     "Random superposition across the grid — watch decoherence crystallize classical structures",
     "soup"),
    ("Bell State Pair",
     "Two maximally-entangled cells — measuring one instantly collapses the other",
     "bell"),
    ("Quantum Garden of Eden",
     "Uniform low-amplitude superposition — a state with no classical predecessor",
     "eden"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────

_DENSITY = ["  ", "· ", "··", "░░", "▒▒", "▓▓", "██"]


def _phase_color(phase: float) -> int:
    """Map phase angle (-pi..pi) to curses color pair index."""
    p = (phase + math.pi) / (2.0 * math.pi)  # 0..1
    if p < 0.167:
        return 1   # red
    elif p < 0.333:
        return 3   # yellow
    elif p < 0.5:
        return 2   # green
    elif p < 0.667:
        return 6   # cyan/white
    elif p < 0.833:
        return 4   # blue
    else:
        return 5   # magenta


def _neighbors(r, c, rows, cols):
    """Yield the 8 Moore-neighbourhood coordinates (toroidal wrap)."""
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            yield (r + dr) % rows, (c + dc) % cols


# ── Enter / Exit ─────────────────────────────────────────────────────────────

def _enter_qgol_mode(self):
    """Enter Quantum Game of Life — show preset menu."""
    self.qgol_menu = True
    self.qgol_menu_sel = 0
    self._flash("Quantum Game of Life — select a configuration")


def _exit_qgol_mode(self):
    """Exit Quantum Game of Life mode."""
    self.qgol_mode = False
    self.qgol_menu = False
    self.qgol_running = False
    self._flash("Quantum Game of Life OFF")


# ── Initialisation ───────────────────────────────────────────────────────────

def _qgol_init(self, preset_idx: int):
    """Set up the quantum state for the chosen preset."""
    name, _desc, kind = QGOL_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(20, max_y - 4)
    cols = max(20, (max_x - 1) // 2)
    self.qgol_rows = rows
    self.qgol_cols = cols
    self.qgol_preset_name = name
    self.qgol_generation = 0
    self.qgol_decoherence = 0.02
    self.qgol_view = "probability"   # probability | phase | entanglement
    self.qgol_steps_per_frame = 1

    # Per-cell alive-amplitude: complex number (re, im).
    # Probability of alive = re² + im².  Dead amplitude = sqrt(1 - p).
    amp_re = [[0.0] * cols for _ in range(rows)]
    amp_im = [[0.0] * cols for _ in range(rows)]

    # Entanglement strength matrix (sparse-ish): dict (r1,c1,r2,c2) -> float
    self.qgol_entanglement = {}

    if kind == "glider":
        _place_glider_superposition(amp_re, amp_im, rows, cols)
    elif kind == "blinker":
        _place_blinker_superposition(amp_re, amp_im, rows, cols)
    elif kind == "gosper":
        _place_gosper_superposition(amp_re, amp_im, rows, cols)
    elif kind == "soup":
        _place_quantum_soup(amp_re, amp_im, rows, cols)
    elif kind == "bell":
        _place_bell_state(amp_re, amp_im, rows, cols, self.qgol_entanglement)
    elif kind == "eden":
        _place_eden(amp_re, amp_im, rows, cols)

    self.qgol_amp_re = amp_re
    self.qgol_amp_im = amp_im
    self.qgol_mode = True
    self.qgol_menu = False
    self.qgol_running = False
    self._flash(f"Quantum GoL: {name} — Space to start, click to measure")


# ── Preset placement helpers ─────────────────────────────────────────────────

def _place_glider_superposition(re, im, rows, cols):
    """Superposition of a glider at two translated positions."""
    cr, cc = rows // 2, cols // 2
    # Glider pattern (relative)
    glider = [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    amp = 1.0 / math.sqrt(2.0)
    offset = 4
    for dr, dc in glider:
        r1, c1 = (cr + dr - offset) % rows, (cc + dc - offset) % cols
        re[r1][c1] += amp
        r2, c2 = (cr + dr + offset) % rows, (cc + dc + offset) % cols
        # Second copy with phase shift for interference
        re[r2][c2] += amp * math.cos(math.pi / 3)
        im[r2][c2] += amp * math.sin(math.pi / 3)


def _place_blinker_superposition(re, im, rows, cols):
    """Blinker in superposition of horizontal and vertical phases."""
    cr, cc = rows // 2, cols // 2
    amp = 1.0 / math.sqrt(2.0)
    # Horizontal phase
    for dc in (-1, 0, 1):
        re[cr][(cc + dc) % cols] += amp
    # Vertical phase (with pi/2 phase shift)
    for dr in (-1, 0, 1):
        r = (cr + dr) % rows
        # Center cell already has amplitude, add vertical parts
        if dr != 0:
            im[r][cc] += amp
        else:
            # Center is already set; add imaginary component
            im[r][cc] += amp


def _place_gosper_superposition(re, im, rows, cols):
    """Gosper glider gun with quantum-uncertain birth sites."""
    cr, cc = rows // 2, cols // 4
    # Classic Gosper gun cells (relative to top-left of bounding box)
    gun = [
        (4, 0), (4, 1), (5, 0), (5, 1),
        (4, 10), (5, 10), (6, 10), (3, 11), (7, 11), (2, 12), (8, 12),
        (2, 13), (8, 13), (5, 14), (3, 15), (7, 15), (4, 16), (5, 16),
        (6, 16), (5, 17),
        (2, 20), (3, 20), (4, 20), (2, 21), (3, 21), (4, 21),
        (1, 22), (5, 22), (0, 24), (1, 24), (5, 24), (6, 24),
        (2, 34), (3, 34), (2, 35), (3, 35),
    ]
    for dr, dc in gun:
        r = (cr + dr) % rows
        c = (cc + dc) % cols
        # Strong alive amplitude with slight phase variation
        phase = 0.1 * (dr + dc)
        re[r][c] = 0.92 * math.cos(phase)
        im[r][c] = 0.92 * math.sin(phase)


def _place_quantum_soup(re, im, rows, cols):
    """Random superposition — each cell gets random amplitude and phase."""
    for r in range(rows):
        for c in range(cols):
            if random.random() < 0.3:
                p = random.random() * 0.8
                phase = random.random() * 2.0 * math.pi
                amp = math.sqrt(p)
                re[r][c] = amp * math.cos(phase)
                im[r][c] = amp * math.sin(phase)


def _place_bell_state(re, im, rows, cols, entanglement):
    """Two maximally-entangled cells."""
    cr, cc = rows // 2, cols // 2
    amp = 1.0 / math.sqrt(2.0)
    c1 = (cc - 5) % cols
    c2 = (cc + 5) % cols
    re[cr][c1] = amp
    re[cr][c2] = amp
    # Mark as maximally entangled
    key = (cr, c1, cr, c2) if (cr, c1) < (cr, c2) else (cr, c2, cr, c1)
    entanglement[key] = 1.0


def _place_eden(re, im, rows, cols):
    """Uniform low-amplitude superposition across the grid."""
    amp = 0.15
    for r in range(rows):
        for c in range(cols):
            phase = (r * 0.3 + c * 0.5) % (2.0 * math.pi)
            re[r][c] = amp * math.cos(phase)
            im[r][c] = amp * math.sin(phase)


# ── Quantum step ─────────────────────────────────────────────────────────────

def _qgol_step(self):
    """One step of the Quantum Game of Life.

    The classical GoL rule (B3/S23) is lifted to a unitary-like operator:
    - Count the *expected* alive neighbours (sum of probabilities).
    - Apply a smooth unitary rotation from |0⟩→|1⟩ (birth) or |1⟩→|0⟩ (death)
      based on how close the neighbour count is to the birth/survival window.
    - Entanglement is generated between cells that participate in each other's
      birth/survival decisions.
    - Environmental decoherence randomly collapses amplitudes.
    """
    rows, cols = self.qgol_rows, self.qgol_cols
    are = self.qgol_amp_re
    aim = self.qgol_amp_im
    new_re = [[0.0] * cols for _ in range(rows)]
    new_im = [[0.0] * cols for _ in range(rows)]
    ent = self.qgol_entanglement

    # Pre-compute probability of alive for each cell
    prob = [[are[r][c] ** 2 + aim[r][c] ** 2 for c in range(cols)] for r in range(rows)]

    for r in range(rows):
        for c in range(cols):
            # Expected number of alive neighbours
            n_alive = 0.0
            for nr, nc in _neighbors(r, c, rows, cols):
                n_alive += prob[nr][nc]

            p_alive = prob[r][c]
            a_re = are[r][c]
            a_im = aim[r][c]

            # Determine rotation angle based on Game of Life rules:
            # B3: birth when ~3 neighbours → rotate |0⟩ toward |1⟩
            # S23: survive when ~2-3 neighbours → keep |1⟩
            # Otherwise: death → rotate |1⟩ toward |0⟩
            theta = _gol_rotation(n_alive, p_alive)

            # Apply rotation in the amplitude space
            # This mixes alive/dead amplitudes unitarily
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            # dead amplitude (sqrt(1-p) with phase 0 for simplicity)
            dead_amp = math.sqrt(max(0.0, 1.0 - p_alive))

            # New alive amplitude: cos(θ)|alive⟩ + sin(θ)|dead⟩
            new_re[r][c] = cos_t * a_re + sin_t * dead_amp
            new_im[r][c] = cos_t * a_im

            # Generate entanglement with neighbours that contributed
            if abs(theta) > 0.05:
                for nr, nc in _neighbors(r, c, rows, cols):
                    if prob[nr][nc] > 0.01:
                        key = (r, c, nr, nc) if (r, c) < (nr, nc) else (nr, nc, r, c)
                        strength = min(1.0, ent.get(key, 0.0) + abs(theta) * prob[nr][nc] * 0.1)
                        ent[key] = strength

    # ── Environmental decoherence ──
    dec = self.qgol_decoherence
    if dec > 0:
        for r in range(rows):
            for c in range(cols):
                if random.random() < dec:
                    # Partial measurement: project toward classical state
                    p = new_re[r][c] ** 2 + new_im[r][c] ** 2
                    if random.random() < p:
                        # Collapse to alive
                        new_re[r][c] = 1.0
                        new_im[r][c] = 0.0
                    else:
                        # Collapse to dead
                        new_re[r][c] = 0.0
                        new_im[r][c] = 0.0
                    # Propagate decoherence to entangled partners
                    _decohere_partners(r, c, ent, new_re, new_im, rows, cols)

    # Decay entanglement over time
    dead_keys = []
    for key in ent:
        ent[key] *= 0.95
        if ent[key] < 0.005:
            dead_keys.append(key)
    for key in dead_keys:
        del ent[key]

    self.qgol_amp_re = new_re
    self.qgol_amp_im = new_im
    self.qgol_generation += 1


def _gol_rotation(n_alive: float, p_alive: float) -> float:
    """Compute rotation angle based on GoL rules (B3/S23).

    Returns a rotation angle θ where:
    - Positive θ rotates toward alive (birth)
    - Negative θ rotates toward dead (death)
    - Near-zero θ preserves current state (survival / stasis)
    """
    # Smooth birth signal: peaked at n_alive = 3
    birth_signal = math.exp(-((n_alive - 3.0) ** 2) / 0.8)
    # Smooth survival signal: peaked at n_alive = 2 and 3
    survive_signal = max(
        math.exp(-((n_alive - 2.0) ** 2) / 0.8),
        math.exp(-((n_alive - 3.0) ** 2) / 0.8),
    )

    if p_alive < 0.3:
        # Mostly dead cell — birth signal drives rotation toward alive
        theta = birth_signal * 0.4 * math.pi
    elif p_alive > 0.7:
        # Mostly alive cell — survival signal keeps it alive, else death
        theta = (survive_signal - 0.5) * 0.3 * math.pi
    else:
        # Superposition — both signals compete
        theta = (birth_signal * (1.0 - p_alive) + survive_signal * p_alive - 0.3) * 0.35 * math.pi

    return theta


def _decohere_partners(r, c, ent, amp_re, amp_im, rows, cols):
    """When cell (r,c) decoheres, partially collapse entangled partners."""
    to_remove = []
    for key, strength in ent.items():
        r1, c1, r2, c2 = key
        partner = None
        if r1 == r and c1 == c:
            partner = (r2, c2)
        elif r2 == r and c2 == c:
            partner = (r1, c1)
        if partner is not None and strength > 0.1:
            pr, pc = partner
            # Partial collapse proportional to entanglement strength
            p = amp_re[pr][pc] ** 2 + amp_im[pr][pc] ** 2
            collapse_prob = strength * 0.5
            if random.random() < collapse_prob:
                if random.random() < p:
                    amp_re[pr][pc] = math.sqrt(p)
                    amp_im[pr][pc] = 0.0
                else:
                    amp_re[pr][pc] = 0.0
                    amp_im[pr][pc] = 0.0
            to_remove.append(key)
    for key in to_remove:
        if key in ent:
            del ent[key]


# ── Measurement (click) ─────────────────────────────────────────────────────

def _qgol_measure(self, r, c):
    """Measure (click) a cell: collapse it and propagate decoherence."""
    if r < 0 or r >= self.qgol_rows or c < 0 or c >= self.qgol_cols:
        return
    are = self.qgol_amp_re
    aim = self.qgol_amp_im
    p = are[r][c] ** 2 + aim[r][c] ** 2
    if random.random() < p:
        are[r][c] = 1.0
        aim[r][c] = 0.0
        self._flash(f"Measured ({r},{c}): ALIVE")
    else:
        are[r][c] = 0.0
        aim[r][c] = 0.0
        self._flash(f"Measured ({r},{c}): DEAD")
    # Propagate decoherence to entangled partners
    _decohere_partners(r, c, self.qgol_entanglement, are, aim,
                       self.qgol_rows, self.qgol_cols)


# ── Key handlers ─────────────────────────────────────────────────────────────

def _handle_qgol_menu_key(self, key: int) -> bool:
    """Handle input in Quantum GoL preset menu."""
    n = len(QGOL_PRESETS)
    if key in (curses.KEY_UP, ord("k")):
        self.qgol_menu_sel = (self.qgol_menu_sel - 1) % n
    elif key in (curses.KEY_DOWN, ord("j")):
        self.qgol_menu_sel = (self.qgol_menu_sel + 1) % n
    elif key in (10, 13, curses.KEY_ENTER):
        self._qgol_init(self.qgol_menu_sel)
    elif key in (27, ord("q")):
        self.qgol_menu = False
        self._flash("Quantum GoL cancelled")
    return True


def _handle_qgol_key(self, key: int) -> bool:
    """Handle input in active Quantum GoL simulation."""
    if key == ord(" "):
        self.qgol_running = not self.qgol_running
        self._flash("Running" if self.qgol_running else "Paused")
    elif key in (ord("n"), ord(".")):
        self.qgol_running = False
        self._qgol_step()
    elif key == ord("+") or key == ord("="):
        self.qgol_steps_per_frame = min(20, self.qgol_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.qgol_steps_per_frame}")
    elif key == ord("-"):
        self.qgol_steps_per_frame = max(1, self.qgol_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.qgol_steps_per_frame}")
    elif key == ord("v"):
        views = ["probability", "phase", "entanglement"]
        idx = views.index(self.qgol_view) if self.qgol_view in views else 0
        self.qgol_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.qgol_view}")
    elif key == ord("d"):
        self.qgol_decoherence = min(1.0, self.qgol_decoherence + 0.005)
        self._flash(f"Decoherence: {self.qgol_decoherence:.3f}")
    elif key == ord("D"):
        self.qgol_decoherence = max(0.0, self.qgol_decoherence - 0.005)
        self._flash(f"Decoherence: {self.qgol_decoherence:.3f}")
    elif key == ord("r"):
        self._qgol_init(self.qgol_menu_sel)
    elif key in (ord("R"), ord("m")):
        self.qgol_mode = False
        self.qgol_running = False
        self.qgol_menu = True
        self.qgol_menu_sel = 0
        self._flash("Quantum GoL — select a configuration")
    elif key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                gr = my - 1   # offset for title bar
                gc = mx // 2
                self._qgol_measure(gr, gc)
        except curses.error:
            pass
    elif key in (27, ord("q")):
        self._exit_qgol_mode()
    else:
        return True
    return True


# ── Drawing ──────────────────────────────────────────────────────────────────

def _draw_qgol_menu(self, max_y: int, max_x: int):
    """Draw the Quantum GoL preset selection menu."""
    self.stdscr.erase()
    title = "── Quantum Game of Life ── Select Configuration ──"
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, *_rest) in enumerate(QGOL_PRESETS):
        y = 2 + i * 2
        if y >= max_y - 2:
            break
        marker = "▶ " if i == self.qgol_menu_sel else "  "
        attr = curses.A_BOLD if i == self.qgol_menu_sel else 0
        try:
            self.stdscr.addstr(y, 2, f"{marker}{name}", curses.color_pair(3) | attr)
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [j/k]=navigate [Enter]=select [q]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_qgol(self, max_y: int, max_x: int):
    """Draw the active Quantum Game of Life simulation."""
    self.stdscr.erase()
    rows, cols = self.qgol_rows, self.qgol_cols
    are = self.qgol_amp_re
    aim = self.qgol_amp_im
    ent = self.qgol_entanglement

    # Title bar
    state = "▶ RUNNING" if self.qgol_running else "⏸ PAUSED"
    n_ent = len(ent)
    title = (f" Quantum GoL: {self.qgol_preset_name}  │  "
             f"Gen {self.qgol_generation}  │  {state}  │  "
             f"View: {self.qgol_view}  │  "
             f"Decoh: {self.qgol_decoherence:.3f}  │  "
             f"Ent: {n_ent}")
    title = title[:max_x - 1]
    try:
        self.stdscr.addstr(0, 0, title, curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    if self.qgol_view == "entanglement":
        # Draw entanglement links as characters between correlated cells
        # First draw a dim probability background
        for r in range(view_rows):
            sy = 1 + r
            if sy >= max_y - 1:
                break
            for c in range(view_cols):
                sx = c * 2
                if sx + 1 >= max_x:
                    break
                p = are[r][c] ** 2 + aim[r][c] ** 2
                if p > 0.01:
                    ch = "░░" if p > 0.3 else "· "
                    try:
                        self.stdscr.addstr(sy, sx, ch, curses.color_pair(4) | curses.A_DIM)
                    except curses.error:
                        pass

        # Draw entanglement links
        for (r1, c1, r2, c2), strength in ent.items():
            if strength < 0.05:
                continue
            if r1 >= view_rows or r2 >= view_rows or c1 >= view_cols or c2 >= view_cols:
                continue
            # Draw a connecting character at the midpoint
            mr = (r1 + r2) // 2
            mc = (c1 + c2) // 2
            sy = 1 + mr
            sx = mc * 2
            if 0 < sy < max_y - 1 and 0 <= sx + 1 < max_x:
                if strength > 0.7:
                    ch, color = "██", curses.color_pair(5) | curses.A_BOLD
                elif strength > 0.4:
                    ch, color = "▓▓", curses.color_pair(5)
                elif strength > 0.2:
                    ch, color = "▒▒", curses.color_pair(5) | curses.A_DIM
                else:
                    ch, color = "░░", curses.color_pair(4) | curses.A_DIM
                try:
                    self.stdscr.addstr(sy, sx, ch, color)
                except curses.error:
                    pass
            # Mark the two endpoints
            for er, ec in ((r1, c1), (r2, c2)):
                ey = 1 + er
                ex = ec * 2
                if 0 < ey < max_y - 1 and 0 <= ex + 1 < max_x:
                    try:
                        self.stdscr.addstr(ey, ex, "◉ " if strength > 0.5 else "● ",
                                           curses.color_pair(5) | curses.A_BOLD)
                    except curses.error:
                        pass
    else:
        # Probability or phase view
        for r in range(view_rows):
            sy = 1 + r
            if sy >= max_y - 1:
                break
            for c in range(view_cols):
                sx = c * 2
                if sx + 1 >= max_x:
                    break
                a_re = are[r][c]
                a_im = aim[r][c]
                p = a_re ** 2 + a_im ** 2

                if p < 0.005:
                    continue  # skip empty cells

                if self.qgol_view == "probability":
                    # Density char based on probability, color based on phase
                    idx = int(min(p, 1.0) * (len(_DENSITY) - 1))
                    ch = _DENSITY[idx]
                    if p > 0.01:
                        phase = math.atan2(a_im, a_re)
                        cp = _phase_color(phase)
                    else:
                        cp = 4
                    bold = curses.A_BOLD if p > 0.5 else 0
                    try:
                        self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | bold)
                    except curses.error:
                        pass
                else:  # phase view
                    phase = math.atan2(a_im, a_re)
                    cp = _phase_color(phase)
                    intensity = math.sqrt(p)
                    if intensity > 0.7:
                        ch = "██"
                    elif intensity > 0.4:
                        ch = "▓▓"
                    elif intensity > 0.2:
                        ch = "▒▒"
                    else:
                        ch = "░░"
                    try:
                        self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | curses.A_BOLD)
                    except curses.error:
                        pass

    # Status / population bar
    pop_y = max_y - 2
    if pop_y > 1:
        # Count expected population (sum of probabilities)
        total_p = 0.0
        for r in range(rows):
            for c in range(cols):
                total_p += are[r][c] ** 2 + aim[r][c] ** 2
        pop_str = f" Expected population: {total_p:.1f}  │  Entangled pairs: {len(ent)}"
        pop_str = pop_str[:max_x - 1]
        try:
            self.stdscr.addstr(pop_y, 0, pop_str, curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [v]=view [d/D]=decoh [click]=measure [+/-]=speed [r]=reset [R]=menu [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ── Registration ─────────────────────────────────────────────────────────────

def register(App):
    """Register Quantum GoL mode methods on the App class."""
    App.QGOL_PRESETS = QGOL_PRESETS
    App._enter_qgol_mode = _enter_qgol_mode
    App._exit_qgol_mode = _exit_qgol_mode
    App._qgol_init = _qgol_init
    App._qgol_step = _qgol_step
    App._qgol_measure = _qgol_measure
    App._handle_qgol_menu_key = _handle_qgol_menu_key
    App._handle_qgol_key = _handle_qgol_key
    App._draw_qgol_menu = _draw_qgol_menu
    App._draw_qgol = _draw_qgol
