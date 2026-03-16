"""Mode: firefly — Firefly Synchronization & Bioluminescence Simulation.

Thousands of firefly agents distributed across a nighttime landscape, each with
an internal integrate-and-fire oscillator.  When a firefly's phase hits threshold
it flashes, and nearby fireflies who see the flash nudge their own phase forward
— producing the real-world phenomenon where entire forests of fireflies
spontaneously synchronize their blinking from initial chaos.

Implements the Peskin / Mirollo-Strogatz integrate-and-fire model with spatial
coupling, species-specific flash patterns, predator femme-fatale *Photuris*
fireflies, and a Kuramoto-style order parameter tracking synchronization.
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

FIREFLY_PRESETS = [
    ("Southeast Asian Mangrove",
     "Dense population in mangrove trees — mass synchrony emerges quickly",
     "mangrove"),
    ("Appalachian Meadow",
     "Mixed Photinus species with distinct flash patterns in open meadow",
     "meadow"),
    ("Femme Fatale Hunting",
     "Predator Photuris mimics flash patterns to lure prey fireflies",
     "femme_fatale"),
    ("Sync Emergence",
     "Watch initial chaos self-organize into global synchronization",
     "sync_emerge"),
    ("Desynchronization Shock",
     "Fully synced swarm hit by a perturbation — recovery dynamics",
     "desync_shock"),
    ("Competitive Signaling",
     "Males compete via flash brightness and timing for female attention",
     "competitive"),
]


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

# Species
SPECIES_PHOTINUS_A = 0   # single pulse
SPECIES_PHOTINUS_B = 1   # double blink
SPECIES_PHOTINUS_C = 2   # rhythmic triplet
SPECIES_PHOTURIS   = 3   # predator / femme fatale

SPECIES_NAMES = ["P. carolinus", "P. pyralis", "P. consimilis", "Photuris (predator)"]

# Flash patterns: list of (on_fraction, off_fraction) within one cycle
FLASH_PATTERNS = {
    SPECIES_PHOTINUS_A: [(0.0, 0.12)],                          # single pulse
    SPECIES_PHOTINUS_B: [(0.0, 0.08), (0.15, 0.23)],            # double blink
    SPECIES_PHOTINUS_C: [(0.0, 0.06), (0.12, 0.18), (0.24, 0.30)],  # triplet
    SPECIES_PHOTURIS:   [(0.0, 0.12)],                          # mimics (dynamic)
}

# Terrain types
TERRAIN_EMPTY = 0
TERRAIN_TREE = 1
TERRAIN_BUSH = 2
TERRAIN_GRASS = 3
TERRAIN_WATER = 4

# Firefly states
STATE_RESTING = 0
STATE_CHARGING = 1   # phase building up
STATE_FLASHING = 2
STATE_COOLDOWN = 3

# View modes
VIEW_NIGHTSCAPE = "nightscape"
VIEW_PHASE_MAP = "phase_map"
VIEW_SYNC_GRAPH = "sync_graph"

VIEWS = [VIEW_NIGHTSCAPE, VIEW_PHASE_MAP, VIEW_SYNC_GRAPH]


# ══════════════════════════════════════════════════════════════════════
#  Firefly agent
# ══════════════════════════════════════════════════════════════════════

class _Firefly:
    __slots__ = ("x", "y", "phase", "natural_freq", "species",
                 "flash_timer", "flash_bright", "state",
                 "coupling_strength", "perception_radius",
                 "is_predator", "prey_target", "alive",
                 "energy", "gender", "attracted_to",
                 "mimic_species", "cooldown")

    def __init__(self, x, y, species=SPECIES_PHOTINUS_A):
        self.x = x
        self.y = y
        self.phase = random.random()        # 0..1
        self.natural_freq = 0.02 + random.gauss(0, 0.003)  # phase increment/tick
        self.species = species
        self.flash_timer = 0.0
        self.flash_bright = 0.0
        self.state = STATE_CHARGING
        self.coupling_strength = 0.05
        self.perception_radius = 8.0
        self.is_predator = (species == SPECIES_PHOTURIS)
        self.prey_target = None
        self.alive = True
        self.energy = 1.0
        self.gender = random.choice([0, 1])  # 0=male, 1=female
        self.attracted_to = None
        self.mimic_species = SPECIES_PHOTINUS_A
        self.cooldown = 0.0


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_firefly_mode(self):
    self.firefly_mode = True
    self.firefly_menu = True
    self.firefly_menu_sel = 0

def _exit_firefly_mode(self):
    self.firefly_mode = False
    self.firefly_menu = False
    self.firefly_running = False
    for attr in list(vars(self)):
        if attr.startswith('firefly_') and attr != 'firefly_mode':
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _firefly_init(self, preset_idx: int):
    name, desc, preset_id = FIREFLY_PRESETS[preset_idx]
    self.firefly_preset_name = name
    self.firefly_preset_id = preset_id
    self.firefly_preset_idx = preset_idx

    max_y, max_x = self.stdscr.getmaxyx()
    self.firefly_rows = max(20, max_y - 4)
    self.firefly_cols = max(40, max_x - 1)

    self.firefly_generation = 0
    self.firefly_view = VIEW_NIGHTSCAPE
    self.firefly_running = False

    # Sync tracking
    self.firefly_order_history = []   # Kuramoto order parameter over time
    self.firefly_max_history = 200

    # Terrain grid
    self.firefly_terrain = [[TERRAIN_EMPTY] * self.firefly_cols
                            for _ in range(self.firefly_rows)]

    # Preset-specific parameters
    if preset_id == "mangrove":
        n_fireflies = min(800, self.firefly_rows * self.firefly_cols // 6)
        tree_density = 0.15
        bush_density = 0.08
        water_density = 0.12
        species_mix = {SPECIES_PHOTINUS_A: 1.0}
        coupling = 0.08
        pred_count = 0
    elif preset_id == "meadow":
        n_fireflies = min(500, self.firefly_rows * self.firefly_cols // 8)
        tree_density = 0.04
        bush_density = 0.12
        water_density = 0.02
        species_mix = {SPECIES_PHOTINUS_A: 0.4, SPECIES_PHOTINUS_B: 0.35,
                       SPECIES_PHOTINUS_C: 0.25}
        coupling = 0.04
        pred_count = 0
    elif preset_id == "femme_fatale":
        n_fireflies = min(400, self.firefly_rows * self.firefly_cols // 8)
        tree_density = 0.06
        bush_density = 0.10
        water_density = 0.03
        species_mix = {SPECIES_PHOTINUS_A: 0.5, SPECIES_PHOTINUS_B: 0.3}
        coupling = 0.05
        pred_count = max(5, n_fireflies // 20)
    elif preset_id == "sync_emerge":
        n_fireflies = min(600, self.firefly_rows * self.firefly_cols // 6)
        tree_density = 0.10
        bush_density = 0.08
        water_density = 0.02
        species_mix = {SPECIES_PHOTINUS_A: 1.0}
        coupling = 0.06
        pred_count = 0
    elif preset_id == "desync_shock":
        n_fireflies = min(600, self.firefly_rows * self.firefly_cols // 6)
        tree_density = 0.10
        bush_density = 0.08
        water_density = 0.02
        species_mix = {SPECIES_PHOTINUS_A: 1.0}
        coupling = 0.07
        pred_count = 0
    else:  # competitive
        n_fireflies = min(500, self.firefly_rows * self.firefly_cols // 7)
        tree_density = 0.05
        bush_density = 0.10
        water_density = 0.02
        species_mix = {SPECIES_PHOTINUS_A: 0.5, SPECIES_PHOTINUS_B: 0.5}
        coupling = 0.03
        pred_count = 0

    self.firefly_coupling = coupling
    self.firefly_pred_count = pred_count
    self.firefly_flash_count = 0       # flashes this tick
    self.firefly_total_flashes = 0
    self.firefly_kills = 0

    # Build terrain
    _firefly_make_terrain(self, tree_density, bush_density, water_density)

    # Create fireflies
    _firefly_make_fireflies(self, n_fireflies, species_mix, pred_count)

    # For desync_shock, start synchronized then perturb later
    if preset_id == "desync_shock":
        for f in self.firefly_flies:
            f.phase = 0.5 + random.gauss(0, 0.02)
            f.phase = f.phase % 1.0
        self.firefly_shock_applied = False
        self.firefly_shock_gen = 80
    else:
        self.firefly_shock_applied = True
        self.firefly_shock_gen = -1


def _firefly_make_terrain(self, tree_density, bush_density, water_density):
    rows, cols = self.firefly_rows, self.firefly_cols
    terrain = self.firefly_terrain

    # Place water bodies (clusters)
    n_water = int(rows * cols * water_density)
    seeds = random.randint(1, max(1, n_water // 20))
    for _ in range(seeds):
        cx, cy = random.randint(0, cols - 1), random.randint(0, rows - 1)
        size = random.randint(3, 8)
        for _ in range(n_water // seeds):
            wx = cx + random.randint(-size, size)
            wy = cy + random.randint(-size // 2, size // 2)
            if 0 <= wy < rows and 0 <= wx < cols:
                terrain[wy][wx] = TERRAIN_WATER

    # Place trees (clustered around groves)
    n_trees = int(rows * cols * tree_density)
    groves = random.randint(2, max(3, n_trees // 15))
    per_grove = n_trees // groves
    for _ in range(groves):
        gx, gy = random.randint(0, cols - 1), random.randint(0, rows - 1)
        for _ in range(per_grove):
            tx = gx + random.randint(-6, 6)
            ty = gy + random.randint(-4, 4)
            if 0 <= ty < rows and 0 <= tx < cols and terrain[ty][tx] == TERRAIN_EMPTY:
                terrain[ty][tx] = TERRAIN_TREE

    # Place bushes
    n_bushes = int(rows * cols * bush_density)
    for _ in range(n_bushes):
        bx = random.randint(0, cols - 1)
        by = random.randint(0, rows - 1)
        if terrain[by][bx] == TERRAIN_EMPTY:
            terrain[by][bx] = TERRAIN_BUSH

    # Fill remaining with grass
    for r in range(rows):
        for c in range(cols):
            if terrain[r][c] == TERRAIN_EMPTY:
                if random.random() < 0.3:
                    terrain[r][c] = TERRAIN_GRASS


def _firefly_make_fireflies(self, count, species_mix, pred_count):
    rows, cols = self.firefly_rows, self.firefly_cols
    terrain = self.firefly_terrain
    flies = []

    # Build species choice list
    species_list = []
    for sp, weight in species_mix.items():
        species_list.extend([sp] * int(weight * 100))
    if not species_list:
        species_list = [SPECIES_PHOTINUS_A]

    # Prefer perching on trees/bushes
    perch_cells = []
    ground_cells = []
    for r in range(rows):
        for c in range(cols):
            t = terrain[r][c]
            if t == TERRAIN_TREE or t == TERRAIN_BUSH:
                perch_cells.append((c, r))
            elif t != TERRAIN_WATER:
                ground_cells.append((c, r))

    all_cells = perch_cells * 3 + ground_cells  # weight toward perches
    random.shuffle(all_cells)

    for i in range(count):
        if i < len(all_cells):
            x, y = all_cells[i]
        else:
            x = random.randint(0, cols - 1)
            y = random.randint(0, rows - 1)
        sp = random.choice(species_list)
        f = _Firefly(x, y, sp)
        f.coupling_strength = self.firefly_coupling
        # Vary natural frequency by species
        if sp == SPECIES_PHOTINUS_B:
            f.natural_freq = 0.018 + random.gauss(0, 0.002)
        elif sp == SPECIES_PHOTINUS_C:
            f.natural_freq = 0.015 + random.gauss(0, 0.002)
        flies.append(f)

    # Add predators
    for _ in range(pred_count):
        if ground_cells:
            x, y = random.choice(ground_cells)
        else:
            x, y = random.randint(0, cols - 1), random.randint(0, rows - 1)
        pred = _Firefly(x, y, SPECIES_PHOTURIS)
        pred.is_predator = True
        pred.natural_freq = 0.02
        pred.coupling_strength = 0.0  # doesn't sync
        pred.perception_radius = 12.0
        pred.mimic_species = random.choice(list(species_mix.keys()))
        flies.append(pred)

    self.firefly_flies = flies


# ══════════════════════════════════════════════════════════════════════
#  Simulation Step
# ══════════════════════════════════════════════════════════════════════

def _firefly_step(self):
    self.firefly_generation += 1
    flies = self.firefly_flies
    rows, cols = self.firefly_rows, self.firefly_cols

    # Apply desync shock if needed
    if (not self.firefly_shock_applied and
            self.firefly_generation >= self.firefly_shock_gen):
        self.firefly_shock_applied = True
        # Perturb ~40% of fireflies with random phase offsets
        for f in flies:
            if random.random() < 0.4:
                f.phase = random.random()

    # Build spatial grid for fast neighbor lookup
    grid = {}
    for f in flies:
        if not f.alive:
            continue
        gx, gy = int(f.x) // 4, int(f.y) // 4
        grid.setdefault((gx, gy), []).append(f)

    flash_count = 0

    # Phase 1: advance phase, detect flashing
    flashers = []
    for f in flies:
        if not f.alive:
            continue

        if f.cooldown > 0:
            f.cooldown -= 1
            f.flash_bright = max(0, f.flash_bright - 0.15)
            f.state = STATE_COOLDOWN
            continue

        # Advance phase
        f.phase += f.natural_freq
        f.flash_bright = max(0, f.flash_bright - 0.1)

        # Check if flashing
        if f.phase >= 1.0:
            f.phase = 0.0
            f.state = STATE_FLASHING
            f.flash_timer = 0.0
            flashers.append(f)
            flash_count += 1
            # Set brightness based on pattern
            pattern = FLASH_PATTERNS.get(
                f.mimic_species if f.is_predator else f.species,
                FLASH_PATTERNS[SPECIES_PHOTINUS_A])
            f.flash_bright = 1.0
            f.cooldown = 3  # brief refractory period
        else:
            f.state = STATE_CHARGING

    self.firefly_flash_count = flash_count
    self.firefly_total_flashes += flash_count

    # Phase 2: coupling — nearby fireflies nudge phase forward on seeing flash
    for flasher in flashers:
        gx, gy = int(flasher.x) // 4, int(flasher.y) // 4
        pr = flasher.perception_radius
        gr = int(pr / 4) + 1
        for dx in range(-gr, gr + 1):
            for dy in range(-gr, gr + 1):
                neighbors = grid.get((gx + dx, gy + dy))
                if not neighbors:
                    continue
                for n in neighbors:
                    if n is flasher or not n.alive or n.cooldown > 0:
                        continue
                    dist = math.hypot(n.x - flasher.x, n.y - flasher.y)
                    if dist > pr or dist < 0.5:
                        continue

                    # Line-of-sight: check for blocking terrain (trees block)
                    blocked = False
                    if dist > 3:
                        mid_x = int((flasher.x + n.x) / 2)
                        mid_y = int((flasher.y + n.y) / 2)
                        if (0 <= mid_y < rows and 0 <= mid_x < cols and
                                self.firefly_terrain[mid_y][mid_x] == TERRAIN_TREE):
                            blocked = True
                    if blocked:
                        continue

                    # Phase advance (Mirollo-Strogatz coupling)
                    strength = n.coupling_strength / (1.0 + dist * 0.15)

                    # Same species couple more strongly
                    if n.species == flasher.species or n.is_predator:
                        strength *= 1.5

                    n.phase = min(n.phase + strength, 1.0)

                    # Predator attraction
                    if n.is_predator and not flasher.is_predator:
                        n.attracted_to = flasher

    # Phase 3: predator behavior — move toward prey and attack
    for f in flies:
        if not f.alive or not f.is_predator:
            continue

        # Move toward attracted target
        if f.attracted_to is not None and f.attracted_to.alive:
            target = f.attracted_to
            dx = target.x - f.x
            dy = target.y - f.y
            dist = math.hypot(dx, dy)
            if dist < 1.5:
                # Attack!
                target.alive = False
                self.firefly_kills += 1
                f.energy = min(f.energy + 0.3, 1.0)
                f.attracted_to = None
            elif dist > 0:
                speed = 0.5
                f.x += (dx / dist) * speed
                f.y += (dy / dist) * speed
                f.x = max(0, min(cols - 1, f.x))
                f.y = max(0, min(rows - 1, f.y))
        else:
            f.attracted_to = None
            # Slow random wander
            if random.random() < 0.3:
                f.x += random.uniform(-0.5, 0.5)
                f.y += random.uniform(-0.5, 0.5)
                f.x = max(0, min(cols - 1, f.x))
                f.y = max(0, min(rows - 1, f.y))

        # Switch mimic pattern occasionally
        if random.random() < 0.01:
            f.mimic_species = random.choice(
                [SPECIES_PHOTINUS_A, SPECIES_PHOTINUS_B, SPECIES_PHOTINUS_C])

    # Phase 4: slight random drift for non-predator fireflies
    for f in flies:
        if not f.alive or f.is_predator:
            continue
        if random.random() < 0.05:
            f.x += random.uniform(-0.3, 0.3)
            f.y += random.uniform(-0.3, 0.3)
            f.x = max(0, min(cols - 1, f.x))
            f.y = max(0, min(rows - 1, f.y))

    # Phase 5: compute Kuramoto order parameter
    alive_flies = [f for f in flies if f.alive and not f.is_predator]
    if alive_flies:
        sum_cos = sum(math.cos(2 * math.pi * f.phase) for f in alive_flies)
        sum_sin = sum(math.sin(2 * math.pi * f.phase) for f in alive_flies)
        n = len(alive_flies)
        order_param = math.hypot(sum_cos / n, sum_sin / n)
    else:
        order_param = 0.0

    self.firefly_order_param = order_param
    self.firefly_order_history.append(order_param)
    if len(self.firefly_order_history) > self.firefly_max_history:
        self.firefly_order_history.pop(0)


# ══════════════════════════════════════════════════════════════════════
#  Input Handling
# ══════════════════════════════════════════════════════════════════════

def _handle_firefly_menu_key(self, key):
    if key == curses.KEY_DOWN or key == ord('j'):
        self.firefly_menu_sel = (self.firefly_menu_sel + 1) % len(FIREFLY_PRESETS)
    elif key == curses.KEY_UP or key == ord('k'):
        self.firefly_menu_sel = (self.firefly_menu_sel - 1) % len(FIREFLY_PRESETS)
    elif key in (ord('\n'), ord(' ')):
        self.firefly_menu = False
        _firefly_init(self, self.firefly_menu_sel)
        self.firefly_running = True


def _handle_firefly_key(self, key):
    if key == ord(' '):
        self.firefly_running = not self.firefly_running
    elif key == ord('v'):
        idx = VIEWS.index(self.firefly_view)
        self.firefly_view = VIEWS[(idx + 1) % len(VIEWS)]
    elif key == ord('r'):
        self.firefly_menu = True
        self.firefly_menu_sel = self.firefly_preset_idx
    elif key == ord('q'):
        self._exit_firefly_mode()


# ══════════════════════════════════════════════════════════════════════
#  Rendering — Menu
# ══════════════════════════════════════════════════════════════════════

def _draw_firefly_menu(self, max_y: int, max_x: int):
    title = "═══ Firefly Synchronization & Bioluminescence ═══"
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Integrate-and-fire oscillators • Mirollo-Strogatz coupling"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(subtitle)) // 2),
                           subtitle[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass

    for i, (name, desc, _) in enumerate(FIREFLY_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        prefix = " ● " if i == self.firefly_menu_sel else "   "
        label = f"{prefix}{name}"
        attr = curses.A_REVERSE | curses.A_BOLD if i == self.firefly_menu_sel else 0
        try:
            self.stdscr.addstr(y, 2, label[:max_x - 3], attr)
        except curses.error:
            pass
        if i == self.firefly_menu_sel and y + 1 < max_y - 2:
            try:
                self.stdscr.addstr(y + 1, 6, desc[:max_x - 7], curses.A_DIM)
            except curses.error:
                pass

    help_y = max_y - 1
    help_text = " ↑↓ Select   ENTER Start   Q Quit"
    try:
        self.stdscr.addstr(help_y, 0, help_text[:max_x - 1],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Rendering — Main dispatch
# ══════════════════════════════════════════════════════════════════════

def _draw_firefly(self, max_y: int, max_x: int):
    view = self.firefly_view
    if view == VIEW_NIGHTSCAPE:
        _draw_firefly_nightscape(self, max_y, max_x)
    elif view == VIEW_PHASE_MAP:
        _draw_firefly_phase_map(self, max_y, max_x)
    else:
        _draw_firefly_sync_graph(self, max_y, max_x)

    # Status bar
    alive = sum(1 for f in self.firefly_flies if f.alive)
    order = getattr(self, 'firefly_order_param', 0.0)
    gen = self.firefly_generation
    flashes = self.firefly_flash_count

    status = (f" Gen:{gen}  Alive:{alive}  Flashes:{flashes}"
              f"  Sync:{order:.3f}  View:{view.upper()}"
              f"  [{self.firefly_preset_name}]")
    kills = getattr(self, 'firefly_kills', 0)
    if kills > 0:
        status += f"  Kills:{kills}"

    try:
        self.stdscr.addstr(max_y - 1, 0, status[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    help_line = " SPACE Pause  V View  R Reset  Q Quit"
    if max_y - 2 > 1:
        try:
            self.stdscr.addstr(max_y - 2, 0, help_line[:max_x - 1],
                               curses.color_pair(7) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  View 1: Nightscape — dark field with flashing glyphs
# ══════════════════════════════════════════════════════════════════════

_TERRAIN_CHARS = {
    TERRAIN_EMPTY: ' ',
    TERRAIN_TREE: '♣',
    TERRAIN_BUSH: '♠',
    TERRAIN_GRASS: '·',
    TERRAIN_WATER: '~',
}

_FLASH_CHARS = ['·', '∘', '○', '◎', '●', '★', '✦', '✧']

def _draw_firefly_nightscape(self, max_y: int, max_x: int):
    rows = min(self.firefly_rows, max_y - 3)
    cols = min(self.firefly_cols, max_x)
    terrain = self.firefly_terrain

    # Draw dark terrain
    for r in range(rows):
        line = []
        for c in range(cols):
            t = terrain[r][c]
            ch = _TERRAIN_CHARS.get(t, ' ')
            line.append(ch)
        row_str = ''.join(line)
        try:
            self.stdscr.addstr(r, 0, row_str[:max_x - 1],
                               curses.color_pair(7) | curses.A_DIM)
        except curses.error:
            pass

    # Draw fireflies
    for f in self.firefly_flies:
        if not f.alive:
            continue
        fy, fx = int(f.y), int(f.x)
        if fy < 0 or fy >= rows or fx < 0 or fx >= cols:
            continue

        if f.flash_bright > 0.05:
            # Flashing — bright glyph
            intensity = min(1.0, f.flash_bright)
            idx = int(intensity * (len(_FLASH_CHARS) - 1))
            ch = _FLASH_CHARS[idx]

            if f.is_predator:
                # Red/magenta for predator
                attr = curses.color_pair(2) | curses.A_BOLD
            elif f.species == SPECIES_PHOTINUS_A:
                attr = curses.color_pair(4) | curses.A_BOLD  # green
            elif f.species == SPECIES_PHOTINUS_B:
                attr = curses.color_pair(3) | curses.A_BOLD  # yellow
            else:
                attr = curses.color_pair(5) | curses.A_BOLD  # cyan

            if intensity > 0.7:
                attr |= curses.A_BOLD
        else:
            # Dim / not flashing
            ch = '·'
            if f.is_predator:
                attr = curses.color_pair(2) | curses.A_DIM
            else:
                attr = curses.color_pair(7) | curses.A_DIM

        try:
            self.stdscr.addstr(fy, fx, ch, attr)
        except curses.error:
            pass

    # Title
    title = f" ✦ {self.firefly_preset_name} — Nightscape ✦ "
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1],
                           curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  View 2: Phase Map — heatmap of oscillator phases
# ══════════════════════════════════════════════════════════════════════

_PHASE_CHARS = " ░▒▓█"

def _draw_firefly_phase_map(self, max_y: int, max_x: int):
    rows = min(self.firefly_rows, max_y - 3)
    cols = min(self.firefly_cols, max_x)

    # Build phase accumulation grid
    phase_grid = [[0.0] * cols for _ in range(rows)]
    count_grid = [[0] * cols for _ in range(rows)]

    for f in self.firefly_flies:
        if not f.alive or f.is_predator:
            continue
        fy, fx = int(f.y), int(f.x)
        if 0 <= fy < rows and 0 <= fx < cols:
            phase_grid[fy][fx] += f.phase
            count_grid[fy][fx] += 1

    # Spread influence to neighboring cells for smoother map
    smooth = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            total = 0.0
            cnt = 0
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and count_grid[nr][nc] > 0:
                        w = 1.0 / (1.0 + abs(dr) + abs(dc))
                        total += (phase_grid[nr][nc] / count_grid[nr][nc]) * w
                        cnt += 1
            smooth[r][c] = total / max(1, cnt)

    # Render
    for r in range(rows):
        for c in range(cols):
            val = smooth[r][c]
            idx = int(val * (len(_PHASE_CHARS) - 1))
            idx = max(0, min(len(_PHASE_CHARS) - 1, idx))
            ch = _PHASE_CHARS[idx]

            # Color by phase region
            if val < 0.25:
                attr = curses.color_pair(5)        # cyan — low phase
            elif val < 0.5:
                attr = curses.color_pair(4)        # green — mid-low
            elif val < 0.75:
                attr = curses.color_pair(3)        # yellow — mid-high
            else:
                attr = curses.color_pair(2) | curses.A_BOLD  # red — near threshold

            try:
                self.stdscr.addstr(r, c, ch, attr)
            except curses.error:
                pass

    # Mark flashing fireflies
    for f in self.firefly_flies:
        if not f.alive or f.flash_bright < 0.5:
            continue
        fy, fx = int(f.y), int(f.x)
        if 0 <= fy < rows and 0 <= fx < cols:
            try:
                self.stdscr.addstr(fy, fx, '★',
                                   curses.color_pair(4) | curses.A_BOLD)
            except curses.error:
                pass

    title = f" Phase Map — Oscillator Phases [0→1] "
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  View 3: Sync Graph — Kuramoto order parameter over time
# ══════════════════════════════════════════════════════════════════════

def _draw_firefly_sync_graph(self, max_y: int, max_x: int):
    history = self.firefly_order_history
    graph_height = max_y - 6
    graph_width = min(max_x - 8, self.firefly_max_history)

    if graph_height < 5 or graph_width < 10:
        try:
            self.stdscr.addstr(1, 1, "Terminal too small for graph",
                               curses.A_DIM)
        except curses.error:
            pass
        return

    title = " Kuramoto Order Parameter (Synchronization) "
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass

    # Draw axis
    x_off = 6
    y_off = 2
    for r in range(graph_height):
        # Y axis label
        val = 1.0 - (r / max(1, graph_height - 1))
        if r % max(1, graph_height // 4) == 0:
            label = f"{val:.1f}│"
        else:
            label = "    │"
        try:
            self.stdscr.addstr(y_off + r, 0, label[:x_off],
                               curses.color_pair(7))
        except curses.error:
            pass

    # X axis
    axis_y = y_off + graph_height
    try:
        self.stdscr.addstr(axis_y, x_off, "└" + "─" * min(graph_width, max_x - x_off - 2),
                           curses.color_pair(7))
    except curses.error:
        pass
    try:
        self.stdscr.addstr(axis_y + 1, x_off, "Time →",
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass

    # Labels
    try:
        self.stdscr.addstr(y_off - 1, x_off, "1.0 = Full Sync",
                           curses.color_pair(4) | curses.A_DIM)
    except curses.error:
        pass

    # Plot data
    if len(history) < 2:
        try:
            self.stdscr.addstr(y_off + graph_height // 2, x_off + 2,
                               "Collecting data...", curses.A_DIM)
        except curses.error:
            pass
        return

    # Take last graph_width points
    data = history[-graph_width:]

    for i, val in enumerate(data):
        col = x_off + i
        if col >= max_x - 1:
            break
        row = y_off + int((1.0 - val) * (graph_height - 1))
        row = max(y_off, min(y_off + graph_height - 1, row))

        # Color by sync level
        if val > 0.8:
            attr = curses.color_pair(4) | curses.A_BOLD   # green — synced
            ch = '█'
        elif val > 0.5:
            attr = curses.color_pair(3)                     # yellow — partial
            ch = '▓'
        elif val > 0.2:
            attr = curses.color_pair(6)                     # dim — low sync
            ch = '▒'
        else:
            attr = curses.color_pair(2) | curses.A_DIM      # red — chaos
            ch = '░'

        try:
            self.stdscr.addstr(row, col, ch, attr)
        except curses.error:
            pass

    # Current order parameter display
    current = history[-1] if history else 0.0
    sync_label = f" R = {current:.4f} "
    if current > 0.8:
        sync_attr = curses.color_pair(4) | curses.A_BOLD
        state_label = "SYNCHRONIZED"
    elif current > 0.5:
        sync_attr = curses.color_pair(3) | curses.A_BOLD
        state_label = "PARTIAL SYNC"
    elif current > 0.2:
        sync_attr = curses.color_pair(6)
        state_label = "LOW COHERENCE"
    else:
        sync_attr = curses.color_pair(2) | curses.A_BOLD
        state_label = "DESYNCHRONIZED"

    try:
        self.stdscr.addstr(axis_y + 1, max_x - len(sync_label) - len(state_label) - 4,
                           sync_label, sync_attr)
        self.stdscr.addstr(axis_y + 1,
                           max_x - len(state_label) - 2,
                           state_label, sync_attr)
    except curses.error:
        pass

    # Phase distribution histogram (bottom right)
    alive_flies = [f for f in self.firefly_flies
                   if f.alive and not f.is_predator]
    if alive_flies and axis_y + 3 < max_y - 2:
        bins = [0] * 10
        for f in alive_flies:
            b = min(9, int(f.phase * 10))
            bins[b] += 1
        max_bin = max(bins) if bins else 1
        hist_label = " Phase distribution: "
        try:
            self.stdscr.addstr(axis_y - 2, x_off, hist_label[:max_x - x_off - 1],
                               curses.A_DIM)
        except curses.error:
            pass
        bar_chars = "▁▂▃▄▅▆▇█"
        hist_str = ""
        for b in bins:
            idx = int((b / max(1, max_bin)) * (len(bar_chars) - 1))
            hist_str += bar_chars[idx]
        try:
            self.stdscr.addstr(axis_y - 1, x_off,
                               f" {hist_str} "[:max_x - x_off - 1],
                               curses.color_pair(4))
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register firefly synchronization mode methods on the App class."""
    App.FIREFLY_PRESETS = FIREFLY_PRESETS
    App._enter_firefly_mode = _enter_firefly_mode
    App._exit_firefly_mode = _exit_firefly_mode
    App._firefly_init = _firefly_init
    App._firefly_make_terrain = _firefly_make_terrain
    App._firefly_make_fireflies = _firefly_make_fireflies
    App._firefly_step = _firefly_step
    App._handle_firefly_menu_key = _handle_firefly_menu_key
    App._handle_firefly_key = _handle_firefly_key
    App._draw_firefly_menu = _draw_firefly_menu
    App._draw_firefly = _draw_firefly
    App._draw_firefly_nightscape = _draw_firefly_nightscape
    App._draw_firefly_phase_map = _draw_firefly_phase_map
    App._draw_firefly_sync_graph = _draw_firefly_sync_graph
