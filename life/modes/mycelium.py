"""Mode: mycelium — Mycelium Network / Wood Wide Web simulation.

A side-view underground simulation of fungal mycorrhizal networks.  Hyphae
branch and spread through soil, connect to tree roots, and shuttle nutrients
(carbon, phosphorus, nitrogen) between trees.  Older "mother trees" become
network hubs.  Stressed or dying trees receive emergency nutrient transfers
from neighbors.  Decomposers break down fallen organic matter.  Seasonal
cycles drive growth and dormancy.  Fruiting bodies (mushrooms) emerge on
the surface when conditions are right.

Presets: Old-Growth Forest, Young Plantation, Drought Stress, Fallen Giant,
Nutrient Hotspot, Four Seasons.
"""
import curses
import math
import random
import time

# ── Cell types ───────────────────────────────────────────────────────
CELL_AIR = 0          # above-ground air
CELL_SURFACE = 1      # ground surface (leaf litter / humus)
CELL_TOPSOIL = 2      # rich organic topsoil
CELL_SUBSOIL = 3      # deeper mineral soil
CELL_CLAY = 4         # clay / compacted soil
CELL_ROCK = 5         # bedrock / stones
CELL_ROOT = 6         # tree root
CELL_ROOT_TIP = 7     # active root tip (growing)
CELL_HYPHA = 8        # fungal hypha strand
CELL_HYPHA_HUB = 9    # thick hyphal hub / junction
CELL_MYCORRHIZA = 10  # mycorrhizal connection (root-hypha interface)
CELL_ORGANIC = 11     # fallen organic matter (dead leaves, wood)
CELL_DECOMPOSING = 12 # organic matter being decomposed
CELL_MUSHROOM = 13    # fruiting body (above ground)
CELL_TRUNK = 14       # tree trunk (above ground)
CELL_CANOPY = 15      # tree canopy (above ground)
CELL_WATER = 16       # water pocket / moisture
CELL_SPORE = 17       # fungal spore

CELL_CHARS = {
    CELL_AIR: "  ", CELL_SURFACE: "::", CELL_TOPSOIL: "..",
    CELL_SUBSOIL: ",,", CELL_CLAY: "==", CELL_ROCK: "##",
    CELL_ROOT: "rr", CELL_ROOT_TIP: "r>", CELL_HYPHA: "~~",
    CELL_HYPHA_HUB: "@@", CELL_MYCORRHIZA: "<>", CELL_ORGANIC: "%%",
    CELL_DECOMPOSING: "%%", CELL_MUSHROOM: "/\\", CELL_TRUNK: "||",
    CELL_CANOPY: "{{", CELL_WATER: "~~", CELL_SPORE: "**",
}

# ── Nutrient packet types (mobile entities) ─────────────────────────
ENT_CARBON = 1        # carbon flowing from tree to fungus
ENT_PHOSPHORUS = 2    # phosphorus flowing from fungus to tree
ENT_NITROGEN = 3      # nitrogen flowing from fungus to tree
ENT_SIGNAL = 4        # chemical distress signal
ENT_WATER_DROP = 5    # water percolating down

ENT_CHARS = {
    ENT_CARBON: "C ", ENT_PHOSPHORUS: "P ", ENT_NITROGEN: "N ",
    ENT_SIGNAL: "! ", ENT_WATER_DROP: "o ",
}

# ── Presets ───────────────────────────────────────────────────────────
MYCELIUM_PRESETS = [
    ("Old-Growth Forest",
     "Mature forest with deep mycelial networks and established mother trees",
     {"num_trees": 6, "tree_maturity": 0.9, "hypha_density": 0.12,
      "organic_density": 0.06, "soil_moisture": 0.7, "season": "summer",
      "rock_density": 0.04, "initial_connections": 12,
      "decomposer_rate": 0.03, "growth_rate": 1.0}),

    ("Young Plantation",
     "Recently planted trees — watch mycorrhizal networks develop from scratch",
     {"num_trees": 8, "tree_maturity": 0.2, "hypha_density": 0.02,
      "organic_density": 0.03, "soil_moisture": 0.6, "season": "spring",
      "rock_density": 0.03, "initial_connections": 2,
      "decomposer_rate": 0.02, "growth_rate": 1.5}),

    ("Drought Stress",
     "Dry conditions stress trees — watch the network shuttle emergency water",
     {"num_trees": 5, "tree_maturity": 0.7, "hypha_density": 0.10,
      "organic_density": 0.04, "soil_moisture": 0.2, "season": "summer",
      "rock_density": 0.05, "initial_connections": 8,
      "decomposer_rate": 0.01, "growth_rate": 0.5}),

    ("Fallen Giant",
     "A large tree has fallen — decomposers feast and nutrients redistribute",
     {"num_trees": 5, "tree_maturity": 0.8, "hypha_density": 0.09,
      "organic_density": 0.15, "soil_moisture": 0.65, "season": "autumn",
      "rock_density": 0.04, "initial_connections": 10,
      "decomposer_rate": 0.06, "growth_rate": 0.8}),

    ("Nutrient Hotspot",
     "Mineral-rich soil patch drives intense fungal competition and growth",
     {"num_trees": 6, "tree_maturity": 0.6, "hypha_density": 0.08,
      "organic_density": 0.10, "soil_moisture": 0.75, "season": "spring",
      "rock_density": 0.02, "initial_connections": 6,
      "decomposer_rate": 0.04, "growth_rate": 1.8}),

    ("Four Seasons",
     "Watch the network through seasonal cycles — growth, fruiting, dormancy",
     {"num_trees": 6, "tree_maturity": 0.5, "hypha_density": 0.06,
      "organic_density": 0.05, "soil_moisture": 0.6, "season": "spring",
      "rock_density": 0.03, "initial_connections": 6,
      "decomposer_rate": 0.03, "growth_rate": 1.0}),
]

