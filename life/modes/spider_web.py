"""Mode: sweb — Spider Orb Web Construction & Prey Capture.

An orb-weaving spider builds its web in real time — laying radial frame threads,
then spiraling sticky capture silk — then prey insects blunder into the web,
triggering vibration waves that propagate through the silk network.  The spider
detects vibration direction/intensity to locate and rush toward trapped prey.
Wind gusts deform the elastic web structure, damaged sections get repaired, and
web geometry adapts to repeated prey capture patterns.

Emergent phenomena:
  - Structural web construction: frame → radii → auxiliary spiral → sticky spiral
  - Vibration propagation through thread network
  - Prey flight & capture with glue droplets on spiral threads
  - Wind deformation of elastic thread network
  - Web repair & adaptation toward high-capture zones
  - Silk reserve management across different silk types
"""
import curses
import math
import random
import time


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

SWEB_PRESETS = [
    ("Garden Orb Weaver",
     "Classic orb web in a sheltered garden — moderate wind, steady insect flow",
     "garden"),
    ("Morning Dew Web",
     "Calm dawn conditions — dew droplets glisten on silk, low wind, slow prey",
     "dew"),
    ("Storm Damage & Repair",
     "Fierce gusts shred the web — watch the spider rebuild damaged sectors",
     "storm"),
    ("Prey Bonanza",
     "Insect swarm event — rapid captures overwhelm web, silk reserves depleted",
     "bonanza"),
    ("Cobweb Tangle Weaver",
     "Irregular 3D tangle web — no neat spiral, sticky lines in all directions",
     "tangle"),
    ("Golden Silk Orbweaver",
     "Nephila-style giant web — extra-strong golden dragline, wide capture area",
     "golden"),
]


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

# Silk types
SILK_FRAME = 0      # dragline — strong, non-sticky
SILK_RADIAL = 1     # radii from hub — strong, non-sticky
SILK_AUX = 2        # auxiliary spiral (temporary scaffold)
SILK_STICKY = 3     # capture spiral — elastic, has glue droplets

_SILK_NAMES = ["Frame", "Radial", "Auxiliary", "Sticky"]

# Thread states
THREAD_OK = 0
THREAD_STRESSED = 1
THREAD_BROKEN = 2

# Spider states
SP_BUILDING_FRAME = 0
SP_BUILDING_RADII = 1
SP_BUILDING_AUX = 2
SP_BUILDING_STICKY = 3
SP_WAITING = 4
SP_RUSHING = 5
SP_WRAPPING = 6
SP_REPAIRING = 7
SP_RESTING = 8

_STATE_NAMES = ["Building Frame", "Building Radii", "Building Aux Spiral",
                "Building Sticky Spiral", "Waiting", "Rushing to Prey",
                "Wrapping Prey", "Repairing Web", "Resting"]

# Prey types
PREY_MOTH = 0
PREY_FLY = 1
PREY_MOSQUITO = 2
PREY_BEETLE = 3
PREY_BUTTERFLY = 4

_PREY_NAMES = ["Moth", "Fly", "Mosquito", "Beetle", "Butterfly"]
_PREY_GLYPHS = ["m", "f", ":", "B", "W"]
_PREY_STRUGGLE = [0.7, 0.5, 0.3, 0.9, 0.4]  # initial struggle intensity
_PREY_MASS = [0.6, 0.3, 0.1, 0.8, 0.4]


# ══════════════════════════════════════════════════════════════════════
#  Data classes
# ══════════════════════════════════════════════════════════════════════

class _Thread:
    """A single silk thread segment between two nodes."""
    __slots__ = ('n0', 'n1', 'silk_type', 'strength', 'elasticity',
                 'tension', 'state', 'vibration', 'age')

    def __init__(self, n0, n1, silk_type):
        self.n0 = n0  # index into nodes list
        self.n1 = n1
        self.silk_type = silk_type
        self.tension = 0.0
        self.vibration = 0.0
        self.age = 0
        self.state = THREAD_OK
        if silk_type == SILK_FRAME:
            self.strength = 1.0
            self.elasticity = 0.3
        elif silk_type == SILK_RADIAL:
            self.strength = 0.8
            self.elasticity = 0.4
        elif silk_type == SILK_AUX:
            self.strength = 0.4
            self.elasticity = 0.2
        elif silk_type == SILK_STICKY:
            self.strength = 0.5
            self.elasticity = 0.8


class _Node:
    """A junction point in the web where threads meet."""
    __slots__ = ('x', 'y', 'rest_x', 'rest_y', 'vx', 'vy',
                 'anchor', 'vibration')

    def __init__(self, x, y, anchor=False):
        self.x = x
        self.y = y
        self.rest_x = x
        self.rest_y = y
        self.vx = 0.0
        self.vy = 0.0
        self.anchor = anchor  # frame anchor points don't move
        self.vibration = 0.0


class _Prey:
    """An insect that may fly freely or be trapped in the web."""
    __slots__ = ('x', 'y', 'vx', 'vy', 'kind', 'trapped', 'struggle',
                 'wrapped', 'node_idx', 'alive')

    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        angle = random.random() * 2 * math.pi
        speed = 0.3 + random.random() * 0.5
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.kind = kind
        self.trapped = False
        self.struggle = _PREY_STRUGGLE[kind]
        self.wrapped = 0.0  # 0=free, 1=fully wrapped
        self.node_idx = -1
        self.alive = True


