"""Mode: coral_reef — multi-species marine ecosystem simulation.

A 2D spatial simulation of a coral reef ecosystem.  Coral polyps grow
branching and massive structures, symbiotic zooxanthellae provide energy
via photosynthesis, herbivorous fish graze algae, predators patrol, and
environmental stressors (ocean warming, acidification) trigger bleaching
cascades and recovery dynamics.

Features multi-trophic interactions, habitat engineering by coral,
depth-based light zonation, and dramatic bleaching/recovery cycles.

Presets: Healthy Reef, Bleaching Event, Algal Takeover, Recovery,
Crown-of-Thorns Outbreak, Acidification Crisis.
"""
import curses
import math
import random
import time

# ── Cell types ───────────────────────────────────────────────────────
CELL_WATER = 0
CELL_CORAL_BRANCH = 1    # branching coral (Acropora-like)
CELL_CORAL_MASSIVE = 2   # massive coral (Porites-like)
CELL_BLEACHED = 3         # bleached coral (lost zooxanthellae)
CELL_DEAD_CORAL = 4       # dead coral skeleton
CELL_ALGAE_TURF = 5       # turf algae
CELL_ALGAE_MACRO = 6      # macroalgae (fleshy)
CELL_ALGAE_CORALLINE = 7  # coralline algae (CCA — helps coral recruitment)
CELL_SAND = 8             # sandy substrate
CELL_ROCK = 9             # rocky substrate
CELL_SPONGE = 10          # sponge
CELL_ANEMONE = 11         # sea anemone

CELL_CHARS = {
    CELL_WATER: "  ", CELL_CORAL_BRANCH: "YY", CELL_CORAL_MASSIVE: "OO",
    CELL_BLEACHED: "[]", CELL_DEAD_CORAL: "##", CELL_ALGAE_TURF: ",,",
    CELL_ALGAE_MACRO: "ww", CELL_ALGAE_CORALLINE: "::", CELL_SAND: "..",
    CELL_ROCK: "==", CELL_SPONGE: "SS", CELL_ANEMONE: "**",
}

# ── Mobile entity types ─────────────────────────────────────────────
ENT_NONE = 0
ENT_HERB_FISH = 1         # herbivorous fish (parrotfish, surgeonfish)
ENT_PREDATOR = 2          # predatory fish (grouper, barracuda)
ENT_CLEANER = 3           # cleaner wrasse / shrimp
ENT_COTS = 4              # crown-of-thorns starfish (coral predator)
ENT_URCHIN = 5            # sea urchin (algae grazer)
ENT_TURTLE = 6            # sea turtle
ENT_PLANKTON = 7          # plankton cloud

ENT_CHARS = {
    ENT_HERB_FISH: "><", ENT_PREDATOR: ">>", ENT_CLEANER: "<>",
    ENT_COTS: "XX", ENT_URCHIN: "oo", ENT_TURTLE: "TT",
    ENT_PLANKTON: "~~",
}

# ── Presets ───────────────────────────────────────────────────────────
REEF_PRESETS = [
    ("Healthy Reef",
     "Thriving coral reef with balanced trophic levels and clear water",
     {"coral_density": 0.35, "algae_density": 0.08, "sand_density": 0.15,
      "rock_density": 0.05, "herb_fish": 40, "predators": 12,
      "cleaners": 8, "cots": 0, "urchins": 15, "turtles": 3,
      "temperature": 26.0, "temp_trend": 0.0, "acidity": 8.1,
      "acid_trend": 0.0, "light_level": 1.0, "nutrient_level": 0.3,
      "sponge_density": 0.02, "anemone_density": 0.01}),

    ("Bleaching Event",
     "Rising ocean temperatures trigger mass coral bleaching",
     {"coral_density": 0.40, "algae_density": 0.05, "sand_density": 0.12,
      "rock_density": 0.04, "herb_fish": 35, "predators": 10,
      "cleaners": 6, "cots": 2, "urchins": 12, "turtles": 2,
      "temperature": 29.0, "temp_trend": 0.02, "acidity": 8.1,
      "acid_trend": 0.0, "light_level": 1.0, "nutrient_level": 0.3,
      "sponge_density": 0.02, "anemone_density": 0.01}),

    ("Algal Takeover",
     "Overfishing removes herbivores — algae smother the reef",
     {"coral_density": 0.25, "algae_density": 0.20, "sand_density": 0.12,
      "rock_density": 0.05, "herb_fish": 8, "predators": 3,
      "cleaners": 2, "cots": 3, "urchins": 4, "turtles": 1,
      "temperature": 27.0, "temp_trend": 0.0, "acidity": 8.0,
      "acid_trend": 0.0, "light_level": 0.8, "nutrient_level": 0.7,
      "sponge_density": 0.03, "anemone_density": 0.01}),

    ("Recovery",
     "A damaged reef slowly recovering — watch coral recruit and grow",
     {"coral_density": 0.08, "algae_density": 0.25, "sand_density": 0.20,
      "rock_density": 0.08, "herb_fish": 30, "predators": 8,
      "cleaners": 6, "cots": 1, "urchins": 20, "turtles": 2,
      "temperature": 26.5, "temp_trend": 0.0, "acidity": 8.1,
      "acid_trend": 0.0, "light_level": 1.0, "nutrient_level": 0.4,
      "sponge_density": 0.03, "anemone_density": 0.02}),

    ("Crown-of-Thorns Outbreak",
     "Coral-eating starfish population explosion devastates the reef",
     {"coral_density": 0.38, "algae_density": 0.06, "sand_density": 0.12,
      "rock_density": 0.04, "herb_fish": 30, "predators": 6,
      "cleaners": 5, "cots": 25, "urchins": 10, "turtles": 2,
      "temperature": 27.0, "temp_trend": 0.0, "acidity": 8.1,
      "acid_trend": 0.0, "light_level": 1.0, "nutrient_level": 0.5,
      "sponge_density": 0.02, "anemone_density": 0.01}),

    ("Acidification Crisis",
     "Falling pH dissolves coral skeletons and inhibits calcification",
     {"coral_density": 0.30, "algae_density": 0.10, "sand_density": 0.15,
      "rock_density": 0.06, "herb_fish": 25, "predators": 8,
      "cleaners": 5, "cots": 2, "urchins": 12, "turtles": 2,
      "temperature": 27.5, "temp_trend": 0.005, "acidity": 7.8,
      "acid_trend": -0.003, "light_level": 0.9, "nutrient_level": 0.5,
      "sponge_density": 0.02, "anemone_density": 0.01}),
]

