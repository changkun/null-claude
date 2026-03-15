"""Mode: evo_playground — Evolutionary Playground.

Interactive natural selection of cellular automata rules.  A grid of
live-running simulations with randomly generated rules competes
side-by-side.  The user selects the most visually interesting ones as
"parents", breeds them (crossover + mutation of birth/survival rules,
neighborhood shapes, and state counts), and repeats — iteratively
discovering emergent behaviors no one designed by hand.
"""
import curses
import json
import math
import os
import random
import time

from life.constants import SAVE_DIR, SPEEDS, SPEED_LABELS
from life.grid import Grid
from life.rules import rule_string, parse_rule_string

# ── Constants ────────────────────────────────────────────────────────

_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]

_COLOR_TIERS = [
    (1, curses.A_DIM), (1, 0), (4, curses.A_DIM), (4, 0),
    (6, curses.A_DIM), (6, 0), (7, 0), (7, curses.A_BOLD),
]

_NEIGHBORHOODS = ["moore", "von_neumann", "hex"]
_NEIGHBORHOOD_LABELS = {"moore": "Moore (8)", "von_neumann": "VN (4)", "hex": "Hex (6)"}

_SAVED_RULES_FILE = os.path.join(SAVE_DIR, "evolved_rules.json")

# ── Genome representation ────────────────────────────────────────────

def _random_genome():
    """Generate a random CA genome: birth set, survival set, neighborhood, num_states."""
    birth = {d for d in range(9) if random.random() < 0.3}
    survival = {d for d in range(9) if random.random() < 0.3}
    if not birth:
        birth.add(random.randint(1, 5))
    if not survival:
        survival.add(random.randint(2, 4))
    neighborhood = random.choice(["moore", "moore", "moore", "von_neumann", "hex"])
    num_states = random.choice([2, 2, 2, 3, 4])  # bias toward binary
    return {
        "birth": birth,
        "survival": survival,
        "neighborhood": neighborhood,
        "num_states": num_states,
    }


def _crossover(g1, g2):
    """Uniform crossover between two genomes."""
    child_birth = set()
    child_survival = set()
    for d in range(9):
        src_b = g1 if random.random() < 0.5 else g2
        if d in src_b["birth"]:
            child_birth.add(d)
        src_s = g1 if random.random() < 0.5 else g2
        if d in src_s["survival"]:
            child_survival.add(d)
    if not child_birth:
        child_birth.add(random.randint(1, 5))
    neighborhood = g1["neighborhood"] if random.random() < 0.5 else g2["neighborhood"]
    num_states = g1["num_states"] if random.random() < 0.5 else g2["num_states"]
    return {
        "birth": child_birth,
        "survival": child_survival,
        "neighborhood": neighborhood,
        "num_states": num_states,
    }


def _mutate(genome, rate=0.15):
    """Mutate a genome in place and return it."""
    g = {
        "birth": set(genome["birth"]),
        "survival": set(genome["survival"]),
        "neighborhood": genome["neighborhood"],
        "num_states": genome["num_states"],
    }
    for d in range(9):
        if random.random() < rate:
            g["birth"].symmetric_difference_update({d})
        if random.random() < rate:
            g["survival"].symmetric_difference_update({d})
    if not g["birth"]:
        g["birth"].add(random.randint(1, 5))
    if random.random() < rate * 0.5:
        g["neighborhood"] = random.choice(_NEIGHBORHOODS)
    if random.random() < rate * 0.5:
        g["num_states"] = random.choice([2, 3, 4, 5])
    return g


def _genome_label(genome):
    """Short human-readable label for a genome."""
    rs = rule_string(genome["birth"], genome["survival"])
    nh = genome["neighborhood"][0].upper()  # M/V/H
    ns = genome["num_states"]
    if ns == 2 and nh == "M":
        return rs
    return f"{rs} {nh}{ns}"


# ── Mini-simulation ──────────────────────────────────────────────────

_HEX_EVEN = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
_HEX_ODD = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]


def _create_mini_sim(genome, rows, cols):
    """Create a mini Grid for a genome."""
    g = Grid(rows, cols)
    g.birth = set(genome["birth"])
    g.survival = set(genome["survival"])
    # Don't set hex_mode on Grid (its hex path has import issues);
    # we handle all neighborhoods in our custom step function.
    g._ep_neighborhood = genome["neighborhood"]
    g._ep_num_states = genome["num_states"]
    # Random 20% fill
    for r in range(rows):
        for c in range(cols):
            if random.random() < 0.2:
                g.set_alive(r, c)
    return g


