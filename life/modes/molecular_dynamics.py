"""Molecular Dynamics / Phase Transitions — Lennard-Jones particles self-organizing
into solid, liquid, and gas phases with real-time temperature control.

Particles interact via the Lennard-Jones 6-12 potential:
    V(r) = 4ε[(σ/r)¹² - (σ/r)⁶]

producing short-range repulsion and long-range attraction.  A velocity-rescaling
thermostat controls temperature, letting you watch crystals melt, liquids boil,
and gases condense — all from the same simple force law.

Presets
-------
1. Crystal Growth      — cold start, particles freeze into hexagonal lattice
2. Melting Point       — crystal just above melting → watch order break down
3. Supercooling        — quench hot gas → nucleation & crystal island growth
4. Triple Point        — near coexistence of solid, liquid, and gas
5. Boiling             — liquid heated past boiling → explosive evaporation
6. Gas / Ideal Gas     — high temperature, dilute → random ballistic motion
"""
import curses
import math
import random

# ── Lennard-Jones parameters (reduced units) ────────────────────────────
SIGMA = 1.0
EPSILON = 1.0
CUTOFF = 2.5 * SIGMA      # truncation radius
CUTOFF2 = CUTOFF * CUTOFF
DT = 0.005                 # integration time step
PARTICLE_MASS = 1.0

# ── Presets ──────────────────────────────────────────────────────────────
MOLDYN_PRESETS = [
    ("Crystal Growth",
     "Cold start — particles freeze into hexagonal lattice",
     {"temperature": 0.1, "density": 0.8, "n_particles": 120,
      "init": "lattice", "thermostat": True}),
    ("Melting Point",
     "Crystal just above melting — watch order break down",
     {"temperature": 0.75, "density": 0.8, "n_particles": 120,
      "init": "lattice", "thermostat": True}),
    ("Supercooling / Nucleation",
     "Quench hot gas — nucleation & crystal island growth",
     {"temperature": 0.3, "density": 0.6, "n_particles": 100,
      "init": "random", "thermostat": True}),
    ("Triple Point",
     "Near coexistence of solid, liquid, and gas",
     {"temperature": 0.69, "density": 0.45, "n_particles": 100,
      "init": "random", "thermostat": True}),
    ("Boiling",
     "Liquid heated past boiling — explosive evaporation",
     {"temperature": 1.5, "density": 0.6, "n_particles": 100,
      "init": "lattice", "thermostat": True}),
    ("Gas / Ideal Gas",
     "High temperature, dilute — random ballistic motion",
     {"temperature": 3.0, "density": 0.15, "n_particles": 80,
      "init": "random", "thermostat": True}),
]

# ── Particle characters by kinetic energy ────────────────────────────────
# low KE → high KE
KE_CHARS = ["·", "∘", "○", "●", "◉", "★"]


# ── Simulation core ─────────────────────────────────────────────────────

