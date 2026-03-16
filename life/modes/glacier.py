"""Mode: glacier — Glacier Dynamics & Ice Age Cycles.

Simulates deep-time climate with:
- Milankovitch orbital forcing (eccentricity ~100kyr, obliquity ~41kyr, precession ~23kyr)
  driving insolation variations at high latitudes
- Ice-albedo feedback (ice reflects sunlight → cooling → more ice → runaway glaciation)
- CO2 greenhouse coupling (volcanic outgassing vs silicate weathering sink vs ocean absorption)
- Ice sheet advance/retreat across a latitudinal cross-section (pole-to-equator)
- Sea level change from ice volume (ice growth lowers sea level, melting raises it)
- Isostatic crustal rebound (lithosphere depresses under ice load, rebounds when ice retreats)
- Heinrich events (iceberg armada calving surges from ice sheet instability)
- Dansgaard-Oeschger rapid warming oscillations (abrupt ~10°C jumps in decades)
- Interglacial/glacial state transitions driven by orbital + feedback coupling

Three views:
  1) Polar-to-equatorial cross-section with advancing/retreating ice sheets,
     bedrock depression, sea level line, albedo overlay
  2) Time-series dashboard: temperature/CO2/ice volume/sea level/insolation over deep time
  3) Orbital parameter phase space + feedback strength diagram

Six presets:
  Last Glacial Maximum, Holocene Optimum, Snowball Earth Onset,
  PETM Hothouse, Anthropogenic Rapid CO2 Injection,
  Dansgaard-Oeschger Oscillations
"""
import curses
import math
import random

# ======================================================================
#  Presets
# ======================================================================

GLACIER_PRESETS = [
    ("Last Glacial Maximum",
     "Peak ice extent ~20 ka — massive Laurentide & Fennoscandian sheets, low CO2, sea level -120m",
     "lgm"),
    ("Holocene Optimum",
     "Warm interglacial ~6 ka — retreated ice, elevated CO2, high obliquity insolation maximum",
     "holocene"),
    ("Snowball Earth Onset",
     "Neoproterozoic runaway glaciation — ice-albedo feedback driving equatorward ice advance",
     "snowball"),
    ("PETM Hothouse",
     "Paleocene-Eocene Thermal Maximum — massive CO2 release, no polar ice, extreme warmth",
     "petm"),
    ("Anthropogenic Rapid CO2 Injection",
     "Modern era — rapid fossil fuel CO2 pulse overwhelming natural sinks, accelerating ice loss",
     "anthropogenic"),
    ("Dansgaard-Oeschger Oscillations",
     "Abrupt glacial climate shifts — rapid ~10°C warming events with Heinrich event coupling",
     "do_oscillations"),
]

# ======================================================================
#  Physical constants (scaled for simulation)
# ======================================================================

_DT = 0.25                    # integration timestep
_NUM_LATS = 60                # latitude bands (pole to equator, symmetric)

# Milankovitch cycles (periods in ticks)
_ECCEN_PERIOD = 400           # ~100 kyr eccentricity
_OBLIQ_PERIOD = 164           # ~41 kyr obliquity
_PRECES_PERIOD = 92           # ~23 kyr precession
_ECCEN_AMP = 0.04             # eccentricity amplitude
_OBLIQ_AMP = 0.03             # obliquity modulation of polar insolation
_PRECES_AMP = 0.02            # precession modulation

# Insolation
_SOLAR_CONST = 1.0            # normalized solar constant
_BASE_ALBEDO_LAND = 0.25      # bare land albedo
_BASE_ALBEDO_OCEAN = 0.06     # open ocean albedo
_ICE_ALBEDO = 0.75            # ice/snow albedo
_ALBEDO_FEEDBACK = 0.6        # strength of ice-albedo feedback

# CO2 / greenhouse
_CO2_BASELINE = 280.0         # preindustrial CO2 (ppm)
_CO2_GREENHOUSE = 0.006       # warming per ppm above baseline (scaled)
_VOLCANIC_OUTGAS = 0.08       # CO2 outgassing rate (ppm/tick)
_WEATHERING_RATE = 0.0003     # silicate weathering CO2 sink (rate × temp × CO2)
_OCEAN_ABSORB = 0.0001        # ocean CO2 absorption (rate × CO2_excess)
_CO2_MIN = 150.0              # minimum CO2 floor
_CO2_MAX = 4000.0             # maximum CO2 cap

# Ice dynamics
_ICE_GROWTH_RATE = 0.012      # ice growth rate when cold
_ICE_MELT_RATE = 0.015        # ice melt rate when warm
_ICE_FLOW_RATE = 0.02         # ice sheet spreading rate (equatorward flow)
_ICE_MAX_THICKNESS = 3.0      # max ice thickness (km, scaled)
_CALVING_THRESHOLD = 2.0      # ice thickness threshold for calving
_CALVING_RATE = 0.15          # fraction lost per calving event
_HEINRICH_PROB = 0.003        # probability of Heinrich event per tick
_HEINRICH_SURGE = 0.4         # fraction of ice discharged in Heinrich event

# Temperature
_TEMP_DIFF = 0.03             # meridional heat diffusion
_BASE_TEMP_EQUATOR = 0.85     # equatorial base temperature (normalized 0-1)
_BASE_TEMP_POLE = 0.15        # polar base temperature
_TEMP_RESPONSE = 0.05         # temperature response rate to forcing

# Sea level
_SEA_LEVEL_SCALE = -40.0      # meters per unit of total ice volume
_SEA_LEVEL_BASELINE = 0.0     # reference sea level