# ── Helpers ───────────────────────────────────────────────────────────
_NBRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NBRS8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
           (0, 1), (1, -1), (1, 0), (1, 1)]


def _count_neighbors(grid, r, c, rows, cols, cell_types):
    """Count neighbors of given cell types in 8-neighborhood."""
    count = 0
    for dr, dc in _NBRS8:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            if grid[nr][nc] in cell_types:
                count += 1
    return count


def _adj_empty(grid, r, c, rows, cols, allowed=None):
    """Return list of adjacent positions that are in allowed set."""
    if allowed is None:
        allowed = {CELL_WATER}
    out = []
    for dr, dc in _NBRS4:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            if grid[nr][nc] in allowed:
                out.append((nr, nc))
    return out


def _light_at_row(row, rows, base_light):
    """Light decreases with depth (row). Top rows = shallow, bottom = deep."""
    depth_frac = row / max(1, rows - 1)
    return base_light * max(0.1, 1.0 - 0.7 * depth_frac)


def _bleach_threshold(temperature):
    """Temperature above which coral begins to bleach (DHW concept simplified)."""
    return max(0.0, (temperature - 28.0) / 3.0)


# ══════════════════════════════════════════════════════════════════════
#  Core mode functions
# ══════════════════════════════════════════════════════════════════════

def _enter_reef_mode(self):
    """Enter Coral Reef Ecosystem mode — show preset menu."""
    self.reef_menu = True
    self.reef_menu_sel = 0
    self._flash("Coral Reef Ecosystem — select a scenario")


def _exit_reef_mode(self):
    """Exit Coral Reef Ecosystem mode."""
    self.reef_mode = False
    self.reef_menu = False
    self.reef_running = False
    self.reef_grid = []
    self.reef_entities = []
    self._flash("Coral Reef mode OFF")


