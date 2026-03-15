"""Mode: battle_royale — 4 cellular automata factions compete for territory on a shared grid."""
import curses
import random
import time

from life.constants import SPEEDS

# Density visualization characters
_DENSITY = " ░▒▓█"

# ── Faction definitions ─────────────────────────────────────────────
# Each faction is a CA rule set defined by birth/survival in B/S notation.

FACTIONS = [
    {"name": "Life",       "id": "life",      "birth": {3},       "survival": {2, 3},
     "desc": "Conway's Game of Life (B3/S23)", "symbol": "██", "char": "L"},
    {"name": "HighLife",   "id": "highlife",   "birth": {3, 6},    "survival": {2, 3},
     "desc": "HighLife (B36/S23) — replicators", "symbol": "▓▓", "char": "H"},
    {"name": "Day&Night",  "id": "daynight",   "birth": {3, 6, 7, 8}, "survival": {3, 4, 6, 7, 8},
     "desc": "Day & Night (B3678/S34678)", "symbol": "▒▒", "char": "D"},
    {"name": "Seeds",      "id": "seeds",      "birth": {2},       "survival": set(),
     "desc": "Seeds (B2/S) — explosive growth", "symbol": "░░", "char": "S"},
    {"name": "Morley",     "id": "morley",     "birth": {3, 6, 8}, "survival": {2, 4, 5},
     "desc": "Morley / Move (B368/S245)", "symbol": "██", "char": "M"},
    {"name": "Maze",       "id": "maze",       "birth": {3},       "survival": {1, 2, 3, 4, 5},
     "desc": "Maze (B3/S12345) — fills space", "symbol": "▓▓", "char": "Z"},
    {"name": "Amoeba",     "id": "amoeba",     "birth": {3, 5, 7}, "survival": {1, 3, 5, 8},
     "desc": "Amoeba (B357/S1358)", "symbol": "▒▒", "char": "A"},
    {"name": "Diamoeba",   "id": "diamoeba",   "birth": {3, 5, 6, 7, 8}, "survival": {5, 6, 7, 8},
     "desc": "Diamoeba (B35678/S5678)", "symbol": "░░", "char": "I"},
]

FACTION_BY_ID = {f["id"]: f for f in FACTIONS}

# Preset combinations (4 factions each)
PRESETS = [
    ("Classic Showdown", ["life", "highlife", "daynight", "seeds"],
     "The four most iconic CA rules battle it out"),
    ("Aggressive Mix", ["seeds", "morley", "highlife", "diamoeba"],
     "Fast-growing explosive rules — quick eliminations"),
    ("Territorial War", ["maze", "amoeba", "daynight", "life"],
     "Space-filling rules compete for every cell"),
    ("Survival of the Fittest", ["life", "morley", "amoeba", "diamoeba"],
     "Diverse survival strategies clash"),
]

# Color pairs for each faction (we use 4 factions, pairs 140-155)
# Faction 0: blue, 1: red, 2: green, 3: yellow
_FACTION_256_COLORS = [
    [33, 39, 27, 21],      # Faction 0: blues
    [196, 209, 160, 124],   # Faction 1: reds
    [46, 48, 34, 22],       # Faction 2: greens
    [226, 220, 214, 178],   # Faction 3: yellows
]
_FACTION_8_COLORS = [
    curses.COLOR_BLUE,
    curses.COLOR_RED,
    curses.COLOR_GREEN,
    curses.COLOR_YELLOW,
]


def _init_br_colors():
    """Initialize color pairs 140-155 for battle royale factions."""
    if curses.COLORS >= 256:
        for fi in range(4):
            for ai in range(4):
                curses.init_pair(140 + fi * 4 + ai, _FACTION_256_COLORS[fi][ai], -1)
    else:
        for fi in range(4):
            for ai in range(4):
                curses.init_pair(140 + fi * 4 + ai, _FACTION_8_COLORS[fi], -1)
    # Neutral/empty pair
    curses.init_pair(156, curses.COLOR_WHITE, -1)


def _faction_color(faction_idx, age):
    """Return curses color pair for a faction cell based on age."""
    if age <= 1:
        ai = 0
    elif age <= 4:
        ai = 1
    elif age <= 10:
        ai = 2
    else:
        ai = 3
    return curses.color_pair(140 + faction_idx * 4 + ai)


