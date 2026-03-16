"""Mode: tokamak — Tokamak Fusion Plasma Confinement.

Simulates a toroidal cross-section (poloidal plane) of magnetically confined
hydrogen plasma in a tokamak fusion reactor.  Particle-in-cell dynamics track
ion and electron populations on nested magnetic flux surfaces created by the
superposition of toroidal (out-of-plane) and poloidal (in-plane) magnetic fields.

Physics modeled:
  - Magnetic topology: toroidal field ~ 1/R (stronger on inboard side),
    poloidal field from plasma current creating nested flux surfaces with
    safety factor q(r) = rB_tor / RB_pol
  - Ohmic heating from plasma current (P_ohm ~ eta * j^2, resistivity drops
    with T^{-3/2})
  - Neutral beam injection (NBI) heating with deposition profile
  - Radiation losses: Bremsstrahlung ~ n^2 * sqrt(T), line radiation
  - Energy confinement time tau_E with L-mode and H-mode scaling
  - Lawson criterion: n * T * tau_E > 3e21 m^-3 keV s for ignition
  - Plasma instabilities: sawtooth crashes (q=1 surface reconnection),
    ELMs (edge localized modes, H-mode pedestal collapse), kink modes
    (q<1 global instability), and full disruptions (thermal + current quench)
  - Turbulent transport: anomalous diffusion across flux surfaces with
    intermittent avalanche-like events
  - Runaway electrons accelerated by electric field when collisionality drops

Three views:
  1) Plasma cross-section — toroidal slice with density/temperature colored
     plasma on nested flux surfaces, magnetic field line topology, LCFS,
     divertor X-point, wall/limiter, NBI beam path
  2) Energy balance dashboard — Lawson triple-product tracker, heating vs
     loss power bars, temperature/density/pressure profiles, confinement
     mode indicator, Q-factor display
  3) Time-series sparkline graphs — 10 key metrics

Six presets:
  Stable Ohmic Confinement, H-Mode Transition, Plasma Disruption,
  ITER-Scale Burning Plasma, Sawtooth Oscillations, Runaway Electron Beam
"""
import curses
import math
import random


# ======================================================================
#  Presets
# ======================================================================

TOKAMAK_PRESETS = [
    ("Stable Ohmic Confinement",
     "Low-power ohmic plasma — resistive heating only, L-mode confinement, stable q-profile",
     "ohmic"),
    ("H-Mode Transition",
     "Auxiliary heating triggers L-H transition — edge pedestal forms, ELMs periodically crash the edge",
     "hmode"),
    ("Plasma Disruption",
     "Unstable plasma — density limit breach triggers thermal quench then current quench, wall loading",
     "disruption"),
    ("ITER-Scale Burning Plasma",
     "DT fusion at Q>10 — alpha heating dominates, approaching Lawson ignition criterion",
     "iter"),
    ("Sawtooth Oscillations",
     "Core q drops below 1 — periodic sawtooth crashes redistribute core pressure to mid-radius",
     "sawtooth"),
    ("Runaway Electron Beam",
     "Post-disruption runaway electrons — Dreicer field accelerates electrons to relativistic energies",
     "runaway"),
]


# ======================================================================
#  Constants / Parameters
# ======================================================================

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

# Plasma physics (normalized units)
_MU0 = 1.0              # permeability (normalized)
_BOLTZMANN = 1.0         # (normalized)

# Confinement
_TAU_E_BASE = 80.0       # base energy confinement time (ticks) L-mode
_TAU_E_HMODE = 200.0     # H-mode confinement time
_HMODE_POWER_THRESH = 0.6  # normalized heating power threshold for L-H transition

# Heating
_OHMIC_COEFF = 0.02      # ohmic heating coefficient
_NBI_POWER = 0.0         # neutral beam injection power (preset-dependent)
_NBI_DEPOSITION_WIDTH = 0.3  # NBI deposition profile width (normalized radius)
_NBI_DEPOSITION_CENTER = 0.3  # NBI peak deposition radius
_ALPHA_POWER_COEFF = 0.04  # fusion alpha heating coefficient

# Losses
_BREMSSTRAHLUNG_COEFF = 0.005  # radiation loss coefficient
_LINE_RAD_COEFF = 0.002  # impurity line radiation

# Transport
_DIFF_CLASSICAL = 0.005  # classical diffusion coefficient
_DIFF_ANOMALOUS = 0.03   # anomalous (turbulent) transport
_DIFF_HMODE_EDGE = 0.005  # reduced edge transport in H-mode

# Instabilities
_SAWTOOTH_PERIOD = 40    # ticks between sawtooth crashes
_ELM_PERIOD = 25         # ticks between ELM crashes
_ELM_FRACTION = 0.15     # fraction of edge pedestal energy ejected per ELM
_DISRUPTION_THERMAL_QUENCH = 5  # ticks for thermal quench
_DISRUPTION_CURRENT_QUENCH = 20  # ticks for current quench

# Geometry
_ASPECT_RATIO = 3.0      # R/a (major radius / minor radius)
_ELONGATION = 1.7        # plasma elongation (kappa)
_TRIANGULARITY = 0.33    # plasma triangularity (delta)

# Lawson criterion threshold (normalized)
_LAWSON_IGNITION = 1.0   # normalized ignition threshold

# Safety factor
_Q_EDGE = 3.5            # edge safety factor
_Q_AXIS = 1.1            # on-axis safety factor (normally > 1)

# History
_MAX_HIST = 500


# ======================================================================
#  Preset parameters
# ======================================================================