def _init_sim(settings):
    """Create a simulation state dict from preset settings."""
    n = settings["n_particles"]
    density = settings["density"]
    # Box size from density: density = N / area → L = sqrt(N / density)
    box_l = math.sqrt(n / density)

    x = [0.0] * n
    y = [0.0] * n
    vx = [0.0] * n
    vy = [0.0] * n

    if settings["init"] == "lattice":
        # Hexagonal close-packed lattice
        cols = max(1, int(math.sqrt(n * box_l / box_l)))  # approx square
        spacing = box_l / (cols + 1)
        cols = max(1, int(box_l / (SIGMA * 1.12)))
        spacing = box_l / cols
        row = 0
        col = 0
        for i in range(n):
            x[i] = (col + 0.5 * (row % 2)) * spacing + spacing * 0.25
            y[i] = row * spacing * 0.866 + spacing * 0.25
            # Wrap into box
            x[i] = x[i] % box_l
            y[i] = y[i] % box_l
            col += 1
            if col >= cols:
                col = 0
                row += 1
    else:
        # Place on a jittered lattice to avoid overlaps at any density
        cols = max(1, int(math.ceil(math.sqrt(n))))
        rows_needed = max(1, int(math.ceil(n / cols)))
        sx_sp = box_l / cols
        sy_sp = box_l / rows_needed
        jitter = min(sx_sp, sy_sp) * 0.15
        idx = 0
        for row in range(rows_needed):
            for col in range(cols):
                if idx >= n:
                    break
                x[idx] = (col + 0.5) * sx_sp + random.uniform(-jitter, jitter)
                y[idx] = (row + 0.5) * sy_sp + random.uniform(-jitter, jitter)
                x[idx] = x[idx] % box_l
                y[idx] = y[idx] % box_l
                idx += 1

    # Maxwell-Boltzmann velocities
    target_t = settings["temperature"]
    for i in range(n):
        vx[i] = random.gauss(0, math.sqrt(target_t))
        vy[i] = random.gauss(0, math.sqrt(target_t))

    # Remove net momentum
    avg_vx = sum(vx) / n
    avg_vy = sum(vy) / n
    for i in range(n):
        vx[i] -= avg_vx
        vy[i] -= avg_vy

    # Force arrays
    fx = [0.0] * n
    fy = [0.0] * n

    sim = {
        "n": n,
        "box_l": box_l,
        "x": x, "y": y,
        "vx": vx, "vy": vy,
        "fx": fx, "fy": fy,
        "target_temp": target_t,
        "thermostat": settings["thermostat"],
        "step": 0,
        "speed": 5,
        "pe": 0.0,
        "ke": 0.0,
        "temp": target_t,
        "pressure": 0.0,
        "ke_history": [],
        "pe_history": [],
        "temp_history": [],
        "rdf_bins": [0.0] * 50,
        "rdf_count": 0,
        "virial_sum": 0.0,
    }
    # Compute initial forces
    _compute_forces(sim)
    return sim


def _compute_forces(sim):
    """Compute Lennard-Jones forces and potential energy."""
    n = sim["n"]
    box_l = sim["box_l"]
    x, y = sim["x"], sim["y"]
    fx, fy = sim["fx"], sim["fy"]

    # Zero forces
    for i in range(n):
        fx[i] = 0.0
        fy[i] = 0.0

    pe = 0.0
    virial = 0.0

    for i in range(n - 1):
        xi, yi = x[i], y[i]
        for j in range(i + 1, n):
            dx = xi - x[j]
            dy = yi - y[j]
            # Minimum image convention (periodic boundaries)
            dx -= box_l * round(dx / box_l)
            dy -= box_l * round(dy / box_l)
            r2 = dx * dx + dy * dy
            if r2 < CUTOFF2 and r2 > 0.01:
                r2i = SIGMA * SIGMA / r2
                r6i = r2i * r2i * r2i
                r12i = r6i * r6i
                # Force magnitude / r
                ff = 24.0 * EPSILON * (2.0 * r12i - r6i) / r2
                fxi = ff * dx
                fyi = ff * dy
                fx[i] += fxi
                fy[i] += fyi
                fx[j] -= fxi
                fy[j] -= fyi
                # Potential
                pe += 4.0 * EPSILON * (r12i - r6i)
                # Virial for pressure
                virial += ff * r2

    sim["pe"] = pe
    sim["virial_sum"] = virial


def _step(sim):
    """Velocity-Verlet integration step."""
    n = sim["n"]
    box_l = sim["box_l"]
    x, y = sim["x"], sim["y"]
    vx, vy = sim["vx"], sim["vy"]
    fx, fy = sim["fx"], sim["fy"]
    dt = DT
    half_dt = 0.5 * dt

    # Half-step velocities & full-step positions
    for i in range(n):
        vx[i] += half_dt * fx[i]
        vy[i] += half_dt * fy[i]
        x[i] += dt * vx[i]
        y[i] += dt * vy[i]
        # Periodic boundary conditions
        x[i] = x[i] % box_l
        y[i] = y[i] % box_l

    # Recompute forces at new positions
    _compute_forces(sim)

    # Complete velocity step
    for i in range(n):
        vx[i] += half_dt * fx[i]
        vy[i] += half_dt * fy[i]

    # Kinetic energy & temperature
    ke = 0.0
    for i in range(n):
        ke += 0.5 * (vx[i] * vx[i] + vy[i] * vy[i])
    sim["ke"] = ke
    # Temperature: KE = (N_dof/2) * kT, N_dof = 2N - 2 (2D, momentum conserved)
    n_dof = max(1, 2 * n - 2)
    sim["temp"] = 2.0 * ke / n_dof

    # Velocity-rescaling thermostat
    if sim["thermostat"] and sim["temp"] > 1e-10:
        scale = math.sqrt(sim["target_temp"] / sim["temp"])
        # Gentle rescaling (Berendsen-like)
        lam = 1.0 + 0.1 * (scale - 1.0)
        for i in range(n):
            vx[i] *= lam
            vy[i] *= lam
        ke *= lam * lam
        sim["ke"] = ke
        sim["temp"] = 2.0 * ke / n_dof

    # Pressure: P = (N*kT + virial/2) / V  (2D: V = area)
    area = box_l * box_l
    sim["pressure"] = (n * sim["temp"] + sim["virial_sum"] / 2.0) / area

    sim["step"] += 1

    # Record history (every 5 steps to keep arrays manageable)
    if sim["step"] % 5 == 0:
        sim["ke_history"].append(sim["ke"] / max(1, n))
        sim["pe_history"].append(sim["pe"] / max(1, n))
        sim["temp_history"].append(sim["temp"])
        # Keep last 200 points
        for key in ("ke_history", "pe_history", "temp_history"):
            if len(sim[key]) > 200:
                sim[key] = sim[key][-200:]

    # Accumulate RDF every 20 steps
    if sim["step"] % 20 == 0:
        _accumulate_rdf(sim)