# Isostasy
_ISOSTATIC_RATE = 0.003       # crustal depression/rebound rate
_ISOSTATIC_SCALE = 0.3        # depression per unit ice thickness

# D-O oscillations
_DO_PERIOD_MIN = 50           # minimum D-O cycle period (ticks)
_DO_PERIOD_MAX = 120          # maximum D-O cycle period (ticks)
_DO_WARMING_AMP = 0.08        # amplitude of D-O warming event
_DO_COOLING_RATE = 0.002      # gradual cooling between D-O events

# Metrics history cap
_HISTORY_LEN = 400


# ======================================================================
#  Helper functions
# ======================================================================

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _base_insolation(lat_idx, n_lats):
    """Base insolation by latitude (pole=0, equator=n_lats-1)."""
    lat_frac = lat_idx / max(1, n_lats - 1)  # 0=pole, 1=equator
    # Cosine distribution: more insolation at equator
    return _SOLAR_CONST * (0.2 + 0.8 * lat_frac)


def _milankovitch(tick, eccen_phase=0.0, obliq_phase=0.0, preces_phase=0.0):
    """Compute Milankovitch orbital forcing anomaly."""
    e = _ECCEN_AMP * math.sin(2 * math.pi * tick / _ECCEN_PERIOD + eccen_phase)
    o = _OBLIQ_AMP * math.sin(2 * math.pi * tick / _OBLIQ_PERIOD + obliq_phase)
    p = _PRECES_AMP * math.sin(2 * math.pi * tick / _PRECES_PERIOD + preces_phase)
    return e + o + p


def _milankovitch_components(tick, eccen_phase=0.0, obliq_phase=0.0, preces_phase=0.0):
    """Return individual Milankovitch components."""
    e = _ECCEN_AMP * math.sin(2 * math.pi * tick / _ECCEN_PERIOD + eccen_phase)
    o = _OBLIQ_AMP * math.sin(2 * math.pi * tick / _OBLIQ_PERIOD + obliq_phase)
    p = _PRECES_AMP * math.sin(2 * math.pi * tick / _PRECES_PERIOD + preces_phase)
    return e, o, p


def _append_metric(hist, key, val):
    """Append to history, cap at _HISTORY_LEN entries."""
    lst = hist[key]
    lst.append(val)
    if len(lst) > _HISTORY_LEN:
        del lst[0]


# ======================================================================
#  Enter / Exit
# ======================================================================

def _enter_glacier_mode(self):
    """Enter glacier dynamics mode — show preset menu."""
    self.glacier_mode = True
    self.glacier_menu = True
    self.glacier_menu_sel = 0


