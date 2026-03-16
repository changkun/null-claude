"""Mode: stellar — Stellar Lifecycle & Supernova Simulation.

Simulates stars from birth to death — gravitational collapse of gas clouds into
protostars, hydrogen fusion ignition, main sequence evolution, red giant expansion,
and (for massive stars) core-collapse supernova with shockwave propagation, heavy
element nucleosynthesis, and neutron star or black hole remnant formation.  Lighter
stars shed planetary nebulae and fade as white dwarfs.

Three visualization views:
  1. Star field — spatial view of a stellar nursery
  2. Hertzsprung-Russell diagram — live luminosity vs temperature plot
  3. Core cross-section — onion-layer fusion shells of a selected star
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

STELLAR_PRESETS = [
    ("Open Cluster Nursery",
     "Young stellar nursery — gas clouds collapse into protostars and ignite",
     "nursery"),
    ("Red Giant Graveyard",
     "Aging cluster of evolved stars swelling into red giants and shedding nebulae",
     "graveyard"),
    ("Supernova Chain Reaction",
     "Massive stars near end of life — supernovae trigger neighboring collapses",
     "chain"),
    ("Binary Star Mass Transfer",
     "Close binary pairs exchanging mass — accretion, nova eruptions and mergers",
     "binary"),
    ("Globular Cluster Evolution",
     "Ancient dense cluster with thousands of stars at various evolutionary stages",
     "globular"),
    ("Wolf-Rayet Wind Bubble",
     "Ultra-massive stars with fierce stellar winds carving bubbles before exploding",
     "wolfrayet"),
]


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

# Evolutionary stages
STAGE_GAS_CLOUD = 0
STAGE_PROTOSTAR = 1
STAGE_MAIN_SEQ  = 2
STAGE_SUBGIANT  = 3
STAGE_RED_GIANT  = 4
STAGE_SUPERGIANT = 5
STAGE_SUPERNOVA  = 6
STAGE_PLAN_NEB   = 7   # planetary nebula
STAGE_WHITE_DWARF = 8
STAGE_NEUTRON    = 9
STAGE_BLACK_HOLE = 10
STAGE_REMNANT_FADE = 11

STAGE_NAMES = {
    STAGE_GAS_CLOUD: "Gas Cloud",
    STAGE_PROTOSTAR: "Protostar",
    STAGE_MAIN_SEQ: "Main Sequence",
    STAGE_SUBGIANT: "Subgiant",
    STAGE_RED_GIANT: "Red Giant",
    STAGE_SUPERGIANT: "Supergiant",
    STAGE_SUPERNOVA: "Supernova!",
    STAGE_PLAN_NEB: "Planetary Nebula",
    STAGE_WHITE_DWARF: "White Dwarf",
    STAGE_NEUTRON: "Neutron Star",
    STAGE_BLACK_HOLE: "Black Hole",
    STAGE_REMNANT_FADE: "Remnant",
}

# Spectral classes (O B A F G K M) — hottest to coolest
SPECTRAL_CLASSES = ["O", "B", "A", "F", "G", "K", "M"]

# Fusion shell elements (innermost to outermost for massive stars)
FUSION_SHELLS = ["Fe", "Si", "O", "C", "He", "H"]

# View modes
VIEW_STAR_FIELD = "star_field"
VIEW_HR_DIAGRAM = "hr_diagram"
VIEW_CORE_SECTION = "core_section"
VIEWS = [VIEW_STAR_FIELD, VIEW_HR_DIAGRAM, VIEW_CORE_SECTION]


# ══════════════════════════════════════════════════════════════════════
#  Star agent
# ══════════════════════════════════════════════════════════════════════

class _Star:
    __slots__ = ("x", "y", "mass", "initial_mass", "radius", "luminosity",
                 "temperature", "stage", "age", "lifetime", "fuel",
                 "shell_layers", "spectral_class", "vx", "vy",
                 "supernova_timer", "supernova_radius", "companion",
                 "wind_strength", "nebula_radius", "selected",
                 "binary_partner", "mass_transfer_rate")

    def __init__(self, x, y, mass=1.0):
        self.x = x
        self.y = y
        self.mass = mass
        self.initial_mass = mass
        self.radius = mass ** 0.8       # rough radius scaling
        self.luminosity = mass ** 3.5   # main-sequence L-M relation
        self.temperature = 5778 * (mass ** 0.505)  # rough T scaling from M
        self.stage = STAGE_GAS_CLOUD
        self.age = 0.0
        # Main sequence lifetime ~ M^{-2.5} (in arbitrary time units)
        self.lifetime = max(50, 1000.0 / (mass ** 2.5)) if mass > 0.1 else 5000
        self.fuel = 1.0   # fraction of hydrogen remaining
        self.shell_layers = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # H, He, C, O, Si, Fe
        self.spectral_class = "G"
        self.vx = random.uniform(-0.02, 0.02)
        self.vy = random.uniform(-0.02, 0.02)
        self.supernova_timer = 0
        self.supernova_radius = 0.0
        self.companion = None
        self.wind_strength = 0.0
        self.nebula_radius = 0.0
        self.selected = False
        self.binary_partner = None
        self.mass_transfer_rate = 0.0


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_stellar_mode(self):
    self.stellar_mode = True
    self.stellar_menu = True
    self.stellar_menu_sel = 0


def _exit_stellar_mode(self):
    self.stellar_mode = False
    self.stellar_menu = False
    self.stellar_running = False
    for attr in list(vars(self)):
        if attr.startswith('stellar_') and attr != 'stellar_mode':
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _stellar_init(self, preset_idx: int):
    name, desc, preset_id = STELLAR_PRESETS[preset_idx]
    self.stellar_preset_name = name
    self.stellar_preset_id = preset_id
    self.stellar_preset_idx = preset_idx

    max_y, max_x = self.stdscr.getmaxyx()
    self.stellar_rows = max(20, max_y - 4)
    self.stellar_cols = max(40, max_x - 1)

    self.stellar_generation = 0
    self.stellar_view = VIEW_STAR_FIELD
    self.stellar_running = False
    self.stellar_selected_idx = 0
    self.stellar_supernova_count = 0
    self.stellar_total_stars_born = 0
    self.stellar_time_scale = 1.0

    # Gas cloud grid (density)
    self.stellar_gas = [[0.0] * self.stellar_cols for _ in range(self.stellar_rows)]

    # Shockwave list: (x, y, radius, strength, age)
    self.stellar_shockwaves = []

    # Preset-specific parameters
    if preset_id == "nursery":
        n_stars = min(60, self.stellar_rows * self.stellar_cols // 40)
        mass_range = (0.3, 8.0)
        gas_density = 0.6
        start_stage = STAGE_GAS_CLOUD
        binary_frac = 0.1
        wind_scale = 1.0
    elif preset_id == "graveyard":
        n_stars = min(40, self.stellar_rows * self.stellar_cols // 50)
        mass_range = (0.8, 5.0)
        gas_density = 0.15
        start_stage = STAGE_RED_GIANT
        binary_frac = 0.1
        wind_scale = 1.0
    elif preset_id == "chain":
        n_stars = min(50, self.stellar_rows * self.stellar_cols // 45)
        mass_range = (5.0, 40.0)
        gas_density = 0.4
        start_stage = STAGE_SUPERGIANT
        binary_frac = 0.05
        wind_scale = 1.0
    elif preset_id == "binary":
        n_stars = min(30, self.stellar_rows * self.stellar_cols // 60)
        mass_range = (1.0, 15.0)
        gas_density = 0.1
        start_stage = STAGE_MAIN_SEQ
        binary_frac = 0.8
        wind_scale = 1.0
    elif preset_id == "globular":
        n_stars = min(120, self.stellar_rows * self.stellar_cols // 20)
        mass_range = (0.2, 3.0)
        gas_density = 0.05
        start_stage = STAGE_MAIN_SEQ
        binary_frac = 0.15
        wind_scale = 1.0
    else:  # wolfrayet
        n_stars = min(25, self.stellar_rows * self.stellar_cols // 60)
        mass_range = (20.0, 80.0)
        gas_density = 0.3
        start_stage = STAGE_MAIN_SEQ
        binary_frac = 0.2
        wind_scale = 5.0

    # Generate gas clouds
    _stellar_make_gas(self, gas_density)

    # Create stars
    _stellar_make_stars(self, n_stars, mass_range, start_stage, binary_frac,
                        wind_scale)

    self.stellar_total_stars_born = len(self.stellar_stars)


def _stellar_make_gas(self, density):
    rows, cols = self.stellar_rows, self.stellar_cols
    gas = self.stellar_gas

    # Place gas cloud seeds
    n_clouds = random.randint(3, 8)
    for _ in range(n_clouds):
        cx = random.randint(0, cols - 1)
        cy = random.randint(0, rows - 1)
        cloud_r = random.randint(3, min(12, rows // 3))
        strength = random.uniform(0.4, 1.0) * density
        for r in range(max(0, cy - cloud_r), min(rows, cy + cloud_r)):
            for c in range(max(0, cx - cloud_r), min(cols, cx + cloud_r)):
                dist = math.hypot(r - cy, c - cx)
                if dist < cloud_r:
                    falloff = 1.0 - (dist / cloud_r)
                    gas[r][c] = min(1.0, gas[r][c] + strength * falloff * falloff)


def _stellar_make_stars(self, count, mass_range, start_stage, binary_frac,
                        wind_scale):
    rows, cols = self.stellar_rows, self.stellar_cols
    stars = []

    for i in range(count):
        x = random.uniform(2, cols - 3)
        y = random.uniform(2, rows - 3)

        # Power-law IMF (Salpeter-like): more low-mass stars
        alpha = random.random()
        mass = mass_range[0] + (mass_range[1] - mass_range[0]) * (alpha ** 2.35)
        mass = max(mass_range[0], min(mass_range[1], mass))

        s = _Star(x, y, mass)
        s.stage = start_stage
        s.wind_strength = wind_scale * (mass / 10.0)

        # If starting evolved, set age appropriately
        if start_stage == STAGE_RED_GIANT:
            s.age = s.lifetime * random.uniform(0.85, 0.98)
            s.fuel = random.uniform(0.02, 0.15)
            _update_star_properties(s)
        elif start_stage == STAGE_SUPERGIANT:
            s.age = s.lifetime * random.uniform(0.92, 0.99)
            s.fuel = random.uniform(0.01, 0.08)
            _update_star_properties(s)
        elif start_stage == STAGE_MAIN_SEQ:
            s.age = s.lifetime * random.uniform(0.0, 0.7)
            s.fuel = 1.0 - (s.age / s.lifetime) * 0.8
            _update_star_properties(s)
        elif start_stage == STAGE_GAS_CLOUD:
            s.age = 0
            s.fuel = 1.0

        stars.append(s)

    # Set up binaries
    available = list(range(len(stars)))
    random.shuffle(available)
    while len(available) >= 2 and random.random() < binary_frac:
        i1 = available.pop()
        i2 = available.pop()
        stars[i1].binary_partner = i2
        stars[i2].binary_partner = i1
        # Place close together
        mid_x = (stars[i1].x + stars[i2].x) / 2
        mid_y = (stars[i1].y + stars[i2].y) / 2
        stars[i1].x = mid_x - 1
        stars[i2].x = mid_x + 1
        stars[i1].y = mid_y
        stars[i2].y = mid_y

    self.stellar_stars = stars


def _update_star_properties(s):
    """Update a star's radius, luminosity, temperature, spectral class based on stage/mass."""
    m = s.mass

    if s.stage == STAGE_GAS_CLOUD:
        s.radius = m * 5.0
        s.luminosity = 0.001
        s.temperature = 100 + m * 50
    elif s.stage == STAGE_PROTOSTAR:
        s.radius = m * 3.0
        s.luminosity = m * 0.5
        s.temperature = 2000 + m * 500
    elif s.stage == STAGE_MAIN_SEQ:
        s.radius = m ** 0.8
        s.luminosity = m ** 3.5
        s.temperature = 5778 * (m ** 0.505)
    elif s.stage == STAGE_SUBGIANT:
        s.radius = m ** 0.8 * 2.5
        s.luminosity = m ** 3.5 * 2.0
        s.temperature = 5778 * (m ** 0.505) * 0.85
    elif s.stage == STAGE_RED_GIANT:
        s.radius = m ** 0.8 * 10.0
        s.luminosity = m ** 3.5 * 5.0
        s.temperature = max(3000, 5778 * (m ** 0.505) * 0.55)
    elif s.stage == STAGE_SUPERGIANT:
        s.radius = m ** 0.8 * 20.0
        s.luminosity = m ** 3.5 * 10.0
        s.temperature = max(3500, 5778 * (m ** 0.505) * 0.45)
    elif s.stage == STAGE_SUPERNOVA:
        s.radius = 1.0
        s.luminosity = 1e6 * m
        s.temperature = 30000
    elif s.stage == STAGE_PLAN_NEB:
        s.radius = 0.3
        s.luminosity = 0.1
        s.temperature = 50000
    elif s.stage == STAGE_WHITE_DWARF:
        s.radius = 0.01
        s.luminosity = 0.01
        s.temperature = max(5000, 30000 - s.age * 10)
    elif s.stage == STAGE_NEUTRON:
        s.radius = 0.001
        s.luminosity = 0.001
        s.temperature = 1e6
    elif s.stage == STAGE_BLACK_HOLE:
        s.radius = 0.0001
        s.luminosity = 0.0
        s.temperature = 0

    # Update spectral class from temperature
    if s.temperature > 30000:
        s.spectral_class = "O"
    elif s.temperature > 10000:
        s.spectral_class = "B"
    elif s.temperature > 7500:
        s.spectral_class = "A"
    elif s.temperature > 6000:
        s.spectral_class = "F"
    elif s.temperature > 5200:
        s.spectral_class = "G"
    elif s.temperature > 3700:
        s.spectral_class = "K"
    else:
        s.spectral_class = "M"

    # Update fusion shell layers based on stage and mass
    if s.stage <= STAGE_PROTOSTAR:
        s.shell_layers = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    elif s.stage == STAGE_MAIN_SEQ:
        burned = 1.0 - s.fuel
        s.shell_layers = [s.fuel, burned * 0.8, burned * 0.15,
                          burned * 0.04, burned * 0.01, 0.0]
    elif s.stage in (STAGE_SUBGIANT, STAGE_RED_GIANT):
        s.shell_layers = [max(0, s.fuel), 0.4, 0.2, 0.1, 0.02, 0.0]
    elif s.stage == STAGE_SUPERGIANT:
        if m > 8:
            s.shell_layers = [max(0, s.fuel * 0.3), 0.25, 0.2, 0.15, 0.1, 0.05]
        else:
            s.shell_layers = [max(0, s.fuel * 0.5), 0.3, 0.15, 0.05, 0.0, 0.0]
    elif s.stage == STAGE_SUPERNOVA:
        s.shell_layers = [0.0, 0.05, 0.1, 0.15, 0.2, 0.5]  # iron core collapse


