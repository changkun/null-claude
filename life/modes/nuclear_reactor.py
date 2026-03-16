"""Mode: nuclear_reactor — Nuclear Reactor Physics & Meltdown Dynamics.

Simulates a pressurized water reactor (PWR) cross-section with neutron transport,
fission chain reactions, control rod mechanics, xenon poisoning, thermal hydraulics,
and failure cascades including loss-of-coolant accidents and core meltdown.

Physics modeled:
  - Neutron transport & fission: 2D diffusion on fuel/moderator/coolant lattice,
    U-235 absorption spawning 2-3 daughter neutrons, k-eff from geometry
  - Control rods: player-adjustable (+/-) neutron absorbers controlling reactivity
  - Xenon-135 poisoning: fission product buildup suppressing reactivity, dangerous
    xenon pit rebound on shutdown (Chernobyl mechanism)
  - Thermal hydraulics: fuel rod heat generation coupled to coolant flow, convective
    heat transfer, temperature-dependent reactivity feedback
  - Void coefficient: negative (PWR safe) or positive (RBMK dangerous) feedback
  - Failure cascades: LOCA, steam void formation, fuel rod melting, hydrogen
    generation, corium pooling

Three views:
  1) Reactor cross-section map — fuel rods, control rods, coolant channels,
     neutron flux density overlay, melted/damaged indicators
  2) Temperature/pressure heatmap — fuel & coolant temperature with flow vectors,
     void fraction overlay, containment pressure
  3) Time-series sparkline graphs — 10 key metrics

Six presets:
  Normal Power Operation, Control Rod Withdrawal Accident, Xenon Poisoning Restart,
  Loss-of-Coolant Accident, Station Blackout, Breeder Reactor Fast Spectrum
"""

import curses
import math
import random


# ======================================================================
#  Presets
# ======================================================================

NUCLEAR_REACTOR_PRESETS = [
    ("Normal Power Operation",
     "Steady-state PWR at 100% — balanced fission, negative void coefficient, stable xenon equilibrium",
     "normal"),
    ("Control Rod Withdrawal Accident",
     "Rods withdrawn too far — supercritical excursion with positive reactivity insertion",
     "rod_withdrawal"),
    ("Xenon Poisoning Restart (Chernobyl)",
     "Restart from xenon pit — operators override safety to raise power, positive void runaway",
     "xenon_restart"),
    ("Loss-of-Coolant Accident (TMI)",
     "Primary coolant pipe break — uncovering fuel rods, void formation, partial meltdown",
     "loca"),
    ("Station Blackout (Fukushima)",
     "Total power loss — decay heat with no cooling, slow boiloff leading to meltdown",
     "blackout"),
    ("Breeder Reactor Fast Spectrum",
     "Fast neutron spectrum — no moderator, Pu-239 breeding from U-238 blanket, higher k-eff",
     "breeder"),
]


# ======================================================================
#  Constants / Parameters
# ======================================================================

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# Cell types
_CELL_EMPTY = 0
_CELL_FUEL = 1
_CELL_MODERATOR = 2
_CELL_COOLANT = 3
_CELL_CONTROL_ROD = 4
_CELL_REFLECTOR = 5
_CELL_VESSEL_WALL = 6
_CELL_MELTED = 7
_CELL_CORIUM = 8

# Neutron physics (normalized)
_FISSION_YIELD = 2.5          # avg neutrons per fission
_SIGMA_FISSION = 0.08         # fission cross-section (fuel)
_SIGMA_ABSORB_FUEL = 0.03     # parasitic absorption in fuel
_SIGMA_ABSORB_ROD = 0.85      # control rod absorption
_SIGMA_ABSORB_XE = 0.60       # xenon-135 absorption (huge!)
_SIGMA_SCATTER_MOD = 0.30     # moderator scattering (thermalization)
_NEUTRON_DIFFUSION = 0.25     # diffusion coefficient
_NEUTRON_SPEED = 1.0          # normalized speed
_DELAYED_FRAC = 0.0065        # delayed neutron fraction (beta)
_DELAYED_DECAY = 0.08         # precursor decay rate

# Xenon dynamics
_XE_YIELD = 0.003             # Xe-135 yield from fission
_XE_DECAY = 0.0001            # Xe-135 radioactive decay rate
_XE_ABSORB_BURNUP = 0.002     # Xe burnup rate from neutron flux
_IODINE_YIELD = 0.006         # I-135 yield (decays to Xe-135)
_IODINE_DECAY = 0.0003        # I-135 decay rate to Xe-135

# Thermal hydraulics
_HEAT_FROM_FISSION = 0.15     # heat generated per fission event
_COOLANT_FLOW_RATE = 0.05     # coolant heat removal rate
_COOLANT_INLET_TEMP = 0.15    # inlet temperature (normalized)
_FUEL_CONDUCTIVITY = 0.04     # fuel thermal conductivity
_CONVECTIVE_COEFF = 0.08      # fuel-to-coolant heat transfer
_FUEL_MELT_TEMP = 0.95        # fuel melting threshold
_COOLANT_BOIL_TEMP = 0.55     # coolant boiling point
_CLAD_FAIL_TEMP = 0.80        # cladding failure temperature

