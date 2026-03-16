"""Mode: cardiac — Cardiac Electrophysiology & Arrhythmia.

Simulates the heart's electrical conduction system as a 2D tissue slab.
SA node pacemaker cells auto-fire at ~60 bpm, propagating action potential
wavefronts through atrial and ventricular myocyte grids via the AV node
(with physiological delay), bundle of His, and Purkinje fiber fast-conduction
pathways.

Electrophysiology is modeled with simplified FitzHugh-Nagumo kinetics:
  dV/dt = V - V³/3 - W + I_stim
  dW/dt = ε(V + a - bW)
where V is membrane voltage (fast variable), W is recovery (slow variable),
and I_stim represents external or pacemaker current.  Ion channel dynamics
are layered on top: Na⁺ fast inward (depolarization), Ca²⁺ plateau, K⁺
repolarization.  The tissue exhibits depolarization → plateau → repolarization
→ refractory period cycling.

Re-entry circuits form when wavefronts encounter refractory tissue and
spiral around obstacles, producing ventricular tachycardia.  An ECG trace
is derived from summed dipole vectors across the tissue.  Defibrillation
delivers a massive current pulse to reset all cells simultaneously.

Three views:
  1) Tissue activation map — wavefront propagation with conduction anatomy
     (SA node ♥, AV node ◆, His bundle ═, Purkinje ─, atrial/ventricular
      myocytes colored by voltage/phase)
  2) Real-time ECG strip — 12-lead-style traces derived from dipole vectors
  3) Time-series sparkline graphs — heart rate, conduction velocity, APD,
     refractory fraction, etc.

Six presets:
  Normal Sinus Rhythm, Atrial Fibrillation, Ventricular Tachycardia,
  AV Block, Long QT Syndrome, Defibrillation Rescue
"""
import curses
import math
import random


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

CARDIAC_PRESETS = [
    ("Normal Sinus Rhythm",
     "Healthy heart — SA node fires at 60 bpm, orderly atrial→AV→His→Purkinje→ventricular conduction",
     "nsr"),
    ("Atrial Fibrillation",
     "Chaotic atrial wavelets — rapid irregular depolarization, AV node filters some beats",
     "afib"),
    ("Ventricular Tachycardia",
     "Re-entry spiral wave in ventricle — fast dangerous rhythm from circuit around scar tissue",
     "vtach"),
    ("AV Block (2nd Degree)",
     "AV node intermittently fails to conduct — dropped ventricular beats, Wenckebach pattern",
     "avblock"),
    ("Long QT Syndrome",
     "Delayed K⁺ repolarization prolongs action potential — risk of torsades de pointes",
     "longqt"),
    ("Defibrillation Rescue",
     "VFib with chaotic activity — press 'd' to deliver defibrillation shock and restore rhythm",
     "defib"),
]


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                (0, 1), (1, -1), (1, 0), (1, 1)]

# FitzHugh-Nagumo parameters
_FHN_A = 0.7        # recovery offset
_FHN_B = 0.8        # recovery coupling
_FHN_EPSILON = 0.08  # recovery timescale (slow)
_FHN_DT = 0.4       # integration timestep

# Diffusion (conduction)
_DIFF_NORMAL = 0.8     # normal myocyte coupling
_DIFF_PURKINJE = 3.5   # fast Purkinje conduction
_DIFF_HIS = 2.5        # His bundle conduction
_DIFF_AV_DELAY = 0.08  # slow AV node conduction (delay)
_DIFF_SCAR = 0.0       # no conduction through scar

# Pacemaker
_SA_PERIOD = 50        # ticks between SA node fires (~60 bpm at display rate)
_SA_CURRENT = 1.5      # stimulus amplitude
_AV_DELAY_TICKS = 8    # AV node delay in ticks

# Ion channel representation (modulate FHN parameters)
_NA_FAST_BOOST = 0.3   # Na+ fast inward current addition during depolarization
_CA_PLATEAU = 0.15     # Ca2+ plateau current sustaining depolarization
_K_REPOL = 0.12        # K+ repolarization current contribution

# Defibrillation
_DEFIB_CURRENT = 3.0   # massive current pulse
_DEFIB_DURATION = 3    # ticks

# ECG derivation
_ECG_HISTORY_LEN = 200  # number of samples to display

# Tissue types
TISSUE_EMPTY = 0
TISSUE_ATRIAL = 1
TISSUE_VENTRICULAR = 2
TISSUE_SA_NODE = 3
TISSUE_AV_NODE = 4
TISSUE_HIS = 5
TISSUE_PURKINJE = 6
TISSUE_SCAR = 7

_TISSUE_NAMES = {
    TISSUE_EMPTY: "empty",
    TISSUE_ATRIAL: "atrial",
    TISSUE_VENTRICULAR: "ventricular",
    TISSUE_SA_NODE: "SA node",
    TISSUE_AV_NODE: "AV node",
    TISSUE_HIS: "His",
    TISSUE_PURKINJE: "Purkinje",
    TISSUE_SCAR: "scar",
}


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_cardiac_mode(self):
    """Enter cardiac electrophysiology mode — show preset menu."""
    self.cardiac_mode = True
    self.cardiac_menu = True
    self.cardiac_menu_sel = 0


