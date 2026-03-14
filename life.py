#!/usr/bin/env python3
"""Terminal-based Conway's Game of Life simulator."""

import argparse
import collections
import copy
import curses
import hashlib
import json
import math
import os
import queue
import random
import select
import socket
import struct
import sys
import tempfile
import threading
import time
import wave

SAVE_DIR = os.path.expanduser("~/.life_saves")
BLUEPRINT_FILE = os.path.join(SAVE_DIR, "blueprints.json")


def _load_blueprints() -> dict:
    """Load user-saved blueprint patterns from disk."""
    if not os.path.isfile(BLUEPRINT_FILE):
        return {}
    try:
        with open(BLUEPRINT_FILE, "r") as f:
            data = json.load(f)
        blueprints = {}
        for name, entry in data.items():
            blueprints[name] = {
                "description": entry.get("description", "Custom blueprint"),
                "cells": [tuple(c) for c in entry["cells"]],
            }
        return blueprints
    except (json.JSONDecodeError, KeyError, TypeError, OSError):
        return {}


def _save_blueprints(blueprints: dict):
    """Save user blueprint patterns to disk."""
    os.makedirs(SAVE_DIR, exist_ok=True)
    data = {}
    for name, entry in blueprints.items():
        data[name] = {
            "description": entry["description"],
            "cells": list(entry["cells"]),
        }
    with open(BLUEPRINT_FILE, "w") as f:
        json.dump(data, f)


# ── Pattern recognition library ─────────────────────────────────────────────

# Canonical patterns stored as frozensets of (row, col) tuples, normalised to
# top-left origin.  For each pattern we pre-compute all distinct orientations
# (rotations × reflections, up to 8) so recognition is orientation-agnostic.


def _normalise(cells):
    """Shift a set of (r,c) tuples so the minimum row and column are 0."""
    if not cells:
        return frozenset()
    min_r = min(r for r, c in cells)
    min_c = min(c for r, c in cells)
    return frozenset((r - min_r, c - min_c) for r, c in cells)


def _orientations(cells):
    """Return all distinct orientations (rotations + reflections) of a pattern."""
    fs = _normalise(cells)
    seen = set()
    results = []
    cur = set(fs)
    for _ in range(4):
        for reflect in (False, True):
            if reflect:
                oriented = frozenset((-r, c) for r, c in cur)
            else:
                oriented = frozenset(cur)
            normed = _normalise(oriented)
            if normed not in seen:
                seen.add(normed)
                results.append(normed)
        # Rotate 90° clockwise: (r, c) -> (c, -r)
        cur = {(c, -r) for r, c in cur}
    return results


def _build_recognition_db():
    """Build the pattern recognition database from PATTERNS.

    Returns a list of (name, category, width, height, orientations) tuples.
    Only includes small/medium patterns suitable for real-time scanning
    (skips patterns larger than 15 cells).
    """
    # Categories for display
    categories = {
        "block": "Still life",
        "beehive": "Still life",
        "blinker": "Oscillator",
        "toad": "Oscillator",
        "beacon": "Oscillator",
        "glider": "Spaceship",
        "lwss": "Spaceship",
    }
    # Additional well-known small patterns not in the PATTERNS dict
    extra_patterns = {
        "loaf": {
            "cells": [(0, 1), (0, 2), (1, 0), (1, 3), (2, 1), (2, 3), (3, 2)],
            "category": "Still life",
        },
        "boat": {
            "cells": [(0, 0), (0, 1), (1, 0), (1, 2), (2, 1)],
            "category": "Still life",
        },
        "tub": {
            "cells": [(0, 1), (1, 0), (1, 2), (2, 1)],
            "category": "Still life",
        },
        "ship": {
            "cells": [(0, 0), (0, 1), (1, 0), (1, 2), (2, 1), (2, 2)],
            "category": "Still life",
        },
        "pond": {
            "cells": [(0, 1), (0, 2), (1, 0), (1, 3), (2, 0), (2, 3), (3, 1), (3, 2)],
            "category": "Still life",
        },
    }

    db = []
    for name, pdata in PATTERNS.items():
        cells = pdata["cells"]
        if len(cells) > 15:
            continue
        cat = categories.get(name, "Pattern")
        orients = _orientations(cells)
        h = max(r for r, c in cells) + 1
        w = max(c for r, c in cells) + 1
        db.append((name, cat, w, h, orients))
    for name, info in extra_patterns.items():
        cells = info["cells"]
        cat = info["category"]
        orients = _orientations(cells)
        h = max(r for r, c in cells) + 1
        w = max(c for r, c in cells) + 1
        db.append((name, cat, w, h, orients))
    return db


# Deferred init: built once on first use (after PATTERNS is defined)
_RECOGNITION_DB = None


def _get_recognition_db():
    global _RECOGNITION_DB
    if _RECOGNITION_DB is None:
        _RECOGNITION_DB = _build_recognition_db()
    return _RECOGNITION_DB


def scan_patterns(grid):
    """Scan the grid and return a list of detected patterns.

    Each result is a dict: {name, category, r, c, w, h, cells}
    where (r, c) is the top-left corner and cells is the set of (gr, gc)
    absolute grid positions belonging to the match.
    """
    db = _get_recognition_db()
    rows, cols = grid.rows, grid.cols

    # Build a set of all alive positions for fast lookup
    alive = set()
    for r in range(rows):
        for c in range(cols):
            if grid.cells[r][c] > 0:
                alive.add((r, c))

    if not alive:
        return []

    # For each alive cell, try to match each pattern orientation starting at that cell
    # as the top-left corner of the pattern's bounding box.
    found = []
    claimed = set()  # cells already claimed by a detected pattern

    # Sort DB so larger patterns match first (avoids sub-pattern conflicts)
    sorted_db = sorted(db, key=lambda x: max(len(o) for o in x[4]), reverse=True)

    for name, cat, pw, ph, orients in sorted_db:
        for orient in orients:
            oh = max(r for r, c in orient) + 1
            ow = max(c for r, c in orient) + 1
            for ar, ac in alive:
                if (ar, ac) in claimed:
                    continue
                # Check if (ar, ac) could be part of this orientation
                # Try it as the min-row, min-col anchor
                match_cells = set()
                ok = True
                for pr, pc in orient:
                    gr = (ar + pr) % rows
                    gc = (ac + pc) % cols
                    if (gr, gc) not in alive:
                        ok = False
                        break
                    match_cells.add((gr, gc))
                if not ok:
                    continue
                # Verify no extra alive cells in the bounding box
                # (otherwise we'd match subsets of larger structures)
                extra = False
                for dr in range(oh):
                    for dc in range(ow):
                        gr = (ar + dr) % rows
                        gc = (ac + dc) % cols
                        if (gr, gc) in alive and (gr, gc) not in match_cells:
                            extra = True
                            break
                    if extra:
                        break
                if extra:
                    continue
                # Check that none of these cells are already claimed
                if match_cells & claimed:
                    continue
                claimed |= match_cells
                found.append({
                    "name": name,
                    "category": cat,
                    "r": ar,
                    "c": ac,
                    "w": ow,
                    "h": oh,
                    "cells": match_cells,
                })

    return found


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

# ── Puzzle / Challenge definitions ────────────────────────────────────────────

PUZZLES = [
    {
        "id": 1,
        "name": "First Still Life",
        "description": "Place exactly 4 cells that form a still life (stable pattern).",
        "type": "still_life",
        "max_cells": 4,
        "sim_gens": 50,
        "goal_text": "Achieve a still life after 50 generations",
        "hint": "A 2x2 block is the simplest still life.",
    },
    {
        "id": 2,
        "name": "Blinker Builder",
        "description": "Create an oscillator with period >= 2 using at most 5 cells.",
        "type": "oscillator",
        "min_period": 2,
        "max_cells": 5,
        "sim_gens": 60,
        "goal_text": "Build an oscillator (period >= 2) using <= 5 cells",
        "hint": "Three cells in a row will oscillate.",
    },
    {
        "id": 3,
        "name": "Population Boom",
        "description": "Place at most 5 cells that grow to population 20+ within 100 generations.",
        "type": "reach_population",
        "target_pop": 20,
        "max_cells": 5,
        "sim_gens": 100,
        "goal_text": "Reach population 20+ within 100 gens (max 5 cells)",
        "hint": "The R-pentomino is famous for explosive growth from just 5 cells.",
    },
    {
        "id": 4,
        "name": "Spaceship Launch",
        "description": "Build a pattern that escapes a 10x10 bounding box within 30 generations.",
        "type": "escape_box",
        "box_size": 10,
        "max_cells": 6,
        "sim_gens": 30,
        "goal_text": "Create a spaceship that escapes a 10x10 box (max 6 cells)",
        "hint": "A glider moves diagonally, escaping any bounded region.",
    },
    {
        "id": 5,
        "name": "Extinction Event",
        "description": "Place at most 7 cells that all die out within 150 generations.",
        "type": "extinction",
        "max_cells": 7,
        "sim_gens": 150,
        "goal_text": "All cells must die within 150 generations (max 7 cells)",
        "hint": "The 'diehard' pattern vanishes after 130 generations from 7 cells.",
    },
    {
        "id": 6,
        "name": "Higher Period",
        "description": "Create an oscillator with period >= 3 using at most 20 cells.",
        "type": "oscillator",
        "min_period": 3,
        "max_cells": 20,
        "sim_gens": 100,
        "goal_text": "Build an oscillator with period >= 3 (max 20 cells)",
        "hint": "The pulsar is a period-3 oscillator.",
    },
    {
        "id": 7,
        "name": "Population Explosion",
        "description": "Reach population 100+ within 200 generations from at most 10 cells.",
        "type": "reach_population",
        "target_pop": 100,
        "max_cells": 10,
        "sim_gens": 200,
        "goal_text": "Reach population 100+ within 200 gens (max 10 cells)",
        "hint": "Try configurations that produce gliders or other expanding structures.",
    },
    {
        "id": 8,
        "name": "Efficient Still Life",
        "description": "Create a still life with exactly 6 cells.",
        "type": "still_life",
        "max_cells": 6,
        "sim_gens": 50,
        "goal_text": "Build a 6-cell still life",
        "hint": "A beehive has 6 cells and is perfectly stable.",
    },
    {
        "id": 9,
        "name": "Speed Run",
        "description": "Reach population 50+ in the fewest generations from at most 8 cells.",
        "type": "reach_population",
        "target_pop": 50,
        "max_cells": 8,
        "sim_gens": 300,
        "goal_text": "Reach population 50+ within 300 gens (max 8 cells, fewer gens = better)",
        "hint": "Methuselahs like the acorn grow slowly but surely.",
    },
    {
        "id": 10,
        "name": "Grand Challenge",
        "description": "Place at most 6 cells that survive 500+ generations without going extinct or reaching a still life.",
        "type": "survive_gens",
        "target_gens": 500,
        "max_cells": 6,
        "sim_gens": 600,
        "goal_text": "Pattern must stay active (not still/extinct) for 500+ gens (max 6 cells)",
        "hint": "The R-pentomino stays active for over 1000 generations from 5 cells.",
    },
]


# ── Color schemes ────────────────────────────────────────────────────────────

# Each scheme maps a cell's neighbour count (for alive cells) and age to a
# curses colour pair index.  We set up the pairs in _init_colors().

CELL_CHAR = "\u2588\u2588"  # Full block × 2 for squarish cells
HEX_CELL = "\u2b22 "       # Hexagon character for hex mode
HEX_DEAD = "\u00b7 "       # Middle dot for empty hex cells

# Hex neighbor offsets for offset-row (even-q) coordinates
# Even rows: neighbors are at these (dr, dc) offsets
HEX_NEIGHBORS_EVEN = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
# Odd rows: neighbors are at these (dr, dc) offsets
HEX_NEIGHBORS_ODD = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]

# Zoom levels: 1 = normal (1:1), 2 = zoom out (2×2 → 1 glyph), 4 = (4×4 → 1 glyph), etc.
ZOOM_LEVELS = [1, 2, 4, 8]
# Density glyphs for zoomed-out rendering (maps alive-cell fraction to visual)
DENSITY_CHARS = ["  ", "░░", "▒▒", "▓▓", CELL_CHAR]
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
    # Heatmap colour tiers (pairs 10–16): cool to hot
    curses.init_pair(10, 17, -1)   # very dim blue (near-zero activity)
    curses.init_pair(11, 19, -1)   # blue
    curses.init_pair(12, 27, -1)   # bright blue
    curses.init_pair(13, 51, -1)   # cyan
    curses.init_pair(14, 226, -1)  # yellow
    curses.init_pair(15, 208, -1)  # orange
    curses.init_pair(16, 196, -1)  # red
    curses.init_pair(17, 231, -1)  # white (maximum heat)
    # Fallback heatmap pairs for terminals with < 256 colors
    curses.init_pair(18, curses.COLOR_BLUE, -1)
    curses.init_pair(19, curses.COLOR_CYAN, -1)
    curses.init_pair(20, curses.COLOR_YELLOW, -1)
    curses.init_pair(21, curses.COLOR_RED, -1)
    curses.init_pair(22, curses.COLOR_WHITE, -1)
    # Pattern search highlight colours (pairs 30–33)
    curses.init_pair(30, curses.COLOR_CYAN, -1)     # Still life
    curses.init_pair(31, curses.COLOR_YELLOW, -1)    # Oscillator
    curses.init_pair(32, curses.COLOR_MAGENTA, -1)   # Spaceship
    curses.init_pair(33, curses.COLOR_WHITE, -1)     # Other / label text
    # Blueprint selection highlight (pair 40)
    curses.init_pair(40, curses.COLOR_GREEN, -1)     # Blueprint selection border/cells
    # Multiplayer player colours (pairs 50–57)
    if curses.COLORS >= 256:
        curses.init_pair(50, 33, -1)    # P1 newborn  (blue)
        curses.init_pair(51, 39, -1)    # P1 young    (light blue)
        curses.init_pair(52, 27, -1)    # P1 mature   (bright blue)
        curses.init_pair(53, 21, -1)    # P1 old      (deep blue)
        curses.init_pair(54, 196, -1)   # P2 newborn  (red)
        curses.init_pair(55, 209, -1)   # P2 young    (orange-red)
        curses.init_pair(56, 160, -1)   # P2 mature   (dark red)
        curses.init_pair(57, 124, -1)   # P2 old      (deep red)
    else:
        curses.init_pair(50, curses.COLOR_BLUE, -1)
        curses.init_pair(51, curses.COLOR_CYAN, -1)
        curses.init_pair(52, curses.COLOR_BLUE, -1)
        curses.init_pair(53, curses.COLOR_BLUE, -1)
        curses.init_pair(54, curses.COLOR_RED, -1)
        curses.init_pair(55, curses.COLOR_MAGENTA, -1)
        curses.init_pair(56, curses.COLOR_RED, -1)
        curses.init_pair(57, curses.COLOR_RED, -1)
    curses.init_pair(58, curses.COLOR_YELLOW, -1)   # contested/neutral born cell


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


# Multiplayer player colour pairs: P1 → 50-53, P2 → 54-57, neutral → 58
_MP_P1_PAIRS = [50, 51, 52, 53]  # newborn → old
_MP_P2_PAIRS = [54, 55, 56, 57]


def color_for_mp(age: int, owner: int) -> int:
    """Return a curses colour pair for a multiplayer cell based on owner (1 or 2) and age."""
    if owner == 1:
        pairs = _MP_P1_PAIRS
    elif owner == 2:
        pairs = _MP_P2_PAIRS
    else:
        return curses.color_pair(58)
    if age <= 1:
        return curses.color_pair(pairs[0])
    if age <= 5:
        return curses.color_pair(pairs[1])
    if age <= 15:
        return curses.color_pair(pairs[2])
    return curses.color_pair(pairs[3])


# Heatmap 256-color tiers (pair indices 10–17) and 8-color fallback (18–22)
HEAT_PAIRS_256 = [10, 11, 12, 13, 14, 15, 16, 17]
HEAT_PAIRS_8 = [18, 18, 19, 19, 20, 20, 21, 22]


def color_for_heat(fraction: float) -> int:
    """Return a curses colour pair attribute for a heatmap fraction 0.0–1.0.
    0 = coolest (dim blue), 1 = hottest (white)."""
    if curses.COLORS >= 256:
        pairs = HEAT_PAIRS_256
    else:
        pairs = HEAT_PAIRS_8
    idx = min(int(fraction * len(pairs)), len(pairs) - 1)
    return curses.color_pair(pairs[idx])


# ── GIF encoder (pure Python, no external dependencies) ─────────────────────

# Color palette for GIF: index 0 = background, 1–5 = age tiers
_GIF_PALETTE = [
    (18, 18, 24),     # 0: background (dark)
    (0, 200, 0),      # 1: newborn (green)
    (0, 200, 200),    # 2: young (cyan)
    (200, 200, 0),    # 3: mature (yellow)
    (200, 0, 200),    # 4: old (magenta)
    (200, 0, 0),      # 5: ancient (red)
    (100, 100, 100),  # 6: grid lines (subtle)
    (255, 255, 255),  # 7: spare (white)
]


def _gif_age_index(age: int) -> int:
    """Map cell age to palette index (mirrors color_for_age tiers)."""
    if age <= 0:
        return 0
    if age <= 1:
        return 1
    if age <= 3:
        return 2
    if age <= 8:
        return 3
    if age <= 20:
        return 4
    return 5


def _lzw_compress(pixels: list[int], min_code_size: int) -> bytes:
    """LZW compression for GIF image data."""
    clear_code = 1 << min_code_size
    eoi_code = clear_code + 1

    code_table: dict[tuple, int] = {}
    for i in range(clear_code):
        code_table[(i,)] = i

    next_code = eoi_code + 1
    code_size = min_code_size + 1
    max_code = (1 << code_size)

    # Bit packing
    bit_buffer = 0
    bits_in_buffer = 0
    output = bytearray()

    def emit(code: int):
        nonlocal bit_buffer, bits_in_buffer
        bit_buffer |= code << bits_in_buffer
        bits_in_buffer += code_size
        while bits_in_buffer >= 8:
            output.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bits_in_buffer -= 8

    emit(clear_code)
    buffer = (pixels[0],)

    for px in pixels[1:]:
        buffer_plus = buffer + (px,)
        if buffer_plus in code_table:
            buffer = buffer_plus
        else:
            emit(code_table[buffer])
            if next_code < 4096:
                code_table[buffer_plus] = next_code
                next_code += 1
                if next_code > max_code and code_size < 12:
                    code_size += 1
                    max_code = 1 << code_size
            else:
                # Table full, reset
                emit(clear_code)
                code_table = {}
                for i in range(clear_code):
                    code_table[(i,)] = i
                next_code = eoi_code + 1
                code_size = min_code_size + 1
                max_code = 1 << code_size
            buffer = (px,)

    emit(code_table[buffer])
    emit(eoi_code)

    # Flush remaining bits
    if bits_in_buffer > 0:
        output.append(bit_buffer & 0xFF)

    return bytes(output)


def _gif_sub_blocks(data: bytes) -> bytes:
    """Split data into GIF sub-blocks (max 255 bytes each)."""
    result = bytearray()
    i = 0
    while i < len(data):
        chunk = data[i:i + 255]
        result.append(len(chunk))
        result.extend(chunk)
        i += 255
    result.append(0)  # block terminator
    return bytes(result)