def _exit_glacier_mode(self):
    """Exit glacier dynamics mode."""
    self.glacier_mode = False
    self.glacier_menu = False
    self.glacier_running = False
    for attr in list(vars(self)):
        if attr.startswith('glacier_') and attr not in ('glacier_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ======================================================================
#  Initialization
# ======================================================================

def _glacier_init(self, preset_idx: int):
    """Initialize glacier dynamics simulation for chosen preset."""
    name, _desc, pid = GLACIER_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()

    n_lats = _NUM_LATS

    self.glacier_menu = False
    self.glacier_running = False
    self.glacier_preset_name = name
    self.glacier_preset_id = pid
    self.glacier_n_lats = n_lats
    self.glacier_generation = 0
    self.glacier_view = "crosssection"  # crosssection | graphs | orbital

    # Milankovitch phase offsets (can vary by preset)
    self.glacier_eccen_phase = 0.0
    self.glacier_obliq_phase = 0.0
    self.glacier_preces_phase = 0.0

    # Per-latitude-band state arrays (index 0 = pole, index n-1 = equator)
    self.glacier_temp = [0.0] * n_lats           # temperature (normalized 0-1)
    self.glacier_ice = [0.0] * n_lats            # ice thickness (0 to _ICE_MAX_THICKNESS)
    self.glacier_albedo = [0.0] * n_lats         # effective albedo
    self.glacier_bedrock = [0.0] * n_lats        # bedrock depression (negative = depressed)
    self.glacier_insolation = [0.0] * n_lats     # current insolation at each latitude

    # Global state
    self.glacier_co2 = _CO2_BASELINE             # atmospheric CO2 (ppm)
    self.glacier_sea_level = 0.0                  # sea level anomaly (m)
    self.glacier_total_ice = 0.0                  # total ice volume
    self.glacier_global_temp = 0.5                # global mean temperature
    self.glacier_co2_injection = 0.0              # external CO2 injection rate (ppm/tick)
    self.glacier_volcanic_mult = 1.0              # volcanic outgassing multiplier

    # D-O oscillation state
    self.glacier_do_timer = random.randint(_DO_PERIOD_MIN, _DO_PERIOD_MAX)
    self.glacier_do_active = False
    self.glacier_do_warmth = 0.0

    # Heinrich event state
    self.glacier_heinrich_active = False
    self.glacier_heinrich_cooldown = 0

    # Metrics history
    self.glacier_history = {
        'global_temp': [],
        'co2': [],
        'total_ice': [],
        'sea_level': [],
        'insolation_65n': [],
        'albedo_mean': [],
        'ice_extent': [],
        'weathering': [],
        'do_index': [],
        'heinrich': [],
    }

    # Apply preset
    _apply_preset(self, pid, n_lats)
    self._flash(f"Glacier Dynamics: {name}")


def _apply_preset(self, pid, n_lats):
    """Configure preset-specific initial conditions."""
    temp = self.glacier_temp
    ice = self.glacier_ice
    bedrock = self.glacier_bedrock

    # Base temperature: pole to equator gradient
    for i in range(n_lats):
        lat_frac = i / max(1, n_lats - 1)  # 0=pole, 1=equator
        temp[i] = _BASE_TEMP_POLE + (_BASE_TEMP_EQUATOR - _BASE_TEMP_POLE) * lat_frac

    if pid == "lgm":
        # Last Glacial Maximum — extensive ice, low CO2
        self.glacier_co2 = 190.0
        # Ice sheets covering ~30% of latitude bands from pole
        ice_extent = int(n_lats * 0.35)
        for i in range(ice_extent):
            frac = 1.0 - i / ice_extent
            ice[i] = _ICE_MAX_THICKNESS * frac * (0.8 + 0.2 * random.random())
            bedrock[i] = -_ISOSTATIC_SCALE * ice[i]
            temp[i] = max(0.05, temp[i] - 0.2 * frac)
        self.glacier_eccen_phase = math.pi * 0.3
        self.glacier_obliq_phase = math.pi * 0.8

    elif pid == "holocene":
        # Holocene Optimum — warm, minimal ice
        self.glacier_co2 = 280.0
        ice_extent = int(n_lats * 0.08)
        for i in range(ice_extent):
            frac = 1.0 - i / max(1, ice_extent)
            ice[i] = _ICE_MAX_THICKNESS * 0.3 * frac
            temp[i] = min(1.0, temp[i] + 0.05)
        self.glacier_obliq_phase = 0.0  # high obliquity = warm poles

    elif pid == "snowball":
        # Snowball Earth onset — low CO2, ice advancing from poles
        self.glacier_co2 = 200.0
        ice_extent = int(n_lats * 0.45)
        for i in range(ice_extent):
            frac = 1.0 - i / ice_extent
            ice[i] = _ICE_MAX_THICKNESS * 0.6 * frac
            bedrock[i] = -_ISOSTATIC_SCALE * ice[i] * 0.5
            temp[i] = max(0.02, temp[i] - 0.3 * frac)
        # Lower equatorial temps to push toward snowball
        for i in range(n_lats):
            temp[i] = max(0.02, temp[i] - 0.15)
        self.glacier_volcanic_mult = 0.3  # reduced outgassing initially

    elif pid == "petm":
        # PETM Hothouse — very high CO2, no ice
        self.glacier_co2 = 1800.0
        for i in range(n_lats):
            temp[i] = min(1.0, temp[i] + 0.25)
        # No ice at all
        self.glacier_volcanic_mult = 2.5

    elif pid == "anthropogenic":
        # Modern with rapid CO2 injection
        self.glacier_co2 = 420.0
        self.glacier_co2_injection = 3.0  # rapid injection
        ice_extent = int(n_lats * 0.10)
        for i in range(ice_extent):
            frac = 1.0 - i / max(1, ice_extent)
            ice[i] = _ICE_MAX_THICKNESS * 0.25 * frac

    elif pid == "do_oscillations":
        # Glacial conditions with active D-O cycling
        self.glacier_co2 = 220.0
        ice_extent = int(n_lats * 0.30)
        for i in range(ice_extent):
            frac = 1.0 - i / ice_extent
            ice[i] = _ICE_MAX_THICKNESS * frac * 0.7
            bedrock[i] = -_ISOSTATIC_SCALE * ice[i]
            temp[i] = max(0.05, temp[i] - 0.15 * frac)
        self.glacier_do_timer = 20  # trigger first D-O event soon

    # Initialize albedo from ice/land
    for i in range(n_lats):
        if ice[i] > 0.1:
            self.glacier_albedo[i] = _ICE_ALBEDO * min(1.0, ice[i] / 0.5) + \
                _BASE_ALBEDO_LAND * max(0.0, 1.0 - ice[i] / 0.5)
        else:
            # Mix of land and ocean
            lat_frac = i / max(1, n_lats - 1)
            ocean_frac = 0.3 + 0.4 * lat_frac  # more ocean near equator
            self.glacier_albedo[i] = ocean_frac * _BASE_ALBEDO_OCEAN + \
                (1.0 - ocean_frac) * _BASE_ALBEDO_LAND

    # Initialize insolation
    tick = self.glacier_generation
    for i in range(n_lats):
        base = _base_insolation(i, n_lats)
        # Milankovitch mainly affects high latitudes
        polar_weight = 1.0 - i / max(1, n_lats - 1)
        mk = _milankovitch(tick, self.glacier_eccen_phase,
                           self.glacier_obliq_phase, self.glacier_preces_phase)
        self.glacier_insolation[i] = base + mk * polar_weight


# ======================================================================
#  Simulation Step
# ======================================================================

def _glacier_step(self):
    """Advance glacier simulation by one tick."""
    n_lats = self.glacier_n_lats
    temp = self.glacier_temp
    ice = self.glacier_ice
    albedo = self.glacier_albedo
    bedrock = self.glacier_bedrock
    insol = self.glacier_insolation
    pid = self.glacier_preset_id

    self.glacier_generation += 1
    tick = self.glacier_generation

    # --- Milankovitch insolation update ---
    mk_total = _milankovitch(tick, self.glacier_eccen_phase,
                              self.glacier_obliq_phase, self.glacier_preces_phase)
    mk_e, mk_o, mk_p = _milankovitch_components(tick, self.glacier_eccen_phase,
                                                   self.glacier_obliq_phase,
                                                   self.glacier_preces_phase)

    for i in range(n_lats):
        base = _base_insolation(i, n_lats)
        polar_weight = 1.0 - i / max(1, n_lats - 1)
        # Obliquity mainly affects poles, precession affects both
        insol[i] = base + (mk_o * 1.5 + mk_e + mk_p) * polar_weight + mk_p * 0.3

    # 65°N equivalent insolation (around index ~n_lats*0.28 from pole)
    idx_65n = max(0, min(n_lats - 1, int(n_lats * 0.28)))
    insol_65n = insol[idx_65n]

    # --- CO2 dynamics ---
    co2 = self.glacier_co2

    # Volcanic outgassing
    volcanic = _VOLCANIC_OUTGAS * self.glacier_volcanic_mult
    co2 += volcanic

    # Silicate weathering sink (stronger when warm and CO2 is high)
    weathering = _WEATHERING_RATE * self.glacier_global_temp * co2
    co2 -= weathering

    # Ocean CO2 absorption (proportional to excess above baseline)
    if co2 > _CO2_BASELINE:
        ocean_sink = _OCEAN_ABSORB * (co2 - _CO2_BASELINE) * (1.0 + self.glacier_global_temp)
        co2 -= ocean_sink

    # External injection (anthropogenic or volcanic events)
    co2 += self.glacier_co2_injection

    co2 = max(_CO2_MIN, min(_CO2_MAX, co2))
    self.glacier_co2 = co2

    # CO2 greenhouse forcing
    co2_forcing = _CO2_GREENHOUSE * (co2 - _CO2_BASELINE)

    # --- D-O oscillations ---
    self.glacier_do_timer -= 1
    if self.glacier_do_timer <= 0 and not self.glacier_do_active:
        # Trigger D-O warming event
        self.glacier_do_active = True
        self.glacier_do_warmth = _DO_WARMING_AMP
        self.glacier_do_timer = random.randint(_DO_PERIOD_MIN, _DO_PERIOD_MAX)

    if self.glacier_do_active:
        # Gradual cooling after abrupt warming
        self.glacier_do_warmth -= _DO_COOLING_RATE
        if self.glacier_do_warmth <= 0:
            self.glacier_do_warmth = 0.0
            self.glacier_do_active = False

    # --- Heinrich events ---
    self.glacier_heinrich_active = False
    if self.glacier_heinrich_cooldown > 0:
        self.glacier_heinrich_cooldown -= 1
    else:
        # Heinrich events more likely with thick ice sheets
        max_ice = max(ice)
        if max_ice > _CALVING_THRESHOLD and random.random() < _HEINRICH_PROB * (max_ice / _ICE_MAX_THICKNESS):
            self.glacier_heinrich_active = True
            self.glacier_heinrich_cooldown = 30  # cooldown between events

    # --- Temperature, ice, and albedo update per latitude band ---
    new_temp = [0.0] * n_lats
    new_ice = [0.0] * n_lats
    new_albedo = [0.0] * n_lats
    new_bedrock = [0.0] * n_lats

    total_ice = 0.0

    for i in range(n_lats):
        lat_frac = i / max(1, n_lats - 1)  # 0=pole, 1=equator

        # --- Effective insolation (reduced by albedo) ---
        absorbed = insol[i] * (1.0 - albedo[i])

        # --- Radiative balance: absorbed solar - outgoing longwave + greenhouse ---
        # Base equilibrium temperature
        t_equil = absorbed * 0.7 + co2_forcing + self.glacier_do_warmth * (1.0 - lat_frac * 0.5)

        # --- Meridional heat diffusion ---
        t_diff = 0.0
        if i > 0:
            t_diff += temp[i - 1] - temp[i]
        if i < n_lats - 1:
            t_diff += temp[i + 1] - temp[i]
        t_diff *= _TEMP_DIFF

        # --- Temperature update ---
        new_t = temp[i] + _DT * (_TEMP_RESPONSE * (t_equil - temp[i]) + t_diff)
        new_t = _clamp(new_t, 0.0, 1.2)
        new_temp[i] = new_t

        # --- Ice dynamics ---
        ice_val = ice[i]

        # Growth: when temperature is below freezing threshold
        freeze_threshold = 0.25 + 0.1 * lat_frac  # easier to freeze at poles
        if new_t < freeze_threshold:
            growth = _ICE_GROWTH_RATE * (freeze_threshold - new_t) * (1.0 + 0.5 * (1.0 - lat_frac))
            ice_val += growth
        else:
            # Melting
            melt = _ICE_MELT_RATE * (new_t - freeze_threshold) * (1.0 + co2_forcing * 2.0)
            ice_val -= melt

        # Ice flow: equatorward spreading
        if i < n_lats - 1 and ice_val > 0.1:
            flow = _ICE_FLOW_RATE * ice_val * 0.1
            ice_val -= flow
            # Don't directly modify ice[i+1] here; accumulate separately

        # Calving at ice margin
        if ice_val > _CALVING_THRESHOLD and i > 0:
            calve = _CALVING_RATE * (ice_val - _CALVING_THRESHOLD)
            ice_val -= calve

        # Heinrich event: massive discharge from polar ice
        if self.glacier_heinrich_active and i < n_lats * 0.25 and ice_val > 0.5:
            discharge = _HEINRICH_SURGE * ice_val
            ice_val -= discharge
            # Freshwater cooling effect
            new_temp[i] = max(0.02, new_temp[i] - 0.03)

        ice_val = max(0.0, min(_ICE_MAX_THICKNESS, ice_val))
        new_ice[i] = ice_val
        total_ice += ice_val

        # --- Ice flow receiving (from poleward neighbor) ---
        if i > 0 and ice[i - 1] > 0.1:
            inflow = _ICE_FLOW_RATE * ice[i - 1] * 0.1
            new_ice[i] = min(_ICE_MAX_THICKNESS, new_ice[i] + inflow)

        # --- Albedo update ---
        if new_ice[i] > 0.1:
            ice_cover = min(1.0, new_ice[i] / 0.5)
            new_albedo[i] = _ICE_ALBEDO * ice_cover + _BASE_ALBEDO_LAND * (1.0 - ice_cover)
        else:
            ocean_frac = 0.3 + 0.4 * lat_frac
            new_albedo[i] = ocean_frac * _BASE_ALBEDO_OCEAN + \
                (1.0 - ocean_frac) * _BASE_ALBEDO_LAND

        # Ice-albedo feedback: amplify albedo effect
        if new_albedo[i] > 0.4:
            new_albedo[i] = min(0.85, new_albedo[i] + _ALBEDO_FEEDBACK * (new_albedo[i] - 0.4) * 0.1)

        # --- Isostatic rebound/depression ---
        equil_depression = -_ISOSTATIC_SCALE * new_ice[i]
        new_bedrock[i] = bedrock[i] + _ISOSTATIC_RATE * (equil_depression - bedrock[i])

    # Apply updated arrays
    self.glacier_temp = new_temp
    self.glacier_ice = new_ice
    self.glacier_albedo = new_albedo
    self.glacier_bedrock = new_bedrock

    # --- Global metrics ---
    self.glacier_total_ice = total_ice
    self.glacier_global_temp = sum(new_temp) / n_lats

    # Sea level: inversely proportional to total ice volume
    self.glacier_sea_level = _SEA_LEVEL_BASELINE + total_ice * _SEA_LEVEL_SCALE / n_lats

    # Ice extent: how far from pole ice extends (as fraction of latitude bands)
    ice_extent = 0
    for i in range(n_lats):
        if new_ice[i] > 0.05:
            ice_extent = i + 1
    ice_extent_frac = ice_extent / n_lats

    mean_albedo = sum(new_albedo) / n_lats

    # --- Metrics ---
    hist = self.glacier_history
    _append_metric(hist, 'global_temp', self.glacier_global_temp)
    _append_metric(hist, 'co2', co2)
    _append_metric(hist, 'total_ice', total_ice)
    _append_metric(hist, 'sea_level', self.glacier_sea_level)
    _append_metric(hist, 'insolation_65n', insol_65n)
    _append_metric(hist, 'albedo_mean', mean_albedo)
    _append_metric(hist, 'ice_extent', ice_extent_frac)
    _append_metric(hist, 'weathering', weathering)
    _append_metric(hist, 'do_index', self.glacier_do_warmth)
    _append_metric(hist, 'heinrich', 1.0 if self.glacier_heinrich_active else 0.0)


# ======================================================================
#  Key Handlers
# ======================================================================

def _handle_glacier_menu_key(self, key: int) -> bool:
    """Handle keys in preset menu."""
    if key == curses.KEY_UP or key == ord('k'):
        self.glacier_menu_sel = (self.glacier_menu_sel - 1) % len(GLACIER_PRESETS)
        return True
    if key == curses.KEY_DOWN or key == ord('j'):
        self.glacier_menu_sel = (self.glacier_menu_sel + 1) % len(GLACIER_PRESETS)
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _glacier_init(self, self.glacier_menu_sel)
        self.glacier_running = True
        return True
    if key == ord('q') or key == 27:
        self._exit_glacier_mode()
        return True
    return False


def _handle_glacier_key(self, key: int) -> bool:
    """Handle keys during simulation."""
    if key == ord(' '):
        self.glacier_running = not self.glacier_running
        return True
    if key == ord('v'):
        views = ["crosssection", "graphs", "orbital"]
        idx = views.index(self.glacier_view)
        self.glacier_view = views[(idx + 1) % len(views)]
        return True
    if key == ord('n'):
        _glacier_step(self)
        return True
    if key == ord('+') or key == ord('='):
        self.glacier_co2_injection = min(20.0, self.glacier_co2_injection + 0.5)
        self._flash(f"CO2 injection: {self.glacier_co2_injection:.1f} ppm/tick")
        return True
    if key == ord('-'):
        self.glacier_co2_injection = max(0.0, self.glacier_co2_injection - 0.5)
        self._flash(f"CO2 injection: {self.glacier_co2_injection:.1f} ppm/tick")
        return True
    if key == ord('V'):
        self.glacier_volcanic_mult = min(5.0, self.glacier_volcanic_mult + 0.5)
        self._flash(f"Volcanic: {self.glacier_volcanic_mult:.1f}x")
        return True
    if key == ord('B'):
        self.glacier_volcanic_mult = max(0.0, self.glacier_volcanic_mult - 0.5)
        self._flash(f"Volcanic: {self.glacier_volcanic_mult:.1f}x")
        return True
    if key == ord('h'):
        # Force a Heinrich event
        self.glacier_heinrich_active = True
        self.glacier_heinrich_cooldown = 30
        self._flash("Heinrich event triggered!")
        return True
    if key == ord('d'):
        # Force a D-O warming event
        self.glacier_do_active = True
        self.glacier_do_warmth = _DO_WARMING_AMP
        self._flash("D-O warming event triggered!")
        return True
    if key == ord('r'):
        idx = next((i for i, p in enumerate(GLACIER_PRESETS)
                     if p[2] == self.glacier_preset_id), 0)
        _glacier_init(self, idx)
        self.glacier_running = True
        return True
    if key == ord('R') or key == ord('m'):
        self.glacier_menu = True
        self.glacier_menu_sel = 0
        return True
    if key == ord('q'):
        self._exit_glacier_mode()
        return True
    return False


# ======================================================================
#  Drawing — Preset Menu
# ======================================================================

def _draw_glacier_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()
    title = "Glacier Dynamics & Ice Age Cycles"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass

    sub = "Select a climate/glaciation preset:"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(sub)) // 2), sub)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(GLACIER_PRESETS):
        y = 5 + i * 3
        if y + 1 >= max_y:
            break
        marker = "> " if i == self.glacier_menu_sel else "  "
        attr = curses.A_REVERSE if i == self.glacier_menu_sel else 0
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
#  Drawing — Main dispatch
# ======================================================================

