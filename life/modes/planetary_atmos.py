"""Mode: planetary_atmos — Planetary Atmosphere & Weather System.

Simulates a 2D cylindrical/Mercator projection of a planet with:
- Atmospheric circulation cells (Hadley/Ferrel/Polar) driven by differential
  solar heating with latitude-dependent insolation
- Coriolis-deflected jet streams and geostrophic wind balance
- Cyclone/anticyclone genesis from baroclinic instability
- Moisture transport & precipitation (evaporation, advection, condensation)
- Ocean-atmosphere coupling (SST fueling tropical cyclones)
- Greenhouse forcing with adjustable CO2 and ice-albedo feedback

Three views:
  1) Pressure/wind map with isobar contours + storm glyphs + precipitation
  2) Temperature/moisture heatmap with ocean currents + ice extent
  3) Time-series sparkline graphs — 10 metrics

Six presets:
  Stable Temperate Earth, Tropical Cyclone Season, Ice Age Glaciation,
  Runaway Greenhouse Venus, Tidally Locked Exoplanet, Snowball Earth Deglaciation
"""
import curses
import math
import random

# ======================================================================
#  Presets
# ======================================================================

PLANETARY_ATMOS_PRESETS = [
    ("Stable Temperate Earth",
     "Balanced climate — Hadley/Ferrel/Polar cells, mid-latitude cyclones, seasonal ice caps",
     "temperate"),
    ("Tropical Cyclone Season",
     "Warm SST tropics spawning intense hurricanes — strong Hadley circulation and moisture transport",
     "cyclone"),
    ("Ice Age Glaciation",
     "Low CO2, expanded polar ice with strong albedo feedback — weak Hadley, equatorward jet stream",
     "iceage"),
    ("Runaway Greenhouse Venus",
     "Extreme CO2 trapping — surface temperature soaring, no ice, violent convective storms",
     "venus"),
    ("Tidally Locked Exoplanet",
     "Permanent day/night hemispheres — substellar convective tower, antistellar cold trap, terminator jets",
     "tidallylocked"),
    ("Snowball Earth Deglaciation",
     "Volcanic CO2 buildup melting global ice — albedo feedback reversal and sudden tropical thaw",
     "snowball"),
]

# ======================================================================
#  Physical constants
# ======================================================================

_DT = 0.2                # integration timestep
_SOLAR_CONST = 1.0        # normalized solar flux at equator
_STEFAN_BOLTZ = 0.02      # simplified radiative cooling coefficient
_CORIOLIS_SCALE = 0.15    # Coriolis parameter scaling
_PRESSURE_SMOOTH = 0.08   # pressure field diffusion rate
_WIND_DRAG = 0.02         # surface drag on wind
_MOISTURE_EVAP = 0.004    # evaporation rate from ocean
_MOISTURE_SAT = 0.85      # saturation threshold for precipitation
_MOISTURE_PRECIP = 0.3    # fraction of excess moisture that precipitates
_MOISTURE_DIFF = 0.03     # moisture diffusion
_TEMP_DIFF = 0.04         # temperature diffusion (atmospheric mixing)
_STORM_SPIN_THRESHOLD = 0.12  # vorticity threshold for storm genesis
_STORM_DISSIPATE = 0.003  # storm weakening rate per tick
_STORM_SST_BOOST = 1.5    # warm SST intensification factor
_ICE_FORM_TEMP = 0.15     # temperature below which ice forms
_ICE_MELT_TEMP = 0.22     # temperature above which ice melts
_ICE_ALBEDO = 0.7         # albedo of ice-covered cells
_OCEAN_ALBEDO = 0.06      # albedo of ocean
_LAND_ALBEDO = 0.3        # albedo of land
_GHG_BASE = 0.35          # base greenhouse trapping fraction
_GHG_CO2_SCALE = 0.4      # additional trapping per unit CO2 above baseline
_JET_STREAM_LAT = 0.45    # default jet stream latitude (fraction from equator)

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


# ======================================================================
#  Helper functions
# ======================================================================

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _wrap_col(c, cols):
    """Cylindrical wrapping in longitude."""
    return c % cols


def _lat_fraction(r, rows):
    """Return latitude as fraction: 0 = north pole, 0.5 = equator, 1.0 = south pole."""
    return r / max(1, rows - 1)


