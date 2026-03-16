"""Mode: rd — Reaction-Diffusion Texture Generator (Gray-Scott model).

Implements the Gray-Scott reaction-diffusion system:
    dU/dt = Du * nabla^2(U) - U*V^2 + f*(1 - U)
    dV/dt = Dv * nabla^2(V) + U*V^2 - (f + k)*V

Named parameter presets produce the mesmerizing, organic patterns (spots,
stripes, coral, mitosis, fingerprints, worms) seen in nature.  The user
picks a preset and watches the pattern self-organise in real-time with
colored ASCII shading.
"""
import curses
import math
import random
import time

from life.constants import SPEEDS, SPEED_LABELS
from life.colors import colormap_addstr, colormap_rgb


# ── Color scheme names for cycling ──────────────────────────────────────
_COLOR_SCHEMES = [
    "ocean",       # cool blue gradient (default, pairs 60-67)
    "thermal",     # warm red-orange-yellow
    "organic",     # green bio gradient
    "purple",      # magenta-violet
    "monochrome",  # grayscale intensity
]

# Map color scheme names to colormaps for truecolor rendering
_SCHEME_COLORMAPS = {
    "ocean": "ocean",
    "thermal": "thermal",
    "organic": "viridis",
    "purple": "plasma",
    "monochrome": "inferno",
}

# Map scheme name -> list of (curses color_pair idx, bold flag) for 8 tiers
# We reuse existing pairs and standard pairs with style flags
def _get_color_tiers(scheme_idx):
    """Return list of 8 (color_pair_index, extra_attr) tuples for the scheme."""
    s = _COLOR_SCHEMES[scheme_idx % len(_COLOR_SCHEMES)]
    if s == "ocean":
        return [(60, 0), (61, 0), (62, 0), (63, 0),
                (64, 0), (65, 0), (66, 0), (67, curses.A_BOLD)]
    elif s == "thermal":
        return [(1, curses.A_DIM), (1, 0), (5, curses.A_DIM), (5, 0),
                (3, curses.A_DIM), (3, 0), (3, curses.A_BOLD), (6, curses.A_BOLD)]
    elif s == "organic":
        return [(1, curses.A_DIM), (1, 0), (2, curses.A_DIM), (2, 0),
                (1, curses.A_BOLD), (3, 0), (3, curses.A_BOLD), (6, curses.A_BOLD)]
    elif s == "purple":
        return [(4, curses.A_DIM), (4, 0), (5, curses.A_DIM), (5, 0),
                (4, curses.A_BOLD), (5, curses.A_BOLD), (7, 0), (7, curses.A_BOLD)]
    else:  # monochrome
        return [(6, curses.A_DIM), (6, curses.A_DIM), (6, 0), (6, 0),
                (6, curses.A_BOLD), (7, 0), (7, curses.A_BOLD), (7, curses.A_BOLD)]


def _enter_rd_mode(self):
    """Enter reaction-diffusion mode -- show preset menu."""
    self.rd_menu = True
    self.rd_menu_sel = 0
    self._flash("Reaction-Diffusion Texture Generator -- select a pattern")


def _exit_rd_mode(self):
    """Exit reaction-diffusion mode."""
    self.rd_mode = False
    self.rd_menu = False
    self.rd_running = False
    self.rd_U = []
    self.rd_V = []
    self._flash("Reaction-Diffusion mode OFF")


