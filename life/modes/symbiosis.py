"""Mode: symbiosis — multi-physics co-simulation with 3+ engines on shared environmental fields."""
import curses
import math
import random
import time

from life.constants import SPEEDS
from life.modes.mashup import MASHUP_SIMS, _ENGINES, _SIM_BY_ID

# Density visualization characters (5 levels)
_DENSITY = " ░▒▓█"

# ── Shared environmental field names ──────────────────────────────────
FIELD_NAMES = ["temperature", "chemical", "flow_u", "flow_v"]

# ── Preset combinations ──────────────────────────────────────────────

SYMBIOSIS_PRESETS = [
    {
        "name": "Fluid-Chemical-Biological",
        "engines": ["wave", "rd", "physarum"],
        "desc": "Waves drive chemical reactions; chemicals guide slime mold; slime creates wave disturbances",
        "colors": ["R", "G", "B"],
    },
    {
        "name": "Fire-Ising-Boids",
        "engines": ["fire", "ising", "boids"],
        "desc": "Fire heats spins; magnetic domains steer flocks; flock density fuels combustion",
        "colors": ["R", "G", "B"],
    },
    {
        "name": "Wave-RPS-GoL",
        "engines": ["wave", "rps", "gol"],
        "desc": "Waves modulate dominance; RPS competition seeds life; life emits wave pulses",
        "colors": ["R", "G", "B"],
    },
    {
        "name": "Full Ecosystem",
        "engines": ["rd", "boids", "fire", "physarum"],
        "desc": "Chemistry, organisms, fire, and fungal networks interacting through shared fields",
        "colors": ["R", "G", "B", "Y"],
    },
    {
        "name": "Quantum-Classical Bridge",
        "engines": ["wave", "ising", "rd"],
        "desc": "Wave interference shapes spin domains; spin alignment catalyzes reactions; reactions emit waves",
        "colors": ["R", "G", "B"],
    },
    {
        "name": "Predator Ecosystem",
        "engines": ["boids", "physarum", "rps", "gol"],
        "desc": "Flocks, slime trails, cyclic competition, and cellular life in one shared world",
        "colors": ["R", "G", "B", "Y"],
    },
]

# Color channel assignments for visualization
_CHANNEL_COLORS = {
    "R": (1, "red"),
    "G": (2, "green"),
    "B": (6, "cyan"),
    "Y": (3, "yellow"),
    "M": (5, "magenta"),
    "W": (7, "white"),
}

# All available channels (for 3-8 engines)
_ALL_CHANNELS = ["R", "G", "B", "Y", "M", "W", "R", "G"]


# ════════════════════════════════════════════════════════════════════
#  Shared Environmental Fields
#
#  Each field is a 2D float grid [0,1] that all engines can read/write.
#  Fields mediate cross-domain interactions:
#    temperature  — friction/fire/reaction heat
#    chemical     — concentration gradients
#    flow_u/v     — velocity components
# ════════════════════════════════════════════════════════════════════

def _init_fields(rows, cols):
    """Create empty shared environmental fields."""
    return {
        "temperature": [[0.0] * cols for _ in range(rows)],
        "chemical": [[0.0] * cols for _ in range(rows)],
        "flow_u": [[0.0] * cols for _ in range(rows)],
        "flow_v": [[0.0] * cols for _ in range(rows)],
    }


