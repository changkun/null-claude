"""Emergent Computation Detector — information-theoretic overlay.

Instruments any running simulation to discover and visualize hidden
computational structures — signal channels, logic gates, memory cells,
oscillators — using transfer entropy, integrated information, and causal
density.

Works as a universal overlay across all 150+ modes via _get_minimap_data().
Toggle with Ctrl+I.  Pure Python — no external dependencies.

Key features:
  - Transfer entropy heatmap: color cells by outgoing information flow
  - Causal density overlay: highlight tightly coupled computational units
  - Structure classifier: auto-detect oscillators, guns, wires, gates
  - Information flow arrows: directional overlay showing information movement
  - Computation summary panel: real-time metrics (bits processed, channel
    capacity, integration score)
"""

import math
import curses

from life.colors import colormap_rgb

# ── Characters ──────────────────────────────────────────────────────────

# Arrow characters for information flow direction (8 directions)
_FLOW_ARROWS = {
    (-1, -1): "↖", (-1, 0): "↑", (-1, 1): "↗",
    (0, -1): "←",                  (0, 1): "→",
    (1, -1): "↙",  (1, 0): "↓",  (1, 1): "↘",
}

# Structure type labels and icons
_STRUCTURE_ICONS = {
    "oscillator": "∿",
    "still_life": "■",
    "wire": "━",
    "gate": "⊕",
    "gun": "⊛",
    "memory": "⊞",
    "source": "◉",
    "sink": "◎",
}

# Block characters for density rendering
_DENSITY_CHARS = " ░▒▓█"


# ── Information-theoretic computations ──────────────────────────────────

def _estimate_transfer_entropy(history, N, dr, dc):
    """Estimate transfer entropy from cell (r+dr, c+dc) to cell (r, c).

    Uses a simplified binned estimator:
      TE(X->Y) = H(Y_t | Y_{t-1}) - H(Y_t | Y_{t-1}, X_{t-1})

    Works with discretised states (binary: alive/dead threshold at 0.5).
    """
    if len(history) < 3:
        return [[0.0] * N for _ in range(N)]

    te = [[0.0] * N for _ in range(N)]
    T = len(history)

    for r in range(N):
        for c in range(N):
            # Source cell coordinates (wrapped)
            sr = (r + dr) % N
            sc = (c + dc) % N

            # Build joint count tables
            # States: target_prev, source_prev, target_curr (all binary)
            counts = {}  # (y_prev, x_prev, y_curr) -> count
            pair_counts = {}  # (y_prev, x_prev) -> count
            single_counts = {}  # (y_prev, y_curr) -> count
            marginal = {}  # y_prev -> count

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

            # Compute TE = sum p(y_t, y_{t-1}, x_{t-1})
            #              * log2(p(y_t|y_{t-1},x_{t-1}) / p(y_t|y_{t-1}))
            n_total = T - 1
            if n_total < 2:
                continue

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

            te[r][c] = max(0.0, te_val)

    return te


def _compute_total_transfer_entropy(history, N):
    """Compute total outgoing transfer entropy per cell.

    Sums TE from each cell to its 4 cardinal neighbors (for speed).
    """
    total_te = [[0.0] * N for _ in range(N)]

    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        te = _estimate_transfer_entropy(history, N, dr, dc)
        for r in range(N):
            for c in range(N):
                total_te[r][c] += te[r][c]

    # Normalise
    max_te = 0.0
    for r in range(N):
        for c in range(N):
            if total_te[r][c] > max_te:
                max_te = total_te[r][c]

    if max_te > 0:
        inv = 1.0 / max_te
        for r in range(N):
            for c in range(N):
                total_te[r][c] *= inv

    return total_te


def _compute_causal_density(history, N):
    """Compute causal density — fraction of significant causal connections.

    For each cell, measure how many of its 8 neighbors have TE > threshold.
    High causal density = tightly coupled computational unit.
    """
    if len(history) < 3:
        return [[0.0] * N for _ in range(N)]

    cd = [[0.0] * N for _ in range(N)]
    te_threshold = 0.02  # minimum TE to count as a causal link

    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            te = _estimate_transfer_entropy(history, N, dr, dc)
            for r in range(N):
                for c in range(N):
                    if te[r][c] > te_threshold:
                        cd[r][c] += 1.0 / 8.0

    return cd


