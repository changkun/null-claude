"""Mode: lenia — simulation mode for the life package."""
import curses
import math
import random
import time


from life.constants import SPEEDS, SPEED_LABELS
from life.grid import Grid
from life.colors import colormap_addstr

def _enter_lenia_mode(self):
    """Enter Lenia mode — show preset menu."""
    self.lenia_menu = True
    self.lenia_menu_sel = 0
    self._flash("Lenia — select a species")



def _exit_lenia_mode(self):
    """Exit Lenia mode."""
    self.lenia_mode = False
    self.lenia_menu = False
    self.lenia_running = False
    self.lenia_grid = []
    self.lenia_kernel = []
    self._flash("Lenia mode OFF")



def _lenia_build_kernel(self):
    """Build the ring-shaped convolution kernel for Lenia.

    The kernel is a 2D array of size (2R+1)x(2R+1) with values following
    an exponential ring shape: K(r) = exp(-((r/R - 0.5) / 0.15)^2 / 2).
    Values are normalised so they sum to 1.
    """
    R = self.lenia_R
    size = 2 * R + 1
    kernel = [[0.0] * size for _ in range(size)]
    total = 0.0
    for dy in range(size):
        for dx in range(size):
            dr = math.sqrt((dy - R) ** 2 + (dx - R) ** 2) / R
            # Ring kernel: peak at distance 0.5 from center
            val = math.exp(-((dr - 0.5) / 0.15) ** 2 / 2.0)
            # Zero outside unit circle
            if dr > 1.0:
                val = 0.0
            kernel[dy][dx] = val
            total += val
    # Normalise
    if total > 0:
        for dy in range(size):
            for dx in range(size):
                kernel[dy][dx] /= total
    self.lenia_kernel = kernel



def _lenia_growth(self, u: float) -> float:
    """Growth function: Gaussian bump centered at mu with width sigma.

    Maps kernel convolution potential to growth/decay delta.
    Returns values in [-1, 1]: positive = growth, negative = decay.
    """
    mu = self.lenia_mu
    sigma = self.lenia_sigma
    return 2.0 * math.exp(-((u - mu) / sigma) ** 2 / 2.0) - 1.0