def _update_fields(fields, layers, rows, cols):
    """Update shared fields from all engine densities.

    Each engine type contributes to different fields:
      wave     → temperature (kinetic energy), flow_u/v (wave gradient)
      rd       → chemical (reaction product concentration)
      fire     → temperature (combustion heat)
      boids    → flow_u/v (flock velocity), chemical (pheromone deposit)
      physarum → chemical (trail pheromone)
      ising    → temperature (spin frustration energy)
      rps      → chemical (competition intensity)
      gol      → temperature (population density heat)
    """
    temp = fields["temperature"]
    chem = fields["chemical"]
    fu = fields["flow_u"]
    fv = fields["flow_v"]

    # Decay existing fields
    for r in range(rows):
        for c in range(cols):
            temp[r][c] *= 0.92
            chem[r][c] *= 0.95
            fu[r][c] *= 0.90
            fv[r][c] *= 0.90

    for layer in layers:
        eid = layer["id"]
        d = layer["density"]
        state = layer["state"]
        w = layer.get("field_weight", 0.3)

        if eid == "wave":
            for r in range(rows):
                for c in range(cols):
                    temp[r][c] = min(1.0, temp[r][c] + d[r][c] * w * 0.5)
                    # Wave gradient as flow
                    dr = (d[(r + 1) % rows][c] - d[(r - 1) % rows][c]) * 0.5
                    dc = (d[r][(c + 1) % cols] - d[r][(c - 1) % cols]) * 0.5
                    fu[r][c] = max(-1.0, min(1.0, fu[r][c] + dr * w))
                    fv[r][c] = max(-1.0, min(1.0, fv[r][c] + dc * w))
        elif eid == "rd":
            for r in range(rows):
                for c in range(cols):
                    chem[r][c] = min(1.0, chem[r][c] + d[r][c] * w * 0.6)
        elif eid == "fire":
            for r in range(rows):
                for c in range(cols):
                    temp[r][c] = min(1.0, temp[r][c] + d[r][c] * w * 0.8)
        elif eid == "boids":
            agents = state.get("agents", [])
            for a in agents:
                ri, ci = int(a[0]) % rows, int(a[1]) % cols
                fu[ri][ci] = max(-1.0, min(1.0, fu[ri][ci] + a[2] * w))
                fv[ri][ci] = max(-1.0, min(1.0, fv[ri][ci] + a[3] * w))
                chem[ri][ci] = min(1.0, chem[ri][ci] + 0.1 * w)
        elif eid == "physarum":
            for r in range(rows):
                for c in range(cols):
                    chem[r][c] = min(1.0, chem[r][c] + d[r][c] * w * 0.4)
        elif eid == "ising":
            for r in range(rows):
                for c in range(cols):
                    temp[r][c] = min(1.0, temp[r][c] + abs(d[r][c] - 0.5) * w)
        elif eid == "rps":
            for r in range(rows):
                for c in range(cols):
                    chem[r][c] = min(1.0, chem[r][c] + d[r][c] * w * 0.3)
        elif eid == "gol":
            for r in range(rows):
                for c in range(cols):
                    temp[r][c] = min(1.0, temp[r][c] + d[r][c] * w * 0.4)

    # Diffuse fields slightly for spatial smoothness
    _diffuse_field(temp, rows, cols, 0.1)
    _diffuse_field(chem, rows, cols, 0.08)
    _diffuse_field(fu, rows, cols, 0.05)
    _diffuse_field(fv, rows, cols, 0.05)


def _diffuse_field(field, rows, cols, rate):
    """Simple 4-neighbor diffusion pass."""
    buf = [[0.0] * cols for _ in range(rows)]
    keep = 1.0 - rate
    spread = rate / 4.0
    for r in range(rows):
        for c in range(cols):
            buf[r][c] = (field[r][c] * keep +
                         (field[(r - 1) % rows][c] + field[(r + 1) % rows][c] +
                          field[r][(c - 1) % cols] + field[r][(c + 1) % cols]) * spread)
    for r in range(rows):
        for c in range(cols):
            field[r][c] = buf[r][c]


