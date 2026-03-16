"""Mode: Rule Phylogenetics — comparative genomics for CA rules.

Treats B/S rule sets as genetic sequences, builds evolutionary family trees,
identifies conserved behavioral motifs, and traces lineage from Genesis
Protocol's Hall of Fame breeding history.
"""

import curses
import json
import math
import os
import random
import time

from life.constants import SAVE_DIR
from life.grid import Grid

# ── Constants ────────────────────────────────────────────────────────

_GALLERY_FILE = os.path.join(SAVE_DIR, "genesis_hall_of_fame.json")

# All possible B/S positions (0-8)
_ALL_POSITIONS = set(range(9))

# Well-known rules for reference
_KNOWN_RULES = {
    "B3/S23": "Life",
    "B36/S23": "HighLife",
    "B3678/S34678": "Day & Night",
    "B1357/S1357": "Replicator",
    "B2/S": "Seeds",
    "B368/S245": "Morley",
    "B3/S012345678": "Life w/o Death",
}

# Behavioral motif library
_MOTIFS = [
    {"name": "Life core", "birth": {3}, "survival": {2, 3},
     "behavior": "gliders, oscillators, still lifes"},
    {"name": "Replicator seed", "birth": {1}, "survival": set(),
     "behavior": "self-replication, explosive growth"},
    {"name": "Day/Night balance", "birth": {3, 6, 7, 8}, "survival": {3, 4, 6, 7, 8},
     "behavior": "complementary symmetry, complex structures"},
    {"name": "HighLife extension", "birth": {3, 6}, "survival": {2, 3},
     "behavior": "replicating gliders"},
    {"name": "Chaos engine", "birth": {2, 3}, "survival": {2, 3},
     "behavior": "rapid chaotic expansion"},
    {"name": "Stability anchor", "birth": set(), "survival": {2, 3},
     "behavior": "decay toward still lifes"},
    {"name": "Low-birth", "birth": {1, 2}, "survival": set(),
     "behavior": "explosive then collapse"},
    {"name": "Dense survival", "birth": set(), "survival": {4, 5, 6, 7, 8},
     "behavior": "persistent dense regions"},
]

_SPARKLINE = "▁▂▃▄▅▆▇█"
_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]

# Classification colors
_CLASS_COLORS = {
    "glider": 3, "oscillator": 4, "still_life": 5,
    "chaotic": 2, "expanding": 6, "collapsing": 1,
    "replicator": 3, "complex": 4, "dead": 0,
    "unknown": 7,
}


# ── Genome operations ────────────────────────────────────────────────

def _rule_to_genome(label):
    """Convert 'B36/S23' to a binary genome vector (18 bits: B0-B8, S0-S8)."""
    genome = [0] * 18
    parts = label.upper().replace(" ", "").split("/")
    for part in parts:
        if part.startswith("B"):
            for ch in part[1:]:
                if ch.isdigit():
                    genome[int(ch)] = 1
        elif part.startswith("S"):
            for ch in part[1:]:
                if ch.isdigit():
                    genome[9 + int(ch)] = 1
    return genome


def _genome_to_rule(genome):
    """Convert 18-bit genome back to 'B.../S...' label."""
    b = "".join(str(i) for i in range(9) if genome[i])
    s = "".join(str(i) for i in range(9) if genome[9 + i])
    return f"B{b}/S{s}"


def _parse_bs(label):
    """Parse 'B36/S23' into (birth_set, survival_set)."""
    birth, surv = set(), set()
    parts = label.upper().replace(" ", "").split("/")
    for part in parts:
        if part.startswith("B"):
            birth = {int(ch) for ch in part[1:] if ch.isdigit()}
        elif part.startswith("S"):
            surv = {int(ch) for ch in part[1:] if ch.isdigit()}
    return birth, surv


def _hamming_distance(g1, g2):
    """Hamming distance between two genomes."""
    return sum(a != b for a, b in zip(g1, g2))


def _jaccard_distance(label1, label2):
    """Jaccard distance between two rules (combined B+S sets)."""
    b1, s1 = _parse_bs(label1)
    b2, s2 = _parse_bs(label2)
    set1 = {f"B{x}" for x in b1} | {f"S{x}" for x in s1}
    set2 = {f"B{x}" for x in b2} | {f"S{x}" for x in s2}
    if not set1 and not set2:
        return 0.0
    inter = len(set1 & set2)
    union = len(set1 | set2)
    return 1.0 - (inter / union) if union else 0.0


def _behavioral_distance(entry1, entry2):
    """Distance based on classification and score similarity."""
    d = 0.0
    # Classification match
    c1 = entry1.get("classification", "unknown")
    c2 = entry2.get("classification", "unknown")
    if c1 != c2:
        d += 0.5
    # Score difference (normalized)
    s1 = entry1.get("score", 0)
    s2 = entry2.get("score", 0)
    max_s = max(abs(s1), abs(s2), 1)
    d += 0.5 * abs(s1 - s2) / max_s
    return d


def _combined_distance(entry1, entry2, weights=(0.4, 0.3, 0.3)):
    """Weighted combination of Hamming, Jaccard, and behavioral distances."""
    g1 = _rule_to_genome(entry1.get("label", "B/S"))
    g2 = _rule_to_genome(entry2.get("label", "B/S"))
    ham = _hamming_distance(g1, g2) / 18.0
    jac = _jaccard_distance(entry1.get("label", "B/S"), entry2.get("label", "B/S"))
    beh = _behavioral_distance(entry1, entry2)
    return weights[0] * ham + weights[1] * jac + weights[2] * beh


