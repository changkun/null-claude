#!/usr/bin/env python3
"""Terminal-based Conway's Game of Life simulator."""

import argparse
import collections
import copy
import curses
import hashlib
import json
import os
import sys
import time

SAVE_DIR = os.path.expanduser("~/.life_saves")

# ── Rule presets (Life-like cellular automata) ───────────────────────────────

RULE_PRESETS = {
    "Conway's Life": {"birth": {3}, "survival": {2, 3}},
    "HighLife":      {"birth": {3, 6}, "survival": {2, 3}},
    "Day & Night":   {"birth": {3, 6, 7, 8}, "survival": {3, 4, 6, 7, 8}},
    "Seeds":         {"birth": {2}, "survival": set()},
    "Life w/o Death":{"birth": {3}, "survival": {0, 1, 2, 3, 4, 5, 6, 7, 8}},
    "Diamoeba":      {"birth": {3, 5, 6, 7, 8}, "survival": {5, 6, 7, 8}},
    "2x2":           {"birth": {3, 6}, "survival": {1, 2, 5}},
    "Morley":        {"birth": {3, 6, 8}, "survival": {2, 4, 5}},
    "Anneal":        {"birth": {4, 6, 7, 8}, "survival": {3, 5, 6, 7, 8}},
}


def rule_string(birth: set, survival: set) -> str:
    """Format birth/survival sets as a rule string like 'B3/S23'."""
    b = "".join(str(n) for n in sorted(birth))
    s = "".join(str(n) for n in sorted(survival))
    return f"B{b}/S{s}"


def parse_rule_string(rs: str) -> tuple[set, set] | None:
    """Parse a rule string like 'B3/S23' into (birth, survival) sets.
    Returns None on invalid input."""
    rs = rs.strip().upper()
    if "/" not in rs:
        return None
    parts = rs.split("/", 1)
    if len(parts) != 2:
        return None
    b_part, s_part = parts
    if not b_part.startswith("B") or not s_part.startswith("S"):
        return None
    try:
        birth = {int(ch) for ch in b_part[1:]} if len(b_part) > 1 else set()
        survival = {int(ch) for ch in s_part[1:]} if len(s_part) > 1 else set()
    except ValueError:
        return None
    if not all(0 <= n <= 8 for n in birth | survival):
        return None
    return birth, survival


# ── RLE parser ──────────────────────────────────────────────────────────────


def parse_rle(text: str) -> dict:
    """Parse an RLE (Run Length Encoded) pattern string.

    Returns a dict with keys: 'name', 'comments', 'cells' (list of (r,c) tuples),
    'rule' (str or None), 'width', 'height'.
    """
    name = ""
    comments = []
    rule = None
    header_found = False
    pattern_data = ""

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            # Metadata comments
            if line.startswith("#N"):
                name = line[2:].strip()
            elif line.startswith("#C") or line.startswith("#c"):
                comments.append(line[2:].strip())
            elif line.startswith("#O"):
                comments.append(f"Author: {line[2:].strip()}")
            # #r, #P, etc. are ignored
            continue
        if not header_found:
            # Parse header line: x = M, y = N [, rule = ...]
            if line.startswith("x"):
                header_found = True
                # Extract x, y, and optional rule
                parts = {}
                for segment in line.split(","):
                    segment = segment.strip()
                    if "=" in segment:
                        k, v = segment.split("=", 1)
                        parts[k.strip().lower()] = v.strip()
                # Rule can appear in various forms
                if "rule" in parts:
                    rule_val = parts["rule"].strip()
                    # Convert common rule formats: e.g. "B3/S23", "23/3" (S/B), "b3/s23"
                    rule_val_upper = rule_val.upper()
                    if rule_val_upper.startswith("B"):
                        rule = rule_val_upper
                    elif "/" in rule_val:
                        # Legacy format: S/B (survival/birth)
                        s_part, b_part = rule_val.split("/", 1)
                        if s_part.isdigit() or s_part == "":
                            rule = f"B{b_part}/S{s_part}"
                continue
        # Pattern data lines (accumulate until '!')
        pattern_data += line
        if "!" in line:
            break

    # Strip everything after '!'
    if "!" in pattern_data:
        pattern_data = pattern_data[: pattern_data.index("!")]

    # Decode RLE pattern data
    cells = []
    row = 0
    col = 0
    i = 0
    while i < len(pattern_data):
        ch = pattern_data[i]
        if ch.isdigit():
            # Read full run count
            j = i
            while j < len(pattern_data) and pattern_data[j].isdigit():
                j += 1
            count = int(pattern_data[i:j])
            i = j
            if i >= len(pattern_data):
                break
            ch = pattern_data[i]
            i += 1
        else:
            count = 1
            i += 1

        if ch == "b" or ch == ".":
            col += count
        elif ch == "o" or ch == "A":
            for _ in range(count):
                cells.append((row, col))
                col += 1
        elif ch == "$":
            row += count
            col = 0

    # Compute bounding box
    if cells:
        max_r = max(r for r, c in cells)
        max_c = max(c for r, c in cells)
    else:
        max_r = max_c = 0

    return {
        "name": name,
        "comments": comments,
        "cells": cells,
        "rule": rule,
        "width": max_c + 1,
        "height": max_r + 1,
    }


# ── Preset patterns ──────────────────────────────────────────────────────────