def _compute_flow_direction(history, N):
    """Compute dominant information flow direction per cell.

    Returns NxN grid of (dr, dc) tuples indicating the direction in which
    each cell sends the most information.
    """
    if len(history) < 3:
        return [[(0, 0)] * N for _ in range(N)]

    flow = [[(0, 0)] * N for _ in range(N)]

    for r in range(N):
        for c in range(N):
            best_te = 0.0
            best_dir = (0, 0)
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    # TE from (r,c) to (r+dr, c+dc)
                    tr = (r + dr) % N
                    tc = (c + dc) % N

                    # Simplified TE estimate for just this pair
                    te_val = _pairwise_te(history, r, c, tr, tc)
                    if te_val > best_te:
                        best_te = te_val
                        best_dir = (dr, dc)

            if best_te > 0.01:
                flow[r][c] = best_dir

    return flow


def _pairwise_te(history, sr, sc, tr, tc):
    """Quick pairwise TE estimate from source (sr,sc) to target (tr,tc)."""
    T = len(history)
    if T < 3:
        return 0.0

    counts = {}
    pair_counts = {}
    single_counts = {}
    marginal = {}
    n_total = T - 1

    for t in range(1, T):
        y_prev = 1 if history[t - 1][tr][tc] > 0.5 else 0
        x_prev = 1 if history[t - 1][sr][sc] > 0.5 else 0
        y_curr = 1 if history[t][tr][tc] > 0.5 else 0

        key3 = (y_prev, x_prev, y_curr)
        counts[key3] = counts.get(key3, 0) + 1
        key2 = (y_prev, x_prev)
        pair_counts[key2] = pair_counts.get(key2, 0) + 1
        key_s = (y_prev, y_curr)
        single_counts[key_s] = single_counts.get(key_s, 0) + 1
        marginal[y_prev] = marginal.get(y_prev, 0) + 1

    te_val = 0.0
    for (yp, xp, yc), cnt in counts.items():
        p_joint = cnt / n_total
        p_cf = cnt / pair_counts[(yp, xp)]
        sc_cnt = single_counts.get((yp, yc), 0)
        m_cnt = marginal.get(yp, 0)
        if sc_cnt > 0 and m_cnt > 0:
            p_cr = sc_cnt / m_cnt
            if p_cf > 0 and p_cr > 0:
                te_val += p_joint * math.log2(p_cf / p_cr)

    return max(0.0, te_val)


def _compute_integration_score(te_map, cd_map, N):
    """Compute a scalar integration score (bits) from TE and causal density.

    Approximation of integrated information (Phi): sum of TE weighted by
    causal density, capturing how much the system's information flow
    exceeds the sum of its parts.
    """
    total = 0.0
    count = 0
    for r in range(N):
        for c in range(N):
            total += te_map[r][c] * cd_map[r][c]
            count += 1
    return total / max(count, 1) * N * N


