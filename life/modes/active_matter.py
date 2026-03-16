"""Mode: active_matter — self-propelled particle system exhibiting MIPS,
active turbulence, and collective flocking transitions."""
import curses
import math
import random
import time

from life.constants import SPEEDS

# ── Presets ──────────────────────────────────────────────────────────────
ACTIVE_MATTER_PRESETS = [
    ("Bacterial Turbulence",
     "Dense pushers with nematic alignment → chaotic vortex streets",
     "bacterial_turbulence"),
    ("Active Nematics",
     "Rod-like extensile particles with ±½ defect nucleation",
     "active_nematics"),
    ("Motility-Induced Clustering",
     "Run-and-tumble particles phase-separate into dense liquid drops",
     "mips"),
    ("Vicsek Flocking",
     "Polar aligning point particles → long-range ordered flock",
     "vicsek"),
    ("Active Spinner Gas",
     "Self-rotating disks with odd-elastic collisions",
     "spinners"),
    ("Contractile Gel",
     "Puller particles that form asters and contractile networks",
     "contractile"),
]

# ── Glyphs & colors ─────────────────────────────────────────────────────
_DIR_ARROWS = ["→→", "↗↗", "↑↑", "↖↖", "←←", "↙↙", "↓↓", "↘↘"]
_DENSITY_CHARS = ["  ", "· ", "░░", "▒▒", "▓▓", "██"]
_TYPE_CHARS = ["●", "◆", "■", "▲", "★", "◉"]
_TYPE_COLORS = [1, 2, 3, 4, 5, 6]


def _angle_to_arrow(theta):
    """Map angle θ ∈ [0, 2π) to one of 8 directional arrows."""
    idx = int((theta / (2 * math.pi) * 8 + 0.5)) % 8
    return _DIR_ARROWS[idx]


def _speed_color(spd, v0):
    """Map speed to color pair index."""
    ratio = spd / max(v0, 0.01)
    if ratio < 0.3:
        return 4  # slow = blue
    elif ratio < 0.8:
        return 6  # medium = cyan
    elif ratio < 1.5:
        return 2  # normal = green
    else:
        return 1  # fast = red


def _density_char(count):
    """Map local density count to a density glyph."""
    idx = min(count, len(_DENSITY_CHARS) - 1)
    return _DENSITY_CHARS[idx]


def _density_color(count):
    """Map local density to color pair."""
    if count == 0:
        return 6
    elif count <= 1:
        return 4
    elif count <= 3:
        return 2
    elif count <= 6:
        return 3
    else:
        return 1


# ── Lifecycle ────────────────────────────────────────────────────────────
def _enter_active_matter_mode(self):
    """Enter Active Matter mode — show preset menu."""
    self.active_matter_menu = True
    self.active_matter_menu_sel = 0
    self._flash("Active Matter — select a configuration")


def _exit_active_matter_mode(self):
    """Exit Active Matter mode."""
    self.active_matter_mode = False
    self.active_matter_menu = False
    self.active_matter_running = False
    self.active_matter_particles = []
    self._flash("Active Matter mode OFF")


