"""Parameter Tuning Overlay — real-time interactive parameter adjustment HUD.

Pressing ``P`` while any simulation mode is active toggles a translucent
overlay listing that mode's tunable parameters.  Arrow keys navigate and
adjust values in real-time while the simulation keeps running.
"""
import curses

from life.registry import MODE_DISPATCH


# ── Explicit tunable-parameter definitions ────────────────────────────────
# Each entry maps a mode *prefix* (e.g. "boids") to a list of parameter
# descriptors.  Every descriptor is a dict:
#   attr  – the self.<attr> attribute name on App
#   name  – human-readable label shown in the HUD
#   min   – minimum allowed value
#   max   – maximum allowed value
#   step  – delta per ←/→ keypress
#   fmt   – Python format spec (e.g. ".2f", "d")

TUNABLE_PARAMS: dict[str, list[dict]] = {
    # ── Classic CA ──
    "wolfram": [
        {"attr": "wolfram_rule", "name": "Rule #", "min": 0, "max": 255, "step": 1, "fmt": "d"},
    ],
    "cyclic": [
        {"attr": "cyclic_n_states", "name": "# States", "min": 3, "max": 24, "step": 1, "fmt": "d"},
        {"attr": "cyclic_threshold", "name": "Threshold", "min": 1, "max": 8, "step": 1, "fmt": "d"},
    ],
    "hodge": [
        {"attr": "hodge_n_states", "name": "# States", "min": 10, "max": 500, "step": 10, "fmt": "d"},
        {"attr": "hodge_k1", "name": "k1 (infection)", "min": 0, "max": 20, "step": 1, "fmt": "d"},
        {"attr": "hodge_k2", "name": "k2 (recovery)", "min": 0, "max": 20, "step": 1, "fmt": "d"},
        {"attr": "hodge_g", "name": "g (growth)", "min": 0, "max": 200, "step": 5, "fmt": "d"},
    ],
    # ── Particle & Swarm ──
    "boids": [
        {"attr": "boids_separation_radius", "name": "Separation R", "min": 1.0, "max": 15.0, "step": 0.5, "fmt": ".1f"},
        {"attr": "boids_alignment_radius", "name": "Alignment R", "min": 2.0, "max": 30.0, "step": 1.0, "fmt": ".1f"},
        {"attr": "boids_cohesion_radius", "name": "Cohesion R", "min": 2.0, "max": 40.0, "step": 1.0, "fmt": ".1f"},
        {"attr": "boids_separation_weight", "name": "Separation W", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "boids_alignment_weight", "name": "Alignment W", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "boids_cohesion_weight", "name": "Cohesion W", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "boids_max_speed", "name": "Max Speed", "min": 0.2, "max": 5.0, "step": 0.1, "fmt": ".2f"},
    ],
    "plife": [
        {"attr": "plife_force_scale", "name": "Force Scale", "min": 0.1, "max": 20.0, "step": 0.5, "fmt": ".1f"},
        {"attr": "plife_friction", "name": "Friction", "min": 0.01, "max": 1.0, "step": 0.01, "fmt": ".3f"},
        {"attr": "plife_interact_radius", "name": "Interact R", "min": 5.0, "max": 50.0, "step": 1.0, "fmt": ".1f"},
    ],
    "physarum": [
        {"attr": "physarum_sensor_angle", "name": "Sensor Angle", "min": 0.05, "max": 1.5, "step": 0.05, "fmt": ".2f"},
        {"attr": "physarum_sensor_dist", "name": "Sensor Dist", "min": 1.0, "max": 30.0, "step": 1.0, "fmt": ".1f"},
        {"attr": "physarum_turn_speed", "name": "Turn Speed", "min": 0.05, "max": 1.5, "step": 0.05, "fmt": ".2f"},
        {"attr": "physarum_move_speed", "name": "Move Speed", "min": 0.2, "max": 5.0, "step": 0.2, "fmt": ".1f"},
        {"attr": "physarum_deposit", "name": "Deposit", "min": 0.5, "max": 20.0, "step": 0.5, "fmt": ".1f"},
        {"attr": "physarum_decay", "name": "Decay", "min": 0.001, "max": 0.1, "step": 0.005, "fmt": ".3f"},
    ],
    "nbody": [
        {"attr": "nbody_grav_const", "name": "Gravity G", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "nbody_dt", "name": "Time Step", "min": 0.005, "max": 0.2, "step": 0.005, "fmt": ".3f"},
        {"attr": "nbody_softening", "name": "Softening", "min": 0.1, "max": 3.0, "step": 0.1, "fmt": ".2f"},
    ],
    "aco": [
        {"attr": "aco_evaporation", "name": "Evaporation", "min": 0.01, "max": 0.5, "step": 0.01, "fmt": ".3f"},
        {"attr": "aco_deposit_strength", "name": "Deposit Str", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
    ],
    # ── Physics & Waves ──
    "wave": [
        {"attr": "wave_c", "name": "Wave Speed c", "min": 0.05, "max": 0.50, "step": 0.01, "fmt": ".2f"},
        {"attr": "wave_damping", "name": "Damping", "min": 0.90, "max": 1.0, "step": 0.005, "fmt": ".3f"},
    ],
    "ising": [
        {"attr": "ising_temperature", "name": "Temperature", "min": 0.01, "max": 10.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "ising_ext_field", "name": "Ext. Field", "min": -2.0, "max": 2.0, "step": 0.1, "fmt": ".2f"},
    ],
    "kuramoto": [
        {"attr": "kuramoto_coupling", "name": "Coupling K", "min": 0.0, "max": 10.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "kuramoto_dt", "name": "Time Step", "min": 0.01, "max": 0.5, "step": 0.01, "fmt": ".2f"},
        {"attr": "kuramoto_noise", "name": "Noise", "min": 0.0, "max": 5.0, "step": 0.1, "fmt": ".2f"},
    ],
    "cloth": [
        {"attr": "cloth_gravity", "name": "Gravity", "min": 0.0, "max": 2.0, "step": 0.05, "fmt": ".2f"},
        {"attr": "cloth_damping", "name": "Damping", "min": 0.9, "max": 1.0, "step": 0.005, "fmt": ".3f"},
        {"attr": "cloth_wind", "name": "Wind", "min": -1.0, "max": 1.0, "step": 0.05, "fmt": ".2f"},
    ],
    "dpend": [
        {"attr": "dpend_gravity", "name": "Gravity", "min": 1.0, "max": 30.0, "step": 0.5, "fmt": ".1f"},
        {"attr": "dpend_dt", "name": "Time Step", "min": 0.001, "max": 0.05, "step": 0.001, "fmt": ".3f"},
    ],
    "fdtd": [
        {"attr": "fdtd_source_freq", "name": "Source Freq", "min": 0.01, "max": 1.0, "step": 0.01, "fmt": ".2f"},
    ],
    # ── Fluid Dynamics ──
    "fluid": [
        {"attr": "fluid_viscosity", "name": "Viscosity", "min": 0.01, "max": 0.5, "step": 0.01, "fmt": ".3f"},
    ],
    "ns": [
        {"attr": "ns_viscosity", "name": "Viscosity", "min": 0.0001, "max": 0.01, "step": 0.0001, "fmt": ".4f"},
        {"attr": "ns_dt", "name": "Time Step", "min": 0.01, "max": 2.0, "step": 0.01, "fmt": ".2f"},
    ],
    "sph": [
        {"attr": "sph_gravity", "name": "Gravity", "min": 0.0, "max": 2.0, "step": 0.05, "fmt": ".2f"},
        {"attr": "sph_rest_density", "name": "Rest Density", "min": 0.5, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "sph_viscosity", "name": "Viscosity", "min": 0.01, "max": 1.0, "step": 0.01, "fmt": ".2f"},
    ],
    # ── Chemical & Biological ──
    "rd": [
        {"attr": "rd_feed", "name": "Feed Rate f", "min": 0.001, "max": 0.100, "step": 0.001, "fmt": ".4f"},
        {"attr": "rd_kill", "name": "Kill Rate k", "min": 0.001, "max": 0.100, "step": 0.001, "fmt": ".4f"},
        {"attr": "rd_Du", "name": "Diffusion U", "min": 0.05, "max": 0.5, "step": 0.01, "fmt": ".2f"},
        {"attr": "rd_Dv", "name": "Diffusion V", "min": 0.01, "max": 0.2, "step": 0.005, "fmt": ".3f"},
        {"attr": "rd_dt", "name": "Time Step", "min": 0.1, "max": 2.0, "step": 0.1, "fmt": ".1f"},
    ],
    "fire": [
        {"attr": "fire_p_grow", "name": "Growth Prob", "min": 0.001, "max": 0.1, "step": 0.001, "fmt": ".4f"},
        {"attr": "fire_p_lightning", "name": "Lightning P", "min": 0.0001, "max": 0.01, "step": 0.0001, "fmt": ".4f"},
        {"attr": "fire_ash_decay", "name": "Ash Decay", "min": 0.01, "max": 1.0, "step": 0.01, "fmt": ".2f"},
    ],
    "sir": [
        {"attr": "sir_transmission_prob", "name": "Transmit P", "min": 0.01, "max": 1.0, "step": 0.01, "fmt": ".2f"},
        {"attr": "sir_recovery_time", "name": "Recovery T", "min": 3, "max": 100, "step": 1, "fmt": "d"},
        {"attr": "sir_mortality_rate", "name": "Mortality", "min": 0.0, "max": 1.0, "step": 0.01, "fmt": ".2f"},
        {"attr": "sir_infection_radius", "name": "Infect R", "min": 1.0, "max": 5.0, "step": 0.5, "fmt": ".1f"},
    ],
    "lv": [
        {"attr": "lv_grass_regrow", "name": "Grass Regrow", "min": 1, "max": 30, "step": 1, "fmt": "d"},
        {"attr": "lv_prey_breed", "name": "Prey Breed T", "min": 2, "max": 30, "step": 1, "fmt": "d"},
        {"attr": "lv_pred_breed", "name": "Pred Breed T", "min": 2, "max": 30, "step": 1, "fmt": "d"},
        {"attr": "lv_prey_gain", "name": "Prey Energy", "min": 1, "max": 20, "step": 1, "fmt": "d"},
        {"attr": "lv_pred_gain", "name": "Pred Energy", "min": 1, "max": 30, "step": 1, "fmt": "d"},
    ],
    "bz": [
        {"attr": "bz_alpha", "name": "Alpha", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "bz_beta", "name": "Beta", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "bz_gamma", "name": "Gamma", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
    ],
    "chemo": [
        {"attr": "chemo_diffusion", "name": "Diffusion", "min": 0.01, "max": 1.0, "step": 0.01, "fmt": ".2f"},
        {"attr": "chemo_decay", "name": "Decay", "min": 0.001, "max": 0.1, "step": 0.005, "fmt": ".3f"},
        {"attr": "chemo_sensitivity", "name": "Sensitivity", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".1f"},
    ],
    "snn": [
        {"attr": "snn_coupling", "name": "Coupling", "min": 0.1, "max": 10.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "snn_noise", "name": "Noise", "min": 0.0, "max": 5.0, "step": 0.1, "fmt": ".2f"},
    ],
    # ── Game Theory & Social ──
    "spd": [
        {"attr": "spd_temptation", "name": "Temptation T", "min": 1.0, "max": 3.0, "step": 0.1, "fmt": ".2f"},
    ],
    "schelling": [
        {"attr": "schelling_tolerance", "name": "Tolerance", "min": 0.1, "max": 0.9, "step": 0.05, "fmt": ".2f"},
    ],
    "rps": [
        {"attr": "rps_threshold", "name": "Threshold", "min": 1, "max": 8, "step": 1, "fmt": "d"},
    ],
    "mkt": [
        {"attr": "mkt_volatility", "name": "Volatility", "min": 0.01, "max": 1.0, "step": 0.01, "fmt": ".2f"},
    ],
    # ── Fractals & Chaos ──
    "snowflake": [
        {"attr": "snowflake_beta", "name": "Beta (vapor)", "min": 0.1, "max": 2.0, "step": 0.05, "fmt": ".2f"},
        {"attr": "snowflake_gamma", "name": "Gamma (melt)", "min": 0.001, "max": 0.1, "step": 0.005, "fmt": ".3f"},
    ],
    # ── Complex Simulations ──
    "traffic": [
        {"attr": "traffic_density", "name": "Density", "min": 0.05, "max": 0.95, "step": 0.05, "fmt": ".2f"},
        {"attr": "traffic_slow_prob", "name": "Slow Prob", "min": 0.0, "max": 1.0, "step": 0.05, "fmt": ".2f"},
        {"attr": "traffic_max_speed", "name": "Max Speed", "min": 1, "max": 10, "step": 1, "fmt": "d"},
    ],
    "galaxy": [
        {"attr": "galaxy_grav_const", "name": "Gravity G", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "galaxy_dt", "name": "Time Step", "min": 0.005, "max": 0.1, "step": 0.005, "fmt": ".3f"},
    ],
    "moldyn": [
        {"attr": "moldyn_temperature", "name": "Temperature", "min": 0.1, "max": 5.0, "step": 0.1, "fmt": ".2f"},
        {"attr": "moldyn_dt", "name": "Time Step", "min": 0.001, "max": 0.05, "step": 0.001, "fmt": ".3f"},
    ],
    "spinglass": [
        {"attr": "spinglass_temperature", "name": "Temperature", "min": 0.01, "max": 5.0, "step": 0.1, "fmt": ".2f"},
    ],
}


# Attributes to exclude from auto-detection (suffixes or full attr names)
_SKIP_SUFFIXES = (
    '_mode', '_menu', '_running', '_generation', '_gen', '_rows', '_cols',
    '_agents', '_trail', '_grid', '_cells', '_num_agents', '_preset_name',
    '_steps_per_frame', '_menu_sel', '_preset_idx', '_phase', '_speed',
    '_speed_mult', '_history', '_tick', '_frame', '_time', '_last',
    '_count', '_data', '_buf', '_buffer', '_queue', '_map', '_hash',
    '_colors', '_chars', '_arrows', '_presets', '_prev', '_next',
    '_view', '_scroll', '_sel', '_selected', '_tab', '_show',
    '_enabled', '_active', '_paused', '_finished', '_started',
    '_recording', '_exporting', '_results', '_stats', '_log',
    '_width', '_height', '_size', '_len', '_max_history',
    '_color_scheme', '_draw_mode', '_tool', '_element',
)


def _get_active_mode_prefix(self) -> str | None:
    """Return the prefix of the currently active dispatch-table mode, or None."""
    for md in MODE_DISPATCH:
        if getattr(self, md['attr'], False):
            return md['prefix']
    # Check explicit modes
    if getattr(self, 'evo_mode', False):
        return 'evo'
    return None


def _get_tunable_params(self) -> list[dict]:
    """Return the list of tunable parameter descriptors for the active mode.

    Uses explicit definitions from TUNABLE_PARAMS if available, otherwise
    falls back to auto-detecting numeric self.{prefix}_* attributes.
    """
    prefix = self._get_active_mode_prefix()
    if prefix is None:
        return []

    # 1. Try explicit definitions
    if prefix in TUNABLE_PARAMS:
        # Filter to only params that actually exist on self
        result = []
        for p in TUNABLE_PARAMS[prefix]:
            if hasattr(self, p['attr']):
                result.append(p)
        if result:
            return result

    # 2. Auto-detect: scan self.__dict__ for {prefix}_{name} floats/ints
    params = []
    search = f'{prefix}_'
    for attr_name, value in sorted(self.__dict__.items()):
        if not attr_name.startswith(search):
            continue
        if not isinstance(value, (int, float)):
            continue
        if isinstance(value, bool):
            continue
        # Skip internal/structural attributes
        skip = False
        for suffix in _SKIP_SUFFIXES:
            if attr_name.endswith(suffix):
                skip = True
                break
        if skip:
            continue
        # Skip very large values (likely sizes/counts, not parameters)
        if isinstance(value, int) and abs(value) > 10000:
            continue

        # Build a human-readable name from the attribute
        short = attr_name[len(search):]
        label = short.replace('_', ' ').title()

        if isinstance(value, float):
            # Determine reasonable step & range
            abs_val = abs(value) if value != 0 else 1.0
            if abs_val < 0.01:
                step, fmt = 0.001, ".4f"
            elif abs_val < 0.1:
                step, fmt = 0.01, ".3f"
            elif abs_val < 1.0:
                step, fmt = 0.05, ".2f"
            elif abs_val < 10.0:
                step, fmt = 0.1, ".2f"
            else:
                step, fmt = 1.0, ".1f"
            mn = 0.0 if value >= 0 else -abs_val * 5
            mx = max(abs_val * 3, step * 2)
            params.append({"attr": attr_name, "name": label,
                           "min": mn, "max": mx, "step": step, "fmt": fmt})
        else:
            # int
            abs_val = abs(value) if value != 0 else 1
            step = max(1, abs_val // 10) if abs_val > 10 else 1
            mn = 0 if value >= 0 else -abs_val * 5
            mx = max(abs_val * 3, 2)
            params.append({"attr": attr_name, "name": label,
                           "min": mn, "max": mx, "step": step, "fmt": "d"})

    return params


def _toggle_param_tuner(self):
    """Toggle the parameter tuning overlay on/off."""
    self.param_tuner_active = not self.param_tuner_active
    if self.param_tuner_active:
        self.param_tuner_params = self._get_tunable_params()
        self.param_tuner_sel = 0
        if not self.param_tuner_params:
            self.param_tuner_active = False
            self._flash("No tunable parameters for this mode")
            return
        self._flash("Parameter Tuner ON — ↑↓ select, ←→ adjust")
    else:
        self._flash("Parameter Tuner OFF")


def _handle_param_tuner_key(self, key: int) -> bool:
    """Handle keys when the parameter tuning overlay is active.

    Returns True if the key was consumed, False otherwise.
    """
    if not self.param_tuner_active:
        return False

    params = self.param_tuner_params
    if not params:
        return False

    n = len(params)

    if key in (curses.KEY_UP, ord('k')):
        self.param_tuner_sel = (self.param_tuner_sel - 1) % n
        return True
    elif key in (curses.KEY_DOWN, ord('j')):
        self.param_tuner_sel = (self.param_tuner_sel + 1) % n
        return True
    elif key in (curses.KEY_RIGHT, ord('l')):
        p = params[self.param_tuner_sel]
        cur = getattr(self, p['attr'], 0)
        # Shift = 10x step
        new = cur + p['step']
        if isinstance(p['min'], int) and isinstance(p['max'], int) and p['fmt'] == 'd':
            new = min(int(new), p['max'])
        else:
            new = min(float(new), float(p['max']))
        setattr(self, p['attr'], new)
        return True
    elif key in (curses.KEY_LEFT, ord('h')):
        p = params[self.param_tuner_sel]
        cur = getattr(self, p['attr'], 0)
        new = cur - p['step']
        if isinstance(p['min'], int) and isinstance(p['max'], int) and p['fmt'] == 'd':
            new = max(int(new), p['min'])
        else:
            new = max(float(new), float(p['min']))
        setattr(self, p['attr'], new)
        return True
    elif key == ord(']'):
        # Large step (10x)
        p = params[self.param_tuner_sel]
        cur = getattr(self, p['attr'], 0)
        new = cur + p['step'] * 10
        if isinstance(p['min'], int) and isinstance(p['max'], int) and p['fmt'] == 'd':
            new = min(int(new), p['max'])
        else:
            new = min(float(new), float(p['max']))
        setattr(self, p['attr'], new)
        return True
    elif key == ord('['):
        # Large step (10x)
        p = params[self.param_tuner_sel]
        cur = getattr(self, p['attr'], 0)
        new = cur - p['step'] * 10
        if isinstance(p['min'], int) and isinstance(p['max'], int) and p['fmt'] == 'd':
            new = max(int(new), p['min'])
        else:
            new = max(float(new), float(p['min']))
        setattr(self, p['attr'], new)
        return True
    elif key == ord('0'):
        # Reset: re-fetch params from current state (effectively a refresh)
        self.param_tuner_params = self._get_tunable_params()
        self.param_tuner_sel = min(self.param_tuner_sel, max(0, len(self.param_tuner_params) - 1))
        self._flash("Params refreshed")
        return True

    # Don't consume other keys — let them pass through to the mode
    return False


def _draw_param_tuner_overlay(self, max_y: int, max_x: int):
    """Draw the parameter tuning HUD overlay on the right side of the screen."""
    if not self.param_tuner_active:
        return

    # Auto-close if mode changed or exited
    if self._get_active_mode_prefix() is None:
        self.param_tuner_active = False
        return

    params = self.param_tuner_params
    if not params:
        return

    # Panel dimensions
    panel_w = min(42, max_x - 4)
    panel_h = min(len(params) + 4, max_y - 2)  # +4 for title, header, footer
    if panel_w < 20 or panel_h < 4:
        return

    # Position: right side of screen
    px = max_x - panel_w - 1
    py = 1

    # Draw panel background
    bg_attr = curses.color_pair(7) | curses.A_DIM
    title_attr = curses.color_pair(7) | curses.A_BOLD
    sel_attr = curses.color_pair(3) | curses.A_BOLD | curses.A_REVERSE
    val_attr = curses.color_pair(6)
    bar_attr = curses.color_pair(2)
    hint_attr = curses.color_pair(6) | curses.A_DIM

    # Title bar
    prefix = self._get_active_mode_prefix() or "?"
    title = f" PARAMS: {prefix.upper()} "
    title_line = title.center(panel_w, '─')
    try:
        self.stdscr.addstr(py, px, title_line[:panel_w], title_attr)
    except curses.error:
        pass

    # Visible window (scroll if needed)
    visible_rows = panel_h - 3  # space for title, footer
    scroll_off = 0
    if self.param_tuner_sel >= scroll_off + visible_rows:
        scroll_off = self.param_tuner_sel - visible_rows + 1
    elif self.param_tuner_sel < scroll_off:
        scroll_off = self.param_tuner_sel

    # Draw parameters
    for vi in range(visible_rows):
        pi = scroll_off + vi
        if pi >= len(params):
            break
        p = params[pi]
        y = py + 1 + vi
        if y >= max_y - 1:
            break

        cur = getattr(self, p['attr'], 0)
        name = p['name']
        fmt = p['fmt']

        # Format value
        if fmt == 'd':
            val_str = f"{int(cur)}"
        else:
            val_str = f"{cur:{fmt}}"

        # Build progress bar
        mn, mx = p['min'], p['max']
        if mx > mn:
            frac = max(0.0, min(1.0, (float(cur) - float(mn)) / (float(mx) - float(mn))))
        else:
            frac = 0.5
        bar_w = max(4, panel_w - len(name) - len(val_str) - 6)
        filled = int(frac * bar_w)
        bar = '█' * filled + '░' * (bar_w - filled)

        # Compose line
        line = f" {name:<{max(8, panel_w - bar_w - len(val_str) - 4)}s}{val_str} {bar} "

        # Truncate to panel width
        line = line[:panel_w]

        is_sel = (pi == self.param_tuner_sel)
        attr = sel_attr if is_sel else bg_attr
        try:
            self.stdscr.addstr(y, px, line, attr)
        except curses.error:
            pass

    # Footer with hints
    footer_y = py + 1 + min(visible_rows, len(params))
    if footer_y < max_y:
        hint = " ↑↓=sel ←→=adj []/10x P=close"
        hint_line = hint[:panel_w].ljust(panel_w, '─')
        try:
            self.stdscr.addstr(footer_y, px, hint_line[:panel_w], hint_attr)
        except curses.error:
            pass


def register(App):
    """Register parameter tuner methods on the App class."""
    App._get_active_mode_prefix = _get_active_mode_prefix
    App._get_tunable_params = _get_tunable_params
    App._toggle_param_tuner = _toggle_param_tuner
    App._handle_param_tuner_key = _handle_param_tuner_key
    App._draw_param_tuner_overlay = _draw_param_tuner_overlay