# Reactivity feedback
_DOPPLER_COEFF = -0.003       # negative Doppler (always stabilizing)
_VOID_COEFF_PWR = -0.015      # negative void coefficient (PWR)
_VOID_COEFF_RBMK = 0.012      # positive void coefficient (RBMK/Chernobyl)

# Decay heat
_DECAY_HEAT_FRAC = 0.07       # decay heat as fraction of full power
_DECAY_HEAT_HALFLIFE = 300     # ticks for decay heat to halve

# Hydrogen generation
_H2_GEN_TEMP = 0.75           # temperature threshold for Zr-steam reaction
_H2_GEN_RATE = 0.005          # hydrogen generation rate above threshold

# Containment
_CONTAINMENT_VOLUME = 1.0
_CONTAINMENT_FAIL_P = 0.95    # containment failure pressure

_MAX_HIST = 300
_MAX_NEUTRONS = 2000


# ======================================================================
#  Preset Parameters
# ======================================================================

def _get_reactor_params(preset_id):
    """Return parameter dict for given preset."""
    defaults = {
        "control_rod_pos": 0.5,       # 0=fully inserted, 1=fully withdrawn
        "void_coeff": _VOID_COEFF_PWR,
        "initial_power": 0.5,
        "coolant_available": True,
        "pumps_running": True,
        "scram_enabled": True,
        "has_moderator": True,
        "initial_xenon": 0.3,
        "initial_iodine": 0.3,
        "decay_heat_level": 0.0,
        "breach_loca": False,
        "k_eff_target": 1.0,
        "fuel_enrichment": 1.0,
    }
    overrides = {
        "normal": {
            "control_rod_pos": 0.45,
            "initial_power": 0.5,
            "initial_xenon": 0.25,
            "initial_iodine": 0.25,
        },
        "rod_withdrawal": {
            "control_rod_pos": 0.85,
            "initial_power": 0.6,
            "scram_enabled": False,
        },
        "xenon_restart": {
            "control_rod_pos": 0.90,
            "void_coeff": _VOID_COEFF_RBMK,
            "initial_xenon": 0.8,
            "initial_iodine": 0.6,
            "initial_power": 0.15,
            "scram_enabled": False,
            "has_moderator": True,
        },
        "loca": {
            "control_rod_pos": 0.45,
            "initial_power": 0.5,
            "breach_loca": True,
            "coolant_available": True,
        },
        "blackout": {
            "control_rod_pos": 0.10,
            "initial_power": 0.08,
            "pumps_running": False,
            "decay_heat_level": 0.06,
            "coolant_available": True,
        },
        "breeder": {
            "control_rod_pos": 0.55,
            "has_moderator": False,
            "fuel_enrichment": 1.4,
            "initial_power": 0.45,
            "void_coeff": -0.005,
        },
    }
    return {**defaults, **overrides.get(preset_id, {})}


# ======================================================================
#  Helper: build reactor geometry
# ======================================================================

