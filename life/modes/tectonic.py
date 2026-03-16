"""Mode: tectonic — Plate Tectonics & Mantle Convection.

Simulates a 2D cross-section/map view of Earth's lithosphere and asthenosphere:
- Mantle convection cells (Rayleigh-Benard thermal plumes driving plate motion)
- Rigid tectonic plates that drift, collide, and subduct
- Divergent boundaries with mid-ocean ridge spreading and new crust formation
- Convergent boundaries with subduction zones, volcanic arcs, deep trenches
- Continental collision producing mountain uplift (orogenesis)
- Transform faults with earthquake stress accumulation and sudden rupture
- Hotspot volcanism from deep mantle plumes (Hawaiian chain analog)
- Oceanic crust aging/cooling/densifying as it moves from ridges
- Wilson Cycle of supercontinent assembly and breakup

Three views:
  1) Tectonic map with plate boundaries, volcanoes, quake epicenters
  2) Mantle convection cross-section with temperature and flow vectors
  3) Time-series sparkline graphs for 10 metrics

Six presets:
  Stable Craton, Mid-Ocean Ridge Spreading, Subduction Zone Cascade,
  Continental Collision Himalayas, Supercontinent Breakup Pangaea,
  Yellowstone Hotspot Plume
"""
import curses
import math
import random

# ======================================================================
#  Presets
# ======================================================================

TECTONIC_PRESETS = [
    ("Stable Craton",
     "Ancient continental shield — slow drift, minimal boundary activity, deep lithospheric roots",
     "craton"),
    ("Mid-Ocean Ridge Spreading",
     "Active divergent boundary — new oceanic crust forming, symmetric spreading, transform offsets",
     "ridge"),
    ("Subduction Zone Cascade",
     "Oceanic plate diving beneath continent — volcanic arc, deep trench, Benioff zone seismicity",
     "subduction"),
    ("Continental Collision Himalayas",
     "Two continental plates converging — massive orogenesis, no subduction, crustal thickening",
     "collision"),
    ("Supercontinent Breakup Pangaea",
     "Single supercontinent rifting apart — plume-driven breakup, new ocean basins forming",
     "pangaea"),
    ("Yellowstone Hotspot Plume",
     "Deep mantle plume beneath moving plate — chain of volcanic islands, hotspot track on crust",
     "hotspot"),
]

# ======================================================================
#  Physical constants
# ======================================================================

# Mantle convection
_MANTLE_TEMP_CORE = 1.0        # normalized core temperature
_MANTLE_TEMP_SURFACE = 0.1     # surface temperature
_MANTLE_DIFF = 0.06            # thermal diffusivity
_MANTLE_BUOYANCY = 0.12        # buoyancy coefficient (Rayleigh number proxy)
_MANTLE_VISC_DRAG = 0.03       # viscous drag on flow
_MANTLE_PLUME_THRESH = 0.75    # temperature threshold for plume detection

# Plate mechanics
_PLATE_DRAG_COEFF = 0.04       # mantle drag on plates
_RIDGE_PUSH = 0.02             # force from elevated ridge
_SLAB_PULL = 0.06              # force from subducting slab
_CRUST_AGE_RATE = 0.005        # aging rate per tick (density increase)
_OCEANIC_DENSITY_BASE = 0.3    # base density of new oceanic crust
_CONTINENTAL_DENSITY = 0.15    # continental crust density (buoyant)
_SUBDUCTION_ANGLE = 0.7        # slab dip angle factor
_TRENCH_DEPTH_RATE = 80.0      # depth increase at trench per convergence

# Boundary processes
_CONVERGENCE_THRESH = 0.08     # velocity threshold for convergent boundary
_DIVERGENCE_THRESH = -0.05     # velocity threshold for divergent boundary
_OROGEN_RATE = 120.0           # mountain uplift rate (m/tick)
_VOLCANIC_ARC_PROB = 0.025     # probability of new volcano at subduction zone
_RIDGE_MAGMA_ELEV = -1800.0    # elevation of new ridge crust
_TRANSFORM_STRESS_RATE = 0.02  # stress accumulation per tick at transform
_QUAKE_TRIGGER_STRESS = 0.8    # stress threshold for earthquake rupture
_QUAKE_STRESS_DROP = 0.6       # fraction of stress released

# Hotspot volcanism
_HOTSPOT_PROB = 0.008          # probability of new hotspot from plume
_HOTSPOT_ERUPT_RATE = 200.0    # elevation added per eruption
_HOTSPOT_SPREAD = 40.0         # lava spread to neighbors

# Erosion and isostasy
_EROSION_RATE = 0.025          # smoothing factor
_PEAK_EROSION = 15.0           # extra erosion for high peaks
_ISOSTATIC_REBOUND = 30.0      # rebound rate for deep trenches
_SEA_LEVEL = 0.0               # sea level elevation

# Wilson cycle
_WILSON_ATTRACT_DIST = 0.35    # distance fraction for continental attraction
_WILSON_REPEL_FORCE = 0.003    # thermal repulsion from plumes under supercontinents

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
_HISTORY_MAX = 300


# ======================================================================
#  Helpers
# ======================================================================

def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _wrap(v, n):
    return v % n


def _append_metric(hist, key, val):
    lst = hist[key]
    lst.append(val)
    if len(lst) > _HISTORY_MAX:
        del lst[0]


# ======================================================================
#  Enter / Exit
# ======================================================================

def _enter_tectonic_mode(self):
    """Enter Plate Tectonics mode — show preset menu."""
    self.tectonic_menu = True
    self.tectonic_menu_sel = 0
    self._flash("Plate Tectonics & Mantle Convection — select a scenario")


def _exit_tectonic_mode(self):
    """Exit Plate Tectonics mode."""
    self.tectonic_mode = False
    self.tectonic_menu = False
    self.tectonic_running = False
    for attr in list(vars(self)):
        if attr.startswith('tectonic_') and attr not in (
                'tectonic_mode', 'tectonic_menu', 'tectonic_running'):
            try:
                delattr(self, attr)
            except AttributeError:
                pass
    self._flash("Plate Tectonics mode OFF")


