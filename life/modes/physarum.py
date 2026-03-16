"""Mode: physarum — simulation mode for the life package."""
import curses
import math
import random
import time


from life.constants import SPEEDS
from life.grid import Grid
from life.colors import colormap_addstr

def _enter_physarum_mode(self):
    """Enter Physarum mode — show preset menu."""
    self.physarum_menu = True
    self.physarum_menu_sel = 0
    self._flash("Physarum — select a configuration")



def _exit_physarum_mode(self):
    """Exit Physarum mode."""
    self.physarum_mode = False
    self.physarum_menu = False
    self.physarum_running = False
    self.physarum_trail = []
    self.physarum_agents = []
    self._flash("Physarum mode OFF")



def _physarum_init(self, preset_idx: int):
    """Initialize Physarum simulation with the given preset."""
    name, _desc, sa, sd, ts, ms, dep, dec, ratio = self.PHYSARUM_PRESETS[preset_idx]
    self.physarum_preset_name = name
    self.physarum_sensor_angle = sa
    self.physarum_sensor_dist = sd
    self.physarum_turn_speed = ts
    self.physarum_move_speed = ms
    self.physarum_deposit = dep
    self.physarum_decay = dec
    self.physarum_generation = 0
    self.physarum_running = False

    max_y, max_x = self.stdscr.getmaxyx()
    self.physarum_rows = max(10, max_y - 3)
    self.physarum_cols = max(10, (max_x - 1) // 2)

    rows, cols = self.physarum_rows, self.physarum_cols
    self.physarum_trail = [[0.0] * cols for _ in range(rows)]

    # Spawn agents in a circle in the centre
    self.physarum_num_agents = max(50, int(rows * cols * ratio))
    self.physarum_agents = []
    cr, cc = rows / 2.0, cols / 2.0
    radius = min(rows, cols) * 0.3
    for _ in range(self.physarum_num_agents):
        angle = random.random() * 2 * math.pi
        r_off = random.random() * radius
        ar = cr + math.sin(angle) * r_off
        ac = cc + math.cos(angle) * r_off
        heading = angle + math.pi + random.uniform(-0.5, 0.5)
        self.physarum_agents.append([ar % rows, ac % cols, heading])

    self.physarum_menu = False
    self.physarum_mode = True
    self._flash(f"Physarum: {name} — Space to start")



def _physarum_sense(self, ar: float, ac: float, heading: float, offset: float) -> float:
    """Sense trail concentration at sensor position."""
    rows, cols = self.physarum_rows, self.physarum_cols
    angle = heading + offset
    sr = ar + math.sin(angle) * self.physarum_sensor_dist
    sc = ac + math.cos(angle) * self.physarum_sensor_dist
    ri = int(sr) % rows
    ci = int(sc) % cols
    return self.physarum_trail[ri][ci]



def _physarum_step(self):
    """Advance Physarum simulation by one step."""
    rows, cols = self.physarum_rows, self.physarum_cols
    trail = self.physarum_trail
    sa = self.physarum_sensor_angle
    ts = self.physarum_turn_speed
    ms = self.physarum_move_speed
    dep = self.physarum_deposit

    # Move agents: sense, rotate, move, deposit
    for agent in self.physarum_agents:
        ar, ac, heading = agent[0], agent[1], agent[2]

        # Sense left, centre, right
        fl = self._physarum_sense(ar, ac, heading, sa)
        fc = self._physarum_sense(ar, ac, heading, 0.0)
        fr = self._physarum_sense(ar, ac, heading, -sa)

        # Steer towards strongest signal
        if fc > fl and fc > fr:
            pass  # go straight
        elif fc < fl and fc < fr:
            # random turn
            heading += ts if random.random() < 0.5 else -ts
        elif fl > fr:
            heading += ts
        elif fr > fl:
            heading -= ts

        # Move forward
        nr = ar + math.sin(heading) * ms
        nc = ac + math.cos(heading) * ms
        nr = nr % rows
        nc = nc % cols
        agent[0] = nr
        agent[1] = nc
        agent[2] = heading

        # Deposit trail
        ri, ci = int(nr) % rows, int(nc) % cols
        trail[ri][ci] = min(1.0, trail[ri][ci] + dep)

    # Diffuse and decay trail (simple 3x3 box blur + decay)
    decay = self.physarum_decay
    new_trail = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        rp = (r - 1) % rows
        rn = (r + 1) % rows
        for c in range(cols):
            cp = (c - 1) % cols
            cn = (c + 1) % cols
            total = (
                trail[rp][cp] + trail[rp][c] + trail[rp][cn] +
                trail[r][cp] + trail[r][c] + trail[r][cn] +
                trail[rn][cp] + trail[rn][c] + trail[rn][cn]
            ) / 9.0
            new_trail[r][c] = max(0.0, total - decay)
    self.physarum_trail = new_trail
    self.physarum_generation += 1



def _handle_physarum_menu_key(self, key: int) -> bool:
    """Handle input in Physarum preset menu."""
    n = len(self.PHYSARUM_PRESETS)
    if key in (ord("j"), curses.KEY_DOWN):
        self.physarum_menu_sel = (self.physarum_menu_sel + 1) % n
    elif key in (ord("k"), curses.KEY_UP):
        self.physarum_menu_sel = (self.physarum_menu_sel - 1) % n
    elif key in (ord("\n"), ord("\r")):
        self._physarum_init(self.physarum_menu_sel)
    elif key in (ord("q"), 27):
        self.physarum_menu = False
        self._flash("Physarum cancelled")
    return True



def _handle_physarum_key(self, key: int) -> bool:
    """Handle input in active Physarum simulation."""
    if key == ord(" "):
        self.physarum_running = not self.physarum_running
    elif key in (ord("n"), ord(".")):
        for _ in range(self.physarum_steps_per_frame):
            self._physarum_step()
    elif key == ord("r"):
        # Reseed with current parameters
        idx = next((i for i, p in enumerate(self.PHYSARUM_PRESETS)
                    if p[0] == self.physarum_preset_name), 0)
        self._physarum_init(idx)
        self.physarum_running = False
    elif key in (ord("R"), ord("m")):
        self.physarum_mode = False
        self.physarum_running = False
        self.physarum_menu = True
        self.physarum_menu_sel = 0
    elif key == ord("a") or key == ord("A"):
        # Adjust sensor angle
        delta = 0.05 if key == ord("a") else -0.05
        self.physarum_sensor_angle = max(0.05, min(1.5, self.physarum_sensor_angle + delta))
        self._flash(f"Sensor angle: {self.physarum_sensor_angle:.2f}")
    elif key == ord("s") or key == ord("S"):
        # Adjust sensor distance
        delta = 1.0 if key == ord("s") else -1.0
        self.physarum_sensor_dist = max(1.0, min(30.0, self.physarum_sensor_dist + delta))
        self._flash(f"Sensor dist: {self.physarum_sensor_dist:.1f}")
    elif key == ord("t") or key == ord("T"):
        # Adjust turn speed
        delta = 0.05 if key == ord("t") else -0.05
        self.physarum_turn_speed = max(0.05, min(1.5, self.physarum_turn_speed + delta))
        self._flash(f"Turn speed: {self.physarum_turn_speed:.2f}")
    elif key == ord("d") or key == ord("D"):
        # Adjust decay
        delta = 0.005 if key == ord("d") else -0.005
        self.physarum_decay = max(0.001, min(0.1, self.physarum_decay + delta))
        self._flash(f"Decay: {self.physarum_decay:.3f}")
    elif key == ord("+") or key == ord("="):
        self.physarum_steps_per_frame = min(20, self.physarum_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.physarum_steps_per_frame}")
    elif key == ord("-"):
        self.physarum_steps_per_frame = max(1, self.physarum_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.physarum_steps_per_frame}")
    elif key == ord("<") or key == ord(","):
        self.speed_idx = max(0, self.speed_idx - 1)
    elif key == ord(">") or key == ord("."):
        self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)
    elif key in (ord("q"), 27):
        self._exit_physarum_mode()
    else:
        return True
    return True



