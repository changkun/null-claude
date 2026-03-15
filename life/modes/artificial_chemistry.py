"""Mode: artificial chemistry — spontaneous emergence of self-replicating molecules.

Cells represent abstract molecules (short rule-strings) that drift, collide,
and react via pattern-matching rules.  Reactions can cleave, concatenate, or
transform molecules.  Over time, autocatalytic cycles form — sets of molecules
that catalyze each other's production — and occasionally genuine self-replicators
emerge from the noise.

The display shows the primordial soup in real-time with color-coded molecule
types, plus live metrics tracking molecular diversity, longest polymer,
autocatalytic cycle count, and replicator detection.
"""

import curses
import math
import random
import time
from collections import Counter, defaultdict

# ── Molecule alphabet & constants ────────────────────────────────────
ALPHABET = "ABCDEFGH"
MAX_MOL_LEN = 16       # max molecule string length
MIN_MOL_LEN = 1
ENERGY_PER_BOND = 0.3  # energy released per bond formed

# Cell types for display
CELL_EMPTY = 0
CELL_MONOMER = 1       # single letter molecule (len 1-2)
CELL_SHORT = 2         # short polymer (len 3-4)
CELL_MEDIUM = 3        # medium polymer (len 5-8)
CELL_LONG = 4          # long polymer (len 9-12)
CELL_REPLICATOR = 5    # detected self-replicator
CELL_CATALYST = 6      # part of autocatalytic cycle
CELL_FOOD = 7          # raw "food" monomer (energy source)

CELL_CHARS = {
    CELL_EMPTY: "  ",
    CELL_MONOMER: "· ",
    CELL_SHORT: "∘∘",
    CELL_MEDIUM: "██",
    CELL_LONG: "▓▓",
    CELL_REPLICATOR: "◆◆",
    CELL_CATALYST: "○○",
    CELL_FOOD: "░░",
}

CELL_NAMES = {
    CELL_EMPTY: "empty", CELL_MONOMER: "monomer", CELL_SHORT: "short",
    CELL_MEDIUM: "medium", CELL_LONG: "long", CELL_REPLICATOR: "replicator",
    CELL_CATALYST: "catalyst", CELL_FOOD: "food",
}

# ── Reaction rules ───────────────────────────────────────────────────
# Pattern-matching reactions: if two molecules collide and match a pattern,
# they react to produce products.

def _can_concatenate(m1, m2):
    """Check if two molecules can concatenate (join end-to-end)."""
    return len(m1) + len(m2) <= MAX_MOL_LEN

def _can_cleave(mol):
    """Check if a molecule can be cleaved (split)."""
    return len(mol) >= 3

def _complement(ch):
    """Return the 'complement' of a character (simple pairing rule)."""
    idx = ALPHABET.index(ch) if ch in ALPHABET else 0
    return ALPHABET[(idx + 4) % len(ALPHABET)]

def _template_match(template, target):
    """Check if target is a complement of template (like base pairing)."""
    if len(template) != len(target):
        return False
    return all(_complement(a) == b for a, b in zip(template, target))

def _find_catalytic_site(catalyst, substrate):
    """Check if catalyst has a subsequence that matches substrate prefix."""
    if len(catalyst) < 2 or len(substrate) < 2:
        return False
    # Catalyst must contain the complement of the substrate's first 2 chars
    target = _complement(substrate[0]) + _complement(substrate[1])
    return target in catalyst


