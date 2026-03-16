"""Mode: genesis_protocol — Autonomous Open-Ended Evolution Engine.

Seeds random rule combinations, runs them forward, scores them for emergent
complexity using information-theoretic metrics (Shannon entropy, transfer
entropy, causal density, symmetry, periodicity), and curates a persistent
ranked gallery of the most interesting discovered universes.

The system autonomously explores the CA rule-space, discovering gliders,
oscillators, self-replicating structures, and phase transitions — building
a hall-of-fame that persists across sessions.

Launch it and watch the simulator explore on its own.
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
    classify_stability,
)
from life.constants import SAVE_DIR, SPEEDS
from life.grid import Grid
from life.rules import rule_string, parse_rule_string

# ── Constants ────────────────────────────────────────────────────────

_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]
_SPARKLINE = "▁▂▃▄▅▆▇█"

_GALLERY_FILE = os.path.join(SAVE_DIR, "genesis_hall_of_fame.json")

_SEED_STYLES = ["random", "symmetric", "clustered", "sparse", "striped", "central"]

# Evaluation parameters
_EVAL_GENERATIONS = 120       # run each universe this many gens
_TRANSFER_ENTROPY_WINDOW = 8  # history frames for TE computation
_TE_SAMPLE_SIZE = 16          # NxN sample resolution for TE
_MIN_POP_FRAC = 0.005
_MAX_POP_FRAC = 0.85

# Score tier thresholds and color pairs
_TIER_COLORS = [
    (1, curses.A_DIM), (1, 0), (4, curses.A_DIM), (4, 0),
    (6, curses.A_DIM), (6, 0), (7, 0), (7, curses.A_BOLD),
]

# Structure detection labels
_STRUCTURE_LABELS = {
    "glider": "⟐",
    "oscillator": "∿",
    "still_life": "■",
    "replicator": "⊛",
    "chaotic": "⊘",
    "expanding": "◎",
    "collapsing": "◉",
}


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
        "density": max(0.02, min(0.6, (g1["density"] + g2["density"]) / 2 + random.gauss(0, 0.03))),
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
    if random.random() < rate:
        g["density"] = max(0.02, min(0.6, g["density"] + random.gauss(0, 0.08)))
    if random.random() < rate * 0.5:
        g["seed_style"] = random.choice(_SEED_STYLES)
    if random.random() < rate * 0.2:
        g["neighborhood"] = "von_neumann" if g["neighborhood"] == "moore" else "moore"
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
    for r in range(rows):
        for c in range(cols):
            grid.cells[r][c] = 0

    if style == "symmetric":
        hr, hc = rows // 2, cols // 2
        for r in range(hr):
            for c in range(hc):
                if random.random() < density:
                    grid.cells[r][c] = 1
                    grid.cells[r][cols - 1 - c] = 1
                    grid.cells[rows - 1 - r][c] = 1
                    grid.cells[rows - 1 - r][cols - 1 - c] = 1
    elif style == "clustered":
        n_clusters = random.randint(2, 5)
        for _ in range(n_clusters):
            cr, cc = random.randint(0, rows - 1), random.randint(0, cols - 1)
            radius = random.randint(2, min(6, rows // 3))
            for r in range(max(0, cr - radius), min(rows, cr + radius)):
                for c in range(max(0, cc - radius), min(cols, cc + radius)):
                    if random.random() < density * 1.5:
                        grid.cells[r][c] = 1
    elif style == "sparse":
        for r in range(rows):
            for c in range(cols):
                if random.random() < density * 0.3:
                    grid.cells[r][c] = 1
    elif style == "striped":
        horiz = random.random() < 0.5
        stripe_w = random.randint(1, 3)
        for r in range(rows):
            for c in range(cols):
                coord = r if horiz else c
                if (coord // stripe_w) % 2 == 0 and random.random() < density:
                    grid.cells[r][c] = 1
    elif style == "central":
        cr, cc = rows // 2, cols // 2
        for r in range(rows):
            for c in range(cols):
                dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
                max_dist = math.sqrt(cr ** 2 + cc ** 2) or 1
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
    g._genesis_nh = genome["neighborhood"]
    _seed_grid(g, genome["density"], genome["seed_style"])
    return g


def _step_sim(grid):
    """Step a mini simulation respecting per-grid neighborhood."""
    rows, cols = grid.rows, grid.cols
    nh = getattr(grid, '_genesis_nh', 'moore')
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


# ── Information-theoretic scoring ────────────────────────────────────

def _sample_grid_float(grid, N):
    """Downsample grid to NxN float [0,1] for TE computation."""
    rows, cols = grid.rows, grid.cols
    result = [[0.0] * N for _ in range(N)]
    for r in range(N):
        gr = int(r * rows / N) % rows
        for c in range(N):
            gc = int(c * cols / N) % cols
            result[r][c] = 1.0 if grid.cells[gr][gc] > 0 else 0.0
    return result


def _compute_transfer_entropy(history, N):
    """Simplified total outgoing transfer entropy per cell.

    Sums TE from each cell to 4 cardinal neighbors.
    Returns mean TE across all cells (scalar).
    """
    if len(history) < 3:
        return 0.0

    T = len(history)
    total_te = 0.0
    count = 0

    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        for r in range(N):
            for c in range(N):
                sr = (r + dr) % N
                sc = (c + dc) % N

                counts = {}
                pair_counts = {}
                single_counts = {}
                marginal = {}

                for t in range(1, T):
                    y_prev = 1 if history[t - 1][r][c] > 0.5 else 0
                    x_prev = 1 if history[t - 1][sr][sc] > 0.5 else 0
                    y_curr = 1 if history[t][r][c] > 0.5 else 0

                    key3 = (y_prev, x_prev, y_curr)
                    counts[key3] = counts.get(key3, 0) + 1
                    key2 = (y_prev, x_prev)
                    pair_counts[key2] = pair_counts.get(key2, 0) + 1
                    key_s = (y_prev, y_curr)
                    single_counts[key_s] = single_counts.get(key_s, 0) + 1
                    marginal[y_prev] = marginal.get(y_prev, 0) + 1

                n_total = T - 1
                te_val = 0.0
                for (yp, xp, yc), cnt in counts.items():
                    p_joint = cnt / n_total
                    p_cond_full = cnt / pair_counts[(yp, xp)]
                    sc_cnt = single_counts.get((yp, yc), 0)
                    m_cnt = marginal.get(yp, 0)
                    if sc_cnt > 0 and m_cnt > 0:
                        p_cond_reduced = sc_cnt / m_cnt
                        if p_cond_full > 0 and p_cond_reduced > 0:
                            te_val += p_joint * math.log2(
                                p_cond_full / p_cond_reduced
                            )

                total_te += max(0.0, te_val)
                count += 1

    return total_te / max(count, 1)


def _compute_spatial_complexity(grid):
    """Edge density as proxy for spatial structure."""
    rows, cols = grid.rows, grid.cols
    edges = 0
    total = 0
    for r in range(rows):
        row = grid.cells[r]
        for c in range(cols - 1):
            a = 1 if row[c] > 0 else 0
            b = 1 if row[c + 1] > 0 else 0
            if a != b:
                edges += 1
            total += 1
        if r < rows - 1:
            next_row = grid.cells[r + 1]
            for c in range(cols):
                a = 1 if row[c] > 0 else 0
                b = 1 if next_row[c] > 0 else 0
                if a != b:
                    edges += 1
                total += 1
    return edges / total if total > 0 else 0.0


def _detect_motion(pop_history, grid, prev_cells):
    """Detect glider-like motion by checking if the pattern translates."""
    if prev_cells is None:
        return False
    rows, cols = grid.rows, grid.cols
    # Check if active region centroid shifted
    cur_r, cur_c, cur_n = 0.0, 0.0, 0
    prv_r, prv_c, prv_n = 0.0, 0.0, 0
    for r in range(rows):
        for c in range(cols):
            if grid.cells[r][c] > 0:
                cur_r += r
                cur_c += c
                cur_n += 1
            if prev_cells[r][c] > 0:
                prv_r += r
                prv_c += c
                prv_n += 1
    if cur_n == 0 or prv_n == 0:
        return False
    dr = abs(cur_r / cur_n - prv_r / prv_n)
    dc = abs(cur_c / cur_n - prv_c / prv_n)
    return dr > 0.3 or dc > 0.3


def _classify_universe(grid, pop_history, period_det, te_score, has_motion):
    """Classify a universe into a structural category."""
    total_cells = grid.rows * grid.cols
    if total_cells == 0:
        return "collapsing"

    pop_frac = grid.population / total_cells
    period = period_det.period

    if grid.population == 0:
        return "collapsing"
    if pop_frac > _MAX_POP_FRAC:
        return "expanding"
    if period is not None and period == 1:
        return "still_life"
    if has_motion and period is not None and 2 <= period <= 20:
        return "glider"
    if period is not None and 2 <= period <= 50:
        return "oscillator"
    if has_motion and te_score > 0.05:
        return "replicator"
    return "chaotic"


def _compute_universe_score(grid, pop_history, period_det, te_score,
                            spatial_complexity, classification):
    """Score a universe for emergent complexity. Higher = more interesting.

    Combines: Shannon entropy, transfer entropy, symmetry, spatial complexity,
    population dynamics, periodicity quality, and structural classification.
    """
    if not pop_history or len(pop_history) < 10:
        return 0.0

    total_cells = grid.rows * grid.cols
    score = 0.0

    # ── Shannon entropy (0-50 pts) ──
    ent = shannon_entropy(grid)
    score += min(ent / 1.0, 1.0) * 50.0

    # ── Transfer entropy (0-60 pts) — information flow ──
    score += min(te_score / 0.1, 1.0) * 60.0

    # ── Symmetry (0-40 pts) — partial symmetry is most interesting ──
    sym = symmetry_score(grid)
    avg_sym = (sym["horiz"] + sym["vert"] + sym["rot180"]) / 3
    if 0.15 < avg_sym < 0.85:
        score += 40.0 * (1.0 - abs(avg_sym - 0.5) * 2)
    elif avg_sym >= 0.85:
        score += 15.0  # too symmetric — still somewhat interesting

    # ── Spatial complexity (0-40 pts) ──
    if 0.1 < spatial_complexity < 0.7:
        score += 40.0 * min(spatial_complexity / 0.35, 1.0)

    # ── Population dynamics (0-30 pts) ──
    recent = pop_history[-40:]
    avg_pop = sum(recent) / len(recent) if recent else 0
    if avg_pop > 0 and total_cells > 0:
        pop_frac = avg_pop / total_cells
        if 0.05 < pop_frac < 0.6:
            score += 20.0
        elif 0.01 < pop_frac < 0.85:
            score += 8.0

        variance = sum((p - avg_pop) ** 2 for p in recent) / len(recent)
        cv = math.sqrt(variance) / max(avg_pop, 1)
        if 0.02 < cv < 0.3:
            score += 10.0  # interesting oscillation

    # ── Periodicity quality (0-25 pts) ──
    period = period_det.period
    if period is not None:
        if 2 <= period <= 8:
            score += 25.0  # clean oscillator
        elif 8 < period <= 50:
            score += 20.0  # medium cycle
        elif period > 50:
            score += 15.0  # long cycle
        elif period == 1:
            score -= 15.0  # static — boring

    # ── Structure classification bonus (0-30 pts) ──
    class_bonus = {
        "glider": 30.0,
        "replicator": 25.0,
        "oscillator": 20.0,
        "chaotic": 10.0,
        "still_life": 0.0,
        "expanding": -10.0,
        "collapsing": -20.0,
    }
    score += class_bonus.get(classification, 0.0)

    # ── Penalties ──
    if grid.population == 0:
        score -= 50.0
    if total_cells > 0 and grid.population > total_cells * 0.85:
        score *= 0.3

    return max(0.0, score)


# ── Gallery persistence ──────────────────────────────────────────────

def _snapshot_cells(grid, max_rows=24, max_cols=32):
    """Capture a compact snapshot of live cell positions."""
    alive = []
    for r in range(min(grid.rows, max_rows)):
        for c in range(min(grid.cols, max_cols)):
            if grid.cells[r][c] > 0:
                alive.append((r, c))
    return alive


def _save_hall_of_fame(gallery):
    """Save the hall of fame to disk."""
    if not gallery:
        return
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(_GALLERY_FILE, "w") as f:
        json.dump(gallery, f, indent=2)


def _load_hall_of_fame():
    """Load hall of fame from disk."""
    if not os.path.isfile(_GALLERY_FILE):
        return []
    try:
        with open(_GALLERY_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


# ── Sparkline helper ─────────────────────────────────────────────────

def _sparkline(data, width):
    """Render a sparkline string."""
    if not data or width <= 0:
        return ""
    vals = list(data[-width:])
    lo, hi = min(vals), max(vals)
    span = hi - lo if hi != lo else 1
    out = []
    for v in vals:
        idx = int((v - lo) / span * (len(_SPARKLINE) - 1))
        idx = max(0, min(idx, len(_SPARKLINE) - 1))
        out.append(_SPARKLINE[idx])
    return "".join(out)


# ── Mode functions ───────────────────────────────────────────────────

def _enter_genesis_mode(self):
    """Enter Genesis Protocol — show preset/settings menu."""
    self.genesis_mode = False
    self.genesis_menu = True
    self.genesis_menu_sel = 0
    # Load existing hall of fame
    self.genesis_hall = _load_hall_of_fame()
    self._flash("Genesis Protocol — autonomous universe discovery engine")


def _exit_genesis_mode(self):
    """Clean up and exit."""
    # Auto-save hall of fame on exit
    if self.genesis_hall:
        _save_hall_of_fame(self.genesis_hall)
    self.genesis_mode = False
    self.genesis_menu = False
    self.genesis_running = False
    self.genesis_sims = []
    self.genesis_genomes = []
    self.genesis_hall_view = False
    self._flash("Genesis Protocol OFF")


def _genesis_init_state(self):
    """Initialize state variables."""
    self.genesis_mode = False
    self.genesis_menu = False
    self.genesis_menu_sel = 0
    self.genesis_running = False
    # Population of universes
    self.genesis_sims = []        # list of Grid objects
    self.genesis_genomes = []     # corresponding genomes
    self.genesis_pop_histories = []
    self.genesis_period_dets = []
    self.genesis_te_histories = []  # TE sample history per sim
    self.genesis_prev_cells = []    # for motion detection
    self.genesis_fitness = []       # score dicts
    self.genesis_classifications = []
    # Layout
    self.genesis_grid_rows = 2
    self.genesis_grid_cols = 4
    self.genesis_tile_h = 10
    self.genesis_tile_w = 10
    # Config
    self.genesis_batch_size = 8
    self.genesis_eval_steps = _EVAL_GENERATIONS
    self.genesis_mutation_rate = 0.15
    self.genesis_hall_max = 50
    # State
    self.genesis_round = 0
    self.genesis_sim_step = 0
    self.genesis_phase = "idle"   # idle, simulating, scored
    self.genesis_cursor = 0
    self.genesis_auto_continue = True
    self.genesis_hall = []
    self.genesis_hall_view = False
    self.genesis_hall_sel = 0
    self.genesis_hall_scroll = 0
    self.genesis_history = []      # per-round summary
    self.genesis_total_universes = 0
    self.genesis_best_ever_score = 0.0
    self.genesis_best_ever_rule = ""
    self.genesis_hall_threshold = 80.0


def _genesis_start_round(self, seed_genomes=None):
    """Spawn a batch of universe candidates and start simulating."""
    max_y, max_x = self.stdscr.getmaxyx()
    usable_h = max_y - 6
    usable_w = max_x - 1

    batch_size = self.genesis_batch_size

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

    self.genesis_grid_rows = best_r
    self.genesis_grid_cols = best_c
    actual_batch = min(batch_size, best_r * best_c)

    self.genesis_tile_h = max(4, usable_h // best_r - 1)
    self.genesis_tile_w = max(4, (usable_w // best_c - 1) // 2)

    sim_rows = max(4, self.genesis_tile_h - 2)
    sim_cols = max(4, self.genesis_tile_w)

    # Generate genomes
    if seed_genomes and len(seed_genomes) >= 2:
        genomes = []
        # Keep some elites
        for sg in seed_genomes[:actual_batch // 3]:
            genomes.append(dict(sg, birth=set(sg["birth"]), survival=set(sg["survival"])))
        # Breed rest via crossover + mutation
        while len(genomes) < actual_batch:
            p1 = random.choice(seed_genomes)
            p2 = random.choice(seed_genomes)
            child = _crossover(p1, p2)
            child = _mutate(child, self.genesis_mutation_rate)
            genomes.append(child)
        genomes = genomes[:actual_batch]
    else:
        genomes = [_random_genome() for _ in range(actual_batch)]

    # Create simulations
    self.genesis_sims = []
    self.genesis_genomes = genomes
    self.genesis_pop_histories = []
    self.genesis_fitness = [{} for _ in range(len(genomes))]
    self.genesis_classifications = ["" for _ in range(len(genomes))]
    self.genesis_period_dets = []
    self.genesis_te_histories = []
    self.genesis_prev_cells = []

    for genome in genomes:
        grid = _create_sim(genome, sim_rows, sim_cols)
        self.genesis_sims.append(grid)
        self.genesis_pop_histories.append([grid.population])
        self.genesis_period_dets.append(PeriodicityDetector(max_history=300))
        self.genesis_te_histories.append([])
        self.genesis_prev_cells.append(None)

    self.genesis_cursor = 0
    self.genesis_sim_step = 0
    self.genesis_phase = "simulating"
    self.genesis_mode = True
    self.genesis_menu = False
    self.genesis_running = True
    self.genesis_hall_view = False
    self.genesis_round += 1
    self.genesis_total_universes += actual_batch

    self._flash(f"Genesis round {self.genesis_round}: seeding {actual_batch} universes...")


def _genesis_step(self):
    """Advance all universe candidates by one step."""
    if self.genesis_phase != "simulating":
        return

    N = _TE_SAMPLE_SIZE

    for i, grid in enumerate(self.genesis_sims):
        # Save previous cells for motion detection (every 20 steps)
        if self.genesis_sim_step % 20 == 0 and self.genesis_sim_step > 0:
            self.genesis_prev_cells[i] = [row[:] for row in grid.cells]

        _step_sim(grid)
        self.genesis_pop_histories[i].append(grid.population)

        # Periodicity detection every 5 steps
        if self.genesis_sim_step % 5 == 0:
            self.genesis_period_dets[i].update(grid)

        # Sample for TE computation every 10 steps
        if self.genesis_sim_step % 10 == 0:
            sample = _sample_grid_float(grid, N)
            self.genesis_te_histories[i].append(sample)
            if len(self.genesis_te_histories[i]) > _TRANSFER_ENTROPY_WINDOW:
                self.genesis_te_histories[i] = self.genesis_te_histories[i][-_TRANSFER_ENTROPY_WINDOW:]

    self.genesis_sim_step += 1

    # Auto-score when done
    if self.genesis_sim_step >= self.genesis_eval_steps:
        _genesis_score_and_rank(self)


def _genesis_score_and_rank(self):
    """Score all universes, update hall of fame, breed next round."""
    self.genesis_phase = "scored"

    N = _TE_SAMPLE_SIZE

    for i, grid in enumerate(self.genesis_sims):
        # Compute transfer entropy
        te_score = _compute_transfer_entropy(self.genesis_te_histories[i], N)

        # Spatial complexity
        spatial = _compute_spatial_complexity(grid)

        # Motion detection
        has_motion = _detect_motion(
            self.genesis_pop_histories[i], grid, self.genesis_prev_cells[i]
        )

        # Classify
        classification = _classify_universe(
            grid, self.genesis_pop_histories[i],
            self.genesis_period_dets[i], te_score, has_motion,
        )
        self.genesis_classifications[i] = classification

        # Score
        score = _compute_universe_score(
            grid, self.genesis_pop_histories[i],
            self.genesis_period_dets[i], te_score,
            spatial, classification,
        )

        self.genesis_fitness[i] = {
            "total": score,
            "te": round(te_score, 4),
            "entropy": round(shannon_entropy(grid), 3),
            "spatial": round(spatial, 3),
            "class": classification,
        }

    # Sort by score (best first)
    indices = list(range(len(self.genesis_sims)))
    indices.sort(key=lambda i: -self.genesis_fitness[i].get("total", 0))

    self.genesis_sims = [self.genesis_sims[i] for i in indices]
    self.genesis_genomes = [self.genesis_genomes[i] for i in indices]
    self.genesis_fitness = [self.genesis_fitness[i] for i in indices]
    self.genesis_pop_histories = [self.genesis_pop_histories[i] for i in indices]
    self.genesis_period_dets = [self.genesis_period_dets[i] for i in indices]
    self.genesis_te_histories = [self.genesis_te_histories[i] for i in indices]
    self.genesis_prev_cells = [self.genesis_prev_cells[i] for i in indices]
    self.genesis_classifications = [self.genesis_classifications[i] for i in indices]

    # Add top performers to hall of fame
    added = 0
    for i in range(min(3, len(self.genesis_sims))):
        score = self.genesis_fitness[i].get("total", 0)
        if score >= self.genesis_hall_threshold:
            entry = {
                "genome": {
                    "birth": sorted(self.genesis_genomes[i]["birth"]),
                    "survival": sorted(self.genesis_genomes[i]["survival"]),
                    "neighborhood": self.genesis_genomes[i]["neighborhood"],
                    "density": round(self.genesis_genomes[i]["density"], 3),
                    "seed_style": self.genesis_genomes[i]["seed_style"],
                },
                "label": _genome_label(self.genesis_genomes[i]),
                "score": round(score, 1),
                "metrics": self.genesis_fitness[i],
                "classification": self.genesis_classifications[i],
                "round": self.genesis_round,
                "snapshot": _snapshot_cells(self.genesis_sims[i]),
                "sim_rows": self.genesis_sims[i].rows,
                "sim_cols": self.genesis_sims[i].cols,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            # Avoid near-duplicates
            label = entry["label"]
            if not any(g["label"] == label and abs(g["score"] - score) < 15
                       for g in self.genesis_hall):
                self.genesis_hall.append(entry)
                added += 1

    # Keep hall sorted and bounded
    self.genesis_hall.sort(key=lambda g: -g["score"])
    self.genesis_hall = self.genesis_hall[:self.genesis_hall_max]

    # Update adaptive threshold
    if len(self.genesis_hall) >= self.genesis_hall_max:
        self.genesis_hall_threshold = max(
            self.genesis_hall_threshold,
            self.genesis_hall[-1]["score"] * 0.95
        )

    # Track best ever
    best_score = self.genesis_fitness[0].get("total", 0) if self.genesis_fitness else 0
    if best_score > self.genesis_best_ever_score:
        self.genesis_best_ever_score = best_score
        self.genesis_best_ever_rule = _genome_label(self.genesis_genomes[0]) if self.genesis_genomes else ""

    best_label = _genome_label(self.genesis_genomes[0]) if self.genesis_genomes else "?"
    best_class = self.genesis_classifications[0] if self.genesis_classifications else "?"
    hall_size = len(self.genesis_hall)

    if added:
        self._flash(
            f"Round {self.genesis_round}: +{added} to Hall of Fame ({hall_size}) "
            f"— {best_label} [{best_class}] {best_score:.0f}pts"
        )
    else:
        self._flash(
            f"Round {self.genesis_round}: {best_label} [{best_class}] {best_score:.0f}pts"
        )

    # Track history
    avg_score = sum(f.get("total", 0) for f in self.genesis_fitness) / max(1, len(self.genesis_fitness))
    self.genesis_history.append({
        "round": self.genesis_round,
        "best_score": best_score,
        "best_rule": best_label,
        "best_class": best_class,
        "avg_score": avg_score,
        "hall_size": hall_size,
    })

    # Auto-save periodically
    if self.genesis_round % 5 == 0 and self.genesis_hall:
        _save_hall_of_fame(self.genesis_hall)

    # Auto-breed next round
    if self.genesis_auto_continue:
        _genesis_breed_next(self)


def _genesis_breed_next(self):
    """Breed next round from hall of fame + top performers."""
    parents = []
    # Draw from hall of fame
    for entry in self.genesis_hall[:8]:
        g = entry["genome"]
        parents.append({
            "birth": set(g["birth"]),
            "survival": set(g["survival"]),
            "neighborhood": g["neighborhood"],
            "density": g["density"],
            "seed_style": g["seed_style"],
        })
    # Add current top performers
    for i in range(min(4, len(self.genesis_genomes))):
        parents.append({
            "birth": set(self.genesis_genomes[i]["birth"]),
            "survival": set(self.genesis_genomes[i]["survival"]),
            "neighborhood": self.genesis_genomes[i]["neighborhood"],
            "density": self.genesis_genomes[i]["density"],
            "seed_style": self.genesis_genomes[i]["seed_style"],
        })

    # Inject some random genomes for diversity (exploration)
    n_random = max(1, self.genesis_batch_size // 4)
    parents_or_none = parents if len(parents) >= 2 else None

    self.genesis_sim_step = 0
    _genesis_start_round(self, seed_genomes=parents_or_none)


# ── Key handlers ─────────────────────────────────────────────────────

def _handle_genesis_menu_key(self, key):
    """Handle keys in the Genesis Protocol settings menu."""
    if key == -1:
        return True

    menu_items = [
        "batch_size", "eval_steps", "mutation_rate", "hall_max",
        "auto_continue", "start_fresh", "start_from_hall", "browse_hall",
    ]
    n = len(menu_items)

    if key in (curses.KEY_UP, ord("k")):
        self.genesis_menu_sel = (self.genesis_menu_sel - 1) % n
        return True
    if key in (curses.KEY_DOWN, ord("j")):
        self.genesis_menu_sel = (self.genesis_menu_sel + 1) % n
        return True
    if key == 27 or key == ord("q"):
        self.genesis_menu = False
        self._flash("Genesis Protocol cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER, ord(" ")):
        item = menu_items[self.genesis_menu_sel]
        if item == "batch_size":
            val = self._prompt_text(f"Batch size 4-20 (current: {self.genesis_batch_size})")
            if val:
                try:
                    v = int(val)
                    if 4 <= v <= 20:
                        self.genesis_batch_size = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "eval_steps":
            val = self._prompt_text(f"Eval steps 50-500 (current: {self.genesis_eval_steps})")
            if val:
                try:
                    v = int(val)
                    if 50 <= v <= 500:
                        self.genesis_eval_steps = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "mutation_rate":
            val = self._prompt_text(f"Mutation rate 0-100% (current: {int(self.genesis_mutation_rate * 100)}%)")
            if val:
                try:
                    v = int(val.replace("%", ""))
                    if 0 <= v <= 100:
                        self.genesis_mutation_rate = v / 100.0
                except ValueError:
                    self._flash("Invalid number")
        elif item == "hall_max":
            val = self._prompt_text(f"Hall of Fame max 10-200 (current: {self.genesis_hall_max})")
            if val:
                try:
                    v = int(val)
                    if 10 <= v <= 200:
                        self.genesis_hall_max = v
                except ValueError:
                    self._flash("Invalid number")
        elif item == "auto_continue":
            self.genesis_auto_continue = not self.genesis_auto_continue
            self._flash(f"Auto-continue: {'ON' if self.genesis_auto_continue else 'OFF'}")
        elif item == "start_fresh":
            self.genesis_round = 0
            self.genesis_history = []
            self.genesis_hall = []
            self.genesis_hall_threshold = 80.0
            self.genesis_total_universes = 0
            self.genesis_best_ever_score = 0.0
            self.genesis_best_ever_rule = ""
            _genesis_start_round(self)
        elif item == "start_from_hall":
            loaded = _load_hall_of_fame()
            if loaded:
                self.genesis_hall = loaded
                self.genesis_round = 0
                self.genesis_history = []
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
                _genesis_start_round(self, seed_genomes=parents)
            else:
                self._flash("No saved Hall of Fame — starting fresh")
                self.genesis_round = 0
                self.genesis_history = []
                self.genesis_hall = []
                self.genesis_hall_threshold = 80.0
                _genesis_start_round(self)
        elif item == "browse_hall":
            loaded = _load_hall_of_fame()
            if loaded:
                self.genesis_hall = loaded
                self.genesis_hall_view = True
                self.genesis_hall_sel = 0
                self.genesis_hall_scroll = 0
                self.genesis_mode = True
                self.genesis_menu = False
                self._flash(f"Hall of Fame: {len(loaded)} universes")
            else:
                self._flash("No saved Hall of Fame yet")
        return True
    return True


def _handle_genesis_key(self, key):
    """Handle keys during active Genesis Protocol exploration."""
    if key == -1:
        return True
    if key == 27 or key == ord("q"):
        _exit_genesis_mode(self)
        return True

    # Toggle hall of fame view
    if key == ord("h"):
        if self.genesis_hall:
            self.genesis_hall_view = not self.genesis_hall_view
            if self.genesis_hall_view:
                self.genesis_hall_sel = 0
                self.genesis_hall_scroll = 0
            self._flash("Hall of Fame" if self.genesis_hall_view else "Explorer")
        else:
            self._flash("Hall of Fame empty — keep exploring!")
        return True

    # Hall of fame view keys
    if self.genesis_hall_view:
        return _handle_genesis_hall_key(self, key)

    pop_size = len(self.genesis_sims)
    gc = self.genesis_grid_cols

    # Play/pause
    if key == ord(" "):
        self.genesis_running = not self.genesis_running
        if self.genesis_phase == "scored" and self.genesis_running:
            _genesis_breed_next(self)
        else:
            self._flash("Running" if self.genesis_running else "Paused")
        return True

    # Navigate cursor
    if key == curses.KEY_UP or key == ord("w"):
        self.genesis_cursor = max(0, self.genesis_cursor - gc)
        return True
    if key == curses.KEY_DOWN or key == ord("s"):
        self.genesis_cursor = min(pop_size - 1, self.genesis_cursor + gc)
        return True
    if key == curses.KEY_LEFT or key == ord("a"):
        self.genesis_cursor = max(0, self.genesis_cursor - 1)
        return True
    if key == curses.KEY_RIGHT or key == ord("d"):
        self.genesis_cursor = min(pop_size - 1, self.genesis_cursor + 1)
        return True

    # Skip to scoring
    if key == ord("S"):
        if self.genesis_phase == "simulating":
            remaining = self.genesis_eval_steps - self.genesis_sim_step
            for _ in range(remaining):
                for i, grid in enumerate(self.genesis_sims):
                    _step_sim(grid)
                    self.genesis_pop_histories[i].append(grid.population)
                self.genesis_sim_step += 1
            _genesis_score_and_rank(self)
        return True

    # Force breed
    if key == ord("b"):
        if self.genesis_phase == "simulating":
            _genesis_score_and_rank(self)
        elif self.genesis_phase == "scored":
            _genesis_breed_next(self)
        return True

    # Toggle auto-continue
    if key == ord("A"):
        self.genesis_auto_continue = not self.genesis_auto_continue
        self._flash(f"Auto-continue: {'ON' if self.genesis_auto_continue else 'OFF'}")
        return True

    # Save hall of fame
    if key == ord("W"):
        if self.genesis_hall:
            _save_hall_of_fame(self.genesis_hall)
            self._flash(f"Hall of Fame saved: {len(self.genesis_hall)} universes → {_GALLERY_FILE}")
        else:
            self._flash("Hall of Fame empty — nothing to save")
        return True

    # Adopt current cursor's rule
    if key == ord("a"):
        if 0 <= self.genesis_cursor < pop_size:
            genome = self.genesis_genomes[self.genesis_cursor]
            self.grid.birth = set(genome["birth"])
            self.grid.survival = set(genome["survival"])
            label = _genome_label(genome)
            _exit_genesis_mode(self)
            self._flash(f"Adopted universe rule: {label}")
        return True

    # New random batch
    if key == ord("r"):
        self.genesis_round = 0
        self.genesis_history = []
        _genesis_start_round(self)
        self._flash("New random genesis")
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
        self.genesis_mode = False
        self.genesis_running = False
        self.genesis_menu = True
        self.genesis_menu_sel = 0
        return True

    return True


def _handle_genesis_hall_key(self, key):
    """Handle keys in hall of fame browsing view."""
    n = len(self.genesis_hall)
    if n == 0:
        self.genesis_hall_view = False
        return True

    if key in (curses.KEY_UP, ord("k")):
        self.genesis_hall_sel = max(0, self.genesis_hall_sel - 1)
        return True
    if key in (curses.KEY_DOWN, ord("j")):
        self.genesis_hall_sel = min(n - 1, self.genesis_hall_sel + 1)
        return True

    # Adopt selected rule
    if key in (10, 13, curses.KEY_ENTER):
        entry = self.genesis_hall[self.genesis_hall_sel]
        genome = entry["genome"]
        self.grid.birth = set(genome["birth"])
        self.grid.survival = set(genome["survival"])
        label = entry["label"]
        _exit_genesis_mode(self)
        self._flash(f"Adopted universe: {label}")
        return True

    # Delete from hall
    if key == ord("x"):
        self.genesis_hall.pop(self.genesis_hall_sel)
        self.genesis_hall_sel = min(self.genesis_hall_sel, len(self.genesis_hall) - 1)
        self._flash("Removed from Hall of Fame")
        return True

    # Save
    if key == ord("W"):
        _save_hall_of_fame(self.genesis_hall)
        self._flash(f"Hall of Fame saved: {len(self.genesis_hall)} universes")
        return True

    # Back
    if key == ord("h") or key == 27:
        self.genesis_hall_view = False
        return True

    return True


# ── Auto-stepping check ─────────────────────────────────────────────

def _is_genesis_auto_stepping(self):
    """Check if Genesis Protocol should auto-step."""
    return self.genesis_running and self.genesis_phase == "simulating"


# ── Drawing ──────────────────────────────────────────────────────────

def _draw_genesis_menu(self, max_y, max_x):
    """Draw the Genesis Protocol settings menu."""
    self.stdscr.erase()

    title = "═══ Genesis Protocol ═══"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Autonomous open-ended evolution engine — discovers the most complex universes"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2),
                           subtitle[:max_x - 2], curses.A_DIM)
    except curses.error:
        pass

    # Stats line
    hall_count = len(self.genesis_hall)
    stats = f"Hall of Fame: {hall_count} universes"
    if self.genesis_best_ever_score > 0:
        stats += f"  |  Best: {self.genesis_best_ever_rule} ({self.genesis_best_ever_score:.0f}pts)"
    if self.genesis_total_universes > 0:
        stats += f"  |  Total explored: {self.genesis_total_universes}"
    try:
        self.stdscr.addstr(5, max(0, (max_x - len(stats)) // 2),
                           stats[:max_x - 2],
                           curses.color_pair(6) if curses.has_colors() else curses.A_DIM)
    except curses.error:
        pass

    items = [
        ("Batch Size", str(self.genesis_batch_size), "Universes per round (4-20)"),
        ("Eval Steps", str(self.genesis_eval_steps), "Generations per universe (50-500)"),
        ("Mutation Rate", f"{int(self.genesis_mutation_rate * 100)}%", "Mutation rate for offspring"),
        ("Hall of Fame Max", str(self.genesis_hall_max), "Max hall entries (10-200)"),
        ("Auto-Continue", "ON" if self.genesis_auto_continue else "OFF", "Auto-breed next round"),
        (">>> START FRESH <<<", "", "Begin exploring from scratch"),
        (">>> START FROM HALL OF FAME <<<", "", "Evolve from previously discovered universes"),
        (">>> BROWSE HALL OF FAME <<<", "", "View ranked universe gallery"),
    ]

    y = 7
    for i, (label, value, hint) in enumerate(items):
        if y >= max_y - 4:
            break
        prefix = "▸ " if i == self.genesis_menu_sel else "  "
        if i >= 5:
            # Action items
            attr = curses.A_BOLD | curses.A_REVERSE if i == self.genesis_menu_sel else curses.A_BOLD
            line = f"{prefix}{label}"
            try:
                self.stdscr.addstr(y, 4, line[:max_x - 8], attr)
            except curses.error:
                pass
        else:
            attr = curses.A_BOLD | curses.A_REVERSE if i == self.genesis_menu_sel else 0
            line = f"{prefix}{label}: {value}"
            try:
                self.stdscr.addstr(y, 4, line[:max_x - 8], attr)
            except curses.error:
                pass
            if i == self.genesis_menu_sel:
                y += 1
                try:
                    self.stdscr.addstr(y, 8, hint[:max_x - 12], curses.A_DIM)
                except curses.error:
                    pass
        y += 2

    # Help
    try:
        help_text = "↑/↓ or j/k: navigate  Enter/Space: select  q: cancel"
        self.stdscr.addstr(max_y - 2, 4, help_text[:max_x - 8], curses.A_DIM)
    except curses.error:
        pass


def _draw_genesis(self, max_y, max_x):
    """Render the Genesis Protocol explorer or hall of fame."""
    if self.genesis_hall_view:
        _draw_genesis_hall(self, max_y, max_x)
        return

    self.stdscr.erase()

    pop_size = len(self.genesis_sims)
    if pop_size == 0:
        try:
            self.stdscr.addstr(1, 2, "No universes — press R for menu", curses.A_DIM)
        except curses.error:
            pass
        return

    gr = self.genesis_grid_rows
    gc = self.genesis_grid_cols
    th = self.genesis_tile_h
    tw = self.genesis_tile_w

    # Draw universe tiles
    for idx in range(pop_size):
        row = idx // gc
        col = idx % gc
        sy = row * (th + 1)
        sx = col * (tw * 2 + 1)

        if sy >= max_y - 4 or sx >= max_x - 2:
            continue

        grid = self.genesis_sims[idx]
        genome = self.genesis_genomes[idx]
        fitness = self.genesis_fitness[idx]
        classification = self.genesis_classifications[idx] if idx < len(self.genesis_classifications) else ""

        is_cursor = (idx == self.genesis_cursor)

        # Tile border
        label = _genome_label(genome)
        score = fitness.get("total", 0) if isinstance(fitness, dict) else 0
        class_icon = _STRUCTURE_LABELS.get(classification, " ")

        # Header
        header = f"{class_icon} {label}"
        if score > 0:
            header += f" {score:.0f}"
        header = header[:tw * 2 - 1]

        try:
            attr = curses.A_BOLD if is_cursor else curses.A_DIM
            if is_cursor:
                attr |= curses.A_REVERSE
            self.stdscr.addstr(sy, sx, header[:max_x - sx - 1], attr)
        except curses.error:
            pass

        # Draw grid cells
        display_rows = min(grid.rows, th - 1)
        display_cols = min(grid.cols, tw)
        for r in range(display_rows):
            for c in range(display_cols):
                py = sy + 1 + r
                px = sx + c * 2
                if py >= max_y - 2 or px + 1 >= max_x:
                    continue
                try:
                    v = grid.cells[r][c]
                    if v > 0:
                        # Color by age
                        if v <= 2:
                            pair = 1
                        elif v <= 5:
                            pair = 4
                        elif v <= 15:
                            pair = 6
                        elif v <= 30:
                            pair = 7
                        else:
                            pair = 3
                        cattr = curses.color_pair(pair) if curses.has_colors() else 0
                        self.stdscr.addstr(py, px, "██", cattr)
                except curses.error:
                    pass

    # Draw info panel on right (if room)
    panel_w = 36
    if max_x > gc * (tw * 2 + 1) + panel_w + 2:
        px = max_x - panel_w
        _draw_genesis_panel(self, max_y, max_x, px, panel_w)

    # Status bar
    _draw_genesis_status(self, max_y, max_x)


def _draw_genesis_panel(self, max_y, max_x, px, panel_w):
    """Draw the info panel on the right side."""
    py = 0

    try:
        self.stdscr.addstr(py, px, "Genesis Protocol", curses.A_BOLD)
        py += 1

        # Current round & phase
        phase_str = self.genesis_phase.upper()
        if self.genesis_phase == "simulating":
            progress = self.genesis_sim_step / max(self.genesis_eval_steps, 1)
            bar_w = panel_w - 4
            filled = int(progress * bar_w)
            bar = "█" * filled + "░" * (bar_w - filled)
            self.stdscr.addstr(py, px, f"Round {self.genesis_round}: [{bar}]"[:panel_w - 1])
        else:
            self.stdscr.addstr(py, px, f"Round {self.genesis_round}: {phase_str}"[:panel_w - 1])
        py += 1

        self.stdscr.addstr(py, px, f"Step {self.genesis_sim_step}/{self.genesis_eval_steps}")
        py += 1

        self.stdscr.addstr(py, px, f"Universes explored: {self.genesis_total_universes}")
        py += 1

        hall_size = len(self.genesis_hall)
        self.stdscr.addstr(py, px, f"Hall of Fame: {hall_size}/{self.genesis_hall_max}")
        py += 2

        # Current cursor info
        if 0 <= self.genesis_cursor < len(self.genesis_sims):
            idx = self.genesis_cursor
            genome = self.genesis_genomes[idx]
            fitness = self.genesis_fitness[idx]
            classification = self.genesis_classifications[idx] if idx < len(self.genesis_classifications) else ""

            self.stdscr.addstr(py, px, "── Selected ──", curses.A_BOLD)
            py += 1
            self.stdscr.addstr(py, px, f"Rule: {_genome_label(genome)}"[:panel_w - 1])
            py += 1
            icon = _STRUCTURE_LABELS.get(classification, "?")
            self.stdscr.addstr(py, px, f"Class: {icon} {classification}")
            py += 1

            if isinstance(fitness, dict) and fitness:
                self.stdscr.addstr(py, px, f"Score: {fitness.get('total', 0):.1f}")
                py += 1
                self.stdscr.addstr(py, px, f"Entropy: {fitness.get('entropy', 0):.3f}")
                py += 1
                self.stdscr.addstr(py, px, f"TE: {fitness.get('te', 0):.4f}")
                py += 1
                self.stdscr.addstr(py, px, f"Spatial: {fitness.get('spatial', 0):.3f}")
                py += 1

            grid = self.genesis_sims[idx]
            total = grid.rows * grid.cols
            pop_pct = grid.population / total * 100 if total > 0 else 0
            self.stdscr.addstr(py, px, f"Pop: {grid.population} ({pop_pct:.0f}%)")
            py += 1

            period = self.genesis_period_dets[idx].period
            if period is not None:
                self.stdscr.addstr(py, px, f"Period: {period}")
                py += 1

            # Population sparkline
            pop_hist = self.genesis_pop_histories[idx]
            if pop_hist:
                py += 1
                self.stdscr.addstr(py, px, "── Population ──", curses.A_BOLD)
                py += 1
                spark = _sparkline(pop_hist, panel_w - 2)
                self.stdscr.addstr(py, px, spark, curses.A_DIM)
                py += 1

        # Best ever
        py += 1
        if self.genesis_best_ever_score > 0:
            self.stdscr.addstr(py, px, "── Best Ever ──", curses.A_BOLD)
            py += 1
            self.stdscr.addstr(py, px, f"{self.genesis_best_ever_rule}"[:panel_w - 1])
            py += 1
            self.stdscr.addstr(py, px, f"Score: {self.genesis_best_ever_score:.1f}")
            py += 2

        # Round history sparkline
        if self.genesis_history:
            self.stdscr.addstr(py, px, "── Score History ──", curses.A_BOLD)
            py += 1
            scores = [h["best_score"] for h in self.genesis_history]
            spark = _sparkline(scores, panel_w - 2)
            self.stdscr.addstr(py, px, spark, curses.A_DIM)
            py += 1

            # Classification breakdown of latest round
            if self.genesis_classifications:
                class_counts = {}
                for cl in self.genesis_classifications:
                    if cl:
                        class_counts[cl] = class_counts.get(cl, 0) + 1
                breakdown = " ".join(
                    f"{_STRUCTURE_LABELS.get(k, '?')}{v}"
                    for k, v in sorted(class_counts.items())
                )
                if breakdown:
                    py += 1
                    self.stdscr.addstr(py, px, breakdown[:panel_w - 1], curses.A_DIM)

    except curses.error:
        pass


def _draw_genesis_status(self, max_y, max_x):
    """Draw status bar at bottom."""
    try:
        status_y = max_y - 1
        state = "▶ RUN" if self.genesis_running else "⏸ STOP"
        auto = "auto:ON" if self.genesis_auto_continue else "auto:OFF"
        bar = (f" {state} {auto} │ SPC:play h:hall W:save "
               f"S:skip b:breed r:reset A:auto a:adopt q:quit ")
        self.stdscr.addstr(status_y, 0, bar[:max_x - 1], curses.A_REVERSE)
    except curses.error:
        pass


def _draw_genesis_hall(self, max_y, max_x):
    """Draw the Hall of Fame browsing view."""
    self.stdscr.erase()

    title = "═══ Hall of Fame — Discovered Universes ═══"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title, curses.A_BOLD)
    except curses.error:
        pass

    n = len(self.genesis_hall)
    if n == 0:
        try:
            self.stdscr.addstr(3, 4, "No universes discovered yet. Start exploring!", curses.A_DIM)
        except curses.error:
            pass
        return

    # List area
    list_w = max_x // 2 - 2
    list_h = max_y - 6

    # Scrolling
    if self.genesis_hall_sel < self.genesis_hall_scroll:
        self.genesis_hall_scroll = self.genesis_hall_sel
    if self.genesis_hall_sel >= self.genesis_hall_scroll + list_h:
        self.genesis_hall_scroll = self.genesis_hall_sel - list_h + 1

    # Draw list
    for i in range(self.genesis_hall_scroll, min(n, self.genesis_hall_scroll + list_h)):
        y = 3 + (i - self.genesis_hall_scroll)
        if y >= max_y - 3:
            break

        entry = self.genesis_hall[i]
        is_sel = (i == self.genesis_hall_sel)
        rank = i + 1
        classification = entry.get("classification", "?")
        icon = _STRUCTURE_LABELS.get(classification, "?")
        label = entry["label"]
        score = entry["score"]

        line = f"{'▸' if is_sel else ' '} #{rank:2d} {icon} {label:<20s} {score:6.1f}pts  [{classification}]"
        attr = curses.A_BOLD | curses.A_REVERSE if is_sel else 0

        # Color tier based on score
        if curses.has_colors() and score > 0:
            tier = min(int(score / 40), len(_TIER_COLORS) - 1)
            pair, extra = _TIER_COLORS[tier]
            if not is_sel:
                attr = curses.color_pair(pair) | extra

        try:
            self.stdscr.addstr(y, 2, line[:list_w], attr)
        except curses.error:
            pass

    # Detail panel (right half)
    if 0 <= self.genesis_hall_sel < n:
        entry = self.genesis_hall[self.genesis_hall_sel]
        dx = max_x // 2 + 1
        dw = max_x - dx - 2
        dy = 3

        try:
            self.stdscr.addstr(dy, dx, "── Universe Details ──", curses.A_BOLD)
            dy += 2

            self.stdscr.addstr(dy, dx, f"Rule: {entry['label']}")
            dy += 1

            classification = entry.get("classification", "?")
            icon = _STRUCTURE_LABELS.get(classification, "?")
            self.stdscr.addstr(dy, dx, f"Type: {icon} {classification}")
            dy += 1

            self.stdscr.addstr(dy, dx, f"Score: {entry['score']:.1f} pts")
            dy += 1

            genome = entry["genome"]
            self.stdscr.addstr(dy, dx, f"Seed: {genome['seed_style']}  Density: {genome['density']:.1%}")
            dy += 1

            nh = "Von Neumann" if genome.get("neighborhood") == "von_neumann" else "Moore"
            self.stdscr.addstr(dy, dx, f"Neighborhood: {nh}")
            dy += 1

            self.stdscr.addstr(dy, dx, f"Round: {entry.get('round', '?')}  {entry.get('timestamp', '')}")
            dy += 2

            # Metrics breakdown
            metrics = entry.get("metrics", {})
            if metrics:
                self.stdscr.addstr(dy, dx, "── Metrics ──", curses.A_BOLD)
                dy += 1
                for mk, mv in metrics.items():
                    if mk == "total":
                        continue
                    self.stdscr.addstr(dy, dx, f"  {mk}: {mv}")
                    dy += 1
                dy += 1

            # Render snapshot thumbnail
            snapshot = entry.get("snapshot", [])
            snap_rows = entry.get("sim_rows", 16)
            snap_cols = entry.get("sim_cols", 16)
            if snapshot and dy < max_y - 4:
                self.stdscr.addstr(dy, dx, "── Snapshot ──", curses.A_BOLD)
                dy += 1

                alive_set = set()
                for coord in snapshot:
                    if isinstance(coord, (list, tuple)) and len(coord) == 2:
                        alive_set.add((coord[0], coord[1]))

                preview_h = min(snap_rows, max_y - dy - 3)
                preview_w = min(snap_cols, dw // 2)
                for r in range(preview_h):
                    for c in range(preview_w):
                        py = dy + r
                        ppx = dx + c * 2
                        if py >= max_y - 2 or ppx + 1 >= max_x:
                            continue
                        if (r, c) in alive_set:
                            cattr = curses.color_pair(1) if curses.has_colors() else 0
                            self.stdscr.addstr(py, ppx, "██", cattr)

        except curses.error:
            pass

    # Status bar
    try:
        help_text = " ↑/↓:navigate  Enter:adopt  x:remove  W:save  h:back  q:quit "
        self.stdscr.addstr(max_y - 1, 0, help_text[:max_x - 1], curses.A_REVERSE)
    except curses.error:
        pass


# ── Registration ─────────────────────────────────────────────────────

def register(App):
    """Register Genesis Protocol mode methods on the App class."""
    App._enter_genesis_mode = _enter_genesis_mode
    App._exit_genesis_mode = _exit_genesis_mode
    App._genesis_step = _genesis_step
    App._handle_genesis_menu_key = _handle_genesis_menu_key
    App._handle_genesis_key = _handle_genesis_key
    App._draw_genesis_menu = _draw_genesis_menu
    App._draw_genesis = _draw_genesis
    App._is_genesis_auto_stepping = _is_genesis_auto_stepping