def _get_tokamak_params(preset_id):
    """Return parameter dict for given preset."""
    defaults = {
        "nbi_power": 0.0,
        "ohmic_coeff": _OHMIC_COEFF,
        "alpha_heating": False,
        "tau_e_base": _TAU_E_BASE,
        "hmode_enabled": False,
        "hmode_active": False,
        "sawtooth_enabled": False,
        "sawtooth_period": _SAWTOOTH_PERIOD,
        "elm_enabled": False,
        "elm_period": _ELM_PERIOD,
        "disruption_enabled": False,
        "disruption_tick": -1,
        "runaway_enabled": False,
        "q_axis": _Q_AXIS,
        "q_edge": _Q_EDGE,
        "initial_temp": 0.3,
        "initial_density": 0.4,
        "density_limit": 2.0,
        "ip_current": 1.0,       # plasma current (normalized)
        "b_toroidal": 1.0,       # toroidal field strength
        "diff_anomalous": _DIFF_ANOMALOUS,
        "turbulence_level": 0.3,
        "wall_recycling": 0.05,
        "impurity_frac": 0.02,
    }
    overrides = {
        "ohmic": {
            "initial_temp": 0.25,
            "initial_density": 0.35,
            "nbi_power": 0.0,
            "q_axis": 1.5,
        },
        "hmode": {
            "nbi_power": 0.8,
            "hmode_enabled": True,
            "elm_enabled": True,
            "initial_temp": 0.4,
            "initial_density": 0.5,
            "q_axis": 1.05,
        },
        "disruption": {
            "nbi_power": 0.5,
            "initial_temp": 0.5,
            "initial_density": 1.6,
            "density_limit": 1.5,
            "disruption_enabled": True,
            "disruption_tick": 60,
            "impurity_frac": 0.08,
        },
        "iter": {
            "nbi_power": 1.2,
            "alpha_heating": True,
            "initial_temp": 0.8,
            "initial_density": 0.7,
            "hmode_enabled": True,
            "hmode_active": True,
            "elm_enabled": True,
            "elm_period": 30,
            "q_axis": 1.05,
            "b_toroidal": 1.5,
            "ip_current": 1.5,
            "tau_e_base": _TAU_E_HMODE,
        },
        "sawtooth": {
            "nbi_power": 0.4,
            "sawtooth_enabled": True,
            "sawtooth_period": _SAWTOOTH_PERIOD,
            "initial_temp": 0.5,
            "initial_density": 0.5,
            "q_axis": 0.85,
        },
        "runaway": {
            "nbi_power": 0.3,
            "runaway_enabled": True,
            "initial_temp": 0.15,
            "initial_density": 0.2,
            "disruption_enabled": True,
            "disruption_tick": 20,
            "impurity_frac": 0.10,
        },
    }
    params = dict(defaults)
    if preset_id in overrides:
        params.update(overrides[preset_id])
    return params


# ======================================================================
#  Enter / Exit
# ======================================================================

def _enter_tokamak_mode(self):
    """Enter tokamak fusion plasma confinement mode — show preset menu."""
    self.tokamak_mode = True
    self.tokamak_menu = True
    self.tokamak_menu_sel = 0


