"""Mode: granular_dynamics — 2D granular material simulation with contact forces,
friction, jamming transitions, force chains, avalanche cascades, and granular
convection (Brazil nut effect)."""
import curses
import math
import random
import time

from life.constants import SPEEDS

# ── Presets ──────────────────────────────────────────────────────────────
GRANULAR_PRESETS = [
    ("Hopper Flow",
     "Funnel with arching/clogging — tilt gravity to restart flow",
     "hopper"),
    ("Avalanche Slope",
     "Sandpile near angle of repose — add grains to trigger cascades",
     "avalanche"),
    ("Brazil Nut Effect",
     "Shaking separates large grains to the top via granular convection",
     "brazil_nut"),
    ("Force Chain Network",
     "Compressed grains reveal branching stress networks",
     "force_chains"),
    ("Granular Gas",
     "Dilute inelastic particles — clustering instability & inelastic collapse",
     "granular_gas"),
    ("Drum Rotation",
     "Rotating drum with segregation bands and avalanching surface flow",
     "drum"),
]

# ── Glyphs & rendering helpers ──────────────────────────────────────────
_GRAIN_CHARS = ["·", "●", "◉", "◆", "■", "⬢"]
_FORCE_CHARS = ["  ", "··", "░░", "▒▒", "▓▓", "██"]
_DENSITY_CHARS = ["  ", "· ", "░░", "▒▒", "▓▓", "██"]


def _grain_color(force_mag, is_large=False):
    """Map contact force magnitude to color pair."""
    if is_large:
        return 3  # yellow for large grains
    if force_mag < 0.1:
        return 6  # cyan — no stress
    elif force_mag < 0.5:
        return 2  # green — low stress
    elif force_mag < 1.5:
        return 3  # yellow — moderate
    elif force_mag < 3.0:
        return 5  # magenta — high
    else:
        return 1  # red — extreme


def _force_chain_color(force_mag):
    """Map force chain intensity to color."""
    if force_mag < 0.3:
        return 4  # blue
    elif force_mag < 1.0:
        return 6  # cyan
    elif force_mag < 2.0:
        return 2  # green
    elif force_mag < 4.0:
        return 3  # yellow
    elif force_mag < 8.0:
        return 5  # magenta
    else:
        return 1  # red


def _force_char(force_mag):
    """Map force magnitude to density glyph."""
    if force_mag < 0.1:
        return _FORCE_CHARS[0]
    elif force_mag < 0.5:
        return _FORCE_CHARS[1]
    elif force_mag < 1.5:
        return _FORCE_CHARS[2]
    elif force_mag < 3.0:
        return _FORCE_CHARS[3]
    elif force_mag < 6.0:
        return _FORCE_CHARS[4]
    else:
        return _FORCE_CHARS[5]


# ── Lifecycle ────────────────────────────────────────────────────────────
def _enter_granular_mode(self):
    """Enter Granular Dynamics mode — show preset menu."""
    self.granular_menu = True
    self.granular_menu_sel = 0
    self._flash("Granular Dynamics — select a configuration")


def _exit_granular_mode(self):
    """Exit Granular Dynamics mode."""
    self.granular_mode = False
    self.granular_menu = False
    self.granular_running = False
    self.granular_particles = []
    self.granular_walls = []
    self._flash("Granular Dynamics mode OFF")


