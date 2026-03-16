"""Mode: rule_mutation — Real-Time Rule Mutation Engine.

Continuously evolves simulation rules toward maximum visual complexity using
entropy feedback. Mutates birth/survival sets each generation, keeps mutations
that increase Shannon entropy and spatial complexity, reverts ones that lead
to extinction or static states. A lineage sidebar shows the ancestry of the
current rule. The simulation discovers its own most visually complex behaviors.
"""
import curses
import math
import random
import time

from life.analytics import (
    PeriodicityDetector,
    shannon_entropy,
    symmetry_score,
)
from life.constants import SPEEDS
from life.grid import Grid
from life.rules import rule_string, parse_rule_string

# ── Constants ────────────────────────────────────────────────────────

_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]

_SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"

# How many generations to evaluate a mutant before deciding keep/revert
_EVAL_WINDOW = 40

# Minimum population fraction to avoid "extinction" revert
_MIN_POP_FRAC = 0.005

# Maximum population fraction to avoid "blob" revert (everything alive)
_MAX_POP_FRAC = 0.85

# Entropy improvement threshold to accept a mutation
_ENTROPY_ACCEPT_DELTA = -0.02  # accept if entropy >= prev - this margin

# Presets: (name, description, initial_rule_str, mutation_rate, seed_density)
RMUT_PRESETS = [
    ("Entropy Climber",
     "Start from Conway's Life, mutate toward maximum Shannon entropy",
     "B3/S23", 0.12, 0.35),
    ("Chaos Seeker",
     "Aggressive mutations from random rules — find the edge of chaos",
     None, 0.25, 0.4),
    ("Gentle Drift",
     "Slow mutations from HighLife — watch rules gradually shift",
     "B36/S23", 0.06, 0.3),
    ("Complexity Hunter",
     "Balanced approach: moderate mutation with diversity bonus",
     "B3/S23", 0.15, 0.35),
    ("From Nothing",
     "Start with empty ruleset and discover viable rules from scratch",
     "B/S", 0.3, 0.5),
    ("Day & Night Explorer",
     "Begin with Day & Night and explore neighboring rulesets",
     "B3678/S34678", 0.1, 0.3),
]


# ── Fitness scoring ──────────────────────────────────────────────────

def _compute_fitness(grid, pop_history, entropy_history, periodicity_det):
    """Score a rule's visual complexity. Higher = more interesting."""
    score = 0.0

    # Shannon entropy (0 to ~log2(max_states)) — main signal
    if entropy_history:
        avg_entropy = sum(entropy_history[-20:]) / len(entropy_history[-20:])
        score += avg_entropy * 40.0  # dominant factor

    # Population dynamics: reward moderate, changing populations
    if len(pop_history) >= 10:
        recent = pop_history[-20:]
        mean_pop = sum(recent) / len(recent)
        total_cells = grid.rows * grid.cols
        pop_frac = mean_pop / total_cells if total_cells > 0 else 0

        # Sweet spot: 5-60% alive
        if 0.05 < pop_frac < 0.6:
            score += 15.0
        elif 0.01 < pop_frac < 0.85:
            score += 5.0

        # Population variance (chaos indicator)
        if mean_pop > 0:
            variance = sum((x - mean_pop) ** 2 for x in recent) / len(recent)
            cv = math.sqrt(variance) / mean_pop
            # Moderate variance is interesting; too much or too little is boring
            if 0.02 < cv < 0.5:
                score += 20.0 * min(cv, 0.3) / 0.3
    else:
        # Not enough data yet
        return 0.0

    # Periodicity penalty: static or short cycles are boring
    period = periodicity_det.period
    if period is not None:
        if period == 1:
            score -= 20.0  # static
        elif period < 5:
            score -= 10.0  # short cycle
        elif period < 20:
            score += 5.0   # interesting oscillation
        else:
            score += 10.0  # complex cycle

    # Symmetry bonus: partial symmetry is more visually interesting than none or full
    sym = symmetry_score(grid)
    avg_sym = (sym["horiz"] + sym["vert"] + sym["rot180"]) / 3
    if 0.2 < avg_sym < 0.8:
        score += 10.0  # partial symmetry bonus

    # Extinction penalty
    if grid.population == 0:
        score -= 50.0

    return score