def _exit_tokamak_mode(self):
    """Exit tokamak mode."""
    self.tokamak_mode = False
    self.tokamak_menu = False
    self.tokamak_running = False
    for attr in list(vars(self)):
        if attr.startswith('tokamak_') and attr not in ('tokamak_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ======================================================================
#  Initialization
# ======================================================================

def _tokamak_init(self, preset_idx: int):
    """Initialize simulation for the chosen preset."""
    name, _desc, pid = TOKAMAK_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(20, max_y - 4)
    cols = max(40, max_x - 2)

    self.tokamak_menu = False
    self.tokamak_running = False
    self.tokamak_preset_name = name
    self.tokamak_preset_id = pid
    self.tokamak_rows = rows
    self.tokamak_cols = cols
    self.tokamak_generation = 0
    self.tokamak_speed = 1
    self.tokamak_view = "plasma"  # plasma | energy | graphs

    params = _get_tokamak_params(pid)
    self.tokamak_params = params

    # --- Build flux-surface geometry ---
    # We model the poloidal cross-section as a grid.
    # Each cell has a normalized flux coordinate rho in [0, 1]
    # (0 = magnetic axis, 1 = last closed flux surface / LCFS).
    # Cells with rho > 1 are in the scrape-off layer (SOL).

    mid_r = rows // 2
    mid_c = cols // 2
    # Minor radius in grid units
    a_r = int(rows * 0.38 / _ELONGATION)
    a_c = int(cols * 0.32)
    self.tokamak_mid_r = mid_r
    self.tokamak_mid_c = mid_c
    self.tokamak_a_r = a_r
    self.tokamak_a_c = a_c

    # Compute rho (normalized flux coordinate) for each cell
    rho = [[2.0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            # Elongated, triangulated flux surface shape
            dr = (r - mid_r) / max(1, a_r * _ELONGATION)
            # Shafranov shift: magnetic axis shifted outward
            shift = 0.08 * (1.0 - abs(dr))
            dc = (c - mid_c - shift * a_c) / max(1, a_c)
            # Triangularity correction
            tri = _TRIANGULARITY * dr * dr
            dc_adj = dc - tri * 0.3
            rr = math.sqrt(dr * dr + dc_adj * dc_adj)
            rho[r][c] = rr
    self.tokamak_rho = rho

    # Safety factor profile q(rho) — increases from axis to edge
    # q = q_axis + (q_edge - q_axis) * rho^2
    self.tokamak_q_axis = params['q_axis']
    self.tokamak_q_edge = params['q_edge']

    # Plasma profiles: temperature T(rho) and density n(rho)
    # Initialized as peaked profiles
    T = [[0.0] * cols for _ in range(rows)]
    n = [[0.0] * cols for _ in range(rows)]
    T0 = params['initial_temp']
    n0 = params['initial_density']
    for r in range(rows):
        for c in range(cols):
            rr = rho[r][c]
            if rr <= 1.0:
                # Parabolic-ish profiles: (1 - rho^2)^alpha
                T[r][c] = T0 * max(0.0, (1.0 - rr * rr)) ** 1.5
                n[r][c] = n0 * max(0.0, (1.0 - rr * rr)) ** 0.8
            elif rr <= 1.3:
                # SOL: rapid decay
                decay = max(0.0, 1.0 - (rr - 1.0) / 0.3)
                T[r][c] = T0 * 0.05 * decay
                n[r][c] = n0 * 0.1 * decay
    self.tokamak_T = T
    self.tokamak_n = n

    # Pressure = n * T (normalized)
    self.tokamak_pressure = [[n[r][c] * T[r][c] for c in range(cols)]
                             for r in range(rows)]

    # Magnetic field strength (poloidal component varies with radius)
    # B_pol ~ j(r) accumulated, B_tor ~ 1/R ~ 1/(R0 + r*cos(theta))
    self.tokamak_b_tor = params['b_toroidal']
    self.tokamak_ip = params['ip_current']

    # Confinement state
    self.tokamak_tau_e = params['tau_e_base']
    self.tokamak_hmode_active = params.get('hmode_active', False)
    self.tokamak_total_heating = 0.0
    self.tokamak_total_loss = 0.0
    self.tokamak_fusion_power = 0.0
    self.tokamak_q_factor = 0.0  # Q = P_fusion / P_input

    # Lawson triple product: n * T * tau_E (normalized so 1.0 = ignition)
    self.tokamak_lawson = 0.0

    # Instability state
    self.tokamak_sawtooth_timer = 0
    self.tokamak_elm_timer = 0
    self.tokamak_disruption_phase = 0  # 0=none, 1=thermal quench, 2=current quench, 3=done
    self.tokamak_disruption_countdown = 0
    self.tokamak_disrupted = False

    # Runaway electrons
    self.tokamak_runaway_pop = 0.0  # fraction of plasma that is runaway electrons
    self.tokamak_runaway_energy = 0.0

    # Turbulence field (perturbation to transport)
    self.tokamak_turb = [[0.0] * cols for _ in range(rows)]

    # NBI toggle
    self.tokamak_nbi_on = params['nbi_power'] > 0

    # H-mode pedestal
    if self.tokamak_hmode_active:
        _build_hmode_pedestal(self)

    # History for sparkline graphs
    self.tokamak_history = {
        'core_temp': [],
        'core_density': [],
        'lawson': [],
        'q_factor': [],
        'heating_power': [],
        'loss_power': [],
        'tau_e': [],
        'beta': [],         # plasma beta = pressure / magnetic pressure
        'runaway_frac': [],
        'stored_energy': [],
    }

    self._flash(f"Tokamak: {name}")


def _build_hmode_pedestal(self):
    """Build H-mode edge pedestal — steep gradients at rho~0.85-1.0."""
    rows = self.tokamak_rows
    cols = self.tokamak_cols
    T = self.tokamak_T
    n = self.tokamak_n
    rho = self.tokamak_rho
    params = self.tokamak_params
    T0 = params['initial_temp']
    n0 = params['initial_density']

    for r in range(rows):
        for c in range(cols):
            rr = rho[r][c]
            if 0.85 <= rr <= 1.0:
                # Pedestal: elevated temperature and density at edge
                ped_frac = (rr - 0.85) / 0.15
                T[r][c] = max(T[r][c], T0 * 0.5 * (1.0 - ped_frac))
                n[r][c] = max(n[r][c], n0 * 0.7 * (1.0 - ped_frac))


# ======================================================================
#  Simulation Step
# ======================================================================

def _tokamak_step(self):
    """One tick of tokamak plasma simulation."""
    rows = self.tokamak_rows
    cols = self.tokamak_cols
    T = self.tokamak_T
    n = self.tokamak_n
    rho = self.tokamak_rho
    params = self.tokamak_params
    gen = self.tokamak_generation
    pid = self.tokamak_preset_id

    # --- Check for disruption trigger ---
    if params['disruption_enabled'] and not self.tokamak_disrupted:
        if gen >= params['disruption_tick'] and self.tokamak_disruption_phase == 0:
            self.tokamak_disruption_phase = 1
            self.tokamak_disruption_countdown = _DISRUPTION_THERMAL_QUENCH

    # --- Handle active disruption ---
    if self.tokamak_disruption_phase == 1:
        # Thermal quench: rapid loss of thermal energy
        self.tokamak_disruption_countdown -= 1
        quench_rate = 0.3
        for r in range(rows):
            for c in range(cols):
                if rho[r][c] <= 1.3:
                    T[r][c] *= (1.0 - quench_rate)
                    # Impurity influx increases radiation
                    n[r][c] *= (1.0 + 0.05)
                    n[r][c] = min(n[r][c], 3.0)
        if self.tokamak_disruption_countdown <= 0:
            self.tokamak_disruption_phase = 2
            self.tokamak_disruption_countdown = _DISRUPTION_CURRENT_QUENCH
    elif self.tokamak_disruption_phase == 2:
        # Current quench: plasma current decays
        self.tokamak_disruption_countdown -= 1
        self.tokamak_ip *= 0.9
        # Runaway electron generation during current quench
        if params['runaway_enabled']:
            self.tokamak_runaway_pop = min(1.0, self.tokamak_runaway_pop + 0.05)
            self.tokamak_runaway_energy = min(5.0, self.tokamak_runaway_energy + 0.2)
        for r in range(rows):
            for c in range(cols):
                if rho[r][c] <= 1.0:
                    T[r][c] *= 0.95
        if self.tokamak_disruption_countdown <= 0:
            self.tokamak_disruption_phase = 3
            self.tokamak_disrupted = True

    # Skip normal physics if fully disrupted
    if self.tokamak_disruption_phase >= 3:
        _tokamak_record_metrics(self)
        self.tokamak_generation += 1
        return

    # --- Heating ---
    total_heat = 0.0

    # Ohmic heating: P_ohmic ~ eta * j^2, eta ~ T^{-3/2}
    for r in range(rows):
        for c in range(cols):
            rr = rho[r][c]
            if rr <= 1.0:
                t_local = max(0.01, T[r][c])
                eta = params['ohmic_coeff'] / (t_local ** 1.5 + 0.01)
                # Current density peaked on axis
                j_local = self.tokamak_ip * max(0.0, (1.0 - rr * rr)) ** 1.0
                p_ohmic = eta * j_local * j_local * 0.01
                T[r][c] += p_ohmic
                total_heat += p_ohmic

    # Neutral beam injection
    if self.tokamak_nbi_on and params['nbi_power'] > 0:
        nbi_p = params['nbi_power']
        for r in range(rows):
            for c in range(cols):
                rr = rho[r][c]
                if rr <= 1.0:
                    # Gaussian deposition profile
                    dep = math.exp(-((rr - _NBI_DEPOSITION_CENTER) ** 2) /
                                   (2 * _NBI_DEPOSITION_WIDTH ** 2))
                    p_nbi = nbi_p * dep * 0.008
                    T[r][c] += p_nbi
                    total_heat += p_nbi

    # Alpha (fusion) heating — only for DT burning plasma
    fusion_power = 0.0
    if params['alpha_heating']:
        for r in range(rows):
            for c in range(cols):
                rr = rho[r][c]
                if rr <= 1.0:
                    t_local = T[r][c]
                    n_local = n[r][c]
                    # Fusion rate ~ n^2 * <sigma*v>(T), peaked around 15 keV
                    # Simplified: reactivity peaks then falls
                    reactivity = t_local * t_local * math.exp(-0.5 * abs(t_local - 0.8))
                    p_alpha = _ALPHA_POWER_COEFF * n_local * n_local * reactivity * 0.01
                    T[r][c] += p_alpha
                    total_heat += p_alpha
                    fusion_power += p_alpha * 5.0  # total fusion = 5x alpha

    self.tokamak_total_heating = total_heat
    self.tokamak_fusion_power = fusion_power

    # --- Losses ---
    total_loss = 0.0

    # Bremsstrahlung radiation: P_brem ~ n^2 * sqrt(T) * Z_eff
    z_eff = 1.0 + params['impurity_frac'] * 20  # impurities increase Z_eff
    for r in range(rows):
        for c in range(cols):
            rr = rho[r][c]
            if rr <= 1.2:
                t_local = max(0.0, T[r][c])
                n_local = max(0.0, n[r][c])
                p_brem = _BREMSSTRAHLUNG_COEFF * n_local * n_local * math.sqrt(t_local + 0.001) * z_eff
                p_line = _LINE_RAD_COEFF * n_local * params['impurity_frac'] * t_local
                loss = (p_brem + p_line) * 0.5
                T[r][c] = max(0.0, T[r][c] - loss)
                total_loss += loss

    # Confinement loss: dW/dt = P_heat - W/tau_E
    tau_e = self.tokamak_tau_e
    for r in range(rows):
        for c in range(cols):
            rr = rho[r][c]
            if rr <= 1.0:
                w_local = n[r][c] * T[r][c]
                loss_rate = w_local / max(1.0, tau_e) * 0.5
                # Remove energy proportionally from temperature
                if n[r][c] > 0.001:
                    T[r][c] = max(0.0, T[r][c] - loss_rate / max(0.001, n[r][c]))
                total_loss += loss_rate

    self.tokamak_total_loss = total_loss

    # --- Transport (diffusion across flux surfaces) ---
    new_T = [row[:] for row in T]
    new_n = [row[:] for row in n]

    # Update turbulence field
    turb = self.tokamak_turb
    turb_level = params['turbulence_level']
    for r in range(rows):
        for c in range(cols):
            if rho[r][c] <= 1.2:
                # Turbulent fluctuations: random walk + gradient-driven
                turb[r][c] = turb[r][c] * 0.8 + (random.random() - 0.5) * turb_level * 0.4

    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            rr = rho[r][c]
            if rr > 1.3:
                continue

            # Effective diffusivity depends on location and H-mode state
            d_eff = _DIFF_CLASSICAL + params['diff_anomalous']
            if self.tokamak_hmode_active and 0.85 <= rr <= 1.0:
                d_eff = _DIFF_HMODE_EDGE  # Transport barrier
            # Add turbulent enhancement
            d_eff += max(0.0, turb[r][c]) * 0.1

            # Laplacian diffusion of temperature and density
            lap_T = 0.0
            lap_n = 0.0
            for dr, dc in _NEIGHBORS_4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if rho[nr][nc] <= 1.4:
                        lap_T += T[nr][nc] - T[r][c]
                        lap_n += n[nr][nc] - n[r][c]

            new_T[r][c] = max(0.0, T[r][c] + d_eff * lap_T)
            new_n[r][c] = max(0.0, min(3.0, n[r][c] + d_eff * lap_n * 0.5))

    self.tokamak_T = new_T
    self.tokamak_n = new_n
    T = new_T
    n = new_n

    # --- H-mode transition check ---
    if params['hmode_enabled'] and not self.tokamak_hmode_active:
        if total_heat > _HMODE_POWER_THRESH:
            self.tokamak_hmode_active = True
            self.tokamak_tau_e = _TAU_E_HMODE
            _build_hmode_pedestal(self)

    # Update confinement time
    if self.tokamak_hmode_active:
        self.tokamak_tau_e = _TAU_E_HMODE
    else:
        self.tokamak_tau_e = params['tau_e_base']

    # --- Sawtooth instability ---
    if params['sawtooth_enabled'] or self.tokamak_q_axis < 1.0:
        self.tokamak_sawtooth_timer += 1
        period = params['sawtooth_period']
        if self.tokamak_sawtooth_timer >= period:
            self.tokamak_sawtooth_timer = 0
            # Sawtooth crash: flatten profiles inside q=1 surface
            # q=1 surface at rho ~ sqrt((1 - q_axis)/(q_edge - q_axis))
            q_ax = self.tokamak_q_axis
            q_ed = self.tokamak_q_edge
            if q_ax < 1.0 and q_ed > 1.0:
                rho_q1 = math.sqrt((1.0 - q_ax) / max(0.01, q_ed - q_ax))
            else:
                rho_q1 = 0.3
            rho_q1 = min(0.5, rho_q1)
            # Mix core values to flatten
            sum_T = 0.0
            sum_n = 0.0
            count = 0
            for r in range(rows):
                for c in range(cols):
                    if rho[r][c] <= rho_q1:
                        sum_T += T[r][c]
                        sum_n += n[r][c]
                        count += 1
            if count > 0:
                avg_T = sum_T / count
                avg_n = sum_n / count
                for r in range(rows):
                    for c in range(cols):
                        if rho[r][c] <= rho_q1:
                            T[r][c] = T[r][c] * 0.3 + avg_T * 0.7
                            n[r][c] = n[r][c] * 0.3 + avg_n * 0.7
                        elif rho[r][c] <= rho_q1 + 0.15:
                            # Heat pushed outward
                            T[r][c] += avg_T * 0.1
                            n[r][c] += avg_n * 0.05

    # --- ELM crashes (H-mode only) ---
    if params['elm_enabled'] and self.tokamak_hmode_active:
        self.tokamak_elm_timer += 1
        if self.tokamak_elm_timer >= params['elm_period']:
            self.tokamak_elm_timer = 0
            # ELM: collapse edge pedestal, expel energy to SOL
            for r in range(rows):
                for c in range(cols):
                    rr = rho[r][c]
                    if 0.8 <= rr <= 1.0:
                        T[r][c] *= (1.0 - _ELM_FRACTION)
                        n[r][c] *= (1.0 - _ELM_FRACTION * 0.5)
                    elif 1.0 < rr <= 1.3:
                        # Energy deposited in SOL
                        T[r][c] += 0.05
                        n[r][c] += 0.02

    # --- Runaway electrons ---
    if params['runaway_enabled'] and self.tokamak_disrupted:
        # Runaway beam: concentrated in core, gaining energy
        self.tokamak_runaway_energy *= 1.02
        for r in range(rows):
            for c in range(cols):
                if rho[r][c] <= 0.2:
                    T[r][c] = self.tokamak_runaway_energy * 0.3
    elif params['runaway_enabled'] and self.tokamak_disruption_phase >= 2:
        self.tokamak_runaway_pop = min(1.0, self.tokamak_runaway_pop + 0.02)
        self.tokamak_runaway_energy = min(5.0, self.tokamak_runaway_energy + 0.1)

    # --- Wall recycling / fueling ---
    if not self.tokamak_disrupted:
        for r in range(rows):
            for c in range(cols):
                rr = rho[r][c]
                if 0.95 <= rr <= 1.1:
                    n[r][c] += params['wall_recycling'] * 0.1

    # --- Compute derived quantities ---
    # Update pressure
    pressure = self.tokamak_pressure
    stored_energy = 0.0
    for r in range(rows):
        for c in range(cols):
            pressure[r][c] = n[r][c] * T[r][c]
            if rho[r][c] <= 1.0:
                stored_energy += pressure[r][c]

    # Core temperature and density (average inside rho < 0.2)
    core_T = 0.0
    core_n = 0.0
    core_count = 0
    for r in range(rows):
        for c in range(cols):
            if rho[r][c] <= 0.2:
                core_T += T[r][c]
                core_n += n[r][c]
                core_count += 1
    if core_count > 0:
        core_T /= core_count
        core_n /= core_count

    # Lawson triple product (normalized)
    tau_e = self.tokamak_tau_e
    self.tokamak_lawson = core_n * core_T * tau_e / max(1.0, 80.0)  # normalized to ~1 at ignition

    # Q factor
    p_input = total_heat - (fusion_power / 5.0 if params['alpha_heating'] else 0)
    if p_input > 0.001:
        self.tokamak_q_factor = fusion_power / p_input
    else:
        self.tokamak_q_factor = 0.0

    # Beta = <p> / (B^2 / 2mu0)
    avg_p = stored_energy / max(1, core_count * 10)
    b_mag = self.tokamak_b_tor
    self.tokamak_beta = avg_p / max(0.01, b_mag * b_mag * 0.5)

    # --- Record metrics ---
    _tokamak_record_metrics(self)

    self.tokamak_generation += 1


def _tokamak_record_metrics(self):
    """Record metrics for sparkline graphs."""
    hist = self.tokamak_history
    rows = self.tokamak_rows
    cols = self.tokamak_cols
    T = self.tokamak_T
    n = self.tokamak_n
    rho = self.tokamak_rho

    # Core averages
    core_T = 0.0
    core_n = 0.0
    cnt = 0
    total_energy = 0.0
    for r in range(rows):
        for c in range(cols):
            if rho[r][c] <= 0.2:
                core_T += T[r][c]
                core_n += n[r][c]
                cnt += 1
            if rho[r][c] <= 1.0:
                total_energy += n[r][c] * T[r][c]
    if cnt > 0:
        core_T /= cnt
        core_n /= cnt

    hist['core_temp'].append(core_T)
    hist['core_density'].append(core_n)
    hist['lawson'].append(getattr(self, 'tokamak_lawson', 0.0))
    hist['q_factor'].append(getattr(self, 'tokamak_q_factor', 0.0))
    hist['heating_power'].append(getattr(self, 'tokamak_total_heating', 0.0))
    hist['loss_power'].append(getattr(self, 'tokamak_total_loss', 0.0))
    hist['tau_e'].append(getattr(self, 'tokamak_tau_e', 0.0))
    hist['beta'].append(getattr(self, 'tokamak_beta', 0.0))
    hist['runaway_frac'].append(getattr(self, 'tokamak_runaway_pop', 0.0))
    hist['stored_energy'].append(total_energy)

    for key in hist:
        if len(hist[key]) > _MAX_HIST:
            hist[key] = hist[key][-_MAX_HIST:]


# ======================================================================
#  Key Handlers
# ======================================================================

def _handle_tokamak_menu_key(self, key: int) -> bool:
    """Handle keys in preset menu."""
    if key == curses.KEY_UP or key == ord('k'):
        self.tokamak_menu_sel = (self.tokamak_menu_sel - 1) % len(TOKAMAK_PRESETS)
        return True
    if key == curses.KEY_DOWN or key == ord('j'):
        self.tokamak_menu_sel = (self.tokamak_menu_sel + 1) % len(TOKAMAK_PRESETS)
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _tokamak_init(self, self.tokamak_menu_sel)
        self.tokamak_running = True
        return True
    if key == ord('q') or key == 27:
        self._exit_tokamak_mode()
        return True
    return False


def _handle_tokamak_key(self, key: int) -> bool:
    """Handle keys during simulation."""
    if key == ord(' '):
        self.tokamak_running = not self.tokamak_running
        return True
    if key == ord('v'):
        views = ["plasma", "energy", "graphs"]
        idx = views.index(self.tokamak_view)
        self.tokamak_view = views[(idx + 1) % len(views)]
        return True
    if key == ord('n'):
        _tokamak_step(self)
        return True
    if key == ord('b'):
        # Toggle NBI
        self.tokamak_nbi_on = not self.tokamak_nbi_on
        self._flash("NBI " + ("ON" if self.tokamak_nbi_on else "OFF"))
        return True
    if key == ord('d'):
        # Trigger disruption manually
        if self.tokamak_disruption_phase == 0 and not self.tokamak_disrupted:
            self.tokamak_disruption_phase = 1
            self.tokamak_disruption_countdown = _DISRUPTION_THERMAL_QUENCH
            self._flash("DISRUPTION TRIGGERED")
        return True
    if key == ord('+') or key == ord('='):
        self.tokamak_speed = min(8, self.tokamak_speed + 1)
        return True
    if key == ord('-'):
        self.tokamak_speed = max(1, self.tokamak_speed - 1)
        return True
    if key == ord('r'):
        idx = next((i for i, p in enumerate(TOKAMAK_PRESETS) if p[2] == self.tokamak_preset_id), 0)
        _tokamak_init(self, idx)
        self.tokamak_running = True
        return True
    if key == ord('R'):
        self.tokamak_menu = True
        self.tokamak_menu_sel = 0
        return True
    if key == ord('q'):
        self._exit_tokamak_mode()
        return True
    return False


# ======================================================================
#  Drawing — Preset Menu
# ======================================================================

def _draw_tokamak_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()
    title = "Tokamak Fusion Plasma Confinement"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD | curses.color_pair(1))
    except curses.error:
        pass

    sub = "Select a plasma scenario:"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(sub)) // 2), sub)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(TOKAMAK_PRESETS):
        y = 5 + i * 3
        if y + 1 >= max_y:
            break
        marker = ">" if i == self.tokamak_menu_sel else " "
        attr = curses.A_REVERSE if i == self.tokamak_menu_sel else 0
        try:
            self.stdscr.addstr(y, 4, f"{marker} {name}", attr | curses.A_BOLD)
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
#  Drawing — Plasma Cross-Section View
# ======================================================================

def _draw_tokamak(self, max_y: int, max_x: int):
    """Dispatch to current view."""
    if self.tokamak_view == "plasma":
        _draw_tokamak_plasma(self, max_y, max_x)
    elif self.tokamak_view == "energy":
        _draw_tokamak_energy(self, max_y, max_x)
    elif self.tokamak_view == "graphs":
        _draw_tokamak_graphs(self, max_y, max_x)


def _draw_tokamak_plasma(self, max_y: int, max_x: int):
    """Render poloidal cross-section with plasma density/temperature and magnetic topology."""
    self.stdscr.erase()
    rows = self.tokamak_rows
    cols = self.tokamak_cols
    T = self.tokamak_T
    n = self.tokamak_n
    rho = self.tokamak_rho
    view_h = min(rows, max_y - 3)
    view_w = min(cols, max_x - 1)

    # Find max temperature for color scaling
    max_T = 0.01
    for r in range(rows):
        for c in range(cols):
            if rho[r][c] <= 1.3 and T[r][c] > max_T:
                max_T = T[r][c]

    for r in range(view_h):
        for c in range(view_w):
            rr = rho[r][c]

            if rr > 1.4:
                continue

            # Wall / vessel boundary
            if 1.3 <= rr <= 1.4:
                try:
                    self.stdscr.addstr(1 + r, c, "#", curses.color_pair(7) | curses.A_DIM)
                except curses.error:
                    pass
                continue

            # SOL (scrape-off layer)
            if 1.0 < rr <= 1.3:
                t_val = T[r][c]
                if t_val > 0.01:
                    try:
                        self.stdscr.addstr(1 + r, c, ".", curses.color_pair(4) | curses.A_DIM)
                    except curses.error:
                        pass
                continue

            # LCFS boundary marker
            if 0.98 <= rr <= 1.02:
                # Draw flux surface boundary occasionally
                gen = self.tokamak_generation
                if (r + c + gen // 4) % 5 == 0:
                    try:
                        self.stdscr.addstr(1 + r, c, ":", curses.color_pair(6))
                    except curses.error:
                        pass
                    continue

            # Plasma interior
            t_val = T[r][c]
            n_val = n[r][c]
            intensity = t_val / max(0.01, max_T)

            # Runaway electron beam visualization
            if self.tokamak_runaway_pop > 0.1 and rr <= 0.25:
                try:
                    ch = "@" if self.tokamak_runaway_energy > 2.0 else "*"
                    self.stdscr.addstr(1 + r, c, ch,
                                       curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass
                continue

            # Choose glyph and color based on temperature
            if intensity > 0.8:
                ch = "@"
                cp = curses.color_pair(1) | curses.A_BOLD  # hot core: bright red/white
            elif intensity > 0.6:
                ch = "#"
                cp = curses.color_pair(1)  # hot
            elif intensity > 0.4:
                ch = "%"
                cp = curses.color_pair(3)  # warm: yellow
            elif intensity > 0.2:
                ch = "="
                cp = curses.color_pair(6)  # moderate: cyan
            elif intensity > 0.05:
                ch = "-"
                cp = curses.color_pair(4)  # cool: blue
            else:
                ch = "."
                cp = curses.color_pair(7) | curses.A_DIM  # cold

            # Draw flux surface contours
            # Show q=1, q=2, q=3 surfaces
            q_local = self.tokamak_q_axis + (self.tokamak_q_edge - self.tokamak_q_axis) * rr * rr
            for q_val in (1.0, 2.0, 3.0):
                if abs(q_local - q_val) < 0.08:
                    ch = "|" if abs(r - self.tokamak_mid_r) > abs(c - self.tokamak_mid_c) * 0.5 else "-"
                    cp = curses.color_pair(2) | curses.A_DIM
                    break

            # Magnetic axis marker
            if rr < 0.03:
                ch = "+"
                cp = curses.color_pair(2) | curses.A_BOLD

            # Disruption visual
            if self.tokamak_disruption_phase == 1:
                if random.random() < 0.15:
                    ch = random.choice(["*", "!", "x", "X"])
                    cp = curses.color_pair(1) | curses.A_BOLD

            try:
                self.stdscr.addstr(1 + r, c, ch, cp)
            except curses.error:
                pass

    # NBI beam path visualization (horizontal line from outboard side)
    if self.tokamak_nbi_on and self.tokamak_params['nbi_power'] > 0:
        beam_r = self.tokamak_mid_r
        for c in range(min(view_w, self.tokamak_mid_c + self.tokamak_a_c + 5),
                       min(view_w, self.tokamak_mid_c + self.tokamak_a_c + 15)):
            try:
                self.stdscr.addstr(1 + beam_r, c, ">",
                                   curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass

    # Divertor X-point marker (bottom of plasma)
    xp_r = min(view_h - 1, self.tokamak_mid_r + int(self.tokamak_a_r * _ELONGATION * 0.95))
    xp_c = self.tokamak_mid_c
    if 0 <= xp_r < view_h and 0 <= xp_c < view_w:
        try:
            self.stdscr.addstr(1 + xp_r, xp_c, "X",
                               curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass

    # Status bar
    gen = self.tokamak_generation
    mode_str = "H-mode" if self.tokamak_hmode_active else "L-mode"
    if self.tokamak_disruption_phase == 1:
        mode_str = "THERMAL QUENCH"
    elif self.tokamak_disruption_phase == 2:
        mode_str = "CURRENT QUENCH"
    elif self.tokamak_disrupted:
        mode_str = "DISRUPTED"

    lawson = getattr(self, 'tokamak_lawson', 0.0)
    q_fac = getattr(self, 'tokamak_q_factor', 0.0)

    status = (f" {self.tokamak_preset_name} | t={gen} | {mode_str} | "
              f"nTt={lawson:.2f} Q={q_fac:.1f} | "
              f"[v]iew [b]NBI [d]isrupt [space] [r]eset [q]uit")
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    legend = "+axis :LCFS #wall @hot #warm =-cool .cold |q-surf >NBI X-point"
    try:
        self.stdscr.addstr(max_y - 1, 0, legend[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Energy Balance Dashboard
# ======================================================================

def _draw_tokamak_energy(self, max_y: int, max_x: int):
    """Render energy balance dashboard with Lawson triple product tracking."""
    self.stdscr.erase()
    gen = self.tokamak_generation
    params = self.tokamak_params

    title = f"Energy Balance -- {self.tokamak_preset_name} | t={gen}"
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD | curses.color_pair(1))
    except curses.error:
        pass

    y = 2

    # --- Confinement Mode ---
    mode_str = "H-MODE" if self.tokamak_hmode_active else "L-MODE"
    if self.tokamak_disruption_phase > 0:
        mode_str = "DISRUPTION"
    mode_color = curses.color_pair(2) if self.tokamak_hmode_active else curses.color_pair(4)
    if self.tokamak_disruption_phase > 0:
        mode_color = curses.color_pair(1) | curses.A_BOLD
    try:
        self.stdscr.addstr(y, 4, f"Confinement: {mode_str}",
                           mode_color | curses.A_BOLD)
        self.stdscr.addstr(y, 35, f"Ip={self.tokamak_ip:.2f}  Bt={self.tokamak_b_tor:.2f}",
                           curses.color_pair(7))
    except curses.error:
        pass
    y += 2

    # --- Lawson Triple Product ---
    lawson = getattr(self, 'tokamak_lawson', 0.0)
    bar_w = min(40, max_x - 30)
    filled = int(min(1.0, lawson) * bar_w)
    bar = "[" + "=" * filled + " " * (bar_w - filled) + "]"
    label = f"Lawson nTtau: {lawson:.3f} / 1.000"
    try:
        cp = curses.color_pair(2) if lawson >= 1.0 else curses.color_pair(3)
        self.stdscr.addstr(y, 4, label, cp | curses.A_BOLD)
        self.stdscr.addstr(y + 1, 4, bar, cp)
        if lawson >= 1.0:
            self.stdscr.addstr(y + 1, 4 + bar_w + 2, "IGNITION!",
                               curses.color_pair(1) | curses.A_BOLD | curses.A_BLINK)
    except curses.error:
        pass
    y += 3

    # --- Q Factor ---
    q_fac = getattr(self, 'tokamak_q_factor', 0.0)
    try:
        q_color = curses.color_pair(2) if q_fac >= 10 else curses.color_pair(3) if q_fac >= 1 else curses.color_pair(7)
        q_label = f"Q = P_fusion/P_input = {q_fac:.2f}"
        if q_fac >= 10:
            q_label += "  (BURNING PLASMA)"
        elif q_fac >= 1:
            q_label += "  (breakeven)"
        self.stdscr.addstr(y, 4, q_label, q_color | curses.A_BOLD)
    except curses.error:
        pass
    y += 2

    # --- Heating Power Breakdown ---
    total_h = max(0.001, self.tokamak_total_heating)
    total_l = max(0.001, self.tokamak_total_loss)
    fusion_p = getattr(self, 'tokamak_fusion_power', 0.0)
    try:
        self.stdscr.addstr(y, 4, "HEATING", curses.color_pair(1) | curses.A_BOLD)
        self.stdscr.addstr(y, 20, "LOSSES", curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass
    y += 1

    # Heating components
    heat_items = [
        (f"Ohmic:  {params['ohmic_coeff']:.3f}", curses.color_pair(3)),
        (f"NBI:    {'ON' if self.tokamak_nbi_on else 'OFF'} ({params['nbi_power']:.1f})",
         curses.color_pair(3)),
        (f"Alpha:  {fusion_p / 5.0:.3f}" if params['alpha_heating'] else "Alpha:  ---",
         curses.color_pair(2)),
        (f"Total:  {total_h:.3f}", curses.color_pair(1) | curses.A_BOLD),
    ]
    loss_items = [
        (f"Bremss: ~{total_l * 0.4:.3f}", curses.color_pair(4)),
        (f"Transp: ~{total_l * 0.5:.3f}", curses.color_pair(4)),
        (f"Line R: ~{total_l * 0.1:.3f}", curses.color_pair(5)),
        (f"Total:  {total_l:.3f}", curses.color_pair(4) | curses.A_BOLD),
    ]

    for i, ((h_text, h_cp), (l_text, l_cp)) in enumerate(zip(heat_items, loss_items)):
        if y + i >= max_y - 4:
            break
        try:
            self.stdscr.addstr(y + i, 4, h_text[:15], h_cp)
            self.stdscr.addstr(y + i, 20, l_text[:15], l_cp)
        except curses.error:
            pass
    y += len(heat_items) + 1

    # --- Confinement parameters ---
    tau_e = getattr(self, 'tokamak_tau_e', 0.0)
    beta = getattr(self, 'tokamak_beta', 0.0)
    try:
        self.stdscr.addstr(y, 4, f"tau_E = {tau_e:.1f} ticks", curses.color_pair(6))
        self.stdscr.addstr(y + 1, 4, f"beta  = {beta:.4f}", curses.color_pair(6))
    except curses.error:
        pass
    y += 3

    # --- Temperature/Density profile bar chart (radial) ---
    try:
        self.stdscr.addstr(y, 4, "Radial profiles (core -> edge):",
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass
    y += 1

    # Sample profiles at 5 radial points
    rho_samples = [0.0, 0.25, 0.5, 0.75, 1.0]
    T = self.tokamak_T
    n_grid = self.tokamak_n
    rho_grid = self.tokamak_rho
    mid_r = self.tokamak_mid_r
    mid_c = self.tokamak_mid_c
    a_c = self.tokamak_a_c

    t_profile = []
    n_profile = []
    for rs in rho_samples:
        # Sample along midplane (outboard)
        sample_c = mid_c + int(rs * a_c)
        if 0 <= mid_r < self.tokamak_rows and 0 <= sample_c < self.tokamak_cols:
            t_profile.append(T[mid_r][sample_c])
            n_profile.append(n_grid[mid_r][sample_c])
        else:
            t_profile.append(0.0)
            n_profile.append(0.0)

    bars = ".|=@#"
    try:
        self.stdscr.addstr(y, 4, "T(r): ", curses.color_pair(1))
        for i, tv in enumerate(t_profile):
            # Simple bar representation
            level = min(4, int(tv * 10))
            ch = bars[max(0, level)] * 3
            self.stdscr.addstr(y, 10 + i * 4, ch, curses.color_pair(1))
        self.stdscr.addstr(y + 1, 4, "n(r): ", curses.color_pair(4))
        for i, nv in enumerate(n_profile):
            level = min(4, int(nv * 5))
            ch = bars[max(0, level)] * 3
            self.stdscr.addstr(y + 1, 10 + i * 4, ch, curses.color_pair(4))
        self.stdscr.addstr(y + 2, 4, "rho:  ", curses.color_pair(7))
        for i, rs in enumerate(rho_samples):
            self.stdscr.addstr(y + 2, 10 + i * 4, f"{rs:.1f}", curses.color_pair(7))
    except curses.error:
        pass
    y += 4

    # --- Runaway electrons ---
    if params['runaway_enabled']:
        re_pop = self.tokamak_runaway_pop
        re_e = self.tokamak_runaway_energy
        try:
            color = curses.color_pair(1) | curses.A_BOLD if re_pop > 0.5 else curses.color_pair(3)
            self.stdscr.addstr(y, 4, f"Runaway e-: {re_pop:.2f} pop, {re_e:.2f} energy",
                               color)
        except curses.error:
            pass
        y += 2

    # Status bar
    status = "[v]iew [b]NBI [d]isrupt [space]pause [r]eset [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Sparkline Graphs View
# ======================================================================

def _draw_tokamak_graphs(self, max_y: int, max_x: int):
    """Time-series sparkline graphs for tokamak metrics."""
    self.stdscr.erase()
    hist = self.tokamak_history
    graph_w = min(200, max_x - 30)

    title = f"Plasma Metrics -- {self.tokamak_preset_name} | t={self.tokamak_generation}"
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD)
    except curses.error:
        pass

    labels = [
        ("Core Temp",       'core_temp',      1),
        ("Core Density",    'core_density',   4),
        ("Lawson nTtau",    'lawson',         2),
        ("Q Factor",        'q_factor',       3),
        ("Heating Power",   'heating_power',  1),
        ("Loss Power",      'loss_power',     5),
        ("tau_E",           'tau_e',          6),
        ("Beta",            'beta',           3),
        ("Runaway e-",      'runaway_frac',   1),
        ("Stored Energy",   'stored_energy',  2),
    ]

    spark = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    n_bars = len(spark)

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
                    self.stdscr.addstr(base_y, x, spark[idx], color)
                except curses.error:
                    pass

    status = "[v]iew [b]NBI [d]isrupt [space]pause [r]eset [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Registration
# ======================================================================

def register(App):
    """Register tokamak fusion plasma confinement mode methods on the App class."""
    App.TOKAMAK_PRESETS = TOKAMAK_PRESETS
    App._enter_tokamak_mode = _enter_tokamak_mode
    App._exit_tokamak_mode = _exit_tokamak_mode
    App._tokamak_init = _tokamak_init
    App._tokamak_step = _tokamak_step
    App._handle_tokamak_menu_key = _handle_tokamak_menu_key
    App._handle_tokamak_key = _handle_tokamak_key
    App._draw_tokamak_menu = _draw_tokamak_menu
    App._draw_tokamak = _draw_tokamak