def _draw_glacier(self, max_y: int, max_x: int):
    """Dispatch to appropriate view drawer."""
    if self.glacier_view == "crosssection":
        _draw_crosssection_view(self, max_y, max_x)
    elif self.glacier_view == "graphs":
        _draw_graphs_view(self, max_y, max_x)
    elif self.glacier_view == "orbital":
        _draw_orbital_view(self, max_y, max_x)


# ======================================================================
#  Drawing — Polar-to-Equatorial Cross-Section
# ======================================================================

_ICE_GLYPHS = ' .:-=*#%@'
_TEMP_COLORS = {
    'hot': 1,       # red
    'warm': 3,      # yellow
    'cool': 6,      # cyan
    'cold': 4,      # blue
    'ice': 7,       # white
}


def _draw_crosssection_view(self, max_y: int, max_x: int):
    """Render pole-to-equator cross-section with ice sheets and bedrock."""
    self.stdscr.erase()
    n_lats = self.glacier_n_lats
    temp = self.glacier_temp
    ice = self.glacier_ice
    albedo = self.glacier_albedo
    bedrock = self.glacier_bedrock
    insol = self.glacier_insolation

    title = f"Glacier Dynamics — {self.glacier_preset_name}"
    try:
        self.stdscr.addstr(0, 2, title[:max_x - 4], curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass

    # Cross-section layout
    # Top: atmosphere/insolation
    # Middle: ice sheet profile
    # Bottom: bedrock with depression
    draw_w = min(n_lats, max_x - 12)
    mid_y = max_y // 2          # baseline (sea level / ground level)
    top_y = 3                    # top of drawing area
    bot_y = max_y - 4            # bottom of drawing area

    # Scaling
    max_ice_display = max(bot_y - top_y - 4, 10)
    ice_scale = max_ice_display / (_ICE_MAX_THICKNESS * 1.2)
    bedrock_scale = max_ice_display * 0.3

    # Labels
    try:
        self.stdscr.addstr(top_y, 1, "POLE", curses.color_pair(4) | curses.A_DIM)
    except curses.error:
        pass
    eq_x = min(max_x - 5, 8 + draw_w)
    try:
        self.stdscr.addstr(top_y, eq_x, "EQ", curses.color_pair(1) | curses.A_DIM)
    except curses.error:
        pass

    # Sea level line
    sea_y = mid_y
    for x in range(8, 8 + draw_w):
        if x >= max_x - 1:
            break
        try:
            self.stdscr.addstr(sea_y, x, '~', curses.color_pair(4) | curses.A_DIM)
        except curses.error:
            pass

    # Draw each latitude band
    for li in range(draw_w):
        x = 8 + li
        if x >= max_x - 1:
            break

        lat_idx = int(li * n_lats / draw_w)
        if lat_idx >= n_lats:
            lat_idx = n_lats - 1

        t = temp[lat_idx]
        ice_h = ice[lat_idx]
        bed = bedrock[lat_idx]
        alb = albedo[lat_idx]

        # Bedrock level (sea_y + depression)
        bed_y = sea_y + int(-bed * bedrock_scale)
        bed_y = max(sea_y - 2, min(bot_y, bed_y))

        # Ice extent above bedrock
        ice_pixels = int(ice_h * ice_scale)

        # Temperature color for background
        if t > 0.65:
            tcol = _TEMP_COLORS['hot']
        elif t > 0.45:
            tcol = _TEMP_COLORS['warm']
        elif t > 0.28:
            tcol = _TEMP_COLORS['cool']
        else:
            tcol = _TEMP_COLORS['cold']

        # Draw atmosphere (above sea level, above ice)
        ice_top_y = bed_y - ice_pixels
        for y in range(top_y + 1, min(sea_y, ice_top_y)):
            if y >= max_y - 3:
                break
            # Insolation indicator
            if y == top_y + 1:
                insol_val = insol[lat_idx]
                if insol_val > 1.05:
                    ch = '*'
                elif insol_val > 0.95:
                    ch = '+'
                elif insol_val > 0.7:
                    ch = ':'
                else:
                    ch = '.'
                try:
                    self.stdscr.addstr(y, x, ch, curses.color_pair(3))
                except curses.error:
                    pass
            else:
                try:
                    self.stdscr.addstr(y, x, ' ')
                except curses.error:
                    pass

        # Draw ice sheet
        if ice_h > 0.05:
            for y in range(max(top_y + 2, ice_top_y), bed_y):
                if y >= max_y - 3 or y < 0:
                    continue
                # Ice density glyph
                depth_in_ice = (y - ice_top_y) / max(1, ice_pixels)
                gi = int(depth_in_ice * (len(_ICE_GLYPHS) - 1))
                gi = max(0, min(len(_ICE_GLYPHS) - 1, gi))
                ch = _ICE_GLYPHS[gi]
                try:
                    self.stdscr.addstr(y, x, ch, curses.color_pair(7) | curses.A_BOLD)
                except curses.error:
                    pass

        # Draw bedrock
        for y in range(bed_y, min(bot_y, bed_y + 2)):
            if y >= max_y - 3 or y < 0:
                continue
            try:
                self.stdscr.addstr(y, x, '#', curses.color_pair(3) | curses.A_DIM)
            except curses.error:
                pass

        # Below bedrock: mantle
        for y in range(min(bot_y, bed_y + 2), bot_y):
            if y >= max_y - 3:
                break
            try:
                self.stdscr.addstr(y, x, '.', curses.color_pair(1) | curses.A_DIM)
            except curses.error:
                pass

        # Temperature bar at very top
        try:
            self.stdscr.addstr(top_y, x, '|', curses.color_pair(tcol))
        except curses.error:
            pass

    # Right side: key info
    info_x = min(max_x - 28, 10 + draw_w)
    if info_x > 0 and info_x < max_x - 4:
        info = [
            f"Tick: {self.glacier_generation}",
            f"CO2: {self.glacier_co2:.0f} ppm",
            f"T_global: {self.glacier_global_temp:.3f}",
            f"Ice vol: {self.glacier_total_ice:.1f}",
            f"Sea lvl: {self.glacier_sea_level:.1f} m",
            f"Ice ext: {sum(1 for x in ice if x > 0.05)}/{n_lats}",
            f"D-O: {'WARM' if self.glacier_do_active else 'cool'}",
            f"Heinrich: {'YES' if self.glacier_heinrich_active else 'no'}",
            f"Volcanic: {self.glacier_volcanic_mult:.1f}x",
            f"CO2 inj: {self.glacier_co2_injection:.1f}",
        ]
        for ii, line in enumerate(info):
            y = top_y + 2 + ii
            if y >= max_y - 4:
                break
            try:
                self.stdscr.addstr(y, info_x, line[:max_x - info_x - 1],
                                   curses.color_pair(7))
            except curses.error:
                pass

    # Status bar
    state = "RUNNING" if self.glacier_running else "PAUSED"
    status = (f" {state} | [v]iew [+/-]CO2 [V/B]volcanic [h]einrich [d]O event "
              f"[space] [r]eset [q]uit")
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    legend = " |=temp  *+:.=insolation  =-*#%@=ice  #=bedrock  ~=sea level  .=mantle"
    try:
        self.stdscr.addstr(max_y - 1, 0, legend[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Time-Series Sparkline Graphs
# ======================================================================

def _draw_graphs_view(self, max_y: int, max_x: int):
    """Time-series sparkline graphs for climate metrics."""
    self.stdscr.erase()
    hist = self.glacier_history
    graph_w = min(200, max_x - 30)

    title = (f"Climate Metrics — {self.glacier_preset_name} | "
             f"tick {self.glacier_generation}")
    try:
        self.stdscr.addstr(0, 2, title[:max_x - 4], curses.A_BOLD)
    except curses.error:
        pass

    labels = [
        ("Global Temp",     'global_temp',     1),
        ("CO2 (ppm)",       'co2',             3),
        ("Total Ice Vol",   'total_ice',       7),
        ("Sea Level (m)",   'sea_level',       4),
        ("Insol 65N",       'insolation_65n',  3),
        ("Mean Albedo",     'albedo_mean',     7),
        ("Ice Extent",      'ice_extent',      6),
        ("Weathering",      'weathering',      2),
        ("D-O Index",       'do_index',        1),
        ("Heinrich Events", 'heinrich',        5),
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
            for i, val in enumerate(visible):
                x = 26 + i
                if x >= max_x - 1:
                    break
                idx = int((val - mn) / rng * n_bars)
                idx = max(0, min(n_bars, idx))
                try:
                    self.stdscr.addstr(base_y, x, bars[idx], color)
                except curses.error:
                    pass

    status = (f" [v]iew [+/-]CO2 [V/B]volcanic [h]einrich [d]O event "
              f"[space]pause [r]estart [q]uit")
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Orbital Parameters & Feedback Diagram
# ======================================================================

def _draw_orbital_view(self, max_y: int, max_x: int):
    """Orbital parameter phase diagram and feedback strengths."""
    self.stdscr.erase()
    tick = self.glacier_generation

    title = (f"Orbital Parameters & Feedbacks — {self.glacier_preset_name} | "
             f"tick {tick}")
    try:
        self.stdscr.addstr(0, 2, title[:max_x - 4], curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass

    mk_e, mk_o, mk_p = _milankovitch_components(
        tick, self.glacier_eccen_phase, self.glacier_obliq_phase, self.glacier_preces_phase)
    mk_total = mk_e + mk_o + mk_p

    # Orbital parameters section
    orb_y = 2
    params = [
        ("Eccentricity",  mk_e,      _ECCEN_AMP,  _ECCEN_PERIOD,  1),
        ("Obliquity",     mk_o,      _OBLIQ_AMP,  _OBLIQ_PERIOD,  3),
        ("Precession",    mk_p,      _PRECES_AMP, _PRECES_PERIOD, 6),
        ("Combined",      mk_total,  _ECCEN_AMP + _OBLIQ_AMP + _PRECES_AMP, 0, 7),
    ]

    bar_w = min(60, max_x - 35)

    for pi, (name, val, amp, period, cp) in enumerate(params):
        y = orb_y + pi * 2
        if y >= max_y - 12:
            break

        period_str = f" ({period} tick period)" if period > 0 else ""
        label = f"{name}: {val:+.4f}{period_str}"
        try:
            self.stdscr.addstr(y, 2, label[:30], curses.color_pair(cp) | curses.A_BOLD)
        except curses.error:
            pass

        # Bar visualization centered at midpoint
        if amp > 0 and bar_w > 4:
            mid = bar_w // 2
            norm_val = val / (amp * 1.2)  # normalized to [-1, 1]
            bar_pos = int(mid + norm_val * mid)
            bar_pos = max(0, min(bar_w - 1, bar_pos))

            for bx in range(bar_w):
                x = 32 + bx
                if x >= max_x - 1:
                    break
                if bx == mid:
                    ch = '|'
                elif bx == bar_pos:
                    ch = '#'
                elif min(bx, bar_pos) < mid <= max(bx, bar_pos) or \
                     min(bx, bar_pos) <= mid < max(bx, bar_pos):
                    ch = '-' if (min(bx, bar_pos) <= bx <= max(bx, bar_pos)) else ' '
                else:
                    ch = ' '
                try:
                    self.stdscr.addstr(y, x, ch, curses.color_pair(cp))
                except curses.error:
                    pass

    # Feedback strengths section
    fb_y = orb_y + len(params) * 2 + 1
    try:
        self.stdscr.addstr(fb_y, 2, "Feedback Strengths:", curses.A_BOLD | curses.A_UNDERLINE)
    except curses.error:
        pass

    co2 = self.glacier_co2
    gt = self.glacier_global_temp
    ti = self.glacier_total_ice
    n_lats = self.glacier_n_lats

    # Calculate feedback strengths
    co2_forcing = _CO2_GREENHOUSE * (co2 - _CO2_BASELINE)
    albedo_feedback = sum(self.glacier_albedo) / n_lats - _BASE_ALBEDO_LAND
    weathering_fb = _WEATHERING_RATE * gt * co2
    ocean_sink = _OCEAN_ABSORB * max(0, co2 - _CO2_BASELINE) * (1.0 + gt)
    ice_albedo_fb = ti / (n_lats * _ICE_MAX_THICKNESS)

    feedbacks = [
        ("CO2 Greenhouse",     co2_forcing,      "+warming" if co2_forcing > 0 else "-cooling", 1),
        ("Ice-Albedo",         ice_albedo_fb,     "+cooling feedback",                           7),
        ("Albedo Anomaly",     albedo_feedback,   "+reflects more" if albedo_feedback > 0 else "-absorbs more", 6),
        ("Weathering Sink",    weathering_fb,     "-CO2 removal",                                2),
        ("Ocean CO2 Sink",     ocean_sink,        "-CO2 absorption",                             4),
        ("D-O Warming",        self.glacier_do_warmth, "+abrupt warming",                        1),
        ("Orbital Forcing",    mk_total,          "+/-insolation",                               3),
    ]

    for fi, (name, val, effect, cp) in enumerate(feedbacks):
        y = fb_y + 2 + fi
        if y >= max_y - 4:
            break
        line = f"  {name:20s} {val:+.4f}  {effect}"
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 4], curses.color_pair(cp))
        except curses.error:
            pass

    # System state summary
    summary_y = fb_y + 2 + len(feedbacks) + 1
    if summary_y < max_y - 4:
        # Determine climate state
        if ti > n_lats * 0.5:
            state_str = "SNOWBALL / DEEP GLACIATION"
            state_cp = 7
        elif ti > n_lats * 0.15:
            state_str = "GLACIAL (Ice Age)"
            state_cp = 4
        elif ti > n_lats * 0.03:
            state_str = "INTERGLACIAL (warm period)"
            state_cp = 3
        else:
            state_str = "HOTHOUSE (ice-free)"
            state_cp = 1

        try:
            self.stdscr.addstr(summary_y, 2, f"Climate State: {state_str}",
                               curses.A_BOLD | curses.color_pair(state_cp))
        except curses.error:
            pass
        if summary_y + 1 < max_y - 4:
            summary = f"CO2: {co2:.0f} ppm | T: {gt:.3f} | Ice: {ti:.1f} | Sea: {self.glacier_sea_level:.1f}m"
            try:
                self.stdscr.addstr(summary_y + 1, 2, summary[:max_x - 4],
                                   curses.color_pair(7))
            except curses.error:
                pass

    status = (f" [v]iew [+/-]CO2 [V/B]volcanic [h]einrich [d]O event "
              f"[space]pause [r]estart [q]uit")
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Registration
# ======================================================================

def register(App):
    """Register glacier dynamics mode methods on the App class."""
    App.GLACIER_PRESETS = GLACIER_PRESETS
    App._enter_glacier_mode = _enter_glacier_mode
    App._exit_glacier_mode = _exit_glacier_mode
    App._glacier_init = _glacier_init
    App._glacier_step = _glacier_step
    App._handle_glacier_menu_key = _handle_glacier_menu_key
    App._handle_glacier_key = _handle_glacier_key
    App._draw_glacier_menu = _draw_glacier_menu
    App._draw_glacier = _draw_glacier