# ── Helpers ───────────────────────────────────────────────────────────
_NBRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NBRS8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
           (0, 1), (1, -1), (1, 0), (1, 1)]

SOIL_TYPES = {CELL_TOPSOIL, CELL_SUBSOIL, CELL_CLAY, CELL_SURFACE}
HYPHA_TYPES = {CELL_HYPHA, CELL_HYPHA_HUB, CELL_MYCORRHIZA}
ROOT_TYPES = {CELL_ROOT, CELL_ROOT_TIP}
GROWABLE_SOIL = {CELL_TOPSOIL, CELL_SUBSOIL}

SEASONS = ["spring", "summer", "autumn", "winter"]
SEASON_LENGTH = 80  # steps per season


def _count_neighbors(grid, r, c, rows, cols, cell_types):
    """Count neighbors of given cell types in 8-neighborhood."""
    count = 0
    for dr, dc in _NBRS8:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            if grid[nr][nc] in cell_types:
                count += 1
    return count


def _adj_cells(grid, r, c, rows, cols, allowed):
    """Return list of adjacent positions with allowed cell types."""
    out = []
    for dr, dc in _NBRS4:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            if grid[nr][nc] in allowed:
                out.append((nr, nc))
    return out


def _adj_cells8(grid, r, c, rows, cols, allowed):
    """Return list of 8-adjacent positions with allowed cell types."""
    out = []
    for dr, dc in _NBRS8:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            if grid[nr][nc] in allowed:
                out.append((nr, nc))
    return out


def _season_factor(season):
    """Return growth multiplier for the season."""
    return {"spring": 1.3, "summer": 1.0, "autumn": 0.6, "winter": 0.15}.get(season, 1.0)


def _moisture_at_depth(row, surface_row, rows, base_moisture):
    """Moisture increases with depth below surface, capped."""
    if row <= surface_row:
        return 0.0
    depth_frac = (row - surface_row) / max(1, rows - surface_row)
    return min(1.0, base_moisture * (0.5 + 0.8 * depth_frac))


# ══════════════════════════════════════════════════════════════════════
#  Core mode functions
# ══════════════════════════════════════════════════════════════════════

def _enter_mycelium_mode(self):
    """Enter Mycelium Network mode — show preset menu."""
    self.mycelium_menu = True
    self.mycelium_menu_sel = 0
    self._flash("Mycelium Network / Wood Wide Web — select a scenario")


def _exit_mycelium_mode(self):
    """Exit Mycelium Network mode."""
    self.mycelium_mode = False
    self.mycelium_menu = False
    self.mycelium_running = False
    self.mycelium_grid = []
    self.mycelium_entities = []
    self._flash("Mycelium Network mode OFF")