def _active_matter_init(self, preset_idx: int):
    """Initialize Active Matter simulation with the given preset."""
    name, _desc, kind = self.ACTIVE_MATTER_PRESETS[preset_idx]
    self.active_matter_preset_name = name
    self.active_matter_kind = kind
    self.active_matter_generation = 0
    self.active_matter_running = False
    self.active_matter_view = 0  # 0=arrows, 1=density, 2=vorticity

    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(10, max_y - 4)
    cols = max(10, (max_x - 1) // 2)
    self.active_matter_rows = rows
    self.active_matter_cols = cols

    rng = random.Random()

    # Default parameters
    v0 = 0.5        # self-propulsion speed
    noise = 0.3     # angular noise strength (η)
    align_r = 3.0   # alignment interaction radius
    align_w = 1.0   # alignment strength
    repel_r = 1.5   # repulsion radius
    repel_w = 0.5   # repulsion strength
    density = 0.08  # particle density (fraction of cells)
    friction = 0.02 # velocity damping
    tumble = 0.0    # tumble rate (for run-and-tumble)
    nematic = False  # nematic (±π) vs polar (2π) alignment
    spin_w = 0.0    # self-rotation angular velocity
    contract = 0.0  # contractile/extensile dipole strength

    if kind == "bacterial_turbulence":
        v0 = 0.8
        noise = 0.15
        align_r = 4.0
        align_w = 0.8
        repel_r = 1.2
        repel_w = 1.0
        density = 0.20
        friction = 0.03
        nematic = True
        contract = -0.3  # extensile (pushers)
    elif kind == "active_nematics":
        v0 = 0.4
        noise = 0.1
        align_r = 5.0
        align_w = 1.5
        repel_r = 1.5
        repel_w = 0.8
        density = 0.15
        friction = 0.05
        nematic = True
        contract = -0.5
    elif kind == "mips":
        v0 = 1.0
        noise = 0.05
        align_r = 0.0    # no alignment — pure MIPS
        align_w = 0.0
        repel_r = 1.2
        repel_w = 1.5
        density = 0.25
        friction = 0.0
        tumble = 0.05     # run-and-tumble
    elif kind == "vicsek":
        v0 = 0.6
        noise = 0.3
        align_r = 4.0
        align_w = 1.0
        repel_r = 1.0
        repel_w = 0.3
        density = 0.10
        friction = 0.0
    elif kind == "spinners":
        v0 = 0.3
        noise = 0.2
        align_r = 3.0
        align_w = 0.5
        repel_r = 2.0
        repel_w = 1.0
        density = 0.12
        friction = 0.02
        spin_w = 0.3
    elif kind == "contractile":
        v0 = 0.4
        noise = 0.15
        align_r = 4.0
        align_w = 1.0
        repel_r = 1.5
        repel_w = 0.6
        density = 0.15
        friction = 0.04
        contract = 0.5  # puller/contractile

    self.active_matter_v0 = v0
    self.active_matter_noise = noise
    self.active_matter_align_r = align_r
    self.active_matter_align_w = align_w
    self.active_matter_repel_r = repel_r
    self.active_matter_repel_w = repel_w
    self.active_matter_friction = friction
    self.active_matter_tumble = tumble
    self.active_matter_nematic = nematic
    self.active_matter_spin_w = spin_w
    self.active_matter_contract = contract
    self.active_matter_steps_per_frame = 1

    # Create particles: [r, c, θ, vr, vc, fuel]
    n_particles = max(30, int(rows * cols * density))
    self.active_matter_num_particles = n_particles
    particles = []
    for _ in range(n_particles):
        pr = rng.random() * rows
        pc = rng.random() * cols
        theta = rng.random() * 2 * math.pi
        vr = v0 * math.sin(theta)
        vc = v0 * math.cos(theta)
        fuel = 1.0
        particles.append([pr, pc, theta, vr, vc, fuel])
    self.active_matter_particles = particles

    self.active_matter_menu = False
    self.active_matter_mode = True
    self._flash(f"Active Matter: {name} — Space to start")


# ── Simulation step ─────────────────────────────────────────────────────
def _active_matter_step(self):
    """Advance Active Matter simulation by one timestep."""
    particles = self.active_matter_particles
    n = len(particles)
    rows = self.active_matter_rows
    cols = self.active_matter_cols
    v0 = self.active_matter_v0
    noise = self.active_matter_noise
    align_r = self.active_matter_align_r
    align_w = self.active_matter_align_w
    repel_r = self.active_matter_repel_r
    repel_w = self.active_matter_repel_w
    friction = self.active_matter_friction
    tumble = self.active_matter_tumble
    nematic = self.active_matter_nematic
    spin_w = self.active_matter_spin_w
    contract = self.active_matter_contract
    half_rows = rows / 2.0
    half_cols = cols / 2.0
    max_r = max(align_r, repel_r)
    max_r2 = max_r * max_r

    # Build spatial grid for neighbor lookup
    cell_size = max(max_r, 1.0)
    grid_h = max(1, int(rows / cell_size) + 1)
    grid_w = max(1, int(cols / cell_size) + 1)
    cells: dict[tuple[int, int], list[int]] = {}
    for i in range(n):
        gr = int(particles[i][0] / cell_size) % grid_h
        gc = int(particles[i][1] / cell_size) % grid_w
        key = (gr, gc)
        if key not in cells:
            cells[key] = []
        cells[key].append(i)

    new_particles = []
    for i in range(n):
        pr, pc, theta, pvr, pvc, fuel = particles[i]

        # Gather neighbors via spatial grid
        gr = int(pr / cell_size) % grid_h
        gc = int(pc / cell_size) % grid_w

        # Sum for alignment
        sin_sum = 0.0
        cos_sum = 0.0
        n_align = 0
        # Sum for repulsion force
        fr, fc = 0.0, 0.0
        # Sum for contractile/extensile dipole
        dip_r, dip_c = 0.0, 0.0

        for dgr in (-1, 0, 1):
            for dgc in (-1, 0, 1):
                nkey = ((gr + dgr) % grid_h, (gc + dgc) % grid_w)
                bucket = cells.get(nkey)
                if bucket is None:
                    continue
                for j in bucket:
                    if i == j:
                        continue
                    qr, qc = particles[j][0], particles[j][1]
                    dr = qr - pr
                    dc = qc - pc
                    if dr > half_rows:
                        dr -= rows
                    elif dr < -half_rows:
                        dr += rows
                    if dc > half_cols:
                        dc -= cols
                    elif dc < -half_cols:
                        dc += cols

                    dist2 = dr * dr + dc * dc
                    if dist2 > max_r2 or dist2 < 0.001:
                        continue
                    dist = math.sqrt(dist2)

                    # Alignment interaction
                    if dist < align_r and align_w > 0:
                        qt = particles[j][2]
                        if nematic:
                            # Nematic: align to ±π (double angle trick)
                            sin_sum += math.sin(2 * qt)
                            cos_sum += math.cos(2 * qt)
                        else:
                            sin_sum += math.sin(qt)
                            cos_sum += math.cos(qt)
                        n_align += 1

                    # Short-range repulsion
                    if dist < repel_r:
                        ndr = dr / dist
                        ndc = dc / dist
                        overlap = 1.0 - dist / repel_r
                        fr -= ndr * overlap * repel_w
                        fc -= ndc * overlap * repel_w

                    # Contractile/extensile dipole force
                    if abs(contract) > 0.001 and dist < align_r:
                        ndr = dr / dist
                        ndc = dc / dist
                        # Project self-propulsion direction onto pair axis
                        ei_r = math.sin(theta)
                        ei_c = math.cos(theta)
                        dot = ei_r * ndr + ei_c * ndc
                        # Contractile (>0) pulls along axis, extensile (<0) pushes
                        strength = contract * dot / (dist + 0.5)
                        dip_r += ndr * strength
                        dip_c += ndc * strength

        # Compute new heading
        new_theta = theta

        # Alignment torque
        if n_align > 0 and align_w > 0:
            if nematic:
                target_2t = math.atan2(sin_sum, cos_sum)
                target_t = target_2t / 2.0
                # Pick closest nematic direction
                diff = target_t - theta
                diff = (diff + math.pi) % (2 * math.pi) - math.pi
                if abs(diff) > math.pi / 2:
                    target_t += math.pi
                diff = target_t - theta
                diff = (diff + math.pi) % (2 * math.pi) - math.pi
                new_theta += align_w * diff * 0.3
            else:
                target = math.atan2(sin_sum, cos_sum)
                diff = target - theta
                diff = (diff + math.pi) % (2 * math.pi) - math.pi
                new_theta += align_w * diff * 0.3

        # Self-rotation (spinners)
        new_theta += spin_w

        # Run-and-tumble
        if tumble > 0 and random.random() < tumble:
            new_theta = random.random() * 2 * math.pi

        # Angular noise
        new_theta += random.gauss(0, noise)
        new_theta = new_theta % (2 * math.pi)

        # Fuel-dependent self-propulsion
        prop_speed = v0 * fuel

        # MIPS: speed decreases with local density
        if tumble > 0 and n_align > 0:
            # Quorum sensing: slow down in crowds
            local_density = n_align / max(1.0, math.pi * align_r * align_r) if align_r > 0 else n_align / 10.0
            prop_speed = v0 / (1.0 + 5.0 * local_density)

        # Self-propulsion velocity
        sp_r = prop_speed * math.sin(new_theta)
        sp_c = prop_speed * math.cos(new_theta)

        # Total velocity = propulsion + interaction forces
        nvr = sp_r + fr + dip_r
        nvc = sp_c + fc + dip_c

        # Add some of old velocity (inertia) with friction damping
        nvr = nvr * (1.0 - friction) + pvr * friction * 0.5
        nvc = nvc * (1.0 - friction) + pvc * friction * 0.5

        # Clamp velocity
        spd = math.sqrt(nvr * nvr + nvc * nvc)
        max_spd = v0 * 3.0
        if spd > max_spd:
            nvr = nvr / spd * max_spd
            nvc = nvc / spd * max_spd

        # Update position (toroidal)
        nr = (pr + nvr) % rows
        nc = (pc + nvc) % cols

        # Fuel slowly regenerates
        new_fuel = min(1.0, fuel + 0.002)

        new_particles.append([nr, nc, new_theta, nvr, nvc, new_fuel])

    self.active_matter_particles = new_particles
    self.active_matter_generation += 1


# ── Input handling ───────────────────────────────────────────────────────
def _handle_active_matter_menu_key(self, key: int) -> bool:
    """Handle input in Active Matter preset menu."""
    n = len(self.ACTIVE_MATTER_PRESETS)
    if key in (ord("j"), curses.KEY_DOWN):
        self.active_matter_menu_sel = (self.active_matter_menu_sel + 1) % n
    elif key in (ord("k"), curses.KEY_UP):
        self.active_matter_menu_sel = (self.active_matter_menu_sel - 1) % n
    elif key in (ord("\n"), ord("\r")):
        self._active_matter_init(self.active_matter_menu_sel)
    elif key in (ord("q"), 27):
        self.active_matter_menu = False
        self._flash("Active Matter cancelled")
    return True


def _handle_active_matter_key(self, key: int) -> bool:
    """Handle input in active Active Matter simulation."""
    if key == ord(" "):
        self.active_matter_running = not self.active_matter_running
    elif key in (ord("n"), ord(".")):
        for _ in range(self.active_matter_steps_per_frame):
            self._active_matter_step()
    elif key == ord("r"):
        idx = next((i for i, p in enumerate(self.ACTIVE_MATTER_PRESETS)
                    if p[0] == self.active_matter_preset_name), 0)
        self._active_matter_init(idx)
        self.active_matter_running = False
    elif key in (ord("R"), ord("m")):
        self.active_matter_mode = False
        self.active_matter_running = False
        self.active_matter_menu = True
        self.active_matter_menu_sel = 0
    elif key == ord("v"):
        self.active_matter_view = (self.active_matter_view + 1) % 3
        labels = ["Arrows", "Density", "Vorticity"]
        self._flash(f"View: {labels[self.active_matter_view]}")
    elif key == ord("s") or key == ord("S"):
        delta = 0.05 if key == ord("s") else -0.05
        self.active_matter_v0 = max(0.1, min(2.0, self.active_matter_v0 + delta))
        self._flash(f"Speed v₀: {self.active_matter_v0:.2f}")
    elif key == ord("e") or key == ord("E"):
        delta = 0.02 if key == ord("e") else -0.02
        self.active_matter_noise = max(0.0, min(1.0, self.active_matter_noise + delta))
        self._flash(f"Noise η: {self.active_matter_noise:.2f}")
    elif key == ord("a") or key == ord("A"):
        delta = 0.1 if key == ord("a") else -0.1
        self.active_matter_align_w = max(0.0, min(3.0, self.active_matter_align_w + delta))
        self._flash(f"Alignment: {self.active_matter_align_w:.1f}")
    elif key == ord("p") or key == ord("P"):
        delta = 0.1 if key == ord("p") else -0.1
        self.active_matter_repel_w = max(0.0, min(3.0, self.active_matter_repel_w + delta))
        self._flash(f"Repulsion: {self.active_matter_repel_w:.1f}")
    elif key == ord("t") or key == ord("T"):
        delta = 0.01 if key == ord("t") else -0.01
        self.active_matter_tumble = max(0.0, min(0.5, self.active_matter_tumble + delta))
        self._flash(f"Tumble rate: {self.active_matter_tumble:.2f}")
    elif key == ord("+") or key == ord("="):
        self.active_matter_steps_per_frame = min(10, self.active_matter_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.active_matter_steps_per_frame}")
    elif key == ord("-"):
        self.active_matter_steps_per_frame = max(1, self.active_matter_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.active_matter_steps_per_frame}")
    elif key == ord("<") or key == ord(","):
        self.speed_idx = max(0, self.speed_idx - 1)
    elif key == ord(">") or key == ord("."):
        self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)
    elif key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            # Drop a cluster of particles at click location
            r_click = my - 1
            c_click = mx // 2
            if 0 <= r_click < self.active_matter_rows and 0 <= c_click < self.active_matter_cols:
                for _ in range(15):
                    pr = (r_click + random.gauss(0, 1.5)) % self.active_matter_rows
                    pc = (c_click + random.gauss(0, 1.5)) % self.active_matter_cols
                    theta = random.random() * 2 * math.pi
                    vr = self.active_matter_v0 * math.sin(theta)
                    vc = self.active_matter_v0 * math.cos(theta)
                    self.active_matter_particles.append([pr, pc, theta, vr, vc, 1.0])
                self.active_matter_num_particles = len(self.active_matter_particles)
                self._flash(f"+15 particles (total: {self.active_matter_num_particles})")
        except curses.error:
            pass
    elif key in (ord("q"), 27):
        self._exit_active_matter_mode()
    else:
        return True
    return True