# ── Presets ───────────────────────────────────────────────────────────
# (name, desc, density, food_rate, react_prob, cleave_prob, drift_speed,
#  mutation_rate, energy_decay, settings_dict)
ACHEM_PRESETS = [
    ("Primordial Soup",
     "Random monomers in warm broth — watch for spontaneous polymerization",
     0.15, 0.02, 0.4, 0.1, 0.3, 0.05, 0.005,
     {"template_replication": True, "catalysis": True}),

    ("Rich Broth",
     "Dense soup with high reactivity — fast polymer formation",
     0.30, 0.04, 0.6, 0.15, 0.2, 0.03, 0.003,
     {"template_replication": True, "catalysis": True}),

    ("Sparse Tidepools",
     "Low density pools — rare but significant encounters",
     0.06, 0.01, 0.5, 0.08, 0.5, 0.08, 0.008,
     {"template_replication": True, "catalysis": True}),

    ("RNA World",
     "Template-directed replication dominates — origin of information",
     0.12, 0.03, 0.3, 0.05, 0.25, 0.02, 0.004,
     {"template_replication": True, "catalysis": True, "template_bias": 0.4}),

    ("Metabolism First",
     "Catalytic cycles before replication — energy-driven self-organization",
     0.20, 0.05, 0.5, 0.2, 0.3, 0.06, 0.006,
     {"template_replication": False, "catalysis": True, "cycle_bonus": 0.3}),

    ("Lipid World",
     "Hydrophobic clustering — molecules aggregate into proto-cells",
     0.18, 0.02, 0.35, 0.12, 0.15, 0.04, 0.005,
     {"template_replication": True, "catalysis": True, "clustering": True}),

    ("Volcanic Vent",
     "Energy-rich environment with rapid turnover and high mutation",
     0.25, 0.06, 0.7, 0.25, 0.4, 0.10, 0.01,
     {"template_replication": True, "catalysis": True}),

    ("Minimal Abiogenesis",
     "Bare minimum — fewest assumptions, maximum emergence",
     0.08, 0.015, 0.25, 0.06, 0.35, 0.03, 0.003,
     {"template_replication": False, "catalysis": False}),
]


# ── Neighbor offsets ─────────────────────────────────────────────────
_NBRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NBRS8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


# ════════════════════════════════════════════════════════════════════════
#  Core mode functions
# ════════════════════════════════════════════════════════════════════════

def _enter_achem_mode(self):
    """Enter Artificial Chemistry mode — show preset menu."""
    self.achem_menu = True
    self.achem_menu_sel = 0
    self._flash("Artificial Chemistry — select a scenario")


def _exit_achem_mode(self):
    """Exit Artificial Chemistry mode."""
    self.achem_mode = False
    self.achem_menu = False
    self.achem_running = False
    self.achem_grid = []
    self.achem_energy = []
    self.achem_mol_history = []
    self._flash("Artificial Chemistry mode OFF")