PATTERNS = {
    "glider": {
        "description": "A small pattern that moves diagonally",
        "cells": [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)],
    },
    "blinker": {
        "description": "Period-2 oscillator",
        "cells": [(0, 0), (0, 1), (0, 2)],
    },
    "toad": {
        "description": "Period-2 oscillator",
        "cells": [(0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2)],
    },
    "beacon": {
        "description": "Period-2 oscillator",
        "cells": [(0, 0), (0, 1), (1, 0), (2, 3), (3, 2), (3, 3)],
    },
    "pulsar": {
        "description": "Period-3 oscillator",
        "cells": [
            # Top-left quadrant (and mirrors)
            (0, 2), (0, 3), (0, 4), (0, 8), (0, 9), (0, 10),
            (2, 0), (2, 5), (2, 7), (2, 12),
            (3, 0), (3, 5), (3, 7), (3, 12),
            (4, 0), (4, 5), (4, 7), (4, 12),
            (5, 2), (5, 3), (5, 4), (5, 8), (5, 9), (5, 10),
            (7, 2), (7, 3), (7, 4), (7, 8), (7, 9), (7, 10),
            (8, 0), (8, 5), (8, 7), (8, 12),
            (9, 0), (9, 5), (9, 7), (9, 12),
            (10, 0), (10, 5), (10, 7), (10, 12),
            (12, 2), (12, 3), (12, 4), (12, 8), (12, 9), (12, 10),
        ],
    },
    "pentadecathlon": {
        "description": "Period-15 oscillator",
        "cells": [
            (0, 1), (1, 1), (2, 0), (2, 2), (3, 1), (4, 1),
            (5, 1), (6, 1), (7, 0), (7, 2), (8, 1), (9, 1),
        ],
    },
    "lwss": {
        "description": "Lightweight spaceship — moves horizontally",
        "cells": [
            (0, 1), (0, 4), (1, 0), (2, 0), (2, 4), (3, 0),
            (3, 1), (3, 2), (3, 3),
        ],
    },
    "glider_gun": {
        "description": "Gosper glider gun — emits gliders forever",
        "cells": [
            (0, 24),
            (1, 22), (1, 24),
            (2, 12), (2, 13), (2, 20), (2, 21), (2, 34), (2, 35),
            (3, 11), (3, 15), (3, 20), (3, 21), (3, 34), (3, 35),
            (4, 0), (4, 1), (4, 10), (4, 16), (4, 20), (4, 21),
            (5, 0), (5, 1), (5, 10), (5, 14), (5, 16), (5, 17), (5, 22), (5, 24),
            (6, 10), (6, 16), (6, 24),
            (7, 11), (7, 15),
            (8, 12), (8, 13),
        ],
    },
    "r_pentomino": {
        "description": "R-pentomino — small but chaotic, stabilises after 1103 generations",
        "cells": [(0, 1), (0, 2), (1, 0), (1, 1), (2, 1)],
    },
    "diehard": {
        "description": "Diehard — vanishes after 130 generations",
        "cells": [
            (0, 6), (1, 0), (1, 1), (2, 1), (2, 5), (2, 6), (2, 7),
        ],
    },
    "acorn": {
        "description": "Acorn — takes 5206 generations to stabilise",
        "cells": [
            (0, 1), (1, 3), (2, 0), (2, 1), (2, 4), (2, 5), (2, 6),
        ],
    },
    "block": {
        "description": "Still life — 2×2 block",
        "cells": [(0, 0), (0, 1), (1, 0), (1, 1)],
    },
    "beehive": {
        "description": "Still life — beehive",
        "cells": [(0, 1), (0, 2), (1, 0), (1, 3), (2, 1), (2, 2)],
    },
}

# ── Color schemes ────────────────────────────────────────────────────────────

# Each scheme maps a cell's neighbour count (for alive cells) and age to a
# curses colour pair index.  We set up the pairs in _init_colors().

CELL_CHAR = "\u2588\u2588"  # Full block × 2 for squarish cells
DEAD_CHAR = "  "

# Age-based colour tiers (pair indices 1–5)
AGE_COLORS = [
    (curses.COLOR_GREEN, 1),   # newborn
    (curses.COLOR_CYAN, 2),    # young
    (curses.COLOR_YELLOW, 3),  # mature
    (curses.COLOR_MAGENTA, 4), # old
    (curses.COLOR_RED, 5),     # ancient
]


def _init_colors():
    curses.start_color()
    curses.use_default_colors()
    for fg, idx in AGE_COLORS:
        curses.init_pair(idx, fg, -1)
    # Pair 6: dim border / info text
    curses.init_pair(6, curses.COLOR_WHITE, -1)
    # Pair 7: highlight / title
    curses.init_pair(7, curses.COLOR_CYAN, -1)


def color_for_age(age: int) -> int:
    """Return a curses colour pair attribute based on cell age."""
    if age <= 1:
        return curses.color_pair(1)
    if age <= 3:
        return curses.color_pair(2)
    if age <= 8:
        return curses.color_pair(3)
    if age <= 20:
        return curses.color_pair(4)
    return curses.color_pair(5)


# ── Grid logic ───────────────────────────────────────────────────────────────