def write_gif(filepath: str, frames: list[list[list[int]]],
              cell_size: int = 4, delay_cs: int = 10):
    """Write an animated GIF from a list of grid frames.

    Each frame is a 2D list of cell ages (0 = dead, >0 = alive with age).
    cell_size: pixels per cell side.
    delay_cs: delay between frames in centiseconds (1/100 s).
    """
    if not frames:
        return
    rows = len(frames[0])
    cols = len(frames[0][0]) if rows else 0
    width = cols * cell_size
    height = rows * cell_size

    # Use 3-bit palette (8 colours)
    min_code_size = 3
    palette_size = 8

    # Build flat palette bytes
    palette_bytes = bytearray()
    for r, g, b in _GIF_PALETTE[:palette_size]:
        palette_bytes.extend([r, g, b])

    out = bytearray()
    # Header
    out.extend(b"GIF89a")
    # Logical screen descriptor
    out.extend(struct.pack("<HH", width, height))
    # GCT flag=1, color res=2 (3 bits), sort=0, GCT size=2 (8 colors)
    out.append(0b10000010)
    out.append(0)  # bg color index
    out.append(0)  # pixel aspect ratio

    # Global color table
    out.extend(palette_bytes)

    # Netscape looping extension (loop forever)
    out.extend(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00")

    for frame in frames:
        # Graphic control extension (delay + disposal)
        out.extend(b"\x21\xF9\x04")
        out.append(0x00)  # disposal=0, no transparency
        out.extend(struct.pack("<H", delay_cs))
        out.append(0)  # transparent color index (unused)
        out.append(0)  # block terminator

        # Image descriptor
        out.extend(b"\x2C")
        out.extend(struct.pack("<HHHH", 0, 0, width, height))
        out.append(0)  # no local color table

        # Build pixel data
        pixels = []
        for r in range(rows):
            row = frame[r]
            for _ in range(cell_size):
                for c in range(cols):
                    idx = _gif_age_index(row[c])
                    pixels.extend([idx] * cell_size)

        # LZW compress
        out.append(min_code_size)
        compressed = _lzw_compress(pixels, min_code_size)
        out.extend(_gif_sub_blocks(compressed))

    # Trailer
    out.append(0x3B)

    with open(filepath, "wb") as f:
        f.write(out)


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
        # Hex mode: use 6 neighbors instead of 8
        self.hex_mode = False

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
        if self.hex_mode:
            offsets = HEX_NEIGHBORS_EVEN if r % 2 == 0 else HEX_NEIGHBORS_ODD
            for dr, dc in offsets:
                nr = (r + dr) % self.rows
                nc = (c + dc) % self.cols
                if self.cells[nr][nc]:
                    count += 1
        else:
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


# ── Sound engine ─────────────────────────────────────────────────────────────

# Pentatonic scale intervals (semitones from root): C D E G A
_PENTATONIC = [0, 2, 4, 7, 9]


def _row_to_freq(row: int, total_rows: int, base_freq: float = 220.0) -> float:
    """Map a grid row to a frequency using a pentatonic scale.

    Row 0 (top) is the highest pitch, row (total_rows-1) is the lowest.
    The mapping wraps through multiple octaves of the pentatonic scale.
    """
    # Invert so top rows are high-pitched
    idx = total_rows - 1 - row
    octave, degree = divmod(idx, len(_PENTATONIC))
    semitones = octave * 12 + _PENTATONIC[degree]
    return base_freq * (2.0 ** (semitones / 12.0))


class SoundEngine:
    """Procedural audio synthesizer that turns grid state into music.

    Generates WAV audio in a background thread, playing through an external
    process (aplay/paplay/afplay) or writing to /dev/dsp if available.
    Stays pure-Python with no external library dependencies.
    """

    SAMPLE_RATE = 22050
    MAX_POLYPHONY = 12  # limit simultaneous tones to keep output pleasant

    def __init__(self):
        self.enabled = False
        self._lock = threading.Lock()
        self._play_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Detect playback method
        self._play_cmd = self._detect_player()

    @staticmethod
    def _detect_player() -> list[str] | None:
        """Find an available audio playback command."""
        import shutil
        for cmd, args in [
            ("paplay", ["paplay", "--raw", "--rate=22050", "--channels=1",
                         "--format=s16le"]),
            ("aplay", ["aplay", "-q", "-f", "S16_LE", "-r", "22050", "-c", "1"]),
            ("afplay", None),  # macOS — needs a file, handled separately
        ]:
            if shutil.which(cmd):
                return args
        return None

    def toggle(self) -> bool:
        """Toggle sound on/off. Returns new state."""
        self.enabled = not self.enabled
        if not self.enabled:
            self._stop_event.set()
        return self.enabled

    def play_grid(self, grid, speed_delay: float):
        """Generate and play a short audio chunk representing the current grid.

        Called each generation. The duration matches the simulation tempo so
        the music stays synced with the visual.
        """
        if not self.enabled or self._play_cmd is None:
            return

        # Don't stack up threads if playback is still going
        if self._play_thread and self._play_thread.is_alive():
            return

        # Collect active rows (any column) and per-column densities
        rows = grid.rows
        cols = grid.cols
        cells = grid.cells

        # Find which rows have living cells and column population counts
        active_rows: list[int] = []
        col_counts = [0] * cols
        for r in range(rows):
            row_alive = False
            for c in range(cols):
                if cells[r][c] > 0:
                    row_alive = True
                    col_counts[c] += 1
            if row_alive:
                active_rows.append(r)

        if not active_rows:
            return

        # Limit polyphony — pick evenly-spaced rows
        if len(active_rows) > self.MAX_POLYPHONY:
            step = len(active_rows) / self.MAX_POLYPHONY
            active_rows = [active_rows[int(i * step)] for i in range(self.MAX_POLYPHONY)]

        # Overall volume from mean population density
        total_alive = grid.population
        density = min(total_alive / (rows * cols), 1.0) if rows * cols > 0 else 0
        master_vol = 0.15 + 0.85 * density  # range [0.15, 1.0]

        # Duration synced to simulation speed (at least 50ms, at most 2s)
        duration = max(0.05, min(speed_delay * 0.8, 2.0))

        freqs = [_row_to_freq(r, rows) for r in active_rows]
        samples = self._synthesize(freqs, duration, master_vol)

        self._stop_event.clear()
        self._play_thread = threading.Thread(
            target=self._play_samples, args=(samples,), daemon=True
        )
        self._play_thread.start()

    def _synthesize(self, freqs: list[float], duration: float, volume: float) -> bytes:
        """Generate mixed sine-wave PCM samples (S16LE mono)."""
        n_samples = int(self.SAMPLE_RATE * duration)
        if not freqs:
            return b"\x00\x00" * n_samples

        amp = volume / len(freqs)  # per-voice amplitude
        max_amp = 28000  # stay below S16 clipping

        buf = bytearray(n_samples * 2)
        # Pre-compute phase increments
        increments = [2.0 * math.pi * f / self.SAMPLE_RATE for f in freqs]

        # Soft attack/release envelope (avoid clicks): 5ms ramp
        ramp_samples = min(int(0.005 * self.SAMPLE_RATE), n_samples // 2)

        for i in range(n_samples):
            # Envelope
            if i < ramp_samples:
                env = i / ramp_samples
            elif i > n_samples - ramp_samples:
                env = (n_samples - i) / ramp_samples
            else:
                env = 1.0

            val = 0.0
            for inc in increments:
                val += math.sin(inc * i)
            val = val * amp * max_amp * env
            sample = max(-32767, min(32767, int(val)))
            struct.pack_into("<h", buf, i * 2, sample)
        return bytes(buf)

    def _play_samples(self, samples: bytes):
        """Play raw PCM samples via detected player (runs in thread)."""
        import subprocess
        if not self._play_cmd:
            return
        try:
            if self._play_cmd[0] == "afplay":
                # macOS afplay needs a WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                    with wave.open(tmp.name, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(self.SAMPLE_RATE)
                        wf.writeframes(samples)
                    subprocess.run(["afplay", tmp.name],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   timeout=5)
            else:
                proc = subprocess.Popen(
                    self._play_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                proc.communicate(input=samples, timeout=5)
        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass


# ── Multiplayer networking ───────────────────────────────────────────────────

MP_DEFAULT_PORT = 7654
MP_PLANNING_TIME = 30  # seconds for planning phase
MP_SIM_GENS = 200  # generations per round


class MultiplayerNet:
    """TCP networking for multiplayer mode using background threads.

    Messages are newline-delimited JSON.  A background thread handles I/O so
    the curses event loop never blocks.
    """

    def __init__(self):
        self.role: str | None = None  # "host" or "client"
        self.sock: socket.socket | None = None  # connected socket to peer
        self.server_sock: socket.socket | None = None  # listening (host only)
        self.connected = False
        self.running = False
        self._send_q: queue.Queue = queue.Queue()
        self._recv_q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._recv_buf = b""

    def start_host(self, port: int) -> bool:
        """Start listening for a connection.  Returns True if bind succeeded."""
        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind(("", port))
            self.server_sock.listen(1)
            self.server_sock.settimeout(0.5)
            self.role = "host"
            self.running = True
            self._thread = threading.Thread(target=self._host_loop, daemon=True)
            self._thread.start()
            return True
        except OSError:
            return False

    def connect(self, host: str, port: int) -> bool:
        """Connect to a host.  Returns True on success."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((host, port))
            self.sock.settimeout(0.1)
            self.role = "client"
            self.connected = True
            self.running = True
            self._thread = threading.Thread(target=self._io_loop, daemon=True)
            self._thread.start()
            return True
        except OSError:
            if self.sock:
                self.sock.close()
                self.sock = None
            return False

    def send(self, msg: dict):
        """Queue a message to send to the peer."""
        self._send_q.put(msg)

    def poll(self) -> list[dict]:
        """Return all messages received since last poll."""
        msgs = []
        while True:
            try:
                msgs.append(self._recv_q.get_nowait())
            except queue.Empty:
                break
        return msgs

    def stop(self):
        """Shut down networking."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        if self.server_sock:
            try:
                self.server_sock.close()
            except OSError:
                pass
        self.connected = False
        self.sock = None
        self.server_sock = None

    # ── internal ──

    def _host_loop(self):
        """Host: wait for connection, then do I/O."""
        while self.running and not self.connected:
            try:
                self.sock, _ = self.server_sock.accept()
                self.sock.settimeout(0.1)
                self.connected = True
            except socket.timeout:
                continue
            except OSError:
                break
        if self.connected:
            self._io_loop()

    def _io_loop(self):
        """Send/receive JSON messages over the socket."""
        while self.running and self.connected:
            # Send queued messages
            while not self._send_q.empty():
                try:
                    msg = self._send_q.get_nowait()
                    data = json.dumps(msg, separators=(",", ":")).encode() + b"\n"
                    self.sock.sendall(data)
                except (OSError, queue.Empty):
                    self.connected = False
                    return
            # Receive
            try:
                chunk = self.sock.recv(8192)
                if not chunk:
                    self.connected = False
                    return
                self._recv_buf += chunk
                while b"\n" in self._recv_buf:
                    line, self._recv_buf = self._recv_buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode())
                        self._recv_q.put(msg)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
            except socket.timeout:
                pass
            except OSError:
                self.connected = False
                return


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
        self.zoom_level = 1  # 1=normal, 2/4/8=zoomed out
        self.cursor_r = grid_rows // 2
        self.cursor_c = grid_cols // 2
        self.show_help = False
        self.message = ""
        self.message_time = 0.0
        self.pattern_menu = False
        self.stamp_menu = False  # stamp mode: overlay pattern at cursor
        self.pattern_list: list[str] = []
        self.pattern_sel = 0
        self.pop_history: list[int] = []
        # Cycle detection: map state_hash -> generation when first seen
        self.state_history: dict[str, int] = {}
        self.cycle_detected = False
        # Draw mode: None, "draw" (paint alive), or "erase" (paint dead)
        self.draw_mode: str | None = None
        # History buffer for rewind (stores (grid_dict, pop_len) tuples)
        self.history: list[tuple[dict, int]] = []
        self.history_max = 500
        # Timeline scrubbing position: None = "live" (at current grid), int = index into history
        self.timeline_pos: int | None = None
        # Bookmarks: list of (generation, grid_dict, pop_len) for notable moments
        self.bookmarks: list[tuple[int, dict, int]] = []
        self.bookmark_menu = False
        self.bookmark_sel = 0
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
        # Race mode state: multi-rule evolution competition
        self.race_mode = False
        self.race_grids: list[Grid] = []         # 3-4 grids with different rules
        self.race_pop_histories: list[list[int]] = []
        self.race_rule_menu = False               # picking rules for race
        self.race_rule_sel = 0
        self.race_selected_rules: list[tuple[str, set, set]] = []  # (name, birth, survival)
        self.race_start_gen = 0
        self.race_max_gens = 500                  # race duration
        self.race_finished = False
        self.race_winner: str | None = None
        # Per-grid race stats: {grid_idx: {extinction_gen, osc_period, peak_pop}}
        self.race_stats: list[dict] = []
        self.race_state_hashes: list[dict] = []   # cycle detection per grid
        # Heatmap mode: cumulative cell activity overlay
        self.heatmap_mode = False
        self.heatmap = [[0] * grid_cols for _ in range(grid_rows)]
        self.heatmap_max = 0  # track peak for normalisation
        # Pattern search mode: detect and highlight known patterns
        self.pattern_search_mode = False
        self.detected_patterns: list[dict] = []
        self._pattern_scan_gen = -1  # generation of last scan
        # Blueprint mode: interactive region selection → save as reusable pattern
        self.blueprint_mode = False
        self.blueprint_anchor: tuple[int, int] | None = None  # (r, c) of selection start
        self.blueprints: dict = _load_blueprints()  # name -> {description, cells}
        self.blueprint_menu = False
        self.blueprint_sel = 0
        # GIF recording mode
        self.recording = False
        self.recorded_frames: list[list[list[int]]] = []
        self.recording_start_gen = 0
        # 3D isometric mode
        self.iso_mode = False
        # Sound/music mode
        self.sound_engine = SoundEngine()
        # Multiplayer mode state
        self.mp_mode = False
        self.mp_net: MultiplayerNet | None = None
        self.mp_role: str | None = None  # "host" or "client"
        self.mp_phase: str = "idle"  # idle/lobby/planning/running/finished
        self.mp_player: int = 0  # 1 = host/blue, 2 = client/red
        self.mp_owner: list[list[int]] = []  # 2D grid: 0=neutral, 1=P1, 2=P2
        self.mp_scores: list[int] = [0, 0]  # [P1, P2]
        self.mp_round: int = 0
        self.mp_planning_deadline: float = 0.0
        self.mp_ready: list[bool] = [False, False]
        self.mp_sim_gens: int = MP_SIM_GENS
        self.mp_start_gen: int = 0
        self.mp_territory_bonus: list[int] = [0, 0]  # cells in opponent's half
        self.mp_state_dirty = False  # host: state changed, needs broadcast
        self.mp_host_port: int = MP_DEFAULT_PORT
        self.mp_connect_addr: str = ""
        # Puzzle / challenge mode state
        self.puzzle_mode = False
        self.puzzle_menu = False           # puzzle selection menu
        self.puzzle_sel = 0                # selected puzzle index
        self.puzzle_phase: str = "idle"    # idle/planning/running/success/fail
        self.puzzle_current: dict | None = None  # current puzzle definition
        self.puzzle_placed_cells: set = set()  # cells placed by player during planning
        self.puzzle_start_pop: int = 0     # population at start of run
        self.puzzle_sim_gen: int = 0       # generations simulated so far
        self.puzzle_peak_pop: int = 0      # peak population during simulation
        self.puzzle_initial_bbox: tuple | None = None  # (min_r, min_c, max_r, max_c) for escape_box
        self.puzzle_state_hashes: dict = {}  # hash -> gen for cycle detection
        self.puzzle_win_gen: int | None = None  # generation when win condition was met
        self.puzzle_score: int = 0         # score for current puzzle
        self.puzzle_scores: dict = {}      # puzzle_id -> best score
        # Genetic algorithm evolution mode state
        self.evo_mode = False
        self.evo_menu = False              # settings menu before starting
        self.evo_pop_size = 12             # number of rulesets in population
        self.evo_grid_gens = 200           # generations to simulate each ruleset
        self.evo_mutation_rate = 0.15      # probability of mutating each digit
        self.evo_elite_count = 4           # top N survivors that reproduce
        self.evo_generation = 0            # current GA generation
        self.evo_grids: list[Grid] = []    # one grid per individual
        self.evo_rules: list[tuple[set, set]] = []  # (birth, survival) per individual
        self.evo_fitness: list[dict] = []  # fitness details per individual
        self.evo_pop_histories: list[list[int]] = []  # population history per grid
        self.evo_sim_step = 0              # current sim step within a generation
        self.evo_phase = "idle"            # idle/simulating/scored/adopting
        self.evo_sel = 0                   # selected individual for adoption
        self.evo_menu_sel = 0              # menu cursor
        self.evo_fitness_mode = "balanced" # balanced/longevity/diversity/population
        self.evo_best_ever: dict | None = None  # best fitness seen across all gens
        self.evo_history: list[dict] = []  # summary per generation
        # Wolfram 1D elementary cellular automaton mode
        self.wolfram_mode = False
        self.wolfram_rule = 30           # current rule number (0-255)
        self.wolfram_rows: list[list[int]] = []  # computed rows of 1D automaton
        self.wolfram_running = False     # auto-advance
        self.wolfram_width = 0           # width of the automaton row
        self.wolfram_menu = False        # rule selection menu
        self.wolfram_menu_sel = 0        # selected preset in menu
        self.wolfram_seed_mode = "center"  # "center" or "gol_row"
        # Langton's Ant mode
        self.ant_mode = False
        self.ant_menu = False
        self.ant_menu_sel = 0
        self.ant_running = False
        self.ant_step_count = 0
        self.ant_grid: dict[tuple[int, int], int] = {}  # (r,c) -> color state
        self.ant_ants: list[dict] = []  # list of {r, c, dir, color_idx}
        self.ant_rule = "RL"            # rule string: R=right, L=left per color
        self.ant_num_ants = 1           # number of ants
        self.ant_rows = 0
        self.ant_cols = 0
        self.ant_steps_per_frame = 1    # how many steps per display frame
        # Hexagonal grid mode
        self.hex_mode = False
        # Wireworld mode
        self.ww_mode = False
        self.ww_menu = False
        self.ww_menu_sel = 0
        self.ww_running = False
        self.ww_generation = 0
        self.ww_grid: dict[tuple[int, int], int] = {}  # (r,c) -> state (1=conductor,2=head,3=tail)
        self.ww_rows = 0
        self.ww_cols = 0
        self.ww_cursor_r = 0
        self.ww_cursor_c = 0
        self.ww_drawing = True  # start in edit/drawing mode
        self.ww_draw_state = 1  # what state to paint (1=conductor,2=head,3=tail)
        # Falling-sand particle simulation mode
        self.sand_mode = False
        self.sand_menu = False
        self.sand_menu_sel = 0
        self.sand_running = False
        self.sand_generation = 0
        self.sand_grid: dict[tuple[int, int], tuple[int, int]] = {}  # (r,c) -> (element, age)
        self.sand_rows = 0
        self.sand_cols = 0
        self.sand_cursor_r = 0
        self.sand_cursor_c = 0
        self.sand_brush = 1       # current brush element type
        self.sand_brush_size = 1  # brush radius
        self._rebuild_pattern_list()

        if pattern:
            self._place_pattern(pattern)

    def _place_pattern(self, name: str):
        pat = self._get_pattern(name)
        if not pat:
            self.message = f"Unknown pattern: {name}"
            self.message_time = time.monotonic()
            return
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = (self.grid.rows - max_r) // 2
        off_c = (self.grid.cols - max_c) // 2
        for r, c in pat["cells"]:
            self.grid.set_alive((r + off_r) % self.grid.rows, (c + off_c) % self.grid.cols)
        self.cursor_r = off_r + max_r // 2
        self.cursor_c = off_c + max_c // 2
        self.message = f"Loaded: {name}"
        self.message_time = time.monotonic()

    def _stamp_pattern(self, name: str):
        """Overlay a pattern centered on the current cursor without clearing the grid."""
        pat = self._get_pattern(name)
        if not pat:
            self._flash(f"Unknown pattern: {name}")
            return
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = self.cursor_r - max_r // 2
        off_c = self.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            self.grid.set_alive((r + off_r) % self.grid.rows, (c + off_c) % self.grid.cols)
        self._flash(f"Stamped: {name}")

    def _flash(self, msg: str):
        self.message = msg
        self.message_time = time.monotonic()

    def _record_pop(self):
        self.pop_history.append(self.grid.population)

    def _scan_patterns(self):
        """Run pattern recognition on the current grid."""
        self.detected_patterns = scan_patterns(self.grid)
        self._pattern_scan_gen = self.grid.generation

    @staticmethod
    def _pattern_color(category: str) -> int:
        """Return curses color pair for a pattern category."""
        if category == "Still life":
            return curses.color_pair(30)
        if category == "Oscillator":
            return curses.color_pair(31)
        if category == "Spaceship":
            return curses.color_pair(32)
        return curses.color_pair(33)

    def _update_heatmap(self):
        """Increment heatmap counters for every currently alive cell."""
        cells = self.grid.cells
        hm = self.heatmap
        peak = self.heatmap_max
        for r in range(self.grid.rows):
            row_cells = cells[r]
            row_hm = hm[r]
            for c in range(self.grid.cols):
                if row_cells[c] > 0:
                    row_hm[c] += 1
                    if row_hm[c] > peak:
                        peak = row_hm[c]
        self.heatmap_max = peak

    def _rebuild_pattern_list(self):
        """Rebuild the combined pattern list from built-ins + blueprints."""
        self.pattern_list = sorted(set(PATTERNS.keys()) | set(self.blueprints.keys()))

    def _get_pattern(self, name: str) -> dict | None:
        """Get a pattern by name from built-ins or blueprints."""
        if name in PATTERNS:
            return PATTERNS[name]
        return self.blueprints.get(name)

    # ── Blueprint mode ──

    def _enter_blueprint_mode(self):
        """Start blueprint region selection at current cursor position."""
        self.blueprint_mode = True
        self.blueprint_anchor = (self.cursor_r, self.cursor_c)
        self._flash("Blueprint: move cursor to select region, Enter=capture, Esc=cancel")

    def _blueprint_region(self) -> tuple[int, int, int, int]:
        """Return (min_r, min_c, max_r, max_c) of the current blueprint selection."""
        ar, ac = self.blueprint_anchor
        cr, cc = self.cursor_r, self.cursor_c
        return (min(ar, cr), min(ac, cc), max(ar, cr), max(ac, cc))

    def _capture_blueprint(self):
        """Capture the selected region as a named blueprint pattern."""
        min_r, min_c, max_r, max_c = self._blueprint_region()
        # Collect alive cells in the region, normalised to (0,0) origin
        cells = []
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                gr = r % self.grid.rows
                gc = c % self.grid.cols
                if self.grid.cells[gr][gc] > 0:
                    cells.append((r - min_r, c - min_c))
        if not cells:
            self._flash("No alive cells in selection — blueprint not saved")
            self.blueprint_mode = False
            self.blueprint_anchor = None
            return
        width = max_c - min_c + 1
        height = max_r - min_r + 1
        self.blueprint_mode = False
        self.blueprint_anchor = None
        # Prompt for a name
        name = self._prompt_text(f"Blueprint name ({len(cells)} cells, {width}x{height})")
        if not name:
            self._flash("Blueprint cancelled")
            return
        # Sanitize name (lowercase, replace spaces with underscores)
        safe_name = name.strip().lower().replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        if not safe_name:
            self._flash("Invalid name")
            return
        # Don't overwrite built-in patterns
        if safe_name in PATTERNS:
            self._flash(f"Cannot overwrite built-in pattern '{safe_name}'")
            return
        desc = f"Custom blueprint ({len(cells)} cells, {width}x{height})"
        self.blueprints[safe_name] = {"description": desc, "cells": cells}
        _save_blueprints(self.blueprints)
        self._rebuild_pattern_list()
        self._flash(f"Saved blueprint: {safe_name}")

    def _stamp_blueprint(self, name: str):
        """Overlay a blueprint pattern centered on the current cursor."""
        pat = self._get_pattern(name)
        if not pat:
            self._flash(f"Unknown pattern: {name}")
            return
        max_r = max(r for r, c in pat["cells"]) if pat["cells"] else 0
        max_c = max(c for r, c in pat["cells"]) if pat["cells"] else 0
        off_r = self.cursor_r - max_r // 2
        off_c = self.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            gr = (r + off_r) % self.grid.rows
            gc = (c + off_c) % self.grid.cols
            self.grid.set_alive(gr, gc)
        self._flash(f"Stamped: {name}")

    def _delete_blueprint(self, name: str):
        """Delete a user-saved blueprint."""
        if name in self.blueprints:
            del self.blueprints[name]
            _save_blueprints(self.blueprints)
            self._rebuild_pattern_list()
            self._flash(f"Deleted blueprint: {name}")

    def _handle_blueprint_mode_key(self, key: int) -> bool:
        """Handle keys while in blueprint selection mode."""
        if key == -1:
            return True
        if key == 27:  # ESC
            self.blueprint_mode = False
            self.blueprint_anchor = None
            self._flash("Blueprint selection cancelled")
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — capture
            self._capture_blueprint()
            return True
        # Cursor movement (same as normal mode)
        if key in (curses.KEY_UP, ord("k")):
            self.cursor_r = (self.cursor_r - 1) % self.grid.rows
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.cursor_r = (self.cursor_r + 1) % self.grid.rows
            return True
        if key in (curses.KEY_LEFT, ord("l") - 4):  # 'h' already used
            self.cursor_c = (self.cursor_c - 1) % self.grid.cols
            return True
        if key in (curses.KEY_RIGHT, ord("l")):
            self.cursor_c = (self.cursor_c + 1) % self.grid.cols
            return True
        return True

    def _handle_blueprint_menu_key(self, key: int) -> bool:
        """Handle keys in the blueprint library menu."""
        if key == -1:
            return True
        bp_names = sorted(self.blueprints.keys())
        if not bp_names:
            self.blueprint_menu = False
            return True
        if key == 27 or key == ord("q"):
            self.blueprint_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.blueprint_sel = (self.blueprint_sel - 1) % len(bp_names)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.blueprint_sel = (self.blueprint_sel + 1) % len(bp_names)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — stamp at cursor
            name = bp_names[self.blueprint_sel]
            self._stamp_blueprint(name)
            self.blueprint_menu = False
            self._reset_cycle_detection()
            return True
        if key == ord("D") or key == curses.KEY_DC:  # D or Delete — remove
            name = bp_names[self.blueprint_sel]
            self._delete_blueprint(name)
            bp_names = sorted(self.blueprints.keys())
            if not bp_names:
                self.blueprint_menu = False
            else:
                self.blueprint_sel = min(self.blueprint_sel, len(bp_names) - 1)
            return True
        return True

    def _draw_blueprint_menu(self, max_y: int, max_x: int):
        """Draw the blueprint library menu."""
        bp_names = sorted(self.blueprints.keys())
        title = "── Blueprint Library (Enter=stamp, D=delete, q/Esc=close) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        if not bp_names:
            msg = "No blueprints saved yet. Press W to create one."
            try:
                self.stdscr.addstr(3, max(0, (max_x - len(msg)) // 2), msg,
                                   curses.color_pair(6))
            except curses.error:
                pass
            return
        for i, name in enumerate(bp_names):
            y = 3 + i
            if y >= max_y - 1:
                break
            desc = self.blueprints[name]["description"]
            line = f"  {name:<20s} {desc}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.blueprint_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass

    def _push_history(self):
        """Save the current grid state to the history buffer before advancing."""
        # If scrubbed back, truncate future history before pushing
        if self.timeline_pos is not None:
            self.history = self.history[:self.timeline_pos + 1]
            self.timeline_pos = None
        self.history.append((self.grid.to_dict(), len(self.pop_history)))
        # Enforce max size by trimming oldest entries
        if len(self.history) > self.history_max:
            self.history = self.history[-self.history_max:]

    def _rewind(self):
        """Restore the most recent state from the history buffer."""
        if not self.history:
            self._flash("No history to rewind")
            return
        # If live, start scrubbing from the end; if already scrubbed, go back one more
        if self.timeline_pos is None:
            self.timeline_pos = len(self.history) - 1
        else:
            if self.timeline_pos <= 0:
                self._flash("At oldest recorded state")
                return
            self.timeline_pos -= 1
        self._restore_timeline_pos()

    def _restore_timeline_pos(self):
        """Restore the grid state at the current timeline position."""
        grid_dict, pop_len = self.history[self.timeline_pos]
        self.grid.load_dict(grid_dict)
        self.pop_history = self.pop_history[:pop_len]
        self._reset_cycle_detection()
        self._flash(f"Gen {self.grid.generation}  ({self.timeline_pos + 1}/{len(self.history)})")

    def _scrub_back(self, steps: int = 10):
        """Scrub backward through the timeline by the given number of steps."""
        if not self.history:
            self._flash("No history to scrub")
            return
        if self.timeline_pos is None:
            self.timeline_pos = max(0, len(self.history) - steps)
        else:
            self.timeline_pos = max(0, self.timeline_pos - steps)
        self._restore_timeline_pos()

    def _scrub_forward(self, steps: int = 10):
        """Scrub forward through the timeline by the given number of steps."""
        if self.timeline_pos is None:
            self._flash("Already at latest state")
            return
        self.timeline_pos += steps
        if self.timeline_pos >= len(self.history):
            # Return to the latest recorded state
            self.timeline_pos = None
            grid_dict, pop_len = self.history[-1]
            self.grid.load_dict(grid_dict)
            self.pop_history = self.pop_history[:pop_len]
            self._reset_cycle_detection()
            self._flash(f"Latest → Gen {self.grid.generation} (press n/Space to continue)")
        else:
            self._restore_timeline_pos()

    def _add_bookmark(self):
        """Bookmark the current generation."""
        gen = self.grid.generation
        # Don't duplicate
        for bg, _, _ in self.bookmarks:
            if bg == gen:
                self._flash(f"Gen {gen} already bookmarked")
                return
        self.bookmarks.append((gen, self.grid.to_dict(), len(self.pop_history)))
        self.bookmarks.sort(key=lambda x: x[0])
        self._flash(f"★ Bookmarked Gen {gen}  ({len(self.bookmarks)} total)")

    def _jump_to_bookmark(self, idx: int):
        """Jump to a bookmarked state."""
        if idx < 0 or idx >= len(self.bookmarks):
            return
        gen, grid_dict, pop_len = self.bookmarks[idx]
        self.grid.load_dict(grid_dict)
        self.pop_history = self.pop_history[:pop_len]
        self.timeline_pos = None  # bookmarks jump to an independent snapshot
        self._reset_cycle_detection()
        self._flash(f"★ Jumped to bookmark Gen {gen}")

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

            # ── Multiplayer network tick ──
            if self.mp_mode:
                self._mp_poll()
                if not self.mp_mode:
                    continue  # disconnected during poll
                if self.mp_phase == "lobby":
                    self._mp_lobby_tick()
                elif self.mp_phase == "planning":
                    self._mp_planning_tick()

            # ── Multiplayer input dispatch ──
            if self.mp_mode and self.mp_phase == "planning":
                self._handle_mp_planning_key(key)
                if self.draw_mode and key in (curses.KEY_UP, curses.KEY_DOWN,
                                               curses.KEY_LEFT, curses.KEY_RIGHT,
                                               ord("h"), ord("j"), ord("k"), ord("l")):
                    self._mp_apply_draw_mode()
                continue
            elif self.mp_mode and self.mp_phase == "running":
                self._handle_mp_running_key(key)
                # Simulation stepping (host-authoritative)
                if self.running:
                    delay = SPEEDS[self.speed_idx]
                    time.sleep(delay)
                    if self.mp_role == "host":
                        self._mp_sim_tick()
                continue
            elif self.mp_mode and self.mp_phase == "finished":
                self._handle_mp_finished_key(key)
                continue
            elif self.mp_mode and self.mp_phase == "lobby":
                # Lobby: only allow quit
                if key == ord("q"):
                    self._mp_exit()
                continue

            if self.puzzle_menu:
                if self._handle_puzzle_menu_key(key):
                    continue
            elif self.puzzle_mode and self.puzzle_phase == "planning":
                if self._handle_puzzle_planning_key(key):
                    continue
            elif self.puzzle_mode and self.puzzle_phase == "running":
                # Auto-step during running phase
                if key == 27:  # ESC to abort
                    self.running = False
                    self._puzzle_fail("Aborted by user.")
                elif self.running:
                    delay = SPEEDS[self.speed_idx]
                    time.sleep(delay)
                    self._puzzle_step()
                continue
            elif self.puzzle_mode and self.puzzle_phase in ("success", "fail"):
                if self._handle_puzzle_result_key(key):
                    continue
            elif self.wolfram_menu:
                if self._handle_wolfram_menu_key(key):
                    continue
            elif self.wolfram_mode:
                if self._handle_wolfram_key(key):
                    if self.wolfram_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._wolfram_step()
                    continue
            elif self.ant_menu:
                if self._handle_ant_menu_key(key):
                    continue
            elif self.ant_mode:
                if self._handle_ant_key(key):
                    if self.ant_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.ant_steps_per_frame):
                            self._ant_step()
                    continue
            elif self.ww_menu:
                if self._handle_ww_menu_key(key):
                    continue
            elif self.ww_mode:
                if self._handle_ww_key(key):
                    if self.ww_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._ww_step()
                    continue
            elif self.sand_menu:
                if self._handle_sand_menu_key(key):
                    continue
            elif self.sand_mode:
                if self._handle_sand_key(key):
                    if self.sand_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._sand_step()
                    continue
            elif self.evo_menu:
                if self._handle_evo_menu_key(key):
                    continue
            elif self.evo_mode:
                if self._handle_evo_key(key):
                    # Step evolution simulation
                    if self.running and self.evo_phase == "simulating":
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._evo_step_sim()
                    continue
            elif self.blueprint_menu:
                if self._handle_blueprint_menu_key(key):
                    continue
            elif self.blueprint_mode:
                if self._handle_blueprint_mode_key(key):
                    continue
            elif self.bookmark_menu:
                if self._handle_bookmark_menu_key(key):
                    continue
            elif self.race_rule_menu:
                if self._handle_race_rule_menu_key(key):
                    continue
            elif self.compare_rule_menu:
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
                self._update_heatmap()
                self._record_pop()
                self._check_cycle()
                if self.pattern_search_mode:
                    self._scan_patterns()
                # Step the second grid in comparison mode
                if self.compare_mode and self.grid2:
                    self.grid2.step()
                    self.pop_history2.append(self.grid2.population)
                # Step all race grids
                if self.race_mode and self.race_grids and not self.race_finished:
                    self._step_race()
                # Capture frame for GIF recording
                if self.recording:
                    self._capture_recording_frame()
                # Play sonification
                if self.sound_engine.enabled:
                    self.sound_engine.play_grid(self.grid, delay)

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
            self._update_heatmap()
            self._record_pop()
            self._check_cycle()
            if self.pattern_search_mode:
                self._scan_patterns()
            if self.compare_mode and self.grid2:
                self.grid2.step()
                self.pop_history2.append(self.grid2.population)
            if self.race_mode and self.race_grids and not self.race_finished:
                self._step_race()
            if self.recording:
                self._capture_recording_frame()
            if self.sound_engine.enabled:
                self.sound_engine.play_grid(self.grid, SPEEDS[self.speed_idx])
            return True
        if key == ord("u"):
            self.running = False
            self._rewind()
            return True
        if key == ord("["):
            self.running = False
            self._scrub_back(10)
            return True
        if key == ord("]"):
            self.running = False
            self._scrub_forward(10)
            return True
        if key == ord("b"):
            self._add_bookmark()
            return True
        if key == ord("B"):
            if self.bookmarks:
                self.bookmark_menu = True
                self.bookmark_sel = 0
            else:
                self._flash("No bookmarks yet (press b to bookmark)")
            return True
        if key == ord("+") or key == ord("="):
            # Zoom in (decrease zoom level)
            idx = ZOOM_LEVELS.index(self.zoom_level)
            if idx > 0:
                self.zoom_level = ZOOM_LEVELS[idx - 1]
            self._flash(f"Zoom: {self.zoom_level}:1" if self.zoom_level > 1 else "Zoom: 1:1 (normal)")
            return True
        if key == ord("-") or key == ord("_"):
            # Zoom out (increase zoom level)
            idx = ZOOM_LEVELS.index(self.zoom_level)
            if idx < len(ZOOM_LEVELS) - 1:
                self.zoom_level = ZOOM_LEVELS[idx + 1]
            self._flash(f"Zoom: {self.zoom_level}:1" if self.zoom_level > 1 else "Zoom: 1:1 (normal)")
            return True
        if key == ord("0"):
            self.zoom_level = 1
            self._flash("Zoom: 1:1 (normal)")
            return True
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
        if key == ord("c"):
            self.grid.clear()
            self.running = False
            self.pop_history.clear()
            self._record_pop()
            self._reset_cycle_detection()
            self.heatmap = [[0] * self.grid.cols for _ in range(self.grid.rows)]
            self.heatmap_max = 0
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
            self.heatmap = [[0] * self.grid.cols for _ in range(self.grid.rows)]
            self.heatmap_max = 0
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
        if key == ord("H"):
            self.heatmap_mode = not self.heatmap_mode
            if self.heatmap_mode:
                self._flash("Heatmap ON (shows cumulative cell activity)")
            else:
                self._flash("Heatmap OFF")
            return True
        if key == ord("I"):
            self.iso_mode = not self.iso_mode
            if self.iso_mode:
                self._flash("3D Isometric view ON (cell height = age)")
            else:
                self._flash("3D Isometric view OFF")
            return True
        if key == ord("F"):
            self.pattern_search_mode = not self.pattern_search_mode
            if self.pattern_search_mode:
                self._scan_patterns()
                n = len(self.detected_patterns)
                self._flash(f"Pattern search ON — {n} pattern{'s' if n != 1 else ''} found")
            else:
                self.detected_patterns.clear()
                self._flash("Pattern search OFF")
            return True
        if key == ord("V"):
            if self.compare_mode:
                self._exit_compare_mode()
            else:
                self._enter_compare_mode()
            return True
        if key == ord("Z"):
            if self.race_mode:
                self._exit_race_mode()
            else:
                self._enter_race_mode()
            return True
        if key == ord("W"):
            self._enter_blueprint_mode()
            return True
        if key == ord("T"):
            if self.blueprints:
                self.blueprint_menu = True
                self.blueprint_sel = 0
            else:
                self._flash("No blueprints saved yet (press W to create one)")
            return True
        if key == ord("C"):
            if self.puzzle_mode:
                self._exit_puzzle_mode()
            else:
                self._enter_puzzle_mode()
            return True
        if key == ord("E"):
            if self.evo_mode:
                self._exit_evo_mode()
            else:
                self._enter_evo_mode()
            return True
        if key == ord("G"):
            self._toggle_recording()
            return True
        if key == ord("1"):
            if self.wolfram_mode:
                self._exit_wolfram_mode()
            else:
                self._enter_wolfram_mode()
            return True
        if key == ord("2"):
            if self.ant_mode:
                self._exit_ant_mode()
            else:
                self._enter_ant_mode()
            return True
        if key == ord("3"):
            self.hex_mode = not self.hex_mode
            self.grid.hex_mode = self.hex_mode
            if self.hex_mode:
                # Switch to B2/S3,4 — a common hex life rule that produces interesting patterns
                self.grid.birth = {2}
                self.grid.survival = {3, 4}
                self._flash("Hex grid ON (6 neighbors, rule B2/S34) — press R to change rule")
            else:
                # Restore standard Conway B3/S23
                self.grid.birth = {3}
                self.grid.survival = {2, 3}
                self._flash("Hex grid OFF (8 neighbors, rule B3/S23)")
            return True
        if key == ord("4"):
            if self.ww_mode:
                self._exit_ww_mode()
            else:
                self._enter_ww_mode()
            return True
        if key == ord("5"):
            if self.sand_mode:
                self._exit_sand_mode()
            else:
                self._enter_sand_mode()
            return True
        if key == ord("M"):
            on = self.sound_engine.toggle()
            if on:
                if self.sound_engine._play_cmd is None:
                    self.sound_engine.enabled = False
                    self._flash("Sound OFF — no audio player found (need aplay/paplay/afplay)")
                else:
                    self._flash("♪ Sound ON (pentatonic synth)")
            else:
                self._flash("Sound OFF")
            return True
        if key == ord("N"):
            # Multiplayer: prompt for host or connect
            choice = self._prompt_text("Multiplayer: [H]ost or [C]onnect?")
            if choice and choice.upper().startswith("H"):
                self._mp_enter_host()
            elif choice and choice.upper().startswith("C"):
                self._mp_enter_client()
            return True
        if key == ord("e"):
            self.grid.toggle(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()
            if self.pattern_search_mode:
                self._scan_patterns()
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
            if self.pattern_search_mode:
                self._scan_patterns()
        elif self.draw_mode == "erase":
            self.grid.set_dead(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()
            if self.pattern_search_mode:
                self._scan_patterns()

    def _toggle_recording(self):
        """Toggle GIF recording on/off."""
        if self.recording:
            self.recording = False
            if self.recorded_frames:
                self._export_gif()
            else:
                self._flash("Recording cancelled (no frames captured)")
        else:
            self.recording = True
            self.recorded_frames = []
            self.recording_start_gen = self.grid.generation
            self._capture_recording_frame()
            self._flash("Recording started (press G to stop & save GIF)")

    def _capture_recording_frame(self):
        """Capture the current grid state as a recording frame."""
        self.recorded_frames.append([row[:] for row in self.grid.cells])

    def _export_gif(self):
        """Export recorded frames as an animated GIF."""
        os.makedirs(SAVE_DIR, exist_ok=True)
        gen_start = self.recording_start_gen
        gen_end = self.grid.generation
        timestamp = int(time.time())
        filename = f"recording_gen{gen_start}-{gen_end}_{timestamp}.gif"
        filepath = os.path.join(SAVE_DIR, filename)
        n = len(self.recorded_frames)
        # Choose cell size: aim for reasonable image dimensions
        cell_size = 4
        # Speed-aware delay: map simulation speed to GIF frame delay
        delay_cs = max(2, int(SPEEDS[self.speed_idx] * 100))
        try:
            write_gif(filepath, self.recorded_frames,
                      cell_size=cell_size, delay_cs=delay_cs)
            self._flash(f"GIF saved: {filename} ({n} frames)")
        except OSError as e:
            self._flash(f"GIF export failed: {e}")
        self.recorded_frames = []

    def _handle_bookmark_menu_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q
            self.bookmark_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.bookmark_sel = (self.bookmark_sel - 1) % len(self.bookmarks)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.bookmark_sel = (self.bookmark_sel + 1) % len(self.bookmarks)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — jump to bookmark
            self.running = False
            self._jump_to_bookmark(self.bookmark_sel)
            self.bookmark_menu = False
            return True
        if key == ord("D") or key == curses.KEY_DC:  # D or Delete — remove bookmark
            if self.bookmarks:
                removed = self.bookmarks.pop(self.bookmark_sel)
                self._flash(f"Removed bookmark Gen {removed[0]}")
                if not self.bookmarks:
                    self.bookmark_menu = False
                else:
                    self.bookmark_sel = min(self.bookmark_sel, len(self.bookmarks) - 1)
            return True
        return True

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

    # ── 3D Isometric mode ──

    # Height tiers for isometric rendering: (max_age, pillar_chars_bottom_to_top)
    # Each pillar is drawn from bottom to top; taller pillars = older cells.
    _ISO_HEIGHT_TIERS = [
        (1,  ["█"]),                              # newborn: 1 row
        (3,  ["█", "▓"]),                         # young: 2 rows
        (8,  ["█", "▓", "▒"]),                    # mature: 3 rows
        (20, ["█", "▓", "▒", "░"]),               # old: 4 rows
    ]
    _ISO_MAX_HEIGHT = 5  # ancient: 5 rows
    _ISO_ANCIENT = ["█", "▓", "▒", "░", "·"]

    # Shade chars for the right face of the isometric column
    _ISO_SHADE_MAP = {"█": "▓", "▓": "▒", "▒": "░", "░": " ", "·": " "}

    def _iso_pillar(self, age: int) -> list[str]:
        """Return pillar characters (bottom to top) for a given cell age."""
        for max_age, chars in self._ISO_HEIGHT_TIERS:
            if age <= max_age:
                return chars
        return self._ISO_ANCIENT[:self._ISO_MAX_HEIGHT]

    def _draw_iso(self, max_y: int, max_x: int):
        """Draw the grid as a pseudo-3D isometric cityscape.

        Each living cell becomes a column whose height reflects the cell's age.
        The view uses a simple oblique projection: each grid row shifts right
        by 1 column and up by 1 row compared to the row behind it, creating
        an isometric illusion.  Taller pillars occlude shorter ones behind them.
        """
        # Reserve bottom rows for status/hint
        draw_h = max_y - 4
        draw_w = max_x - 1
        if draw_h < 5 or draw_w < 10:
            return

        # Determine how many grid cells we can fit.
        # In iso view, each cell occupies 2 screen columns.  Each successive
        # grid row shifts +1 col and -1 row on screen.  We work out a window
        # that fits in the available terminal space.
        #
        # visible grid rows  = R, visible grid cols = C
        # screen width needed  = 2*C + R   (the shift per row is +1 col)
        # screen height needed = R + max_pillar_height
        max_pillar = self._ISO_MAX_HEIGHT

        # Solve for R, C from available space
        vis_rows = min(self.grid.rows, draw_h - max_pillar)
        if vis_rows < 1:
            vis_rows = 1
        vis_cols = min(self.grid.cols, (draw_w - vis_rows) // 2)
        if vis_cols < 1:
            vis_cols = 1

        # Centre viewport on cursor
        start_r = self.cursor_r - vis_rows // 2
        start_c = self.cursor_c - vis_cols // 2

        # Build a z-buffer: screen[sy][sx] = (char, color_pair_idx, bold)
        # We'll use a dict for sparse storage
        zbuf: dict[tuple[int, int], tuple[str, int, bool]] = {}

        # We iterate grid back-to-front (painter's algorithm) so that closer
        # rows overwrite farther ones.
        for gy in range(vis_rows):
            gr = (start_r + gy) % self.grid.rows
            # Screen base position for this grid row:
            # row 0 (farthest) is at top-right; last row at bottom-left.
            base_sy = (vis_rows - 1 - gy) + max_pillar  # bottom of pillar footprint
            base_sx = gy  # iso shift: each row shifts right by 1

            for gx in range(vis_cols):
                gc = (start_c + gx) % self.grid.cols
                age = self.grid.cells[gr][gc]
                sx = base_sx + gx * 2
                is_cursor = (gr == self.cursor_r and gc == self.cursor_c)

                if age > 0:
                    pillar = self._iso_pillar(age)
                    height = len(pillar)
                    # Determine color based on age
                    if age <= 1:
                        cpair = 1   # green
                    elif age <= 3:
                        cpair = 2   # cyan
                    elif age <= 8:
                        cpair = 3   # yellow
                    elif age <= 20:
                        cpair = 4   # magenta
                    else:
                        cpair = 5   # red

                    # Draw pillar from bottom to top
                    for i, ch in enumerate(pillar):
                        sy = base_sy - i
                        if 0 <= sy < draw_h and 0 <= sx < draw_w - 1:
                            bold = is_cursor or (i == height - 1)
                            zbuf[(sy, sx)] = (ch + ch, cpair, bold)
                            # Right-face shade (1 col to the right of the 2-char cell)
                            shade_sx = sx + 2
                            shade_ch = self._ISO_SHADE_MAP.get(ch, " ")
                            if shade_ch != " " and 0 <= shade_sx < draw_w - 1:
                                # Only draw shade if nothing solid is there already
                                if (sy, shade_sx) not in zbuf:
                                    zbuf[(sy, shade_sx)] = (shade_ch + " ", cpair, False)
                else:
                    # Dead cell: draw ground marker
                    if is_cursor:
                        sy = base_sy
                        if 0 <= sy < draw_h and 0 <= sx < draw_w - 1:
                            zbuf[(sy, sx)] = ("▒▒", 6, False)
                    # else: leave empty (background)

        # Render the z-buffer to screen
        for (sy, sx), (chars, cpair, bold) in zbuf.items():
            attr = curses.color_pair(cpair)
            if bold:
                attr |= curses.A_BOLD
            try:
                self.stdscr.addstr(sy, sx, chars, attr)
            except curses.error:
                pass

        # Draw a ground line at the base
        ground_y = vis_rows + max_pillar
        if ground_y < draw_h:
            ground_str = "╌" * min(draw_w, 2 * vis_cols + vis_rows)
            try:
                self.stdscr.addstr(ground_y, 0, ground_str, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            state = "▶ PLAY" if self.running else "⏸ PAUSE"
            speed = SPEED_LABELS[self.speed_idx]
            rs = rule_string(self.grid.birth, self.grid.survival)
            mode = "  │  🏙 ISO-3D"
            if self.heatmap_mode:
                mode += "  │  🔥 HEATMAP"
            if self.sound_engine.enabled:
                mode += "  │  ♪ SOUND"
            if self.recording:
                mode += f"  │  ⏺ REC({len(self.recorded_frames)})"
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

        # Hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            else:
                hint = " [Space]=play [n]=step [I]=exit 3D [arrows]=move cursor [H]=heatmap [M]=sound [+/-]=zoom [?]=help [q]=quit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
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

    # ── Race mode ──

    def _enter_race_mode(self):
        """Open the multi-rule selection menu for race mode."""
        if self.compare_mode:
            self._exit_compare_mode()
        self.race_rule_menu = True
        self.race_rule_sel = 0
        self.race_selected_rules = []

    def _exit_race_mode(self):
        """Leave race mode and discard race grids."""
        self.race_mode = False
        self.race_grids.clear()
        self.race_pop_histories.clear()
        self.race_rule_menu = False
        self.race_selected_rules.clear()
        self.race_finished = False
        self.race_winner = None
        self.race_stats.clear()
        self.race_state_hashes.clear()
        self._flash("Race mode OFF")

    def _start_race(self):
        """Clone current grid into N grids with different rules and start the race."""
        self.race_grids = []
        self.race_pop_histories = []
        self.race_stats = []
        self.race_state_hashes = []
        for name, birth, survival in self.race_selected_rules:
            g = Grid(self.grid.rows, self.grid.cols)
            for r in range(self.grid.rows):
                for c in range(self.grid.cols):
                    g.cells[r][c] = self.grid.cells[r][c]
            g.generation = self.grid.generation
            g.population = self.grid.population
            g.birth = birth
            g.survival = survival
            self.race_grids.append(g)
            self.race_pop_histories.append([g.population])
            self.race_stats.append({
                "extinction_gen": None,
                "osc_period": None,
                "peak_pop": g.population,
            })
            self.race_state_hashes.append({g.state_hash(): g.generation})
        self.race_start_gen = self.grid.generation
        self.race_mode = True
        self.race_rule_menu = False
        self.race_finished = False
        self.race_winner = None
        n = len(self.race_selected_rules)
        self._flash(f"Race started! {n} rules competing for {self.race_max_gens} generations (Space=play, Z=exit)")

    def _step_race(self):
        """Advance all race grids by one generation and update stats."""
        gens_elapsed = 0
        for i, g in enumerate(self.race_grids):
            if self.race_stats[i]["extinction_gen"] is not None:
                # Already extinct — keep stepping but population stays 0
                self.race_pop_histories[i].append(0)
                continue
            g.step()
            pop = g.population
            self.race_pop_histories[i].append(pop)
            stats = self.race_stats[i]
            if pop > stats["peak_pop"]:
                stats["peak_pop"] = pop
            # Check extinction
            if pop == 0 and stats["extinction_gen"] is None:
                stats["extinction_gen"] = g.generation
            # Check oscillation via cycle detection
            if stats["osc_period"] is None:
                h = g.state_hash()
                hashes = self.race_state_hashes[i]
                if h in hashes:
                    stats["osc_period"] = g.generation - hashes[h]
                else:
                    hashes[h] = g.generation
            gens_elapsed = g.generation - self.race_start_gen
        # Check if race is over
        if gens_elapsed >= self.race_max_gens and not self.race_finished:
            self._finish_race()

    def _finish_race(self):
        """Determine winner based on scoring: population + survival + oscillation bonus."""
        self.race_finished = True
        self.running = False
        best_score = -1
        best_name = ""
        for i, (name, birth, survival) in enumerate(self.race_selected_rules):
            stats = self.race_stats[i]
            g = self.race_grids[i]
            # Scoring: weighted combination
            pop_score = g.population
            # Survival bonus: full marks if never went extinct
            survival_bonus = self.race_max_gens if stats["extinction_gen"] is None else stats["extinction_gen"] - self.race_start_gen
            # Oscillation bonus: detecting a cycle is interesting
            osc_bonus = 50 if stats["osc_period"] is not None and stats["osc_period"] > 1 else 0
            # Peak population bonus
            peak_bonus = stats["peak_pop"] // 2
            score = pop_score + survival_bonus + osc_bonus + peak_bonus
            stats["final_score"] = score
            rs = rule_string(birth, survival)
            if score > best_score:
                best_score = score
                best_name = f"{name} ({rs})"
        self.race_winner = best_name
        self._flash(f"Race complete! Winner: {best_name}")

    def _handle_race_rule_menu_key(self, key: int) -> bool:
        """Handle input in the race rule selection menu."""
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q — cancel
            self.race_rule_menu = False
            self.race_selected_rules.clear()
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.race_rule_sel = (self.race_rule_sel - 1) % len(self.rule_preset_list)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.race_rule_sel = (self.race_rule_sel + 1) % len(self.rule_preset_list)
            return True
        if key == ord(" "):  # Space to toggle selection
            name = self.rule_preset_list[self.race_rule_sel]
            preset = RULE_PRESETS[name]
            # Check if already selected — toggle off
            existing = [i for i, (n, b, s) in enumerate(self.race_selected_rules) if n == name]
            if existing:
                self.race_selected_rules.pop(existing[0])
            elif len(self.race_selected_rules) < 4:
                self.race_selected_rules.append((name, set(preset["birth"]), set(preset["survival"])))
            else:
                self._flash("Max 4 rules — deselect one first")
            return True
        if key == ord("/"):  # Custom rule entry
            if len(self.race_selected_rules) >= 4:
                self._flash("Max 4 rules — deselect one first")
                return True
            rs = self._prompt_text("Custom rule (e.g. B36/S23)")
            if rs:
                parsed = parse_rule_string(rs)
                if parsed:
                    self.race_selected_rules.append((rs, parsed[0], parsed[1]))
                else:
                    self._flash("Invalid rule string (use format B.../S...)")
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — start race
            if len(self.race_selected_rules) < 2:
                self._flash("Select at least 2 rules (Space=toggle, /=custom)")
                return True
            self._start_race()
            return True
        if key == ord("g"):  # Change max generations
            gs = self._prompt_text(f"Race duration in generations (current: {self.race_max_gens})")
            if gs:
                try:
                    val = int(gs)
                    if 10 <= val <= 10000:
                        self.race_max_gens = val
                    else:
                        self._flash("Must be between 10 and 10000")
                except ValueError:
                    self._flash("Invalid number")
            return True
        return True

    def _draw_race_rule_menu(self, max_y: int, max_x: int):
        """Draw the multi-select rule menu for race mode."""
        title = "── Race Mode: Select 2-4 Rules (Space=toggle, Enter=start, /=custom, g=gens, q=cancel) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        sel_names = {n for n, b, s in self.race_selected_rules}
        info = f"Selected: {len(self.race_selected_rules)}/4  │  Duration: {self.race_max_gens} gens"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(info)) // 2), info,
                               curses.color_pair(6))
        except curses.error:
            pass

        for i, name in enumerate(self.rule_preset_list):
            y = 5 + i
            if y >= max_y - 2:
                break
            preset = RULE_PRESETS[name]
            rs = rule_string(preset["birth"], preset["survival"])
            check = "[X]" if name in sel_names else "[ ]"
            line = f"  {check} {name:<20s} {rs}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.race_rule_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass

        # Show custom rules if any
        custom_y = 5 + len(self.rule_preset_list) + 1
        for i, (name, birth, survival) in enumerate(self.race_selected_rules):
            if name not in RULE_PRESETS:
                if custom_y < max_y - 2:
                    rs = rule_string(birth, survival)
                    line = f"  [X] {rs:<20s} (custom)"
                    try:
                        self.stdscr.addstr(custom_y, 2, line[:max_x - 2],
                                           curses.color_pair(3))
                    except curses.error:
                        pass
                    custom_y += 1

        tip_y = max_y - 1
        if tip_y > 0:
            tip = " Space=toggle selection │ /=custom rule │ g=set duration │ Enter=start race │ q/Esc=cancel"
            try:
                self.stdscr.addstr(tip_y, 0, tip[:max_x - 1],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_race(self, max_y: int, max_x: int):
        """Draw the race mode view with tiled sub-grids and scoreboard."""
        n = len(self.race_grids)
        if n == 0:
            return

        # Layout: 2 columns, 1-2 rows depending on count
        # n=2: 1 row, 2 cols  |  n=3: 2 rows (2+1)  |  n=4: 2 rows, 2 cols
        if n <= 2:
            tile_rows, tile_cols = 1, n
        else:
            tile_rows, tile_cols = 2, 2

        scoreboard_h = n + 3  # header + n entries + separator + winner line
        grid_area_h = max_y - scoreboard_h - 1
        grid_area_w = max_x

        if grid_area_h < 4 or grid_area_w < 10:
            try:
                self.stdscr.addstr(0, 0, "Terminal too small for race mode", curses.color_pair(5))
            except curses.error:
                pass
            return

        # Each tile dimensions (in screen coords)
        tile_h = grid_area_h // tile_rows
        tile_w = grid_area_w // tile_cols

        # Draw each grid tile
        for idx in range(n):
            tr = idx // tile_cols  # tile row
            tc = idx % tile_cols   # tile column
            origin_y = tr * tile_h
            origin_x = tc * tile_w
            cell_vis_rows = tile_h - 2  # leave room for label
            cell_vis_cols = (tile_w - 1) // 2  # each cell = 2 screen cols

            g = self.race_grids[idx]
            name, birth, survival = self.race_selected_rules[idx]
            rs = rule_string(birth, survival)

            # Draw label bar at top of tile
            stats = self.race_stats[idx]
            label = f" {name} ({rs}) Pop:{g.population}"
            if stats.get("extinction_gen") is not None:
                label += " EXTINCT"
            elif stats.get("osc_period") is not None:
                label += f" Osc:{stats['osc_period']}"
            label = label[:tile_w - 1]
            # Color the label: winner gets special highlight
            label_attr = curses.color_pair(7) | curses.A_BOLD
            if self.race_finished and self.race_winner and name in self.race_winner:
                label_attr = curses.color_pair(3) | curses.A_BOLD
            try:
                self.stdscr.addstr(origin_y, origin_x, label, label_attr)
            except curses.error:
                pass

            # Draw cells
            view_r = self.cursor_r - cell_vis_rows // 2
            view_c = self.cursor_c - cell_vis_cols // 2
            for sy in range(min(cell_vis_rows, g.rows)):
                gr = (view_r + sy) % g.rows
                for sx in range(min(cell_vis_cols, g.cols)):
                    gc = (view_c + sx) % g.cols
                    age = g.cells[gr][gc]
                    px = origin_x + sx * 2
                    py = origin_y + 1 + sy
                    if py >= origin_y + tile_h - 1 or px + 1 >= origin_x + tile_w:
                        continue
                    if py >= grid_area_h or px + 1 >= max_x:
                        continue
                    if age > 0:
                        try:
                            self.stdscr.addstr(py, px, CELL_CHAR, color_for_age(age))
                        except curses.error:
                            pass

            # Draw tile border (right edge) if not last column
            if tc < tile_cols - 1:
                border_x = origin_x + tile_w - 1
                if border_x < max_x:
                    for sy in range(tile_h):
                        py = origin_y + sy
                        if py < grid_area_h:
                            try:
                                self.stdscr.addstr(py, border_x, "│",
                                                   curses.color_pair(6) | curses.A_DIM)
                            except curses.error:
                                pass

            # Draw tile border (bottom edge) if not last row
            if tr < tile_rows - 1:
                border_y = origin_y + tile_h - 1
                if border_y < grid_area_h:
                    for sx in range(tile_w):
                        px = origin_x + sx
                        if px < max_x:
                            try:
                                self.stdscr.addstr(border_y, px, "─",
                                                   curses.color_pair(6) | curses.A_DIM)
                            except curses.error:
                                pass

        # Draw scoreboard at bottom
        sb_y = grid_area_h
        gens_elapsed = 0
        if self.race_grids:
            gens_elapsed = self.race_grids[0].generation - self.race_start_gen

        # Progress bar
        progress = min(1.0, gens_elapsed / max(1, self.race_max_gens))
        bar_w = max_x - 30
        if bar_w > 5:
            filled = int(bar_w * progress)
            bar = "█" * filled + "░" * (bar_w - filled)
            progress_line = f" Gen {gens_elapsed}/{self.race_max_gens} [{bar}] {int(progress * 100)}%"
            progress_line = progress_line[:max_x - 1]
            try:
                self.stdscr.addstr(sb_y, 0, progress_line,
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Scoreboard header
        sb_y += 1
        header = f" {'#':<3s} {'Rule':<25s} {'Pop':>7s} {'Peak':>7s} {'Osc':>6s} {'Extinct':>8s} {'Score':>7s}"
        header = header[:max_x - 1]
        if sb_y < max_y:
            try:
                self.stdscr.addstr(sb_y, 0, header,
                                   curses.color_pair(6) | curses.A_BOLD)
            except curses.error:
                pass

        # Scoreboard entries (sorted by score if finished, else by population)
        entries = []
        for i, (name, birth, survival) in enumerate(self.race_selected_rules):
            stats = self.race_stats[i]
            g = self.race_grids[i]
            rs = rule_string(birth, survival)
            score = stats.get("final_score", 0)
            entries.append((i, name, rs, g.population, stats))

        if self.race_finished:
            entries.sort(key=lambda e: e[4].get("final_score", 0), reverse=True)
        else:
            entries.sort(key=lambda e: e[3], reverse=True)

        for rank, (i, name, rs, pop, stats) in enumerate(entries):
            sb_y += 1
            if sb_y >= max_y - 1:
                break
            osc = str(stats["osc_period"]) if stats["osc_period"] is not None else "—"
            ext = str(stats["extinction_gen"] - self.race_start_gen) if stats["extinction_gen"] is not None else "alive"
            score_str = str(stats.get("final_score", "—")) if self.race_finished else "—"
            display_name = f"{name[:15]} {rs}"
            medal = ""
            if self.race_finished and rank == 0:
                medal = "👑 "
            line = f" {medal}{rank+1:<3d} {display_name:<25s} {pop:>7d} {stats['peak_pop']:>7d} {osc:>6s} {ext:>8s} {score_str:>7s}"
            line = line[:max_x - 1]
            attr = curses.color_pair(6)
            if self.race_finished and rank == 0:
                attr = curses.color_pair(3) | curses.A_BOLD
            elif stats["extinction_gen"] is not None:
                attr = curses.color_pair(5) | curses.A_DIM
            try:
                self.stdscr.addstr(sb_y, 0, line, attr)
            except curses.error:
                pass

        # Hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            elif self.race_finished:
                hint = " Race complete! [Space]=restart [Z]=exit race [q]=quit"
            else:
                hint = " [Space]=play/pause [n]=step [+/-]=speed [Z]=exit race [Arrows]=scroll [q]=quit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Genetic Algorithm Evolution mode ──

    def _enter_evo_mode(self):
        """Open the evolution mode settings menu."""
        if self.compare_mode:
            self._exit_compare_mode()
        if self.race_mode:
            self._exit_race_mode()
        self.evo_menu = True
        self.evo_menu_sel = 0

    def _exit_evo_mode(self):
        """Leave evolution mode entirely."""
        self.evo_mode = False
        self.evo_menu = False
        self.evo_phase = "idle"
        self.evo_grids.clear()
        self.evo_rules.clear()
        self.evo_fitness.clear()
        self.evo_pop_histories.clear()
        self.evo_generation = 0
        self.evo_sim_step = 0
        self.evo_sel = 0
        self.evo_history.clear()
        self.evo_best_ever = None
        self._flash("Evolution mode OFF")

    def _evo_random_rule(self) -> tuple[set, set]:
        """Generate a random B/S ruleset."""
        birth = {d for d in range(9) if random.random() < 0.3}
        survival = {d for d in range(9) if random.random() < 0.3}
        # Ensure at least one birth and one survival digit
        if not birth:
            birth.add(random.randint(1, 5))
        if not survival:
            survival.add(random.randint(2, 4))
        return birth, survival

    def _evo_mutate(self, birth: set, survival: set) -> tuple[set, set]:
        """Mutate a ruleset by flipping individual digits."""
        new_birth = set(birth)
        new_survival = set(survival)
        for d in range(9):
            if random.random() < self.evo_mutation_rate:
                if d in new_birth:
                    new_birth.discard(d)
                else:
                    new_birth.add(d)
            if random.random() < self.evo_mutation_rate:
                if d in new_survival:
                    new_survival.discard(d)
                else:
                    new_survival.add(d)
        # Ensure at least one birth digit
        if not new_birth:
            new_birth.add(random.randint(1, 5))
        return new_birth, new_survival

    def _evo_crossover(self, parent1: tuple[set, set], parent2: tuple[set, set]) -> tuple[set, set]:
        """Single-point crossover between two rulesets."""
        b1, s1 = parent1
        b2, s2 = parent2
        # For each digit, pick from either parent
        child_birth = set()
        child_survival = set()
        for d in range(9):
            child_birth.add(d) if (d in (b1 if random.random() < 0.5 else b2)) else None
            child_survival.add(d) if (d in (s1 if random.random() < 0.5 else s2)) else None
        if not child_birth:
            child_birth.add(random.randint(1, 5))
        return child_birth, child_survival

    def _evo_init_population(self):
        """Create initial random population and start simulation."""
        self.evo_grids = []
        self.evo_rules = []
        self.evo_fitness = []
        self.evo_pop_histories = []
        self.evo_sim_step = 0
        self.evo_generation += 1

        # If we have previous elite, breed from them; otherwise random
        if self.evo_history and len(self.evo_history[-1].get("elite_rules", [])) >= 2:
            elite_rules = self.evo_history[-1]["elite_rules"]
            new_rules = list(elite_rules)  # keep elites
            while len(new_rules) < self.evo_pop_size:
                # Crossover two random elites + mutate
                p1 = random.choice(elite_rules)
                p2 = random.choice(elite_rules)
                child = self._evo_crossover(p1, p2)
                child = self._evo_mutate(child[0], child[1])
                new_rules.append(child)
        else:
            new_rules = [self._evo_random_rule() for _ in range(self.evo_pop_size)]

        # Create a small grid for each individual with random initial state
        sub_rows = 30
        sub_cols = 40
        for birth, survival in new_rules:
            g = Grid(sub_rows, sub_cols)
            g.birth = set(birth)
            g.survival = set(survival)
            # Random 20% fill
            for r in range(sub_rows):
                for c in range(sub_cols):
                    if random.random() < 0.2:
                        g.set_alive(r, c)
            self.evo_grids.append(g)
            self.evo_rules.append((set(birth), set(survival)))
            self.evo_pop_histories.append([g.population])
            self.evo_fitness.append({})

        self.evo_phase = "simulating"
        self.running = True

    def _evo_step_sim(self):
        """Advance all evolution grids by one step."""
        if self.evo_phase != "simulating":
            return
        self.evo_sim_step += 1
        for i, g in enumerate(self.evo_grids):
            g.step()
            self.evo_pop_histories[i].append(g.population)

        if self.evo_sim_step >= self.evo_grid_gens:
            self._evo_score_all()

    def _evo_score_all(self):
        """Compute fitness for all individuals."""
        self.evo_phase = "scored"
        self.running = False
        for i, g in enumerate(self.evo_grids):
            hist = self.evo_pop_histories[i]
            self.evo_fitness[i] = self._evo_compute_fitness(g, hist)

        # Sort by fitness score (best first)
        order = sorted(range(len(self.evo_fitness)),
                       key=lambda i: self.evo_fitness[i].get("total", 0), reverse=True)
        self.evo_grids = [self.evo_grids[i] for i in order]
        self.evo_rules = [self.evo_rules[i] for i in order]
        self.evo_fitness = [self.evo_fitness[i] for i in order]
        self.evo_pop_histories = [self.evo_pop_histories[i] for i in order]

        # Track best ever
        best = self.evo_fitness[0]
        if self.evo_best_ever is None or best.get("total", 0) > self.evo_best_ever.get("total", 0):
            self.evo_best_ever = dict(best)
            self.evo_best_ever["rule"] = rule_string(self.evo_rules[0][0], self.evo_rules[0][1])
            self.evo_best_ever["gen"] = self.evo_generation

        # Record elite rules for next generation
        elite_count = min(self.evo_elite_count, len(self.evo_rules))
        elite_rules = [self.evo_rules[i] for i in range(elite_count)]
        self.evo_history.append({
            "generation": self.evo_generation,
            "best_score": best.get("total", 0),
            "best_rule": rule_string(self.evo_rules[0][0], self.evo_rules[0][1]),
            "avg_score": sum(f.get("total", 0) for f in self.evo_fitness) / max(1, len(self.evo_fitness)),
            "elite_rules": elite_rules,
        })
        self.evo_sel = 0
        self._flash(f"Gen {self.evo_generation} scored! Best: {rule_string(self.evo_rules[0][0], self.evo_rules[0][1])} ({best.get('total', 0):.0f}pts)")

    def _evo_compute_fitness(self, g: Grid, hist: list[int]) -> dict:
        """Compute fitness score for a single individual."""
        if not hist:
            return {"total": 0, "longevity": 0, "stability": 0, "diversity": 0, "population": 0}

        # Longevity: how many gens stayed alive (non-zero population)
        alive_gens = sum(1 for p in hist if p > 0)
        longevity = alive_gens

        # Population score: average population (normalized)
        avg_pop = sum(hist) / len(hist) if hist else 0
        pop_score = min(avg_pop, 200)  # cap at 200

        # Stability: low variance = more stable
        if len(hist) > 1 and avg_pop > 0:
            variance = sum((p - avg_pop) ** 2 for p in hist) / len(hist)
            std = variance ** 0.5
            # Low std relative to mean = more stable
            cv = std / max(avg_pop, 1)  # coefficient of variation
            stability = max(0, 100 - cv * 100)
        else:
            stability = 0

        # Diversity: count distinct population values (pattern richness)
        unique_pops = len(set(hist[-100:]))  # last 100 gens
        diversity = min(unique_pops * 2, 100)

        # Weight based on fitness mode
        if self.evo_fitness_mode == "longevity":
            total = longevity * 3 + pop_score * 0.5 + stability * 0.5 + diversity * 0.5
        elif self.evo_fitness_mode == "diversity":
            total = diversity * 3 + longevity * 0.5 + pop_score * 0.5 + stability * 0.5
        elif self.evo_fitness_mode == "population":
            total = pop_score * 3 + longevity * 0.5 + stability * 0.5 + diversity * 0.5
        else:  # balanced
            total = longevity + pop_score + stability + diversity

        return {
            "total": total,
            "longevity": longevity,
            "stability": stability,
            "diversity": diversity,
            "population": pop_score,
        }

    def _evo_next_generation(self):
        """Breed the next generation from current elite."""
        self._evo_init_population()

    def _evo_adopt_rule(self):
        """Adopt the selected evolved ruleset into the main simulator."""
        if not self.evo_rules:
            return
        idx = self.evo_sel
        birth, survival = self.evo_rules[idx]
        self.grid.birth = set(birth)
        self.grid.survival = set(survival)
        rs = rule_string(birth, survival)
        self._exit_evo_mode()
        self._flash(f"Adopted evolved rule: {rs}")

    def _handle_evo_menu_key(self, key: int) -> bool:
        """Handle input in the evolution settings menu."""
        if key == -1:
            return True
        if key == 27 or key == ord("q"):
            self.evo_menu = False
            return True
        menu_items = ["pop_size", "grid_gens", "mutation_rate", "elite_count", "fitness_mode", "start"]
        if key in (curses.KEY_UP, ord("k")):
            self.evo_menu_sel = (self.evo_menu_sel - 1) % len(menu_items)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.evo_menu_sel = (self.evo_menu_sel + 1) % len(menu_items)
            return True
        if key in (10, 13, curses.KEY_ENTER, ord(" ")):
            item = menu_items[self.evo_menu_sel]
            if item == "start":
                self.evo_menu = False
                self.evo_mode = True
                self.evo_generation = 0
                self.evo_history.clear()
                self.evo_best_ever = None
                self._evo_init_population()
                return True
            if item == "pop_size":
                val = self._prompt_text(f"Population size (current: {self.evo_pop_size})")
                if val:
                    try:
                        n = int(val)
                        if 4 <= n <= 24:
                            self.evo_pop_size = n
                        else:
                            self._flash("Must be 4-24")
                    except ValueError:
                        self._flash("Invalid number")
            elif item == "grid_gens":
                val = self._prompt_text(f"Simulation generations (current: {self.evo_grid_gens})")
                if val:
                    try:
                        n = int(val)
                        if 50 <= n <= 2000:
                            self.evo_grid_gens = n
                        else:
                            self._flash("Must be 50-2000")
                    except ValueError:
                        self._flash("Invalid number")
            elif item == "mutation_rate":
                val = self._prompt_text(f"Mutation rate 0-100% (current: {int(self.evo_mutation_rate * 100)}%)")
                if val:
                    try:
                        n = int(val.replace("%", ""))
                        if 0 <= n <= 100:
                            self.evo_mutation_rate = n / 100.0
                        else:
                            self._flash("Must be 0-100")
                    except ValueError:
                        self._flash("Invalid number")
            elif item == "elite_count":
                val = self._prompt_text(f"Elite survivors (current: {self.evo_elite_count})")
                if val:
                    try:
                        n = int(val)
                        if 2 <= n <= self.evo_pop_size // 2:
                            self.evo_elite_count = n
                        else:
                            self._flash(f"Must be 2-{self.evo_pop_size // 2}")
                    except ValueError:
                        self._flash("Invalid number")
            elif item == "fitness_mode":
                modes = ["balanced", "longevity", "diversity", "population"]
                idx = modes.index(self.evo_fitness_mode)
                self.evo_fitness_mode = modes[(idx + 1) % len(modes)]
            return True
        return True

    def _handle_evo_key(self, key: int) -> bool:
        """Handle input during active evolution mode."""
        if key == -1:
            return True
        if key == 27 or key == ord("q"):
            self._exit_evo_mode()
            return True
        if key == ord(" "):
            if self.evo_phase == "scored":
                # Start next generation
                self._evo_next_generation()
            else:
                self.running = not self.running
                self._flash("Playing" if self.running else "Paused")
            return True
        if key == ord("n"):
            if self.evo_phase == "simulating":
                self.running = False
                self._evo_step_sim()
            elif self.evo_phase == "scored":
                self._evo_next_generation()
            return True
        if key == ord("a"):
            if self.evo_phase == "scored" and self.evo_rules:
                self._evo_adopt_rule()
            return True
        if key in (curses.KEY_UP, ord("k")):
            if self.evo_phase == "scored" and self.evo_rules:
                self.evo_sel = (self.evo_sel - 1) % len(self.evo_rules)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            if self.evo_phase == "scored" and self.evo_rules:
                self.evo_sel = (self.evo_sel + 1) % len(self.evo_rules)
            return True
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
        if key == ord("f"):
            # Cycle fitness mode
            modes = ["balanced", "longevity", "diversity", "population"]
            idx = modes.index(self.evo_fitness_mode)
            self.evo_fitness_mode = modes[(idx + 1) % len(modes)]
            self._flash(f"Fitness: {self.evo_fitness_mode}")
            return True
        if key == ord("m"):
            # Adjust mutation rate interactively
            val = self._prompt_text(f"Mutation rate 0-100% (current: {int(self.evo_mutation_rate * 100)}%)")
            if val:
                try:
                    n = int(val.replace("%", ""))
                    if 0 <= n <= 100:
                        self.evo_mutation_rate = n / 100.0
                        self._flash(f"Mutation: {int(self.evo_mutation_rate * 100)}%")
                except ValueError:
                    self._flash("Invalid number")
            return True
        if key == ord("s"):
            # Skip to end of simulation
            if self.evo_phase == "simulating":
                while self.evo_sim_step < self.evo_grid_gens:
                    self.evo_sim_step += 1
                    for i, g in enumerate(self.evo_grids):
                        g.step()
                        self.evo_pop_histories[i].append(g.population)
                self._evo_score_all()
            return True
        return True

    def _draw_evo_menu(self, max_y: int, max_x: int):
        """Draw the evolution mode settings menu."""
        title = "── Evolution Mode: Genetic Algorithm Settings ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        desc = "Breed Life-like rulesets through natural selection"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(desc)) // 2), desc,
                               curses.color_pair(6))
        except curses.error:
            pass

        items = [
            ("Population Size", str(self.evo_pop_size), "Number of competing rulesets (4-24)"),
            ("Sim Generations", str(self.evo_grid_gens), "Generations to simulate each ruleset (50-2000)"),
            ("Mutation Rate", f"{int(self.evo_mutation_rate * 100)}%", "Chance of flipping each rule digit"),
            ("Elite Survivors", str(self.evo_elite_count), "Top performers that reproduce"),
            ("Fitness Criteria", self.evo_fitness_mode, "balanced / longevity / diversity / population"),
            (">>> START EVOLUTION <<<", "", "Begin breeding rulesets!"),
        ]

        for i, (label, value, hint) in enumerate(items):
            y = 5 + i * 2
            if y >= max_y - 2:
                break
            if i == len(items) - 1:
                # Start button
                line = f"  {label}"
                attr = curses.color_pair(3) | curses.A_BOLD
                if i == self.evo_menu_sel:
                    attr = curses.color_pair(3) | curses.A_BOLD | curses.A_REVERSE
            else:
                line = f"  {label:<20s} {value:<12s} {hint}"
                attr = curses.color_pair(6)
                if i == self.evo_menu_sel:
                    attr = curses.color_pair(7) | curses.A_REVERSE
            line = line[:max_x - 2]
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass

        tip_y = max_y - 1
        if tip_y > 0:
            tip = " Up/Down=navigate │ Enter/Space=edit/toggle │ q/Esc=cancel"
            try:
                self.stdscr.addstr(tip_y, 0, tip[:max_x - 1],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_evo(self, max_y: int, max_x: int):
        """Draw the evolution mode view with tiled sub-grids and fitness scoreboard."""
        n = len(self.evo_grids)
        if n == 0:
            return

        # Compute tile layout: roughly square arrangement
        tile_cols = int(math.ceil(math.sqrt(n)))
        tile_rows = int(math.ceil(n / tile_cols))

        # Reserve space for scoreboard at bottom
        scoreboard_lines = min(n + 4, max_y // 3)
        grid_area_h = max_y - scoreboard_lines
        grid_area_w = max_x

        if grid_area_h < 4 or grid_area_w < 10:
            try:
                self.stdscr.addstr(0, 0, "Terminal too small for evolution mode", curses.color_pair(5))
            except curses.error:
                pass
            return

        tile_h = max(3, grid_area_h // tile_rows)
        tile_w = max(6, grid_area_w // tile_cols)

        # Draw each individual's grid tile
        for idx in range(n):
            tr = idx // tile_cols
            tc = idx % tile_cols
            origin_y = tr * tile_h
            origin_x = tc * tile_w

            if origin_y >= grid_area_h or origin_x >= grid_area_w:
                continue

            g = self.evo_grids[idx]
            birth, survival = self.evo_rules[idx]
            rs = rule_string(birth, survival)

            # Label bar
            label = f" {rs} P:{g.population}"
            if self.evo_phase == "scored":
                score = self.evo_fitness[idx].get("total", 0)
                label = f" {rs} {score:.0f}pts"
            label = label[:tile_w - 1]

            label_attr = curses.color_pair(6) | curses.A_BOLD
            if self.evo_phase == "scored" and idx == 0:
                label_attr = curses.color_pair(3) | curses.A_BOLD
            if self.evo_phase == "scored" and idx == self.evo_sel:
                label_attr = curses.color_pair(7) | curses.A_REVERSE | curses.A_BOLD
            try:
                self.stdscr.addstr(origin_y, origin_x, label, label_attr)
            except curses.error:
                pass

            # Draw cells using density rendering for small tiles
            cell_vis_rows = tile_h - 1
            cell_vis_cols = (tile_w - 1) // 2

            for sy in range(min(cell_vis_rows, g.rows)):
                for sx in range(min(cell_vis_cols, g.cols)):
                    age = g.cells[sy][sx]
                    px = origin_x + sx * 2
                    py = origin_y + 1 + sy
                    if py >= origin_y + tile_h or px + 1 >= origin_x + tile_w:
                        continue
                    if py >= grid_area_h or px + 1 >= max_x:
                        continue
                    if age > 0:
                        try:
                            self.stdscr.addstr(py, px, CELL_CHAR, color_for_age(age))
                        except curses.error:
                            pass

            # Tile borders
            if tc < tile_cols - 1:
                border_x = origin_x + tile_w - 1
                if border_x < max_x:
                    for sy in range(tile_h):
                        py = origin_y + sy
                        if py < grid_area_h:
                            try:
                                self.stdscr.addstr(py, border_x, "│",
                                                   curses.color_pair(6) | curses.A_DIM)
                            except curses.error:
                                pass

        # ── Scoreboard / status area ──
        sb_y = grid_area_h

        # Header line with generation info
        progress = min(1.0, self.evo_sim_step / max(1, self.evo_grid_gens))
        if self.evo_phase == "simulating":
            bar_w = max(5, max_x - 50)
            filled = int(bar_w * progress)
            bar = "█" * filled + "░" * (bar_w - filled)
            status = f" GA Gen {self.evo_generation} │ Sim {self.evo_sim_step}/{self.evo_grid_gens} [{bar}] {int(progress * 100)}%"
        elif self.evo_phase == "scored":
            status = f" GA Gen {self.evo_generation} │ SCORED │ Fitness: {self.evo_fitness_mode} │ Mutation: {int(self.evo_mutation_rate * 100)}%"
        else:
            status = f" GA Gen {self.evo_generation}"
        status = status[:max_x - 1]
        if sb_y < max_y:
            try:
                self.stdscr.addstr(sb_y, 0, status,
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Scoreboard header
        sb_y += 1
        header = f" {'#':<3s} {'Rule':<18s} {'Score':>7s} {'Long':>5s} {'Stab':>5s} {'Div':>5s} {'Pop':>5s} {'Sparkline'}"
        header = header[:max_x - 1]
        if sb_y < max_y:
            try:
                self.stdscr.addstr(sb_y, 0, header,
                                   curses.color_pair(6) | curses.A_BOLD)
            except curses.error:
                pass

        # Individual entries
        for i in range(min(n, scoreboard_lines - 3)):
            sb_y += 1
            if sb_y >= max_y - 1:
                break
            birth, survival = self.evo_rules[i]
            rs = rule_string(birth, survival)
            fit = self.evo_fitness[i] if self.evo_fitness[i] else {}
            total = fit.get("total", 0)
            longevity = fit.get("longevity", 0)
            stability = fit.get("stability", 0)
            diversity = fit.get("diversity", 0)
            pop_sc = fit.get("population", 0)

            # Mini sparkline of population history
            spark = ""
            if self.evo_pop_histories[i]:
                spark_w = max(1, max_x - 55)
                spark = sparkline(self.evo_pop_histories[i], spark_w)

            medal = ""
            if self.evo_phase == "scored" and i == 0:
                medal = "★ "
            elif self.evo_phase == "scored" and i < self.evo_elite_count:
                medal = "● "

            line = f" {medal}{i+1:<3d} {rs:<18s} {total:>7.0f} {longevity:>5.0f} {stability:>5.0f} {diversity:>5.0f} {pop_sc:>5.0f} {spark}"
            line = line[:max_x - 1]

            attr = curses.color_pair(6)
            if self.evo_phase == "scored":
                if i == self.evo_sel:
                    attr = curses.color_pair(7) | curses.A_REVERSE
                elif i == 0:
                    attr = curses.color_pair(3) | curses.A_BOLD
                elif i < self.evo_elite_count:
                    attr = curses.color_pair(3)
            try:
                self.stdscr.addstr(sb_y, 0, line, attr)
            except curses.error:
                pass

        # Best ever line
        if self.evo_best_ever:
            sb_y += 1
            if sb_y < max_y - 1:
                best_line = f" Best ever: {self.evo_best_ever.get('rule', '?')} ({self.evo_best_ever.get('total', 0):.0f}pts, gen {self.evo_best_ever.get('gen', '?')})"
                best_line = best_line[:max_x - 1]
                try:
                    self.stdscr.addstr(sb_y, 0, best_line,
                                       curses.color_pair(7) | curses.A_DIM)
                except curses.error:
                    pass

        # Hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            elif self.evo_phase == "scored":
                hint = " [Space/n]=next gen [a]=adopt rule [↑↓]=select [f]=fitness mode [m]=mutation [s]=skip [q]=quit"
            else:
                hint = " [Space]=play/pause [n]=step [s]=skip to end [</>]=speed [f]=fitness [m]=mutation [q]=quit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Puzzle / Challenge mode ──

    def _enter_puzzle_mode(self):
        """Open the puzzle selection menu."""
        self.puzzle_menu = True
        self.puzzle_sel = 0
        self.puzzle_mode = False
        self.puzzle_phase = "idle"

    def _exit_puzzle_mode(self):
        """Leave puzzle mode entirely."""
        self.puzzle_mode = False
        self.puzzle_menu = False
        self.puzzle_phase = "idle"
        self.puzzle_current = None
        self.puzzle_placed_cells.clear()
        self.puzzle_state_hashes.clear()
        self.puzzle_win_gen = None
        self._flash("Puzzle mode OFF")

    def _puzzle_start_planning(self, puzzle: dict):
        """Begin the planning phase for a specific puzzle."""
        self.puzzle_current = puzzle
        self.puzzle_mode = True
        self.puzzle_menu = False
        self.puzzle_phase = "planning"
        self.puzzle_placed_cells.clear()
        self.puzzle_state_hashes.clear()
        self.puzzle_win_gen = None
        self.puzzle_sim_gen = 0
        self.puzzle_peak_pop = 0
        self.puzzle_score = 0
        self.puzzle_initial_bbox = None
        # Clear grid for a fresh start
        self.grid.clear()
        self.running = False
        self.pop_history.clear()
        self._record_pop()
        self._reset_cycle_detection()
        # Centre cursor
        self.cursor_r = self.grid.rows // 2
        self.cursor_c = self.grid.cols // 2
        self._flash(f"Puzzle: {puzzle['name']} — place cells, then press Enter to run!")

    def _puzzle_run(self):
        """Transition from planning to running phase."""
        puzzle = self.puzzle_current
        if not puzzle:
            return
        n = len(self.puzzle_placed_cells)
        if n == 0:
            self._flash("Place at least one cell before running!")
            return
        max_cells = puzzle.get("max_cells", 999)
        if n > max_cells:
            self._flash(f"Too many cells! Max {max_cells}, you placed {n}")
            return
        self.puzzle_phase = "running"
        self.puzzle_start_pop = n
        self.puzzle_sim_gen = 0
        self.puzzle_peak_pop = n
        self.puzzle_state_hashes.clear()
        self.puzzle_state_hashes[self.grid.state_hash()] = 0
        # Compute initial bounding box for escape_box puzzles
        if puzzle["type"] == "escape_box":
            rows = [r for r, c in self.puzzle_placed_cells]
            cols = [c for r, c in self.puzzle_placed_cells]
            mid_r = (min(rows) + max(rows)) // 2
            mid_c = (min(cols) + max(cols)) // 2
            half = puzzle.get("box_size", 10) // 2
            self.puzzle_initial_bbox = (mid_r - half, mid_c - half,
                                        mid_r + half, mid_c + half)
        self.running = True
        self._flash("Simulating...")

    def _puzzle_step(self):
        """Advance one generation and check win/loss conditions."""
        puzzle = self.puzzle_current
        if not puzzle or self.puzzle_phase != "running":
            return
        self.grid.step()
        self._record_pop()
        self.puzzle_sim_gen += 1
        pop = self.grid.population
        if pop > self.puzzle_peak_pop:
            self.puzzle_peak_pop = pop

        sim_gens = puzzle.get("sim_gens", 100)
        ptype = puzzle["type"]

        # Cycle detection for puzzles
        h = self.grid.state_hash()
        cycle_period = None
        if h in self.puzzle_state_hashes:
            cycle_period = self.puzzle_sim_gen - self.puzzle_state_hashes[h]
        else:
            self.puzzle_state_hashes[h] = self.puzzle_sim_gen

        # Check win conditions by puzzle type
        if ptype == "still_life":
            if cycle_period is not None and cycle_period == 1 and pop > 0:
                self._puzzle_win()
                return
            if pop == 0:
                self._puzzle_fail("All cells died — not a still life!")
                return
            if self.puzzle_sim_gen >= sim_gens:
                self._puzzle_fail("Did not stabilise into a still life in time.")
                return

        elif ptype == "oscillator":
            min_period = puzzle.get("min_period", 2)
            if cycle_period is not None and cycle_period >= min_period and pop > 0:
                self.puzzle_win_gen = self.puzzle_sim_gen
                self._puzzle_win()
                return
            if pop == 0:
                self._puzzle_fail("All cells died — not an oscillator!")
                return
            if self.puzzle_sim_gen >= sim_gens:
                if cycle_period is not None and cycle_period == 1 and pop > 0:
                    self._puzzle_fail(f"Stable still life (period 1) — need period >= {min_period}.")
                else:
                    self._puzzle_fail("Did not form an oscillator in time.")
                return

        elif ptype == "reach_population":
            target = puzzle.get("target_pop", 50)
            if pop >= target:
                self.puzzle_win_gen = self.puzzle_sim_gen
                self._puzzle_win()
                return
            if pop == 0:
                self._puzzle_fail("All cells died before reaching the target population!")
                return
            if self.puzzle_sim_gen >= sim_gens:
                self._puzzle_fail(f"Peak population {self.puzzle_peak_pop} — needed {target}.")
                return

        elif ptype == "escape_box":
            if self.puzzle_initial_bbox and pop > 0:
                min_r, min_c, max_r, max_c = self.puzzle_initial_bbox
                escaped = False
                for r in range(self.grid.rows):
                    for c in range(self.grid.cols):
                        if self.grid.cells[r][c] > 0:
                            if r < min_r or r > max_r or c < min_c or c > max_c:
                                escaped = True
                                break
                    if escaped:
                        break
                if escaped:
                    self.puzzle_win_gen = self.puzzle_sim_gen
                    self._puzzle_win()
                    return
            if pop == 0:
                self._puzzle_fail("All cells died before escaping the box!")
                return
            if self.puzzle_sim_gen >= sim_gens:
                self._puzzle_fail("Pattern did not escape the bounding box in time.")
                return

        elif ptype == "extinction":
            if pop == 0:
                self.puzzle_win_gen = self.puzzle_sim_gen
                self._puzzle_win()
                return
            if cycle_period is not None and pop > 0:
                self._puzzle_fail("Pattern stabilised — it won't go extinct!")
                return
            if self.puzzle_sim_gen >= sim_gens:
                self._puzzle_fail(f"Population still {pop} after {sim_gens} generations.")
                return

        elif ptype == "survive_gens":
            target_gens = puzzle.get("target_gens", 500)
            # Fail if extinct or still life before target
            if pop == 0:
                self._puzzle_fail(f"Went extinct at gen {self.puzzle_sim_gen} — needed {target_gens}+ active.")
                return
            if cycle_period is not None and cycle_period == 1:
                self._puzzle_fail(f"Became a still life at gen {self.puzzle_sim_gen} — needed active for {target_gens}+ gens.")
                return
            if self.puzzle_sim_gen >= target_gens:
                self._puzzle_win()
                return
            if self.puzzle_sim_gen >= sim_gens:
                self._puzzle_fail(f"Simulation ended. Pattern didn't stay active long enough.")
                return

    def _puzzle_win(self):
        """Handle a puzzle win."""
        self.running = False
        self.puzzle_phase = "success"
        puzzle = self.puzzle_current
        # Score: fewer cells = better, bonus for fewer generations to win
        cells_used = len(self.puzzle_placed_cells)
        max_cells = puzzle.get("max_cells", cells_used)
        # Base score: 100 * (max_cells / cells_used), clamped
        if cells_used > 0:
            cell_bonus = int(100 * max_cells / cells_used)
        else:
            cell_bonus = 100
        # Speed bonus: for types where winning fast matters
        gen_bonus = 0
        if self.puzzle_win_gen is not None:
            sim_gens = puzzle.get("sim_gens", 100)
            remaining = sim_gens - self.puzzle_win_gen
            gen_bonus = int(50 * remaining / max(1, sim_gens))
        self.puzzle_score = min(999, cell_bonus + gen_bonus)
        # Track best score
        pid = puzzle["id"]
        if pid not in self.puzzle_scores or self.puzzle_score > self.puzzle_scores[pid]:
            self.puzzle_scores[pid] = self.puzzle_score
        self._flash(f"PUZZLE SOLVED! Score: {self.puzzle_score} ({cells_used} cells used)")

    def _puzzle_fail(self, reason: str):
        """Handle a puzzle failure."""
        self.running = False
        self.puzzle_phase = "fail"
        self.puzzle_score = 0
        self._flash(f"FAILED: {reason}")

    def _handle_puzzle_menu_key(self, key: int) -> bool:
        """Handle input in the puzzle selection menu."""
        if key == -1:
            return True
        if key == 27 or key == ord("q"):
            self.puzzle_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.puzzle_sel = (self.puzzle_sel - 1) % len(PUZZLES)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.puzzle_sel = (self.puzzle_sel + 1) % len(PUZZLES)
            return True
        if key in (10, 13, curses.KEY_ENTER):
            self._puzzle_start_planning(PUZZLES[self.puzzle_sel])
            return True
        return True

    def _handle_puzzle_planning_key(self, key: int) -> bool:
        """Handle input during puzzle planning phase (place cells)."""
        if key == -1:
            return True
        puzzle = self.puzzle_current
        if not puzzle:
            return True
        max_cells = puzzle.get("max_cells", 999)

        if key == 27:  # ESC — exit puzzle
            self._exit_puzzle_mode()
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — run simulation
            self._puzzle_run()
            return True
        if key == ord("e"):  # Toggle cell
            pos = (self.cursor_r, self.cursor_c)
            if pos in self.puzzle_placed_cells:
                self.grid.set_dead(self.cursor_r, self.cursor_c)
                self.puzzle_placed_cells.discard(pos)
            else:
                if len(self.puzzle_placed_cells) >= max_cells:
                    self._flash(f"Max {max_cells} cells! Remove some first.")
                else:
                    self.grid.set_alive(self.cursor_r, self.cursor_c)
                    self.puzzle_placed_cells.add(pos)
            return True
        if key == ord("d"):  # Draw mode
            if self.draw_mode == "draw":
                self.draw_mode = None
                self._flash("Draw mode OFF")
            else:
                self.draw_mode = "draw"
                if len(self.puzzle_placed_cells) < max_cells:
                    pos = (self.cursor_r, self.cursor_c)
                    self.grid.set_alive(self.cursor_r, self.cursor_c)
                    self.puzzle_placed_cells.add(pos)
                self._flash("Draw mode ON (move to paint)")
            return True
        if key == ord("x"):  # Erase mode
            if self.draw_mode == "erase":
                self.draw_mode = None
                self._flash("Erase mode OFF")
            else:
                self.draw_mode = "erase"
                pos = (self.cursor_r, self.cursor_c)
                self.grid.set_dead(self.cursor_r, self.cursor_c)
                self.puzzle_placed_cells.discard(pos)
                self._flash("Erase mode ON (move to erase)")
            return True
        if key == ord("c"):  # Clear all placed cells
            self.grid.clear()
            self.puzzle_placed_cells.clear()
            self._flash("Cleared all cells")
            return True
        if key == ord("?"):  # Show hint
            hint = puzzle.get("hint", "No hint available.")
            self._flash(f"Hint: {hint}")
            return True
        # Arrow / vim keys for cursor movement
        moved = False
        if key in (curses.KEY_UP, ord("k")):
            self.cursor_r = (self.cursor_r - 1) % self.grid.rows
            moved = True
        elif key in (curses.KEY_DOWN, ord("j")):
            self.cursor_r = (self.cursor_r + 1) % self.grid.rows
            moved = True
        elif key in (curses.KEY_LEFT, ord("h")):
            self.cursor_c = (self.cursor_c - 1) % self.grid.cols
            moved = True
        elif key in (curses.KEY_RIGHT, ord("l")):
            self.cursor_c = (self.cursor_c + 1) % self.grid.cols
            moved = True
        if moved and self.draw_mode:
            pos = (self.cursor_r, self.cursor_c)
            if self.draw_mode == "draw":
                if len(self.puzzle_placed_cells) < max_cells:
                    self.grid.set_alive(self.cursor_r, self.cursor_c)
                    self.puzzle_placed_cells.add(pos)
            elif self.draw_mode == "erase":
                self.grid.set_dead(self.cursor_r, self.cursor_c)
                self.puzzle_placed_cells.discard(pos)
        return True  # consume all keys in puzzle planning

    def _handle_puzzle_result_key(self, key: int) -> bool:
        """Handle input on puzzle success/fail screen."""
        if key == -1:
            return True
        if key == ord("r") or key == ord("R"):  # Retry
            self._puzzle_start_planning(self.puzzle_current)
            return True
        if key == ord("q") or key == 27:  # Quit puzzle mode
            self._exit_puzzle_mode()
            return True
        if key == ord("n") or key in (10, 13, curses.KEY_ENTER):  # Next puzzle
            idx = next((i for i, p in enumerate(PUZZLES) if p["id"] == self.puzzle_current["id"]), 0)
            if idx + 1 < len(PUZZLES):
                self._puzzle_start_planning(PUZZLES[idx + 1])
            else:
                self._flash("That was the last puzzle! Press q to exit.")
            return True
        if key == ord("l"):  # Back to puzzle list
            self._enter_puzzle_mode()
            return True
        return True

    def _draw_puzzle_menu(self, max_y: int, max_x: int):
        """Draw the puzzle selection menu."""
        title = "── Puzzle / Challenge Mode (Enter=start, q/Esc=cancel) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        subtitle = "Solve cellular automata challenges with the fewest cells possible!"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                               curses.color_pair(6))
        except curses.error:
            pass

        for i, puzzle in enumerate(PUZZLES):
            y = 5 + i
            if y >= max_y - 2:
                break
            pid = puzzle["id"]
            best = self.puzzle_scores.get(pid)
            solved_mark = f" [Best: {best}]" if best is not None else ""
            check = "+" if best is not None else " "
            line = f"  [{check}] {pid:>2d}. {puzzle['name']:<22s} {puzzle['description'][:max_x - 40]}{solved_mark}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.puzzle_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            elif best is not None:
                attr = curses.color_pair(3)
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass

        tip_y = max_y - 1
        if tip_y > 0:
            tip = " Up/Down=select │ Enter=start puzzle │ q/Esc=cancel"
            try:
                self.stdscr.addstr(tip_y, 0, tip[:max_x - 1],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_puzzle(self, max_y: int, max_x: int):
        """Draw the puzzle mode UI (planning, running, or result)."""
        puzzle = self.puzzle_current
        if not puzzle:
            return

        # Header
        phase_label = {"planning": "PLANNING", "running": "SIMULATING",
                       "success": "SOLVED!", "fail": "FAILED"}.get(self.puzzle_phase, "")
        cells_used = len(self.puzzle_placed_cells)
        max_cells = puzzle.get("max_cells", 999)
        header = f" Puzzle #{puzzle['id']}: {puzzle['name']}  │  {phase_label}  │  Cells: {cells_used}/{max_cells}"
        header = header[:max_x - 1]
        try:
            if self.puzzle_phase == "success":
                attr = curses.color_pair(3) | curses.A_BOLD
            elif self.puzzle_phase == "fail":
                attr = curses.color_pair(5) | curses.A_BOLD
            else:
                attr = curses.color_pair(7) | curses.A_BOLD
            self.stdscr.addstr(0, 0, header, attr)
        except curses.error:
            pass

        # Goal text
        goal = f" Goal: {puzzle['goal_text']}"
        goal = goal[:max_x - 1]
        try:
            self.stdscr.addstr(1, 0, goal, curses.color_pair(6))
        except curses.error:
            pass

        # Grid rendering
        grid_start_y = 2
        vis_rows = max_y - 7  # leave room for header, goal, status, hint
        vis_cols = (max_x - 1) // 2

        # Centre viewport on cursor
        self.view_r = self.cursor_r - vis_rows // 2
        self.view_c = self.cursor_c - vis_cols // 2

        # Bounding box for escape_box puzzle visualisation
        bbox = self.puzzle_initial_bbox
        if bbox is None and puzzle["type"] == "escape_box" and self.puzzle_placed_cells:
            # Preview bbox centered on placed cells during planning
            rows_p = [r for r, c in self.puzzle_placed_cells]
            cols_p = [c for r, c in self.puzzle_placed_cells]
            mid_r = (min(rows_p) + max(rows_p)) // 2
            mid_c = (min(cols_p) + max(cols_p)) // 2
            half = puzzle.get("box_size", 10) // 2
            bbox = (mid_r - half, mid_c - half, mid_r + half, mid_c + half)

        for sy in range(min(vis_rows, self.grid.rows)):
            gr = (self.view_r + sy) % self.grid.rows
            for sx in range(min(vis_cols, self.grid.cols)):
                gc = (self.view_c + sx) % self.grid.cols
                age = self.grid.cells[gr][gc]
                is_cursor = (gr == self.cursor_r and gc == self.cursor_c)
                px = sx * 2
                py = grid_start_y + sy
                if py >= max_y - 4 or px + 1 >= max_x:
                    continue
                # Draw bounding box border for escape_box
                in_bbox_border = False
                if bbox and self.puzzle_phase in ("planning", "running"):
                    br0, bc0, br1, bc1 = bbox
                    if ((gr == br0 or gr == br1) and bc0 <= gc <= bc1) or \
                       ((gc == bc0 or gc == bc1) and br0 <= gr <= br1):
                        in_bbox_border = True
                if age > 0:
                    attr = color_for_age(age)
                    if is_cursor:
                        attr |= curses.A_REVERSE
                    try:
                        self.stdscr.addstr(py, px, CELL_CHAR, attr)
                    except curses.error:
                        pass
                elif in_bbox_border:
                    try:
                        self.stdscr.addstr(py, px, "··", curses.color_pair(6) | curses.A_DIM)
                    except curses.error:
                        pass
                elif is_cursor:
                    try:
                        self.stdscr.addstr(py, px, "▒▒", curses.color_pair(6) | curses.A_DIM)
                    except curses.error:
                        pass

        # Progress / status bar
        status_y = max_y - 4
        if status_y > 0:
            if self.puzzle_phase == "running":
                sim_gens = puzzle.get("sim_gens", 100)
                progress = min(1.0, self.puzzle_sim_gen / max(1, sim_gens))
                bar_w = max_x - 40
                if bar_w > 5:
                    filled = int(bar_w * progress)
                    bar = "█" * filled + "░" * (bar_w - filled)
                    status = f" Gen {self.puzzle_sim_gen}/{sim_gens} [{bar}] Pop: {self.grid.population} Peak: {self.puzzle_peak_pop}"
                else:
                    status = f" Gen {self.puzzle_sim_gen}/{sim_gens} Pop: {self.grid.population}"
                status = status[:max_x - 1]
                try:
                    self.stdscr.addstr(status_y, 0, status, curses.color_pair(7))
                except curses.error:
                    pass
            elif self.puzzle_phase == "success":
                score_line = f" SCORE: {self.puzzle_score}  │  Cells used: {cells_used}  │  "
                if self.puzzle_win_gen is not None:
                    score_line += f"Won at gen {self.puzzle_win_gen}"
                else:
                    score_line += f"Completed in {self.puzzle_sim_gen} gens"
                best = self.puzzle_scores.get(puzzle["id"], 0)
                score_line += f"  │  Best: {best}"
                score_line = score_line[:max_x - 1]
                try:
                    self.stdscr.addstr(status_y, 0, score_line, curses.color_pair(3) | curses.A_BOLD)
                except curses.error:
                    pass
            elif self.puzzle_phase == "fail":
                fail_line = f" {self.message}" if self.message else " Failed!"
                fail_line = fail_line[:max_x - 1]
                try:
                    self.stdscr.addstr(status_y, 0, fail_line, curses.color_pair(5) | curses.A_BOLD)
                except curses.error:
                    pass

        # Sparkline
        spark_y = max_y - 3
        if spark_y > 0 and len(self.pop_history) > 1:
            spark_width = max_x - 16
            if spark_width > 0:
                spark_str = sparkline(self.pop_history, spark_width)
                label = " Pop history: "
                try:
                    self.stdscr.addstr(spark_y, 0, label, curses.color_pair(6) | curses.A_DIM)
                    self.stdscr.addstr(spark_y, len(label), spark_str, curses.color_pair(1))
                except curses.error:
                    pass

        # Status / mode bar
        mode_y = max_y - 2
        if mode_y > 0:
            mode_info = f" Gen: {self.grid.generation}  │  Pop: {self.grid.population}"
            if self.draw_mode == "draw":
                mode_info += "  │  DRAW MODE"
            elif self.draw_mode == "erase":
                mode_info += "  │  ERASE MODE"
            mode_info = mode_info[:max_x - 1]
            try:
                self.stdscr.addstr(mode_y, 0, mode_info, curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 4.0:
                hint = f" {self.message}"
            elif self.puzzle_phase == "planning":
                hint = " [e]=toggle cell [d]=draw [x]=erase [c]=clear [?]=hint [Enter]=run [Esc]=quit"
            elif self.puzzle_phase == "running":
                hint = " Simulating... [Esc]=abort"
            elif self.puzzle_phase == "success":
                hint = " [r]=retry [n/Enter]=next puzzle [l]=puzzle list [q]=quit"
            elif self.puzzle_phase == "fail":
                hint = " [r]=retry [l]=puzzle list [q]=quit"
            else:
                hint = ""
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Multiplayer mode ──

    def _mp_init_owner_grid(self):
        """Create a fresh ownership grid matching the main grid dimensions."""
        self.mp_owner = [[0] * self.grid.cols for _ in range(self.grid.rows)]

    def _mp_enter_host(self):
        """Start hosting a multiplayer game."""
        if self.mp_mode:
            self._mp_exit()
            return
        ps = self._prompt_text(f"Host on port (default {MP_DEFAULT_PORT})")
        if ps is None:
            return
        port = MP_DEFAULT_PORT
        if ps.strip():
            try:
                port = int(ps.strip())
            except ValueError:
                self._flash("Invalid port number")
                return
        net = MultiplayerNet()
        if not net.start_host(port):
            self._flash(f"Cannot bind to port {port}")
            return
        self.mp_net = net
        self.mp_mode = True
        self.mp_role = "host"
        self.mp_player = 1
        self.mp_phase = "lobby"
        self.mp_host_port = port
        self.running = False
        self._flash(f"Hosting on port {port} — waiting for opponent...")

    def _mp_enter_client(self):
        """Connect to a multiplayer host."""
        if self.mp_mode:
            self._mp_exit()
            return
        addr = self._prompt_text("Connect to (host:port or host)")
        if not addr:
            return
        if ":" in addr:
            parts = addr.rsplit(":", 1)
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                self._flash("Invalid port")
                return
        else:
            host = addr
            port = MP_DEFAULT_PORT
        net = MultiplayerNet()
        self._flash(f"Connecting to {host}:{port}...")
        self.stdscr.refresh()
        if not net.connect(host, port):
            self._flash(f"Cannot connect to {host}:{port}")
            return
        self.mp_net = net
        self.mp_mode = True
        self.mp_role = "client"
        self.mp_player = 2
        self.mp_phase = "lobby"
        self.mp_connect_addr = addr
        self.running = False
        self._flash("Connected! Waiting for game setup...")

    def _mp_exit(self):
        """Leave multiplayer mode and clean up."""
        if self.mp_net:
            self.mp_net.send({"type": "quit"})
            self.mp_net.stop()
        self.mp_mode = False
        self.mp_net = None
        self.mp_role = None
        self.mp_phase = "idle"
        self.mp_player = 0
        self.mp_owner = []
        self.mp_scores = [0, 0]
        self.mp_round = 0
        self.mp_ready = [False, False]
        self.running = False
        self._flash("Multiplayer ended")

    def _mp_start_planning(self):
        """Begin the planning phase: clear grid, set territory, start timer."""
        self.grid.clear()
        self._mp_init_owner_grid()
        self.mp_phase = "planning"
        self.mp_ready = [False, False]
        self.mp_round += 1
        self.mp_planning_deadline = time.monotonic() + MP_PLANNING_TIME
        # Centre cursor in player's half
        half = self.grid.cols // 2
        if self.mp_player == 1:
            self.cursor_c = half // 2
        else:
            self.cursor_c = half + half // 2
        self.cursor_r = self.grid.rows // 2
        self._flash(f"Round {self.mp_round} — Place cells on your side! ({MP_PLANNING_TIME}s)")

    def _mp_start_sim(self):
        """Transition from planning to simulation phase."""
        self.mp_phase = "running"
        self.mp_start_gen = self.grid.generation
        self.mp_scores = [0, 0]
        self.mp_territory_bonus = [0, 0]
        self.running = True
        self.speed_idx = 3  # 4× speed for watching
        self._flash("Simulation running! Watch your cells compete...")

    def _mp_place_cell(self, r: int, c: int, alive: bool):
        """Place or remove a cell during planning, respecting territory."""
        half = self.grid.cols // 2
        # Player 1 owns left half, Player 2 owns right half
        if self.mp_player == 1 and c >= half:
            self._flash("You can only place on the LEFT side")
            return
        if self.mp_player == 2 and c < half:
            self._flash("You can only place on the RIGHT side")
            return
        if alive:
            self.grid.set_alive(r, c)
            self.mp_owner[r][c] = self.mp_player
        else:
            self.grid.set_dead(r, c)
            self.mp_owner[r][c] = 0
        # Send placement to peer
        if self.mp_net:
            self.mp_net.send({"type": "place", "r": r, "c": c, "alive": alive,
                              "player": self.mp_player})

    def _mp_step(self):
        """Advance one generation with ownership tracking.

        New cells inherit the majority owner of their alive neighbours.
        Surviving cells keep their current owner.
        """
        rows, cols = self.grid.rows, self.grid.cols
        old_cells = self.grid.cells
        old_owner = self.mp_owner
        new_cells = [[0] * cols for _ in range(rows)]
        new_owner = [[0] * cols for _ in range(rows)]
        pop = 0
        for r in range(rows):
            for c in range(cols):
                n = self.grid._count_neighbours(r, c)
                alive = old_cells[r][c] > 0
                if alive and n in self.grid.survival:
                    new_cells[r][c] = old_cells[r][c] + 1
                    new_owner[r][c] = old_owner[r][c]
                    pop += 1
                elif not alive and n in self.grid.birth:
                    new_cells[r][c] = 1
                    pop += 1
                    # Determine owner from neighbours
                    p1 = 0
                    p2 = 0
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            if dr == 0 and dc == 0:
                                continue
                            nr = (r + dr) % rows
                            nc = (c + dc) % cols
                            if old_cells[nr][nc] > 0:
                                ow = old_owner[nr][nc]
                                if ow == 1:
                                    p1 += 1
                                elif ow == 2:
                                    p2 += 1
                    if p1 > p2:
                        new_owner[r][c] = 1
                    elif p2 > p1:
                        new_owner[r][c] = 2
                    else:
                        new_owner[r][c] = 0  # contested
        self.grid.cells = new_cells
        self.grid.generation += 1
        self.grid.population = pop
        self.mp_owner = new_owner

    def _mp_calc_scores(self):
        """Calculate scores: cells owned + bonus for cells in enemy territory."""
        s1 = s2 = 0
        b1 = b2 = 0
        half = self.grid.cols // 2
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                ow = self.mp_owner[r][c]
                if self.grid.cells[r][c] > 0:
                    if ow == 1:
                        s1 += 1
                        if c >= half:  # P1 cell in P2's territory
                            b1 += 1
                    elif ow == 2:
                        s2 += 1
                        if c < half:  # P2 cell in P1's territory
                            b2 += 1
        self.mp_scores = [s1, s2]
        self.mp_territory_bonus = [b1, b2]

    def _mp_finish(self):
        """End the simulation round and show results."""
        self.mp_phase = "finished"
        self.running = False
        self._mp_calc_scores()
        s1, s2 = self.mp_scores
        b1, b2 = self.mp_territory_bonus
        total1 = s1 + b1 * 2  # territory bonus worth double
        total2 = s2 + b2 * 2
        if total1 > total2:
            winner = "Player 1 (Blue)"
        elif total2 > total1:
            winner = "Player 2 (Red)"
        else:
            winner = "TIE"
        self._flash(f"Round over! {winner} wins!  P1:{total1} P2:{total2}")
        if self.mp_net and self.mp_role == "host":
            self.mp_net.send({"type": "finished", "scores": [s1, s2],
                              "bonus": [b1, b2]})

    def _mp_send_state(self):
        """Host sends full grid state + ownership to client."""
        if not self.mp_net or self.mp_role != "host":
            return
        cells = []
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                age = self.grid.cells[r][c]
                if age > 0:
                    cells.append((r, c, age, self.mp_owner[r][c]))
        self.mp_net.send({
            "type": "state",
            "gen": self.grid.generation,
            "cells": cells,
            "scores": self.mp_scores,
            "bonus": self.mp_territory_bonus,
        })

    def _mp_recv_state(self, msg: dict):
        """Client applies a full state update from host."""
        self.grid.generation = msg["gen"]
        self.grid.cells = [[0] * self.grid.cols for _ in range(self.grid.rows)]
        self.mp_owner = [[0] * self.grid.cols for _ in range(self.grid.rows)]
        pop = 0
        for entry in msg["cells"]:
            r, c, age, ow = entry
            if 0 <= r < self.grid.rows and 0 <= c < self.grid.cols:
                self.grid.cells[r][c] = age
                self.mp_owner[r][c] = ow
                pop += 1
        self.grid.population = pop
        if "scores" in msg:
            self.mp_scores = msg["scores"]
        if "bonus" in msg:
            self.mp_territory_bonus = msg["bonus"]

    def _mp_poll(self):
        """Process incoming network messages each frame."""
        if not self.mp_net:
            return
        for msg in self.mp_net.poll():
            mtype = msg.get("type")
            if mtype == "quit":
                self._flash("Opponent disconnected!")
                self._mp_exit()
                return
            elif mtype == "hello":
                # Client receives game config from host
                rows = msg.get("rows", self.grid.rows)
                cols = msg.get("cols", self.grid.cols)
                if rows != self.grid.rows or cols != self.grid.cols:
                    self.grid = Grid(rows, cols)
                self.mp_sim_gens = msg.get("max_gens", MP_SIM_GENS)
                # Don't start planning yet — wait for explicit start_planning
            elif mtype == "start_planning":
                self._mp_start_planning()
            elif mtype == "place":
                r, c = msg["r"], msg["c"]
                player = msg.get("player", 0)
                if msg.get("alive", True):
                    self.grid.set_alive(r, c)
                    if 0 <= r < self.grid.rows and 0 <= c < self.grid.cols:
                        self.mp_owner[r][c] = player
                else:
                    self.grid.set_dead(r, c)
                    if 0 <= r < self.grid.rows and 0 <= c < self.grid.cols:
                        self.mp_owner[r][c] = 0
            elif mtype == "ready":
                peer = 2 if self.mp_player == 1 else 1
                self.mp_ready[peer - 1] = True
                self._flash("Opponent is ready!")
                if self.mp_ready[0] and self.mp_ready[1]:
                    self._mp_start_sim()
                    if self.mp_role == "host":
                        self.mp_net.send({"type": "start_sim"})
            elif mtype == "start_sim":
                self._mp_start_sim()
            elif mtype == "state":
                self._mp_recv_state(msg)
            elif mtype == "finished":
                self.mp_phase = "finished"
                self.running = False
                if "scores" in msg:
                    self.mp_scores = msg["scores"]
                if "bonus" in msg:
                    self.mp_territory_bonus = msg["bonus"]
        # Check for disconnection
        if self.mp_net and not self.mp_net.connected and self.mp_phase != "lobby":
            self._flash("Connection lost!")
            self._mp_exit()

    def _mp_lobby_tick(self):
        """Host lobby: check if client connected, then send hello and start planning."""
        if self.mp_role == "host" and self.mp_net and self.mp_net.connected:
            self.mp_net.send({
                "type": "hello",
                "rows": self.grid.rows,
                "cols": self.grid.cols,
                "max_gens": self.mp_sim_gens,
            })
            self._mp_start_planning()
            self.mp_net.send({"type": "start_planning"})
        elif self.mp_role == "client":
            # Client waits for hello message (handled in _mp_poll)
            pass

    def _mp_planning_tick(self):
        """Check planning timer and auto-ready if expired."""
        remaining = self.mp_planning_deadline - time.monotonic()
        if remaining <= 0 and not self.mp_ready[self.mp_player - 1]:
            self._mp_set_ready()

    def _mp_set_ready(self):
        """Mark this player as ready."""
        self.mp_ready[self.mp_player - 1] = True
        if self.mp_net:
            self.mp_net.send({"type": "ready"})
        self._flash("Ready! Waiting for opponent...")
        if self.mp_ready[0] and self.mp_ready[1]:
            self._mp_start_sim()
            if self.mp_role == "host" and self.mp_net:
                self.mp_net.send({"type": "start_sim"})

    def _mp_sim_tick(self):
        """Host runs simulation step and broadcasts state."""
        if self.mp_role != "host":
            return
        self._mp_step()
        self._mp_calc_scores()
        # Broadcast every 3 generations to reduce bandwidth
        if self.grid.generation % 3 == 0:
            self._mp_send_state()
        gens_elapsed = self.grid.generation - self.mp_start_gen
        if gens_elapsed >= self.mp_sim_gens:
            self._mp_finish()

    def _handle_mp_planning_key(self, key: int) -> bool:
        """Handle input during multiplayer planning phase."""
        if key == -1:
            return True
        if key == ord("q"):
            self._mp_exit()
            return True
        # Movement
        if key in (curses.KEY_UP, ord("k")):
            self.cursor_r = (self.cursor_r - 1) % self.grid.rows
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.cursor_r = (self.cursor_r + 1) % self.grid.rows
            return True
        if key in (curses.KEY_LEFT, ord("h")):
            self.cursor_c = (self.cursor_c - 1) % self.grid.cols
            return True
        if key in (curses.KEY_RIGHT, ord("l")):
            self.cursor_c = (self.cursor_c + 1) % self.grid.cols
            return True
        # Place/remove cell
        if key == ord("e") or key == ord(" "):
            alive = self.grid.cells[self.cursor_r][self.cursor_c] == 0
            self._mp_place_cell(self.cursor_r, self.cursor_c, alive)
            return True
        if key == ord("d"):
            # Toggle draw mode for painting
            if self.draw_mode == "draw":
                self.draw_mode = None
                self._flash("Draw mode OFF")
            else:
                self.draw_mode = "draw"
                self._mp_place_cell(self.cursor_r, self.cursor_c, True)
                self._flash("Draw mode ON (move to paint)")
            return True
        if key == ord("x"):
            if self.draw_mode == "erase":
                self.draw_mode = None
                self._flash("Erase mode OFF")
            else:
                self.draw_mode = "erase"
                self._mp_place_cell(self.cursor_r, self.cursor_c, False)
                self._flash("Erase mode ON")
            return True
        if key == 27:  # ESC
            self.draw_mode = None
            return True
        # Ready up
        if key in (10, 13, curses.KEY_ENTER):
            if not self.mp_ready[self.mp_player - 1]:
                self._mp_set_ready()
            return True
        # Random fill on player's side
        if key == ord("r"):
            import random
            half = self.grid.cols // 2
            c_start = 0 if self.mp_player == 1 else half
            c_end = half if self.mp_player == 1 else self.grid.cols
            for r in range(self.grid.rows):
                for c in range(c_start, c_end):
                    if random.random() < 0.15:
                        self.grid.set_alive(r, c)
                        self.mp_owner[r][c] = self.mp_player
            if self.mp_net:
                # Send all placements
                for r in range(self.grid.rows):
                    for c in range(c_start, c_end):
                        if self.grid.cells[r][c] > 0:
                            self.mp_net.send({"type": "place", "r": r, "c": c,
                                              "alive": True, "player": self.mp_player})
            self._flash("Random fill on your territory!")
            return True
        # Clear player's side
        if key == ord("c"):
            half = self.grid.cols // 2
            c_start = 0 if self.mp_player == 1 else half
            c_end = half if self.mp_player == 1 else self.grid.cols
            for r in range(self.grid.rows):
                for c in range(c_start, c_end):
                    if self.grid.cells[r][c] > 0:
                        self.grid.set_dead(r, c)
                        self.mp_owner[r][c] = 0
                        if self.mp_net:
                            self.mp_net.send({"type": "place", "r": r, "c": c,
                                              "alive": False, "player": self.mp_player})
            self._flash("Cleared your territory")
            return True
        return True

    def _mp_apply_draw_mode(self):
        """Apply draw/erase under cursor during multiplayer planning, respecting territory."""
        if not self.draw_mode or self.mp_phase != "planning":
            return
        if self.mp_ready[self.mp_player - 1]:
            return  # already locked in
        half = self.grid.cols // 2
        c = self.cursor_c
        if (self.mp_player == 1 and c >= half) or (self.mp_player == 2 and c < half):
            return  # out of territory
        if self.draw_mode == "draw":
            self._mp_place_cell(self.cursor_r, self.cursor_c, True)
        elif self.draw_mode == "erase":
            self._mp_place_cell(self.cursor_r, self.cursor_c, False)

    def _handle_mp_running_key(self, key: int) -> bool:
        """Handle input during multiplayer simulation phase."""
        if key == -1:
            return True
        if key == ord("q"):
            self._mp_exit()
            return True
        if key == ord(" "):
            self.running = not self.running
            return True
        if key == ord("+") or key == ord("="):
            if self.speed_idx < len(SPEEDS) - 1:
                self.speed_idx += 1
            return True
        if key == ord("-") or key == ord("_"):
            if self.speed_idx > 0:
                self.speed_idx -= 1
            return True
        # Arrow keys for scrolling viewport
        if key in (curses.KEY_UP, ord("k")):
            self.cursor_r = (self.cursor_r - 1) % self.grid.rows
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.cursor_r = (self.cursor_r + 1) % self.grid.rows
            return True
        if key in (curses.KEY_LEFT, ord("h")):
            self.cursor_c = (self.cursor_c - 1) % self.grid.cols
            return True
        if key in (curses.KEY_RIGHT, ord("l")):
            self.cursor_c = (self.cursor_c + 1) % self.grid.cols
            return True
        return True

    def _handle_mp_finished_key(self, key: int) -> bool:
        """Handle input on the multiplayer results screen."""
        if key == -1:
            return True
        if key == ord("q") or key == 27:
            self._mp_exit()
            return True
        # Enter = play again
        if key in (10, 13, curses.KEY_ENTER):
            if self.mp_role == "host" and self.mp_net:
                self._mp_start_planning()
                self.mp_net.send({"type": "start_planning"})
            else:
                self._flash("Waiting for host to start next round...")
            return True
        return True

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
        saves = sorted(f for f in os.listdir(SAVE_DIR) if f.endswith(".json") and f != "blueprints.json")
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

        if self.puzzle_menu:
            self._draw_puzzle_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.puzzle_mode and self.puzzle_current:
            self._draw_puzzle(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.blueprint_menu:
            self._draw_blueprint_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.bookmark_menu:
            self._draw_bookmark_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.show_help:
            self._draw_help(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wolfram_menu:
            self._draw_wolfram_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wolfram_mode:
            self._draw_wolfram(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ant_menu:
            self._draw_ant_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ant_mode:
            self._draw_ant(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ww_menu:
            self._draw_ww_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ww_mode:
            self._draw_ww(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sand_menu:
            self._draw_sand_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sand_mode:
            self._draw_sand(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.evo_menu:
            self._draw_evo_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.evo_mode:
            self._draw_evo(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.race_rule_menu:
            self._draw_race_rule_menu(max_y, max_x)
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

        if self.mp_mode:
            self._draw_multiplayer(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.race_mode and self.race_grids:
            self._draw_race(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.compare_mode and self.grid2:
            self._draw_compare(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.iso_mode:
            self._draw_iso(max_y, max_x)
            self.stdscr.refresh()
            return

        # Compute viewport
        # Each cell takes 2 columns on screen
        zoom = self.zoom_level
        vis_rows = max_y - 5  # leave room for timeline + sparkline + status + hint
        vis_cols = (max_x - 1) // 2

        # At zoom > 1, each screen cell covers zoom×zoom grid cells
        grid_vis_rows = vis_rows * zoom
        grid_vis_cols = vis_cols * zoom

        # Centre viewport on cursor
        self.view_r = self.cursor_r - grid_vis_rows // 2
        self.view_c = self.cursor_c - grid_vis_cols // 2

        # Build pattern highlight lookup: (gr, gc) -> category string
        pat_highlight = {}
        if self.pattern_search_mode and self.detected_patterns:
            for pat in self.detected_patterns:
                for cell in pat["cells"]:
                    pat_highlight[cell] = pat["category"]

        # Blueprint selection region bounds
        bp_min_r = bp_min_c = bp_max_r = bp_max_c = -1
        if self.blueprint_mode and self.blueprint_anchor:
            bp_min_r, bp_min_c, bp_max_r, bp_max_c = self._blueprint_region()

        if zoom == 1:
            # Normal 1:1 rendering
            hex_offset_cols = vis_cols - 1 if self.hex_mode else vis_cols
            for sy in range(min(vis_rows, self.grid.rows)):
                gr = (self.view_r + sy) % self.grid.rows
                for sx in range(min(hex_offset_cols, self.grid.cols)):
                    gc = (self.view_c + sx) % self.grid.cols
                    age = self.grid.cells[gr][gc]
                    is_cursor = (gr == self.cursor_r and gc == self.cursor_c)
                    in_blueprint = (self.blueprint_mode and self.blueprint_anchor and
                                    bp_min_r <= gr <= bp_max_r and bp_min_c <= gc <= bp_max_c)
                    # Hex mode: offset odd grid rows by 1 column for hex tiling
                    hex_shift = 1 if (self.hex_mode and gr % 2 == 1) else 0
                    px = sx * 2 + hex_shift
                    py = sy
                    if py >= max_y - 2 or px + 1 >= max_x:
                        continue
                    if self.heatmap_mode and self.heatmap_max > 0:
                        heat = self.heatmap[gr][gc]
                        if heat > 0:
                            frac = heat / self.heatmap_max
                            attr = color_for_heat(frac)
                            if age > 0:
                                attr |= curses.A_BOLD
                            if is_cursor:
                                attr |= curses.A_REVERSE
                            heat_ch = HEX_CELL if self.hex_mode else CELL_CHAR
                            try:
                                self.stdscr.addstr(py, px, heat_ch, attr)
                            except curses.error:
                                pass
                        else:
                            if is_cursor:
                                try:
                                    self.stdscr.addstr(py, px, "▒▒", curses.color_pair(6) | curses.A_DIM)
                                except curses.error:
                                    pass
                            elif in_blueprint:
                                try:
                                    self.stdscr.addstr(py, px, "░░", curses.color_pair(40) | curses.A_DIM)
                                except curses.error:
                                    pass
                    elif age > 0:
                        # Pattern search highlighting
                        pcat = pat_highlight.get((gr, gc))
                        if pcat:
                            attr = self._pattern_color(pcat) | curses.A_BOLD
                        else:
                            attr = color_for_age(age)
                        if in_blueprint:
                            attr = curses.color_pair(40) | curses.A_BOLD
                        if is_cursor:
                            attr |= curses.A_REVERSE
                        cell_ch = HEX_CELL if self.hex_mode else CELL_CHAR
                        try:
                            self.stdscr.addstr(py, px, cell_ch, attr)
                        except curses.error:
                            pass
                    else:
                        if is_cursor:
                            cursor_ch = HEX_CELL if self.hex_mode else "▒▒"
                            try:
                                self.stdscr.addstr(py, px, cursor_ch, curses.color_pair(6) | curses.A_DIM)
                            except curses.error:
                                pass
                        elif in_blueprint:
                            try:
                                self.stdscr.addstr(py, px, "░░", curses.color_pair(40) | curses.A_DIM)
                            except curses.error:
                                pass
                        elif self.hex_mode:
                            # Show hex grid structure with dots
                            try:
                                self.stdscr.addstr(py, px, HEX_DEAD, curses.color_pair(6) | curses.A_DIM)
                            except curses.error:
                                pass
        else:
            # Zoomed-out rendering: each screen cell covers zoom×zoom grid cells
            screen_rows = min(vis_rows, (self.grid.rows + zoom - 1) // zoom)
            screen_cols = min(vis_cols, (self.grid.cols + zoom - 1) // zoom)
            for sy in range(screen_rows):
                for sx in range(screen_cols):
                    px = sx * 2
                    py = sy
                    if py >= max_y - 2 or px + 1 >= max_x:
                        continue
                    # Compute density of the zoom×zoom block
                    alive_count = 0
                    total = 0
                    heat_sum = 0
                    max_age = 0
                    has_cursor = False
                    has_blueprint = False
                    base_r = self.view_r + sy * zoom
                    base_c = self.view_c + sx * zoom
                    for dr in range(zoom):
                        for dc in range(zoom):
                            gr = (base_r + dr) % self.grid.rows
                            gc = (base_c + dc) % self.grid.cols
                            total += 1
                            age = self.grid.cells[gr][gc]
                            if age > 0:
                                alive_count += 1
                                if age > max_age:
                                    max_age = age
                            if gr == self.cursor_r and gc == self.cursor_c:
                                has_cursor = True
                            if (self.blueprint_mode and self.blueprint_anchor and
                                    bp_min_r <= gr <= bp_max_r and bp_min_c <= gc <= bp_max_c):
                                has_blueprint = True
                            if self.heatmap_mode and self.heatmap_max > 0:
                                heat_sum += self.heatmap[gr][gc]
                    # Pick density glyph
                    if alive_count == 0:
                        density_idx = 0
                    else:
                        frac = alive_count / total
                        if frac <= 0.25:
                            density_idx = 1
                        elif frac <= 0.5:
                            density_idx = 2
                        elif frac <= 0.75:
                            density_idx = 3
                        else:
                            density_idx = 4
                    char = DENSITY_CHARS[density_idx]
                    # Determine color/attr
                    if self.heatmap_mode and self.heatmap_max > 0:
                        if heat_sum > 0:
                            heat_frac = (heat_sum / total) / self.heatmap_max
                            attr = color_for_heat(min(1.0, heat_frac))
                            if alive_count > 0:
                                attr |= curses.A_BOLD
                        else:
                            attr = curses.color_pair(6) | curses.A_DIM
                            if alive_count == 0 and not has_cursor and not has_blueprint:
                                continue
                    elif alive_count > 0:
                        attr = color_for_age(max_age)
                    elif has_blueprint:
                        attr = curses.color_pair(40) | curses.A_DIM
                        char = "░░"
                    elif has_cursor:
                        attr = curses.color_pair(6) | curses.A_DIM
                        char = "▒▒"
                    else:
                        continue  # empty, nothing to draw
                    if has_cursor:
                        attr |= curses.A_REVERSE
                    try:
                        self.stdscr.addstr(py, px, char, attr)
                    except curses.error:
                        pass

        # Draw pattern labels (name tags near detected patterns)
        if self.pattern_search_mode and self.detected_patterns:
            for pat in self.detected_patterns:
                # Label position: just above the pattern's top-left, or on top row
                label_gr = pat["r"]
                label_gc = pat["c"]
                # Convert to screen coords (accounting for zoom)
                sy = ((label_gr - self.view_r) % self.grid.rows) // zoom
                sx = ((label_gc - self.view_c) % self.grid.cols) // zoom
                lpy = sy - 1  # one row above
                lpx = sx * 2
                label = pat["name"]
                if lpy < 0:
                    lpy = sy + pat["h"]  # below if no room above
                if 0 <= lpy < vis_rows and 0 <= lpx < max_x - len(label):
                    attr = self._pattern_color(pat["category"]) | curses.A_DIM
                    try:
                        self.stdscr.addstr(lpy, lpx, label, attr)
                    except curses.error:
                        pass

        # Timeline bar
        timeline_y = max_y - 4
        if timeline_y > 0 and len(self.history) > 0:
            bar_label = " Timeline: "
            bookmark_info = f"  ★{len(self.bookmarks)}" if self.bookmarks else ""
            hist_len = len(self.history)
            # Determine current position in history
            if self.timeline_pos is not None:
                cur_pos = self.timeline_pos + 1  # 1-based
                pos_label = f" Gen {self.grid.generation} ({cur_pos}/{hist_len}){bookmark_info} "
            else:
                pos_label = f" LIVE Gen {self.grid.generation} ({hist_len} saved){bookmark_info} "
            bar_width = max_x - len(bar_label) - len(pos_label) - 1
            if bar_width > 2:
                if self.timeline_pos is not None:
                    # Show position within the history buffer
                    filled = max(1, int((self.timeline_pos + 1) / hist_len * bar_width))
                    empty = bar_width - filled
                    # Mark bookmark positions on the bar
                    bar_chars = list("█" * filled + "░" * empty)
                    for bg, _, _ in self.bookmarks:
                        # Find the approximate bar position for this bookmark
                        for hi, (hd, _) in enumerate(self.history):
                            if hd.get("generation") == bg:
                                bi = int(hi / hist_len * bar_width)
                                bi = min(bi, len(bar_chars) - 1)
                                bar_chars[bi] = "★"
                                break
                    bar_str = "".join(bar_chars)
                else:
                    # At live position — full bar
                    bar_chars = list("█" * bar_width)
                    for bg, _, _ in self.bookmarks:
                        for hi, (hd, _) in enumerate(self.history):
                            if hd.get("generation") == bg:
                                bi = int(hi / hist_len * bar_width)
                                bi = min(bi, len(bar_chars) - 1)
                                bar_chars[bi] = "★"
                                break
                    bar_str = "".join(bar_chars)
                try:
                    self.stdscr.addstr(timeline_y, 0, bar_label, curses.color_pair(6) | curses.A_DIM)
                    self.stdscr.addstr(timeline_y, len(bar_label), bar_str, curses.color_pair(7))
                    self.stdscr.addstr(timeline_y, len(bar_label) + len(bar_str), pos_label,
                                       curses.color_pair(6) | curses.A_DIM)
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
            if self.heatmap_mode:
                mode = "  │  🔥 HEATMAP"
            if self.pattern_search_mode:
                n = len(self.detected_patterns)
                mode += f"  │  🔍 SEARCH({n})"
            if self.blueprint_mode:
                mode += "  │  📐 BLUEPRINT"
            if self.recording:
                mode += f"  │  ⏺ REC({len(self.recorded_frames)})"
            if self.sound_engine.enabled:
                mode += "  │  ♪ SOUND"
            if self.hex_mode:
                mode += "  │  ⬡ HEX"
            if self.iso_mode:
                mode += "  │  🏙 ISO-3D"
            if self.draw_mode == "draw":
                mode += "  │  ✏ DRAW"
            elif self.draw_mode == "erase":
                mode += "  │  ✘ ERASE"
            rs = rule_string(self.grid.birth, self.grid.survival)
            zoom_str = f"  │  Zoom: {self.zoom_level}:1" if self.zoom_level > 1 else ""
            status = (
                f" Gen: {self.grid.generation}  │  "
                f"Pop: {self.grid.population}  │  "
                f"{state}  │  Speed: {speed}  │  "
                f"Rule: {rs}  │  "
                f"Cursor: ({self.cursor_r},{self.cursor_c}){zoom_str}{mode}"
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
                hint = " [Space]=play [n]=step [u]=rewind [/]=scrub10 [b]=bookmark [B]=bookmarks [p]=patterns [t]=stamp [W]=blueprint [T]=blueprints [e]=edit [d]=draw [F]=search [H]=heatmap [I]=3D [1]=wolfram [2]=ant [3]=hex [M]=sound [R]=rules [V]=compare [Z]=race [C]=puzzles [N]=multiplayer [G]=record GIF [s]=save [o]=load [+/-]=zoom [0]=reset zoom [</>]=speed [?]=help [q]=quit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

        self.stdscr.refresh()

    def _draw_multiplayer(self, max_y: int, max_x: int):
        """Draw the multiplayer mode UI based on current phase."""
        if self.mp_phase == "lobby":
            self._draw_mp_lobby(max_y, max_x)
        elif self.mp_phase == "planning":
            self._draw_mp_planning(max_y, max_x)
        elif self.mp_phase == "running":
            self._draw_mp_game(max_y, max_x)
        elif self.mp_phase == "finished":
            self._draw_mp_finished(max_y, max_x)

    def _draw_mp_lobby(self, max_y: int, max_x: int):
        """Draw the waiting-for-connection lobby screen."""
        lines = [
            "╔════════════════════════════════════════════╗",
            "║        MULTIPLAYER — Waiting for Player    ║",
            "╠════════════════════════════════════════════╣",
            "║                                            ║",
        ]
        if self.mp_role == "host":
            lines.append(f"║  Hosting on port {self.mp_host_port:<25d} ║")
            lines.append("║  Waiting for opponent to connect...       ║")
        else:
            lines.append("║  Connecting...                            ║")
            lines.append("║  Waiting for host to start game...        ║")
        lines += [
            "║                                            ║",
            "║  You are: " + ("Player 1 (BLUE)" if self.mp_player == 1 else "Player 2 (RED) ") + "              ║",
            "║                                            ║",
            "║  Press q to cancel                         ║",
            "║                                            ║",
            "╚════════════════════════════════════════════╝",
        ]
        start_y = max(0, (max_y - len(lines)) // 2)
        for i, line in enumerate(lines):
            y = start_y + i
            if y >= max_y:
                break
            x = max(0, (max_x - len(line)) // 2)
            attr = curses.color_pair(7)
            try:
                self.stdscr.addstr(y, x, line, attr)
            except curses.error:
                pass

    def _draw_mp_grid(self, max_y: int, max_x: int, status_rows: int = 5):
        """Render the grid with multiplayer ownership colours.

        Returns (vis_rows, vis_cols) used for layout.
        """
        vis_rows = max_y - status_rows
        vis_cols = (max_x - 1) // 2
        half = self.grid.cols // 2

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
                # Draw territory divider
                if gc == half:
                    try:
                        self.stdscr.addstr(py, px, "│ ", curses.color_pair(6) | curses.A_DIM)
                    except curses.error:
                        pass
                    continue
                if age > 0:
                    ow = 0
                    if self.mp_owner and gr < len(self.mp_owner) and gc < len(self.mp_owner[0]):
                        ow = self.mp_owner[gr][gc]
                    attr = color_for_mp(age, ow)
                    if age > 3:
                        attr |= curses.A_BOLD
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
        return vis_rows, vis_cols

    def _draw_mp_planning(self, max_y: int, max_x: int):
        """Draw the multiplayer planning phase with grid and timer."""
        self._draw_mp_grid(max_y, max_x, status_rows=4)

        remaining = max(0, self.mp_planning_deadline - time.monotonic())
        my_ready = self.mp_ready[self.mp_player - 1]
        opp_ready = self.mp_ready[2 - self.mp_player]

        # Player info bar
        info_y = max_y - 4
        if info_y > 0:
            p_label = "P1 (BLUE)" if self.mp_player == 1 else "P2 (RED)"
            p_color = curses.color_pair(50) if self.mp_player == 1 else curses.color_pair(54)
            status = "READY" if my_ready else "PLACING"
            opp_status = "READY" if opp_ready else "placing..."
            info = f" You: {p_label} [{status}]  │  Opponent: [{opp_status}]  │  Round {self.mp_round}"
            try:
                self.stdscr.addstr(info_y, 0, info[:max_x - 1], p_color | curses.A_BOLD)
            except curses.error:
                pass

        # Timer bar
        timer_y = max_y - 3
        if timer_y > 0:
            secs = int(remaining)
            bar_width = max_x - 30
            if bar_width > 0:
                frac = remaining / MP_PLANNING_TIME
                filled = int(frac * bar_width)
                bar = "█" * filled + "░" * (bar_width - filled)
                timer_color = curses.color_pair(1) if remaining > 10 else curses.color_pair(5)
                timer_str = f" Time: {secs:2d}s [{bar}]"
                try:
                    self.stdscr.addstr(timer_y, 0, timer_str[:max_x - 1], timer_color)
                except curses.error:
                    pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            half_label = "LEFT" if self.mp_player == 1 else "RIGHT"
            status = (
                f" PLANNING — Place cells on {half_label} side  │  "
                f"Pop: {self.grid.population}  │  "
                f"Cursor: ({self.cursor_r},{self.cursor_c})"
            )
            try:
                self.stdscr.addstr(status_y, 0, status[:max_x - 1],
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            else:
                hint = " [e/Space]=toggle cell [d]=draw [x]=erase [r]=random fill [c]=clear [Enter]=ready [q]=quit"
            try:
                self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_mp_game(self, max_y: int, max_x: int):
        """Draw the multiplayer simulation with scoreboard."""
        self._draw_mp_grid(max_y, max_x, status_rows=5)

        gens_elapsed = self.grid.generation - self.mp_start_gen
        gens_remain = max(0, self.mp_sim_gens - gens_elapsed)

        # Score bar
        score_y = max_y - 5
        if score_y > 0:
            s1, s2 = self.mp_scores
            b1, b2 = self.mp_territory_bonus
            total1 = s1 + b1 * 2
            total2 = s2 + b2 * 2
            # Score bar with proportional fill
            bar_width = max(10, max_x - 50)
            total = max(total1 + total2, 1)
            p1_fill = int(total1 / total * bar_width)
            p2_fill = bar_width - p1_fill
            p1_bar = "█" * p1_fill
            p2_bar = "█" * p2_fill
            try:
                self.stdscr.addstr(score_y, 0, " P1:", curses.color_pair(50) | curses.A_BOLD)
                self.stdscr.addstr(score_y, 4, f"{total1:4d} ", curses.color_pair(51))
                self.stdscr.addstr(score_y, 10, p1_bar, curses.color_pair(50))
                self.stdscr.addstr(score_y, 10 + p1_fill, p2_bar, curses.color_pair(54))
                p2_label = f" {total2:4d} :P2"
                self.stdscr.addstr(score_y, 10 + bar_width + 1, p2_label,
                                   curses.color_pair(54) | curses.A_BOLD)
            except curses.error:
                pass

        # Progress bar
        prog_y = max_y - 4
        if prog_y > 0:
            frac = gens_elapsed / max(self.mp_sim_gens, 1)
            prog_w = max_x - 30
            if prog_w > 0:
                filled = int(frac * prog_w)
                bar = "█" * filled + "░" * (prog_w - filled)
                prog_str = f" Gen {gens_elapsed}/{self.mp_sim_gens} [{bar}]"
                try:
                    self.stdscr.addstr(prog_y, 0, prog_str[:max_x - 1],
                                       curses.color_pair(6))
                except curses.error:
                    pass

        # Population sparkline
        spark_y = max_y - 3
        if spark_y > 0:
            # Quick sparkline from current pop
            s1, s2 = self.mp_scores
            info = f" P1 cells: {s1}  │  P2 cells: {s2}  │  Total: {self.grid.population}"
            try:
                self.stdscr.addstr(spark_y, 0, info[:max_x - 1], curses.color_pair(6))
            except curses.error:
                pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            state = "▶ RUNNING" if self.running else "⏸ PAUSED"
            speed = SPEED_LABELS[self.speed_idx]
            role = "HOST" if self.mp_role == "host" else "CLIENT"
            status = (
                f" MULTIPLAYER {role}  │  {state}  │  Speed: {speed}  │  "
                f"Round {self.mp_round}  │  {gens_remain} gens left"
            )
            try:
                self.stdscr.addstr(status_y, 0, status[:max_x - 1],
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            else:
                hint = " [Space]=pause [+/-]=speed [Arrows]=scroll [q]=quit"
            try:
                self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_mp_finished(self, max_y: int, max_x: int):
        """Draw the multiplayer results screen."""
        s1, s2 = self.mp_scores
        b1, b2 = self.mp_territory_bonus
        total1 = s1 + b1 * 2
        total2 = s2 + b2 * 2

        if total1 > total2:
            winner_text = "Player 1 (BLUE) WINS!"
            winner_color = curses.color_pair(50)
        elif total2 > total1:
            winner_text = "Player 2 (RED) WINS!"
            winner_color = curses.color_pair(54)
        else:
            winner_text = "IT'S A TIE!"
            winner_color = curses.color_pair(58)

        lines = [
            ("╔════════════════════════════════════════════════╗", curses.color_pair(7)),
            ("║           MULTIPLAYER — ROUND OVER            ║", curses.color_pair(7)),
            ("╠════════════════════════════════════════════════╣", curses.color_pair(7)),
            ("║                                                ║", curses.color_pair(7)),
            (f"║  {winner_text:^44s}  ║", winner_color | curses.A_BOLD),
            ("║                                                ║", curses.color_pair(7)),
            (f"║  Player 1 (BLUE):                              ║", curses.color_pair(50)),
            (f"║    Cells alive: {s1:<6d}                         ║", curses.color_pair(51)),
            (f"║    Territory bonus: {b1:<4d} (x2 = {b1*2:<5d})         ║", curses.color_pair(51)),
            (f"║    TOTAL: {total1:<8d}                           ║", curses.color_pair(50) | curses.A_BOLD),
            ("║                                                ║", curses.color_pair(7)),
            (f"║  Player 2 (RED):                               ║", curses.color_pair(54)),
            (f"║    Cells alive: {s2:<6d}                         ║", curses.color_pair(55)),
            (f"║    Territory bonus: {b2:<4d} (x2 = {b2*2:<5d})         ║", curses.color_pair(55)),
            (f"║    TOTAL: {total2:<8d}                           ║", curses.color_pair(54) | curses.A_BOLD),
            ("║                                                ║", curses.color_pair(7)),
            ("║  Enter = play again  │  q/Esc = exit           ║", curses.color_pair(6)),
            ("║                                                ║", curses.color_pair(7)),
            ("╚════════════════════════════════════════════════╝", curses.color_pair(7)),
        ]
        start_y = max(0, (max_y - len(lines)) // 2)
        for i, (line, attr) in enumerate(lines):
            y = start_y + i
            if y >= max_y:
                break
            x = max(0, (max_x - len(line)) // 2)
            try:
                self.stdscr.addstr(y, x, line, attr)
            except curses.error:
                pass

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

    def _draw_bookmark_menu(self, max_y: int, max_x: int):
        title = "── Bookmarks (Enter=jump, D=delete, q/Esc=close) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        for i, (gen, grid_dict, pop_len) in enumerate(self.bookmarks):
            y = 3 + i
            if y >= max_y - 1:
                break
            pop = len(grid_dict.get("cells", []))
            line = f"  ★ Gen {gen:<8d}  Pop: {pop}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.bookmark_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass

    # ── Wolfram 1D Elementary Cellular Automaton mode ──────────────────────────

    WOLFRAM_PRESETS = [
        (30, "Rule 30 — chaotic / pseudorandom"),
        (90, "Rule 90 — Sierpinski triangle (XOR)"),
        (110, "Rule 110 — Turing-complete"),
        (184, "Rule 184 — traffic flow model"),
        (73, "Rule 73 — complex structures"),
        (54, "Rule 54 — complex with triangles"),
        (150, "Rule 150 — Sierpinski variant"),
        (22, "Rule 22 — nested triangles"),
        (126, "Rule 126 — complement of 90"),
        (250, "Rule 250 — simple stripes"),
        (0, "Rule 0 — all cells die"),
        (255, "Rule 255 — all cells alive"),
    ]

    def _wolfram_apply_rule(self, rule_num: int, left: int, center: int, right: int) -> int:
        """Apply a Wolfram elementary rule. The 3-cell neighbourhood (left, center, right)
        forms a 3-bit index into the 8-bit rule number."""
        idx = (left << 2) | (center << 1) | right
        return (rule_num >> idx) & 1

    def _wolfram_init(self):
        """Initialize the Wolfram automaton with the chosen seed mode."""
        max_y, max_x = self.stdscr.getmaxyx()
        self.wolfram_width = max_x - 2  # leave margin
        if self.wolfram_width < 10:
            self.wolfram_width = 10
        row0 = [0] * self.wolfram_width
        if self.wolfram_seed_mode == "center":
            row0[self.wolfram_width // 2] = 1
        elif self.wolfram_seed_mode == "gol_row":
            # Use the middle row of the current Game of Life grid
            mid_r = self.grid.rows // 2
            for c in range(min(self.wolfram_width, self.grid.cols)):
                if self.grid.is_alive(mid_r, c):
                    row0[c] = 1
            # If completely empty, fall back to center cell
            if sum(row0) == 0:
                row0[self.wolfram_width // 2] = 1
        elif self.wolfram_seed_mode == "random":
            for c in range(self.wolfram_width):
                row0[c] = random.randint(0, 1)
        self.wolfram_rows = [row0]

    def _wolfram_step(self):
        """Compute the next row of the 1D automaton."""
        if not self.wolfram_rows:
            return
        prev = self.wolfram_rows[-1]
        w = len(prev)
        new_row = [0] * w
        for i in range(w):
            left = prev[(i - 1) % w]
            center = prev[i]
            right = prev[(i + 1) % w]
            new_row[i] = self._wolfram_apply_rule(self.wolfram_rule, left, center, right)
        self.wolfram_rows.append(new_row)

    def _enter_wolfram_mode(self):
        """Enter the Wolfram 1D automaton mode — show rule menu first."""
        self.wolfram_menu = True
        self.wolfram_menu_sel = 0
        self._flash("Wolfram 1D Automaton — select a rule")

    def _exit_wolfram_mode(self):
        """Exit Wolfram mode back to normal Game of Life."""
        self.wolfram_mode = False
        self.wolfram_menu = False
        self.wolfram_running = False
        self.wolfram_rows = []
        self._flash("Wolfram mode OFF")

    def _handle_wolfram_menu_key(self, key: int) -> bool:
        """Handle keys in the Wolfram rule selection menu."""
        if key == -1:
            return True
        n_presets = len(self.WOLFRAM_PRESETS)
        if key == curses.KEY_UP or key == ord("k"):
            self.wolfram_menu_sel = (self.wolfram_menu_sel - 1) % (n_presets + 3)
            return True
        if key == curses.KEY_DOWN or key == ord("j"):
            self.wolfram_menu_sel = (self.wolfram_menu_sel + 1) % (n_presets + 3)
            return True
        if key == ord("q") or key == 27:
            self.wolfram_menu = False
            self._flash("Wolfram mode cancelled")
            return True
        if key in (10, 13, curses.KEY_ENTER):
            if self.wolfram_menu_sel < n_presets:
                self.wolfram_rule = self.WOLFRAM_PRESETS[self.wolfram_menu_sel][0]
            elif self.wolfram_menu_sel == n_presets:
                # Custom rule input
                txt = self._prompt_text("Enter rule number (0-255)")
                if txt is not None:
                    try:
                        val = int(txt)
                        if 0 <= val <= 255:
                            self.wolfram_rule = val
                        else:
                            self._flash("Rule must be 0-255")
                            return True
                    except ValueError:
                        self._flash("Invalid number")
                        return True
                else:
                    return True
            elif self.wolfram_menu_sel == n_presets + 1:
                # Toggle seed mode
                modes = ["center", "gol_row", "random"]
                idx = modes.index(self.wolfram_seed_mode)
                self.wolfram_seed_mode = modes[(idx + 1) % len(modes)]
                return True
            elif self.wolfram_menu_sel == n_presets + 2:
                # Start with currently selected settings
                pass
            self.wolfram_menu = False
            self.wolfram_mode = True
            self.wolfram_running = False
            self._wolfram_init()
            self._flash(f"Wolfram Rule {self.wolfram_rule} — Space=play, n=step, q=exit")
            return True
        return True

    def _handle_wolfram_key(self, key: int) -> bool:
        """Handle keys while in Wolfram 1D automaton mode."""
        if key == -1:
            return True
        if key == ord("q") or key == 27:
            self._exit_wolfram_mode()
            return True
        if key == ord(" "):
            self.wolfram_running = not self.wolfram_running
            self._flash("Playing" if self.wolfram_running else "Paused")
            return True
        if key == ord("n") or key == ord("."):
            self.wolfram_running = False
            self._wolfram_step()
            return True
        if key == ord("r"):
            # Reset with current rule
            self._wolfram_init()
            self._flash(f"Reset Rule {self.wolfram_rule}")
            return True
        if key == ord("R") or key == ord("m"):
            # Open rule menu again
            self.wolfram_mode = False
            self.wolfram_running = False
            self.wolfram_menu = True
            self.wolfram_menu_sel = 0
            return True
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
        if key == curses.KEY_LEFT or key == ord("h"):
            if self.wolfram_rule > 0:
                self.wolfram_rule -= 1
                self._wolfram_init()
                self._flash(f"Rule {self.wolfram_rule}")
            return True
        if key == curses.KEY_RIGHT or key == ord("l"):
            if self.wolfram_rule < 255:
                self.wolfram_rule += 1
                self._wolfram_init()
                self._flash(f"Rule {self.wolfram_rule}")
            return True
        return True

    def _draw_wolfram_menu(self, max_y: int, max_x: int):
        """Draw the Wolfram rule selection menu."""
        title = "── Wolfram 1D Elementary Cellular Automaton ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        subtitle = "Select a rule preset or enter a custom rule (0-255)"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                               curses.color_pair(6))
        except curses.error:
            pass

        n_presets = len(self.WOLFRAM_PRESETS)
        for i, (rule_num, desc) in enumerate(self.WOLFRAM_PRESETS):
            y = 5 + i
            if y >= max_y - 6:
                break
            # Show mini rule table: 8 outputs for the 8 input patterns
            rule_bits = f"{rule_num:08b}"
            line = f"  {desc}  [{rule_bits}]"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.wolfram_menu_sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            try:
                self.stdscr.addstr(y, 1, line, attr)
            except curses.error:
                pass

        # Extra menu items
        extra_y = 5 + min(n_presets, max_y - 11)
        extra_items = [
            f"  [Custom] Enter rule number manually",
            f"  [Seed: {self.wolfram_seed_mode}] Toggle initial condition (center/GoL row/random)",
            f"  >>> Start with Rule {self.wolfram_rule}, seed={self.wolfram_seed_mode} <<<",
        ]
        for i, line in enumerate(extra_items):
            y = extra_y + i
            idx = n_presets + i
            if y >= max_y - 2:
                break
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if idx == self.wolfram_menu_sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            try:
                self.stdscr.addstr(y, 1, line, attr)
            except curses.error:
                pass

        # Draw the rule table visualization for current rule
        table_y = extra_y + len(extra_items) + 1
        if table_y < max_y - 3:
            rule_bits = f"{self.wolfram_rule:08b}"
            header = f"  Rule {self.wolfram_rule} table:  "
            patterns = ["111", "110", "101", "100", "011", "010", "001", "000"]
            for j, pat in enumerate(patterns):
                header += f" {pat}={rule_bits[j]}"
            header = header[:max_x - 2]
            try:
                self.stdscr.addstr(table_y, 1, header, curses.color_pair(1))
            except curses.error:
                pass

        # Hint
        hint_y = max_y - 1
        if hint_y > 0:
            hint = " [j/k]=navigate [Enter]=select [q/Esc]=cancel"
            try:
                self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_wolfram(self, max_y: int, max_x: int):
        """Draw the Wolfram 1D automaton — rows cascade top to bottom."""
        # Title bar
        rule_bits = f"{self.wolfram_rule:08b}"
        title = f" Wolfram Rule {self.wolfram_rule} [{rule_bits}]  Gen: {len(self.wolfram_rows) - 1}  Seed: {self.wolfram_seed_mode}"
        state = " PLAY" if self.wolfram_running else " PAUSE"
        title += f"  {state}"
        title = title[:max_x - 1]
        try:
            self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        # Rule table visualization on line 1
        table_line = " Table: "
        patterns = ["111", "110", "101", "100", "011", "010", "001", "000"]
        for j, pat in enumerate(patterns):
            table_line += f"{pat}={'#' if rule_bits[j] == '1' else '.'} "
        table_line = table_line[:max_x - 1]
        try:
            self.stdscr.addstr(1, 0, table_line, curses.color_pair(1))
        except curses.error:
            pass

        # Draw the automaton rows
        draw_start = 3
        draw_rows = max_y - 5  # leave room for status/hint
        if draw_rows < 1:
            draw_rows = 1

        # Show the most recent rows that fit on screen
        total_rows = len(self.wolfram_rows)
        start_idx = max(0, total_rows - draw_rows)
        display_width = min(self.wolfram_width, max_x - 1)

        for i, row_idx in enumerate(range(start_idx, total_rows)):
            y = draw_start + i
            if y >= max_y - 2:
                break
            row = self.wolfram_rows[row_idx]
            # Center the row if it's narrower than the screen
            offset = max(0, (max_x - display_width) // 2)
            line_chars = []
            for c in range(display_width):
                if c < len(row) and row[c]:
                    line_chars.append("\u2588")  # full block
                else:
                    line_chars.append(" ")
            line = "".join(line_chars)
            try:
                color = curses.color_pair(1)
                # Use different colors for generation bands
                if row_idx % 2 == 0:
                    color = curses.color_pair(2) if curses.has_colors() else curses.A_NORMAL
                self.stdscr.addstr(y, offset, line, color)
            except curses.error:
                pass

        # Highlight known interesting rules
        interesting = {30: "chaotic", 90: "Sierpinski", 110: "Turing-complete",
                       184: "traffic", 73: "complex", 54: "complex"}
        note = interesting.get(self.wolfram_rule, "")
        if note:
            note = f" ({note})"

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            pop = sum(self.wolfram_rows[-1]) if self.wolfram_rows else 0
            density = pop / self.wolfram_width * 100 if self.wolfram_width > 0 else 0
            status = f" Rule: {self.wolfram_rule}{note}  |  Gen: {len(self.wolfram_rows) - 1}  |  Alive: {pop}/{self.wolfram_width} ({density:.0f}%)  |  Speed: {SPEED_LABELS[self.speed_idx]}"
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
                hint = " [Space]=play [n]=step [h/l]=prev/next rule [r]=reset [R]=menu [</>]=speed [q]=exit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Langton's Ant mode ──────────────────────────────────────────

    ANT_PRESETS = [
        ("RL", "Classic Langton's Ant — produces highway after ~10k steps"),
        ("RLR", "3-color — symmetric triangular patterns"),
        ("LLRR", "4-color — grows a filled square"),
        ("LRRRRRLLR", "9-color — intricate fractal growth"),
        ("RRLLLRLLLRRR", "12-color — chaotic spiral expansion"),
        ("RRLL", "4-color — diamond-shaped growth"),
        ("RLLR", "4-color — square with internal structure"),
        ("LRRL", "4-color — complex highway variant"),
    ]

    # Colors for ants and multi-state cells
    ANT_COLORS = [1, 2, 3, 4, 5, 6, 7, 8]

    def _ant_step(self):
        """Advance all ants by one step."""
        for ant in self.ant_ants:
            r, c = ant["r"], ant["c"]
            color_state = self.ant_grid.get((r, c), 0)
            rule_len = len(self.ant_rule)
            turn = self.ant_rule[color_state % rule_len]
            # Turn: R = clockwise, L = counterclockwise
            # Directions: 0=up, 1=right, 2=down, 3=left
            if turn == "R":
                ant["dir"] = (ant["dir"] + 1) % 4
            else:  # L
                ant["dir"] = (ant["dir"] - 1) % 4
            # Flip color to next state
            new_state = (color_state + 1) % rule_len
            if new_state == 0:
                self.ant_grid.pop((r, c), None)
            else:
                self.ant_grid[(r, c)] = new_state
            # Move forward
            dr = [-1, 0, 1, 0]
            dc = [0, 1, 0, -1]
            ant["r"] = (r + dr[ant["dir"]]) % self.ant_rows
            ant["c"] = (c + dc[ant["dir"]]) % self.ant_cols
        self.ant_step_count += 1

    def _ant_init(self):
        """Initialize the ant grid and place ants."""
        max_y, max_x = self.stdscr.getmaxyx()
        self.ant_rows = max_y - 5
        self.ant_cols = (max_x - 1) // 2
        if self.ant_rows < 10:
            self.ant_rows = 10
        if self.ant_cols < 10:
            self.ant_cols = 10
        self.ant_grid = {}
        self.ant_step_count = 0
        self.ant_ants = []
        center_r = self.ant_rows // 2
        center_c = self.ant_cols // 2
        if self.ant_num_ants == 1:
            self.ant_ants.append({"r": center_r, "c": center_c, "dir": 0, "color_idx": 0})
        else:
            # Place ants symmetrically around center
            for i in range(self.ant_num_ants):
                angle_idx = (i * 4) // self.ant_num_ants  # spread directions
                offset = max(1, self.ant_rows // 8)
                dr = [-1, 0, 1, 0]
                dc = [0, 1, 0, -1]
                ar = center_r + dr[angle_idx % 4] * offset
                ac = center_c + dc[angle_idx % 4] * offset
                self.ant_ants.append({
                    "r": ar % self.ant_rows,
                    "c": ac % self.ant_cols,
                    "dir": angle_idx % 4,
                    "color_idx": i % len(self.ANT_COLORS),
                })

    def _enter_ant_mode(self):
        """Enter Langton's Ant mode — show menu first."""
        self.ant_menu = True
        self.ant_menu_sel = 0
        self._flash("Langton's Ant — select a rule")

    def _exit_ant_mode(self):
        """Exit Langton's Ant mode."""
        self.ant_mode = False
        self.ant_menu = False
        self.ant_running = False
        self.ant_grid = {}
        self.ant_ants = []
        self._flash("Langton's Ant mode OFF")

    def _handle_ant_menu_key(self, key: int) -> bool:
        """Handle keys in the ant rule selection menu."""
        if key == -1:
            return True
        n_presets = len(self.ANT_PRESETS)
        total_items = n_presets + 4  # custom rule, num ants, steps/frame, start
        if key == curses.KEY_UP or key == ord("k"):
            self.ant_menu_sel = (self.ant_menu_sel - 1) % total_items
            return True
        if key == curses.KEY_DOWN or key == ord("j"):
            self.ant_menu_sel = (self.ant_menu_sel + 1) % total_items
            return True
        if key == ord("q") or key == 27:
            self.ant_menu = False
            self._flash("Langton's Ant cancelled")
            return True
        if key in (10, 13, curses.KEY_ENTER):
            if self.ant_menu_sel < n_presets:
                self.ant_rule = self.ANT_PRESETS[self.ant_menu_sel][0]
            elif self.ant_menu_sel == n_presets:
                # Custom rule input
                txt = self._prompt_text("Enter rule string (R/L chars, e.g. RLR)")
                if txt is not None:
                    txt = txt.upper().strip()
                    if len(txt) >= 2 and all(ch in "RL" for ch in txt):
                        self.ant_rule = txt
                    else:
                        self._flash("Rule must be 2+ chars of R and L only")
                        return True
                else:
                    return True
            elif self.ant_menu_sel == n_presets + 1:
                # Cycle number of ants
                choices = [1, 2, 3, 4]
                idx = choices.index(self.ant_num_ants) if self.ant_num_ants in choices else 0
                self.ant_num_ants = choices[(idx + 1) % len(choices)]
                return True
            elif self.ant_menu_sel == n_presets + 2:
                # Cycle steps per frame
                choices = [1, 5, 10, 50, 100, 500]
                idx = choices.index(self.ant_steps_per_frame) if self.ant_steps_per_frame in choices else 0
                self.ant_steps_per_frame = choices[(idx + 1) % len(choices)]
                return True
            elif self.ant_menu_sel == n_presets + 3:
                # Start
                pass
            # Start the mode
            self.ant_menu = False
            self.ant_mode = True
            self.ant_running = False
            self._ant_init()
            self._flash(f"Langton's Ant [{self.ant_rule}] — Space=play, n=step, q=exit")
            return True
        return True

    def _handle_ant_key(self, key: int) -> bool:
        """Handle keys while in Langton's Ant mode."""
        if key == -1:
            return True
        if key == ord("q") or key == 27:
            self._exit_ant_mode()
            return True
        if key == ord(" "):
            self.ant_running = not self.ant_running
            self._flash("Playing" if self.ant_running else "Paused")
            return True
        if key == ord("n") or key == ord("."):
            self.ant_running = False
            for _ in range(self.ant_steps_per_frame):
                self._ant_step()
            return True
        if key == ord("r"):
            self._ant_init()
            self._flash(f"Reset [{self.ant_rule}]")
            return True
        if key == ord("R") or key == ord("m"):
            self.ant_mode = False
            self.ant_running = False
            self.ant_menu = True
            self.ant_menu_sel = 0
            return True
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
        if key == ord("+") or key == ord("="):
            choices = [1, 5, 10, 50, 100, 500]
            idx = choices.index(self.ant_steps_per_frame) if self.ant_steps_per_frame in choices else 0
            if idx < len(choices) - 1:
                self.ant_steps_per_frame = choices[idx + 1]
            self._flash(f"Steps/frame: {self.ant_steps_per_frame}")
            return True
        if key == ord("-"):
            choices = [1, 5, 10, 50, 100, 500]
            idx = choices.index(self.ant_steps_per_frame) if self.ant_steps_per_frame in choices else 0
            if idx > 0:
                self.ant_steps_per_frame = choices[idx - 1]
            self._flash(f"Steps/frame: {self.ant_steps_per_frame}")
            return True
        return True

    def _draw_ant_menu(self, max_y: int, max_x: int):
        """Draw the Langton's Ant rule selection menu."""
        title = "── Langton's Ant ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        subtitle = "Select a rule string (R=turn right, L=turn left per cell color)"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                               curses.color_pair(6))
        except curses.error:
            pass

        n_presets = len(self.ANT_PRESETS)
        for i, (rule, desc) in enumerate(self.ANT_PRESETS):
            y = 5 + i
            if y >= max_y - 8:
                break
            line = f"  {rule:<14s} {desc}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.ant_menu_sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            try:
                self.stdscr.addstr(y, 1, line, attr)
            except curses.error:
                pass

        extra_y = 5 + min(n_presets, max_y - 13)
        extra_items = [
            f"  [Custom] Enter rule string manually",
            f"  [Ants: {self.ant_num_ants}] Number of ants (press Enter to cycle)",
            f"  [Steps/frame: {self.ant_steps_per_frame}] Simulation speed multiplier",
            f"  >>> Start with rule={self.ant_rule}, ants={self.ant_num_ants} <<<",
        ]
        for i, line in enumerate(extra_items):
            y = extra_y + i
            idx = n_presets + i
            if y >= max_y - 2:
                break
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if idx == self.ant_menu_sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            try:
                self.stdscr.addstr(y, 1, line, attr)
            except curses.error:
                pass

        # Info section
        info_y = extra_y + len(extra_items) + 1
        if info_y < max_y - 3:
            info = "  Each char in the rule = what to do on that color (R=right turn, L=left turn)"
            try:
                self.stdscr.addstr(info_y, 1, info[:max_x - 2], curses.color_pair(1))
            except curses.error:
                pass
            if info_y + 1 < max_y - 2:
                info2 = "  Classic RL: highway emerges after ~10,000 steps"
                try:
                    self.stdscr.addstr(info_y + 1, 1, info2[:max_x - 2], curses.color_pair(1))
                except curses.error:
                    pass

        hint_y = max_y - 1
        if hint_y > 0:
            hint = " [j/k]=navigate [Enter]=select [q/Esc]=cancel"
            try:
                self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_ant(self, max_y: int, max_x: int):
        """Draw the Langton's Ant simulation."""
        # Title bar
        n_ants = len(self.ant_ants)
        title = f" Langton's Ant [{self.ant_rule}]  Ants: {n_ants}  Step: {self.ant_step_count}  Steps/frame: {self.ant_steps_per_frame}"
        state = " PLAY" if self.ant_running else " PAUSE"
        title += f"  {state}"
        title = title[:max_x - 1]
        try:
            self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        # Draw grid
        draw_start = 1
        draw_rows = max_y - 3
        draw_cols = (max_x - 1) // 2
        if draw_rows < 1:
            draw_rows = 1

        rule_len = len(self.ant_rule)
        # Color mapping for cell states
        state_colors = []
        for s in range(rule_len):
            state_colors.append(curses.color_pair(self.ANT_COLORS[s % len(self.ANT_COLORS)]))

        # Build set of ant positions for overlay
        ant_positions = {}
        for i, ant in enumerate(self.ant_ants):
            ant_positions[(ant["r"], ant["c"])] = i

        for y in range(draw_rows):
            row_idx = y
            if row_idx >= self.ant_rows:
                break
            screen_y = draw_start + y
            if screen_y >= max_y - 2:
                break
            # Build the line character by character
            for x in range(draw_cols):
                col_idx = x
                if col_idx >= self.ant_cols:
                    break
                sx = x * 2
                if sx + 1 >= max_x:
                    break
                cell_state = self.ant_grid.get((row_idx, col_idx), 0)
                if (row_idx, col_idx) in ant_positions:
                    # Draw ant marker
                    ant_idx = ant_positions[(row_idx, col_idx)]
                    ant_color = self.ANT_COLORS[ant_idx % len(self.ANT_COLORS)]
                    # Direction arrows: up, right, down, left
                    arrows = ["\u25b2 ", "\u25b6 ", "\u25bc ", "\u25c0 "]
                    ant_dir = self.ant_ants[ant_idx]["dir"]
                    ch = arrows[ant_dir]
                    try:
                        self.stdscr.addstr(screen_y, sx, ch,
                                           curses.color_pair(ant_color) | curses.A_BOLD)
                    except curses.error:
                        pass
                elif cell_state > 0:
                    color = state_colors[cell_state % rule_len]
                    try:
                        self.stdscr.addstr(screen_y, sx, "\u2588\u2588", color)
                    except curses.error:
                        pass
                # state 0 = empty, just leave blank

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            colored_cells = len(self.ant_grid)
            status = f" Rule: {self.ant_rule}  |  Step: {self.ant_step_count}  |  Colored: {colored_cells}  |  Ants: {n_ants}  |  Speed: {SPEED_LABELS[self.speed_idx]}"
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
                hint = " [Space]=play [n]=step [+/-]=steps/frame [r]=reset [R]=menu [</>]=speed [q]=exit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Wireworld mode ──────────────────────────────────────────────────

    # States: 0=empty, 1=conductor, 2=electron head, 3=electron tail
    WW_EMPTY = 0
    WW_CONDUCTOR = 1
    WW_HEAD = 2
    WW_TAIL = 3

    WW_PRESETS = [
        ("Diode", "One-way electron flow", {
            (2, 0): 2, (2, 1): 3, (2, 2): 1, (2, 3): 1,
            (1, 3): 1, (3, 3): 1, (1, 4): 1, (3, 4): 1,
            (2, 5): 1, (2, 6): 1, (2, 7): 1, (2, 8): 1,
        }),
        ("Clock", "Periodic electron emitter", {
            (2, 0): 1, (2, 1): 1, (2, 2): 1, (1, 3): 1, (3, 3): 1,
            (0, 4): 1, (4, 4): 1, (1, 5): 1, (3, 5): 1,
            (2, 6): 1, (2, 7): 2, (2, 8): 3,
        }),
        ("OR gate", "Output fires if any input has signal", {
            (0, 0): 2, (0, 1): 3, (0, 2): 1, (0, 3): 1, (1, 4): 1,
            (2, 5): 1, (2, 6): 1, (2, 7): 1,
            (3, 4): 1, (4, 0): 1, (4, 1): 1, (4, 2): 1, (4, 3): 1,
        }),
        ("AND gate", "Output fires only when both inputs fire", {
            (0, 0): 2, (0, 1): 3, (0, 2): 1, (0, 3): 1, (0, 4): 1,
            (1, 5): 1, (2, 6): 1, (2, 7): 1, (2, 8): 1,
            (3, 5): 1, (4, 0): 1, (4, 1): 1, (4, 2): 1, (4, 3): 1, (4, 4): 1,
            (1, 4): 1, (3, 4): 1,
        }),
        ("XOR gate", "Output fires when exactly one input fires", {
            (0, 0): 2, (0, 1): 3, (0, 2): 1, (0, 3): 1,
            (1, 4): 1, (1, 5): 1, (2, 6): 1,
            (3, 5): 1, (3, 4): 1, (2, 3): 1,
            (4, 0): 1, (4, 1): 1, (4, 2): 1, (4, 3): 1,
            (2, 7): 1, (2, 8): 1,
        }),
        ("Loop", "Electron circulating in a loop", {
            (0, 1): 1, (0, 2): 1, (0, 3): 1,
            (1, 0): 1, (1, 4): 1,
            (2, 0): 3, (2, 4): 1,
            (3, 0): 2, (3, 4): 1,
            (4, 1): 1, (4, 2): 1, (4, 3): 1,
        }),
        ("Empty grid", "Start with a blank grid for drawing", {}),
    ]

    def _ww_step(self):
        """Advance the Wireworld simulation by one generation."""
        new_grid: dict[tuple[int, int], int] = {}
        # Gather all cells that need checking: conductors and their neighbors
        check_cells: set[tuple[int, int]] = set()
        for (r, c), state in self.ww_grid.items():
            check_cells.add((r, c))
            if state == self.WW_CONDUCTOR:
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr = (r + dr) % self.ww_rows
                        nc = (c + dc) % self.ww_cols
                        check_cells.add((nr, nc))

        for (r, c) in check_cells:
            state = self.ww_grid.get((r, c), self.WW_EMPTY)
            if state == self.WW_EMPTY:
                continue  # empty stays empty
            elif state == self.WW_HEAD:
                new_grid[(r, c)] = self.WW_TAIL
            elif state == self.WW_TAIL:
                new_grid[(r, c)] = self.WW_CONDUCTOR
            elif state == self.WW_CONDUCTOR:
                # Count electron head neighbors
                head_count = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        nr = (r + dr) % self.ww_rows
                        nc = (c + dc) % self.ww_cols
                        if self.ww_grid.get((nr, nc), 0) == self.WW_HEAD:
                            head_count += 1
                if head_count == 1 or head_count == 2:
                    new_grid[(r, c)] = self.WW_HEAD
                else:
                    new_grid[(r, c)] = self.WW_CONDUCTOR

        self.ww_grid = new_grid
        self.ww_generation += 1

    def _ww_init(self, preset_cells: dict[tuple[int, int], int] | None = None):
        """Initialize the Wireworld grid."""
        max_y, max_x = self.stdscr.getmaxyx()
        self.ww_rows = max_y - 5
        self.ww_cols = (max_x - 1) // 2
        if self.ww_rows < 10:
            self.ww_rows = 10
        if self.ww_cols < 10:
            self.ww_cols = 10
        self.ww_grid = {}
        self.ww_generation = 0
        self.ww_cursor_r = self.ww_rows // 2
        self.ww_cursor_c = self.ww_cols // 2
        if preset_cells:
            # Center the preset on the grid
            if preset_cells:
                min_r = min(r for r, c in preset_cells)
                max_r = max(r for r, c in preset_cells)
                min_c = min(c for r, c in preset_cells)
                max_c = max(c for r, c in preset_cells)
                off_r = self.ww_rows // 2 - (min_r + max_r) // 2
                off_c = self.ww_cols // 2 - (min_c + max_c) // 2
                for (r, c), state in preset_cells.items():
                    nr = (r + off_r) % self.ww_rows
                    nc = (c + off_c) % self.ww_cols
                    self.ww_grid[(nr, nc)] = state

    def _enter_ww_mode(self):
        """Enter Wireworld mode — show preset menu first."""
        self.ww_menu = True
        self.ww_menu_sel = 0
        self._flash("Wireworld — select a preset or start empty")

    def _exit_ww_mode(self):
        """Exit Wireworld mode."""
        self.ww_mode = False
        self.ww_menu = False
        self.ww_running = False
        self.ww_grid = {}
        self._flash("Wireworld mode OFF")

    def _handle_ww_menu_key(self, key: int) -> bool:
        """Handle keys in the Wireworld preset selection menu."""
        if key == -1:
            return True
        n_presets = len(self.WW_PRESETS)
        if key == curses.KEY_UP or key == ord("k"):
            self.ww_menu_sel = (self.ww_menu_sel - 1) % n_presets
            return True
        if key == curses.KEY_DOWN or key == ord("j"):
            self.ww_menu_sel = (self.ww_menu_sel + 1) % n_presets
            return True
        if key == ord("q") or key == 27:
            self.ww_menu = False
            self._flash("Wireworld cancelled")
            return True
        if key in (10, 13, curses.KEY_ENTER):
            name, desc, cells = self.WW_PRESETS[self.ww_menu_sel]
            self.ww_menu = False
            self.ww_mode = True
            self.ww_running = False
            self.ww_drawing = True
            self._ww_init(cells if cells else None)
            self._flash(f"Wireworld [{name}] — e=draw, Space=play, n=step, q=exit")
            return True
        return True

    def _handle_ww_key(self, key: int) -> bool:
        """Handle keys while in Wireworld mode."""
        if key == -1:
            return True
        if key == ord("q") or key == 27:
            self._exit_ww_mode()
            return True
        if key == ord(" "):
            self.ww_running = not self.ww_running
            if self.ww_running:
                self.ww_drawing = False
            self._flash("Playing" if self.ww_running else "Paused")
            return True
        if key == ord("n") or key == ord("."):
            self.ww_running = False
            self._ww_step()
            return True
        if key == ord("r"):
            self._ww_init()
            self._flash("Grid cleared")
            return True
        if key == ord("R") or key == ord("m"):
            self.ww_mode = False
            self.ww_running = False
            self.ww_menu = True
            self.ww_menu_sel = 0
            return True
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
        # Cursor movement
        if key == curses.KEY_UP or key == ord("k"):
            self.ww_cursor_r = (self.ww_cursor_r - 1) % self.ww_rows
            if self.ww_drawing and not self.ww_running:
                self._ww_paint()
            return True
        if key == curses.KEY_DOWN or key == ord("j"):
            self.ww_cursor_r = (self.ww_cursor_r + 1) % self.ww_rows
            if self.ww_drawing and not self.ww_running:
                self._ww_paint()
            return True
        if key == curses.KEY_LEFT or key == ord("h"):
            self.ww_cursor_c = (self.ww_cursor_c - 1) % self.ww_cols
            if self.ww_drawing and not self.ww_running:
                self._ww_paint()
            return True
        if key == curses.KEY_RIGHT or key == ord("l"):
            self.ww_cursor_c = (self.ww_cursor_c + 1) % self.ww_cols
            if self.ww_drawing and not self.ww_running:
                self._ww_paint()
            return True
        # Drawing controls
        if key == ord("e"):
            self.ww_drawing = not self.ww_drawing
            self._flash("Draw mode ON" if self.ww_drawing else "Draw mode OFF")
            return True
        if key == ord("1"):
            self.ww_draw_state = self.WW_CONDUCTOR
            self._flash("Brush: conductor (orange)")
            return True
        if key == ord("2"):
            self.ww_draw_state = self.WW_HEAD
            self._flash("Brush: electron head (blue)")
            return True
        if key == ord("3"):
            self.ww_draw_state = self.WW_TAIL
            self._flash("Brush: electron tail (white)")
            return True
        if key == ord("0"):
            self.ww_draw_state = self.WW_EMPTY
            self._flash("Brush: eraser")
            return True
        # Toggle cell at cursor
        if key == 10 or key == 13 or key == curses.KEY_ENTER:
            pos = (self.ww_cursor_r, self.ww_cursor_c)
            current = self.ww_grid.get(pos, self.WW_EMPTY)
            # Cycle through states: empty -> conductor -> head -> tail -> empty
            next_state = (current + 1) % 4
            if next_state == self.WW_EMPTY:
                self.ww_grid.pop(pos, None)
            else:
                self.ww_grid[pos] = next_state
            return True
        return True

    def _ww_paint(self):
        """Paint the current draw_state at cursor position."""
        pos = (self.ww_cursor_r, self.ww_cursor_c)
        if self.ww_draw_state == self.WW_EMPTY:
            self.ww_grid.pop(pos, None)
        else:
            self.ww_grid[pos] = self.ww_draw_state

    def _draw_ww_menu(self, max_y: int, max_x: int):
        """Draw the Wireworld preset selection menu."""
        title = "── Wireworld ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        subtitle = "4-state cellular automaton for circuit simulation"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                               curses.color_pair(6))
        except curses.error:
            pass

        n_presets = len(self.WW_PRESETS)
        for i, (name, desc, _cells) in enumerate(self.WW_PRESETS):
            y = 5 + i
            if y >= max_y - 8:
                break
            line = f"  {name:<14s} {desc}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.ww_menu_sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            try:
                self.stdscr.addstr(y, 1, line, attr)
            except curses.error:
                pass

        # Info section
        info_y = 5 + min(n_presets, max_y - 13) + 1
        info_lines = [
            "States: empty (black), conductor (orange), electron head (blue), electron tail (white)",
            "Rules: head->tail, tail->conductor, conductor->head if 1 or 2 head neighbors",
            "Draw circuits, add electrons, and watch signals flow!",
        ]
        for i, info in enumerate(info_lines):
            y = info_y + i
            if y >= max_y - 2:
                break
            try:
                self.stdscr.addstr(y, 2, info[:max_x - 3], curses.color_pair(1))
            except curses.error:
                pass

        hint_y = max_y - 1
        if hint_y > 0:
            hint = " [j/k]=navigate [Enter]=select [q/Esc]=cancel"
            try:
                self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_ww(self, max_y: int, max_x: int):
        """Draw the Wireworld simulation."""
        # Title bar
        heads = sum(1 for s in self.ww_grid.values() if s == self.WW_HEAD)
        tails = sum(1 for s in self.ww_grid.values() if s == self.WW_TAIL)
        conductors = sum(1 for s in self.ww_grid.values() if s == self.WW_CONDUCTOR)
        title = f" Wireworld  Gen: {self.ww_generation}  Conductors: {conductors}  Heads: {heads}  Tails: {tails}"
        state = " PLAY" if self.ww_running else " PAUSE"
        if self.ww_drawing and not self.ww_running:
            brush_names = {0: "eraser", 1: "conductor", 2: "head", 3: "tail"}
            state += f"  DRAW [{brush_names[self.ww_draw_state]}]"
        title += f"  {state}"
        title = title[:max_x - 1]
        try:
            self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        # Draw grid
        draw_start = 1
        draw_rows = max_y - 3
        draw_cols = (max_x - 1) // 2
        if draw_rows < 1:
            draw_rows = 1

        # Color mapping: conductor=yellow/orange(3), head=blue(5), tail=white(8)
        for y in range(draw_rows):
            row_idx = y
            if row_idx >= self.ww_rows:
                break
            screen_y = draw_start + y
            if screen_y >= max_y - 2:
                break
            for x in range(draw_cols):
                col_idx = x
                if col_idx >= self.ww_cols:
                    break
                sx = x * 2
                if sx + 1 >= max_x:
                    break
                cell_state = self.ww_grid.get((row_idx, col_idx), self.WW_EMPTY)
                is_cursor = (row_idx == self.ww_cursor_r and col_idx == self.ww_cursor_c)
                if is_cursor and not self.ww_running:
                    # Draw cursor
                    if cell_state == self.WW_EMPTY:
                        ch = "[]"
                    else:
                        ch = "\u2588\u2588"
                    try:
                        self.stdscr.addstr(screen_y, sx, ch,
                                           curses.color_pair(7) | curses.A_BOLD)
                    except curses.error:
                        pass
                elif cell_state == self.WW_HEAD:
                    try:
                        self.stdscr.addstr(screen_y, sx, "\u2588\u2588",
                                           curses.color_pair(5))  # blue
                    except curses.error:
                        pass
                elif cell_state == self.WW_TAIL:
                    try:
                        self.stdscr.addstr(screen_y, sx, "\u2588\u2588",
                                           curses.color_pair(8))  # white
                    except curses.error:
                        pass
                elif cell_state == self.WW_CONDUCTOR:
                    try:
                        self.stdscr.addstr(screen_y, sx, "\u2588\u2588",
                                           curses.color_pair(3))  # yellow/orange
                    except curses.error:
                        pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            total_cells = len(self.ww_grid)
            status = f" Gen: {self.ww_generation}  |  Cells: {total_cells} (C:{conductors} H:{heads} T:{tails})  |  Speed: {SPEED_LABELS[self.speed_idx]}"
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
                hint = " [Space]=play [n]=step [e]=draw [0-3]=brush [Enter]=cycle [r]=clear [R]=menu [</>]=speed [q]=exit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── Falling Sand particle simulation ────────────────────────────────────
    # Elements: 0=empty, 1=sand, 2=water, 3=fire, 4=stone, 5=plant
    SAND_EMPTY = 0
    SAND_SAND = 1
    SAND_WATER = 2
    SAND_FIRE = 3
    SAND_STONE = 4
    SAND_PLANT = 5

    SAND_ELEM_NAMES = {0: "empty", 1: "sand", 2: "water", 3: "fire", 4: "stone", 5: "plant"}
    SAND_ELEM_COLORS = {
        1: 3,   # sand = yellow
        2: 5,   # water = blue
        3: 2,   # fire = red
        4: 8,   # stone = white
        5: 4,   # plant = green
    }
    SAND_ELEM_CHARS = {
        1: "\u2591\u2591",  # sand: light shade
        2: "\u2248\u2248",  # water: waves
        3: "\u2588\u2588",  # fire: full block
        4: "\u2593\u2593",  # stone: dark shade
        5: "\u2588\u2588",  # plant: full block
    }

    SAND_PRESETS = [
        ("Hourglass", "Sand falling through a narrow gap", "hourglass"),
        ("Rainfall", "Water drops falling on stone platforms", "rainfall"),
        ("Bonfire", "Fire burning through a plant forest", "bonfire"),
        ("Sandbox", "Empty grid — draw freely", "empty"),
        ("Lava Lamp", "Water and sand mixing", "lavalamp"),
    ]

    def _sand_build_preset(self, name: str) -> dict[tuple[int, int], tuple[int, int]]:
        """Build a preset scene for falling sand."""
        grid: dict[tuple[int, int], tuple[int, int]] = {}
        mid_r = self.sand_rows // 2
        mid_c = self.sand_cols // 2

        if name == "hourglass":
            # Stone walls forming an hourglass shape
            for c in range(mid_c - 12, mid_c + 13):
                grid[(2, c)] = (self.SAND_STONE, 0)
                grid[(self.sand_rows - 3, c)] = (self.SAND_STONE, 0)
            for r in range(2, self.sand_rows - 2):
                grid[(r, mid_c - 12)] = (self.SAND_STONE, 0)
                grid[(r, mid_c + 12)] = (self.SAND_STONE, 0)
            # Narrow gap in the middle
            gap_r = mid_r
            for c in range(mid_c - 12, mid_c - 1):
                grid[(gap_r, c)] = (self.SAND_STONE, 0)
            for c in range(mid_c + 2, mid_c + 13):
                grid[(gap_r, c)] = (self.SAND_STONE, 0)
            # Fill top half with sand
            for r in range(3, gap_r):
                for c in range(mid_c - 11, mid_c + 12):
                    grid[(r, c)] = (self.SAND_SAND, 0)

        elif name == "rainfall":
            # Stone platforms
            for c in range(mid_c - 10, mid_c - 2):
                grid[(mid_r, c)] = (self.SAND_STONE, 0)
            for c in range(mid_c + 3, mid_c + 11):
                grid[(mid_r, c)] = (self.SAND_STONE, 0)
            for c in range(mid_c - 6, mid_c + 7):
                grid[(mid_r + 8, c)] = (self.SAND_STONE, 0)
            # Water at top
            for r in range(2, 5):
                for c in range(mid_c - 8, mid_c + 9):
                    grid[(r, c)] = (self.SAND_WATER, 0)

        elif name == "bonfire":
            # Ground
            for c in range(mid_c - 15, mid_c + 16):
                grid[(self.sand_rows - 4, c)] = (self.SAND_STONE, 0)
            # Plant forest
            for r in range(mid_r, self.sand_rows - 4):
                for c in range(mid_c - 12, mid_c + 13):
                    if random.random() < 0.6:
                        grid[(r, c)] = (self.SAND_PLANT, 0)
            # Fire at bottom center
            for r in range(self.sand_rows - 7, self.sand_rows - 4):
                for c in range(mid_c - 2, mid_c + 3):
                    grid[(r, c)] = (self.SAND_FIRE, 0)

        elif name == "lavalamp":
            # Walls
            for r in range(2, self.sand_rows - 2):
                grid[(r, mid_c - 8)] = (self.SAND_STONE, 0)
                grid[(r, mid_c + 8)] = (self.SAND_STONE, 0)
            for c in range(mid_c - 8, mid_c + 9):
                grid[(self.sand_rows - 3, c)] = (self.SAND_STONE, 0)
            # Alternating layers of sand and water
            for r in range(self.sand_rows - 10, self.sand_rows - 3):
                for c in range(mid_c - 7, mid_c + 8):
                    if (r // 2) % 2 == 0:
                        grid[(r, c)] = (self.SAND_SAND, 0)
                    else:
                        grid[(r, c)] = (self.SAND_WATER, 0)

        return grid

    def _sand_init(self, preset: str | None = None):
        """Initialize the falling sand grid."""
        max_y, max_x = self.stdscr.getmaxyx()
        self.sand_rows = max_y - 3
        self.sand_cols = (max_x - 1) // 2
        if self.sand_rows < 10:
            self.sand_rows = 10
        if self.sand_cols < 10:
            self.sand_cols = 10
        self.sand_grid = {}
        self.sand_generation = 0
        self.sand_cursor_r = self.sand_rows // 2
        self.sand_cursor_c = self.sand_cols // 2
        if preset and preset != "empty":
            self.sand_grid = self._sand_build_preset(preset)

    def _sand_step(self):
        """Advance the falling-sand simulation by one tick."""
        new_grid: dict[tuple[int, int], tuple[int, int]] = {}
        # Copy all static elements first (stone)
        for (r, c), (elem, age) in self.sand_grid.items():
            if elem == self.SAND_STONE:
                new_grid[(r, c)] = (elem, age)

        # Track which cells are occupied in new_grid as we go
        # Process from bottom to top so falling works correctly
        moved: set[tuple[int, int]] = set()

        # Process rows bottom-to-top for gravity elements
        for r in range(self.sand_rows - 1, -1, -1):
            # Randomize left-right processing to avoid bias
            cols = list(range(self.sand_cols))
            random.shuffle(cols)
            for c in cols:
                if (r, c) in moved:
                    continue
                cell = self.sand_grid.get((r, c))
                if cell is None:
                    continue
                elem, age = cell

                if elem == self.SAND_STONE:
                    continue  # already copied

                if elem == self.SAND_SAND:
                    # Sand: fall down, try diagonals, sink through water
                    nr = r + 1
                    if nr < self.sand_rows:
                        below = new_grid.get((nr, c))
                        below_orig = self.sand_grid.get((nr, c))
                        if below is None and (below_orig is None or (nr, c) in moved):
                            new_grid[(nr, c)] = (elem, age + 1)
                            moved.add((nr, c))
                            continue
                        # Swap with water below
                        if below is not None and below[0] == self.SAND_WATER:
                            new_grid[(nr, c)] = (elem, age + 1)
                            new_grid[(r, c)] = (self.SAND_WATER, below[1])
                            moved.add((nr, c))
                            moved.add((r, c))
                            continue
                        # Try diagonal
                        dirs = [-1, 1]
                        random.shuffle(dirs)
                        fell = False
                        for dc in dirs:
                            nc = c + dc
                            if 0 <= nc < self.sand_cols and nr < self.sand_rows:
                                diag = new_grid.get((nr, nc))
                                diag_orig = self.sand_grid.get((nr, nc))
                                if diag is None and (diag_orig is None or (nr, nc) in moved):
                                    new_grid[(nr, nc)] = (elem, age + 1)
                                    moved.add((nr, nc))
                                    fell = True
                                    break
                        if fell:
                            continue
                    # Stay in place
                    new_grid[(r, c)] = (elem, age)
                    moved.add((r, c))

                elif elem == self.SAND_WATER:
                    # Water: fall down, then flow sideways
                    nr = r + 1
                    if nr < self.sand_rows:
                        below = new_grid.get((nr, c))
                        below_orig = self.sand_grid.get((nr, c))
                        if below is None and (below_orig is None or (nr, c) in moved):
                            new_grid[(nr, c)] = (elem, age + 1)
                            moved.add((nr, c))
                            continue
                        # Try diagonal down
                        dirs = [-1, 1]
                        random.shuffle(dirs)
                        fell = False
                        for dc in dirs:
                            nc = c + dc
                            if 0 <= nc < self.sand_cols:
                                diag = new_grid.get((nr, nc))
                                diag_orig = self.sand_grid.get((nr, nc))
                                if diag is None and (diag_orig is None or (nr, nc) in moved):
                                    new_grid[(nr, nc)] = (elem, age + 1)
                                    moved.add((nr, nc))
                                    fell = True
                                    break
                        if fell:
                            continue
                    # Try flowing sideways
                    dirs = [-1, 1]
                    random.shuffle(dirs)
                    flowed = False
                    for dc in dirs:
                        nc = c + dc
                        if 0 <= nc < self.sand_cols:
                            side = new_grid.get((r, nc))
                            side_orig = self.sand_grid.get((r, nc))
                            if side is None and (side_orig is None or (r, nc) in moved):
                                new_grid[(r, nc)] = (elem, age + 1)
                                moved.add((r, nc))
                                flowed = True
                                break
                    if flowed:
                        continue
                    # Stay in place
                    new_grid[(r, c)] = (elem, age)
                    moved.add((r, c))

                elif elem == self.SAND_FIRE:
                    # Fire: rises upward, has limited lifetime, random flicker
                    if age > 12 + random.randint(0, 8):
                        # Fire dies out
                        continue
                    # Ignite adjacent plants
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                        ar, ac = r + dr, c + dc
                        if 0 <= ar < self.sand_rows and 0 <= ac < self.sand_cols:
                            adj = self.sand_grid.get((ar, ac))
                            if adj and adj[0] == self.SAND_PLANT:
                                if random.random() < 0.4:
                                    new_grid[(ar, ac)] = (self.SAND_FIRE, 0)
                                    moved.add((ar, ac))
                    # Try to rise
                    nr = r - 1
                    if nr >= 0 and random.random() < 0.7:
                        dc = random.choice([-1, 0, 0, 1])
                        nc = c + dc
                        if 0 <= nc < self.sand_cols:
                            above = new_grid.get((nr, nc))
                            above_orig = self.sand_grid.get((nr, nc))
                            if above is None and (above_orig is None or (nr, nc) in moved):
                                new_grid[(nr, nc)] = (elem, age + 1)
                                moved.add((nr, nc))
                                continue
                    # Stay or flicker
                    new_grid[(r, c)] = (elem, age + 1)
                    moved.add((r, c))

                elif elem == self.SAND_PLANT:
                    # Plant: grows when adjacent to water, burns near fire
                    # Check for fire neighbors (already handled by fire spreading)
                    # Grow into empty adjacent cells if water is nearby
                    has_water = False
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ar, ac = r + dr, c + dc
                        if 0 <= ar < self.sand_rows and 0 <= ac < self.sand_cols:
                            adj = self.sand_grid.get((ar, ac))
                            if adj and adj[0] == self.SAND_WATER:
                                has_water = True
                                break
                    if has_water and random.random() < 0.05:
                        # Try to grow in a random direction (prefer upward)
                        grow_dirs = [(-1, 0), (-1, -1), (-1, 1), (0, -1), (0, 1)]
                        random.shuffle(grow_dirs)
                        for dr, dc in grow_dirs:
                            gr, gc = r + dr, c + dc
                            if 0 <= gr < self.sand_rows and 0 <= gc < self.sand_cols:
                                if (gr, gc) not in new_grid and (gr, gc) not in self.sand_grid:
                                    new_grid[(gr, gc)] = (self.SAND_PLANT, 0)
                                    moved.add((gr, gc))
                                    break
                    # Stay in place
                    if (r, c) not in new_grid:
                        new_grid[(r, c)] = (elem, age + 1)
                        moved.add((r, c))

        self.sand_grid = new_grid
        self.sand_generation += 1

    def _enter_sand_mode(self):
        """Enter falling-sand mode — show preset menu."""
        self.sand_menu = True
        self.sand_menu_sel = 0
        self._flash("Falling Sand — select a scene")

    def _exit_sand_mode(self):
        """Exit falling-sand mode."""
        self.sand_mode = False
        self.sand_menu = False
        self.sand_running = False
        self.sand_grid = {}
        self._flash("Falling Sand mode OFF")

    def _handle_sand_menu_key(self, key: int) -> bool:
        """Handle keys in the falling-sand preset menu."""
        if key == -1:
            return True
        n = len(self.SAND_PRESETS)
        if key == curses.KEY_UP or key == ord("k"):
            self.sand_menu_sel = (self.sand_menu_sel - 1) % n
            return True
        if key == curses.KEY_DOWN or key == ord("j"):
            self.sand_menu_sel = (self.sand_menu_sel + 1) % n
            return True
        if key == ord("q") or key == 27:
            self.sand_menu = False
            self._flash("Falling Sand cancelled")
            return True
        if key in (10, 13, curses.KEY_ENTER):
            name, desc, preset_id = self.SAND_PRESETS[self.sand_menu_sel]
            self.sand_menu = False
            self.sand_mode = True
            self.sand_running = False
            self._sand_init(preset_id)
            self._flash(f"Falling Sand [{name}] — Space=play, arrows=move, 1-5=brush, Enter=place, q=exit")
            return True
        return True

    def _handle_sand_key(self, key: int) -> bool:
        """Handle keys while in falling-sand mode."""
        if key == -1:
            return True
        if key == ord("q") or key == 27:
            self._exit_sand_mode()
            return True
        if key == ord(" "):
            self.sand_running = not self.sand_running
            self._flash("Playing" if self.sand_running else "Paused")
            return True
        if key == ord("n") or key == ord("."):
            self.sand_running = False
            self._sand_step()
            return True
        if key == ord("r"):
            self._sand_init()
            self._flash("Grid cleared")
            return True
        if key == ord("R") or key == ord("m"):
            self.sand_mode = False
            self.sand_running = False
            self.sand_menu = True
            self.sand_menu_sel = 0
            return True
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
        # Brush selection
        if key == ord("1"):
            self.sand_brush = self.SAND_SAND
            self._flash("Brush: sand")
            return True
        if key == ord("2"):
            self.sand_brush = self.SAND_WATER
            self._flash("Brush: water")
            return True
        if key == ord("3"):
            self.sand_brush = self.SAND_FIRE
            self._flash("Brush: fire")
            return True
        if key == ord("4"):
            self.sand_brush = self.SAND_STONE
            self._flash("Brush: stone")
            return True
        if key == ord("6"):
            self.sand_brush = self.SAND_PLANT
            self._flash("Brush: plant")
            return True
        if key == ord("0"):
            self.sand_brush = self.SAND_EMPTY
            self._flash("Brush: eraser")
            return True
        # Brush size
        if key == ord("+") or key == ord("="):
            self.sand_brush_size = min(self.sand_brush_size + 1, 5)
            self._flash(f"Brush size: {self.sand_brush_size}")
            return True
        if key == ord("-"):
            self.sand_brush_size = max(self.sand_brush_size - 1, 1)
            self._flash(f"Brush size: {self.sand_brush_size}")
            return True
        # Cursor movement
        if key == curses.KEY_UP or key == ord("k"):
            self.sand_cursor_r = max(0, self.sand_cursor_r - 1)
            return True
        if key == curses.KEY_DOWN or key == ord("j"):
            self.sand_cursor_r = min(self.sand_rows - 1, self.sand_cursor_r + 1)
            return True
        if key == curses.KEY_LEFT or key == ord("h"):
            self.sand_cursor_c = max(0, self.sand_cursor_c - 1)
            return True
        if key == curses.KEY_RIGHT or key == ord("l"):
            self.sand_cursor_c = min(self.sand_cols - 1, self.sand_cursor_c + 1)
            return True
        # Place element at cursor
        if key == 10 or key == 13 or key == curses.KEY_ENTER:
            self._sand_paint()
            return True
        # Draw mode: d to paint while moving
        if key == ord("d"):
            self._sand_paint()
            self._flash("Painted — use arrows + Enter to draw more")
            return True
        return True

    def _sand_paint(self):
        """Paint the current brush at cursor position with brush size."""
        sz = self.sand_brush_size
        for dr in range(-sz + 1, sz):
            for dc in range(-sz + 1, sz):
                pr, pc = self.sand_cursor_r + dr, self.sand_cursor_c + dc
                if 0 <= pr < self.sand_rows and 0 <= pc < self.sand_cols:
                    if self.sand_brush == self.SAND_EMPTY:
                        self.sand_grid.pop((pr, pc), None)
                    else:
                        self.sand_grid[(pr, pc)] = (self.sand_brush, 0)

    def _draw_sand_menu(self, max_y: int, max_x: int):
        """Draw the falling-sand preset selection menu."""
        title = "── Falling Sand ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        subtitle = "Gravity-based particle simulation with interacting elements"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                               curses.color_pair(6))
        except curses.error:
            pass

        n = len(self.SAND_PRESETS)
        for i, (name, desc, _pid) in enumerate(self.SAND_PRESETS):
            y = 5 + i
            if y >= max_y - 10:
                break
            line = f"  {name:<14s} {desc}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.sand_menu_sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            try:
                self.stdscr.addstr(y, 1, line, attr)
            except curses.error:
                pass

        info_y = 5 + min(n, max_y - 15) + 1
        info_lines = [
            "Elements: sand (falls, piles), water (flows), fire (rises, burns),",
            "          stone (static walls), plant (grows near water, burns)",
            "",
            "Sand sinks through water. Fire ignites plants. Plants grow near water.",
        ]
        for i, info in enumerate(info_lines):
            y = info_y + i
            if y >= max_y - 2:
                break
            try:
                self.stdscr.addstr(y, 2, info[:max_x - 3], curses.color_pair(1))
            except curses.error:
                pass

        hint_y = max_y - 1
        if hint_y > 0:
            hint = " [j/k]=navigate [Enter]=select [q/Esc]=cancel"
            try:
                self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_sand(self, max_y: int, max_x: int):
        """Draw the falling-sand simulation."""
        # Count elements
        counts: dict[int, int] = {}
        for (_, _), (elem, _) in self.sand_grid.items():
            counts[elem] = counts.get(elem, 0) + 1

        # Title bar
        brush_name = self.SAND_ELEM_NAMES.get(self.sand_brush, "?")
        title = f" Falling Sand  Tick: {self.sand_generation}  Particles: {len(self.sand_grid)}"
        state = " PLAY" if self.sand_running else f" PAUSE  Brush: {brush_name} (sz:{self.sand_brush_size})"
        title += f"  {state}"
        title = title[:max_x - 1]
        try:
            self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        # Draw grid
        draw_start = 1
        draw_rows = max_y - 3
        draw_cols = (max_x - 1) // 2
        if draw_rows < 1:
            draw_rows = 1

        for y in range(draw_rows):
            if y >= self.sand_rows:
                break
            screen_y = draw_start + y
            if screen_y >= max_y - 2:
                break
            for x in range(draw_cols):
                if x >= self.sand_cols:
                    break
                sx = x * 2
                if sx + 1 >= max_x:
                    break
                cell = self.sand_grid.get((y, x))
                is_cursor = (y == self.sand_cursor_r and x == self.sand_cursor_c)

                if is_cursor and not self.sand_running:
                    if cell is None:
                        ch = "[]"
                    else:
                        ch = "\u2588\u2588"
                    try:
                        self.stdscr.addstr(screen_y, sx, ch,
                                           curses.color_pair(7) | curses.A_BOLD)
                    except curses.error:
                        pass
                elif cell is not None:
                    elem, age = cell
                    color = self.SAND_ELEM_COLORS.get(elem, 1)
                    ch = self.SAND_ELEM_CHARS.get(elem, "\u2588\u2588")
                    attr = curses.color_pair(color)
                    # Fire flickers
                    if elem == self.SAND_FIRE:
                        if age > 10:
                            attr = curses.color_pair(3)  # yellow as it dies
                        if random.random() < 0.3:
                            attr |= curses.A_BOLD
                    # Plant gets brighter with age
                    if elem == self.SAND_PLANT and age > 5:
                        attr |= curses.A_BOLD
                    try:
                        self.stdscr.addstr(screen_y, sx, ch, attr)
                    except curses.error:
                        pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            parts = []
            for eid, ename in sorted(self.SAND_ELEM_NAMES.items()):
                if eid == 0:
                    continue
                cnt = counts.get(eid, 0)
                if cnt > 0:
                    parts.append(f"{ename}:{cnt}")
            status = f" Tick: {self.sand_generation}  |  {' '.join(parts)}  |  Speed: {SPEED_LABELS[self.speed_idx]}"
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
                hint = " [Space]=play [n]=step [1-4,6]=element [0]=erase [+/-]=size [Enter]=place [r]=clear [R]=menu [q]=exit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    def _draw_help(self, max_y: int, max_x: int):
        help_lines = [
            "╔══════════════════════════════════════════════╗",
            "║         Game of Life — Help                  ║",
            "╠══════════════════════════════════════════════╣",
            "║                                              ║",
            "║  Space     Play / Pause auto-advance         ║",
            "║  n / .     Step one generation                ║",
            "║  u         Rewind one generation              ║",
            "║  [ / ]     Scrub timeline back/forward 10     ║",
            "║  b         Bookmark current generation        ║",
            "║  B         List/jump to bookmarks             ║",
            "║  + / -     Zoom in / out (density glyphs)     ║",
            "║  0         Reset zoom to 1:1                  ║",
            "║  < / >     Decrease / increase speed          ║",
            "║  Arrows    Move cursor (also vim hjkl)        ║",
            "║  e         Toggle cell under cursor           ║",
            "║  d         Draw mode (paint while moving)     ║",
            "║  x         Erase mode (erase while moving)    ║",
            "║  Esc       Exit draw/erase mode               ║",
            "║  p         Open pattern selector              ║",
            "║  t         Stamp pattern at cursor            ║",
            "║  R         Rule editor (B../S.. presets)      ║",
            "║  W         Blueprint: select region & save      ║",
            "║  T         Stamp from blueprint library        ║",
            "║  F         Pattern search (find known shapes) ║",
            "║  H         Toggle heatmap (cell activity)      ║",
            "║  I         Toggle 3D isometric view            ║",
            "║  V         Compare two rules side-by-side     ║",
            "║  Z         Race 2-4 rules with scoreboard      ║",
            "║  N         Multiplayer (host or connect)       ║",
            "║  C         Puzzle / challenge mode              ║",
            "║  E         Evolution (genetic algorithm)        ║",
            "║  M         Toggle sound/music mode             ║",
            "║  1         Wolfram 1D automaton (Rules 0-255) ║",
            "║  2         Langton's Ant (turmite simulation) ║",
            "║  3         Hexagonal grid (6 neighbors)       ║",
            "║  4         Wireworld (circuit simulation)     ║",
            "║  5         Falling Sand (particle sim)        ║",
            "║  G         Record/stop GIF (export frames)   ║",
            "║  i         Import RLE pattern file            ║",
            "║  r         Fill grid randomly                 ║",
            "║  s         Save grid state to file            ║",
            "║  o         Open/load a saved state            ║",
            "║  c         Clear grid                         ║",
            "║  q         Quit                               ║",
            "║  ? / h     Show this help                     ║",
            "║                                              ║",
            "║  Press any key to close help                  ║",
            "╚══════════════════════════════════════════════╝",
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
            pat = self._get_pattern(name)
            desc = pat["description"] if pat else ""
            is_bp = name in self.blueprints
            prefix = "[BP] " if is_bp else ""
            line = f"  {prefix}{name:<20s} {desc}"
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
    parser.add_argument(
        "--host", type=int, nargs="?", const=MP_DEFAULT_PORT, default=None,
        metavar="PORT",
        help=f"Host a multiplayer game (default port: {MP_DEFAULT_PORT})",
    )
    parser.add_argument(
        "--connect", type=str, default=None,
        metavar="HOST:PORT",
        help="Connect to a multiplayer game (e.g. 192.168.1.5:7654)",
    )
    args = parser.parse_args()

    if args.list_patterns:
        print("Available patterns:")
        for name in sorted(PATTERNS.keys()):
            print(f"  {name:<20s} {PATTERNS[name]['description']}")
        sys.exit(0)

    def start(stdscr):
        app = App(stdscr, args.pattern, args.rows, args.cols)
        # Auto-start multiplayer if CLI flags given
        if args.host is not None:
            app.mp_host_port = args.host
            net = MultiplayerNet()
            if not net.start_host(args.host):
                app._flash(f"Cannot bind to port {args.host}")
            else:
                app.mp_net = net
                app.mp_mode = True
                app.mp_role = "host"
                app.mp_player = 1
                app.mp_phase = "lobby"
                app.running = False
                app._flash(f"Hosting on port {args.host} — waiting for opponent...")
        elif args.connect is not None:
            addr = args.connect
            if ":" in addr:
                parts = addr.rsplit(":", 1)
                host, port = parts[0], int(parts[1])
            else:
                host, port = addr, MP_DEFAULT_PORT
            net = MultiplayerNet()
            if not net.connect(host, port):
                app._flash(f"Cannot connect to {host}:{port}")
            else:
                app.mp_net = net
                app.mp_mode = True
                app.mp_role = "client"
                app.mp_player = 2
                app.mp_phase = "lobby"
                app.running = False
                app.mp_connect_addr = addr
                app._flash("Connected! Waiting for game setup...")
        app.run()

    try:
        curses.wrapper(start)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