def _achem_init(self, preset_idx: int):
    """Initialize the Artificial Chemistry simulation with the given preset."""
    (name, _desc, density, food_rate, react_prob, cleave_prob, drift_speed,
     mutation_rate, energy_decay, extras) = self.ACHEM_PRESETS[preset_idx]

    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(20, max_y - 4)
    cols = max(20, (max_x - 1) // 2)
    self.achem_rows = rows
    self.achem_cols = cols
    self.achem_preset_name = name
    self.achem_generation = 0
    self.achem_steps_per_frame = 1
    self.achem_density = density
    self.achem_food_rate = food_rate
    self.achem_react_prob = react_prob
    self.achem_cleave_prob = cleave_prob
    self.achem_drift_speed = drift_speed
    self.achem_mutation_rate = mutation_rate
    self.achem_energy_decay = energy_decay
    self.achem_extras = dict(extras)
    self.achem_view = "soup"  # soup / energy / diversity

    # Statistics
    self.achem_total_reactions = 0
    self.achem_total_replications = 0
    self.achem_longest_polymer = 0
    self.achem_cycle_count = 0
    self.achem_replicator_count = 0
    self.achem_mol_history = []       # (gen, diversity, longest, cycles, replicators)
    self.achem_replicator_seqs = set()  # known replicator sequences
    self.achem_catalytic_pairs = {}    # mol_seq -> set of products it catalyzes

    # Grids: each cell is either None (empty) or a molecule string
    self.achem_grid = [[None] * cols for _ in range(rows)]
    self.achem_energy = [[0.0] * cols for _ in range(rows)]
    self.achem_age = [[0] * cols for _ in range(rows)]

    # Populate with random monomers / short polymers
    for r in range(rows):
        for c in range(cols):
            if random.random() < density:
                length = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
                mol = "".join(random.choice(ALPHABET) for _ in range(length))
                self.achem_grid[r][c] = mol
                self.achem_energy[r][c] = random.uniform(0.3, 1.0)
            else:
                # Some food particles
                if random.random() < food_rate * 3:
                    self.achem_grid[r][c] = random.choice(ALPHABET)
                    self.achem_energy[r][c] = 1.0

    self.achem_mode = True
    self.achem_menu = False
    self.achem_running = False
    self._flash(f"Artificial Chemistry: {name} — Space to start")


def _achem_step(self):
    """Advance the artificial chemistry simulation by one step."""
    grid = self.achem_grid
    energy = self.achem_energy
    age_grid = self.achem_age
    rows, cols = self.achem_rows, self.achem_cols
    react_prob = self.achem_react_prob
    cleave_prob = self.achem_cleave_prob
    drift_speed = self.achem_drift_speed
    mutation_rate = self.achem_mutation_rate
    energy_decay = self.achem_energy_decay
    food_rate = self.achem_food_rate
    extras = self.achem_extras
    gen = self.achem_generation

    # ── 1. Drift / diffusion — molecules move randomly ────────────
    if random.random() < drift_speed:
        # Shuffle a fraction of molecules around
        moves = []
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] is not None and random.random() < drift_speed:
                    dr, dc = random.choice(_NBRS4)
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] is None:
                        moves.append((r, c, nr, nc))
        for r, c, nr, nc in moves:
            if grid[r][c] is not None and grid[nr][nc] is None:
                grid[nr][nc] = grid[r][c]
                energy[nr][nc] = energy[r][c]
                age_grid[nr][nc] = age_grid[r][c]
                grid[r][c] = None
                energy[r][c] = 0.0
                age_grid[r][c] = 0

    # ── 2. Reactions: collision-based ─────────────────────────────
    reacted = set()
    new_mols = []  # (r, c, molecule, energy)

    # Scan for adjacent molecule pairs
    for r in range(rows):
        for c in range(cols):
            if (r, c) in reacted or grid[r][c] is None:
                continue
            mol1 = grid[r][c]
            e1 = energy[r][c]

            # Check each neighbor for reaction partner
            nbrs = list(_NBRS4)
            random.shuffle(nbrs)
            for dr, dc in nbrs:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                if (nr, nc) in reacted or grid[nr][nc] is None:
                    continue
                mol2 = grid[nr][nc]
                e2 = energy[nr][nc]

                if random.random() > react_prob:
                    continue

                # Determine reaction type
                reaction_done = False

                # a) Template-directed replication
                if (extras.get("template_replication") and
                        len(mol1) >= 3 and len(mol2) >= 2):
                    template_bias = extras.get("template_bias", 0.2)
                    if random.random() < template_bias:
                        # mol1 acts as template, try to replicate
                        if e1 + e2 > 0.5:
                            # Create complement of mol1 using mol2 as raw material
                            comp_len = min(len(mol1), len(mol2) + 1)
                            comp = "".join(_complement(ch) for ch in mol1[:comp_len])
                            # Apply mutation
                            comp_list = list(comp)
                            for i in range(len(comp_list)):
                                if random.random() < mutation_rate:
                                    comp_list[i] = random.choice(ALPHABET)
                            comp = "".join(comp_list)
                            # Place product nearby
                            empties = []
                            for ddr, ddc in _NBRS8:
                                er, ec = r + ddr, c + ddc
                                if 0 <= er < rows and 0 <= ec < cols and grid[er][ec] is None:
                                    empties.append((er, ec))
                            if empties:
                                pr, pc = random.choice(empties)
                                new_mols.append((pr, pc, comp, 0.4))
                                energy[r][c] = max(0.0, e1 - 0.3)
                                # Consume part of mol2
                                if len(mol2) > 1:
                                    grid[nr][nc] = mol2[1:]
                                    energy[nr][nc] = max(0.0, e2 - 0.2)
                                else:
                                    grid[nr][nc] = None
                                    energy[nr][nc] = 0.0
                                reacted.add((r, c))
                                reacted.add((nr, nc))
                                self.achem_total_replications += 1
                                reaction_done = True
                                # Track potential replicator
                                if _template_match(mol1, comp):
                                    self.achem_replicator_seqs.add(mol1)
                                break

                if reaction_done:
                    continue

                # b) Catalysis
                if extras.get("catalysis") and len(mol1) >= 3:
                    if _find_catalytic_site(mol1, mol2):
                        # mol1 catalyzes transformation of mol2
                        if e1 > 0.2:
                            # Transform mol2: shift each char
                            transformed = "".join(
                                ALPHABET[(ALPHABET.index(ch) + 1) % len(ALPHABET)]
                                if ch in ALPHABET else ch
                                for ch in mol2
                            )
                            grid[nr][nc] = transformed
                            energy[r][c] = max(0.0, e1 - 0.1)
                            energy[nr][nc] = min(1.0, e2 + 0.2)
                            reacted.add((r, c))
                            reacted.add((nr, nc))
                            self.achem_total_reactions += 1
                            # Track catalytic relationship
                            if mol1 not in self.achem_catalytic_pairs:
                                self.achem_catalytic_pairs[mol1] = set()
                            self.achem_catalytic_pairs[mol1].add(transformed)
                            reaction_done = True
                            break

                if reaction_done:
                    continue

                # c) Concatenation
                if (_can_concatenate(mol1, mol2) and
                        random.random() < react_prob * 0.5 and
                        e1 + e2 > 0.3):
                    new_mol = mol1 + mol2
                    grid[r][c] = new_mol
                    energy[r][c] = min(1.0, e1 + e2 * 0.5 + ENERGY_PER_BOND)
                    grid[nr][nc] = None
                    energy[nr][nc] = 0.0
                    age_grid[nr][nc] = 0
                    reacted.add((r, c))
                    reacted.add((nr, nc))
                    self.achem_total_reactions += 1
                    break

                # d) Cleavage (splitting)
                if (_can_cleave(mol1) and random.random() < cleave_prob and
                        grid[nr][nc] is None):
                    # Not consumed — this path is for spontaneous cleavage
                    pass

    # Place new molecules from replication
    for pr, pc, mol, e in new_mols:
        if grid[pr][pc] is None:
            grid[pr][pc] = mol
            energy[pr][pc] = e
            age_grid[pr][pc] = 0

    # ── 3. Spontaneous cleavage of long molecules ────────────────
    for r in range(rows):
        for c in range(cols):
            mol = grid[r][c]
            if mol is not None and len(mol) >= 4 and random.random() < cleave_prob * 0.3:
                # Split at random point
                split = random.randint(1, len(mol) - 1)
                frag1 = mol[:split]
                frag2 = mol[split:]
                grid[r][c] = frag1
                energy[r][c] *= 0.6
                # Place frag2 nearby
                empties = []
                for dr, dc in _NBRS4:
                    er, ec = r + dr, c + dc
                    if 0 <= er < rows and 0 <= ec < cols and grid[er][ec] is None:
                        empties.append((er, ec))
                if empties:
                    pr, pc = random.choice(empties)
                    grid[pr][pc] = frag2
                    energy[pr][pc] = energy[r][c] * 0.4
                    age_grid[pr][pc] = 0

    # ── 4. Energy decay and food injection ───────────────────────
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] is not None:
                energy[r][c] = max(0.0, energy[r][c] - energy_decay)
                age_grid[r][c] += 1
                # Molecules with no energy degrade
                if energy[r][c] <= 0.0 and len(grid[r][c]) > 1:
                    # Lose last character
                    grid[r][c] = grid[r][c][:-1]
                    energy[r][c] = 0.05
                elif energy[r][c] <= 0.0 and len(grid[r][c]) <= 1:
                    # Monomer with no energy disappears
                    if random.random() < 0.3:
                        grid[r][c] = None
                        energy[r][c] = 0.0
                        age_grid[r][c] = 0

    # Food injection at edges
    if random.random() < food_rate:
        for _ in range(max(1, int(cols * food_rate))):
            r = random.randint(0, rows - 1)
            c = random.choice([0, cols - 1, random.randint(0, cols - 1)])
            if grid[r][c] is None:
                grid[r][c] = random.choice(ALPHABET)
                energy[r][c] = 1.0

    # ── 5. Clustering (if enabled) — molecules attract ───────────
    if extras.get("clustering"):
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] is None or len(grid[r][c]) < 3:
                    continue
                # Pull nearby small molecules toward this one
                for dr, dc in _NBRS8:
                    sr, sc = r + dr * 2, c + dc * 2
                    if (0 <= sr < rows and 0 <= sc < cols and
                            grid[sr][sc] is not None and len(grid[sr][sc]) <= 2):
                        tr, tc = r + dr, c + dc
                        if 0 <= tr < rows and 0 <= tc < cols and grid[tr][tc] is None:
                            grid[tr][tc] = grid[sr][sc]
                            energy[tr][tc] = energy[sr][sc]
                            age_grid[tr][tc] = age_grid[sr][sc]
                            grid[sr][sc] = None
                            energy[sr][sc] = 0.0
                            age_grid[sr][sc] = 0

    # ── 6. Detect autocatalytic cycles ───────────────────────────
    if gen % 20 == 0:
        self._achem_detect_cycles()

    # ── 7. Collect statistics ────────────────────────────────────
    self.achem_generation += 1
    if gen % 5 == 0:
        diversity, longest = self._achem_compute_stats()
        self.achem_longest_polymer = longest
        self.achem_replicator_count = len(self.achem_replicator_seqs)
        self.achem_mol_history.append(
            (gen, diversity, longest, self.achem_cycle_count,
             self.achem_replicator_count))
        if len(self.achem_mol_history) > 200:
            self.achem_mol_history = self.achem_mol_history[-200:]