class Grid:
    """Finite grid with wrapping (toroidal) boundaries."""

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        # cells[r][c] = 0 means dead; >0 means alive (value = age in gens)
        self.cells = [[0] * cols for _ in range(rows)]
        self.generation = 0
        self.population = 0
        # Birth/survival rules (default: Conway's B3/S23)
        self.birth = {3}
        self.survival = {2, 3}

    def set_alive(self, r: int, c: int):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.cells[r][c] == 0:
                self.population += 1
            self.cells[r][c] = max(self.cells[r][c], 1)

    def set_dead(self, r: int, c: int):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.cells[r][c] > 0:
                self.population -= 1
            self.cells[r][c] = 0

    def toggle(self, r: int, c: int):
        if self.cells[r][c]:
            self.set_dead(r, c)
        else:
            self.set_alive(r, c)

    def clear(self):
        self.cells = [[0] * self.cols for _ in range(self.rows)]
        self.generation = 0
        self.population = 0

    def load_pattern(self, name: str, offset_r: int = 0, offset_c: int = 0):
        pattern = PATTERNS.get(name)
        if not pattern:
            return
        for r, c in pattern["cells"]:
            self.set_alive((r + offset_r) % self.rows, (c + offset_c) % self.cols)

    def _count_neighbours(self, r: int, c: int) -> int:
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr = (r + dr) % self.rows
                nc = (c + dc) % self.cols
                if self.cells[nr][nc]:
                    count += 1
        return count

    def to_dict(self) -> dict:
        """Serialize grid state to a dictionary."""
        alive_cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c] > 0:
                    alive_cells.append((r, c, self.cells[r][c]))
        return {
            "rows": self.rows,
            "cols": self.cols,
            "generation": self.generation,
            "cells": alive_cells,
            "rule": rule_string(self.birth, self.survival),
        }

    def load_dict(self, data: dict):
        """Restore grid state from a dictionary."""
        self.rows = data["rows"]
        self.cols = data["cols"]
        self.generation = data["generation"]
        self.cells = [[0] * self.cols for _ in range(self.rows)]
        self.population = 0
        for r, c, age in data["cells"]:
            if 0 <= r < self.rows and 0 <= c < self.cols:
                self.cells[r][c] = age
                self.population += 1
        # Restore rule if present in save data
        if "rule" in data:
            parsed = parse_rule_string(data["rule"])
            if parsed:
                self.birth, self.survival = parsed

    def state_hash(self) -> str:
        """Return a hash of the current alive-cell positions for cycle detection."""
        # Build a compact bytes representation of alive cell positions
        alive = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c] > 0:
                    alive.append(r * self.cols + c)
        data = b"".join(int.to_bytes(v, 4, "little") for v in alive)
        return hashlib.md5(data).hexdigest()

    def step(self):
        """Advance one generation."""
        new = [[0] * self.cols for _ in range(self.rows)]
        pop = 0
        for r in range(self.rows):
            for c in range(self.cols):
                n = self._count_neighbours(r, c)
                alive = self.cells[r][c] > 0
                if alive and n in self.survival:
                    new[r][c] = self.cells[r][c] + 1
                    pop += 1
                elif not alive and n in self.birth:
                    new[r][c] = 1
                    pop += 1
        self.cells = new
        self.generation += 1
        self.population = pop


# ── UI ───────────────────────────────────────────────────────────────────────

SPEEDS = [2.0, 1.0, 0.5, 0.25, 0.1, 0.05, 0.02, 0.01]
SPEED_LABELS = ["0.5×", "1×", "2×", "4×", "10×", "20×", "50×", "100×"]

SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[int], width: int) -> str:
    """Return a Unicode sparkline string for the given values, scaled to fit width."""
    if not values:
        return ""
    # Use the last `width` values
    vals = values[-width:]
    lo = min(vals)
    hi = max(vals)
    rng = hi - lo if hi > lo else 1
    result = []
    for v in vals:
        idx = int((v - lo) / rng * (len(SPARKLINE_CHARS) - 1))
        result.append(SPARKLINE_CHARS[idx])
    return "".join(result)