def _mycelium_init(self, preset_idx: int):
    """Initialize the Mycelium Network simulation with the given preset."""
    name, _desc, settings = self.MYCELIUM_PRESETS[preset_idx]

    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(30, max_y - 4)
    cols = max(40, (max_x - 1) // 2)

    self.mycelium_rows = rows
    self.mycelium_cols = cols
    self.mycelium_preset_name = name
    self.mycelium_preset_idx = preset_idx
    self.mycelium_generation = 0
    self.mycelium_steps_per_frame = 1
    self.mycelium_settings = dict(settings)
    self.mycelium_view = "network"  # network / moisture / nutrients

    # Season tracking
    self.mycelium_season_idx = SEASONS.index(settings["season"])
    self.mycelium_season = settings["season"]
    self.mycelium_season_tick = 0
    self.mycelium_moisture = settings["soil_moisture"]

    # Statistics
    self.mycelium_stats = {
        "hypha_cells": 0, "connections": 0, "trees_alive": 0,
        "trees_stressed": 0, "organic_matter": 0, "mushrooms": 0,
        "nutrients_transferred": 0, "total_decomposed": 0,
    }

    # Determine ground surface row (upper 15% is above ground)
    surface_row = int(rows * 0.15)
    self.mycelium_surface = surface_row

    # ── Build grid ──
    grid = [[CELL_AIR] * cols for _ in range(rows)]

    # Fill soil layers
    for r in range(rows):
        for c in range(cols):
            if r < surface_row:
                grid[r][c] = CELL_AIR
            elif r == surface_row:
                grid[r][c] = CELL_SURFACE
            elif r < surface_row + int((rows - surface_row) * 0.3):
                grid[r][c] = CELL_TOPSOIL
            elif r < surface_row + int((rows - surface_row) * 0.65):
                grid[r][c] = CELL_SUBSOIL
            else:
                grid[r][c] = CELL_CLAY

    # Scatter rocks
    for r in range(surface_row + 2, rows):
        for c in range(cols):
            if random.random() < settings["rock_density"]:
                grid[r][c] = CELL_ROCK

    # Scatter water pockets in deeper soil
    for r in range(surface_row + 3, rows):
        for c in range(cols):
            if random.random() < settings["soil_moisture"] * 0.03:
                grid[r][c] = CELL_WATER

    # Scatter organic matter near surface
    for r in range(surface_row, surface_row + 5):
        for c in range(cols):
            if grid[r][c] in SOIL_TYPES and random.random() < settings["organic_density"]:
                grid[r][c] = CELL_ORGANIC

    # ── Place trees ──
    self.mycelium_trees = []
    num_trees = settings["num_trees"]
    tree_spacing = max(4, cols // (num_trees + 1))
    for i in range(num_trees):
        tc = tree_spacing * (i + 1) + random.randint(-2, 2)
        tc = max(2, min(cols - 3, tc))
        maturity = settings["tree_maturity"] + random.uniform(-0.15, 0.15)
        maturity = max(0.1, min(1.0, maturity))
        age = int(maturity * 200)
        is_mother = maturity > 0.75 and random.random() < 0.6

        tree = {
            "col": tc, "maturity": maturity, "age": age,
            "health": 0.7 + maturity * 0.3,
            "stress": 0.0, "is_mother": is_mother,
            "carbon_stored": 50 + int(maturity * 100),
            "root_depth": int(maturity * (rows - surface_row) * 0.5),
        }
        self.mycelium_trees.append(tree)

        # Draw trunk above ground
        trunk_height = max(2, int(maturity * (surface_row - 1)))
        for r in range(surface_row - trunk_height, surface_row):
            if 0 <= r < rows:
                grid[r][tc] = CELL_TRUNK

        # Draw canopy above trunk
        canopy_width = max(1, int(maturity * 4))
        canopy_top = max(0, surface_row - trunk_height - 2)
        for r in range(canopy_top, surface_row - trunk_height):
            for dc in range(-canopy_width, canopy_width + 1):
                cc = tc + dc
                if 0 <= r < rows and 0 <= cc < cols and grid[r][cc] == CELL_AIR:
                    if abs(dc) <= canopy_width - (surface_row - trunk_height - r):
                        grid[r][cc] = CELL_CANOPY

        # Draw roots underground
        root_depth = tree["root_depth"]
        root_spread = max(3, int(maturity * 8))
        for depth in range(1, root_depth + 1):
            r = surface_row + depth
            if r >= rows:
                break
            # Main taproot
            if grid[r][tc] in SOIL_TYPES:
                grid[r][tc] = CELL_ROOT
            # Lateral roots spread wider near surface
            lateral_range = int(root_spread * max(0.2, 1.0 - depth / max(1, root_depth)))
            for dc in range(-lateral_range, lateral_range + 1):
                if dc == 0:
                    continue
                rc = tc + dc
                if 0 <= rc < cols and r < rows and grid[r][rc] in SOIL_TYPES:
                    prob = 0.3 * (1.0 - abs(dc) / max(1, lateral_range))
                    if random.random() < prob:
                        grid[r][rc] = CELL_ROOT
            # Root tips at the ends
            for dc in [-lateral_range, lateral_range]:
                rc = tc + dc
                if 0 <= rc < cols and r < rows and grid[r][rc] == CELL_ROOT:
                    grid[r][rc] = CELL_ROOT_TIP

    # ── Place initial hyphae ──
    for r in range(surface_row + 1, rows - 2):
        for c in range(cols):
            if grid[r][c] in GROWABLE_SOIL and random.random() < settings["hypha_density"]:
                # Prefer placement near roots
                near_root = _count_neighbors(grid, r, c, rows, cols, ROOT_TYPES)
                if near_root > 0 or random.random() < 0.3:
                    grid[r][c] = CELL_HYPHA

    # ── Create initial mycorrhizal connections ──
    connections_made = 0
    for r in range(surface_row + 1, rows):
        for c in range(cols):
            if connections_made >= settings["initial_connections"]:
                break
            if grid[r][c] == CELL_HYPHA:
                near_root = _count_neighbors(grid, r, c, rows, cols, ROOT_TYPES)
                if near_root > 0:
                    grid[r][c] = CELL_MYCORRHIZA
                    connections_made += 1

    # ── Create hyphal hubs where many hyphae converge ──
    for r in range(surface_row + 1, rows - 1):
        for c in range(cols):
            if grid[r][c] == CELL_HYPHA:
                hypha_near = _count_neighbors(grid, r, c, rows, cols, HYPHA_TYPES)
                if hypha_near >= 4:
                    grid[r][c] = CELL_HYPHA_HUB

    self.mycelium_grid = grid

    # Nutrient concentration grid: tracks available N/P per cell
    self.mycelium_nutrient = [[0.0] * cols for _ in range(rows)]
    # Organic cells start with nutrients
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == CELL_ORGANIC:
                self.mycelium_nutrient[r][c] = 0.8 + random.random() * 0.2
            elif grid[r][c] in SOIL_TYPES:
                self.mycelium_nutrient[r][c] = random.random() * 0.2

    # ── Nutrient packet entities ──
    self.mycelium_entities = []

    self.mycelium_mode = True
    self.mycelium_menu = False
    self.mycelium_running = False
    self._flash(f"Mycelium Network: {name} — Space to start")


def _mycelium_step(self):
    """Advance the mycelium simulation by one step."""
    grid = self.mycelium_grid
    nutrient = self.mycelium_nutrient
    entities = self.mycelium_entities
    trees = self.mycelium_trees
    rows, cols = self.mycelium_rows, self.mycelium_cols
    settings = self.mycelium_settings
    gen = self.mycelium_generation
    stats = self.mycelium_stats
    surface_row = self.mycelium_surface
    moisture = self.mycelium_moisture
    season = self.mycelium_season

    sf = _season_factor(season)

    # ── 0. Seasonal cycle ──────────────────────────────────
    self.mycelium_season_tick += 1
    if self.mycelium_season_tick >= SEASON_LENGTH:
        self.mycelium_season_tick = 0
        self.mycelium_season_idx = (self.mycelium_season_idx + 1) % 4
        self.mycelium_season = SEASONS[self.mycelium_season_idx]
        season = self.mycelium_season
        sf = _season_factor(season)
        # Seasonal moisture changes
        if season == "spring":
            self.mycelium_moisture = min(1.0, moisture + 0.15)
        elif season == "summer":
            self.mycelium_moisture = max(0.2, moisture - 0.05)
        elif season == "autumn":
            self.mycelium_moisture = min(1.0, moisture + 0.1)
            # Drop organic matter (leaves falling)
            for c in range(cols):
                if random.random() < 0.15:
                    r = surface_row
                    if 0 <= r < rows and grid[r][c] == CELL_SURFACE:
                        grid[r][c] = CELL_ORGANIC
                        nutrient[r][c] = 0.6
        elif season == "winter":
            self.mycelium_moisture = max(0.1, moisture - 0.1)
        moisture = self.mycelium_moisture

    # ── 1. Hyphal growth ──────────────────────────────────
    grow_candidates = []
    for r in range(surface_row + 1, rows - 1):
        for c in range(cols):
            ct = grid[r][c]
            if ct == CELL_HYPHA or ct == CELL_HYPHA_HUB:
                if random.random() > 0.03 * sf * moisture:
                    continue
                # Hyphae grow into adjacent soil, preferring nutrient-rich areas
                adj = _adj_cells8(grid, r, c, rows, cols, GROWABLE_SOIL)
                if adj:
                    # Weight by nutrient concentration
                    best = max(adj, key=lambda p: nutrient[p[0]][p[1]] + random.random() * 0.3)
                    grow_candidates.append(best)

            elif ct == CELL_HYPHA and random.random() < 0.005 * sf:
                # Chance to form hub where hyphae are dense
                hypha_near = _count_neighbors(grid, r, c, rows, cols, HYPHA_TYPES)
                if hypha_near >= 3:
                    grid[r][c] = CELL_HYPHA_HUB

    for nr, nc in grow_candidates:
        if grid[nr][nc] in GROWABLE_SOIL:
            grid[nr][nc] = CELL_HYPHA

    # ── 2. Mycorrhizal connection formation ───────────────
    for r in range(surface_row + 1, rows):
        for c in range(cols):
            if grid[r][c] == CELL_HYPHA:
                near_root = _count_neighbors(grid, r, c, rows, cols, ROOT_TYPES)
                if near_root > 0 and random.random() < 0.01 * sf:
                    grid[r][c] = CELL_MYCORRHIZA

    # ── 3. Root growth ────────────────────────────────────
    for r in range(surface_row + 1, rows - 1):
        for c in range(cols):
            if grid[r][c] == CELL_ROOT_TIP and random.random() < 0.008 * sf * moisture:
                adj = _adj_cells(grid, r, c, rows, cols, GROWABLE_SOIL)
                if adj:
                    # Grow toward moisture / nutrients
                    best = max(adj, key=lambda p: (
                        _moisture_at_depth(p[0], surface_row, rows, moisture) +
                        nutrient[p[0]][p[1]] + random.random() * 0.2))
                    grid[r][c] = CELL_ROOT
                    grid[best[0]][best[1]] = CELL_ROOT_TIP

    # ── 4. Tree dynamics ──────────────────────────────────
    for tree in trees:
        tc = tree["col"]
        # Carbon production (photosynthesis) — seasonal
        if season != "winter":
            carbon_gain = 2.0 * sf * tree["maturity"]
            tree["carbon_stored"] += carbon_gain

        # Stress from low moisture
        if moisture < 0.3:
            tree["stress"] = min(1.0, tree["stress"] + 0.02)
        elif moisture > 0.5:
            tree["stress"] = max(0.0, tree["stress"] - 0.01)

        # Winter dormancy
        if season == "winter":
            tree["stress"] = min(1.0, tree["stress"] + 0.005)

        # Health decays with stress
        tree["health"] = max(0.1, min(1.0, tree["health"] - tree["stress"] * 0.01 + 0.005))

        # Aging
        tree["age"] += 1
        if tree["age"] > 50 and tree["maturity"] < 1.0:
            tree["maturity"] = min(1.0, tree["maturity"] + 0.001)
        if tree["maturity"] > 0.75:
            tree["is_mother"] = True

        # ── Nutrient transfer via mycorrhizae ──
        # Count connections this tree has
        tree_connections = 0
        for r in range(surface_row + 1, min(rows, surface_row + tree["root_depth"] + 2)):
            for c in range(max(0, tc - 10), min(cols, tc + 11)):
                if grid[r][c] == CELL_MYCORRHIZA:
                    tree_connections += 1

        if tree_connections > 0:
            # Tree sends carbon to fungus
            if tree["carbon_stored"] > 30 and random.random() < 0.05:
                tree["carbon_stored"] -= 2
                # Spawn carbon packet
                for r in range(surface_row + 1, min(rows, surface_row + 5)):
                    if grid[r][tc] in (ROOT_TYPES | HYPHA_TYPES):
                        entities.append({
                            "type": ENT_CARBON, "r": r, "c": tc,
                            "ttl": 30, "origin_tree": trees.index(tree),
                        })
                        break

            # Fungus provides P and N to tree
            if random.random() < 0.03 * tree_connections:
                tree["health"] = min(1.0, tree["health"] + 0.01)
                stats["nutrients_transferred"] += 1

        # ── Mother tree emergency transfer ──
        if tree["is_mother"] and tree["carbon_stored"] > 60:
            for other in trees:
                if other is tree:
                    continue
                if other["stress"] > 0.5 and other["health"] < 0.5:
                    # Check if connected via network
                    dist = abs(other["col"] - tc)
                    if dist < 15 and tree_connections > 0:
                        transfer = min(10, tree["carbon_stored"] - 40)
                        if transfer > 0:
                            tree["carbon_stored"] -= transfer
                            other["health"] = min(1.0, other["health"] + 0.03)
                            other["stress"] = max(0.0, other["stress"] - 0.05)
                            stats["nutrients_transferred"] += 1
                            # Spawn signal packet
                            if random.random() < 0.3:
                                entities.append({
                                    "type": ENT_SIGNAL, "r": surface_row + 2,
                                    "c": tc, "ttl": 20,
                                    "origin_tree": trees.index(tree),
                                })

    # ── 5. Decomposition ──────────────────────────────────
    for r in range(surface_row, rows):
        for c in range(cols):
            ct = grid[r][c]
            if ct == CELL_ORGANIC:
                # Decomposition accelerated by nearby hyphae
                hypha_near = _count_neighbors(grid, r, c, rows, cols, HYPHA_TYPES)
                decomp_rate = settings["decomposer_rate"] * sf * moisture
                if hypha_near > 0:
                    decomp_rate *= 2.0 + hypha_near * 0.5
                if random.random() < decomp_rate:
                    grid[r][c] = CELL_DECOMPOSING
                    nutrient[r][c] = max(nutrient[r][c], 0.5)

            elif ct == CELL_DECOMPOSING:
                # Release nutrients to soil
                nutrient[r][c] = max(0.0, nutrient[r][c] - 0.02)
                # Spread nutrients to neighbors
                for dr, dc in _NBRS4:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if grid[nr][nc] in SOIL_TYPES or grid[nr][nc] in HYPHA_TYPES:
                            nutrient[nr][nc] = min(1.0, nutrient[nr][nc] + 0.005)
                if nutrient[r][c] <= 0.05:
                    grid[r][c] = CELL_TOPSOIL
                    stats["total_decomposed"] += 1

    # ── 6. Nutrient diffusion ─────────────────────────────
    if gen % 3 == 0:
        new_nutrient = [row[:] for row in nutrient]
        for r in range(surface_row, rows):
            for c in range(cols):
                if grid[r][c] in (SOIL_TYPES | HYPHA_TYPES | ROOT_TYPES):
                    total = nutrient[r][c]
                    count = 1
                    for dr, dc in _NBRS4:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if grid[nr][nc] not in (CELL_AIR, CELL_ROCK):
                                total += nutrient[nr][nc]
                                count += 1
                    new_nutrient[r][c] = total / count
        self.mycelium_nutrient = new_nutrient
        nutrient = new_nutrient

    # ── 7. Nutrient packet movement ───────────────────────
    new_entities = []
    for ent in entities:
        ent["ttl"] -= 1
        if ent["ttl"] <= 0:
            continue

        er, ec = ent["r"], ent["c"]
        etype = ent["type"]

        if etype == ENT_CARBON:
            # Carbon flows along hyphae away from origin tree
            adj = _adj_cells8(grid, er, ec, rows, cols, HYPHA_TYPES)
            if adj:
                # Move away from origin tree
                origin = trees[ent["origin_tree"]] if ent["origin_tree"] < len(trees) else None
                if origin:
                    best = max(adj, key=lambda p: abs(p[1] - origin["col"]) + random.random())
                else:
                    best = random.choice(adj)
                ent["r"], ent["c"] = best
                nutrient[best[0]][best[1]] = min(1.0, nutrient[best[0]][best[1]] + 0.05)
            new_entities.append(ent)

        elif etype in (ENT_PHOSPHORUS, ENT_NITROGEN):
            # P and N flow along hyphae toward roots
            adj = _adj_cells8(grid, er, ec, rows, cols, HYPHA_TYPES | ROOT_TYPES)
            if adj:
                # Prefer moving toward roots
                root_adj = [p for p in adj if grid[p[0]][p[1]] in ROOT_TYPES]
                if root_adj:
                    ent["r"], ent["c"] = random.choice(root_adj)
                    ent["ttl"] = 0  # absorbed
                    stats["nutrients_transferred"] += 1
                else:
                    ent["r"], ent["c"] = random.choice(adj)
                    new_entities.append(ent)
            else:
                new_entities.append(ent)

        elif etype == ENT_SIGNAL:
            # Distress signals propagate along network
            adj = _adj_cells8(grid, er, ec, rows, cols, HYPHA_TYPES | ROOT_TYPES)
            if adj:
                ent["r"], ent["c"] = random.choice(adj)
            new_entities.append(ent)

        elif etype == ENT_WATER_DROP:
            # Water percolates downward
            nr = er + 1
            if nr < rows and grid[nr][ec] in (SOIL_TYPES | HYPHA_TYPES | ROOT_TYPES):
                ent["r"] = nr
                new_entities.append(ent)
            # Otherwise absorbed

    self.mycelium_entities = new_entities

    # ── 8. Spawn nutrient packets from hubs ───────────────
    if gen % 10 == 0:
        for r in range(surface_row + 1, rows):
            for c in range(cols):
                if grid[r][c] == CELL_HYPHA_HUB and nutrient[r][c] > 0.3:
                    if random.random() < 0.1:
                        etype = random.choice([ENT_PHOSPHORUS, ENT_NITROGEN])
                        entities.append({
                            "type": etype, "r": r, "c": c,
                            "ttl": 25, "origin_tree": -1,
                        })

    # ── 9. Fruiting bodies (mushrooms) ────────────────────
    # Mushrooms appear in autumn or when moisture and nutrients are high
    fruiting_chance = 0.0
    if season == "autumn":
        fruiting_chance = 0.004
    elif moisture > 0.6 and season != "winter":
        fruiting_chance = 0.001

    if fruiting_chance > 0:
        for c in range(cols):
            r = surface_row
            if grid[r][c] == CELL_SURFACE or grid[r][c] == CELL_ORGANIC:
                # Need hyphae below
                below_hypha = False
                for dr in range(1, 4):
                    if r + dr < rows and grid[r + dr][c] in HYPHA_TYPES:
                        below_hypha = True
                        break
                if below_hypha and random.random() < fruiting_chance:
                    # Place mushroom above ground
                    mr = r - 1
                    if 0 <= mr < rows and grid[mr][c] == CELL_AIR:
                        grid[mr][c] = CELL_MUSHROOM

    # Mushrooms decay after a while
    for r in range(surface_row):
        for c in range(cols):
            if grid[r][c] == CELL_MUSHROOM:
                if random.random() < 0.02:
                    grid[r][c] = CELL_AIR
                    # Release spores
                    for _ in range(random.randint(1, 3)):
                        sc = c + random.randint(-5, 5)
                        sr = r + random.randint(-1, 2)
                        if 0 <= sr < rows and 0 <= sc < cols and grid[sr][sc] == CELL_AIR:
                            grid[sr][sc] = CELL_SPORE

    # Spores drift down and colonize soil
    for r in range(rows - 1):
        for c in range(cols):
            if grid[r][c] == CELL_SPORE:
                grid[r][c] = CELL_AIR
                nr = r + 1
                nc = c + random.choice([-1, 0, 0, 1])
                nc = max(0, min(cols - 1, nc))
                if nr < rows:
                    if grid[nr][nc] in GROWABLE_SOIL:
                        grid[nr][nc] = CELL_HYPHA  # spore germinates
                    elif grid[nr][nc] == CELL_AIR:
                        grid[nr][nc] = CELL_SPORE  # keep falling

    # ── 10. Water percolation ─────────────────────────────
    if gen % 5 == 0 and season in ("spring", "autumn"):
        # Rain adds water drops
        for _ in range(max(1, int(moisture * 3))):
            c = random.randint(0, cols - 1)
            entities.append({
                "type": ENT_WATER_DROP, "r": surface_row,
                "c": c, "ttl": rows, "origin_tree": -1,
            })

    # ── 11. Hyphal die-back in drought/winter ─────────────
    if moisture < 0.25 or season == "winter":
        dieback_rate = 0.003 if season == "winter" else 0.002
        for r in range(surface_row + 1, rows):
            for c in range(cols):
                if grid[r][c] == CELL_HYPHA and random.random() < dieback_rate:
                    grid[r][c] = CELL_TOPSOIL if r < surface_row + int((rows - surface_row) * 0.3) else CELL_SUBSOIL

    # ── 12. Update stats ──────────────────────────────────
    hypha_n = 0
    conn_n = 0
    organic_n = 0
    mushroom_n = 0
    for r in range(rows):
        for c in range(cols):
            ct = grid[r][c]
            if ct in (CELL_HYPHA, CELL_HYPHA_HUB):
                hypha_n += 1
            elif ct == CELL_MYCORRHIZA:
                conn_n += 1
                hypha_n += 1
            elif ct in (CELL_ORGANIC, CELL_DECOMPOSING):
                organic_n += 1
            elif ct == CELL_MUSHROOM:
                mushroom_n += 1

    alive = sum(1 for t in trees if t["health"] > 0.2)
    stressed = sum(1 for t in trees if t["stress"] > 0.3)

    stats["hypha_cells"] = hypha_n
    stats["connections"] = conn_n
    stats["trees_alive"] = alive
    stats["trees_stressed"] = stressed
    stats["organic_matter"] = organic_n
    stats["mushrooms"] = mushroom_n

    self.mycelium_generation += 1


# ══════════════════════════════════════════════════════════════════════
#  Input handling
# ══════════════════════════════════════════════════════════════════════

def _handle_mycelium_menu_key(self, key: int) -> bool:
    """Handle input in Mycelium Network preset menu."""
    presets = self.MYCELIUM_PRESETS
    if key == curses.KEY_DOWN or key == ord("j"):
        self.mycelium_menu_sel = (self.mycelium_menu_sel + 1) % len(presets)
    elif key == curses.KEY_UP or key == ord("k"):
        self.mycelium_menu_sel = (self.mycelium_menu_sel - 1) % len(presets)
    elif key in (10, 13, curses.KEY_ENTER):
        self._mycelium_init(self.mycelium_menu_sel)
    elif key == ord("q") or key == 27:
        self.mycelium_menu = False
        self._flash("Mycelium Network cancelled")
    return True


def _handle_mycelium_key(self, key: int) -> bool:
    """Handle input in active Mycelium Network simulation."""
    if key == ord("q") or key == 27:
        self._exit_mycelium_mode()
        return True
    if key == ord(" "):
        self.mycelium_running = not self.mycelium_running
        return True
    if key == ord("n") or key == ord("."):
        self._mycelium_step()
        return True
    if key == ord("r"):
        self._mycelium_init(self.mycelium_preset_idx)
        return True
    if key == ord("R") or key == ord("m"):
        self.mycelium_mode = False
        self.mycelium_running = False
        self.mycelium_menu = True
        self.mycelium_menu_sel = 0
        return True
    if key == ord("+") or key == ord("="):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.mycelium_steps_per_frame) if self.mycelium_steps_per_frame in choices else 0
        self.mycelium_steps_per_frame = choices[min(idx + 1, len(choices) - 1)]
        self._flash(f"Speed: {self.mycelium_steps_per_frame} steps/frame")
        return True
    if key == ord("-") or key == ord("_"):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.mycelium_steps_per_frame) if self.mycelium_steps_per_frame in choices else 0
        self.mycelium_steps_per_frame = choices[max(idx - 1, 0)]
        self._flash(f"Speed: {self.mycelium_steps_per_frame} steps/frame")
        return True
    if key == ord("v"):
        views = ["network", "moisture", "nutrients"]
        idx = views.index(self.mycelium_view) if self.mycelium_view in views else 0
        self.mycelium_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.mycelium_view}")
        return True
    # Add water (rain)
    if key == ord("w"):
        self.mycelium_moisture = min(1.0, self.mycelium_moisture + 0.15)
        self._flash(f"Rain! Moisture: {self.mycelium_moisture:.1f}")
        return True
    # Drought
    if key == ord("d"):
        self.mycelium_moisture = max(0.05, self.mycelium_moisture - 0.15)
        self._flash(f"Drought! Moisture: {self.mycelium_moisture:.1f}")
        return True
    # Drop organic matter
    if key == ord("o"):
        surface = self.mycelium_surface
        cols = self.mycelium_cols
        grid = self.mycelium_grid
        nutrient = self.mycelium_nutrient
        for _ in range(8):
            c = random.randint(0, cols - 1)
            if grid[surface][c] in (CELL_SURFACE, CELL_TOPSOIL):
                grid[surface][c] = CELL_ORGANIC
                nutrient[surface][c] = 0.7
        self._flash("Organic matter dropped!")
        return True
    # Advance season
    if key == ord("s"):
        self.mycelium_season_tick = SEASON_LENGTH - 1
        self._flash(f"Advancing season...")
        return True
    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing
# ══════════════════════════════════════════════════════════════════════

def _draw_mycelium_menu(self, max_y: int, max_x: int):
    """Draw the Mycelium Network preset selection menu."""
    self.stdscr.erase()
    title = "── Mycelium Network / Wood Wide Web ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _settings) in enumerate(self.MYCELIUM_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        marker = ">" if i == self.mycelium_menu_sel else " "
        attr = (curses.color_pair(3) | curses.A_BOLD
                if i == self.mycelium_menu_sel
                else curses.color_pair(7))
        line = f" {marker} {name:30s}"
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 3], attr)
        except curses.error:
            pass
        desc_attr = (curses.color_pair(6) if i == self.mycelium_menu_sel
                     else curses.color_pair(7) | curses.A_DIM)
        try:
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8], desc_attr)
        except curses.error:
            pass

    # Legend
    legend_y = 3 + len(self.MYCELIUM_PRESETS) * 2 + 1
    if legend_y < max_y - 5:
        legend_lines = [
            "Above:  || trunk  {{ canopy  /\\ mushroom  ** spore",
            "Ground: :: surface  %% organic  .. topsoil  ,, subsoil  == clay  ## rock",
            "Under:  ~~ hypha  @@ hub  <> mycorrhiza  rr root  r> root tip  ~~ water",
            "Packets: C  carbon  P  phosphorus  N  nitrogen  !  signal  o  water",
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


def _draw_mycelium(self, max_y: int, max_x: int):
    """Draw the active Mycelium Network simulation."""
    self.stdscr.erase()
    grid = self.mycelium_grid
    nutrient = self.mycelium_nutrient
    entities = self.mycelium_entities
    trees = self.mycelium_trees
    rows, cols = self.mycelium_rows, self.mycelium_cols
    state = "RUN" if self.mycelium_running else "PAUSED"
    view = self.mycelium_view
    stats = self.mycelium_stats
    season = self.mycelium_season
    moisture = self.mycelium_moisture
    surface_row = self.mycelium_surface

    # Title bar
    season_icon = {"spring": "Spr", "summer": "Sum", "autumn": "Aut", "winter": "Win"}.get(season, "?")
    title = (f" Mycelium: {self.mycelium_preset_name}  |  gen {self.mycelium_generation}"
             f"  |  {season_icon}  hyphae={stats['hypha_cells']} conn={stats['connections']}"
             f" trees={stats['trees_alive']}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    # Color mapping
    cell_colors = {
        CELL_AIR: curses.color_pair(7),
        CELL_SURFACE: curses.color_pair(2) | curses.A_DIM,      # dim yellow — leaf litter
        CELL_TOPSOIL: curses.color_pair(2) | curses.A_DIM,      # dim brown-ish
        CELL_SUBSOIL: curses.color_pair(7) | curses.A_DIM,      # dim gray
        CELL_CLAY: curses.color_pair(3) | curses.A_DIM,          # dim orange
        CELL_ROCK: curses.color_pair(7),                          # white
        CELL_ROOT: curses.color_pair(2),                          # yellow — roots
        CELL_ROOT_TIP: curses.color_pair(2) | curses.A_BOLD,    # bright yellow — active tips
        CELL_HYPHA: curses.color_pair(7) | curses.A_BOLD,        # bright white — hyphae
        CELL_HYPHA_HUB: curses.color_pair(6) | curses.A_BOLD,   # bright cyan — hubs
        CELL_MYCORRHIZA: curses.color_pair(1) | curses.A_BOLD,   # bright green — connections
        CELL_ORGANIC: curses.color_pair(3),                       # orange — organic matter
        CELL_DECOMPOSING: curses.color_pair(3) | curses.A_DIM,   # dim orange — decomposing
        CELL_MUSHROOM: curses.color_pair(5) | curses.A_BOLD,     # bright magenta — mushrooms!
        CELL_TRUNK: curses.color_pair(2),                         # brown/yellow — trunk
        CELL_CANOPY: curses.color_pair(1) | curses.A_BOLD,       # bright green — leaves
        CELL_WATER: curses.color_pair(4) | curses.A_BOLD,        # bright blue — water
        CELL_SPORE: curses.color_pair(5),                         # magenta — spores
    }

    ent_colors = {
        ENT_CARBON: curses.color_pair(1) | curses.A_BOLD,       # green — carbon
        ENT_PHOSPHORUS: curses.color_pair(4) | curses.A_BOLD,   # blue — phosphorus
        ENT_NITROGEN: curses.color_pair(6) | curses.A_BOLD,     # cyan — nitrogen
        ENT_SIGNAL: curses.color_pair(5) | curses.A_BOLD,       # magenta — signal
        ENT_WATER_DROP: curses.color_pair(4),                    # blue — water
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

            if view == "network":
                # Check for entity first
                ent = ent_map.get((r, c))
                if ent:
                    ch = ENT_CHARS.get(ent["type"], "? ")
                    attr = ent_colors.get(ent["type"], curses.color_pair(7))
                else:
                    ct = grid[r][c]
                    if ct == CELL_AIR:
                        continue  # skip empty air
                    ch = CELL_CHARS.get(ct, "??")
                    attr = cell_colors.get(ct, curses.color_pair(7))

            elif view == "moisture":
                if r < surface_row:
                    continue
                m = _moisture_at_depth(r, surface_row, rows, moisture)
                if m > 0.7:
                    ch, attr = "##", curses.color_pair(4) | curses.A_BOLD
                elif m > 0.4:
                    ch, attr = "==", curses.color_pair(4)
                elif m > 0.2:
                    ch, attr = "..", curses.color_pair(4) | curses.A_DIM
                else:
                    ch, attr = "  ", curses.color_pair(7) | curses.A_DIM

            else:  # nutrients view
                if r < surface_row:
                    continue
                n = nutrient[r][c] if r < rows and c < cols else 0
                if n > 0.6:
                    ch, attr = "##", curses.color_pair(1) | curses.A_BOLD
                elif n > 0.3:
                    ch, attr = "==", curses.color_pair(1)
                elif n > 0.1:
                    ch, attr = "..", curses.color_pair(1) | curses.A_DIM
                else:
                    continue

            try:
                self.stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    # Tree status indicators on title row or second-to-last
    tree_y = max_y - 3
    if tree_y > 1 and trees:
        tree_info = " Trees:"
        for i, t in enumerate(trees):
            star = "*" if t["is_mother"] else " "
            stress_ch = "!" if t["stress"] > 0.3 else " "
            tree_info += f" [{star}T{i+1} h={t['health']:.1f}{stress_ch} C={t['carbon_stored']:.0f}]"
        try:
            self.stdscr.addstr(tree_y, 0, tree_info[:max_x - 1],
                               curses.color_pair(7) | curses.A_DIM)
        except curses.error:
            pass

    # Environment status line
    env_y = max_y - 2
    if env_y > 1:
        env_line = (f" Season={season}  Moisture={moisture:.1f}"
                    f"  Organic={stats['organic_matter']}  Mushrooms={stats['mushrooms']}"
                    f"  Transfers={stats['nutrients_transferred']}"
                    f"  Decomposed={stats['total_decomposed']}")
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
            hint = " [Space]=play [n]=step [v]=view [w]=rain [d]=drought [o]=organic [s]=season [+/-]=speed [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register mycelium network mode methods on the App class."""
    App._enter_mycelium_mode = _enter_mycelium_mode
    App._exit_mycelium_mode = _exit_mycelium_mode
    App._mycelium_init = _mycelium_init
    App._mycelium_step = _mycelium_step
    App._handle_mycelium_menu_key = _handle_mycelium_menu_key
    App._handle_mycelium_key = _handle_mycelium_key
    App._draw_mycelium_menu = _draw_mycelium_menu
    App._draw_mycelium = _draw_mycelium
    App.MYCELIUM_PRESETS = MYCELIUM_PRESETS