def _reef_init(self, preset_idx: int):
    """Initialize the Coral Reef simulation with the given preset."""
    name, _desc, settings = self.REEF_PRESETS[preset_idx]

    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(30, max_y - 4)
    cols = max(40, (max_x - 1) // 2)

    self.reef_rows = rows
    self.reef_cols = cols
    self.reef_preset_name = name
    self.reef_preset_idx = preset_idx
    self.reef_generation = 0
    self.reef_steps_per_frame = 1
    self.reef_settings = dict(settings)
    self.reef_view = "reef"  # reef / light / health

    # Environment state
    self.reef_temperature = settings["temperature"]
    self.reef_acidity = settings["acidity"]
    self.reef_light = settings["light_level"]
    self.reef_nutrients = settings["nutrient_level"]

    # Statistics
    self.reef_stats = {
        "coral_cover": 0, "algae_cover": 0, "bleached": 0,
        "dead_coral": 0, "fish_pop": 0, "peak_coral": 0,
        "bleach_events": 0,
    }

    # ── Build grid ──
    grid = [[CELL_WATER] * cols for _ in range(rows)]

    # Bottom portion is substrate (sand/rock) — lower 20%
    substrate_start = int(rows * 0.80)
    for r in range(substrate_start, rows):
        for c in range(cols):
            if random.random() < settings["sand_density"] * 3:
                grid[r][c] = CELL_SAND
            elif random.random() < settings["rock_density"] * 3:
                grid[r][c] = CELL_ROCK

    # Scatter rock substrate in lower 60% as anchor points
    reef_zone_start = int(rows * 0.25)
    for r in range(reef_zone_start, substrate_start):
        for c in range(cols):
            if random.random() < settings["rock_density"]:
                grid[r][c] = CELL_ROCK

    # Place coral — branching coral prefers upper zone, massive lower
    for r in range(reef_zone_start, substrate_start):
        depth_frac = (r - reef_zone_start) / max(1, substrate_start - reef_zone_start)
        for c in range(cols):
            if grid[r][c] != CELL_WATER:
                continue
            # Need rock or coral neighbor to attach to
            has_anchor = _count_neighbors(grid, r, c, rows, cols,
                                          {CELL_ROCK, CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE}) > 0
            if not has_anchor and random.random() > 0.05:
                continue

            if random.random() < settings["coral_density"]:
                # Branching more common in shallow, massive in deeper
                if random.random() > depth_frac * 0.7:
                    grid[r][c] = CELL_CORAL_BRANCH
                else:
                    grid[r][c] = CELL_CORAL_MASSIVE

    # Place algae
    for r in range(reef_zone_start, rows):
        for c in range(cols):
            if grid[r][c] != CELL_WATER:
                continue
            if random.random() < settings["algae_density"] * 0.3:
                grid[r][c] = CELL_ALGAE_TURF
            elif random.random() < settings["algae_density"] * 0.15:
                grid[r][c] = CELL_ALGAE_MACRO
            elif random.random() < settings["algae_density"] * 0.1:
                grid[r][c] = CELL_ALGAE_CORALLINE

    # Place sponges and anemones
    for r in range(reef_zone_start, substrate_start):
        for c in range(cols):
            if grid[r][c] != CELL_WATER:
                continue
            coral_near = _count_neighbors(grid, r, c, rows, cols,
                                          {CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE})
            if coral_near > 0:
                if random.random() < settings["sponge_density"]:
                    grid[r][c] = CELL_SPONGE
                elif random.random() < settings["anemone_density"]:
                    grid[r][c] = CELL_ANEMONE

    self.reef_grid = grid

    # Health grid: 0.0 = dead, 1.0 = fully healthy (for coral cells)
    self.reef_health = [[1.0 if grid[r][c] in (CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE) else 0.0
                         for c in range(cols)] for r in range(rows)]

    # Zooxanthellae density (symbiont): 0.0-1.0 per coral cell
    self.reef_zoox = [[0.9 if grid[r][c] in (CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE) else 0.0
                        for c in range(cols)] for r in range(rows)]

    # ── Place mobile entities ──
    self.reef_entities = []
    reef_cells = [(r, c) for r in range(reef_zone_start, substrate_start)
                  for c in range(cols) if grid[r][c] == CELL_WATER]

    def _place_entities(etype, count):
        for _ in range(min(count, len(reef_cells))):
            if not reef_cells:
                break
            idx = random.randint(0, len(reef_cells) - 1)
            r, c = reef_cells[idx]
            self.reef_entities.append({
                "type": etype, "r": r, "c": c,
                "energy": 80 + random.randint(0, 40),
                "age": 0, "dir": random.choice([-1, 1]),
            })

    _place_entities(ENT_HERB_FISH, settings["herb_fish"])
    _place_entities(ENT_PREDATOR, settings["predators"])
    _place_entities(ENT_CLEANER, settings["cleaners"])
    _place_entities(ENT_URCHIN, settings["urchins"])
    _place_entities(ENT_TURTLE, settings["turtles"])

    # COTS placed near coral
    coral_cells = [(r, c) for r in range(rows) for c in range(cols)
                   if grid[r][c] in (CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE)]
    for _ in range(settings["cots"]):
        if coral_cells:
            r, c = random.choice(coral_cells)
            # Place in adjacent water
            adj = _adj_empty(grid, r, c, rows, cols)
            if adj:
                nr, nc = random.choice(adj)
                self.reef_entities.append({
                    "type": ENT_COTS, "r": nr, "c": nc,
                    "energy": 100, "age": 0, "dir": 1,
                })

    # Plankton clouds
    for _ in range(max(3, int(settings["nutrient_level"] * 10))):
        r = random.randint(2, reef_zone_start)
        c = random.randint(0, cols - 1)
        self.reef_entities.append({
            "type": ENT_PLANKTON, "r": r, "c": c,
            "energy": 50, "age": 0, "dir": random.choice([-1, 1]),
        })

    self.reef_mode = True
    self.reef_menu = False
    self.reef_running = False
    self._flash(f"Coral Reef: {name} — Space to start")


def _reef_step(self):
    """Advance the coral reef simulation by one step."""
    grid = self.reef_grid
    health = self.reef_health
    zoox = self.reef_zoox
    entities = self.reef_entities
    rows, cols = self.reef_rows, self.reef_cols
    settings = self.reef_settings
    gen = self.reef_generation
    stats = self.reef_stats

    temperature = self.reef_temperature
    acidity = self.reef_acidity
    base_light = self.reef_light
    nutrients = self.reef_nutrients

    # ── 0. Environmental drift ──────────────────────────────────
    self.reef_temperature += settings["temp_trend"]
    self.reef_acidity += settings["acid_trend"]
    temperature = self.reef_temperature
    acidity = self.reef_acidity

    bleach_prob = _bleach_threshold(temperature)
    acid_stress = max(0.0, (8.1 - acidity) / 1.0)  # stress from low pH

    # ── 1. Coral dynamics ───────────────────────────────────────
    coral_types = {CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE}
    grow_candidates = []

    for r in range(rows):
        for c in range(cols):
            ct = grid[r][c]

            if ct in coral_types:
                light = _light_at_row(r, rows, base_light)
                z = zoox[r][c]

                # Photosynthesis: zooxanthellae produce energy
                energy_gain = z * light * 0.05
                # Acid stress reduces calcification
                energy_gain *= max(0.2, 1.0 - acid_stress)

                health[r][c] = min(1.0, health[r][c] + energy_gain - 0.01)

                # Bleaching: thermal stress expels zooxanthellae
                if bleach_prob > 0 and random.random() < bleach_prob * 0.08:
                    zoox[r][c] = max(0.0, zoox[r][c] - 0.15)
                    if zoox[r][c] < 0.1:
                        grid[r][c] = CELL_BLEACHED
                        health[r][c] = max(0.2, health[r][c])
                        stats["bleached"] += 1

                # Recovery: zooxanthellae slowly recolonize if temp OK
                if temperature < 28.5 and z < 0.9:
                    zoox[r][c] = min(1.0, z + 0.005)

                # Growth: coral can spread to adjacent water/turf algae
                if health[r][c] > 0.6 and random.random() < 0.015 * health[r][c]:
                    grow_candidates.append((r, c, ct))

                # Acid dissolution of skeleton
                if acid_stress > 0.3 and random.random() < acid_stress * 0.01:
                    health[r][c] -= 0.1

                # Death
                if health[r][c] <= 0:
                    grid[r][c] = CELL_DEAD_CORAL
                    zoox[r][c] = 0.0
                    health[r][c] = 0.0
                    stats["dead_coral"] += 1

            elif ct == CELL_BLEACHED:
                # Bleached coral can recover or die
                light = _light_at_row(r, rows, base_light)
                if temperature < 28.0 and random.random() < 0.02:
                    # Recovery
                    zoox[r][c] = 0.3
                    # Recover to branch or massive (coin flip weighted to branch)
                    grid[r][c] = CELL_CORAL_BRANCH if random.random() < 0.6 else CELL_CORAL_MASSIVE
                    health[r][c] = 0.5
                else:
                    health[r][c] -= 0.008
                    if health[r][c] <= 0:
                        grid[r][c] = CELL_DEAD_CORAL
                        zoox[r][c] = 0.0
                        stats["dead_coral"] += 1

            elif ct == CELL_DEAD_CORAL:
                # Dead coral gets colonized by algae
                if random.random() < 0.02 * nutrients:
                    grid[r][c] = CELL_ALGAE_TURF
                    health[r][c] = 0.0
                # Or by coralline algae (good for reef recovery)
                elif random.random() < 0.005:
                    grid[r][c] = CELL_ALGAE_CORALLINE
                    health[r][c] = 0.0

            elif ct == CELL_ALGAE_TURF:
                # Turf algae spread
                if random.random() < 0.02 * nutrients:
                    adj = _adj_empty(grid, r, c, rows, cols,
                                     {CELL_WATER, CELL_DEAD_CORAL})
                    if adj:
                        nr, nc = random.choice(adj)
                        grid[nr][nc] = CELL_ALGAE_TURF

                # Turf can grow into macroalgae in high nutrients
                if nutrients > 0.5 and random.random() < 0.008 * nutrients:
                    grid[r][c] = CELL_ALGAE_MACRO

            elif ct == CELL_ALGAE_MACRO:
                # Macroalgae spread aggressively and can overgrow coral
                if random.random() < 0.025 * nutrients:
                    adj = _adj_empty(grid, r, c, rows, cols,
                                     {CELL_WATER, CELL_DEAD_CORAL, CELL_ALGAE_TURF})
                    if adj:
                        nr, nc = random.choice(adj)
                        grid[nr][nc] = CELL_ALGAE_MACRO

                # Can smother adjacent coral
                if nutrients > 0.5 and random.random() < 0.005:
                    for dr, dc in _NBRS4:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if grid[nr][nc] in coral_types:
                                health[nr][nc] -= 0.05

            elif ct == CELL_ALGAE_CORALLINE:
                # CCA facilitates coral recruitment
                if random.random() < 0.003 and temperature < 29.0:
                    adj = _adj_empty(grid, r, c, rows, cols,
                                     {CELL_WATER, CELL_ALGAE_TURF})
                    if adj:
                        nr, nc = random.choice(adj)
                        coral_t = CELL_CORAL_BRANCH if random.random() < 0.6 else CELL_CORAL_MASSIVE
                        grid[nr][nc] = coral_t
                        health[nr][nc] = 0.4
                        zoox[nr][nc] = 0.5

            elif ct == CELL_SPONGE:
                # Sponges filter water (reduce nutrients locally)
                if random.random() < 0.01:
                    adj = _adj_empty(grid, r, c, rows, cols,
                                     {CELL_ALGAE_TURF, CELL_ALGAE_MACRO})
                    if adj:
                        nr, nc = random.choice(adj)
                        grid[nr][nc] = CELL_WATER

    # ── Apply coral growth ──────────────────────────────────────
    for r, c, coral_type in grow_candidates:
        adj = _adj_empty(grid, r, c, rows, cols,
                         {CELL_WATER, CELL_ALGAE_TURF, CELL_DEAD_CORAL})
        if adj:
            nr, nc = random.choice(adj)
            grid[nr][nc] = coral_type
            health[nr][nc] = 0.5
            zoox[nr][nc] = 0.6

    # ── 2. Mobile entity updates ────────────────────────────────
    new_entities = []
    entity_positions = set()

    for ent in entities:
        er, ec = ent["r"], ent["c"]
        etype = ent["type"]
        ent["age"] += 1
        ent["energy"] -= 1

        if ent["energy"] <= 0 or ent["age"] > 500:
            continue  # entity dies

        if etype == ENT_HERB_FISH:
            # Graze algae
            grazed = False
            for dr, dc in _NBRS8:
                nr, nc = er + dr, ec + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] in (CELL_ALGAE_TURF, CELL_ALGAE_MACRO):
                        grid[nr][nc] = CELL_WATER
                        ent["energy"] += 20
                        grazed = True
                        break

            # Move
            _move_entity(ent, grid, rows, cols)

            # Reproduce
            if ent["energy"] > 120 and random.random() < 0.02:
                ent["energy"] -= 40
                new_entities.append({
                    "type": ENT_HERB_FISH,
                    "r": er, "c": ec, "energy": 60,
                    "age": 0, "dir": random.choice([-1, 1]),
                })

        elif etype == ENT_PREDATOR:
            # Hunt herbivorous fish
            hunted = False
            for other in entities:
                if other["type"] in (ENT_HERB_FISH, ENT_CLEANER):
                    dr = abs(other["r"] - er)
                    dc = abs(other["c"] - ec)
                    if dr <= 2 and dc <= 2 and random.random() < 0.1:
                        other["energy"] = 0  # kill prey
                        ent["energy"] += 30
                        hunted = True
                        break

            _move_entity(ent, grid, rows, cols)

            if ent["energy"] > 130 and random.random() < 0.01:
                ent["energy"] -= 50
                new_entities.append({
                    "type": ENT_PREDATOR,
                    "r": er, "c": ec, "energy": 70,
                    "age": 0, "dir": random.choice([-1, 1]),
                })

        elif etype == ENT_CLEANER:
            # Clean parasites from coral (boost health)
            for dr, dc in _NBRS4:
                nr, nc = er + dr, ec + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] in (CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE):
                        health[nr][nc] = min(1.0, health[nr][nc] + 0.02)
                        ent["energy"] += 3
                        break

            _move_entity(ent, grid, rows, cols)

            if ent["energy"] > 100 and random.random() < 0.015:
                ent["energy"] -= 30
                new_entities.append({
                    "type": ENT_CLEANER,
                    "r": er, "c": ec, "energy": 50,
                    "age": 0, "dir": random.choice([-1, 1]),
                })

        elif etype == ENT_COTS:
            # Crown-of-thorns eat coral
            ate = False
            for dr, dc in _NBRS8:
                nr, nc = er + dr, ec + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] in (CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE):
                        grid[nr][nc] = CELL_DEAD_CORAL
                        health[nr][nc] = 0.0
                        zoox[nr][nc] = 0.0
                        ent["energy"] += 25
                        ate = True
                        stats["dead_coral"] += 1
                        break

            _move_entity(ent, grid, rows, cols)

            # COTS reproduce when well-fed and high nutrients
            if ent["energy"] > 140 and nutrients > 0.4 and random.random() < 0.02:
                ent["energy"] -= 50
                new_entities.append({
                    "type": ENT_COTS,
                    "r": er, "c": ec, "energy": 80,
                    "age": 0, "dir": random.choice([-1, 1]),
                })

        elif etype == ENT_URCHIN:
            # Graze algae (slower but more thorough than fish)
            for dr, dc in _NBRS4:
                nr, nc = er + dr, ec + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] in (CELL_ALGAE_TURF, CELL_ALGAE_MACRO):
                        grid[nr][nc] = CELL_WATER
                        ent["energy"] += 15
                        break

            # Urchins move slowly
            if random.random() < 0.3:
                _move_entity(ent, grid, rows, cols)

            if ent["energy"] > 100 and random.random() < 0.01:
                ent["energy"] -= 30
                new_entities.append({
                    "type": ENT_URCHIN,
                    "r": er, "c": ec, "energy": 50,
                    "age": 0, "dir": random.choice([-1, 1]),
                })

        elif etype == ENT_TURTLE:
            # Turtles eat sponges and algae
            for dr, dc in _NBRS8:
                nr, nc = er + dr, ec + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] in (CELL_SPONGE, CELL_ALGAE_MACRO):
                        grid[nr][nc] = CELL_WATER
                        ent["energy"] += 20
                        break

            _move_entity(ent, grid, rows, cols)
            ent["energy"] = max(ent["energy"], 30)  # turtles are resilient

        elif etype == ENT_PLANKTON:
            # Drift with current
            ent["c"] = (ent["c"] + ent["dir"]) % cols
            if random.random() < 0.1:
                ent["r"] = max(0, min(rows - 1, ent["r"] + random.choice([-1, 0, 1])))
            ent["energy"] = 50  # plankton doesn't die from energy

            # Plankton feeds coral polyps
            for dr, dc in _NBRS4:
                nr, nc = ent["r"], (ent["c"] + dc) % cols
                nr = ent["r"] + dr
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] in coral_types:
                        health[nr][nc] = min(1.0, health[nr][nc] + 0.005)

        # Keep entity in bounds
        ent["r"] = max(0, min(rows - 1, ent["r"]))
        ent["c"] = max(0, min(cols - 1, ent["c"]))

        pos = (ent["r"], ent["c"])
        if ent["energy"] > 0:
            new_entities.append(ent)
            entity_positions.add(pos)

    entities.extend(new_entities)

    # Remove dead entities
    self.reef_entities = [e for e in entities if e["energy"] > 0]

    # ── 3. Occasional spawning of plankton ──────────────────────
    if gen % 20 == 0:
        for _ in range(max(1, int(nutrients * 3))):
            r = random.randint(0, max(1, rows // 4))
            c = random.randint(0, cols - 1)
            self.reef_entities.append({
                "type": ENT_PLANKTON, "r": r, "c": c,
                "energy": 50, "age": 0, "dir": random.choice([-1, 1]),
            })

    # ── 4. Coral recruitment events (larvae settlement) ─────────
    if gen % 30 == 0 and temperature < 29.5:
        for _ in range(3):
            r = random.randint(int(rows * 0.3), int(rows * 0.75))
            c = random.randint(0, cols - 1)
            if grid[r][c] in (CELL_ROCK, CELL_ALGAE_CORALLINE, CELL_DEAD_CORAL):
                coral_t = CELL_CORAL_BRANCH if random.random() < 0.5 else CELL_CORAL_MASSIVE
                grid[r][c] = coral_t
                health[r][c] = 0.3
                zoox[r][c] = 0.4

    # ── 5. Update stats ─────────────────────────────────────────
    coral_n = 0
    algae_n = 0
    bleach_n = 0
    dead_n = 0
    for r in range(rows):
        for c in range(cols):
            ct = grid[r][c]
            if ct in coral_types:
                coral_n += 1
            elif ct in (CELL_ALGAE_TURF, CELL_ALGAE_MACRO, CELL_ALGAE_CORALLINE):
                algae_n += 1
            elif ct == CELL_BLEACHED:
                bleach_n += 1
            elif ct == CELL_DEAD_CORAL:
                dead_n += 1

    stats["coral_cover"] = coral_n
    stats["algae_cover"] = algae_n
    stats["bleached"] = bleach_n
    stats["dead_coral"] = dead_n
    stats["fish_pop"] = sum(1 for e in self.reef_entities
                            if e["type"] in (ENT_HERB_FISH, ENT_PREDATOR, ENT_CLEANER))
    stats["peak_coral"] = max(stats["peak_coral"], coral_n)

    self.reef_generation += 1


def _move_entity(ent, grid, rows, cols):
    """Move an entity semi-randomly through water cells."""
    er, ec = ent["r"], ent["c"]
    # Prefer forward direction with some randomness
    dr = random.choice([-1, 0, 0, 1])
    dc = ent["dir"]
    if random.random() < 0.3:
        dc = random.choice([-1, 0, 1])

    nr, nc = er + dr, ec + dc
    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == CELL_WATER:
        ent["r"], ent["c"] = nr, nc
    elif random.random() < 0.5:
        ent["dir"] = -ent["dir"]  # bounce


# ══════════════════════════════════════════════════════════════════════
#  Input handling
# ══════════════════════════════════════════════════════════════════════

def _handle_reef_menu_key(self, key: int) -> bool:
    """Handle input in Coral Reef preset menu."""
    presets = self.REEF_PRESETS
    if key == curses.KEY_DOWN or key == ord("j"):
        self.reef_menu_sel = (self.reef_menu_sel + 1) % len(presets)
    elif key == curses.KEY_UP or key == ord("k"):
        self.reef_menu_sel = (self.reef_menu_sel - 1) % len(presets)
    elif key in (10, 13, curses.KEY_ENTER):
        self._reef_init(self.reef_menu_sel)
    elif key == ord("q") or key == 27:
        self.reef_menu = False
        self._flash("Coral Reef cancelled")
    return True


def _handle_reef_key(self, key: int) -> bool:
    """Handle input in active Coral Reef simulation."""
    if key == ord("q") or key == 27:
        self._exit_reef_mode()
        return True
    if key == ord(" "):
        self.reef_running = not self.reef_running
        return True
    if key == ord("n") or key == ord("."):
        self._reef_step()
        return True
    if key == ord("r"):
        self._reef_init(self.reef_preset_idx)
        return True
    if key == ord("R") or key == ord("m"):
        self.reef_mode = False
        self.reef_running = False
        self.reef_menu = True
        self.reef_menu_sel = 0
        return True
    if key == ord("+") or key == ord("="):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.reef_steps_per_frame) if self.reef_steps_per_frame in choices else 0
        self.reef_steps_per_frame = choices[min(idx + 1, len(choices) - 1)]
        self._flash(f"Speed: {self.reef_steps_per_frame} steps/frame")
        return True
    if key == ord("-") or key == ord("_"):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.reef_steps_per_frame) if self.reef_steps_per_frame in choices else 0
        self.reef_steps_per_frame = choices[max(idx - 1, 0)]
        self._flash(f"Speed: {self.reef_steps_per_frame} steps/frame")
        return True
    if key == ord("v"):
        views = ["reef", "light", "health"]
        idx = views.index(self.reef_view) if self.reef_view in views else 0
        self.reef_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.reef_view}")
        return True
    # Heat wave
    if key == ord("h"):
        self.reef_temperature += 1.5
        self._flash(f"Heat wave! Temp: {self.reef_temperature:.1f}C")
        return True
    # Cool down
    if key == ord("c"):
        self.reef_temperature = max(24.0, self.reef_temperature - 1.0)
        self._flash(f"Cooling! Temp: {self.reef_temperature:.1f}C")
        return True
    # Add herbivores
    if key == ord("f"):
        rows, cols = self.reef_rows, self.reef_cols
        for _ in range(10):
            r = random.randint(int(rows * 0.25), int(rows * 0.75))
            c = random.randint(0, cols - 1)
            self.reef_entities.append({
                "type": ENT_HERB_FISH, "r": r, "c": c,
                "energy": 80, "age": 0, "dir": random.choice([-1, 1]),
            })
        self._flash("Herbivorous fish released!")
        return True
    # Nutrient pulse
    if key == ord("N"):
        self.reef_nutrients = min(1.0, self.reef_nutrients + 0.2)
        self._flash(f"Nutrient runoff! Level: {self.reef_nutrients:.1f}")
        return True
    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing
# ══════════════════════════════════════════════════════════════════════

def _draw_reef_menu(self, max_y: int, max_x: int):
    """Draw the Coral Reef preset selection menu."""
    self.stdscr.erase()
    title = "── Coral Reef Ecosystem ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _settings) in enumerate(self.REEF_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        marker = ">" if i == self.reef_menu_sel else " "
        attr = (curses.color_pair(3) | curses.A_BOLD
                if i == self.reef_menu_sel
                else curses.color_pair(7))
        line = f" {marker} {name:30s}"
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 3], attr)
        except curses.error:
            pass
        desc_attr = (curses.color_pair(6) if i == self.reef_menu_sel
                     else curses.color_pair(7) | curses.A_DIM)
        try:
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8], desc_attr)
        except curses.error:
            pass

    # Legend
    legend_y = 3 + len(self.REEF_PRESETS) * 2 + 1
    if legend_y < max_y - 4:
        legend_lines = [
            "Cells:  YY branching coral  OO massive coral  [] bleached  ## dead coral",
            "        ,, turf algae  ww macroalgae  :: coralline algae  .. sand  == rock",
            "Fish:   >< herbivore  >> predator  <> cleaner  XX crown-of-thorns  oo urchin",
        ]
        for i, line in enumerate(legend_lines):
            if legend_y + i < max_y - 2:
                try:
                    self.stdscr.addstr(legend_y + i, 4, line[:max_x - 6],
                                       curses.color_pair(7) | curses.A_DIM)
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


