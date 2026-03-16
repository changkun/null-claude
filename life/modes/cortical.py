"""Mode: cortical — Cortical Neural Dynamics & Seizure Propagation.

Simulates a 2D cortical sheet with excitatory/inhibitory (E/I) neuron
populations using Wilson-Cowan dynamics.  Models emergent neural oscillations
(theta 4-8 Hz, alpha 8-13 Hz, beta 13-30 Hz, gamma 30-80 Hz), GABAergic
inhibition, STDP synaptic plasticity, focal seizure initiation from E/I
imbalance, seizure wavefront propagation, spreading cortical depression,
and anticonvulsant drug mechanics.

Wilson-Cowan population model:
  tau_E * dE/dt = -E + S(w_EE*E - w_IE*I + I_ext + noise)
  tau_I * dI/dt = -I + S(w_EI*E - w_II*I + noise)
where S(x) = 1/(1+exp(-a*(x-theta))) is a sigmoid transfer function.

Three views:
  1) Cortical activation map — E/I cell coloring with wavefront glyphs
  2) Real-time multi-channel EEG strip with frequency band decomposition
  3) Time-series sparkline graphs — 10 metrics

Six presets:
  Normal Resting State, Gamma Burst Working Memory, Focal Seizure Onset,
  Generalized Tonic-Clonic, Spreading Depression, Drug Intervention
"""
import curses
import math
import random


# ======================================================================
#  Presets
# ======================================================================

CORTICAL_PRESETS = [
    ("Normal Resting State",
     "Alpha-dominant idle cortex — balanced E/I with 8-13 Hz oscillations, low-amplitude background",
     "resting"),
    ("Gamma Burst Working Memory",
     "Task-evoked high-frequency 30-80 Hz gamma oscillations — elevated excitatory drive in focal patch",
     "gamma"),
    ("Focal Seizure Onset",
     "Local E/I collapse — GABA failure in focus zone spreads ictal wavefront outward across cortex",
     "focal"),
    ("Generalized Tonic-Clonic",
     "Whole-cortex hypersynchrony — tonic phase (sustained depol) then clonic phase (rhythmic bursts)",
     "gtc"),
    ("Spreading Depression",
     "Slow depolarization wave (~3 mm/min analog) silencing cortex in its wake — migraine aura model",
     "csd"),
    ("Drug Intervention",
     "Seizure in progress — press 'g' to apply GABAergic anticonvulsant, watch inhibition restore balance",
     "drug"),
]


# ======================================================================
#  Constants
# ======================================================================

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                (0, 1), (1, -1), (1, 0), (1, 1)]

# Wilson-Cowan parameters
_TAU_E = 1.0        # excitatory time constant
_TAU_I = 1.5        # inhibitory time constant (slower)
_DT = 0.25           # integration timestep

# Sigmoid transfer function
_SIG_A = 4.0         # sigmoid gain
_SIG_THETA = 0.25    # sigmoid threshold

# Synaptic weights (defaults — presets modify)
_W_EE = 10.0         # E→E (recurrent excitation)
_W_IE = 12.0         # I→E (inhibition onto excitatory)
_W_EI = 8.0          # E→I (excitation of inhibitory)
_W_II = 3.0          # I→I (mutual inhibition)

# Spatial diffusion (lateral coupling)
_DIFF_E = 0.12       # excitatory lateral spread
_DIFF_I = 0.05       # inhibitory spread (shorter range)

# Noise
_NOISE_E = 0.06      # excitatory noise amplitude
_NOISE_I = 0.02      # inhibitory noise amplitude

# STDP plasticity
_STDP_RATE = 0.001   # learning rate
_STDP_WINDOW = 10    # ticks for spike timing window
_STDP_MAX_W = 16.0   # max weight
_STDP_MIN_W = 2.0    # min weight

# Spreading depression
_CSD_SPEED = 0.04    # CSD wave propagation coefficient
_CSD_DURATION = 60   # ticks of suppression after CSD wave passes
_CSD_RECOVERY = 120  # full recovery ticks

# Drug parameters
_DRUG_DIFFUSION = 0.08     # drug field diffusion rate
_DRUG_DECAY = 0.005        # drug decay per tick
_DRUG_GABA_BOOST = 2.5     # multiplier to inhibitory weights

# EEG
_EEG_CHANNELS = 8    # number of electrode channels
_EEG_HISTORY = 200   # samples to display

# Frequency bands (in ticks — normalized, not real Hz)
_BAND_NAMES = ["delta", "theta", "alpha", "beta", "gamma"]


# ======================================================================
#  Sigmoid transfer function
# ======================================================================