def _classify_structures(te_map, cd_map, history, N):
    """Auto-detect computational structures from TE and causal density maps.

    Returns a list of (row, col, type_str, size) tuples.
    """
    structures = []
    visited = [[False] * N for _ in range(N)]

    # Thresholds for structure detection
    high_te = 0.4
    high_cd = 0.5
    wire_te = 0.3

    for r in range(N):
        for c in range(N):
            if visited[r][c]:
                continue

            te = te_map[r][c]
            cd = cd_map[r][c]

            if te < 0.1 and cd < 0.1:
                continue

            # Flood-fill to find connected region
            region = []
            stack = [(r, c)]
            while stack:
                cr, cc = stack.pop()
                if visited[cr][cc]:
                    continue
                if te_map[cr][cc] < 0.05 and cd_map[cr][cc] < 0.05:
                    continue
                visited[cr][cc] = True
                region.append((cr, cc))
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = (cr + dr) % N, (cc + dc) % N
                        if not visited[nr][nc]:
                            stack.append((nr, nc))

            if len(region) < 2:
                continue

            # Classify based on region properties
            avg_te = sum(te_map[pr][pc] for pr, pc in region) / len(region)
            avg_cd = sum(cd_map[pr][pc] for pr, pc in region) / len(region)

            # Check temporal periodicity of region
            is_periodic = _region_is_periodic(history, region)

            # Determine structure type
            size = len(region)
            center_r = sum(pr for pr, _ in region) // size
            center_c = sum(pc for _, pc in region) // size

            if is_periodic and size <= 6:
                structures.append((center_r, center_c, "oscillator", size))
            elif is_periodic and avg_te > high_te and size > 6:
                structures.append((center_r, center_c, "gun", size))
            elif avg_cd > high_cd and size <= 4:
                structures.append((center_r, center_c, "gate", size))
            elif avg_cd > high_cd and size > 4:
                structures.append((center_r, center_c, "memory", size))
            elif avg_te > wire_te and avg_cd < 0.3 and size >= 3:
                structures.append((center_r, center_c, "wire", size))
            elif avg_te > high_te and avg_cd < 0.2:
                structures.append((center_r, center_c, "source", size))
            elif avg_te < 0.15 and avg_cd > 0.3 and not is_periodic:
                structures.append((center_r, center_c, "still_life", size))
            elif avg_te < 0.1 and avg_cd > 0.4:
                structures.append((center_r, center_c, "sink", size))

    return structures


