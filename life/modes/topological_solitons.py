"""Mode: topological_solitons — Topological Solitons.

Simulates a 2D order-parameter field (XY model / O(2) field) where topological
defects — vortices, antivortices, skyrmions, and domain walls — emerge,
interact, annihilate in pairs, and scatter off each other.

Physics modelled:
  1. XY spin field: continuous angle θ(r,c) ∈ [−π, π) at each cell
  2. Gradient energy: E = (K/2) Σ |∇θ|² — penalises rapid angle changes
  3. Overdamped relaxation: ∂θ/∂t = −δE/δθ + thermal noise
  4. Topological charge: q = (1/2π) ∮ dθ around a plaquette
     q = +1 → vortex, q = −1 → antivortex
  5. Vortex dynamics: defects interact via Coulomb-like log potential,
     opposite charges attract and annihilate
  6. Skyrmion extension: full n-vector field (θ,φ) with DMI producing
     stable particle-like topological solitons
  7. BKT transition: below T_BKT, vortex–antivortex pairs are bound;
     above T_BKT they unbind and proliferate

Visualization:
  - Field view: angle θ mapped to hue via directional arrows/colours
  - Charge view: topological charge density (red +1 vortices, blue −1 antivortices)
  - Energy view: local gradient energy density
  - Defect tracking: trails showing defect motion history
"""
import curses
import math
import random
import time

# ── Presets ──────────────────────────────────────────────────────────────────

TOPO_SOLITON_PRESETS = [
    ("Vortex Gas",
     "Random vortex–antivortex pairs in XY field — watch them orbit and annihilate",
     "vortex_gas"),
    ("BKT Transition",
     "Tune temperature through the Berezinskii-Kosterlitz-Thouless transition",
     "bkt"),
    ("Skyrmion Lattice",
     "Magnetic skyrmions stabilised by Dzyaloshinskii-Moriya interaction",
     "skyrmion"),
    ("Domain Walls",
     "Ising-like domain walls between ordered regions — wall dynamics and coarsening",
     "domain_wall"),
    ("Vortex Dipoles",
     "Bound vortex–antivortex pairs that propagate as composite solitons",
     "dipole"),
    ("Turbulent Defects",
     "High-temperature defect turbulence — dense tangle of interacting vortices",
     "turbulent"),
]

# ── Glyphs & colours ────────────────────────────────────────────────────────

# Direction arrows for 8 angle sectors
_ANGLE_ARROWS = ["→→", "↗↗", "↑↑", "↖↖", "←←", "↙↙", "↓↓", "↘↘"]

# Charge glyphs
_VORTEX_GLYPH = "⊕⊕"     # positive charge (vortex)
_ANTIVORTEX_GLYPH = "⊖⊖"  # negative charge (antivortex)
_SKYRMION_GLYPH = "◉◉"    # skyrmion

# Energy density glyphs
_ENERGY_CHARS = ["  ", "· ", "░░", "▒▒", "▓▓", "██"]


def _angle_to_color(theta: float) -> int:
    """Map angle θ to curses color pair for directional colouring."""
    # Normalise to [0, 2π)
    t = theta % (2.0 * math.pi)
    sector = t / (2.0 * math.pi) * 6.0
    if sector < 1.0:
        return 1   # red (0°)
    elif sector < 2.0:
        return 3   # yellow (60°)
    elif sector < 3.0:
        return 2   # green (120°)
    elif sector < 4.0:
        return 4   # blue (180°) (actually cyan)
    elif sector < 5.0:
        return 5   # magenta (240°)
    else:
        return 1   # red (300°)


def _angle_to_arrow(theta: float) -> str:
    """Map angle θ to a directional arrow glyph."""
    t = theta % (2.0 * math.pi)
    idx = int(t / (2.0 * math.pi) * 8.0 + 0.5) % 8
    return _ANGLE_ARROWS[idx]