# ── Drawing ──────────────────────────────────────────────────────────────
def _draw_active_matter_menu(self, max_y: int, max_x: int):
    """Draw the Active Matter preset selection menu."""
    self.stdscr.erase()
    title = "── Active Matter ── Select Configuration ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _kind) in enumerate(self.ACTIVE_MATTER_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        line = f"  {name:<28s}  {desc}"
        attr = curses.color_pair(6)
        if i == self.active_matter_menu_sel:
            attr = curses.color_pair(7) | curses.A_REVERSE
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
        except curses.error:
            pass

    hint = " [j/k]=navigate  [Enter]=select  [q]=cancel"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


def _draw_active_matter(self, max_y: int, max_x: int):
    """Draw the active Active Matter simulation."""
    self.stdscr.erase()
    particles = self.active_matter_particles
    rows = self.active_matter_rows
    cols = self.active_matter_cols
    v0 = self.active_matter_v0
    view = self.active_matter_view
    state = "▶ RUNNING" if self.active_matter_running else "⏸ PAUSED"

    # Title bar
    title = (f" Active Matter: {self.active_matter_preset_name}  |  gen {self.active_matter_generation}"
             f"  |  N={self.active_matter_num_particles}"
             f"  v₀={v0:.2f}  η={self.active_matter_noise:.2f}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 4)
    view_cols = min(cols, (max_x - 1) // 2)

    if view == 0:
        # Arrow view — show each particle as a directional arrow
        grid: dict[tuple[int, int], int] = {}
        for idx, p in enumerate(particles):
            ri = int(p[0]) % rows
            ci = int(p[1]) % cols
            if ri < view_rows and ci < view_cols:
                grid[(ri, ci)] = idx

        for (ri, ci), idx in grid.items():
            p = particles[idx]
            ch = _angle_to_arrow(p[2])
            spd = math.sqrt(p[3] * p[3] + p[4] * p[4])
            cp = _speed_color(spd, v0)
            bold = curses.A_BOLD if spd > v0 else (curses.A_DIM if spd < v0 * 0.3 else 0)
            try:
                self.stdscr.addstr(1 + ri, ci * 2, ch, curses.color_pair(cp) | bold)
            except curses.error:
                pass

    elif view == 1:
        # Density view — coarse-grained density field
        density_grid = [[0] * view_cols for _ in range(view_rows)]
        for p in particles:
            ri = int(p[0]) % rows
            ci = int(p[1]) % cols
            if ri < view_rows and ci < view_cols:
                density_grid[ri][ci] += 1

        for r in range(view_rows):
            for c in range(view_cols):
                cnt = density_grid[r][c]
                if cnt == 0:
                    continue
                ch = _density_char(cnt)
                cp = _density_color(cnt)
                try:
                    self.stdscr.addstr(1 + r, c * 2, ch, curses.color_pair(cp))
                except curses.error:
                    pass

    else:
        # Vorticity view — local curl of velocity field
        # Build velocity field
        vr_field = [[0.0] * view_cols for _ in range(view_rows)]
        vc_field = [[0.0] * view_cols for _ in range(view_rows)]
        count_field = [[0] * view_cols for _ in range(view_rows)]
        for p in particles:
            ri = int(p[0]) % rows
            ci = int(p[1]) % cols
            if ri < view_rows and ci < view_cols:
                vr_field[ri][ci] += p[3]
                vc_field[ri][ci] += p[4]
                count_field[ri][ci] += 1

        for r in range(view_rows):
            for c in range(view_cols):
                if count_field[r][c] > 0:
                    vr_field[r][c] /= count_field[r][c]
                    vc_field[r][c] /= count_field[r][c]

        # Compute vorticity ω = ∂vc/∂r - ∂vr/∂c
        for r in range(view_rows):
            for c in range(view_cols):
                rp = (r + 1) % view_rows
                cp_ = (c + 1) % view_cols
                omega = (vc_field[rp][c] - vc_field[r][c]) - (vr_field[r][cp_] - vr_field[r][c])

                if abs(omega) < 0.01:
                    continue
                if omega > 0:
                    if omega > 0.3:
                        ch = "⟳⟳"
                        color = 1  # red = strong CW
                    else:
                        ch = "○○"
                        color = 3  # yellow = weak CW
                else:
                    if omega < -0.3:
                        ch = "⟲⟲"
                        color = 4  # blue = strong CCW
                    else:
                        ch = "○○"
                        color = 6  # cyan = weak CCW
                try:
                    self.stdscr.addstr(1 + r, c * 2, ch, curses.color_pair(color))
                except curses.error:
                    pass

    # Compute order parameter (polar or nematic)
    if len(particles) > 0:
        if self.active_matter_nematic:
            sx = sum(math.cos(2 * p[2]) for p in particles)
            sy = sum(math.sin(2 * p[2]) for p in particles)
            order = math.sqrt(sx * sx + sy * sy) / len(particles)
        else:
            sx = sum(math.cos(p[2]) for p in particles)
            sy = sum(math.sin(p[2]) for p in particles)
            order = math.sqrt(sx * sx + sy * sy) / len(particles)
    else:
        order = 0.0

    avg_spd = 0.0
    for p in particles:
        avg_spd += math.sqrt(p[3] * p[3] + p[4] * p[4])
    avg_spd /= max(1, len(particles))

    # Status bar
    views = ["Arrows", "Density", "Vorticity"]
    status_y = max_y - 3
    if status_y > 1:
        info = (f" Gen {self.active_matter_generation}"
                f"  |  ψ={order:.3f}"
                f"  |  ⟨v⟩={avg_spd:.3f}"
                f"  |  align={self.active_matter_align_w:.1f}"
                f"  repel={self.active_matter_repel_w:.1f}"
                f"  |  view={views[view]}")
        try:
            self.stdscr.addstr(status_y, 0, info[:max_x - 1], curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 2
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [v]=view [s/S]=speed [e/E]=noise [a/A]=align [p/P]=repel [t/T]=tumble [click]=add [r]=reset [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    # Bottom line with steps/frame
    bot_y = max_y - 1
    if bot_y > 0:
        bot = f" steps/frame={self.active_matter_steps_per_frame}  |  [+/-]=steps/frame  [</>]=delay  [R]=menu"
        try:
            self.stdscr.addstr(bot_y, 0, bot[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ── Registration ─────────────────────────────────────────────────────────
def register(App):
    """Register Active Matter mode methods on the App class."""
    App.ACTIVE_MATTER_PRESETS = ACTIVE_MATTER_PRESETS
    App._enter_active_matter_mode = _enter_active_matter_mode
    App._exit_active_matter_mode = _exit_active_matter_mode
    App._active_matter_init = _active_matter_init
    App._active_matter_step = _active_matter_step
    App._handle_active_matter_menu_key = _handle_active_matter_menu_key
    App._handle_active_matter_key = _handle_active_matter_key
    App._draw_active_matter_menu = _draw_active_matter_menu
    App._draw_active_matter = _draw_active_matter
