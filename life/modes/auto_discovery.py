"""Mode: auto_discovery — Autonomous Pattern Discovery Engine.

Autonomously explores the CA rule space by mutating rules and initial conditions,
scoring each configuration by visual complexity (entropy, symmetry, periodicity),
and curating a gallery of the most "interesting" emergent patterns found.

An automated explorer that breeds and evolves configurations toward maximum
visual interest, surfacing hidden gems no human would find by hand.
"""
import curses
import json
import math
import os
import random
import time

from life.analytics import (
    PeriodicityDetector,
    shannon_entropy,
    symmetry_score,
)
from life.constants import SAVE_DIR, SPEEDS
from life.grid import Grid
from life.rules import rule_string, parse_rule_string

# ── Constants ────────────────────────────────────────────────────────

_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]

_GALLERY_FILE = os.path.join(SAVE_DIR, "auto_discovery_gallery.json")

_SEED_STYLES = ["random", "symmetric", "clustered", "sparse", "striped", "central"]

_COLOR_TIERS = [
    (1, curses.A_DIM), (1, 0), (4, curses.A_DIM), (4, 0),
    (6, curses.A_DIM), (6, 0), (7, 0), (7, curses.A_BOLD),
]

# ── Genome helpers ───────────────────────────────────────────────────


def _random_genome():
    """Generate a random CA genome with initial condition style."""
    birth = {d for d in range(9) if random.random() < 0.3}
    survival = {d for d in range(9) if random.random() < 0.3}
    if not birth:
        birth.add(random.randint(1, 5))
    if not survival:
        survival.add(random.randint(2, 4))
    neighborhood = random.choice(["moore", "moore", "moore", "von_neumann"])
    density = random.uniform(0.05, 0.5)
    seed_style = random.choice(_SEED_STYLES)
    return {
        "birth": birth,
        "survival": survival,
        "neighborhood": neighborhood,
        "density": density,
        "seed_style": seed_style,
    }


def _crossover(g1, g2):
    """Uniform crossover between two genomes."""
    child_birth = set()
    child_survival = set()
    for d in range(9):
        if d in (g1 if random.random() < 0.5 else g2)["birth"]:
            child_birth.add(d)
        if d in (g1 if random.random() < 0.5 else g2)["survival"]:
            child_survival.add(d)
    if not child_birth:
        child_birth.add(random.randint(1, 5))
    return {
        "birth": child_birth,
        "survival": child_survival,
        "neighborhood": g1["neighborhood"] if random.random() < 0.5 else g2["neighborhood"],
        "density": (g1["density"] + g2["density"]) / 2 + random.gauss(0, 0.03),
        "seed_style": g1["seed_style"] if random.random() < 0.5 else g2["seed_style"],
    }


def _mutate(genome, rate=0.15):
    """Mutate a genome and return a new copy."""
    g = {
        "birth": set(genome["birth"]),
        "survival": set(genome["survival"]),
        "neighborhood": genome["neighborhood"],
        "density": genome["density"],
        "seed_style": genome["seed_style"],
    }
    for d in range(9):
        if random.random() < rate:
            g["birth"].symmetric_difference_update({d})
        if random.random() < rate:
            g["survival"].symmetric_difference_update({d})
    if not g["birth"]:
        g["birth"].add(random.randint(1, 5))
    if random.random() < rate * 0.5:
        g["neighborhood"] = random.choice(["moore", "von_neumann"])
    if random.random() < rate:
        g["density"] = max(0.02, min(0.6, g["density"] + random.gauss(0, 0.08)))
    if random.random() < rate * 0.5:
        g["seed_style"] = random.choice(_SEED_STYLES)
    return g


def _genome_label(genome):
    """Short human-readable label."""
    rs = rule_string(genome["birth"], genome["survival"])
    nh = "VN" if genome["neighborhood"] == "von_neumann" else ""
    parts = [rs]
    if nh:
        parts.append(nh)
    return " ".join(parts)


# ── Mini-simulation ──────────────────────────────────────────────────


def _count_neighbors(cells, r, c, rows, cols, neighborhood):
    """Count live neighbors for a cell."""
    count = 0
    if neighborhood == "von_neumann":
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if cells[(r + dr) % rows][(c + dc) % cols] > 0:
                count += 1
    else:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                if cells[(r + dr) % rows][(c + dc) % cols] > 0:
                    count += 1
    return count