def _compute_spatial_complexity(grid):
    """Compute edge density as a proxy for spatial structure complexity."""
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


# ── Mutation operators ───────────────────────────────────────────────

def _mutate_rule(birth, survival, mutation_rate):
    """Mutate a birth/survival ruleset by flipping random digits."""
    new_birth = set(birth)
    new_survival = set(survival)

    for d in range(9):
        if random.random() < mutation_rate:
            if d in new_birth:
                new_birth.discard(d)
            else:
                new_birth.add(d)
        if random.random() < mutation_rate:
            if d in new_survival:
                new_survival.discard(d)
            else:
                new_survival.add(d)

    # Ensure at least one birth condition
    if not new_birth:
        new_birth.add(random.randint(1, 5))

    return new_birth, new_survival


def _random_rule():
    """Generate a random rule with reasonable constraints."""
    birth = {d for d in range(9) if random.random() < 0.3}
    survival = {d for d in range(9) if random.random() < 0.35}
    if not birth:
        birth.add(random.randint(1, 5))
    return birth, survival


def _crossover_rules(rule_a, rule_b):
    """Crossover two rules — take random bits from each parent."""
    birth_a, surv_a = rule_a
    birth_b, surv_b = rule_b
    new_birth = set()
    new_surv = set()
    for d in range(9):
        if random.random() < 0.5:
            if d in birth_a:
                new_birth.add(d)
        else:
            if d in birth_b:
                new_birth.add(d)
        if random.random() < 0.5:
            if d in surv_a:
                new_surv.add(d)
        else:
            if d in surv_b:
                new_surv.add(d)
    if not new_birth:
        new_birth.add(random.randint(1, 5))
    return new_birth, new_surv


# ── Lineage tracking ────────────────────────────────────────────────

class LineageNode:
    """Track the ancestry of rules."""
    __slots__ = ("rule_str", "fitness", "generation", "parent_str",
                 "accepted", "entropy", "population_frac")

    def __init__(self, rule_str, fitness, generation, parent_str,
                 accepted, entropy=0.0, population_frac=0.0):
        self.rule_str = rule_str
        self.fitness = fitness
        self.generation = generation
        self.parent_str = parent_str
        self.accepted = accepted
        self.entropy = entropy
        self.population_frac = population_frac


# ── Seed initialization ─────────────────────────────────────────────

def _seed_grid(grid, density):
    """Fill grid with random cells at given density."""
    for r in range(grid.rows):
        for c in range(grid.cols):
            if random.random() < density:
                grid.cells[r][c] = 1
            else:
                grid.cells[r][c] = 0
    grid.population = sum(
        1 for r in range(grid.rows) for c in range(grid.cols) if grid.cells[r][c] > 0
    )


# ── Mode functions ───────────────────────────────────────────────────

def _enter_rmut_mode(self):
    """Show preset selection menu."""
    self.rmut_menu = True
    self.rmut_menu_sel = 0
    self._flash("Rule Mutation Engine — select a preset")


def _exit_rmut_mode(self):
    """Clean up and exit mode."""
    self.rmut_mode = False
    self.rmut_menu = False
    self.rmut_running = False
    self._flash("Rule Mutation Engine OFF")


