"""Mode: Superfluid Helium — quantum vortex dynamics simulation.

Simulates superfluid helium (He-II) below the lambda point, featuring:
  1. Quantized vortex filaments with circulation κ = h/m_He
  2. Vortex reconnection events that redistribute energy
  3. Kelvin wave cascades along vortex cores
  4. Two-fluid model: superfluid (inviscid, irrotational) + normal component
  5. Second sound waves: temperature/entropy oscillations
  6. Lambda-point phase transition at T_λ ≈ 2.17 K

Physics:
  - Vortices are point objects in 2D (cross-section of 3D filaments)
  - Same-sign vortices co-rotate; opposite-sign reconnect and annihilate
  - Biot-Savart velocity: each vortex induces v ∝ κ/(2πr) azimuthally
  - Mutual friction: coupling between normal and superfluid components
  - Superfluid fraction ρ_s/ρ varies with temperature (0 at T_λ, 1 at T=0)

Visualization:
  - Vortex view: vortex positions with circulation arrows and velocity field
  - Density view: superfluid density perturbations (second sound)
  - Energy view: kinetic energy spectrum (Kolmogorov cascade)
"""
import curses
import math
import random
import time

# ── Presets ──────────────────────────────────────────────────────────────────

SUPERFLUID_PRESETS = [
    ("Quantum Turbulence",
     "Dense vortex tangle — Kolmogorov energy cascade via reconnection events",
     "turbulence"),
    ("Vortex Reconnection",
     "Watch pairs of opposite-sign vortices approach, reconnect, and emit Kelvin waves",
     "reconnection"),
    ("Kelvin Wave Cascade",
     "Perturbations along a vortex ring cascade to smaller scales and radiate phonons",
     "kelvin"),
    ("Two-Fluid Counterflow",
     "Normal and superfluid components flow in opposite directions — generates vortex tangle",
     "counterflow"),
    ("Second Sound",
     "Temperature waves propagate as entropy oscillations in the two-fluid system",
     "second_sound"),
    ("Lambda Point Transition",
     "Cool through T_λ = 2.17 K — watch superfluid fraction grow and vortices freeze out",
     "lambda_point"),
]

# ── Glyphs ───────────────────────────────────────────────────────────────────

_VORTEX_POS = "⊕"   # positive circulation (counterclockwise)
_VORTEX_NEG = "⊖"   # negative circulation (clockwise)
_VORTEX_CORE = "●"
_FLOW_ARROWS = ["→ ", "↗ ", "↑ ", "↖ ", "← ", "↙ ", "↓ ", "↘ "]
_DENSITY_CHARS = ["  ", "· ", "░░", "▒▒", "▓▓", "██"]
_WAVE_CHARS = ["  ", "~ ", "≈ ", "∿ ", "≋ "]
_ENERGY_BARS = " ▁▂▃▄▅▆▇█"

# Physical constants (scaled for simulation)
KAPPA = 1.0          # quantum of circulation (h/m_He, normalised)
T_LAMBDA = 2.17      # lambda point temperature (K)


def _sf_color_by_circ(charge: int) -> int:
    """Color for a vortex by its circulation sign."""
    return 1 if charge > 0 else 4  # red=positive, blue=negative


def _sf_velocity_color(speed: float) -> int:
    """Map flow speed to color."""
    if speed > 0.6:
        return 1   # red (fast)
    elif speed > 0.3:
        return 3   # yellow
    elif speed > 0.1:
        return 6   # white
    else:
        return 4   # blue (slow)


def _sf_density_color(rho: float) -> int:
    """Map superfluid density to color."""
    if rho > 0.7:
        return 5   # cyan (dense superfluid)
    elif rho > 0.4:
        return 4   # blue
    elif rho > 0.2:
        return 6   # white
    else:
        return 3   # yellow (normal-dominant)


def _sf_temp_color(T: float) -> int:
    """Map temperature to color."""
    if T > T_LAMBDA:
        return 1   # red (above lambda point, normal fluid)
    elif T > 1.5:
        return 3   # yellow (partial superfluid)
    elif T > 0.8:
        return 6   # white (mostly superfluid)
    else:
        return 5   # cyan (deep superfluid)


# ── Enter / Exit ─────────────────────────────────────────────────────────────

def _enter_superfluid_mode(self):
    """Enter Superfluid Helium mode — show preset menu."""
    self.superfluid_menu = True
    self.superfluid_menu_sel = 0
    self._flash("Superfluid Helium — select a configuration")


def _exit_superfluid_mode(self):
    """Exit Superfluid Helium mode."""
    self.superfluid_mode = False
    self.superfluid_menu = False
    self.superfluid_running = False
    self._flash("Superfluid Helium OFF")


# ── Initialisation ───────────────────────────────────────────────────────────