# ======================================================================
#  Initialization
# ======================================================================

def _tectonic_init(self, preset_idx: int):
    """Initialize plate tectonics simulation from preset."""
    preset = TECTONIC_PRESETS[preset_idx]
    self.tectonic_preset_name = preset[0]
    kind = preset[2]

    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(24, max_y - 4)
    cols = max(50, max_x - 2)
    self.tectonic_rows = rows
    self.tectonic_cols = cols

    # --- Mantle convection grid (same dims as surface) ---
    self.tectonic_mantle_temp = [[0.0] * cols for _ in range(rows)]
    self.tectonic_mantle_vr = [[0.0] * cols for _ in range(rows)]
    self.tectonic_mantle_vc = [[0.0] * cols for _ in range(rows)]

    # Initialize mantle: hot at bottom, cool at top
    for r in range(rows):
        frac = r / max(1, rows - 1)  # 0=top, 1=bottom
        base_t = _MANTLE_TEMP_SURFACE + (_MANTLE_TEMP_CORE - _MANTLE_TEMP_SURFACE) * frac
        for c in range(cols):
            self.tectonic_mantle_temp[r][c] = base_t + random.uniform(-0.05, 0.05)

    # --- Surface grids ---
    self.tectonic_elevation = [[-4000.0] * cols for _ in range(rows)]
    self.tectonic_plate_id = [[0] * cols for _ in range(rows)]
    self.tectonic_crust_type = [[0] * cols for _ in range(rows)]  # 0=oceanic, 1=continental
    self.tectonic_crust_age = [[0.0] * cols for _ in range(rows)]
    self.tectonic_stress = [[0.0] * cols for _ in range(rows)]  # transform fault stress

    # Events
    self.tectonic_volcanoes = []    # (r, c, intensity, age)
    self.tectonic_quakes = []       # (r, c, magnitude, age)
    self.tectonic_hotspots = []     # (r, c, plume_strength)
    self.tectonic_ridges = set()    # (r, c) divergent boundary cells
    self.tectonic_trenches = set()  # (r, c) convergent trench cells

    # State
    self.tectonic_generation = 0
    self.tectonic_age = 0
    self.tectonic_view = "tectonic"  # "tectonic", "mantle", "graphs"
    self.tectonic_speed_scale = 1.0
    self.tectonic_show_help = True
    self.tectonic_wilson_phase = "dispersed"  # "assembling" or "dispersed"

    # History for sparkline
    self.tectonic_history = {
        'plate_velocity': [], 'volcanic_activity': [], 'seismic_energy': [],
        'ocean_crust_pct': [], 'continental_pct': [], 'mean_elevation': [],
        'max_elevation': [], 'mantle_heat_flux': [], 'num_hotspots': [],
        'stress_level': [],
    }

    # --- Generate plates via Voronoi ---
    num_plates = _preset_plate_count(kind)
    self.tectonic_num_plates = num_plates
    seeds = _generate_seeds(kind, num_plates, rows, cols)

    # Voronoi assignment
    for r in range(rows):
        for c in range(cols):
            best = 0
            best_d = float('inf')
            for i, (sr, sc) in enumerate(seeds):
                dr = min(abs(r - sr), rows - abs(r - sr))
                dc = min(abs(c - sc), cols - abs(c - sc))
                d = dr * dr + dc * dc
                if d < best_d:
                    best_d = d
                    best = i
            self.tectonic_plate_id[r][c] = best

    # Build plates
    plate_names = ["Pacifica", "Laurasia", "Gondwana", "Tethys",
                   "Panthalassa", "Rodinia", "Baltica", "Avalonia"]
    self.tectonic_plates = []
    for i in range(num_plates):
        props = _preset_plate_props(kind, i, num_plates, seeds, rows, cols)
        self.tectonic_plates.append({
            "vr": props["vr"], "vc": props["vc"],
            "color": (i % 6) + 1,
            "name": plate_names[i % len(plate_names)],
            "continental": props["continental"],
            "seed_r": seeds[i][0], "seed_c": seeds[i][1],
            "accum_r": 0.0, "accum_c": 0.0,
            "density": _CONTINENTAL_DENSITY if props["continental"] else _OCEANIC_DENSITY_BASE,
        })

    # Set initial elevation and crust type
    for r in range(rows):
        for c in range(cols):
            pid = self.tectonic_plate_id[r][c]
            plate = self.tectonic_plates[pid]
            if plate["continental"]:
                self.tectonic_elevation[r][c] = random.uniform(200, 900)
                self.tectonic_crust_type[r][c] = 1
                self.tectonic_crust_age[r][c] = random.uniform(0.5, 1.0)
            else:
                self.tectonic_elevation[r][c] = random.uniform(-5000, -3000)
                self.tectonic_crust_type[r][c] = 0
                self.tectonic_crust_age[r][c] = random.uniform(0.0, 0.3)

    # Preset-specific hotspots
    if kind == "hotspot":
        # Place a deep mantle plume
        pr, pc = rows // 2, cols // 2
        self.tectonic_hotspots.append((pr, pc, 0.9))
        # Heat up mantle beneath
        for dr in range(-3, 4):
            for dc in range(-3, 4):
                rr = _wrap(pr + dr, rows)
                cc = _wrap(pc + dc, cols)
                dist = math.sqrt(dr * dr + dc * dc)
                if dist < 4:
                    self.tectonic_mantle_temp[rr][cc] = min(1.0,
                        self.tectonic_mantle_temp[rr][cc] + 0.3 * (1.0 - dist / 4.0))

    # Preset-specific mantle plumes for Pangaea breakup
    if kind == "pangaea":
        for _ in range(3):
            pr = rows // 2 + random.randint(-rows // 6, rows // 6)
            pc = cols // 2 + random.randint(-cols // 6, cols // 6)
            self.tectonic_hotspots.append((pr, pc, 0.7))
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    rr = _wrap(pr + dr, rows)
                    cc = _wrap(pc + dc, cols)
                    self.tectonic_mantle_temp[rr][cc] = min(1.0,
                        self.tectonic_mantle_temp[rr][cc] + 0.2)

    self.tectonic_menu = False
    self.tectonic_mode = True
    self.tectonic_running = True
    self._flash(f"Plate Tectonics: {self.tectonic_preset_name}")