def _charge_color(q: float) -> int:
    """Map topological charge to colour."""
    if q > 0.3:
        return 1   # red for vortex (+1)
    elif q < -0.3:
        return 4   # blue for antivortex (−1)
    else:
        return 6   # white for neutral


def _energy_color(e: float, e_max: float) -> int:
    """Map energy density to colour."""
    if e_max < 1e-6:
        return 6
    norm = min(e / e_max, 1.0)
    if norm > 0.7:
        return 1   # red (high energy)
    elif norm > 0.4:
        return 3   # yellow
    elif norm > 0.15:
        return 6   # white
    else:
        return 4   # blue (low energy)


def _angle_diff(a: float, b: float) -> float:
    """Compute the shortest signed angle difference (a - b), wrapped to [-π, π)."""
    d = a - b
    while d > math.pi:
        d -= 2.0 * math.pi
    while d < -math.pi:
        d += 2.0 * math.pi
    return d


# ── Enter / Exit ────────────────────────────────────────────────────────────

def _enter_topo_soliton_mode(self):
    """Enter Topological Solitons mode — show preset menu."""
    self.topo_soliton_menu = True
    self.topo_soliton_menu_sel = 0
    self._flash("Topological Solitons — select a configuration")


def _exit_topo_soliton_mode(self):
    """Exit Topological Solitons mode."""
    self.topo_soliton_mode = False
    self.topo_soliton_menu = False
    self.topo_soliton_running = False
    self._flash("Topological Solitons OFF")


# ── Initialisation ──────────────────────────────────────────────────────────