def _superfluid_init(self, preset_idx: int):
    """Set up the superfluid simulation for the chosen preset."""
    name, _desc, kind = SUPERFLUID_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(16, max_y - 4)
    cols = max(16, (max_x - 1) // 2)
    self.superfluid_rows = rows
    self.superfluid_cols = cols
    self.superfluid_preset_name = name
    self.superfluid_preset_kind = kind
    self.superfluid_generation = 0
    self.superfluid_view = "vortex"          # vortex | density | energy
    self.superfluid_steps_per_frame = 2

    # Two-fluid parameters
    self.superfluid_T = 1.5                  # temperature (K)
    self.superfluid_T_target = 1.5           # target temperature for ramping
    self.superfluid_rho_s_frac = 0.0         # superfluid fraction (computed)
    self.superfluid_mutual_friction_alpha = 0.1  # mutual friction coefficient
    self.superfluid_damping = 0.998          # velocity damping

    # Vortex list: each is [x, y, charge, kw_phase, kw_amp]
    # charge = +1 (CCW) or -1 (CW)
    # kw_phase, kw_amp = Kelvin wave state on this vortex
    self.superfluid_vortices = []

    # Velocity field (coarse grid for visualisation)
    self.superfluid_vx = [[0.0] * cols for _ in range(rows)]
    self.superfluid_vy = [[0.0] * cols for _ in range(rows)]

    # Density/temperature field for second sound
    self.superfluid_rho = [[0.0] * cols for _ in range(rows)]
    self.superfluid_entropy = [[0.0] * cols for _ in range(rows)]
    self.superfluid_rho_v = [[0.0] * cols for _ in range(rows)]  # density velocity

    # Normal fluid velocity (counterflow)
    self.superfluid_vn_x = 0.0
    self.superfluid_vn_y = 0.0

    # Energy spectrum for display
    self.superfluid_energy_spectrum = []
    self.superfluid_reconnection_count = 0
    self.superfluid_total_reconnections = 0

    # Compute initial superfluid fraction
    _update_superfluid_fraction(self)

    # Preset-specific initialisation
    if kind == "turbulence":
        self.superfluid_T = 1.2
        self.superfluid_T_target = 1.2
        _update_superfluid_fraction(self)
        _init_random_vortices(self, n_pairs=25)
    elif kind == "reconnection":
        self.superfluid_T = 1.0
        self.superfluid_T_target = 1.0
        _update_superfluid_fraction(self)
        _init_reconnection_pairs(self, n_pairs=4)
        self.superfluid_steps_per_frame = 1
    elif kind == "kelvin":
        self.superfluid_T = 0.8
        self.superfluid_T_target = 0.8
        _update_superfluid_fraction(self)
        _init_kelvin_ring(self)
    elif kind == "counterflow":
        self.superfluid_T = 1.6
        self.superfluid_T_target = 1.6
        _update_superfluid_fraction(self)
        self.superfluid_vn_x = 0.3  # normal fluid moves right
        _init_random_vortices(self, n_pairs=8)
    elif kind == "second_sound":
        self.superfluid_T = 1.4
        self.superfluid_T_target = 1.4
        _update_superfluid_fraction(self)
        _init_second_sound(self)
    elif kind == "lambda_point":
        self.superfluid_T = 2.5     # start above lambda point
        self.superfluid_T_target = 0.5  # cool down
        _update_superfluid_fraction(self)
        _init_random_vortices(self, n_pairs=15)

    self.superfluid_mode = True
    self.superfluid_menu = False
    self.superfluid_running = False
    rho_s = self.superfluid_rho_s_frac
    self._flash(f"Superfluid He: {name} — T={self.superfluid_T:.2f}K, ρₛ/ρ={rho_s:.2f}")


# ── Preset initialisers ──────────────────────────────────────────────────────

def _update_superfluid_fraction(self):
    """Compute superfluid fraction from temperature.

    Uses simplified two-fluid model:
      ρ_s/ρ = 1 - (T/T_λ)^5.6  for T < T_λ
      ρ_s/ρ = 0                  for T >= T_λ
    """
    T = self.superfluid_T
    if T >= T_LAMBDA:
        self.superfluid_rho_s_frac = 0.0
    else:
        ratio = T / T_LAMBDA
        self.superfluid_rho_s_frac = max(0.0, 1.0 - ratio ** 5.6)


def _init_random_vortices(self, n_pairs=20):
    """Place random vortex-antivortex pairs (net circulation = 0)."""
    rows, cols = self.superfluid_rows, self.superfluid_cols
    margin = 2
    vortices = self.superfluid_vortices
    for _ in range(n_pairs):
        x = random.uniform(margin, cols - margin)
        y = random.uniform(margin, rows - margin)
        sep = random.uniform(2.0, 5.0)
        angle = random.uniform(0, 2 * math.pi)
        dx = sep * 0.5 * math.cos(angle)
        dy = sep * 0.5 * math.sin(angle)
        vortices.append([x + dx, y + dy, +1, 0.0, 0.0])
        vortices.append([x - dx, y - dy, -1, 0.0, 0.0])


def _init_reconnection_pairs(self, n_pairs=4):
    """Place vortex-antivortex pairs aimed at each other for reconnection."""
    rows, cols = self.superfluid_rows, self.superfluid_cols
    vortices = self.superfluid_vortices
    spacing_y = rows / (n_pairs + 1)
    for i in range(n_pairs):
        y = spacing_y * (i + 1)
        x_center = cols / 2.0
        sep = 8.0 + random.uniform(-1, 1)
        vortices.append([x_center - sep, y, +1, 0.0, 0.0])
        vortices.append([x_center + sep, y, -1, 0.0, 0.0])


def _init_kelvin_ring(self):
    """Place vortices in a ring with Kelvin wave perturbation."""
    rows, cols = self.superfluid_rows, self.superfluid_cols
    cx, cy = cols / 2.0, rows / 2.0
    radius = min(rows, cols) / 4.0
    n_vortices = 16
    vortices = self.superfluid_vortices
    for i in range(n_vortices):
        angle = 2 * math.pi * i / n_vortices
        # Add Kelvin wave perturbation (mode 3)
        kw_amp = 1.5
        r = radius + kw_amp * math.sin(3 * angle)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        vortices.append([x, y, +1, angle, kw_amp])
    # Add a central antivortex cluster to balance circulation
    for i in range(n_vortices):
        angle = 2 * math.pi * i / n_vortices
        r = radius * 0.2
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        vortices.append([x, y, -1, 0.0, 0.0])


def _init_second_sound(self):
    """Initialise with a temperature pulse for second sound propagation."""
    rows, cols = self.superfluid_rows, self.superfluid_cols
    # Place a temperature pulse at centre
    cr, cc = rows // 2, cols // 2
    for r in range(rows):
        for c in range(cols):
            dr = r - cr
            dc = c - cc
            d2 = dr * dr + dc * dc
            # Gaussian temperature pulse
            pulse = 0.4 * math.exp(-d2 / (min(rows, cols) * 2.0))
            self.superfluid_entropy[r][c] = pulse
            self.superfluid_rho[r][c] = -pulse * 0.3  # density depletion
    # A few vortices as scatterers
    _init_random_vortices(self, n_pairs=5)


# ── Physics step ─────────────────────────────────────────────────────────────

def _superfluid_step(self):
    """Advance the superfluid simulation by one timestep."""
    kind = self.superfluid_preset_kind

    # Temperature ramping (lambda point transition)
    if abs(self.superfluid_T - self.superfluid_T_target) > 0.005:
        rate = 0.003
        if self.superfluid_T > self.superfluid_T_target:
            self.superfluid_T = max(self.superfluid_T_target,
                                    self.superfluid_T - rate)
        else:
            self.superfluid_T = min(self.superfluid_T_target,
                                    self.superfluid_T + rate)
        _update_superfluid_fraction(self)

    rho_s = self.superfluid_rho_s_frac
    if rho_s < 0.01:
        # Above lambda point — no superfluid dynamics, just thermal diffusion
        _diffuse_entropy(self)
        self.superfluid_generation += 1
        return

    # 1. Compute vortex-vortex interactions (Biot-Savart)
    _step_vortices(self)

    # 2. Check for reconnections
    _check_reconnections(self)

    # 3. Update Kelvin waves
    _step_kelvin_waves(self)

    # 4. Counterflow vortex generation
    if kind == "counterflow":
        _counterflow_generation(self)

    # 5. Second sound propagation
    _step_second_sound(self)

    # 6. Update velocity field for visualisation
    _compute_velocity_field(self)

    # 7. Update energy spectrum
    _compute_energy_spectrum(self)

    self.superfluid_generation += 1


def _step_vortices(self):
    """Move vortices according to Biot-Savart law and mutual friction."""
    vortices = self.superfluid_vortices
    rows, cols = self.superfluid_rows, self.superfluid_cols
    n = len(vortices)
    if n == 0:
        return

    rho_s = self.superfluid_rho_s_frac
    alpha = self.superfluid_mutual_friction_alpha
    vn_x = self.superfluid_vn_x
    vn_y = self.superfluid_vn_y
    dt = 0.15 * rho_s  # timestep scales with superfluid fraction

    for i in range(n):
        xi, yi, qi, _, _ = vortices[i]
        vx_i, vy_i = 0.0, 0.0

        # Sum Biot-Savart contributions from other vortices
        for j in range(n):
            if i == j:
                continue
            xj, yj, qj, _, _ = vortices[j]
            dx = xj - xi
            dy = yj - yi
            # Toroidal wrapping
            if dx > cols / 2:
                dx -= cols
            elif dx < -cols / 2:
                dx += cols
            if dy > rows / 2:
                dy -= rows
            elif dy < -rows / 2:
                dy += rows
            r2 = dx * dx + dy * dy
            # Regularised core: prevent singularity
            r2 = max(r2, 0.5)
            # v = κ/(2π) × ẑ × r̂/|r| → perpendicular velocity
            factor = KAPPA * qj / (2 * math.pi * r2)
            vx_i += -dy * factor
            vy_i += dx * factor

        # Mutual friction: coupling to normal fluid
        # F_mf = α ŝ × (ŝ × (v_n - v_s)) drives vortex toward normal velocity
        rel_x = vn_x - vx_i
        rel_y = vn_y - vy_i
        vx_i += alpha * rel_x
        vy_i += alpha * rel_y

        # Update position
        new_x = xi + vx_i * dt
        new_y = yi + vy_i * dt

        # Toroidal boundaries
        new_x = new_x % cols
        new_y = new_y % rows

        vortices[i][0] = new_x
        vortices[i][1] = new_y


def _check_reconnections(self):
    """Check for vortex-antivortex reconnections.

    When opposite-sign vortices approach within a critical distance,
    they reconnect (annihilate) and emit energy as Kelvin waves / phonons.
    """
    vortices = self.superfluid_vortices
    rows, cols = self.superfluid_rows, self.superfluid_cols
    reconnect_dist = 1.5
    to_remove = set()
    reconnection_sites = []

    n = len(vortices)
    for i in range(n):
        if i in to_remove:
            continue
        for j in range(i + 1, n):
            if j in to_remove:
                continue
            xi, yi, qi = vortices[i][0], vortices[i][1], vortices[i][2]
            xj, yj, qj = vortices[j][0], vortices[j][1], vortices[j][2]
            if qi == qj:
                continue  # same sign don't reconnect
            dx = xj - xi
            dy = yj - yi
            if dx > cols / 2:
                dx -= cols
            elif dx < -cols / 2:
                dx += cols
            if dy > rows / 2:
                dy -= rows
            elif dy < -rows / 2:
                dy += rows
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < reconnect_dist:
                to_remove.add(i)
                to_remove.add(j)
                reconnection_sites.append(((xi + xj) / 2, (yi + yj) / 2))

    if to_remove:
        self.superfluid_vortices = [v for idx, v in enumerate(vortices)
                                     if idx not in to_remove]
        self.superfluid_reconnection_count = len(to_remove) // 2
        self.superfluid_total_reconnections += self.superfluid_reconnection_count

        # Reconnection emits entropy (heat) — local temperature pulse
        for sx, sy in reconnection_sites:
            r = int(sy) % rows
            c = int(sx) % cols
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    d2 = dr * dr + dc * dc
                    if d2 <= 4:
                        rr = (r + dr) % rows
                        rc = (c + dc) % cols
                        self.superfluid_entropy[rr][rc] += 0.2 * (1 - d2 / 5.0)
    else:
        self.superfluid_reconnection_count = 0


def _step_kelvin_waves(self):
    """Evolve Kelvin wave perturbations on vortex cores.

    Kelvin waves are helical displacement waves along vortex filaments.
    In 2D, we model them as oscillating perturbations of vortex position.
    """
    vortices = self.superfluid_vortices
    rho_s = self.superfluid_rho_s_frac
    damping = 0.995

    for v in vortices:
        phase = v[3]
        amp = v[4]
        if amp < 0.01:
            continue
        # Kelvin wave dispersion: ω ∝ k² ln(1/ka)
        # Simplified: phase advances, amplitude slowly decays (energy cascade)
        omega = 0.3 * rho_s
        v[3] = phase + omega
        v[4] = amp * damping
        # Perturb vortex position
        v[0] += amp * 0.05 * math.cos(phase)
        v[1] += amp * 0.05 * math.sin(phase)


def _counterflow_generation(self):
    """In counterflow, generate new vortex pairs when relative velocity is high."""
    rho_s = self.superfluid_rho_s_frac
    vn_x = self.superfluid_vn_x
    vn_y = self.superfluid_vn_y
    v_rel = math.sqrt(vn_x * vn_x + vn_y * vn_y) * rho_s

    # Probability of pair generation proportional to counterflow velocity
    if random.random() < v_rel * 0.05 and len(self.superfluid_vortices) < 200:
        rows, cols = self.superfluid_rows, self.superfluid_cols
        x = random.uniform(2, cols - 2)
        y = random.uniform(2, rows - 2)
        sep = 2.0
        angle = random.uniform(0, 2 * math.pi)
        dx = sep * 0.5 * math.cos(angle)
        dy = sep * 0.5 * math.sin(angle)
        self.superfluid_vortices.append([x + dx, y + dy, +1, 0.0, 0.0])
        self.superfluid_vortices.append([x - dx, y - dy, -1, 0.0, 0.0])


def _step_second_sound(self):
    """Propagate second sound: temperature/entropy waves.

    Second sound speed: c₂² = (ρ_s/ρ_n) · s²T / c_v
    Simplified as a wave equation on the entropy field.
    """
    rows, cols = self.superfluid_rows, self.superfluid_cols
    entropy = self.superfluid_entropy
    rho_v = self.superfluid_rho_v
    rho_s = self.superfluid_rho_s_frac
    rho_n = 1.0 - rho_s

    if rho_s < 0.01 or rho_n < 0.01:
        return

    # Second sound speed squared (scaled)
    c2_sq = 0.3 * rho_s / rho_n
    damping = 0.998

    new_entropy = [[0.0] * cols for _ in range(rows)]
    new_rv = [[0.0] * cols for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            # Laplacian of entropy
            s_center = entropy[r][c]
            lap = 0.0
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr = (r + dr) % rows
                nc = (c + dc) % cols
                lap += entropy[nr][nc]
            lap -= 4.0 * s_center

            # Wave equation: ∂²s/∂t² = c₂² ∇²s
            new_rv[r][c] = rho_v[r][c] * damping + c2_sq * lap
            new_rv[r][c] = max(-0.5, min(0.5, new_rv[r][c]))
            new_entropy[r][c] = s_center + new_rv[r][c]
            # Entropy must be non-negative, allow small negative for waves
            new_entropy[r][c] = max(-0.5, min(1.0, new_entropy[r][c]))

    self.superfluid_entropy = new_entropy
    self.superfluid_rho_v = new_rv


def _diffuse_entropy(self):
    """Simple diffusion when above lambda point (no superfluid)."""
    rows, cols = self.superfluid_rows, self.superfluid_cols
    entropy = self.superfluid_entropy
    new_entropy = [[0.0] * cols for _ in range(rows)]
    diff = 0.1

    for r in range(rows):
        for c in range(cols):
            s = entropy[r][c]
            lap = 0.0
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr = (r + dr) % rows
                nc = (c + dc) % cols
                lap += entropy[nr][nc]
            lap -= 4.0 * s
            new_entropy[r][c] = s + diff * lap
            new_entropy[r][c] = max(-0.3, min(1.0, new_entropy[r][c]))

    self.superfluid_entropy = new_entropy


def _compute_velocity_field(self):
    """Compute coarse-grained velocity field from vortex positions."""
    rows, cols = self.superfluid_rows, self.superfluid_cols
    vx = self.superfluid_vx
    vy = self.superfluid_vy
    vortices = self.superfluid_vortices

    # Reset
    for r in range(rows):
        for c in range(cols):
            vx[r][c] = 0.0
            vy[r][c] = 0.0

    # Sample on a coarser grid for speed
    step = max(1, min(rows, cols) // 30)
    for r in range(0, rows, step):
        for c in range(0, cols, step):
            ux, uy = 0.0, 0.0
            for v in vortices:
                vxp, vyp, q = v[0], v[1], v[2]
                dx = vxp - c
                dy = vyp - r
                if dx > cols / 2:
                    dx -= cols
                elif dx < -cols / 2:
                    dx += cols
                if dy > rows / 2:
                    dy -= rows
                elif dy < -rows / 2:
                    dy += rows
                r2 = dx * dx + dy * dy
                r2 = max(r2, 1.0)
                factor = KAPPA * q / (2 * math.pi * r2)
                ux += -dy * factor
                uy += dx * factor
            # Fill the block
            for dr in range(step):
                for dc in range(step):
                    rr = r + dr
                    cc = c + dc
                    if rr < rows and cc < cols:
                        vx[rr][cc] = ux
                        vy[rr][cc] = uy


def _compute_energy_spectrum(self):
    """Compute a simplified energy spectrum from the velocity field.

    Groups energy by wavenumber shell to show Kolmogorov-like cascade.
    """
    rows, cols = self.superfluid_rows, self.superfluid_cols
    vx = self.superfluid_vx
    vy = self.superfluid_vy

    n_bins = min(20, min(rows, cols) // 2)
    spectrum = [0.0] * n_bins
    max_k = n_bins

    # Sample energy from velocity field in radial shells
    cr, cc = rows // 2, cols // 2
    for r in range(0, rows, 2):
        for c in range(0, cols, 2):
            dr = r - cr
            dc = c - cc
            k = int(math.sqrt(dr * dr + dc * dc) * n_bins / max(min(rows, cols) // 2, 1))
            if 0 <= k < n_bins:
                e = vx[r][c] ** 2 + vy[r][c] ** 2
                spectrum[k] += e

    # Normalise
    max_e = max(spectrum) if spectrum else 1.0
    if max_e > 0:
        spectrum = [s / max_e for s in spectrum]

    self.superfluid_energy_spectrum = spectrum


# ── Key handlers ─────────────────────────────────────────────────────────────

def _handle_superfluid_menu_key(self, key: int) -> bool:
    """Handle input in Superfluid preset menu."""
    n = len(SUPERFLUID_PRESETS)
    if key in (curses.KEY_UP, ord("k")):
        self.superfluid_menu_sel = (self.superfluid_menu_sel - 1) % n
    elif key in (curses.KEY_DOWN, ord("j")):
        self.superfluid_menu_sel = (self.superfluid_menu_sel + 1) % n
    elif key in (10, 13, curses.KEY_ENTER):
        self._superfluid_init(self.superfluid_menu_sel)
    elif key in (27, ord("q")):
        self.superfluid_menu = False
        self._flash("Superfluid cancelled")
    return True


def _handle_superfluid_key(self, key: int) -> bool:
    """Handle input in active Superfluid simulation."""
    if key == ord(" "):
        self.superfluid_running = not self.superfluid_running
        self._flash("Running" if self.superfluid_running else "Paused")
    elif key in (ord("n"), ord(".")):
        self.superfluid_running = False
        self._superfluid_step()
    elif key == ord("+") or key == ord("="):
        self.superfluid_steps_per_frame = min(20, self.superfluid_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.superfluid_steps_per_frame}")
    elif key == ord("-"):
        self.superfluid_steps_per_frame = max(1, self.superfluid_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.superfluid_steps_per_frame}")
    elif key == ord("v"):
        views = ["vortex", "density", "energy"]
        idx = views.index(self.superfluid_view) if self.superfluid_view in views else 0
        self.superfluid_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.superfluid_view}")
    elif key == ord("t"):
        self.superfluid_T_target = min(3.0, self.superfluid_T_target + 0.1)
        self._flash(f"Target T: {self.superfluid_T_target:.2f} K")
    elif key == ord("T"):
        self.superfluid_T_target = max(0.1, self.superfluid_T_target - 0.1)
        self._flash(f"Target T: {self.superfluid_T_target:.2f} K")
    elif key == ord("f"):
        self.superfluid_mutual_friction_alpha = min(
            1.0, self.superfluid_mutual_friction_alpha + 0.02)
        self._flash(f"Mutual friction α: {self.superfluid_mutual_friction_alpha:.2f}")
    elif key == ord("F"):
        self.superfluid_mutual_friction_alpha = max(
            0.0, self.superfluid_mutual_friction_alpha - 0.02)
        self._flash(f"Mutual friction α: {self.superfluid_mutual_friction_alpha:.2f}")
    elif key == ord("c"):
        self.superfluid_vn_x = min(1.0, self.superfluid_vn_x + 0.05)
        self._flash(f"Normal flow vₙ: {self.superfluid_vn_x:.2f}")
    elif key == ord("C"):
        self.superfluid_vn_x = max(-1.0, self.superfluid_vn_x - 0.05)
        self._flash(f"Normal flow vₙ: {self.superfluid_vn_x:.2f}")
    elif key == ord("p"):
        # Add a vortex-antivortex pair at random position
        rows, cols = self.superfluid_rows, self.superfluid_cols
        x = random.uniform(4, cols - 4)
        y = random.uniform(4, rows - 4)
        sep = 3.0
        angle = random.uniform(0, 2 * math.pi)
        dx = sep * 0.5 * math.cos(angle)
        dy = sep * 0.5 * math.sin(angle)
        self.superfluid_vortices.append([x + dx, y + dy, +1, 0.0, 0.0])
        self.superfluid_vortices.append([x - dx, y - dy, -1, 0.0, 0.0])
        self._flash(f"Added vortex pair (total: {len(self.superfluid_vortices)})")
    elif key == ord("s"):
        # Inject second sound pulse at centre
        rows, cols = self.superfluid_rows, self.superfluid_cols
        cr, cc = rows // 2, cols // 2
        for dr in range(-3, 4):
            for dc in range(-3, 4):
                d2 = dr * dr + dc * dc
                if d2 <= 9:
                    rr = (cr + dr) % rows
                    rc = (cc + dc) % cols
                    self.superfluid_entropy[rr][rc] += 0.3 * (1 - d2 / 10.0)
        self._flash("Injected second sound pulse")
    elif key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                gc = mx // 2
                gr = my - 1
                rows, cols = self.superfluid_rows, self.superfluid_cols
                if 0 <= gr < rows and 0 <= gc < cols:
                    # Add vortex pair at click location
                    sep = 2.5
                    angle = random.uniform(0, 2 * math.pi)
                    dx = sep * 0.5 * math.cos(angle)
                    dy = sep * 0.5 * math.sin(angle)
                    self.superfluid_vortices.append(
                        [gc + dx, gr + dy, +1, 0.0, random.uniform(0, 0.5)])
                    self.superfluid_vortices.append(
                        [gc - dx, gr - dy, -1, 0.0, random.uniform(0, 0.5)])
                    self._flash(f"Added vortex pair at ({gr},{gc})")
        except curses.error:
            pass
    elif key == ord("r"):
        self._superfluid_init(self.superfluid_menu_sel)
    elif key in (ord("R"), ord("m")):
        self.superfluid_mode = False
        self.superfluid_running = False
        self.superfluid_menu = True
        self.superfluid_menu_sel = 0
        self._flash("Superfluid Helium — select a configuration")
    elif key in (27, ord("q")):
        self._exit_superfluid_mode()
    else:
        return True
    return True


# ── Drawing ──────────────────────────────────────────────────────────────────

def _draw_superfluid_menu(self, max_y: int, max_x: int):
    """Draw the Superfluid Helium preset selection menu."""
    self.stdscr.erase()
    title = "── Superfluid Helium (He-II) ── Select Configuration ──"
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(5) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, *_rest) in enumerate(SUPERFLUID_PRESETS):
        y = 2 + i * 2
        if y >= max_y - 2:
            break
        marker = "▶ " if i == self.superfluid_menu_sel else "  "
        attr = curses.A_BOLD if i == self.superfluid_menu_sel else 0
        try:
            self.stdscr.addstr(y, 2, f"{marker}{name}",
                               curses.color_pair(5) | attr)
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8],
                               curses.color_pair(6) | curses.A_DIM)
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


def _draw_superfluid(self, max_y: int, max_x: int):
    """Draw the active Superfluid Helium simulation."""
    self.stdscr.erase()
    rows, cols = self.superfluid_rows, self.superfluid_cols
    T = self.superfluid_T
    rho_s = self.superfluid_rho_s_frac
    n_vort = len(self.superfluid_vortices)

    # Title bar
    state = "▶ RUNNING" if self.superfluid_running else "⏸ PAUSED"
    phase = "SUPERFLUID" if T < T_LAMBDA else "NORMAL"
    title = (f" He-II: {self.superfluid_preset_name}  │  "
             f"t={self.superfluid_generation}  │  {state}  │  "
             f"T={T:.2f}K ({phase})  │  "
             f"ρₛ/ρ={rho_s:.2f}  │  "
             f"Vortices: {n_vort}")
    title = title[:max_x - 1]
    try:
        tc = curses.color_pair(5 if T < T_LAMBDA else 1)
        self.stdscr.addstr(0, 0, title, tc | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    if self.superfluid_view == "density":
        _draw_superfluid_density(self, max_y, max_x, view_rows, view_cols)
    elif self.superfluid_view == "energy":
        _draw_superfluid_energy(self, max_y, max_x, view_rows, view_cols)
    else:
        _draw_superfluid_vortex(self, max_y, max_x, view_rows, view_cols)

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        recon = self.superfluid_total_reconnections
        alpha = self.superfluid_mutual_friction_alpha
        vn = self.superfluid_vn_x
        info = (f" Reconnections: {recon}  │  "
                f"α={alpha:.2f}  │  vₙ={vn:.2f}  │  "
                f"View: {self.superfluid_view}")
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
            hint = (" [Space]=play [n]=step [v]=view [t/T]=temp "
                    "[f/F]=friction [c/C]=counterflow [p]=pair "
                    "[s]=sound [click]=pair [r]=reset [R]=menu [q]=exit")
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_superfluid_vortex(self, max_y, max_x, view_rows, view_cols):
    """Vortex view: show vortex positions and velocity field."""
    vx = self.superfluid_vx
    vy = self.superfluid_vy
    vortices = self.superfluid_vortices

    # Draw velocity field arrows (sampled)
    step = max(2, min(view_rows, view_cols) // 20)
    for r in range(0, view_rows, step):
        sy = 1 + r
        if sy >= max_y - 2:
            break
        for c in range(0, view_cols, step):
            sx = c * 2
            if sx + 1 >= max_x:
                break
            ux = vx[r][c] if r < len(vx) and c < len(vx[0]) else 0.0
            uy = vy[r][c] if r < len(vy) and c < len(vy[0]) else 0.0
            speed = math.sqrt(ux * ux + uy * uy)
            if speed < 0.02:
                continue
            # Direction to arrow index
            angle = math.atan2(-uy, ux)
            idx = int((angle + math.pi) / (2 * math.pi) * 8) % 8
            ch = _FLOW_ARROWS[idx]
            cp = _sf_velocity_color(speed)
            try:
                self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | curses.A_DIM)
            except curses.error:
                pass

    # Draw vortices on top
    for v in vortices:
        vxp, vyp, q = v[0], v[1], v[2]
        sc = int(vxp) * 2
        sr = int(vyp) + 1
        if 1 <= sr < max_y - 2 and 0 <= sc < max_x - 1:
            if q > 0:
                ch = _VORTEX_POS
            else:
                ch = _VORTEX_NEG
            cp = _sf_color_by_circ(q)
            try:
                self.stdscr.addstr(sr, sc, ch, curses.color_pair(cp) | curses.A_BOLD)
            except curses.error:
                pass


def _draw_superfluid_density(self, max_y, max_x, view_rows, view_cols):
    """Density view: second sound / entropy field + superfluid density."""
    entropy = self.superfluid_entropy
    rho_s = self.superfluid_rho_s_frac

    for r in range(view_rows):
        sy = 1 + r
        if sy >= max_y - 2:
            break
        for c in range(view_cols):
            sx = c * 2
            if sx + 1 >= max_x:
                break
            s = entropy[r][c] if r < len(entropy) and c < len(entropy[0]) else 0.0
            # Map entropy to density: high entropy = low superfluid density
            rho_local = rho_s * (1.0 - s * 0.5)
            val = max(0.0, min(1.0, rho_local + s * 0.5))
            if val < 0.02:
                continue
            idx = int(val * (len(_DENSITY_CHARS) - 1))
            if abs(s) > 0.1:
                # Use wave chars for active second sound
                widx = int(min(abs(s) * 3, 1.0) * (len(_WAVE_CHARS) - 1))
                ch = _WAVE_CHARS[widx]
            else:
                ch = _DENSITY_CHARS[idx]
            cp = _sf_density_color(rho_local)
            bold = curses.A_BOLD if abs(s) > 0.2 else 0
            try:
                self.stdscr.addstr(sy, sx, ch, curses.color_pair(cp) | bold)
            except curses.error:
                pass

    # Overlay vortex positions
    for v in self.superfluid_vortices:
        sc = int(v[0]) * 2
        sr = int(v[1]) + 1
        if 1 <= sr < max_y - 2 and 0 <= sc < max_x - 1:
            cp = _sf_color_by_circ(v[2])
            try:
                self.stdscr.addstr(sr, sc, _VORTEX_CORE,
                                   curses.color_pair(cp) | curses.A_BOLD)
            except curses.error:
                pass


def _draw_superfluid_energy(self, max_y, max_x, view_rows, view_cols):
    """Energy view: show kinetic energy spectrum (Kolmogorov cascade)."""
    spectrum = self.superfluid_energy_spectrum
    n_bins = len(spectrum) if spectrum else 0

    if n_bins == 0:
        try:
            self.stdscr.addstr(max_y // 2, 2, "No energy data yet — run simulation",
                               curses.color_pair(6))
        except curses.error:
            pass
        return

    # Draw spectrum as bar chart
    chart_height = max_y - 6
    chart_width = min(max_x - 4, n_bins * 3)
    bar_width = max(1, chart_width // n_bins)

    # Title
    try:
        self.stdscr.addstr(1, 2, "Energy Spectrum E(k) — Kolmogorov cascade",
                           curses.color_pair(5) | curses.A_BOLD)
        # k-5/3 reference line label
        self.stdscr.addstr(2, 2, "Reference: k^(-5/3) Kolmogorov scaling",
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    base_y = max_y - 4
    for i in range(n_bins):
        val = spectrum[i]
        bar_height = int(val * chart_height)
        x = 2 + i * bar_width

        # Draw bar
        for dy in range(bar_height):
            sy = base_y - dy
            if sy < 3 or sy >= max_y - 2:
                continue
            frac = dy / max(chart_height, 1)
            if frac > 0.7:
                cp = 1   # red (high energy)
            elif frac > 0.4:
                cp = 3   # yellow
            elif frac > 0.15:
                cp = 5   # cyan
            else:
                cp = 4   # blue
            # Use block character
            ch_idx = min(int(val * (len(_ENERGY_BARS) - 1)), len(_ENERGY_BARS) - 1)
            ch = _ENERGY_BARS[max(ch_idx, 1)]
            try:
                for bx in range(min(bar_width - 1, 1) + 1):
                    if x + bx < max_x:
                        self.stdscr.addstr(sy, x + bx, ch,
                                           curses.color_pair(cp) | curses.A_BOLD)
            except curses.error:
                pass

        # k label
        if i % max(1, n_bins // 10) == 0 and base_y + 1 < max_y - 1:
            try:
                label = f"k{i}"
                self.stdscr.addstr(base_y + 1, x, label[:bar_width],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # Draw Kolmogorov k^(-5/3) reference line
    for i in range(1, n_bins):
        ref = (1.0 / i) ** (5.0 / 3.0)
        ref = min(ref, 1.0)
        sy = base_y - int(ref * chart_height)
        x = 2 + i * bar_width
        if 3 <= sy < max_y - 2 and x < max_x - 1:
            try:
                self.stdscr.addstr(sy, x, "─", curses.color_pair(3) | curses.A_DIM)
            except curses.error:
                pass

    # Also show vortex positions in lower portion
    v_start_y = 3
    for v in self.superfluid_vortices:
        sc = int(v[0]) * 2
        sr = int(v[1]) + v_start_y
        if v_start_y <= sr < base_y - chart_height and 0 <= sc < max_x - 1:
            cp = _sf_color_by_circ(v[2])
            try:
                self.stdscr.addstr(sr, sc, _VORTEX_CORE,
                                   curses.color_pair(cp) | curses.A_BOLD)
            except curses.error:
                pass


# ── Registration ─────────────────────────────────────────────────────────────

def register(App):
    """Register Superfluid Helium mode methods on the App class."""
    App.SUPERFLUID_PRESETS = SUPERFLUID_PRESETS
    App._enter_superfluid_mode = _enter_superfluid_mode
    App._exit_superfluid_mode = _exit_superfluid_mode
    App._superfluid_init = _superfluid_init
    App._superfluid_step = _superfluid_step
    App._handle_superfluid_menu_key = _handle_superfluid_menu_key
    App._handle_superfluid_key = _handle_superfluid_key
    App._draw_superfluid_menu = _draw_superfluid_menu
    App._draw_superfluid = _draw_superfluid