# ══════════════════════════════════════════════════════════════════════
#  Simulation Step
# ══════════════════════════════════════════════════════════════════════

def _stellar_step(self):
    self.stellar_generation += 1
    stars = self.stellar_stars
    rows, cols = self.stellar_rows, self.stellar_cols
    dt = self.stellar_time_scale

    new_stars = []

    for s in stars:
        s.age += dt

        if s.stage == STAGE_GAS_CLOUD:
            # Gravitational collapse — check local gas density
            gy, gx = int(s.y), int(s.x)
            local_gas = 0.0
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    nr, nc = gy + dr, gx + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        local_gas += self.stellar_gas[nr][nc]
            # Also triggered by nearby shockwaves
            shock_boost = 0.0
            for sw in self.stellar_shockwaves:
                dist = math.hypot(s.x - sw[0], s.y - sw[1])
                if dist < sw[2] + 3 and dist > sw[2] - 3:
                    shock_boost += sw[3] * 0.5

            collapse_prob = (local_gas * 0.003 + shock_boost * 0.05) * dt
            if s.age > 20 or random.random() < collapse_prob:
                s.stage = STAGE_PROTOSTAR
                # Consume local gas
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        nr, nc = gy + dr, gx + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            self.stellar_gas[nr][nc] *= 0.3
                _update_star_properties(s)

        elif s.stage == STAGE_PROTOSTAR:
            # Accumulating mass, heating up
            if s.age > 30:
                s.stage = STAGE_MAIN_SEQ
                _update_star_properties(s)

        elif s.stage == STAGE_MAIN_SEQ:
            # Burn hydrogen
            burn_rate = (s.mass ** 2.5) * 0.001 * dt
            s.fuel = max(0, s.fuel - burn_rate)

            if s.fuel <= 0.1:
                s.stage = STAGE_SUBGIANT
                _update_star_properties(s)

        elif s.stage == STAGE_SUBGIANT:
            s.fuel = max(0, s.fuel - 0.005 * dt)
            if s.fuel <= 0.02:
                if s.mass > 8:
                    s.stage = STAGE_SUPERGIANT
                else:
                    s.stage = STAGE_RED_GIANT
                _update_star_properties(s)

        elif s.stage == STAGE_RED_GIANT:
            s.fuel = max(0, s.fuel - 0.003 * dt)
            # Expand radius gradually
            s.radius = min(s.mass * 15.0, s.radius + 0.05 * dt)

            if s.fuel <= 0:
                # Low-mass stars → planetary nebula → white dwarf
                s.stage = STAGE_PLAN_NEB
                s.nebula_radius = 1.0
                _update_star_properties(s)

        elif s.stage == STAGE_SUPERGIANT:
            s.fuel = max(0, s.fuel - 0.008 * dt)
            s.radius = min(s.mass * 25.0, s.radius + 0.1 * dt)

            # Stellar wind
            if s.wind_strength > 2.0:
                s.mass = max(s.mass * 0.5, s.mass - 0.01 * s.wind_strength * dt)

            if s.fuel <= 0:
                # Core collapse → supernova!
                s.stage = STAGE_SUPERNOVA
                s.supernova_timer = 0
                s.supernova_radius = 0.0
                self.stellar_supernova_count += 1
                # Create shockwave
                self.stellar_shockwaves.append(
                    [s.x, s.y, 0.0, min(1.0, s.initial_mass / 20.0), 0])
                _update_star_properties(s)

        elif s.stage == STAGE_SUPERNOVA:
            s.supernova_timer += 1
            s.supernova_radius += 1.5

            if s.supernova_timer > 15:
                # Determine remnant
                if s.initial_mass > 25:
                    s.stage = STAGE_BLACK_HOLE
                    s.mass = s.initial_mass * 0.3
                else:
                    s.stage = STAGE_NEUTRON
                    s.mass = 1.4  # Chandrasekhar-ish

                # Seed new gas from expelled material
                for dr in range(-5, 6):
                    for dc in range(-5, 6):
                        nr, nc = int(s.y) + dr, int(s.x) + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            dist = math.hypot(dr, dc)
                            if dist < 6:
                                self.stellar_gas[nr][nc] = min(
                                    1.0, self.stellar_gas[nr][nc] +
                                    0.3 * (1.0 - dist / 6.0))

                _update_star_properties(s)

        elif s.stage == STAGE_PLAN_NEB:
            s.nebula_radius += 0.3 * dt
            if s.nebula_radius > 8:
                s.stage = STAGE_WHITE_DWARF
                s.mass = min(1.4, s.mass * 0.6)
                # Seed gas
                for dr in range(-3, 4):
                    for dc in range(-3, 4):
                        nr, nc = int(s.y) + dr, int(s.x) + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            dist = math.hypot(dr, dc)
                            if dist < 4:
                                self.stellar_gas[nr][nc] = min(
                                    1.0, self.stellar_gas[nr][nc] + 0.15)
                _update_star_properties(s)

        elif s.stage in (STAGE_WHITE_DWARF, STAGE_NEUTRON, STAGE_BLACK_HOLE):
            # Slowly cool / fade
            if s.stage == STAGE_WHITE_DWARF:
                s.temperature = max(3000, s.temperature - 5 * dt)
                s.luminosity = max(0.001, s.luminosity - 0.0001 * dt)

        # Binary mass transfer
        if s.binary_partner is not None and 0 <= s.binary_partner < len(stars):
            partner = stars[s.binary_partner]
            if (s.stage in (STAGE_RED_GIANT, STAGE_SUPERGIANT) and
                    partner.stage in (STAGE_MAIN_SEQ, STAGE_WHITE_DWARF,
                                      STAGE_NEUTRON)):
                transfer = 0.005 * dt
                if s.mass > transfer * 2:
                    s.mass -= transfer
                    partner.mass += transfer
                    s.mass_transfer_rate = transfer

        # Drift
        s.x += s.vx * dt
        s.y += s.vy * dt
        s.x = max(1, min(cols - 2, s.x))
        s.y = max(1, min(rows - 2, s.y))

    # Update shockwaves
    new_shocks = []
    for sw in self.stellar_shockwaves:
        sw[2] += 1.2  # expand radius
        sw[3] *= 0.92  # decay strength
        sw[4] += 1     # age
        if sw[3] > 0.01 and sw[2] < max(rows, cols):
            new_shocks.append(sw)

            # Shockwave triggers new star formation in dense gas
            if random.random() < 0.02 * sw[3]:
                angle = random.uniform(0, 2 * math.pi)
                nx = sw[0] + math.cos(angle) * sw[2]
                ny = sw[1] + math.sin(angle) * sw[2]
                if 1 < nx < cols - 2 and 1 < ny < rows - 2:
                    gy, gx = int(ny), int(nx)
                    if self.stellar_gas[gy][gx] > 0.3:
                        new_mass = random.uniform(0.5, 15.0)
                        ns = _Star(nx, ny, new_mass)
                        ns.stage = STAGE_GAS_CLOUD
                        new_stars.append(ns)
                        self.stellar_total_stars_born += 1

    self.stellar_shockwaves = new_shocks

    # Add newly born stars
    if new_stars:
        self.stellar_stars.extend(new_stars)

    # Diffuse gas slightly
    if self.stellar_generation % 5 == 0:
        gas = self.stellar_gas
        new_gas = [[0.0] * cols for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                total = gas[r][c] * 0.92
                cnt = 0.92
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        total += gas[nr][nc] * 0.02
                        cnt += 0.02
                new_gas[r][c] = min(1.0, total)
        self.stellar_gas = new_gas

    # Ensure selected index is valid
    if self.stellar_stars:
        self.stellar_selected_idx = self.stellar_selected_idx % len(self.stellar_stars)


# ══════════════════════════════════════════════════════════════════════
#  Input Handling
# ══════════════════════════════════════════════════════════════════════

def _handle_stellar_menu_key(self, key):
    if key == curses.KEY_DOWN or key == ord('j'):
        self.stellar_menu_sel = (self.stellar_menu_sel + 1) % len(STELLAR_PRESETS)
    elif key == curses.KEY_UP or key == ord('k'):
        self.stellar_menu_sel = (self.stellar_menu_sel - 1) % len(STELLAR_PRESETS)
    elif key in (ord('\n'), ord(' ')):
        self.stellar_menu = False
        _stellar_init(self, self.stellar_menu_sel)
        self.stellar_running = True


def _handle_stellar_key(self, key):
    if key == ord(' '):
        self.stellar_running = not self.stellar_running
    elif key == ord('v'):
        idx = VIEWS.index(self.stellar_view)
        self.stellar_view = VIEWS[(idx + 1) % len(VIEWS)]
    elif key == ord('r'):
        self.stellar_menu = True
        self.stellar_menu_sel = self.stellar_preset_idx
    elif key == ord('q'):
        self._exit_stellar_mode()
    elif key == ord('s'):
        # Cycle selected star
        if self.stellar_stars:
            self.stellar_selected_idx = (
                (self.stellar_selected_idx + 1) % len(self.stellar_stars))
    elif key == ord('+') or key == ord('='):
        self.stellar_time_scale = min(5.0, self.stellar_time_scale + 0.5)
    elif key == ord('-'):
        self.stellar_time_scale = max(0.5, self.stellar_time_scale - 0.5)


# ══════════════════════════════════════════════════════════════════════
#  Rendering — Menu
# ══════════════════════════════════════════════════════════════════════

def _draw_stellar_menu(self, max_y: int, max_x: int):
    title = "═══ Stellar Lifecycle & Supernova ═══"
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "From gas clouds to supernovae — stellar evolution in real time"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(subtitle)) // 2),
                           subtitle[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass

    for i, (name, desc, _) in enumerate(STELLAR_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        prefix = " * " if i == self.stellar_menu_sel else "   "
        label = f"{prefix}{name}"
        attr = curses.A_REVERSE | curses.A_BOLD if i == self.stellar_menu_sel else 0
        try:
            self.stdscr.addstr(y, 2, label[:max_x - 3], attr)
        except curses.error:
            pass
        if i == self.stellar_menu_sel and y + 1 < max_y - 2:
            try:
                self.stdscr.addstr(y + 1, 6, desc[:max_x - 7], curses.A_DIM)
            except curses.error:
                pass

    help_y = max_y - 1
    help_text = " Up/Down Select   ENTER Start   Q Quit"
    try:
        self.stdscr.addstr(help_y, 0, help_text[:max_x - 1],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Rendering — Main dispatch
# ══════════════════════════════════════════════════════════════════════

def _draw_stellar(self, max_y: int, max_x: int):
    view = self.stellar_view
    if view == VIEW_STAR_FIELD:
        _draw_stellar_star_field(self, max_y, max_x)
    elif view == VIEW_HR_DIAGRAM:
        _draw_stellar_hr_diagram(self, max_y, max_x)
    else:
        _draw_stellar_core_section(self, max_y, max_x)

    # Status bar
    n_stars = len(self.stellar_stars)
    gen = self.stellar_generation
    sn_count = self.stellar_supernova_count
    born = self.stellar_total_stars_born

    # Count by stage
    stage_counts = {}
    for s in self.stellar_stars:
        stage_counts[s.stage] = stage_counts.get(s.stage, 0) + 1

    ms = stage_counts.get(STAGE_MAIN_SEQ, 0)
    rg = stage_counts.get(STAGE_RED_GIANT, 0) + stage_counts.get(STAGE_SUPERGIANT, 0)
    rem = (stage_counts.get(STAGE_WHITE_DWARF, 0) +
           stage_counts.get(STAGE_NEUTRON, 0) +
           stage_counts.get(STAGE_BLACK_HOLE, 0))

    status = (f" Gen:{gen}  Stars:{n_stars}  MS:{ms}  Giants:{rg}"
              f"  Remnants:{rem}  SN:{sn_count}  Speed:{self.stellar_time_scale:.1f}x"
              f"  [{self.stellar_preset_name}]")

    try:
        self.stdscr.addstr(max_y - 1, 0, status[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    help_line = " SPACE Pause  V View  S Select  +/- Speed  R Reset  Q Quit"
    if max_y - 2 > 1:
        try:
            self.stdscr.addstr(max_y - 2, 0, help_line[:max_x - 1],
                               curses.color_pair(7) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  View 1: Star Field — spatial nursery view
# ══════════════════════════════════════════════════════════════════════

_STAR_GLYPHS = {
    STAGE_GAS_CLOUD: '~',
    STAGE_PROTOSTAR: '+',
    STAGE_MAIN_SEQ: '*',
    STAGE_SUBGIANT: '*',
    STAGE_RED_GIANT: 'O',
    STAGE_SUPERGIANT: '#',
    STAGE_SUPERNOVA: '@',
    STAGE_PLAN_NEB: '%',
    STAGE_WHITE_DWARF: '.',
    STAGE_NEUTRON: ':',
    STAGE_BLACK_HOLE: 'o',
    STAGE_REMNANT_FADE: '.',
}

_GAS_CHARS = " .:-=+*#%@"


def _draw_stellar_star_field(self, max_y: int, max_x: int):
    rows = min(self.stellar_rows, max_y - 3)
    cols = min(self.stellar_cols, max_x)
    gas = self.stellar_gas

    # Draw gas clouds
    for r in range(rows):
        line = []
        for c in range(cols):
            val = gas[r][c]
            if val < 0.02:
                line.append(' ')
            else:
                idx = int(val * (len(_GAS_CHARS) - 1))
                idx = max(0, min(len(_GAS_CHARS) - 1, idx))
                line.append(_GAS_CHARS[idx])
        row_str = ''.join(line)
        try:
            self.stdscr.addstr(r, 0, row_str[:max_x - 1],
                               curses.color_pair(5) | curses.A_DIM)
        except curses.error:
            pass

    # Draw shockwaves
    for sw in self.stellar_shockwaves:
        sx, sy, sr, strength, _ = sw
        for angle_i in range(36):
            angle = angle_i * math.pi / 18
            wx = int(sx + math.cos(angle) * sr)
            wy = int(sy + math.sin(angle) * sr)
            if 0 <= wy < rows and 0 <= wx < cols:
                try:
                    ch = '*' if strength > 0.3 else '.'
                    self.stdscr.addstr(wy, wx, ch,
                                       curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass

    # Draw stars
    for i, s in enumerate(self.stellar_stars):
        sy, sx = int(s.y), int(s.x)
        if sy < 0 or sy >= rows or sx < 0 or sx >= cols:
            continue

        ch = _STAR_GLYPHS.get(s.stage, '?')
        attr = 0

        if s.stage == STAGE_GAS_CLOUD:
            attr = curses.color_pair(5) | curses.A_DIM
        elif s.stage == STAGE_PROTOSTAR:
            attr = curses.color_pair(3)  # yellow
        elif s.stage == STAGE_MAIN_SEQ:
            # Color by spectral class
            if s.spectral_class in ("O", "B"):
                attr = curses.color_pair(5) | curses.A_BOLD  # cyan/blue
            elif s.spectral_class in ("A", "F"):
                attr = curses.color_pair(8) | curses.A_BOLD  # white
            elif s.spectral_class == "G":
                attr = curses.color_pair(3) | curses.A_BOLD  # yellow
            else:
                attr = curses.color_pair(2)  # red/orange
        elif s.stage in (STAGE_SUBGIANT,):
            attr = curses.color_pair(3)  # yellow-orange
        elif s.stage in (STAGE_RED_GIANT, STAGE_SUPERGIANT):
            attr = curses.color_pair(2) | curses.A_BOLD  # red
        elif s.stage == STAGE_SUPERNOVA:
            attr = curses.color_pair(4) | curses.A_BOLD  # bright!
            # Draw explosion ring
            for dr in range(-int(s.supernova_radius), int(s.supernova_radius) + 1):
                for dc in range(-int(s.supernova_radius), int(s.supernova_radius) + 1):
                    dist = math.hypot(dr, dc)
                    if abs(dist - s.supernova_radius) < 1.5:
                        ey, ex = sy + dr, sx + dc
                        if 0 <= ey < rows and 0 <= ex < cols:
                            try:
                                explosion_ch = random.choice(['*', '+', '.', 'x'])
                                self.stdscr.addstr(
                                    ey, ex, explosion_ch,
                                    curses.color_pair(3) | curses.A_BOLD)
                            except curses.error:
                                pass
        elif s.stage == STAGE_PLAN_NEB:
            attr = curses.color_pair(6) | curses.A_DIM
            # Draw nebula ring
            nr = int(s.nebula_radius)
            for dr in range(-nr, nr + 1):
                for dc in range(-nr, nr + 1):
                    dist = math.hypot(dr, dc)
                    if abs(dist - s.nebula_radius) < 1.2 and dist > 0:
                        ey, ex = sy + dr, sx + dc
                        if 0 <= ey < rows and 0 <= ex < cols:
                            try:
                                self.stdscr.addstr(
                                    ey, ex, '.',
                                    curses.color_pair(6))
                            except curses.error:
                                pass
        elif s.stage == STAGE_WHITE_DWARF:
            attr = curses.color_pair(8)  # white dim
        elif s.stage == STAGE_NEUTRON:
            attr = curses.color_pair(5) | curses.A_BOLD
        elif s.stage == STAGE_BLACK_HOLE:
            attr = curses.color_pair(7) | curses.A_DIM
            ch = 'o'

        # Highlight selected star
        if i == getattr(self, 'stellar_selected_idx', -1):
            attr |= curses.A_UNDERLINE

        try:
            self.stdscr.addstr(sy, sx, ch, attr)
        except curses.error:
            pass

        # Draw binary link
        if s.binary_partner is not None and s.binary_partner < len(self.stellar_stars):
            partner = self.stellar_stars[s.binary_partner]
            if s.binary_partner > i:  # draw once
                px, py = int(partner.x), int(partner.y)
                mx, my = (sx + px) // 2, (sy + py) // 2
                if 0 <= my < rows and 0 <= mx < cols:
                    try:
                        self.stdscr.addstr(my, mx, '-',
                                           curses.color_pair(7) | curses.A_DIM)
                    except curses.error:
                        pass

    # Title
    title = f" Stellar Nursery — {self.stellar_preset_name} "
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1],
                           curses.color_pair(5) | curses.A_BOLD)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  View 2: Hertzsprung-Russell Diagram
# ══════════════════════════════════════════════════════════════════════

def _draw_stellar_hr_diagram(self, max_y: int, max_x: int):
    graph_height = max_y - 6
    graph_width = max_x - 12

    if graph_height < 8 or graph_width < 20:
        try:
            self.stdscr.addstr(1, 1, "Terminal too small for HR diagram",
                               curses.A_DIM)
        except curses.error:
            pass
        return

    title = " Hertzsprung-Russell Diagram "
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass

    x_off = 10
    y_off = 2

    # Y axis: Luminosity (log scale)  — high at top
    # X axis: Temperature — high at left (reversed, as in real HR diagrams)
    lum_min, lum_max = -4.0, 7.0   # log10 luminosity range
    temp_min, temp_max = 2500, 50000  # temperature range

    # Draw axes
    for r in range(graph_height):
        val = lum_max - (r / max(1, graph_height - 1)) * (lum_max - lum_min)
        if r % max(1, graph_height // 5) == 0:
            label = f"10^{val:+.0f}|"
        else:
            label = "      |"
        try:
            self.stdscr.addstr(y_off + r, 0, label[:x_off],
                               curses.color_pair(7))
        except curses.error:
            pass

    # Luminosity label
    try:
        self.stdscr.addstr(y_off - 1, 0, "Luminosity",
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass

    # X axis
    axis_y = y_off + graph_height
    try:
        self.stdscr.addstr(axis_y, x_off,
                           "+" + "-" * min(graph_width, max_x - x_off - 2),
                           curses.color_pair(7))
    except curses.error:
        pass

    # Temperature labels (reversed: hot on left)
    spec_labels = "O    B    A    F    G    K    M"
    try:
        self.stdscr.addstr(axis_y + 1, x_off, spec_labels[:graph_width],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass
    try:
        self.stdscr.addstr(axis_y + 2, x_off + graph_width // 2 - 8,
                           "Temperature ->  (hot to cool)",
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass

    # Draw main sequence band (faint guide)
    for i in range(graph_width):
        frac = i / max(1, graph_width - 1)  # 0 = hot, 1 = cool
        # Main sequence: log L ~ 3.5 * log M, with T ~ M^0.5
        # Approximate MS line
        ms_log_lum = lum_max - (lum_max - lum_min) * (frac * 0.85 + 0.1)
        ms_row = int((lum_max - ms_log_lum) / (lum_max - lum_min) * (graph_height - 1))
        ms_row = max(0, min(graph_height - 1, ms_row))
        py = y_off + ms_row
        px = x_off + i
        if px < max_x - 1:
            try:
                self.stdscr.addstr(py, px, '.', curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

    # Plot stars
    for idx, s in enumerate(self.stellar_stars):
        if s.stage in (STAGE_GAS_CLOUD, STAGE_REMNANT_FADE):
            continue

        # Map temperature to x (reversed — hot on left)
        if s.temperature <= 0:
            continue
        log_temp = math.log10(max(100, s.temperature))
        log_temp_min = math.log10(temp_min)
        log_temp_max = math.log10(temp_max)
        x_frac = 1.0 - (log_temp - log_temp_min) / (log_temp_max - log_temp_min)
        x_frac = max(0, min(1, x_frac))

        # Map luminosity to y
        log_lum = math.log10(max(1e-5, s.luminosity))
        y_frac = (lum_max - log_lum) / (lum_max - lum_min)
        y_frac = max(0, min(1, y_frac))

        px = x_off + int(x_frac * (graph_width - 1))
        py = y_off + int(y_frac * (graph_height - 1))

        if px >= max_x - 1 or py >= max_y - 3 or px < x_off or py < y_off:
            continue

        # Glyph and color by stage
        if s.stage == STAGE_SUPERNOVA:
            ch, color = '@', curses.color_pair(3) | curses.A_BOLD
        elif s.stage in (STAGE_RED_GIANT, STAGE_SUPERGIANT):
            ch, color = 'O', curses.color_pair(2) | curses.A_BOLD
        elif s.stage == STAGE_WHITE_DWARF:
            ch, color = '.', curses.color_pair(8)
        elif s.stage == STAGE_NEUTRON:
            ch, color = ':', curses.color_pair(5) | curses.A_BOLD
        elif s.stage == STAGE_BLACK_HOLE:
            ch, color = 'o', curses.color_pair(7) | curses.A_DIM
        elif s.stage == STAGE_PROTOSTAR:
            ch, color = '+', curses.color_pair(3)
        else:  # main sequence, subgiant
            ch = '*'
            if s.spectral_class in ("O", "B"):
                color = curses.color_pair(5) | curses.A_BOLD
            elif s.spectral_class in ("A", "F"):
                color = curses.color_pair(8) | curses.A_BOLD
            elif s.spectral_class == "G":
                color = curses.color_pair(3) | curses.A_BOLD
            else:
                color = curses.color_pair(2)

        if idx == getattr(self, 'stellar_selected_idx', -1):
            color |= curses.A_UNDERLINE

        try:
            self.stdscr.addstr(py, px, ch, color)
        except curses.error:
            pass

    # Legend
    legend_y = y_off
    legend_x = max_x - 22
    if legend_x > x_off + graph_width:
        legend_items = [
            ("* Main Seq", curses.color_pair(3)),
            ("O Red Giant", curses.color_pair(2)),
            ("@ Supernova", curses.color_pair(3) | curses.A_BOLD),
            (". White Dwarf", curses.color_pair(8)),
            (": Neutron", curses.color_pair(5)),
            ("o Black Hole", curses.color_pair(7)),
        ]
        for li, (txt, attr) in enumerate(legend_items):
            if legend_y + li < max_y - 3:
                try:
                    self.stdscr.addstr(legend_y + li, legend_x,
                                       txt[:max_x - legend_x - 1], attr)
                except curses.error:
                    pass


# ══════════════════════════════════════════════════════════════════════
#  View 3: Core Cross-Section — onion-layer fusion shells
# ══════════════════════════════════════════════════════════════════════

_SHELL_COLORS = [
    curses.A_BOLD,        # H  — white
    3,                    # He — yellow
    2,                    # C  — red
    6,                    # O  — cyan
    5,                    # Si — magenta
    1,                    # Fe — blue? use color pair
]

_SHELL_LABELS = ["H  (hydrogen)", "He (helium)", "C  (carbon)",
                 "O  (oxygen)", "Si (silicon)", "Fe (iron core)"]

_SHELL_CHARS = ['H', 'e', 'C', 'O', 'i', 'F']


def _draw_stellar_core_section(self, max_y: int, max_x: int):
    stars = self.stellar_stars
    if not stars:
        try:
            self.stdscr.addstr(1, 1, "No stars to display", curses.A_DIM)
        except curses.error:
            pass
        return

    sel_idx = getattr(self, 'stellar_selected_idx', 0) % len(stars)
    s = stars[sel_idx]

    title = f" Core Cross-Section — Star #{sel_idx + 1} "
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass

    # Star info panel
    info_y = 2
    info_lines = [
        f"Mass: {s.mass:.2f} M_sun  (initial: {s.initial_mass:.2f})",
        f"Stage: {STAGE_NAMES.get(s.stage, '?')}",
        f"Spectral Class: {s.spectral_class}",
        f"Temperature: {s.temperature:.0f} K",
        f"Luminosity: {s.luminosity:.2f} L_sun",
        f"Radius: {s.radius:.2f} R_sun",
        f"Age: {s.age:.0f}  Lifetime: {s.lifetime:.0f}",
        f"Fuel (H): {s.fuel:.1%}",
    ]
    if s.binary_partner is not None:
        info_lines.append(f"Binary partner: #{s.binary_partner + 1}")

    for i, line in enumerate(info_lines):
        if info_y + i < max_y - 3:
            try:
                self.stdscr.addstr(info_y + i, 2, line[:max_x - 3],
                                   curses.color_pair(7))
            except curses.error:
                pass

    # Draw concentric circles representing fusion shells
    cx = max_x // 2
    cy = (max_y - 3) // 2 + 4
    max_r = min(cx - 15, cy - 5, 15)

    if max_r < 3:
        return

    # Shell layers (outermost to innermost): H, He, C, O, Si, Fe
    layers = s.shell_layers  # [H, He, C, O, Si, Fe]
    total = sum(layers)
    if total < 0.001:
        total = 1.0

    # Draw from outermost shell inward
    shell_colors_pairs = [
        curses.color_pair(8),                     # H — white
        curses.color_pair(3),                     # He — yellow
        curses.color_pair(2),                     # C — red
        curses.color_pair(5),                     # O — cyan
        curses.color_pair(6),                     # Si — magenta
        curses.color_pair(4) | curses.A_BOLD,     # Fe — green (iron)
    ]

    shell_chars = ['H', 'e', 'C', 'O', 'S', 'F']

    # Compute cumulative radii
    cumulative = []
    running = 0
    for val in layers:
        running += val / total
        cumulative.append(running)

    # Draw shells from outside in
    for dy in range(-max_r, max_r + 1):
        for dx in range(-max_r * 2, max_r * 2 + 1):  # wider for aspect ratio
            dist = math.hypot(dy, dx / 2.0)
            norm_dist = dist / max_r
            if norm_dist > 1.0:
                continue

            px = cx + dx
            py = cy + dy
            if px < 1 or px >= max_x - 1 or py < 1 or py >= max_y - 3:
                continue

            # Which shell?
            shell_idx = 0
            for si, cum in enumerate(cumulative):
                if norm_dist <= cum:
                    shell_idx = si
                    break
            else:
                shell_idx = len(cumulative) - 1

            # Reverse: innermost has highest index
            display_idx = len(layers) - 1 - shell_idx

            if layers[display_idx] < 0.001:
                # Skip negligible shells, show next inward
                continue

            ch = shell_chars[display_idx]
            color = shell_colors_pairs[display_idx]

            # Add some texture
            if (dx + dy) % 3 == 0:
                ch = '.'

            try:
                self.stdscr.addstr(py, px, ch, color)
            except curses.error:
                pass

    # Energy output indicator
    energy_y = cy + max_r + 2
    if energy_y < max_y - 3:
        if s.stage == STAGE_SUPERNOVA:
            energy_str = "ENERGY: >>>>> SUPERNOVA EXPLOSION! <<<<<"
            eattr = curses.color_pair(3) | curses.A_BOLD
        elif s.stage in (STAGE_WHITE_DWARF, STAGE_NEUTRON, STAGE_BLACK_HOLE):
            energy_str = "ENERGY: [dim] — no active fusion"
            eattr = curses.color_pair(7) | curses.A_DIM
        elif s.stage in (STAGE_GAS_CLOUD, STAGE_PROTOSTAR):
            energy_str = "ENERGY: [gravitational contraction]"
            eattr = curses.color_pair(5) | curses.A_DIM
        else:
            # Active fusion
            bars = int(min(20, s.luminosity ** 0.3 * 5))
            bar_str = '|' * bars + ' ' * (20 - bars)
            energy_str = f"ENERGY: [{bar_str}] {s.luminosity:.1f} L_sun"
            eattr = curses.color_pair(3)

        try:
            self.stdscr.addstr(energy_y, max(1, (max_x - len(energy_str)) // 2),
                               energy_str[:max_x - 2], eattr)
        except curses.error:
            pass

    # Shell legend
    legend_x = 2
    legend_y = cy - max_r
    if legend_x + 20 < cx - max_r * 2:
        for i, (label, color) in enumerate(zip(_SHELL_LABELS, shell_colors_pairs)):
            ly = legend_y + i
            if ly < 1 or ly >= max_y - 3:
                continue
            fraction = layers[i] if i < len(layers) else 0
            bar_len = int(fraction / max(0.01, total) * 10)
            bar = '#' * bar_len
            line = f"{label}: {bar}"
            try:
                self.stdscr.addstr(ly, legend_x, line[:max_x // 2 - 2], color)
            except curses.error:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register stellar lifecycle mode methods on the App class."""
    App.STELLAR_PRESETS = STELLAR_PRESETS
    App._enter_stellar_mode = _enter_stellar_mode
    App._exit_stellar_mode = _exit_stellar_mode
    App._stellar_init = _stellar_init
    App._stellar_make_gas = _stellar_make_gas
    App._stellar_make_stars = _stellar_make_stars
    App._stellar_step = _stellar_step
    App._handle_stellar_menu_key = _handle_stellar_menu_key
    App._handle_stellar_key = _handle_stellar_key
    App._draw_stellar_menu = _draw_stellar_menu
    App._draw_stellar = _draw_stellar
    App._draw_stellar_star_field = _draw_stellar_star_field
    App._draw_stellar_hr_diagram = _draw_stellar_hr_diagram
    App._draw_stellar_core_section = _draw_stellar_core_section