def _field_coupling_density(fields, engine_id, rows, cols):
    """Build a coupling density for an engine from the shared fields.

    Each engine type responds to different fields:
      wave     ← chemical (reactions create wave sources)
      rd       ← temperature (heat accelerates reactions)
      fire     ← chemical (fuel from chemicals), flow (wind spreads fire)
      boids    ← chemical (follow gradients), flow (carried by currents)
      physarum ← chemical (attracted to concentration), temperature (avoid heat)
      ising    ← temperature (modulates thermal fluctuations)
      rps      ← flow (advection of competition fronts)
      gol      ← temperature (warmth aids birth), chemical (nutrients)
    """
    temp = fields["temperature"]
    chem = fields["chemical"]
    fu = fields["flow_u"]
    fv = fields["flow_v"]

    od = [[0.0] * cols for _ in range(rows)]
    if engine_id == "wave":
        for r in range(rows):
            for c in range(cols):
                od[r][c] = chem[r][c] * 0.6 + temp[r][c] * 0.2
    elif engine_id == "rd":
        for r in range(rows):
            for c in range(cols):
                od[r][c] = temp[r][c] * 0.7 + abs(fu[r][c]) * 0.2
    elif engine_id == "fire":
        for r in range(rows):
            for c in range(cols):
                wind = math.sqrt(fu[r][c] ** 2 + fv[r][c] ** 2)
                od[r][c] = chem[r][c] * 0.5 + min(1.0, wind) * 0.4
    elif engine_id == "boids":
        for r in range(rows):
            for c in range(cols):
                od[r][c] = chem[r][c] * 0.5 + temp[r][c] * 0.2
    elif engine_id == "physarum":
        for r in range(rows):
            for c in range(cols):
                od[r][c] = chem[r][c] * 0.6 + max(0.0, 0.3 - temp[r][c] * 0.3)
    elif engine_id == "ising":
        for r in range(rows):
            for c in range(cols):
                od[r][c] = temp[r][c] * 0.8
    elif engine_id == "rps":
        for r in range(rows):
            for c in range(cols):
                wind = math.sqrt(fu[r][c] ** 2 + fv[r][c] ** 2)
                od[r][c] = min(1.0, wind) * 0.5 + chem[r][c] * 0.3
    elif engine_id == "gol":
        for r in range(rows):
            for c in range(cols):
                od[r][c] = temp[r][c] * 0.4 + chem[r][c] * 0.5
    return od


# ════════════════════════════════════════════════════════════════════
#  Mode entry / exit
# ════════════════════════════════════════════════════════════════════

def _enter_symbiosis_mode(self):
    """Enter Symbiosis mode — show engine selection menu."""
    self.symbiosis_menu = True
    self.symbiosis_menu_sel = 0
    self.symbiosis_menu_phase = 0  # 0=presets, 1=custom pick
    self.symbiosis_custom_picks = []
    self._flash("Symbiosis — multi-physics co-simulation")


def _exit_symbiosis_mode(self):
    """Exit Symbiosis mode and clean up."""
    self.symbiosis_mode = False
    self.symbiosis_menu = False
    self.symbiosis_running = False
    self.symbiosis_layers = None
    self.symbiosis_fields = None
    self._flash("Symbiosis mode OFF")


# ════════════════════════════════════════════════════════════════════
#  Initialization
# ════════════════════════════════════════════════════════════════════