def _accumulate_rdf(sim):
    """Accumulate radial distribution function histogram."""
    n = sim["n"]
    box_l = sim["box_l"]
    x, y = sim["x"], sim["y"]
    bins = sim["rdf_bins"]
    n_bins = len(bins)
    max_r = min(box_l / 2.0, 4.0 * SIGMA)
    dr = max_r / n_bins

    for i in range(n - 1):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            dx -= box_l * round(dx / box_l)
            dy -= box_l * round(dy / box_l)
            r = math.sqrt(dx * dx + dy * dy)
            b = int(r / dr)
            if 0 <= b < n_bins:
                bins[b] += 2  # count both i-j and j-i

    sim["rdf_count"] += 1


def _classify_phase(sim):
    """Heuristic phase classification based on temperature and structure."""
    t = sim["temp"]
    # Use RDF peak height as order parameter
    if sim["rdf_count"] > 0:
        bins = sim["rdf_bins"]
        max_val = max(bins) if bins else 0
        avg_val = sum(bins) / len(bins) if bins else 1
        order = max_val / max(avg_val, 1e-10)
    else:
        order = 1.0

    if t < 0.4 and order > 5.0:
        return "SOLID", curses.color_pair(4)   # blue
    elif t < 1.2:
        return "LIQUID", curses.color_pair(6)  # cyan
    else:
        return "GAS", curses.color_pair(1)     # red


# ── Mode integration ─────────────────────────────────────────────────────

def _enter_moldyn_mode(self):
    """Enter Molecular Dynamics mode — show preset menu."""
    self.moldyn_mode = True
    self.moldyn_menu = True
    self.moldyn_menu_sel = 0
    self.moldyn_sim = None
    self.moldyn_running = False
    self.moldyn_view = 0  # 0=particles, 1=energy, 2=rdf


def _exit_moldyn_mode(self):
    """Exit Molecular Dynamics mode."""
    self.moldyn_mode = False
    self.moldyn_menu = False
    self.moldyn_sim = None


def _moldyn_init(self, preset_idx):
    """Initialize simulation from selected preset."""
    _, _, settings = MOLDYN_PRESETS[preset_idx]
    self.moldyn_sim = _init_sim(settings)
    self.moldyn_menu = False
    self.moldyn_running = True
    self.moldyn_preset_name = MOLDYN_PRESETS[preset_idx][0]


def _moldyn_step(self):
    """Advance simulation by configured number of sub-steps."""
    if not self.moldyn_sim or not self.moldyn_running:
        return
    for _ in range(self.moldyn_sim["speed"]):
        _step(self.moldyn_sim)


