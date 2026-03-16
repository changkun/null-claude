"""Mode: crowd — Crowd Dynamics & Evacuation Simulation.

Social-force model where individual agents navigate rooms, corridors, and
doorways with emergent crowd behaviors — lane formation in counterflow,
arch formation at bottlenecks, panic propagation, and stampede dynamics.

Emergent phenomena:
  - Arch / clogging at narrow exits
  - Lane formation in bidirectional flow
  - Faster-is-slower effect under panic
  - Herding / panic contagion waves
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

CROWD_PRESETS = [
    ("Normal Evacuation",
     "Single-room evacuation through one exit — orderly flow with arch formation",
     "normal"),
    ("Panic Stampede",
     "High-panic evacuation — faster-is-slower effect, crushing near exit",
     "panic"),
    ("Concert Venue",
     "Large open venue with multiple exits and a stage obstacle",
     "concert"),
    ("Stadium Exit",
     "Radial seating with narrow vomitoria — merging flows and bottlenecks",
     "stadium"),
    ("Counterflow Corridors",
     "Two groups walking toward each other in a corridor — emergent lane formation",
     "counterflow"),
    ("Black Friday Rush",
     "Crowd rushing inward toward a store entrance — competitive pushing",
     "blackfriday"),
]


# ══════════════════════════════════════════════════════════════════════
#  Agent class
# ══════════════════════════════════════════════════════════════════════

class _Agent:
    """A single pedestrian agent."""
    __slots__ = ("x", "y", "vx", "vy", "target_x", "target_y",
                 "desired_speed", "radius", "panic", "group", "escaped")

    def __init__(self, x, y, target_x, target_y, desired_speed=1.2,
                 radius=0.3, panic=0.0, group=0):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.target_x = target_x
        self.target_y = target_y
        self.desired_speed = desired_speed
        self.radius = radius
        self.panic = panic
        self.group = group
        self.escaped = False


# ══════════════════════════════════════════════════════════════════════
#  Geometry helpers
# ══════════════════════════════════════════════════════════════════════

def _build_walls_and_exits(preset_id, rows, cols):
    """Return (walls_set, exits_list) for the given preset.

    walls_set: set of (r, c) wall cells
    exits_list: list of (r, c, group) — group=-1 means any agent can use it
    """
    walls = set()
    exits = []

    if preset_id == "normal" or preset_id == "panic":
        # Rectangular room with one exit on the right wall
        for r in range(rows):
            walls.add((r, 0))
            walls.add((r, cols - 1))
        for c in range(cols):
            walls.add((0, c))
            walls.add((rows - 1, c))
        # Exit: gap in right wall, centered
        exit_half = max(1, rows // 10)
        mid = rows // 2
        for r in range(mid - exit_half, mid + exit_half + 1):
            walls.discard((r, cols - 1))
            exits.append((r, cols - 1, -1))

    elif preset_id == "concert":
        # Large room, stage obstacle on left, two exits on right
        for r in range(rows):
            walls.add((r, 0))
            walls.add((r, cols - 1))
        for c in range(cols):
            walls.add((0, c))
            walls.add((rows - 1, c))
        # Stage block on left side
        stage_w = cols // 5
        stage_h = rows // 3
        stage_r0 = rows // 2 - stage_h // 2
        for r in range(stage_r0, stage_r0 + stage_h):
            for c in range(1, stage_w):
                walls.add((r, c))
        # Two exits on right wall
        gap = max(1, rows // 12)
        for offset in [rows // 3, 2 * rows // 3]:
            for r in range(offset - gap, offset + gap + 1):
                walls.discard((r, cols - 1))
                exits.append((r, cols - 1, -1))

    elif preset_id == "stadium":
        # Oval-ish boundary with narrow exits at cardinal points
        cx, cy = cols // 2, rows // 2
        rx, ry = cols // 2 - 1, rows // 2 - 1
        for r in range(rows):
            for c in range(cols):
                # Ellipse boundary
                dx = (c - cx) / max(rx, 1)
                dy = (r - cy) / max(ry, 1)
                dist = dx * dx + dy * dy
                if dist >= 0.92 and dist <= 1.1:
                    walls.add((r, c))
        # Four exits (gaps in the ellipse)
        gap = max(1, min(rows, cols) // 12)
        # Top
        for c in range(cx - gap, cx + gap + 1):
            walls.discard((0, c))
            walls.discard((1, c))
            exits.append((0, c, -1))
        # Bottom
        for c in range(cx - gap, cx + gap + 1):
            walls.discard((rows - 1, c))
            walls.discard((rows - 2, c))
            exits.append((rows - 1, c, -1))
        # Left
        for r in range(cy - gap, cy + gap + 1):
            walls.discard((r, 0))
            walls.discard((r, 1))
            exits.append((r, 0, -1))
        # Right
        for r in range(cy - gap, cy + gap + 1):
            walls.discard((r, cols - 1))
            walls.discard((r, cols - 2))
            exits.append((r, cols - 1, -1))

    elif preset_id == "counterflow":
        # Long corridor — walls top and bottom, open left and right
        for c in range(cols):
            walls.add((0, c))
            walls.add((rows - 1, c))
        # Left exit for group 0, right exit for group 1
        corridor_h = max(1, rows // 8)
        mid = rows // 2
        for r in range(mid - corridor_h, mid + corridor_h + 1):
            exits.append((r, 0, 0))
            exits.append((r, cols - 1, 1))

    elif preset_id == "blackfriday":
        # Open area, entrance at top center (the "store door")
        for c in range(cols):
            walls.add((0, c))
        # Entrance gap
        gap = max(1, cols // 10)
        mid_c = cols // 2
        for c in range(mid_c - gap, mid_c + gap + 1):
            walls.discard((0, c))
            exits.append((0, c, -1))
        # Side walls (partial)
        for r in range(rows // 3):
            walls.add((r, 0))
            walls.add((r, cols - 1))

    return walls, exits


def _spawn_agents(preset_id, rows, cols, walls, exits):
    """Create initial agent population for the preset."""
    agents = []
    rng = random.random

    # Find mean exit position for targeting
    if exits:
        ex_r = sum(e[0] for e in exits) / len(exits)
        ex_c = sum(e[1] for e in exits) / len(exits)
    else:
        ex_r, ex_c = rows // 2, cols - 1

    if preset_id in ("normal", "panic"):
        n = min(200, int(rows * cols * 0.15))
        panic_base = 0.8 if preset_id == "panic" else 0.1
        speed_base = 2.0 if preset_id == "panic" else 1.2
        for _ in range(n):
            for _try in range(20):
                r = random.randint(2, rows - 3)
                c = random.randint(2, cols - 5)
                if (r, c) not in walls:
                    break
            a = _Agent(float(c), float(r), ex_c, ex_r,
                       desired_speed=speed_base * (0.8 + 0.4 * rng()),
                       panic=min(1.0, panic_base + 0.3 * rng()))
            agents.append(a)

    elif preset_id == "concert":
        n = min(250, int(rows * cols * 0.12))
        right_exits = [e for e in exits if e[1] >= cols - 2]
        if right_exits:
            ex_r = sum(e[0] for e in right_exits) / len(right_exits)
            ex_c = sum(e[1] for e in right_exits) / len(right_exits)
        for _ in range(n):
            for _try in range(20):
                r = random.randint(2, rows - 3)
                c = random.randint(cols // 5, cols - 3)
                if (r, c) not in walls:
                    break
            a = _Agent(float(c), float(r), ex_c, ex_r,
                       desired_speed=1.3 * (0.8 + 0.4 * rng()),
                       panic=0.2 + 0.3 * rng())
            agents.append(a)

    elif preset_id == "stadium":
        n = min(300, int(rows * cols * 0.10))
        cx, cy = cols // 2, rows // 2
        for _ in range(n):
            for _try in range(20):
                r = random.randint(2, rows - 3)
                c = random.randint(2, cols - 3)
                if (r, c) not in walls:
                    dx = c - cx
                    dy = r - cy
                    dist = (dx * dx / max(1, (cols // 2) ** 2) +
                            dy * dy / max(1, (rows // 2) ** 2))
                    if dist < 0.85:
                        break
            # Target nearest exit
            best_exit = min(exits, key=lambda e: (e[0] - r) ** 2 + (e[1] - c) ** 2)
            a = _Agent(float(c), float(r), float(best_exit[1]), float(best_exit[0]),
                       desired_speed=1.2 * (0.8 + 0.4 * rng()),
                       panic=0.15 + 0.2 * rng())
            agents.append(a)

    elif preset_id == "counterflow":
        n_per_side = min(80, int(rows * cols * 0.06))
        mid = rows // 2
        corridor_h = max(1, rows // 8)
        # Group 0: starts on left, targets right
        right_exits = [e for e in exits if e[2] == 0]
        left_exits = [e for e in exits if e[2] == 1]
        for _ in range(n_per_side):
            r = random.randint(mid - corridor_h + 1, mid + corridor_h - 1)
            c = random.randint(2, cols // 3)
            if right_exits:
                tgt = random.choice(right_exits)
            else:
                tgt = (mid, 0, 0)
            a = _Agent(float(c), float(r), float(tgt[1]), float(tgt[0]),
                       desired_speed=1.0 + 0.3 * rng(), group=0)
            agents.append(a)
        # Group 1: starts on right, targets left
        for _ in range(n_per_side):
            r = random.randint(mid - corridor_h + 1, mid + corridor_h - 1)
            c = random.randint(2 * cols // 3, cols - 3)
            if left_exits:
                tgt = random.choice(left_exits)
            else:
                tgt = (mid, cols - 1, 1)
            a = _Agent(float(c), float(r), float(tgt[1]), float(tgt[0]),
                       desired_speed=1.0 + 0.3 * rng(), group=1)
            agents.append(a)

    elif preset_id == "blackfriday":
        n = min(200, int(rows * cols * 0.10))
        for _ in range(n):
            r = random.randint(rows // 2, rows - 2)
            c = random.randint(2, cols - 3)
            a = _Agent(float(c), float(r), ex_c, ex_r,
                       desired_speed=1.8 * (0.8 + 0.4 * rng()),
                       panic=0.5 + 0.4 * rng())
            agents.append(a)

    return agents


# ══════════════════════════════════════════════════════════════════════
#  Social-force model
# ══════════════════════════════════════════════════════════════════════

def _crowd_compute_forces(self):
    """Compute social-force model accelerations for all agents."""
    agents = self.crowd_agents
    walls = self.crowd_walls
    rows = self.crowd_rows
    cols = self.crowd_cols
    dt = self.crowd_dt

    # Parameters
    tau = 0.5  # relaxation time
    A_agent = 2.0  # agent repulsion strength
    B_agent = 0.3  # agent repulsion range
    A_wall = 5.0   # wall repulsion strength
    B_wall = 0.2   # wall repulsion range
    panic_amplifier = 2.5  # extra force under panic

    for agent in agents:
        if agent.escaped:
            continue

        # ── Desired velocity force (driving term) ──
        dx = agent.target_x - agent.x
        dy = agent.target_y - agent.y
        dist_to_target = math.sqrt(dx * dx + dy * dy)
        if dist_to_target < 0.5:
            # Reached target (exit)
            agent.escaped = True
            continue

        # Desired direction
        ex = dx / dist_to_target
        ey = dy / dist_to_target

        # Panic increases desired speed
        v0 = agent.desired_speed * (1.0 + agent.panic * panic_amplifier)

        # Driving force
        fx = (v0 * ex - agent.vx) / tau
        fy = (v0 * ey - agent.vy) / tau

        # ── Agent-agent repulsion ──
        for other in agents:
            if other is agent or other.escaped:
                continue
            ox = agent.x - other.x
            oy = agent.y - other.y
            d = math.sqrt(ox * ox + oy * oy)
            r_sum = agent.radius + other.radius
            if d < 0.01:
                d = 0.01
                ox = random.random() - 0.5
                oy = random.random() - 0.5
            if d < 3.0:  # interaction cutoff
                nx = ox / d
                ny = oy / d
                overlap = r_sum - d
                # Exponential repulsion
                f_rep = A_agent * math.exp(overlap / B_agent)
                fx += f_rep * nx
                fy += f_rep * ny
                # Body force (physical contact)
                if overlap > 0:
                    k_body = 12.0
                    fx += k_body * overlap * nx
                    fy += k_body * overlap * ny
                    # Tangential friction
                    k_friction = 6.0
                    tx = -ny
                    ty = nx
                    dvt = (other.vx - agent.vx) * tx + (other.vy - agent.vy) * ty
                    fx += k_friction * overlap * dvt * tx
                    fy += k_friction * overlap * dvt * ty

        # ── Wall repulsion ──
        # Sample nearby wall cells
        ar, ac = int(round(agent.y)), int(round(agent.x))
        scan = 3
        for wr in range(max(0, ar - scan), min(rows, ar + scan + 1)):
            for wc in range(max(0, ac - scan), min(cols, ac + scan + 1)):
                if (wr, wc) not in walls:
                    continue
                wx = wc + 0.5 - agent.x
                wy = wr + 0.5 - agent.y
                d = math.sqrt(wx * wx + wy * wy)
                if d < 0.01:
                    d = 0.01
                if d < 3.0:
                    nx = -wx / d
                    ny = -wy / d
                    overlap = agent.radius - d + 0.5
                    f_rep = A_wall * math.exp(-d / B_wall)
                    fx += f_rep * nx
                    fy += f_rep * ny
                    if overlap > 0:
                        fx += 20.0 * overlap * nx
                        fy += 20.0 * overlap * ny

        # ── Noise (panic jitter) ──
        noise = agent.panic * 0.5
        fx += noise * (random.random() - 0.5)
        fy += noise * (random.random() - 0.5)

        # ── Update velocity and position ──
        agent.vx += fx * dt
        agent.vy += fy * dt

        # Clamp speed
        speed = math.sqrt(agent.vx ** 2 + agent.vy ** 2)
        max_speed = agent.desired_speed * (2.0 + agent.panic * 2.0)
        if speed > max_speed:
            agent.vx *= max_speed / speed
            agent.vy *= max_speed / speed

        # Position update
        new_x = agent.x + agent.vx * dt
        new_y = agent.y + agent.vy * dt

        # Boundary clamp
        new_x = max(0.5, min(cols - 0.5, new_x))
        new_y = max(0.5, min(rows - 0.5, new_y))

        # Wall collision: don't enter wall cells
        nr, nc = int(round(new_y)), int(round(new_x))
        if (nr, nc) in walls:
            new_x = agent.x
            new_y = agent.y
            agent.vx *= -0.3
            agent.vy *= -0.3

        agent.x = new_x
        agent.y = new_y

    # ── Panic contagion ──
    for agent in agents:
        if agent.escaped:
            continue
        for other in agents:
            if other is agent or other.escaped:
                continue
            dx = agent.x - other.x
            dy = agent.y - other.y
            d = math.sqrt(dx * dx + dy * dy)
            if d < 2.5:
                # Nearby panicked agent raises panic
                contagion = 0.01 * other.panic / max(d, 0.5)
                agent.panic = min(1.0, agent.panic + contagion)
        # Natural panic decay
        agent.panic = max(0.0, agent.panic - 0.002)


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _enter_crowd_mode(self):
    """Enter Crowd Dynamics mode — show preset menu."""
    self.crowd_menu = True
    self.crowd_menu_sel = 0
    self._flash("Crowd Dynamics & Evacuation — select a scenario")


def _exit_crowd_mode(self):
    """Exit Crowd Dynamics mode."""
    self.crowd_mode = False
    self.crowd_menu = False
    self.crowd_running = False
    self._flash("Crowd Dynamics mode OFF")


def _crowd_init(self, preset_idx: int):
    """Initialize crowd simulation with the given preset."""
    name, _desc, preset_id = self.CROWD_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()

    rows = max(10, max_y - 5)
    cols = max(15, max_x - 2)
    self.crowd_rows = rows
    self.crowd_cols = cols

    self.crowd_preset_name = name
    self.crowd_preset_id = preset_id
    self.crowd_generation = 0
    self.crowd_running = False
    self.crowd_menu = False
    self.crowd_mode = True

    self.crowd_dt = 0.1
    self.crowd_initial_count = 0
    self.crowd_escaped_count = 0
    self.crowd_max_density = 0.0
    self.crowd_avg_speed = 0.0
    self.crowd_avg_panic = 0.0
    self.crowd_flow_rate = 0.0

    # Escape history for flow rate calculation
    self.crowd_escape_times = []

    # Build environment
    self.crowd_walls, self.crowd_exits = _build_walls_and_exits(
        preset_id, rows, cols)
    self.crowd_agents = _spawn_agents(
        preset_id, rows, cols, self.crowd_walls, self.crowd_exits)
    self.crowd_initial_count = len(self.crowd_agents)

    # History for plots
    self.crowd_history = []  # (escaped_frac, avg_speed, avg_panic)


# ══════════════════════════════════════════════════════════════════════
#  Simulation step
# ══════════════════════════════════════════════════════════════════════

def _crowd_step(self):
    """Advance one simulation step."""
    _crowd_compute_forces(self)

    agents = self.crowd_agents
    active = [a for a in agents if not a.escaped]
    total = self.crowd_initial_count

    # Statistics
    if active:
        self.crowd_avg_speed = sum(
            math.sqrt(a.vx ** 2 + a.vy ** 2) for a in active) / len(active)
        self.crowd_avg_panic = sum(a.panic for a in active) / len(active)

        # Density: max agents in any 3x3 region
        rows, cols = self.crowd_rows, self.crowd_cols
        density_grid = [[0] * cols for _ in range(rows)]
        for a in active:
            r, c = int(a.y), int(a.x)
            if 0 <= r < rows and 0 <= c < cols:
                density_grid[r][c] += 1
        max_d = 0
        for r in range(rows - 2):
            for c in range(cols - 2):
                d = sum(density_grid[r + dr][c + dc]
                        for dr in range(3) for dc in range(3))
                if d > max_d:
                    max_d = d
        self.crowd_max_density = max_d
    else:
        self.crowd_avg_speed = 0.0
        self.crowd_avg_panic = 0.0
        self.crowd_max_density = 0

    escaped_now = sum(1 for a in agents if a.escaped)
    newly_escaped = escaped_now - self.crowd_escaped_count
    self.crowd_escaped_count = escaped_now

    # Track escape events for flow rate
    t = self.crowd_generation
    for _ in range(newly_escaped):
        self.crowd_escape_times.append(t)
    # Flow rate: escapes in last 50 steps
    recent = [et for et in self.crowd_escape_times if t - et < 50]
    self.crowd_flow_rate = len(recent) / 50.0 if t > 0 else 0.0

    escaped_frac = escaped_now / max(total, 1)
    self.crowd_history.append((escaped_frac, self.crowd_avg_speed, self.crowd_avg_panic))
    if len(self.crowd_history) > 2000:
        self.crowd_history = self.crowd_history[-2000:]

    self.crowd_generation += 1

    # Stop if everyone escaped
    if not active:
        self.crowd_running = False


# ══════════════════════════════════════════════════════════════════════
#  Key handling
# ══════════════════════════════════════════════════════════════════════

def _handle_crowd_menu_key(self, key: int) -> bool:
    """Handle input in Crowd Dynamics preset menu."""
    presets = self.CROWD_PRESETS
    if key == curses.KEY_DOWN or key == ord("j"):
        self.crowd_menu_sel = (self.crowd_menu_sel + 1) % len(presets)
    elif key == curses.KEY_UP or key == ord("k"):
        self.crowd_menu_sel = (self.crowd_menu_sel - 1) % len(presets)
    elif key in (10, 13, curses.KEY_ENTER):
        self._crowd_init(self.crowd_menu_sel)
    elif key == ord("q") or key == 27:
        self.crowd_menu = False
        self._flash("Crowd Dynamics mode cancelled")
    return True


def _handle_crowd_key(self, key: int) -> bool:
    """Handle input in active Crowd simulation."""
    if key == ord("q") or key == 27:
        self._exit_crowd_mode()
        return True
    if key == ord(" "):
        self.crowd_running = not self.crowd_running
        return True
    if key == ord("n") or key == ord("."):
        self._crowd_step()
        return True
    if key == ord("r"):
        idx = next(
            (i for i, p in enumerate(self.CROWD_PRESETS)
             if p[0] == self.crowd_preset_name), 0)
        self._crowd_init(idx)
        return True
    if key == ord("R") or key == ord("m"):
        self.crowd_mode = False
        self.crowd_running = False
        self.crowd_menu = True
        self.crowd_menu_sel = 0
        return True
    # Adjust panic globally
    if key == ord("p"):
        for a in self.crowd_agents:
            a.panic = min(1.0, a.panic + 0.1)
        self._flash("Panic increased!")
        return True
    if key == ord("P"):
        for a in self.crowd_agents:
            a.panic = max(0.0, a.panic - 0.1)
        self._flash("Panic decreased")
        return True
    # Adjust time step
    if key == ord("+") or key == ord("="):
        self.crowd_dt = min(0.5, self.crowd_dt * 1.3)
        self._flash(f"dt = {self.crowd_dt:.3f}")
        return True
    if key == ord("-"):
        self.crowd_dt = max(0.01, self.crowd_dt / 1.3)
        self._flash(f"dt = {self.crowd_dt:.3f}")
        return True
    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing
# ══════════════════════════════════════════════════════════════════════

def _draw_crowd_menu(self, max_y: int, max_x: int):
    """Draw the Crowd Dynamics preset selection menu."""
    self.stdscr.erase()
    title = "── Crowd Dynamics & Evacuation Simulation ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(self.CROWD_PRESETS):
        y = 4 + i * 2
        if y >= max_y - 6:
            break
        marker = "▸ " if i == self.crowd_menu_sel else "  "
        attr = curses.color_pair(3) | curses.A_BOLD if i == self.crowd_menu_sel else curses.color_pair(7)
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
            "Social-force model: agents feel driving, repulsive, and frictional forces.",
            "Emergent: lane formation, arch clogging, panic contagion, faster-is-slower.",
            "Watch for crowd crush near exits and self-organized flow patterns.",
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


def _draw_crowd(self, max_y: int, max_x: int):
    """Draw the active Crowd simulation."""
    self.stdscr.erase()
    state = "▶ RUNNING" if self.crowd_running else "⏸ PAUSED"
    active = sum(1 for a in self.crowd_agents if not a.escaped)
    escaped = self.crowd_escaped_count
    total = self.crowd_initial_count

    title = (f" Crowd: {self.crowd_preset_name}  |  "
             f"agents={active}/{total}  escaped={escaped}"
             f"  step={self.crowd_generation}  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    _draw_crowd_field(self, max_y, max_x)

    # Info bar
    info_y = max_y - 2
    if info_y > 1:
        info = (f" speed={self.crowd_avg_speed:.2f}"
                f"  panic={self.crowd_avg_panic:.2f}"
                f"  density={self.crowd_max_density}"
                f"  flow={self.crowd_flow_rate:.2f}/step"
                f"  dt={self.crowd_dt:.3f}")
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
            hint = " [Space]=play [n]=step [p/P]=±panic [+/-]=dt [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_crowd_field(self, max_y: int, max_x: int):
    """Draw the crowd field: walls, exits, and agents."""
    rows = self.crowd_rows
    cols = self.crowd_cols
    walls = self.crowd_walls
    exits_set = set((e[0], e[1]) for e in self.crowd_exits)
    agents = self.crowd_agents

    disp_rows = max_y - 4
    disp_cols = max_x - 1
    row_scale = max(1, (rows + disp_rows - 1) // disp_rows)
    col_scale = max(1, (cols + disp_cols - 1) // disp_cols)

    # Build agent density grid for rendering
    agent_grid = [[0.0] * cols for _ in range(rows)]
    panic_grid = [[0.0] * cols for _ in range(rows)]
    group_grid = [[-1] * cols for _ in range(rows)]
    for a in agents:
        if a.escaped:
            continue
        r = int(round(a.y))
        c = int(round(a.x))
        if 0 <= r < rows and 0 <= c < cols:
            agent_grid[r][c] += 1.0
            panic_grid[r][c] = max(panic_grid[r][c], a.panic)
            group_grid[r][c] = a.group

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

            # Walls
            if (r, c) in walls:
                try:
                    self.stdscr.addstr(screen_y, sx, "█",
                                       curses.color_pair(7) | curses.A_DIM)
                except curses.error:
                    pass
                continue

            # Exits
            if (r, c) in exits_set:
                try:
                    self.stdscr.addstr(screen_y, sx, "▒",
                                       curses.color_pair(3))
                except curses.error:
                    pass
                continue

            # Agents
            density = agent_grid[r][c]
            if density > 0:
                panic = panic_grid[r][c]
                group = group_grid[r][c]

                if density >= 3:
                    ch = "█"
                elif density >= 2:
                    ch = "▓"
                else:
                    ch = "●"

                # Color: red for high panic, blue/cyan for group 0,
                # green for group 1, white for low panic
                if panic > 0.6:
                    color = 1  # red
                    attr = curses.color_pair(color) | curses.A_BOLD
                elif panic > 0.3:
                    color = 5  # magenta/yellow
                    attr = curses.color_pair(color)
                elif group == 1:
                    color = 2  # green
                    attr = curses.color_pair(color)
                else:
                    color = 4  # blue/cyan
                    attr = curses.color_pair(color)

                if density >= 3:
                    attr |= curses.A_BOLD

                try:
                    self.stdscr.addstr(screen_y, sx, ch, attr)
                except curses.error:
                    pass
            # else: empty space, leave blank


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register crowd dynamics mode methods on the App class."""
    App.CROWD_PRESETS = CROWD_PRESETS
    App._enter_crowd_mode = _enter_crowd_mode
    App._exit_crowd_mode = _exit_crowd_mode
    App._crowd_init = _crowd_init
    App._crowd_compute_forces = _crowd_compute_forces
    App._crowd_step = _crowd_step
    App._handle_crowd_menu_key = _handle_crowd_menu_key
    App._handle_crowd_key = _handle_crowd_key
    App._draw_crowd_menu = _draw_crowd_menu
    App._draw_crowd = _draw_crowd
    App._draw_crowd_field = _draw_crowd_field