def _draw_reef(self, max_y: int, max_x: int):
    """Draw the active Coral Reef simulation."""
    self.stdscr.erase()
    grid = self.reef_grid
    health = self.reef_health
    zoox = self.reef_zoox
    entities = self.reef_entities
    rows, cols = self.reef_rows, self.reef_cols
    state = "RUN" if self.reef_running else "PAUSED"
    view = self.reef_view
    stats = self.reef_stats

    temperature = self.reef_temperature
    acidity = self.reef_acidity

    # Title bar
    title = (f" Reef: {self.reef_preset_name}  |  gen {self.reef_generation}"
             f"  |  coral={stats['coral_cover']} algae={stats['algae_cover']}"
             f" bleach={stats['bleached']} fish={stats['fish_pop']}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    # Color mapping for cells
    cell_colors = {
        CELL_CORAL_BRANCH: curses.color_pair(2) | curses.A_BOLD,   # yellow/green — branching
        CELL_CORAL_MASSIVE: curses.color_pair(1) | curses.A_BOLD,   # green — massive
        CELL_BLEACHED: curses.color_pair(7) | curses.A_BOLD,        # bright white
        CELL_DEAD_CORAL: curses.color_pair(7) | curses.A_DIM,       # dim gray
        CELL_ALGAE_TURF: curses.color_pair(1),                       # dim green
        CELL_ALGAE_MACRO: curses.color_pair(1) | curses.A_BOLD,     # bright green
        CELL_ALGAE_CORALLINE: curses.color_pair(5),                   # magenta
        CELL_SAND: curses.color_pair(2) | curses.A_DIM,              # dim yellow
        CELL_ROCK: curses.color_pair(7),                              # white
        CELL_SPONGE: curses.color_pair(3) | curses.A_BOLD,           # bright orange/yellow
        CELL_ANEMONE: curses.color_pair(5) | curses.A_BOLD,          # bright magenta
    }

    ent_colors = {
        ENT_HERB_FISH: curses.color_pair(6) | curses.A_BOLD,   # cyan — herbivore
        ENT_PREDATOR: curses.color_pair(4) | curses.A_BOLD,     # blue — predator
        ENT_CLEANER: curses.color_pair(6),                       # dim cyan
        ENT_COTS: curses.color_pair(1) | curses.A_BOLD,         # red-ish (reusing green+bold)
        ENT_URCHIN: curses.color_pair(5),                        # magenta
        ENT_TURTLE: curses.color_pair(1) | curses.A_BOLD,       # green bold
        ENT_PLANKTON: curses.color_pair(6) | curses.A_DIM,      # dim cyan
    }

    # Build entity position lookup
    ent_map = {}
    for ent in entities:
        pos = (ent["r"], ent["c"])
        if pos not in ent_map:
            ent_map[pos] = ent

    for r in range(view_rows):
        sy = 1 + r
        for c in range(view_cols):
            sx = c * 2

            if view == "reef":
                # Check for entity first
                ent = ent_map.get((r, c))
                if ent:
                    ch = ENT_CHARS.get(ent["type"], "??")
                    attr = ent_colors.get(ent["type"], curses.color_pair(7))
                else:
                    ct = grid[r][c]
                    if ct == CELL_WATER:
                        # Water has depth-based blue tint
                        depth_frac = r / max(1, rows - 1)
                        if depth_frac > 0.7:
                            ch, attr = "~~", curses.color_pair(4) | curses.A_DIM
                        elif depth_frac > 0.3:
                            ch, attr = "  ", curses.color_pair(4)
                        else:
                            continue  # shallow water = blank
                    else:
                        ch = CELL_CHARS.get(ct, "??")
                        attr = cell_colors.get(ct, curses.color_pair(7))

            elif view == "light":
                light = _light_at_row(r, rows, self.reef_light)
                if light > 0.8:
                    ch, attr = "##", curses.color_pair(2) | curses.A_BOLD
                elif light > 0.5:
                    ch, attr = "%%", curses.color_pair(2)
                elif light > 0.3:
                    ch, attr = "..", curses.color_pair(4)
                elif light > 0.1:
                    ch, attr = "..", curses.color_pair(4) | curses.A_DIM
                else:
                    continue

            else:  # health view
                ct = grid[r][c]
                if ct in (CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE, CELL_BLEACHED):
                    h = health[r][c]
                    z = zoox[r][c]
                    if h > 0.8 and z > 0.7:
                        ch, attr = "OO", curses.color_pair(1) | curses.A_BOLD
                    elif h > 0.5:
                        ch, attr = "oo", curses.color_pair(2)
                    elif h > 0.2:
                        ch, attr = "..", curses.color_pair(2) | curses.A_DIM
                    else:
                        ch, attr = "!!", curses.color_pair(5) | curses.A_BOLD
                else:
                    continue

            try:
                self.stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    # Environment status line
    env_y = max_y - 2
    if env_y > 1:
        temp_warn = " !!!" if temperature > 29.0 else ""
        acid_warn = " !!!" if acidity < 7.9 else ""
        env_line = (f" Temp={temperature:.1f}C{temp_warn}  pH={acidity:.2f}{acid_warn}"
                    f"  Light={self.reef_light:.1f}  Nutrients={self.reef_nutrients:.1f}"
                    f"  COTS={sum(1 for e in entities if e['type'] == ENT_COTS)}"
                    f"  Peak coral={stats['peak_coral']}")
        try:
            self.stdscr.addstr(env_y, 0, env_line[:max_x - 1], curses.color_pair(7))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [v]=view [h]=heat [c]=cool [f]=fish [N]=nutrients [+/-]=speed [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register coral reef mode methods on the App class."""
    App._enter_reef_mode = _enter_reef_mode
    App._exit_reef_mode = _exit_reef_mode
    App._reef_init = _reef_init
    App._reef_step = _reef_step
    App._handle_reef_menu_key = _handle_reef_menu_key
    App._handle_reef_key = _handle_reef_key
    App._draw_reef_menu = _draw_reef_menu
    App._draw_reef = _draw_reef
    App.REEF_PRESETS = REEF_PRESETS