def _achem_compute_stats(self):
    """Compute diversity (unique species) and longest polymer."""
    species = Counter()
    longest = 0
    for r in range(self.achem_rows):
        for c in range(self.achem_cols):
            mol = self.achem_grid[r][c]
            if mol is not None:
                species[mol] += 1
                if len(mol) > longest:
                    longest = len(mol)
    return len(species), longest


def _achem_detect_cycles(self):
    """Detect autocatalytic cycles in the catalytic network."""
    pairs = self.achem_catalytic_pairs
    if not pairs:
        self.achem_cycle_count = 0
        return

    # Build adjacency: A -> B means A catalyzes production of B
    # Look for cycles of length 2-4
    cycles_found = 0
    visited = set()

    for start in pairs:
        if start in visited:
            continue
        # BFS/DFS for short cycles
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            if node not in pairs:
                continue
            for product in pairs[node]:
                if product == start and len(path) >= 2:
                    cycles_found += 1
                    visited.update(path)
                elif product not in path and len(path) < 4 and product in pairs:
                    stack.append((product, path + [product]))

    self.achem_cycle_count = cycles_found


def _achem_get_cell_type(mol, is_replicator, is_catalyst):
    """Determine display cell type for a molecule."""
    if mol is None:
        return CELL_EMPTY
    if is_replicator:
        return CELL_REPLICATOR
    if is_catalyst:
        return CELL_CATALYST
    n = len(mol)
    if n <= 2:
        return CELL_MONOMER
    if n <= 4:
        return CELL_SHORT
    if n <= 8:
        return CELL_MEDIUM
    return CELL_LONG


