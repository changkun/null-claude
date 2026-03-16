"""Mode: wfire — Wildfire Spread & Firefighting Simulation.

Rothermel-inspired fire propagation model on heterogeneous terrain with
elevation, wind fields, multiple fuel types (grass/shrub/timber/urban),
slope-driven acceleration, ember spotting for long-range ignition, smoke
plume visualization, and active firefighting agents (firebreaks, water drops).

Emergent phenomena:
  - Crown fire transitions when surface intensity exceeds threshold
  - Slope-driven fire acceleration (uphill runs)
  - Ember spotting — long-range ignition ahead of the main front
  - Fuel moisture dynamics affecting ignition probability
  - Smoke plume dispersion following wind field
  - Firefighting agents cutting firebreaks and dropping water
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

# Fuel types: (name, base_spread_rate, heat_content, moisture_extinction,
#               crown_threshold, ember_production, color_unburned)
FUEL_GRASS = 0
FUEL_SHRUB = 1
FUEL_TIMBER = 2
FUEL_URBAN = 3
FUEL_WATER = 4
FUEL_ROCK = 5

_FUEL_PROPS = {
    FUEL_GRASS:  {"name": "grass",  "spread": 1.8, "heat": 0.6, "moist_ext": 0.25,
                  "crown_thr": 999.0, "ember": 0.02},
    FUEL_SHRUB:  {"name": "shrub",  "spread": 1.2, "heat": 1.0, "moist_ext": 0.30,
                  "crown_thr": 3.5, "ember": 0.05},
    FUEL_TIMBER: {"name": "timber", "spread": 0.7, "heat": 1.8, "moist_ext": 0.35,
                  "crown_thr": 2.5, "ember": 0.10},
    FUEL_URBAN:  {"name": "urban",  "spread": 0.4, "heat": 2.5, "moist_ext": 0.15,
                  "crown_thr": 2.0, "ember": 0.08},
    FUEL_WATER:  {"name": "water",  "spread": 0.0, "heat": 0.0, "moist_ext": 1.0,
                  "crown_thr": 999.0, "ember": 0.0},
    FUEL_ROCK:   {"name": "rock",   "spread": 0.0, "heat": 0.0, "moist_ext": 1.0,
                  "crown_thr": 999.0, "ember": 0.0},
}


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

WFIRE_PRESETS = [
    ("Grassland Brushfire",
     "Fast-moving grass fire on flat terrain with low fuel load",
     "grassland"),
    ("Mountain Wildfire",
     "Timber fire on steep terrain with slope-driven runs and spotting",
     "mountain"),
    ("Urban-Wildland Interface",
     "Mixed urban-vegetation zone with structure ignitions",
     "wui"),
    ("Prescribed Burn",
     "Controlled low-intensity burn with firefighter containment lines",
     "prescribed"),
    ("Firestorm",
     "Extreme fire behavior with crown fire, massive spotting and pyro-convection",
     "firestorm"),
    ("Canyon Wind Event",
     "Strong downslope winds drive fire through canyon terrain",
     "canyon"),
]


# ══════════════════════════════════════════════════════════════════════
#  Firefighter agent
# ══════════════════════════════════════════════════════════════════════

class _Firefighter:
    __slots__ = ('r', 'c', 'type', 'cooldown', 'active')

    def __init__(self, r, c, ftype='break'):
        self.r = r
        self.c = c
        self.type = ftype        # 'break' or 'water'
        self.cooldown = 0
        self.active = True


# ══════════════════════════════════════════════════════════════════════
#  Helpers — terrain generation
# ══════════════════════════════════════════════════════════════════════

def _wfire_make_terrain(self):
    """Generate elevation, fuel type, and fuel moisture grids."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    rng = random.random
    preset_id = self.wfire_preset_id

    # Elevation: simple diamond-square-ish noise via octave summation
    elev = [[0.0] * cols for _ in range(rows)]

    # Generate smooth noise with multiple octaves
    n_peaks = max(3, (rows * cols) // 200)
    peaks = [(random.randint(0, rows - 1), random.randint(0, cols - 1),
              rng() * self.wfire_max_elevation) for _ in range(n_peaks)]

    for r in range(rows):
        for c in range(cols):
            h = 0.0
            for pr, pc, ph in peaks:
                dist = math.sqrt((r - pr) ** 2 + (c - pc) ** 2)
                sigma = max(4, min(rows, cols) // 4)
                h += ph * math.exp(-dist * dist / (2 * sigma * sigma))
            elev[r][c] = h

    # Canyon preset: create a valley
    if preset_id == "canyon":
        mid_c = cols // 2
        for r in range(rows):
            for c in range(cols):
                dist_from_center = abs(c - mid_c)
                canyon_depth = self.wfire_max_elevation * 0.8
                canyon_width = max(3, cols // 6)
                if dist_from_center < canyon_width:
                    elev[r][c] = max(0, elev[r][c] - canyon_depth *
                                     (1.0 - dist_from_center / canyon_width))
                else:
                    elev[r][c] += canyon_depth * 0.3

    # Mountain preset: steeper terrain
    if preset_id == "mountain":
        for r in range(rows):
            for c in range(cols):
                elev[r][c] *= 1.5

    self.wfire_elevation = elev

    # Fuel type grid
    fuel = [[FUEL_GRASS] * cols for _ in range(rows)]

    if preset_id == "grassland":
        # Mostly grass with scattered shrub patches
        for r in range(rows):
            for c in range(cols):
                v = rng()
                if v < 0.85:
                    fuel[r][c] = FUEL_GRASS
                elif v < 0.95:
                    fuel[r][c] = FUEL_SHRUB
                else:
                    fuel[r][c] = FUEL_ROCK
    elif preset_id == "mountain":
        for r in range(rows):
            for c in range(cols):
                h = elev[r][c]
                v = rng()
                if h > self.wfire_max_elevation * 0.85:
                    fuel[r][c] = FUEL_ROCK
                elif h > self.wfire_max_elevation * 0.5:
                    fuel[r][c] = FUEL_TIMBER if v < 0.8 else FUEL_SHRUB
                elif h > self.wfire_max_elevation * 0.2:
                    fuel[r][c] = FUEL_TIMBER if v < 0.5 else FUEL_SHRUB
                else:
                    fuel[r][c] = FUEL_GRASS if v < 0.6 else FUEL_SHRUB
    elif preset_id == "wui":
        # Urban clusters amid vegetation
        n_clusters = max(2, (rows * cols) // 300)
        for _ in range(n_clusters):
            cr, cc = random.randint(2, rows - 3), random.randint(2, cols - 3)
            rad = random.randint(2, max(3, min(rows, cols) // 8))
            for dr in range(-rad, rad + 1):
                for dc in range(-rad, rad + 1):
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if dr * dr + dc * dc <= rad * rad and rng() < 0.7:
                            fuel[nr][nc] = FUEL_URBAN
        for r in range(rows):
            for c in range(cols):
                if fuel[r][c] == FUEL_GRASS:
                    v = rng()
                    if v < 0.4:
                        fuel[r][c] = FUEL_SHRUB
                    elif v < 0.65:
                        fuel[r][c] = FUEL_TIMBER
    elif preset_id == "prescribed":
        for r in range(rows):
            for c in range(cols):
                v = rng()
                fuel[r][c] = FUEL_GRASS if v < 0.5 else FUEL_SHRUB
    elif preset_id == "firestorm":
        for r in range(rows):
            for c in range(cols):
                v = rng()
                if v < 0.15:
                    fuel[r][c] = FUEL_GRASS
                elif v < 0.40:
                    fuel[r][c] = FUEL_SHRUB
                else:
                    fuel[r][c] = FUEL_TIMBER
    elif preset_id == "canyon":
        mid_c = cols // 2
        canyon_width = max(3, cols // 6)
        for r in range(rows):
            for c in range(cols):
                dist = abs(c - mid_c)
                v = rng()
                if dist < canyon_width:
                    fuel[r][c] = FUEL_SHRUB if v < 0.6 else FUEL_GRASS
                else:
                    fuel[r][c] = FUEL_TIMBER if v < 0.7 else FUEL_SHRUB

    # Add scattered water bodies
    n_water = max(1, (rows * cols) // 500)
    for _ in range(n_water):
        wr, wc = random.randint(0, rows - 1), random.randint(0, cols - 1)
        rad = random.randint(1, max(2, min(rows, cols) // 12))
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                nr, nc = wr + dr, wc + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if dr * dr + dc * dc <= rad * rad:
                        fuel[nr][nc] = FUEL_WATER

    self.wfire_fuel = fuel

    # Fuel moisture content (0.0 = bone dry, 1.0 = saturated)
    moisture = [[0.0] * cols for _ in range(rows)]
    base_m = self.wfire_base_moisture
    for r in range(rows):
        for c in range(cols):
            if fuel[r][c] == FUEL_WATER:
                moisture[r][c] = 1.0
            else:
                moisture[r][c] = max(0.0, min(1.0,
                    base_m + 0.1 * (rng() - 0.5)))
    self.wfire_moisture = moisture


def _wfire_make_fire_state(self):
    """Initialize fire intensity, burned status, and smoke grids."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    self.wfire_intensity = [[0.0] * cols for _ in range(rows)]
    self.wfire_burned = [[False] * cols for _ in range(rows)]
    self.wfire_crown = [[False] * cols for _ in range(rows)]
    self.wfire_smoke = [[0.0] * cols for _ in range(rows)]
    self.wfire_firebreak = [[False] * cols for _ in range(rows)]


def _wfire_ignite(self):
    """Place initial ignition point(s)."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    fuel = self.wfire_fuel
    intensity = self.wfire_intensity
    preset_id = self.wfire_preset_id

    if preset_id == "prescribed":
        # Line ignition along left edge
        c = 2
        for r in range(rows // 4, 3 * rows // 4):
            if fuel[r][c] not in (FUEL_WATER, FUEL_ROCK):
                intensity[r][c] = 1.0
    elif preset_id == "canyon":
        # Ignite at bottom of canyon
        mid_c = cols // 2
        r = rows - 3
        for dc in range(-2, 3):
            c = mid_c + dc
            if 0 <= c < cols and fuel[r][c] not in (FUEL_WATER, FUEL_ROCK):
                intensity[r][c] = 2.0
    elif preset_id == "firestorm":
        # Multiple ignition points
        for _ in range(3):
            r = random.randint(rows // 4, 3 * rows // 4)
            c = random.randint(cols // 4, 3 * cols // 4)
            if fuel[r][c] not in (FUEL_WATER, FUEL_ROCK):
                intensity[r][c] = 3.0
    else:
        # Single point ignition near center-left
        r = rows // 2
        c = cols // 4
        # Find a burnable cell near this point
        for dr in range(-3, 4):
            for dc in range(-3, 4):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if fuel[nr][nc] not in (FUEL_WATER, FUEL_ROCK):
                        intensity[nr][nc] = 2.0
                        break
            else:
                continue
            break


def _wfire_make_wind(self):
    """Initialize wind field (direction in radians, speed)."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    base_dir = self.wfire_wind_dir
    base_speed = self.wfire_wind_speed
    rng = random.random

    wind_u = [[0.0] * cols for _ in range(rows)]  # east component
    wind_v = [[0.0] * cols for _ in range(rows)]  # north component

    for r in range(rows):
        for c in range(cols):
            # Local perturbation
            local_dir = base_dir + 0.3 * (rng() - 0.5)
            local_speed = base_speed * (0.8 + 0.4 * rng())
            wind_u[r][c] = local_speed * math.cos(local_dir)
            wind_v[r][c] = local_speed * math.sin(local_dir)

    self.wfire_wind_u = wind_u
    self.wfire_wind_v = wind_v


def _wfire_make_firefighters(self):
    """Place firefighting agents based on preset."""
    self.wfire_fighters = []
    preset_id = self.wfire_preset_id
    rows = self.wfire_rows
    cols = self.wfire_cols

    if preset_id == "prescribed":
        # Firefighters forming containment lines
        n = max(4, min(rows, cols) // 4)
        for i in range(n):
            r = rows // 4 + i * (rows // 2) // max(1, n - 1)
            r = min(r, rows - 1)
            self.wfire_fighters.append(_Firefighter(r, cols // 2, 'break'))
        for i in range(n // 2):
            r = rows // 3 + i * (rows // 3) // max(1, n // 2)
            r = min(r, rows - 1)
            self.wfire_fighters.append(_Firefighter(r, cols * 3 // 4, 'water'))
    elif preset_id == "wui":
        # Firefighters defending structures
        n = max(3, (rows * cols) // 400)
        for _ in range(n):
            r = random.randint(1, rows - 2)
            c = random.randint(cols // 2, cols - 2)
            self.wfire_fighters.append(
                _Firefighter(r, c, 'water' if random.random() < 0.6 else 'break'))
    else:
        # Few or no firefighters for natural scenarios
        if preset_id not in ("firestorm",):
            n = max(2, (rows * cols) // 600)
            for _ in range(n):
                r = random.randint(1, rows - 2)
                c = random.randint(cols // 2, cols - 2)
                self.wfire_fighters.append(
                    _Firefighter(r, c, 'water' if random.random() < 0.5 else 'break'))


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _enter_wfire_mode(self):
    """Enter Wildfire mode — show preset menu."""
    self.wfire_menu = True
    self.wfire_menu_sel = 0
    self._flash("Wildfire Spread & Firefighting — select a scenario")


def _exit_wfire_mode(self):
    """Exit Wildfire mode."""
    self.wfire_mode = False
    self.wfire_menu = False
    self.wfire_running = False
    self._flash("Wildfire mode OFF")


def _wfire_init(self, preset_idx: int):
    """Initialize wildfire simulation with the given preset."""
    name, _desc, preset_id = self.WFIRE_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()

    # Grid dimensions
    cols = max(20, max_x - 2)
    rows = max(12, max_y - 4)
    self.wfire_rows = rows
    self.wfire_cols = cols

    self.wfire_preset_name = name
    self.wfire_preset_id = preset_id
    self.wfire_generation = 0
    self.wfire_running = False
    self.wfire_steps_per_frame = 1

    # Physics parameters (defaults)
    self.wfire_wind_dir = 0.0          # radians (0=east, pi/2=north)
    self.wfire_wind_speed = 1.0        # wind speed multiplier
    self.wfire_base_moisture = 0.15    # base fuel moisture content
    self.wfire_max_elevation = 10.0    # elevation range
    self.wfire_ember_range = 8         # max spotting distance
    self.wfire_ember_prob = 0.03       # base ember ignition probability
    self.wfire_spread_rate = 1.0       # global spread rate multiplier
    self.wfire_slope_factor = 0.6      # slope effect on spread rate
    self.wfire_crown_intensity = 2.5   # intensity threshold for crown fire
    self.wfire_burnout_rate = 0.08     # rate of intensity decay
    self.wfire_smoke_decay = 0.92      # smoke dissipation rate

    # Display mode
    self.wfire_view = "fire"   # "fire", "elevation", "fuel", "moisture"

    # Statistics
    self.wfire_total_burned = 0
    self.wfire_active_cells = 0
    self.wfire_crown_cells = 0
    self.wfire_ember_ignitions = 0
    self.wfire_max_intensity = 0.0
    self.wfire_area_fraction = 0.0
    self.wfire_history = []            # (gen, active, burned_frac)

    # Preset-specific tuning
    if preset_id == "grassland":
        self.wfire_wind_speed = 1.5
        self.wfire_wind_dir = 0.0
        self.wfire_base_moisture = 0.10
        self.wfire_max_elevation = 3.0
        self.wfire_ember_range = 5
        self.wfire_spread_rate = 1.4
    elif preset_id == "mountain":
        self.wfire_wind_speed = 0.8
        self.wfire_wind_dir = math.pi * 0.25
        self.wfire_base_moisture = 0.20
        self.wfire_max_elevation = 25.0
        self.wfire_slope_factor = 1.0
        self.wfire_ember_range = 12
        self.wfire_ember_prob = 0.05
    elif preset_id == "wui":
        self.wfire_wind_speed = 1.2
        self.wfire_wind_dir = math.pi * 0.1
        self.wfire_base_moisture = 0.12
        self.wfire_max_elevation = 8.0
        self.wfire_ember_range = 10
        self.wfire_spread_rate = 1.1
    elif preset_id == "prescribed":
        self.wfire_wind_speed = 0.5
        self.wfire_wind_dir = 0.0
        self.wfire_base_moisture = 0.22
        self.wfire_max_elevation = 4.0
        self.wfire_ember_range = 3
        self.wfire_ember_prob = 0.01
        self.wfire_spread_rate = 0.7
    elif preset_id == "firestorm":
        self.wfire_wind_speed = 2.0
        self.wfire_wind_dir = math.pi * 0.15
        self.wfire_base_moisture = 0.05
        self.wfire_max_elevation = 15.0
        self.wfire_ember_range = 15
        self.wfire_ember_prob = 0.08
        self.wfire_spread_rate = 1.6
        self.wfire_crown_intensity = 1.8
    elif preset_id == "canyon":
        self.wfire_wind_speed = 2.5
        self.wfire_wind_dir = -math.pi * 0.5   # downslope (southward)
        self.wfire_base_moisture = 0.08
        self.wfire_max_elevation = 20.0
        self.wfire_slope_factor = 1.2
        self.wfire_ember_range = 10
        self.wfire_spread_rate = 1.3

    # Build terrain and state
    self._wfire_make_terrain()
    self._wfire_make_fire_state()
    self._wfire_make_wind()
    self._wfire_make_firefighters()
    self._wfire_ignite()

    self.wfire_mode = True
    self.wfire_menu = False
    self._flash(f"Wildfire: {name} — Space to start")


# ══════════════════════════════════════════════════════════════════════
#  Physics step
# ══════════════════════════════════════════════════════════════════════

def _wfire_step(self):
    """Advance wildfire simulation by one time step."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    intensity = self.wfire_intensity
    burned = self.wfire_burned
    crown = self.wfire_crown
    smoke = self.wfire_smoke
    fuel = self.wfire_fuel
    moisture = self.wfire_moisture
    elev = self.wfire_elevation
    wind_u = self.wfire_wind_u
    wind_v = self.wfire_wind_v
    firebreak = self.wfire_firebreak
    rand = random.random
    sqrt = math.sqrt
    exp = math.exp

    spread_rate = self.wfire_spread_rate
    slope_factor = self.wfire_slope_factor
    burnout = self.wfire_burnout_rate
    crown_thr = self.wfire_crown_intensity
    ember_range = self.wfire_ember_range
    ember_prob = self.wfire_ember_prob
    smoke_decay = self.wfire_smoke_decay

    # New intensity grid
    new_intensity = [[0.0] * cols for _ in range(rows)]
    new_crown = [[False] * cols for _ in range(rows)]
    active = 0
    crown_count = 0
    max_int = 0.0
    ember_ign = 0

    # 8-connected neighbors with distance
    neighbors = [(-1, -1, 1.414), (-1, 0, 1.0), (-1, 1, 1.414),
                 (0, -1, 1.0),                   (0, 1, 1.0),
                 (1, -1, 1.414),  (1, 0, 1.0),   (1, 1, 1.414)]

    for r in range(rows):
        for c in range(cols):
            # Skip non-burnable or firebreak cells
            f = fuel[r][c]
            if f in (FUEL_WATER, FUEL_ROCK) or firebreak[r][c]:
                new_intensity[r][c] = 0.0
                continue

            fp = _FUEL_PROPS[f]
            cur = intensity[r][c]

            if burned[r][c] and cur <= 0.01:
                # Already fully burned out
                new_intensity[r][c] = 0.0
                continue

            # ── Spread from neighbors ──
            spread_in = 0.0
            for dr, dc, dist in neighbors:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    ni = intensity[nr][nc]
                    if ni <= 0.0:
                        continue
                    if firebreak[nr][nc]:
                        continue

                    nf = fuel[nr][nc]
                    if nf in (FUEL_WATER, FUEL_ROCK):
                        continue

                    # Base spread from neighbor
                    nfp = _FUEL_PROPS[nf]
                    base = ni * nfp["spread"] * spread_rate / dist

                    # Wind effect: dot product of wind with direction to cell
                    dx, dy = dc, -dr  # screen coords
                    wu = wind_u[nr][nc]
                    wv = wind_v[nr][nc]
                    wind_dot = (wu * dx + wv * dy)
                    wind_mult = max(0.1, 1.0 + 0.5 * wind_dot)

                    # Slope effect: fire spreads faster uphill
                    dh = elev[r][c] - elev[nr][nc]
                    slope_mult = 1.0 + slope_factor * (dh / max(1.0, dist * 3.0))
                    slope_mult = max(0.2, min(3.0, slope_mult))

                    # Moisture dampening
                    m = moisture[r][c]
                    m_ext = fp["moist_ext"]
                    if m >= m_ext:
                        moist_mult = 0.0
                    else:
                        moist_mult = 1.0 - (m / m_ext) ** 1.5

                    # Crown fire boost
                    crown_mult = 1.5 if crown[nr][nc] else 1.0

                    contribution = base * wind_mult * slope_mult * moist_mult * crown_mult
                    spread_in += max(0.0, contribution)

            # ── Update intensity ──
            if cur > 0.0:
                # Existing fire: burn and decay
                new_int = cur + spread_in * 0.3 - burnout * (1.0 + cur * 0.1)
                # Fuel exhaustion accelerates burnout
                if burned[r][c]:
                    new_int -= burnout * 0.5
            else:
                # Potential new ignition from spread
                ignition_threshold = 0.15 + moisture[r][c] * 0.5
                if spread_in > ignition_threshold:
                    new_int = spread_in * 0.5
                else:
                    new_int = 0.0

            new_int = max(0.0, new_int)

            # Crown fire transition
            if new_int >= fp["crown_thr"] and new_int >= crown_thr:
                new_crown[r][c] = True
                crown_count += 1

            if new_int > 0.0:
                burned[r][c] = True
                active += 1
                if new_int > max_int:
                    max_int = new_int

            new_intensity[r][c] = new_int

    # ── Ember spotting ──
    for r in range(rows):
        for c in range(cols):
            ni = new_intensity[r][c]
            if ni < 1.5:
                continue
            f = fuel[r][c]
            fp = _FUEL_PROPS[f]
            ep = fp["ember"] * ember_prob * ni

            if rand() > ep:
                continue

            # Launch ember in wind direction with random range
            wu = wind_u[r][c]
            wv = wind_v[r][c]
            w_mag = sqrt(wu * wu + wv * wv) + 0.01
            dist = random.randint(3, ember_range)
            # Add some random spread
            angle_pert = (rand() - 0.5) * 1.0
            base_angle = math.atan2(-wv, wu)
            angle = base_angle + angle_pert
            tr = r - int(dist * math.sin(angle))
            tc = c + int(dist * math.cos(angle))

            if 0 <= tr < rows and 0 <= tc < cols:
                tf = fuel[tr][tc]
                if (tf not in (FUEL_WATER, FUEL_ROCK) and
                        not firebreak[tr][tc] and
                        new_intensity[tr][tc] <= 0.0 and
                        not burned[tr][tc]):
                    # Ember ignition — moisture check
                    if moisture[tr][tc] < _FUEL_PROPS[tf]["moist_ext"] * 0.8:
                        new_intensity[tr][tc] = 0.8 + rand() * 0.5
                        burned[tr][tc] = True
                        ember_ign += 1

    self.wfire_intensity = new_intensity
    self.wfire_crown = new_crown

    # ── Smoke plume propagation ──
    new_smoke = [[s * smoke_decay for s in row] for row in smoke]
    for r in range(rows):
        for c in range(cols):
            if new_intensity[r][c] > 0.3:
                smoke_prod = new_intensity[r][c] * 0.15
                if new_crown[r][c]:
                    smoke_prod *= 2.0
                new_smoke[r][c] += smoke_prod
                # Advect smoke downwind
                wu = wind_u[r][c]
                wv = wind_v[r][c]
                sr = r - int(wv * 0.8)
                sc = c + int(wu * 0.8)
                if 0 <= sr < rows and 0 <= sc < cols:
                    new_smoke[sr][sc] += smoke_prod * 0.4
    self.wfire_smoke = new_smoke

    # ── Moisture drying near fire ──
    for r in range(rows):
        for c in range(cols):
            if new_intensity[r][c] > 0.5:
                # Fire dries nearby cells
                for dr, dc, _ in neighbors:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        moisture[nr][nc] = max(0.0,
                            moisture[nr][nc] - 0.005 * new_intensity[r][c])

    # ── Firefighter actions ──
    for ff in self.wfire_fighters:
        if not ff.active:
            continue
        if ff.cooldown > 0:
            ff.cooldown -= 1
            continue

        # Move toward nearest fire front
        best_dist = 999999
        best_r, best_c = ff.r, ff.c
        search_rad = max(5, min(rows, cols) // 5)
        for dr in range(-search_rad, search_rad + 1):
            for dc in range(-search_rad, search_rad + 1):
                nr, nc = ff.r + dr, ff.c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if new_intensity[nr][nc] > 0.3:
                        d = abs(dr) + abs(dc)
                        if d < best_dist:
                            best_dist = d
                            best_r = nr
                            best_c = nc

        if best_dist < 999999:
            # Move 1-2 cells toward fire (but not into it)
            dr = 0
            dc = 0
            if best_r > ff.r:
                dr = 1
            elif best_r < ff.r:
                dr = -1
            if best_c > ff.c:
                dc = 1
            elif best_c < ff.c:
                dc = -1

            nr, nc = ff.r + dr, ff.c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if new_intensity[nr][nc] < 0.5:
                    ff.r = nr
                    ff.c = nc

            # Perform action
            if ff.type == 'break':
                # Cut firebreak ahead of fire
                for bdr in range(-1, 2):
                    for bdc in range(-1, 2):
                        br, bc = ff.r + bdr, ff.c + bdc
                        if 0 <= br < rows and 0 <= bc < cols:
                            if new_intensity[br][bc] <= 0.0 and not burned[br][bc]:
                                firebreak[br][bc] = True
                ff.cooldown = 2
            elif ff.type == 'water':
                # Drop water to suppress fire
                for bdr in range(-1, 2):
                    for bdc in range(-1, 2):
                        br, bc = ff.r + bdr, ff.c + bdc
                        if 0 <= br < rows and 0 <= bc < cols:
                            new_intensity[br][bc] = max(0.0,
                                new_intensity[br][bc] - 1.5)
                            moisture[br][bc] = min(1.0,
                                moisture[br][bc] + 0.3)
                ff.cooldown = 3

    # ── Statistics ──
    total_burned = sum(1 for r in range(rows) for c in range(cols)
                       if burned[r][c])
    burnable = sum(1 for r in range(rows) for c in range(cols)
                   if fuel[r][c] not in (FUEL_WATER, FUEL_ROCK))
    frac = total_burned / max(1, burnable)

    self.wfire_total_burned = total_burned
    self.wfire_active_cells = active
    self.wfire_crown_cells = crown_count
    self.wfire_ember_ignitions += ember_ign
    self.wfire_max_intensity = max_int
    self.wfire_area_fraction = frac

    self.wfire_history.append((self.wfire_generation, active, frac))
    if len(self.wfire_history) > 500:
        self.wfire_history = self.wfire_history[-500:]

    self.wfire_generation += 1

    # Auto-stop if fire is out
    if active == 0 and self.wfire_generation > 5:
        self.wfire_running = False


# ══════════════════════════════════════════════════════════════════════
#  Key handling
# ══════════════════════════════════════════════════════════════════════

def _handle_wfire_menu_key(self, key: int) -> bool:
    """Handle input in Wildfire preset menu."""
    presets = self.WFIRE_PRESETS
    if key == curses.KEY_DOWN or key == ord("j"):
        self.wfire_menu_sel = (self.wfire_menu_sel + 1) % len(presets)
    elif key == curses.KEY_UP or key == ord("k"):
        self.wfire_menu_sel = (self.wfire_menu_sel - 1) % len(presets)
    elif key in (10, 13, curses.KEY_ENTER):
        self._wfire_init(self.wfire_menu_sel)
    elif key == ord("q") or key == 27:
        self.wfire_menu = False
        self._flash("Wildfire mode cancelled")
    return True


def _handle_wfire_key(self, key: int) -> bool:
    """Handle input in active Wildfire simulation."""
    if key == ord("q") or key == 27:
        self._exit_wfire_mode()
        return True
    if key == ord(" "):
        self.wfire_running = not self.wfire_running
        return True
    if key == ord("n") or key == ord("."):
        self._wfire_step()
        return True
    if key == ord("r"):
        idx = next(
            (i for i, p in enumerate(self.WFIRE_PRESETS)
             if p[0] == self.wfire_preset_name), 0)
        self._wfire_init(idx)
        return True
    if key == ord("R") or key == ord("m"):
        self.wfire_mode = False
        self.wfire_running = False
        self.wfire_menu = True
        self.wfire_menu_sel = 0
        return True
    # Speed controls
    if key == ord("+") or key == ord("="):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.wfire_steps_per_frame) if self.wfire_steps_per_frame in choices else 0
        self.wfire_steps_per_frame = choices[min(idx + 1, len(choices) - 1)]
        self._flash(f"Speed: {self.wfire_steps_per_frame} steps/frame")
        return True
    if key == ord("-") or key == ord("_"):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.wfire_steps_per_frame) if self.wfire_steps_per_frame in choices else 0
        self.wfire_steps_per_frame = choices[max(idx - 1, 0)]
        self._flash(f"Speed: {self.wfire_steps_per_frame} steps/frame")
        return True
    # Wind direction
    if key == ord("w"):
        self.wfire_wind_dir += 0.2
        self._wfire_make_wind()
        self._flash(f"Wind dir: {math.degrees(self.wfire_wind_dir):.0f}°")
        return True
    if key == ord("W"):
        self.wfire_wind_dir -= 0.2
        self._wfire_make_wind()
        self._flash(f"Wind dir: {math.degrees(self.wfire_wind_dir):.0f}°")
        return True
    # Wind speed
    if key == ord("s"):
        self.wfire_wind_speed = max(0.0, self.wfire_wind_speed - 0.2)
        self._wfire_make_wind()
        self._flash(f"Wind speed: {self.wfire_wind_speed:.1f}")
        return True
    if key == ord("S"):
        self.wfire_wind_speed = min(5.0, self.wfire_wind_speed + 0.2)
        self._wfire_make_wind()
        self._flash(f"Wind speed: {self.wfire_wind_speed:.1f}")
        return True
    # View toggle
    if key == ord("v") or key == ord("V"):
        views = ["fire", "elevation", "fuel", "moisture"]
        idx = views.index(self.wfire_view) if self.wfire_view in views else 0
        self.wfire_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.wfire_view}")
        return True
    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing
# ══════════════════════════════════════════════════════════════════════

def _draw_wfire_menu(self, max_y: int, max_x: int):
    """Draw the Wildfire preset selection menu."""
    self.stdscr.erase()
    title = "── Wildfire Spread & Firefighting ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(self.WFIRE_PRESETS):
        y = 4 + i * 2
        if y >= max_y - 6:
            break
        marker = "▸ " if i == self.wfire_menu_sel else "  "
        attr = curses.color_pair(3) | curses.A_BOLD if i == self.wfire_menu_sel else curses.color_pair(7)
        line = f"{marker}{name}"
        try:
            self.stdscr.addstr(y, 3, line[:max_x - 4], attr)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    # Legend
    legend_y = max_y - 5
    if legend_y > 0:
        lines = [
            "Rothermel-inspired fire spread with slope, wind, fuel moisture & crown transitions.",
            "Ember spotting launches long-range ignitions; smoke plumes follow the wind field.",
            "Firefighters cut breaks and drop water to contain the blaze.",
        ]
        for i, line in enumerate(lines):
            try:
                self.stdscr.addstr(legend_y + i, 3, line[:max_x - 4],
                                   curses.color_pair(6))
            except curses.error:
                pass

    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [j/k]=navigate  [Enter]=select  [q/Esc]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_wfire(self, max_y: int, max_x: int):
    """Draw the active Wildfire simulation."""
    self.stdscr.erase()
    state = "▶ RUNNING" if self.wfire_running else "⏸ PAUSED"

    # Title bar
    title = (f" Wildfire: {self.wfire_preset_name}  |  t={self.wfire_generation}"
             f"  active={self.wfire_active_cells}"
             f"  burned={self.wfire_area_fraction:.1%}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view = self.wfire_view
    if view == "fire":
        _draw_wfire_field(self, max_y, max_x)
    elif view == "elevation":
        _draw_wfire_elevation(self, max_y, max_x)
    elif view == "fuel":
        _draw_wfire_fuel(self, max_y, max_x)
    elif view == "moisture":
        _draw_wfire_moisture(self, max_y, max_x)

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        wind_deg = math.degrees(self.wfire_wind_dir) % 360
        info = (f" wind={wind_deg:.0f}°/{self.wfire_wind_speed:.1f}"
                f"  crown={self.wfire_crown_cells}"
                f"  embers={self.wfire_ember_ignitions}"
                f"  burned={self.wfire_total_burned}"
                f"  maxI={self.wfire_max_intensity:.1f}"
                f"  fighters={len(self.wfire_fighters)}"
                f"  view={self.wfire_view}"
                f"  spf={self.wfire_steps_per_frame}")
        try:
            self.stdscr.addstr(info_y, 0, info[:max_x - 1],
                               curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [w/W]=wind dir [s/S]=wind spd [v]=view [+/-]=speed [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_wfire_field(self, max_y: int, max_x: int):
    """Draw the fire intensity / smoke view."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    intensity = self.wfire_intensity
    burned = self.wfire_burned
    crown = self.wfire_crown
    smoke = self.wfire_smoke
    fuel = self.wfire_fuel
    firebreak = self.wfire_firebreak
    fighters = self.wfire_fighters

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    fire_chars = " .,:;+=*#%@"

    for sy in range(min(disp_rows, rows)):
        r = sy * row_scale
        if r >= rows:
            break
        screen_y = 1 + sy
        if screen_y >= max_y - 2:
            break

        for sx in range(min(disp_cols, cols)):
            c = sx * col_scale
            if c >= cols:
                break
            if sx >= max_x - 1:
                break

            fi = intensity[r][c]
            sm = smoke[r][c]
            f = fuel[r][c]

            if firebreak[r][c]:
                ch = "░"
                attr = curses.color_pair(6) | curses.A_DIM
            elif fi > 3.0 and crown[r][c]:
                # Crown fire: bright white/yellow
                ch = "█"
                attr = curses.color_pair(3) | curses.A_BOLD
            elif fi > 2.0:
                # Intense fire: red
                ch = "█"
                attr = curses.color_pair(1) | curses.A_BOLD
            elif fi > 1.0:
                # Moderate fire: red/orange
                idx = min(10, int(fi * 3))
                ch = fire_chars[idx]
                attr = curses.color_pair(1)
            elif fi > 0.3:
                # Low fire: yellow
                idx = min(10, int(fi * 4))
                ch = fire_chars[idx]
                attr = curses.color_pair(3)
            elif fi > 0.0:
                # Smoldering
                ch = "."
                attr = curses.color_pair(3) | curses.A_DIM
            elif burned[r][c]:
                # Burned out
                ch = "·"
                attr = curses.color_pair(6) | curses.A_DIM
            elif sm > 0.5:
                # Dense smoke
                ch = "░"
                attr = curses.color_pair(7) | curses.A_DIM
            elif sm > 0.2:
                # Light smoke
                ch = "."
                attr = curses.color_pair(7) | curses.A_DIM
            elif f == FUEL_WATER:
                ch = "~"
                attr = curses.color_pair(4)
            elif f == FUEL_ROCK:
                ch = "^"
                attr = curses.color_pair(7) | curses.A_DIM
            elif f == FUEL_URBAN:
                ch = "▪"
                attr = curses.color_pair(7)
            elif f == FUEL_TIMBER:
                ch = "♣"
                attr = curses.color_pair(2)
            elif f == FUEL_SHRUB:
                ch = "♠"
                attr = curses.color_pair(2) | curses.A_DIM
            else:
                # Grass
                ch = "·"
                attr = curses.color_pair(2)

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass

    # Draw firefighters
    for ff in fighters:
        if not ff.active:
            continue
        fy = 1 + ff.r // max(1, row_scale)
        fx = ff.c // max(1, col_scale)
        if 1 <= fy < max_y - 2 and 0 <= fx < max_x - 1:
            ch = "◆" if ff.type == 'water' else "◇"
            attr = curses.color_pair(4) | curses.A_BOLD
            try:
                self.stdscr.addstr(fy, fx, ch, attr)
            except curses.error:
                pass


def _draw_wfire_elevation(self, max_y: int, max_x: int):
    """Draw elevation heatmap view."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    elev = self.wfire_elevation
    max_elev = self.wfire_max_elevation * 1.5

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    elev_chars = " .:-=+*#%@█"

    for sy in range(min(disp_rows, rows)):
        r = sy * row_scale
        if r >= rows:
            break
        screen_y = 1 + sy
        if screen_y >= max_y - 2:
            break

        for sx in range(min(disp_cols, cols)):
            c = sx * col_scale
            if c >= cols or sx >= max_x - 1:
                break

            h = elev[r][c]
            ratio = min(1.0, h / max(0.01, max_elev))
            idx = min(10, int(ratio * 10))
            ch = elev_chars[idx]

            if ratio > 0.7:
                attr = curses.color_pair(7) | curses.A_BOLD
            elif ratio > 0.4:
                attr = curses.color_pair(3)
            else:
                attr = curses.color_pair(2)

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass


def _draw_wfire_fuel(self, max_y: int, max_x: int):
    """Draw fuel type map view."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    fuel = self.wfire_fuel

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    for sy in range(min(disp_rows, rows)):
        r = sy * row_scale
        if r >= rows:
            break
        screen_y = 1 + sy
        if screen_y >= max_y - 2:
            break

        for sx in range(min(disp_cols, cols)):
            c = sx * col_scale
            if c >= cols or sx >= max_x - 1:
                break

            f = fuel[r][c]
            if f == FUEL_GRASS:
                ch, attr = "·", curses.color_pair(2)
            elif f == FUEL_SHRUB:
                ch, attr = "♠", curses.color_pair(2) | curses.A_BOLD
            elif f == FUEL_TIMBER:
                ch, attr = "♣", curses.color_pair(2) | curses.A_BOLD
            elif f == FUEL_URBAN:
                ch, attr = "▪", curses.color_pair(7) | curses.A_BOLD
            elif f == FUEL_WATER:
                ch, attr = "~", curses.color_pair(4)
            else:
                ch, attr = "^", curses.color_pair(7) | curses.A_DIM

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass


def _draw_wfire_moisture(self, max_y: int, max_x: int):
    """Draw fuel moisture content view."""
    rows = self.wfire_rows
    cols = self.wfire_cols
    moisture = self.wfire_moisture

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    moist_chars = " .:-=+*#%@"

    for sy in range(min(disp_rows, rows)):
        r = sy * row_scale
        if r >= rows:
            break
        screen_y = 1 + sy
        if screen_y >= max_y - 2:
            break

        for sx in range(min(disp_cols, cols)):
            c = sx * col_scale
            if c >= cols or sx >= max_x - 1:
                break

            m = moisture[r][c]
            idx = min(9, int(m * 9))
            ch = moist_chars[idx]

            if m > 0.6:
                attr = curses.color_pair(4) | curses.A_BOLD
            elif m > 0.3:
                attr = curses.color_pair(4)
            elif m > 0.1:
                attr = curses.color_pair(6)
            else:
                attr = curses.color_pair(1) | curses.A_DIM

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register wildfire mode methods on the App class."""
    App.WFIRE_PRESETS = WFIRE_PRESETS
    App._enter_wfire_mode = _enter_wfire_mode
    App._exit_wfire_mode = _exit_wfire_mode
    App._wfire_init = _wfire_init
    App._wfire_make_terrain = _wfire_make_terrain
    App._wfire_make_fire_state = _wfire_make_fire_state
    App._wfire_make_wind = _wfire_make_wind
    App._wfire_make_firefighters = _wfire_make_firefighters
    App._wfire_ignite = _wfire_ignite
    App._wfire_step = _wfire_step
    App._handle_wfire_menu_key = _handle_wfire_menu_key
    App._handle_wfire_key = _handle_wfire_key
    App._draw_wfire_menu = _draw_wfire_menu
    App._draw_wfire = _draw_wfire
    App._draw_wfire_field = _draw_wfire_field
    App._draw_wfire_elevation = _draw_wfire_elevation
    App._draw_wfire_fuel = _draw_wfire_fuel
    App._draw_wfire_moisture = _draw_wfire_moisture