def _rmut_init(self, preset_idx):
    """Initialize the mutation engine from a preset."""
    name, desc, rule_str, mutation_rate, density = RMUT_PRESETS[preset_idx]

    max_y, max_x = self.stdscr.getmaxyx()
    self.rmut_rows = max(10, max_y - 3)
    self.rmut_cols = max(10, (max_x - 36) // 2)

    # Create simulation grid
    self.rmut_grid = Grid(self.rmut_rows, self.rmut_cols)

    # Set initial rule
    if rule_str is None:
        birth, survival = _random_rule()
    else:
        parsed = parse_rule_string(rule_str)
        if parsed:
            birth, survival = parsed
        else:
            birth, survival = {3}, {2, 3}

    self.rmut_grid.birth = set(birth)
    self.rmut_grid.survival = set(survival)

    # Seed the grid
    _seed_grid(self.rmut_grid, density)

    # State
    self.rmut_preset_name = name
    self.rmut_mutation_rate = mutation_rate
    self.rmut_density = density
    self.rmut_generation = 0
    self.rmut_mutation_gen = 0  # which mutation cycle we're on
    self.rmut_running = False
    self.rmut_speed_mult = 1
    self.rmut_paused_evolving = False  # pause evolution but keep sim running

    # Current rule tracking
    self.rmut_current_birth = set(birth)
    self.rmut_current_survival = set(survival)

    # Candidate rule (being evaluated)
    self.rmut_candidate_birth = None
    self.rmut_candidate_survival = None
    self.rmut_eval_step = 0
    self.rmut_eval_phase = "stable"  # "stable" or "evaluating"

    # Saved grid state for reverting failed mutations
    self.rmut_saved_cells = None
    self.rmut_saved_gen = 0

    # Fitness tracking
    self.rmut_current_fitness = 0.0
    self.rmut_best_fitness = 0.0
    self.rmut_best_rule = rule_string(birth, survival)

    # Analytics per-step
    self.rmut_periodicity = PeriodicityDetector(max_history=200)
    self.rmut_entropy_history = []
    self.rmut_pop_history = []
    self.rmut_fitness_history = []

    # Lineage
    self.rmut_lineage = [
        LineageNode(rule_string(birth, survival), 0.0, 0, "—", True)
    ]
    self.rmut_lineage_scroll = 0

    # Stats
    self.rmut_total_mutations = 0
    self.rmut_accepted_mutations = 0
    self.rmut_reverted_mutations = 0
    self.rmut_best_entropy = 0.0

    self.rmut_menu = False
    self.rmut_mode = True


def _rmut_step(self):
    """Advance the simulation and mutation engine by one step."""
    grid = self.rmut_grid

    # Step the simulation
    grid.step()
    self.rmut_generation += 1

    # Track metrics
    self.rmut_pop_history.append(grid.population)
    if len(self.rmut_pop_history) > 200:
        self.rmut_pop_history.pop(0)

    # Compute entropy periodically
    if self.rmut_generation % 2 == 0:
        ent = shannon_entropy(grid)
        self.rmut_entropy_history.append(ent)
        if len(self.rmut_entropy_history) > 200:
            self.rmut_entropy_history.pop(0)
        if ent > self.rmut_best_entropy:
            self.rmut_best_entropy = ent

    # Periodicity check
    self.rmut_periodicity.update(grid)

    # Skip evolution if paused
    if self.rmut_paused_evolving:
        return

    total_cells = grid.rows * grid.cols
    pop_frac = grid.population / total_cells if total_cells > 0 else 0

    if self.rmut_eval_phase == "stable":
        # Check if it's time to try a mutation
        # Mutate every _EVAL_WINDOW steps
        if self.rmut_generation > 0 and self.rmut_generation % _EVAL_WINDOW == 0:
            # Compute current fitness
            self.rmut_current_fitness = _compute_fitness(
                grid, self.rmut_pop_history, self.rmut_entropy_history,
                self.rmut_periodicity,
            )
            self.rmut_fitness_history.append(self.rmut_current_fitness)
            if len(self.rmut_fitness_history) > 100:
                self.rmut_fitness_history.pop(0)

            if self.rmut_current_fitness > self.rmut_best_fitness:
                self.rmut_best_fitness = self.rmut_current_fitness
                self.rmut_best_rule = rule_string(
                    self.rmut_current_birth, self.rmut_current_survival
                )

            # Save state for potential revert
            self.rmut_saved_cells = [row[:] for row in grid.cells]
            self.rmut_saved_gen = self.rmut_generation

            # Generate candidate mutation
            self.rmut_candidate_birth, self.rmut_candidate_survival = _mutate_rule(
                self.rmut_current_birth, self.rmut_current_survival,
                self.rmut_mutation_rate,
            )

            # Apply candidate rule
            grid.birth = set(self.rmut_candidate_birth)
            grid.survival = set(self.rmut_candidate_survival)
            self.rmut_eval_step = 0
            self.rmut_eval_phase = "evaluating"
            self.rmut_periodicity.reset()
            self.rmut_total_mutations += 1
            self.rmut_mutation_gen += 1

    elif self.rmut_eval_phase == "evaluating":
        self.rmut_eval_step += 1

        if self.rmut_eval_step >= _EVAL_WINDOW:
            # Evaluate the candidate
            candidate_fitness = _compute_fitness(
                grid, self.rmut_pop_history, self.rmut_entropy_history,
                self.rmut_periodicity,
            )

            # Check for immediate failures
            extinct = grid.population == 0
            blob = pop_frac > _MAX_POP_FRAC
            static = (self.rmut_periodicity.period is not None
                      and self.rmut_periodicity.period <= 1)

            # Accept or revert
            accepted = False
            if extinct or blob:
                # Hard reject
                accepted = False
            elif static and candidate_fitness <= self.rmut_current_fitness:
                accepted = False
            elif candidate_fitness >= self.rmut_current_fitness + _ENTROPY_ACCEPT_DELTA:
                # Accept: fitness didn't drop significantly (or improved)
                accepted = True
                # Simulated annealing: occasionally accept worse mutations
            elif random.random() < 0.05:
                accepted = True  # occasional random acceptance for exploration

            current_entropy = (self.rmut_entropy_history[-1]
                               if self.rmut_entropy_history else 0.0)

            if accepted:
                # Keep the mutation
                self.rmut_current_birth = set(self.rmut_candidate_birth)
                self.rmut_current_survival = set(self.rmut_candidate_survival)
                self.rmut_current_fitness = candidate_fitness
                self.rmut_accepted_mutations += 1

                # Feed accepted mutation to phase transition detector
                _rmut_feed_phase_detector(self, grid, current_entropy, pop_frac)

                self.rmut_lineage.append(LineageNode(
                    rule_string(self.rmut_current_birth, self.rmut_current_survival),
                    candidate_fitness,
                    self.rmut_generation,
                    rule_string(set(self.rmut_saved_cells is not None and
                                    self.rmut_current_birth or set()),
                                set()),
                    True,
                    current_entropy,
                    pop_frac,
                ))
                # Fix parent tracking
                if len(self.rmut_lineage) >= 2:
                    self.rmut_lineage[-1].parent_str = self.rmut_lineage[-2].rule_str
            else:
                # Revert
                self.rmut_reverted_mutations += 1
                grid.birth = set(self.rmut_current_birth)
                grid.survival = set(self.rmut_current_survival)

                # Revert grid if we have saved state and extinction happened
                if extinct and self.rmut_saved_cells is not None:
                    grid.cells = [row[:] for row in self.rmut_saved_cells]
                    grid.population = sum(
                        1 for r in range(grid.rows)
                        for c in range(grid.cols)
                        if grid.cells[r][c] > 0
                    )
                    # Re-seed if still empty
                    if grid.population == 0:
                        _seed_grid(grid, self.rmut_density)

                self.rmut_lineage.append(LineageNode(
                    rule_string(self.rmut_candidate_birth, self.rmut_candidate_survival),
                    candidate_fitness,
                    self.rmut_generation,
                    self.rmut_lineage[-1].rule_str if self.rmut_lineage else "—",
                    False,
                    current_entropy,
                    pop_frac,
                ))

            # Trim lineage
            if len(self.rmut_lineage) > 200:
                self.rmut_lineage = self.rmut_lineage[-150:]

            self.rmut_candidate_birth = None
            self.rmut_candidate_survival = None
            self.rmut_eval_phase = "stable"
            self.rmut_periodicity.reset()


# ── Key handlers ─────────────────────────────────────────────────────

def _handle_rmut_menu_key(self, key):
    """Handle key input on the preset menu."""
    n = len(RMUT_PRESETS)
    if key == ord("q") or key == 27:
        self.rmut_menu = False
        self._flash("Rule Mutation cancelled")
        return True
    if key == ord("j") or key == curses.KEY_DOWN:
        self.rmut_menu_sel = (self.rmut_menu_sel + 1) % n
        return True
    if key == ord("k") or key == curses.KEY_UP:
        self.rmut_menu_sel = (self.rmut_menu_sel - 1) % n
        return True
    if key in (ord("\n"), ord(" "), curses.KEY_ENTER, 10, 13):
        _rmut_init(self, self.rmut_menu_sel)
        return True
    return True


def _handle_rmut_key(self, key):
    """Handle key input in active simulation."""
    if key == ord("q") or key == 27:
        _exit_rmut_mode(self)
        return True
    if key == ord(" "):
        self.rmut_running = not self.rmut_running
        self._flash("Running" if self.rmut_running else "Paused")
        return True
    if key == ord("n"):
        _rmut_step(self)
        return True
    if key == ord("e"):
        # Toggle evolution pause (sim keeps running, mutations stop)
        self.rmut_paused_evolving = not self.rmut_paused_evolving
        self._flash("Evolution " + ("PAUSED" if self.rmut_paused_evolving else "ACTIVE"))
        return True
    if key == ord("r"):
        # Re-seed grid with current rule
        _seed_grid(self.rmut_grid, self.rmut_density)
        self.rmut_periodicity.reset()
        self._flash("Grid re-seeded")
        return True
    if key == ord("R"):
        # Full reset with random rule
        birth, survival = _random_rule()
        self.rmut_current_birth = birth
        self.rmut_current_survival = survival
        self.rmut_grid.birth = set(birth)
        self.rmut_grid.survival = set(survival)
        _seed_grid(self.rmut_grid, self.rmut_density)
        self.rmut_periodicity.reset()
        self.rmut_lineage.append(
            LineageNode(rule_string(birth, survival), 0.0,
                        self.rmut_generation, "random", True)
        )
        self._flash(f"Reset to random: {rule_string(birth, survival)}")
        return True
    if key == ord("+") or key == ord("="):
        self.rmut_mutation_rate = min(0.5, self.rmut_mutation_rate + 0.02)
        self._flash(f"Mutation rate: {self.rmut_mutation_rate:.2f}")
        return True
    if key == ord("-") or key == ord("_"):
        self.rmut_mutation_rate = max(0.01, self.rmut_mutation_rate - 0.02)
        self._flash(f"Mutation rate: {self.rmut_mutation_rate:.2f}")
        return True
    if key == ord("]"):
        self.rmut_speed_mult = min(20, self.rmut_speed_mult + 1)
        self._flash(f"Steps/frame: {self.rmut_speed_mult}")
        return True
    if key == ord("["):
        self.rmut_speed_mult = max(1, self.rmut_speed_mult - 1)
        self._flash(f"Steps/frame: {self.rmut_speed_mult}")
        return True
    if key == ord("a"):
        # Adopt current rule into main Game of Life
        self.grid.birth = set(self.rmut_current_birth)
        self.grid.survival = set(self.rmut_current_survival)
        self._flash(f"Adopted {rule_string(self.rmut_current_birth, self.rmut_current_survival)} into main grid")
        return True
    return True


# ── Drawing ──────────────────────────────────────────────────────────

def _sparkline(data, width):
    """Render a sparkline string."""
    if not data or width <= 0:
        return ""
    vals = list(data[-width:])
    lo, hi = min(vals), max(vals)
    span = hi - lo if hi != lo else 1
    out = []
    for v in vals:
        idx = int((v - lo) / span * (len(_SPARKLINE_CHARS) - 1))
        idx = max(0, min(idx, len(_SPARKLINE_CHARS) - 1))
        out.append(_SPARKLINE_CHARS[idx])
    return "".join(out)


def _draw_rmut_menu(self, max_y, max_x):
    """Render the preset selection menu."""
    self.stdscr.erase()
    y = 1
    try:
        title = "═══ Rule Mutation Engine ═══"
        self.stdscr.addstr(y, max(0, (max_x - len(title)) // 2), title,
                           curses.A_BOLD)
        y += 2
        subtitle = "Autonomous rule evolution toward maximum visual complexity"
        self.stdscr.addstr(y, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.A_DIM)
        y += 2

        for i, (name, desc, rule_s, mrate, dens) in enumerate(RMUT_PRESETS):
            if y >= max_y - 3:
                break
            prefix = "▸ " if i == self.rmut_menu_sel else "  "
            attr = curses.A_BOLD | curses.A_REVERSE if i == self.rmut_menu_sel else 0
            line = f"{prefix}{name}"
            self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
            y += 1
            if i == self.rmut_menu_sel and y < max_y - 3:
                detail = f"  {desc}"
                self.stdscr.addstr(y, 2, detail[:max_x - 4], curses.A_DIM)
                y += 1
                rule_label = rule_s if rule_s else "Random"
                params = f"  Rule: {rule_label}  Mutation: {mrate:.2f}  Density: {dens:.0%}"
                self.stdscr.addstr(y, 2, params[:max_x - 4], curses.A_DIM)
                y += 1

        y = max_y - 2
        if y > 0:
            help_text = "↑/↓ or j/k: navigate  Enter: select  q: cancel"
            self.stdscr.addstr(y, 2, help_text[:max_x - 4], curses.A_DIM)
    except curses.error:
        pass


def _draw_rmut(self, max_y, max_x):
    """Render the active simulation with lineage sidebar."""
    self.stdscr.erase()
    grid = self.rmut_grid

    # Layout: grid on left, panel on right
    panel_w = 34
    grid_area_w = max_x - panel_w if max_x > 70 else max_x
    grid_display_cols = min(grid.cols, grid_area_w // 2)
    grid_display_rows = min(grid.rows, max_y - 2)

    # ── Draw simulation grid ──
    for r in range(grid_display_rows):
        for c in range(grid_display_cols):
            sx = c * 2
            sy = r
            if sy >= max_y - 1 or sx + 1 >= grid_area_w:
                continue
            try:
                v = grid.cells[r][c]
                if v > 0:
                    # Age-based color using built-in pairs
                    age = v
                    if age <= 2:
                        pair = 1  # green
                    elif age <= 5:
                        pair = 4  # cyan
                    elif age <= 15:
                        pair = 6  # yellow
                    elif age <= 30:
                        pair = 7  # magenta
                    else:
                        pair = 3  # red
                    attr = curses.color_pair(pair)
                    if self.rmut_eval_phase == "evaluating":
                        attr |= curses.A_BOLD
                    self.stdscr.addstr(sy, sx, "██", attr)
            except curses.error:
                pass

    # ── Draw info panel ──
    if max_x <= 70:
        # No room for panel, just draw status bar
        _draw_rmut_status(self, max_y, max_x)
        return

    px = max_x - panel_w + 1
    py = 0

    try:
        # Title
        self.stdscr.addstr(py, px, "Rule Mutation Engine", curses.A_BOLD)
        py += 1
        self.stdscr.addstr(py, px, f"Preset: {self.rmut_preset_name}"[:panel_w - 2],
                           curses.A_DIM)
        py += 2

        # Current rule
        current_rule = rule_string(self.rmut_current_birth, self.rmut_current_survival)
        self.stdscr.addstr(py, px, f"Rule: {current_rule}", curses.A_BOLD)
        py += 1

        # Phase indicator
        if self.rmut_eval_phase == "evaluating":
            cand_rule = rule_string(self.rmut_candidate_birth, self.rmut_candidate_survival)
            phase_str = f"Testing: {cand_rule}"
            self.stdscr.addstr(py, px, phase_str[:panel_w - 2],
                               curses.A_BOLD)
            progress = self.rmut_eval_step / _EVAL_WINDOW
            bar_w = panel_w - 4
            filled = int(progress * bar_w)
            bar = "█" * filled + "░" * (bar_w - filled)
            py += 1
            self.stdscr.addstr(py, px, f"[{bar}]"[:panel_w - 2])
        elif self.rmut_paused_evolving:
            self.stdscr.addstr(py, px, "Evolution: PAUSED", curses.A_DIM)
        else:
            self.stdscr.addstr(py, px, "Evolution: ACTIVE",
                               curses.color_pair(1) if curses.has_colors() else 0)
        py += 2

        # Stats
        self.stdscr.addstr(py, px, f"Gen: {self.rmut_generation}")
        py += 1
        self.stdscr.addstr(py, px, f"Population: {grid.population}")
        py += 1
        total_cells = grid.rows * grid.cols
        pop_pct = grid.population / total_cells * 100 if total_cells > 0 else 0
        self.stdscr.addstr(py, px, f"Density: {pop_pct:.1f}%")
        py += 1
        ent = self.rmut_entropy_history[-1] if self.rmut_entropy_history else 0
        self.stdscr.addstr(py, px, f"Entropy: {ent:.3f}")
        py += 1
        self.stdscr.addstr(py, px, f"Fitness: {self.rmut_current_fitness:.1f}")
        py += 1
        self.stdscr.addstr(py, px, f"Mutation rate: {self.rmut_mutation_rate:.2f}")
        py += 1
        self.stdscr.addstr(py, px, f"Mutations: {self.rmut_mutation_gen}")
        py += 1
        accept_rate = (self.rmut_accepted_mutations / self.rmut_total_mutations * 100
                       if self.rmut_total_mutations > 0 else 0)
        self.stdscr.addstr(py, px, f"Accept rate: {accept_rate:.0f}%")
        py += 2

        # Best rule ever
        self.stdscr.addstr(py, px, "── Best Rule ──", curses.A_BOLD)
        py += 1
        self.stdscr.addstr(py, px, f"{self.rmut_best_rule}")
        py += 1
        self.stdscr.addstr(py, px, f"Fitness: {self.rmut_best_fitness:.1f}")
        py += 2

        # Entropy sparkline
        if self.rmut_entropy_history:
            self.stdscr.addstr(py, px, "── Entropy ──", curses.A_BOLD)
            py += 1
            spark = _sparkline(self.rmut_entropy_history, panel_w - 3)
            self.stdscr.addstr(py, px, spark, curses.A_DIM)
            py += 1

        # Fitness sparkline
        if self.rmut_fitness_history:
            self.stdscr.addstr(py, px, "── Fitness ──", curses.A_BOLD)
            py += 1
            spark = _sparkline(self.rmut_fitness_history, panel_w - 3)
            self.stdscr.addstr(py, px, spark, curses.A_DIM)
            py += 2

        # Lineage sidebar
        lineage_space = max_y - py - 3
        if lineage_space > 3 and self.rmut_lineage:
            self.stdscr.addstr(py, px, "── Lineage ──", curses.A_BOLD)
            py += 1

            # Show most recent lineage entries
            visible = self.rmut_lineage[-(lineage_space):]
            for node in visible:
                if py >= max_y - 2:
                    break
                marker = "✓" if node.accepted else "✗"
                # Truncate rule string to fit
                rule_s = node.rule_str
                if len(rule_s) > panel_w - 12:
                    rule_s = rule_s[:panel_w - 15] + "…"
                line = f"{marker} {rule_s} {node.fitness:+.0f}"
                if node.accepted:
                    attr = curses.color_pair(1) if curses.has_colors() else 0
                else:
                    attr = curses.A_DIM
                self.stdscr.addstr(py, px, line[:panel_w - 2], attr)
                py += 1

    except curses.error:
        pass

    # Status bar
    _draw_rmut_status(self, max_y, max_x)


def _draw_rmut_status(self, max_y, max_x):
    """Draw status bar at bottom."""
    try:
        status_y = max_y - 1
        state = "▶ RUN" if self.rmut_running else "⏸ STOP"
        evo = "evo:ON" if not self.rmut_paused_evolving else "evo:OFF"
        bar = (f" {state} {evo} │ SPC:play e:evo r:seed R:reset "
               f"+/-:mutrate [/]:speed a:adopt q:quit ")
        self.stdscr.addstr(status_y, 0, bar[:max_x - 1], curses.A_REVERSE)
    except curses.error:
        pass


# ── Phase transition integration ──────────────────────────────────────

def _rmut_feed_phase_detector(self, grid, entropy, pop_frac):
    """Feed rule mutation state to the app's phase transition detector."""
    det = self.analytics.phase_detector
    if not det.enabled:
        return
    # Classify the rule mutation's current state for the detector
    from life.analytics import classify_stability
    stability = classify_stability(self.rmut_pop_history, self.rmut_periodicity.period)
    sym = symmetry_score(grid)
    det.update(grid, entropy, self.rmut_pop_history, sym, stability,
               self.rmut_periodicity.period)
    # Let the app process any new transitions
    self._process_phase_transitions()


# ── Registration ─────────────────────────────────────────────────────

def register(App):
    """Register Rule Mutation Engine mode methods on the App class."""
    App._enter_rmut_mode = _enter_rmut_mode
    App._exit_rmut_mode = _exit_rmut_mode
    App._rmut_init = _rmut_init
    App._rmut_step = _rmut_step
    App._handle_rmut_menu_key = _handle_rmut_menu_key
    App._handle_rmut_key = _handle_rmut_key
    App._draw_rmut_menu = _draw_rmut_menu
    App._draw_rmut = _draw_rmut