class _Spider:
    """The orb-weaving spider."""
    __slots__ = ('x', 'y', 'state', 'target_node', 'silk_reserve',
                 'energy', 'build_progress', 'captures', 'target_prey',
                 'repair_list', 'capture_zones')

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.state = SP_BUILDING_FRAME
        self.target_node = -1
        self.silk_reserve = 100.0
        self.energy = 1.0
        self.build_progress = 0  # tracks which step of construction
        self.captures = 0
        self.target_prey = -1
        self.repair_list = []     # thread indices that need repair
        self.capture_zones = {}   # angle_bin → capture_count


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_sweb_mode(self):
    """Enter spider web mode — show preset menu."""
    self.sweb_mode = True
    self.sweb_menu = True
    self.sweb_menu_sel = 0


def _exit_sweb_mode(self):
    """Exit spider web mode."""
    self.sweb_mode = False
    self.sweb_menu = False
    self.sweb_running = False
    for attr in list(vars(self)):
        if attr.startswith('sweb_') and attr not in ('sweb_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _sweb_init(self, preset_idx: int):
    """Initialize spider web simulation for the chosen preset."""
    name, _desc, pid = SWEB_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(20, max_y - 4)
    cols = max(40, max_x - 2)

    self.sweb_menu = False
    self.sweb_running = False
    self.sweb_preset_name = name
    self.sweb_preset_id = pid
    self.sweb_rows = rows
    self.sweb_cols = cols
    self.sweb_generation = 0
    self.sweb_speed = 1
    self.sweb_view = "web"   # web | vibration | graphs

    # Web center
    cx = cols / 2.0
    cy = rows / 2.0
    self.sweb_cx = cx
    self.sweb_cy = cy

    # Web radius
    self.sweb_radius = min(rows, cols) * 0.40

    # Wind
    self.sweb_wind_x = 0.0
    self.sweb_wind_y = 0.0
    self.sweb_wind_strength = 0.0
    self.sweb_wind_gust_timer = 0

    # Nodes and threads
    self.sweb_nodes = []
    self.sweb_threads = []

    # Prey
    self.sweb_prey = []
    self.sweb_prey_rate = 0.02  # probability per tick of new prey

    # Spider
    self.sweb_spider = _Spider(cx, cy)

    # History for graphs
    self.sweb_capture_history = []
    self.sweb_integrity_history = []
    self.sweb_silk_history = []
    self.sweb_prey_count_history = []

    # Construction state
    self.sweb_num_radii = 24
    self.sweb_spiral_spacing = 1.2
    self.sweb_build_phase = 0  # 0=frame, 1=radii, 2=aux, 3=sticky, 4=done
    self.sweb_build_step = 0

    # Preset tuning
    if pid == "storm":
        self.sweb_wind_strength = 0.5
        self.sweb_prey_rate = 0.015
    elif pid == "bonanza":
        self.sweb_prey_rate = 0.08
        self.sweb_wind_strength = 0.05
    elif pid == "dew":
        self.sweb_wind_strength = 0.01
        self.sweb_prey_rate = 0.01
    elif pid == "tangle":
        self.sweb_num_radii = 40
        self.sweb_spiral_spacing = 0.8
        self.sweb_prey_rate = 0.025
    elif pid == "golden":
        self.sweb_radius = min(rows, cols) * 0.48
        self.sweb_num_radii = 32
        self.sweb_spider.silk_reserve = 150.0
        self.sweb_prey_rate = 0.03

    # Build the initial web structure
    _sweb_build_web(self, pid)
    self._flash(f"Spider Web: {name}")


def _sweb_build_web(self, pid):
    """Build the orb web structure — frame, radii, spirals."""
    nodes = self.sweb_nodes
    threads = self.sweb_threads
    cx = self.sweb_cx
    cy = self.sweb_cy
    radius = self.sweb_radius
    n_radii = self.sweb_num_radii

    nodes.clear()
    threads.clear()

    # Hub node (center)
    hub = _Node(cx, cy)
    nodes.append(hub)

    # Frame anchor points (rectangular frame around web)
    frame_margin = radius * 1.15
    anchors = [
        _Node(cx - frame_margin, cy - frame_margin * 0.6, anchor=True),
        _Node(cx + frame_margin, cy - frame_margin * 0.6, anchor=True),
        _Node(cx + frame_margin, cy + frame_margin * 0.6, anchor=True),
        _Node(cx - frame_margin, cy + frame_margin * 0.6, anchor=True),
    ]
    anchor_start = len(nodes)
    for a in anchors:
        nodes.append(a)

    # Frame threads (connect anchors in rectangle)
    for i in range(4):
        j = (i + 1) % 4
        threads.append(_Thread(anchor_start + i, anchor_start + j, SILK_FRAME))

    # Radial threads from hub to frame
    radial_tips = []
    for i in range(n_radii):
        angle = 2 * math.pi * i / n_radii
        # Tip at the frame intersection
        tip_x = cx + radius * math.cos(angle)
        tip_y = cy + radius * math.sin(angle)
        tip = _Node(tip_x, tip_y)
        tip_idx = len(nodes)
        nodes.append(tip)
        radial_tips.append(tip_idx)

        # Connect hub to tip
        threads.append(_Thread(0, tip_idx, SILK_RADIAL))

        # Connect tip to nearest frame anchor
        nearest_anchor = anchor_start
        best_dist = float('inf')
        for ai in range(4):
            a = nodes[anchor_start + ai]
            d = math.hypot(a.x - tip_x, a.y - tip_y)
            if d < best_dist:
                best_dist = d
                nearest_anchor = anchor_start + ai
        threads.append(_Thread(tip_idx, nearest_anchor, SILK_FRAME))

    # Intermediate radial nodes (for spiral attachment)
    # Create nodes along each radius at regular intervals
    n_rings = max(3, int(radius / self.sweb_spiral_spacing))
    self.sweb_radial_nodes = []  # [ring][radial] = node_idx
    for ring in range(n_rings):
        ring_frac = (ring + 1) / (n_rings + 1)
        ring_r = radius * ring_frac
        ring_nodes = []
        for ri in range(n_radii):
            angle = 2 * math.pi * ri / n_radii
            nx = cx + ring_r * math.cos(angle)
            ny = cy + ring_r * math.sin(angle)
            n_idx = len(nodes)
            nodes.append(_Node(nx, ny))
            ring_nodes.append(n_idx)
        self.sweb_radial_nodes.append(ring_nodes)

    # Connect radial intermediate nodes along each radius
    for ri in range(n_radii):
        prev = 0  # hub
        for ring in range(n_rings):
            cur = self.sweb_radial_nodes[ring][ri]
            threads.append(_Thread(prev, cur, SILK_RADIAL))
            prev = cur
        # Connect last ring node to tip
        threads.append(_Thread(prev, radial_tips[ri], SILK_RADIAL))

    # Auxiliary spiral (inner region, non-sticky)
    inner_rings = max(1, n_rings // 4)
    for ring in range(inner_rings):
        for ri in range(n_radii):
            ri_next = (ri + 1) % n_radii
            n0 = self.sweb_radial_nodes[ring][ri]
            n1 = self.sweb_radial_nodes[ring][ri_next]
            threads.append(_Thread(n0, n1, SILK_AUX))

    # Sticky capture spiral (outer region)
    for ring in range(inner_rings, n_rings):
        for ri in range(n_radii):
            ri_next = (ri + 1) % n_radii
            n0 = self.sweb_radial_nodes[ring][ri]
            n1 = self.sweb_radial_nodes[ring][ri_next]
            threads.append(_Thread(n0, n1, SILK_STICKY))

    # Tangle weaver: add extra random cross-threads
    if pid == "tangle":
        for _ in range(n_radii * 2):
            a = random.randint(0, len(nodes) - 1)
            b = random.randint(0, len(nodes) - 1)
            if a != b:
                d = math.hypot(nodes[a].x - nodes[b].x,
                               nodes[a].y - nodes[b].y)
                if d < radius * 0.5:
                    threads.append(_Thread(a, b, SILK_STICKY))

    self.sweb_build_phase = 4  # construction complete
    self.sweb_spider.state = SP_WAITING

    # Build adjacency for vibration propagation
    _sweb_build_adjacency(self)


def _sweb_build_adjacency(self):
    """Build node→thread adjacency for fast vibration lookup."""
    n = len(self.sweb_nodes)
    adj = [[] for _ in range(n)]
    for ti, t in enumerate(self.sweb_threads):
        if t.state != THREAD_BROKEN:
            adj[t.n0].append((ti, t.n1))
            adj[t.n1].append((ti, t.n0))
    self.sweb_adj = adj


# ══════════════════════════════════════════════════════════════════════
#  Simulation step
# ══════════════════════════════════════════════════════════════════════

def _sweb_step(self):
    """Advance spider web simulation by one tick."""
    nodes = self.sweb_nodes
    threads = self.sweb_threads
    spider = self.sweb_spider
    prey_list = self.sweb_prey
    pid = self.sweb_preset_id
    rows = self.sweb_rows
    cols = self.sweb_cols
    gen = self.sweb_generation

    # ── 1. Wind ──
    _sweb_update_wind(self, gen, pid)

    # ── 2. Physics: thread tension, node displacement ──
    _sweb_physics(self)

    # ── 3. Vibration propagation ──
    _sweb_propagate_vibration(self)

    # ── 4. Spawn prey ──
    if random.random() < self.sweb_prey_rate:
        _sweb_spawn_prey(self)

    # ── 5. Update prey (flight / struggle) ──
    _sweb_update_prey(self)

    # ── 6. Spider behavior ──
    _sweb_update_spider(self)

    # ── 7. Thread degradation / breakage ──
    _sweb_check_threads(self)

    # ── 8. Record history ──
    total_threads = len(threads)
    ok_threads = sum(1 for t in threads if t.state == THREAD_OK)
    integrity = ok_threads / max(1, total_threads)
    trapped = sum(1 for p in prey_list if p.trapped and p.alive)

    self.sweb_capture_history.append(spider.captures)
    self.sweb_integrity_history.append(integrity)
    self.sweb_silk_history.append(spider.silk_reserve)
    self.sweb_prey_count_history.append(trapped)
    for hist in (self.sweb_capture_history, self.sweb_integrity_history,
                 self.sweb_silk_history, self.sweb_prey_count_history):
        if len(hist) > 200:
            hist.pop(0)

    # Clean up dead/escaped prey
    self.sweb_prey = [p for p in prey_list if p.alive and
                      0 <= p.x <= cols and 0 <= p.y <= rows]

    self.sweb_generation += 1


def _sweb_update_wind(self, gen, pid):
    """Update wind vector — gusts and steady component."""
    base_strength = self.sweb_wind_strength
    # Sinusoidal base + random gusts
    wx = base_strength * math.sin(gen * 0.02) * 0.5
    wy = base_strength * math.cos(gen * 0.015) * 0.3

    # Random gusts
    self.sweb_wind_gust_timer -= 1
    if self.sweb_wind_gust_timer <= 0:
        if random.random() < 0.03:
            # Start a gust
            self.sweb_wind_gust_timer = random.randint(10, 40)
            gust_angle = random.random() * 2 * math.pi
            gust_str = base_strength * (1.5 + random.random() * 2.0)
            if pid == "storm":
                gust_str *= 2.0
            wx += math.cos(gust_angle) * gust_str
            wy += math.sin(gust_angle) * gust_str

    self.sweb_wind_x = wx
    self.sweb_wind_y = wy


def _sweb_physics(self):
    """Update node positions based on thread tension and wind."""
    nodes = self.sweb_nodes
    threads = self.sweb_threads
    wind_x = self.sweb_wind_x
    wind_y = self.sweb_wind_y

    damping = 0.85
    restore = 0.05  # spring back toward rest position

    for node in nodes:
        if node.anchor:
            continue
        # Wind force
        node.vx += wind_x * 0.01
        node.vy += wind_y * 0.01
        # Restore toward rest position
        dx = node.rest_x - node.x
        dy = node.rest_y - node.y
        node.vx += dx * restore
        node.vy += dy * restore

    # Thread spring forces
    for t in threads:
        if t.state == THREAD_BROKEN:
            continue
        n0 = nodes[t.n0]
        n1 = nodes[t.n1]
        dx = n1.x - n0.x
        dy = n1.y - n0.y
        dist = math.hypot(dx, dy)
        if dist < 0.01:
            continue
        rest_dist = math.hypot(n1.rest_x - n0.rest_x, n1.rest_y - n0.rest_y)
        stretch = dist - rest_dist
        t.tension = abs(stretch) / max(0.1, rest_dist)

        # Spring force
        k = 0.02 * (1.0 + t.elasticity)
        fx = k * stretch * dx / dist
        fy = k * stretch * dy / dist
        if not n0.anchor:
            n0.vx += fx
            n0.vy += fy
        if not n1.anchor:
            n1.vx -= fx
            n1.vy -= fy

    # Integrate
    for node in nodes:
        if node.anchor:
            continue
        node.vx *= damping
        node.vy *= damping
        node.x += node.vx
        node.y += node.vy


def _sweb_propagate_vibration(self):
    """Propagate vibration waves through the thread network."""
    nodes = self.sweb_nodes
    threads = self.sweb_threads

    # Decay existing vibrations
    for node in nodes:
        node.vibration *= 0.85
    for t in threads:
        t.vibration *= 0.80

    # Propagate from nodes to connected threads and vice versa
    if not hasattr(self, 'sweb_adj'):
        return
    adj = self.sweb_adj
    for ni, node in enumerate(nodes):
        if node.vibration > 0.01:
            for ti, neighbor in adj[ni]:
                t = threads[ti]
                if t.state == THREAD_BROKEN:
                    continue
                # Transfer vibration along thread (attenuated by distance)
                n_other = nodes[neighbor]
                dist = math.hypot(node.x - n_other.x, node.y - n_other.y)
                atten = max(0.1, 1.0 - dist * 0.02)
                transfer = node.vibration * 0.3 * atten
                t.vibration = max(t.vibration, transfer)
                n_other.vibration = max(n_other.vibration,
                                        transfer * 0.5)


def _sweb_spawn_prey(self):
    """Spawn a new prey insect at a random edge."""
    rows = self.sweb_rows
    cols = self.sweb_cols
    side = random.randint(0, 3)
    if side == 0:      # top
        x, y = random.random() * cols, 0
    elif side == 1:    # right
        x, y = cols, random.random() * rows
    elif side == 2:    # bottom
        x, y = random.random() * cols, rows
    else:              # left
        x, y = 0, random.random() * rows

    kind = random.choices(range(5), weights=[3, 4, 3, 1, 1])[0]
    self.sweb_prey.append(_Prey(x, y, kind))


def _sweb_update_prey(self):
    """Update prey: fly, check web collision, struggle."""
    nodes = self.sweb_nodes
    threads = self.sweb_threads
    cx = self.sweb_cx
    cy = self.sweb_cy

    for prey in self.sweb_prey:
        if not prey.alive:
            continue

        if prey.trapped:
            # Struggle: vibrate the web
            if prey.struggle > 0.01 and prey.wrapped < 1.0:
                prey.struggle *= 0.995
                # Generate vibration at trap location
                if 0 <= prey.node_idx < len(nodes):
                    nodes[prey.node_idx].vibration = max(
                        nodes[prey.node_idx].vibration,
                        prey.struggle * 0.8)
            continue

        # Free flight — move toward web area with some randomness
        prey.vx += (random.random() - 0.5) * 0.15
        prey.vy += (random.random() - 0.5) * 0.15
        # Slight attraction toward light (center-ish)
        dx = cx - prey.x
        dy = cy - prey.y
        dist = math.hypot(dx, dy)
        if dist > 1:
            prey.vx += dx / dist * 0.01
            prey.vy += dy / dist * 0.01
        # Speed limit
        speed = math.hypot(prey.vx, prey.vy)
        if speed > 1.0:
            prey.vx /= speed
            prey.vy /= speed
        prey.x += prey.vx
        prey.y += prey.vy

        # Wind pushes prey too
        prey.x += self.sweb_wind_x * 0.005
        prey.y += self.sweb_wind_y * 0.005

        # Check collision with sticky threads
        for ti, t in enumerate(threads):
            if t.state == THREAD_BROKEN or t.silk_type != SILK_STICKY:
                continue
            n0 = nodes[t.n0]
            n1 = nodes[t.n1]
            # Point-to-segment distance
            d = _point_seg_dist(prey.x, prey.y, n0.x, n0.y, n1.x, n1.y)
            if d < 0.8:
                # Caught!
                prey.trapped = True
                prey.vx = 0
                prey.vy = 0
                # Snap to nearest node
                d0 = math.hypot(prey.x - n0.x, prey.y - n0.y)
                d1 = math.hypot(prey.x - n1.x, prey.y - n1.y)
                prey.node_idx = t.n0 if d0 < d1 else t.n1
                node = nodes[prey.node_idx]
                prey.x = node.x
                prey.y = node.y
                # Initial vibration burst
                node.vibration = max(node.vibration,
                                     _PREY_MASS[prey.kind] * 1.5)
                break

        # Escape if off-screen
        if (prey.x < -5 or prey.x > self.sweb_cols + 5 or
                prey.y < -5 or prey.y > self.sweb_rows + 5):
            prey.alive = False


def _point_seg_dist(px, py, ax, ay, bx, by):
    """Distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    dx = bx - ax
    dy = by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 0.001:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _sweb_update_spider(self):
    """Spider AI: detect vibrations, rush to prey, wrap, repair."""
    spider = self.sweb_spider
    nodes = self.sweb_nodes
    threads = self.sweb_threads
    prey_list = self.sweb_prey
    cx = self.sweb_cx
    cy = self.sweb_cy

    if spider.state == SP_WAITING:
        # Check for vibrations — find strongest vibrating node
        max_vib = 0.05
        max_node = -1
        for ni, node in enumerate(nodes):
            if node.vibration > max_vib:
                max_vib = node.vibration
                max_node = ni

        if max_node >= 0:
            # Check if there's trapped prey near that node
            target_prey_idx = -1
            for pi, prey in enumerate(prey_list):
                if prey.trapped and prey.alive and prey.wrapped < 0.9:
                    if prey.node_idx == max_node or (
                        math.hypot(prey.x - nodes[max_node].x,
                                   prey.y - nodes[max_node].y) < 3):
                        target_prey_idx = pi
                        break
            if target_prey_idx >= 0:
                spider.state = SP_RUSHING
                spider.target_prey = target_prey_idx
                spider.target_node = prey_list[target_prey_idx].node_idx

        # Check for broken threads to repair
        if spider.state == SP_WAITING and spider.silk_reserve > 5:
            broken = [ti for ti, t in enumerate(threads)
                      if t.state == THREAD_BROKEN]
            if broken:
                spider.repair_list = broken[:3]
                spider.state = SP_REPAIRING
                spider.target_node = threads[broken[0]].n0

        # Silk regeneration while waiting
        spider.silk_reserve = min(150.0, spider.silk_reserve + 0.05)
        spider.energy = min(1.0, spider.energy + 0.002)

    elif spider.state == SP_RUSHING:
        # Move toward target prey
        if 0 <= spider.target_prey < len(prey_list):
            prey = prey_list[spider.target_prey]
            if prey.alive and prey.trapped:
                dx = prey.x - spider.x
                dy = prey.y - spider.y
                dist = math.hypot(dx, dy)
                if dist < 1.0:
                    spider.state = SP_WRAPPING
                else:
                    speed = min(1.5, dist * 0.3)
                    spider.x += dx / dist * speed
                    spider.y += dy / dist * speed
                    spider.energy -= 0.003
            else:
                spider.state = SP_WAITING
                spider.target_prey = -1
        else:
            spider.state = SP_WAITING

    elif spider.state == SP_WRAPPING:
        if 0 <= spider.target_prey < len(prey_list):
            prey = prey_list[spider.target_prey]
            if prey.alive and prey.trapped:
                prey.wrapped = min(1.0, prey.wrapped + 0.05)
                prey.struggle *= 0.9
                spider.silk_reserve -= 0.3
                spider.energy -= 0.002
                if prey.wrapped >= 1.0:
                    spider.captures += 1
                    spider.energy = min(1.0, spider.energy + 0.2)
                    # Record capture zone for adaptation
                    angle = math.atan2(prey.y - cy, prey.x - cx)
                    zone_bin = int((angle + math.pi) / (2 * math.pi) * 8) % 8
                    spider.capture_zones[zone_bin] = (
                        spider.capture_zones.get(zone_bin, 0) + 1)
                    spider.state = SP_WAITING
                    spider.target_prey = -1
            else:
                spider.state = SP_WAITING
                spider.target_prey = -1
        else:
            spider.state = SP_WAITING

    elif spider.state == SP_REPAIRING:
        if spider.repair_list and spider.silk_reserve > 2:
            ti = spider.repair_list[0]
            if ti < len(threads):
                t = threads[ti]
                # Move toward the broken thread
                n0 = nodes[t.n0]
                mid_x = n0.x
                mid_y = n0.y
                dx = mid_x - spider.x
                dy = mid_y - spider.y
                dist = math.hypot(dx, dy)
                if dist < 1.5:
                    # Repair it
                    t.state = THREAD_OK
                    t.strength = max(0.3, t.strength * 0.7)  # patched, weaker
                    t.tension = 0.0
                    spider.silk_reserve -= 3.0
                    spider.repair_list.pop(0)
                    _sweb_build_adjacency(self)
                else:
                    speed = min(1.2, dist * 0.25)
                    spider.x += dx / dist * speed
                    spider.y += dy / dist * speed
                    spider.energy -= 0.002
            else:
                spider.repair_list.pop(0)
        else:
            spider.state = SP_WAITING
            spider.repair_list = []

        # Return to hub after repairs
        if not spider.repair_list:
            spider.state = SP_WAITING

    elif spider.state == SP_RESTING:
        spider.energy = min(1.0, spider.energy + 0.005)
        spider.silk_reserve = min(150.0, spider.silk_reserve + 0.1)
        if spider.energy > 0.5:
            spider.state = SP_WAITING

    # Low energy → rest
    if spider.energy < 0.1 and spider.state not in (SP_RESTING,):
        spider.state = SP_RESTING
        # Move back toward hub
        dx = cx - spider.x
        dy = cy - spider.y
        dist = math.hypot(dx, dy)
        if dist > 1:
            spider.x += dx / dist * 0.5
            spider.y += dy / dist * 0.5


def _sweb_check_threads(self):
    """Check for thread breakage from tension/wind/age."""
    threads = self.sweb_threads
    pid = self.sweb_preset_id
    rebuilt = False

    for t in threads:
        if t.state == THREAD_BROKEN:
            continue
        t.age += 1

        # Stress from tension
        if t.tension > t.strength * 0.7:
            t.state = THREAD_STRESSED

        # Break under extreme tension or old age
        break_chance = 0.0
        if t.tension > t.strength:
            break_chance += 0.05 * (t.tension - t.strength) / max(0.01, t.strength)
        if pid == "storm":
            break_chance += 0.002
        if t.age > 500 and t.silk_type == SILK_STICKY:
            break_chance += 0.001  # sticky silk degrades
        if t.state == THREAD_STRESSED:
            break_chance += 0.005

        if random.random() < break_chance:
            t.state = THREAD_BROKEN
            rebuilt = True

    if rebuilt:
        _sweb_build_adjacency(self)


# ══════════════════════════════════════════════════════════════════════
#  Key handlers
# ══════════════════════════════════════════════════════════════════════

def _handle_sweb_menu_key(self, key: int) -> bool:
    """Handle key input in the preset selection menu."""
    n = len(SWEB_PRESETS)
    if key == ord("q") or key == 27:
        self.sweb_mode = False
        self.sweb_menu = False
        return True
    if key == curses.KEY_UP or key == ord("k"):
        self.sweb_menu_sel = (self.sweb_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.sweb_menu_sel = (self.sweb_menu_sel + 1) % n
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _sweb_init(self, self.sweb_menu_sel)
        return True
    return True


def _handle_sweb_key(self, key: int) -> bool:
    """Handle key input during simulation."""
    if key == ord(" "):
        self.sweb_running = not self.sweb_running
        self._flash("Running" if self.sweb_running else "Paused")
        return True

    if key == ord("n") or key == ord("."):
        _sweb_step(self)
        return True

    if key == ord("v"):
        views = ["web", "vibration", "graphs"]
        cur = views.index(self.sweb_view) if self.sweb_view in views else 0
        self.sweb_view = views[(cur + 1) % len(views)]
        self._flash(f"View: {self.sweb_view}")
        return True

    if key == ord("+") or key == ord("="):
        self.sweb_speed = min(20, self.sweb_speed + 1)
        self._flash(f"Speed: {self.sweb_speed}x")
        return True

    if key == ord("-") or key == ord("_"):
        self.sweb_speed = max(1, self.sweb_speed - 1)
        self._flash(f"Speed: {self.sweb_speed}x")
        return True

    if key == ord("r"):
        idx = next((i for i, p in enumerate(SWEB_PRESETS)
                     if p[0] == self.sweb_preset_name), 0)
        _sweb_init(self, idx)
        return True

    if key == ord("R") or key == ord("m"):
        self.sweb_running = False
        self.sweb_menu = True
        self.sweb_menu_sel = 0
        return True

    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing — menu
# ══════════════════════════════════════════════════════════════════════

def _draw_sweb_menu(self, max_y: int, max_x: int):
    """Draw the preset selection menu."""
    self.stdscr.erase()

    title = "── Spider Orb Web Construction & Prey Capture ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2),
                           title[:max_x - 1],
                           curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(SWEB_PRESETS):
        y = 4 + i * 3
        if y >= max_y - 6:
            break
        marker = "▸ " if i == self.sweb_menu_sel else "  "
        attr = (curses.color_pair(3) | curses.A_BOLD
                if i == self.sweb_menu_sel
                else curses.color_pair(7))
        try:
            self.stdscr.addstr(y, 3, f"{marker}{name}"[:max_x - 4], attr)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    hints = " [↑/↓] Navigate   [Enter] Select   [q/Esc] Back"
    hy = max_y - 2
    if 0 < hy < max_y:
        try:
            self.stdscr.addstr(hy, 2, hints[:max_x - 4],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — main dispatcher
# ══════════════════════════════════════════════════════════════════════

def _draw_sweb(self, max_y: int, max_x: int):
    """Draw the active spider web simulation."""
    self.stdscr.erase()

    spider = self.sweb_spider
    n_trapped = sum(1 for p in self.sweb_prey if p.trapped and p.alive)
    ok_threads = sum(1 for t in self.sweb_threads if t.state == THREAD_OK)
    total_threads = max(1, len(self.sweb_threads))
    integrity = int(100 * ok_threads / total_threads)

    title = (f" Spider Web: {self.sweb_preset_name}"
             f" | t={self.sweb_generation}"
             f" | captures={spider.captures}"
             f" | trapped={n_trapped}"
             f" | web={integrity}%"
             f" | silk={int(spider.silk_reserve)}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(4) | curses.A_BOLD)
    except curses.error:
        pass

    view = self.sweb_view
    if view == "web":
        _draw_sweb_web(self, max_y, max_x)
    elif view == "vibration":
        _draw_sweb_vibration(self, max_y, max_x)
    elif view == "graphs":
        _draw_sweb_graphs(self, max_y, max_x)

    # Hint bar
    hint_y = max_y - 1
    now = time.monotonic()
    if hasattr(self, 'message') and self.message and now - self.message_time < 3.0:
        hint = f" {self.message}"
    else:
        hint = " [Space]=play [n]=step [v]=view [+/-]=speed [r]=reset [R]=menu [q]=exit"
    try:
        self.stdscr.addstr(hint_y, 0, hint[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — web structure view
# ══════════════════════════════════════════════════════════════════════

def _draw_sweb_web(self, max_y: int, max_x: int):
    """Draw web threads, spider, prey, wind arrows, vibration ripples."""
    nodes = self.sweb_nodes
    threads = self.sweb_threads
    spider = self.sweb_spider
    rows = self.sweb_rows
    cols = self.sweb_cols

    view_h = max_y - 3
    view_w = max_x - 2
    y_scale = view_h / max(1, rows)
    x_scale = view_w / max(1, cols)

    def to_screen(wx, wy):
        sx = int(wx * x_scale) + 1
        sy = int(wy * y_scale) + 1
        return sy, sx

    # Draw threads using line characters
    # Build a character buffer
    buf = {}  # (sy, sx) -> (char, attr)

    for t in threads:
        if t.state == THREAD_BROKEN:
            continue
        n0 = nodes[t.n0]
        n1 = nodes[t.n1]
        sy0, sx0 = to_screen(n0.x, n0.y)
        sy1, sx1 = to_screen(n1.x, n1.y)

        # Pick thread character and color based on silk type
        if t.silk_type == SILK_FRAME:
            color = curses.color_pair(7) | curses.A_BOLD
        elif t.silk_type == SILK_RADIAL:
            color = curses.color_pair(7)
        elif t.silk_type == SILK_AUX:
            color = curses.color_pair(6) | curses.A_DIM
        elif t.silk_type == SILK_STICKY:
            color = curses.color_pair(6)
            if t.vibration > 0.1:
                color = curses.color_pair(3) | curses.A_BOLD

        if t.state == THREAD_STRESSED:
            color = curses.color_pair(1)

        # Bresenham-ish line drawing
        dx = abs(sx1 - sx0)
        dy = abs(sy1 - sy0)
        steps = max(dx, dy, 1)
        for s in range(steps + 1):
            frac = s / steps if steps > 0 else 0
            cx = int(sx0 + (sx1 - sx0) * frac)
            cy = int(sy0 + (sy1 - sy0) * frac)
            if 1 <= cy < max_y - 2 and 1 <= cx < max_x - 1:
                # Choose line char based on direction
                if dx > dy * 2:
                    ch = '─'
                elif dy > dx * 2:
                    ch = '│'
                elif (sx1 - sx0) * (sy1 - sy0) > 0:
                    ch = '╲'
                else:
                    ch = '╱'
                # Node junctions get a dot
                if s == 0 or s == steps:
                    ch = '·'
                # Vibration ripple overlay
                if t.vibration > 0.3:
                    ch = '○' if t.vibration > 0.6 else '∙'
                buf[(cy, cx)] = (ch, color)

    # Draw buffer
    for (sy, sx), (ch, attr) in buf.items():
        try:
            self.stdscr.addstr(sy, sx, ch, attr)
        except curses.error:
            pass

    # Draw prey
    for prey in self.sweb_prey:
        if not prey.alive:
            continue
        sy, sx = to_screen(prey.x, prey.y)
        if 1 <= sy < max_y - 2 and 1 <= sx < max_x - 1:
            if prey.trapped:
                if prey.wrapped >= 1.0:
                    ch = '●'
                    attr = curses.color_pair(7) | curses.A_DIM
                else:
                    ch = _PREY_GLYPHS[prey.kind]
                    attr = curses.color_pair(1) | curses.A_BOLD
            else:
                ch = _PREY_GLYPHS[prey.kind]
                attr = curses.color_pair(3)
            try:
                self.stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    # Draw spider
    sy, sx = to_screen(spider.x, spider.y)
    if 1 <= sy < max_y - 2 and 1 <= sx < max_x - 1:
        spider_ch = '◆'
        spider_attr = curses.color_pair(2) | curses.A_BOLD
        if spider.state == SP_RUSHING:
            spider_attr = curses.color_pair(1) | curses.A_BOLD
        elif spider.state == SP_WRAPPING:
            spider_attr = curses.color_pair(3) | curses.A_BOLD
        elif spider.state == SP_REPAIRING:
            spider_attr = curses.color_pair(6) | curses.A_BOLD
        try:
            self.stdscr.addstr(sy, sx, spider_ch, spider_attr)
        except curses.error:
            pass

    # Wind arrow
    wind_mag = math.hypot(self.sweb_wind_x, self.sweb_wind_y)
    if wind_mag > 0.01:
        wind_label = f"Wind: {'→' if self.sweb_wind_x > 0 else '←'}"
        wind_bar = '▸' * min(10, int(wind_mag * 20))
        info = f" {wind_label} {wind_bar}"
    else:
        info = " Wind: calm"

    # Spider state
    state_label = _STATE_NAMES[spider.state]
    info += f"  Spider: {state_label}"
    info_y = max_y - 2
    try:
        self.stdscr.addstr(info_y, 0, info[:max_x - 1], curses.color_pair(6))
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — vibration heatmap view
# ══════════════════════════════════════════════════════════════════════

def _draw_sweb_vibration(self, max_y: int, max_x: int):
    """Draw vibration intensity through the web as a heatmap."""
    nodes = self.sweb_nodes
    threads = self.sweb_threads
    spider = self.sweb_spider
    rows = self.sweb_rows
    cols = self.sweb_cols

    view_h = max_y - 3
    view_w = max_x - 2
    y_scale = view_h / max(1, rows)
    x_scale = view_w / max(1, cols)

    def to_screen(wx, wy):
        sx = int(wx * x_scale) + 1
        sy = int(wy * y_scale) + 1
        return sy, sx

    # Heat chars for vibration intensity
    heat_chars = " ░▒▓█"
    heat_colors = [0, 6, 3, 1, 1]

    # Draw threads colored by vibration
    for t in threads:
        if t.state == THREAD_BROKEN:
            continue
        n0 = nodes[t.n0]
        n1 = nodes[t.n1]
        sy0, sx0 = to_screen(n0.x, n0.y)
        sy1, sx1 = to_screen(n1.x, n1.y)

        vib = t.vibration
        heat_idx = min(4, int(vib * 8))
        ch = heat_chars[heat_idx]
        if ch == ' ':
            ch = '·'
            attr = curses.color_pair(7) | curses.A_DIM
        else:
            attr = curses.color_pair(heat_colors[heat_idx]) | curses.A_BOLD

        dx = abs(sx1 - sx0)
        dy = abs(sy1 - sy0)
        steps = max(dx, dy, 1)
        for s in range(0, steps + 1, max(1, steps // 8)):
            frac = s / steps if steps > 0 else 0
            cx = int(sx0 + (sx1 - sx0) * frac)
            cy = int(sy0 + (sy1 - sy0) * frac)
            if 1 <= cy < max_y - 2 and 1 <= cx < max_x - 1:
                try:
                    self.stdscr.addstr(cy, cx, ch, attr)
                except curses.error:
                    pass

    # Draw vibrating nodes
    for ni, node in enumerate(nodes):
        if node.vibration > 0.05:
            sy, sx = to_screen(node.x, node.y)
            if 1 <= sy < max_y - 2 and 1 <= sx < max_x - 1:
                heat_idx = min(4, int(node.vibration * 6))
                ch = heat_chars[heat_idx] if heat_idx > 0 else '∙'
                attr = curses.color_pair(heat_colors[max(1, heat_idx)])
                try:
                    self.stdscr.addstr(sy, sx, ch, attr | curses.A_BOLD)
                except curses.error:
                    pass

    # Draw trapped prey as bright spots
    for prey in self.sweb_prey:
        if prey.trapped and prey.alive:
            sy, sx = to_screen(prey.x, prey.y)
            if 1 <= sy < max_y - 2 and 1 <= sx < max_x - 1:
                try:
                    self.stdscr.addstr(sy, sx, '◎',
                                       curses.color_pair(1) | curses.A_BOLD)
                except curses.error:
                    pass

    # Spider
    sy, sx = to_screen(spider.x, spider.y)
    if 1 <= sy < max_y - 2 and 1 <= sx < max_x - 1:
        try:
            self.stdscr.addstr(sy, sx, '◆',
                               curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass

    # Legend
    info_y = max_y - 2
    legend = " Vibration: ░=low ▒=med ▓=high █=peak  ◎=trapped prey  ◆=spider"
    try:
        self.stdscr.addstr(info_y, 0, legend[:max_x - 1], curses.color_pair(6))
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — time-series graphs
# ══════════════════════════════════════════════════════════════════════

def _draw_sweb_graphs(self, max_y: int, max_x: int):
    """Draw capture rate, web integrity, silk reserves graphs."""
    view_h = max_y - 4
    view_w = max_x - 4
    graph_h = max(3, view_h // 4)
    graph_w = min(200, view_w - 12)

    # Capture count graph
    _draw_sweb_sparkline(self, 2, 2, graph_h, graph_w,
                         self.sweb_capture_history, "Captures",
                         curses.color_pair(3), max_y, max_x)

    # Web integrity graph
    base2 = 3 + graph_h
    _draw_sweb_sparkline(self, base2, 2, graph_h, graph_w,
                         self.sweb_integrity_history, "Web Integrity",
                         curses.color_pair(2), max_y, max_x)

    # Silk reserves graph
    base3 = base2 + graph_h + 1
    _draw_sweb_sparkline(self, base3, 2, graph_h, graph_w,
                         self.sweb_silk_history, "Silk Reserve",
                         curses.color_pair(4), max_y, max_x)

    # Trapped prey count graph
    base4 = base3 + graph_h + 1
    _draw_sweb_sparkline(self, base4, 2, graph_h, graph_w,
                         self.sweb_prey_count_history, "Trapped Prey",
                         curses.color_pair(1), max_y, max_x)

    # Stats summary
    spider = self.sweb_spider
    stats_y = base4 + graph_h + 1
    if stats_y < max_y - 2:
        stats = (f" Total captures: {spider.captures}"
                 f"  Silk: {int(spider.silk_reserve)}"
                 f"  Energy: {int(spider.energy * 100)}%"
                 f"  State: {_STATE_NAMES[spider.state]}")
        try:
            self.stdscr.addstr(stats_y, 2, stats[:max_x - 4],
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass


def _draw_sweb_sparkline(self, base_y, base_x, height, width,
                         data, label, color, max_y, max_x):
    """Draw a sparkline graph."""
    if base_y >= max_y - 1:
        return
    try:
        self.stdscr.addstr(base_y, base_x, f"{label}:",
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    if not data:
        return
    visible = data[-width:]
    mn = min(visible)
    mx = max(visible)
    rng = mx - mn if mx > mn else 1.0
    bars = "▁▂▃▄▅▆▇█"
    n = len(bars)

    for i, v in enumerate(visible):
        x = base_x + i
        y = base_y + 1
        if x >= max_x - 1 or y >= max_y - 1:
            continue
        idx = int((v - mn) / rng * (n - 1))
        idx = max(0, min(n - 1, idx))
        try:
            self.stdscr.addstr(y, x, bars[idx], color)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register spider web mode methods on the App class."""
    App.SWEB_PRESETS = SWEB_PRESETS
    App._enter_sweb_mode = _enter_sweb_mode
    App._exit_sweb_mode = _exit_sweb_mode
    App._sweb_init = _sweb_init
    App._sweb_step = _sweb_step
    App._handle_sweb_menu_key = _handle_sweb_menu_key
    App._handle_sweb_key = _handle_sweb_key
    App._draw_sweb_menu = _draw_sweb_menu
    App._draw_sweb = _draw_sweb
