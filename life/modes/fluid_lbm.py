"""Mode: fluid — simulation mode for the life package."""
import curses
import math
import random
import time


from life.constants import SPEEDS
from life.colors import colormap_addstr

# ══════════════════════════════════════════════════════════════════════
#  Fluid Dynamics (Lattice Boltzmann Method) — Mode F
# ══════════════════════════════════════════════════════════════════════

# D2Q9 lattice velocities: (ex, ey) for each of 9 directions
#   6 2 5
#   3 0 1
#   7 4 8
FLUID_EX = [0, 1, 0, -1,  0, 1, -1, -1,  1]
FLUID_EY = [0, 0, 1,  0, -1, 1,  1, -1, -1]
FLUID_W  = [4.0/9, 1.0/9, 1.0/9, 1.0/9, 1.0/9,
            1.0/36, 1.0/36, 1.0/36, 1.0/36]
FLUID_OPP = [0, 3, 4, 1, 2, 7, 8, 5, 6]  # opposite direction index

FLUID_SPEED_CHARS = [" ", "░", "▒", "▓", "█"]
FLUID_VORT_POS = ["·", "∘", "○", "◎", "◉"]   # counterclockwise
FLUID_VORT_NEG = ["·", "∙", "•", "●", "⬤"]    # clockwise

FLUID_PRESETS = [
    # (name, description, omega, inflow_speed, obstacle_type)
    ("Wind Tunnel", "Uniform flow past a cylindrical obstacle", 1.4, 0.10, "cylinder"),
    ("Von Kármán Street", "Vortex shedding behind a cylinder (low viscosity)", 1.85, 0.12, "cylinder_small"),
    ("Lid-Driven Cavity", "Enclosed box with moving top wall", 1.5, 0.10, "cavity"),
    ("Channel Flow", "Poiseuille flow between parallel walls", 1.6, 0.08, "channel"),
    ("Obstacle Course", "Flow weaving through multiple obstacles", 1.5, 0.10, "obstacles"),
    ("Turbulence", "High-speed chaotic flow with perturbations", 1.9, 0.15, "turbulence"),
]


def _enter_fluid_mode(self):
    """Enter Fluid Dynamics mode — show preset menu."""
    self.fluid_menu = True
    self.fluid_menu_sel = 0
    self._flash("Fluid Dynamics (LBM) — select a configuration")



def _exit_fluid_mode(self):
    """Exit Fluid Dynamics mode."""
    self.fluid_mode = False
    self.fluid_menu = False
    self.fluid_running = False
    self.fluid_f = []
    self.fluid_obstacle = []
    self._flash("Fluid Dynamics mode OFF")