def _count_neighbors(grid, r, c, neighborhood):
    """Count live neighbors for a cell given a neighborhood type."""
    rows, cols = grid.rows, grid.cols
    count = 0
    if neighborhood == "von_neumann":
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if grid.cells[(r + dr) % rows][(c + dc) % cols] > 0:
                count += 1
    elif neighborhood == "hex":
        offsets = _HEX_EVEN if r % 2 == 0 else _HEX_ODD
        for dr, dc in offsets:
            if grid.cells[(r + dr) % rows][(c + dc) % cols] > 0:
                count += 1
    else:  # moore
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                if grid.cells[(r + dr) % rows][(c + dc) % cols] > 0:
                    count += 1
    return count


def _step_mini_sim(grid):
    """Step a mini simulation, handling all neighborhood types and multi-state."""
    rows, cols = grid.rows, grid.cols
    neighborhood = getattr(grid, '_ep_neighborhood', 'moore')
    num_states = getattr(grid, '_ep_num_states', 2)

    new = [[0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            n = _count_neighbors(grid, r, c, neighborhood)
            alive = grid.cells[r][c] > 0
            if alive and n in grid.survival:
                new[r][c] = min(grid.cells[r][c] + 1, num_states * 50)
            elif not alive and n in grid.birth:
                new[r][c] = 1
            else:
                if num_states > 2 and grid.cells[r][c] > 1:
                    new[r][c] = grid.cells[r][c] - 1  # decay
                else:
                    new[r][c] = 0
    grid.cells = new
    grid.generation += 1
    grid.population = sum(1 for row in new for cell in row if cell > 0)


# ── Mode functions ───────────────────────────────────────────────────

def _enter_evo_playground(self):
    """Enter the Evolutionary Playground mode."""
    self.ep_mode = False
    self.ep_menu = True
    self.ep_menu_sel = 0
    self._flash("Evolutionary Playground — breed new CA rules through selection")


def _exit_evo_playground(self):
    """Exit the Evolutionary Playground."""
    self.ep_mode = False
    self.ep_menu = False
    self.ep_running = False
    self.ep_sims = []
    self.ep_genomes = []
    self.ep_selected = set()
    self.ep_generation = 0
    self._flash("Evolutionary Playground OFF")


def _ep_init(self, seed_genomes=None):
    """Initialize the playground grid with a population of simulations."""
    max_y, max_x = self.stdscr.getmaxyx()

    # Determine grid layout
    usable_h = max_y - 5  # title + status + hint
    usable_w = max_x - 1

    tile_inner_h = max(3, min(8, (usable_h - 2) // 4 - 1))
    tile_inner_w = max(4, min(12, (usable_w - 2) // 4 - 1))

    self.ep_grid_rows = max(2, min(4, (usable_h - 1) // (tile_inner_h + 1)))
    self.ep_grid_cols = max(2, min(5, (usable_w - 1) // (tile_inner_w * 2 + 1)))

    self.ep_tile_h = max(3, (usable_h - 1) // self.ep_grid_rows - 1)
    self.ep_tile_w = max(3, (usable_w - 1) // (self.ep_grid_cols * 2) - 1)

    pop_size = self.ep_grid_rows * self.ep_grid_cols
    sim_rows = self.ep_tile_h
    sim_cols = self.ep_tile_w

    # Generate genomes
    if seed_genomes and len(seed_genomes) >= 2:
        # Breed from selected parents
        genomes = []
        # Keep parents
        for sg in seed_genomes:
            genomes.append(dict(sg, birth=set(sg["birth"]), survival=set(sg["survival"])))
        # Fill rest with crossover + mutation
        while len(genomes) < pop_size:
            p1 = random.choice(seed_genomes)
            p2 = random.choice(seed_genomes)
            child = _crossover(p1, p2)
            child = _mutate(child, self.ep_mutation_rate)
            genomes.append(child)
        # Truncate if too many parents
        genomes = genomes[:pop_size]
    else:
        genomes = [_random_genome() for _ in range(pop_size)]

    # Create simulations
    self.ep_sims = []
    self.ep_genomes = genomes
    self.ep_pop_histories = []
    for genome in genomes:
        grid = _create_mini_sim(genome, sim_rows, sim_cols)
        self.ep_sims.append(grid)
        self.ep_pop_histories.append([grid.population])

    self.ep_selected = set()
    self.ep_cursor = 0  # flat index into grid
    self.ep_sim_generation = 0
    self.ep_mode = True
    self.ep_menu = False
    self.ep_running = False
    self.ep_generation += 1

    n_parents = len(seed_genomes) if seed_genomes else 0
    if n_parents > 0:
        self._flash(f"Gen {self.ep_generation}: bred {pop_size} from {n_parents} parents — Space to run, Enter to select")
    else:
        self._flash(f"Gen {self.ep_generation}: {pop_size} random rules — Space to run, arrows to navigate, Enter to select parents")


def _ep_step(self):
    """Advance all mini simulations by one step."""
    for i, grid in enumerate(self.ep_sims):
        _step_mini_sim(grid)
        self.ep_pop_histories[i].append(grid.population)
    self.ep_sim_generation += 1


def _ep_breed(self):
    """Breed selected parents into next generation."""
    if len(self.ep_selected) < 2:
        self._flash("Select at least 2 parents (Enter to toggle selection)")
        return
    parents = [self.ep_genomes[i] for i in sorted(self.ep_selected)]
    self.ep_sim_generation = 0
    self.ep_pop_histories = []
    self._ep_init(seed_genomes=parents)
    self.ep_running = True


def _ep_save_rule(self, idx):
    """Save a genome to the evolved rules file."""
    genome = self.ep_genomes[idx]
    entry = {
        "rule": rule_string(genome["birth"], genome["survival"]),
        "birth": sorted(genome["birth"]),
        "survival": sorted(genome["survival"]),
        "neighborhood": genome["neighborhood"],
        "num_states": genome["num_states"],
        "label": _genome_label(genome),
        "generation": self.ep_generation,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    # Load existing
    saved = []
    if os.path.isfile(_SAVED_RULES_FILE):
        try:
            with open(_SAVED_RULES_FILE, "r") as f:
                saved = json.load(f)
        except (json.JSONDecodeError, OSError):
            saved = []
    saved.append(entry)
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(_SAVED_RULES_FILE, "w") as f:
        json.dump(saved, f, indent=2)
    self._flash(f"Saved: {entry['label']} to evolved_rules.json")


def _ep_adopt_rule(self, idx):
    """Adopt a genome's ruleset into the main Game of Life grid."""
    genome = self.ep_genomes[idx]
    self.grid.birth = set(genome["birth"])
    self.grid.survival = set(genome["survival"])
    rs = _genome_label(genome)
    self._exit_evo_playground()
    self._flash(f"Adopted evolved rule: {rs}")


def _ep_load_saved(self):
    """Load saved rules as seed genomes."""
    if not os.path.isfile(_SAVED_RULES_FILE):
        self._flash("No saved rules found")
        return None
    try:
        with open(_SAVED_RULES_FILE, "r") as f:
            saved = json.load(f)
    except (json.JSONDecodeError, OSError):
        self._flash("Error reading saved rules")
        return None
    if not saved:
        self._flash("No saved rules found")
        return None
    genomes = []
    for entry in saved[-12:]:  # last 12
        genomes.append({
            "birth": set(entry["birth"]),
            "survival": set(entry["survival"]),
            "neighborhood": entry.get("neighborhood", "moore"),
            "num_states": entry.get("num_states", 2),
        })
    return genomes


# ── Key handlers ─────────────────────────────────────────────────────

def _handle_ep_menu_key(self, key):
    """Handle keys in the playground settings menu."""
    if key == -1:
        return True
    menu_items = ["mutation_rate", "load_saved", "start_random", "start_saved"]
    n = len(menu_items)

    if key in (curses.KEY_UP, ord("k")):
        self.ep_menu_sel = (self.ep_menu_sel - 1) % n
        return True
    if key in (curses.KEY_DOWN, ord("j")):
        self.ep_menu_sel = (self.ep_menu_sel + 1) % n
        return True
    if key == 27 or key == ord("q"):
        self.ep_menu = False
        self._flash("Evolutionary Playground cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER, ord(" ")):
        item = menu_items[self.ep_menu_sel]
        if item == "mutation_rate":
            val = self._prompt_text(f"Mutation rate 0-100% (current: {int(self.ep_mutation_rate * 100)}%)")
            if val:
                try:
                    n_val = int(val.replace("%", ""))
                    if 0 <= n_val <= 100:
                        self.ep_mutation_rate = n_val / 100.0
                        self._flash(f"Mutation rate: {n_val}%")
                except ValueError:
                    self._flash("Invalid number")
        elif item == "start_random":
            self.ep_generation = 0
            self._ep_init()
        elif item == "start_saved":
            genomes = self._ep_load_saved()
            if genomes:
                self.ep_generation = 0
                self._ep_init(seed_genomes=genomes)
            else:
                self._flash("No saved rules — starting random")
                self.ep_generation = 0
                self._ep_init()
        elif item == "load_saved":
            genomes = self._ep_load_saved()
            if genomes:
                self._flash(f"Loaded {len(genomes)} saved rules")
        return True
    return True


def _handle_ep_key(self, key):
    """Handle keys during active playground mode."""
    if key == -1:
        return True
    if key == 27 or key == ord("q"):
        self._exit_evo_playground()
        return True

    pop_size = len(self.ep_sims)
    gc = self.ep_grid_cols

    # Play/pause
    if key == ord(" "):
        self.ep_running = not self.ep_running
        self._flash("Running" if self.ep_running else "Paused")
        return True

    # Single step
    if key == ord("."):
        self.ep_running = False
        self._ep_step()
        return True

    # Navigate cursor
    if key == curses.KEY_UP or key == ord("w"):
        self.ep_cursor = max(0, self.ep_cursor - gc)
        return True
    if key == curses.KEY_DOWN or key == ord("s"):
        self.ep_cursor = min(pop_size - 1, self.ep_cursor + gc)
        return True
    if key == curses.KEY_LEFT or key == ord("a"):
        self.ep_cursor = max(0, self.ep_cursor - 1)
        return True
    if key == curses.KEY_RIGHT or key == ord("d"):
        self.ep_cursor = min(pop_size - 1, self.ep_cursor + 1)
        return True

    # Toggle selection (mark as parent)
    if key in (10, 13, curses.KEY_ENTER):
        if self.ep_cursor in self.ep_selected:
            self.ep_selected.discard(self.ep_cursor)
            self._flash(f"Deselected #{self.ep_cursor + 1} — {len(self.ep_selected)} parents chosen")
        else:
            self.ep_selected.add(self.ep_cursor)
            self._flash(f"Selected #{self.ep_cursor + 1} as parent — {len(self.ep_selected)} parents chosen")
        return True

    # Breed next generation
    if key == ord("b"):
        self._ep_breed()
        return True

    # Select all / deselect all
    if key == ord("A"):
        if len(self.ep_selected) == pop_size:
            self.ep_selected.clear()
            self._flash("Deselected all")
        else:
            self.ep_selected = set(range(pop_size))
            self._flash(f"Selected all {pop_size}")
        return True

    # Save selected rule
    if key == ord("S"):
        self._ep_save_rule(self.ep_cursor)
        return True

    # Adopt rule into main grid
    if key == ord("a"):
        self._ep_adopt_rule(self.ep_cursor)
        return True

    # Randomize (new random generation)
    if key == ord("r"):
        self.ep_generation = 0
        self._ep_init()
        self._flash("New random population")
        return True

    # Speed controls
    if key == ord(">"):
        if self.speed_idx < len(SPEEDS) - 1:
            self.speed_idx += 1
        self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True
    if key == ord("<"):
        if self.speed_idx > 0:
            self.speed_idx -= 1
        self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True

    # Mouse click
    if key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            tile_idx = _screen_to_tile_idx(self, mx, my)
            if tile_idx is not None and 0 <= tile_idx < pop_size:
                self.ep_cursor = tile_idx
                if bstate & curses.BUTTON1_DOUBLE_CLICKED:
                    # Toggle selection on double click
                    if tile_idx in self.ep_selected:
                        self.ep_selected.discard(tile_idx)
                    else:
                        self.ep_selected.add(tile_idx)
        except curses.error:
            pass
        return True

    return True


def _screen_to_tile_idx(self, mx, my):
    """Convert screen coords to flat tile index."""
    draw_y_start = 2
    th = self.ep_tile_h
    tw = self.ep_tile_w
    gc = self.ep_grid_cols
    gr = self.ep_grid_rows

    rel_y = my - draw_y_start
    rel_x = mx - 1  # small left margin

    if rel_y < 0 or rel_x < 0:
        return None

    tile_r = rel_y // (th + 1)
    tile_c = rel_x // (tw * 2 + 1)

    if 0 <= tile_r < gr and 0 <= tile_c < gc:
        idx = tile_r * gc + tile_c
        if idx < len(self.ep_sims):
            return idx
    return None


# ── Drawing ──────────────────────────────────────────────────────────

def _draw_ep_menu(self, max_y, max_x):
    """Draw the playground settings/launch menu."""
    self.stdscr.erase()

    title = "── Evolutionary Playground ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Breed novel cellular automata rules through interactive natural selection"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.color_pair(6))
    except curses.error:
        pass

    items = [
        ("Mutation Rate", f"{int(self.ep_mutation_rate * 100)}%",
         "Chance of mutating each rule digit during breeding"),
        ("Load Saved Rules", "",
         "View previously saved evolved rules"),
        (">>> START (Random) <<<", "",
         "Begin with a random population of rules"),
        (">>> START (From Saved) <<<", "",
         "Begin breeding from previously saved rules"),
    ]

    for i, (label, value, hint) in enumerate(items):
        y = 5 + i * 2
        if y >= max_y - 10:
            break
        if i >= 2:
            line = f"  {label}"
            attr = curses.color_pair(3) | curses.A_BOLD
            if i == self.ep_menu_sel:
                attr |= curses.A_REVERSE
        else:
            line = f"  {label:<25s} {value:<10s} {hint}"
            attr = curses.color_pair(6)
            if i == self.ep_menu_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
        line = line[:max_x - 2]
        try:
            self.stdscr.addstr(y, 2, line, attr)
        except curses.error:
            pass

    # How it works
    info_y = max(5 + len(items) * 2 + 1, max_y - 12)
    info_lines = [
        "HOW IT WORKS:",
        "  1. A grid of live simulations runs with random CA rules",
        "  2. Watch them evolve — look for interesting emergent patterns",
        "  3. Press Enter on tiles to select the best ones as parents",
        "  4. Press 'b' to breed: parents are crossed over + mutated",
        "  5. Repeat! Each generation discovers more interesting rules",
        "",
        "  Think of it as a genetic algorithm where YOU are the fitness function.",
        "  Save (S) or adopt (a) rules you discover.",
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
        hint = " [j/k]=navigate  [Enter]=select  [q/Esc]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_ep(self, max_y, max_x):
    """Draw the playground grid of live simulations."""
    self.stdscr.erase()

    gr = self.ep_grid_rows
    gc = self.ep_grid_cols
    th = self.ep_tile_h
    tw = self.ep_tile_w
    pop_size = len(self.ep_sims)

    # Title bar
    state_ch = "▶" if self.ep_running else "‖"
    n_sel = len(self.ep_selected)
    title = (f" {state_ch} Evolutionary Playground"
             f"  |  Gen {self.ep_generation}"
             f"  |  Step {self.ep_sim_generation}"
             f"  |  {n_sel} selected"
             f"  |  Mutation {int(self.ep_mutation_rate * 100)}%")
    title = title[:max_x - 1]
    try:
        self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    draw_y_start = 2
    draw_x_start = 1

    # Draw tiles
    for idx in range(pop_size):
        row = idx // gc
        col = idx % gc

        tile_y = draw_y_start + row * (th + 1)
        tile_x = draw_x_start + col * (tw * 2 + 1)

        if tile_y + th >= max_y - 2 or tile_x + tw * 2 >= max_x:
            continue

        grid = self.ep_sims[idx]
        genome = self.ep_genomes[idx]
        is_cursor = (idx == self.ep_cursor)
        is_selected = (idx in self.ep_selected)

        # Tile border
        if is_selected:
            border_attr = curses.color_pair(3) | curses.A_BOLD
        elif is_cursor:
            border_attr = curses.color_pair(7) | curses.A_BOLD
        else:
            border_attr = curses.color_pair(6) | curses.A_DIM

        # Top border with label
        label = _genome_label(genome)
        if is_selected:
            label = "★ " + label
        pop_str = f" P:{grid.population}"
        header = label[:tw * 2 - len(pop_str) - 1] + pop_str
        header = header[:tw * 2]
        try:
            self.stdscr.addstr(tile_y, tile_x, header, border_attr)
        except curses.error:
            pass

        # Draw horizontal border below label
        border_str = "─" * (tw * 2)
        try:
            self.stdscr.addstr(tile_y + 1, tile_x, border_str[:max_x - tile_x], border_attr)
        except curses.error:
            pass

        # Draw simulation content
        sim_rows = min(th - 2, grid.rows)
        sim_cols = min(tw, grid.cols)
        for sr in range(sim_rows):
            sy = tile_y + 2 + sr
            if sy >= max_y - 2:
                break
            for sc in range(sim_cols):
                sx = tile_x + sc * 2
                if sx + 1 >= max_x:
                    break
                age = grid.cells[sr][sc]
                if age > 0:
                    # Map age to density/color
                    v = min(1.0, age / 20.0)
                    di = max(1, min(4, int(v * 4.0) + 1))
                    ch = _DENSITY[di]
                    ci = min(7, int(v * 7.99))
                    pair_idx, extra = _COLOR_TIERS[ci]
                    attr = curses.color_pair(pair_idx) | extra
                    if not is_cursor and not is_selected:
                        attr |= curses.A_DIM
                    try:
                        self.stdscr.addstr(sy, sx, ch, attr)
                    except curses.error:
                        pass

        # Bottom border
        by = tile_y + th
        if by < max_y - 2:
            try:
                self.stdscr.addstr(by, tile_x, "─" * (tw * 2), border_attr)
            except curses.error:
                pass

        # Selection / cursor markers
        if is_cursor:
            try:
                self.stdscr.addstr(tile_y + 1, tile_x, "▸", curses.color_pair(7) | curses.A_BOLD)
                if by < max_y - 2:
                    self.stdscr.addstr(by, tile_x, "▸", curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        if is_selected:
            try:
                self.stdscr.addstr(tile_y + 1, tile_x, "★", curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass

    # Status bar: show cursor info
    status_y = max_y - 3
    if status_y > 0 and 0 <= self.ep_cursor < pop_size:
        genome = self.ep_genomes[self.ep_cursor]
        grid = self.ep_sims[self.ep_cursor]
        nh_label = _NEIGHBORHOOD_LABELS.get(genome["neighborhood"], genome["neighborhood"])
        ns = genome["num_states"]
        hist = self.ep_pop_histories[self.ep_cursor] if self.ep_cursor < len(self.ep_pop_histories) else []
        avg_pop = sum(hist) / len(hist) if hist else 0

        info = (f" Cursor: {_genome_label(genome)}"
                f"  |  {nh_label}"
                f"  |  States: {ns}"
                f"  |  Pop: {grid.population}"
                f"  |  Avg: {avg_pop:.0f}"
                f"  |  Speed: {SPEED_LABELS[self.speed_idx]}")
        info = info[:max_x - 1]
        try:
            self.stdscr.addstr(status_y, 0, info, curses.color_pair(6))
        except curses.error:
            pass

    # Selection summary
    sel_y = max_y - 2
    if sel_y > 0:
        if n_sel > 0:
            parent_labels = [_genome_label(self.ep_genomes[i]) for i in sorted(self.ep_selected)]
            sel_info = f" Parents ({n_sel}): " + ", ".join(parent_labels)
            sel_info = sel_info[:max_x - 1]
            try:
                self.stdscr.addstr(sel_y, 0, sel_info, curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass
        else:
            try:
                self.stdscr.addstr(sel_y, 0, " No parents selected — press Enter on interesting tiles",
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [↑↓←→]=navigate [Enter]=select parent [b]=breed [S]=save [a]=adopt [r]=randomize [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ── Registration ─────────────────────────────────────────────────────

def register(App):
    """Register Evolutionary Playground methods on the App class."""
    App._enter_evo_playground = _enter_evo_playground
    App._exit_evo_playground = _exit_evo_playground
    App._ep_init = _ep_init
    App._ep_step = _ep_step
    App._ep_breed = _ep_breed
    App._ep_save_rule = _ep_save_rule
    App._ep_adopt_rule = _ep_adopt_rule
    App._ep_load_saved = _ep_load_saved
    App._handle_ep_menu_key = _handle_ep_menu_key
    App._handle_ep_key = _handle_ep_key
    App._draw_ep_menu = _draw_ep_menu
    App._draw_ep = _draw_ep
