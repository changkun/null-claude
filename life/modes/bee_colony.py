"""Mode: bee — Bee Colony & Waggle Dance Communication Simulation.

Forager bees discover flower patches and return to the hive to perform waggle
dances encoding distance and direction to food sources.  Recruit bees interpret
dances and navigate to advertised locations.  The colony builds hexagonal comb
(honey, brood, pollen storage), regulates hive temperature via fanner bees,
and shifts roles through age-based polyethism (nurse → builder → forager →
guard).

Emergent phenomena:
  - Waggle dance recruitment amplifies exploitation of best patches
  - Diminishing returns & seasonal bloom cycles force exploration
  - Thermoregulation from collective fanning behavior
  - Hexagonal comb self-organization
  - Age-based role transitions (polyethism)
  - Colony-level resource economics (nectar, pollen, honey)
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

BEE_PRESETS = [
    ("Spring Bloom",
     "Abundant wildflower meadow — many patches, gentle foraging",
     "spring"),
    ("Overwintering Cluster",
     "Cold season — bees cluster for warmth, limited foraging",
     "overwinter"),
    ("Swarm Departure",
     "Colony splits — scouts search for new hive site",
     "swarm"),
    ("Bear Attack Defense",
     "Predator intrusion — guards mobilize, foragers return to defend",
     "bear"),
    ("Robber Bee Invasion",
     "Foreign bees raid honey stores — guards vs invaders",
     "robber"),
    ("Pollination Network",
     "Diverse flora with cross-pollination dynamics & specialization",
     "pollination"),
]


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

# Bee roles
ROLE_QUEEN = 0
ROLE_NURSE = 1
ROLE_BUILDER = 2
ROLE_FORAGER = 3
ROLE_GUARD = 4
ROLE_FANNER = 5
ROLE_SCOUT = 6

ROLE_NAMES = ["Queen", "Nurse", "Builder", "Forager", "Guard", "Fanner", "Scout"]

# Comb cell types
COMB_EMPTY = 0
COMB_HONEY = 1
COMB_POLLEN = 2
COMB_BROOD = 3
COMB_WAX = 4       # structural wall

# Bee states
STATE_IDLE = 0
STATE_FORAGING = 1
STATE_RETURNING = 2
STATE_DANCING = 3
STATE_FOLLOWING = 4
STATE_BUILDING = 5
STATE_NURSING = 6
STATE_GUARDING = 7
STATE_FANNING = 8
STATE_SCOUTING = 9

# Dance types
DANCE_NONE = 0
DANCE_WAGGLE = 1   # distance > threshold
DANCE_ROUND = 2    # close source


# ══════════════════════════════════════════════════════════════════════
#  Bee agent
# ══════════════════════════════════════════════════════════════════════

class _Bee:
    __slots__ = ("x", "y", "role", "age", "energy", "state",
                 "nectar", "pollen", "target_x", "target_y",
                 "dance_timer", "dance_angle", "dance_dist",
                 "heading", "speed", "home_x", "home_y",
                 "known_patch", "task_timer")

    def __init__(self, x, y, role=ROLE_FORAGER):
        self.x = x
        self.y = y
        self.role = role
        self.age = random.randint(0, 30) if role != ROLE_QUEEN else 0
        self.energy = 1.0
        self.state = STATE_IDLE
        self.nectar = 0.0
        self.pollen = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.dance_timer = 0
        self.dance_angle = 0.0
        self.dance_dist = 0.0
        self.heading = random.random() * 2 * math.pi
        self.speed = 0.4 + random.random() * 0.3
        self.home_x = x
        self.home_y = y
        self.known_patch = -1
        self.task_timer = 0


# ══════════════════════════════════════════════════════════════════════
#  Flower patch
# ══════════════════════════════════════════════════════════════════════

class _FlowerPatch:
    __slots__ = ("x", "y", "nectar", "pollen", "max_nectar", "max_pollen",
                 "regen_rate", "radius", "species", "bloom_start", "bloom_end")

    def __init__(self, x, y, nectar=100.0, pollen=50.0, radius=3.0, species=0):
        self.x = x
        self.y = y
        self.nectar = nectar
        self.pollen = pollen
        self.max_nectar = nectar
        self.max_pollen = pollen
        self.regen_rate = 0.02
        self.radius = radius
        self.species = species
        self.bloom_start = 0
        self.bloom_end = 9999


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _bee_init(self, preset_idx: int):
    """Initialize bee colony simulation with the given preset."""
    name, _desc, preset_id = BEE_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()

    cols = max(30, max_x - 2)
    rows = max(16, max_y - 4)

    self.bee_cols = cols
    self.bee_rows = rows
    self.bee_preset_name = name
    self.bee_preset_id = preset_id
    self.bee_generation = 0
    self.bee_running = False
    self.bee_steps_per_frame = 1
    self.bee_view = "colony"  # colony, dance, comb

    # Hive center
    hive_x = cols / 2
    hive_y = rows / 2
    self.bee_hive_x = hive_x
    self.bee_hive_y = hive_y
    self.bee_hive_radius = min(rows, cols) / 8

    # Temperature
    self.bee_hive_temp = 35.0   # ideal ~35°C
    self.bee_ambient_temp = 20.0

    # Colony resources
    self.bee_honey_store = 50.0
    self.bee_pollen_store = 30.0
    self.bee_wax_store = 10.0

    # Comb grid (small grid centered on hive)
    comb_r = max(6, rows // 4)
    comb_c = max(10, cols // 4)
    self.bee_comb_rows = comb_r
    self.bee_comb_cols = comb_c
    self.bee_comb = [[COMB_EMPTY] * comb_c for _ in range(comb_r)]
    # Seed some comb structure
    cr, cc = comb_r // 2, comb_c // 2
    for r in range(comb_r):
        for c in range(comb_c):
            dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
            if dist < min(comb_r, comb_c) / 3:
                if random.random() < 0.3:
                    self.bee_comb[r][c] = random.choice([COMB_HONEY, COMB_POLLEN, COMB_BROOD, COMB_WAX])
                elif random.random() < 0.2:
                    self.bee_comb[r][c] = COMB_WAX

    # Active dances (for visualization)
    self.bee_dances = []  # list of (x, y, angle, dist, timer, quality)

    # Statistics
    self.bee_total_nectar = 0.0
    self.bee_total_pollen = 0.0
    self.bee_total_dances = 0
    self.bee_alert_level = 0.0  # 0-1 defense alert

    # Create flower patches
    _bee_make_patches(self, preset_id)

    # Create bees
    _bee_make_bees(self, preset_id)

    # Preset-specific tweaks
    if preset_id == "overwinter":
        self.bee_ambient_temp = -5.0
        self.bee_hive_temp = 20.0
        self.bee_honey_store = 200.0
    elif preset_id == "bear":
        self.bee_alert_level = 0.8
    elif preset_id == "robber":
        self.bee_alert_level = 0.5

    self.bee_mode = True
    self.bee_menu = False
    self._flash(f"Bee Colony: {name} — Space to start")


def _bee_make_patches(self, preset_id):
    """Create flower patches based on preset."""
    cols = self.bee_cols
    rows = self.bee_rows
    hx = self.bee_hive_x
    hy = self.bee_hive_y
    patches = []

    if preset_id == "spring":
        # Many patches scattered around
        for _ in range(12):
            px = random.uniform(2, cols - 2)
            py = random.uniform(2, rows - 2)
            dist = math.sqrt((px - hx) ** 2 + (py - hy) ** 2)
            if dist < 3:
                continue
            nectar = random.uniform(50, 150)
            pollen = random.uniform(20, 80)
            patches.append(_FlowerPatch(px, py, nectar, pollen,
                                        radius=random.uniform(2, 5),
                                        species=random.randint(0, 4)))
    elif preset_id == "overwinter":
        # Very few patches, far away
        for _ in range(3):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(cols / 4, cols / 3)
            px = hx + math.cos(angle) * dist
            py = hy + math.sin(angle) * dist * rows / cols
            px = max(1, min(cols - 2, px))
            py = max(1, min(rows - 2, py))
            patches.append(_FlowerPatch(px, py, 20, 10, radius=2, species=0))
    elif preset_id == "swarm":
        # Moderate patches, some clustered
        for _ in range(8):
            px = random.uniform(2, cols - 2)
            py = random.uniform(2, rows - 2)
            patches.append(_FlowerPatch(px, py, random.uniform(40, 120),
                                        random.uniform(15, 60), radius=3,
                                        species=random.randint(0, 3)))
    elif preset_id == "bear":
        # Good patches but will be disrupted
        for _ in range(10):
            px = random.uniform(2, cols - 2)
            py = random.uniform(2, rows - 2)
            dist = math.sqrt((px - hx) ** 2 + (py - hy) ** 2)
            if dist < 3:
                continue
            patches.append(_FlowerPatch(px, py, random.uniform(60, 140),
                                        random.uniform(30, 70), radius=3.5,
                                        species=random.randint(0, 3)))
    elif preset_id == "robber":
        # Scarce patches to motivate robbing
        for _ in range(5):
            px = random.uniform(2, cols - 2)
            py = random.uniform(2, rows - 2)
            patches.append(_FlowerPatch(px, py, random.uniform(30, 80),
                                        random.uniform(10, 40), radius=2.5,
                                        species=random.randint(0, 2)))
    elif preset_id == "pollination":
        # Diverse species patches in clusters
        for sp in range(6):
            cx = random.uniform(cols * 0.15, cols * 0.85)
            cy = random.uniform(rows * 0.15, rows * 0.85)
            for _ in range(3):
                px = cx + random.uniform(-4, 4)
                py = cy + random.uniform(-3, 3)
                px = max(1, min(cols - 2, px))
                py = max(1, min(rows - 2, py))
                patches.append(_FlowerPatch(px, py, random.uniform(40, 100),
                                            random.uniform(20, 50), radius=2.5,
                                            species=sp))

    self.bee_patches = patches


def _bee_make_bees(self, preset_id):
    """Create the initial bee population."""
    hx = self.bee_hive_x
    hy = self.bee_hive_y
    hr = self.bee_hive_radius
    bees = []

    if preset_id == "spring":
        n_foragers = 60
        n_nurses = 20
        n_builders = 10
        n_guards = 5
        n_fanners = 5
    elif preset_id == "overwinter":
        n_foragers = 15
        n_nurses = 30
        n_builders = 5
        n_guards = 5
        n_fanners = 25
    elif preset_id == "swarm":
        n_foragers = 50
        n_nurses = 15
        n_builders = 15
        n_guards = 10
        n_fanners = 5
    elif preset_id == "bear":
        n_foragers = 40
        n_nurses = 15
        n_builders = 5
        n_guards = 30
        n_fanners = 5
    elif preset_id == "robber":
        n_foragers = 35
        n_nurses = 15
        n_builders = 5
        n_guards = 25
        n_fanners = 5
    elif preset_id == "pollination":
        n_foragers = 70
        n_nurses = 20
        n_builders = 10
        n_guards = 5
        n_fanners = 5
    else:
        n_foragers = 50
        n_nurses = 20
        n_builders = 10
        n_guards = 5
        n_fanners = 5

    # Queen
    q = _Bee(hx, hy, ROLE_QUEEN)
    q.state = STATE_IDLE
    q.home_x = hx
    q.home_y = hy
    bees.append(q)

    def _make_bee(role, age_range=(0, 40)):
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, hr)
        bx = hx + math.cos(angle) * dist
        by = hy + math.sin(angle) * dist
        b = _Bee(bx, by, role)
        b.age = random.randint(*age_range)
        b.home_x = hx
        b.home_y = hy
        return b

    for _ in range(n_foragers):
        b = _make_bee(ROLE_FORAGER, (20, 40))
        bees.append(b)
    for _ in range(n_nurses):
        b = _make_bee(ROLE_NURSE, (3, 12))
        bees.append(b)
    for _ in range(n_builders):
        b = _make_bee(ROLE_BUILDER, (10, 20))
        bees.append(b)
    for _ in range(n_guards):
        b = _make_bee(ROLE_GUARD, (15, 35))
        bees.append(b)
    for _ in range(n_fanners):
        b = _make_bee(ROLE_FANNER, (10, 25))
        bees.append(b)

    # Add scouts
    n_scouts = max(3, n_foragers // 10)
    for _ in range(n_scouts):
        b = _make_bee(ROLE_SCOUT, (20, 40))
        b.state = STATE_SCOUTING
        bees.append(b)

    # Robber preset: add invader bees outside hive
    if preset_id == "robber":
        self.bee_robbers = []
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(hr * 2, hr * 4)
            rx = hx + math.cos(angle) * dist
            ry = hy + math.sin(angle) * dist
            rb = _Bee(rx, ry, ROLE_FORAGER)
            rb.state = STATE_FORAGING
            rb.target_x = hx
            rb.target_y = hy
            rb.energy = 0.8
            self.bee_robbers.append(rb)
    else:
        self.bee_robbers = []

    # Bear preset: place a bear position
    if preset_id == "bear":
        angle = random.uniform(0, 2 * math.pi)
        self.bee_bear_x = hx + math.cos(angle) * hr * 5
        self.bee_bear_y = hy + math.sin(angle) * hr * 5
        self.bee_bear_active = True
    else:
        self.bee_bear_x = 0
        self.bee_bear_y = 0
        self.bee_bear_active = False

    self.bee_bees = bees


# ══════════════════════════════════════════════════════════════════════
#  Simulation step
# ══════════════════════════════════════════════════════════════════════

def _bee_step(self):
    """Advance bee colony simulation by one tick."""
    cols = self.bee_cols
    rows = self.bee_rows
    bees = self.bee_bees
    patches = self.bee_patches
    hx = self.bee_hive_x
    hy = self.bee_hive_y
    hr = self.bee_hive_radius
    gen = self.bee_generation
    rng = random.random

    # ── 1. Patch regeneration & seasonal bloom ──
    for p in patches:
        if p.bloom_start <= gen <= p.bloom_end:
            p.nectar = min(p.max_nectar, p.nectar + p.regen_rate * p.max_nectar)
            p.pollen = min(p.max_pollen, p.pollen + p.regen_rate * 0.5 * p.max_pollen)
        else:
            # Out of bloom — slow decay
            p.nectar = max(0, p.nectar - 0.01)
            p.pollen = max(0, p.pollen - 0.005)

    # Seasonal bloom cycling (every 500 ticks, shift blooms)
    if gen % 500 == 0 and gen > 0:
        for p in patches:
            if rng() < 0.3:
                p.bloom_start = gen + random.randint(0, 200)
                p.bloom_end = p.bloom_start + random.randint(200, 600)
                p.nectar = p.max_nectar * 0.5

    # ── 2. Temperature regulation ──
    fanner_count = sum(1 for b in bees if b.role == ROLE_FANNER and b.state == STATE_FANNING)
    heat_from_bees = len(bees) * 0.015
    cooling = fanner_count * 0.4
    temp_target = 35.0
    self.bee_hive_temp += (self.bee_ambient_temp - self.bee_hive_temp) * 0.01
    self.bee_hive_temp += heat_from_bees * 0.01
    self.bee_hive_temp -= cooling * 0.1
    self.bee_hive_temp = max(self.bee_ambient_temp, min(45.0, self.bee_hive_temp))

    # ── 3. Update each bee ──
    new_dances = []

    for bee in bees:
        if bee.role == ROLE_QUEEN:
            # Queen stays in hive, produces brood
            bee.x = hx + (rng() - 0.5) * 0.5
            bee.y = hy + (rng() - 0.5) * 0.5
            if gen % 50 == 0 and self.bee_honey_store > 5:
                # Lay egg in brood cell
                cr = self.bee_comb_rows // 2 + random.randint(-2, 2)
                cc = self.bee_comb_cols // 2 + random.randint(-2, 2)
                if (0 <= cr < self.bee_comb_rows and
                        0 <= cc < self.bee_comb_cols and
                        self.bee_comb[cr][cc] == COMB_EMPTY):
                    self.bee_comb[cr][cc] = COMB_BROOD
                    self.bee_honey_store -= 0.5
            continue

        dist_to_hive = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)
        in_hive = dist_to_hive < hr * 1.5

        # ── Age-based polyethism ──
        if gen % 100 == 0 and bee.role != ROLE_QUEEN:
            bee.age += 1
            if bee.age > 40 and bee.role != ROLE_GUARD and rng() < 0.1:
                bee.role = ROLE_GUARD
            elif bee.age > 20 and bee.role == ROLE_NURSE and rng() < 0.15:
                bee.role = ROLE_FORAGER
                bee.state = STATE_IDLE
            elif bee.age > 12 and bee.role == ROLE_NURSE and rng() < 0.1:
                bee.role = ROLE_BUILDER
                bee.state = STATE_IDLE

        # ── Emergency role switching ──
        if self.bee_alert_level > 0.5 and bee.role == ROLE_FORAGER and in_hive and rng() < 0.05:
            bee.role = ROLE_GUARD
            bee.state = STATE_GUARDING

        # Temperature emergency: recruit fanners
        if self.bee_hive_temp > 38.0 and in_hive and bee.role not in (ROLE_QUEEN, ROLE_FANNER) and rng() < 0.03:
            bee.role = ROLE_FANNER
            bee.state = STATE_FANNING

        # ── Role-specific behavior ──
        if bee.role == ROLE_FORAGER:
            _bee_update_forager(self, bee, patches, hx, hy, hr, cols, rows, rng, new_dances)

        elif bee.role == ROLE_SCOUT:
            _bee_update_scout(self, bee, patches, hx, hy, hr, cols, rows, rng, new_dances)

        elif bee.role == ROLE_NURSE:
            _bee_update_nurse(self, bee, hx, hy, hr, rng)

        elif bee.role == ROLE_BUILDER:
            _bee_update_builder(self, bee, hx, hy, hr, rng)

        elif bee.role == ROLE_GUARD:
            _bee_update_guard(self, bee, hx, hy, hr, rng)

        elif bee.role == ROLE_FANNER:
            _bee_update_fanner(self, bee, hx, hy, hr, rng)

        # Energy drain
        bee.energy -= 0.001
        if bee.energy < 0.3 and in_hive and self.bee_honey_store > 0.1:
            bee.energy = min(1.0, bee.energy + 0.2)
            self.bee_honey_store -= 0.1

        # Keep in bounds
        bee.x = max(0.5, min(cols - 0.5, bee.x))
        bee.y = max(0.5, min(rows - 0.5, bee.y))

    # ── 4. Update dances ──
    active_dances = []
    for d in self.bee_dances:
        dx, dy, angle, dist, timer, quality = d
        if timer > 0:
            active_dances.append((dx, dy, angle, dist, timer - 1, quality))
    for d in new_dances:
        active_dances.append(d)
    self.bee_dances = active_dances

    # ── 5. Bear movement (bear preset) ──
    if self.bee_bear_active:
        dx = hx - self.bee_bear_x
        dy = hy - self.bee_bear_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 1:
            self.bee_bear_x += dx / dist * 0.15
            self.bee_bear_y += dy / dist * 0.15
        if dist < hr * 2:
            self.bee_alert_level = min(1.0, self.bee_alert_level + 0.02)
            # Bear damages honey stores
            if dist < hr * 1.2:
                self.bee_honey_store = max(0, self.bee_honey_store - 0.5)
        # Guards sting bear — push it back
        guard_count = sum(1 for b in bees if b.role == ROLE_GUARD
                          and b.state == STATE_GUARDING
                          and math.sqrt((b.x - self.bee_bear_x) ** 2 +
                                        (b.y - self.bee_bear_y) ** 2) < 3)
        if guard_count > 10:
            self.bee_bear_x -= dx / max(1, dist) * 0.3
            self.bee_bear_y -= dy / max(1, dist) * 0.3
        if dist > hr * 6:
            self.bee_bear_active = False

    # ── 6. Robber bees (robber preset) ──
    for rb in self.bee_robbers:
        dx = hx - rb.x
        dy = hy - rb.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 1:
            rb.x += dx / dist * 0.3
            rb.y += dy / dist * 0.3
        if dist < hr * 1.5:
            # Steal honey
            if self.bee_honey_store > 0 and rng() < 0.1:
                self.bee_honey_store -= 0.3
            # Guards intercept
            for b in bees:
                if b.role == ROLE_GUARD and b.state == STATE_GUARDING:
                    gd = math.sqrt((b.x - rb.x) ** 2 + (b.y - rb.y) ** 2)
                    if gd < 2:
                        rb.energy -= 0.05
                        break
        if rb.energy <= 0:
            rb.x = hx + random.uniform(-hr * 5, hr * 5)
            rb.y = hy + random.uniform(-hr * 5, hr * 5)
            rb.energy = 0.8
        rb.x = max(0.5, min(cols - 0.5, rb.x))
        rb.y = max(0.5, min(rows - 0.5, rb.y))

    # ── 7. Alert decay ──
    if self.bee_alert_level > 0:
        self.bee_alert_level = max(0, self.bee_alert_level - 0.002)

    # ── 8. Honey production from stored nectar ──
    # (simplified: nectar brought in is already counted as honey)

    self.bee_generation += 1


# ── Forager behavior ──

def _bee_update_forager(self, bee, patches, hx, hy, hr, cols, rows, rng, new_dances):
    dist_to_hive = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)
    in_hive = dist_to_hive < hr * 1.5

    if bee.state == STATE_IDLE and in_hive:
        # Check if following a dance
        for d in self.bee_dances:
            dx, dy, angle, dist, timer, quality = d
            if timer > 0 and rng() < 0.04 * quality:
                # Follow dance — compute target from angle+dist
                bee.target_x = hx + math.cos(angle) * dist
                bee.target_y = hy + math.sin(angle) * dist
                bee.target_x = max(1, min(cols - 1, bee.target_x))
                bee.target_y = max(1, min(rows - 1, bee.target_y))
                bee.state = STATE_FOLLOWING
                bee.known_patch = -1
                break
        else:
            # Random exploration or known patch
            if bee.known_patch >= 0 and bee.known_patch < len(patches):
                p = patches[bee.known_patch]
                if p.nectar > 1:
                    bee.target_x = p.x + (rng() - 0.5) * p.radius
                    bee.target_y = p.y + (rng() - 0.5) * p.radius
                    bee.state = STATE_FORAGING
                else:
                    bee.known_patch = -1
            if bee.state == STATE_IDLE and rng() < 0.02:
                bee.target_x = rng() * cols
                bee.target_y = rng() * rows
                bee.state = STATE_FORAGING

    elif bee.state in (STATE_FORAGING, STATE_FOLLOWING):
        # Move toward target
        dx = bee.target_x - bee.x
        dy = bee.target_y - bee.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0.5:
            bee.heading = math.atan2(dy, dx)
            bee.x += math.cos(bee.heading) * bee.speed
            bee.y += math.sin(bee.heading) * bee.speed
        else:
            # Arrived at target — look for patch
            best_patch = -1
            best_dist = 999
            for i, p in enumerate(patches):
                pd = math.sqrt((bee.x - p.x) ** 2 + (bee.y - p.y) ** 2)
                if pd < p.radius and p.nectar > 0.5 and pd < best_dist:
                    best_dist = pd
                    best_patch = i
            if best_patch >= 0:
                p = patches[best_patch]
                # Collect nectar/pollen
                collect = min(p.nectar, 2.0)
                bee.nectar += collect
                p.nectar -= collect
                pcollect = min(p.pollen, 1.0)
                bee.pollen += pcollect
                p.pollen -= pcollect
                bee.known_patch = best_patch
                bee.state = STATE_RETURNING
                bee.target_x = hx
                bee.target_y = hy
            else:
                # Nothing here — wander
                bee.target_x = bee.x + (rng() - 0.5) * 10
                bee.target_y = bee.y + (rng() - 0.5) * 10
                bee.target_x = max(1, min(cols - 1, bee.target_x))
                bee.target_y = max(1, min(rows - 1, bee.target_y))
                if rng() < 0.05:
                    # Give up and return
                    bee.state = STATE_RETURNING
                    bee.target_x = hx
                    bee.target_y = hy

    elif bee.state == STATE_RETURNING:
        dx = hx - bee.x
        dy = hy - bee.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 1:
            bee.heading = math.atan2(dy, dx)
            bee.x += math.cos(bee.heading) * bee.speed * 1.2
            bee.y += math.sin(bee.heading) * bee.speed * 1.2
        else:
            # Deposit nectar/pollen
            if bee.nectar > 0:
                self.bee_honey_store += bee.nectar * 0.8
                self.bee_total_nectar += bee.nectar
                # Store in comb
                _bee_store_in_comb(self, COMB_HONEY)
            if bee.pollen > 0:
                self.bee_pollen_store += bee.pollen * 0.9
                self.bee_total_pollen += bee.pollen
                _bee_store_in_comb(self, COMB_POLLEN)

            # Perform waggle dance if good source found
            if bee.nectar > 0.5 and bee.known_patch >= 0:
                p = patches[bee.known_patch]
                pdist = math.sqrt((p.x - hx) ** 2 + (p.y - hy) ** 2)
                pangle = math.atan2(p.y - hy, p.x - hx)
                quality = min(1.0, bee.nectar / 3.0)
                dance_len = max(10, int(quality * 40))
                new_dances.append((bee.x, bee.y, pangle, pdist,
                                   dance_len, quality))
                bee.dance_timer = dance_len
                bee.dance_angle = pangle
                bee.dance_dist = pdist
                bee.state = STATE_DANCING
                self.bee_total_dances += 1
            else:
                bee.state = STATE_IDLE

            bee.nectar = 0.0
            bee.pollen = 0.0

    elif bee.state == STATE_DANCING:
        # Waggle dance motion — figure-eight pattern
        if bee.dance_timer > 0:
            t = bee.dance_timer
            phase = (t % 20) / 20.0 * 2 * math.pi
            waggle_x = math.cos(bee.dance_angle) * math.sin(phase) * 1.5
            waggle_y = math.sin(bee.dance_angle) * math.sin(phase) * 1.5
            # Figure-eight cross
            if t % 20 < 10:
                waggle_x += math.cos(bee.dance_angle + math.pi / 2) * math.cos(phase) * 0.5
                waggle_y += math.sin(bee.dance_angle + math.pi / 2) * math.cos(phase) * 0.5
            else:
                waggle_x -= math.cos(bee.dance_angle + math.pi / 2) * math.cos(phase) * 0.5
                waggle_y -= math.sin(bee.dance_angle + math.pi / 2) * math.cos(phase) * 0.5
            bee.x = hx + waggle_x
            bee.y = hy + waggle_y
            bee.dance_timer -= 1
        else:
            bee.state = STATE_IDLE


# ── Scout behavior ──

def _bee_update_scout(self, bee, patches, hx, hy, hr, cols, rows, rng, new_dances):
    dist_to_hive = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)

    if bee.state == STATE_SCOUTING:
        # Fly in wide exploration pattern
        bee.heading += (rng() - 0.5) * 0.6
        bee.x += math.cos(bee.heading) * bee.speed * 1.3
        bee.y += math.sin(bee.heading) * bee.speed * 1.3

        # Check for undiscovered patches
        for i, p in enumerate(patches):
            pd = math.sqrt((bee.x - p.x) ** 2 + (bee.y - p.y) ** 2)
            if pd < p.radius and p.nectar > 10:
                bee.known_patch = i
                bee.nectar = min(p.nectar, 1.0)
                p.nectar -= bee.nectar
                bee.state = STATE_RETURNING
                bee.target_x = hx
                bee.target_y = hy
                break

        # Return home periodically
        if dist_to_hive > max(cols, rows) * 0.8:
            bee.heading = math.atan2(hy - bee.y, hx - bee.x) + (rng() - 0.5) * 0.3
        if rng() < 0.005:
            bee.state = STATE_RETURNING
            bee.target_x = hx
            bee.target_y = hy

    elif bee.state == STATE_RETURNING:
        dx = hx - bee.x
        dy = hy - bee.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 1:
            bee.heading = math.atan2(dy, dx)
            bee.x += math.cos(bee.heading) * bee.speed * 1.2
            bee.y += math.sin(bee.heading) * bee.speed * 1.2
        else:
            if bee.nectar > 0 and bee.known_patch >= 0:
                p = patches[bee.known_patch]
                pdist = math.sqrt((p.x - hx) ** 2 + (p.y - hy) ** 2)
                pangle = math.atan2(p.y - hy, p.x - hx)
                quality = min(1.0, p.nectar / p.max_nectar)
                dance_len = max(15, int(quality * 50))
                new_dances.append((bee.x, bee.y, pangle, pdist,
                                   dance_len, quality))
                bee.dance_timer = dance_len
                bee.dance_angle = pangle
                bee.dance_dist = pdist
                bee.state = STATE_DANCING
                self.bee_total_dances += 1
                self.bee_honey_store += bee.nectar * 0.5
                self.bee_total_nectar += bee.nectar
                bee.nectar = 0
            else:
                bee.state = STATE_SCOUTING

    elif bee.state == STATE_DANCING:
        if bee.dance_timer > 0:
            t = bee.dance_timer
            phase = (t % 16) / 16.0 * 2 * math.pi
            waggle_x = math.cos(bee.dance_angle) * math.sin(phase) * 1.5
            waggle_y = math.sin(bee.dance_angle) * math.sin(phase) * 1.5
            bee.x = hx + waggle_x
            bee.y = hy + waggle_y
            bee.dance_timer -= 1
        else:
            bee.state = STATE_SCOUTING

    elif bee.state == STATE_IDLE:
        bee.state = STATE_SCOUTING


# ── Nurse behavior ──

def _bee_update_nurse(self, bee, hx, hy, hr, rng):
    # Stay in hive, tend brood cells
    dist = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)
    if dist > hr:
        # Return to hive
        angle = math.atan2(hy - bee.y, hx - bee.x)
        bee.x += math.cos(angle) * bee.speed * 0.5
        bee.y += math.sin(angle) * bee.speed * 0.5
    else:
        # Wander inside hive
        bee.heading += (rng() - 0.5) * 1.0
        bee.x += math.cos(bee.heading) * bee.speed * 0.2
        bee.y += math.sin(bee.heading) * bee.speed * 0.2
        bee.state = STATE_NURSING

        # Tend brood: convert brood to empty (hatched) and use pollen
        if rng() < 0.02 and self.bee_pollen_store > 0.1:
            cr = random.randint(0, self.bee_comb_rows - 1)
            cc = random.randint(0, self.bee_comb_cols - 1)
            if self.bee_comb[cr][cc] == COMB_BROOD:
                self.bee_pollen_store -= 0.1


# ── Builder behavior ──

def _bee_update_builder(self, bee, hx, hy, hr, rng):
    dist = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)
    if dist > hr:
        angle = math.atan2(hy - bee.y, hx - bee.x)
        bee.x += math.cos(angle) * bee.speed * 0.5
        bee.y += math.sin(angle) * bee.speed * 0.5
    else:
        bee.heading += (rng() - 0.5) * 0.8
        bee.x += math.cos(bee.heading) * bee.speed * 0.15
        bee.y += math.sin(bee.heading) * bee.speed * 0.15
        bee.state = STATE_BUILDING

        # Build comb: convert empty to wax, expanding outward
        if rng() < 0.03 and self.bee_honey_store > 1.0:
            cr = random.randint(0, self.bee_comb_rows - 1)
            cc = random.randint(0, self.bee_comb_cols - 1)
            if self.bee_comb[cr][cc] == COMB_EMPTY:
                # Only build adjacent to existing comb
                has_neighbor = False
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = cr + dr, cc + dc
                    if (0 <= nr < self.bee_comb_rows and
                            0 <= nc < self.bee_comb_cols and
                            self.bee_comb[nr][nc] != COMB_EMPTY):
                        has_neighbor = True
                        break
                if has_neighbor:
                    self.bee_comb[cr][cc] = COMB_WAX
                    self.bee_honey_store -= 0.5
                    self.bee_wax_store += 0.1


# ── Guard behavior ──

def _bee_update_guard(self, bee, hx, hy, hr, rng):
    bee.state = STATE_GUARDING
    # Patrol hive entrance (perimeter)
    target_dist = hr * 1.2
    dist = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)

    if dist < target_dist - 1:
        # Move outward
        angle = math.atan2(bee.y - hy, bee.x - hx)
        bee.x += math.cos(angle) * bee.speed * 0.3
        bee.y += math.sin(angle) * bee.speed * 0.3
    elif dist > target_dist + 2:
        # Move inward
        angle = math.atan2(hy - bee.y, hx - bee.x)
        bee.x += math.cos(angle) * bee.speed * 0.3
        bee.y += math.sin(angle) * bee.speed * 0.3
    else:
        # Patrol around perimeter
        angle = math.atan2(bee.y - hy, bee.x - hx)
        angle += 0.05
        bee.x = hx + math.cos(angle) * target_dist
        bee.y = hy + math.sin(angle) * target_dist

    # Chase bear if nearby
    if self.bee_bear_active:
        bd = math.sqrt((bee.x - self.bee_bear_x) ** 2 + (bee.y - self.bee_bear_y) ** 2)
        if bd < hr * 3:
            bangle = math.atan2(self.bee_bear_y - bee.y, self.bee_bear_x - bee.x)
            bee.x += math.cos(bangle) * bee.speed * 0.8
            bee.y += math.sin(bangle) * bee.speed * 0.8


# ── Fanner behavior ──

def _bee_update_fanner(self, bee, hx, hy, hr, rng):
    bee.state = STATE_FANNING
    dist = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)
    if dist > hr * 0.8:
        angle = math.atan2(hy - bee.y, hx - bee.x)
        bee.x += math.cos(angle) * bee.speed * 0.3
        bee.y += math.sin(angle) * bee.speed * 0.3
    else:
        # Vibrate in place (fanning wings)
        bee.x += (rng() - 0.5) * 0.3
        bee.y += (rng() - 0.5) * 0.3

    # Stop fanning if temp is fine
    if self.bee_hive_temp < 35.5 and rng() < 0.05:
        bee.role = ROLE_FORAGER
        bee.state = STATE_IDLE


# ── Comb storage helper ──

def _bee_store_in_comb(self, cell_type):
    """Store resource in an available comb cell."""
    cr = self.bee_comb_rows
    cc = self.bee_comb_cols
    # Find empty cell near center
    center_r = cr // 2
    center_c = cc // 2
    for radius in range(max(cr, cc)):
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                r, c = center_r + dr, center_c + dc
                if (0 <= r < cr and 0 <= c < cc and
                        self.bee_comb[r][c] in (COMB_EMPTY, COMB_WAX)):
                    self.bee_comb[r][c] = cell_type
                    return
        if radius > 5:
            break


# ══════════════════════════════════════════════════════════════════════
#  Enter / exit
# ══════════════════════════════════════════════════════════════════════

def _enter_bee_mode(self):
    """Enter Bee Colony mode — show preset menu."""
    self.bee_menu = True
    self.bee_menu_sel = 0
    self._flash("Bee Colony & Waggle Dance Communication — select a scenario")


def _exit_bee_mode(self):
    """Exit Bee Colony mode."""
    self.bee_mode = False
    self.bee_menu = False
    self.bee_running = False
    self._flash("Bee Colony mode OFF")


# ══════════════════════════════════════════════════════════════════════
#  Key handlers
# ══════════════════════════════════════════════════════════════════════

def _handle_bee_menu_key(self, key: int) -> bool:
    """Handle key input in preset menu."""
    n = len(BEE_PRESETS)

    if key == ord("q") or key == 27:
        self.bee_mode = False
        self.bee_menu = False
        return True

    if key == curses.KEY_UP or key == ord("k"):
        self.bee_menu_sel = (self.bee_menu_sel - 1) % n
        return True

    if key == curses.KEY_DOWN or key == ord("j"):
        self.bee_menu_sel = (self.bee_menu_sel + 1) % n
        return True

    if key in (10, 13, curses.KEY_ENTER):
        self._bee_init(self.bee_menu_sel)
        return True

    return True


def _handle_bee_key(self, key: int) -> bool:
    """Handle key input during simulation."""
    if key == ord(" "):
        self.bee_running = not self.bee_running
        self._flash("Running" if self.bee_running else "Paused")
        return True

    if key == ord("n") or key == ord("."):
        self._bee_step()
        return True

    if key == ord("r"):
        idx = next((i for i, p in enumerate(BEE_PRESETS)
                     if p[0] == self.bee_preset_name), 0)
        self._bee_init(idx)
        return True

    if key == ord("R") or key == ord("m"):
        self.bee_mode = False
        self.bee_running = False
        self.bee_menu = True
        self.bee_menu_sel = 0
        return True

    if key == ord("v"):
        views = ["colony", "dance", "comb"]
        cur = views.index(self.bee_view) if self.bee_view in views else 0
        self.bee_view = views[(cur + 1) % len(views)]
        self._flash(f"View: {self.bee_view}")
        return True

    if key == ord("+") or key == ord("="):
        self.bee_steps_per_frame = min(20, self.bee_steps_per_frame + 1)
        self._flash(f"Speed: {self.bee_steps_per_frame}x")
        return True

    if key == ord("-") or key == ord("_"):
        self.bee_steps_per_frame = max(1, self.bee_steps_per_frame - 1)
        self._flash(f"Speed: {self.bee_steps_per_frame}x")
        return True

    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing — menu
# ══════════════════════════════════════════════════════════════════════

def _draw_bee_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()

    title = "── Bee Colony & Waggle Dance Communication ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(BEE_PRESETS):
        y = 4 + i * 2
        if y >= max_y - 6:
            break

        marker = "▸ " if i == self.bee_menu_sel else "  "
        attr = (curses.color_pair(3) | curses.A_BOLD
                if i == self.bee_menu_sel
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
        " Waggle dance communication, comb construction & colony economics",
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

def _draw_bee(self, max_y: int, max_x: int):
    """Draw the active bee colony simulation."""
    self.stdscr.erase()
    state = "▶ RUNNING" if self.bee_running else "⏸ PAUSED"

    title = (f" Bee Colony: {self.bee_preset_name}  |  "
             f"t={self.bee_generation}  "
             f"bees={len(self.bee_bees)}  "
             f"|  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view = self.bee_view
    if view == "colony":
        _draw_bee_colony(self, max_y, max_x)
    elif view == "dance":
        _draw_bee_dance(self, max_y, max_x)
    elif view == "comb":
        _draw_bee_comb(self, max_y, max_x)

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        temp_str = f"{self.bee_hive_temp:.1f}°C"
        info = (f" honey={self.bee_honey_store:.0f}"
                f"  pollen={self.bee_pollen_store:.0f}"
                f"  temp={temp_str}"
                f"  dances={self.bee_total_dances}"
                f"  patches={len(self.bee_patches)}"
                f"  alert={self.bee_alert_level:.0%}")
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


def _draw_bee_colony(self, max_y: int, max_x: int):
    """Draw the main colony view — field with hive, patches, bees."""
    rows = self.bee_rows
    cols = self.bee_cols
    hx = self.bee_hive_x
    hy = self.bee_hive_y
    hr = self.bee_hive_radius

    disp_rows = max_y - 4
    disp_cols = max_x - 1

    # Scale factors
    y_scale = rows / disp_rows if disp_rows > 0 else 1
    x_scale = cols / disp_cols if disp_cols > 0 else 1

    # Draw flower patches as background
    for p in self.bee_patches:
        px = int(p.x / x_scale)
        py = int(p.y / y_scale) + 1
        rad = max(1, int(p.radius / max(x_scale, y_scale)))
        if p.nectar < 1:
            continue
        # Species colors
        species_colors = [2, 3, 5, 1, 6, 4]  # green, yellow, magenta, red, cyan, blue
        color = species_colors[p.species % len(species_colors)]
        brightness = min(1.0, p.nectar / p.max_nectar)
        ch = "✿" if brightness > 0.5 else "·"
        attr = curses.color_pair(color)
        if brightness > 0.7:
            attr |= curses.A_BOLD
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                sr, sc = py + dr, px + dc
                if 1 <= sr < max_y - 2 and 0 <= sc < disp_cols:
                    if dr * dr + dc * dc <= rad * rad:
                        try:
                            self.stdscr.addstr(sr, sc, ch, attr)
                        except curses.error:
                            pass

    # Draw hive
    hive_sx = int(hx / x_scale)
    hive_sy = int(hy / y_scale) + 1
    hive_sr = max(2, int(hr / max(x_scale, y_scale)))
    for dr in range(-hive_sr, hive_sr + 1):
        for dc in range(-hive_sr * 2, hive_sr * 2 + 1):
            sr, sc = hive_sy + dr, hive_sx + dc
            if 1 <= sr < max_y - 2 and 0 <= sc < disp_cols:
                dist = math.sqrt(dr * dr + (dc / 2.0) ** 2)
                if dist <= hive_sr:
                    ch = "⬡" if (dr + dc) % 2 == 0 else "⬢"
                    attr = curses.color_pair(3) | curses.A_BOLD
                    try:
                        self.stdscr.addstr(sr, sc, ch, attr)
                    except curses.error:
                        pass

    # Draw waggle dance trails
    for d in self.bee_dances:
        dx, dy, angle, dist_d, timer, quality = d
        if timer <= 0:
            continue
        # Draw dance direction arrow from hive
        for step in range(1, min(6, int(dist_d / max(x_scale, y_scale)) + 1)):
            ax = int((hx + math.cos(angle) * step * max(x_scale, y_scale)) / x_scale)
            ay = int((hy + math.sin(angle) * step * max(y_scale, x_scale)) / y_scale) + 1
            if 1 <= ay < max_y - 2 and 0 <= ax < disp_cols:
                waggle_ch = "~" if (timer + step) % 3 == 0 else "≈"
                attr = curses.color_pair(3) | curses.A_BOLD
                try:
                    self.stdscr.addstr(ay, ax, waggle_ch, attr)
                except curses.error:
                    pass

    # Draw bees
    for bee in self.bee_bees:
        sx = int(bee.x / x_scale)
        sy = int(bee.y / y_scale) + 1
        if not (1 <= sy < max_y - 2 and 0 <= sx < disp_cols):
            continue

        if bee.role == ROLE_QUEEN:
            ch = "♛"
            attr = curses.color_pair(5) | curses.A_BOLD
        elif bee.role == ROLE_GUARD:
            ch = "●"
            attr = curses.color_pair(1) | curses.A_BOLD
        elif bee.state == STATE_DANCING:
            ch = "∞"
            attr = curses.color_pair(3) | curses.A_BOLD
        elif bee.state == STATE_FORAGING or bee.state == STATE_FOLLOWING:
            ch = "→" if bee.heading is not None and abs(math.cos(bee.heading)) > 0.7 else "↗"
            attr = curses.color_pair(3)
        elif bee.state == STATE_RETURNING:
            ch = "◇" if bee.nectar > 0 else "·"
            attr = curses.color_pair(3)
        elif bee.role == ROLE_FANNER:
            ch = "~"
            attr = curses.color_pair(6)
        elif bee.role == ROLE_NURSE:
            ch = "+"
            attr = curses.color_pair(2)
        elif bee.role == ROLE_BUILDER:
            ch = "□"
            attr = curses.color_pair(3)
        elif bee.role == ROLE_SCOUT:
            ch = "◊"
            attr = curses.color_pair(6) | curses.A_BOLD
        else:
            ch = "·"
            attr = curses.color_pair(7) | curses.A_DIM

        try:
            self.stdscr.addstr(sy, sx, ch, attr)
        except curses.error:
            pass

    # Draw robber bees
    for rb in self.bee_robbers:
        sx = int(rb.x / x_scale)
        sy = int(rb.y / y_scale) + 1
        if 1 <= sy < max_y - 2 and 0 <= sx < disp_cols:
            try:
                self.stdscr.addstr(sy, sx, "✖", curses.color_pair(1) | curses.A_BOLD)
            except curses.error:
                pass

    # Draw bear
    if self.bee_bear_active:
        bsx = int(self.bee_bear_x / x_scale)
        bsy = int(self.bee_bear_y / y_scale) + 1
        if 1 <= bsy < max_y - 2 and 0 <= bsx < disp_cols - 1:
            try:
                self.stdscr.addstr(bsy, bsx, "🐻"[:1], curses.color_pair(1) | curses.A_BOLD)
            except curses.error:
                pass
            # Bear is big — draw as B
            try:
                self.stdscr.addstr(bsy, bsx, "B", curses.color_pair(1) | curses.A_BOLD)
            except curses.error:
                pass


def _draw_bee_dance(self, max_y: int, max_x: int):
    """Draw dance floor view — focused on waggle dance patterns."""
    rows = self.bee_rows
    cols = self.bee_cols
    hx = self.bee_hive_x
    hy = self.bee_hive_y
    hr = self.bee_hive_radius

    disp_rows = max_y - 4
    disp_cols = max_x - 1

    # Zoom into hive area
    view_radius = hr * 3
    view_left = hx - view_radius
    view_top = hy - view_radius
    view_w = view_radius * 2
    view_h = view_radius * 2

    x_scale = view_w / disp_cols if disp_cols > 0 else 1
    y_scale = view_h / disp_rows if disp_rows > 0 else 1

    # Draw hive background
    for sy in range(disp_rows):
        for sx in range(disp_cols):
            wx = view_left + sx * x_scale
            wy = view_top + sy * y_scale
            dist = math.sqrt((wx - hx) ** 2 + (wy - hy) ** 2)
            screen_y = 1 + sy
            if screen_y >= max_y - 2:
                break
            if dist < hr:
                ch = "⬡" if (sy + sx) % 3 == 0 else " "
                attr = curses.color_pair(3) | curses.A_DIM
                try:
                    self.stdscr.addstr(screen_y, sx, ch, attr)
                except curses.error:
                    pass

    # Draw active dances with figure-eight trails
    for d in self.bee_dances:
        dx, dy, angle, dist_d, timer, quality = d
        if timer <= 0:
            continue

        # Draw waggle run (straight line in dance direction)
        waggle_len = min(8, max(2, int(dist_d / 3)))
        for step in range(-waggle_len, waggle_len + 1):
            wx = hx + math.cos(angle) * step * 0.4
            wy = hy + math.sin(angle) * step * 0.4
            sx = int((wx - view_left) / x_scale)
            sy = int((wy - view_top) / y_scale) + 1
            if 1 <= sy < max_y - 2 and 0 <= sx < disp_cols:
                phase = (timer + step) % 4
                ch = "≈~-·"[phase]
                intensity = quality
                attr = curses.color_pair(3)
                if intensity > 0.6:
                    attr |= curses.A_BOLD
                try:
                    self.stdscr.addstr(sy, sx, ch, attr)
                except curses.error:
                    pass

        # Draw return loops (circles at each end)
        for sign in (-1, 1):
            loop_cx = hx + math.cos(angle) * waggle_len * 0.4 * sign
            loop_cy = hy + math.sin(angle) * waggle_len * 0.4 * sign
            perp = angle + math.pi / 2
            loop_cx += math.cos(perp) * sign * 1.5
            loop_cy += math.sin(perp) * sign * 1.5
            for t in range(8):
                a = t / 8.0 * 2 * math.pi
                lx = loop_cx + math.cos(a) * 1.2
                ly = loop_cy + math.sin(a) * 1.2
                lsx = int((lx - view_left) / x_scale)
                lsy = int((ly - view_top) / y_scale) + 1
                if 1 <= lsy < max_y - 2 and 0 <= lsx < disp_cols:
                    try:
                        self.stdscr.addstr(lsy, lsx, "○",
                                           curses.color_pair(3) | curses.A_DIM)
                    except curses.error:
                        pass

    # Draw dancing bees
    for bee in self.bee_bees:
        if bee.state != STATE_DANCING:
            continue
        sx = int((bee.x - view_left) / x_scale)
        sy = int((bee.y - view_top) / y_scale) + 1
        if 1 <= sy < max_y - 2 and 0 <= sx < disp_cols:
            try:
                self.stdscr.addstr(sy, sx, "∞",
                                   curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass

    # Draw following bees (recruits watching dances)
    for bee in self.bee_bees:
        if bee.state not in (STATE_IDLE, STATE_FOLLOWING):
            continue
        dist = math.sqrt((bee.x - hx) ** 2 + (bee.y - hy) ** 2)
        if dist > hr * 2:
            continue
        sx = int((bee.x - view_left) / x_scale)
        sy = int((bee.y - view_top) / y_scale) + 1
        if 1 <= sy < max_y - 2 and 0 <= sx < disp_cols:
            ch = "◦" if bee.state == STATE_FOLLOWING else "·"
            try:
                self.stdscr.addstr(sy, sx, ch, curses.color_pair(7))
            except curses.error:
                pass

    # Dance count overlay
    dance_count = sum(1 for b in self.bee_bees if b.state == STATE_DANCING)
    follow_count = sum(1 for b in self.bee_bees if b.state == STATE_FOLLOWING)
    overlay = f" Dancing: {dance_count}  Following: {follow_count}  Active dances: {len(self.bee_dances)}"
    try:
        self.stdscr.addstr(1, 0, overlay[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


def _draw_bee_comb(self, max_y: int, max_x: int):
    """Draw honeycomb grid view."""
    comb = self.bee_comb
    comb_r = self.bee_comb_rows
    comb_c = self.bee_comb_cols

    disp_rows = max_y - 4
    disp_cols = max_x - 1

    # Center comb display
    cell_w = 3  # characters per cell
    cell_h = 2  # rows per cell
    total_w = comb_c * cell_w
    total_h = comb_r * cell_h
    offset_x = max(0, (disp_cols - total_w) // 2)
    offset_y = max(1, (disp_rows - total_h) // 2 + 1)

    # Count cells by type
    honey_cells = 0
    pollen_cells = 0
    brood_cells = 0
    wax_cells = 0

    for r in range(comb_r):
        for c in range(comb_c):
            cell = comb[r][c]
            sy = offset_y + r * cell_h
            sx = offset_x + c * cell_w
            # Hex offset for odd rows
            if r % 2 == 1:
                sx += cell_w // 2

            if sy >= max_y - 2 or sx >= disp_cols - 2 or sy < 1:
                continue

            if cell == COMB_HONEY:
                ch = "⬡H"
                attr = curses.color_pair(3) | curses.A_BOLD
                honey_cells += 1
            elif cell == COMB_POLLEN:
                ch = "⬡P"
                attr = curses.color_pair(3)
                pollen_cells += 1
            elif cell == COMB_BROOD:
                ch = "⬡B"
                attr = curses.color_pair(5)
                brood_cells += 1
            elif cell == COMB_WAX:
                ch = "⬡ "
                attr = curses.color_pair(3) | curses.A_DIM
                wax_cells += 1
            else:
                ch = "· "
                attr = curses.color_pair(7) | curses.A_DIM

            try:
                self.stdscr.addstr(sy, sx, ch[:min(3, disp_cols - sx)], attr)
            except curses.error:
                pass

    # Comb stats
    stats_y = max_y - 3
    if stats_y > offset_y + total_h:
        stats = (f" Comb: honey={honey_cells}  pollen={pollen_cells}"
                 f"  brood={brood_cells}  wax={wax_cells}")
        try:
            self.stdscr.addstr(stats_y, 0, stats[:max_x - 1],
                               curses.color_pair(6))
        except curses.error:
            pass

    # Role distribution
    role_counts = [0] * 7
    for bee in self.bee_bees:
        if bee.role < 7:
            role_counts[bee.role] += 1
    roles_str = "  ".join(f"{ROLE_NAMES[i]}={role_counts[i]}" for i in range(7) if role_counts[i] > 0)
    try:
        self.stdscr.addstr(1, 0, f" {roles_str}"[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register bee colony mode methods on the App class."""
    App.BEE_PRESETS = BEE_PRESETS
    App._enter_bee_mode = _enter_bee_mode
    App._exit_bee_mode = _exit_bee_mode
    App._bee_init = _bee_init
    App._bee_make_patches = _bee_make_patches
    App._bee_make_bees = _bee_make_bees
    App._bee_step = _bee_step
    App._handle_bee_menu_key = _handle_bee_menu_key
    App._handle_bee_key = _handle_bee_key
    App._draw_bee_menu = _draw_bee_menu
    App._draw_bee = _draw_bee
    App._draw_bee_colony = _draw_bee_colony
    App._draw_bee_dance = _draw_bee_dance
    App._draw_bee_comb = _draw_bee_comb