def _symbiosis_init(self, engine_ids, channel_map=None):
    """Initialize N simulation engines on a shared grid with environmental fields."""
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(16, max_y - 5)
    cols = max(16, (max_x - 1) // 2)
    self.symbiosis_rows = rows
    self.symbiosis_cols = cols
    self.symbiosis_engine_ids = engine_ids

    # Initialize each engine as a layer
    self.symbiosis_layers = []
    for i, eid in enumerate(engine_ids):
        init_fn, _, dens_fn = _ENGINES[eid]
        state = init_fn(rows, cols)
        ch = (channel_map[i] if channel_map and i < len(channel_map)
              else _ALL_CHANNELS[i % len(_ALL_CHANNELS)])
        self.symbiosis_layers.append({
            "id": eid,
            "name": _SIM_BY_ID[eid]["name"],
            "state": state,
            "density": dens_fn(state),
            "channel": ch,
            "visible": True,
            "solo": False,
            "field_weight": 0.3,
        })

    # Shared environmental fields
    self.symbiosis_fields = _init_fields(rows, cols)
    self.symbiosis_generation = 0
    self.symbiosis_running = False
    self.symbiosis_coupling = 0.5
    self.symbiosis_show_fields = False  # Toggle field overlay
    self.symbiosis_field_view = 0       # Which field to show (0-3)

    self.symbiosis_menu = False
    self.symbiosis_mode = True
    names = " + ".join(l["name"] for l in self.symbiosis_layers)
    self._flash(f"Symbiosis: {names} — Space to start")


# ════════════════════════════════════════════════════════════════════
#  Simulation step
# ════════════════════════════════════════════════════════════════════

def _symbiosis_step(self):
    """Advance all engines by one step with shared-field coupling."""
    rows = self.symbiosis_rows
    cols = self.symbiosis_cols
    layers = self.symbiosis_layers
    fields = self.symbiosis_fields
    coupling = self.symbiosis_coupling

    # Update shared environmental fields from current densities
    _update_fields(fields, layers, rows, cols)

    # Step each engine with field-derived coupling
    for layer in layers:
        eid = layer["id"]
        _, step_fn, dens_fn = _ENGINES[eid]

        # Build coupling input from shared fields
        od = _field_coupling_density(fields, eid, rows, cols)

        step_fn(layer["state"], od, coupling)
        layer["density"] = dens_fn(layer["state"])

    self.symbiosis_generation += 1


# ════════════════════════════════════════════════════════════════════
#  Menu drawing
# ════════════════════════════════════════════════════════════════════

def _draw_symbiosis_menu(self, max_y, max_x):
    """Draw the symbiosis mode selection menu."""
    self.stdscr.erase()
    phase = self.symbiosis_menu_phase

    title = "── Symbiosis: Multi-Physics Co-Simulation ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    if phase == 0:
        # ── Preset selection ──
        subtitle = "Choose a preset ecosystem or build custom:"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                               curses.color_pair(6))
        except curses.error:
            pass

        for i, preset in enumerate(SYMBIOSIS_PRESETS):
            y = 5 + i
            if y >= max_y - 3:
                break
            sel = i == self.symbiosis_menu_sel
            marker = "▸ " if sel else "  "
            attr = curses.color_pair(7) | curses.A_BOLD if sel else curses.color_pair(6)
            n_engines = len(preset["engines"])
            line = f"{marker}{preset['name']} ({n_engines} engines)"
            try:
                self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
            except curses.error:
                pass
            if sel:
                try:
                    self.stdscr.addstr(y + 1, 6, preset["desc"][:max_x - 8],
                                       curses.color_pair(6) | curses.A_DIM)
                except curses.error:
                    pass

        # Custom option
        ci = len(SYMBIOSIS_PRESETS)
        # Account for description lines
        y = 5 + ci + 1
        if y < max_y - 3:
            sel = self.symbiosis_menu_sel == ci
            marker = "▸ " if sel else "  "
            attr = curses.color_pair(7) | curses.A_BOLD if sel else curses.color_pair(3)
            try:
                self.stdscr.addstr(y, 2, f"{marker}Custom Symbiosis (pick 3-8 engines)..."[:max_x - 4], attr)
            except curses.error:
                pass

    elif phase == 1:
        # ── Custom engine picking ──
        picks = self.symbiosis_custom_picks
        picked_names = [_SIM_BY_ID[p]["name"] for p in picks]
        subtitle = f"Selected ({len(picks)}): {', '.join(picked_names) if picks else 'none'}"
        try:
            self.stdscr.addstr(3, 2, subtitle[:max_x - 4], curses.color_pair(3))
        except curses.error:
            pass

        help_text = "[Enter]=toggle  [G]=go (need 3+)  [Esc]=back"
        try:
            self.stdscr.addstr(4, 2, help_text[:max_x - 4],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

        for i, sim in enumerate(MASHUP_SIMS):
            y = 6 + i
            if y >= max_y - 2:
                break
            sel = i == self.symbiosis_menu_sel
            picked = sim["id"] in picks
            marker = "▸ " if sel else "  "
            check = "■ " if picked else "□ "
            if picked:
                attr = curses.color_pair(2) | curses.A_BOLD
            elif sel:
                attr = curses.color_pair(7) | curses.A_BOLD
            else:
                attr = curses.color_pair(6)
            try:
                self.stdscr.addstr(y, 2, f"{marker}{check}{sim['name']}"[:max_x - 4], attr)
                self.stdscr.addstr(y, 32, sim["desc"][:max_x - 34],
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        if phase == 0:
            hint = " [Up/Down]=navigate  [Enter]=select  [Esc]=exit"
        else:
            hint = " [Up/Down]=navigate  [Enter]=toggle  [G]=launch  [Esc]=back"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ════════════════════════════════════════════════════════════════════
#  Menu key handling
# ════════════════════════════════════════════════════════════════════

def _handle_symbiosis_menu_key(self, key):
    """Handle input in the symbiosis selection menu."""
    if key == -1:
        return True
    phase = self.symbiosis_menu_phase

    if phase == 0:
        n = len(SYMBIOSIS_PRESETS) + 1  # +1 for Custom
        if key in (curses.KEY_UP, ord("k")):
            self.symbiosis_menu_sel = (self.symbiosis_menu_sel - 1) % max(1, n)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.symbiosis_menu_sel = (self.symbiosis_menu_sel + 1) % max(1, n)
            return True
        if key == 27:
            self.symbiosis_menu = False
            self._flash("Symbiosis cancelled")
            return True
        if key in (10, 13, curses.KEY_ENTER):
            sel = self.symbiosis_menu_sel
            if sel < len(SYMBIOSIS_PRESETS):
                preset = SYMBIOSIS_PRESETS[sel]
                self._symbiosis_init(preset["engines"], preset["colors"])
            else:
                self.symbiosis_menu_phase = 1
                self.symbiosis_menu_sel = 0
                self.symbiosis_custom_picks = []
            return True

    elif phase == 1:
        n = len(MASHUP_SIMS)
        if key in (curses.KEY_UP, ord("k")):
            self.symbiosis_menu_sel = (self.symbiosis_menu_sel - 1) % max(1, n)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.symbiosis_menu_sel = (self.symbiosis_menu_sel + 1) % max(1, n)
            return True
        if key == 27:
            self.symbiosis_menu_phase = 0
            self.symbiosis_menu_sel = 0
            return True
        if key in (10, 13, curses.KEY_ENTER):
            # Toggle selection
            eid = MASHUP_SIMS[self.symbiosis_menu_sel]["id"]
            if eid in self.symbiosis_custom_picks:
                self.symbiosis_custom_picks.remove(eid)
            else:
                if len(self.symbiosis_custom_picks) < 8:
                    self.symbiosis_custom_picks.append(eid)
                else:
                    self._flash("Maximum 8 engines")
            return True
        if key in (ord("g"), ord("G")):
            if len(self.symbiosis_custom_picks) >= 3:
                self._symbiosis_init(self.symbiosis_custom_picks)
            else:
                self._flash("Select at least 3 engines")
            return True

    return True


# ════════════════════════════════════════════════════════════════════
#  Main simulation drawing
# ════════════════════════════════════════════════════════════════════

def _draw_symbiosis(self, max_y, max_x):
    """Draw the overlaid multi-physics simulation with RGB-layered channels."""
    self.stdscr.erase()
    layers = self.symbiosis_layers
    rows = self.symbiosis_rows
    cols = self.symbiosis_cols

    # ── Title bar ──
    state = "▶ RUNNING" if self.symbiosis_running else "⏸ PAUSED"
    n_vis = sum(1 for l in layers if l["visible"])
    any_solo = any(l["solo"] for l in layers)
    title = (f" SYMBIOSIS: {len(layers)} engines"
             f"  |  gen {self.symbiosis_generation}"
             f"  |  coupling={self.symbiosis_coupling:.2f}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # ── Determine visible layers ──
    if any_solo:
        vis_layers = [l for l in layers if l["solo"]]
    else:
        vis_layers = [l for l in layers if l["visible"]]

    # ── Render overlaid density grid ──
    view_rows = min(rows, max_y - 5 - len(layers))
    view_cols = min(cols, (max_x - 1) // 2)

    if self.symbiosis_show_fields:
        # Show environmental field instead
        _draw_field_overlay(self, max_y, max_x, view_rows, view_cols)
    else:
        for r in range(view_rows):
            sy = 1 + r
            if sy >= max_y - 3 - len(layers):
                break
            for c in range(view_cols):
                sx = c * 2
                if sx + 1 >= max_x:
                    break

                # Find dominant layer and total intensity
                best_val = 0.0
                best_ch = "W"
                total = 0.0
                n_active = 0
                for l in vis_layers:
                    d = l["density"]
                    v = d[r][c] if r < len(d) and c < len(d[r]) else 0.0
                    total += v
                    if v > best_val:
                        best_val = v
                        best_ch = l["channel"]
                    if v > 0.05:
                        n_active += 1

                if best_val < 0.01:
                    continue

                # Density glyph
                mx = min(1.0, total / max(1, len(vis_layers)) * 2.0)
                mx = max(mx, best_val)
                di = max(1, min(4, int(mx * 4.0)))
                ch = _DENSITY[di]

                # Color from dominant layer's channel
                if n_active > 1:
                    # Mix: find two strongest
                    vals = []
                    for l in vis_layers:
                        d = l["density"]
                        v = d[r][c] if r < len(d) and c < len(d[r]) else 0.0
                        vals.append((v, l["channel"]))
                    vals.sort(reverse=True)
                    if vals[0][0] > vals[1][0] * 1.5 + 0.05:
                        pair = _CHANNEL_COLORS.get(vals[0][1], (7, "white"))[0]
                    else:
                        # Overlap — use magenta for mix
                        pair = 5
                else:
                    pair = _CHANNEL_COLORS.get(best_ch, (7, "white"))[0]

                if mx > 0.7:
                    attr = curses.color_pair(pair) | curses.A_BOLD
                elif mx > 0.3:
                    attr = curses.color_pair(pair)
                else:
                    attr = curses.color_pair(pair) | curses.A_DIM

                try:
                    self.stdscr.addstr(sy, sx, ch + " ", attr)
                except curses.error:
                    pass

    # ── Layer legend ──
    legend_y = max_y - 2 - len(layers)
    for i, l in enumerate(layers):
        y = legend_y + i
        if y < 1 or y >= max_y - 2:
            continue
        ch_info = _CHANNEL_COLORS.get(l["channel"], (7, "white"))
        vis_icon = "●" if l["visible"] else "○"
        solo_icon = " [SOLO]" if l["solo"] else ""
        label = f" {i + 1}:{vis_icon} {l['name']} ({ch_info[1]}){solo_icon}"
        attr = curses.color_pair(ch_info[0])
        if not l["visible"] and not l["solo"]:
            attr |= curses.A_DIM
        if l["solo"]:
            attr |= curses.A_BOLD
        try:
            self.stdscr.addstr(y, 0, label[:max_x - 1], attr)
        except curses.error:
            pass

    # ── Status bar ──
    status_y = max_y - 2
    if status_y > 1:
        densities = []
        cnt = max(1, rows * cols)
        for l in layers:
            s = sum(sum(row) for row in l["density"]) / cnt
            densities.append(f"{l['id']}={s:.3f}")
        field_mode = f"  field={FIELD_NAMES[self.symbiosis_field_view]}" if self.symbiosis_show_fields else ""
        status = f" gen {self.symbiosis_generation}  |  {' '.join(densities)}  |  c={self.symbiosis_coupling:.2f}{field_mode}"
        try:
            self.stdscr.addstr(status_y, 0, status[:max_x - 1],
                               curses.color_pair(6))
        except curses.error:
            pass

    # ── Hint bar ──
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [1-8]=solo [!-*]=mute [f]=fields [+/-]=coupling [r]=reset [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_field_overlay(self, max_y, max_x, view_rows, view_cols):
    """Draw the currently selected environmental field as a heatmap."""
    fields = self.symbiosis_fields
    field_name = FIELD_NAMES[self.symbiosis_field_view]
    field = fields[field_name]
    rows = self.symbiosis_rows
    n_layers = len(self.symbiosis_layers)

    for r in range(view_rows):
        sy = 1 + r
        if sy >= max_y - 3 - n_layers:
            break
        for c in range(view_cols):
            sx = c * 2
            if sx + 1 >= max_x:
                break
            v = field[r][c] if r < len(field) and c < len(field[r]) else 0.0
            if field_name in ("flow_u", "flow_v"):
                v = (v + 1.0) / 2.0  # Remap [-1,1] to [0,1]
            v = max(0.0, min(1.0, v))
            if v < 0.01:
                continue
            di = max(1, min(4, int(v * 4.0)))
            ch = _DENSITY[di]
            # Temperature=red, chemical=green, flow=cyan
            if field_name == "temperature":
                pair = 1  # red
            elif field_name == "chemical":
                pair = 2  # green
            else:
                pair = 6  # cyan
            if v > 0.7:
                attr = curses.color_pair(pair) | curses.A_BOLD
            elif v > 0.3:
                attr = curses.color_pair(pair)
            else:
                attr = curses.color_pair(pair) | curses.A_DIM
            try:
                self.stdscr.addstr(sy, sx, ch + " ", attr)
            except curses.error:
                pass


# ════════════════════════════════════════════════════════════════════
#  Simulation key handling
# ════════════════════════════════════════════════════════════════════

# Mute key mapping: Shift+1..8 → '!', '@', '#', '$', '%', '^', '&', '*'
_MUTE_KEYS = {ord("!"): 0, ord("@"): 1, ord("#"): 2, ord("$"): 3,
              ord("%"): 4, ord("^"): 5, ord("&"): 6, ord("*"): 7}


def _handle_symbiosis_key(self, key):
    """Handle input during active symbiosis simulation."""
    if key == -1:
        return True
    layers = self.symbiosis_layers

    if key in (ord("q"), 27):
        self._exit_symbiosis_mode()
        return True
    if key == ord(" "):
        self.symbiosis_running = not self.symbiosis_running
        self._flash("Playing" if self.symbiosis_running else "Paused")
        return True
    if key in (ord("n"), ord(".")):
        self.symbiosis_running = False
        self._symbiosis_step()
        return True

    # Solo: press 1-8 to solo a layer (press again to unsolo)
    if ord("1") <= key <= ord("8"):
        idx = key - ord("1")
        if idx < len(layers):
            was_solo = layers[idx]["solo"]
            # Clear all solos
            for l in layers:
                l["solo"] = False
            if not was_solo:
                layers[idx]["solo"] = True
                self._flash(f"Solo: {layers[idx]['name']}")
            else:
                self._flash("All layers visible")
        return True

    # Mute: Shift+1-8
    if key in _MUTE_KEYS:
        idx = _MUTE_KEYS[key]
        if idx < len(layers):
            layers[idx]["visible"] = not layers[idx]["visible"]
            state_str = "visible" if layers[idx]["visible"] else "muted"
            self._flash(f"{layers[idx]['name']}: {state_str}")
        return True

    # Show all layers
    if key == ord("a"):
        for l in layers:
            l["visible"] = True
            l["solo"] = False
        self._flash("All layers visible")
        return True

    # Toggle field overlay
    if key == ord("f"):
        self.symbiosis_show_fields = not self.symbiosis_show_fields
        if self.symbiosis_show_fields:
            self._flash(f"Field view: {FIELD_NAMES[self.symbiosis_field_view]}")
        else:
            self._flash("Field view OFF")
        return True

    # Cycle field view
    if key == ord("F"):
        self.symbiosis_field_view = (self.symbiosis_field_view + 1) % len(FIELD_NAMES)
        self.symbiosis_show_fields = True
        self._flash(f"Field: {FIELD_NAMES[self.symbiosis_field_view]}")
        return True

    # Coupling adjustment
    if key in (ord("+"), ord("=")):
        self.symbiosis_coupling = min(1.0, self.symbiosis_coupling + 0.05)
        self._flash(f"Coupling: {self.symbiosis_coupling:.2f}")
        return True
    if key in (ord("-"), ord("_")):
        self.symbiosis_coupling = max(0.0, self.symbiosis_coupling - 0.05)
        self._flash(f"Coupling: {self.symbiosis_coupling:.2f}")
        return True
    if key == ord("0"):
        self.symbiosis_coupling = 0.0
        self._flash("Coupling: OFF (independent)")
        return True

    # Reset
    if key == ord("r"):
        ch_map = [l["channel"] for l in layers]
        self._symbiosis_init(self.symbiosis_engine_ids, ch_map)
        self._flash("Reset!")
        return True

    # Back to menu
    if key == ord("R"):
        self.symbiosis_mode = False
        self.symbiosis_running = False
        self.symbiosis_menu = True
        self.symbiosis_menu_phase = 0
        self.symbiosis_menu_sel = 0
        return True

    # Speed
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
    """Register symbiosis mode methods on the App class."""
    App._enter_symbiosis_mode = _enter_symbiosis_mode
    App._exit_symbiosis_mode = _exit_symbiosis_mode
    App._symbiosis_init = _symbiosis_init
    App._symbiosis_step = _symbiosis_step
    App._handle_symbiosis_menu_key = _handle_symbiosis_menu_key
    App._handle_symbiosis_key = _handle_symbiosis_key
    App._draw_symbiosis_menu = _draw_symbiosis_menu
    App._draw_symbiosis = _draw_symbiosis
    App.SYMBIOSIS_PRESETS = SYMBIOSIS_PRESETS