def _sigmoid(x, a=_SIG_A, theta=_SIG_THETA):
    """Sigmoid activation function for Wilson-Cowan model."""
    arg = -a * (x - theta)
    if arg > 50:
        return 0.0
    if arg < -50:
        return 1.0
    return 1.0 / (1.0 + math.exp(arg))


# ======================================================================
#  Enter / Exit
# ======================================================================

def _enter_cortical_mode(self):
    """Enter cortical neural dynamics mode — show preset menu."""
    self.cortical_mode = True
    self.cortical_menu = True
    self.cortical_menu_sel = 0


def _exit_cortical_mode(self):
    """Exit cortical mode."""
    self.cortical_mode = False
    self.cortical_menu = False
    self.cortical_running = False
    for attr in list(vars(self)):
        if attr.startswith('cortical_') and attr not in ('cortical_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ======================================================================
#  Initialization
# ======================================================================

def _cortical_init(self, preset_idx: int):
    """Initialize cortical simulation for chosen preset."""
    name, _desc, pid = CORTICAL_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(16, max_y - 4)
    cols = max(30, max_x - 2)

    self.cortical_menu = False
    self.cortical_running = False
    self.cortical_preset_name = name
    self.cortical_preset_id = pid
    self.cortical_rows = rows
    self.cortical_cols = cols
    self.cortical_generation = 0
    self.cortical_speed = 1
    self.cortical_view = "cortex"  # cortex | eeg | graphs

    # Excitatory and Inhibitory population activity [0,1]
    self.cortical_E = [[0.0] * cols for _ in range(rows)]
    self.cortical_I = [[0.0] * cols for _ in range(rows)]

    # Local synaptic weights (can be modulated by STDP)
    self.cortical_w_ee = [[_W_EE] * cols for _ in range(rows)]
    self.cortical_w_ie = [[_W_IE] * cols for _ in range(rows)]

    # External input field
    self.cortical_I_ext = [[0.0] * cols for _ in range(rows)]

    # Spreading depression state: 0=normal, >0=depressed (countdown)
    self.cortical_csd = [[0] * cols for _ in range(rows)]
    self.cortical_csd_wave = [[0.0] * cols for _ in range(rows)]

    # Drug concentration field
    self.cortical_drug = [[0.0] * cols for _ in range(rows)]
    self.cortical_drug_active = False

    # Seizure zone tracking
    self.cortical_seizure_zone = [[False] * cols for _ in range(rows)]

    # STDP: last spike times for E population
    self.cortical_last_spike_E = [[-999] * cols for _ in range(rows)]

    # Phase tracking for oscillation detection
    self.cortical_phase_acc = [[0.0] * cols for _ in range(rows)]

    # EEG channels — electrodes placed across cortex
    self.cortical_eeg = [[] for _ in range(_EEG_CHANNELS)]
    self.cortical_eeg_electrodes = []  # (row, col) positions
    _cortical_place_electrodes(self, rows, cols)

    # Frequency power estimates per channel
    self.cortical_band_power = {band: [] for band in _BAND_NAMES}

    # Metrics history
    self.cortical_history = {
        'mean_E': [],
        'mean_I': [],
        'ei_ratio': [],
        'synchrony': [],
        'seizure_area': [],
        'alpha_power': [],
        'gamma_power': [],
        'drug_conc': [],
        'csd_area': [],
        'w_ee_mean': [],
    }

    # GTC phase tracking
    self.cortical_gtc_phase = "tonic"  # tonic | clonic
    self.cortical_gtc_tick = 0

    # Apply preset-specific parameters
    _cortical_apply_preset(self, pid, rows, cols)
    self._flash(f"Cortical: {name}")


def _cortical_place_electrodes(self, rows, cols):
    """Place EEG electrode positions across cortex."""
    self.cortical_eeg_electrodes = []
    n = _EEG_CHANNELS
    for i in range(n):
        r = int(rows * (0.15 + 0.7 * (i // 2) / max(1, (n // 2 - 1))))
        c = int(cols * (0.25 if i % 2 == 0 else 0.75))
        r = min(r, rows - 2)
        c = min(c, cols - 2)
        self.cortical_eeg_electrodes.append((r, c))


def _cortical_apply_preset(self, pid, rows, cols):
    """Configure preset-specific parameters."""
    E = self.cortical_E
    I = self.cortical_I

    # Small random initial activity everywhere
    for r in range(rows):
        for c in range(cols):
            E[r][c] = random.uniform(0.01, 0.08)
            I[r][c] = random.uniform(0.01, 0.06)

    if pid == "resting":
        # Balanced E/I → alpha oscillations emerge naturally
        # Slightly elevated tonic input to sustain oscillations
        for r in range(rows):
            for c in range(cols):
                self.cortical_I_ext[r][c] = 0.15 + random.uniform(-0.02, 0.02)

    elif pid == "gamma":
        # Focal high-frequency drive in a central patch
        cr, cc = rows // 2, cols // 2
        radius = min(rows, cols) // 6
        for r in range(rows):
            for c in range(cols):
                dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
                if dist < radius:
                    self.cortical_I_ext[r][c] = 0.45 + random.uniform(-0.02, 0.02)
                    self.cortical_w_ee[r][c] = _W_EE * 1.3
                else:
                    self.cortical_I_ext[r][c] = 0.12 + random.uniform(-0.02, 0.02)

    elif pid == "focal":
        # Seizure focus: reduced inhibition in one zone
        focus_r = rows // 3
        focus_c = cols // 3
        focus_radius = min(rows, cols) // 8
        for r in range(rows):
            for c in range(cols):
                self.cortical_I_ext[r][c] = 0.15
                dist = math.sqrt((r - focus_r) ** 2 + (c - focus_c) ** 2)
                if dist < focus_radius:
                    # GABA failure — reduced inhibition, increased excitation
                    self.cortical_w_ie[r][c] = _W_IE * 0.25
                    self.cortical_w_ee[r][c] = _W_EE * 1.6
                    self.cortical_I_ext[r][c] = 0.5
                    E[r][c] = 0.6
                    self.cortical_seizure_zone[r][c] = True

    elif pid == "gtc":
        # Generalized: whole cortex with E/I imbalance
        for r in range(rows):
            for c in range(cols):
                self.cortical_w_ie[r][c] = _W_IE * 0.35
                self.cortical_w_ee[r][c] = _W_EE * 1.5
                self.cortical_I_ext[r][c] = 0.4 + random.uniform(-0.05, 0.05)
                E[r][c] = random.uniform(0.3, 0.7)
        self.cortical_gtc_phase = "tonic"
        self.cortical_gtc_tick = 0

    elif pid == "csd":
        # Spreading depression: seed a depolarization wave at one edge
        for r in range(rows):
            for c in range(cols):
                self.cortical_I_ext[r][c] = 0.15
        # Seed CSD at left edge
        for r in range(rows // 4, 3 * rows // 4):
            for c in range(0, 3):
                self.cortical_csd_wave[r][c] = 1.0
                E[r][c] = 0.95
                I[r][c] = 0.05

    elif pid == "drug":
        # Seizure in progress — focal onset, drug not yet applied
        focus_r = rows // 2
        focus_c = cols // 2
        focus_radius = min(rows, cols) // 5
        for r in range(rows):
            for c in range(cols):
                self.cortical_I_ext[r][c] = 0.18
                dist = math.sqrt((r - focus_r) ** 2 + (c - focus_c) ** 2)
                if dist < focus_radius:
                    self.cortical_w_ie[r][c] = _W_IE * 0.2
                    self.cortical_w_ee[r][c] = _W_EE * 1.7
                    self.cortical_I_ext[r][c] = 0.55
                    E[r][c] = random.uniform(0.5, 0.9)
                    self.cortical_seizure_zone[r][c] = True


# ======================================================================
#  Simulation Step
# ======================================================================

def _cortical_step(self):
    """One tick of cortical neural dynamics simulation."""
    rows = self.cortical_rows
    cols = self.cortical_cols
    E = self.cortical_E
    I = self.cortical_I
    w_ee = self.cortical_w_ee
    w_ie = self.cortical_w_ie
    I_ext = self.cortical_I_ext
    csd = self.cortical_csd
    csd_wave = self.cortical_csd_wave
    drug = self.cortical_drug
    gen = self.cortical_generation
    pid = self.cortical_preset_id
    dt = _DT

    new_E = [[0.0] * cols for _ in range(rows)]
    new_I = [[0.0] * cols for _ in range(rows)]

    # --- GTC phase transitions ---
    if pid == "gtc":
        self.cortical_gtc_tick += 1
        if self.cortical_gtc_phase == "tonic" and self.cortical_gtc_tick > 80:
            self.cortical_gtc_phase = "clonic"
            self.cortical_gtc_tick = 0
        elif self.cortical_gtc_phase == "clonic" and self.cortical_gtc_tick > 200:
            # Post-ictal
            self.cortical_gtc_phase = "postictal"

    # --- Drug diffusion and decay ---
    if self.cortical_drug_active:
        new_drug = [[0.0] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                d = drug[r][c]
                # Diffusion
                lap = 0.0
                for dr, dc in _NEIGHBORS_4:
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        lap += drug[rr][cc] - d
                new_drug[r][c] = max(0.0, d + _DRUG_DIFFUSION * lap - _DRUG_DECAY * d)
        self.cortical_drug = new_drug
        drug = new_drug

    # --- Spreading depression propagation ---
    if pid == "csd":
        new_csd_wave = [[0.0] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                w = csd_wave[r][c]
                if csd[r][c] > 0:
                    csd[r][c] -= 1
                    new_csd_wave[r][c] = 0.0
                    continue
                lap = 0.0
                for dr, dc in _NEIGHBORS_4:
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        lap += csd_wave[rr][cc] - w
                nw = w + _CSD_SPEED * lap
                if nw > 0.5 and csd[r][c] == 0 and w < 0.5:
                    # CSD wave just arrived — begin depression
                    csd[r][c] = _CSD_DURATION
                new_csd_wave[r][c] = max(0.0, min(1.0, nw))
        self.cortical_csd_wave = new_csd_wave
        csd_wave = new_csd_wave

    # --- Wilson-Cowan dynamics + lateral coupling ---
    seizure_count = 0
    csd_count = 0

    for r in range(rows):
        for c in range(cols):
            e = E[r][c]
            i_val = I[r][c]

            # CSD suppression
            if csd[r][c] > 0:
                # Depressed — minimal activity, slow recovery
                recovery = 1.0 - (csd[r][c] / _CSD_DURATION)
                new_E[r][c] = e * 0.85 * (0.1 + 0.9 * recovery)
                new_I[r][c] = i_val * 0.85 * (0.1 + 0.9 * recovery)
                csd_count += 1
                continue

            # Drug effect: boost inhibitory weights
            drug_level = drug[r][c]
            local_w_ie = w_ie[r][c]
            if drug_level > 0.01:
                local_w_ie *= (1.0 + drug_level * _DRUG_GABA_BOOST)

            local_w_ee = w_ee[r][c]

            # GTC clonic: oscillate external input
            local_I_ext = I_ext[r][c]
            if pid == "gtc" and self.cortical_gtc_phase == "clonic":
                burst = 0.3 * math.sin(gen * 0.3)
                local_I_ext += max(0, burst)
            elif pid == "gtc" and self.cortical_gtc_phase == "postictal":
                local_I_ext *= 0.3  # post-ictal suppression

            # Lateral excitatory coupling (diffusion)
            e_lap = 0.0
            i_lap = 0.0
            for dr, dc in _NEIGHBORS_4:
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols:
                    if csd[rr][cc] == 0:
                        e_lap += E[rr][cc] - e
                        i_lap += I[rr][cc] - i_val

            # Noise
            noise_e = random.gauss(0, _NOISE_E)
            noise_i = random.gauss(0, _NOISE_I)

            # Wilson-Cowan equations
            se_input = local_w_ee * e - local_w_ie * i_val + local_I_ext + noise_e
            si_input = _W_EI * e - _W_II * i_val + noise_i

            se = _sigmoid(se_input)
            si = _sigmoid(si_input)

            de = (-e + se) / _TAU_E
            di = (-i_val + si) / _TAU_I

            # Add lateral coupling
            de += _DIFF_E * e_lap
            di += _DIFF_I * i_lap

            new_e = e + dt * de
            new_i = i_val + dt * di

            # Clamp
            new_e = max(0.0, min(1.0, new_e))
            new_i = max(0.0, min(1.0, new_i))

            new_E[r][c] = new_e
            new_I[r][c] = new_i

            # STDP: if E just "spiked" (crossed threshold upward)
            if new_e > 0.7 and e <= 0.7:
                self.cortical_last_spike_E[r][c] = gen

            # Seizure detection: high E, low I ratio
            if new_e > 0.7 and new_i < 0.3:
                seizure_count += 1
                # Seizure spreading: increase E/I imbalance in neighbors
                if pid in ("focal", "drug"):
                    for dr, dc in _NEIGHBORS_8:
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < rows and 0 <= cc < cols:
                            if not self.cortical_seizure_zone[rr][cc]:
                                if random.random() < 0.008:
                                    self.cortical_seizure_zone[rr][cc] = True
                                    w_ie[rr][cc] *= 0.7
                                    w_ee[rr][cc] *= 1.15

    self.cortical_E = new_E
    self.cortical_I = new_I

    # --- STDP weight update (sparse, every 5 ticks) ---
    if gen % 5 == 0:
        _cortical_stdp_update(self, gen, rows, cols)

    # --- EEG recording ---
    _cortical_record_eeg(self, rows, cols)

    # --- Record metrics ---
    _cortical_record_metrics(self, seizure_count, csd_count)

    self.cortical_generation += 1


def _cortical_stdp_update(self, gen, rows, cols):
    """Spike-timing dependent plasticity update for w_ee."""
    w_ee = self.cortical_w_ee
    last_spike = self.cortical_last_spike_E
    for r in range(0, rows, 3):  # sample every 3rd cell for performance
        for c in range(0, cols, 3):
            t_post = last_spike[r][c]
            if gen - t_post > _STDP_WINDOW:
                continue
            for dr, dc in _NEIGHBORS_4:
                rr, cc = r + dr, c + dc
                if 0 <= rr < rows and 0 <= cc < cols:
                    t_pre = last_spike[rr][cc]
                    dt_spike = t_post - t_pre
                    if 0 < dt_spike < _STDP_WINDOW:
                        # Pre before post → potentiation
                        dw = _STDP_RATE * math.exp(-dt_spike / _STDP_WINDOW)
                        w_ee[r][c] = min(_STDP_MAX_W, w_ee[r][c] + dw)
                    elif -_STDP_WINDOW < dt_spike < 0:
                        # Post before pre → depression
                        dw = _STDP_RATE * math.exp(dt_spike / _STDP_WINDOW)
                        w_ee[r][c] = max(_STDP_MIN_W, w_ee[r][c] - dw)


def _cortical_record_eeg(self, rows, cols):
    """Record EEG from electrode positions — sum local field potential."""
    E = self.cortical_E
    I = self.cortical_I
    radius = 3  # spatial averaging radius

    for ch, (er, ec) in enumerate(self.cortical_eeg_electrodes):
        # LFP = sum of excitatory - inhibitory activity in neighborhood
        lfp = 0.0
        count = 0
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                rr, cc = er + dr, ec + dc
                if 0 <= rr < rows and 0 <= cc < cols:
                    lfp += E[rr][cc] - 0.5 * I[rr][cc]
                    count += 1
        if count > 0:
            lfp /= count
        self.cortical_eeg[ch].append(lfp)
        if len(self.cortical_eeg[ch]) > _EEG_HISTORY:
            self.cortical_eeg[ch].pop(0)

    # Band power estimation (simple variance-based proxy)
    # Uses differences at different lag scales as frequency proxy
    if len(self.cortical_eeg[0]) > 20:
        ref = self.cortical_eeg[0]
        n = len(ref)
        # Delta: lag 8-16, Theta: lag 5-8, Alpha: lag 3-5, Beta: lag 2-3, Gamma: lag 1
        band_lags = {"delta": (8, 16), "theta": (5, 8), "alpha": (3, 5),
                     "beta": (2, 3), "gamma": (1, 2)}
        for band, (lo, hi) in band_lags.items():
            power = 0.0
            cnt = 0
            for lag in range(lo, min(hi + 1, n)):
                for j in range(max(0, n - 20), n - lag):
                    diff = ref[j + lag] - ref[j]
                    power += diff * diff
                    cnt += 1
            power = power / max(1, cnt)
            self.cortical_band_power[band].append(power)
            if len(self.cortical_band_power[band]) > 500:
                self.cortical_band_power[band] = self.cortical_band_power[band][-500:]


def _cortical_record_metrics(self, seizure_count, csd_count):
    """Record metrics for sparkline graphs."""
    hist = self.cortical_history
    rows = self.cortical_rows
    cols = self.cortical_cols
    E = self.cortical_E
    I = self.cortical_I

    total = rows * cols
    sum_e = 0.0
    sum_i = 0.0
    sum_sync = 0.0

    for r in range(rows):
        for c in range(cols):
            sum_e += E[r][c]
            sum_i += I[r][c]

    mean_e = sum_e / total
    mean_i = sum_i / total

    # Synchrony: variance of E (high variance = desynchronized, low = hypersync)
    var_e = 0.0
    for r in range(0, rows, 2):
        for c in range(0, cols, 2):
            d = E[r][c] - mean_e
            var_e += d * d
    var_e /= max(1, (rows // 2) * (cols // 2))
    # Invert: low variance = high synchrony
    synchrony = max(0.0, 1.0 - math.sqrt(var_e) * 5)

    hist['mean_E'].append(mean_e)
    hist['mean_I'].append(mean_i)
    hist['ei_ratio'].append(mean_e / max(0.001, mean_i))
    hist['synchrony'].append(synchrony)
    hist['seizure_area'].append(seizure_count / max(1, total) * 100)

    # Band powers
    bp = self.cortical_band_power
    hist['alpha_power'].append(bp['alpha'][-1] if bp['alpha'] else 0)
    hist['gamma_power'].append(bp['gamma'][-1] if bp['gamma'] else 0)

    # Drug concentration
    drug_sum = 0.0
    for r in range(rows):
        for c in range(cols):
            drug_sum += self.cortical_drug[r][c]
    hist['drug_conc'].append(drug_sum / total)

    hist['csd_area'].append(csd_count / max(1, total) * 100)

    # Mean w_ee
    w_sum = 0.0
    for r in range(0, rows, 3):
        for c in range(0, cols, 3):
            w_sum += self.cortical_w_ee[r][c]
    hist['w_ee_mean'].append(w_sum / max(1, (rows // 3) * (cols // 3)))

    # Trim
    max_hist = 500
    for key in hist:
        if len(hist[key]) > max_hist:
            hist[key] = hist[key][-max_hist:]


# ======================================================================
#  Key Handlers
# ======================================================================

def _handle_cortical_menu_key(self, key: int) -> bool:
    """Handle keys in preset menu."""
    if key == curses.KEY_UP or key == ord('k'):
        self.cortical_menu_sel = (self.cortical_menu_sel - 1) % len(CORTICAL_PRESETS)
        return True
    if key == curses.KEY_DOWN or key == ord('j'):
        self.cortical_menu_sel = (self.cortical_menu_sel + 1) % len(CORTICAL_PRESETS)
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _cortical_init(self, self.cortical_menu_sel)
        self.cortical_running = True
        return True
    if key == ord('q') or key == 27:
        self._exit_cortical_mode()
        return True
    return False


def _handle_cortical_key(self, key: int) -> bool:
    """Handle keys during simulation."""
    if key == ord(' '):
        self.cortical_running = not self.cortical_running
        return True
    if key == ord('v'):
        views = ["cortex", "eeg", "graphs"]
        idx = views.index(self.cortical_view)
        self.cortical_view = views[(idx + 1) % len(views)]
        return True
    if key == ord('n'):
        _cortical_step(self)
        return True
    if key == ord('g'):
        # Apply GABAergic anticonvulsant drug
        _cortical_apply_drug(self)
        return True
    if key == ord('+') or key == ord('='):
        self.cortical_speed = min(8, self.cortical_speed + 1)
        return True
    if key == ord('-'):
        self.cortical_speed = max(1, self.cortical_speed - 1)
        return True
    if key == ord('r'):
        idx = next((i for i, p in enumerate(CORTICAL_PRESETS) if p[2] == self.cortical_preset_id), 0)
        _cortical_init(self, idx)
        self.cortical_running = True
        return True
    if key == ord('R'):
        self.cortical_menu = True
        self.cortical_menu_sel = 0
        return True
    if key == ord('q'):
        self._exit_cortical_mode()
        return True
    return False


def _cortical_apply_drug(self):
    """Apply GABAergic anticonvulsant — flood drug field from center."""
    rows = self.cortical_rows
    cols = self.cortical_cols
    cr, cc = rows // 2, cols // 2
    max_dist = math.sqrt(cr * cr + cc * cc)

    for r in range(rows):
        for c in range(cols):
            dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
            self.cortical_drug[r][c] = max(self.cortical_drug[r][c],
                                           max(0, 1.0 - dist / max_dist))
    self.cortical_drug_active = True
    self._flash("GABAergic anticonvulsant applied")


# ======================================================================
#  Drawing — Preset Menu
# ======================================================================

def _draw_cortical_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()
    title = "Cortical Neural Dynamics & Seizure Propagation"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass

    sub = "Select a cortical dynamics preset:"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(sub)) // 2), sub)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(CORTICAL_PRESETS):
        y = 5 + i * 3
        if y + 1 >= max_y:
            break
        marker = ">" if i == self.cortical_menu_sel else "  "
        attr = curses.A_REVERSE if i == self.cortical_menu_sel else 0
        try:
            self.stdscr.addstr(y, 4, f"{marker}{name}", attr | curses.A_BOLD)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(y + 1, 8, desc[:max_x - 10], curses.color_pair(7))
        except curses.error:
            pass

    hint = "[up/dn] select  [Enter] start  [q] back"
    try:
        self.stdscr.addstr(max_y - 2, max(0, (max_x - len(hint)) // 2), hint,
                           curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Cortical Activation Map
# ======================================================================

def _draw_cortical(self, max_y: int, max_x: int):
    """Dispatch to appropriate view drawer."""
    if self.cortical_view == "cortex":
        _draw_cortical_cortex(self, max_y, max_x)
    elif self.cortical_view == "eeg":
        _draw_cortical_eeg(self, max_y, max_x)
    elif self.cortical_view == "graphs":
        _draw_cortical_graphs(self, max_y, max_x)


def _draw_cortical_cortex(self, max_y: int, max_x: int):
    """Render cortical activation map with E/I cell coloring."""
    self.stdscr.erase()
    rows = self.cortical_rows
    cols = self.cortical_cols
    E = self.cortical_E
    I = self.cortical_I
    csd = self.cortical_csd
    drug = self.cortical_drug
    seizure = self.cortical_seizure_zone

    view_h = min(rows, max_y - 3)
    view_w = min(cols, max_x - 1)

    for r in range(view_h):
        for c in range(view_w):
            e = E[r][c]
            i_val = I[r][c]

            # CSD: dark suppressed zone
            if csd[r][c] > 0:
                if csd[r][c] > _CSD_DURATION * 0.7:
                    ch = "~"
                    cp = curses.color_pair(5) | curses.A_BOLD  # wave front
                else:
                    ch = "."
                    cp = curses.color_pair(7) | curses.A_DIM  # suppressed
                try:
                    self.stdscr.addstr(1 + r, c, ch, cp)
                except curses.error:
                    pass
                continue

            # Drug presence overlay
            d = drug[r][c]

            # Color by E/I balance and activity level
            if e > 0.8:
                # High excitation — seizure-level
                ch = "#"
                cp = curses.color_pair(1) | curses.A_BOLD  # bright red
            elif e > 0.6:
                # Strong excitatory
                ch = "E" if i_val < 0.3 else "%"
                cp = curses.color_pair(1)  # red
            elif e > 0.4:
                # Moderate activity
                if i_val > 0.5:
                    ch = "I"
                    cp = curses.color_pair(4) | curses.A_BOLD  # blue = inhibitory
                elif i_val > 0.3:
                    ch = "+"
                    cp = curses.color_pair(3)  # yellow = balanced
                else:
                    ch = "e"
                    cp = curses.color_pair(3) | curses.A_DIM
            elif e > 0.2:
                # Low activity
                ch = ":"
                cp = curses.color_pair(4) if i_val > e else curses.color_pair(7)
            else:
                # Near resting
                ch = "."
                cp = curses.color_pair(7) | curses.A_DIM

            # Drug overlay: green tint
            if d > 0.3:
                cp = curses.color_pair(2) | (curses.A_BOLD if d > 0.6 else 0)

            # Seizure zone marker
            if seizure[r][c] and e > 0.5:
                ch = "!" if e > 0.7 else "*"
                if d < 0.2:
                    cp = curses.color_pair(1) | curses.A_BOLD | curses.A_BLINK

            try:
                self.stdscr.addstr(1 + r, c, ch, cp)
            except curses.error:
                pass

    # Electrode positions
    for ch_idx, (er, ec) in enumerate(self.cortical_eeg_electrodes):
        if er < view_h and ec < view_w:
            try:
                self.stdscr.addstr(1 + er, ec, "o",
                                   curses.color_pair(6) | curses.A_BOLD)
            except curses.error:
                pass

    # Status bar
    gen = self.cortical_generation
    hist = self.cortical_history
    ei = hist['ei_ratio'][-1] if hist['ei_ratio'] else 0
    sz = hist['seizure_area'][-1] if hist['seizure_area'] else 0

    phase_str = ""
    if self.cortical_preset_id == "gtc":
        phase_str = f" | phase:{self.cortical_gtc_phase}"
    drug_str = " | DRUG" if self.cortical_drug_active else ""

    status = (f" {self.cortical_preset_name} | tick {gen} | E/I:{ei:.2f} | "
              f"seizure:{sz:.1f}%{phase_str}{drug_str} | "
              f"[v]iew [g]ABA [space]pause [r]estart [q]uit")
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    legend = "#E:excit I:inhib +:balanced .:rest ~:CSD !:seizure o:electrode"
    try:
        self.stdscr.addstr(max_y - 1, 0, legend[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — EEG Strip
# ======================================================================

def _draw_cortical_eeg(self, max_y: int, max_x: int):
    """Render multi-channel EEG strip with frequency band decomposition."""
    self.stdscr.erase()

    title = f"EEG -- {self.cortical_preset_name} | tick {self.cortical_generation}"
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass

    n_ch = _EEG_CHANNELS
    strip_h = max(3, (max_y - 6) // n_ch)
    strip_w = min(_EEG_HISTORY, max_x - 14)

    ch_labels = [f"Ch{i+1}" for i in range(n_ch)]
    cp_cycle = [1, 2, 3, 4, 5, 6, 1, 2]

    for ch in range(n_ch):
        base_y = 2 + ch * strip_h
        mid_y = base_y + strip_h // 2

        if base_y >= max_y - 3:
            break

        cp = curses.color_pair(cp_cycle[ch % len(cp_cycle)])

        # Label
        try:
            self.stdscr.addstr(base_y, 1, ch_labels[ch], curses.A_BOLD | cp)
        except curses.error:
            pass

        # Baseline
        for x in range(8, 8 + strip_w):
            if x >= max_x - 1:
                break
            try:
                self.stdscr.addstr(mid_y, x, "-", curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

        # EEG trace
        data = self.cortical_eeg[ch] if ch < len(self.cortical_eeg) else []
        if len(data) > 1:
            visible = data[-strip_w:]
            mn = min(visible)
            mx = max(visible)
            rng = mx - mn if mx > mn else 0.001
            half_h = max(1, strip_h // 2 - 1)

            for j, val in enumerate(visible):
                x = 8 + j
                if x >= max_x - 1:
                    break
                norm = (val - (mn + mx) / 2) / (rng / 2) if rng > 0 else 0
                y_off = int(-norm * half_h)
                y = mid_y + y_off
                y = max(base_y, min(base_y + strip_h - 1, y))

                if abs(norm) > 0.7:
                    glyph = "|"
                    attr = cp | curses.A_BOLD
                elif abs(norm) > 0.3:
                    glyph = ":"
                    attr = cp
                else:
                    glyph = "."
                    attr = cp | curses.A_DIM

                try:
                    self.stdscr.addstr(y, x, glyph, attr)
                except curses.error:
                    pass

    # Band power bar at bottom
    bp = self.cortical_band_power
    bar_y = max_y - 3
    if bar_y > 2 + n_ch * strip_h:
        band_colors = {"delta": 5, "theta": 4, "alpha": 2, "beta": 3, "gamma": 1}
        x_off = 2
        for band in _BAND_NAMES:
            vals = bp.get(band, [])
            pwr = vals[-1] if vals else 0.0
            bar_len = min(15, int(pwr * 300))
            label = f"{band:>6}:"
            try:
                self.stdscr.addstr(bar_y, x_off, label,
                                   curses.color_pair(band_colors.get(band, 7)))
                bar_str = "|" * bar_len
                self.stdscr.addstr(bar_y, x_off + 7, bar_str,
                                   curses.color_pair(band_colors.get(band, 7)) | curses.A_BOLD)
            except curses.error:
                pass
            x_off += 24
            if x_off + 24 >= max_x:
                break

    # Status
    status = "[v]iew [g]ABA [space]pause [r]estart [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Sparkline Graphs View
# ======================================================================

def _draw_cortical_graphs(self, max_y: int, max_x: int):
    """Time-series sparkline graphs for cortical metrics."""
    self.stdscr.erase()
    hist = self.cortical_history
    graph_w = min(200, max_x - 30)

    title = f"Cortical Metrics -- {self.cortical_preset_name} | tick {self.cortical_generation}"
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD)
    except curses.error:
        pass

    labels = [
        ("Mean Excitatory",  'mean_E',        1),
        ("Mean Inhibitory",  'mean_I',        4),
        ("E/I Ratio",        'ei_ratio',      3),
        ("Synchrony",        'synchrony',     5),
        ("Seizure Area %",   'seizure_area',  1),
        ("Alpha Power",      'alpha_power',   2),
        ("Gamma Power",      'gamma_power',   6),
        ("Drug Conc",        'drug_conc',     2),
        ("CSD Area %",       'csd_area',      5),
        ("Mean w_EE",        'w_ee_mean',     3),
    ]

    bars = " _.,:-=!#%@"
    n_bars = len(bars) - 1

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
                idx = int((v - mn) / rng * n_bars)
                idx = max(0, min(n_bars, idx))
                try:
                    self.stdscr.addstr(base_y, x, bars[idx], color)
                except curses.error:
                    pass

    status = "[v]iew [g]ABA [space]pause [r]estart [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Registration
# ======================================================================

def register(App):
    """Register cortical neural dynamics mode methods on the App class."""
    App.CORTICAL_PRESETS = CORTICAL_PRESETS
    App._enter_cortical_mode = _enter_cortical_mode
    App._exit_cortical_mode = _exit_cortical_mode
    App._cortical_init = _cortical_init
    App._cortical_step = _cortical_step
    App._handle_cortical_menu_key = _handle_cortical_menu_key
    App._handle_cortical_key = _handle_cortical_key
    App._draw_cortical_menu = _draw_cortical_menu
    App._draw_cortical = _draw_cortical
