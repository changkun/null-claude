"""Mode: hvent — Deep Sea Hydrothermal Vent Ecosystem.

Black smoker chimneys ejecting superheated mineral-rich fluid into frigid
deep-ocean water, with chemosynthetic bacteria forming the base of a food
web that includes tube worms, vent shrimp, crabs, and octopuses — all
without sunlight.

Emergent phenomena:
  - Chimney growth from mineral precipitation (iron sulfide, calcium sulfate)
  - Buoyancy-driven thermal plumes with temperature diffusion
  - Chemosynthetic microbe colonies metabolizing hydrogen sulfide
  - Symbiotic/grazing/predatory food-web dynamics
  - Tectonic vent activation/deactivation, fissure opening, chimney collapse
  - Ocean current drift affecting plume dispersion and larval transport
  - Bioluminescent creatures glowing in the abyss
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

HVENT_PRESETS = [
    ("Classic Black Smoker",
     "Tall iron-sulfide chimneys belching 350°C superheated fluid into 2°C water",
     "black_smoker"),
    ("White Smoker Garden",
     "Lower-temperature vents with barium/calcium/silicon deposits and lush fauna",
     "white_smoker"),
    ("Lost City (Alkaline Vents)",
     "Tall carbonate towers driven by serpentinization — warm, alkaline, hydrogen-rich",
     "lost_city"),
    ("Mid-Ocean Ridge",
     "Active spreading center with multiple vent fields and tectonic fissures",
     "mid_ocean_ridge"),
    ("Vent Field Colonization",
     "New vents emerge on bare basalt — watch pioneer species arrive via larval drift",
     "colonization"),
    ("Dying Vent Succession",
     "Waning hydrothermal activity — community collapse and ecological succession",
     "dying_vent"),
]


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

# Tile types
TILE_WATER = 0
TILE_BASALT = 1
TILE_CHIMNEY = 2
TILE_MINERAL = 3       # precipitated mineral deposits
TILE_FISSURE = 4       # active tectonic fissure
TILE_SEDIMENT = 5      # settled particulate

# Fauna types
FAUNA_MICROBE = 0      # chemosynthetic bacteria/archaea
FAUNA_TUBEWORM = 1     # giant tube worms (Riftia) with symbiotic bacteria
FAUNA_SHRIMP = 2       # vent shrimp (Rimicaris) — grazers
FAUNA_CRAB = 3         # vent crabs — scavengers/predators
FAUNA_OCTOPUS = 4      # deep-sea octopus — apex predator
FAUNA_MUSSEL = 5       # vent mussels — filter feeders

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NEIGHBORS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                (0, 1), (1, -1), (1, 0), (1, 1)]


# ══════════════════════════════════════════════════════════════════════
#  Fauna agent class
# ══════════════════════════════════════════════════════════════════════

class _VentCreature:
    __slots__ = ('r', 'c', 'kind', 'energy', 'age', 'biolum')

    def __init__(self, r, c, kind, energy=1.0):
        self.r = r
        self.c = c
        self.kind = kind
        self.energy = energy
        self.age = 0
        self.biolum = random.random() < 0.3  # some creatures bioluminesce


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_hvent_mode(self):
    """Enter the hydrothermal vent ecosystem mode (show preset menu)."""
    self.hvent_mode = True
    self.hvent_menu = True
    self.hvent_menu_sel = 0


def _exit_hvent_mode(self):
    """Exit hydrothermal vent mode."""
    self.hvent_mode = False
    self.hvent_menu = False
    self.hvent_running = False
    for attr in list(vars(self)):
        if attr.startswith('hvent_') and attr not in ('hvent_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _hvent_init(self, preset_idx: int):
    """Initialize vent simulation for the chosen preset."""
    name, desc, pid = HVENT_PRESETS[preset_idx]
    self.hvent_preset_name = name
    self.hvent_preset_id = pid
    self.hvent_preset_idx = preset_idx

    max_y, max_x = self.stdscr.getmaxyx()
    self.hvent_rows = max(20, max_y - 4)
    self.hvent_cols = max(40, max_x - 1)
    rows, cols = self.hvent_rows, self.hvent_cols

    self.hvent_generation = 0
    self.hvent_view = "ecosystem"   # ecosystem, thermal, chemistry
    self.hvent_running = False

    # Preset parameters
    if pid == "black_smoker":
        self.hvent_vent_temp = 350.0
        self.hvent_n_vents = 3
        self.hvent_chimney_growth_rate = 0.08
        self.hvent_mineral_type = "sulfide"
        self.hvent_tectonic_rate = 0.002
        self.hvent_current_strength = 0.3
        self.hvent_h2s_output = 1.0
        self.hvent_initial_fauna = 0.6
    elif pid == "white_smoker":
        self.hvent_vent_temp = 200.0
        self.hvent_n_vents = 5
        self.hvent_chimney_growth_rate = 0.04
        self.hvent_mineral_type = "baite"
        self.hvent_tectonic_rate = 0.001
        self.hvent_current_strength = 0.2
        self.hvent_h2s_output = 0.6
        self.hvent_initial_fauna = 0.8
    elif pid == "lost_city":
        self.hvent_vent_temp = 90.0
        self.hvent_n_vents = 4
        self.hvent_chimney_growth_rate = 0.03
        self.hvent_mineral_type = "carbonate"
        self.hvent_tectonic_rate = 0.0005
        self.hvent_current_strength = 0.15
        self.hvent_h2s_output = 0.3
        self.hvent_initial_fauna = 0.7
    elif pid == "mid_ocean_ridge":
        self.hvent_vent_temp = 300.0
        self.hvent_n_vents = 6
        self.hvent_chimney_growth_rate = 0.06
        self.hvent_mineral_type = "sulfide"
        self.hvent_tectonic_rate = 0.008
        self.hvent_current_strength = 0.4
        self.hvent_h2s_output = 0.9
        self.hvent_initial_fauna = 0.5
    elif pid == "colonization":
        self.hvent_vent_temp = 280.0
        self.hvent_n_vents = 2
        self.hvent_chimney_growth_rate = 0.07
        self.hvent_mineral_type = "sulfide"
        self.hvent_tectonic_rate = 0.004
        self.hvent_current_strength = 0.5
        self.hvent_h2s_output = 0.8
        self.hvent_initial_fauna = 0.05
    else:  # dying_vent
        self.hvent_vent_temp = 120.0
        self.hvent_n_vents = 4
        self.hvent_chimney_growth_rate = 0.01
        self.hvent_mineral_type = "sulfide"
        self.hvent_tectonic_rate = 0.0003
        self.hvent_current_strength = 0.2
        self.hvent_h2s_output = 0.2
        self.hvent_initial_fauna = 0.9

    # Build terrain
    _hvent_make_terrain(self)
    # Init thermal/chemical fields
    _hvent_make_fields(self)
    # Populate fauna
    _hvent_make_fauna(self)

    # Stats
    self.hvent_chimney_cells = 0
    self.hvent_mineral_cells = 0
    self.hvent_active_vents = 0
    self.hvent_total_fauna = 0
    _hvent_update_stats(self)

    self.hvent_menu = False
    self.hvent_mode = True


def _hvent_make_terrain(self):
    """Build the seabed terrain with basalt floor, vents, and initial chimneys."""
    rows, cols = self.hvent_rows, self.hvent_cols
    pid = self.hvent_preset_id

    # Tile grid
    self.hvent_tiles = [[TILE_WATER for _ in range(cols)] for _ in range(rows)]

    # Basalt floor at bottom ~20% of grid
    floor_start = int(rows * 0.78)
    for r in range(floor_start, rows):
        for c in range(cols):
            self.hvent_tiles[r][c] = TILE_BASALT

    # Irregular floor surface
    self.hvent_floor = [floor_start] * cols
    elevation = 0.0
    for c in range(cols):
        elevation += random.gauss(0, 0.4)
        elevation *= 0.95
        h = floor_start + int(elevation)
        h = max(int(rows * 0.65), min(rows - 2, h))
        self.hvent_floor[c] = h
        for r in range(h, rows):
            self.hvent_tiles[r][c] = TILE_BASALT

    # Place vent sites
    self.hvent_vents = []  # list of (col, active, temp_mult, age)
    n_vents = self.hvent_n_vents
    spacing = cols // (n_vents + 1)
    for i in range(n_vents):
        vc = spacing * (i + 1) + random.randint(-spacing // 4, spacing // 4)
        vc = max(2, min(cols - 3, vc))
        active = True
        if pid == "dying_vent":
            active = random.random() < 0.4
        elif pid == "colonization":
            active = True
        temp_mult = random.uniform(0.7, 1.3)
        self.hvent_vents.append([vc, active, temp_mult, 0])

        # Build initial chimney
        if pid != "colonization" or random.random() < 0.5:
            floor_r = self.hvent_floor[vc]
            if pid == "lost_city":
                chimney_h = random.randint(8, min(18, floor_r - 2))
            elif pid == "black_smoker":
                chimney_h = random.randint(5, min(14, floor_r - 2))
            else:
                chimney_h = random.randint(3, min(10, floor_r - 2))

            for dr in range(chimney_h):
                r = floor_r - 1 - dr
                if 0 <= r < rows:
                    self.hvent_tiles[r][vc] = TILE_CHIMNEY
                    # Wider base
                    if dr < chimney_h // 3:
                        for dc in [-1, 1]:
                            nc = vc + dc
                            if 0 <= nc < cols and self.hvent_tiles[r][nc] == TILE_WATER:
                                self.hvent_tiles[r][nc] = TILE_CHIMNEY

            # Fissure at base
            if active:
                fr = floor_r - 1
                if 0 <= fr < rows:
                    self.hvent_tiles[fr][vc] = TILE_FISSURE

    # Add sediment patches near floor
    for c in range(cols):
        fl = self.hvent_floor[c]
        if fl > 0 and self.hvent_tiles[fl - 1][c] == TILE_WATER:
            if random.random() < 0.15:
                self.hvent_tiles[fl - 1][c] = TILE_SEDIMENT


def _hvent_make_fields(self):
    """Initialize temperature, H2S concentration, and mineral saturation fields."""
    rows, cols = self.hvent_rows, self.hvent_cols
    ambient = 2.0  # deep ocean ~2°C

    self.hvent_temperature = [[ambient for _ in range(cols)] for _ in range(rows)]
    self.hvent_h2s = [[0.0 for _ in range(cols)] for _ in range(rows)]
    self.hvent_minerals_dissolved = [[0.0 for _ in range(cols)] for _ in range(rows)]

    # Current direction (angle in radians, 0 = right)
    self.hvent_current_angle = random.uniform(-0.3, 0.3)
    self.hvent_current_time = 0.0

    # Seed fields around active vents
    for vc, active, temp_mult, _age in self.hvent_vents:
        if not active:
            continue
        fl = self.hvent_floor[min(vc, cols - 1)]
        vent_temp = self.hvent_vent_temp * temp_mult
        for dr in range(-5, 1):
            for dc in range(-3, 4):
                r = fl + dr
                c = vc + dc
                if 0 <= r < rows and 0 <= c < cols:
                    dist = math.sqrt(dr * dr + dc * dc) + 0.1
                    self.hvent_temperature[r][c] = ambient + (vent_temp - ambient) / (1 + dist)
                    self.hvent_h2s[r][c] = self.hvent_h2s_output / (1 + dist * 0.5)


def _hvent_make_fauna(self):
    """Populate the vent ecosystem with creatures."""
    rows, cols = self.hvent_rows, self.hvent_cols
    self.hvent_fauna = []
    pid = self.hvent_preset_id
    fauna_density = self.hvent_initial_fauna

    for vc, active, _tm, _age in self.hvent_vents:
        if not active and pid != "dying_vent":
            continue
        fl = self.hvent_floor[min(vc, cols - 1)]

        # Microbe colonies near vents
        n_microbes = int(20 * fauna_density)
        for _ in range(n_microbes):
            r = fl - random.randint(1, 6)
            c = vc + random.randint(-4, 4)
            if 0 <= r < rows and 0 <= c < cols and self.hvent_tiles[r][c] == TILE_WATER:
                self.hvent_fauna.append(_VentCreature(r, c, FAUNA_MICROBE, random.uniform(0.5, 1.0)))

        # Tube worms on chimney surfaces
        n_worms = int(12 * fauna_density)
        for _ in range(n_worms):
            r = fl - random.randint(1, 10)
            c = vc + random.randint(-3, 3)
            if 0 <= r < rows and 0 <= c < cols:
                self.hvent_fauna.append(_VentCreature(r, c, FAUNA_TUBEWORM, random.uniform(0.6, 1.0)))

        # Mussels cluster near base
        n_mussels = int(8 * fauna_density)
        for _ in range(n_mussels):
            r = fl - random.randint(0, 3)
            c = vc + random.randint(-5, 5)
            if 0 <= r < rows and 0 <= c < cols:
                self.hvent_fauna.append(_VentCreature(r, c, FAUNA_MUSSEL, random.uniform(0.5, 0.9)))

        # Shrimp swarming around plumes
        n_shrimp = int(15 * fauna_density)
        for _ in range(n_shrimp):
            r = fl - random.randint(2, 12)
            c = vc + random.randint(-6, 6)
            if 0 <= r < rows and 0 <= c < cols:
                self.hvent_fauna.append(_VentCreature(r, c, FAUNA_SHRIMP, random.uniform(0.4, 0.8)))

        # Crabs on the seafloor
        n_crabs = int(5 * fauna_density)
        for _ in range(n_crabs):
            r = fl - random.randint(0, 2)
            c = vc + random.randint(-8, 8)
            if 0 <= r < rows and 0 <= c < cols:
                self.hvent_fauna.append(_VentCreature(r, c, FAUNA_CRAB, random.uniform(0.6, 1.0)))

        # Rare octopus — apex predator
        if random.random() < 0.3 * fauna_density:
            r = fl - random.randint(3, 10)
            c = vc + random.randint(-10, 10)
            if 0 <= r < rows and 0 <= c < cols:
                self.hvent_fauna.append(_VentCreature(r, c, FAUNA_OCTOPUS, 1.0))


def _hvent_update_stats(self):
    """Recount statistics."""
    rows, cols = self.hvent_rows, self.hvent_cols
    chimney = mineral = 0
    for r in range(rows):
        for c in range(cols):
            t = self.hvent_tiles[r][c]
            if t == TILE_CHIMNEY:
                chimney += 1
            elif t == TILE_MINERAL:
                mineral += 1
    self.hvent_chimney_cells = chimney
    self.hvent_mineral_cells = mineral
    self.hvent_active_vents = sum(1 for v in self.hvent_vents if v[1])
    self.hvent_total_fauna = len(self.hvent_fauna)


# ══════════════════════════════════════════════════════════════════════
#  Simulation step
# ══════════════════════════════════════════════════════════════════════

def _hvent_step(self):
    """Advance the hydrothermal vent simulation by one tick."""
    rows, cols = self.hvent_rows, self.hvent_cols
    tiles = self.hvent_tiles
    temp = self.hvent_temperature
    h2s = self.hvent_h2s
    minerals = self.hvent_minerals_dissolved
    gen = self.hvent_generation
    ambient_temp = 2.0

    # ── 1. Vent emission ──────────────────────────────────────────
    for vi, (vc, active, temp_mult, age) in enumerate(self.hvent_vents):
        self.hvent_vents[vi][3] = age + 1
        if not active:
            continue
        fl = self.hvent_floor[min(vc, cols - 1)]
        vent_temp = self.hvent_vent_temp * temp_mult

        # Find chimney top
        chimney_top = fl
        for r in range(fl - 1, -1, -1):
            if tiles[r][vc] in (TILE_CHIMNEY, TILE_FISSURE):
                chimney_top = r
            else:
                break

        # Emit heat and H2S from chimney top
        emit_r = max(0, chimney_top - 1)
        if 0 <= emit_r < rows and 0 <= vc < cols:
            temp[emit_r][vc] = min(temp[emit_r][vc] + vent_temp * 0.15, vent_temp)
            h2s[emit_r][vc] = min(h2s[emit_r][vc] + self.hvent_h2s_output * 0.3, 2.0)
            minerals[emit_r][vc] = min(minerals[emit_r][vc] + 0.15, 2.0)

        # Dying vent: gradually reduce temperature
        if self.hvent_preset_id == "dying_vent" and gen % 50 == 0:
            self.hvent_vents[vi][2] *= 0.97

    # ── 2. Thermal plume (buoyancy-driven rise + diffusion) ───────
    # Process from top to bottom so heat rises
    current_dx = math.cos(self.hvent_current_angle) * self.hvent_current_strength
    self.hvent_current_time += 0.02
    self.hvent_current_angle += math.sin(self.hvent_current_time * 0.3) * 0.005

    new_temp = [[ambient_temp for _ in range(cols)] for _ in range(rows)]
    new_h2s = [[0.0 for _ in range(cols)] for _ in range(rows)]
    new_minerals = [[0.0 for _ in range(cols)] for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            if tiles[r][c] != TILE_WATER:
                new_temp[r][c] = temp[r][c]
                new_h2s[r][c] = h2s[r][c]
                new_minerals[r][c] = minerals[r][c]
                continue

            t = temp[r][c]
            s = h2s[r][c]
            m = minerals[r][c]

            # Buoyancy: hot fluid rises
            buoyancy = max(0, (t - ambient_temp) * 0.06)

            # Diffuse to neighbors
            sum_t = t * 4.0
            sum_s = s * 4.0
            sum_m = m * 4.0
            count = 4.0
            for dr, dc in _NEIGHBORS_4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    wt = 1.0
                    if dr == -1:
                        wt += buoyancy  # heat rises more
                    # Current drift
                    if dc == (1 if current_dx > 0 else -1):
                        wt += abs(current_dx) * 0.3
                    sum_t += temp[nr][nc] * wt
                    sum_s += h2s[nr][nc] * wt
                    sum_m += minerals[nr][nc] * wt
                    count += wt
                else:
                    sum_t += ambient_temp
                    count += 1.0

            new_temp[r][c] = sum_t / count
            new_h2s[r][c] = max(0, sum_s / count * 0.985)   # H2S decays
            new_minerals[r][c] = max(0, sum_m / count * 0.99)  # minerals settle

    self.hvent_temperature = new_temp
    self.hvent_h2s = new_h2s
    self.hvent_minerals_dissolved = new_minerals
    temp = new_temp
    h2s = new_h2s
    minerals = new_minerals

    # ── 3. Mineral precipitation (chimney growth) ─────────────────
    for r in range(rows):
        for c in range(cols):
            if tiles[r][c] != TILE_WATER:
                continue
            # Precipitation where hot meets cold (high gradient + dissolved minerals)
            if minerals[r][c] > 0.3 and temp[r][c] > 20:
                # Check if adjacent to chimney or basalt
                adj_solid = False
                for dr, dc in _NEIGHBORS_4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if tiles[nr][nc] in (TILE_CHIMNEY, TILE_BASALT, TILE_MINERAL):
                            adj_solid = True
                            break
                if adj_solid and random.random() < self.hvent_chimney_growth_rate * minerals[r][c]:
                    tiles[r][c] = TILE_CHIMNEY if temp[r][c] > 50 else TILE_MINERAL
                    minerals[r][c] *= 0.3

    # Sediment settling
    for c in range(cols):
        fl = self.hvent_floor[c]
        r = fl - 1
        if 0 < r < rows and tiles[r][c] == TILE_WATER:
            if minerals[r][c] > 0.1 and random.random() < 0.005:
                tiles[r][c] = TILE_SEDIMENT

    # ── 4. Tectonic activity ──────────────────────────────────────
    if random.random() < self.hvent_tectonic_rate:
        event = random.choice(["new_fissure", "chimney_collapse", "vent_toggle"])
        if event == "new_fissure" and len(self.hvent_vents) < 10:
            nc = random.randint(3, cols - 4)
            fl = self.hvent_floor[nc]
            self.hvent_vents.append([nc, True, random.uniform(0.6, 1.0), 0])
            if 0 <= fl - 1 < rows:
                tiles[fl - 1][nc] = TILE_FISSURE
        elif event == "chimney_collapse":
            # Pick random chimney column and remove top portion
            chimney_cols = set()
            for vv in self.hvent_vents:
                chimney_cols.add(vv[0])
            if chimney_cols:
                cc = random.choice(list(chimney_cols))
                fl = self.hvent_floor[min(cc, cols - 1)]
                collapse_depth = random.randint(2, 5)
                for r in range(max(0, fl - 20), fl):
                    if tiles[r][cc] == TILE_CHIMNEY:
                        if random.random() < 0.5 and collapse_depth > 0:
                            tiles[r][cc] = TILE_WATER
                            collapse_depth -= 1
        elif event == "vent_toggle" and self.hvent_vents:
            vi = random.randint(0, len(self.hvent_vents) - 1)
            self.hvent_vents[vi][1] = not self.hvent_vents[vi][1]

    # ── 5. Fauna behavior ─────────────────────────────────────────
    new_fauna = []
    fauna_grid = {}  # (r,c) -> list of creatures for interaction
    for f in self.hvent_fauna:
        key = (f.r, f.c)
        if key not in fauna_grid:
            fauna_grid[key] = []
        fauna_grid[key].append(f)

    for f in self.hvent_fauna:
        f.age += 1
        r, c = f.r, f.c

        # Temperature damage
        if 0 <= r < rows and 0 <= c < cols:
            cell_temp = temp[r][c]
            if f.kind == FAUNA_TUBEWORM:
                # Tolerant up to ~80°C
                if cell_temp > 80:
                    f.energy -= (cell_temp - 80) * 0.005
            elif f.kind == FAUNA_MICROBE:
                # Thermophilic — thrive in heat
                if cell_temp > 120:
                    f.energy -= 0.01
                elif cell_temp > 30:
                    f.energy += 0.005
            else:
                # Most fauna damaged above ~40°C
                if cell_temp > 40:
                    f.energy -= (cell_temp - 40) * 0.008

        # ── Microbe behavior ──
        if f.kind == FAUNA_MICROBE:
            # Chemosynthesis: gain energy from H2S
            if 0 <= r < rows and 0 <= c < cols:
                h2s_here = h2s[r][c]
                f.energy += h2s_here * 0.08
                h2s[r][c] *= 0.95  # consume H2S
            f.energy -= 0.005  # basal metabolism
            # Reproduce
            if f.energy > 1.5 and random.random() < 0.1:
                nr, nc = r + random.choice([-1, 0, 1]), c + random.choice([-1, 0, 1])
                if 0 <= nr < rows and 0 <= nc < cols and tiles[nr][nc] == TILE_WATER:
                    new_fauna.append(_VentCreature(nr, nc, FAUNA_MICROBE, 0.5))
                    f.energy -= 0.5
            # Drift
            if random.random() < 0.3:
                f.r += random.choice([-1, 0, 1])
                f.c += random.choice([-1, 0, 1])

        # ── Tube worm behavior ──
        elif f.kind == FAUNA_TUBEWORM:
            # Symbiotic bacteria provide energy proportional to H2S
            if 0 <= r < rows and 0 <= c < cols:
                f.energy += h2s[r][c] * 0.12
                h2s[r][c] *= 0.97
            f.energy -= 0.008
            # Sessile — don't move, but slowly reproduce
            if f.energy > 1.8 and random.random() < 0.02:
                nr = r + random.choice([-1, 0, 1])
                nc = c + random.choice([-1, 0, 1])
                if 0 <= nr < rows and 0 <= nc < cols and tiles[nr][nc] == TILE_WATER:
                    new_fauna.append(_VentCreature(nr, nc, FAUNA_TUBEWORM, 0.5))
                    f.energy -= 0.6

        # ── Mussel behavior ──
        elif f.kind == FAUNA_MUSSEL:
            # Filter feed — gain from dissolved minerals and microbes
            if 0 <= r < rows and 0 <= c < cols:
                f.energy += minerals[r][c] * 0.05
                f.energy += h2s[r][c] * 0.04
            f.energy -= 0.006
            # Sessile, slow reproduction
            if f.energy > 1.6 and random.random() < 0.015:
                nr = r + random.choice([-1, 0, 1])
                nc = c + random.choice([-1, 0, 1])
                if 0 <= nr < rows and 0 <= nc < cols and tiles[nr][nc] == TILE_WATER:
                    new_fauna.append(_VentCreature(nr, nc, FAUNA_MUSSEL, 0.4))
                    f.energy -= 0.5

        # ── Shrimp behavior ──
        elif f.kind == FAUNA_SHRIMP:
            # Graze on microbes
            neighbors = fauna_grid.get((r, c), [])
            ate = False
            for other in neighbors:
                if other.kind == FAUNA_MICROBE and other.energy > 0:
                    f.energy += 0.15
                    other.energy -= 0.4
                    ate = True
                    break
            if not ate:
                # Also graze on biofilm (H2S as proxy)
                if 0 <= r < rows and 0 <= c < cols:
                    f.energy += h2s[r][c] * 0.03
            f.energy -= 0.01
            # Move toward H2S
            best_r, best_c = r, c
            best_h2s = -1
            for dr, dc in _NEIGHBORS_8:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and tiles[nr][nc] == TILE_WATER:
                    if h2s[nr][nc] > best_h2s:
                        best_h2s = h2s[nr][nc]
                        best_r, best_c = nr, nc
            if random.random() < 0.6:
                f.r, f.c = best_r, best_c
            else:
                f.r += random.choice([-1, 0, 1])
                f.c += random.choice([-1, 0, 1])
            # Reproduce
            if f.energy > 1.4 and random.random() < 0.04:
                new_fauna.append(_VentCreature(f.r, f.c, FAUNA_SHRIMP, 0.4))
                f.energy -= 0.5

        # ── Crab behavior ──
        elif f.kind == FAUNA_CRAB:
            # Scavenge / eat microbes, mussels, dead things
            neighbors = fauna_grid.get((r, c), [])
            ate = False
            for other in neighbors:
                if other.kind in (FAUNA_MICROBE, FAUNA_MUSSEL) and other.energy > 0:
                    f.energy += 0.2
                    other.energy -= 0.5
                    ate = True
                    break
            f.energy -= 0.012
            # Wander along seafloor
            fl_here = self.hvent_floor[min(max(0, c), cols - 1)]
            target_r = fl_here - random.randint(0, 3)
            if f.r < target_r:
                f.r += 1
            elif f.r > target_r:
                f.r -= 1
            f.c += random.choice([-1, 0, 0, 1])
            # Reproduce
            if f.energy > 1.6 and random.random() < 0.02:
                new_fauna.append(_VentCreature(f.r, f.c, FAUNA_CRAB, 0.5))
                f.energy -= 0.6

        # ── Octopus behavior ──
        elif f.kind == FAUNA_OCTOPUS:
            # Hunt crabs and shrimp
            ate = False
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    nr, nc = r + dr, c + dc
                    key2 = (nr, nc)
                    for other in fauna_grid.get(key2, []):
                        if other.kind in (FAUNA_CRAB, FAUNA_SHRIMP) and other.energy > 0:
                            f.energy += 0.35
                            other.energy = -1  # kill
                            ate = True
                            break
                    if ate:
                        break
                if ate:
                    break
            f.energy -= 0.015
            # Intelligent movement — toward prey
            if random.random() < 0.7:
                best_dir = (0, 0)
                best_val = -1
                for dr, dc in _NEIGHBORS_8:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and tiles[nr][nc] == TILE_WATER:
                        prey_count = sum(1 for ff in fauna_grid.get((nr, nc), [])
                                         if ff.kind in (FAUNA_CRAB, FAUNA_SHRIMP))
                        if prey_count > best_val:
                            best_val = prey_count
                            best_dir = (dr, dc)
                f.r += best_dir[0] if best_val > 0 else random.choice([-1, 0, 1])
                f.c += best_dir[1] if best_val > 0 else random.choice([-1, 0, 1])
            # Rare reproduction
            if f.energy > 2.0 and random.random() < 0.005:
                new_fauna.append(_VentCreature(f.r, f.c, FAUNA_OCTOPUS, 0.8))
                f.energy -= 1.0

        # Clamp position
        f.r = max(0, min(rows - 1, f.r))
        f.c = max(0, min(cols - 1, f.c))

        # Energy clamp
        f.energy = min(f.energy, 3.0)

    # Remove dead fauna, add newborn
    max_fauna = rows * cols // 4
    self.hvent_fauna = [f for f in self.hvent_fauna if f.energy > 0]
    self.hvent_fauna.extend(new_fauna)
    if len(self.hvent_fauna) > max_fauna:
        self.hvent_fauna.sort(key=lambda f: f.energy, reverse=True)
        self.hvent_fauna = self.hvent_fauna[:max_fauna]

    # ── 6. Larval transport (colonization preset) ─────────────────
    if self.hvent_preset_id == "colonization" and gen % 30 == 0:
        # Random larvae arrive from distant vent fields
        if random.random() < 0.15:
            kind = random.choice([FAUNA_MICROBE, FAUNA_TUBEWORM, FAUNA_SHRIMP,
                                  FAUNA_MUSSEL, FAUNA_CRAB])
            lc = random.randint(0, cols - 1)
            lr = random.randint(0, rows // 2)
            self.hvent_fauna.append(_VentCreature(lr, lc, kind, 0.5))

    self.hvent_generation += 1
    if gen % 10 == 0:
        _hvent_update_stats(self)


# ══════════════════════════════════════════════════════════════════════
#  Key handlers
# ══════════════════════════════════════════════════════════════════════

def _handle_hvent_menu_key(self, key):
    """Handle key input on the preset selection menu."""
    if key in (curses.KEY_UP, ord('k')):
        self.hvent_menu_sel = (self.hvent_menu_sel - 1) % len(HVENT_PRESETS)
    elif key in (curses.KEY_DOWN, ord('j')):
        self.hvent_menu_sel = (self.hvent_menu_sel + 1) % len(HVENT_PRESETS)
    elif key in (curses.KEY_ENTER, 10, 13):
        self._hvent_init(self.hvent_menu_sel)
    elif key in (ord('q'), 27):
        self._exit_hvent_mode()


def _handle_hvent_key(self, key):
    """Handle key input during simulation."""
    if key == ord(' '):
        self.hvent_running = not self.hvent_running
    elif key in (ord('n'), ord('.')):
        self._hvent_step()
    elif key == ord('v'):
        views = ["ecosystem", "thermal", "chemistry"]
        idx = views.index(self.hvent_view)
        self.hvent_view = views[(idx + 1) % len(views)]
    elif key == ord('+') or key == ord('='):
        if hasattr(self, 'speed_idx'):
            self.speed_idx = max(0, self.speed_idx - 1)
    elif key == ord('-'):
        if hasattr(self, 'speed_idx'):
            self.speed_idx = min(len(getattr(self, 'SPEEDS', [0.5])) - 1,
                                 self.speed_idx + 1)
    elif key == ord('r'):
        self._hvent_init(self.hvent_preset_idx)
    elif key in (ord('R'), ord('m')):
        self.hvent_running = False
        self.hvent_menu = True
        self.hvent_menu_sel = self.hvent_preset_idx
    elif key in (ord('q'), 27):
        self._exit_hvent_mode()


# ══════════════════════════════════════════════════════════════════════
#  Drawing — preset menu
# ══════════════════════════════════════════════════════════════════════

def _draw_hvent_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()
    title = " Deep Sea Hydrothermal Vent Ecosystem "
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    subtitle = " Select a vent scenario:"
    try:
        self.stdscr.addstr(2, 1, subtitle[:max_x - 2], curses.color_pair(7))
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(HVENT_PRESETS):
        y = 4 + i * 2
        if y >= max_y - 6:
            break

        marker = "▸ " if i == self.hvent_menu_sel else "  "
        attr = (curses.color_pair(6) | curses.A_BOLD
                if i == self.hvent_menu_sel
                else curses.color_pair(7))

        try:
            self.stdscr.addstr(y, 3, f"{marker}{name}"[:max_x - 4], attr)
        except curses.error:
            pass

        try:
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    hint_y = max_y - 3
    hints = [
        " [↑/↓] Navigate   [Enter] Select   [q/Esc] Back",
        " Chemosynthetic ecosystems in the deep ocean abyss",
    ]
    for i, h in enumerate(hints):
        hy = hint_y + i
        if 0 < hy < max_y:
            try:
                self.stdscr.addstr(hy, 2, h[:max_x - 4],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — simulation views
# ══════════════════════════════════════════════════════════════════════

def _draw_hvent(self, max_y: int, max_x: int):
    """Draw the active hydrothermal vent simulation."""
    self.stdscr.erase()
    state = "▶ RUNNING" if self.hvent_running else "⏸ PAUSED"

    title = (f" Hydrothermal Vent: {self.hvent_preset_name}  |  "
             f"t={self.hvent_generation}  "
             f"fauna={self.hvent_total_fauna}  "
             f"vents={self.hvent_active_vents}  "
             f"|  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view = self.hvent_view
    if view == "ecosystem":
        _draw_hvent_ecosystem(self, max_y, max_x)
    elif view == "thermal":
        _draw_hvent_thermal(self, max_y, max_x)
    elif view == "chemistry":
        _draw_hvent_chemistry(self, max_y, max_x)

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        info = (f" chimneys={self.hvent_chimney_cells}"
                f"  minerals={self.hvent_mineral_cells}"
                f"  active_vents={self.hvent_active_vents}"
                f"  fauna={self.hvent_total_fauna}"
                f"  view={self.hvent_view}")
        try:
            self.stdscr.addstr(info_y, 0, info[:max_x - 1],
                               curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if hasattr(self, 'message') and self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [v]=view [+/-]=speed [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_hvent_ecosystem(self, max_y: int, max_x: int):
    """Draw the main ecosystem view — terrain, plumes, and fauna."""
    rows = self.hvent_rows
    cols = self.hvent_cols
    tiles = self.hvent_tiles
    temp = self.hvent_temperature
    h2s = self.hvent_h2s

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    gen = self.hvent_generation

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

            t = tiles[r][c]
            cell_temp = temp[r][c] if r < rows and c < cols else 2.0
            cell_h2s = h2s[r][c] if r < rows and c < cols else 0.0

            if t == TILE_BASALT:
                ch = "█"
                attr = curses.color_pair(7) | curses.A_DIM  # dark rock
            elif t == TILE_CHIMNEY:
                ch = "▓"
                attr = curses.color_pair(3) | curses.A_BOLD  # yellow chimney
            elif t == TILE_FISSURE:
                # Glowing fissure — pulsing
                if (gen + c) % 3 == 0:
                    ch = "▓"
                else:
                    ch = "█"
                attr = curses.color_pair(1) | curses.A_BOLD  # red glow
            elif t == TILE_MINERAL:
                ch = "░"
                attr = curses.color_pair(3)  # mineral deposits
            elif t == TILE_SEDIMENT:
                ch = "·"
                attr = curses.color_pair(7) | curses.A_DIM
            else:  # WATER
                # Show thermal plume in water
                if cell_temp > 100:
                    ch = "░"
                    attr = curses.color_pair(1) | curses.A_BOLD  # hot plume
                elif cell_temp > 40:
                    ch = "·"
                    attr = curses.color_pair(1)  # warm water
                elif cell_temp > 15:
                    ch = "·"
                    attr = curses.color_pair(3) | curses.A_DIM  # slightly warm
                elif cell_h2s > 0.3:
                    ch = "~"
                    attr = curses.color_pair(2) | curses.A_DIM  # H2S-rich water
                elif cell_h2s > 0.1:
                    ch = "."
                    attr = curses.color_pair(4) | curses.A_DIM  # trace chemicals
                else:
                    ch = " "
                    attr = 0  # dark ocean

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass

    # Draw fauna on top
    for f in self.hvent_fauna:
        fy = 1 + f.r // max(1, row_scale)
        fx = f.c // max(1, col_scale)
        if 1 <= fy < max_y - 2 and 0 <= fx < max_x - 1:
            if f.kind == FAUNA_TUBEWORM:
                ch = "╿"
                attr = curses.color_pair(1) | curses.A_BOLD  # red tube worm
            elif f.kind == FAUNA_SHRIMP:
                ch = "°"
                attr = curses.color_pair(7)  # white shrimp
            elif f.kind == FAUNA_CRAB:
                ch = "♦"
                attr = curses.color_pair(3)  # yellow-orange crab
            elif f.kind == FAUNA_OCTOPUS:
                ch = "◎"
                attr = curses.color_pair(5) | curses.A_BOLD  # magenta octopus
            elif f.kind == FAUNA_MUSSEL:
                ch = "▪"
                attr = curses.color_pair(4)  # blue mussel
            elif f.kind == FAUNA_MICROBE:
                # Microbes shown as faint dots, bioluminescent ones glow
                if f.biolum and (gen + f.r + f.c) % 4 == 0:
                    ch = "*"
                    attr = curses.color_pair(6) | curses.A_BOLD  # cyan glow
                else:
                    ch = "·"
                    attr = curses.color_pair(2) | curses.A_DIM
            else:
                continue

            try:
                self.stdscr.addstr(fy, fx, ch, attr)
            except curses.error:
                pass


def _draw_hvent_thermal(self, max_y: int, max_x: int):
    """Draw temperature heatmap view."""
    rows = self.hvent_rows
    cols = self.hvent_cols
    temp = self.hvent_temperature
    tiles = self.hvent_tiles

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    heat_chars = " .·:;+=@#█"

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

            if tiles[r][c] in (TILE_BASALT, TILE_CHIMNEY, TILE_MINERAL):
                ch = "█"
                attr = curses.color_pair(7) | curses.A_DIM
            else:
                t = temp[r][c]
                if t > 200:
                    idx = 9
                    attr = curses.color_pair(1) | curses.A_BOLD  # very hot
                elif t > 100:
                    idx = min(9, 6 + int((t - 100) / 40))
                    attr = curses.color_pair(1)
                elif t > 30:
                    idx = min(6, 3 + int((t - 30) / 25))
                    attr = curses.color_pair(3)
                elif t > 10:
                    idx = min(3, 1 + int((t - 10) / 10))
                    attr = curses.color_pair(3) | curses.A_DIM
                else:
                    idx = 0
                    attr = 0
                ch = heat_chars[idx]

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass


def _draw_hvent_chemistry(self, max_y: int, max_x: int):
    """Draw H2S and mineral concentration view."""
    rows = self.hvent_rows
    cols = self.hvent_cols
    h2s = self.hvent_h2s
    minerals = self.hvent_minerals_dissolved
    tiles = self.hvent_tiles

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    chars = " .·:;+=#%@"

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

            if tiles[r][c] in (TILE_BASALT, TILE_CHIMNEY, TILE_MINERAL):
                ch = "█"
                attr = curses.color_pair(7) | curses.A_DIM
            else:
                s = h2s[r][c]
                m = minerals[r][c]

                if s > m:
                    idx = min(9, int(s * 8))
                    ch = chars[idx]
                    attr = curses.color_pair(2)  # green = H2S
                    if s > 0.5:
                        attr |= curses.A_BOLD
                elif m > 0.05:
                    idx = min(9, int(m * 8))
                    ch = chars[idx]
                    attr = curses.color_pair(3)  # yellow = minerals
                    if m > 0.5:
                        attr |= curses.A_BOLD
                else:
                    ch = " "
                    attr = 0

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register hydrothermal vent mode methods on the App class."""
    App.HVENT_PRESETS = HVENT_PRESETS
    App._enter_hvent_mode = _enter_hvent_mode
    App._exit_hvent_mode = _exit_hvent_mode
    App._hvent_init = _hvent_init
    App._hvent_make_terrain = _hvent_make_terrain
    App._hvent_make_fields = _hvent_make_fields
    App._hvent_make_fauna = _hvent_make_fauna
    App._hvent_update_stats = _hvent_update_stats
    App._hvent_step = _hvent_step
    App._handle_hvent_menu_key = _handle_hvent_menu_key
    App._handle_hvent_key = _handle_hvent_key
    App._draw_hvent_menu = _draw_hvent_menu
    App._draw_hvent = _draw_hvent
    App._draw_hvent_ecosystem = _draw_hvent_ecosystem
    App._draw_hvent_thermal = _draw_hvent_thermal
    App._draw_hvent_chemistry = _draw_hvent_chemistry