def _build_reactor_core(rows, cols, params):
    """Build 2D reactor cross-section grid."""
    grid = [[_CELL_EMPTY] * cols for _ in range(rows)]
    cy, cx = rows // 2, cols // 2
    radius = min(rows, cols) // 2 - 2

    # Fill vessel
    for r in range(rows):
        for c in range(cols):
            dy, dx = r - cy, c - cx
            dist = math.sqrt(dy * dy + dx * dx)
            if dist <= radius:
                if dist >= radius - 1:
                    grid[r][c] = _CELL_VESSEL_WALL
                elif dist >= radius - 2:
                    grid[r][c] = _CELL_REFLECTOR
                else:
                    # Alternating fuel and moderator/coolant pattern
                    if (r + c) % 3 == 0:
                        grid[r][c] = _CELL_FUEL
                    elif (r + c) % 3 == 1:
                        grid[r][c] = _CELL_MODERATOR if params["has_moderator"] else _CELL_FUEL
                    else:
                        grid[r][c] = _CELL_COOLANT
            elif dist <= radius + 1:
                grid[r][c] = _CELL_VESSEL_WALL

    # Control rod channels (vertical columns)
    n_rods = 5
    rod_spacing = max(3, (2 * radius) // (n_rods + 1))
    rod_positions = []
    for i in range(n_rods):
        rc = cx - radius + 3 + (i + 1) * rod_spacing
        if abs(rc - cx) < radius - 3:
            rod_positions.append(rc)

    return grid, rod_positions, cy, cx, radius


def _insert_control_rods(grid, rod_positions, cy, radius, rod_pos_frac):
    """Insert control rods based on position fraction (0=in, 1=out)."""
    rod_cells = []
    insertion_depth = int((1.0 - rod_pos_frac) * (radius * 1.5))
    for rc in rod_positions:
        for r in range(max(0, cy - radius + 2), min(len(grid), cy + radius - 1)):
            if r < cy - radius + 2 + insertion_depth:
                if 0 <= rc < len(grid[0]) and grid[r][rc] != _CELL_VESSEL_WALL:
                    if grid[r][rc] != _CELL_MELTED and grid[r][rc] != _CELL_CORIUM:
                        grid[r][rc] = _CELL_CONTROL_ROD
                        rod_cells.append((r, rc))
            else:
                if 0 <= rc < len(grid[0]) and grid[r][rc] == _CELL_CONTROL_ROD:
                    grid[r][rc] = _CELL_COOLANT
    return rod_cells


# ======================================================================
#  Enter / Exit
# ======================================================================

def _enter_nuclear_reactor_mode(self):
    """Enter mode — show preset menu."""
    self.nuclear_reactor_mode = True
    self.nuclear_reactor_menu = True
    self.nuclear_reactor_menu_sel = 0
    self.nuclear_reactor_running = False
    self._flash("Nuclear Reactor Physics — select a configuration")


def _exit_nuclear_reactor_mode(self):
    """Exit mode and clean up."""
    self.nuclear_reactor_mode = False
    self.nuclear_reactor_menu = False
    self.nuclear_reactor_running = False
    for attr in list(vars(self)):
        if attr.startswith('nuclear_reactor_') and attr != 'nuclear_reactor_mode':
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ======================================================================
#  Initialization
# ======================================================================

def _nuclear_reactor_init(self, preset_idx):
    """Initialize simulation for the chosen preset."""
    name, _desc, pid = NUCLEAR_REACTOR_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()

    self.nuclear_reactor_preset_name = name
    self.nuclear_reactor_preset_id = pid
    rows = max(24, max_y - 4)
    cols = max(40, max_x - 2)
    self.nuclear_reactor_rows = rows
    self.nuclear_reactor_cols = cols
    self.nuclear_reactor_generation = 0
    self.nuclear_reactor_running = False
    self.nuclear_reactor_menu = False
    self.nuclear_reactor_view = 0  # 0=cross-section, 1=temp/pressure, 2=graphs
    self.nuclear_reactor_scram = False
    self.nuclear_reactor_meltdown = False

    params = _get_reactor_params(pid)
    self.nuclear_reactor_params = params

    # Build geometry
    grid, rod_positions, cy, cx, radius = _build_reactor_core(rows, cols, params)
    self.nuclear_reactor_grid = grid
    self.nuclear_reactor_rod_positions = rod_positions
    self.nuclear_reactor_cy = cy
    self.nuclear_reactor_cx = cx
    self.nuclear_reactor_radius = radius

    # Control rod position
    self.nuclear_reactor_rod_pos = params["control_rod_pos"]
    _insert_control_rods(grid, rod_positions, cy, radius, self.nuclear_reactor_rod_pos)

    # Neutron flux field
    self.nuclear_reactor_flux = [[0.0] * cols for _ in range(rows)]
    # Seed initial flux
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == _CELL_FUEL:
                self.nuclear_reactor_flux[r][c] = params["initial_power"] * (0.5 + 0.5 * random.random())

    # Delayed neutron precursors
    self.nuclear_reactor_precursors = [[0.0] * cols for _ in range(rows)]

    # Temperature fields
    self.nuclear_reactor_fuel_temp = [[0.2] * cols for _ in range(rows)]
    self.nuclear_reactor_coolant_temp = [[_COOLANT_INLET_TEMP] * cols for _ in range(rows)]

    # Xenon and iodine concentration fields
    self.nuclear_reactor_xenon = [[params["initial_xenon"] * (0.8 + 0.4 * random.random()) if grid[r][c] == _CELL_FUEL else 0.0 for c in range(cols)] for r in range(rows)]
    self.nuclear_reactor_iodine = [[params["initial_iodine"] * (0.8 + 0.4 * random.random()) if grid[r][c] == _CELL_FUEL else 0.0 for c in range(cols)] for r in range(rows)]

    # Void fraction (steam)
    self.nuclear_reactor_void = [[0.0] * cols for _ in range(rows)]

    # Containment pressure
    self.nuclear_reactor_containment_p = 0.1
    # Hydrogen accumulation
    self.nuclear_reactor_hydrogen = 0.0
    # Decay heat
    self.nuclear_reactor_decay_heat = params["decay_heat_level"]
    # Coolant level (1.0 = full)
    self.nuclear_reactor_coolant_level = 1.0
    # LOCA state
    self.nuclear_reactor_loca_active = params["breach_loca"]
    self.nuclear_reactor_loca_tick = 0
    # Pumps
    self.nuclear_reactor_pumps = params["pumps_running"]

    # Damage tracking
    self.nuclear_reactor_damaged = [[False] * cols for _ in range(rows)]

    # Metrics history
    self.nuclear_reactor_history = {
        'k_eff': [],
        'neutron_flux': [],
        'fuel_temp': [],
        'coolant_temp': [],
        'xenon': [],
        'power': [],
        'rod_pos': [],
        'void_frac': [],
        'dose_rate': [],
        'containment_p': [],
    }

    self._flash(f"Nuclear Reactor: {name}")


# ======================================================================
#  Physics Simulation Step
# ======================================================================

def _nuclear_reactor_step(self):
    """One tick of reactor simulation."""
    rows = self.nuclear_reactor_rows
    cols = self.nuclear_reactor_cols
    grid = self.nuclear_reactor_grid
    flux = self.nuclear_reactor_flux
    prec = self.nuclear_reactor_precursors
    f_temp = self.nuclear_reactor_fuel_temp
    c_temp = self.nuclear_reactor_coolant_temp
    xenon = self.nuclear_reactor_xenon
    iodine = self.nuclear_reactor_iodine
    void = self.nuclear_reactor_void
    params = self.nuclear_reactor_params
    damaged = self.nuclear_reactor_damaged

    # --- Rebuild control rods each tick ---
    # First clear old rod cells
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == _CELL_CONTROL_ROD:
                grid[r][c] = _CELL_COOLANT
    if self.nuclear_reactor_scram:
        self.nuclear_reactor_rod_pos = max(0.0, self.nuclear_reactor_rod_pos - 0.05)
    _insert_control_rods(grid, self.nuclear_reactor_rod_positions,
                         self.nuclear_reactor_cy, self.nuclear_reactor_radius,
                         self.nuclear_reactor_rod_pos)

    # --- LOCA: coolant loss ---
    if self.nuclear_reactor_loca_active:
        self.nuclear_reactor_loca_tick += 1
        drain = 0.003 + 0.001 * min(self.nuclear_reactor_loca_tick, 50)
        self.nuclear_reactor_coolant_level = max(0.0, self.nuclear_reactor_coolant_level - drain)
        self.nuclear_reactor_containment_p += 0.002

    # --- Pumps off: reduced cooling ---
    if not self.nuclear_reactor_pumps:
        effective_flow = _COOLANT_FLOW_RATE * 0.05  # natural circulation only
    else:
        effective_flow = _COOLANT_FLOW_RATE

    coolant_avail = self.nuclear_reactor_coolant_level

    # --- Neutron transport ---
    new_flux = [[0.0] * cols for _ in range(rows)]
    total_fission = 0.0
    total_flux = 0.0

    for r in range(rows):
        for c in range(cols):
            cell = grid[r][c]
            phi = flux[r][c]

            if cell == _CELL_EMPTY or cell == _CELL_VESSEL_WALL:
                new_flux[r][c] = 0.0
                continue

            if cell == _CELL_MELTED or cell == _CELL_CORIUM:
                # Some residual flux in melted regions
                new_flux[r][c] = phi * 0.5
                continue

            # Diffusion: gather from neighbors
            diff_sum = 0.0
            n_count = 0
            for dr, dc in _NEIGHBORS_4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    ng = grid[nr][nc]
                    if ng not in (_CELL_EMPTY, _CELL_VESSEL_WALL):
                        diff_sum += flux[nr][nc]
                        n_count += 1

            laplacian = (diff_sum - n_count * phi) if n_count > 0 else 0.0
            diffused = phi + _NEUTRON_DIFFUSION * laplacian

            if cell == _CELL_FUEL:
                # Fission source
                enrichment = params["fuel_enrichment"]
                sigma_f = _SIGMA_FISSION * enrichment
                fission_rate = sigma_f * phi
                # Doppler feedback
                doppler = 1.0 + _DOPPLER_COEFF * max(0, f_temp[r][c] - 0.3)
                fission_rate *= max(0.1, doppler)
                # Void feedback
                v = void[r][c]
                void_fb = 1.0 + params["void_coeff"] * v * 10.0
                fission_rate *= max(0.1, void_fb)

                # Xenon absorption
                xe_absorb = _SIGMA_ABSORB_XE * xenon[r][c] * phi
                # Parasitic absorption
                para_absorb = _SIGMA_ABSORB_FUEL * phi

                # Prompt neutrons
                prompt = fission_rate * _FISSION_YIELD * (1.0 - _DELAYED_FRAC)
                # Delayed neutrons from precursors
                delayed = _DELAYED_DECAY * prec[r][c]

                new_flux[r][c] = max(0.0, diffused + prompt + delayed - xe_absorb - para_absorb)
                total_fission += fission_rate
                total_flux += new_flux[r][c]

                # Update precursors
                prec[r][c] += fission_rate * _FISSION_YIELD * _DELAYED_FRAC - _DELAYED_DECAY * prec[r][c]
                prec[r][c] = max(0.0, prec[r][c])

            elif cell == _CELL_CONTROL_ROD:
                new_flux[r][c] = max(0.0, diffused * (1.0 - _SIGMA_ABSORB_ROD))

            elif cell == _CELL_MODERATOR:
                # Scattering (thermalization) — enhances fission in nearby fuel
                new_flux[r][c] = max(0.0, diffused * (1.0 + _SIGMA_SCATTER_MOD * 0.3))

            elif cell == _CELL_COOLANT:
                # Some moderation in water coolant
                mod_boost = 0.1 if params["has_moderator"] else 0.0
                new_flux[r][c] = max(0.0, diffused * (1.0 + mod_boost))

            elif cell == _CELL_REFLECTOR:
                new_flux[r][c] = max(0.0, diffused * 0.85)

            else:
                new_flux[r][c] = max(0.0, diffused * 0.9)

    # Cap neutron flux
    for r in range(rows):
        for c in range(cols):
            new_flux[r][c] = min(3.0, new_flux[r][c])
    self.nuclear_reactor_flux = new_flux

    # --- Xenon / Iodine dynamics ---
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == _CELL_FUEL:
                phi = new_flux[r][c]
                # Iodine production from fission, decay to xenon
                iodine[r][c] += _IODINE_YIELD * phi - _IODINE_DECAY * iodine[r][c]
                iodine[r][c] = max(0.0, min(2.0, iodine[r][c]))
                # Xenon: from iodine decay + direct fission yield - decay - neutron burnup
                xenon[r][c] += (_IODINE_DECAY * iodine[r][c] +
                                _XE_YIELD * phi -
                                _XE_DECAY * xenon[r][c] -
                                _XE_ABSORB_BURNUP * phi * xenon[r][c])
                xenon[r][c] = max(0.0, min(2.0, xenon[r][c]))

    # --- Thermal hydraulics ---
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == _CELL_FUEL or grid[r][c] == _CELL_MELTED:
                # Heat from fission + decay heat
                q_fission = _HEAT_FROM_FISSION * new_flux[r][c]
                q_decay = self.nuclear_reactor_decay_heat * 0.5
                # Conduction within fuel
                t_neighbors = 0.0
                t_count = 0
                for dr, dc in _NEIGHBORS_4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        t_neighbors += f_temp[nr][nc]
                        t_count += 1
                t_cond = _FUEL_CONDUCTIVITY * (t_neighbors / max(1, t_count) - f_temp[r][c]) if t_count > 0 else 0.0
                # Convective removal to coolant
                local_coolant = coolant_avail * (1.0 - void[r][c])
                q_conv = _CONVECTIVE_COEFF * (f_temp[r][c] - c_temp[r][c]) * local_coolant
                f_temp[r][c] += q_fission + q_decay + t_cond - q_conv
                f_temp[r][c] = max(0.0, min(1.5, f_temp[r][c]))

                # Coolant heating
                if grid[r][c] != _CELL_MELTED:
                    c_temp[r][c] += q_conv * 0.5 - effective_flow * (c_temp[r][c] - _COOLANT_INLET_TEMP) * local_coolant
                    c_temp[r][c] = max(0.0, min(1.2, c_temp[r][c]))

            elif grid[r][c] == _CELL_COOLANT or grid[r][c] == _CELL_MODERATOR:
                # Coolant: flow toward inlet temp
                c_temp[r][c] += -effective_flow * (c_temp[r][c] - _COOLANT_INLET_TEMP) * coolant_avail
                c_temp[r][c] = max(0.0, min(1.2, c_temp[r][c]))

    # --- Void (steam) formation ---
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] in (_CELL_COOLANT, _CELL_MODERATOR, _CELL_FUEL):
                if c_temp[r][c] > _COOLANT_BOIL_TEMP:
                    void[r][c] = min(1.0, void[r][c] + 0.05 * (c_temp[r][c] - _COOLANT_BOIL_TEMP))
                else:
                    void[r][c] = max(0.0, void[r][c] - 0.02)
                # Low coolant increases void
                if coolant_avail < 0.5:
                    void[r][c] = min(1.0, void[r][c] + 0.01 * (1.0 - coolant_avail))

    # --- Fuel damage / meltdown ---
    melt_count = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == _CELL_FUEL:
                if f_temp[r][c] >= _FUEL_MELT_TEMP:
                    grid[r][c] = _CELL_MELTED
                    damaged[r][c] = True
                    melt_count += 1
                    self.nuclear_reactor_containment_p += 0.003
                elif f_temp[r][c] >= _CLAD_FAIL_TEMP:
                    damaged[r][c] = True
                    # Hydrogen generation from zirconium-steam reaction
                    if f_temp[r][c] >= _H2_GEN_TEMP:
                        self.nuclear_reactor_hydrogen += _H2_GEN_RATE * (f_temp[r][c] - _H2_GEN_TEMP)
                        self.nuclear_reactor_containment_p += 0.001
            elif grid[r][c] == _CELL_MELTED:
                melt_count += 1
                # Corium slumping (gravity: moves down)
                if r + 1 < rows and grid[r + 1][c] in (_CELL_COOLANT, _CELL_EMPTY, _CELL_MODERATOR):
                    if random.random() < 0.02:
                        grid[r + 1][c] = _CELL_CORIUM
                        f_temp[r + 1][c] = f_temp[r][c] * 0.9

    if melt_count > 5:
        self.nuclear_reactor_meltdown = True

    # --- Decay heat update ---
    if total_fission > 0:
        self.nuclear_reactor_decay_heat = max(self.nuclear_reactor_decay_heat,
                                              _DECAY_HEAT_FRAC * total_fission / max(1.0, total_flux + 1.0))
    else:
        self.nuclear_reactor_decay_heat *= (1.0 - 1.0 / _DECAY_HEAT_HALFLIFE)

    # --- Auto-SCRAM ---
    if params["scram_enabled"] and not self.nuclear_reactor_scram:
        avg_flux = total_flux / max(1, sum(1 for r in range(rows) for c in range(cols) if grid[r][c] == _CELL_FUEL))
        if avg_flux > 1.5 or self.nuclear_reactor_meltdown:
            self.nuclear_reactor_scram = True

    # --- Containment ---
    self.nuclear_reactor_containment_p += self.nuclear_reactor_hydrogen * 0.001
    self.nuclear_reactor_containment_p = max(0.0, self.nuclear_reactor_containment_p - 0.0005)  # slow leak
    self.nuclear_reactor_containment_p = min(1.5, self.nuclear_reactor_containment_p)

    # --- Record metrics ---
    _nuclear_reactor_record_metrics(self, total_fission, total_flux)
    self.nuclear_reactor_generation += 1