def _topo_soliton_init(self, preset_idx: int):
    """Set up the topological soliton simulation for the chosen preset."""
    name, _desc, kind = TOPO_SOLITON_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(16, max_y - 4)
    cols = max(16, (max_x - 1) // 2)
    self.topo_soliton_rows = rows
    self.topo_soliton_cols = cols
    self.topo_soliton_preset_name = name
    self.topo_soliton_preset_kind = kind
    self.topo_soliton_generation = 0
    self.topo_soliton_view = "field"     # field | charge | energy
    self.topo_soliton_steps_per_frame = 3

    # Physics parameters
    self.topo_soliton_K = 1.0            # stiffness (exchange coupling)
    self.topo_soliton_T = 0.0            # temperature (noise)
    self.topo_soliton_dt = 0.15          # timestep
    self.topo_soliton_dmi = 0.0          # Dzyaloshinskii-Moriya interaction
    self.topo_soliton_ext_field = 0.0    # external field (Zeeman)
    self.topo_soliton_damping = 0.05     # Gilbert damping

    # Angle field θ(r,c)
    theta = [[0.0] * cols for _ in range(rows)]
    # Topological charge cache
    charge = [[0.0] * cols for _ in range(rows)]
    # Defect trail history
    self.topo_soliton_trails = []        # list of (r, c, q, gen)
    self.topo_soliton_max_trails = 500

    if kind == "vortex_gas":
        self.topo_soliton_K = 1.0
        self.topo_soliton_T = 0.1
        _init_vortex_pairs(theta, rows, cols, n_pairs=4)
    elif kind == "bkt":
        self.topo_soliton_K = 1.0
        self.topo_soliton_T = 0.5      # start near transition
        _init_vortex_pairs(theta, rows, cols, n_pairs=6)
    elif kind == "skyrmion":
        self.topo_soliton_K = 1.0
        self.topo_soliton_dmi = 0.5
        self.topo_soliton_ext_field = 0.3
        self.topo_soliton_T = 0.02
        _init_skyrmions(theta, rows, cols, n_skyrmions=5)
    elif kind == "domain_wall":
        self.topo_soliton_K = 1.5
        self.topo_soliton_T = 0.05
        _init_domain_walls(theta, rows, cols)
    elif kind == "dipole":
        self.topo_soliton_K = 1.0
        self.topo_soliton_T = 0.05
        _init_vortex_dipoles(theta, rows, cols, n_dipoles=3)
    elif kind == "turbulent":
        self.topo_soliton_K = 0.8
        self.topo_soliton_T = 0.8
        _init_turbulent(theta, rows, cols)

    self.topo_soliton_theta = theta
    self.topo_soliton_charge = charge
    self.topo_soliton_mode = True
    self.topo_soliton_menu = False
    self.topo_soliton_running = False
    _compute_charges(charge, theta, rows, cols)
    self._flash(f"Topological Solitons: {name} — Space to start")


# ── Preset placement helpers ────────────────────────────────────────────────

def _place_vortex(theta, rows, cols, cr, cc, charge_sign=1):
    """Imprint a single vortex (charge_sign=+1) or antivortex (−1) at (cr,cc)."""
    for r in range(rows):
        for c in range(cols):
            dr = r - cr
            dc = c - cc
            # Toroidal wrapping: pick shortest displacement
            if dr > rows / 2:
                dr -= rows
            elif dr < -rows / 2:
                dr += rows
            if dc > cols / 2:
                dc -= cols
            elif dc < -cols / 2:
                dc += cols
            if abs(dr) < 1e-9 and abs(dc) < 1e-9:
                continue
            angle = charge_sign * math.atan2(dr, dc)
            # Superpose onto existing field
            theta[r][c] += angle


def _normalize_field(theta, rows, cols):
    """Wrap all angles to [-π, π)."""
    for r in range(rows):
        for c in range(cols):
            a = theta[r][c]
            while a > math.pi:
                a -= 2.0 * math.pi
            while a < -math.pi:
                a += 2.0 * math.pi
            theta[r][c] = a


def _init_vortex_pairs(theta, rows, cols, n_pairs=4):
    """Place n vortex-antivortex pairs at random positions."""
    # Start with uniform field
    base_angle = random.uniform(-math.pi, math.pi)
    for r in range(rows):
        for c in range(cols):
            theta[r][c] = base_angle

    sep = max(4, min(rows, cols) // 6)
    for _ in range(n_pairs):
        cr = random.randint(sep, rows - sep - 1)
        cc = random.randint(sep, cols - sep - 1)
        offset_r = random.randint(-sep // 2, sep // 2)
        offset_c = random.choice([-1, 1]) * random.randint(sep // 2, sep)
        _place_vortex(theta, rows, cols, cr, cc, +1)
        _place_vortex(theta, rows, cols,
                      (cr + offset_r) % rows, (cc + offset_c) % cols, -1)

    _normalize_field(theta, rows, cols)


def _init_skyrmions(theta, rows, cols, n_skyrmions=5):
    """Place skyrmion textures — radial hedgehog configurations."""
    # Background: uniform field pointing "up" (θ = 0)
    for r in range(rows):
        for c in range(cols):
            theta[r][c] = 0.0

    radius = max(3, min(rows, cols) // 10)
    for _ in range(n_skyrmions):
        cr = random.randint(radius + 2, rows - radius - 2)
        cc = random.randint(radius + 2, cols - radius - 2)
        for r in range(rows):
            for c in range(cols):
                dr = r - cr
                dc = c - cc
                if dr > rows / 2:
                    dr -= rows
                elif dr < -rows / 2:
                    dr += rows
                if dc > cols / 2:
                    dc -= cols
                elif dc < -cols / 2:
                    dc += cols
                dist = math.sqrt(dr * dr + dc * dc)
                if dist < radius:
                    # Skyrmion profile: θ goes from π at centre to 0 at edge
                    profile = math.pi * (1.0 - dist / radius)
                    phi = math.atan2(dr, dc)
                    # Néel skyrmion: in-plane angle follows azimuthal
                    theta[r][c] = profile + phi

    _normalize_field(theta, rows, cols)


def _init_domain_walls(theta, rows, cols):
    """Create several domain walls separating ordered regions."""
    n_domains = random.randint(3, 5)
    # Assign random angles to vertical strips
    strip_width = max(1, cols // n_domains)
    angles = [random.uniform(-math.pi, math.pi) for _ in range(n_domains)]
    for r in range(rows):
        for c in range(cols):
            domain = min(c // strip_width, n_domains - 1)
            theta[r][c] = angles[domain] + random.uniform(-0.1, 0.1)
    # Add a couple of horizontal walls too
    h_wall_r = rows // 3
    angle_shift = random.uniform(0.5, 1.5)
    for r in range(h_wall_r, rows):
        for c in range(cols):
            theta[r][c] += angle_shift
    _normalize_field(theta, rows, cols)


def _init_vortex_dipoles(theta, rows, cols, n_dipoles=3):
    """Place tightly bound vortex-antivortex dipoles."""
    base_angle = random.uniform(-math.pi, math.pi)
    for r in range(rows):
        for c in range(cols):
            theta[r][c] = base_angle

    sep = 3  # tight binding
    for _ in range(n_dipoles):
        cr = random.randint(6, rows - 6)
        cc = random.randint(6, cols - 6)
        angle = random.uniform(0, 2 * math.pi)
        dr = int(sep * math.sin(angle))
        dc = int(sep * math.cos(angle))
        _place_vortex(theta, rows, cols, cr, cc, +1)
        _place_vortex(theta, rows, cols,
                      (cr + dr) % rows, (cc + dc) % cols, -1)

    _normalize_field(theta, rows, cols)


def _init_turbulent(theta, rows, cols):
    """High-temperature disordered field — many defects emerge spontaneously."""
    for r in range(rows):
        for c in range(cols):
            theta[r][c] = random.uniform(-math.pi, math.pi)


# ── Topological charge computation ──────────────────────────────────────────

def _compute_charges(charge, theta, rows, cols):
    """Compute topological charge q at each plaquette.

    q = (1/2π) Σ Δθ around a 2x2 plaquette.
    q ≈ +1 for a vortex, −1 for an antivortex, 0 elsewhere.
    """
    for r in range(rows):
        for c in range(cols):
            r1 = (r + 1) % rows
            c1 = (c + 1) % cols
            # Plaquette corners: (r,c) → (r,c+1) → (r+1,c+1) → (r+1,c) → (r,c)
            d1 = _angle_diff(theta[r][c1], theta[r][c])
            d2 = _angle_diff(theta[r1][c1], theta[r][c1])
            d3 = _angle_diff(theta[r1][c], theta[r1][c1])
            d4 = _angle_diff(theta[r][c], theta[r1][c])
            winding = (d1 + d2 + d3 + d4) / (2.0 * math.pi)
            charge[r][c] = winding


# ── Physics step ────────────────────────────────────────────────────────────

def _topo_soliton_step(self):
    """Advance the topological soliton simulation by one timestep.

    Uses overdamped Landau-Lifshitz-Gilbert dynamics on the XY field:
      ∂θ/∂t = K ∇²θ − D·(curl term) − H_ext·sin(θ) + η(T)

    where:
      K    = stiffness (exchange)
      D    = DMI strength (stabilises skyrmions)
      H_ext = external Zeeman field
      η    = Gaussian thermal noise ∝ √T
    """
    rows, cols = self.topo_soliton_rows, self.topo_soliton_cols
    theta = self.topo_soliton_theta
    K = self.topo_soliton_K
    T = self.topo_soliton_T
    dt = self.topo_soliton_dt
    dmi = self.topo_soliton_dmi
    h_ext = self.topo_soliton_ext_field

    new_theta = [[0.0] * cols for _ in range(rows)]
    noise_scale = math.sqrt(2.0 * T * dt) if T > 0 else 0.0

    for r in range(rows):
        for c in range(cols):
            th = theta[r][c]

            # 4-neighbour Laplacian of θ (respecting angle wrapping)
            r_up = (r - 1) % rows
            r_dn = (r + 1) % rows
            c_lt = (c - 1) % cols
            c_rt = (c + 1) % cols

            lap = (_angle_diff(theta[r_up][c], th) +
                   _angle_diff(theta[r_dn][c], th) +
                   _angle_diff(theta[r][c_lt], th) +
                   _angle_diff(theta[r][c_rt], th))

            # Exchange torque: K ∇²θ
            torque = K * lap

            # DMI torque (Dzyaloshinskii-Moriya): favours perpendicular neighbours
            # Approximated as antisymmetric exchange: D·(sin(θ_right − θ) − sin(θ_left − θ))
            if dmi > 0:
                dmi_torque = dmi * (
                    math.sin(_angle_diff(theta[r][c_rt], th)) -
                    math.sin(_angle_diff(theta[r][c_lt], th)) +
                    math.sin(_angle_diff(theta[r_dn][c], th)) -
                    math.sin(_angle_diff(theta[r_up][c], th))
                )
                torque += dmi_torque

            # External field (Zeeman): tries to align θ → 0
            if abs(h_ext) > 1e-9:
                torque -= h_ext * math.sin(th)

            # Thermal noise
            noise = 0.0
            if noise_scale > 0:
                noise = random.gauss(0.0, noise_scale)

            # Update
            new_th = th + dt * torque + noise
            # Wrap to [-π, π)
            while new_th > math.pi:
                new_th -= 2.0 * math.pi
            while new_th < -math.pi:
                new_th += 2.0 * math.pi
            new_theta[r][c] = new_th

    self.topo_soliton_theta = new_theta
    self.topo_soliton_generation += 1

    # Recompute topological charges
    charge = self.topo_soliton_charge
    _compute_charges(charge, new_theta, rows, cols)

    # Record defect positions for trails
    gen = self.topo_soliton_generation
    trails = self.topo_soliton_trails
    for r in range(rows):
        for c in range(cols):
            q = charge[r][c]
            if abs(q) > 0.3:
                trails.append((r, c, q, gen))

    # Trim old trails
    max_t = self.topo_soliton_max_trails
    if len(trails) > max_t:
        self.topo_soliton_trails = trails[-max_t:]


# ── Interaction ─────────────────────────────────────────────────────────────

def _topo_soliton_place_defect(self, r, c, charge_sign=1):
    """Place a vortex (+1) or antivortex (−1) at the given position."""
    rows, cols = self.topo_soliton_rows, self.topo_soliton_cols
    if r < 0 or r >= rows or c < 0 or c >= cols:
        return
    theta = self.topo_soliton_theta
    _place_vortex(theta, rows, cols, r, c, charge_sign)
    _normalize_field(theta, rows, cols)
    _compute_charges(self.topo_soliton_charge, theta, rows, cols)
    name = "vortex" if charge_sign > 0 else "antivortex"
    self._flash(f"Placed {name} at ({r},{c})")


# ── Key handlers ────────────────────────────────────────────────────────────

def _handle_topo_soliton_menu_key(self, key: int) -> bool:
    """Handle input in Topological Solitons preset menu."""
    n = len(TOPO_SOLITON_PRESETS)
    if key in (curses.KEY_UP, ord("k")):
        self.topo_soliton_menu_sel = (self.topo_soliton_menu_sel - 1) % n
    elif key in (curses.KEY_DOWN, ord("j")):
        self.topo_soliton_menu_sel = (self.topo_soliton_menu_sel + 1) % n
    elif key in (10, 13, curses.KEY_ENTER):
        self._topo_soliton_init(self.topo_soliton_menu_sel)
    elif key in (27, ord("q")):
        self.topo_soliton_menu = False
        self._flash("Topological Solitons cancelled")
    return True


def _handle_topo_soliton_key(self, key: int) -> bool:
    """Handle input in active Topological Solitons simulation."""
    if key == ord(" "):
        self.topo_soliton_running = not self.topo_soliton_running
        self._flash("Running" if self.topo_soliton_running else "Paused")
    elif key in (ord("n"), ord(".")):
        self.topo_soliton_running = False
        self._topo_soliton_step()
    elif key == ord("+") or key == ord("="):
        self.topo_soliton_steps_per_frame = min(20, self.topo_soliton_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.topo_soliton_steps_per_frame}")
    elif key == ord("-"):
        self.topo_soliton_steps_per_frame = max(1, self.topo_soliton_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.topo_soliton_steps_per_frame}")
    elif key == ord("v"):
        views = ["field", "charge", "energy"]
        idx = views.index(self.topo_soliton_view) if self.topo_soliton_view in views else 0
        self.topo_soliton_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.topo_soliton_view}")
    elif key == ord("t"):
        self.topo_soliton_T = min(2.0, self.topo_soliton_T + 0.05)
        self._flash(f"Temperature T: {self.topo_soliton_T:.2f}")
    elif key == ord("T"):
        self.topo_soliton_T = max(0.0, self.topo_soliton_T - 0.05)
        self._flash(f"Temperature T: {self.topo_soliton_T:.2f}")
    elif key == ord("k"):
        self.topo_soliton_K = min(3.0, self.topo_soliton_K + 0.1)
        self._flash(f"Stiffness K: {self.topo_soliton_K:.1f}")
    elif key == ord("K"):
        self.topo_soliton_K = max(0.1, self.topo_soliton_K - 0.1)
        self._flash(f"Stiffness K: {self.topo_soliton_K:.1f}")
    elif key == ord("d"):
        self.topo_soliton_dmi = min(2.0, self.topo_soliton_dmi + 0.05)
        self._flash(f"DMI D: {self.topo_soliton_dmi:.2f}")
    elif key == ord("D"):
        self.topo_soliton_dmi = max(0.0, self.topo_soliton_dmi - 0.05)
        self._flash(f"DMI D: {self.topo_soliton_dmi:.2f}")
    elif key == ord("h"):
        self.topo_soliton_ext_field = min(2.0, self.topo_soliton_ext_field + 0.05)
        self._flash(f"External field H: {self.topo_soliton_ext_field:.2f}")
    elif key == ord("H"):
        self.topo_soliton_ext_field = max(0.0, self.topo_soliton_ext_field - 0.05)
        self._flash(f"External field H: {self.topo_soliton_ext_field:.2f}")
    elif key == ord("c"):
        # Clear trails
        self.topo_soliton_trails = []
        self._flash("Trails cleared")
    elif key == ord("r"):
        self._topo_soliton_init(self.topo_soliton_menu_sel)
    elif key in (ord("R"), ord("m")):
        self.topo_soliton_mode = False
        self.topo_soliton_running = False
        self.topo_soliton_menu = True
        self.topo_soliton_menu_sel = 0
        self._flash("Topological Solitons — select a configuration")
    elif key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                gr = my - 1
                gc = mx // 2
                self._topo_soliton_place_defect(gr, gc, +1)
            elif bstate & (curses.BUTTON3_CLICKED | curses.BUTTON3_PRESSED):
                gr = my - 1
                gc = mx // 2
                self._topo_soliton_place_defect(gr, gc, -1)
        except curses.error:
            pass
    elif key in (27, ord("q")):
        self._exit_topo_soliton_mode()
    else:
        return True
    return True


# ── Drawing ─────────────────────────────────────────────────────────────────

def _draw_topo_soliton_menu(self, max_y: int, max_x: int):
    """Draw the Topological Solitons preset selection menu."""
    self.stdscr.erase()
    title = "── Topological Solitons ── Select Configuration ──"
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, *_rest) in enumerate(TOPO_SOLITON_PRESETS):
        y = 2 + i * 2
        if y >= max_y - 2:
            break
        marker = "▶ " if i == self.topo_soliton_menu_sel else "  "
        attr = curses.A_BOLD if i == self.topo_soliton_menu_sel else 0
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


def _draw_topo_soliton(self, max_y: int, max_x: int):
    """Draw the active Topological Solitons simulation."""
    self.stdscr.erase()
    rows, cols = self.topo_soliton_rows, self.topo_soliton_cols
    theta = self.topo_soliton_theta
    charge = self.topo_soliton_charge

    # Count defects
    n_vortex = 0
    n_anti = 0
    total_charge = 0.0
    for r in range(rows):
        for c in range(cols):
            q = charge[r][c]
            if q > 0.3:
                n_vortex += 1
                total_charge += q
            elif q < -0.3:
                n_anti += 1
                total_charge += q

    # Title bar
    state = "▶ RUNNING" if self.topo_soliton_running else "⏸ PAUSED"
    title = (f" Solitons: {self.topo_soliton_preset_name}  │  "
             f"T={self.topo_soliton_generation}  │  {state}  │  "
             f"⊕{n_vortex} ⊖{n_anti}  │  "
             f"Q={total_charge:+.0f}")
    title = title[:max_x - 1]
    try:
        tc = curses.color_pair(3) if n_vortex + n_anti > 0 else curses.color_pair(6)
        self.stdscr.addstr(0, 0, title, tc | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    if self.topo_soliton_view == "charge":
        _draw_topo_charge(self, max_y, max_x, view_rows, view_cols)
    elif self.topo_soliton_view == "energy":
        _draw_topo_energy(self, max_y, max_x, view_rows, view_cols)
    else:
        _draw_topo_field(self, max_y, max_x, view_rows, view_cols)

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        info = (f" K={self.topo_soliton_K:.1f}  │  "
                f"T={self.topo_soliton_T:.2f}  │  "
                f"DMI={self.topo_soliton_dmi:.2f}  │  "
                f"H={self.topo_soliton_ext_field:.2f}  │  "
                f"View: {self.topo_soliton_view}")
        info = info[:max_x - 1]
        try:
            self.stdscr.addstr(info_y, 0, info, curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = (" [Space]=play [n]=step [v]=view [t/T]=temp [k/K]=stiffness "
                     "[d/D]=DMI [h/H]=field [click]=vortex [c]=trails [r]=reset [R]=menu [q]=exit")
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_topo_field(self, max_y, max_x, view_rows, view_cols):
    """Field view: angle θ mapped to directional arrows with hue colouring."""
    theta = self.topo_soliton_theta
    charge = self.topo_soliton_charge
    trails = self.topo_soliton_trails
    gen = self.topo_soliton_generation

    # Draw trail dots (faded)
    trail_set = set()
    for (tr, tc, tq, tg) in trails:
        if tr < view_rows and tc < view_cols:
            age = gen - tg
            if age < 100:
                trail_set.add((tr, tc, tq))

    for r in range(view_rows):
        sy = 1 + r
        if sy >= max_y - 2:
            break
        for c in range(view_cols):
            sx = c * 2
            if sx + 1 >= max_x:
                break

            q = charge[r][c]

            # Defects get special glyphs
            if q > 0.3:
                try:
                    self.stdscr.addstr(sy, sx, _VORTEX_GLYPH,
                                       curses.color_pair(1) | curses.A_BOLD)
                except curses.error:
                    pass
                continue
            elif q < -0.3:
                try:
                    self.stdscr.addstr(sy, sx, _ANTIVORTEX_GLYPH,
                                       curses.color_pair(4) | curses.A_BOLD)
                except curses.error:
                    pass
                continue

            # Trail marker
            if (r, c, 1.0) in trail_set or any(tr == r and tc == c for tr, tc, tq, tg in []):
                pass  # trails shown via field colouring below

            # Show field direction
            th = theta[r][c]
            arrow = _angle_to_arrow(th)
            cp = _angle_to_color(th)

            # Dim trail positions
            is_trail = False
            for (tr, tc, tq) in trail_set:
                if tr == r and tc == c:
                    is_trail = True
                    break

            attr = curses.A_DIM if is_trail else 0
            try:
                self.stdscr.addstr(sy, sx, arrow, curses.color_pair(cp) | attr)
            except curses.error:
                pass


def _draw_topo_charge(self, max_y, max_x, view_rows, view_cols):
    """Charge view: topological charge density with defect markers."""
    charge = self.topo_soliton_charge
    trails = self.topo_soliton_trails
    gen = self.topo_soliton_generation

    # Build trail map for faded dots
    trail_map = {}
    for (tr, tc, tq, tg) in trails:
        age = gen - tg
        if age < 80 and tr < view_rows and tc < view_cols:
            trail_map[(tr, tc)] = (tq, age)

    for r in range(view_rows):
        sy = 1 + r
        if sy >= max_y - 2:
            break
        for c in range(view_cols):
            sx = c * 2
            if sx + 1 >= max_x:
                break

            q = charge[r][c]

            if q > 0.3:
                # Vortex
                try:
                    self.stdscr.addstr(sy, sx, _VORTEX_GLYPH,
                                       curses.color_pair(1) | curses.A_BOLD)
                except curses.error:
                    pass
            elif q < -0.3:
                # Antivortex
                try:
                    self.stdscr.addstr(sy, sx, _ANTIVORTEX_GLYPH,
                                       curses.color_pair(4) | curses.A_BOLD)
                except curses.error:
                    pass
            elif (r, c) in trail_map:
                tq, age = trail_map[(r, c)]
                cp = 1 if tq > 0 else 4
                # Fade with age
                attr = curses.A_DIM if age > 30 else 0
                try:
                    self.stdscr.addstr(sy, sx, "· ", curses.color_pair(cp) | attr)
                except curses.error:
                    pass


def _draw_topo_energy(self, max_y, max_x, view_rows, view_cols):
    """Energy view: local gradient energy density."""
    theta = self.topo_soliton_theta
    rows, cols = self.topo_soliton_rows, self.topo_soliton_cols

    # Compute energy density
    e_max = 0.0
    energy = [[0.0] * view_cols for _ in range(view_rows)]
    for r in range(view_rows):
        for c in range(view_cols):
            th = theta[r][c]
            # Sum of squared angle differences to neighbours
            e = 0.0
            for nr, nc in ((r, (c + 1) % cols), ((r + 1) % rows, c)):
                d = _angle_diff(theta[nr][nc], th)
                e += d * d
            energy[r][c] = e
            if e > e_max:
                e_max = e

    for r in range(view_rows):
        sy = 1 + r
        if sy >= max_y - 2:
            break
        for c in range(view_cols):
            sx = c * 2
            if sx + 1 >= max_x:
                break
            e = energy[r][c]
            if e < 0.01:
                continue
            norm = min(e / max(e_max, 1e-6), 1.0)
            idx = int(norm * (len(_ENERGY_CHARS) - 1))
            ch = _ENERGY_CHARS[idx]
            cp = _energy_color(e, e_max)
            bold = curses.A_BOLD if norm > 0.6 else 0
            try:
                self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | bold)
            except curses.error:
                pass


# ── Registration ────────────────────────────────────────────────────────────

def register(App):
    """Register Topological Solitons mode methods on the App class."""
    App.TOPO_SOLITON_PRESETS = TOPO_SOLITON_PRESETS
    App._enter_topo_soliton_mode = _enter_topo_soliton_mode
    App._exit_topo_soliton_mode = _exit_topo_soliton_mode
    App._topo_soliton_init = _topo_soliton_init
    App._topo_soliton_step = _topo_soliton_step
    App._topo_soliton_place_defect = _topo_soliton_place_defect
    App._handle_topo_soliton_menu_key = _handle_topo_soliton_menu_key
    App._handle_topo_soliton_key = _handle_topo_soliton_key
    App._draw_topo_soliton_menu = _draw_topo_soliton_menu
    App._draw_topo_soliton = _draw_topo_soliton