# ── Clustering (UPGMA-style) ─────────────────────────────────────────

def _cluster_entries(entries):
    """UPGMA hierarchical clustering. Returns a tree node structure.
    Each node: {"label": str, "children": [node, ...], "dist": float,
                "entry": dict_or_None, "idx": int_or_None}
    """
    if not entries:
        return None
    n = len(entries)
    # Initialize leaf nodes
    nodes = []
    for i, e in enumerate(entries):
        nodes.append({
            "label": e.get("label", "?"),
            "children": [],
            "dist": 0.0,
            "entry": e,
            "idx": i,
            "members": [i],
        })

    if n == 1:
        return nodes[0]

    # Distance matrix
    dist = {}
    for i in range(n):
        for j in range(i + 1, n):
            dist[(i, j)] = _combined_distance(entries[i], entries[j])

    active = list(range(n))
    next_id = n

    while len(active) > 1:
        # Find minimum distance pair
        min_d = float("inf")
        mi, mj = active[0], active[1]
        for ii in range(len(active)):
            for jj in range(ii + 1, len(active)):
                a, b = active[ii], active[jj]
                key = (min(a, b), max(a, b))
                d = dist.get(key, 1.0)
                if d < min_d:
                    min_d = d
                    mi, mj = a, b

        # Create new merged node
        new_node = {
            "label": "",
            "children": [nodes[mi], nodes[mj]],
            "dist": min_d,
            "entry": None,
            "idx": next_id,
            "members": nodes[mi]["members"] + nodes[mj]["members"],
        }

        # Update distances (UPGMA average)
        for k in active:
            if k == mi or k == mj:
                continue
            key_i = (min(k, mi), max(k, mi))
            key_j = (min(k, mj), max(k, mj))
            d_i = dist.get(key_i, 1.0)
            d_j = dist.get(key_j, 1.0)
            ni = len(nodes[mi]["members"])
            nj = len(nodes[mj]["members"])
            new_d = (d_i * ni + d_j * nj) / (ni + nj)
            new_key = (min(k, next_id), max(k, next_id))
            dist[new_key] = new_d

        nodes.append(new_node)
        active.remove(mi)
        active.remove(mj)
        active.append(next_id)
        next_id += 1

    return nodes[active[0]]


# ── Tree rendering ────────────────────────────────────────────────────

def _render_tree(node, max_width=60):
    """Render a phylogenetic tree as list of strings (ASCII art)."""
    lines = []
    _render_subtree(node, lines, "", True, max_width)
    return lines


def _render_subtree(node, lines, prefix, is_last, max_width):
    """Recursive ASCII tree renderer."""
    connector = "└── " if is_last else "├── "
    if node["children"]:
        dist_str = f"d={node['dist']:.2f}" if node["dist"] > 0 else ""
        line = f"{prefix}{connector}┬ {dist_str}"
        lines.append(line[:max_width])
        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(node["children"]):
            _render_subtree(child, lines, child_prefix,
                            i == len(node["children"]) - 1, max_width)
    else:
        entry = node.get("entry", {})
        label = node.get("label", "?")
        cls = entry.get("classification", "?")[:6]
        score = entry.get("score", 0)
        line = f"{prefix}{connector}{label} [{cls}] s={score:.0f}"
        lines.append(line[:max_width])


# ── Motif identification ─────────────────────────────────────────────

def _identify_motifs(label):
    """Identify which conserved motifs are present in a rule."""
    birth, surv = _parse_bs(label)
    found = []
    for motif in _MOTIFS:
        mb = motif["birth"]
        ms = motif["survival"]
        # Motif present if it's a subset of the rule's B/S
        if mb <= birth and ms <= surv:
            found.append(motif)
    return found


def _find_conserved_motifs(entries):
    """Find motifs conserved across many entries."""
    motif_counts = {}
    for entry in entries:
        found = _identify_motifs(entry.get("label", "B/S"))
        for m in found:
            name = m["name"]
            if name not in motif_counts:
                motif_counts[name] = {"motif": m, "count": 0, "examples": []}
            motif_counts[name]["count"] += 1
            if len(motif_counts[name]["examples"]) < 5:
                motif_counts[name]["examples"].append(entry.get("label", "?"))
    # Sort by frequency
    return sorted(motif_counts.values(), key=lambda x: -x["count"])


# ── Mini-simulation for preview ──────────────────────────────────────

def _create_preview_grid(label, rows, cols, density=0.35):
    """Create a small Grid with the given rule for preview."""
    birth, surv = _parse_bs(label)
    g = Grid(rows, cols)
    g.birth = birth
    g.survival = surv
    # Random seed
    for r in range(rows):
        for c in range(cols):
            if random.random() < density:
                g.cells[r][c] = 1
    return g