def _nuclear_reactor_record_metrics(self, total_fission, total_flux):
    """Record telemetry for sparkline graphs."""
    rows = self.nuclear_reactor_rows
    cols = self.nuclear_reactor_cols
    grid = self.nuclear_reactor_grid
    flux = self.nuclear_reactor_flux
    f_temp = self.nuclear_reactor_fuel_temp
    c_temp = self.nuclear_reactor_coolant_temp
    xenon = self.nuclear_reactor_xenon
    void = self.nuclear_reactor_void
    h = self.nuclear_reactor_history

    # Count fuel cells
    fuel_cells = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] in (_CELL_FUEL, _CELL_MELTED)]
    n_fuel = max(1, len(fuel_cells))

    # k-effective estimate: production / (absorption + leakage)
    total_prod = total_fission * _FISSION_YIELD if total_fission > 0 else 0.001
    total_abs = sum(flux[r][c] * (_SIGMA_ABSORB_FUEL + _SIGMA_ABSORB_XE * xenon[r][c])
                    for r, c in fuel_cells) + 0.001
    k_eff = total_prod / total_abs
    k_eff = min(3.0, max(0.0, k_eff))

    avg_flux = total_flux / n_fuel
    avg_fuel_t = sum(f_temp[r][c] for r, c in fuel_cells) / n_fuel
    avg_cool_t = sum(c_temp[r][c] for r in range(rows) for c in range(cols)
                     if grid[r][c] in (_CELL_COOLANT, _CELL_MODERATOR)) / max(1, sum(
                         1 for r in range(rows) for c in range(cols)
                         if grid[r][c] in (_CELL_COOLANT, _CELL_MODERATOR)))
    avg_xe = sum(xenon[r][c] for r, c in fuel_cells) / n_fuel
    power = total_fission * _HEAT_FROM_FISSION
    avg_void = sum(void[r][c] for r in range(rows) for c in range(cols)
                   if grid[r][c] in (_CELL_FUEL, _CELL_COOLANT, _CELL_MODERATOR)) / max(1, sum(
                       1 for r in range(rows) for c in range(cols)
                       if grid[r][c] in (_CELL_FUEL, _CELL_COOLANT, _CELL_MODERATOR)))
    dose = avg_flux * 2.0 + self.nuclear_reactor_hydrogen * 5.0

    h['k_eff'].append(k_eff)
    h['neutron_flux'].append(avg_flux)
    h['fuel_temp'].append(avg_fuel_t)
    h['coolant_temp'].append(avg_cool_t)
    h['xenon'].append(avg_xe)
    h['power'].append(power)
    h['rod_pos'].append(self.nuclear_reactor_rod_pos)
    h['void_frac'].append(avg_void)
    h['dose_rate'].append(dose)
    h['containment_p'].append(self.nuclear_reactor_containment_p)

    for key in h:
        if len(h[key]) > _MAX_HIST:
            h[key].pop(0)


