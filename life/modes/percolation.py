"""Mode: perc — Percolation Theory & Critical Phenomena simulation.

Site/bond percolation on a 2D lattice with real-time cluster identification,
order-parameter tracking (spanning probability, largest-cluster fraction),
and fractal geometry at the critical threshold.

Emergent phenomena:
  - Sharp phase transition at p_c ≈ 0.5927 (site) / 0.5 (bond)
  - Fractal cluster geometry at criticality
  - Power-law cluster-size distribution
  - Universality class behavior
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

PERC_PRESETS = [
    ("Site Percolation",
     "Classic Bernoulli site percolation — occupy each site with probability p",
     "site"),
    ("Bond Percolation",
     "Bernoulli bond percolation — each edge is open with probability p",
     "bond"),
    ("Invasion Percolation",
     "Growth process — cluster invades weakest neighboring site (no tuning parameter)",
     "invasion"),
    ("Directed Percolation",
     "Percolation with a preferred direction — models spreading with time arrow",
     "directed"),
    ("Bootstrap Percolation",
     "k-neighbor bootstrap — occupied sites survive only if ≥k neighbors occupied",
     "bootstrap"),
    ("Continuum Percolation",
     "Random discs in the plane — overlap creates connected components",
     "continuum"),
]


# ══════════════════════════════════════════════════════════════════════
#  Union-Find for cluster identification
# ══════════════════════════════════════════════════════════════════════

class _UnionFind:
    """Weighted quick-union with path compression."""
    __slots__ = ("parent", "rank", "size")

    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.size = [1] * n

    def find(self, x):
        p = self.parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════

def _perc_build_clusters(self):
    """Run union-find to identify connected clusters on the grid."""
    rows = self.perc_rows
    cols = self.perc_cols
    grid = self.perc_grid
    uf = _UnionFind(rows * cols)

    preset_id = self.perc_preset_id

    if preset_id == "bond":
        hbonds = self.perc_hbonds
        vbonds = self.perc_vbonds
        for r in range(rows):
            for c in range(cols):
                if not grid[r][c]:
                    continue
                idx = r * cols + c
                # Right neighbor via horizontal bond
                if c + 1 < cols and grid[r][c + 1] and hbonds[r][c]:
                    uf.union(idx, idx + 1)
                # Down neighbor via vertical bond
                if r + 1 < rows and grid[r + 1][c] and vbonds[r][c]:
                    uf.union(idx, (r + 1) * cols + c)
    elif preset_id == "directed":
        for r in range(rows):
            for c in range(cols):
                if not grid[r][c]:
                    continue
                idx = r * cols + c
                # Only connect downward and right (directed)
                if c + 1 < cols and grid[r][c + 1]:
                    uf.union(idx, idx + 1)
                if r + 1 < rows and grid[r + 1][c]:
                    uf.union(idx, (r + 1) * cols + c)
    else:
        for r in range(rows):
            for c in range(cols):
                if not grid[r][c]:
                    continue
                idx = r * cols + c
                if c + 1 < cols and grid[r][c + 1]:
                    uf.union(idx, idx + 1)
                if r + 1 < rows and grid[r + 1][c]:
                    uf.union(idx, (r + 1) * cols + c)

    # Build cluster labels and sizes
    cluster_id = [[-1] * cols for _ in range(rows)]
    cluster_sizes = {}
    for r in range(rows):
        for c in range(cols):
            if grid[r][c]:
                root = uf.find(r * cols + c)
                cluster_id[r][c] = root
                cluster_sizes[root] = uf.size[root]

    self.perc_cluster_id = cluster_id
    self.perc_cluster_sizes = cluster_sizes
    self.perc_uf = uf

    # Compute order parameters
    total_occupied = sum(1 for r in range(rows) for c in range(cols) if grid[r][c])
    total_sites = rows * cols

    if cluster_sizes:
        largest = max(cluster_sizes.values())
    else:
        largest = 0
    self.perc_largest_cluster = largest
    self.perc_largest_frac = largest / total_sites if total_sites > 0 else 0.0
    self.perc_density = total_occupied / total_sites if total_sites > 0 else 0.0

    # Check spanning: does any cluster connect top to bottom?
    top_roots = set()
    bot_roots = set()
    for c in range(cols):
        if grid[0][c]:
            top_roots.add(uf.find(c))
        if grid[rows - 1][c]:
            bot_roots.add(uf.find((rows - 1) * cols + c))
    spanning = top_roots & bot_roots
    self.perc_spanning = len(spanning) > 0
    self.perc_spanning_roots = spanning

    # Cluster size distribution (for power-law analysis)
    size_counts = {}
    for s in cluster_sizes.values():
        size_counts[s] = size_counts.get(s, 0) + 1
    self.perc_size_dist = size_counts


def _perc_assign_colors(self):
    """Assign a color index to each cluster root for display."""
    cluster_sizes = self.perc_cluster_sizes
    if not cluster_sizes:
        self.perc_cluster_colors = {}
        return
    # Sort clusters by size descending; assign rotating colors
    sorted_roots = sorted(cluster_sizes, key=lambda r: cluster_sizes[r], reverse=True)
    palette = [1, 2, 3, 4, 5, 6, 7]  # curses color pairs
    colors = {}
    for i, root in enumerate(sorted_roots):
        if root in self.perc_spanning_roots:
            colors[root] = 3  # yellow/green for spanning cluster
        else:
            colors[root] = palette[i % len(palette)]
    self.perc_cluster_colors = colors


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _enter_perc_mode(self):
    """Enter Percolation mode — show preset menu."""
    self.perc_menu = True
    self.perc_menu_sel = 0
    self._flash("Percolation Theory & Critical Phenomena — select a scenario")


def _exit_perc_mode(self):
    """Exit Percolation mode."""
    self.perc_mode = False
    self.perc_menu = False
    self.perc_running = False
    self._flash("Percolation mode OFF")


def _perc_init(self, preset_idx: int):
    """Initialize percolation simulation with the given preset."""
    name, _desc, preset_id = self.PERC_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()

    rows = max(8, max_y - 5)
    cols = max(12, max_x - 2)
    self.perc_rows = rows
    self.perc_cols = cols

    self.perc_preset_name = name
    self.perc_preset_id = preset_id
    self.perc_generation = 0
    self.perc_running = False
    self.perc_menu = False
    self.perc_mode = True

    # Probability parameter
    self.perc_p = 0.50
    self.perc_p_step = 0.005  # increment per animation step

    # Grid: True = occupied, False = empty
    self.perc_grid = [[False] * cols for _ in range(rows)]

    # Bond arrays (for bond percolation)
    self.perc_hbonds = None
    self.perc_vbonds = None

    # Invasion percolation state
    self.perc_inv_weights = None
    self.perc_inv_frontier = None

    # Continuum state
    self.perc_discs = None
    self.perc_disc_radius = 1.5

    # Bootstrap parameter
    self.perc_bootstrap_k = 3

    # Cluster data
    self.perc_cluster_id = [[-1] * cols for _ in range(rows)]
    self.perc_cluster_sizes = {}
    self.perc_cluster_colors = {}
    self.perc_spanning = False
    self.perc_spanning_roots = set()
    self.perc_largest_cluster = 0
    self.perc_largest_frac = 0.0
    self.perc_density = 0.0
    self.perc_size_dist = {}
    self.perc_uf = None

    # History for order-parameter plot
    self.perc_history = []  # list of (p, largest_frac, spanning)

    # Animation mode: "sweep" gradually increases p; "static" holds
    self.perc_anim_mode = "sweep"

    # Preset-specific setup
    if preset_id == "site":
        self.perc_p = 0.30
        self.perc_p_step = 0.003
    elif preset_id == "bond":
        self.perc_p = 0.25
        self.perc_p_step = 0.003
        self.perc_hbonds = [[False] * cols for _ in range(rows)]
        self.perc_vbonds = [[False] * cols for _ in range(rows)]
    elif preset_id == "invasion":
        self.perc_p = 0.0
        self.perc_anim_mode = "invasion"
        # Assign random weights to each site
        self.perc_inv_weights = [[random.random() for _ in range(cols)]
                                  for _ in range(rows)]
        # Seed from center
        cr, cc = rows // 2, cols // 2
        self.perc_grid[cr][cc] = True
        # Build initial frontier
        self.perc_inv_frontier = set()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = cr + dr, cc + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                self.perc_inv_frontier.add((nr, nc))
        self.perc_p_step = 0.0
    elif preset_id == "directed":
        self.perc_p = 0.30
        self.perc_p_step = 0.003
    elif preset_id == "bootstrap":
        self.perc_p = 0.30
        self.perc_p_step = 0.003
    elif preset_id == "continuum":
        self.perc_p = 0.10
        self.perc_p_step = 0.002
        self.perc_discs = []
        self.perc_disc_radius = max(1.0, min(rows, cols) * 0.03)

    # Generate initial configuration
    _perc_generate(self)
    _perc_build_clusters(self)
    _perc_assign_colors(self)


def _perc_generate(self):
    """Generate/regenerate the grid for current p value."""
    rows = self.perc_rows
    cols = self.perc_cols
    p = self.perc_p
    preset_id = self.perc_preset_id
    rng = random.random

    if preset_id == "site" or preset_id == "directed":
        grid = self.perc_grid
        for r in range(rows):
            for c in range(cols):
                grid[r][c] = rng() < p

    elif preset_id == "bond":
        # All sites occupied; bonds random
        grid = self.perc_grid
        for r in range(rows):
            for c in range(cols):
                grid[r][c] = True
        hb = self.perc_hbonds
        vb = self.perc_vbonds
        for r in range(rows):
            for c in range(cols):
                hb[r][c] = rng() < p
                vb[r][c] = rng() < p

    elif preset_id == "bootstrap":
        # Initial random occupation, then iterate bootstrap rule
        grid = self.perc_grid
        for r in range(rows):
            for c in range(cols):
                grid[r][c] = rng() < p
        # Bootstrap iterations: remove sites with < k occupied neighbors
        k = self.perc_bootstrap_k
        changed = True
        while changed:
            changed = False
            for r in range(rows):
                for c in range(cols):
                    if not grid[r][c]:
                        continue
                    nbrs = 0
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc]:
                            nbrs += 1
                    if nbrs < k:
                        grid[r][c] = False
                        changed = True

    elif preset_id == "continuum":
        # Place random discs; map to grid
        n_discs = int(p * rows * cols * 0.15)
        discs = [(random.uniform(0, rows), random.uniform(0, cols))
                 for _ in range(n_discs)]
        self.perc_discs = discs
        R = self.perc_disc_radius
        grid = self.perc_grid
        for r in range(rows):
            for c in range(cols):
                grid[r][c] = False
        for dy, dx in discs:
            r0 = int(dy)
            c0 = int(dx)
            ir = int(R) + 1
            for dr in range(-ir, ir + 1):
                for dc in range(-ir, ir + 1):
                    rr, cc = r0 + dr, c0 + dc
                    if 0 <= rr < rows and 0 <= cc < cols:
                        dist = math.sqrt((rr - dy) ** 2 + (cc - dx) ** 2)
                        if dist <= R:
                            grid[rr][cc] = True

    # invasion: don't regenerate (it grows incrementally)


# ══════════════════════════════════════════════════════════════════════
#  Simulation step
# ══════════════════════════════════════════════════════════════════════

def _perc_step(self):
    """Advance one step of the percolation animation."""
    preset_id = self.perc_preset_id

    if self.perc_anim_mode == "invasion":
        # Invasion percolation: grow cluster by invading weakest frontier site
        frontier = self.perc_inv_frontier
        weights = self.perc_inv_weights
        grid = self.perc_grid
        rows = self.perc_rows
        cols = self.perc_cols

        if not frontier:
            return

        steps = max(1, len(frontier) // 20)  # invade a few per frame
        for _ in range(steps):
            if not frontier:
                break
            # Find weakest frontier site
            best = None
            best_w = 2.0
            for pos in frontier:
                w = weights[pos[0]][pos[1]]
                if w < best_w:
                    best_w = w
                    best = pos
            if best is None:
                break
            r, c = best
            frontier.discard(best)
            grid[r][c] = True
            # Add new frontier neighbors
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and not grid[nr][nc]:
                    frontier.add((nr, nc))

        occupied = sum(1 for r in range(rows) for c in range(cols) if grid[r][c])
        self.perc_p = occupied / (rows * cols)

    elif self.perc_anim_mode == "sweep":
        # Gradually increase p
        self.perc_p += self.perc_p_step
        if self.perc_p > 1.0:
            self.perc_p = 1.0
            self.perc_running = False
        _perc_generate(self)

    _perc_build_clusters(self)
    _perc_assign_colors(self)

    # Record history
    self.perc_history.append((self.perc_p, self.perc_largest_frac, self.perc_spanning))
    if len(self.perc_history) > 2000:
        self.perc_history = self.perc_history[-2000:]

    self.perc_generation += 1


# ══════════════════════════════════════════════════════════════════════
#  Key handling
# ══════════════════════════════════════════════════════════════════════

def _handle_perc_menu_key(self, key: int) -> bool:
    """Handle input in Percolation preset menu."""
    presets = self.PERC_PRESETS
    if key == curses.KEY_DOWN or key == ord("j"):
        self.perc_menu_sel = (self.perc_menu_sel + 1) % len(presets)
    elif key == curses.KEY_UP or key == ord("k"):
        self.perc_menu_sel = (self.perc_menu_sel - 1) % len(presets)
    elif key in (10, 13, curses.KEY_ENTER):
        self._perc_init(self.perc_menu_sel)
    elif key == ord("q") or key == 27:
        self.perc_menu = False
        self._flash("Percolation mode cancelled")
    return True


def _handle_perc_key(self, key: int) -> bool:
    """Handle input in active Percolation simulation."""
    if key == ord("q") or key == 27:
        self._exit_perc_mode()
        return True
    if key == ord(" "):
        self.perc_running = not self.perc_running
        return True
    if key == ord("n") or key == ord("."):
        self._perc_step()
        return True
    if key == ord("r"):
        idx = next(
            (i for i, p in enumerate(self.PERC_PRESETS)
             if p[0] == self.perc_preset_name), 0)
        self._perc_init(idx)
        return True
    if key == ord("R") or key == ord("m"):
        self.perc_mode = False
        self.perc_running = False
        self.perc_menu = True
        self.perc_menu_sel = 0
        return True
    # Adjust p directly
    if key == ord("p"):
        self.perc_p = min(1.0, self.perc_p + 0.01)
        _perc_generate(self)
        _perc_build_clusters(self)
        _perc_assign_colors(self)
        self._flash(f"p = {self.perc_p:.3f}")
        return True
    if key == ord("P"):
        self.perc_p = max(0.0, self.perc_p - 0.01)
        _perc_generate(self)
        _perc_build_clusters(self)
        _perc_assign_colors(self)
        self._flash(f"p = {self.perc_p:.3f}")
        return True
    # Jump to critical point
    if key == ord("c"):
        if self.perc_preset_id == "bond":
            self.perc_p = 0.5
        elif self.perc_preset_id == "directed":
            self.perc_p = 0.6445
        elif self.perc_preset_id == "bootstrap":
            self.perc_p = 0.66
        else:
            self.perc_p = 0.5927
        _perc_generate(self)
        _perc_build_clusters(self)
        _perc_assign_colors(self)
        self._flash(f"p = p_c ≈ {self.perc_p:.4f}")
        return True
    # Step size
    if key == ord("+") or key == ord("="):
        self.perc_p_step = min(0.05, self.perc_p_step * 1.5)
        self._flash(f"Δp = {self.perc_p_step:.4f}")
        return True
    if key == ord("-"):
        self.perc_p_step = max(0.0005, self.perc_p_step / 1.5)
        self._flash(f"Δp = {self.perc_p_step:.4f}")
        return True
    # Bootstrap k
    if key == ord("k") and self.perc_preset_id == "bootstrap":
        self.perc_bootstrap_k = min(4, self.perc_bootstrap_k + 1)
        _perc_generate(self)
        _perc_build_clusters(self)
        _perc_assign_colors(self)
        self._flash(f"Bootstrap k = {self.perc_bootstrap_k}")
        return True
    if key == ord("K") and self.perc_preset_id == "bootstrap":
        self.perc_bootstrap_k = max(1, self.perc_bootstrap_k - 1)
        _perc_generate(self)
        _perc_build_clusters(self)
        _perc_assign_colors(self)
        self._flash(f"Bootstrap k = {self.perc_bootstrap_k}")
        return True
    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing
# ══════════════════════════════════════════════════════════════════════

def _draw_perc_menu(self, max_y: int, max_x: int):
    """Draw the Percolation preset selection menu."""
    self.stdscr.erase()
    title = "── Percolation Theory & Critical Phenomena ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(self.PERC_PRESETS):
        y = 4 + i * 2
        if y >= max_y - 6:
            break
        marker = "▸ " if i == self.perc_menu_sel else "  "
        attr = curses.color_pair(3) | curses.A_BOLD if i == self.perc_menu_sel else curses.color_pair(7)
        line = f"{marker}{name}"
        try:
            self.stdscr.addstr(y, 3, line[:max_x - 4], attr)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    # Legend
    legend_y = max_y - 5
    if legend_y > 0:
        lines = [
            "Percolation: the canonical model of phase transitions in random media.",
            "At p_c the infinite cluster is born — a fractal that spans the system.",
            "Power-law cluster sizes, universal critical exponents, and geometric order.",
        ]
        for i, line in enumerate(lines):
            try:
                self.stdscr.addstr(legend_y + i, 3, line[:max_x - 4],
                                   curses.color_pair(6))
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


def _draw_perc(self, max_y: int, max_x: int):
    """Draw the active Percolation simulation."""
    self.stdscr.erase()
    state = "▶ RUNNING" if self.perc_running else "⏸ PAUSED"

    span_str = "YES" if self.perc_spanning else "no"

    # Title bar
    title = (f" Percolation: {self.perc_preset_name}  |  p={self.perc_p:.4f}"
             f"  step={self.perc_generation}"
             f"  spanning={span_str}"
             f"  largest={self.perc_largest_frac:.3f}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Main grid display
    _draw_perc_grid(self, max_y, max_x)

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        n_clusters = len(self.perc_cluster_sizes)
        density = self.perc_density

        # Estimate fractal dimension from cluster size distribution
        frac_dim = ""
        sd = self.perc_size_dist
        if len(sd) >= 3:
            sizes = sorted(sd.keys())
            if sizes[-1] > sizes[0] > 0:
                # tau exponent: n(s) ~ s^{-tau}
                log_s = [math.log(s) for s in sizes if s > 1 and sd[s] > 0]
                log_n = [math.log(sd[int(round(math.exp(ls)))]) for ls in log_s
                         if int(round(math.exp(ls))) in sd and sd[int(round(math.exp(ls)))] > 0]
                if len(log_s) >= 3 and len(log_n) >= 3:
                    n = min(len(log_s), len(log_n))
                    log_s = log_s[:n]
                    log_n = log_n[:n]
                    mean_x = sum(log_s) / n
                    mean_y = sum(log_n) / n
                    num = sum((log_s[i] - mean_x) * (log_n[i] - mean_y) for i in range(n))
                    den = sum((log_s[i] - mean_x) ** 2 for i in range(n))
                    if abs(den) > 1e-10:
                        tau = -num / den
                        frac_dim = f"  τ≈{tau:.2f}"

        info = (f" p={self.perc_p:.4f}"
                f"  Δp={self.perc_p_step:.4f}"
                f"  density={density:.3f}"
                f"  clusters={n_clusters}"
                f"  largest={self.perc_largest_cluster}"
                f"  frac={self.perc_largest_frac:.3f}"
                f"{frac_dim}")
        if self.perc_preset_id == "bootstrap":
            info += f"  k={self.perc_bootstrap_k}"
        try:
            self.stdscr.addstr(info_y, 0, info[:max_x - 1],
                               curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [p/P]=±p [c]=p_c [+/-]=Δp [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_perc_grid(self, max_y: int, max_x: int):
    """Draw the percolation grid with cluster coloring."""
    rows = self.perc_rows
    cols = self.perc_cols
    grid = self.perc_grid
    cluster_id = self.perc_cluster_id
    cluster_colors = self.perc_cluster_colors
    spanning_roots = self.perc_spanning_roots

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    for sy in range(min(disp_rows, rows)):
        r = sy * row_scale
        if r >= rows:
            break
        screen_y = 1 + sy
        if screen_y >= max_y - 2:
            break
        for sx in range(min(disp_cols, cols)):
            c = sx * col_scale
            if c >= cols:
                break

            if not grid[r][c]:
                # Empty site
                try:
                    self.stdscr.addstr(screen_y, sx, " ")
                except curses.error:
                    pass
                continue

            cid = cluster_id[r][c]
            if cid < 0:
                ch = "·"
                attr = curses.color_pair(7)
            else:
                root = self.perc_uf.find(cid) if self.perc_uf else cid
                if root in spanning_roots:
                    ch = "█"
                    attr = curses.color_pair(3) | curses.A_BOLD
                else:
                    size = self.perc_cluster_sizes.get(root, 1)
                    if size >= 20:
                        ch = "█"
                    elif size >= 5:
                        ch = "▓"
                    elif size >= 2:
                        ch = "▒"
                    else:
                        ch = "░"
                    color_idx = cluster_colors.get(root, 7)
                    attr = curses.color_pair(color_idx)
                    if size >= 10:
                        attr |= curses.A_BOLD

            try:
                self.stdscr.addstr(screen_y, sx, ch, attr)
            except curses.error:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register percolation mode methods on the App class."""
    App.PERC_PRESETS = PERC_PRESETS
    App._enter_perc_mode = _enter_perc_mode
    App._exit_perc_mode = _exit_perc_mode
    App._perc_init = _perc_init
    App._perc_generate = _perc_generate
    App._perc_build_clusters = _perc_build_clusters
    App._perc_assign_colors = _perc_assign_colors
    App._perc_step = _perc_step
    App._handle_perc_menu_key = _handle_perc_menu_key
    App._handle_perc_key = _handle_perc_key
    App._draw_perc_menu = _draw_perc_menu
    App._draw_perc = _draw_perc
    App._draw_perc_grid = _draw_perc_grid