def _rd_init(self, preset_idx: int | None = None):
    """Initialize the reaction-diffusion grid with the given preset."""
    max_y, max_x = self.stdscr.getmaxyx()
    self.rd_rows = max(10, max_y - 3)
    self.rd_cols = max(10, (max_x - 1) // 2)
    self.rd_generation = 0

    if preset_idx is not None and 0 <= preset_idx < len(self.RD_PRESETS):
        _, _, f, k = self.RD_PRESETS[preset_idx]
        self.rd_feed = f
        self.rd_kill = k
        self.rd_preset_name = self.RD_PRESETS[preset_idx][0]

    # Initialise color scheme index if not set
    if not hasattr(self, 'rd_color_scheme'):
        self.rd_color_scheme = 0

    # Initialize U=1 everywhere, V=0 everywhere
    rows, cols = self.rd_rows, self.rd_cols
    self.rd_U = [[1.0] * cols for _ in range(rows)]
    self.rd_V = [[0.0] * cols for _ in range(rows)]

    # Seed V with random circular patches to initiate pattern formation
    num_seeds = max(3, (rows * cols) // 600)
    for _ in range(num_seeds):
        sr = random.randint(rows // 6, 5 * rows // 6)
        sc = random.randint(cols // 6, 5 * cols // 6)
        radius = random.randint(2, max(3, min(rows, cols) // 10))
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                dist = math.sqrt(dr * dr + dc * dc)
                if dist <= radius:
                    r2, c2 = sr + dr, sc + dc
                    if 0 <= r2 < rows and 0 <= c2 < cols:
                        # Smooth circular seed with perturbation
                        falloff = max(0.0, 1.0 - dist / radius)
                        self.rd_U[r2][c2] = 0.5 + random.random() * 0.02
                        self.rd_V[r2][c2] = 0.25 * falloff + random.random() * 0.02

    self.rd_mode = True
    self.rd_menu = False
    self.rd_running = False
    self._flash(f"Reaction-Diffusion: {self.rd_preset_name} -- Space to start")


def _rd_step(self):
    """Advance the Gray-Scott simulation by one time step.

    Gray-Scott equations:
        dU/dt = Du * lap(U) - U*V^2 + f*(1 - U)
        dV/dt = Dv * lap(V) + U*V^2 - (f + k)*V

    Uses a 5-point Laplacian stencil with wrapping boundary conditions.
    """
    rows, cols = self.rd_rows, self.rd_cols
    U, V = self.rd_U, self.rd_V
    Du, Dv = self.rd_Du, self.rd_Dv
    f, k = self.rd_feed, self.rd_kill
    dt = self.rd_dt

    newU = [[0.0] * cols for _ in range(rows)]
    newV = [[0.0] * cols for _ in range(rows)]

    for r in range(rows):
        rp = r + 1 if r + 1 < rows else 0
        rm = r - 1  # Python negative indexing wraps
        Ur = U[r]
        Vr = V[r]
        Uu = U[rm]
        Ud = U[rp]
        Vu = V[rm]
        Vd = V[rp]
        for c in range(cols):
            cp = c + 1 if c + 1 < cols else 0
            cm = c - 1

            u = Ur[c]
            v = Vr[c]
            # 5-point discrete Laplacian
            lap_u = Uu[c] + Ud[c] + Ur[cm] + Ur[cp] - 4.0 * u
            lap_v = Vu[c] + Vd[c] + Vr[cm] + Vr[cp] - 4.0 * v

            uvv = u * v * v
            nu = u + dt * (Du * lap_u - uvv + f * (1.0 - u))
            nv = v + dt * (Dv * lap_v + uvv - (f + k) * v)

            # Clamp to [0, 1]
            if nu < 0.0:
                nu = 0.0
            elif nu > 1.0:
                nu = 1.0
            if nv < 0.0:
                nv = 0.0
            elif nv > 1.0:
                nv = 1.0

            newU[r][c] = nu
            newV[r][c] = nv

    self.rd_U = newU
    self.rd_V = newV
    self.rd_generation += 1


def _handle_rd_menu_key(self, key: int) -> bool:
    """Handle keys in the reaction-diffusion preset menu."""
    if key == -1:
        return True
    n = len(self.RD_PRESETS)
    if key == curses.KEY_UP or key == ord("k"):
        self.rd_menu_sel = (self.rd_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.rd_menu_sel = (self.rd_menu_sel + 1) % n
        return True
    if key == ord("q") or key == 27:
        self.rd_menu = False
        self._flash("Reaction-Diffusion cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER):
        self.rd_menu = False
        self.rd_running = False
        self._rd_init(self.rd_menu_sel)
        return True
    return True


def _handle_rd_key(self, key: int) -> bool:
    """Handle keys while in reaction-diffusion mode."""
    if key == -1:
        return True
    if key == ord("q") or key == 27:
        self._exit_rd_mode()
        return True
    if key == ord(" "):
        self.rd_running = not self.rd_running
        self._flash("Playing" if self.rd_running else "Paused")
        return True
    if key == ord("n") or key == ord("."):
        self.rd_running = False
        for _ in range(self.rd_steps_per_frame):
            self._rd_step()
        return True
    if key == ord("r"):
        self._rd_init()
        self._flash("Grid re-seeded")
        return True
    if key == ord("R") or key == ord("m"):
        self.rd_mode = False
        self.rd_running = False
        self.rd_menu = True
        self.rd_menu_sel = 0
        return True
    # Adjust feed rate
    if key == ord("f"):
        self.rd_feed = min(self.rd_feed + 0.001, 0.100)
        self._flash(f"Feed rate: {self.rd_feed:.4f}")
        return True
    if key == ord("F"):
        self.rd_feed = max(self.rd_feed - 0.001, 0.001)
        self._flash(f"Feed rate: {self.rd_feed:.4f}")
        return True
    # Adjust kill rate
    if key == ord("k"):
        self.rd_kill = min(self.rd_kill + 0.001, 0.100)
        self._flash(f"Kill rate: {self.rd_kill:.4f}")
        return True
    if key == ord("K"):
        self.rd_kill = max(self.rd_kill - 0.001, 0.001)
        self._flash(f"Kill rate: {self.rd_kill:.4f}")
        return True
    # Steps per frame
    if key == ord("+") or key == ord("="):
        self.rd_steps_per_frame = min(self.rd_steps_per_frame + 1, 20)
        self._flash(f"Steps/frame: {self.rd_steps_per_frame}")
        return True
    if key == ord("-"):
        self.rd_steps_per_frame = max(self.rd_steps_per_frame - 1, 1)
        self._flash(f"Steps/frame: {self.rd_steps_per_frame}")
        return True
    # Global speed
    if key == ord(">"):
        if self.speed_idx < len(SPEEDS) - 1:
            self.speed_idx += 1
        self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True
    if key == ord("<"):
        if self.speed_idx > 0:
            self.speed_idx -= 1
        self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
        return True
    # Cycle color scheme
    if key == ord("c"):
        if not hasattr(self, 'rd_color_scheme'):
            self.rd_color_scheme = 0
        self.rd_color_scheme = (self.rd_color_scheme + 1) % len(_COLOR_SCHEMES)
        self._flash(f"Color scheme: {_COLOR_SCHEMES[self.rd_color_scheme]}")
        return True
    # Perturb: add a random V patch
    if key == ord("p"):
        rows, cols = self.rd_rows, self.rd_cols
        pr = random.randint(3, rows - 4)
        pc = random.randint(3, cols - 4)
        radius = random.randint(2, max(3, min(rows, cols) // 12))
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                dist = math.sqrt(dr * dr + dc * dc)
                if dist <= radius:
                    nr, nc = pr + dr, pc + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        falloff = max(0.0, 1.0 - dist / radius)
                        self.rd_V[nr][nc] = min(1.0, self.rd_V[nr][nc] + 0.25 * falloff)
                        self.rd_U[nr][nc] = max(0.0, self.rd_U[nr][nc] - 0.15 * falloff)
        self._flash("Perturbed!")
        return True
    # Mouse click to add V
    if key == curses.KEY_MOUSE:
        try:
            _, mx, my, _, _ = curses.getmouse()
            r = my - 1
            c = mx // 2
            rows, cols = self.rd_rows, self.rd_cols
            if 0 <= r < rows and 0 <= c < cols:
                for rr in range(-3, 4):
                    for rc in range(-3, 4):
                        nr, nc = r + rr, c + rc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            d = math.sqrt(rr * rr + rc * rc)
                            if d <= 3.5:
                                falloff = max(0.0, 1.0 - d / 3.5)
                                self.rd_V[nr][nc] = min(1.0, self.rd_V[nr][nc] + 0.25 * falloff)
                                self.rd_U[nr][nc] = max(0.0, self.rd_U[nr][nc] - 0.15 * falloff)
        except curses.error:
            pass
        return True
    return True


def _draw_rd_menu(self, max_y: int, max_x: int):
    """Draw the reaction-diffusion preset selection menu."""
    self.stdscr.erase()
    title = "── Reaction-Diffusion Texture Generator (Gray-Scott) ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    subtitle = "Two chemicals diffuse and react to produce organic patterns"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.color_pair(6))
    except curses.error:
        pass

    n = len(self.RD_PRESETS)
    # Show category headers
    last_category = None
    y = 5
    for i, (name, desc, f_val, k_val) in enumerate(self.RD_PRESETS):
        if y >= max_y - 8:
            break
        # Category dividers at preset indices
        cat = None
        if i == 0:
            cat = "Classic Patterns"
        elif i == 5:
            cat = "Exotic Patterns"
        elif i == 10:
            cat = "Biological Analogues"
        if cat and cat != last_category:
            last_category = cat
            try:
                self.stdscr.addstr(y, 2, f"  {cat}", curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass
            y += 1
            if y >= max_y - 8:
                break

        marker = ">" if i == self.rd_menu_sel else " "
        attr = curses.color_pair(7) | curses.A_BOLD if i == self.rd_menu_sel else curses.color_pair(6)
        line = f" {marker} {name:<16s} f={f_val:.4f} k={k_val:.4f}  {desc}"
        line = line[:max_x - 2]
        try:
            self.stdscr.addstr(y, 1, line, attr)
        except curses.error:
            pass
        y += 1

    # Info box
    info_y = max(y + 1, max_y - 7)
    info_lines = [
        "The Gray-Scott model simulates two chemicals (U and V) that",
        "diffuse and react: U + 2V -> 3V.  Feed rate (f) replenishes U;",
        "kill rate (k) removes V.  Tiny parameter changes produce wildly",
        "different self-organising textures: spots, stripes, coral, worms.",
    ]
    for i, info in enumerate(info_lines):
        iy = info_y + i
        if iy >= max_y - 2:
            break
        try:
            self.stdscr.addstr(iy, 2, info[:max_x - 3], curses.color_pair(1))
        except curses.error:
            pass

    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [j/k]=navigate  [Enter]=select  [q/Esc]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def _draw_rd(self, max_y: int, max_x: int):
    """Draw the reaction-diffusion simulation with colored ASCII shading."""
    self.stdscr.erase()

    # Title bar
    state = ">" if self.rd_running else "||"
    scheme_name = _COLOR_SCHEMES[getattr(self, 'rd_color_scheme', 0)]
    title = (f" Reaction-Diffusion: {self.rd_preset_name}"
             f"  |  gen {self.rd_generation}"
             f"  |  f={self.rd_feed:.4f} k={self.rd_kill:.4f}"
             f"  |  {state}  {self.rd_steps_per_frame}x"
             f"  |  {scheme_name}")
    title = title[:max_x - 1]
    try:
        self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Draw grid -- map V concentration to density glyphs with colour
    draw_start = 1
    draw_rows = min(max_y - 3, self.rd_rows)
    draw_cols = min((max_x - 1) // 2, self.rd_cols)
    density = self.RD_DENSITY

    # Get color tiers for current scheme
    scheme_idx = getattr(self, 'rd_color_scheme', 0)
    tiers = _get_color_tiers(scheme_idx)

    # Truecolor path: use continuous colormap gradient
    tc_buf = getattr(self, 'tc_buf', None)
    use_tc = tc_buf is not None and tc_buf.enabled
    if use_tc:
        scheme_name = _COLOR_SCHEMES[scheme_idx % len(_COLOR_SCHEMES)]
        cmap_name = _SCHEME_COLORMAPS.get(scheme_name, 'ocean')

    for y in range(draw_rows):
        screen_y = draw_start + y
        if screen_y >= max_y - 2:
            break
        Vrow = self.rd_V[y]
        for x in range(draw_cols):
            sx = x * 2
            if sx + 1 >= max_x:
                break
            v = Vrow[x]
            if v < 0.005:
                continue  # leave blank (already erased)

            # Map V to density glyph (1-4, skip 0=blank)
            di = int(v * 4.0)
            if di < 1:
                di = 1
            elif di > 4:
                di = 4
            ch = density[di]

            if use_tc:
                # Continuous 24-bit colour from colormap
                colormap_addstr(self.stdscr, screen_y, sx, ch,
                                cmap_name, v, bold=(v > 0.5), tc_buf=tc_buf)
            else:
                # Discrete 8-tier fallback
                ci = int(v * 7.99)
                if ci > 7:
                    ci = 7
                pair_idx, extra = tiers[ci]
                attr = curses.color_pair(pair_idx) | extra
                try:
                    self.stdscr.addstr(screen_y, sx, ch, attr)
                except curses.error:
                    pass

    # Status bar
    status_y = max_y - 2
    if status_y > 0:
        total = self.rd_rows * self.rd_cols
        v_sum = 0.0
        v_max = 0.0
        for row in self.rd_V:
            for v in row:
                v_sum += v
                if v > v_max:
                    v_max = v
        v_avg = v_sum / total if total > 0 else 0.0
        status = (f" gen {self.rd_generation}  |"
                  f"  V avg={v_avg:.4f}  max={v_max:.4f}  |"
                  f"  Du={self.rd_Du}  Dv={self.rd_Dv}  dt={self.rd_dt}")
        status = status[:max_x - 1]
        try:
            self.stdscr.addstr(status_y, 0, status, curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

    # Hint bar
    hint_y = max_y - 1
    if hint_y > 0:
        now = time.monotonic()
        if self.message and now - self.message_time < 3.0:
            hint = f" {self.message}"
        else:
            hint = " [Space]=play [n]=step [f/F]=feed [k/K]=kill [c]=color [p]=perturb [+/-]=speed [r]=reseed [R]=menu [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


def register(App):
    """Register rd mode methods on the App class."""
    App._enter_rd_mode = _enter_rd_mode
    App._exit_rd_mode = _exit_rd_mode
    App._rd_init = _rd_init
    App._rd_step = _rd_step
    App._handle_rd_menu_key = _handle_rd_menu_key
    App._handle_rd_key = _handle_rd_key
    App._draw_rd_menu = _draw_rd_menu
    App._draw_rd = _draw_rd
