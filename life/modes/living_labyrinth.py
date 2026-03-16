"""Mode: Living Labyrinth — a playable roguelike where the dungeon IS a cellular automaton.

Navigate an ever-shifting maze as walls grow and decay by CA rules.  Reach the
exit portal before corridors seal shut.  Items scattered on the grid let you
freeze, reverse, or mutate the CA around you.

You are a *participant* inside the simulation — the first mode where you're not
just an observer but an agent interacting with the living automaton.

Keys:
  Arrow keys / WASD / hjkl — move player (@)
  Space                    — wait one turn (CA still ticks)
  f                        — use Freeze item (freezes CA around you for 10 turns)
  v                        — use Reverse item (rewinds CA 5 steps around you)
  m                        — use Mutate item (randomises CA rule locally)
  r                        — cycle CA rule preset
  n                        — new dungeon (regenerate)
  +/-                      — adjust CA tick rate (ticks per player move)
  ?                        — toggle help overlay
  q / Escape               — exit Living Labyrinth
"""

import curses
import math
import random
import time

from life.rules import parse_rule_string, rule_string


# ── Constants ──

WALL = 1        # alive cell = wall
FLOOR = 0       # dead cell = passable

PLAYER_CHAR = "@"
EXIT_CHAR = "◈"
ITEM_FREEZE_CHAR = "❄"
ITEM_REVERSE_CHAR = "⊛"
ITEM_MUTATE_CHAR = "✦"
WALL_CHAR = "██"
FLOOR_CHAR = "··"

# Item types
ITEM_FREEZE = "freeze"
ITEM_REVERSE = "reverse"
ITEM_MUTATE = "mutate"

ITEM_CHARS = {
    ITEM_FREEZE: ITEM_FREEZE_CHAR,
    ITEM_REVERSE: ITEM_REVERSE_CHAR,
    ITEM_MUTATE: ITEM_MUTATE_CHAR,
}

# Labyrinth rule presets — curated for interesting dungeon behavior
LABYRINTH_RULES = [
    {"name": "Maze (B3/S12345)", "birth": {3}, "survival": {1, 2, 3, 4, 5}},
    {"name": "Coral (B3/S45678)", "birth": {3}, "survival": {4, 5, 6, 7, 8}},
    {"name": "Anneal (B4678/S35678)", "birth": {4, 6, 7, 8}, "survival": {3, 5, 6, 7, 8}},
    {"name": "Day & Night (B3678/S34678)", "birth": {3, 6, 7, 8}, "survival": {3, 4, 6, 7, 8}},
    {"name": "Stains (B3678/S235678)", "birth": {3, 6, 7, 8}, "survival": {2, 3, 5, 6, 7, 8}},
    {"name": "Diamoeba (B35678/S5678)", "birth": {3, 5, 6, 7, 8}, "survival": {5, 6, 7, 8}},
    {"name": "Slow Decay (B3/S238)", "birth": {3}, "survival": {2, 3, 8}},
    {"name": "Life (B3/S23)", "birth": {3}, "survival": {2, 3}},
]

# Directions: (dr, dc)
DIRS = {
    "up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1),
}

# How many items to scatter per dungeon
ITEMS_PER_DUNGEON = 12


# ── Maze generation (recursive backtracker) ──