def _handle_moldyn_menu_key(self, key):
    """Handle keys on the preset selection menu."""
    n = len(MOLDYN_PRESETS)
    if key == curses.KEY_UP or key == ord('k'):
        self.moldyn_menu_sel = (self.moldyn_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN or key == ord('j'):
        self.moldyn_menu_sel = (self.moldyn_menu_sel + 1) % n
        return True
    if key in (curses.KEY_ENTER, 10, 13, ord('\n')):
        _moldyn_init(self, self.moldyn_menu_sel)
        return True
    if key == ord('q') or key == 27:
        _exit_moldyn_mode(self)
        self.mode_browser = True
        return True
    return True


def _handle_moldyn_key(self, key):
    """Handle keys during simulation."""
    if key == ord('q') or key == 27:
        _exit_moldyn_mode(self)
        self.mode_browser = True
        return True
    if key == ord(' '):
        self.moldyn_running = not self.moldyn_running
        return True
    if key == ord('n'):
        if not self.moldyn_running:
            _step(self.moldyn_sim)
        return True
    if key == ord('+') or key == ord('='):
        self.moldyn_sim["speed"] = min(self.moldyn_sim["speed"] + 1, 30)
        return True
    if key == ord('-'):
        self.moldyn_sim["speed"] = max(self.moldyn_sim["speed"] - 1, 1)
        return True
    if key == ord('v'):
        self.moldyn_view = (self.moldyn_view + 1) % 3
        return True
    if key == ord('t') or key == ord('T'):
        # Toggle thermostat
        self.moldyn_sim["thermostat"] = not self.moldyn_sim["thermostat"]
        self._flash("Thermostat " + ("ON" if self.moldyn_sim["thermostat"] else "OFF"))
        return True
    if key == curses.KEY_UP:
        # Raise target temperature
        self.moldyn_sim["target_temp"] = min(
            self.moldyn_sim["target_temp"] + 0.05, 10.0)
        self._flash(f"T_target = {self.moldyn_sim['target_temp']:.2f}")
        return True
    if key == curses.KEY_DOWN:
        # Lower target temperature
        self.moldyn_sim["target_temp"] = max(
            self.moldyn_sim["target_temp"] - 0.05, 0.01)
        self._flash(f"T_target = {self.moldyn_sim['target_temp']:.2f}")
        return True
    if key == ord('r'):
        # Reset with current preset
        _moldyn_init(self, self.moldyn_menu_sel)
        return True
    if key == ord('R'):
        # Back to menu
        self.moldyn_menu = True
        self.moldyn_running = False
        return True
    return True


# ── Drawing ──────────────────────────────────────────────────────────────

def _draw_moldyn_menu(self, max_y, max_x):
    """Draw the preset selection menu."""
    title = "╔══ MOLECULAR DYNAMICS: PHASE TRANSITIONS ══╗"
    subtitle = "Lennard-Jones particles · solid ↔ liquid ↔ gas"
    try:
        cy = max(1, max_y // 2 - len(MOLDYN_PRESETS) - 3)
        cx = max(0, (max_x - len(title)) // 2)
        self.stdscr.addstr(cy, cx, title, curses.A_BOLD | curses.color_pair(6))
        self.stdscr.addstr(cy + 1, max(0, (max_x - len(subtitle)) // 2),
                           subtitle, curses.color_pair(7))

        y = cy + 3
        for i, (name, desc, _) in enumerate(MOLDYN_PRESETS):
            if y >= max_y - 2:
                break
            marker = "▸ " if i == self.moldyn_menu_sel else "  "
            attr = curses.A_BOLD | curses.color_pair(3) if i == self.moldyn_menu_sel else curses.color_pair(7)
            line = f"{marker}{name}"
            self.stdscr.addstr(y, cx + 2, line[:max_x - cx - 4], attr)
            if y + 1 < max_y - 2:
                self.stdscr.addstr(y + 1, cx + 4, desc[:max_x - cx - 6],
                                   curses.A_DIM | curses.color_pair(7))
            y += 3

        # Footer
        hint = "↑/↓ select · Enter start · q/Esc back"
        if y + 2 < max_y:
            self.stdscr.addstr(y + 1, max(0, (max_x - len(hint)) // 2),
                               hint, curses.A_DIM | curses.color_pair(7))
    except curses.error:
        pass


def _draw_moldyn(self, max_y, max_x):
    """Draw the active molecular dynamics simulation."""
    sim = self.moldyn_sim
    if not sim:
        return

    n = sim["n"]
    box_l = sim["box_l"]
    x_arr, y_arr = sim["x"], sim["y"]
    vx_arr, vy_arr = sim["vx"], sim["vy"]

    # Layout: particle view on left, stats on right
    stats_w = 32
    view_w = max(10, max_x - stats_w - 2)
    view_h = max(5, max_y - 3)

    # ── Title bar ──
    phase_name, phase_color = _classify_phase(sim)
    title = f" Molecular Dynamics — {self.moldyn_preset_name} "
    try:
        self.stdscr.addstr(0, 0, title[:max_x], curses.A_BOLD | curses.color_pair(6))
        phase_str = f" [{phase_name}] "
        px = min(len(title), max_x - len(phase_str) - 1)
        if px > 0:
            self.stdscr.addstr(0, px, phase_str, curses.A_BOLD | phase_color)
    except curses.error:
        pass

    if self.moldyn_view == 0:
        _draw_particles(self, sim, 1, 0, view_h, view_w)
    elif self.moldyn_view == 1:
        _draw_energy_plot(self, sim, 1, 0, view_h, view_w)
    else:
        _draw_rdf(self, sim, 1, 0, view_h, view_w)

    # ── Stats panel ──
    _draw_stats_panel(self, sim, 1, view_w + 1, view_h, stats_w, phase_name, phase_color)

    # ── Footer ──
    paused = " PAUSED" if not self.moldyn_running else ""
    thermo = "ON" if sim["thermostat"] else "OFF"
    hint = f" ↑↓ temp · space pause · v view · t thermostat({thermo}) · +/- speed · r reset · q quit{paused}"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                           curses.A_DIM | curses.color_pair(7))
    except curses.error:
        pass


def _draw_particles(self, sim, top, left, height, width):
    """Render particles in the simulation box as ASCII."""
    n = sim["n"]
    box_l = sim["box_l"]
    x_arr, y_arr = sim["x"], sim["y"]
    vx_arr, vy_arr = sim["vx"], sim["vy"]

    # Scale box to terminal area
    sx = (width - 1) / box_l if box_l > 0 else 1
    sy = (height - 1) / box_l if box_l > 0 else 1

    # Build character grid
    grid = {}
    for i in range(n):
        col = int(x_arr[i] * sx)
        row = int(y_arr[i] * sy)
        col = max(0, min(col, width - 1))
        row = max(0, min(row, height - 1))

        # Kinetic energy of this particle
        ke_i = 0.5 * (vx_arr[i] ** 2 + vy_arr[i] ** 2)
        # Map to character
        if ke_i < 0.1:
            ci = 0
        elif ke_i < 0.3:
            ci = 1
        elif ke_i < 0.8:
            ci = 2
        elif ke_i < 1.5:
            ci = 3
        elif ke_i < 3.0:
            ci = 4
        else:
            ci = 5

        key = (row, col)
        if key not in grid or ci > grid[key][0]:
            grid[key] = (ci, i)

    # Draw particles
    for (row, col), (ci, _idx) in grid.items():
        ch = KE_CHARS[ci]
        # Color by kinetic energy: blue(cold) → cyan → green → yellow → red(hot)
        if ci <= 1:
            cp = curses.color_pair(4)  # blue
        elif ci == 2:
            cp = curses.color_pair(6)  # cyan
        elif ci == 3:
            cp = curses.color_pair(2)  # green
        elif ci == 4:
            cp = curses.color_pair(3)  # yellow
        else:
            cp = curses.color_pair(1)  # red
        try:
            self.stdscr.addstr(top + row, left + col, ch, cp)
        except curses.error:
            pass

    # Draw box border hint (corners)
    try:
        self.stdscr.addstr(top, left, "┌", curses.A_DIM | curses.color_pair(7))
        self.stdscr.addstr(top, left + width - 1, "┐",
                           curses.A_DIM | curses.color_pair(7))
        self.stdscr.addstr(top + height - 1, left, "└",
                           curses.A_DIM | curses.color_pair(7))
        if left + width - 1 < self.stdscr.getmaxyx()[1] - 1:
            self.stdscr.addstr(top + height - 1, left + width - 1, "┘",
                               curses.A_DIM | curses.color_pair(7))
    except curses.error:
        pass


def _draw_energy_plot(self, sim, top, left, height, width):
    """Draw kinetic/potential energy and temperature time series."""
    ke_hist = sim["ke_history"]
    pe_hist = sim["pe_history"]
    temp_hist = sim["temp_history"]

    plot_h = max(3, height - 4)
    plot_w = max(10, width - 2)

    try:
        self.stdscr.addstr(top, left + 1, "Energy & Temperature",
                           curses.A_BOLD | curses.color_pair(7))
    except curses.error:
        pass

    if not ke_hist:
        return

    # Plot temperature on the main graph
    data = temp_hist[-plot_w:]
    if not data:
        return
    mn = min(data)
    mx = max(data)
    rng = mx - mn if mx > mn else 1.0

    for ci, val in enumerate(data):
        if ci >= plot_w:
            break
        bar_h = int((val - mn) / rng * (plot_h - 1))
        bar_h = max(0, min(bar_h, plot_h - 1))
        row = top + 2 + (plot_h - 1 - bar_h)
        try:
            self.stdscr.addstr(row, left + 1 + ci, "█",
                               curses.color_pair(1))
        except curses.error:
            pass

    # Overlay KE
    ke_data = ke_hist[-plot_w:]
    if ke_data:
        ke_mn = min(ke_data)
        ke_mx = max(ke_data)
        ke_rng = ke_mx - ke_mn if ke_mx > ke_mn else 1.0
        for ci, val in enumerate(ke_data):
            if ci >= plot_w:
                break
            bar_h = int((val - ke_mn) / ke_rng * (plot_h - 1))
            bar_h = max(0, min(bar_h, plot_h - 1))
            row = top + 2 + (plot_h - 1 - bar_h)
            try:
                self.stdscr.addstr(row, left + 1 + ci, "▪",
                                   curses.color_pair(6))
            except curses.error:
                pass

    # Legend
    ly = top + plot_h + 3
    try:
        self.stdscr.addstr(ly, left + 1, "█ Temperature  ",
                           curses.color_pair(1))
        self.stdscr.addstr(ly, left + 17, "▪ KE/particle",
                           curses.color_pair(6))
    except curses.error:
        pass


def _draw_rdf(self, sim, top, left, height, width):
    """Draw radial distribution function g(r)."""
    bins = sim["rdf_bins"]
    n_bins = len(bins)
    count = max(1, sim["rdf_count"])
    n = sim["n"]
    box_l = sim["box_l"]

    plot_h = max(3, height - 4)
    plot_w = max(10, width - 2)

    try:
        self.stdscr.addstr(top, left + 1, "Radial Distribution Function g(r)",
                           curses.A_BOLD | curses.color_pair(7))
    except curses.error:
        pass

    if count < 1 or n < 2:
        return

    # Normalize bins to g(r)
    max_r = min(box_l / 2.0, 4.0 * SIGMA)
    dr = max_r / n_bins
    density_val = n / (box_l * box_l)
    g = []
    for b in range(n_bins):
        r = (b + 0.5) * dr
        shell_area = 2 * math.pi * r * dr
        ideal = density_val * shell_area * n * count / 2.0
        g_val = bins[b] / ideal if ideal > 0 else 0
        g.append(g_val)

    # Plot
    max_g = max(g) if g else 1.0
    if max_g < 1e-10:
        max_g = 1.0

    bins_per_col = max(1, n_bins // plot_w)
    for ci in range(min(plot_w, n_bins)):
        b_start = ci * bins_per_col
        b_end = min(b_start + bins_per_col, n_bins)
        val = sum(g[b_start:b_end]) / max(1, b_end - b_start)

        bar_h = int(val / max_g * (plot_h - 1))
        bar_h = max(0, min(bar_h, plot_h - 1))
        for ri in range(bar_h + 1):
            row = top + 2 + (plot_h - 1 - ri)
            # Color: first peak blue, rest cyan
            cp = curses.color_pair(4) if ci < plot_w // 4 else curses.color_pair(6)
            try:
                self.stdscr.addstr(row, left + 1 + ci, "▮", cp)
            except curses.error:
                pass

    # Axis labels
    try:
        self.stdscr.addstr(top + plot_h + 2, left + 1, "r/σ →",
                           curses.A_DIM | curses.color_pair(7))
        self.stdscr.addstr(top + plot_h + 3, left + 1,
                           f"0{' ' * max(0, plot_w - 6)}{max_r:.1f}",
                           curses.A_DIM | curses.color_pair(7))
    except curses.error:
        pass


def _draw_stats_panel(self, sim, top, left, height, width, phase_name, phase_color):
    """Draw statistics panel on the right side."""
    n = sim["n"]
    y = top
    w = width

    def put(row, text, attr=curses.color_pair(7)):
        try:
            self.stdscr.addstr(row, left, text[:w], attr)
        except curses.error:
            pass

    put(y, "─── Statistics ───", curses.A_BOLD | curses.color_pair(3))
    y += 1
    put(y, f" Step:       {sim['step']:>8d}")
    y += 1
    put(y, f" Particles:  {n:>8d}")
    y += 1
    put(y, f" T_target:   {sim['target_temp']:>8.3f}")
    y += 1
    put(y, f" T_actual:   {sim['temp']:>8.3f}",
        curses.color_pair(1) if sim['temp'] > sim['target_temp'] * 1.5
        else curses.color_pair(4) if sim['temp'] < sim['target_temp'] * 0.5
        else curses.color_pair(7))
    y += 1
    put(y, f" KE/N:       {sim['ke'] / max(1, n):>8.3f}")
    y += 1
    put(y, f" PE/N:       {sim['pe'] / max(1, n):>8.3f}")
    y += 1
    total_e = (sim['ke'] + sim['pe']) / max(1, n)
    put(y, f" E_total/N:  {total_e:>8.3f}")
    y += 1
    put(y, f" Pressure:   {sim['pressure']:>8.3f}")
    y += 1
    put(y, f" Speed:      {sim['speed']:>8d}x")
    y += 1
    thermo = "ON" if sim["thermostat"] else "OFF"
    put(y, f" Thermostat: {thermo:>8s}")
    y += 2
    put(y, f" Phase: {phase_name}", curses.A_BOLD | phase_color)
    y += 2

    # Phase diagram hint
    put(y, "─── Phase Guide ───", curses.A_BOLD | curses.color_pair(3))
    y += 1
    put(y, " T < 0.4  → SOLID", curses.color_pair(4))
    y += 1
    put(y, " 0.4-1.2  → LIQUID", curses.color_pair(6))
    y += 1
    put(y, " T > 1.2  → GAS", curses.color_pair(1))
    y += 2

    # KE distribution indicator (particle speed histogram)
    if y + 6 < top + height:
        put(y, "─── Speed Dist ───", curses.A_BOLD | curses.color_pair(3))
        y += 1
        vx_arr, vy_arr = sim["vx"], sim["vy"]
        speeds = [math.sqrt(vx_arr[i] ** 2 + vy_arr[i] ** 2)
                  for i in range(n)]
        if speeds:
            max_speed = max(speeds) if speeds else 1.0
            if max_speed < 1e-10:
                max_speed = 1.0
            # 5-bin histogram
            n_hbins = min(5, w - 2)
            hbins = [0] * n_hbins
            for s in speeds:
                b = int(s / max_speed * n_hbins)
                b = min(b, n_hbins - 1)
                hbins[b] += 1
            max_h = max(hbins) if hbins else 1
            bar_chars = " ▁▂▃▄▅▆▇█"
            bar_str = ""
            for hb in hbins:
                idx = int(hb / max(max_h, 1) * (len(bar_chars) - 1))
                bar_str += bar_chars[idx] * 3
            put(y, f" {bar_str}", curses.color_pair(6))
            y += 1
            put(y, f" 0{' ' * max(0, n_hbins * 3 - 4)}{max_speed:.1f}",
                curses.A_DIM | curses.color_pair(7))

    # View indicator
    views = ["Particles", "Energy Plot", "RDF g(r)"]
    vy = top + height - 1
    put(vy, f" View: {views[self.moldyn_view]} (v)",
        curses.A_DIM | curses.color_pair(7))


# ── Registration ─────────────────────────────────────────────────────────

def register(App):
    """Register Molecular Dynamics mode methods on the App class."""
    App._enter_moldyn_mode = _enter_moldyn_mode
    App._exit_moldyn_mode = _exit_moldyn_mode
    App._moldyn_init = _moldyn_init
    App._moldyn_step = _moldyn_step
    App._handle_moldyn_menu_key = _handle_moldyn_menu_key
    App._handle_moldyn_key = _handle_moldyn_key
    App._draw_moldyn_menu = _draw_moldyn_menu
    App._draw_moldyn = _draw_moldyn
    App.MOLDYN_PRESETS = MOLDYN_PRESETS