def _fluid_init(self, preset_idx: int):
    """Initialize LBM simulation with the given preset."""
    name, _desc, omega, inflow, obs_type = self.FLUID_PRESETS[preset_idx]
    self.fluid_preset_name = name
    self.fluid_omega = omega
    self.fluid_inflow_speed = inflow
    self.fluid_generation = 0
    self.fluid_running = False
    self.fluid_viz_mode = 0

    max_y, max_x = self.stdscr.getmaxyx()
    self.fluid_rows = max(10, max_y - 3)
    self.fluid_cols = max(10, (max_x - 1) // 2)
    rows, cols = self.fluid_rows, self.fluid_cols

    # Initialize obstacle grid
    self.fluid_obstacle = [[False] * cols for _ in range(rows)]

    # Place obstacles based on preset type
    cr, cc = rows // 2, cols // 4
    if obs_type == "cylinder":
        radius = min(rows, cols) // 8
        for r in range(rows):
            for c in range(cols):
                dr = r - cr
                dc = c - cc
                if dr * dr + dc * dc <= radius * radius:
                    self.fluid_obstacle[r][c] = True
    elif obs_type == "cylinder_small":
        radius = min(rows, cols) // 12
        for r in range(rows):
            for c in range(cols):
                dr = r - cr
                dc = c - cc
                if dr * dr + dc * dc <= radius * radius:
                    self.fluid_obstacle[r][c] = True
    elif obs_type == "cavity":
        # Walls on all sides except top (which will be the moving lid)
        for r in range(rows):
            self.fluid_obstacle[r][0] = True
            self.fluid_obstacle[r][cols - 1] = True
        for c in range(cols):
            self.fluid_obstacle[rows - 1][c] = True
    elif obs_type == "channel":
        wall_h = rows // 6
        for c in range(cols):
            for r in range(wall_h):
                self.fluid_obstacle[r][c] = True
                self.fluid_obstacle[rows - 1 - r][c] = True
    elif obs_type == "obstacles":
        # Multiple circular obstacles
        positions = [
            (rows // 4, cols // 4),
            (3 * rows // 4, cols // 4),
            (rows // 2, cols // 2),
            (rows // 4, 3 * cols // 4),
            (3 * rows // 4, 3 * cols // 4),
        ]
        radius = min(rows, cols) // 14
        for pr, pc in positions:
            for r in range(rows):
                for c in range(cols):
                    dr = r - pr
                    dc = c - pc
                    if dr * dr + dc * dc <= radius * radius:
                        self.fluid_obstacle[r][c] = True
    elif obs_type == "turbulence":
        # Small obstacle to trigger instability
        radius = min(rows, cols) // 16
        for r in range(rows):
            for c in range(cols):
                dr = r - cr
                dc = c - cc
                if dr * dr + dc * dc <= radius * radius:
                    self.fluid_obstacle[r][c] = True

    # Initialize distribution functions to equilibrium with uniform rightward flow
    ex = self.FLUID_EX
    ey = self.FLUID_EY
    w = self.FLUID_W
    u0 = inflow if obs_type != "cavity" else 0.0

    self.fluid_f = []
    for r in range(rows):
        row_data = []
        for c in range(cols):
            cell = [0.0] * 9
            if not self.fluid_obstacle[r][c]:
                rho = 1.0
                ux = u0
                uy = 0.0
                usq = ux * ux + uy * uy
                for i in range(9):
                    eu = ex[i] * ux + ey[i] * uy
                    cell[i] = w[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * usq)
            row_data.append(cell)
        self.fluid_f.append(row_data)

    self.fluid_menu = False
    self.fluid_mode = True
    self._flash(f"Fluid Dynamics: {name} — Space to start")



def _fluid_step(self):
    """Advance LBM simulation by one step (stream + collide)."""
    rows = self.fluid_rows
    cols = self.fluid_cols
    f = self.fluid_f
    obstacle = self.fluid_obstacle
    omega = self.fluid_omega
    ex = self.FLUID_EX
    ey = self.FLUID_EY
    w = self.FLUID_W
    opp = self.FLUID_OPP
    inflow = self.fluid_inflow_speed
    preset = self.fluid_preset_name

    # ── Streaming step: propagate distributions ──
    f_new = [[[0.0] * 9 for _ in range(cols)] for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            for i in range(9):
                # Source cell for direction i
                sr = (r - ey[i]) % rows
                sc = (c - ex[i]) % cols
                f_new[r][c][i] = f[sr][sc][i]

    # ── Bounce-back for obstacles ──
    for r in range(rows):
        for c in range(cols):
            if obstacle[r][c]:
                for i in range(9):
                    f_new[r][c][i] = f[r][c][opp[i]]

    # ── Collision step (BGK) ──
    for r in range(rows):
        for c in range(cols):
            if obstacle[r][c]:
                continue
            fc = f_new[r][c]
            # Compute macroscopic quantities
            rho = 0.0
            ux = 0.0
            uy = 0.0
            for i in range(9):
                rho += fc[i]
                ux += ex[i] * fc[i]
                uy += ey[i] * fc[i]
            if rho > 0.0:
                ux /= rho
                uy /= rho
            else:
                rho = 1.0
                ux = 0.0
                uy = 0.0

            # Compute equilibrium and relax
            usq = ux * ux + uy * uy
            for i in range(9):
                eu = ex[i] * ux + ey[i] * uy
                feq = w[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * usq)
                fc[i] += omega * (feq - fc[i])

    # ── Boundary conditions ──
    if preset == "Lid-Driven Cavity":
        # Top row: moving lid (rightward velocity)
        lid_ux = inflow
        for c in range(1, cols - 1):
            if not obstacle[0][c]:
                rho = 1.0
                usq = lid_ux * lid_ux
                for i in range(9):
                    eu = ex[i] * lid_ux
                    f_new[0][c][i] = w[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * usq)
    else:
        # Left boundary: inflow (Zou-He style simplified)
        for r in range(rows):
            if not obstacle[r][0]:
                rho = 1.0
                ux = inflow
                uy = 0.0
                usq = ux * ux
                for i in range(9):
                    eu = ex[i] * ux + ey[i] * uy
                    f_new[r][0][i] = w[i] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * usq)
        # Right boundary: outflow (copy from neighbor)
        for r in range(rows):
            if not obstacle[r][cols - 1] and not obstacle[r][cols - 2]:
                for i in range(9):
                    f_new[r][cols - 1][i] = f_new[r][cols - 2][i]

    self.fluid_f = f_new
    self.fluid_generation += 1



def _fluid_get_macros(self):
    """Compute macroscopic fields (density, velocity) from distributions."""
    rows = self.fluid_rows
    cols = self.fluid_cols
    f = self.fluid_f
    ex = self.FLUID_EX
    ey = self.FLUID_EY
    obstacle = self.fluid_obstacle

    rho = [[1.0] * cols for _ in range(rows)]
    ux = [[0.0] * cols for _ in range(rows)]
    uy = [[0.0] * cols for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            if obstacle[r][c]:
                continue
            fc = f[r][c]
            d = 0.0
            vx = 0.0
            vy = 0.0
            for i in range(9):
                d += fc[i]
                vx += ex[i] * fc[i]
                vy += ey[i] * fc[i]
            if d > 0.0:
                rho[r][c] = d
                ux[r][c] = vx / d
                uy[r][c] = vy / d
    return rho, ux, uy



def _handle_fluid_menu_key(self, key: int) -> bool:
    """Handle input in Fluid Dynamics preset menu."""
    n = len(self.FLUID_PRESETS)
    if key in (ord("j"), curses.KEY_DOWN):
        self.fluid_menu_sel = (self.fluid_menu_sel + 1) % n
    elif key in (ord("k"), curses.KEY_UP):
        self.fluid_menu_sel = (self.fluid_menu_sel - 1) % n
    elif key in (ord("\n"), ord("\r")):
        self._fluid_init(self.fluid_menu_sel)
    elif key in (ord("q"), 27):
        self.fluid_menu = False
        self._flash("Fluid Dynamics cancelled")
    return True



def _handle_fluid_key(self, key: int) -> bool:
    """Handle input in active Fluid Dynamics simulation."""
    if key == ord(" "):
        self.fluid_running = not self.fluid_running
    elif key in (ord("n"), ord(".")):
        for _ in range(self.fluid_steps_per_frame):
            self._fluid_step()
    elif key == ord("r"):
        idx = next((i for i, p in enumerate(self.FLUID_PRESETS)
                    if p[0] == self.fluid_preset_name), 0)
        self._fluid_init(idx)
        self.fluid_running = False
    elif key in (ord("R"), ord("m")):
        self.fluid_mode = False
        self.fluid_running = False
        self.fluid_menu = True
        self.fluid_menu_sel = 0
    elif key == ord("v"):
        self.fluid_viz_mode = (self.fluid_viz_mode + 1) % 3
        modes = ["Speed", "Vorticity", "Density"]
        self._flash(f"Visualization: {modes[self.fluid_viz_mode]}")
    elif key == ord("w") or key == ord("W"):
        delta = 0.05 if key == ord("w") else -0.05
        self.fluid_omega = max(0.5, min(1.99, self.fluid_omega + delta))
        viscosity = (1.0 / self.fluid_omega - 0.5) / 3.0
        self._flash(f"Omega: {self.fluid_omega:.2f}  (viscosity: {viscosity:.4f})")
    elif key == ord("u") or key == ord("U"):
        delta = 0.01 if key == ord("u") else -0.01
        self.fluid_inflow_speed = max(0.01, min(0.25, self.fluid_inflow_speed + delta))
        self._flash(f"Inflow speed: {self.fluid_inflow_speed:.3f}")
    elif key == ord("+") or key == ord("="):
        self.fluid_steps_per_frame = min(20, self.fluid_steps_per_frame + 1)
        self._flash(f"Steps/frame: {self.fluid_steps_per_frame}")
    elif key == ord("-"):
        self.fluid_steps_per_frame = max(1, self.fluid_steps_per_frame - 1)
        self._flash(f"Steps/frame: {self.fluid_steps_per_frame}")
    elif key == ord("<") or key == ord(","):
        self.speed_idx = max(0, self.speed_idx - 1)
    elif key == ord(">") or key == ord("."):
        self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)
    elif key in (ord("q"), 27):
        self._exit_fluid_mode()
    else:
        return True
    return True



def _draw_fluid_menu(self, max_y: int, max_x: int):
    """Draw the Fluid Dynamics preset selection menu."""
    self.stdscr.erase()
    title = "── Fluid Dynamics (Lattice Boltzmann) ── Select Configuration ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, omega, inflow, _obs) in enumerate(self.FLUID_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        line = f"  {name:<22s}  {desc}"
        viscosity = (1.0 / omega - 0.5) / 3.0
        params = f"    omega={omega:.2f}  viscosity={viscosity:.4f}  inflow={inflow:.2f}"
        attr = curses.color_pair(6)
        if i == self.fluid_menu_sel:
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



def _draw_fluid(self, max_y: int, max_x: int):
    """Draw the active Fluid Dynamics simulation."""
    self.stdscr.erase()
    rows, cols = self.fluid_rows, self.fluid_cols
    obstacle = self.fluid_obstacle
    state = "▶ RUNNING" if self.fluid_running else "⏸ PAUSED"
    viz_names = ["Speed", "Vorticity", "Density"]
    viscosity = (1.0 / self.fluid_omega - 0.5) / 3.0

    # Title bar
    title = (f" Fluid (LBM): {self.fluid_preset_name}  |  step {self.fluid_generation}"
             f"  |  ω={self.fluid_omega:.2f}"
             f"  ν={viscosity:.4f}"
             f"  u₀={self.fluid_inflow_speed:.2f}"
             f"  |  {viz_names[self.fluid_viz_mode]}  |  {state}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Compute macroscopic fields
    rho, ux_field, uy_field = self._fluid_get_macros()

    view_rows = min(rows, max_y - 3)
    view_cols = min(cols, (max_x - 1) // 2)

    # Determine visualization field and range
    viz = self.fluid_viz_mode
    max_val = 0.001  # avoid div by zero

    if viz == 0:  # Speed
        field = [[0.0] * cols for _ in range(rows)]
        for r in range(view_rows):
            for c in range(view_cols):
                if not obstacle[r][c]:
                    spd = math.sqrt(ux_field[r][c] ** 2 + uy_field[r][c] ** 2)
                    field[r][c] = spd
                    if spd > max_val:
                        max_val = spd
    elif viz == 1:  # Vorticity (curl of velocity)
        field = [[0.0] * cols for _ in range(rows)]
        for r in range(1, min(view_rows, rows - 1)):
            for c in range(1, min(view_cols, cols - 1)):
                if obstacle[r][c]:
                    continue
                # curl = duy/dx - dux/dy (finite difference)
                duy_dx = (uy_field[r][(c + 1) % cols] - uy_field[r][(c - 1) % cols]) * 0.5
                dux_dy = (ux_field[(r + 1) % rows][c] - ux_field[(r - 1) % rows][c]) * 0.5
                curl = duy_dx - dux_dy
                field[r][c] = curl
                av = abs(curl)
                if av > max_val:
                    max_val = av
    else:  # Density
        field = rho
        min_rho = 1.0
        max_rho = 1.0
        for r in range(view_rows):
            for c in range(view_cols):
                if not obstacle[r][c]:
                    v = rho[r][c]
                    if v < min_rho:
                        min_rho = v
                    if v > max_rho:
                        max_rho = v
        max_val = max(0.001, max_rho - min_rho)
        rho_offset = min_rho

    # Render grid
    speed_chars = self.FLUID_SPEED_CHARS
    vort_pos = self.FLUID_VORT_POS
    vort_neg = self.FLUID_VORT_NEG
    n_levels = len(speed_chars)

    # Truecolor path
    tc_buf = getattr(self, 'tc_buf', None)
    use_tc = tc_buf is not None and tc_buf.enabled
    # Colormaps: speed=inferno, vorticity=plasma, density=viridis
    _fluid_cmaps = ['inferno', 'plasma', 'viridis']

    for r in range(view_rows):
        for c in range(view_cols):
            if obstacle[r][c]:
                try:
                    self.stdscr.addstr(1 + r, c * 2, "██",
                                       curses.color_pair(7) | curses.A_DIM)
                except curses.error:
                    pass
                continue

            val = field[r][c]

            if viz == 0:  # Speed
                norm = min(1.0, val / max_val)
                lvl = int(norm * (n_levels - 1))
                ch = speed_chars[lvl]
            elif viz == 1:  # Vorticity
                norm = min(1.0, abs(val) / max_val)
                lvl = int(norm * (n_levels - 1))
                ch = vort_pos[lvl] if val >= 0 else vort_neg[lvl]
            else:  # Density
                norm = min(1.0, max(0.0, (val - rho_offset) / max_val))
                lvl = int(norm * (n_levels - 1))
                ch = speed_chars[lvl]

            if ch != " ":
                if use_tc:
                    colormap_addstr(self.stdscr, 1 + r, c * 2, ch + " ",
                                    _fluid_cmaps[viz], norm,
                                    bold=(norm > 0.6), tc_buf=tc_buf)
                else:
                    if viz == 0:
                        if norm > 0.7:
                            attr = curses.color_pair(1) | curses.A_BOLD
                        elif norm > 0.4:
                            attr = curses.color_pair(3)
                        elif norm > 0.15:
                            attr = curses.color_pair(4)
                        else:
                            attr = curses.color_pair(6) | curses.A_DIM
                    elif viz == 1:
                        if val >= 0:
                            attr = curses.color_pair(1) | (curses.A_BOLD if norm > 0.5 else 0)
                        else:
                            attr = curses.color_pair(4) | (curses.A_BOLD if norm > 0.5 else 0)
                    else:
                        if norm > 0.65:
                            attr = curses.color_pair(5) | curses.A_BOLD
                        elif norm > 0.35:
                            attr = curses.color_pair(2)
                        else:
                            attr = curses.color_pair(6) | curses.A_DIM
                    try:
                        self.stdscr.addstr(1 + r, c * 2, ch + " ", attr)
                    except curses.error:
                        pass

    # Status bar
    status_y = max_y - 2
    if status_y > 1:
        # Compute average speed
        total_spd = 0.0
        cnt = 0
        for r in range(rows):
            for c in range(cols):
                if not obstacle[r][c]:
                    total_spd += math.sqrt(ux_field[r][c] ** 2 + uy_field[r][c] ** 2)
                    cnt += 1
        avg_spd = total_spd / max(1, cnt)
        re_approx = self.fluid_inflow_speed * min(rows, cols) / max(0.0001, viscosity) * 0.1
        info = (f" Step {self.fluid_generation}  |  grid={rows}×{cols}"
                f"  |  avg speed={avg_spd:.4f}"
                f"  |  Re≈{re_approx:.0f}"
                f"  |  steps/f={self.fluid_steps_per_frame}")
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
            hint = " [Space]=play [n]=step [v]=viz mode [w/W]=viscosity+/- [u/U]=inflow+/- [r]=reset [R]=menu [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def register(App):
    """Register fluid mode methods on the App class."""
    App.FLUID_EX = FLUID_EX
    App.FLUID_EY = FLUID_EY
    App.FLUID_W = FLUID_W
    App.FLUID_OPP = FLUID_OPP
    App.FLUID_SPEED_CHARS = FLUID_SPEED_CHARS
    App.FLUID_VORT_POS = FLUID_VORT_POS
    App.FLUID_VORT_NEG = FLUID_VORT_NEG
    App.FLUID_PRESETS = FLUID_PRESETS
    App._enter_fluid_mode = _enter_fluid_mode
    App._exit_fluid_mode = _exit_fluid_mode
    App._fluid_init = _fluid_init
    App._fluid_step = _fluid_step
    App._fluid_get_macros = _fluid_get_macros
    App._handle_fluid_menu_key = _handle_fluid_menu_key
    App._handle_fluid_key = _handle_fluid_key
    App._draw_fluid_menu = _draw_fluid_menu
    App._draw_fluid = _draw_fluid