# ======================================================================
#  Input Handling
# ======================================================================

def _handle_nuclear_reactor_menu_key(self, key):
    """Handle input in preset menu."""
    n = len(NUCLEAR_REACTOR_PRESETS)
    if key in (ord("j"), curses.KEY_DOWN):
        self.nuclear_reactor_menu_sel = (self.nuclear_reactor_menu_sel + 1) % n
    elif key in (ord("k"), curses.KEY_UP):
        self.nuclear_reactor_menu_sel = (self.nuclear_reactor_menu_sel - 1) % n
    elif key in (ord("\n"), ord("\r")):
        self._nuclear_reactor_init(self.nuclear_reactor_menu_sel)
    elif key in (ord("q"), 27):
        self._exit_nuclear_reactor_mode()
    return True


def _handle_nuclear_reactor_key(self, key):
    """Handle input in active simulation."""
    if key == ord(" "):
        self.nuclear_reactor_running = not self.nuclear_reactor_running
    elif key in (ord("n"), ord(".")):
        self._nuclear_reactor_step()
    elif key == ord("v"):
        self.nuclear_reactor_view = (self.nuclear_reactor_view + 1) % 3
    elif key == ord("+") or key == ord("="):
        # Withdraw rods (increase reactivity)
        self.nuclear_reactor_rod_pos = min(1.0, self.nuclear_reactor_rod_pos + 0.03)
        self.nuclear_reactor_scram = False
    elif key == ord("-") or key == ord("_"):
        # Insert rods (decrease reactivity)
        self.nuclear_reactor_rod_pos = max(0.0, self.nuclear_reactor_rod_pos - 0.03)
    elif key == ord("s"):
        # SCRAM — emergency shutdown
        self.nuclear_reactor_scram = True
    elif key == ord("p"):
        # Toggle pumps
        self.nuclear_reactor_pumps = not self.nuclear_reactor_pumps
    elif key == ord("l"):
        # Trigger LOCA
        self.nuclear_reactor_loca_active = not self.nuclear_reactor_loca_active
    elif key == ord("r"):
        idx = next((i for i, p in enumerate(NUCLEAR_REACTOR_PRESETS)
                    if p[0] == self.nuclear_reactor_preset_name), 0)
        self._nuclear_reactor_init(idx)
    elif key in (ord("R"), ord("m")):
        self.nuclear_reactor_mode = True
        self.nuclear_reactor_menu = True
        self.nuclear_reactor_running = False
    elif key in (ord("q"), 27):
        self._exit_nuclear_reactor_mode()
    else:
        return False
    return True