def _lenia_init(self, preset_idx: int | None = None):
    """Initialize the Lenia grid with a preset species."""
    max_y, max_x = self.stdscr.getmaxyx()
    self.lenia_rows = max_y - 3
    self.lenia_cols = (max_x - 1) // 2
    if self.lenia_rows < 10:
        self.lenia_rows = 10
    if self.lenia_cols < 10:
        self.lenia_cols = 10
    self.lenia_generation = 0

    if preset_idx is not None and 0 <= preset_idx < len(self.LENIA_PRESETS):
        _, _, R, mu, sigma, dt = self.LENIA_PRESETS[preset_idx]
        self.lenia_R = R
        self.lenia_mu = mu
        self.lenia_sigma = sigma
        self.lenia_dt = dt
        self.lenia_preset_name = self.LENIA_PRESETS[preset_idx][0]

    # Build kernel
    self._lenia_build_kernel()

    # Initialize grid to zero
    rows, cols = self.lenia_rows, self.lenia_cols
    self.lenia_grid = [[0.0] * cols for _ in range(rows)]

    # Seed with circular blobs of varying density
    num_seeds = max(2, (rows * cols) // 1200)
    for _ in range(num_seeds):
        cr = random.randint(rows // 4, 3 * rows // 4)
        cc = random.randint(cols // 4, 3 * cols // 4)
        rad = random.randint(max(3, self.lenia_R // 2), max(4, self.lenia_R))
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                dist = math.sqrt(dr * dr + dc * dc)
                if dist <= rad:
                    r2 = (cr + dr) % rows
                    c2 = (cc + dc) % cols
                    # Smooth falloff from center
                    val = 0.5 + 0.5 * math.cos(math.pi * dist / rad)
                    # Add some noise
                    val *= 0.8 + random.random() * 0.4
                    val = max(0.0, min(1.0, val))
                    self.lenia_grid[r2][c2] = max(self.lenia_grid[r2][c2], val)



def _lenia_step(self):
    """Advance the Lenia simulation by one time step.

    For each cell:
    1. Convolve with the ring kernel to get local potential U
    2. Apply growth function G(U) to get delta
    3. Update: A(t+dt) = clip(A(t) + dt * G(U), 0, 1)
    """
    rows, cols = self.lenia_rows, self.lenia_cols
    grid = self.lenia_grid
    kernel = self.lenia_kernel
    R = self.lenia_R
    ksize = 2 * R + 1
    dt = self.lenia_dt

    new_grid = [[0.0] * cols for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            # Convolution: sum of kernel * neighborhood
            potential = 0.0
            for ky in range(ksize):
                kr = (r + ky - R) % rows
                krow = kernel[ky]
                grow = grid[kr]
                for kx in range(ksize):
                    kval = krow[kx]
                    if kval == 0.0:
                        continue
                    kc = (c + kx - R) % cols
                    potential += kval * grow[kc]

            # Growth function
            delta = self._lenia_growth(potential)

            # Update cell
            val = grid[r][c] + dt * delta
            if val < 0.0:
                val = 0.0
            elif val > 1.0:
                val = 1.0
            new_grid[r][c] = val

    self.lenia_grid = new_grid
    self.lenia_generation += 1



def _handle_lenia_menu_key(self, key: int) -> bool:
    """Handle keys in the Lenia preset menu."""
    if key == -1:
        return True
    n = len(self.LENIA_PRESETS)
    if key == curses.KEY_UP or key == ord("k"):
        self.lenia_menu_sel = (self.lenia_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.lenia_menu_sel = (self.lenia_menu_sel + 1) % n
        return True
    if key == ord("q") or key == 27:
        self.lenia_menu = False
        self._flash("Lenia cancelled")
        return True
    if key in (10, 13, curses.KEY_ENTER):
        self.lenia_menu = False
        self.lenia_mode = True
        self.lenia_running = False
        self._lenia_init(self.lenia_menu_sel)
        name = self.LENIA_PRESETS[self.lenia_menu_sel][0]
        self._flash(f"Lenia [{name}] — Space=play, µ/σ=adjust params, q=exit")
        return True
    return True



def _handle_lenia_key(self, key: int) -> bool:
    """Handle keys while in Lenia mode."""
    if key == -1:
        return True
    if key == ord("q") or key == 27:
        self._exit_lenia_mode()
        return True
    if key == ord(" "):
        self.lenia_running = not self.lenia_running
        self._flash("Playing" if self.lenia_running else "Paused")
        return True
    if key == ord("n") or key == ord("."):
        self.lenia_running = False
        for _ in range(self.lenia_steps_per_frame):
            self._lenia_step()
        return True
    if key == ord("r"):
        self._lenia_init()
        self._flash("Grid re-seeded")
        return True
    if key == ord("R") or key == ord("m"):
        self.lenia_mode = False
        self.lenia_running = False
        self.lenia_menu = True
        self.lenia_menu_sel = 0
        return True
    # Adjust growth center (mu)
    if key == ord("u"):
        self.lenia_mu = min(self.lenia_mu + 0.005, 0.500)
        self._flash(f"Growth center (µ): {self.lenia_mu:.3f}")
        return True
    if key == ord("U"):
        self.lenia_mu = max(self.lenia_mu - 0.005, 0.010)
        self._flash(f"Growth center (µ): {self.lenia_mu:.3f}")
        return True
    # Adjust growth width (sigma)
    if key == ord("s"):
        self.lenia_sigma = min(self.lenia_sigma + 0.001, 0.100)
        self._flash(f"Growth width (σ): {self.lenia_sigma:.3f}")
        return True
    if key == ord("S"):
        self.lenia_sigma = max(self.lenia_sigma - 0.001, 0.001)
        self._flash(f"Growth width (σ): {self.lenia_sigma:.3f}")
        return True
    # Adjust kernel radius
    if key == ord("d"):
        self.lenia_R = min(self.lenia_R + 1, 25)
        self._lenia_build_kernel()
        self._flash(f"Kernel radius: {self.lenia_R}")
        return True
    if key == ord("D"):
        self.lenia_R = max(self.lenia_R - 1, 3)
        self._lenia_build_kernel()
        self._flash(f"Kernel radius: {self.lenia_R}")
        return True
    # Adjust timestep
    if key == ord("t"):
        self.lenia_dt = min(self.lenia_dt + 0.01, 0.50)
        self._flash(f"Time step (dt): {self.lenia_dt:.2f}")
        return True
    if key == ord("T"):
        self.lenia_dt = max(self.lenia_dt - 0.01, 0.01)
        self._flash(f"Time step (dt): {self.lenia_dt:.2f}")
        return True
    # Adjust simulation speed (steps per frame)
    if key == ord("+") or key == ord("="):
        self.lenia_steps_per_frame = min(self.lenia_steps_per_frame + 1, 10)
        self._flash(f"Steps/frame: {self.lenia_steps_per_frame}")
        return True
    if key == ord("-"):
        self.lenia_steps_per_frame = max(self.lenia_steps_per_frame - 1, 1)
        self._flash(f"Steps/frame: {self.lenia_steps_per_frame}")
        return True
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
    return True



def _draw_lenia_menu(self, max_y: int, max_x: int):
    """Draw the Lenia preset selection menu."""
    title = "── Lenia (Continuous Cellular Automaton) ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass
    subtitle = "Smooth lifelike organisms from continuous growth/decay dynamics"
    try:
        self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                           curses.color_pair(6))
    except curses.error:
        pass

    n = len(self.LENIA_PRESETS)
    for i, (name, desc, R, mu, sigma, dt) in enumerate(self.LENIA_PRESETS):
        y = 5 + i
        if y >= max_y - 12:
            break
        line = f"  {name:<18s} R={R:<3d} mu={mu:.3f} s={sigma:.3f} dt={dt:.2f}  {desc}"
        line = line[:max_x - 2]
        attr = curses.color_pair(6)
        if i == self.lenia_menu_sel:
            attr = curses.color_pair(7) | curses.A_BOLD
        try:
            self.stdscr.addstr(y, 1, line, attr)
        except curses.error:
            pass

    info_y = 5 + min(n, max_y - 17) + 1
    info_lines = [
        "Lenia generalises Conway's Game of Life to continuous space:",
        "cells hold real values 0-1, and a smooth ring-shaped kernel",
        "replaces the discrete neighbor count. A Gaussian growth",
        "function maps the local potential to growth or decay,",
        "producing organic, self-organizing lifeforms that glide,",
        "replicate, and pulsate with striking biological realism.",
    ]
    for i, info in enumerate(info_lines):
        y = info_y + i
        if y >= max_y - 2:
            break
        try:
            self.stdscr.addstr(y, 2, info[:max_x - 3], curses.color_pair(1))
        except curses.error:
            pass

    hint_y = max_y - 1
    if hint_y > 0:
        hint = " [j/k]=navigate [Enter]=select [q/Esc]=cancel"
        try:
            self.stdscr.addstr(hint_y, 0, hint[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass



def _draw_lenia(self, max_y: int, max_x: int):
    """Draw the Lenia simulation."""
    # Title bar
    title = (f" Lenia [{self.lenia_preset_name}]"
             f"  Gen: {self.lenia_generation}"
             f"  R={self.lenia_R}"
             f"  mu={self.lenia_mu:.3f}  sigma={self.lenia_sigma:.3f}"
             f"  dt={self.lenia_dt:.2f}")
    state = " PLAY" if self.lenia_running else " PAUSE"
    title += f"  {state}"
    title = title[:max_x - 1]
    try:
        self.stdscr.addstr(0, 0, title, curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Draw grid — map cell value to density glyphs with colour
    draw_start = 1
    draw_rows = min(max_y - 3, self.lenia_rows)
    draw_cols = min((max_x - 1) // 2, self.lenia_cols)
    density = self.LENIA_DENSITY

    # Colour pair lookup: 8 tiers (pairs 70-77)
    color_tiers = [70, 71, 72, 73, 74, 75, 76, 77]

    # Truecolor path: continuous magma gradient
    tc_buf = getattr(self, 'tc_buf', None)
    use_tc = tc_buf is not None and tc_buf.enabled

    for y in range(draw_rows):
        screen_y = draw_start + y
        if screen_y >= max_y - 2:
            break
        row = self.lenia_grid[y]
        for x in range(draw_cols):
            sx = x * 2
            if sx + 1 >= max_x:
                break
            v = row[x]
            if v < 0.005:
                continue  # leave blank
            # Map value to density glyph (1-4)
            di = int(v * 4.0)
            if di < 1:
                di = 1
            elif di > 4:
                di = 4
            ch = density[di]

            if use_tc:
                colormap_addstr(self.stdscr, screen_y, sx, ch,
                                'magma', v, bold=(v > 0.5), tc_buf=tc_buf)
            else:
                # Map value to colour tier (0-7)
                ci = int(v * 7.99)
                if ci > 7:
                    ci = 7
                attr = curses.color_pair(color_tiers[ci])
                if v > 0.5:
                    attr |= curses.A_BOLD
                try:
                    self.stdscr.addstr(screen_y, sx, ch, attr)
                except curses.error:
                    pass

    # Status bar
    status_y = max_y - 2
    if status_y > 0:
        total = self.lenia_rows * self.lenia_cols
        v_sum = 0.0
        v_max = 0.0
        alive = 0
        for row in self.lenia_grid:
            for v in row:
                v_sum += v
                if v > v_max:
                    v_max = v
                if v > 0.01:
                    alive += 1
        v_avg = v_sum / total if total > 0 else 0.0
        status = (f" Gen: {self.lenia_generation}  |"
                  f"  Avg: {v_avg:.4f}  Max: {v_max:.4f}  |"
                  f"  Active: {alive}/{total}  |"
                  f"  Speed: {SPEED_LABELS[self.speed_idx]}")
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
            hint = " [Space]=play [n]=step [u/U]=mu+/- [s/S]=sigma+/- [d/D]=radius+/- [t/T]=dt+/- [r]=reseed [R]=menu [q]=exit"
        hint = hint[:max_x - 1]
        try:
            self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


LENIA_PRESETS = [
    # (name, description, radius, mu, sigma, dt)
    ("Orbium", "Smooth glider — stable traveling organism", 13, 0.15, 0.015, 0.1),
    ("Geminium", "Self-replicating twin organism", 10, 0.14, 0.014, 0.1),
    ("Scutium", "Shield-shaped stationary life", 12, 0.16, 0.016, 0.1),
    ("Hydrogeminium", "Fluid replicator with organic motion", 15, 0.15, 0.017, 0.05),
    ("Pentadecathlon", "Pulsating ring oscillator", 8, 0.12, 0.012, 0.1),
    ("Wanderer", "Erratic slow-moving blob", 10, 0.13, 0.020, 0.08),
]

LENIA_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]


def register(App):
    """Register lenia mode methods on the App class."""
    App.LENIA_PRESETS = LENIA_PRESETS
    App.LENIA_DENSITY = LENIA_DENSITY
    App._enter_lenia_mode = _enter_lenia_mode
    App._exit_lenia_mode = _exit_lenia_mode
    App._lenia_build_kernel = _lenia_build_kernel
    App._lenia_growth = _lenia_growth
    App._lenia_init = _lenia_init
    App._lenia_step = _lenia_step
    App._handle_lenia_menu_key = _handle_lenia_menu_key
    App._handle_lenia_key = _handle_lenia_key
    App._draw_lenia_menu = _draw_lenia_menu
    App._draw_lenia = _draw_lenia