def _insolation(lat_frac, tidal_lock=False, substellar_col=None, c=0, cols=1):
    """Solar heating as function of latitude (and longitude for tidally locked)."""
    if tidal_lock:
        # Longitude-dependent: max at substellar point
        lon_frac = abs(c - substellar_col) / max(1, cols // 2)
        if lon_frac > 1.0:
            lon_frac = 2.0 - lon_frac
        lat_dev = abs(lat_frac - 0.5) * 2.0
        dist = math.sqrt(lon_frac ** 2 + lat_dev ** 2)
        return max(0.0, _SOLAR_CONST * (1.0 - dist * 0.9))
    # Normal: max at equator, zero at poles
    return _SOLAR_CONST * max(0.0, math.cos(math.pi * (lat_frac - 0.5)))


def _coriolis(lat_frac):
    """Coriolis parameter f = 2*omega*sin(lat). Positive NH, negative SH."""
    lat_rad = math.pi * (lat_frac - 0.5)  # -pi/2 to +pi/2
    return _CORIOLIS_SCALE * math.sin(lat_rad)


# ======================================================================
#  Enter / Exit
# ======================================================================

def _enter_planetary_atmos_mode(self):
    """Enter planetary atmosphere mode — show preset menu."""
    self.planetary_atmos_mode = True
    self.planetary_atmos_menu = True
    self.planetary_atmos_menu_sel = 0


def _exit_planetary_atmos_mode(self):
    """Exit planetary atmosphere mode."""
    self.planetary_atmos_mode = False
    self.planetary_atmos_menu = False
    self.planetary_atmos_running = False
    for attr in list(vars(self)):
        if attr.startswith('planetary_atmos_') and attr not in ('planetary_atmos_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ======================================================================
#  Initialization
# ======================================================================

def _planetary_atmos_init(self, preset_idx: int):
    """Initialize planetary atmosphere simulation for chosen preset."""
    name, _desc, pid = PLANETARY_ATMOS_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(20, max_y - 4)
    cols = max(40, max_x - 2)

    self.planetary_atmos_menu = False
    self.planetary_atmos_running = False
    self.planetary_atmos_preset_name = name
    self.planetary_atmos_preset_id = pid
    self.planetary_atmos_rows = rows
    self.planetary_atmos_cols = cols
    self.planetary_atmos_generation = 0
    self.planetary_atmos_view = "pressure"  # pressure | temperature | graphs

    # --- Surface type: 0=ocean, 1=land ---
    land = [[0] * cols for _ in range(rows)]
    _generate_land(land, rows, cols, pid)
    self.planetary_atmos_land = land

    # --- Temperature field [0, 1+] (normalized, ~0=frozen, ~0.5=temperate, ~1+=hot) ---
    temp = [[0.0] * cols for _ in range(rows)]
    self.planetary_atmos_temp = temp

    # --- Pressure field (normalized around 1.0: <1 = low, >1 = high) ---
    pres = [[1.0] * cols for _ in range(rows)]
    self.planetary_atmos_pressure = pres

    # --- Wind field (u = east-west, v = north-south) ---
    self.planetary_atmos_u = [[0.0] * cols for _ in range(rows)]
    self.planetary_atmos_v = [[0.0] * cols for _ in range(rows)]

    # --- Moisture field [0, 1] ---
    self.planetary_atmos_moisture = [[0.0] * cols for _ in range(rows)]

    # --- Precipitation accumulator (for display) ---
    self.planetary_atmos_precip = [[0.0] * cols for _ in range(rows)]

    # --- Ice coverage [0, 1] ---
    self.planetary_atmos_ice = [[0.0] * cols for _ in range(rows)]

    # --- Sea surface temperature (ocean only) ---
    self.planetary_atmos_sst = [[0.0] * cols for _ in range(rows)]

    # --- CO2 concentration (global scalar, normalized) ---
    self.planetary_atmos_co2 = 0.5

    # --- Storm tracking ---
    self.planetary_atmos_storms = []  # list of {r, c, intensity, type, age, vr, vc}

    # --- Jet stream latitude (fraction from pole) ---
    self.planetary_atmos_jet_lat = _JET_STREAM_LAT

    # --- Tidal lock parameters ---
    self.planetary_atmos_tidal_lock = False
    self.planetary_atmos_substellar_col = cols // 2

    # --- Metrics history ---
    self.planetary_atmos_history = {
        'global_temp': [],
        'co2': [],
        'storm_count': [],
        'precipitation': [],
        'jet_lat': [],
        'ice_area': [],
        'mean_pressure': [],
        'max_wind': [],
        'humidity': [],
        'ghg_forcing': [],
    }

    # Apply preset
    _apply_preset(self, pid, rows, cols)
    self._flash(f"Planetary Atmosphere: {name}")


def _generate_land(land, rows, cols, pid):
    """Generate simple continent shapes."""
    if pid == "venus":
        # Mostly land (rocky planet)
        for r in range(rows):
            for c in range(cols):
                land[r][c] = 1 if random.random() < 0.7 else 0
        return
    if pid == "tidallylocked":
        # Ring continent around terminator
        mid_c = cols // 2
        for r in range(rows):
            for c in range(cols):
                dist = abs(c - mid_c)
                if cols // 4 - 3 < dist < cols // 4 + 3:
                    land[r][c] = 1 if random.random() < 0.5 else 0
        return

    # Earth-like: generate a few blob continents
    n_continents = random.randint(3, 6)
    for _ in range(n_continents):
        cr = random.randint(rows // 6, rows * 5 // 6)
        cc = random.randint(0, cols - 1)
        size = random.randint(3, max(4, min(rows, cols) // 5))
        for r in range(max(0, cr - size), min(rows, cr + size)):
            for c in range(cc - size, cc + size):
                wc = _wrap_col(c, cols)
                dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
                if dist < size * (0.5 + 0.5 * random.random()):
                    land[r][wc] = 1


def _apply_preset(self, pid, rows, cols):
    """Configure preset-specific initial conditions."""
    temp = self.planetary_atmos_temp
    moisture = self.planetary_atmos_moisture
    ice = self.planetary_atmos_ice
    sst = self.planetary_atmos_sst
    land = self.planetary_atmos_land
    pres = self.planetary_atmos_pressure

    # Initialize temperature from insolation
    tidal = pid == "tidallylocked"
    self.planetary_atmos_tidal_lock = tidal
    sub_col = cols // 2

    for r in range(rows):
        lat = _lat_fraction(r, rows)
        for c in range(cols):
            insol = _insolation(lat, tidal, sub_col, c, cols)
            base_temp = insol * 0.55 + random.uniform(-0.02, 0.02)
            temp[r][c] = base_temp
            if not land[r][c]:
                sst[r][c] = base_temp
                moisture[r][c] = base_temp * 0.4

    if pid == "temperate":
        self.planetary_atmos_co2 = 0.5
    elif pid == "cyclone":
        self.planetary_atmos_co2 = 0.55
        # Warm up tropics SST
        for r in range(rows):
            lat = _lat_fraction(r, rows)
            eq_dist = abs(lat - 0.5)
            if eq_dist < 0.25:
                for c in range(cols):
                    if not land[r][c]:
                        sst[r][c] = min(1.0, sst[r][c] + 0.2)
                        temp[r][c] = min(1.0, temp[r][c] + 0.15)
                        moisture[r][c] = min(1.0, moisture[r][c] + 0.2)
    elif pid == "iceage":
        self.planetary_atmos_co2 = 0.2
        self.planetary_atmos_jet_lat = 0.35
        for r in range(rows):
            lat = _lat_fraction(r, rows)
            for c in range(cols):
                temp[r][c] *= 0.6
                pole_dist = min(lat, 1.0 - lat)
                if pole_dist < 0.35:
                    ice[r][c] = max(0.0, 1.0 - pole_dist / 0.35)
    elif pid == "venus":
        self.planetary_atmos_co2 = 1.0
        for r in range(rows):
            for c in range(cols):
                temp[r][c] = 0.85 + random.uniform(-0.05, 0.05)
                pres[r][c] = 1.3 + random.uniform(-0.05, 0.05)
                moisture[r][c] = 0.1
    elif pid == "tidallylocked":
        self.planetary_atmos_co2 = 0.45
        # Day side hot, night side cold
        for r in range(rows):
            for c in range(cols):
                lon_dist = abs(c - sub_col) / max(1, cols // 2)
                if lon_dist > 1.0:
                    lon_dist = 2.0 - lon_dist
                if lon_dist > 0.5:
                    # Night side
                    temp[r][c] *= 0.3
                    ice[r][c] = 0.5 + 0.5 * (lon_dist - 0.5) / 0.5
    elif pid == "snowball":
        self.planetary_atmos_co2 = 0.15  # starts low, will rise
        for r in range(rows):
            for c in range(cols):
                temp[r][c] = 0.1 + random.uniform(-0.02, 0.02)
                ice[r][c] = 0.8 + random.uniform(0, 0.2)
                moisture[r][c] = 0.02

    # Initialize pressure from temperature (warm = low pressure tendency)
    for r in range(rows):
        for c in range(cols):
            pres[r][c] = 1.0 - 0.1 * (temp[r][c] - 0.5)
            pres[r][c] += random.uniform(-0.01, 0.01)


# ======================================================================
#  Simulation Step
# ======================================================================

def _planetary_atmos_step(self):
    """Advance simulation by one tick."""
    rows = self.planetary_atmos_rows
    cols = self.planetary_atmos_cols
    temp = self.planetary_atmos_temp
    pres = self.planetary_atmos_pressure
    u = self.planetary_atmos_u
    v = self.planetary_atmos_v
    moisture = self.planetary_atmos_moisture
    precip = self.planetary_atmos_precip
    ice = self.planetary_atmos_ice
    sst = self.planetary_atmos_sst
    land = self.planetary_atmos_land
    co2 = self.planetary_atmos_co2
    pid = self.planetary_atmos_preset_id
    tidal = self.planetary_atmos_tidal_lock
    sub_col = self.planetary_atmos_substellar_col

    self.planetary_atmos_generation += 1

    # --- Snowball deglaciation: CO2 slowly rises ---
    if pid == "snowball":
        self.planetary_atmos_co2 = min(1.0, co2 + 0.0003)
        co2 = self.planetary_atmos_co2

    # Greenhouse forcing
    ghg = _GHG_BASE + _GHG_CO2_SCALE * co2

    # New fields for this step
    new_temp = [[0.0] * cols for _ in range(rows)]
    new_pres = [[0.0] * cols for _ in range(rows)]
    new_u = [[0.0] * cols for _ in range(rows)]
    new_v = [[0.0] * cols for _ in range(rows)]
    new_moist = [[0.0] * cols for _ in range(rows)]
    new_precip = [[0.0] * cols for _ in range(rows)]
    new_ice = [[0.0] * cols for _ in range(rows)]

    total_precip = 0.0
    max_wind = 0.0
    total_humidity = 0.0

    for r in range(rows):
        lat = _lat_fraction(r, rows)
        f = _coriolis(lat)
        for c in range(cols):
            # --- Solar heating ---
            insol = _insolation(lat, tidal, sub_col, c, cols)
            albedo = _ICE_ALBEDO * ice[r][c] + (1.0 - ice[r][c]) * (
                _LAND_ALBEDO if land[r][c] else _OCEAN_ALBEDO)
            absorbed = insol * (1.0 - albedo)

            # --- Radiative cooling ---
            outgoing = _STEFAN_BOLTZ * temp[r][c] ** 2 * (1.0 - ghg)

            # --- Temperature update ---
            # Diffusion (atmospheric mixing)
            t_lap = 0.0
            for dr, dc in _NEIGHBORS_4:
                rr = r + dr
                cc = _wrap_col(c + dc, cols)
                if 0 <= rr < rows:
                    t_lap += temp[rr][cc] - temp[r][c]
            # Advection by wind
            t_adv = 0.0
            # Upwind advection
            src_r = r - int(round(v[r][c] * 2))
            src_c = c - int(round(u[r][c] * 2))
            src_r = max(0, min(rows - 1, src_r))
            src_c = _wrap_col(src_c, cols)
            t_adv = (temp[src_r][src_c] - temp[r][c]) * 0.15

            new_t = temp[r][c] + _DT * (absorbed - outgoing + _TEMP_DIFF * t_lap + t_adv)
            new_temp[r][c] = _clamp(new_t, 0.0, 1.5)

            # --- Pressure from temperature (warm air rises -> low pressure) ---
            p_lap = 0.0
            for dr, dc in _NEIGHBORS_4:
                rr = r + dr
                cc = _wrap_col(c + dc, cols)
                if 0 <= rr < rows:
                    p_lap += pres[rr][cc] - pres[r][c]
            thermal_p = 1.0 - 0.12 * (new_temp[r][c] - 0.5)
            new_p = pres[r][c] + _DT * (_PRESSURE_SMOOTH * p_lap + 0.05 * (thermal_p - pres[r][c]))
            new_pres[r][c] = _clamp(new_p, 0.6, 1.5)

            # --- Wind from pressure gradient + Coriolis ---
            # Pressure gradient force
            dp_dx = 0.0
            dp_dy = 0.0
            cl = _wrap_col(c - 1, cols)
            cr_ = _wrap_col(c + 1, cols)
            dp_dx = (pres[r][cr_] - pres[r][cl]) * 0.5
            if r > 0 and r < rows - 1:
                dp_dy = (pres[r + 1][c] - pres[r - 1][c]) * 0.5

            # Geostrophic balance: wind perpendicular to pressure gradient
            # With Coriolis deflection
            pgf_u = -dp_dx * 3.0
            pgf_v = -dp_dy * 3.0

            # Coriolis deflection (f cross v)
            cor_u = f * v[r][c]
            cor_v = -f * u[r][c]

            # Jet stream enhancement at jet latitude
            jet_boost = 0.0
            jet_lat_n = self.planetary_atmos_jet_lat
            jet_lat_s = 1.0 - jet_lat_n
            for jl, sign in [(jet_lat_n, 1.0), (jet_lat_s, -1.0)]:
                dist = abs(lat - jl)
                if dist < 0.08:
                    jet_boost += sign * 0.3 * (1.0 - dist / 0.08)

            new_u[r][c] = u[r][c] + _DT * (pgf_u + cor_u - _WIND_DRAG * u[r][c]) + jet_boost * _DT
            new_v[r][c] = v[r][c] + _DT * (pgf_v + cor_v - _WIND_DRAG * v[r][c])

            # Clamp wind
            new_u[r][c] = _clamp(new_u[r][c], -1.0, 1.0)
            new_v[r][c] = _clamp(new_v[r][c], -1.0, 1.0)

            ws = math.sqrt(new_u[r][c] ** 2 + new_v[r][c] ** 2)
            if ws > max_wind:
                max_wind = ws

            # --- Moisture ---
            m = moisture[r][c]
            # Evaporation from ocean
            evap = 0.0
            if not land[r][c] and ice[r][c] < 0.5:
                evap = _MOISTURE_EVAP * sst[r][c] * (1.0 - m)
            # Advection
            m_src_r = r - int(round(v[r][c] * 1.5))
            m_src_c = c - int(round(u[r][c] * 1.5))
            m_src_r = max(0, min(rows - 1, m_src_r))
            m_src_c = _wrap_col(m_src_c, cols)
            m_adv = (moisture[m_src_r][m_src_c] - m) * 0.12
            # Diffusion
            m_lap = 0.0
            for dr, dc in _NEIGHBORS_4:
                rr = r + dr
                cc = _wrap_col(c + dc, cols)
                if 0 <= rr < rows:
                    m_lap += moisture[rr][cc] - m
            new_m = m + _DT * (evap + m_adv + _MOISTURE_DIFF * m_lap)

            # Precipitation
            p_rain = 0.0
            if new_m > _MOISTURE_SAT:
                p_rain = (new_m - _MOISTURE_SAT) * _MOISTURE_PRECIP
                new_m -= p_rain
            # Orographic lift: land forces upward motion -> more precip
            if land[r][c] and new_m > 0.5:
                oro_precip = 0.01 * ws
                p_rain += oro_precip
                new_m -= oro_precip

            new_moist[r][c] = _clamp(new_m, 0.0, 1.0)
            new_precip[r][c] = _clamp(p_rain, 0.0, 1.0)
            total_precip += p_rain
            total_humidity += new_moist[r][c]

            # --- Ice dynamics ---
            t_local = new_temp[r][c]
            ice_val = ice[r][c]
            if t_local < _ICE_FORM_TEMP and not land[r][c]:
                ice_val = min(1.0, ice_val + 0.005)
            elif t_local > _ICE_MELT_TEMP:
                ice_val = max(0.0, ice_val - 0.003)
            new_ice[r][c] = ice_val

    # Update fields
    self.planetary_atmos_temp = new_temp
    self.planetary_atmos_pressure = new_pres
    self.planetary_atmos_u = new_u
    self.planetary_atmos_v = new_v
    self.planetary_atmos_moisture = new_moist
    self.planetary_atmos_precip = new_precip
    self.planetary_atmos_ice = new_ice

    # --- SST update (slow thermal inertia) ---
    for r in range(rows):
        for c in range(cols):
            if not land[r][c]:
                sst[r][c] += 0.01 * (new_temp[r][c] - sst[r][c])

    # --- Storm tracking ---
    _update_storms(self, rows, cols)

    # --- Metrics ---
    n = rows * cols
    avg_temp = sum(new_temp[r][c] for r in range(rows) for c in range(cols)) / n
    avg_pres = sum(new_pres[r][c] for r in range(rows) for c in range(cols)) / n
    ice_area = sum(1 for r in range(rows) for c in range(cols) if new_ice[r][c] > 0.3) / n

    hist = self.planetary_atmos_history
    _append_metric(hist, 'global_temp', avg_temp)
    _append_metric(hist, 'co2', self.planetary_atmos_co2)
    _append_metric(hist, 'storm_count', len(self.planetary_atmos_storms))
    _append_metric(hist, 'precipitation', total_precip / n)
    _append_metric(hist, 'jet_lat', self.planetary_atmos_jet_lat)
    _append_metric(hist, 'ice_area', ice_area)
    _append_metric(hist, 'mean_pressure', avg_pres)
    _append_metric(hist, 'max_wind', max_wind)
    _append_metric(hist, 'humidity', total_humidity / n)
    _append_metric(hist, 'ghg_forcing', ghg)


def _append_metric(hist, key, val):
    """Append to history, cap at 300 entries."""
    lst = hist[key]
    lst.append(val)
    if len(lst) > 300:
        del lst[0]


def _update_storms(self, rows, cols):
    """Track cyclones/anticyclones from vorticity and pressure minima."""
    pres = self.planetary_atmos_pressure
    u = self.planetary_atmos_u
    v = self.planetary_atmos_v
    sst = self.planetary_atmos_sst
    land = self.planetary_atmos_land
    storms = self.planetary_atmos_storms

    # Storm genesis: scan for strong vorticity + low pressure
    if self.planetary_atmos_generation % 8 == 0:
        for _ in range(3):
            r = random.randint(2, rows - 3)
            c = random.randint(0, cols - 1)
            lat = _lat_fraction(r, rows)
            eq_dist = abs(lat - 0.5)

            # Compute local vorticity (dv/dx - du/dy)
            cl = _wrap_col(c - 1, cols)
            cr_ = _wrap_col(c + 1, cols)
            dvdx = (v[r][cr_] - v[r][cl]) * 0.5
            dudy = 0.0
            if r > 0 and r < rows - 1:
                dudy = (u[r + 1][c] - u[r - 1][c]) * 0.5
            vort = abs(dvdx - dudy)

            if vort > _STORM_SPIN_THRESHOLD and pres[r][c] < 0.95:
                # Tropical cyclone if near equator over warm ocean
                if eq_dist < 0.2 and not land[r][c] and sst[r][c] > 0.45:
                    storm_type = "tropical"
                    intensity = 0.5 + sst[r][c] * _STORM_SST_BOOST * 0.3
                else:
                    storm_type = "extratropical"
                    intensity = 0.3 + vort * 2.0

                # Don't spawn too close to existing storms
                too_close = False
                for s in storms:
                    dr = abs(s['r'] - r)
                    dc = min(abs(s['c'] - c), cols - abs(s['c'] - c))
                    if dr + dc < 6:
                        too_close = True
                        break
                if not too_close and len(storms) < 15:
                    storms.append({
                        'r': float(r), 'c': float(c),
                        'intensity': min(1.0, intensity),
                        'type': storm_type,
                        'age': 0,
                        'vr': random.uniform(-0.15, 0.15),
                        'vc': random.uniform(-0.1, 0.1),
                    })

    # Update existing storms
    new_storms = []
    for s in storms:
        s['age'] += 1
        # Move storm with mean wind + poleward drift for tropical
        r_int = max(0, min(rows - 1, int(s['r'])))
        c_int = _wrap_col(int(s['c']), cols)
        s['r'] += v[r_int][c_int] * 0.5 + s['vr']
        s['c'] += u[r_int][c_int] * 0.5 + s['vc']
        s['c'] = s['c'] % cols

        # Tropical storms drift poleward
        if s['type'] == "tropical":
            lat = _lat_fraction(int(s['r']), rows)
            if lat < 0.5:
                s['r'] -= 0.08  # north
            else:
                s['r'] += 0.08  # south
            # Intensify over warm water, weaken over land/cold
            if 0 <= int(s['r']) < rows:
                ri, ci = int(s['r']), _wrap_col(int(s['c']), cols)
                if land[ri][ci]:
                    s['intensity'] -= 0.02
                elif sst[ri][ci] > 0.5:
                    s['intensity'] = min(1.0, s['intensity'] + 0.005)

        # Dissipation
        s['intensity'] -= _STORM_DISSIPATE
        if s['intensity'] > 0.05 and 0 <= s['r'] < rows:
            new_storms.append(s)

        # Storm influences pressure field
        if 0 <= int(s['r']) < rows:
            ri = int(s['r'])
            ci = _wrap_col(int(s['c']), cols)
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    rr = ri + dr
                    cc = _wrap_col(ci + dc, cols)
                    if 0 <= rr < rows:
                        dist = math.sqrt(dr * dr + dc * dc)
                        if dist < 3:
                            pres[rr][cc] -= 0.01 * s['intensity'] * (1.0 - dist / 3.0)

    self.planetary_atmos_storms = new_storms


# ======================================================================
#  Key Handlers
# ======================================================================

def _handle_planetary_atmos_menu_key(self, key: int) -> bool:
    """Handle keys in preset menu."""
    if key == curses.KEY_UP or key == ord('k'):
        self.planetary_atmos_menu_sel = (self.planetary_atmos_menu_sel - 1) % len(PLANETARY_ATMOS_PRESETS)
        return True
    if key == curses.KEY_DOWN or key == ord('j'):
        self.planetary_atmos_menu_sel = (self.planetary_atmos_menu_sel + 1) % len(PLANETARY_ATMOS_PRESETS)
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _planetary_atmos_init(self, self.planetary_atmos_menu_sel)
        self.planetary_atmos_running = True
        return True
    if key == ord('q') or key == 27:
        self._exit_planetary_atmos_mode()
        return True
    return False


def _handle_planetary_atmos_key(self, key: int) -> bool:
    """Handle keys during simulation."""
    if key == ord(' '):
        self.planetary_atmos_running = not self.planetary_atmos_running
        return True
    if key == ord('v'):
        views = ["pressure", "temperature", "graphs"]
        idx = views.index(self.planetary_atmos_view)
        self.planetary_atmos_view = views[(idx + 1) % len(views)]
        return True
    if key == ord('n'):
        _planetary_atmos_step(self)
        return True
    if key == ord('+') or key == ord('='):
        self.planetary_atmos_co2 = min(1.0, self.planetary_atmos_co2 + 0.05)
        self._flash(f"CO2: {self.planetary_atmos_co2:.2f}")
        return True
    if key == ord('-'):
        self.planetary_atmos_co2 = max(0.0, self.planetary_atmos_co2 - 0.05)
        self._flash(f"CO2: {self.planetary_atmos_co2:.2f}")
        return True
    if key == ord('r'):
        idx = next((i for i, p in enumerate(PLANETARY_ATMOS_PRESETS)
                     if p[2] == self.planetary_atmos_preset_id), 0)
        _planetary_atmos_init(self, idx)
        self.planetary_atmos_running = True
        return True
    if key == ord('R') or key == ord('m'):
        self.planetary_atmos_menu = True
        self.planetary_atmos_menu_sel = 0
        return True
    if key == ord('q'):
        self._exit_planetary_atmos_mode()
        return True
    return False


# ======================================================================
#  Drawing — Preset Menu
# ======================================================================

def _draw_planetary_atmos_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()
    title = "Planetary Atmosphere & Weather System"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD | curses.color_pair(4))
    except curses.error:
        pass

    sub = "Select a climate preset:"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(sub)) // 2), sub)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(PLANETARY_ATMOS_PRESETS):
        y = 5 + i * 3
        if y + 1 >= max_y:
            break
        marker = "> " if i == self.planetary_atmos_menu_sel else "  "
        attr = curses.A_REVERSE if i == self.planetary_atmos_menu_sel else 0
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

def _draw_planetary_atmos(self, max_y: int, max_x: int):
    """Dispatch to appropriate view drawer."""
    if self.planetary_atmos_view == "pressure":
        _draw_pressure_view(self, max_y, max_x)
    elif self.planetary_atmos_view == "temperature":
        _draw_temperature_view(self, max_y, max_x)
    elif self.planetary_atmos_view == "graphs":
        _draw_graphs_view(self, max_y, max_x)


# ======================================================================
#  Drawing — Pressure / Wind Map
# ======================================================================

_WIND_ARROWS = {
    (0, 1): '\u2192', (0, -1): '\u2190',
    (1, 0): '\u2193', (-1, 0): '\u2191',
    (1, 1): '\u2198', (1, -1): '\u2199',
    (-1, 1): '\u2197', (-1, -1): '\u2196',
    (0, 0): '\u00b7',
}

_PRESSURE_GLYPHS = " .:-=oO@#"
_PRECIP_GLYPHS = [' ', '.', ',', ';', ':', '!', '|']

# Storm glyphs
_STORM_TROPICAL = '@'
_STORM_EXTRA = '*'
_STORM_INTENSE = '#'


def _draw_pressure_view(self, max_y: int, max_x: int):
    """Render pressure/wind map with isobars, storms, precipitation."""
    self.stdscr.erase()
    rows = self.planetary_atmos_rows
    cols = self.planetary_atmos_cols
    pres = self.planetary_atmos_pressure
    u = self.planetary_atmos_u
    v = self.planetary_atmos_v
    precip = self.planetary_atmos_precip
    land = self.planetary_atmos_land
    ice = self.planetary_atmos_ice
    storms = self.planetary_atmos_storms

    # Determine pressure range for isobar coloring
    p_min = min(pres[r][c] for r in range(rows) for c in range(cols))
    p_max = max(pres[r][c] for r in range(rows) for c in range(cols))
    p_rng = p_max - p_min if p_max > p_min else 0.01

    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, max_x - 1)

    for r in range(draw_rows):
        for c in range(draw_cols):
            if r >= rows or c >= cols:
                continue

            p_val = (pres[r][c] - p_min) / p_rng
            rain = precip[r][c]
            is_ice = ice[r][c] > 0.3
            is_land = land[r][c]

            # Choose glyph
            ch = ' '
            color_idx = 7  # default white

            if rain > 0.01:
                # Precipitation overlay
                ri = min(len(_PRECIP_GLYPHS) - 1, int(rain * len(_PRECIP_GLYPHS) * 3))
                ch = _PRECIP_GLYPHS[ri]
                color_idx = 4  # blue for rain
            elif is_ice:
                ch = '~'
                color_idx = 7  # white
            elif is_land:
                ch = '#' if p_val > 0.6 else '='
                color_idx = 3  # yellow/brown for land
            else:
                # Ocean: show wind direction at sparse intervals
                if r % 3 == 0 and c % 4 == 0:
                    # Wind arrow
                    uu = u[r][c]
                    vv = v[r][c]
                    ws = math.sqrt(uu * uu + vv * vv)
                    if ws > 0.05:
                        du = 1 if uu > 0.1 else (-1 if uu < -0.1 else 0)
                        dv = 1 if vv > 0.1 else (-1 if vv < -0.1 else 0)
                        ch = _WIND_ARROWS.get((dv, du), '.')
                        # Color by wind speed
                        if ws > 0.6:
                            color_idx = 1  # red = strong
                        elif ws > 0.3:
                            color_idx = 3  # yellow = moderate
                        else:
                            color_idx = 6  # cyan = light
                    else:
                        ch = '\u00b7'
                        color_idx = 7
                else:
                    # Isobar visualization
                    # Draw contour lines at regular pressure intervals
                    p_quantized = int(p_val * 8)
                    ch = _PRESSURE_GLYPHS[min(len(_PRESSURE_GLYPHS) - 1, p_quantized)]
                    if p_val < 0.3:
                        color_idx = 4  # blue = low pressure
                    elif p_val > 0.7:
                        color_idx = 1  # red = high pressure
                    else:
                        color_idx = 7

            try:
                self.stdscr.addstr(r, c, ch, curses.color_pair(color_idx))
            except curses.error:
                pass

    # Draw storms on top
    for s in storms:
        sr = int(s['r'])
        sc = int(s['c']) % cols
        if 0 <= sr < draw_rows and 0 <= sc < draw_cols:
            if s['intensity'] > 0.7:
                glyph = _STORM_INTENSE
            elif s['type'] == "tropical":
                glyph = _STORM_TROPICAL
            else:
                glyph = _STORM_EXTRA
            try:
                self.stdscr.addstr(sr, sc, glyph,
                                   curses.color_pair(1) | curses.A_BOLD)
            except curses.error:
                pass

    # Status bar
    gen = self.planetary_atmos_generation
    n_storms = len(storms)
    co2 = self.planetary_atmos_co2
    state = "RUNNING" if self.planetary_atmos_running else "PAUSED"
    status = (f" {self.planetary_atmos_preset_name} | tick {gen} | {state} | "
              f"storms:{n_storms} | CO2:{co2:.2f} | [v]iew [+/-]CO2 [space] [r]eset [q]uit")
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Legend
    legend = " L=low(blue) H=high(red)  @=tropical *=extratropical #=intense  .:;|=rain  ~=ice  #/==land"
    try:
        self.stdscr.addstr(max_y - 1, 0, legend[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Temperature / Moisture Heatmap
# ======================================================================

_TEMP_GLYPHS = ' .,:;+=*#@'
_ICE_GLYPH = '~'


def _draw_temperature_view(self, max_y: int, max_x: int):
    """Render temperature heatmap with ice extent and moisture."""
    self.stdscr.erase()
    rows = self.planetary_atmos_rows
    cols = self.planetary_atmos_cols
    temp = self.planetary_atmos_temp
    moisture = self.planetary_atmos_moisture
    ice = self.planetary_atmos_ice
    land = self.planetary_atmos_land
    sst = self.planetary_atmos_sst

    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, max_x - 1)

    for r in range(draw_rows):
        for c in range(draw_cols):
            if r >= rows or c >= cols:
                continue

            t = temp[r][c]
            m = moisture[r][c]
            is_ice = ice[r][c] > 0.3
            is_land = land[r][c]

            if is_ice:
                ch = _ICE_GLYPH
                color_idx = 7  # bright white
            else:
                # Temperature glyph
                ti = int(t / 1.0 * (len(_TEMP_GLYPHS) - 1))
                ti = max(0, min(len(_TEMP_GLYPHS) - 1, ti))
                ch = _TEMP_GLYPHS[ti]

                # Color by temperature band
                if t > 0.7:
                    color_idx = 1  # red = hot
                elif t > 0.5:
                    color_idx = 3  # yellow = warm
                elif t > 0.3:
                    color_idx = 2  # green = temperate
                elif t > 0.15:
                    color_idx = 6  # cyan = cool
                else:
                    color_idx = 4  # blue = cold

                # Moisture overlay: bold if humid
                if m > 0.6 and not is_land:
                    ch = ':'  # humid ocean
                    color_idx = 4

            attr = curses.color_pair(color_idx)
            if is_land and not is_ice:
                attr |= curses.A_DIM

            try:
                self.stdscr.addstr(r, c, ch, attr)
            except curses.error:
                pass

    # Draw ocean current hints (SST gradient)
    for r in range(0, draw_rows, 4):
        for c in range(0, draw_cols, 6):
            if r >= rows or c >= cols:
                continue
            if not land[r][c] and ice[r][c] < 0.3:
                s = sst[r][c]
                if s > 0.55:
                    try:
                        self.stdscr.addstr(r, c, '\u00b7', curses.color_pair(1))
                    except curses.error:
                        pass

    # Status bar
    gen = self.planetary_atmos_generation
    state = "RUNNING" if self.planetary_atmos_running else "PAUSED"
    hist = self.planetary_atmos_history
    g_temp = hist['global_temp'][-1] if hist['global_temp'] else 0
    ice_a = hist['ice_area'][-1] if hist['ice_area'] else 0
    status = (f" {self.planetary_atmos_preset_name} | tick {gen} | {state} | "
              f"T:{g_temp:.3f} | ice:{ice_a:.1%} | CO2:{self.planetary_atmos_co2:.2f} | "
              f"[v]iew [+/-]CO2 [space] [r]eset [q]uit")
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    legend = " cold(blue) cool(cyan) temperate(green) warm(yellow) hot(red)  ~=ice  :=humid"
    try:
        self.stdscr.addstr(max_y - 1, 0, legend[:max_x - 1], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Drawing — Time-Series Sparkline Graphs
# ======================================================================

def _draw_graphs_view(self, max_y: int, max_x: int):
    """Time-series sparkline graphs for planetary metrics."""
    self.stdscr.erase()
    hist = self.planetary_atmos_history
    graph_w = min(200, max_x - 30)

    title = (f"Planetary Metrics -- {self.planetary_atmos_preset_name} | "
             f"tick {self.planetary_atmos_generation}")
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD)
    except curses.error:
        pass

    labels = [
        ("Global Temp",     'global_temp',    1),
        ("CO2 Level",       'co2',            3),
        ("Storm Count",     'storm_count',    1),
        ("Precipitation",   'precipitation',  4),
        ("Jet Stream Lat",  'jet_lat',        6),
        ("Ice Area %",      'ice_area',       7),
        ("Mean Pressure",   'mean_pressure',  5),
        ("Max Wind Speed",  'max_wind',       1),
        ("Humidity",        'humidity',        4),
        ("GHG Forcing",     'ghg_forcing',    3),
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

    status = "[v]iew [+/-]CO2 [space]pause [r]estart [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Registration
# ======================================================================

def register(App):
    """Register planetary atmosphere mode methods on the App class."""
    App.PLANETARY_ATMOS_PRESETS = PLANETARY_ATMOS_PRESETS
    App._enter_planetary_atmos_mode = _enter_planetary_atmos_mode
    App._exit_planetary_atmos_mode = _exit_planetary_atmos_mode
    App._planetary_atmos_init = _planetary_atmos_init
    App._planetary_atmos_step = _planetary_atmos_step
    App._handle_planetary_atmos_menu_key = _handle_planetary_atmos_menu_key
    App._handle_planetary_atmos_key = _handle_planetary_atmos_key
    App._draw_planetary_atmos_menu = _draw_planetary_atmos_menu
    App._draw_planetary_atmos = _draw_planetary_atmos