def _generate_maze(rows, cols):
    """Generate a maze using recursive backtracker. Returns 2D list of 0/1."""
    # Ensure odd dimensions for proper maze corridors
    mr = rows if rows % 2 == 1 else rows - 1
    mc = cols if cols % 2 == 1 else cols - 1
    maze = [[WALL] * cols for _ in range(rows)]

    def neighbors(r, c):
        """Return unvisited neighbors 2 cells away."""
        result = []
        for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            nr, nc = r + dr, c + dc
            if 1 <= nr < mr - 1 and 1 <= nc < mc - 1 and maze[nr][nc] == WALL:
                result.append((nr, nc, r + dr // 2, c + dc // 2))
        return result

    # Start from (1, 1)
    stack = [(1, 1)]
    maze[1][1] = FLOOR
    while stack:
        r, c = stack[-1]
        nbrs = neighbors(r, c)
        if nbrs:
            nr, nc, wr, wc = random.choice(nbrs)
            maze[wr][wc] = FLOOR
            maze[nr][nc] = FLOOR
            stack.append((nr, nc))
        else:
            stack.pop()

    # Open up some extra passages (30% of walls adjacent to 2+ floors)
    for r in range(1, mr - 1):
        for c in range(1, mc - 1):
            if maze[r][c] == WALL:
                adj_floors = sum(
                    1 for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                    if 0 <= r + dr < rows and 0 <= c + dc < cols
                    and maze[r + dr][c + dc] == FLOOR
                )
                if adj_floors >= 2 and random.random() < 0.3:
                    maze[r][c] = FLOOR

    return maze


def _find_open_cells(maze, rows, cols):
    """Return list of (r, c) floor cells."""
    return [(r, c) for r in range(rows) for c in range(cols) if maze[r][c] == FLOOR]


# ── CA step for the labyrinth ──

def _labyrinth_ca_step(cells, rows, cols, birth, survival, frozen_mask=None):
    """One CA generation. Returns new cells grid. frozen_mask prevents changes."""
    new = [[0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if frozen_mask and frozen_mask[r][c] > 0:
                new[r][c] = cells[r][c]
                continue
            # Count Moore neighbors
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = (r + dr) % rows
                    nc = (c + dc) % cols
                    if cells[nr][nc] > 0:
                        count += 1
            alive = cells[r][c] > 0
            if alive:
                new[r][c] = cells[r][c] + 1 if count in survival else 0
            else:
                new[r][c] = 1 if count in birth else 0
    return new


def _labyrinth_ca_step_local(cells, rows, cols, birth, survival, center_r, center_c, radius):
    """CA step only within radius of center. Returns new cells grid."""
    new = [row[:] for row in cells]
    for r in range(max(0, center_r - radius), min(rows, center_r + radius + 1)):
        for c in range(max(0, center_c - radius), min(cols, center_c + radius + 1)):
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = (r + dr) % rows
                    nc = (c + dc) % cols
                    if cells[nr][nc] > 0:
                        count += 1
            alive = cells[r][c] > 0
            if alive:
                new[r][c] = cells[r][c] + 1 if count in survival else 0
            else:
                new[r][c] = 1 if count in birth else 0
    return new


# ── State initialization ──

def _labyrinth_init(self):
    """Initialize Living Labyrinth state variables."""
    self.labyrinth_mode = False
    self.labyrinth_running = False
    self.labyrinth_cells = None       # 2D grid of wall/floor
    self.labyrinth_rows = 0
    self.labyrinth_cols = 0
    self.labyrinth_player_r = 1
    self.labyrinth_player_c = 1
    self.labyrinth_exit_r = 0
    self.labyrinth_exit_c = 0
    self.labyrinth_items = {}          # (r, c) -> item_type
    self.labyrinth_inventory = {ITEM_FREEZE: 0, ITEM_REVERSE: 0, ITEM_MUTATE: 0}
    self.labyrinth_frozen_mask = None  # 2D grid of freeze countdown timers
    self.labyrinth_birth = {3}
    self.labyrinth_survival = {1, 2, 3, 4, 5}
    self.labyrinth_rule_idx = 0
    self.labyrinth_ca_ticks = 1        # CA ticks per player move
    self.labyrinth_turn = 0
    self.labyrinth_score = 0
    self.labyrinth_level = 1
    self.labyrinth_wins = 0
    self.labyrinth_deaths = 0
    self.labyrinth_history = []        # for reverse item: past cell states
    self.labyrinth_max_history = 10
    self.labyrinth_show_help = False
    self.labyrinth_msg = ""
    self.labyrinth_msg_time = 0.0
    self.labyrinth_game_over = False
    self.labyrinth_won = False
    self.labyrinth_fov_radius = 20     # field of view radius


def _labyrinth_generate(self):
    """Generate a new labyrinth dungeon."""
    h, w = self.grid.rows, self.grid.cols
    self.labyrinth_rows = h
    self.labyrinth_cols = w

    # Generate base maze
    self.labyrinth_cells = _generate_maze(h, w)

    # Set CA rule
    rule = LABYRINTH_RULES[self.labyrinth_rule_idx]
    self.labyrinth_birth = set(rule["birth"])
    self.labyrinth_survival = set(rule["survival"])

    # Place player at a floor cell near top-left
    open_cells = _find_open_cells(self.labyrinth_cells, h, w)
    if not open_cells:
        # Fallback: clear center area
        for r in range(h // 4, 3 * h // 4):
            for c in range(w // 4, 3 * w // 4):
                self.labyrinth_cells[r][c] = FLOOR
        open_cells = _find_open_cells(self.labyrinth_cells, h, w)

    # Player near top-left
    open_cells.sort(key=lambda rc: rc[0] + rc[1])
    self.labyrinth_player_r, self.labyrinth_player_c = open_cells[0]

    # Exit near bottom-right
    open_cells.sort(key=lambda rc: rc[0] + rc[1], reverse=True)
    self.labyrinth_exit_r, self.labyrinth_exit_c = open_cells[0]

    # Ensure player and exit are not on walls
    self.labyrinth_cells[self.labyrinth_player_r][self.labyrinth_player_c] = FLOOR
    self.labyrinth_cells[self.labyrinth_exit_r][self.labyrinth_exit_c] = FLOOR

    # Clear area around player and exit (2-cell radius safety zone)
    for cr, cc in [(self.labyrinth_player_r, self.labyrinth_player_c),
                   (self.labyrinth_exit_r, self.labyrinth_exit_c)]:
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < h and 0 <= nc < w:
                    self.labyrinth_cells[nr][nc] = FLOOR

    # Scatter items on floor cells
    self.labyrinth_items = {}
    floor_cells = [
        (r, c) for r, c in _find_open_cells(self.labyrinth_cells, h, w)
        if (r, c) != (self.labyrinth_player_r, self.labyrinth_player_c)
        and (r, c) != (self.labyrinth_exit_r, self.labyrinth_exit_c)
    ]
    random.shuffle(floor_cells)
    item_types = [ITEM_FREEZE, ITEM_REVERSE, ITEM_MUTATE]
    for i in range(min(ITEMS_PER_DUNGEON, len(floor_cells))):
        self.labyrinth_items[floor_cells[i]] = random.choice(item_types)

    # Reset state
    self.labyrinth_frozen_mask = [[0] * w for _ in range(h)]
    self.labyrinth_history = []
    self.labyrinth_turn = 0
    self.labyrinth_game_over = False
    self.labyrinth_won = False
    self.labyrinth_inventory = {ITEM_FREEZE: 0, ITEM_REVERSE: 0, ITEM_MUTATE: 0}

    # Save initial state to history
    self.labyrinth_history.append([row[:] for row in self.labyrinth_cells])


def _labyrinth_flash(self, msg):
    """Show a temporary message."""
    self.labyrinth_msg = msg
    self.labyrinth_msg_time = time.time()


# ── Entry / exit ──

def _enter_labyrinth_mode(self):
    """Enter Living Labyrinth mode."""
    self.labyrinth_mode = True
    self.labyrinth_running = True
    self.labyrinth_level = 1
    self.labyrinth_wins = 0
    self.labyrinth_deaths = 0
    self.labyrinth_score = 0
    self.labyrinth_show_help = False
    _labyrinth_generate(self)
    _labyrinth_flash(self, "Welcome to the Living Labyrinth! Reach ◈ to escape. Press ? for help.")


def _exit_labyrinth_mode(self):
    """Exit Living Labyrinth mode."""
    self.labyrinth_mode = False
    self.labyrinth_running = False
    self.labyrinth_cells = None
    self.labyrinth_frozen_mask = None
    self.labyrinth_history = []
    self.labyrinth_items = {}


# ── CA tick ──

def _labyrinth_tick_ca(self):
    """Advance the CA one generation."""
    h, w = self.labyrinth_rows, self.labyrinth_cols

    # Save to history (for reverse item)
    if len(self.labyrinth_history) >= self.labyrinth_max_history:
        self.labyrinth_history.pop(0)
    self.labyrinth_history.append([row[:] for row in self.labyrinth_cells])

    # Step CA
    self.labyrinth_cells = _labyrinth_ca_step(
        self.labyrinth_cells, h, w,
        self.labyrinth_birth, self.labyrinth_survival,
        self.labyrinth_frozen_mask,
    )

    # Ensure player and exit cells stay open
    self.labyrinth_cells[self.labyrinth_player_r][self.labyrinth_player_c] = FLOOR
    self.labyrinth_cells[self.labyrinth_exit_r][self.labyrinth_exit_c] = FLOOR

    # Tick down freeze timers
    for r in range(h):
        for c in range(w):
            if self.labyrinth_frozen_mask[r][c] > 0:
                self.labyrinth_frozen_mask[r][c] -= 1


# ── Item usage ──

def _labyrinth_use_freeze(self):
    """Use freeze item: freeze CA in a radius around player for 10 turns."""
    if self.labyrinth_inventory[ITEM_FREEZE] <= 0:
        _labyrinth_flash(self, "No freeze items!")
        return
    self.labyrinth_inventory[ITEM_FREEZE] -= 1
    radius = 5
    pr, pc = self.labyrinth_player_r, self.labyrinth_player_c
    h, w = self.labyrinth_rows, self.labyrinth_cols
    for r in range(max(0, pr - radius), min(h, pr + radius + 1)):
        for c in range(max(0, pc - radius), min(w, pc + radius + 1)):
            if (r - pr) ** 2 + (c - pc) ** 2 <= radius ** 2:
                self.labyrinth_frozen_mask[r][c] = 10
    _labyrinth_flash(self, "❄ Freeze! Walls locked for 10 turns.")


def _labyrinth_use_reverse(self):
    """Use reverse item: rewind CA 5 steps in a radius around player."""
    if self.labyrinth_inventory[ITEM_REVERSE] <= 0:
        _labyrinth_flash(self, "No reverse items!")
        return
    self.labyrinth_inventory[ITEM_REVERSE] -= 1
    # Rewind to 5 steps ago if possible
    steps_back = min(5, len(self.labyrinth_history) - 1)
    if steps_back > 0:
        old = self.labyrinth_history[-(steps_back + 1)]
        radius = 6
        pr, pc = self.labyrinth_player_r, self.labyrinth_player_c
        h, w = self.labyrinth_rows, self.labyrinth_cols
        for r in range(max(0, pr - radius), min(h, pr + radius + 1)):
            for c in range(max(0, pc - radius), min(w, pc + radius + 1)):
                if (r - pr) ** 2 + (c - pc) ** 2 <= radius ** 2:
                    self.labyrinth_cells[r][c] = old[r][c]
        _labyrinth_flash(self, f"⊛ Reverse! Rewound {steps_back} steps locally.")
    else:
        _labyrinth_flash(self, "Not enough history to rewind!")


def _labyrinth_use_mutate(self):
    """Use mutate item: randomize CA rule in a radius, creating chaos."""
    if self.labyrinth_inventory[ITEM_MUTATE] <= 0:
        _labyrinth_flash(self, "No mutate items!")
        return
    self.labyrinth_inventory[ITEM_MUTATE] -= 1
    # Apply a random local mutation by flipping some cells
    radius = 7
    pr, pc = self.labyrinth_player_r, self.labyrinth_player_c
    h, w = self.labyrinth_rows, self.labyrinth_cols
    flipped = 0
    for r in range(max(0, pr - radius), min(h, pr + radius + 1)):
        for c in range(max(0, pc - radius), min(w, pc + radius + 1)):
            if (r - pr) ** 2 + (c - pc) ** 2 <= radius ** 2:
                if random.random() < 0.4:
                    self.labyrinth_cells[r][c] = FLOOR if self.labyrinth_cells[r][c] > 0 else WALL
                    flipped += 1
    _labyrinth_flash(self, f"✦ Mutate! Flipped {flipped} cells nearby.")


# ── Player movement ──

def _labyrinth_move(self, dr, dc):
    """Try to move player in direction (dr, dc). Returns True if moved."""
    if self.labyrinth_game_over:
        return False
    nr = self.labyrinth_player_r + dr
    nc = self.labyrinth_player_c + dc
    h, w = self.labyrinth_rows, self.labyrinth_cols

    if nr < 0 or nr >= h or nc < 0 or nc >= w:
        return False

    if self.labyrinth_cells[nr][nc] > 0:
        _labyrinth_flash(self, "Blocked by wall!")
        return False

    self.labyrinth_player_r = nr
    self.labyrinth_player_c = nc

    # Pick up items
    pos = (nr, nc)
    if pos in self.labyrinth_items:
        item_type = self.labyrinth_items.pop(pos)
        self.labyrinth_inventory[item_type] += 1
        name = item_type.capitalize()
        _labyrinth_flash(self, f"Picked up {ITEM_CHARS[item_type]} {name}!")

    # Check win
    if nr == self.labyrinth_exit_r and nc == self.labyrinth_exit_c:
        self.labyrinth_won = True
        self.labyrinth_game_over = True
        self.labyrinth_wins += 1
        bonus = max(0, 500 - self.labyrinth_turn * 2)
        level_bonus = self.labyrinth_level * 100
        self.labyrinth_score += bonus + level_bonus
        _labyrinth_flash(self, f"Level {self.labyrinth_level} complete! Score +{bonus + level_bonus}")

    return True


def _labyrinth_player_turn(self, dr, dc):
    """Execute a player turn: move, then tick CA."""
    moved = _labyrinth_move(self, dr, dc)

    # Tick CA regardless of whether player moved (time passes)
    self.labyrinth_turn += 1
    for _ in range(self.labyrinth_ca_ticks):
        _labyrinth_tick_ca(self)

    # Check if player got trapped (surrounded by walls)
    pr, pc = self.labyrinth_player_r, self.labyrinth_player_c
    h, w = self.labyrinth_rows, self.labyrinth_cols
    if self.labyrinth_cells[pr][pc] > 0 and not self.labyrinth_game_over:
        # Player got crushed by a wall!
        self.labyrinth_game_over = True
        self.labyrinth_won = False
        self.labyrinth_deaths += 1
        _labyrinth_flash(self, "Crushed by the living walls! Press 'n' for new dungeon.")


# ── Key handler ──

def _handle_labyrinth_key(self, key):
    """Handle keyboard input for Living Labyrinth mode."""
    if key == ord('q') or key == 27:  # q or Escape
        _exit_labyrinth_mode(self)
        return True

    if key == ord('?'):
        self.labyrinth_show_help = not self.labyrinth_show_help
        return True

    if key == ord('n'):
        if self.labyrinth_won:
            self.labyrinth_level += 1
        else:
            self.labyrinth_level = 1
            self.labyrinth_score = 0
        _labyrinth_generate(self)
        _labyrinth_flash(self, f"Level {self.labyrinth_level} — {LABYRINTH_RULES[self.labyrinth_rule_idx]['name']}")
        return True

    if self.labyrinth_game_over and self.labyrinth_won:
        # Auto-advance on any movement key after winning
        if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT,
                   ord('w'), ord('a'), ord('s'), ord('d'),
                   ord('h'), ord('j'), ord('k'), ord('l'), ord(' ')):
            self.labyrinth_level += 1
            # Cycle rule every 3 levels for variety
            if self.labyrinth_level % 3 == 1 and self.labyrinth_level > 1:
                self.labyrinth_rule_idx = (self.labyrinth_rule_idx + 1) % len(LABYRINTH_RULES)
            _labyrinth_generate(self)
            _labyrinth_flash(self, f"Level {self.labyrinth_level} — {LABYRINTH_RULES[self.labyrinth_rule_idx]['name']}")
            return True

    if self.labyrinth_game_over:
        return True

    # Movement keys
    if key == curses.KEY_UP or key == ord('w') or key == ord('k'):
        _labyrinth_player_turn(self, -1, 0)
        return True
    if key == curses.KEY_DOWN or key == ord('s') or key == ord('j'):
        _labyrinth_player_turn(self, 1, 0)
        return True
    if key == curses.KEY_LEFT or key == ord('a') or key == ord('h'):
        _labyrinth_player_turn(self, 0, -1)
        return True
    if key == curses.KEY_RIGHT or key == ord('d') or key == ord('l'):
        _labyrinth_player_turn(self, 0, 1)
        return True
    if key == ord(' '):
        # Wait: just tick CA
        _labyrinth_player_turn(self, 0, 0)
        return True

    # Item usage
    if key == ord('f'):
        _labyrinth_use_freeze(self)
        return True
    if key == ord('v'):
        _labyrinth_use_reverse(self)
        return True
    if key == ord('m'):
        _labyrinth_use_mutate(self)
        return True

    # Rule cycling
    if key == ord('r'):
        self.labyrinth_rule_idx = (self.labyrinth_rule_idx + 1) % len(LABYRINTH_RULES)
        rule = LABYRINTH_RULES[self.labyrinth_rule_idx]
        self.labyrinth_birth = set(rule["birth"])
        self.labyrinth_survival = set(rule["survival"])
        _labyrinth_flash(self, f"Rule: {rule['name']}")
        return True

    # CA tick rate
    if key == ord('+') or key == ord('='):
        self.labyrinth_ca_ticks = min(5, self.labyrinth_ca_ticks + 1)
        _labyrinth_flash(self, f"CA ticks per move: {self.labyrinth_ca_ticks}")
        return True
    if key == ord('-'):
        self.labyrinth_ca_ticks = max(1, self.labyrinth_ca_ticks - 1)
        _labyrinth_flash(self, f"CA ticks per move: {self.labyrinth_ca_ticks}")
        return True

    return True


# ── Drawing ──

def _draw_labyrinth(self):
    """Render the Living Labyrinth."""
    scr = self.stdscr
    scr.erase()
    max_h, max_w = scr.getmaxyx()

    if self.labyrinth_cells is None:
        return

    h, w = self.labyrinth_rows, self.labyrinth_cols
    pr, pc = self.labyrinth_player_r, self.labyrinth_player_c
    er, ec = self.labyrinth_exit_r, self.labyrinth_exit_c

    # Viewport: center on player
    view_h = max_h - 3  # leave room for HUD
    view_w = max_w // 2  # each cell is 2 chars wide
    half_h = view_h // 2
    half_w = view_w // 2
    cam_r = max(half_h, min(h - half_h - 1, pr))
    cam_c = max(half_w, min(w - half_w - 1, pc))
    start_r = cam_r - half_h
    start_c = cam_c - half_w

    # Color pairs (reuse existing if possible, or use basic curses colors)
    # Wall colors by age
    try:
        curses.init_pair(200, curses.COLOR_WHITE, curses.COLOR_WHITE)
        curses.init_pair(201, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(202, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(203, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(204, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(205, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(206, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(207, curses.COLOR_WHITE, curses.COLOR_BLUE)  # frozen
    except curses.error:
        pass

    for screen_r in range(view_h):
        grid_r = start_r + screen_r
        if grid_r < 0 or grid_r >= h:
            continue
        for screen_c in range(view_w):
            grid_c = start_c + screen_c
            if grid_c < 0 or grid_c >= w:
                continue
            sx = screen_c * 2
            sy = screen_r
            if sy >= max_h - 3 or sx + 1 >= max_w:
                continue

            # Determine what to draw
            pos = (grid_r, grid_c)
            ch = None
            attr = curses.A_NORMAL

            if grid_r == pr and grid_c == pc:
                # Player
                ch = PLAYER_CHAR + " "
                attr = curses.color_pair(201) | curses.A_BOLD
            elif grid_r == er and grid_c == ec:
                # Exit portal
                ch = EXIT_CHAR + " "
                attr = curses.color_pair(203) | curses.A_BOLD
            elif pos in self.labyrinth_items:
                # Item on floor
                item_type = self.labyrinth_items[pos]
                ch = ITEM_CHARS[item_type] + " "
                if item_type == ITEM_FREEZE:
                    attr = curses.color_pair(202) | curses.A_BOLD
                elif item_type == ITEM_REVERSE:
                    attr = curses.color_pair(205) | curses.A_BOLD
                else:
                    attr = curses.color_pair(203) | curses.A_BOLD
            elif self.labyrinth_cells[grid_r][grid_c] > 0:
                # Wall
                age = self.labyrinth_cells[grid_r][grid_c]
                if self.labyrinth_frozen_mask[grid_r][grid_c] > 0:
                    ch = WALL_CHAR
                    attr = curses.color_pair(207)
                elif age <= 1:
                    ch = "░░"
                    attr = curses.color_pair(204)
                elif age <= 3:
                    ch = "▒▒"
                    attr = curses.color_pair(204)
                elif age <= 8:
                    ch = "▓▓"
                    attr = curses.color_pair(200)
                else:
                    ch = WALL_CHAR
                    attr = curses.color_pair(200)
            else:
                # Floor
                ch = FLOOR_CHAR
                attr = curses.color_pair(206) | curses.A_DIM

            try:
                scr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    # ── HUD ──
    hud_y = max_h - 3
    rule = LABYRINTH_RULES[self.labyrinth_rule_idx]

    # Status line
    inv_str = (
        f"❄×{self.labyrinth_inventory[ITEM_FREEZE]} "
        f"⊛×{self.labyrinth_inventory[ITEM_REVERSE]} "
        f"✦×{self.labyrinth_inventory[ITEM_MUTATE]}"
    )
    status = (
        f" Lv {self.labyrinth_level} │ Turn {self.labyrinth_turn} │ "
        f"Score {self.labyrinth_score} │ {inv_str} │ "
        f"Rule: {rule['name']} │ CA/move: {self.labyrinth_ca_ticks}"
    )
    try:
        scr.addstr(hud_y, 0, status[:max_w - 1], curses.A_REVERSE)
        # Pad rest of line
        remaining = max_w - 1 - len(status)
        if remaining > 0:
            scr.addstr(hud_y, len(status), " " * remaining, curses.A_REVERSE)
    except curses.error:
        pass

    # Stats line
    stats = (
        f" W:{self.labyrinth_wins} D:{self.labyrinth_deaths} │ "
        f"Pos: ({pr},{pc}) → Exit: ({er},{ec}) │ "
        f"[?]Help [f]Freeze [v]Reverse [m]Mutate [r]Rule [n]New [q]Quit"
    )
    try:
        scr.addstr(hud_y + 1, 0, stats[:max_w - 1], curses.A_DIM)
    except curses.error:
        pass

    # Flash message
    if self.labyrinth_msg and time.time() - self.labyrinth_msg_time < 3.0:
        msg = f" {self.labyrinth_msg} "
        msg_x = max(0, (max_w - len(msg)) // 2)
        try:
            scr.addstr(hud_y + 2, msg_x, msg[:max_w - 1],
                       curses.color_pair(203) | curses.A_BOLD)
        except curses.error:
            pass

    # Game over overlay
    if self.labyrinth_game_over:
        if self.labyrinth_won:
            msg = f"  ◈ LEVEL {self.labyrinth_level} COMPLETE! Press any move key to continue.  "
            attr = curses.color_pair(201) | curses.A_BOLD
        else:
            msg = "  ☠ CRUSHED! Press 'n' for new dungeon.  "
            attr = curses.color_pair(204) | curses.A_BOLD
        msg_x = max(0, (max_w - len(msg)) // 2)
        msg_y = max(0, view_h // 2)
        try:
            scr.addstr(msg_y, msg_x, msg, attr)
        except curses.error:
            pass

    # Help overlay
    if self.labyrinth_show_help:
        help_lines = [
            "╔══════════════════════════════════════╗",
            "║      LIVING LABYRINTH — HELP         ║",
            "╠══════════════════════════════════════╣",
            "║ Arrow/WASD/hjkl — Move player (@)    ║",
            "║ Space           — Wait (CA ticks)     ║",
            "║ f               — Use Freeze item     ║",
            "║ v               — Use Reverse item    ║",
            "║ m               — Use Mutate item     ║",
            "║ r               — Cycle CA rule       ║",
            "║ n               — New dungeon          ║",
            "║ +/-             — CA ticks per move    ║",
            "║ ?               — Toggle this help     ║",
            "║ q/Esc           — Exit mode            ║",
            "╠══════════════════════════════════════╣",
            "║ Walls grow & decay by CA rules.       ║",
            "║ Reach ◈ before paths seal shut!       ║",
            "║ ❄ Freeze  — lock walls 10 turns       ║",
            "║ ⊛ Reverse — rewind walls 5 steps      ║",
            "║ ✦ Mutate  — randomize walls nearby    ║",
            "╚══════════════════════════════════════╝",
        ]
        hy = max(0, (view_h - len(help_lines)) // 2)
        hx = max(0, (max_w - 40) // 2)
        for i, line in enumerate(help_lines):
            try:
                scr.addstr(hy + i, hx, line, curses.A_BOLD)
            except curses.error:
                pass

    scr.nontimeout(True)
    scr.timeout(100)  # 100ms refresh for responsiveness


# ── Step (auto-called by dispatch) ──

def _labyrinth_step(self):
    """Auto-step: no-op since movement is turn-based."""
    pass


def _is_labyrinth_auto_stepping(self):
    """Labyrinth is turn-based, no auto-stepping."""
    return False


# ── Menu (simple — no separate menu needed) ──

def _handle_labyrinth_menu_key(self, key):
    """No separate menu for labyrinth."""
    return _handle_labyrinth_key(self, key)


def _draw_labyrinth_menu(self):
    """No separate menu draw."""
    _draw_labyrinth(self)


# ── Registration ──

def register(App):
    """Register Living Labyrinth mode methods on App class."""
    App.labyrinth_mode = False
    App.labyrinth_running = False
    _labyrinth_init(App)

    App._enter_labyrinth_mode = _enter_labyrinth_mode
    App._exit_labyrinth_mode = _exit_labyrinth_mode
    App._handle_labyrinth_key = _handle_labyrinth_key
    App._handle_labyrinth_menu_key = _handle_labyrinth_menu_key
    App._draw_labyrinth = _draw_labyrinth
    App._draw_labyrinth_menu = _draw_labyrinth_menu
    App._labyrinth_step = _labyrinth_step
    App._is_labyrinth_auto_stepping = _is_labyrinth_auto_stepping