def _granular_init(self, preset_idx: int):
    """Initialize simulation with chosen preset."""
    name, _desc, kind = self.GRANULAR_PRESETS[preset_idx]
    self.granular_preset_name = name
    self.granular_kind = kind
    self.granular_generation = 0
    self.granular_running = False
    self.granular_view = 0  # 0=grains, 1=force chains, 2=density

    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(10, max_y - 4)
    cols = max(10, (max_x - 1) // 2)
    self.granular_rows = rows
    self.granular_cols = cols

    rng = random.Random()

    # Physics parameters
    gravity_r = 0.15     # downward gravity
    gravity_c = 0.0      # lateral gravity (tilt)
    restitution = 0.3    # coefficient of restitution
    friction_coeff = 0.4 # Coulomb friction coefficient
    stiffness = 8.0      # contact spring stiffness (Hertz-like)
    damping = 0.05       # velocity damping
    grain_radius = 0.45  # default grain radius
    n_grains = 200
    shake_amp = 0.0      # shaking amplitude
    shake_freq = 0.0     # shaking frequency

    # Walls: list of (r1, c1, r2, c2) line segments
    walls = []
    # Floor
    walls.append((rows - 1, 0, rows - 1, cols - 1))
    # Left wall
    walls.append((0, 0, rows - 1, 0))
    # Right wall
    walls.append((0, cols - 1, rows - 1, cols - 1))

    if kind == "hopper":
        n_grains = 300
        gravity_r = 0.12
        restitution = 0.2
        friction_coeff = 0.5
        stiffness = 10.0
        # Funnel walls converging to narrow opening
        mid_c = cols // 2
        gap = max(3, cols // 15)
        funnel_r = rows * 2 // 3
        # Left funnel wall
        walls.append((funnel_r - rows // 4, 2, funnel_r, mid_c - gap))
        # Right funnel wall
        walls.append((funnel_r - rows // 4, cols - 3, funnel_r, mid_c + gap))
    elif kind == "avalanche":
        n_grains = 250
        gravity_r = 0.15
        restitution = 0.15
        friction_coeff = 0.6
        stiffness = 12.0
    elif kind == "brazil_nut":
        n_grains = 200
        gravity_r = 0.12
        restitution = 0.25
        friction_coeff = 0.4
        stiffness = 8.0
        shake_amp = 0.4
        shake_freq = 0.15
    elif kind == "force_chains":
        n_grains = 350
        gravity_r = 0.2
        restitution = 0.1
        friction_coeff = 0.5
        stiffness = 15.0
        damping = 0.08
    elif kind == "granular_gas":
        n_grains = 150
        gravity_r = 0.0
        restitution = 0.9
        friction_coeff = 0.1
        stiffness = 6.0
        damping = 0.0
    elif kind == "drum":
        n_grains = 250
        gravity_r = 0.12
        restitution = 0.2
        friction_coeff = 0.5
        stiffness = 10.0
        # Drum is simulated by slow gravity rotation
        self.granular_drum_angle = 0.0
        self.granular_drum_speed = 0.01

    self.granular_gravity_r = gravity_r
    self.granular_gravity_c = gravity_c
    self.granular_restitution = restitution
    self.granular_friction_coeff = friction_coeff
    self.granular_stiffness = stiffness
    self.granular_damping = damping
    self.granular_shake_amp = shake_amp
    self.granular_shake_freq = shake_freq
    self.granular_steps_per_frame = 2
    self.granular_walls = walls

    # Force chain accumulator for rendering
    self.granular_force_grid = [[0.0] * cols for _ in range(rows)]

    # Create particles: [r, c, vr, vc, radius, mass, force_accum, is_large]
    particles = []
    n_large = 0
    if kind == "brazil_nut":
        n_large = max(5, n_grains // 15)

    for i in range(n_grains):
        is_large = i < n_large
        radius = grain_radius * (1.8 if is_large else (0.8 + rng.random() * 0.4))
        mass = radius * radius * math.pi  # mass ~ area

        if kind == "hopper":
            # Fill upper region
            pr = rng.random() * (rows * 0.5) + 1
            pc = rng.random() * (cols - 4) + 2
        elif kind == "avalanche":
            # Triangular pile
            pr = rows - 2 - rng.random() * (rows * 0.5)
            pc = cols * 0.3 + rng.random() * (cols * 0.4)
        elif kind == "brazil_nut":
            pr = rows - 2 - rng.random() * (rows * 0.5)
            pc = rng.random() * (cols - 4) + 2
        elif kind == "force_chains":
            pr = rows - 2 - rng.random() * (rows * 0.7)
            pc = rng.random() * (cols - 4) + 2
        elif kind == "granular_gas":
            pr = rng.random() * (rows - 4) + 2
            pc = rng.random() * (cols - 4) + 2
        elif kind == "drum":
            pr = rows - 2 - rng.random() * (rows * 0.5)
            pc = rng.random() * (cols - 4) + 2
        else:
            pr = rng.random() * (rows - 4) + 2
            pc = rng.random() * (cols - 4) + 2

        # Initial velocities
        if kind == "granular_gas":
            vr = rng.gauss(0, 0.5)
            vc = rng.gauss(0, 0.5)
        else:
            vr = 0.0
            vc = 0.0

        particles.append([pr, pc, vr, vc, radius, mass, 0.0, is_large])

    self.granular_particles = particles
    self.granular_num_particles = len(particles)

    self.granular_menu = False
    self.granular_mode = True
    self._flash(f"Granular Dynamics: {name} — Space to start")


# ── Simulation step ─────────────────────────────────────────────────────
def _granular_step(self):
    """Advance granular simulation by one timestep using DEM
    (Discrete Element Method) with Hertzian contact + Coulomb friction."""
    particles = self.granular_particles
    n = len(particles)
    rows = self.granular_rows
    cols = self.granular_cols
    grav_r = self.granular_gravity_r
    grav_c = self.granular_gravity_c
    rest = self.granular_restitution
    mu = self.granular_friction_coeff
    stiff = self.granular_stiffness
    damp = self.granular_damping
    shake_amp = self.granular_shake_amp
    shake_freq = self.granular_shake_freq
    gen = self.granular_generation
    walls = self.granular_walls

    # Drum rotation — rotate gravity direction
    if self.granular_kind == "drum" and hasattr(self, 'granular_drum_angle'):
        self.granular_drum_angle += self.granular_drum_speed
        angle = self.granular_drum_angle
        base_g = math.sqrt(grav_r * grav_r + grav_c * grav_c)
        if base_g < 0.01:
            base_g = 0.12
        grav_r = base_g * math.cos(angle)
        grav_c = base_g * math.sin(angle)

    # Shaking (vertical oscillation)
    shake_offset = 0.0
    if shake_amp > 0:
        shake_offset = shake_amp * math.sin(gen * shake_freq * 2 * math.pi)

    # Spatial hashing for O(n) neighbor lookup
    cell_size = 2.0
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

    # Reset force accumulator grid
    force_grid = self.granular_force_grid
    for r in range(rows):
        for c in range(cols):
            force_grid[r][c] *= 0.7  # decay for visualization persistence

    # Compute contact forces
    # fr[i], fc[i] = net force on particle i
    fr_arr = [0.0] * n
    fc_arr = [0.0] * n

    for i in range(n):
        pr_i, pc_i, vr_i, vc_i, rad_i, mass_i, _, _ = particles[i]
        gr = int(pr_i / cell_size) % grid_h
        gc = int(pc_i / cell_size) % grid_w

        for dgr in (-1, 0, 1):
            for dgc in (-1, 0, 1):
                nkey = ((gr + dgr) % grid_h, (gc + dgc) % grid_w)
                bucket = cells.get(nkey)
                if bucket is None:
                    continue
                for j in bucket:
                    if j <= i:
                        continue
                    pr_j, pc_j, vr_j, vc_j, rad_j, mass_j, _, _ = particles[j]

                    dr = pr_j - pr_i
                    dc = pc_j - pc_i
                    dist2 = dr * dr + dc * dc
                    contact_dist = rad_i + rad_j
                    contact_dist2 = contact_dist * contact_dist

                    if dist2 >= contact_dist2 or dist2 < 0.0001:
                        continue

                    dist = math.sqrt(dist2)
                    overlap = contact_dist - dist

                    # Normal direction (i → j)
                    nr = dr / dist
                    nc = dc / dist

                    # Hertzian normal force: F_n = k * overlap^1.5
                    fn_mag = stiff * (overlap ** 1.5)

                    # Normal damping (dashpot)
                    dvr = vr_j - vr_i
                    dvc = vc_j - vc_i
                    vn = dvr * nr + dvc * nc  # relative normal velocity
                    fn_damp = -0.3 * stiff * vn * math.sqrt(overlap)
                    fn_total = fn_mag + fn_damp
                    if fn_total < 0:
                        fn_total = 0.0

                    # Tangential (friction) force
                    vt = dvr * (-nc) + dvc * nr  # relative tangential velocity
                    ft_mag = mu * fn_total
                    # Clamp friction by tangential velocity (regularized Coulomb)
                    ft_actual = max(-ft_mag, min(ft_mag, -0.5 * stiff * vt * math.sqrt(overlap)))

                    # Apply forces
                    # Normal force on i: towards j
                    fir = -fn_total * nr + ft_actual * (-nc)
                    fic = -fn_total * nc + ft_actual * nr
                    fjr = fn_total * nr - ft_actual * (-nc)
                    fjc = fn_total * nc - ft_actual * nr

                    fr_arr[i] += fir
                    fc_arr[i] += fic
                    fr_arr[j] += fjr
                    fc_arr[j] += fjc

                    # Record force chain magnitude on grid
                    mid_r = int((pr_i + pr_j) / 2)
                    mid_c = int((pc_i + pc_j) / 2)
                    if 0 <= mid_r < rows and 0 <= mid_c < cols:
                        force_grid[mid_r][mid_c] = max(force_grid[mid_r][mid_c], fn_total)

    # Wall collisions
    for i in range(n):
        pr_i, pc_i, vr_i, vc_i, rad_i, mass_i, _, _ = particles[i]

        # Simple axis-aligned boundary collisions
        # Floor
        if pr_i + rad_i > rows - 1:
            overlap = pr_i + rad_i - (rows - 1)
            fn = stiff * (overlap ** 1.5)
            fr_arr[i] -= fn
            # Friction on floor
            ft = mu * fn
            if abs(vc_i) > 0.001:
                fc_arr[i] -= ft * (1 if vc_i > 0 else -1)
            # Record
            ri = min(rows - 1, int(pr_i))
            ci = max(0, min(cols - 1, int(pc_i)))
            if 0 <= ri < rows:
                force_grid[ri][ci] = max(force_grid[ri][ci], fn)

        # Ceiling (for granular gas / shaking)
        if pr_i - rad_i < 0:
            overlap = rad_i - pr_i
            fn = stiff * (overlap ** 1.5)
            fr_arr[i] += fn

        # Left wall
        if pc_i - rad_i < 0:
            overlap = rad_i - pc_i
            fn = stiff * (overlap ** 1.5)
            fc_arr[i] += fn
            ft = mu * fn
            if abs(vr_i) > 0.001:
                fr_arr[i] -= ft * (1 if vr_i > 0 else -1)

        # Right wall
        if pc_i + rad_i > cols - 1:
            overlap = pc_i + rad_i - (cols - 1)
            fn = stiff * (overlap ** 1.5)
            fc_arr[i] -= fn
            ft = mu * fn
            if abs(vr_i) > 0.001:
                fr_arr[i] -= ft * (1 if vr_i > 0 else -1)

        # Hopper funnel walls — line segment collisions
        if self.granular_kind == "hopper":
            for w in walls[3:]:  # skip boundary walls
                wr1, wc1, wr2, wc2 = w
                _wall_collision(pr_i, pc_i, vr_i, vc_i, rad_i,
                                wr1, wc1, wr2, wc2,
                                stiff, mu, fr_arr, fc_arr, i)

    # Update velocities and positions
    for i in range(n):
        pr_i, pc_i, vr_i, vc_i, rad_i, mass_i, _, is_large = particles[i]

        # Gravity + shaking
        acc_r = grav_r + fr_arr[i] / mass_i
        acc_c = grav_c + fc_arr[i] / mass_i

        if shake_amp > 0:
            acc_r += shake_offset / mass_i

        # Velocity update
        vr_new = (vr_i + acc_r) * (1.0 - damp)
        vc_new = (vc_i + acc_c) * (1.0 - damp)

        # Clamp velocity
        spd = math.sqrt(vr_new * vr_new + vc_new * vc_new)
        max_spd = 3.0
        if spd > max_spd:
            vr_new = vr_new / spd * max_spd
            vc_new = vc_new / spd * max_spd

        # Position update
        pr_new = pr_i + vr_new
        pc_new = pc_i + vc_new

        # Hard boundary clamp
        if pr_new - rad_i < 0:
            pr_new = rad_i
            vr_new = abs(vr_new) * rest
        if pr_new + rad_i > rows - 1:
            pr_new = rows - 1 - rad_i
            vr_new = -abs(vr_new) * rest
        if pc_new - rad_i < 0:
            pc_new = rad_i
            vc_new = abs(vc_new) * rest
        if pc_new + rad_i > cols - 1:
            pc_new = cols - 1 - rad_i
            vc_new = -abs(vc_new) * rest

        # Compute force magnitude for this particle's display
        force_mag = math.sqrt(fr_arr[i] ** 2 + fc_arr[i] ** 2)

        particles[i] = [pr_new, pc_new, vr_new, vc_new, rad_i, mass_i, force_mag, is_large]

    self.granular_generation += 1

    # Compute global stats
    total_ke = 0.0
    for p in particles:
        spd2 = p[2] * p[2] + p[3] * p[3]
        total_ke += 0.5 * p[5] * spd2
    self.granular_kinetic_energy = total_ke

    # Jamming detection — fraction of particles with very low velocity
    n_jammed = sum(1 for p in particles if (p[2] * p[2] + p[3] * p[3]) < 0.001)
    self.granular_jammed_fraction = n_jammed / max(1, n)

    # Max force for force chain stats
    max_force = max((p[6] for p in particles), default=0.0)
    self.granular_max_force = max_force


def _wall_collision(pr, pc, vr, vc, rad, wr1, wc1, wr2, wc2,
                    stiff, mu, fr_arr, fc_arr, idx):
    """Compute collision between a particle and a line-segment wall."""
    # Vector along wall
    wr = wr2 - wr1
    wc = wc2 - wc1
    wall_len2 = wr * wr + wc * wc
    if wall_len2 < 0.001:
        return

    # Project particle center onto wall segment
    t = ((pr - wr1) * wr + (pc - wc1) * wc) / wall_len2
    t = max(0.0, min(1.0, t))
    closest_r = wr1 + t * wr
    closest_c = wc1 + t * wc

    dr = pr - closest_r
    dc = pc - closest_c
    dist2 = dr * dr + dc * dc

    if dist2 >= rad * rad or dist2 < 0.0001:
        return

    dist = math.sqrt(dist2)
    overlap = rad - dist
    nr = dr / dist
    nc = dc / dist

    fn = stiff * (overlap ** 1.5)
    fr_arr[idx] += fn * nr
    fc_arr[idx] += fn * nc

    # Tangential friction
    vt = vr * (-nc) + vc * nr
    ft = mu * fn
    ft_actual = max(-ft, min(ft, -0.3 * vt * stiff * math.sqrt(overlap)))
    fr_arr[idx] += ft_actual * (-nc)
    fc_arr[idx] += ft_actual * nr


# ── Input handling ───────────────────────────────────────────────────────
def _handle_granular_menu_key(self, key: int) -> bool:
    """Handle input in Granular Dynamics preset menu."""
    n = len(self.GRANULAR_PRESETS)
    if key in (ord("j"), curses.KEY_DOWN):
        self.granular_menu_sel = (self.granular_menu_sel + 1) % n
    elif key in (ord("k"), curses.KEY_UP):
        self.granular_menu_sel = (self.granular_menu_sel - 1) % n
    elif key in (ord("\n"), ord("\r")):
        self._granular_init(self.granular_menu_sel)
    elif key in (ord("q"), 27):
        self.granular_menu = False
        self._flash("Granular Dynamics cancelled")
    return True


def _handle_granular_key(self, key: int) -> bool:
    """Handle input in active Granular Dynamics simulation."""
    if key == ord(" "):
        self.granular_running = not self.granular_running
    elif key in (ord("n"), ord(".")):
        for _ in range(self.granular_steps_per_frame):
            self._granular_step()
    elif key == ord("r"):
        idx = next((i for i, p in enumerate(self.GRANULAR_PRESETS)
                    if p[0] == self.granular_preset_name), 0)
        self._granular_init(idx)
        self.granular_running = False
    elif key in (ord("R"), ord("m")):
        self.granular_mode = False
        self.granular_running = False
        self.granular_menu = True
        self.granular_menu_sel = 0
    elif key == ord("v"):
        self.granular_view = (self.granular_view + 1) % 3
        labels = ["Grains", "Force Chains", "Density"]
        self._flash(f"View: {labels[self.granular_view]}")
    elif key == ord("g") or key == ord("G"):
        # Adjust gravity strength
        delta = 0.02 if key == ord("g") else -0.02
        self.granular_gravity_r = max(0.0, min(0.5, self.granular_gravity_r + delta))
        self._flash(f"Gravity: {self.granular_gravity_r:.2f}")
    elif key == ord("t") or key == ord("T"):
        # Tilt gravity laterally
        delta = 0.02 if key == ord("t") else -0.02
        self.granular_gravity_c = max(-0.3, min(0.3, self.granular_gravity_c + delta))
        self._flash(f"Tilt: {self.granular_gravity_c:.2f}")
    elif key == ord("f") or key == ord("F"):
        # Adjust friction
        delta = 0.05 if key == ord("f") else -0.05
        self.granular_friction_coeff = max(0.0, min(1.0, self.granular_friction_coeff + delta))
        self._flash(f"Friction: {self.granular_friction_coeff:.2f}")
    elif key == ord("e") or key == ord("E"):
        # Adjust restitution
        delta = 0.05 if key == ord("e") else -0.05
        self.granular_restitution = max(0.0, min(1.0, self.granular_restitution + delta))
        self._flash(f"Restitution: {self.granular_restitution:.2f}")
    elif key == ord("s") or key == ord("S"):
        # Shake / vibrate
        delta = 0.1 if key == ord("s") else -0.1
        self.granular_shake_amp = max(0.0, min(2.0, self.granular_shake_amp + delta))
        if self.granular_shake_freq < 0.01:
            self.granular_shake_freq = 0.1
        self._flash(f"Shake: {self.granular_shake_amp:.1f}")
    elif key == ord("k") or key == ord("K"):
        # Adjust stiffness
        delta = 1.0 if key == ord("k") else -1.0
        self.granular_stiffness = max(1.0, min(30.0, self.granular_stiffness + delta))
        self._flash(f"Stiffness: {self.granular_stiffness:.0f}")
    elif key == ord("+") or key == ord("="):
        self.granular_steps_per_frame = min(10, self.granular_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.granular_steps_per_frame}")
    elif key == ord("-"):
        self.granular_steps_per_frame = max(1, self.granular_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.granular_steps_per_frame}")
    elif key == ord("<") or key == ord(","):
        self.speed_idx = max(0, self.speed_idx - 1)
    elif key == ord(">") or key == ord("."):
        self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)
    elif key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, bstate = curses.getmouse()
            r_click = my - 1
            c_click = mx // 2
            if 0 <= r_click < self.granular_rows and 0 <= c_click < self.granular_cols:
                # Drop a cluster of grains at click location
                rng = random.Random()
                for _ in range(12):
                    pr = (r_click + rng.gauss(0, 1.5))
                    pc = (c_click + rng.gauss(0, 1.5))
                    pr = max(0.5, min(self.granular_rows - 1.5, pr))
                    pc = max(0.5, min(self.granular_cols - 1.5, pc))
                    radius = 0.35 + rng.random() * 0.2
                    mass = radius * radius * math.pi
                    self.granular_particles.append([pr, pc, 0.0, 0.0, radius, mass, 0.0, False])
                self.granular_num_particles = len(self.granular_particles)
                self._flash(f"+12 grains (total: {self.granular_num_particles})")
        except curses.error:
            pass
    elif key in (ord("q"), 27):
        self._exit_granular_mode()
    else:
        return True
    return True


# ── Drawing ──────────────────────────────────────────────────────────────
def _draw_granular_menu(self, max_y: int, max_x: int):
    """Draw the Granular Dynamics preset selection menu."""
    self.stdscr.erase()
    title = "── Granular Dynamics ── Select Configuration ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _kind) in enumerate(self.GRANULAR_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        line = f"  {name:<28s}  {desc}"
        attr = curses.color_pair(6)
        if i == self.granular_menu_sel:
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


def _draw_granular(self, max_y: int, max_x: int):
    """Draw the active Granular Dynamics simulation."""
    self.stdscr.erase()
    particles = self.granular_particles
    rows = self.granular_rows
    cols = self.granular_cols
    view = self.granular_view
    state = "▶ RUNNING" if self.granular_running else "⏸ PAUSED"

    ke = getattr(self, 'granular_kinetic_energy', 0.0)
    jammed = getattr(self, 'granular_jammed_fraction', 0.0)
    max_f = getattr(self, 'granular_max_force', 0.0)

    # Title bar
    title = (f" Granular: {self.granular_preset_name}  |  gen {self.granular_generation}"
             f"  |  N={self.granular_num_particles}"
             f"  g={self.granular_gravity_r:.2f}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    view_rows = min(rows, max_y - 4)
    view_cols = min(cols, (max_x - 1) // 2)

    if view == 0:
        # Grain view — show each particle as a glyph colored by contact force
        # Build occupancy grid: store best particle per cell
        grid: dict[tuple[int, int], int] = {}
        for idx, p in enumerate(particles):
            ri = int(p[0]) % rows
            ci = int(p[1]) % cols
            if ri < view_rows and ci < view_cols:
                # Prefer showing highest-force particle
                if (ri, ci) not in grid or p[6] > particles[grid[(ri, ci)]][6]:
                    grid[(ri, ci)] = idx

        for (ri, ci), idx in grid.items():
            p = particles[idx]
            is_large = p[7]
            force_mag = p[6]
            if is_large:
                ch = "◆◆"
            elif p[4] > 0.5:
                ch = "●●"
            else:
                ch = "··"
            cp = _grain_color(force_mag, is_large)
            bold = curses.A_BOLD if force_mag > 2.0 else (curses.A_DIM if force_mag < 0.1 else 0)
            try:
                self.stdscr.addstr(1 + ri, ci * 2, ch, curses.color_pair(cp) | bold)
            except curses.error:
                pass

        # Draw hopper funnel walls
        if self.granular_kind == "hopper":
            for w in self.granular_walls[3:]:
                _draw_wall_segment(self, w, view_rows, view_cols)

    elif view == 1:
        # Force chain view — show force magnitude field
        force_grid = self.granular_force_grid
        for r in range(view_rows):
            for c in range(view_cols):
                f = force_grid[r][c]
                if f < 0.05:
                    continue
                ch = _force_char(f)
                cp = _force_chain_color(f)
                bold = curses.A_BOLD if f > 3.0 else 0
                try:
                    self.stdscr.addstr(1 + r, c * 2, ch, curses.color_pair(cp) | bold)
                except curses.error:
                    pass

        # Overlay grains as dots
        for p in particles:
            ri = int(p[0]) % rows
            ci = int(p[1]) % cols
            if ri < view_rows and ci < view_cols:
                try:
                    self.stdscr.addstr(1 + ri, ci * 2, "· ",
                                       curses.color_pair(6) | curses.A_DIM)
                except curses.error:
                    pass

    else:
        # Density view — coarse-grained packing field
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
                idx = min(cnt, len(_DENSITY_CHARS) - 1)
                ch = _DENSITY_CHARS[idx]
                # Color by packing: sparse=blue, moderate=green, jammed=red
                if cnt <= 1:
                    cp = 4
                elif cnt <= 2:
                    cp = 6
                elif cnt <= 3:
                    cp = 2
                elif cnt <= 5:
                    cp = 3
                else:
                    cp = 1
                try:
                    self.stdscr.addstr(1 + r, c * 2, ch, curses.color_pair(cp))
                except curses.error:
                    pass

    # Status bar
    views = ["Grains", "Force Chains", "Density"]
    status_y = max_y - 3
    if status_y > 1:
        jam_label = "JAMMED" if jammed > 0.9 else ("flowing" if jammed < 0.3 else "partial")
        info = (f" Gen {self.granular_generation}"
                f"  |  KE={ke:.2f}"
                f"  |  F_max={max_f:.1f}"
                f"  |  jammed={jammed:.0%} ({jam_label})"
                f"  |  μ={self.granular_friction_coeff:.2f}"
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
            hint = " [Space]=play [n]=step [v]=view [g/G]=gravity [t/T]=tilt [f/F]=friction [e/E]=restitution [s/S]=shake [click]=add [r]=reset [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    # Bottom line
    bot_y = max_y - 1
    if bot_y > 0:
        bot = f" steps/frame={self.granular_steps_per_frame}  |  [+/-]=steps/frame  [</>]=delay  [k/K]=stiffness  [R]=menu"
        try:
            self.stdscr.addstr(bot_y, 0, bot[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_wall_segment(self, wall, view_rows, view_cols):
    """Draw a wall segment on screen using Bresenham-style line."""
    wr1, wc1, wr2, wc2 = wall
    steps = max(abs(wr2 - wr1), abs(wc2 - wc1), 1)
    for s in range(steps + 1):
        t = s / steps
        r = int(wr1 + t * (wr2 - wr1))
        c = int(wc1 + t * (wc2 - wc1))
        if 0 <= r < view_rows and 0 <= c < view_cols:
            try:
                self.stdscr.addstr(1 + r, c * 2, "▓▓",
                                   curses.color_pair(6) | curses.A_BOLD)
            except curses.error:
                pass


# ── Registration ─────────────────────────────────────────────────────────
def register(App):
    """Register Granular Dynamics mode methods on the App class."""
    App.GRANULAR_PRESETS = GRANULAR_PRESETS
    App._enter_granular_mode = _enter_granular_mode
    App._exit_granular_mode = _exit_granular_mode
    App._granular_init = _granular_init
    App._granular_step = _granular_step
    App._handle_granular_menu_key = _handle_granular_menu_key
    App._handle_granular_key = _handle_granular_key
    App._draw_granular_menu = _draw_granular_menu
    App._draw_granular = _draw_granular