def _exit_cardiac_mode(self):
    """Exit cardiac mode."""
    self.cardiac_mode = False
    self.cardiac_menu = False
    self.cardiac_running = False
    for attr in list(vars(self)):
        if attr.startswith('cardiac_') and attr not in ('cardiac_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _cardiac_init(self, preset_idx: int):
    """Initialize simulation for the chosen preset."""
    name, _desc, pid = CARDIAC_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(16, max_y - 4)
    cols = max(30, max_x - 2)

    self.cardiac_menu = False
    self.cardiac_running = False
    self.cardiac_preset_name = name
    self.cardiac_preset_id = pid
    self.cardiac_rows = rows
    self.cardiac_cols = cols
    self.cardiac_generation = 0
    self.cardiac_speed = 1
    self.cardiac_view = "tissue"   # tissue | ecg | graphs

    # Membrane voltage (V) and recovery variable (W) — FHN state
    self.cardiac_V = [[0.0] * cols for _ in range(rows)]
    self.cardiac_W = [[0.0] * cols for _ in range(rows)]

    # Tissue type map
    self.cardiac_tissue = [[TISSUE_EMPTY] * cols for _ in range(rows)]

    # Diffusion coefficient map
    self.cardiac_diff = [[0.0] * cols for _ in range(rows)]

    # Ion channel state per cell: Na activation, Ca activation, K activation
    self.cardiac_na = [[0.0] * cols for _ in range(rows)]
    self.cardiac_ca = [[0.0] * cols for _ in range(rows)]
    self.cardiac_k = [[0.0] * cols for _ in range(rows)]

    # Refractory state (countdown ticks)
    self.cardiac_refract = [[0] * cols for _ in range(rows)]

    # Pacemaker phase
    self.cardiac_sa_phase = 0
    self.cardiac_sa_period = _SA_PERIOD

    # AV node state
    self.cardiac_av_buffer = []  # queued activations with delay
    self.cardiac_av_block_ratio = 0  # 0=normal, >0 = drop fraction

    # Long QT modifier
    self.cardiac_k_modifier = 1.0  # <1 = delayed repolarization

    # Defibrillation state
    self.cardiac_defib_active = 0  # countdown ticks
    self.cardiac_defib_count = 0

    # ECG traces (simulated leads)
    self.cardiac_ecg_i = []     # Lead I (horizontal dipole)
    self.cardiac_ecg_ii = []    # Lead II (diagonal, primary)
    self.cardiac_ecg_v1 = []    # Precordial V1

    # Metrics history
    self.cardiac_history = {
        'heart_rate': [],
        'conduction_vel': [],
        'apd': [],
        'refractory_frac': [],
        'sa_fires': [],
        'av_conducted': [],
        'mean_voltage': [],
        'max_voltage': [],
        'active_cells': [],
        'defib_shocks': [],
    }

    # Beat detection for HR calculation
    self.cardiac_last_beat_tick = 0
    self.cardiac_beat_intervals = []
    self.cardiac_sa_fire_count = 0
    self.cardiac_av_conduct_count = 0

    # Build anatomy
    _cardiac_build_anatomy(self, pid, rows, cols)
    self._flash(f"Cardiac: {name}")


def _cardiac_build_anatomy(self, pid, rows, cols):
    """Lay out heart tissue, conduction system, and preset-specific features."""
    tissue = self.cardiac_tissue
    diff = self.cardiac_diff
    V = self.cardiac_V

    # Define atrial region (top 40%) and ventricular region (bottom 55%)
    atrial_bottom = int(rows * 0.38)
    av_row = int(rows * 0.40)
    his_top = int(rows * 0.42)
    his_bottom = int(rows * 0.52)
    vent_top = int(rows * 0.45)

    # Atrial tissue — upper region, shaped as two chambers
    mid_c = cols // 2
    for r in range(1, atrial_bottom):
        # Left atrium
        la_left = max(1, mid_c - int((cols * 0.4)))
        la_right = mid_c - 1
        for c in range(la_left, la_right):
            tissue[r][c] = TISSUE_ATRIAL
            diff[r][c] = _DIFF_NORMAL
        # Right atrium
        ra_left = mid_c + 1
        ra_right = min(cols - 1, mid_c + int((cols * 0.4)))
        for c in range(ra_left, ra_right):
            tissue[r][c] = TISSUE_ATRIAL
            diff[r][c] = _DIFF_NORMAL

    # SA node — top right atrium
    sa_r = max(2, rows // 8)
    sa_c = mid_c + int(cols * 0.25)
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            rr, cc = sa_r + dr, sa_c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                tissue[rr][cc] = TISSUE_SA_NODE
                diff[rr][cc] = _DIFF_NORMAL
    self.cardiac_sa_r = sa_r
    self.cardiac_sa_c = sa_c

    # AV node — junction between atria and ventricles, near septum
    av_c = mid_c
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            rr, cc = av_row + dr, av_c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                tissue[rr][cc] = TISSUE_AV_NODE
                diff[rr][cc] = _DIFF_AV_DELAY
    self.cardiac_av_r = av_row
    self.cardiac_av_c = av_c

    # Bundle of His — runs down the septum
    for r in range(his_top, his_bottom):
        tissue[r][mid_c] = TISSUE_HIS
        diff[r][mid_c] = _DIFF_HIS
        if mid_c + 1 < cols:
            tissue[r][mid_c + 1] = TISSUE_HIS
            diff[r][mid_c + 1] = _DIFF_HIS

    # Purkinje fibers — branch left and right from bottom of His bundle
    purk_r = his_bottom
    # Left bundle branch
    for i in range(1, min(int(cols * 0.35), cols - mid_c)):
        r_off = purk_r + i // 3
        c_off = mid_c - i
        if 0 <= r_off < rows and 0 <= c_off < cols:
            tissue[r_off][c_off] = TISSUE_PURKINJE
            diff[r_off][c_off] = _DIFF_PURKINJE
    # Right bundle branch
    for i in range(1, min(int(cols * 0.35), cols - mid_c)):
        r_off = purk_r + i // 3
        c_off = mid_c + i
        if 0 <= r_off < rows and 0 <= c_off < cols:
            tissue[r_off][c_off] = TISSUE_PURKINJE
            diff[r_off][c_off] = _DIFF_PURKINJE

    # Ventricular tissue — lower region, two chambers
    for r in range(vent_top, rows - 1):
        # Wall thickness varies: thicker at apex
        span = int(cols * 0.38 * (1.0 - 0.3 * abs(r - (vent_top + rows - 1) // 2) / max(1, (rows - 1 - vent_top) // 2)))
        span = max(4, span)
        # Left ventricle
        for c in range(max(1, mid_c - span), mid_c - 1):
            if tissue[r][c] == TISSUE_EMPTY:
                tissue[r][c] = TISSUE_VENTRICULAR
                diff[r][c] = _DIFF_NORMAL
        # Right ventricle
        for c in range(mid_c + 2, min(cols - 1, mid_c + span)):
            if tissue[r][c] == TISSUE_EMPTY:
                tissue[r][c] = TISSUE_VENTRICULAR
                diff[r][c] = _DIFF_NORMAL

    # Preset-specific modifications
    if pid == "afib":
        # Multiple random ectopic foci in atria
        self.cardiac_afib_foci = []
        for _ in range(6):
            fr = random.randint(2, atrial_bottom - 2)
            fc = random.randint(max(2, mid_c - int(cols * 0.35)),
                                min(cols - 3, mid_c + int(cols * 0.35)))
            if tissue[fr][fc] == TISSUE_ATRIAL:
                self.cardiac_afib_foci.append((fr, fc))
        self.cardiac_sa_period = _SA_PERIOD  # SA still fires but overwhelmed

    elif pid == "vtach":
        # Create scar tissue in ventricle to anchor re-entry
        scar_r = (vent_top + rows - 1) // 2
        scar_c = mid_c - int(cols * 0.15)
        for dr in range(-3, 4):
            for dc in range(-2, 8):
                rr, cc = scar_r + dr, scar_c + dc
                if 0 <= rr < rows and 0 <= cc < cols and tissue[rr][cc] == TISSUE_VENTRICULAR:
                    tissue[rr][cc] = TISSUE_SCAR
                    diff[rr][cc] = _DIFF_SCAR
        # Initiate a spiral by pre-exciting a wavefront near scar
        for dc in range(8, 18):
            cc = scar_c + dc
            if 0 <= cc < cols and tissue[scar_r][cc] == TISSUE_VENTRICULAR:
                V[scar_r][cc] = 1.5
                self.cardiac_refract[scar_r][cc] = 8

    elif pid == "avblock":
        # AV node conducts only ~50% of beats (2nd degree Mobitz Type I)
        self.cardiac_av_block_ratio = 0.5
        self.cardiac_av_wenckebach_count = 0
        self.cardiac_av_wenckebach_period = 4  # conduct 3, drop 1

    elif pid == "longqt":
        # Reduced K+ repolarization → prolonged APD
        self.cardiac_k_modifier = 0.4  # K+ channels only 40% effective

    elif pid == "defib":
        # Start with chaotic VFib — random activation across ventricles
        for r in range(vent_top, rows - 1):
            for c in range(1, cols - 1):
                if tissue[r][c] == TISSUE_VENTRICULAR:
                    if random.random() < 0.3:
                        V[r][c] = random.uniform(0.5, 2.0)
                        self.cardiac_W[r][c] = random.uniform(-0.5, 0.5)
                        self.cardiac_refract[r][c] = random.randint(0, 5)
        # Also scramble atria
        for r in range(1, atrial_bottom):
            for c in range(1, cols - 1):
                if tissue[r][c] == TISSUE_ATRIAL:
                    if random.random() < 0.2:
                        V[r][c] = random.uniform(0.3, 1.5)


# ══════════════════════════════════════════════════════════════════════
#  Simulation Step
# ══════════════════════════════════════════════════════════════════════

def _cardiac_step(self):
    """One tick of cardiac electrophysiology simulation."""
    rows = self.cardiac_rows
    cols = self.cardiac_cols
    V = self.cardiac_V
    W = self.cardiac_W
    tissue = self.cardiac_tissue
    diff = self.cardiac_diff
    refract = self.cardiac_refract
    gen = self.cardiac_generation
    pid = self.cardiac_preset_id

    dt = _FHN_DT
    k_mod = self.cardiac_k_modifier

    # --- SA node pacemaker ---
    self.cardiac_sa_phase += 1
    sa_fired = False
    if self.cardiac_sa_phase >= self.cardiac_sa_period:
        self.cardiac_sa_phase = 0
        sa_fired = True
        self.cardiac_sa_fire_count += 1
        # Stimulate SA node cells
        for r in range(rows):
            for c in range(cols):
                if tissue[r][c] == TISSUE_SA_NODE and refract[r][c] <= 0:
                    V[r][c] = max(V[r][c], _SA_CURRENT)

    # --- Atrial fibrillation ectopic foci ---
    if pid == "afib" and hasattr(self, 'cardiac_afib_foci'):
        for (fr, fc) in self.cardiac_afib_foci:
            if random.random() < 0.08:  # rapid irregular firing
                if refract[fr][fc] <= 0:
                    V[fr][fc] = max(V[fr][fc], _SA_CURRENT * 0.9)

    # --- AV node gating ---
    # Check if atrial wavefront reached AV node
    av_r, av_c = self.cardiac_av_r, self.cardiac_av_c
    av_excited = False
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            rr, cc = av_r + dr, av_c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                if tissue[rr][cc] == TISSUE_AV_NODE and V[rr][cc] > 0.8:
                    av_excited = True
                    break

    if av_excited:
        # Queue delayed conduction through AV node
        conduct = True
        if pid == "avblock":
            self.cardiac_av_wenckebach_count = getattr(self, 'cardiac_av_wenckebach_count', 0) + 1
            period = getattr(self, 'cardiac_av_wenckebach_period', 4)
            if self.cardiac_av_wenckebach_count >= period:
                conduct = False  # Drop this beat
                self.cardiac_av_wenckebach_count = 0

        if conduct:
            already_queued = any(abs(t - gen) < _AV_DELAY_TICKS for t in self.cardiac_av_buffer)
            if not already_queued:
                self.cardiac_av_buffer.append(gen + _AV_DELAY_TICKS)
                self.cardiac_av_conduct_count += 1

    # Process AV buffer — activate His bundle after delay
    new_buffer = []
    for fire_tick in self.cardiac_av_buffer:
        if gen >= fire_tick:
            # Stimulate top of His bundle
            mid_c = cols // 2
            his_top = int(rows * 0.42)
            for dr in range(0, 3):
                rr = his_top + dr
                if 0 <= rr < rows:
                    for dc in range(0, 2):
                        cc = mid_c + dc
                        if 0 <= cc < cols and tissue[rr][cc] == TISSUE_HIS and refract[rr][cc] <= 0:
                            V[rr][cc] = max(V[rr][cc], _SA_CURRENT * 0.8)
        else:
            new_buffer.append(fire_tick)
    self.cardiac_av_buffer = new_buffer

    # --- Defibrillation ---
    if self.cardiac_defib_active > 0:
        self.cardiac_defib_active -= 1
        for r in range(rows):
            for c in range(cols):
                if tissue[r][c] != TISSUE_EMPTY and tissue[r][c] != TISSUE_SCAR:
                    V[r][c] = _DEFIB_CURRENT
                    W[r][c] = 0.0
                    refract[r][c] = 15  # force full refractory
        if self.cardiac_defib_active == 0:
            # Reset all to resting
            for r in range(rows):
                for c in range(cols):
                    if tissue[r][c] != TISSUE_EMPTY and tissue[r][c] != TISSUE_SCAR:
                        V[r][c] = 0.0
                        W[r][c] = 0.0
                        refract[r][c] = 20

    # --- FitzHugh-Nagumo + diffusion update ---
    new_V = [[0.0] * cols for _ in range(rows)]
    new_W = [[0.0] * cols for _ in range(rows)]

    active_count = 0

    for r in range(rows):
        for c in range(cols):
            tt = tissue[r][c]
            if tt == TISSUE_EMPTY or tt == TISSUE_SCAR:
                new_V[r][c] = 0.0
                new_W[r][c] = 0.0
                continue

            v = V[r][c]
            w = W[r][c]

            # Ion channel dynamics
            na = self.cardiac_na[r][c]
            ca = self.cardiac_ca[r][c]
            k = self.cardiac_k[r][c]

            # Na+ fast inward: activates rapidly when V > threshold
            if v > 0.3 and refract[r][c] <= 0:
                na = min(1.0, na + 0.3)
            else:
                na = max(0.0, na - 0.15)

            # Ca2+ plateau: activates after Na+, sustains depolarization
            if na > 0.5:
                ca = min(1.0, ca + 0.08)
            else:
                ca = max(0.0, ca - 0.04)

            # K+ repolarization: activates during plateau, drives recovery
            if ca > 0.3:
                k = min(1.0, k + 0.06 * k_mod)
            else:
                k = max(0.0, k - 0.03)

            self.cardiac_na[r][c] = na
            self.cardiac_ca[r][c] = ca
            self.cardiac_k[r][c] = k

            # FHN reaction with ion channel modulation
            i_ion = na * _NA_FAST_BOOST + ca * _CA_PLATEAU - k * _K_REPOL
            dv = v - (v * v * v) / 3.0 - w + i_ion
            dw = _FHN_EPSILON * (v + _FHN_A - _FHN_B * w)

            # Diffusion: sum contributions from neighbors
            d_local = diff[r][c]
            laplacian = 0.0
            for dr, dc in _NEIGHBORS_4:
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols:
                    tt_n = tissue[rr][cc]
                    if tt_n != TISSUE_EMPTY and tt_n != TISSUE_SCAR:
                        d_n = diff[rr][cc]
                        # Use geometric mean of coupling coefficients
                        d_eff = math.sqrt(d_local * d_n) if d_local > 0 and d_n > 0 else 0.0
                        laplacian += d_eff * (V[rr][cc] - v)

            new_v = v + dt * (dv + laplacian)
            new_w = w + dt * dw

            # Clamp voltage
            new_v = max(-2.5, min(3.0, new_v))
            new_w = max(-2.0, min(2.0, new_w))

            new_V[r][c] = new_v
            new_W[r][c] = new_w

            # Track active (depolarized) cells
            if new_v > 0.5:
                active_count += 1

            # Update refractory
            if refract[r][c] > 0:
                refract[r][c] -= 1
            elif v < 0.3 and new_v >= 0.8:
                # Just depolarized — enter refractory
                base_refract = 12
                if pid == "longqt":
                    base_refract = 20  # prolonged APD
                refract[r][c] = base_refract

    self.cardiac_V = new_V
    self.cardiac_W = new_W

    # --- ECG derivation from tissue dipole vectors ---
    _cardiac_compute_ecg(self, rows, cols)

    # --- Beat detection ---
    # Detect ventricular activation wave
    vent_top = int(rows * 0.45)
    vent_mid_r = (vent_top + rows - 1) // 2
    mid_c = cols // 2
    v_probe = new_V[vent_mid_r][mid_c + 5] if mid_c + 5 < cols else 0
    if v_probe > 1.0 and (gen - self.cardiac_last_beat_tick) > 15:
        interval = gen - self.cardiac_last_beat_tick
        self.cardiac_last_beat_tick = gen
        self.cardiac_beat_intervals.append(interval)
        if len(self.cardiac_beat_intervals) > 20:
            self.cardiac_beat_intervals.pop(0)

    # --- Record metrics ---
    _cardiac_record_metrics(self, active_count)

    self.cardiac_generation += 1


def _cardiac_compute_ecg(self, rows, cols):
    """Derive ECG leads from spatial voltage gradient (dipole vectors)."""
    V = self.cardiac_V
    tissue = self.cardiac_tissue

    # Compute net dipole vector from voltage gradients
    dx_total = 0.0
    dy_total = 0.0
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if tissue[r][c] == TISSUE_EMPTY or tissue[r][c] == TISSUE_SCAR:
                continue
            # Gradient approximation
            dvdx = (V[r][c + 1] - V[r][c - 1]) * 0.5
            dvdy = (V[r + 1][c] - V[r - 1][c]) * 0.5
            dx_total += dvdx
            dy_total += dvdy

    # Scale down
    n_cells = max(1, rows * cols * 0.01)
    dx_total /= n_cells
    dy_total /= n_cells

    # Lead I: horizontal (left-right)
    lead_i = dx_total
    # Lead II: ~60° axis (standard limb lead)
    lead_ii = dx_total * 0.5 + dy_total * 0.866
    # V1: precordial, roughly anterior-posterior (use vertical component)
    lead_v1 = -dy_total * 0.7 + dx_total * 0.3

    self.cardiac_ecg_i.append(lead_i)
    self.cardiac_ecg_ii.append(lead_ii)
    self.cardiac_ecg_v1.append(lead_v1)

    # Trim to history length
    if len(self.cardiac_ecg_i) > _ECG_HISTORY_LEN:
        self.cardiac_ecg_i.pop(0)
        self.cardiac_ecg_ii.pop(0)
        self.cardiac_ecg_v1.pop(0)


def _cardiac_record_metrics(self, active_count):
    """Record metrics for sparkline graphs."""
    hist = self.cardiac_history
    gen = self.cardiac_generation

    # Heart rate from beat intervals
    intervals = self.cardiac_beat_intervals
    if intervals:
        avg_interval = sum(intervals) / len(intervals)
        hr = 60.0 / max(0.1, avg_interval * 0.02)  # convert ticks to approx bpm
    else:
        hr = 0.0
    hist['heart_rate'].append(min(300, hr))

    # Conduction velocity proxy: average diffusion of active cells
    rows, cols = self.cardiac_rows, self.cardiac_cols
    total_diff = 0.0
    count = 0
    for r in range(rows):
        for c in range(cols):
            if self.cardiac_V[r][c] > 0.5 and self.cardiac_tissue[r][c] not in (TISSUE_EMPTY, TISSUE_SCAR):
                total_diff += self.cardiac_diff[r][c]
                count += 1
    hist['conduction_vel'].append(total_diff / max(1, count))

    # APD proxy: fraction of cells in refractory
    total_tissue = 0
    total_refract = 0
    for r in range(rows):
        for c in range(cols):
            if self.cardiac_tissue[r][c] not in (TISSUE_EMPTY, TISSUE_SCAR):
                total_tissue += 1
                if self.cardiac_refract[r][c] > 0:
                    total_refract += 1
    refract_frac = total_refract / max(1, total_tissue)
    hist['refractory_frac'].append(refract_frac)
    hist['apd'].append(refract_frac * 20)  # approximate APD in arbitrary units

    # SA fire and AV conduct counts (cumulative per window)
    hist['sa_fires'].append(self.cardiac_sa_fire_count)
    hist['av_conducted'].append(self.cardiac_av_conduct_count)

    # Mean and max voltage
    sum_v = 0.0
    max_v = -10.0
    for r in range(rows):
        for c in range(cols):
            if self.cardiac_tissue[r][c] not in (TISSUE_EMPTY, TISSUE_SCAR):
                v = self.cardiac_V[r][c]
                sum_v += v
                if v > max_v:
                    max_v = v
    hist['mean_voltage'].append(sum_v / max(1, total_tissue))
    hist['max_voltage'].append(max_v)
    hist['active_cells'].append(active_count)
    hist['defib_shocks'].append(self.cardiac_defib_count)

    # Trim histories
    max_hist = 500
    for key in hist:
        if len(hist[key]) > max_hist:
            hist[key] = hist[key][-max_hist:]


# ══════════════════════════════════════════════════════════════════════
#  Key Handlers
# ══════════════════════════════════════════════════════════════════════

def _handle_cardiac_menu_key(self, key: int) -> bool:
    """Handle keys in preset menu."""
    if key == curses.KEY_UP or key == ord('k'):
        self.cardiac_menu_sel = (self.cardiac_menu_sel - 1) % len(CARDIAC_PRESETS)
        return True
    if key == curses.KEY_DOWN or key == ord('j'):
        self.cardiac_menu_sel = (self.cardiac_menu_sel + 1) % len(CARDIAC_PRESETS)
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _cardiac_init(self, self.cardiac_menu_sel)
        self.cardiac_running = True
        return True
    if key == ord('q') or key == 27:
        self._exit_cardiac_mode()
        return True
    return False


def _handle_cardiac_key(self, key: int) -> bool:
    """Handle keys during simulation."""
    if key == ord(' '):
        self.cardiac_running = not self.cardiac_running
        return True
    if key == ord('v'):
        views = ["tissue", "ecg", "graphs"]
        idx = views.index(self.cardiac_view)
        self.cardiac_view = views[(idx + 1) % len(views)]
        return True
    if key == ord('n'):
        # Single step
        _cardiac_step(self)
        return True
    if key == ord('d'):
        # Deliver defibrillation shock
        self.cardiac_defib_active = _DEFIB_DURATION
        self.cardiac_defib_count += 1
        self._flash("⚡ DEFIBRILLATION SHOCK ⚡")
        return True
    if key == ord('+') or key == ord('='):
        self.cardiac_speed = min(8, self.cardiac_speed + 1)
        return True
    if key == ord('-'):
        self.cardiac_speed = max(1, self.cardiac_speed - 1)
        return True
    if key == ord('r'):
        # Restart with same preset
        idx = next((i for i, p in enumerate(CARDIAC_PRESETS) if p[2] == self.cardiac_preset_id), 0)
        _cardiac_init(self, idx)
        self.cardiac_running = True
        return True
    if key == ord('R'):
        self.cardiac_menu = True
        self.cardiac_menu_sel = 0
        return True
    if key == ord('q'):
        self._exit_cardiac_mode()
        return True
    return False


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Preset Menu
# ══════════════════════════════════════════════════════════════════════

def _draw_cardiac_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()
    title = "♥ Cardiac Electrophysiology & Arrhythmia ♥"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD | curses.color_pair(1))
    except curses.error:
        pass

    sub = "Select a cardiac rhythm preset:"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(sub)) // 2), sub)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(CARDIAC_PRESETS):
        y = 5 + i * 3
        if y + 1 >= max_y:
            break
        marker = "▸ " if i == self.cardiac_menu_sel else "  "
        attr = curses.A_REVERSE if i == self.cardiac_menu_sel else 0
        try:
            self.stdscr.addstr(y, 4, f"{marker}{name}", attr | curses.A_BOLD)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(y + 1, 8, desc[:max_x - 10], curses.color_pair(7))
        except curses.error:
            pass

    hint = "[↑/↓] select  [Enter] start  [q] back"
    try:
        self.stdscr.addstr(max_y - 2, max(0, (max_x - len(hint)) // 2), hint,
                           curses.color_pair(7))
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Tissue Activation Map
# ══════════════════════════════════════════════════════════════════════

def _draw_cardiac(self, max_y: int, max_x: int):
    """Dispatch to appropriate view drawer."""
    if self.cardiac_view == "tissue":
        _draw_cardiac_tissue(self, max_y, max_x)
    elif self.cardiac_view == "ecg":
        _draw_cardiac_ecg(self, max_y, max_x)
    elif self.cardiac_view == "graphs":
        _draw_cardiac_graphs(self, max_y, max_x)


def _draw_cardiac_tissue(self, max_y: int, max_x: int):
    """Render tissue activation map with conduction anatomy."""
    self.stdscr.erase()
    rows = self.cardiac_rows
    cols = self.cardiac_cols
    V = self.cardiac_V
    tissue = self.cardiac_tissue
    refract = self.cardiac_refract

    view_h = min(rows, max_y - 3)
    view_w = min(cols, max_x - 1)

    # Voltage-to-color mapping
    # depolarized (high V) = bright red/white, resting = dark blue/black,
    # refractory = magenta/dim, plateau = yellow
    for r in range(view_h):
        for c in range(view_w):
            tt = tissue[r][c]
            if tt == TISSUE_EMPTY:
                continue

            v = V[r][c]
            ref = refract[r][c]

            # Choose glyph and color based on tissue type and voltage state
            if tt == TISSUE_SA_NODE:
                ch = "♥"
                if v > 0.8:
                    cp = curses.color_pair(1) | curses.A_BOLD  # bright red
                else:
                    cp = curses.color_pair(5) | curses.A_DIM
            elif tt == TISSUE_AV_NODE:
                ch = "◆" if v > 0.5 else "◇"
                cp = curses.color_pair(3) | (curses.A_BOLD if v > 0.5 else 0)
            elif tt == TISSUE_HIS:
                ch = "═"
                if v > 0.8:
                    cp = curses.color_pair(3) | curses.A_BOLD
                elif v > 0.3:
                    cp = curses.color_pair(3)
                else:
                    cp = curses.color_pair(7)
            elif tt == TISSUE_PURKINJE:
                ch = "─"
                if v > 0.8:
                    cp = curses.color_pair(2) | curses.A_BOLD
                elif v > 0.3:
                    cp = curses.color_pair(2)
                else:
                    cp = curses.color_pair(7)
            elif tt == TISSUE_SCAR:
                ch = "░"
                cp = curses.color_pair(7) | curses.A_DIM
            else:
                # Atrial or ventricular myocyte
                if v > 1.5:
                    ch = "█"
                    cp = curses.color_pair(1) | curses.A_BOLD  # peak depolarization
                elif v > 0.8:
                    ch = "▓"
                    cp = curses.color_pair(1)  # depolarizing wavefront
                elif v > 0.3:
                    ch = "▒"
                    cp = curses.color_pair(3)  # plateau (Ca2+)
                elif ref > 0:
                    ch = "▒"
                    cp = curses.color_pair(5) | curses.A_DIM  # refractory
                elif v > -0.5:
                    ch = "░"
                    cp = curses.color_pair(4)  # resting
                else:
                    ch = "·"
                    cp = curses.color_pair(7) | curses.A_DIM

            try:
                self.stdscr.addstr(1 + r, c, ch, cp)
            except curses.error:
                pass

    # Status bar
    gen = self.cardiac_generation
    intervals = self.cardiac_beat_intervals
    if intervals:
        hr = 60.0 / max(0.1, (sum(intervals) / len(intervals)) * 0.02)
        hr_str = f"{hr:.0f} bpm"
    else:
        hr_str = "-- bpm"

    status = (f" {self.cardiac_preset_name} | tick {gen} | {hr_str} | "
              f"defib:{self.cardiac_defib_count} | [v]iew [d]efib [space]pause [r]estart [q]uit")
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Legend
    legend = "♥SA ◆AV ═His ─Purk █depol ▒plateau ░rest ░scar"
    try:
        self.stdscr.addstr(max_y - 1, 0, legend[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — ECG Strip
# ══════════════════════════════════════════════════════════════════════

def _draw_cardiac_ecg(self, max_y: int, max_x: int):
    """Render real-time ECG strip with multiple leads."""
    self.stdscr.erase()

    title = f"ECG — {self.cardiac_preset_name} | tick {self.cardiac_generation}"
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD | curses.color_pair(2))
    except curses.error:
        pass

    leads = [
        ("Lead I",  self.cardiac_ecg_i,  1),
        ("Lead II", self.cardiac_ecg_ii, 2),
        ("V1",      self.cardiac_ecg_v1, 3),
    ]

    n_leads = len(leads)
    strip_h = max(5, (max_y - 4) // n_leads)
    strip_w = min(_ECG_HISTORY_LEN, max_x - 14)

    for li, (label, data, cp) in enumerate(leads):
        base_y = 2 + li * strip_h
        mid_y = base_y + strip_h // 2

        if base_y >= max_y - 2:
            break

        # Label
        try:
            self.stdscr.addstr(base_y, 1, label, curses.A_BOLD | curses.color_pair(cp))
        except curses.error:
            pass

        # Draw baseline
        for x in range(12, 12 + strip_w):
            if x >= max_x - 1:
                break
            try:
                self.stdscr.addstr(mid_y, x, "·", curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

        # Draw ECG trace
        if data:
            visible = data[-strip_w:]
            if len(visible) > 1:
                mn = min(visible)
                mx = max(visible)
                rng = mx - mn if mx > mn else 1.0
                half_h = strip_h // 2 - 1

                for i, val in enumerate(visible):
                    x = 12 + i
                    if x >= max_x - 1:
                        break
                    # Map value to y offset from midline
                    norm = (val - (mn + mx) / 2) / (rng / 2) if rng > 0 else 0
                    y_off = int(-norm * half_h)
                    y = mid_y + y_off
                    y = max(base_y, min(base_y + strip_h - 1, y))

                    # Glyph based on amplitude
                    if abs(norm) > 0.7:
                        ch = "█"
                        attr = curses.color_pair(cp) | curses.A_BOLD
                    elif abs(norm) > 0.3:
                        ch = "▌"
                        attr = curses.color_pair(cp)
                    else:
                        ch = "│"
                        attr = curses.color_pair(cp) | curses.A_DIM

                    try:
                        self.stdscr.addstr(y, x, ch, attr)
                    except curses.error:
                        pass

        # Scale markings
        try:
            self.stdscr.addstr(base_y, 8, "▲", curses.color_pair(7))
            self.stdscr.addstr(base_y + strip_h - 1, 8, "▼", curses.color_pair(7))
        except curses.error:
            pass

    # Defibrillation indicator
    if self.cardiac_defib_active > 0:
        shock_msg = "⚡⚡⚡ SHOCK DELIVERED ⚡⚡⚡"
        try:
            self.stdscr.addstr(max_y // 2, max(0, (max_x - len(shock_msg)) // 2),
                               shock_msg, curses.color_pair(1) | curses.A_BOLD | curses.A_BLINK)
        except curses.error:
            pass

    # Status bar
    status = "[v]iew [d]efib [space]pause [r]estart [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Sparkline Graphs View
# ══════════════════════════════════════════════════════════════════════

def _draw_cardiac_graphs(self, max_y: int, max_x: int):
    """Time-series sparkline graphs for cardiac metrics."""
    self.stdscr.erase()
    hist = self.cardiac_history
    graph_w = min(200, max_x - 30)

    title = f"Cardiac Metrics — {self.cardiac_preset_name} | tick {self.cardiac_generation}"
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD)
    except curses.error:
        pass

    labels = [
        ("Heart Rate",       'heart_rate',       1),
        ("Conduction Vel",   'conduction_vel',   2),
        ("APD (approx)",     'apd',              3),
        ("Refractory Frac",  'refractory_frac',  5),
        ("SA Node Fires",    'sa_fires',         1),
        ("AV Conducted",     'av_conducted',     3),
        ("Mean Voltage",     'mean_voltage',     4),
        ("Max Voltage",      'max_voltage',      1),
        ("Active Cells",     'active_cells',     2),
        ("Defib Shocks",     'defib_shocks',     6),
    ]

    bars = "▁▂▃▄▅▆▇█"
    n_bars = len(bars)

    for gi, (label, key, cp) in enumerate(labels):
        base_y = 2 + gi * 2
        if base_y + 1 >= max_y - 2:
            break

        data = hist.get(key, [])
        cur_val = data[-1] if data else 0
        if isinstance(cur_val, float):
            lbl = f"{label}: {cur_val:.3f}"
        else:
            lbl = f"{label}: {cur_val}"
        try:
            self.stdscr.addstr(base_y, 2, lbl[:24],
                               curses.color_pair(cp) | curses.A_BOLD)
        except curses.error:
            pass

        if data:
            visible = data[-graph_w:]
            mn = min(visible)
            mx = max(visible)
            rng = mx - mn if mx > mn else 1.0
            color = curses.color_pair(cp)
            for i, v in enumerate(visible):
                x = 26 + i
                if x >= max_x - 1:
                    break
                idx = int((v - mn) / rng * (n_bars - 1))
                idx = max(0, min(n_bars - 1, idx))
                try:
                    self.stdscr.addstr(base_y, x, bars[idx], color)
                except curses.error:
                    pass

    status = "[v]iew [d]efib [space]pause [r]estart [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register cardiac electrophysiology mode methods on the App class."""
    App.CARDIAC_PRESETS = CARDIAC_PRESETS
    App._enter_cardiac_mode = _enter_cardiac_mode
    App._exit_cardiac_mode = _exit_cardiac_mode
    App._cardiac_init = _cardiac_init
    App._cardiac_step = _cardiac_step
    App._handle_cardiac_menu_key = _handle_cardiac_menu_key
    App._handle_cardiac_key = _handle_cardiac_key
    App._draw_cardiac_menu = _draw_cardiac_menu
    App._draw_cardiac = _draw_cardiac