# ======================================================================
#  Drawing: Preset Menu
# ======================================================================

def _draw_nuclear_reactor_menu(self, max_y, max_x):
    """Draw the preset selection menu."""
    self.stdscr.erase()
    title = "── Nuclear Reactor Physics & Meltdown Dynamics ── Select Preset ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(NUCLEAR_REACTOR_PRESETS):
        y = 3 + i * 3
        if y >= max_y - 2:
            break
        attr = curses.color_pair(7) | curses.A_REVERSE if i == self.nuclear_reactor_menu_sel else curses.color_pair(6)
        marker = ">" if i == self.nuclear_reactor_menu_sel else " "
        try:
            self.stdscr.addstr(y, 2, f"{marker} {name}", attr | curses.A_BOLD)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(y + 1, 4, desc[:max_x - 6], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    hint = " [j/k]=navigate  [Enter]=select  [q]=cancel"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


# ======================================================================
#  Drawing: View 1 — Reactor Cross-Section Map
# ======================================================================

def _draw_nuclear_reactor(self, max_y, max_x):
    """Draw the currently selected view."""
    view = getattr(self, 'nuclear_reactor_view', 0)
    if view == 0:
        _draw_reactor_crosssection(self, max_y, max_x)
    elif view == 1:
        _draw_reactor_thermal(self, max_y, max_x)
    else:
        _draw_reactor_graphs(self, max_y, max_x)


def _draw_reactor_crosssection(self, max_y, max_x):
    """View 1: Reactor cross-section with neutron flux overlay."""
    self.stdscr.erase()
    grid = self.nuclear_reactor_grid
    flux = self.nuclear_reactor_flux
    damaged = self.nuclear_reactor_damaged
    rows = self.nuclear_reactor_rows
    cols = self.nuclear_reactor_cols
    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, max_x - 1)

    for r in range(draw_rows):
        line = []
        for c in range(draw_cols):
            cell = grid[r][c]
            phi = flux[r][c]

            if cell == _CELL_VESSEL_WALL:
                ch = '#'
                cp = 7
            elif cell == _CELL_REFLECTOR:
                ch = '='
                cp = 7
            elif cell == _CELL_CONTROL_ROD:
                ch = '|'
                cp = 5  # magenta
            elif cell == _CELL_CORIUM:
                ch = '@'
                cp = 2  # red
            elif cell == _CELL_MELTED:
                ch = '*'
                cp = 2  # red
            elif cell == _CELL_FUEL:
                # Flux-colored fuel
                if damaged[r][c]:
                    ch = 'x'
                    cp = 2
                elif phi > 1.0:
                    ch = '#'
                    cp = 2  # high flux = red
                elif phi > 0.5:
                    ch = 'O'
                    cp = 4  # yellow
                elif phi > 0.2:
                    ch = 'o'
                    cp = 3  # green
                else:
                    ch = '.'
                    cp = 6  # cyan
            elif cell == _CELL_MODERATOR:
                if phi > 0.3:
                    ch = ':'
                    cp = 7
                else:
                    ch = '~'
                    cp = 6
            elif cell == _CELL_COOLANT:
                v = self.nuclear_reactor_void[r][c]
                if v > 0.5:
                    ch = '^'  # steam
                    cp = 7
                elif v > 0.2:
                    ch = 'o'
                    cp = 6
                else:
                    ch = '~'
                    cp = 5 if self.nuclear_reactor_coolant_level < 0.5 else 6
            else:
                ch = ' '
                cp = 7

            try:
                self.stdscr.addstr(1 + r, c, ch, curses.color_pair(cp))
            except curses.error:
                pass

    # Title bar
    gen = self.nuclear_reactor_generation
    rod = self.nuclear_reactor_rod_pos
    scram = " SCRAM!" if self.nuclear_reactor_scram else ""
    melt = " MELTDOWN!" if self.nuclear_reactor_meltdown else ""
    k_eff_str = ""
    if self.nuclear_reactor_history['k_eff']:
        k_eff_str = f" k={self.nuclear_reactor_history['k_eff'][-1]:.3f}"

    title = f" {self.nuclear_reactor_preset_name} | t={gen} | Rods={rod:.0%}{k_eff_str}{scram}{melt}"
    try:
        cp = 2 if self.nuclear_reactor_meltdown else (4 if self.nuclear_reactor_scram else 7)
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(cp) | curses.A_BOLD)
    except curses.error:
        pass

    # Status bar
    h2 = self.nuclear_reactor_hydrogen
    cont_p = self.nuclear_reactor_containment_p
    cool_lvl = self.nuclear_reactor_coolant_level
    pumps = "ON" if self.nuclear_reactor_pumps else "OFF"
    loca = " LOCA!" if self.nuclear_reactor_loca_active else ""
    status = (f" [v]iew [+/-]rods [s]cram [p]umps:{pumps} [l]oca{loca}"
              f" | H2={h2:.2f} P={cont_p:.2f} Cool={cool_lvl:.0%} [r]eset [q]uit")
    try:
        self.stdscr.addstr(max_y - 1, 0, status[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing: View 2 — Temperature / Pressure Heatmap
# ======================================================================

def _draw_reactor_thermal(self, max_y, max_x):
    """View 2: Temperature heatmap with void overlay."""
    self.stdscr.erase()
    grid = self.nuclear_reactor_grid
    f_temp = self.nuclear_reactor_fuel_temp
    c_temp = self.nuclear_reactor_coolant_temp
    void = self.nuclear_reactor_void
    rows = self.nuclear_reactor_rows
    cols = self.nuclear_reactor_cols
    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, max_x - 1)

    temp_chars = " .:-=+*#%@"

    for r in range(draw_rows):
        for c in range(draw_cols):
            cell = grid[r][c]
            if cell in (_CELL_EMPTY,):
                ch = ' '
                cp = 7
            elif cell == _CELL_VESSEL_WALL:
                ch = '#'
                cp = 7
            else:
                # Temperature mapping
                if cell in (_CELL_FUEL, _CELL_MELTED, _CELL_CORIUM):
                    t = f_temp[r][c]
                else:
                    t = c_temp[r][c]

                idx = int(t / 1.0 * (len(temp_chars) - 1))
                idx = max(0, min(len(temp_chars) - 1, idx))
                ch = temp_chars[idx]

                # Color by temperature band
                if t > 0.8:
                    cp = 2  # red — danger
                elif t > 0.55:
                    cp = 4  # yellow — hot
                elif t > 0.3:
                    cp = 3  # green — warm
                elif t > 0.15:
                    cp = 6  # cyan — cool
                else:
                    cp = 5  # blue — cold

                # Void overlay
                v = void[r][c]
                if v > 0.5:
                    ch = '^'
                    cp = 7

            try:
                self.stdscr.addstr(1 + r, c, ch, curses.color_pair(cp))
            except curses.error:
                pass

    # Title
    title = f" THERMAL VIEW | {self.nuclear_reactor_preset_name} | t={self.nuclear_reactor_generation}"
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Legend and status
    legend = " Cold[.] Cool[:] Warm[=] Hot[*] Danger[@] Steam[^]"
    try:
        self.stdscr.addstr(max_y - 2, 0, legend[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    status = f" [v]iew [+/-]rods [s]cram [p]umps [l]oca [r]eset [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 0, status[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing: View 3 — Time-Series Sparkline Graphs
# ======================================================================

def _draw_reactor_graphs(self, max_y, max_x):
    """View 3: Time-series sparkline graphs for 10 metrics."""
    self.stdscr.erase()
    h = self.nuclear_reactor_history
    spark = " ▁▂▃▄▅▆▇█"
    n_bars = len(spark)

    metrics = [
        ('k_eff', 'k-effective', 4),
        ('neutron_flux', 'Neutron Flux', 3),
        ('fuel_temp', 'Fuel Temp', 2),
        ('coolant_temp', 'Coolant Temp', 6),
        ('xenon', 'Xe-135 Conc', 5),
        ('power', 'Thermal Power', 4),
        ('rod_pos', 'Rod Position', 7),
        ('void_frac', 'Void Fraction', 3),
        ('dose_rate', 'Dose Rate', 2),
        ('containment_p', 'Containment P', 2),
    ]

    title = f" METRICS | {self.nuclear_reactor_preset_name} | t={self.nuclear_reactor_generation}"
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    graph_w = max(10, max_x - 28)
    row_h = max(1, (max_y - 3) // len(metrics))

    for mi, (key, label, cp) in enumerate(metrics):
        base_y = 2 + mi * row_h
        if base_y >= max_y - 2:
            break

        data = h.get(key, [])
        # Label with current value
        val_str = f"{data[-1]:.3f}" if data else "—"
        lbl = f"{label:>16s} {val_str:>7s} "
        try:
            self.stdscr.addstr(base_y, 0, lbl[:26], curses.color_pair(cp))
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

    status = " [v]iew [+/-]rods [s]cram [p]umps [l]oca [space]pause [r]eset [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 0, status[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Registration
# ======================================================================

def register(App):
    """Register nuclear reactor physics mode methods on the App class."""
    App.NUCLEAR_REACTOR_PRESETS = NUCLEAR_REACTOR_PRESETS
    App._enter_nuclear_reactor_mode = _enter_nuclear_reactor_mode
    App._exit_nuclear_reactor_mode = _exit_nuclear_reactor_mode
    App._nuclear_reactor_init = _nuclear_reactor_init
    App._nuclear_reactor_step = _nuclear_reactor_step
    App._handle_nuclear_reactor_menu_key = _handle_nuclear_reactor_menu_key
    App._handle_nuclear_reactor_key = _handle_nuclear_reactor_key
    App._draw_nuclear_reactor_menu = _draw_nuclear_reactor_menu
    App._draw_nuclear_reactor = _draw_nuclear_reactor