def _seed_grid(grid, density, style):
    """Seed a grid with initial conditions based on style."""
    rows, cols = grid.rows, grid.cols
    if style == "symmetric":
        # 4-fold symmetric seeding
        hr, hc = rows // 2, cols // 2
        for r in range(hr):
            for c in range(hc):
                if random.random() < density:
                    grid.cells[r][c] = 1
                    grid.cells[r][cols - 1 - c] = 1
                    grid.cells[rows - 1 - r][c] = 1
                    grid.cells[rows - 1 - r][cols - 1 - c] = 1
    elif style == "clustered":
        # A few random clusters
        n_clusters = random.randint(2, 5)
        for _ in range(n_clusters):
            cr, cc = random.randint(0, rows - 1), random.randint(0, cols - 1)
            radius = random.randint(2, min(6, rows // 3))
            for r in range(max(0, cr - radius), min(rows, cr + radius)):
                for c in range(max(0, cc - radius), min(cols, cc + radius)):
                    if random.random() < density * 1.5:
                        grid.cells[r][c] = 1
    elif style == "sparse":
        # Very sparse random
        for r in range(rows):
            for c in range(cols):
                if random.random() < density * 0.3:
                    grid.cells[r][c] = 1
    elif style == "striped":
        # Horizontal or vertical stripes with noise
        horiz = random.random() < 0.5
        stripe_w = random.randint(1, 3)
        for r in range(rows):
            for c in range(cols):
                coord = r if horiz else c
                if (coord // stripe_w) % 2 == 0 and random.random() < density:
                    grid.cells[r][c] = 1
    elif style == "central":
        # Dense center, sparse edges
        cr, cc = rows // 2, cols // 2
        for r in range(rows):
            for c in range(cols):
                dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
                max_dist = math.sqrt(cr ** 2 + cc ** 2)
                p = density * max(0, 1 - dist / max_dist) * 2
                if random.random() < p:
                    grid.cells[r][c] = 1
    else:  # random
        for r in range(rows):
            for c in range(cols):
                if random.random() < density:
                    grid.cells[r][c] = 1
    grid.population = sum(1 for r in range(rows) for c in range(cols) if grid.cells[r][c] > 0)


def _create_sim(genome, rows, cols):
    """Create a mini Grid for a genome."""
    g = Grid(rows, cols)
    g.birth = set(genome["birth"])
    g.survival = set(genome["survival"])
    g._adisco_nh = genome["neighborhood"]
    _seed_grid(g, genome["density"], genome["seed_style"])
    return g


def _step_sim(grid):
    """Step a mini simulation."""
    rows, cols = grid.rows, grid.cols
    nh = getattr(grid, '_adisco_nh', 'moore')
    cells = grid.cells
    new = [[0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            n = _count_neighbors(cells, r, c, rows, cols, nh)
            alive = cells[r][c] > 0
            if alive and n in grid.survival:
                new[r][c] = min(cells[r][c] + 1, 200)
            elif not alive and n in grid.birth:
                new[r][c] = 1
            else:
                new[r][c] = 0
    grid.cells = new
    grid.generation += 1
    grid.population = sum(1 for row in new for cell in row if cell > 0)


# ── Complexity scoring ───────────────────────────────────────────────


def _compute_interest_score(grid, pop_history, period_detector):
    """Score a configuration's visual interest.

    Returns dict with individual metrics and weighted total.
    Scoring emphasizes configurations that are neither dead/static
    nor fully chaotic — the sweet spot of complex, structured behavior.
    """
    if not pop_history or len(pop_history) < 10:
        return {"total": 0, "entropy": 0, "symmetry": 0, "stability": 0,
                "periodicity": 0, "longevity": 0}

    total_cells = grid.rows * grid.cols

    # ── Entropy (0-100): structured complexity ──
    ent = shannon_entropy(grid)
    ent_score = min(ent / 1.0, 1.0) * 100  # normalize to ~1 bit max

    # ── Symmetry (0-100): emergent order ──
    sym = symmetry_score(grid)
    sym_score = (sym["horiz"] + sym["vert"] + sym["rot180"]) / 3.0 * 100

    # ── Stability / oscillation quality (0-100) ──
    recent = pop_history[-40:]
    avg_pop = sum(recent) / len(recent) if recent else 0
    if avg_pop > 0 and len(recent) > 8:
        variance = sum((p - avg_pop) ** 2 for p in recent) / len(recent)
        cv = math.sqrt(variance) / max(avg_pop, 1)
        if cv < 0.005:
            stab_score = 20   # static — boring
        elif cv < 0.05:
            stab_score = 60   # very stable oscillation
        elif cv < 0.2:
            stab_score = 100  # interesting oscillation
        elif cv < 0.5:
            stab_score = 75   # somewhat chaotic — still interesting
        else:
            stab_score = 35   # very chaotic — less interesting
    else:
        stab_score = 0

    # ── Periodicity bonus (0-100): detected repeating cycles ──
    period = period_detector.period
    if period is not None:
        if 2 <= period <= 8:
            period_score = 100  # clean short oscillation
        elif 8 < period <= 50:
            period_score = 80   # medium cycle
        elif period == 1:
            period_score = 15   # static
        else:
            period_score = 50   # long cycle
    else:
        # No cycle detected — could be chaotic or just not enough steps
        period_score = 40

    # ── Longevity (0-100): survived and stayed active ──
    alive_gens = sum(1 for p in pop_history if p > 0)
    longevity_score = (alive_gens / len(pop_history)) * 100

    # ── Penalties ──
    # Extinction
    if pop_history[-1] == 0:
        longevity_score *= 0.2
        stab_score *= 0.1
        period_score *= 0.1

    # Full saturation (boring)
    if total_cells > 0 and grid.population > total_cells * 0.85:
        ent_score *= 0.2
        stab_score *= 0.3

    # Very low population (not visually interesting)
    if total_cells > 0 and 0 < grid.population < total_cells * 0.02:
        ent_score *= 0.5
        stab_score *= 0.5

    # ── Weighted total — emphasize visual complexity ──
    total = (
        ent_score * 1.5 +      # entropy: complex structure
        sym_score * 2.0 +      # symmetry: visual beauty
        stab_score * 2.0 +     # oscillation: dynamic interest
        period_score * 1.5 +   # periodicity: structured behavior
        longevity_score * 1.0  # longevity: sustainability
    )

    return {
        "total": total,
        "entropy": round(ent_score, 1),
        "symmetry": round(sym_score, 1),
        "stability": round(stab_score, 1),
        "periodicity": round(period_score, 1),
        "longevity": round(longevity_score, 1),
    }


# ── Gallery entry ────────────────────────────────────────────────────


def _snapshot_cells(grid, max_rows=24, max_cols=32):
    """Capture a compact snapshot of live cell positions."""
    alive = []
    for r in range(min(grid.rows, max_rows)):
        for c in range(min(grid.cols, max_cols)):
            if grid.cells[r][c] > 0:
                alive.append((r, c))
    return alive


# ── Mode functions ───────────────────────────────────────────────────


def _enter_adisco_mode(self):
    """Enter Auto-Discovery mode — show settings menu."""
    self.adisco_mode = False
    self.adisco_menu = True
    self.adisco_menu_sel = 0
    self._flash("Auto-Discovery — autonomous search for beautiful CA patterns")


def _exit_adisco_mode(self):
    """Exit Auto-Discovery mode."""
    self.adisco_mode = False
    self.adisco_menu = False
    self.adisco_running = False
    self.adisco_sims = []
    self.adisco_genomes = []
    self.adisco_fitness = []
    self.adisco_pop_histories = []
    self.adisco_period_detectors = []
    self.adisco_gallery_view = False
    self._flash("Auto-Discovery OFF")


def _adisco_init(self, seed_genomes=None):
    """Initialize a batch of candidate configurations."""
    max_y, max_x = self.stdscr.getmaxyx()
    usable_h = max_y - 6
    usable_w = max_x - 1

    batch_size = self.adisco_batch_size

    # Find tile layout
    best_r, best_c = 2, 4
    for gc in range(2, 8):
        gr = math.ceil(batch_size / gc)
        if gr <= 0:
            continue
        th = usable_h // gr
        tw = usable_w // gc
        if th >= 4 and tw >= 8:
            best_r, best_c = gr, gc
            if gr * gc >= batch_size:
                break

    self.adisco_grid_rows = best_r
    self.adisco_grid_cols = best_c
    actual_batch = min(batch_size, best_r * best_c)

    self.adisco_tile_h = max(4, usable_h // best_r - 1)
    self.adisco_tile_w = max(4, (usable_w // best_c - 1) // 2)

    sim_rows = max(4, self.adisco_tile_h - 2)
    sim_cols = max(4, self.adisco_tile_w)

    # Generate genomes
    if seed_genomes and len(seed_genomes) >= 2:
        genomes = []
        for sg in seed_genomes[:actual_batch // 3]:
            genomes.append(dict(sg, birth=set(sg["birth"]), survival=set(sg["survival"])))
        while len(genomes) < actual_batch:
            p1 = random.choice(seed_genomes)
            p2 = random.choice(seed_genomes)
            child = _crossover(p1, p2)
            child = _mutate(child, self.adisco_mutation_rate)
            genomes.append(child)
        genomes = genomes[:actual_batch]
    else:
        genomes = [_random_genome() for _ in range(actual_batch)]

    # Create simulations
    self.adisco_sims = []
    self.adisco_genomes = genomes
    self.adisco_pop_histories = []
    self.adisco_fitness = [{} for _ in range(len(genomes))]
    self.adisco_period_detectors = []
    for genome in genomes:
        grid = _create_sim(genome, sim_rows, sim_cols)
        self.adisco_sims.append(grid)
        self.adisco_pop_histories.append([grid.population])
        self.adisco_period_detectors.append(PeriodicityDetector(max_history=300))

    self.adisco_cursor = 0
    self.adisco_sim_step = 0
    self.adisco_phase = "simulating"
    self.adisco_mode = True
    self.adisco_menu = False
    self.adisco_running = True
    self.adisco_gallery_view = False
    self.adisco_round += 1

    self._flash(f"Round {self.adisco_round}: exploring {actual_batch} configurations...")


def _adisco_step(self):
    """Advance all candidates by one simulation step."""
    if self.adisco_phase != "simulating":
        return
    for i, grid in enumerate(self.adisco_sims):
        _step_sim(grid)
        self.adisco_pop_histories[i].append(grid.population)
        # Update periodicity detector every 5 steps
        if self.adisco_sim_step % 5 == 0:
            self.adisco_period_detectors[i].update(grid)
    self.adisco_sim_step += 1

    # Auto-score when enough steps have run
    if self.adisco_sim_step >= self.adisco_eval_steps:
        _adisco_score_and_curate(self)


def _adisco_score_and_curate(self):
    """Score all candidates, add best to gallery, breed next round."""
    self.adisco_phase = "scored"

    # Score all
    for i, grid in enumerate(self.adisco_sims):
        self.adisco_fitness[i] = _compute_interest_score(
            grid, self.adisco_pop_histories[i], self.adisco_period_detectors[i]
        )

    # Sort by total score (best first)
    indices = list(range(len(self.adisco_sims)))
    indices.sort(key=lambda i: -self.adisco_fitness[i].get("total", 0))

    self.adisco_sims = [self.adisco_sims[i] for i in indices]
    self.adisco_genomes = [self.adisco_genomes[i] for i in indices]
    self.adisco_fitness = [self.adisco_fitness[i] for i in indices]
    self.adisco_pop_histories = [self.adisco_pop_histories[i] for i in indices]
    self.adisco_period_detectors = [self.adisco_period_detectors[i] for i in indices]

    # Add top performers to gallery (if they meet threshold)
    threshold = self.adisco_gallery_threshold
    added = 0
    for i in range(min(3, len(self.adisco_sims))):
        score = self.adisco_fitness[i].get("total", 0)
        if score >= threshold:
            entry = {
                "genome": {
                    "birth": sorted(self.adisco_genomes[i]["birth"]),
                    "survival": sorted(self.adisco_genomes[i]["survival"]),
                    "neighborhood": self.adisco_genomes[i]["neighborhood"],
                    "density": round(self.adisco_genomes[i]["density"], 3),
                    "seed_style": self.adisco_genomes[i]["seed_style"],
                },
                "label": _genome_label(self.adisco_genomes[i]),
                "score": round(score, 1),
                "metrics": self.adisco_fitness[i],
                "round": self.adisco_round,
                "snapshot": _snapshot_cells(self.adisco_sims[i]),
                "sim_rows": self.adisco_sims[i].rows,
                "sim_cols": self.adisco_sims[i].cols,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            # Avoid near-duplicates (same rule string)
            label = entry["label"]
            if not any(g["label"] == label and abs(g["score"] - score) < 20
                       for g in self.adisco_gallery):
                self.adisco_gallery.append(entry)
                added += 1

    # Keep gallery sorted and bounded
    self.adisco_gallery.sort(key=lambda g: -g["score"])
    self.adisco_gallery = self.adisco_gallery[:self.adisco_gallery_max]

    # Update adaptive threshold
    if self.adisco_gallery:
        min_gallery_score = self.adisco_gallery[-1]["score"]
        self.adisco_gallery_threshold = max(threshold, min_gallery_score * 0.9)

    best = self.adisco_fitness[0]
    best_label = _genome_label(self.adisco_genomes[0])
    gallery_size = len(self.adisco_gallery)

    if added:
        self._flash(f"Round {self.adisco_round}: +{added} to gallery ({gallery_size} total) — best: {best_label} ({best.get('total', 0):.0f}pts)")
    else:
        self._flash(f"Round {self.adisco_round}: no new gems — best: {best_label} ({best.get('total', 0):.0f}pts)")

    # Track history
    avg_score = sum(f.get("total", 0) for f in self.adisco_fitness) / max(1, len(self.adisco_fitness))
    self.adisco_history.append({
        "round": self.adisco_round,
        "best_score": best.get("total", 0),
        "best_rule": best_label,
        "avg_score": avg_score,
        "gallery_size": gallery_size,
    })

    # Auto-breed next round from gallery + top performers
    if self.adisco_auto_continue:
        _adisco_breed_next(self)


def _adisco_breed_next(self):
    """Breed next round from gallery entries and top performers."""
    # Collect parent genomes from gallery + current top
    parents = []
    for entry in self.adisco_gallery[:6]:
        g = entry["genome"]
        parents.append({
            "birth": set(g["birth"]),
            "survival": set(g["survival"]),
            "neighborhood": g["neighborhood"],
            "density": g["density"],
            "seed_style": g["seed_style"],
        })
    # Add current top performers
    for i in range(min(3, len(self.adisco_genomes))):
        parents.append({
            "birth": set(self.adisco_genomes[i]["birth"]),
            "survival": set(self.adisco_genomes[i]["survival"]),
            "neighborhood": self.adisco_genomes[i]["neighborhood"],
            "density": self.adisco_genomes[i]["density"],
            "seed_style": self.adisco_genomes[i]["seed_style"],
        })

    if len(parents) < 2:
        parents = None  # fall back to random

    self.adisco_sim_step = 0
    _adisco_init(self, seed_genomes=parents)
    self.adisco_running = True


def _adisco_save_gallery(self):
    """Save the gallery to disk."""
    if not self.adisco_gallery:
        self._flash("Gallery is empty — nothing to save")
        return
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(_GALLERY_FILE, "w") as f:
        json.dump(self.adisco_gallery, f, indent=2)
    self._flash(f"Gallery saved: {len(self.adisco_gallery)} entries → {_GALLERY_FILE}")


def _adisco_load_gallery(self):
    """Load gallery from disk."""
    if not os.path.isfile(_GALLERY_FILE):
        return []
    try:
        with open(_GALLERY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _adisco_adopt_rule(self, genome_data):
    """Adopt a genome's ruleset into the main Game of Life."""
    birth = set(genome_data["birth"])
    survival = set(genome_data["survival"])
    self.grid.birth = birth
    self.grid.survival = survival
    label = rule_string(birth, survival)
    _exit_adisco_mode(self)
    self._flash(f"Adopted discovered rule: {label}")


# ── Key handlers ─────────────────────────────────────────────────────


def _handle_adisco_menu_key(self, key):
    """Handle keys in the Auto-Discovery settings menu."""
    if key == -1:
        return True
    menu_items = ["batch_size", "eval_steps", "mutation_rate",
                  "gallery_max", "auto_continue", "start_fresh",
                  "start_from_gallery", "browse_gallery"]
    n = len(menu_items)

    if key in (curses.KEY_UP, ord("k")):
        self.adisco_menu_sel = (self.adisco_menu_sel - 1) % n
        return True
    if key in (curses.KEY_DOWN, ord("j")):
        self.adisco_menu_sel = (self.adisco_menu_sel + 1) % n
        return True
    if key == 27 or key == ord("q"):
        self.adisco_menu = False
        self._flash("Auto-Discovery cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER, ord(" ")):
        item = menu_items[self.adisco_menu_sel]
        if item == "batch_size":
            val = self._prompt_text(f"Batch size 4-20 (current: {self.adisco_batch_size})")
            if val:
                try:
                    v = int(val)
                    if 4 <= v <= 20:
                        self.adisco_batch_size = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "eval_steps":
            val = self._prompt_text(f"Eval steps 50-500 (current: {self.adisco_eval_steps})")
            if val:
                try:
                    v = int(val)
                    if 50 <= v <= 500:
                        self.adisco_eval_steps = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "mutation_rate":
            val = self._prompt_text(f"Mutation rate 0-100% (current: {int(self.adisco_mutation_rate * 100)}%)")
            if val:
                try:
                    v = int(val.replace("%", ""))
                    if 0 <= v <= 100:
                        self.adisco_mutation_rate = v / 100.0
                except ValueError:
                    self._flash("Invalid number")
        elif item == "gallery_max":
            val = self._prompt_text(f"Max gallery size 10-100 (current: {self.adisco_gallery_max})")
            if val:
                try:
                    v = int(val)
                    if 10 <= v <= 100:
                        self.adisco_gallery_max = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "auto_continue":
            self.adisco_auto_continue = not self.adisco_auto_continue
            self._flash(f"Auto-continue: {'ON' if self.adisco_auto_continue else 'OFF'}")
        elif item == "start_fresh":
            self.adisco_round = 0
            self.adisco_history = []
            self.adisco_gallery = []
            self.adisco_gallery_threshold = 150
            _adisco_init(self)
        elif item == "start_from_gallery":
            loaded = _adisco_load_gallery(self)
            if loaded:
                self.adisco_gallery = loaded
                self.adisco_round = 0
                self.adisco_history = []
                parents = []
                for entry in loaded[:8]:
                    g = entry["genome"]
                    parents.append({
                        "birth": set(g["birth"]),
                        "survival": set(g["survival"]),
                        "neighborhood": g["neighborhood"],
                        "density": g["density"],
                        "seed_style": g["seed_style"],
                    })
                _adisco_init(self, seed_genomes=parents)
            else:
                self._flash("No saved gallery — starting fresh")
                self.adisco_round = 0
                self.adisco_history = []
                self.adisco_gallery = []
                self.adisco_gallery_threshold = 150
                _adisco_init(self)
        elif item == "browse_gallery":
            loaded = _adisco_load_gallery(self)
            if loaded:
                self.adisco_gallery = loaded
                self.adisco_gallery_view = True
                self.adisco_gallery_sel = 0
                self.adisco_gallery_scroll = 0
                self.adisco_mode = True
                self.adisco_menu = False
                self._flash(f"Gallery: {len(loaded)} entries")
            else:
                self._flash("No saved gallery")
        return True
    return True


def _handle_adisco_key(self, key):
    """Handle keys during active Auto-Discovery exploration."""
    if key == -1:
        return True
    if key == 27 or key == ord("q"):
        _exit_adisco_mode(self)
        return True

    # Toggle gallery view
    if key == ord("g"):
        if self.adisco_gallery:
            self.adisco_gallery_view = not self.adisco_gallery_view
            if self.adisco_gallery_view:
                self.adisco_gallery_sel = 0
                self.adisco_gallery_scroll = 0
            self._flash("Gallery" if self.adisco_gallery_view else "Explorer")
        else:
            self._flash("Gallery empty — keep exploring!")
        return True

    # Gallery view keys
    if self.adisco_gallery_view:
        return _handle_adisco_gallery_key(self, key)

    pop_size = len(self.adisco_sims)
    gc = self.adisco_grid_cols

    # Play/pause
    if key == ord(" "):
        self.adisco_running = not self.adisco_running
        if self.adisco_phase == "scored" and self.adisco_running:
            _adisco_breed_next(self)
        else:
            self._flash("Running" if self.adisco_running else "Paused")
        return True

    # Navigate cursor
    if key == curses.KEY_UP or key == ord("w"):
        self.adisco_cursor = max(0, self.adisco_cursor - gc)
        return True
    if key == curses.KEY_DOWN or key == ord("s"):
        self.adisco_cursor = min(pop_size - 1, self.adisco_cursor + gc)
        return True
    if key == curses.KEY_LEFT or key == ord("a"):
        self.adisco_cursor = max(0, self.adisco_cursor - 1)
        return True
    if key == curses.KEY_RIGHT or key == ord("d"):
        self.adisco_cursor = min(pop_size - 1, self.adisco_cursor + 1)
        return True

    # Skip to scoring
    if key == ord("S"):
        if self.adisco_phase == "simulating":
            remaining = self.adisco_eval_steps - self.adisco_sim_step
            for _ in range(remaining):
                for i, grid in enumerate(self.adisco_sims):
                    _step_sim(grid)
                    self.adisco_pop_histories[i].append(grid.population)
                self.adisco_sim_step += 1
            _adisco_score_and_curate(self)
        return True

    # Force breed now
    if key == ord("b"):
        if self.adisco_phase == "simulating":
            _adisco_score_and_curate(self)
        elif self.adisco_phase == "scored":
            _adisco_breed_next(self)
        return True

    # Toggle auto-continue
    if key == ord("A"):
        self.adisco_auto_continue = not self.adisco_auto_continue
        self._flash(f"Auto-continue: {'ON' if self.adisco_auto_continue else 'OFF'}")
        return True

    # Save gallery
    if key == ord("W"):
        _adisco_save_gallery(self)
        return True

    # Adopt current cursor's rule
    if key == ord("a"):
        if 0 <= self.adisco_cursor < pop_size:
            _adisco_adopt_rule(self, {
                "birth": self.adisco_genomes[self.adisco_cursor]["birth"],
                "survival": self.adisco_genomes[self.adisco_cursor]["survival"],
            })
        return True

    # New random batch
    if key == ord("r"):
        self.adisco_round = 0
        self.adisco_history = []
        _adisco_init(self)
        self._flash("New random exploration")
        return True

    # Speed controls
    if key == ord(">"):
        if self.speed_idx < len(SPEEDS) - 1:
            self.speed_idx += 1
        return True
    if key == ord("<"):
        if self.speed_idx > 0:
            self.speed_idx -= 1
        return True

    # Return to menu
    if key == ord("R"):
        self.adisco_mode = False
        self.adisco_running = False
        self.adisco_menu = True
        self.adisco_menu_sel = 0
        return True

    return True


def _handle_adisco_gallery_key(self, key):
    """Handle keys in gallery browsing view."""
    n = len(self.adisco_gallery)
    if n == 0:
        self.adisco_gallery_view = False
        return True

    if key in (curses.KEY_UP, ord("k")):
        self.adisco_gallery_sel = max(0, self.adisco_gallery_sel - 1)
        return True
    if key in (curses.KEY_DOWN, ord("j")):
        self.adisco_gallery_sel = min(n - 1, self.adisco_gallery_sel + 1)
        return True

    # Adopt selected rule
    if key in (10, 13, curses.KEY_ENTER):
        entry = self.adisco_gallery[self.adisco_gallery_sel]
        _adisco_adopt_rule(self, entry["genome"])
        return True

    # Delete from gallery
    if key == ord("x"):
        entry = self.adisco_gallery[self.adisco_gallery_sel]
        self.adisco_gallery.pop(self.adisco_gallery_sel)
        self.adisco_gallery_sel = min(self.adisco_gallery_sel, len(self.adisco_gallery) - 1)
        self._flash(f"Removed {entry['label']} from gallery")
        return True

    # Save gallery
    if key == ord("W"):
        _adisco_save_gallery(self)
        return True

    # Back to explorer
    if key == ord("g") or key == 27:
        self.adisco_gallery_view = False
        return True

    return True


# ── Drawing ──────────────────────────────────────────────────────────


def _draw_adisco_menu(self, max_y, max_x):
    """Draw the Auto-Discovery settings menu."""
    self.stdscr.erase()

    title = "── Auto-Discovery: Autonomous Pattern Explorer ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Searches the CA rule space for visually striking emergent patterns"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.color_pair(6))
    except curses.error:
        pass

    items = [
        ("Batch Size", str(self.adisco_batch_size), "Candidates per round (4-20)"),
        ("Eval Steps", str(self.adisco_eval_steps), "Simulation steps before scoring (50-500)"),
        ("Mutation Rate", f"{int(self.adisco_mutation_rate * 100)}%", "Mutation rate for offspring"),
        ("Gallery Max", str(self.adisco_gallery_max), "Max gallery entries to keep"),
        ("Auto-Continue", "ON" if self.adisco_auto_continue else "OFF", "Auto-breed next round"),
        (">>> START FRESH <<<", "", "Begin exploring from scratch"),
        (">>> START FROM GALLERY <<<", "", "Evolve from previously saved gallery"),
        (">>> BROWSE GALLERY <<<", "", "View curated discoveries"),
    ]

    for i, (label, value, hint) in enumerate(items):
        y = 5 + i * 2
        if y >= max_y - 14:
            break
        if i >= 5:
            line = f"  {label}"
            attr = curses.color_pair(3) | curses.A_BOLD
            if i == self.adisco_menu_sel:
                attr |= curses.A_REVERSE
        else:
            line = f"  {label:<20s} {value:<12s} {hint}"
            attr = curses.color_pair(6)
            if i == self.adisco_menu_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
        except curses.error:
            pass

    # Info box
    info_y = max(5 + len(items) * 2 + 1, max_y - 12)
    info_lines = [
        "HOW IT WORKS:",
        "  The engine autonomously generates CA rule + initial condition pairs.",
        "  Each candidate is simulated and scored by visual complexity:",
        "    Entropy (disorder) + Symmetry (beauty) + Oscillation quality",
        "    + Periodicity detection + Longevity (sustainability)",
        "  Top performers breed via crossover + mutation to explore nearby rules.",
        "  Beautiful patterns are auto-curated into a gallery you can browse.",
        "",
        "  Runs hands-free — just watch it discover gems, or browse the gallery.",
    ]
    for i, line in enumerate(info_lines):
        iy = info_y + i
        if iy >= max_y - 2:
            break
        try:
            self.stdscr.addstr(iy, 2, line[:max_x - 3],
                               curses.color_pair(1) if i > 0 else curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [j/k]=navigate  [Enter/Space]=select  [q/Esc]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_adisco(self, max_y, max_x):
    """Draw the Auto-Discovery explorer or gallery view."""
    if self.adisco_gallery_view:
        _draw_adisco_gallery(self, max_y, max_x)
        return

    self.stdscr.erase()

    gr = self.adisco_grid_rows
    gc = self.adisco_grid_cols
    pop_size = len(self.adisco_sims)

    # Title bar
    state_ch = "▶" if self.adisco_running else "‖"
    progress = f"{self.adisco_sim_step}/{self.adisco_eval_steps}"
    if self.adisco_phase == "scored":
        progress = "SCORED"

    gallery_n = len(self.adisco_gallery)
    title = (f" {state_ch} AUTO-DISCOVERY"
             f"  |  Round {self.adisco_round}"
             f"  |  {progress}"
             f"  |  Gallery: {gallery_n}")

    if self.adisco_gallery:
        best = self.adisco_gallery[0]
        title += f"  |  Top: {best['label']} ({best['score']:.0f}pts)"

    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Recalculate tile dimensions
    usable_h = max_y - 6
    usable_w = max_x - 1
    th = max(4, usable_h // gr - 1)
    tw_chars = max(8, usable_w // gc - 1)
    tw = tw_chars // 2

    draw_y_start = 2
    draw_x_start = 1

    for idx in range(pop_size):
        row = idx // gc
        col = idx % gc

        tile_y = draw_y_start + row * (th + 1)
        tile_x = draw_x_start + col * (tw * 2 + 1)

        if tile_y + th >= max_y - 3 or tile_x + tw * 2 >= max_x:
            continue

        grid = self.adisco_sims[idx]
        genome = self.adisco_genomes[idx]
        fitness = self.adisco_fitness[idx] if idx < len(self.adisco_fitness) else {}
        is_cursor = (idx == self.adisco_cursor)

        # Border color
        if is_cursor:
            border_attr = curses.color_pair(7) | curses.A_BOLD
        else:
            border_attr = curses.color_pair(6) | curses.A_DIM

        # Header: label + score
        label = _genome_label(genome)
        score = fitness.get("total", 0)
        if score > 0:
            score_str = f" {score:.0f}"
        else:
            score_str = f" P:{grid.population}"
        header = label[:tw * 2 - len(score_str) - 1] + score_str
        header = header[:tw * 2]
        try:
            self.stdscr.addstr(tile_y, tile_x, header, border_attr)
        except curses.error:
            pass

        # Border line
        try:
            self.stdscr.addstr(tile_y + 1, tile_x, "─" * (tw * 2), border_attr)
        except curses.error:
            pass

        # Simulation content
        sim_rows = min(th - 2, grid.rows)
        sim_cols = min(tw, grid.cols)
        for sr in range(sim_rows):
            sy = tile_y + 2 + sr
            if sy >= max_y - 3:
                break
            for sc in range(sim_cols):
                sx = tile_x + sc * 2
                if sx + 1 >= max_x:
                    break
                age = grid.cells[sr][sc]
                if age > 0:
                    v = min(1.0, age / 20.0)
                    di = max(1, min(4, int(v * 4.0) + 1))
                    ch = _DENSITY[di]
                    ci = min(7, int(v * 7.99))
                    pair_idx, extra = _COLOR_TIERS[ci]
                    attr = curses.color_pair(pair_idx) | extra
                    if not is_cursor:
                        attr |= curses.A_DIM
                    try:
                        self.stdscr.addstr(sy, sx, ch, attr)
                    except curses.error:
                        pass

        # Cursor marker
        if is_cursor:
            try:
                self.stdscr.addstr(tile_y + 1, tile_x, "▸", curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

    # ── Fitness detail for cursor ──
    status_y = max_y - 4
    if status_y > 0 and 0 <= self.adisco_cursor < pop_size:
        genome = self.adisco_genomes[self.adisco_cursor]
        fitness = self.adisco_fitness[self.adisco_cursor] if self.adisco_cursor < len(self.adisco_fitness) else {}
        grid = self.adisco_sims[self.adisco_cursor]

        if fitness.get("total", 0) > 0:
            info = (f" #{self.adisco_cursor + 1} {_genome_label(genome)}"
                    f"  |  Score:{fitness.get('total', 0):.0f}"
                    f"  Ent:{fitness.get('entropy', 0):.0f}"
                    f"  Sym:{fitness.get('symmetry', 0):.0f}"
                    f"  Stab:{fitness.get('stability', 0):.0f}"
                    f"  Per:{fitness.get('periodicity', 0):.0f}"
                    f"  Long:{fitness.get('longevity', 0):.0f}"
                    f"  [{genome.get('seed_style', '?')}]")
        else:
            info = (f" #{self.adisco_cursor + 1} {_genome_label(genome)}"
                    f"  |  Pop: {grid.population}"
                    f"  |  Step: {self.adisco_sim_step}"
                    f"  |  Seed: {genome.get('seed_style', '?')}")
        try:
            self.stdscr.addstr(status_y, 0, info[:max_x - 1], curses.color_pair(6))
        except curses.error:
            pass

    # ── Round history sparkline ──
    hist_y = max_y - 3
    if hist_y > 0 and self.adisco_history:
        scores = [h["best_score"] for h in self.adisco_history[-40:]]
        spark_chars = "▁▂▃▄▅▆▇█"
        if scores:
            lo, hi = min(scores), max(scores)
            span = hi - lo if hi != lo else 1
            sparkline = ""
            for sc in scores:
                si = int((sc - lo) / span * (len(spark_chars) - 1))
                si = max(0, min(si, len(spark_chars) - 1))
                sparkline += spark_chars[si]
            hist_info = f" Discovery trend: {sparkline}"
            try:
                self.stdscr.addstr(hist_y, 0, hist_info[:max_x - 1],
                                   curses.color_pair(3))
            except curses.error:
                pass

    # ── Gallery preview bar ──
    gal_y = max_y - 2
    if gal_y > 0 and self.adisco_gallery:
        top3 = self.adisco_gallery[:3]
        gal_info = " Gallery top: " + " | ".join(
            f"{e['label']}({e['score']:.0f})" for e in top3
        )
        try:
            self.stdscr.addstr(gal_y, 0, gal_info[:max_x - 1],
                               curses.color_pair(4))
        except curses.error:
            pass

    # ── Hint bar ──
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=pause [g]=gallery [b]=score now [S]=skip [a]=adopt [W]=save [A]=auto [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_adisco_gallery(self, max_y, max_x):
    """Draw the gallery browsing view."""
    self.stdscr.erase()

    title = f"── Auto-Discovery Gallery ({len(self.adisco_gallery)} patterns) ──"
    try:
        self.stdscr.addstr(0, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    if not self.adisco_gallery:
        try:
            self.stdscr.addstr(3, 4, "Gallery is empty. Start exploring to discover patterns!",
                               curses.color_pair(6))
        except curses.error:
            pass
        return

    # List area
    list_w = min(max_x - 2, 80)
    list_h = max_y - 8
    sel = self.adisco_gallery_sel

    # Ensure selection is visible
    if sel < self.adisco_gallery_scroll:
        self.adisco_gallery_scroll = sel
    if sel >= self.adisco_gallery_scroll + list_h:
        self.adisco_gallery_scroll = sel - list_h + 1

    # Column headers
    header = f" {'#':>3s}  {'Rule':<22s}  {'Score':>6s}  {'Ent':>4s}  {'Sym':>4s}  {'Stab':>4s}  {'Per':>4s}  {'Seed':<10s}  {'Round':>5s}"
    try:
        self.stdscr.addstr(2, 1, header[:max_x - 2], curses.color_pair(6) | curses.A_BOLD)
        self.stdscr.addstr(3, 1, "─" * min(list_w, max_x - 2), curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    for i in range(list_h):
        idx = self.adisco_gallery_scroll + i
        if idx >= len(self.adisco_gallery):
            break
        entry = self.adisco_gallery[idx]
        y = 4 + i
        if y >= max_y - 4:
            break

        is_sel = (idx == sel)
        metrics = entry.get("metrics", {})
        line = (f" {idx + 1:>3d}  {entry['label']:<22s}"
                f"  {entry['score']:>6.0f}"
                f"  {metrics.get('entropy', 0):>4.0f}"
                f"  {metrics.get('symmetry', 0):>4.0f}"
                f"  {metrics.get('stability', 0):>4.0f}"
                f"  {metrics.get('periodicity', 0):>4.0f}"
                f"  {entry['genome'].get('seed_style', '?'):<10s}"
                f"  R{entry.get('round', '?'):>4}")

        attr = curses.color_pair(7) | curses.A_REVERSE if is_sel else curses.color_pair(6)
        try:
            self.stdscr.addstr(y, 1, line[:max_x - 2], attr)
        except curses.error:
            pass

    # ── Preview of selected entry ──
    if 0 <= sel < len(self.adisco_gallery):
        entry = self.adisco_gallery[sel]
        snapshot = entry.get("snapshot", [])
        sim_rows = entry.get("sim_rows", 16)
        sim_cols = entry.get("sim_cols", 24)

        # Draw miniature preview on the right if space allows
        preview_x = list_w + 4
        preview_w = (max_x - preview_x) // 2
        preview_h = min(max_y - 8, sim_rows)

        if preview_w >= 6 and preview_x + preview_w * 2 < max_x:
            try:
                self.stdscr.addstr(2, preview_x, "Preview:", curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass
            alive_set = set()
            for r, c in snapshot:
                alive_set.add((r, c))
            for sr in range(preview_h):
                for sc in range(min(preview_w, sim_cols)):
                    sy = 3 + sr
                    sx = preview_x + sc * 2
                    if sy >= max_y - 4 or sx + 1 >= max_x:
                        break
                    if (sr, sc) in alive_set:
                        try:
                            self.stdscr.addstr(sy, sx, "██",
                                               curses.color_pair(4) | curses.A_BOLD)
                        except curses.error:
                            pass

    # ── Detail of selected ──
    detail_y = max_y - 3
    if detail_y > 0 and 0 <= sel < len(self.adisco_gallery):
        entry = self.adisco_gallery[sel]
        genome = entry["genome"]
        detail = (f" {entry['label']}"
                  f"  |  nh:{genome.get('neighborhood', '?')}"
                  f"  density:{genome.get('density', 0):.2f}"
                  f"  seed:{genome.get('seed_style', '?')}"
                  f"  |  {entry.get('timestamp', '')}")
        try:
            self.stdscr.addstr(detail_y, 0, detail[:max_x - 1], curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [j/k]=navigate  [Enter]=adopt rule  [x]=remove  [W]=save gallery  [g/Esc]=back to explorer"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ── Registration ─────────────────────────────────────────────────────


def register(App):
    """Register Auto-Discovery methods on the App class."""
    App._enter_adisco_mode = _enter_adisco_mode
    App._exit_adisco_mode = _exit_adisco_mode
    App._adisco_init = _adisco_init
    App._adisco_step = _adisco_step
    App._adisco_score_and_curate = _adisco_score_and_curate
    App._adisco_breed_next = _adisco_breed_next
    App._adisco_save_gallery = _adisco_save_gallery
    App._adisco_load_gallery = _adisco_load_gallery
    App._adisco_adopt_rule = _adisco_adopt_rule
    App._handle_adisco_menu_key = _handle_adisco_menu_key
    App._handle_adisco_key = _handle_adisco_key
    App._handle_adisco_gallery_key = _handle_adisco_gallery_key
    App._draw_adisco_menu = _draw_adisco_menu
    App._draw_adisco = _draw_adisco
    App._draw_adisco_gallery = _draw_adisco_gallery