class App:
    def __init__(self, stdscr, pattern: str | None, grid_rows: int, grid_cols: int):
        self.stdscr = stdscr
        self.grid = Grid(grid_rows, grid_cols)
        self.running = False  # auto-play
        self.speed_idx = 2  # default 2× (0.5s)
        self.view_r = 0  # viewport top-left
        self.view_c = 0
        self.cursor_r = grid_rows // 2
        self.cursor_c = grid_cols // 2
        self.show_help = False
        self.message = ""
        self.message_time = 0.0
        self.pattern_menu = False
        self.stamp_menu = False  # stamp mode: overlay pattern at cursor
        self.pattern_list = sorted(PATTERNS.keys())
        self.pattern_sel = 0
        self.pop_history: list[int] = []
        # Cycle detection: map state_hash -> generation when first seen
        self.state_history: dict[str, int] = {}
        self.cycle_detected = False
        # Draw mode: None, "draw" (paint alive), or "erase" (paint dead)
        self.draw_mode: str | None = None
        # History buffer for rewind (stores (grid_dict, population) tuples)
        self.history: collections.deque[tuple[dict, int]] = collections.deque(maxlen=500)
        # Rule editor state
        self.rule_menu = False
        self.rule_preset_list = sorted(RULE_PRESETS.keys())
        self.rule_sel = 0
        # Comparison mode state
        self.compare_mode = False
        self.grid2: Grid | None = None  # second grid for comparison
        self.pop_history2: list[int] = []
        self.compare_rule_menu = False  # picking rule for grid2
        self.compare_rule_sel = 0

        if pattern:
            self._place_pattern(pattern)

    def _place_pattern(self, name: str):
        pat = PATTERNS.get(name)
        if not pat:
            self.message = f"Unknown pattern: {name}"
            self.message_time = time.monotonic()
            return
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = (self.grid.rows - max_r) // 2
        off_c = (self.grid.cols - max_c) // 2
        self.grid.load_pattern(name, off_r, off_c)
        self.cursor_r = off_r + max_r // 2
        self.cursor_c = off_c + max_c // 2
        self.message = f"Loaded: {name}"
        self.message_time = time.monotonic()

    def _stamp_pattern(self, name: str):
        """Overlay a pattern centered on the current cursor without clearing the grid."""
        pat = PATTERNS.get(name)
        if not pat:
            self._flash(f"Unknown pattern: {name}")
            return
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = self.cursor_r - max_r // 2
        off_c = self.cursor_c - max_c // 2
        self.grid.load_pattern(name, off_r, off_c)
        self._flash(f"Stamped: {name}")

    def _flash(self, msg: str):
        self.message = msg
        self.message_time = time.monotonic()

    def _record_pop(self):
        self.pop_history.append(self.grid.population)

    def _push_history(self):
        """Save the current grid state to the history buffer before advancing."""
        self.history.append((self.grid.to_dict(), len(self.pop_history)))

    def _rewind(self):
        """Restore the most recent state from the history buffer."""
        if not self.history:
            self._flash("No history to rewind")
            return
        grid_dict, pop_len = self.history.pop()
        self.grid.load_dict(grid_dict)
        # Trim population history back to match the restored state
        self.pop_history = self.pop_history[:pop_len]
        self._reset_cycle_detection()
        self._flash(f"Rewind → Gen {self.grid.generation}")

    def _reset_cycle_detection(self):
        """Reset cycle detection state (call when grid is modified externally)."""
        self.state_history.clear()
        self.cycle_detected = False

    def _check_cycle(self):
        """Check if the current grid state has been seen before. Auto-pauses on detection."""
        h = self.grid.state_hash()
        gen = self.grid.generation
        if h in self.state_history:
            period = gen - self.state_history[h]
            self.running = False
            self.cycle_detected = True
            if self.grid.population == 0:
                self._flash("Extinction detected — all cells dead")
            elif period == 1:
                self._flash("Still life detected")
            else:
                self._flash(f"Cycle detected (period {period})")
        else:
            self.state_history[h] = gen

    def run(self):
        _init_colors()
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(50)
        self._record_pop()
        # Seed initial state for cycle detection
        self.state_history[self.grid.state_hash()] = self.grid.generation

        while True:
            self._draw()
            key = self.stdscr.getch()

            if self.compare_rule_menu:
                if self._handle_compare_rule_menu_key(key):
                    continue
            elif self.rule_menu:
                if self._handle_rule_menu_key(key):
                    continue
            elif self.pattern_menu or self.stamp_menu:
                if self._handle_menu_key(key):
                    continue
            elif self.show_help:
                if key != -1:
                    self.show_help = False
                continue
            else:
                if self._handle_key(key):
                    continue

            if self.running:
                delay = SPEEDS[self.speed_idx]
                time.sleep(delay)
                self._push_history()
                self.grid.step()
                self._record_pop()
                self._check_cycle()
                # Step the second grid in comparison mode
                if self.compare_mode and self.grid2:
                    self.grid2.step()
                    self.pop_history2.append(self.grid2.population)

    # ── Key handling ──

    def _handle_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == ord("q"):
            sys.exit(0)
        if key == ord("?") or key == ord("h"):
            self.show_help = True
            return True
        if key == ord(" "):
            self.running = not self.running
            if self.running and self.cycle_detected:
                self._reset_cycle_detection()
            self._flash("Playing" if self.running else "Paused")
            return True
        if key == ord("n") or key == ord("."):
            self.running = False
            self._push_history()
            self.grid.step()
            self._record_pop()
            self._check_cycle()
            if self.compare_mode and self.grid2:
                self.grid2.step()
                self.pop_history2.append(self.grid2.population)
            return True
        if key == ord("u"):
            self.running = False
            self._rewind()
            return True
        if key == ord("+") or key == ord("="):
            if self.speed_idx < len(SPEEDS) - 1:
                self.speed_idx += 1
            self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
            return True
        if key == ord("-") or key == ord("_"):
            if self.speed_idx > 0:
                self.speed_idx -= 1
            self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
            return True
        if key == ord("c"):
            self.grid.clear()
            self.running = False
            self.pop_history.clear()
            self._record_pop()
            self._reset_cycle_detection()
            self._flash("Cleared")
            return True
        if key == ord("r"):
            self.grid.clear()
            self.running = False
            import random
            for r in range(self.grid.rows):
                for c in range(self.grid.cols):
                    if random.random() < 0.2:
                        self.grid.set_alive(r, c)
            self.pop_history.clear()
            self._record_pop()
            self._reset_cycle_detection()
            self._flash("Randomised")
            return True
        if key == ord("R"):
            self.rule_menu = True
            return True
        if key == ord("p"):
            self.pattern_menu = True
            return True
        if key == ord("t"):
            self.stamp_menu = True
            return True
        if key == ord("s"):
            self._save_state()
            return True
        if key == ord("o"):
            self._load_state()
            return True
        if key == ord("i"):
            self._import_rle()
            return True
        if key == ord("V"):
            if self.compare_mode:
                self._exit_compare_mode()
            else:
                self._enter_compare_mode()
            return True
        if key == ord("e"):
            self.grid.toggle(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()
            return True
        if key == ord("d"):
            if self.draw_mode == "draw":
                self.draw_mode = None
                self._flash("Draw mode OFF")
            else:
                self.draw_mode = "draw"
                self.grid.set_alive(self.cursor_r, self.cursor_c)
                self._reset_cycle_detection()
                self._flash("Draw mode ON (move to paint, d/Esc=exit)")
            return True
        if key == ord("x"):
            if self.draw_mode == "erase":
                self.draw_mode = None
                self._flash("Erase mode OFF")
            else:
                self.draw_mode = "erase"
                self.grid.set_dead(self.cursor_r, self.cursor_c)
                self._reset_cycle_detection()
                self._flash("Erase mode ON (move to erase, x/Esc=exit)")
            return True
        if key == 27:  # ESC
            if self.draw_mode:
                self.draw_mode = None
                self._flash("Draw/erase mode OFF")
            return True
        # Arrow keys / vim keys for cursor movement
        if key in (curses.KEY_UP, ord("k")):
            self.cursor_r = (self.cursor_r - 1) % self.grid.rows
            self._apply_draw_mode()
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.cursor_r = (self.cursor_r + 1) % self.grid.rows
            self._apply_draw_mode()
            return True
        if key in (curses.KEY_LEFT, ord("l") - 4):  # 'h' already used for help
            self.cursor_c = (self.cursor_c - 1) % self.grid.cols
            self._apply_draw_mode()
            return True
        if key in (curses.KEY_RIGHT, ord("l")):
            self.cursor_c = (self.cursor_c + 1) % self.grid.cols
            self._apply_draw_mode()
            return True
        return True

    def _apply_draw_mode(self):
        """If in draw/erase mode, paint or erase the cell under the cursor."""
        if self.draw_mode == "draw":
            self.grid.set_alive(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()
        elif self.draw_mode == "erase":
            self.grid.set_dead(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()

    def _handle_menu_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q
            self.pattern_menu = False
            self.stamp_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.pattern_sel = (self.pattern_sel - 1) % len(self.pattern_list)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.pattern_sel = (self.pattern_sel + 1) % len(self.pattern_list)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter
            name = self.pattern_list[self.pattern_sel]
            if self.stamp_menu:
                self._stamp_pattern(name)
                self.stamp_menu = False
                self.running = False
                self._reset_cycle_detection()
            else:
                self.grid.clear()
                self._place_pattern(name)
                self.pattern_menu = False
                self.running = False
                self.pop_history.clear()
                self._record_pop()
                self._reset_cycle_detection()
            return True
        return True

    # ── Rule editor ──

    def _handle_rule_menu_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q
            self.rule_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.rule_sel = (self.rule_sel - 1) % len(self.rule_preset_list)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.rule_sel = (self.rule_sel + 1) % len(self.rule_preset_list)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — apply preset
            name = self.rule_preset_list[self.rule_sel]
            preset = RULE_PRESETS[name]
            self.grid.birth = set(preset["birth"])
            self.grid.survival = set(preset["survival"])
            self.rule_menu = False
            self._reset_cycle_detection()
            self._flash(f"Rule: {name} ({rule_string(self.grid.birth, self.grid.survival)})")
            return True
        if key == ord("/"):  # Custom rule entry
            self.rule_menu = False
            rs = self._prompt_text("Rule (e.g. B3/S23)")
            if rs:
                parsed = parse_rule_string(rs)
                if parsed:
                    self.grid.birth, self.grid.survival = parsed
                    self._reset_cycle_detection()
                    self._flash(f"Rule set: {rule_string(self.grid.birth, self.grid.survival)}")
                else:
                    self._flash("Invalid rule string (use format B.../S...)")
            return True
        return True

    def _draw_rule_menu(self, max_y: int, max_x: int):
        title = "── Rule Editor (Enter=apply, /=custom, q/Esc=cancel) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        current = rule_string(self.grid.birth, self.grid.survival)
        current_line = f"Current rule: {current}"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(current_line)) // 2), current_line,
                               curses.color_pair(6))
        except curses.error:
            pass
        for i, name in enumerate(self.rule_preset_list):
            y = 5 + i
            if y >= max_y - 1:
                break
            preset = RULE_PRESETS[name]
            rs = rule_string(preset["birth"], preset["survival"])
            line = f"  {name:<20s} {rs}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.rule_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass
        tip_y = 5 + len(self.rule_preset_list) + 1
        if tip_y < max_y - 1:
            tip = "Press / to type a custom rule string (e.g. B36/S23)"
            try:
                self.stdscr.addstr(tip_y, max(0, (max_x - len(tip)) // 2), tip,
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Comparison mode ──

    def _enter_compare_mode(self):
        """Open the rule picker for the second grid to start comparison mode."""
        self.compare_rule_menu = True
        self.compare_rule_sel = 0

    def _exit_compare_mode(self):
        """Leave comparison mode and discard the second grid."""
        self.compare_mode = False
        self.grid2 = None
        self.pop_history2.clear()
        self.compare_rule_menu = False
        self._flash("Comparison mode OFF")

    def _start_compare(self, birth2: set, survival2: set):
        """Clone the current grid into a second grid with different rules and start comparison."""
        self.grid2 = Grid(self.grid.rows, self.grid.cols)
        # Copy cell state from the primary grid
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                self.grid2.cells[r][c] = self.grid.cells[r][c]
        self.grid2.generation = self.grid.generation
        self.grid2.population = self.grid.population
        # Apply the chosen rule to the second grid
        self.grid2.birth = birth2
        self.grid2.survival = survival2
        self.pop_history2 = list(self.pop_history)
        self.compare_mode = True
        self.compare_rule_menu = False
        r1 = rule_string(self.grid.birth, self.grid.survival)
        r2 = rule_string(birth2, survival2)
        self._flash(f"Comparing: {r1} vs {r2}  (V to exit)")

    def _handle_compare_rule_menu_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q
            self.compare_rule_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.compare_rule_sel = (self.compare_rule_sel - 1) % len(self.rule_preset_list)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.compare_rule_sel = (self.compare_rule_sel + 1) % len(self.rule_preset_list)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — apply preset
            name = self.rule_preset_list[self.compare_rule_sel]
            preset = RULE_PRESETS[name]
            self._start_compare(set(preset["birth"]), set(preset["survival"]))
            return True
        if key == ord("/"):  # Custom rule entry
            self.compare_rule_menu = False
            rs = self._prompt_text("Second rule (e.g. B36/S23)")
            if rs:
                parsed = parse_rule_string(rs)
                if parsed:
                    self._start_compare(parsed[0], parsed[1])
                else:
                    self._flash("Invalid rule string (use format B.../S...)")
            return True
        return True

    def _draw_compare_rule_menu(self, max_y: int, max_x: int):
        title = "── Pick Second Rule for Comparison (Enter=select, /=custom, q/Esc=cancel) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        current = rule_string(self.grid.birth, self.grid.survival)
        current_line = f"Left panel rule: {current}  —  Select rule for right panel:"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(current_line)) // 2), current_line,
                               curses.color_pair(6))
        except curses.error:
            pass
        for i, name in enumerate(self.rule_preset_list):
            y = 5 + i
            if y >= max_y - 1:
                break
            preset = RULE_PRESETS[name]
            rs = rule_string(preset["birth"], preset["survival"])
            line = f"  {name:<20s} {rs}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.compare_rule_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass
        tip_y = 5 + len(self.rule_preset_list) + 1
        if tip_y < max_y - 1:
            tip = "Press / to type a custom rule string (e.g. B36/S23)"
            try:
                self.stdscr.addstr(tip_y, max(0, (max_x - len(tip)) // 2), tip,
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Save / Load ──

    def _prompt_text(self, prompt: str) -> str | None:
        """Show a text prompt on the bottom line and return user input, or None on ESC."""
        self.stdscr.nodelay(False)
        max_y, max_x = self.stdscr.getmaxyx()
        y = max_y - 1
        buf = ""
        while True:
            try:
                self.stdscr.move(y, 0)
                self.stdscr.clrtoeol()
                display = f" {prompt}: {buf}"
                self.stdscr.addstr(y, 0, display[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch == 27:  # ESC
                self.stdscr.nodelay(True)
                return None
            if ch in (10, 13, curses.KEY_ENTER):
                self.stdscr.nodelay(True)
                return buf.strip()
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                buf = buf[:-1]
            elif 32 <= ch < 127:
                buf += chr(ch)
        self.stdscr.nodelay(True)
        return None

    def _save_state(self):
        name = self._prompt_text("Save name (enter to cancel)")
        if not name:
            self._flash("Save cancelled")
            return
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        if not safe_name:
            self._flash("Invalid name")
            return
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = os.path.join(SAVE_DIR, safe_name + ".json")
        data = self.grid.to_dict()
        data["name"] = name
        with open(path, "w") as f:
            json.dump(data, f)
        self._flash(f"Saved: {safe_name}.json")

    def _load_state(self):
        if not os.path.isdir(SAVE_DIR):
            self._flash("No saves found")
            return
        saves = sorted(f for f in os.listdir(SAVE_DIR) if f.endswith(".json"))
        if not saves:
            self._flash("No saves found")
            return
        # Show a selection menu
        self._save_menu = True
        self._save_list = saves
        self._save_sel = 0
        self._show_save_menu()

    def _show_save_menu(self):
        """Run a blocking menu to select a save file."""
        self.stdscr.nodelay(False)
        while True:
            self.stdscr.erase()
            max_y, max_x = self.stdscr.getmaxyx()
            title = "── Load Save (Enter=load, q/Esc=cancel) ──"
            try:
                self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass
            for i, fname in enumerate(self._save_list):
                y = 3 + i
                if y >= max_y - 1:
                    break
                label = fname.removesuffix(".json")
                line = f"  {label}"[:max_x - 2]
                attr = curses.color_pair(6)
                if i == self._save_sel:
                    attr = curses.color_pair(7) | curses.A_REVERSE
                try:
                    self.stdscr.addstr(y, 2, line, attr)
                except curses.error:
                    pass
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key == 27 or key == ord("q"):
                break
            if key in (curses.KEY_UP, ord("k")):
                self._save_sel = (self._save_sel - 1) % len(self._save_list)
            elif key in (curses.KEY_DOWN, ord("j")):
                self._save_sel = (self._save_sel + 1) % len(self._save_list)
            elif key in (10, 13, curses.KEY_ENTER):
                path = os.path.join(SAVE_DIR, self._save_list[self._save_sel])
                try:
                    with open(path) as f:
                        data = json.load(f)
                    self.grid.load_dict(data)
                    self.running = False
                    self.pop_history.clear()
                    self._record_pop()
                    self._reset_cycle_detection()
                    self._flash(f"Loaded: {self._save_list[self._save_sel].removesuffix('.json')}")
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    self._flash(f"Error loading save: {e}")
                break
        self.stdscr.nodelay(True)

    # ── RLE Import ──

    def _import_rle(self):
        """Prompt for an RLE file path and load the pattern."""
        path = self._prompt_text("RLE file path")
        if not path:
            self._flash("Import cancelled")
            return
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            self._flash(f"File not found: {path}")
            return
        try:
            with open(path, "r", errors="replace") as f:
                text = f.read()
        except OSError as e:
            self._flash(f"Error reading file: {e}")
            return
        rle = parse_rle(text)
        if not rle["cells"]:
            self._flash("No cells found in RLE file")
            return
        # Apply rule from RLE if present
        if rle["rule"]:
            parsed = parse_rule_string(rle["rule"])
            if parsed:
                self.grid.birth, self.grid.survival = parsed
        # Clear grid and place pattern centered
        self.grid.clear()
        off_r = (self.grid.rows - rle["height"]) // 2
        off_c = (self.grid.cols - rle["width"]) // 2
        for r, c in rle["cells"]:
            gr = (r + off_r) % self.grid.rows
            gc = (c + off_c) % self.grid.cols
            self.grid.set_alive(gr, gc)
        # Center cursor on the pattern
        self.cursor_r = (off_r + rle["height"] // 2) % self.grid.rows
        self.cursor_c = (off_c + rle["width"] // 2) % self.grid.cols
        self.running = False
        self.pop_history.clear()
        self._record_pop()
        self._reset_cycle_detection()
        label = rle["name"] or os.path.basename(path)
        self._flash(f"Imported: {label} ({rle['width']}×{rle['height']}, {len(rle['cells'])} cells)")

    # ── Drawing ──

    def _draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()

        if self.show_help:
            self._draw_help(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.compare_rule_menu:
            self._draw_compare_rule_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rule_menu:
            self._draw_rule_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.pattern_menu or self.stamp_menu:
            self._draw_pattern_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.compare_mode and self.grid2:
            self._draw_compare(max_y, max_x)
            self.stdscr.refresh()
            return

        # Compute viewport
        # Each cell takes 2 columns on screen
        vis_rows = max_y - 4  # leave room for status bar + sparkline
        vis_cols = (max_x - 1) // 2

        # Centre viewport on cursor
        self.view_r = self.cursor_r - vis_rows // 2
        self.view_c = self.cursor_c - vis_cols // 2

        for sy in range(min(vis_rows, self.grid.rows)):
            gr = (self.view_r + sy) % self.grid.rows
            for sx in range(min(vis_cols, self.grid.cols)):
                gc = (self.view_c + sx) % self.grid.cols
                age = self.grid.cells[gr][gc]
                is_cursor = (gr == self.cursor_r and gc == self.cursor_c)
                px = sx * 2
                py = sy
                if py >= max_y - 2 or px + 1 >= max_x:
                    continue
                if age > 0:
                    attr = color_for_age(age)
                    if is_cursor:
                        attr |= curses.A_REVERSE
                    try:
                        self.stdscr.addstr(py, px, CELL_CHAR, attr)
                    except curses.error:
                        pass
                else:
                    if is_cursor:
                        try:
                            self.stdscr.addstr(py, px, "▒▒", curses.color_pair(6) | curses.A_DIM)
                        except curses.error:
                            pass

        # Population sparkline
        spark_y = max_y - 3
        if spark_y > 0 and len(self.pop_history) > 1:
            spark_width = max_x - 16  # reserve space for label
            if spark_width > 0:
                spark_str = sparkline(self.pop_history, spark_width)
                label = " Pop history: "
                try:
                    self.stdscr.addstr(spark_y, 0, label, curses.color_pair(6) | curses.A_DIM)
                    self.stdscr.addstr(spark_y, len(label), spark_str, curses.color_pair(1))
                except curses.error:
                    pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            state = "▶ PLAY" if self.running else "⏸ PAUSE"
            speed = SPEED_LABELS[self.speed_idx]
            mode = ""
            if self.draw_mode == "draw":
                mode = "  │  ✏ DRAW"
            elif self.draw_mode == "erase":
                mode = "  │  ✘ ERASE"
            rs = rule_string(self.grid.birth, self.grid.survival)
            status = (
                f" Gen: {self.grid.generation}  │  "
                f"Pop: {self.grid.population}  │  "
                f"{state}  │  Speed: {speed}  │  "
                f"Rule: {rs}  │  "
                f"Cursor: ({self.cursor_r},{self.cursor_c}){mode}"
            )
            status = status[:max_x - 1]
            try:
                self.stdscr.addstr(status_y, 0, status, curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Message / hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            else:
                hint = " [Space]=play/pause [n]=step [u]=rewind [p]=patterns [t]=stamp [i]=import [e]=edit [d]=draw [x]=erase [R]=rules [V]=compare [s]=save [o]=load [+/-]=speed [r]=random [c]=clear [?]=help [q]=quit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

        self.stdscr.refresh()

    def _draw_compare(self, max_y: int, max_x: int):
        """Draw split-screen comparison of two grids side by side."""
        # Layout: [left grid] [divider col] [right grid]
        # Each cell = 2 screen columns, divider = 1 column
        half_x = max_x // 2
        divider_x = half_x  # column for the vertical divider
        vis_rows = max_y - 4  # leave room for status + sparkline

        # Each panel's cell columns
        left_cell_cols = (divider_x) // 2
        right_cell_cols = (max_x - divider_x - 1) // 2

        # Centre viewport on cursor for both panels
        self.view_r = self.cursor_r - vis_rows // 2
        self.view_c = self.cursor_c - left_cell_cols // 2

        # Draw left panel (grid 1)
        for sy in range(min(vis_rows, self.grid.rows)):
            gr = (self.view_r + sy) % self.grid.rows
            for sx in range(min(left_cell_cols, self.grid.cols)):
                gc = (self.view_c + sx) % self.grid.cols
                age = self.grid.cells[gr][gc]
                px = sx * 2
                py = sy
                if py >= max_y - 3 or px + 1 >= divider_x:
                    continue
                if age > 0:
                    try:
                        self.stdscr.addstr(py, px, CELL_CHAR, color_for_age(age))
                    except curses.error:
                        pass

        # Draw vertical divider
        for sy in range(min(vis_rows, max_y - 3)):
            try:
                self.stdscr.addstr(sy, divider_x, "│", curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

        # Draw right panel (grid 2)
        right_start = divider_x + 1
        for sy in range(min(vis_rows, self.grid2.rows)):
            gr = (self.view_r + sy) % self.grid2.rows
            for sx in range(min(right_cell_cols, self.grid2.cols)):
                gc = (self.view_c + sx) % self.grid2.cols
                age = self.grid2.cells[gr][gc]
                px = right_start + sx * 2
                py = sy
                if py >= max_y - 3 or px + 1 >= max_x:
                    continue
                if age > 0:
                    try:
                        self.stdscr.addstr(py, px, CELL_CHAR, color_for_age(age))
                    except curses.error:
                        pass

        # Panel labels
        r1 = rule_string(self.grid.birth, self.grid.survival)
        r2 = rule_string(self.grid2.birth, self.grid2.survival)
        label_y = max_y - 4
        if label_y > 0:
            l1 = f" {r1}  Pop: {self.grid.population}"
            l2 = f" {r2}  Pop: {self.grid2.population}"
            try:
                self.stdscr.addstr(label_y, 0, l1[:divider_x], curses.color_pair(7) | curses.A_BOLD)
                self.stdscr.addstr(label_y, right_start, l2[:max_x - right_start - 1],
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Dual sparklines
        spark_y = max_y - 3
        if spark_y > 0:
            spark_w = divider_x - 2
            if spark_w > 0 and len(self.pop_history) > 1:
                try:
                    s1 = sparkline(self.pop_history, spark_w)
                    self.stdscr.addstr(spark_y, 0, " " + s1, curses.color_pair(1))
                except curses.error:
                    pass
            spark_w2 = max_x - right_start - 1
            if spark_w2 > 0 and len(self.pop_history2) > 1:
                try:
                    s2 = sparkline(self.pop_history2, spark_w2)
                    self.stdscr.addstr(spark_y, right_start, " " + s2, curses.color_pair(1))
                except curses.error:
                    pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            state = "▶ PLAY" if self.running else "⏸ PAUSE"
            speed = SPEED_LABELS[self.speed_idx]
            status = (
                f" Gen: {self.grid.generation}  │  "
                f"{state}  │  Speed: {speed}  │  "
                f"COMPARE: {r1} vs {r2}"
            )
            status = status[:max_x - 1]
            try:
                self.stdscr.addstr(status_y, 0, status, curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            else:
                hint = " [Space]=play/pause [n]=step [+/-]=speed [V]=exit compare [Arrows]=scroll [q]=quit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_help(self, max_y: int, max_x: int):
        help_lines = [
            "╔══════════════════════════════════════════╗",
            "║       Game of Life — Help                ║",
            "╠══════════════════════════════════════════╣",
            "║                                          ║",
            "║  Space     Play / Pause auto-advance     ║",
            "║  n / .     Step one generation            ║",
            "║  u         Rewind one generation          ║",
            "║  + / -     Increase / decrease speed      ║",
            "║  Arrows    Move cursor (also vim hjkl)    ║",
            "║  e         Toggle cell under cursor       ║",
            "║  d         Draw mode (paint while moving) ║",
            "║  x         Erase mode (erase while moving)║",
            "║  Esc       Exit draw/erase mode           ║",
            "║  p         Open pattern selector          ║",
            "║  t         Stamp pattern at cursor        ║",
            "║  R         Rule editor (B../S.. presets)  ║",
            "║  V         Compare two rules side-by-side  ║",
            "║  i         Import RLE pattern file         ║",
            "║  r         Fill grid randomly             ║",
            "║  s         Save grid state to file        ║",
            "║  o         Open/load a saved state        ║",
            "║  c         Clear grid                     ║",
            "║  q         Quit                           ║",
            "║  ? / h     Show this help                 ║",
            "║                                          ║",
            "║  Press any key to close help              ║",
            "╚══════════════════════════════════════════╝",
        ]
        start_y = max(0, (max_y - len(help_lines)) // 2)
        for i, line in enumerate(help_lines):
            y = start_y + i
            if y >= max_y:
                break
            x = max(0, (max_x - len(line)) // 2)
            try:
                self.stdscr.addstr(y, x, line, curses.color_pair(7))
            except curses.error:
                pass

    def _draw_pattern_menu(self, max_y: int, max_x: int):
        if self.stamp_menu:
            title = "── Stamp Pattern at Cursor (Enter=stamp, q/Esc=cancel) ──"
        else:
            title = "── Select Pattern (Enter=load, q/Esc=cancel) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        for i, name in enumerate(self.pattern_list):
            y = 3 + i
            if y >= max_y - 1:
                break
            desc = PATTERNS[name]["description"]
            line = f"  {name:<20s} {desc}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.pattern_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Conway's Game of Life — terminal edition")
    parser.add_argument(
        "-p", "--pattern",
        choices=sorted(PATTERNS.keys()),
        help="Start with a preset pattern",
    )
    parser.add_argument(
        "--rows", type=int, default=80,
        help="Grid height (default: 80)",
    )
    parser.add_argument(
        "--cols", type=int, default=120,
        help="Grid width (default: 120)",
    )
    parser.add_argument(
        "--list-patterns", action="store_true",
        help="List available patterns and exit",
    )
    args = parser.parse_args()

    if args.list_patterns:
        print("Available patterns:")
        for name in sorted(PATTERNS.keys()):
            print(f"  {name:<20s} {PATTERNS[name]['description']}")
        sys.exit(0)

    def start(stdscr):
        app = App(stdscr, args.pattern, args.rows, args.cols)
        app.run()

    try:
        curses.wrapper(start)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