def _preset_plate_count(kind):
    if kind == "craton":
        return 5
    elif kind == "ridge":
        return 6
    elif kind == "subduction":
        return 5
    elif kind == "collision":
        return 4
    elif kind == "pangaea":
        return 7
    elif kind == "hotspot":
        return 4
    return 6


def _generate_seeds(kind, num, rows, cols):
    seeds = []
    if kind == "pangaea":
        # Cluster in center for supercontinent
        for i in range(num):
            r = rows // 2 + random.randint(-rows // 5, rows // 5)
            c = cols // 2 + random.randint(-cols // 5, cols // 5)
            seeds.append((r % rows, c % cols))
    elif kind == "collision":
        # Two groups converging
        for i in range(2):
            seeds.append((rows // 2 + random.randint(-rows // 8, rows // 8),
                          cols // 4 + random.randint(-cols // 8, cols // 8)))
        for i in range(2):
            seeds.append((rows // 2 + random.randint(-rows // 8, rows // 8),
                          3 * cols // 4 + random.randint(-cols // 8, cols // 8)))
    elif kind == "subduction":
        # Oceanic plate + continental plate arrangement
        for i in range(num):
            seeds.append((random.randint(0, rows - 1), random.randint(0, cols - 1)))
    else:
        for i in range(num):
            seeds.append((random.randint(0, rows - 1), random.randint(0, cols - 1)))
    return seeds


def _preset_plate_props(kind, i, num, seeds, rows, cols):
    """Return dict with vr, vc, continental for a plate."""
    if kind == "craton":
        # Slow stable plates, mostly continental
        angle = 2 * math.pi * i / num
        speed = random.uniform(0.05, 0.15)
        return {"vr": math.sin(angle) * speed, "vc": math.cos(angle) * speed,
                "continental": i < 3}
    elif kind == "ridge":
        # Plates diverge from center ridges
        angle = 2 * math.pi * i / num
        speed = random.uniform(0.2, 0.4)
        return {"vr": math.sin(angle) * speed, "vc": math.cos(angle) * speed,
                "continental": i % 3 == 0}
    elif kind == "subduction":
        # One oceanic plate moves toward continental
        if i == 0:
            return {"vr": 0.0, "vc": 0.4, "continental": False}
        elif i == 1:
            return {"vr": 0.0, "vc": -0.1, "continental": True}
        else:
            return {"vr": random.uniform(-0.15, 0.15),
                    "vc": random.uniform(-0.15, 0.15),
                    "continental": random.random() < 0.4}
    elif kind == "collision":
        # Left plates move right, right move left
        if i < 2:
            return {"vr": random.uniform(-0.05, 0.05), "vc": 0.35,
                    "continental": True}
        else:
            return {"vr": random.uniform(-0.05, 0.05), "vc": -0.35,
                    "continental": True}
    elif kind == "pangaea":
        # Radiate outward from center (breakup)
        angle = 2 * math.pi * i / num
        speed = random.uniform(0.15, 0.35)
        return {"vr": math.sin(angle) * speed, "vc": math.cos(angle) * speed,
                "continental": i < 5}
    elif kind == "hotspot":
        # Plate moves over stationary hotspot
        if i == 0:
            return {"vr": -0.05, "vc": 0.3, "continental": False}
        else:
            return {"vr": random.uniform(-0.1, 0.1),
                    "vc": random.uniform(-0.1, 0.1),
                    "continental": i == 1}
    return {"vr": random.uniform(-0.3, 0.3), "vc": random.uniform(-0.3, 0.3),
            "continental": random.random() < 0.4}


# ======================================================================
#  Simulation Step
# ======================================================================

def _tectonic_step(self):
    """Advance plate tectonics simulation by one tick."""
    rows = self.tectonic_rows
    cols = self.tectonic_cols
    elev = self.tectonic_elevation
    pid_map = self.tectonic_plate_id
    plates = self.tectonic_plates
    mantle_t = self.tectonic_mantle_temp
    mantle_vr = self.tectonic_mantle_vr
    mantle_vc = self.tectonic_mantle_vc
    crust_age = self.tectonic_crust_age
    crust_type = self.tectonic_crust_type
    stress = self.tectonic_stress
    speed = self.tectonic_speed_scale

    self.tectonic_generation += 1
    self.tectonic_age += 1

    # ------ 1. Mantle convection update ------
    new_mt = [[0.0] * cols for _ in range(rows)]
    new_vr = [[0.0] * cols for _ in range(rows)]
    new_vc = [[0.0] * cols for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            # Thermal diffusion
            t_sum = 0.0
            for dr, dc in _NEIGHBORS_4:
                nr = _wrap(r + dr, rows)
                nc = _wrap(c + dc, cols)
                t_sum += mantle_t[nr][nc]
            t_avg = t_sum / 4.0
            new_t = mantle_t[r][c] + _MANTLE_DIFF * (t_avg - mantle_t[r][c])

            # Advection
            vr_here = mantle_vr[r][c]
            vc_here = mantle_vc[r][c]
            src_r = r - vr_here
            src_c = c - vc_here
            ir = int(src_r) % rows
            ic = int(src_c) % cols
            new_t = new_t * 0.7 + mantle_t[ir][ic] * 0.3

            # Bottom heating, top cooling
            frac = r / max(1, rows - 1)
            new_t += 0.005 * frac  # heat from below
            new_t -= 0.004 * (1.0 - frac)  # cool from above
            new_mt[r][c] = _clamp(new_t, 0.0, 1.0)

            # Buoyancy-driven flow (hot rises = negative vr, cold sinks)
            buoy = _MANTLE_BUOYANCY * (mantle_t[r][c] - 0.5)
            new_vr[r][c] = mantle_vr[r][c] * (1.0 - _MANTLE_VISC_DRAG) - buoy

            # Horizontal flow from pressure gradient (temperature gradient)
            if c > 0 and c < cols - 1:
                dt_dc = (mantle_t[r][(c + 1) % cols] - mantle_t[r][(c - 1) % cols]) * 0.5
            else:
                dt_dc = 0.0
            new_vc[r][c] = mantle_vc[r][c] * (1.0 - _MANTLE_VISC_DRAG) + dt_dc * 0.05

            # Clamp velocities
            new_vr[r][c] = _clamp(new_vr[r][c], -1.0, 1.0)
            new_vc[r][c] = _clamp(new_vc[r][c], -1.0, 1.0)

    self.tectonic_mantle_temp = new_mt
    self.tectonic_mantle_vr = new_vr
    self.tectonic_mantle_vc = new_vc

    # ------ 2. Plate motion from mantle drag + slab pull + ridge push ------
    for pi, plate in enumerate(plates):
        # Average mantle flow under this plate
        count = 0
        avg_vr = 0.0
        avg_vc = 0.0
        for r in range(0, rows, 3):
            for c in range(0, cols, 3):
                if pid_map[r][c] == pi:
                    avg_vr += new_vr[r][c]
                    avg_vc += new_vc[r][c]
                    count += 1
        if count > 0:
            avg_vr /= count
            avg_vc /= count

        # Mantle drag coupling
        plate["vr"] += _PLATE_DRAG_COEFF * avg_vr * speed
        plate["vc"] += _PLATE_DRAG_COEFF * avg_vc * speed

        # Slab pull: dense old oceanic crust at edges pulls plate
        # Ridge push: elevated ridges push plate away
        # (simplified: applied via velocity damping toward mantle flow)

        # Velocity damping
        plate["vr"] *= 0.995
        plate["vc"] *= 0.995

        # Clamp plate velocity
        max_v = 0.6
        plate["vr"] = _clamp(plate["vr"], -max_v, max_v)
        plate["vc"] = _clamp(plate["vc"], -max_v, max_v)

    # ------ 3. Move plates (shift grid cells) ------
    new_pid = [row[:] for row in pid_map]
    new_elev = [row[:] for row in elev]
    new_ctype = [row[:] for row in crust_type]
    new_cage = [row[:] for row in crust_age]

    for pi, plate in enumerate(plates):
        plate["accum_r"] += plate["vr"] * speed
        plate["accum_c"] += plate["vc"] * speed
        shift_r = int(plate["accum_r"])
        shift_c = int(plate["accum_c"])
        if shift_r == 0 and shift_c == 0:
            continue
        plate["accum_r"] -= shift_r
        plate["accum_c"] -= shift_c

        for r in range(rows):
            for c in range(cols):
                if pid_map[r][c] == pi:
                    nr = _wrap(r + shift_r, rows)
                    nc = _wrap(c + shift_c, cols)
                    new_pid[nr][nc] = pi
                    new_elev[nr][nc] = elev[r][c]
                    new_ctype[nr][nc] = crust_type[r][c]
                    new_cage[nr][nc] = crust_age[r][c]

    self.tectonic_plate_id = new_pid
    self.tectonic_elevation = new_elev
    self.tectonic_crust_type = new_ctype
    self.tectonic_crust_age = new_cage
    elev = new_elev
    pid_map = new_pid
    crust_type = new_ctype
    crust_age = new_cage

    # ------ 4. Boundary detection and geological processes ------
    new_volcanoes = []
    new_quakes = []
    new_ridges = set()
    new_trenches = set()
    total_seismic = 0.0

    for r in range(rows):
        for c in range(cols):
            my_pid = pid_map[r][c]
            my_plate = plates[my_pid]

            # Age crust
            crust_age[r][c] += _CRUST_AGE_RATE * speed
            # Oceanic crust cools and densifies
            if crust_type[r][c] == 0:
                age_density = _OCEANIC_DENSITY_BASE + crust_age[r][c] * 0.15
                # Slight subsidence from cooling
                if crust_age[r][c] > 0.5:
                    elev[r][c] -= 2.0 * speed

            # Check neighbors for plate boundaries
            for dr, dc in _NEIGHBORS_4:
                nr = _wrap(r + dr, rows)
                nc = _wrap(c + dc, cols)
                n_pid = pid_map[nr][nc]
                if n_pid == my_pid:
                    continue

                n_plate = plates[n_pid]
                # Relative velocity toward boundary
                rel_vr = my_plate["vr"] - n_plate["vr"]
                rel_vc = my_plate["vc"] - n_plate["vc"]
                convergence = rel_vr * dr + rel_vc * dc

                if convergence > _CONVERGENCE_THRESH:
                    # === CONVERGENT BOUNDARY ===
                    my_cont = my_plate["continental"] or crust_type[r][c] == 1
                    n_cont = n_plate["continental"] or crust_type[nr][nc] == 1

                    if my_cont and n_cont:
                        # Continental-continental collision → orogenesis
                        uplift = convergence * _OROGEN_RATE * speed
                        elev[r][c] = min(9000, elev[r][c] + uplift)
                        # Crustal thickening
                        if random.random() < 0.05 * convergence * speed:
                            new_quakes.append((r, c, convergence * 3.0, 0))
                            total_seismic += convergence * 3.0
                    elif my_cont:
                        # Oceanic subducts under continental → volcanic arc + trench
                        elev[r][c] = min(6000, elev[r][c] + convergence * 50.0 * speed)
                        new_trenches.add((nr, nc))
                        elev[nr][nc] = max(-11000, elev[nr][nc] - _TRENCH_DEPTH_RATE * convergence * speed)
                        if random.random() < _VOLCANIC_ARC_PROB * convergence * speed:
                            arc_r = _wrap(r - dr * 2, rows)
                            arc_c = _wrap(c - dc * 2, cols)
                            new_volcanoes.append((arc_r, arc_c, convergence * 2.0, 0))
                        if random.random() < 0.03 * convergence * speed:
                            new_quakes.append((r, c, convergence * 4.0, 0))
                            total_seismic += convergence * 4.0
                        # Heat mantle from friction
                        self.tectonic_mantle_temp[nr][nc] = min(1.0,
                            self.tectonic_mantle_temp[nr][nc] + 0.01 * convergence)
                    else:
                        # Oceanic-oceanic → trench + island arc
                        new_trenches.add((r, c))
                        elev[r][c] = max(-11000, elev[r][c] - _TRENCH_DEPTH_RATE * convergence * speed)
                        if random.random() < 0.015 * convergence * speed:
                            arc_r = _wrap(r - dr * 2, rows)
                            arc_c = _wrap(c - dc * 2, cols)
                            new_volcanoes.append((arc_r, arc_c, convergence * 1.5, 0))
                            elev[arc_r][arc_c] = min(3000, elev[arc_r][arc_c] + random.uniform(100, 400))
                        if random.random() < 0.02 * convergence * speed:
                            new_quakes.append((r, c, convergence * 2.5, 0))
                            total_seismic += convergence * 2.5

                elif convergence < _DIVERGENCE_THRESH:
                    # === DIVERGENT BOUNDARY (mid-ocean ridge / continental rift) ===
                    rift_rate = abs(convergence)
                    new_ridges.add((r, c))
                    if crust_type[r][c] == 1 and elev[r][c] > 0:
                        # Continental rift
                        elev[r][c] = max(-2000, elev[r][c] - rift_rate * 60.0 * speed)
                        if elev[r][c] < -500:
                            crust_type[r][c] = 0  # becomes oceanic
                            crust_age[r][c] = 0.0
                    else:
                        # Mid-ocean ridge: new young oceanic crust
                        elev[r][c] = _RIDGE_MAGMA_ELEV + random.uniform(-200, 200)
                        crust_type[r][c] = 0
                        crust_age[r][c] = 0.0
                    if random.random() < 0.02 * rift_rate * speed:
                        new_volcanoes.append((r, c, rift_rate, 0))

                else:
                    # === TRANSFORM BOUNDARY ===
                    # Stress accumulation
                    rel_tangent = abs(rel_vr * dc - rel_vc * dr)
                    stress[r][c] += _TRANSFORM_STRESS_RATE * rel_tangent * speed
                    if stress[r][c] > _QUAKE_TRIGGER_STRESS:
                        # Earthquake rupture!
                        mag = stress[r][c] * 2.0 + random.uniform(0, 1.5)
                        new_quakes.append((r, c, mag, 0))
                        total_seismic += mag
                        stress[r][c] *= (1.0 - _QUAKE_STRESS_DROP)
                        elev[r][c] += random.uniform(-50, 50) * speed

    self.tectonic_ridges = new_ridges
    self.tectonic_trenches = new_trenches

    # ------ 5. Hotspot volcanism ------
    new_hotspots = []
    for hr, hc, strength in self.tectonic_hotspots:
        # Hotspot is fixed in mantle frame — plate moves over it
        if self.tectonic_mantle_temp[hr][hc] > _MANTLE_PLUME_THRESH * 0.7:
            # Erupt
            elev[hr][hc] = min(5000, elev[hr][hc] + _HOTSPOT_ERUPT_RATE * strength * speed)
            for dr, dc in _NEIGHBORS_4:
                nr = _wrap(hr + dr, rows)
                nc = _wrap(hc + dc, cols)
                elev[nr][nc] += _HOTSPOT_SPREAD * strength * speed
            if random.random() < 0.15 * strength:
                new_volcanoes.append((hr, hc, strength * 2.0, 0))
            # Plume heats mantle
            self.tectonic_mantle_temp[hr][hc] = min(1.0,
                self.tectonic_mantle_temp[hr][hc] + 0.01)
            # Slowly weaken
            new_strength = strength * 0.9995
            if new_strength > 0.1:
                new_hotspots.append((hr, hc, new_strength))
        else:
            if strength > 0.1:
                new_hotspots.append((hr, hc, strength * 0.998))

    # Spawn new hotspots from mantle plumes
    if random.random() < _HOTSPOT_PROB * speed:
        # Find hottest mantle cell
        best_r, best_c, best_t = 0, 0, 0
        for _ in range(10):
            rr = random.randint(rows // 2, rows - 1)
            cc = random.randint(0, cols - 1)
            if self.tectonic_mantle_temp[rr][cc] > best_t:
                best_t = self.tectonic_mantle_temp[rr][cc]
                best_r, best_c = rr, cc
        if best_t > _MANTLE_PLUME_THRESH:
            new_hotspots.append((best_r, best_c, best_t * 0.8))

    self.tectonic_hotspots = new_hotspots

    # ------ 6. Existing volcano activity ------
    surviving_volc = []
    for vr, vc, intensity, age in self.tectonic_volcanoes:
        if age > 30 or intensity < 0.1:
            continue
        if random.random() < 0.85:
            elev[vr][vc] = min(6000, elev[vr][vc] + intensity * 30.0 * speed)
            for dr, dc in _NEIGHBORS_4:
                nr = _wrap(vr + dr, rows)
                nc = _wrap(vc + dc, cols)
                elev[nr][nc] += intensity * 8.0 * speed
            surviving_volc.append((vr, vc, intensity * 0.97, age + 1))
    for v in new_volcanoes:
        surviving_volc.append(v)
    self.tectonic_volcanoes = surviving_volc

    # ------ 7. Earthquake decay ------
    surviving_quakes = []
    for qr, qc, mag, age in self.tectonic_quakes:
        if age < 8:
            surviving_quakes.append((qr, qc, mag * 0.85, age + 1))
    for q in new_quakes:
        surviving_quakes.append(q)
    self.tectonic_quakes = surviving_quakes

    # ------ 8. Erosion & isostasy ------
    if self.tectonic_generation % 2 == 0:
        for r in range(rows):
            for c in range(cols):
                avg = 0.0
                for dr, dc in _NEIGHBORS_4:
                    nr = _wrap(r + dr, rows)
                    nc = _wrap(c + dc, cols)
                    avg += elev[nr][nc]
                avg /= 4.0
                elev[r][c] = elev[r][c] * (1.0 - _EROSION_RATE) + avg * _EROSION_RATE
                if elev[r][c] > 5000:
                    elev[r][c] -= _PEAK_EROSION * speed
                if elev[r][c] < -9000:
                    elev[r][c] += _ISOSTATIC_REBOUND * speed

    # ------ 9. Wilson cycle check ------
    # Count continental clustering
    cont_cells = []
    for r in range(0, rows, 4):
        for c in range(0, cols, 4):
            if crust_type[r][c] == 1:
                cont_cells.append((r, c))
    if len(cont_cells) > 5:
        # Check if continents are clustered (supercontinent) or dispersed
        cr_mean = sum(r for r, c in cont_cells) / len(cont_cells)
        cc_mean = sum(c for r, c in cont_cells) / len(cont_cells)
        variance = sum((r - cr_mean) ** 2 + (c - cc_mean) ** 2
                       for r, c in cont_cells) / len(cont_cells)
        max_var = (rows * rows + cols * cols) / 4.0
        dispersion = variance / max_var if max_var > 0 else 0
        if dispersion < 0.15:
            self.tectonic_wilson_phase = "assembling"
            # Supercontinent insulation → mantle heats up → breakup force
            for r, c in cont_cells:
                self.tectonic_mantle_temp[r][c] = min(1.0,
                    self.tectonic_mantle_temp[r][c] + _WILSON_REPEL_FORCE)
        else:
            self.tectonic_wilson_phase = "dispersed"

    # ------ 10. Update metrics history ------
    avg_vel = 0.0
    for plate in plates:
        avg_vel += math.sqrt(plate["vr"] ** 2 + plate["vc"] ** 2)
    avg_vel /= max(1, len(plates))

    total_cells = rows * cols
    ocean_cells = sum(1 for r in range(rows) for c in range(cols) if crust_type[r][c] == 0)
    cont_cells_count = total_cells - ocean_cells
    flat_elev = [elev[r][c] for r in range(rows) for c in range(cols)]
    mean_elev = sum(flat_elev) / len(flat_elev)
    max_elev = max(flat_elev)

    # Mantle heat flux (average temperature at surface row)
    heat_flux = sum(self.tectonic_mantle_temp[0][c] for c in range(cols)) / cols

    avg_stress = sum(stress[r][c] for r in range(rows) for c in range(cols)) / total_cells

    hist = self.tectonic_history
    _append_metric(hist, 'plate_velocity', avg_vel)
    _append_metric(hist, 'volcanic_activity', len(self.tectonic_volcanoes))
    _append_metric(hist, 'seismic_energy', total_seismic)
    _append_metric(hist, 'ocean_crust_pct', ocean_cells / total_cells * 100)
    _append_metric(hist, 'continental_pct', cont_cells_count / total_cells * 100)
    _append_metric(hist, 'mean_elevation', mean_elev)
    _append_metric(hist, 'max_elevation', max_elev)
    _append_metric(hist, 'mantle_heat_flux', heat_flux)
    _append_metric(hist, 'num_hotspots', len(self.tectonic_hotspots))
    _append_metric(hist, 'stress_level', avg_stress)


# ======================================================================
#  Elevation helpers
# ======================================================================

TECTONIC_ELEV_CHARS = " .\u00b7~-=\u2248:;+*#%\u2592\u2593\u2588\u25b2"
TECTONIC_ELEV_THRESHOLDS = [
    -8000, -5000, -3000, -1500, -500, -100, 0, 100, 300, 600,
    1200, 2000, 3000, 4500, 6000, 7500, 9000,
]


def _tectonic_elev_char(self, e):
    chars = TECTONIC_ELEV_CHARS
    thresholds = TECTONIC_ELEV_THRESHOLDS
    for i, t in enumerate(thresholds):
        if e < t:
            return chars[i]
    return chars[-1]


def _tectonic_elev_color(self, e):
    if e < -5000:
        return curses.color_pair(4)  # deep ocean (blue)
    elif e < -1500:
        return curses.color_pair(4) | curses.A_BOLD
    elif e < 0:
        return curses.color_pair(6)  # shallow/cyan
    elif e < 300:
        return curses.color_pair(3)  # lowland green
    elif e < 1200:
        return curses.color_pair(3) | curses.A_BOLD
    elif e < 3000:
        return curses.color_pair(4)  # mountains
    elif e < 6000:
        return curses.color_pair(7) | curses.A_BOLD
    else:
        return curses.color_pair(1) | curses.A_BOLD  # peaks


# ======================================================================
#  Key Handlers
# ======================================================================

def _handle_tectonic_menu_key(self, key):
    n = len(TECTONIC_PRESETS)
    if key == curses.KEY_DOWN or key == ord('j'):
        self.tectonic_menu_sel = (self.tectonic_menu_sel + 1) % n
    elif key == curses.KEY_UP or key == ord('k'):
        self.tectonic_menu_sel = (self.tectonic_menu_sel - 1) % n
    elif key in (10, 13, curses.KEY_ENTER):
        _tectonic_init(self, self.tectonic_menu_sel)
    elif key == 27:
        self.tectonic_menu = False
        self.tectonic_mode = False
        self._flash("Plate Tectonics cancelled")
    else:
        return True
    return True


def _handle_tectonic_key(self, key):
    if key == -1:
        return True
    if key == ord(' '):
        self.tectonic_running = not self.tectonic_running
        self._flash("Paused" if not self.tectonic_running else "Running")
    elif key == ord('v'):
        views = ["tectonic", "mantle", "graphs"]
        idx = views.index(self.tectonic_view)
        self.tectonic_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.tectonic_view}")
    elif key == ord('n'):
        _tectonic_step(self)
    elif key == ord('+') or key == ord('='):
        self.tectonic_speed_scale = min(5.0, self.tectonic_speed_scale + 0.25)
        self._flash(f"Speed: {self.tectonic_speed_scale:.1f}x")
    elif key == ord('-'):
        self.tectonic_speed_scale = max(0.25, self.tectonic_speed_scale - 0.25)
        self._flash(f"Speed: {self.tectonic_speed_scale:.1f}x")
    elif key == ord('p'):
        self.tectonic_show_plates = not getattr(self, 'tectonic_show_plates', False)
        self._flash("Plate coloring: " + ("ON" if self.tectonic_show_plates else "OFF"))
    elif key == ord('?'):
        self.tectonic_show_help = not self.tectonic_show_help
    elif key == ord('r'):
        _tectonic_init(self, self.tectonic_menu_sel)
    elif key == ord('m'):
        self.tectonic_menu = True
        self.tectonic_menu_sel = 0
        self.tectonic_running = False
    elif key == 27:
        _exit_tectonic_mode(self)
    else:
        return True
    return True


# ======================================================================
#  Drawing — Preset Menu
# ======================================================================

def _draw_tectonic_menu(self, max_y, max_x):
    self.stdscr.erase()
    title = "\u2550\u2550\u2550 Plate Tectonics & Mantle Convection \u2550\u2550\u2550"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD | curses.color_pair(4))
        self.stdscr.addstr(3, 2, "Select a tectonic scenario:",
                           curses.color_pair(3))
        for i, (name, desc, _) in enumerate(TECTONIC_PRESETS):
            y = 5 + i * 2
            if y >= max_y - 2:
                break
            marker = "\u25b8 " if i == self.tectonic_menu_sel else "  "
            attr = curses.A_BOLD | curses.color_pair(4) if i == self.tectonic_menu_sel else curses.color_pair(3)
            self.stdscr.addstr(y, 3, f"{marker}{name}", attr)
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8], curses.A_DIM)
        foot_y = min(5 + len(TECTONIC_PRESETS) * 2 + 1, max_y - 2)
        self.stdscr.addstr(foot_y, 3, "Enter=Select  Esc=Cancel",
                           curses.A_DIM | curses.color_pair(6))
    except curses.error:
        pass


# ======================================================================
#  Drawing — View Dispatch
# ======================================================================

def _draw_tectonic(self, max_y, max_x):
    if self.tectonic_view == "tectonic":
        _draw_tectonic_map(self, max_y, max_x)
    elif self.tectonic_view == "mantle":
        _draw_mantle_view(self, max_y, max_x)
    elif self.tectonic_view == "graphs":
        _draw_graphs_view(self, max_y, max_x)


# ======================================================================
#  Drawing — Tectonic Map View
# ======================================================================

def _draw_tectonic_map(self, max_y, max_x):
    """Render tectonic map with plate boundaries, volcanoes, quake epicenters."""
    self.stdscr.erase()
    rows = self.tectonic_rows
    cols = self.tectonic_cols
    elev = self.tectonic_elevation
    pid_map = self.tectonic_plate_id
    plates = self.tectonic_plates
    show_plates = getattr(self, 'tectonic_show_plates', False)

    # Pre-build sets for overlay
    volc_set = {}
    for vr, vc, intensity, age in self.tectonic_volcanoes:
        volc_set[(vr, vc)] = intensity
    quake_set = {}
    for qr, qc, mag, age in self.tectonic_quakes:
        if age < 6:
            quake_set[(qr, qc)] = mag
    ridge_set = self.tectonic_ridges
    trench_set = self.tectonic_trenches
    hotspot_set = set((hr, hc) for hr, hc, _ in self.tectonic_hotspots)

    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, max_x - 1)

    for r in range(draw_rows):
        for c in range(draw_cols):
            e = elev[r][c]

            # Determine glyph and color
            if (r, c) in quake_set:
                mag = quake_set[(r, c)]
                ch = '*' if mag > 3.0 else '+'
                attr = curses.color_pair(1) | curses.A_BOLD  # red
            elif (r, c) in volc_set:
                ch = '^'
                attr = curses.color_pair(2) | curses.A_BOLD  # bright red/orange
            elif (r, c) in hotspot_set:
                ch = '@'
                attr = curses.color_pair(2) | curses.A_BOLD
            elif (r, c) in trench_set:
                ch = 'v'
                attr = curses.color_pair(5)  # magenta trench
            elif (r, c) in ridge_set:
                ch = '|' if random.random() < 0.5 else ':'
                attr = curses.color_pair(2)  # red ridge
            else:
                ch = _tectonic_elev_char(self, e)
                if show_plates:
                    pid = pid_map[r][c]
                    attr = curses.color_pair(plates[pid]["color"])
                else:
                    attr = _tectonic_elev_color(self, e)

            try:
                self.stdscr.addch(r, c, ord(ch[0]) if ch else ord(' '), attr)
            except curses.error:
                pass

    # Status bar
    status_y = min(draw_rows, max_y - 2)
    try:
        flat_elev = [elev[r][c] for r in range(rows) for c in range(cols)]
        min_e = min(flat_elev)
        max_e = max(flat_elev)
        total = rows * cols
        land_pct = sum(1 for e in flat_elev if e > 0) / total * 100

        status = (f" Age:{self.tectonic_age}MY "
                  f"Plates:{self.tectonic_num_plates} "
                  f"Land:{land_pct:.0f}% "
                  f"Elev:{min_e:.0f}..{max_e:.0f}m "
                  f"V:{len(self.tectonic_volcanoes)} "
                  f"Q:{len(self.tectonic_quakes)} "
                  f"H:{len(self.tectonic_hotspots)} "
                  f"Wilson:{self.tectonic_wilson_phase} "
                  f"Spd:{self.tectonic_speed_scale:.1f}x ")
        self.stdscr.addstr(status_y, 0, status[:max_x - 1],
                           curses.color_pair(0) | curses.A_REVERSE)
    except curses.error:
        pass

    # Legend
    try:
        legend = " ^volcano *quake @hotspot v:trench |ridge  [v]iew [p]lates [+/-]speed [?]help "
        self.stdscr.addstr(status_y + 1, 0, legend[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass

    # Help overlay
    if getattr(self, 'tectonic_show_help', False):
        help_lines = [
            "Controls:",
            " Space  Pause/Resume",
            " v      Cycle views",
            " +/-    Speed up/down",
            " p      Plate colors",
            " n      Single step",
            " r      Restart",
            " m      Preset menu",
            " ?      Toggle help",
            " Esc    Exit mode",
        ]
        hx = max(0, max_x - 22)
        hy = 1
        try:
            for i, line in enumerate(help_lines):
                if hy + i >= max_y - 3:
                    break
                self.stdscr.addstr(hy + i, hx, line[:22],
                                   curses.A_DIM | curses.color_pair(6))
        except curses.error:
            pass


# ======================================================================
#  Drawing — Mantle Convection Cross-Section
# ======================================================================

_MANTLE_HEAT_CHARS = " .\u00b7:;+=*#%@"
_FLOW_ARROWS = {
    (0, 1): '\u2192', (0, -1): '\u2190',
    (1, 0): '\u2193', (-1, 0): '\u2191',
    (1, 1): '\u2198', (1, -1): '\u2199',
    (-1, 1): '\u2197', (-1, -1): '\u2196',
    (0, 0): '\u00b7',
}


def _draw_mantle_view(self, max_y, max_x):
    """Render mantle convection cross-section with temperature and flow vectors."""
    self.stdscr.erase()
    rows = self.tectonic_rows
    cols = self.tectonic_cols
    mt = self.tectonic_mantle_temp
    mvr = self.tectonic_mantle_vr
    mvc = self.tectonic_mantle_vc

    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, max_x - 1)
    heat_chars = _MANTLE_HEAT_CHARS
    n_chars = len(heat_chars) - 1

    for r in range(draw_rows):
        for c in range(draw_cols):
            t = mt[r][c]

            # Show flow arrow every 3 cells, temperature otherwise
            if r % 3 == 1 and c % 4 == 2:
                vr_val = mvr[r][c]
                vc_val = mvc[r][c]
                dr = 1 if vr_val > 0.02 else (-1 if vr_val < -0.02 else 0)
                dc = 1 if vc_val > 0.02 else (-1 if vc_val < -0.02 else 0)
                ch = _FLOW_ARROWS.get((dr, dc), '\u00b7')
                # Color by speed
                spd = math.sqrt(vr_val ** 2 + vc_val ** 2)
                if spd > 0.1:
                    attr = curses.color_pair(7) | curses.A_BOLD
                elif spd > 0.03:
                    attr = curses.color_pair(7)
                else:
                    attr = curses.color_pair(6)
            else:
                idx = int(t * n_chars)
                idx = _clamp(idx, 0, n_chars)
                ch = heat_chars[idx]
                # Color by temperature
                if t > 0.8:
                    attr = curses.color_pair(1) | curses.A_BOLD  # hot red
                elif t > 0.6:
                    attr = curses.color_pair(1)
                elif t > 0.4:
                    attr = curses.color_pair(3)  # yellow/warm
                elif t > 0.25:
                    attr = curses.color_pair(4)  # blue/cool
                else:
                    attr = curses.color_pair(4) | curses.A_BOLD  # cold

            try:
                self.stdscr.addstr(r, c, ch, attr)
            except curses.error:
                pass

    # Label
    status_y = min(draw_rows, max_y - 2)
    try:
        avg_t = sum(mt[r][c] for r in range(rows) for c in range(cols)) / (rows * cols)
        max_t = max(mt[r][c] for r in range(rows) for c in range(cols))
        status = (f" Mantle Cross-Section | Age:{self.tectonic_age}MY "
                  f"| Avg T:{avg_t:.3f} | Max T:{max_t:.3f} "
                  f"| Hotspots:{len(self.tectonic_hotspots)} "
                  f"| Arrows=flow vectors ")
        self.stdscr.addstr(status_y, 0, status[:max_x - 1],
                           curses.color_pair(0) | curses.A_REVERSE)
    except curses.error:
        pass
    try:
        legend = " Cold=blue  Warm=green  Hot=red  Arrows=convection flow  [v]iew [space]pause "
        self.stdscr.addstr(status_y + 1, 0, legend[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass


# ======================================================================
#  Drawing — Sparkline Graphs
# ======================================================================

def _draw_graphs_view(self, max_y, max_x):
    """Time-series sparkline graphs for tectonic metrics."""
    self.stdscr.erase()
    hist = self.tectonic_history
    graph_w = min(200, max_x - 30)

    title = (f"Plate Tectonics Metrics -- {self.tectonic_preset_name} | "
             f"tick {self.tectonic_generation}")
    try:
        self.stdscr.addstr(0, 2, title, curses.A_BOLD)
    except curses.error:
        pass

    labels = [
        ("Plate Velocity",    'plate_velocity',    7),
        ("Volcanic Activity", 'volcanic_activity',  1),
        ("Seismic Energy",    'seismic_energy',     1),
        ("Ocean Crust %",     'ocean_crust_pct',    4),
        ("Continental %",     'continental_pct',     3),
        ("Mean Elevation",    'mean_elevation',      6),
        ("Max Elevation",     'max_elevation',       7),
        ("Mantle Heat Flux",  'mantle_heat_flux',    1),
        ("Hotspot Count",     'num_hotspots',        2),
        ("Stress Level",      'stress_level',        5),
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

    status = "[v]iew [+/-]speed [space]pause [r]estart [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, status[:max_x - 3], curses.color_pair(7))
    except curses.error:
        pass


# ======================================================================
#  Registration
# ======================================================================

def register(App):
    """Register plate tectonics mode methods on the App class."""
    App.TECTONIC_PRESETS = TECTONIC_PRESETS
    App.TECTONIC_ELEV_CHARS = TECTONIC_ELEV_CHARS
    App.TECTONIC_ELEV_THRESHOLDS = TECTONIC_ELEV_THRESHOLDS
    App._enter_tectonic_mode = _enter_tectonic_mode
    App._exit_tectonic_mode = _exit_tectonic_mode
    App._tectonic_init = _tectonic_init
    App._tectonic_step = _tectonic_step
    App._tectonic_elev_char = _tectonic_elev_char
    App._tectonic_elev_color = _tectonic_elev_color
    App._handle_tectonic_menu_key = _handle_tectonic_menu_key
    App._handle_tectonic_key = _handle_tectonic_key
    App._draw_tectonic_menu = _draw_tectonic_menu
    App._draw_tectonic = _draw_tectonic