def _step_preview(grid):
    """Advance preview grid one generation."""
    rows, cols = grid.rows, grid.cols
    new = [[0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            neighbors = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr = (r + dr) % rows
                    nc = (c + dc) % cols
                    if grid.cells[nr][nc] > 0:
                        neighbors += 1
            alive = grid.cells[r][c] > 0
            if alive:
                new[r][c] = 1 if neighbors in grid.survival else 0
            else:
                new[r][c] = 1 if neighbors in grid.birth else 0
    grid.cells = new


# ── Diff two rules ───────────────────────────────────────────────────

def _diff_rules(label1, label2):
    """Return detailed diff of two rules."""
    b1, s1 = _parse_bs(label1)
    b2, s2 = _parse_bs(label2)
    diff = {
        "birth_added": sorted(b2 - b1),
        "birth_removed": sorted(b1 - b2),
        "birth_shared": sorted(b1 & b2),
        "survival_added": sorted(s2 - s1),
        "survival_removed": sorted(s1 - s2),
        "survival_shared": sorted(s1 & s2),
        "hamming": _hamming_distance(_rule_to_genome(label1), _rule_to_genome(label2)),
        "jaccard": _jaccard_distance(label1, label2),
    }
    return diff


# ── State initialization ─────────────────────────────────────────────

def _phylo_init_state(self):
    """Initialize all phylo mode state attributes."""
    self.phylo_mode = False
    self.phylo_menu = True
    self.phylo_running = False
    self.phylo_menu_sel = 0

    # Data
    self.phylo_entries = []         # loaded Hall of Fame entries
    self.phylo_tree = None          # clustered tree
    self.phylo_tree_lines = []      # rendered tree ASCII lines
    self.phylo_families = []        # clustered families list
    self.phylo_motifs = []          # conserved motifs found
    self.phylo_lineage = []         # lineage trace (parent→child)

    # View state
    self.phylo_view = 0             # 0=tree, 1=motifs, 2=diff, 3=lineage, 4=families
    self.phylo_cursor = 0           # cursor in current view
    self.phylo_scroll = 0           # scroll offset
    self.phylo_tree_cursor = 0      # cursor in tree view

    # Diff mode
    self.phylo_diff_a = -1          # first rule index for diff
    self.phylo_diff_b = -1          # second rule index for diff
    self.phylo_diff_result = None   # diff result dict

    # Preview
    self.phylo_preview = None       # preview Grid
    self.phylo_preview_label = ""
    self.phylo_preview_step = 0
    self.phylo_preview_running = False
    self.phylo_preview_pop_hist = []

    # Sort
    self.phylo_sort_by = 0          # 0=score, 1=classification, 2=hamming from Life

    # Distance weights
    self.phylo_w_hamming = 0.4
    self.phylo_w_jaccard = 0.3
    self.phylo_w_behavioral = 0.3


# ── Enter / Exit ──────────────────────────────────────────────────────

def _enter_phylo_mode(self):
    """Enter Rule Phylogenetics mode."""
    _phylo_init_state(self)
    self.phylo_menu = True
    self.phylo_menu_sel = 0
    # Load hall of fame
    self.phylo_entries = _load_hall(self)
    self._flash("Rule Phylogenetics — comparative genomics for CA rules")


def _exit_phylo_mode(self):
    """Exit phylo mode."""
    self.phylo_mode = False
    self.phylo_menu = False
    self.phylo_running = False
    self.phylo_preview = None
    self._flash("Rule Phylogenetics OFF")


def _load_hall(self):
    """Load hall of fame entries."""
    if not os.path.isfile(_GALLERY_FILE):
        return []
    try:
        with open(_GALLERY_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


# ── Analysis pipeline ─────────────────────────────────────────────────

def _phylo_analyze(self):
    """Run full analysis on loaded entries."""
    entries = self.phylo_entries
    if not entries:
        self._flash("No Hall of Fame data found — run Genesis Protocol first")
        return

    weights = (self.phylo_w_hamming, self.phylo_w_jaccard, self.phylo_w_behavioral)

    # Build tree
    # Limit to top 40 entries for performance
    subset = entries[:40]
    self.phylo_tree = _cluster_entries(subset)
    self.phylo_tree_lines = _render_tree(self.phylo_tree, max_width=70) if self.phylo_tree else []

    # Find conserved motifs
    self.phylo_motifs = _find_conserved_motifs(entries)

    # Build families (group by classification)
    families = {}
    for e in entries:
        cls = e.get("classification", "unknown")
        if cls not in families:
            families[cls] = []
        families[cls].append(e)
    self.phylo_families = sorted(families.items(), key=lambda x: -len(x[1]))

    # Build lineage from round data
    self.phylo_lineage = _build_lineage(entries)

    self.phylo_mode = True
    self.phylo_menu = False
    self.phylo_view = 0
    self.phylo_cursor = 0
    self.phylo_scroll = 0
    self._flash(f"Analysis complete — {len(entries)} rules, "
                f"{len(self.phylo_families)} families, "
                f"{len(self.phylo_motifs)} motifs found")


def _build_lineage(entries):
    """Build lineage relationships from round ordering."""
    lineage = []
    # Group by round
    by_round = {}
    for e in entries:
        r = e.get("round", 0)
        if r not in by_round:
            by_round[r] = []
        by_round[r].append(e)

    rounds = sorted(by_round.keys())
    for i in range(1, len(rounds)):
        prev_entries = by_round[rounds[i - 1]]
        curr_entries = by_round[rounds[i]]
        for child in curr_entries:
            # Find closest parent from previous round
            best_parent = None
            best_dist = float("inf")
            for parent in prev_entries:
                d = _combined_distance(parent, child)
                if d < best_dist:
                    best_dist = d
                    best_parent = parent
            if best_parent and best_dist < 0.8:
                diff = _diff_rules(best_parent.get("label", "B/S"),
                                   child.get("label", "B/S"))
                lineage.append({
                    "parent": best_parent.get("label", "?"),
                    "child": child.get("label", "?"),
                    "parent_round": rounds[i - 1],
                    "child_round": rounds[i],
                    "distance": best_dist,
                    "parent_class": best_parent.get("classification", "?"),
                    "child_class": child.get("classification", "?"),
                    "mutations": diff,
                })
    return lineage


# ── Step ──────────────────────────────────────────────────────────────

def _phylo_step(self):
    """Advance preview simulation if running."""
    if self.phylo_preview and self.phylo_preview_running:
        _step_preview(self.phylo_preview)
        self.phylo_preview_step += 1
        pop = sum(1 for r in self.phylo_preview.cells for c in r if c > 0)
        self.phylo_preview_pop_hist.append(pop)
        if len(self.phylo_preview_pop_hist) > 60:
            self.phylo_preview_pop_hist.pop(0)


# ── Menu key handler ──────────────────────────────────────────────────

_MENU_ITEMS = [
    ("analyze", "Analyze Hall of Fame"),
    ("weights", "Distance Weights"),
    ("quit", "Back"),
]


def _handle_phylo_menu_key(self, key):
    """Handle menu key input."""
    n = len(_MENU_ITEMS)
    if key == curses.KEY_UP:
        self.phylo_menu_sel = (self.phylo_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN:
        self.phylo_menu_sel = (self.phylo_menu_sel + 1) % n
        return True
    if key in (10, 13, ord("\n")):
        item = _MENU_ITEMS[self.phylo_menu_sel][0]
        if item == "analyze":
            _phylo_analyze(self)
        elif item == "weights":
            # Cycle weight presets
            presets = [
                (0.4, 0.3, 0.3, "Balanced"),
                (0.7, 0.2, 0.1, "Genomic focus"),
                (0.2, 0.2, 0.6, "Behavioral focus"),
                (0.1, 0.7, 0.2, "Set-theoretic focus"),
            ]
            # Find current and advance
            cur = (self.phylo_w_hamming, self.phylo_w_jaccard, self.phylo_w_behavioral)
            idx = 0
            for i, p in enumerate(presets):
                if abs(p[0] - cur[0]) < 0.05 and abs(p[1] - cur[1]) < 0.05:
                    idx = (i + 1) % len(presets)
                    break
            p = presets[idx]
            self.phylo_w_hamming = p[0]
            self.phylo_w_jaccard = p[1]
            self.phylo_w_behavioral = p[2]
            self._flash(f"Distance weights: {p[3]} ({p[0]:.1f}/{p[1]:.1f}/{p[2]:.1f})")
        elif item == "quit":
            _exit_phylo_mode(self)
        return True
    if key == ord("q") or key == 27:
        _exit_phylo_mode(self)
        return True
    return True


# ── Main key handler ──────────────────────────────────────────────────

def _handle_phylo_key(self, key):
    """Handle active mode key input."""
    if key == ord("q") or key == 27:
        if self.phylo_preview:
            self.phylo_preview = None
            self.phylo_preview_running = False
            return True
        if self.phylo_diff_result and self.phylo_view == 2:
            self.phylo_diff_result = None
            self.phylo_diff_a = -1
            self.phylo_diff_b = -1
            return True
        _exit_phylo_mode(self)
        return True

    # View switching: 1-5
    if key == ord("1"):
        self.phylo_view = 0
        self.phylo_scroll = 0
        self._flash("Phylogenetic Tree")
        return True
    if key == ord("2"):
        self.phylo_view = 1
        self.phylo_scroll = 0
        self._flash("Conserved Motifs")
        return True
    if key == ord("3"):
        self.phylo_view = 2
        self.phylo_scroll = 0
        self._flash("Rule Diff (select two rules)")
        return True
    if key == ord("4"):
        self.phylo_view = 3
        self.phylo_scroll = 0
        self._flash("Lineage Trace")
        return True
    if key == ord("5"):
        self.phylo_view = 4
        self.phylo_scroll = 0
        self._flash("Rule Families")
        return True

    # Navigation
    if key == curses.KEY_UP:
        self.phylo_cursor = max(0, self.phylo_cursor - 1)
        return True
    if key == curses.KEY_DOWN:
        self.phylo_cursor += 1
        return True
    if key == curses.KEY_PPAGE:
        self.phylo_scroll = max(0, self.phylo_scroll - 10)
        return True
    if key == curses.KEY_NPAGE:
        self.phylo_scroll += 10
        return True

    # Preview: Enter on a rule
    if key in (10, 13, ord("\n")):
        entry = _get_selected_entry(self)
        if entry:
            label = entry.get("label", "B3/S23")
            self.phylo_preview = _create_preview_grid(label, 20, 40)
            self.phylo_preview_label = label
            self.phylo_preview_step = 0
            self.phylo_preview_pop_hist = []
            self.phylo_preview_running = True
            self._flash(f"Preview: {label}")
        return True

    # Space: toggle preview running
    if key == ord(" "):
        if self.phylo_preview:
            self.phylo_preview_running = not self.phylo_preview_running
        else:
            self.phylo_running = not self.phylo_running
        return True

    # Diff mode: 'a' and 'b' to select rules
    if self.phylo_view == 2:
        if key == ord("a"):
            idx = _get_selected_index(self)
            if idx >= 0:
                self.phylo_diff_a = idx
                self._flash(f"Diff rule A: {self.phylo_entries[idx].get('label', '?')}")
            return True
        if key == ord("b"):
            idx = _get_selected_index(self)
            if idx >= 0:
                self.phylo_diff_b = idx
                self._flash(f"Diff rule B: {self.phylo_entries[idx].get('label', '?')}")
            return True
        if key == ord("d"):
            if self.phylo_diff_a >= 0 and self.phylo_diff_b >= 0:
                ea = self.phylo_entries[self.phylo_diff_a]
                eb = self.phylo_entries[self.phylo_diff_b]
                self.phylo_diff_result = _diff_rules(
                    ea.get("label", "B/S"), eb.get("label", "B/S"))
                self._flash("Diff computed")
            else:
                self._flash("Select rules with 'a' and 'b' first")
            return True

    # Sort: 's' to cycle sort
    if key == ord("s"):
        self.phylo_sort_by = (self.phylo_sort_by + 1) % 3
        names = ["Score", "Classification", "Hamming from Life"]
        self._flash(f"Sort: {names[self.phylo_sort_by]}")
        _apply_sort(self)
        return True

    # Re-analyze with 'r'
    if key == ord("r"):
        _phylo_analyze(self)
        return True

    return True


def _get_selected_entry(self):
    """Get the entry at current cursor position."""
    entries = self.phylo_entries
    if not entries:
        return None
    idx = self.phylo_cursor
    if 0 <= idx < len(entries):
        return entries[idx]
    return None


def _get_selected_index(self):
    """Get index of entry at cursor."""
    if 0 <= self.phylo_cursor < len(self.phylo_entries):
        return self.phylo_cursor
    return -1


def _apply_sort(self):
    """Sort entries by current sort mode."""
    if self.phylo_sort_by == 0:
        self.phylo_entries.sort(key=lambda e: -e.get("score", 0))
    elif self.phylo_sort_by == 1:
        self.phylo_entries.sort(key=lambda e: e.get("classification", "z"))
    elif self.phylo_sort_by == 2:
        life_genome = _rule_to_genome("B3/S23")
        self.phylo_entries.sort(
            key=lambda e: _hamming_distance(
                _rule_to_genome(e.get("label", "B/S")), life_genome))


# ── Drawing ───────────────────────────────────────────────────────────

def _draw_phylo_menu(self, max_y, max_x):
    """Draw the settings/start menu."""
    self.stdscr.erase()
    y = 1
    try:
        title = "═══ Rule Phylogenetics ═══"
        self.stdscr.addstr(y, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(4) | curses.A_BOLD)
        y += 2

        subtitle = "Comparative Genomics for Cellular Automata"
        self.stdscr.addstr(y, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.color_pair(5))
        y += 2

        # Show hall of fame status
        n = len(self.phylo_entries)
        if n > 0:
            self.stdscr.addstr(y, 2, f"Hall of Fame loaded: {n} rules",
                               curses.color_pair(3))
        else:
            self.stdscr.addstr(y, 2, "No Hall of Fame data — run Genesis Protocol first",
                               curses.color_pair(2))
        y += 2

        # Weights display
        self.stdscr.addstr(y, 2, "Distance weights:", curses.color_pair(7))
        self.stdscr.addstr(y + 1, 4,
                           f"Hamming={self.phylo_w_hamming:.1f}  "
                           f"Jaccard={self.phylo_w_jaccard:.1f}  "
                           f"Behavioral={self.phylo_w_behavioral:.1f}",
                           curses.color_pair(5))
        y += 3

        # Menu items
        for i, (key, label) in enumerate(_MENU_ITEMS):
            attr = curses.A_REVERSE if i == self.phylo_menu_sel else 0
            prefix = "▸ " if i == self.phylo_menu_sel else "  "
            self.stdscr.addstr(y, 4, f"{prefix}{label}", attr | curses.color_pair(7))
            y += 1

        y += 2
        self.stdscr.addstr(y, 2, "↑↓ Navigate  Enter Select  q Quit",
                           curses.color_pair(5) | curses.A_DIM)

    except curses.error:
        pass


def _draw_phylo(self, max_y, max_x):
    """Draw the active phylo analysis view."""
    self.stdscr.erase()

    # Draw preview overlay if active
    if self.phylo_preview:
        _draw_preview(self, max_y, max_x)
        return

    try:
        # Header
        views = ["Tree", "Motifs", "Diff", "Lineage", "Families"]
        header_parts = []
        for i, v in enumerate(views):
            if i == self.phylo_view:
                header_parts.append(f"[{i+1}:{v}]")
            else:
                header_parts.append(f" {i+1}:{v} ")
        header = " ".join(header_parts)
        self.stdscr.addstr(0, 1, header[:max_x - 2], curses.color_pair(4) | curses.A_BOLD)

        # Status bar
        n = len(self.phylo_entries)
        sort_names = ["score", "class", "hamming"]
        status = f"{n} rules │ sort:{sort_names[self.phylo_sort_by]} │ q:back s:sort r:rebuild"
        self.stdscr.addstr(max_y - 1, 1, status[:max_x - 2],
                           curses.color_pair(5) | curses.A_DIM)

        # Dispatch to view
        area_y = 2
        area_h = max_y - 3
        if self.phylo_view == 0:
            _draw_tree_view(self, area_y, area_h, max_x)
        elif self.phylo_view == 1:
            _draw_motifs_view(self, area_y, area_h, max_x)
        elif self.phylo_view == 2:
            _draw_diff_view(self, area_y, area_h, max_x)
        elif self.phylo_view == 3:
            _draw_lineage_view(self, area_y, area_h, max_x)
        elif self.phylo_view == 4:
            _draw_families_view(self, area_y, area_h, max_x)

    except curses.error:
        pass


def _draw_tree_view(self, start_y, height, max_x):
    """Draw phylogenetic tree."""
    lines = self.phylo_tree_lines
    if not lines:
        try:
            self.stdscr.addstr(start_y + 1, 2, "No tree data — press 'r' to rebuild",
                               curses.color_pair(2))
        except curses.error:
            pass
        return

    # Clamp scroll
    max_scroll = max(0, len(lines) - height)
    self.phylo_scroll = min(self.phylo_scroll, max_scroll)

    try:
        self.stdscr.addstr(start_y, 1, "Phylogenetic Tree (UPGMA clustering)",
                           curses.color_pair(7) | curses.A_BOLD)
        for i in range(height - 1):
            idx = self.phylo_scroll + i
            if idx >= len(lines):
                break
            line = lines[idx]
            # Color based on content
            color = curses.color_pair(5)
            if "glider" in line.lower() or "replic" in line.lower():
                color = curses.color_pair(3)
            elif "chaot" in line.lower():
                color = curses.color_pair(2)
            elif "oscil" in line.lower():
                color = curses.color_pair(4)
            elif "still" in line.lower():
                color = curses.color_pair(5)
            elif "┬" in line:
                color = curses.color_pair(7) | curses.A_DIM

            # Highlight cursor line
            if idx == self.phylo_tree_cursor:
                color |= curses.A_REVERSE

            self.stdscr.addstr(start_y + 1 + i, 1, line[:max_x - 2], color)
    except curses.error:
        pass


def _draw_motifs_view(self, start_y, height, max_x):
    """Draw conserved motifs analysis."""
    motifs = self.phylo_motifs
    if not motifs:
        try:
            self.stdscr.addstr(start_y + 1, 2, "No motifs found",
                               curses.color_pair(2))
        except curses.error:
            pass
        return

    try:
        self.stdscr.addstr(start_y, 1, "Conserved Behavioral Motifs",
                           curses.color_pair(7) | curses.A_BOLD)
        y = start_y + 1
        total = len(self.phylo_entries) or 1
        for i, mc in enumerate(motifs):
            if y >= start_y + height - 1:
                break
            m = mc["motif"]
            count = mc["count"]
            pct = 100 * count / total
            bar_w = min(20, int(20 * count / total))
            bar = "█" * bar_w + "░" * (20 - bar_w)

            attr = curses.A_REVERSE if i == self.phylo_cursor else 0

            # Motif name and frequency
            self.stdscr.addstr(y, 2, f"{'▸' if i == self.phylo_cursor else ' '} {m['name']}",
                               curses.color_pair(4) | curses.A_BOLD | attr)
            self.stdscr.addstr(y, 24, f"{count}/{total} ({pct:.0f}%)",
                               curses.color_pair(7))
            self.stdscr.addstr(y, 42, bar[:max_x - 43],
                               curses.color_pair(3))
            y += 1

            # Details
            b_str = ",".join(str(x) for x in sorted(m["birth"])) or "∅"
            s_str = ",".join(str(x) for x in sorted(m["survival"])) or "∅"
            self.stdscr.addstr(y, 6, f"B{{{b_str}}} S{{{s_str}}}",
                               curses.color_pair(5))
            self.stdscr.addstr(y, 30, m["behavior"][:max_x - 31],
                               curses.color_pair(5) | curses.A_DIM)
            y += 1

            # Examples
            examples = mc.get("examples", [])
            if examples:
                self.stdscr.addstr(y, 6, "Examples: " + ", ".join(examples[:4]),
                                   curses.color_pair(5) | curses.A_DIM)
            y += 2
    except curses.error:
        pass


def _draw_diff_view(self, start_y, height, max_x):
    """Draw rule diff / comparison view."""
    entries = self.phylo_entries
    try:
        self.stdscr.addstr(start_y, 1, "Rule Diff — Side-by-Side Comparison",
                           curses.color_pair(7) | curses.A_BOLD)

        if self.phylo_diff_result:
            _draw_diff_result(self, start_y + 1, height - 1, max_x)
            return

        y = start_y + 1
        self.stdscr.addstr(y, 2, "Navigate to a rule, press 'a' for left, 'b' for right, 'd' to diff",
                           curses.color_pair(5) | curses.A_DIM)
        y += 1

        # Show selected
        if self.phylo_diff_a >= 0 and self.phylo_diff_a < len(entries):
            self.stdscr.addstr(y, 2, f"A: {entries[self.phylo_diff_a].get('label', '?')}",
                               curses.color_pair(3))
        else:
            self.stdscr.addstr(y, 2, "A: (none)", curses.color_pair(5) | curses.A_DIM)
        y += 1

        if self.phylo_diff_b >= 0 and self.phylo_diff_b < len(entries):
            self.stdscr.addstr(y, 2, f"B: {entries[self.phylo_diff_b].get('label', '?')}",
                               curses.color_pair(4))
        else:
            self.stdscr.addstr(y, 2, "B: (none)", curses.color_pair(5) | curses.A_DIM)
        y += 2

        # Rule list for selection
        self.stdscr.addstr(y, 2, "Rules:", curses.color_pair(7))
        y += 1
        max_show = height - (y - start_y) - 1
        offset = max(0, self.phylo_cursor - max_show + 2)
        for i in range(min(max_show, len(entries))):
            idx = offset + i
            if idx >= len(entries):
                break
            e = entries[idx]
            label = e.get("label", "?")
            cls = e.get("classification", "?")[:8]
            score = e.get("score", 0)
            marker = ""
            if idx == self.phylo_diff_a:
                marker = " [A]"
            elif idx == self.phylo_diff_b:
                marker = " [B]"
            attr = curses.A_REVERSE if idx == self.phylo_cursor else 0
            line = f"{'▸' if idx == self.phylo_cursor else ' '} {label:16s} {cls:8s} s={score:6.1f}{marker}"
            self.stdscr.addstr(y, 2, line[:max_x - 3], attr | curses.color_pair(7))
            y += 1
    except curses.error:
        pass


def _draw_diff_result(self, start_y, height, max_x):
    """Draw the computed diff between two rules."""
    diff = self.phylo_diff_result
    entries = self.phylo_entries
    ea = entries[self.phylo_diff_a] if 0 <= self.phylo_diff_a < len(entries) else {}
    eb = entries[self.phylo_diff_b] if 0 <= self.phylo_diff_b < len(entries) else {}

    try:
        y = start_y
        mid = max_x // 2

        # Headers
        la = ea.get("label", "?")
        lb = eb.get("label", "?")
        self.stdscr.addstr(y, 2, f"A: {la}", curses.color_pair(3) | curses.A_BOLD)
        self.stdscr.addstr(y, mid, f"B: {lb}", curses.color_pair(4) | curses.A_BOLD)
        y += 1

        ca = ea.get("classification", "?")
        cb = eb.get("classification", "?")
        self.stdscr.addstr(y, 2, f"   {ca}", curses.color_pair(3))
        self.stdscr.addstr(y, mid, f"   {cb}", curses.color_pair(4))
        y += 2

        # Genome visualization
        self.stdscr.addstr(y, 2, "Genome (B0-B8 S0-S8):", curses.color_pair(7))
        y += 1
        ga = _rule_to_genome(la)
        gb = _rule_to_genome(lb)
        genome_a = ""
        genome_b = ""
        diff_line = ""
        labels_line = ""
        for i in range(18):
            prefix = "B" if i < 9 else "S"
            pos = i if i < 9 else i - 9
            labels_line += f"{prefix}{pos}"
            genome_a += f" {ga[i]}"
            genome_b += f" {gb[i]}"
            if ga[i] != gb[i]:
                diff_line += " ^"
            else:
                diff_line += "  "

        self.stdscr.addstr(y, 2, "     " + labels_line[:max_x - 8],
                           curses.color_pair(5) | curses.A_DIM)
        y += 1
        self.stdscr.addstr(y, 2, f"  A:{genome_a[:max_x - 8]}",
                           curses.color_pair(3))
        y += 1
        self.stdscr.addstr(y, 2, f"  B:{genome_b[:max_x - 8]}",
                           curses.color_pair(4))
        y += 1
        self.stdscr.addstr(y, 2, f"    {diff_line[:max_x - 8]}",
                           curses.color_pair(2) | curses.A_BOLD)
        y += 2

        # Distance metrics
        self.stdscr.addstr(y, 2, "Distances:", curses.color_pair(7) | curses.A_BOLD)
        y += 1
        self.stdscr.addstr(y, 4, f"Hamming:    {diff['hamming']}/18 bits",
                           curses.color_pair(5))
        y += 1
        self.stdscr.addstr(y, 4, f"Jaccard:    {diff['jaccard']:.3f}",
                           curses.color_pair(5))
        y += 1
        if ea and eb:
            bd = _behavioral_distance(ea, eb)
            self.stdscr.addstr(y, 4, f"Behavioral: {bd:.3f}",
                               curses.color_pair(5))
        y += 2

        # Changes summary
        self.stdscr.addstr(y, 2, "Birth changes:", curses.color_pair(7))
        y += 1
        shared = diff["birth_shared"]
        added = diff["birth_added"]
        removed = diff["birth_removed"]
        self.stdscr.addstr(y, 4, f"Shared: {shared}", curses.color_pair(5))
        y += 1
        if added:
            self.stdscr.addstr(y, 4, f"Added in B: +{added}", curses.color_pair(3))
            y += 1
        if removed:
            self.stdscr.addstr(y, 4, f"Removed in B: -{removed}", curses.color_pair(2))
            y += 1
        y += 1

        self.stdscr.addstr(y, 2, "Survival changes:", curses.color_pair(7))
        y += 1
        shared = diff["survival_shared"]
        added = diff["survival_added"]
        removed = diff["survival_removed"]
        self.stdscr.addstr(y, 4, f"Shared: {shared}", curses.color_pair(5))
        y += 1
        if added:
            self.stdscr.addstr(y, 4, f"Added in B: +{added}", curses.color_pair(3))
            y += 1
        if removed:
            self.stdscr.addstr(y, 4, f"Removed in B: -{removed}", curses.color_pair(2))
            y += 1

        y += 1
        # Behavioral shift
        if ca != cb:
            self.stdscr.addstr(y, 2,
                               f"Behavioral shift: {ca} → {cb}",
                               curses.color_pair(6) | curses.A_BOLD)
        else:
            self.stdscr.addstr(y, 2,
                               f"Same behavior class: {ca}",
                               curses.color_pair(3))
        y += 2
        self.stdscr.addstr(y, 2, "Press 'q' to close diff",
                           curses.color_pair(5) | curses.A_DIM)

    except curses.error:
        pass


def _draw_lineage_view(self, start_y, height, max_x):
    """Draw lineage trace from breeding history."""
    lineage = self.phylo_lineage
    try:
        self.stdscr.addstr(start_y, 1, "Lineage Trace — Parent → Child Mutations",
                           curses.color_pair(7) | curses.A_BOLD)

        if not lineage:
            self.stdscr.addstr(start_y + 2, 2,
                               "No lineage data (need multi-round Hall of Fame)",
                               curses.color_pair(2))
            return

        y = start_y + 1
        max_show = height - 2
        offset = max(0, self.phylo_cursor - max_show + 2)

        for i in range(min(max_show, len(lineage))):
            idx = offset + i
            if idx >= len(lineage):
                break
            if y >= start_y + height:
                break

            l = lineage[idx]
            attr = curses.A_REVERSE if idx == self.phylo_cursor else 0

            # Parent → Child
            parent = l["parent"]
            child = l["child"]
            pc = l.get("parent_class", "?")[:6]
            cc = l.get("child_class", "?")[:6]
            dist = l["distance"]

            arrow = f"{parent} [{pc}] → {child} [{cc}]  d={dist:.2f}"
            self.stdscr.addstr(y, 2, arrow[:max_x - 3],
                               attr | curses.color_pair(7))
            y += 1

            # Mutations
            mut = l.get("mutations", {})
            changes = []
            ba = mut.get("birth_added", [])
            br = mut.get("birth_removed", [])
            sa = mut.get("survival_added", [])
            sr = mut.get("survival_removed", [])
            if ba:
                changes.append(f"+B{ba}")
            if br:
                changes.append(f"-B{br}")
            if sa:
                changes.append(f"+S{sa}")
            if sr:
                changes.append(f"-S{sr}")

            if changes:
                change_str = "  " + " ".join(changes)
                # Color by shift type
                if pc != cc:
                    color = curses.color_pair(6) | curses.A_BOLD
                else:
                    color = curses.color_pair(5) | curses.A_DIM
                self.stdscr.addstr(y, 4, change_str[:max_x - 5], color)
            y += 1

    except curses.error:
        pass


def _draw_families_view(self, start_y, height, max_x):
    """Draw rule families grouped by classification."""
    families = self.phylo_families
    try:
        self.stdscr.addstr(start_y, 1, "Rule Families — Clustered by Behavior",
                           curses.color_pair(7) | curses.A_BOLD)

        if not families:
            self.stdscr.addstr(start_y + 2, 2, "No families found",
                               curses.color_pair(2))
            return

        y = start_y + 1
        total = len(self.phylo_entries) or 1

        for fi, (cls, members) in enumerate(families):
            if y >= start_y + height - 1:
                break

            count = len(members)
            pct = 100 * count / total
            color = _CLASS_COLORS.get(cls, 7)

            # Family header
            bar_w = min(15, max(1, int(15 * count / total)))
            bar = "█" * bar_w + "░" * (15 - bar_w)
            self.stdscr.addstr(y, 2, f"┌─ {cls.upper()} ", curses.color_pair(color) | curses.A_BOLD)
            self.stdscr.addstr(y, 20, f"{count} rules ({pct:.0f}%)",
                               curses.color_pair(7))
            self.stdscr.addstr(y, 40, bar[:max_x - 41], curses.color_pair(color))
            y += 1

            # Show top members
            sorted_members = sorted(members, key=lambda e: -e.get("score", 0))
            for mi, m in enumerate(sorted_members[:4]):
                if y >= start_y + height - 1:
                    break
                label = m.get("label", "?")
                score = m.get("score", 0)
                motifs = _identify_motifs(label)
                motif_str = ", ".join(mt["name"] for mt in motifs[:2]) if motifs else ""
                line = f"│  {label:16s} s={score:6.1f}"
                if motif_str:
                    line += f"  [{motif_str}]"
                self.stdscr.addstr(y, 2, line[:max_x - 3],
                                   curses.color_pair(color) | curses.A_DIM)
                y += 1

            if count > 4:
                self.stdscr.addstr(y, 2, f"└  ... +{count - 4} more",
                                   curses.color_pair(5) | curses.A_DIM)
                y += 1
            y += 1

    except curses.error:
        pass


def _draw_preview(self, max_y, max_x):
    """Draw a live preview of a selected rule."""
    grid = self.phylo_preview
    if not grid:
        return

    try:
        # Title
        label = self.phylo_preview_label
        step = self.phylo_preview_step
        self.stdscr.addstr(0, 1, f"Preview: {label}  step={step}  (Space:pause q:close)",
                           curses.color_pair(4) | curses.A_BOLD)

        # Grid
        g_start_y = 2
        g_height = min(grid.rows, max_y - 6)
        g_width = min(grid.cols, (max_x - 4) // 2)

        for r in range(g_height):
            row_str = ""
            for c in range(g_width):
                if grid.cells[r][c] > 0:
                    row_str += "██"
                else:
                    row_str += "  "
            self.stdscr.addstr(g_start_y + r, 2, row_str[:max_x - 3],
                               curses.color_pair(3))

        # Population sparkline
        hist = self.phylo_preview_pop_hist
        if hist:
            y = g_start_y + g_height + 1
            pop = hist[-1]
            max_pop = max(hist) or 1
            spark = ""
            for p in hist[-40:]:
                idx = min(7, int(8 * p / max_pop)) if max_pop > 0 else 0
                spark += _SPARKLINE[idx]
            self.stdscr.addstr(y, 2, f"Pop: {pop:4d}  {spark}",
                               curses.color_pair(5))

            # Motifs in this rule
            y += 1
            motifs = _identify_motifs(label)
            if motifs:
                motif_names = ", ".join(m["name"] for m in motifs[:3])
                self.stdscr.addstr(y, 2, f"Motifs: {motif_names}",
                                   curses.color_pair(6))

    except curses.error:
        pass


# ── Register ──────────────────────────────────────────────────────────

def register(App):
    """Register Rule Phylogenetics mode methods on the App class."""
    App._enter_phylo_mode = _enter_phylo_mode
    App._exit_phylo_mode = _exit_phylo_mode
    App._phylo_step = _phylo_step
    App._handle_phylo_menu_key = _handle_phylo_menu_key
    App._handle_phylo_key = _handle_phylo_key
    App._draw_phylo_menu = _draw_phylo_menu
    App._draw_phylo = _draw_phylo