# ════════════════════════════════════════════════════════════════════════
#  Input handling
# ════════════════════════════════════════════════════════════════════════

def _handle_achem_menu_key(self, key: int) -> bool:
    """Handle input in Artificial Chemistry preset menu."""
    presets = self.ACHEM_PRESETS
    if key == curses.KEY_DOWN or key == ord("j"):
        self.achem_menu_sel = (self.achem_menu_sel + 1) % len(presets)
    elif key == curses.KEY_UP or key == ord("k"):
        self.achem_menu_sel = (self.achem_menu_sel - 1) % len(presets)
    elif key in (10, 13, curses.KEY_ENTER):
        self._achem_init(self.achem_menu_sel)
    elif key == ord("q") or key == 27:
        self.achem_menu = False
        self._flash("Artificial Chemistry cancelled")
    return True


def _handle_achem_key(self, key: int) -> bool:
    """Handle input in active Artificial Chemistry simulation."""
    if key == ord("q") or key == 27:
        self._exit_achem_mode()
        return True
    if key == ord(" "):
        self.achem_running = not self.achem_running
        return True
    if key == ord("n") or key == ord("."):
        self._achem_step()
        return True
    if key == ord("r"):
        idx = next(
            (i for i, p in enumerate(self.ACHEM_PRESETS)
             if p[0] == self.achem_preset_name), 0)
        self._achem_init(idx)
        return True
    if key == ord("R") or key == ord("m"):
        self.achem_mode = False
        self.achem_running = False
        self.achem_menu = True
        self.achem_menu_sel = 0
        return True
    if key == ord("+") or key == ord("="):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.achem_steps_per_frame) if self.achem_steps_per_frame in choices else 0
        self.achem_steps_per_frame = choices[min(idx + 1, len(choices) - 1)]
        self._flash(f"Speed: {self.achem_steps_per_frame} steps/frame")
        return True
    if key == ord("-") or key == ord("_"):
        choices = [1, 2, 3, 5, 10, 20]
        idx = choices.index(self.achem_steps_per_frame) if self.achem_steps_per_frame in choices else 0
        self.achem_steps_per_frame = choices[max(idx - 1, 0)]
        self._flash(f"Speed: {self.achem_steps_per_frame} steps/frame")
        return True
    if key == ord("v"):
        views = ["soup", "energy", "diversity"]
        idx = views.index(self.achem_view) if self.achem_view in views else 0
        self.achem_view = views[(idx + 1) % len(views)]
        self._flash(f"View: {self.achem_view}")
        return True
    # Reactivity: e/E
    if key == ord("e"):
        self.achem_react_prob = max(0.05, self.achem_react_prob - 0.05)
        self._flash(f"Reactivity: {self.achem_react_prob:.2f}")
        return True
    if key == ord("E"):
        self.achem_react_prob = min(1.0, self.achem_react_prob + 0.05)
        self._flash(f"Reactivity: {self.achem_react_prob:.2f}")
        return True
    # Food rate: f/F
    if key == ord("f"):
        self.achem_food_rate = max(0.005, self.achem_food_rate - 0.005)
        self._flash(f"Food rate: {self.achem_food_rate:.3f}")
        return True
    if key == ord("F"):
        self.achem_food_rate = min(0.2, self.achem_food_rate + 0.005)
        self._flash(f"Food rate: {self.achem_food_rate:.3f}")
        return True
    # Mutation rate: u/U
    if key == ord("u"):
        self.achem_mutation_rate = max(0.0, self.achem_mutation_rate - 0.01)
        self._flash(f"Mutation rate: {self.achem_mutation_rate:.2f}")
        return True
    if key == ord("U"):
        self.achem_mutation_rate = min(0.5, self.achem_mutation_rate + 0.01)
        self._flash(f"Mutation rate: {self.achem_mutation_rate:.2f}")
        return True
    # Drop food at mouse click
    if key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, _ = curses.getmouse()
            r = my - 1
            c = mx // 2
            rows, cols = self.achem_rows, self.achem_cols
            if 0 <= r < rows and 0 <= c < cols:
                if self.achem_grid[r][c] is None:
                    # Drop a short polymer
                    length = random.randint(2, 4)
                    mol = "".join(random.choice(ALPHABET) for _ in range(length))
                    self.achem_grid[r][c] = mol
                    self.achem_energy[r][c] = 1.0
                    self._flash(f"Dropped molecule: {mol}")
        except curses.error:
            pass
        return True
    return True