def _draw_physarum_menu(self, max_y: int, max_x: int):
    """Draw the Physarum preset selection menu."""
    self.stdscr.erase()
    title = "── Physarum Slime Mold ── Select Configuration ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, sa, sd, ts, ms, dep, dec, ratio) in enumerate(self.PHYSARUM_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        line = f"  {name:<14s}  {desc}"
        params = f"    SA={sa:.2f}  SD={sd:.1f}  TS={ts:.2f}  dep={dep:.1f}  dec={dec:.3f}"
        attr = curses.color_pair(6)
        if i == self.physarum_menu_sel:
            attr = curses.color_pair(7) | curses.A_REVERSE
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 4], attr)
            self.stdscr.addstr(y + 1, 2, params[:max_x - 4], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    hint = " [j/k]=navigate  [Enter]=select  [q]=cancel"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass



def _draw_physarum(self, max_y: int, max_x: int):
    """Draw the active Physarum simulation."""
    self.stdscr.erase()
    trail = self.physarum_trail
    rows, cols = self.physarum_rows, self.physarum_cols
    density = self.PHYSARUM_DENSITY
    state = "▶ RUNNING" if self.physarum_running else "⏸ PAUSED"

    # Title bar
    title = (f" Physarum: {self.physarum_preset_name}  |  gen {self.physarum_generation}"
             f"  |  SA={self.physarum_sensor_angle:.2f}  SD={self.physarum_sensor_dist:.1f}"
             f"  TS={self.physarum_turn_speed:.2f}  dec={self.physarum_decay:.3f}"
             f"  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Grid area
    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)
    # Truecolor path
    tc_buf = getattr(self, 'tc_buf', None)
    use_tc = tc_buf is not None and tc_buf.enabled

    for r in range(view_rows):
        for c in range(view_cols):
            v = trail[r][c]
            # Density glyph
            di = int(v * 4.99)
            if di < 0:
                di = 0
            elif di > 4:
                di = 4
            ch = density[di]

            if use_tc:
                if v > 0.005:
                    colormap_addstr(self.stdscr, 1 + r, c * 2, ch,
                                    'amber', v, bold=(v > 0.5), tc_buf=tc_buf)
            else:
                # Colour tier (0-7)
                ci = int(v * 7.99)
                if ci < 0:
                    ci = 0
                elif ci > 7:
                    ci = 7
                attr = curses.color_pair(80 + ci)
                if v > 0.5:
                    attr |= curses.A_BOLD
                try:
                    self.stdscr.addstr(1 + r, c * 2, ch, attr)
                except curses.error:
                    pass

    # Status bar
    status_y = max_y - 2
    if status_y > 1:
        total_trail = sum(trail[r][c] for r in range(rows) for c in range(cols))
        avg_trail = total_trail / (rows * cols) if rows * cols > 0 else 0
        max_trail = max(trail[r][c] for r in range(rows) for c in range(cols))
        info = (f" Gen {self.physarum_generation}  |  agents={self.physarum_num_agents}"
                f"  |  avg={avg_trail:.4f}  max={max_trail:.3f}"
                f"  |  steps/f={self.physarum_steps_per_frame}")
        try:
            self.stdscr.addstr(status_y, 0, info[:max_x - 1], curses.color_pair(6))
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [a/A]=angle+/- [s/S]=dist+/- [t/T]=turn+/- [d/D]=decay+/- [r]=reseed [R]=menu [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def register(App):
    """Register physarum mode methods on the App class."""
    App._enter_physarum_mode = _enter_physarum_mode
    App._exit_physarum_mode = _exit_physarum_mode
    App._physarum_init = _physarum_init
    App._physarum_sense = _physarum_sense
    App._physarum_step = _physarum_step
    App._handle_physarum_menu_key = _handle_physarum_menu_key
    App._handle_physarum_key = _handle_physarum_key
    App._draw_physarum_menu = _draw_physarum_menu
    App._draw_physarum = _draw_physarum

