"""Mode: tcrystal — Discrete Time Crystal.

Simulates a discrete time crystal (DTC) where cells with spin-1/2 states
spontaneously break time-translation symmetry under periodic Floquet driving.
Each cell has a spin on the Bloch sphere (θ, φ) subject to:
  1. A global periodic drive (imperfect π-pulse rotating all spins)
  2. Nearest-neighbour Ising interactions (Jᵢⱼ Zᵢ Zⱼ)
  3. Quenched disorder in local fields (many-body localization)

The hallmark DTC phenomenon: the system responds at half the drive frequency
(period-doubling), and this subharmonic response is robust against
perturbations to the drive — a spontaneous breaking of discrete
time-translation symmetry.

Visualization:
  - Color / glyph ↔ spin-z expectation ⟨σᶻ⟩ (up = warm, down = cool)
  - Brightness ↔ oscillation amplitude (how strongly the spin period-doubles)
  - Stroboscopic view shows the system sampled every 2 drive periods
"""
import curses
import math
import random
import time

# ── Presets ──────────────────────────────────────────────────────────────────

TCRYSTAL_PRESETS = [
    ("Clean DTC",
     "Uniform Ising coupling, slight drive imperfection — watch period-doubling emerge",
     "clean"),
    ("Disordered DTC",
     "Strong quenched disorder in local fields — many-body localized time crystal",
     "disordered"),
    ("Melting Crystal",
     "Large drive error pushing toward the thermal phase boundary — fragile oscillations",
     "melting"),
    ("Domain Walls",
     "Alternating spin domains — boundary dynamics and subharmonic domain breathing",
     "domains"),
    ("Period-4 Attempt",
     "Engineered interactions seeking higher-order subharmonic response (T/4 periodicity)",
     "period4"),
    ("Random Spins",
     "Fully random initial spins with moderate disorder — spontaneous DTC formation",
     "random"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────

_SPIN_CHARS_UP   = ["  ", "· ", "░░", "▒▒", "▓▓", "██"]
_SPIN_CHARS_DOWN = ["  ", "· ", "░░", "▒▒", "▓▓", "██"]


def _sz_color(sz: float) -> int:
    """Map spin-z expectation to curses color pair index."""
    if sz > 0.5:
        return 1   # red (strong up)
    elif sz > 0.15:
        return 3   # yellow (weak up)
    elif sz > -0.15:
        return 6   # white (near zero)
    elif sz > -0.5:
        return 4   # blue (weak down)
    else:
        return 4   # blue (strong down)


def _osc_color(amp: float) -> int:
    """Map oscillation amplitude to color — strong DTC = green."""
    if amp > 0.7:
        return 2   # green (strong period-doubling)
    elif amp > 0.4:
        return 6   # cyan (moderate)
    elif amp > 0.15:
        return 3   # yellow (weak)
    else:
        return 4   # blue (negligible)


def _neighbors(r, c, rows, cols):
    """Yield the 4 von Neumann neighbourhood coordinates (toroidal wrap)."""
    yield (r - 1) % rows, c
    yield (r + 1) % rows, c
    yield r, (c - 1) % cols
    yield r, (c + 1) % cols


# ── Enter / Exit ─────────────────────────────────────────────────────────────

def _enter_tcrystal_mode(self):
    """Enter Time Crystal mode — show preset menu."""
    self.tcrystal_menu = True
    self.tcrystal_menu_sel = 0
    self._flash("Time Crystal — select a configuration")


def _exit_tcrystal_mode(self):
    """Exit Time Crystal mode."""
    self.tcrystal_mode = False
    self.tcrystal_menu = False
    self.tcrystal_running = False
    self._flash("Time Crystal OFF")


# ── Initialisation ───────────────────────────────────────────────────────────

def _tcrystal_init(self, preset_idx: int):
    """Set up the spin lattice for the chosen preset."""
    name, _desc, kind = TCRYSTAL_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(16, max_y - 4)
    cols = max(16, (max_x - 1) // 2)
    self.tcrystal_rows = rows
    self.tcrystal_cols = cols
    self.tcrystal_preset_name = name
    self.tcrystal_generation = 0
    self.tcrystal_drive_period = 0   # counts within a Floquet period (0 or 1)
    self.tcrystal_view = "spin"      # spin | oscillation | stroboscopic
    self.tcrystal_steps_per_frame = 1

    # Drive parameters
    self.tcrystal_epsilon = 0.03     # drive imperfection (deviation from π)
    self.tcrystal_J = 1.0            # Ising coupling strength
    self.tcrystal_disorder = 0.0     # disorder strength in local fields

    # Per-cell spin state: sz in [-1, 1] (spin-z expectation value)
    # and phase φ for transverse component
    sz = [[0.0] * cols for _ in range(rows)]
    phi = [[0.0] * cols for _ in range(rows)]

    # Per-cell quenched disorder: random local field
    h_disorder = [[0.0] * cols for _ in range(rows)]

    # Per-cell Ising coupling disorder
    J_disorder = [[1.0] * cols for _ in range(rows)]

    # History for oscillation detection (store last N stroboscopic sz values)
    hist_len = 16
    self.tcrystal_hist_len = hist_len
    history = [[[0.0] * cols for _ in range(rows)] for _ in range(hist_len)]

    if kind == "clean":
        self.tcrystal_epsilon = 0.03
        self.tcrystal_J = 1.0
        self.tcrystal_disorder = 0.0
        _place_all_up(sz, rows, cols)
    elif kind == "disordered":
        self.tcrystal_epsilon = 0.05
        self.tcrystal_J = 0.8
        self.tcrystal_disorder = 0.5
        _place_all_up(sz, rows, cols)
        _apply_disorder(h_disorder, J_disorder, 0.5, rows, cols)
    elif kind == "melting":
        self.tcrystal_epsilon = 0.20
        self.tcrystal_J = 0.6
        self.tcrystal_disorder = 0.3
        _place_all_up(sz, rows, cols)
        _apply_disorder(h_disorder, J_disorder, 0.3, rows, cols)
    elif kind == "domains":
        self.tcrystal_epsilon = 0.03
        self.tcrystal_J = 1.0
        self.tcrystal_disorder = 0.1
        _place_domains(sz, rows, cols)
        _apply_disorder(h_disorder, J_disorder, 0.1, rows, cols)
    elif kind == "period4":
        self.tcrystal_epsilon = 0.03
        self.tcrystal_J = 1.5
        self.tcrystal_disorder = 0.2
        _place_checkerboard(sz, rows, cols)
        _apply_disorder(h_disorder, J_disorder, 0.2, rows, cols)
    elif kind == "random":
        self.tcrystal_epsilon = 0.05
        self.tcrystal_J = 0.9
        self.tcrystal_disorder = 0.4
        _place_random(sz, phi, rows, cols)
        _apply_disorder(h_disorder, J_disorder, 0.4, rows, cols)

    self.tcrystal_sz = sz
    self.tcrystal_phi = phi
    self.tcrystal_h_disorder = h_disorder
    self.tcrystal_J_disorder = J_disorder
    self.tcrystal_history = history
    self.tcrystal_hist_idx = 0
    self.tcrystal_mode = True
    self.tcrystal_menu = False
    self.tcrystal_running = False
    self._flash(f"Time Crystal: {name} — Space to start, ε={self.tcrystal_epsilon:.2f}")


# ── Preset placement helpers ─────────────────────────────────────────────────

def _place_all_up(sz, rows, cols):
    """All spins polarized up (sz = +1)."""
    for r in range(rows):
        for c in range(cols):
            sz[r][c] = 1.0


def _place_domains(sz, rows, cols):
    """Alternating horizontal stripe domains."""
    stripe_w = max(3, rows // 6)
    for r in range(rows):
        val = 1.0 if (r // stripe_w) % 2 == 0 else -1.0
        for c in range(cols):
            sz[r][c] = val


def _place_checkerboard(sz, rows, cols):
    """Checkerboard pattern of up/down spins."""
    for r in range(rows):
        for c in range(cols):
            sz[r][c] = 1.0 if (r + c) % 2 == 0 else -1.0


def _place_random(sz, phi, rows, cols):
    """Random spin orientations."""
    for r in range(rows):
        for c in range(cols):
            sz[r][c] = random.uniform(-1.0, 1.0)
            phi[r][c] = random.uniform(0.0, 2.0 * math.pi)


def _apply_disorder(h_disorder, J_disorder, strength, rows, cols):
    """Apply quenched disorder to local fields and couplings."""
    for r in range(rows):
        for c in range(cols):
            h_disorder[r][c] = random.gauss(0.0, strength)
            J_disorder[r][c] = 1.0 + random.gauss(0.0, strength * 0.3)


# ── Floquet step ─────────────────────────────────────────────────────────────

def _tcrystal_step(self):
    """One Floquet half-period of the discrete time crystal.

    Each full Floquet period consists of two half-steps:
      Phase 1 (drive_period=0): Ising interaction + disorder
        H₁ = Σᵢⱼ Jᵢⱼ σᶻᵢ σᶻⱼ + Σᵢ hᵢ σᶻᵢ
      Phase 2 (drive_period=1): Global spin flip (imperfect π-pulse)
        U = exp(-i(π - ε)Σᵢ σˣᵢ / 2)

    The DTC signature: despite the π-pulse trying to flip all spins every
    period, the Ising interactions and disorder conspire to produce a
    response at period 2T (half the drive frequency).
    """
    rows, cols = self.tcrystal_rows, self.tcrystal_cols
    sz = self.tcrystal_sz
    phi = self.tcrystal_phi
    phase = self.tcrystal_drive_period

    if phase == 0:
        # Phase 1: Ising interaction + longitudinal disorder
        # Each spin precesses around z-axis due to neighbors and local field
        J = self.tcrystal_J
        h_dis = self.tcrystal_h_disorder
        J_dis = self.tcrystal_J_disorder
        new_sz = [[0.0] * cols for _ in range(rows)]
        new_phi = [[0.0] * cols for _ in range(rows)]

        for r in range(rows):
            for c in range(cols):
                # Effective field from neighbors (Ising Z-Z)
                h_eff = h_dis[r][c]
                for nr, nc in _neighbors(r, c, rows, cols):
                    h_eff += J * J_dis[r][c] * sz[nr][nc]

                # Spin precession under effective field
                # |sz| is preserved; phi rotates
                cur_sz = sz[r][c]
                cur_phi = phi[r][c]

                # The effective field tilts the spin
                # For Ising model: sz is approximately conserved,
                # but the transverse components precess
                dt = 0.5  # interaction time per half-period
                # Effective interaction modifies the spin-z slightly
                # through transverse coupling effects
                sx = math.sqrt(max(0.0, 1.0 - cur_sz * cur_sz)) * math.cos(cur_phi)
                sy = math.sqrt(max(0.0, 1.0 - cur_sz * cur_sz)) * math.sin(cur_phi)

                # Precession around z due to h_eff
                angle = h_eff * dt
                new_sx = sx * math.cos(angle) - sy * math.sin(angle)
                new_sy = sx * math.sin(angle) + sy * math.cos(angle)
                new_sz_val = cur_sz  # Ising preserves sz component

                # Small transverse-field mixing for richer dynamics
                mix = 0.02 * h_eff * dt
                new_sz_val = max(-1.0, min(1.0, new_sz_val + mix * new_sx))

                # Reconstruct transverse magnitude
                trans = math.sqrt(max(0.0, 1.0 - new_sz_val * new_sz_val))
                if trans > 1e-10:
                    new_phi[r][c] = math.atan2(new_sy, new_sx)
                else:
                    new_phi[r][c] = cur_phi
                new_sz[r][c] = new_sz_val

        self.tcrystal_sz = new_sz
        self.tcrystal_phi = new_phi

    else:
        # Phase 2: Global π-pulse (imperfect by ε)
        # Rotation by angle (π - ε) around x-axis
        # This flips sz → -sz (perfect flip) with a small error ε
        eps = self.tcrystal_epsilon
        rot_angle = math.pi - eps  # imperfect π-pulse

        cos_r = math.cos(rot_angle)
        sin_r = math.sin(rot_angle)

        for r in range(rows):
            for c in range(cols):
                cur_sz = sz[r][c]
                cur_phi = phi[r][c]

                # Decompose spin into Bloch vector
                trans = math.sqrt(max(0.0, 1.0 - cur_sz * cur_sz))
                sx = trans * math.cos(cur_phi)
                sy = trans * math.sin(cur_phi)

                # Rotation around x-axis by rot_angle:
                # sx' = sx
                # sy' = sy cos(θ) - sz sin(θ)
                # sz' = sy sin(θ) + sz cos(θ)
                new_sx = sx
                new_sy = sy * cos_r - cur_sz * sin_r
                new_sz_val = sy * sin_r + cur_sz * cos_r

                new_sz_val = max(-1.0, min(1.0, new_sz_val))
                new_trans = math.sqrt(max(0.0, 1.0 - new_sz_val * new_sz_val))
                if new_trans > 1e-10:
                    phi[r][c] = math.atan2(new_sy, new_sx)
                else:
                    phi[r][c] = 0.0
                sz[r][c] = new_sz_val

        # Record stroboscopic snapshot after each full period
        hist = self.tcrystal_history
        idx = self.tcrystal_hist_idx % self.tcrystal_hist_len
        for r in range(rows):
            for c in range(cols):
                hist[idx][r][c] = sz[r][c]
        self.tcrystal_hist_idx += 1

    # Advance drive phase
    self.tcrystal_drive_period = 1 - phase
    self.tcrystal_generation += 1


# ── Analysis helpers ────────────────────────────────────────────────────────

def _compute_oscillation(self, r, c):
    """Compute oscillation amplitude for cell (r,c) from stroboscopic history.

    Returns a value in [0, 1] measuring how strongly the spin alternates
    sign every Floquet period (period-doubling = DTC signature).
    """
    hist = self.tcrystal_history
    n = min(self.tcrystal_hist_idx, self.tcrystal_hist_len)
    if n < 4:
        return 0.0
    start = self.tcrystal_hist_idx - n
    # Check for period-2 pattern: sign should alternate
    alternating = 0.0
    total = 0.0
    for i in range(1, n):
        idx_cur = (start + i) % self.tcrystal_hist_len
        idx_prev = (start + i - 1) % self.tcrystal_hist_len
        val_cur = hist[idx_cur][r][c]
        val_prev = hist[idx_prev][r][c]
        # If signs alternate, this contributes positively
        if val_cur * val_prev < 0:
            alternating += min(abs(val_cur), abs(val_prev))
        total += max(abs(val_cur), abs(val_prev))
    if total < 0.01:
        return 0.0
    return min(1.0, alternating / total)


def _compute_order_parameter(self):
    """Compute the global DTC order parameter.

    Returns the stroboscopic magnetization alternation — the fraction of
    spins that flip sign between consecutive Floquet periods.
    """
    n = min(self.tcrystal_hist_idx, self.tcrystal_hist_len)
    if n < 2:
        return 0.0
    rows, cols = self.tcrystal_rows, self.tcrystal_cols
    hist = self.tcrystal_history
    idx_cur = (self.tcrystal_hist_idx - 1) % self.tcrystal_hist_len
    idx_prev = (self.tcrystal_hist_idx - 2) % self.tcrystal_hist_len

    flip_sum = 0.0
    mag_sum = 0.0
    for r in range(rows):
        for c in range(cols):
            s_cur = hist[idx_cur][r][c]
            s_prev = hist[idx_prev][r][c]
            flip_sum += abs(s_cur - s_prev)
            mag_sum += abs(s_cur) + abs(s_prev)
    if mag_sum < 0.01:
        return 0.0
    # Perfect period-doubling: every spin flips, so flip_sum ≈ 2*mag_sum/2
    return min(1.0, flip_sum / max(mag_sum, 0.01))


# ── Perturbation (click) ────────────────────────────────────────────────────

def _tcrystal_perturb(self, r, c):
    """Perturb a cell by flipping its spin — test DTC robustness."""
    if r < 0 or r >= self.tcrystal_rows or c < 0 or c >= self.tcrystal_cols:
        return
    self.tcrystal_sz[r][c] *= -1.0
    self._flash(f"Flipped spin at ({r},{c}) — sz={self.tcrystal_sz[r][c]:+.2f}")


# ── Key handlers ─────────────────────────────────────────────────────────────

def _handle_tcrystal_menu_key(self, key: int) -> bool:
    """Handle input in Time Crystal preset menu."""
    n = len(TCRYSTAL_PRESETS)
    if key in (curses.KEY_UP, ord("k")):
        self.tcrystal_menu_sel = (self.tcrystal_menu_sel - 1) % n
    elif key in (curses.KEY_DOWN, ord("j")):
        self.tcrystal_menu_sel = (self.tcrystal_menu_sel + 1) % n
    elif key in (10, 13, curses.KEY_ENTER):
        self._tcrystal_init(self.tcrystal_menu_sel)
    elif key in (27, ord("q")):
        self.tcrystal_menu = False
        self._flash("Time Crystal cancelled")
    return True


def _handle_tcrystal_key(self, key: int) -> bool:
    """Handle input in active Time Crystal simulation."""
    if key == ord(" "):
        self.tcrystal_running = not self.tcrystal_running
        self._flash("Running" if self.tcrystal_running else "Paused")
    elif key in (ord("n"), ord(".")):
        self.tcrystal_running = False
        self._tcrystal_step()
    elif key == ord("+") or key == ord("="):
        self.tcrystal_steps_per_frame = min(20, self.tcrystal_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.tcrystal_steps_per_frame}")
    elif key == ord("-"):
        self.tcrystal_steps_per_frame = max(1, self.tcrystal_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.tcrystal_steps_per_frame}")
    elif key == ord("v"):
        views = ["spin", "oscillation", "stroboscopic"]
        idx = views.index(self.tcrystal_view) if self.tcrystal_view in views else 0
        self.tcrystal_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.tcrystal_view}")
    elif key == ord("e"):
        self.tcrystal_epsilon = min(0.5, self.tcrystal_epsilon + 0.01)
        self._flash(f"Drive error ε: {self.tcrystal_epsilon:.2f}")
    elif key == ord("E"):
        self.tcrystal_epsilon = max(0.0, self.tcrystal_epsilon - 0.01)
        self._flash(f"Drive error ε: {self.tcrystal_epsilon:.2f}")
    elif key == ord("j") and not (key in (curses.KEY_DOWN,)):
        self.tcrystal_J = min(3.0, self.tcrystal_J + 0.1)
        self._flash(f"Ising coupling J: {self.tcrystal_J:.1f}")
    elif key == ord("J"):
        self.tcrystal_J = max(0.0, self.tcrystal_J - 0.1)
        self._flash(f"Ising coupling J: {self.tcrystal_J:.1f}")
    elif key == ord("d"):
        self.tcrystal_disorder = min(2.0, self.tcrystal_disorder + 0.05)
        _apply_disorder(self.tcrystal_h_disorder, self.tcrystal_J_disorder,
                        self.tcrystal_disorder, self.tcrystal_rows, self.tcrystal_cols)
        self._flash(f"Disorder: {self.tcrystal_disorder:.2f}")
    elif key == ord("D"):
        self.tcrystal_disorder = max(0.0, self.tcrystal_disorder - 0.05)
        _apply_disorder(self.tcrystal_h_disorder, self.tcrystal_J_disorder,
                        self.tcrystal_disorder, self.tcrystal_rows, self.tcrystal_cols)
        self._flash(f"Disorder: {self.tcrystal_disorder:.2f}")
    elif key == ord("r"):
        self._tcrystal_init(self.tcrystal_menu_sel)
    elif key in (ord("R"), ord("m")):
        self.tcrystal_mode = False
        self.tcrystal_running = False
        self.tcrystal_menu = True
        self.tcrystal_menu_sel = 0
        self._flash("Time Crystal — select a configuration")
    elif key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                gr = my - 1
                gc = mx // 2
                self._tcrystal_perturb(gr, gc)
        except curses.error:
            pass
    elif key in (27, ord("q")):
        self._exit_tcrystal_mode()
    else:
        return True
    return True


# ── Drawing ──────────────────────────────────────────────────────────────────

def _draw_tcrystal_menu(self, max_y: int, max_x: int):
    """Draw the Time Crystal preset selection menu."""
    self.stdscr.erase()
    title = "── Discrete Time Crystal ── Select Configuration ──"
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, *_rest) in enumerate(TCRYSTAL_PRESETS):
        y = 2 + i * 2
        if y >= max_y - 2:
            break
        marker = "▶ " if i == self.tcrystal_menu_sel else "  "
        attr = curses.A_BOLD if i == self.tcrystal_menu_sel else 0
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


def _draw_tcrystal(self, max_y: int, max_x: int):
    """Draw the active Time Crystal simulation."""
    self.stdscr.erase()
    rows, cols = self.tcrystal_rows, self.tcrystal_cols
    sz = self.tcrystal_sz

    # Compute order parameter
    order = _compute_order_parameter(self)
    drive_phase_str = "INTERACT" if self.tcrystal_drive_period == 0 else "π-PULSE"

    # Title bar
    state = "▶ RUNNING" if self.tcrystal_running else "⏸ PAUSED"
    title = (f" Time Crystal: {self.tcrystal_preset_name}  │  "
             f"T={self.tcrystal_generation}  │  {state}  │  "
             f"Phase: {drive_phase_str}  │  "
             f"ε={self.tcrystal_epsilon:.2f}  │  "
             f"DTC order: {order:.2f}")
    title = title[:max_x - 1]
    try:
        # Color title by DTC strength
        tc = curses.color_pair(2 if order > 0.5 else 3 if order > 0.2 else 1)
        self.stdscr.addstr(0, 0, title, tc | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    if self.tcrystal_view == "oscillation":
        # Show DTC oscillation amplitude per cell
        for r in range(view_rows):
            sy = 1 + r
            if sy >= max_y - 1:
                break
            for c in range(view_cols):
                sx = c * 2
                if sx + 1 >= max_x:
                    break
                osc = _compute_oscillation(self, r, c)
                if osc < 0.02:
                    continue
                idx = int(min(osc, 1.0) * (len(_SPIN_CHARS_UP) - 1))
                ch = _SPIN_CHARS_UP[idx]
                cp = _osc_color(osc)
                bold = curses.A_BOLD if osc > 0.5 else 0
                try:
                    self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | bold)
                except curses.error:
                    pass

    elif self.tcrystal_view == "stroboscopic":
        # Show stroboscopic spin state (sampled every full period)
        n = min(self.tcrystal_hist_idx, self.tcrystal_hist_len)
        if n > 0:
            hist = self.tcrystal_history
            idx = (self.tcrystal_hist_idx - 1) % self.tcrystal_hist_len
            for r in range(view_rows):
                sy = 1 + r
                if sy >= max_y - 1:
                    break
                for c in range(view_cols):
                    sx = c * 2
                    if sx + 1 >= max_x:
                        break
                    val = hist[idx][r][c]
                    if abs(val) < 0.02:
                        continue
                    a = abs(val)
                    ci = int(min(a, 1.0) * (len(_SPIN_CHARS_UP) - 1))
                    ch = _SPIN_CHARS_UP[ci]
                    cp = _sz_color(val)
                    bold = curses.A_BOLD if a > 0.5 else 0
                    try:
                        self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | bold)
                    except curses.error:
                        pass
    else:
        # Default spin view: show current sz
        for r in range(view_rows):
            sy = 1 + r
            if sy >= max_y - 1:
                break
            for c in range(view_cols):
                sx = c * 2
                if sx + 1 >= max_x:
                    break
                val = sz[r][c]
                if abs(val) < 0.02:
                    continue
                a = abs(val)
                ci = int(min(a, 1.0) * (len(_SPIN_CHARS_UP) - 1))
                ch = _SPIN_CHARS_UP[ci]
                cp = _sz_color(val)
                bold = curses.A_BOLD if a > 0.5 else 0
                try:
                    self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | bold)
                except curses.error:
                    pass

    # Magnetization bar
    pop_y = max_y - 2
    if pop_y > 1:
        total_m = 0.0
        for r in range(rows):
            for c in range(cols):
                total_m += sz[r][c]
        avg_m = total_m / (rows * cols)
        pop_str = (f" ⟨σᶻ⟩={avg_m:+.3f}  │  J={self.tcrystal_J:.1f}  │  "
                   f"Disorder={self.tcrystal_disorder:.2f}  │  "
                   f"View: {self.tcrystal_view}  │  "
                   f"DTC order: {order:.2f}")
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
            hint = " [Space]=play [n]=step [v]=view [e/E]=drive ε [d/D]=disorder [click]=perturb [+/-]=speed [r]=reset [R]=menu [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ── Registration ─────────────────────────────────────────────────────────────

def register(App):
    """Register Time Crystal mode methods on the App class."""
    App.TCRYSTAL_PRESETS = TCRYSTAL_PRESETS
    App._enter_tcrystal_mode = _enter_tcrystal_mode
    App._exit_tcrystal_mode = _exit_tcrystal_mode
    App._tcrystal_init = _tcrystal_init
    App._tcrystal_step = _tcrystal_step
    App._tcrystal_perturb = _tcrystal_perturb
    App._compute_oscillation = _compute_oscillation
    App._compute_order_parameter = _compute_order_parameter
    App._handle_tcrystal_menu_key = _handle_tcrystal_menu_key
    App._handle_tcrystal_key = _handle_tcrystal_key
    App._draw_tcrystal_menu = _draw_tcrystal_menu
    App._draw_tcrystal = _draw_tcrystal