# ════════════════════════════════════════════════════════════════════════
#  Drawing
# ════════════════════════════════════════════════════════════════════════

def _draw_achem_menu(self, max_y: int, max_x: int):
    """Draw the Artificial Chemistry preset selection menu."""
    self.stdscr.erase()
    title = "── Artificial Chemistry: Origin of Life ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, *_rest) in enumerate(self.ACHEM_PRESETS):
        y = 3 + i
        if y >= max_y - 2:
            break
        marker = "▸ " if i == self.achem_menu_sel else "  "
        attr = curses.color_pair(3) | curses.A_BOLD if i == self.achem_menu_sel else curses.color_pair(7)
        line = f"{marker}{name:28s} {desc}"
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 3], attr)
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


def _draw_achem(self, max_y: int, max_x: int):
    """Draw the active Artificial Chemistry simulation."""
    self.stdscr.erase()
    grid = self.achem_grid
    energy = self.achem_energy
    rows, cols = self.achem_rows, self.achem_cols
    state = "▶ RUNNING" if self.achem_running else "⏸ PAUSED"
    view = self.achem_view

    # Count molecule types
    mol_count = 0
    type_counts = Counter()
    for r in range(rows):
        for c in range(cols):
            mol = grid[r][c]
            if mol is not None:
                mol_count += 1
                is_rep = mol in self.achem_replicator_seqs
                is_cat = mol in self.achem_catalytic_pairs
                ct = _achem_get_cell_type(mol, is_rep, is_cat)
                type_counts[ct] += 1

    # Title bar
    title = (f" Artificial Chemistry: {self.achem_preset_name}  |  gen {self.achem_generation}"
             f"  |  molecules={mol_count}  rxns={self.achem_total_reactions}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    # Color mapping
    cell_colors = {
        CELL_MONOMER: curses.color_pair(7) | curses.A_DIM,        # dim white
        CELL_SHORT: curses.color_pair(2),                          # yellow
        CELL_MEDIUM: curses.color_pair(1) | curses.A_BOLD,        # bright green
        CELL_LONG: curses.color_pair(6) | curses.A_BOLD,          # cyan bold
        CELL_REPLICATOR: curses.color_pair(5) | curses.A_BOLD,    # magenta bold
        CELL_CATALYST: curses.color_pair(3) | curses.A_BOLD,      # yellow bold
        CELL_FOOD: curses.color_pair(4) | curses.A_DIM,           # blue dim
    }

    for r in range(view_rows):
        sy = 1 + r
        for c in range(view_cols):
            sx = c * 2
            mol = grid[r][c]
            if mol is None:
                continue

            if view == "soup":
                is_rep = mol in self.achem_replicator_seqs
                is_cat = mol in self.achem_catalytic_pairs
                ct = _achem_get_cell_type(mol, is_rep, is_cat)
                ch = CELL_CHARS.get(ct, "??")
                attr = cell_colors.get(ct, curses.color_pair(7))
            elif view == "energy":
                e = energy[r][c]
                if e > 0.7:
                    ch, attr = "██", curses.color_pair(1) | curses.A_BOLD
                elif e > 0.4:
                    ch, attr = "▓▓", curses.color_pair(2)
                elif e > 0.2:
                    ch, attr = "▒▒", curses.color_pair(3) | curses.A_DIM
                elif e > 0.05:
                    ch, attr = "░░", curses.color_pair(7) | curses.A_DIM
                else:
                    ch, attr = "··", curses.color_pair(7) | curses.A_DIM
            else:  # diversity view — color by first char
                idx = ALPHABET.index(mol[0]) if mol[0] in ALPHABET else 0
                pair = (idx % 6) + 1  # color pairs 1-6
                ch = mol[:2].ljust(2) if len(mol) >= 2 else mol[0] + " "
                attr = curses.color_pair(pair)

            try:
                self.stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    # Stats line
    stats_y = max_y - 2
    if stats_y > 1:
        diversity, longest = self._achem_compute_stats() if self.achem_generation > 0 else (0, 0)
        counts_str = " ".join(f"{CELL_NAMES.get(k, '?')}={v}" for k, v in sorted(type_counts.items()))
        stats = (f" {counts_str}  |  longest={self.achem_longest_polymer}"
                 f"  cycles={self.achem_cycle_count}"
                 f"  replicators={self.achem_replicator_count}"
                 f"  species={diversity}")
        try:
            self.stdscr.addstr(stats_y, 0, stats[:max_x - 1], curses.color_pair(7))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [v]=view [e/E]=reactivity [f/F]=food [u/U]=mutation [+/-]=speed [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ════════════════════════════════════════════════════════════════════════
#  Registration
# ════════════════════════════════════════════════════════════════════════

def register(App):
    """Register artificial chemistry mode methods on the App class."""
    App._enter_achem_mode = _enter_achem_mode
    App._exit_achem_mode = _exit_achem_mode
    App._achem_init = _achem_init
    App._achem_step = _achem_step
    App._achem_compute_stats = _achem_compute_stats
    App._achem_detect_cycles = _achem_detect_cycles
    App._handle_achem_menu_key = _handle_achem_menu_key
    App._handle_achem_key = _handle_achem_key
    App._draw_achem_menu = _draw_achem_menu
    App._draw_achem = _draw_achem
    App.ACHEM_PRESETS = ACHEM_PRESETS