def _region_is_periodic(history, region):
    """Check if a region's total activity shows periodic behavior."""
    if len(history) < 6:
        return False

    # Compute activity sum for each timestep
    activity = []
    for frame in history:
        total = sum(frame[r][c] for r, c in region)
        activity.append(total)

    # Check for period-2 or period-3 repetition
    n = len(activity)
    for period in range(2, min(8, n // 2 + 1)):
        matches = 0
        checks = 0
        for i in range(n - period):
            checks += 1
            if abs(activity[i] - activity[i + period]) < 0.1:
                matches += 1
        if checks > 0 and matches / checks > 0.8:
            return True
    return False


# ── State initialisation ─────────────────────────────────────────────

def _compdet_init(self):
    """Initialise computation detector overlay state."""
    self.compdet_active = False
    self.compdet_view = 0     # 0=TE heatmap, 1=causal density, 2=flow arrows
    self.compdet_size = 24    # sampling resolution NxN
    self.compdet_history = []  # list of sampled NxN grids
    self.compdet_max_history = 12  # frames to retain
    self.compdet_te_map = None
    self.compdet_cd_map = None
    self.compdet_flow_map = None
    self.compdet_structures = []
    self.compdet_integration = 0.0
    self.compdet_bits_processed = 0.0
    self.compdet_channel_capacity = 0.0
    self.compdet_frame = -1
    self.compdet_compute_interval = 4  # recompute every N draw frames
    self.compdet_colormap = "plasma"
    self.compdet_show_labels = True


# ── Sampling ─────────────────────────────────────────────────────────

def _compdet_sample_grid(self, N):
    """Sample current simulation into NxN grid of floats [0,1]."""
    data = self._get_minimap_data()
    if data is None:
        return None

    grid_rows, grid_cols, sample_fn = data[0], data[1], data[2]
    if grid_rows <= 0 or grid_cols <= 0:
        return None

    result = [[0.0] * N for _ in range(N)]
    for r in range(N):
        gr = int(r * grid_rows / N) % grid_rows
        for c in range(N):
            gc = int(c * grid_cols / N) % grid_cols
            try:
                result[r][c] = sample_fn(gr, gc)
            except Exception:
                result[r][c] = 0.0
    return result


# ── Compute step ─────────────────────────────────────────────────────

def _compdet_compute(self):
    """Recompute information-theoretic measures with caching."""
    frame = getattr(self, 'pp_frame_count', 0)
    if (self.compdet_te_map is not None
            and (frame - self.compdet_frame) < self.compdet_compute_interval):
        return

    N = self.compdet_size
    grid = _compdet_sample_grid(self, N)
    if grid is None:
        return

    # Append to history ring buffer
    self.compdet_history.append(grid)
    if len(self.compdet_history) > self.compdet_max_history:
        self.compdet_history = self.compdet_history[-self.compdet_max_history:]

    if len(self.compdet_history) < 3:
        return

    history = self.compdet_history

    # Compute transfer entropy heatmap
    self.compdet_te_map = _compute_total_transfer_entropy(history, N)

    # Compute causal density
    self.compdet_cd_map = _compute_causal_density(history, N)

    # Compute flow direction
    self.compdet_flow_map = _compute_flow_direction(history, N)

    # Classify structures
    self.compdet_structures = _classify_structures(
        self.compdet_te_map, self.compdet_cd_map, history, N
    )

    # Compute summary metrics
    self.compdet_integration = _compute_integration_score(
        self.compdet_te_map, self.compdet_cd_map, N
    )

    # Bits processed: total TE across all cells
    total_te = 0.0
    for r in range(N):
        for c in range(N):
            total_te += self.compdet_te_map[r][c]
    self.compdet_bits_processed += total_te

    # Channel capacity: max TE in any cell (normalised max)
    max_te = 0.0
    for r in range(N):
        for c in range(N):
            if self.compdet_te_map[r][c] > max_te:
                max_te = self.compdet_te_map[r][c]
    self.compdet_channel_capacity = max_te

    self.compdet_frame = frame


# ── Draw overlay panels ──────────────────────────────────────────────

def _compdet_draw_heatmap(self):
    """Draw the TE/causal density heatmap panel (bottom-left)."""
    if self.compdet_view == 0:
        data = self.compdet_te_map
        title = " TRANSFER ENTROPY "
    elif self.compdet_view == 1:
        data = self.compdet_cd_map
        title = " CAUSAL DENSITY "
    else:
        data = self.compdet_te_map
        title = " INFO FLOW "

    if data is None:
        return

    my, mx = self.stdscr.getmaxyx()
    N = len(data)

    panel_h = min(N, max(6, my // 3))
    panel_w = min(N * 2, max(12, mx // 3))
    cell_w = 2

    start_y = my - panel_h - 2
    start_x = 1

    if start_y < 2 or start_x + panel_w + 2 >= mx:
        return

    # Draw border
    border_w = panel_w + 2
    try:
        top = "\u250c" + title + "\u2500" * max(0, border_w - 2 - len(title)) + "\u2510"
        self.stdscr.addstr(start_y - 1, start_x - 1, top[:mx - start_x],
                           curses.color_pair(0) | curses.A_DIM)
        bot = "\u2514" + "\u2500" * (border_w - 2) + "\u2518"
        self.stdscr.addstr(start_y + panel_h, start_x - 1, bot[:mx - start_x],
                           curses.color_pair(0) | curses.A_DIM)
        for dy in range(panel_h):
            self.stdscr.addstr(start_y + dy, start_x - 1, "\u2502",
                               curses.color_pair(0) | curses.A_DIM)
            rx = start_x + panel_w
            if rx < mx - 1:
                self.stdscr.addstr(start_y + dy, rx, "\u2502",
                                   curses.color_pair(0) | curses.A_DIM)
    except curses.error:
        pass

    # Render cells
    cells_h = panel_h
    cells_w = panel_w // cell_w
    cmap = self.compdet_colormap

    if self.compdet_view == 2 and self.compdet_flow_map:
        # Flow arrow mode
        flow = self.compdet_flow_map
        for dy in range(cells_h):
            sr = int(dy * N / cells_h) % N
            py = start_y + dy
            if py >= my - 1:
                break
            for dx in range(cells_w):
                sc = int(dx * N / cells_w) % N
                px = start_x + dx * cell_w
                if px + cell_w > mx - 2:
                    break

                val = data[sr][sc]
                direction = flow[sr][sc]
                r, g, b = colormap_rgb(cmap, val)

                if direction != (0, 0) and val > 0.05:
                    arrow = _FLOW_ARROWS.get(direction, " ")
                    self.tc_buf.put(py, px, arrow + " ", r, g, b)
                else:
                    self.tc_buf.put(py, px, "\u2588\u2588", r, g, b)
    else:
        # Heatmap mode
        for dy in range(cells_h):
            sr = int(dy * N / cells_h) % N
            py = start_y + dy
            if py >= my - 1:
                break
            for dx in range(cells_w):
                sc = int(dx * N / cells_w) % N
                px = start_x + dx * cell_w
                if px + cell_w > mx - 2:
                    break

                val = data[sr][sc]
                r, g, b = colormap_rgb(cmap, val)
                self.tc_buf.put(py, px, "\u2588\u2588", r, g, b)

    # Draw structure labels on top of heatmap
    if self.compdet_show_labels and self.compdet_structures:
        for sr, sc, stype, size in self.compdet_structures[:12]:
            # Map structure position to panel position
            py = start_y + int(sr * cells_h / N)
            px = start_x + int(sc * cells_w / N) * cell_w
            if py < start_y or py >= start_y + panel_h:
                continue
            if px < start_x or px + 2 > start_x + panel_w:
                continue
            icon = _STRUCTURE_ICONS.get(stype, "?")
            try:
                self.stdscr.addstr(py, px, icon,
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass


def _compdet_draw_summary(self):
    """Draw the computation summary panel (bottom-right)."""
    my, mx = self.stdscr.getmaxyx()

    panel_w = 36
    panel_h = 10
    start_x = mx - panel_w - 2
    start_y = my - panel_h - 2

    if start_y < 2 or start_x < 2:
        return

    # Build summary lines
    N = self.compdet_size
    view_names = ["Transfer Entropy", "Causal Density", "Info Flow Arrows"]
    view_name = view_names[self.compdet_view % 3]

    n_structures = len(self.compdet_structures)
    struct_summary = {}
    for _, _, stype, _ in self.compdet_structures:
        struct_summary[stype] = struct_summary.get(stype, 0) + 1
    struct_str = " ".join(
        f"{_STRUCTURE_ICONS.get(k, '?')}{v}"
        for k, v in sorted(struct_summary.items())
    ) if struct_summary else "scanning..."

    lines = [
        f" View: {view_name}",
        f" Resolution: {N}\u00d7{N}",
        f" Frames: {len(self.compdet_history)}/{self.compdet_max_history}",
        f" \u03a6 Integration: {self.compdet_integration:.3f}",
        f" Bits processed: {self.compdet_bits_processed:.1f}",
        f" Channel cap: {self.compdet_channel_capacity:.3f}",
        f" Structures: {n_structures}",
        f" {struct_str}",
    ]

    # Draw border
    title = " COMPUTATION "
    border_w = panel_w + 2
    try:
        top = "\u250c" + title + "\u2500" * max(0, border_w - 2 - len(title)) + "\u2510"
        self.stdscr.addstr(start_y - 1, start_x - 1, top[:mx - start_x],
                           curses.color_pair(0) | curses.A_DIM)
        bot = "\u2514" + "\u2500" * (border_w - 2) + "\u2518"
        self.stdscr.addstr(start_y + panel_h, start_x - 1, bot[:mx - start_x],
                           curses.color_pair(0) | curses.A_DIM)
        for dy in range(panel_h):
            self.stdscr.addstr(start_y + dy, start_x - 1, "\u2502",
                               curses.color_pair(0) | curses.A_DIM)
            rx = start_x + panel_w
            if rx < mx - 1:
                self.stdscr.addstr(start_y + dy, rx, "\u2502",
                                   curses.color_pair(0) | curses.A_DIM)
    except curses.error:
        pass

    # Draw lines
    for i, line in enumerate(lines):
        py = start_y + i
        if py >= start_y + panel_h or py >= my - 1:
            break
        try:
            text = line[:panel_w]
            attr = curses.color_pair(0)
            if i == 0:
                attr |= curses.A_BOLD
            elif i == 3:
                attr |= curses.A_BOLD  # Phi highlighted
            self.stdscr.addstr(py, start_x, text, attr)
        except curses.error:
            pass

    # Key help line
    help_line = " Tab:view  +/-:res  l:labels "
    try:
        self.stdscr.addstr(start_y + panel_h - 1, start_x,
                           help_line[:panel_w],
                           curses.color_pair(0) | curses.A_DIM)
    except curses.error:
        pass


def _compdet_draw_indicator(self):
    """Draw a compact status badge when computation detector is active."""
    if not self.compdet_active:
        return
    my, mx = self.stdscr.getmaxyx()
    phi_str = f"{self.compdet_integration:.2f}" if self.compdet_integration > 0 else "..."
    label = f" COMPUTATION \u03a6={phi_str} "
    col = max(1, mx - len(label) - 2)
    row = 1
    if col + len(label) >= mx:
        return
    try:
        self.stdscr.addstr(row, col, label,
                           curses.color_pair(5) | curses.A_BOLD)
    except curses.error:
        pass


def _compdet_draw(self):
    """Draw all computation detector overlays."""
    if not self.compdet_active:
        return

    _compdet_compute(self)

    if self.compdet_te_map is None:
        # Not enough data yet — show waiting indicator
        _compdet_draw_indicator(self)
        return

    _compdet_draw_heatmap(self)
    _compdet_draw_summary(self)
    _compdet_draw_indicator(self)


# ── Key handling ─────────────────────────────────────────────────────

def _compdet_handle_key(self, key):
    """Handle computation detector key bindings.  Returns True if consumed."""
    # Ctrl+I — toggle on/off
    if key == 9:  # Ctrl+I = TAB = 9, use Ctrl+Shift+I check below
        pass  # TAB is too common, use different binding

    # Use 'I' (capital i) to toggle
    if key == ord("I"):
        self.compdet_active = not self.compdet_active
        if not self.compdet_active:
            self.compdet_te_map = None
            self.compdet_cd_map = None
            self.compdet_flow_map = None
            self.compdet_structures = []
            self.compdet_history = []
            self.compdet_bits_processed = 0.0
        msg = ("Computation Detector ON" if self.compdet_active
               else "Computation Detector OFF")
        if self.compdet_active:
            msg += f" ({self.compdet_size}\u00d7{self.compdet_size})"
        self._flash(msg)
        return True

    if not self.compdet_active:
        return False

    # TAB — cycle view: TE heatmap -> causal density -> flow arrows
    if key == 9:  # TAB
        self.compdet_view = (self.compdet_view + 1) % 3
        names = ["Transfer Entropy", "Causal Density", "Info Flow Arrows"]
        self._flash(f"Computation view: {names[self.compdet_view]}")
        return True

    # +/- — adjust resolution
    if key == ord("+") or key == ord("="):
        old = self.compdet_size
        self.compdet_size = min(48, self.compdet_size + 4)
        if self.compdet_size != old:
            self.compdet_history = []
            self.compdet_te_map = None
        self._flash(f"Computation resolution: {self.compdet_size}\u00d7{self.compdet_size}")
        return True
    if key == ord("-") or key == ord("_"):
        old = self.compdet_size
        self.compdet_size = max(8, self.compdet_size - 4)
        if self.compdet_size != old:
            self.compdet_history = []
            self.compdet_te_map = None
        self._flash(f"Computation resolution: {self.compdet_size}\u00d7{self.compdet_size}")
        return True

    # 'l' — toggle structure labels
    if key == ord("l"):
        self.compdet_show_labels = not self.compdet_show_labels
        self._flash("Structure labels " + ("ON" if self.compdet_show_labels else "OFF"))
        return True

    return False


# ── Registration ─────────────────────────────────────────────────────

def register(App):
    """Attach computation detector overlay methods to App."""
    App._compdet_init = _compdet_init
    App._compdet_draw = _compdet_draw
    App._compdet_draw_indicator = _compdet_draw_indicator
    App._compdet_handle_key = _compdet_handle_key