# ════════════════════════════════════════════════════════════════════
#  Grid state
#
#  owner[r][c] = -1 (neutral/dead) or 0..3 (faction index)
#  age[r][c]   = how many generations this cell has been alive
# ════════════════════════════════════════════════════════════════════

def _br_init_grid(rows, cols, faction_ids):
    """Create initial grid with 4 factions in corners."""
    owner = [[-1] * cols for _ in range(rows)]
    age = [[0] * cols for _ in range(rows)]

    # Each faction gets a corner block, ~1/8 of each dimension
    spawn_h = max(3, rows // 6)
    spawn_w = max(3, cols // 6)

    corners = [
        (0, 0),                          # top-left
        (0, cols - spawn_w),             # top-right
        (rows - spawn_h, 0),             # bottom-left
        (rows - spawn_h, cols - spawn_w), # bottom-right
    ]

    for fi in range(min(4, len(faction_ids))):
        sr, sc = corners[fi]
        for r in range(sr, sr + spawn_h):
            for c in range(sc, sc + spawn_w):
                if random.random() < 0.45:
                    owner[r % rows][c % cols] = fi
                    age[r % rows][c % cols] = 1

    return owner, age


def _br_step(owner, age, rows, cols, factions):
    """Advance the battle royale by one generation.

    Rules:
    1. For each empty cell, count neighbors from each faction.
       If exactly one faction meets the cell's birth condition
       (using that faction's birth set), the cell is born as that faction.
       If multiple factions could birth, the one with more neighbors wins.
    2. For each alive cell, check survival with that faction's survival set.
       Also check for enemy attack: if neighboring enemy density exceeds
       own-faction neighbors, the cell dies (conquered).
    3. Dead cells from conquest become neutral.
    """
    new_owner = [[-1] * cols for _ in range(rows)]
    new_age = [[0] * cols for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            # Count neighbors by faction
            counts = [0, 0, 0, 0]
            total = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = (r + dr) % rows
                    nc = (c + dc) % cols
                    o = owner[nr][nc]
                    if o >= 0:
                        counts[o] += 1
                        total += 1

            cur_owner = owner[r][c]

            if cur_owner < 0:
                # Empty cell — check birth from each faction
                best_faction = -1
                best_count = 0
                for fi in range(4):
                    if counts[fi] > 0 and counts[fi] in factions[fi]["birth"]:
                        if counts[fi] > best_count:
                            best_count = counts[fi]
                            best_faction = fi
                        elif counts[fi] == best_count and best_faction >= 0:
                            # Tie — randomly pick
                            if random.random() < 0.5:
                                best_faction = fi
                if best_faction >= 0:
                    new_owner[r][c] = best_faction
                    new_age[r][c] = 1
            else:
                # Alive cell — check survival
                own_count = counts[cur_owner]
                enemy_count = total - own_count

                # Survival check using faction's rules
                survives = own_count in factions[cur_owner]["survival"]

                # Combat: if enemy density around this cell is much higher,
                # the cell gets overwritten by the dominant enemy faction
                if survives and enemy_count > own_count + 1:
                    # Find dominant enemy
                    max_enemy = -1
                    max_enemy_count = 0
                    for fi in range(4):
                        if fi != cur_owner and counts[fi] > max_enemy_count:
                            max_enemy_count = counts[fi]
                            max_enemy = fi
                    if max_enemy >= 0 and max_enemy_count >= 3:
                        # Conquered!
                        new_owner[r][c] = max_enemy
                        new_age[r][c] = 1
                        survives = False

                if survives:
                    new_owner[r][c] = cur_owner
                    new_age[r][c] = age[r][c] + 1

    return new_owner, new_age


def _br_scores(owner, rows, cols, num_factions=4):
    """Return territory counts for each faction and total cells."""
    counts = [0] * num_factions
    total = rows * cols
    for r in range(rows):
        for c in range(cols):
            o = owner[r][c]
            if o >= 0:
                counts[o] += 1
    return counts, total


# ════════════════════════════════════════════════════════════════════
#  Mode entry / exit
# ════════════════════════════════════════════════════════════════════

def _enter_battle_royale(self):
    """Enter Battle Royale mode — show faction selection menu."""
    self.br_menu = True
    self.br_menu_sel = 0
    self.br_menu_phase = 0  # 0=presets, 1=pick factions
    self.br_custom_picks = []
    self._flash("Battle Royale — pick your combatants!")


def _exit_battle_royale(self):
    """Exit Battle Royale mode."""
    self.br_mode = False
    self.br_menu = False
    self.br_running = False
    self._flash("Battle Royale OFF")


# ════════════════════════════════════════════════════════════════════
#  Initialization
# ════════════════════════════════════════════════════════════════════

def _br_init(self, faction_ids):
    """Set up a fresh battle royale with chosen factions."""
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(20, max_y - 6)
    cols = max(20, (max_x - 1) // 2)
    self.br_rows = rows
    self.br_cols = cols
    self.br_faction_ids = faction_ids[:4]
    self.br_factions = [FACTION_BY_ID[fid] for fid in self.br_faction_ids]
    self.br_eliminated = [False] * 4
    self.br_winner = -1
    self.br_generation = 0
    self.br_running = False

    _init_br_colors()

    self.br_owner, self.br_age = _br_init_grid(rows, cols, faction_ids)
    self.br_scores, _ = _br_scores(self.br_owner, rows, cols)

    self.br_menu = False
    self.br_mode = True
    names = " vs ".join(FACTION_BY_ID[fid]["name"] for fid in faction_ids[:4])
    self._flash(f"Battle Royale: {names} — Space to start!")


# ════════════════════════════════════════════════════════════════════
#  Simulation step
# ════════════════════════════════════════════════════════════════════

def _br_do_step(self):
    """Advance battle royale by one generation."""
    if self.br_winner >= 0:
        return  # game over

    self.br_owner, self.br_age = _br_step(
        self.br_owner, self.br_age, self.br_rows, self.br_cols, self.br_factions
    )
    self.br_generation += 1

    # Update scores and check eliminations
    self.br_scores, total = _br_scores(self.br_owner, self.br_rows, self.br_cols)
    alive_factions = []
    for fi in range(4):
        if self.br_scores[fi] == 0 and not self.br_eliminated[fi]:
            self.br_eliminated[fi] = True
        if self.br_scores[fi] > 0:
            alive_factions.append(fi)

    # Check for winner
    if len(alive_factions) == 1:
        self.br_winner = alive_factions[0]
        self.br_running = False
        self._flash(f"{self.br_factions[self.br_winner]['name']} WINS the Battle Royale!")
    elif len(alive_factions) == 0:
        # Everyone died simultaneously
        self.br_winner = -2  # draw
        self.br_running = False
        self._flash("DRAW — all factions eliminated simultaneously!")


# ════════════════════════════════════════════════════════════════════
#  Drawing — Menu
# ════════════════════════════════════════════════════════════════════

def _draw_br_menu(self, max_y, max_x):
    """Draw the battle royale faction selection menu."""
    self.stdscr.erase()

    title = "═══ BATTLE ROYALE ═══"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "4 CA factions start in corners and fight for territory"
    try:
        self.stdscr.addstr(2, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    phase = self.br_menu_phase

    if phase == 0:
        # Preset selection
        label = "Choose a preset or build custom:"
        try:
            self.stdscr.addstr(4, 2, label, curses.color_pair(6))
        except curses.error:
            pass

        for i, (name, ids, desc) in enumerate(PRESETS):
            y = 6 + i
            if y >= max_y - 3:
                break
            sel = i == self.br_menu_sel
            marker = "▸ " if sel else "  "
            attr = curses.color_pair(7) | curses.A_BOLD if sel else curses.color_pair(6)
            fnames = ", ".join(FACTION_BY_ID[fid]["name"] for fid in ids)
            line = f"{marker}{name}  ({fnames})"
            try:
                self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
            except curses.error:
                pass
            if sel:
                try:
                    self.stdscr.addstr(y + 1, 6, desc[:max_x - 8],
                                       curses.color_pair(6) | curses.A_DIM)
                except curses.error:
                    pass

        # Custom option
        ci = len(PRESETS)
        y = 6 + ci + 1
        if y < max_y - 3:
            sel = self.br_menu_sel == ci
            marker = "▸ " if sel else "  "
            attr = curses.color_pair(7) | curses.A_BOLD if sel else curses.color_pair(3)
            try:
                self.stdscr.addstr(y, 2, f"{marker}Custom Battle..."[:max_x - 4], attr)
            except curses.error:
                pass

        hint = " [↑/↓]=select [Enter]=start [q]=exit"
        try:
            self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    elif phase == 1:
        # Custom faction picking
        picked = len(self.br_custom_picks)
        label = f"Pick faction {picked + 1} of 4:"
        try:
            self.stdscr.addstr(4, 2, label, curses.color_pair(6))
        except curses.error:
            pass

        # Show already picked
        if self.br_custom_picks:
            picked_names = ", ".join(FACTION_BY_ID[fid]["name"] for fid in self.br_custom_picks)
            try:
                self.stdscr.addstr(5, 4, f"Selected: {picked_names}"[:max_x - 6],
                                   curses.color_pair(7))
            except curses.error:
                pass

        for i, f in enumerate(FACTIONS):
            y = 7 + i
            if y >= max_y - 3:
                break
            sel = i == self.br_menu_sel
            already = f["id"] in self.br_custom_picks
            marker = "▸ " if sel else "  "
            if already:
                attr = curses.color_pair(6) | curses.A_DIM
                marker = "✓ "
            elif sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            else:
                attr = curses.color_pair(6)
            line = f"{marker}{f['name']}  —  {f['desc']}"
            try:
                self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
            except curses.error:
                pass

        hint = " [↑/↓]=select [Enter]=pick [q]=back"
        try:
            self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ════════════════════════════════════════════════════════════════════
#  Drawing — Battle Grid
# ════════════════════════════════════════════════════════════════════

def _draw_battle_royale(self, max_y, max_x):
    """Render the battle royale grid with scoreboard."""
    self.stdscr.erase()
    rows = self.br_rows
    cols = self.br_cols

    # Reserve bottom rows for scoreboard + hints
    grid_h = max(5, max_y - 6)
    grid_w = max(5, (max_x - 1) // 2)

    # Draw grid
    for y in range(min(grid_h, rows)):
        for x in range(min(grid_w, cols)):
            o = self.br_owner[y][x]
            if o < 0:
                continue  # empty — leave blank
            a = self.br_age[y][x]
            col = _faction_color(o, a)
            ch = self.br_factions[o]["symbol"]
            sx = x * 2
            if sx + 2 <= max_x and y < max_y:
                try:
                    self.stdscr.addstr(y, sx, ch, col)
                except curses.error:
                    pass

    # ── Scoreboard ──
    score_y = max_y - 5
    total = self.br_rows * self.br_cols
    if score_y > 0 and score_y < max_y:
        # Title line
        gen_str = f" Gen {self.br_generation}"
        if self.br_winner >= 0:
            gen_str += f"  ★ {self.br_factions[self.br_winner]['name']} WINS! ★"
        elif self.br_winner == -2:
            gen_str += "  ★ DRAW ★"
        try:
            self.stdscr.addstr(score_y, 0, gen_str[:max_x - 1],
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

    # Faction scores line
    score_y2 = max_y - 4
    if score_y2 > 0 and score_y2 < max_y:
        parts = []
        for fi in range(4):
            if fi < len(self.br_factions):
                f = self.br_factions[fi]
                sc = self.br_scores[fi]
                pct = (sc / total * 100) if total > 0 else 0
                status = "☠" if self.br_eliminated[fi] else ""
                parts.append(f"{f['char']}:{sc}({pct:.1f}%){status}")
        score_line = "  ".join(parts)
        try:
            self.stdscr.addstr(score_y2, 1, score_line[:max_x - 2],
                               curses.color_pair(6))
        except curses.error:
            pass

    # Territory bar
    bar_y = max_y - 3
    if bar_y > 0 and bar_y < max_y:
        bar_w = max_x - 2
        if bar_w > 4 and total > 0:
            bar = ""
            faction_chars = []
            for fi in range(4):
                n = int(self.br_scores[fi] / total * bar_w) if total > 0 else 0
                faction_chars.append((fi, n))

            x_pos = 1
            for fi, n in faction_chars:
                if n > 0:
                    seg = "█" * n
                    col = _faction_color(fi, 2)
                    try:
                        self.stdscr.addstr(bar_y, x_pos, seg[:max_x - x_pos - 1], col)
                    except curses.error:
                        pass
                    x_pos += n

    # Legend line
    legend_y = max_y - 2
    if legend_y > 0 and legend_y < max_y:
        parts = []
        colors_8 = [curses.COLOR_BLUE, curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW]
        for fi in range(min(4, len(self.br_factions))):
            f = self.br_factions[fi]
            parts.append(f"{f['char']}={f['name']}")
        legend = "  ".join(parts)
        try:
            self.stdscr.addstr(legend_y, 1, legend[:max_x - 2],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if hasattr(self, 'message') and self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            if self.br_winner >= 0 or self.br_winner == -2:
                hint = " [r]=rematch [R]=menu [q]=exit"
            else:
                hint = " [Space]=play [n]=step [r]=restart [R]=menu [</>=speed [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ════════════════════════════════════════════════════════════════════
#  Key handling — Menu
# ════════════════════════════════════════════════════════════════════

def _handle_br_menu_key(self, key):
    """Handle input during battle royale menu."""
    if key == -1:
        return True
    if key == ord("q") or key == 27:
        if self.br_menu_phase == 1:
            # Go back to presets
            self.br_menu_phase = 0
            self.br_menu_sel = 0
            self.br_custom_picks = []
            return True
        self.br_menu = False
        self._flash("Battle Royale cancelled")
        return True

    phase = self.br_menu_phase

    if phase == 0:
        n_items = len(PRESETS) + 1  # presets + custom
        if key == curses.KEY_UP or key == ord("k"):
            self.br_menu_sel = (self.br_menu_sel - 1) % n_items
        elif key == curses.KEY_DOWN or key == ord("j"):
            self.br_menu_sel = (self.br_menu_sel + 1) % n_items
        elif key == ord("\n") or key == ord(" "):
            if self.br_menu_sel < len(PRESETS):
                _, ids, _ = PRESETS[self.br_menu_sel]
                self._br_init(ids)
            else:
                # Custom
                self.br_menu_phase = 1
                self.br_menu_sel = 0
                self.br_custom_picks = []
        return True

    elif phase == 1:
        n_items = len(FACTIONS)
        if key == curses.KEY_UP or key == ord("k"):
            self.br_menu_sel = (self.br_menu_sel - 1) % n_items
        elif key == curses.KEY_DOWN or key == ord("j"):
            self.br_menu_sel = (self.br_menu_sel + 1) % n_items
        elif key == ord("\n") or key == ord(" "):
            fid = FACTIONS[self.br_menu_sel]["id"]
            if fid not in self.br_custom_picks:
                self.br_custom_picks.append(fid)
                if len(self.br_custom_picks) == 4:
                    self._br_init(self.br_custom_picks)
        return True

    return True


# ════════════════════════════════════════════════════════════════════
#  Key handling — Battle
# ════════════════════════════════════════════════════════════════════

def _handle_br_key(self, key):
    """Handle input during active battle royale."""
    if key == -1:
        return True
    if key == ord("q") or key == 27:
        self._exit_battle_royale()
        return True
    if key == ord(" "):
        if self.br_winner < 0:
            self.br_running = not self.br_running
            self._flash("Playing" if self.br_running else "Paused")
        return True
    if key == ord("n") or key == ord("."):
        if self.br_winner < 0:
            self.br_running = False
            self._br_do_step()
        return True
    if key == ord("r"):
        # Restart with same factions
        self._br_init(self.br_faction_ids)
        self._flash("Rematch!")
        return True
    if key == ord("R"):
        # Back to menu
        self.br_mode = False
        self.br_running = False
        self.br_menu = True
        self.br_menu_phase = 0
        self.br_menu_sel = 0
        return True
    if key == ord(">"):
        if self.speed_idx < len(SPEEDS) - 1:
            self.speed_idx += 1
        return True
    if key == ord("<"):
        if self.speed_idx > 0:
            self.speed_idx -= 1
        return True
    return True


# ════════════════════════════════════════════════════════════════════
#  Registration
# ════════════════════════════════════════════════════════════════════

def register(App):
    """Register battle royale mode methods on the App class."""
    App._enter_battle_royale = _enter_battle_royale
    App._exit_battle_royale = _exit_battle_royale
    App._br_init = _br_init
    App._br_do_step = _br_do_step
    App._handle_br_menu_key = _handle_br_menu_key
    App._handle_br_key = _handle_br_key
    App._draw_br_menu = _draw_br_menu
    App._draw_battle_royale = _draw_battle_royale
