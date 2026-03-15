"""Electric Circuit Simulator — grid-based circuit builder with real-time
current flow, voltage heatmap, and oscilloscope view.

Users place components (batteries, resistors, capacitors, inductors, LEDs,
switches, wires) on a grid and watch animated charge flow.  The simulator
solves the circuit using Modified Nodal Analysis (Kirchhoff's laws) with
transient response for reactive components (capacitors & inductors).

Presets
-------
1. Simple DC Loop       — battery + resistor, basic Ohm's law
2. Voltage Divider      — two resistors splitting a voltage
3. RC Charging Curve    — capacitor charging through resistor
4. LC Oscillator        — energy sloshing between L and C
5. RLC Resonance        — damped sinusoidal oscillation
6. Wheatstone Bridge    — balanced bridge with galvanometer
"""
import curses
import math
import random

# ── Component types ─────────────────────────────────────────────────────
COMP_WIRE = 0
COMP_BATTERY = 1
COMP_RESISTOR = 2
COMP_CAPACITOR = 3
COMP_INDUCTOR = 4
COMP_LED = 5
COMP_SWITCH = 6
COMP_GROUND = 7

COMP_NAMES = {
    COMP_WIRE: "Wire",
    COMP_BATTERY: "Battery",
    COMP_RESISTOR: "Resistor",
    COMP_CAPACITOR: "Capacitor",
    COMP_INDUCTOR: "Inductor",
    COMP_LED: "LED",
    COMP_SWITCH: "Switch",
    COMP_GROUND: "Ground",
}

# Visual characters for components (horizontal, vertical)
COMP_CHARS = {
    COMP_WIRE: ("─", "│"),
    COMP_BATTERY: ("╠╣", "╦╩"),
    COMP_RESISTOR: ("┤├", "┬┴"),
    COMP_CAPACITOR: ("||", "═"),
    COMP_INDUCTOR: ("∿∿", "∿"),
    COMP_LED: ("▷|", "▽"),
    COMP_SWITCH: ("/ ", "/ "),
    COMP_GROUND: ("⏚", "⏚"),
}

# Direction constants
DIR_RIGHT = 0
DIR_DOWN = 1
DIR_LEFT = 2
DIR_UP = 3

DIR_DELTA = {DIR_RIGHT: (0, 1), DIR_DOWN: (1, 0), DIR_LEFT: (0, -1), DIR_UP: (-1, 0)}

# ── Presets ──────────────────────────────────────────────────────────────

CIRCUIT_PRESETS = [
    ("Simple DC Loop",
     "Battery + resistor — Ohm's law: V = IR",
     {
         "components": [
             # (type, row, col, direction, value, label)
             (COMP_BATTERY, 3, 2, DIR_RIGHT, 9.0, "9V"),
             (COMP_WIRE, 3, 4, DIR_RIGHT, 0, ""),
             (COMP_WIRE, 3, 5, DIR_RIGHT, 0, ""),
             (COMP_WIRE, 3, 6, DIR_DOWN, 0, ""),
             (COMP_WIRE, 4, 6, DIR_DOWN, 0, ""),
             (COMP_WIRE, 5, 6, DIR_DOWN, 0, ""),
             (COMP_RESISTOR, 6, 6, DIR_LEFT, 100.0, "100Ω"),
             (COMP_WIRE, 6, 4, DIR_LEFT, 0, ""),
             (COMP_WIRE, 6, 3, DIR_LEFT, 0, ""),
             (COMP_WIRE, 6, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 5, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 4, 2, DIR_UP, 0, ""),
         ],
         "ac_source": False,
         "ac_freq": 0,
         "ac_amplitude": 0,
     }),
    ("Voltage Divider",
     "Two resistors splitting voltage — V_out = V × R2/(R1+R2)",
     {
         "components": [
             (COMP_BATTERY, 2, 2, DIR_RIGHT, 12.0, "12V"),
             (COMP_WIRE, 2, 4, DIR_RIGHT, 0, ""),
             (COMP_WIRE, 2, 5, DIR_RIGHT, 0, ""),
             (COMP_RESISTOR, 2, 6, DIR_DOWN, 1000.0, "1kΩ"),
             (COMP_WIRE, 4, 6, DIR_DOWN, 0, ""),
             (COMP_RESISTOR, 5, 6, DIR_DOWN, 2000.0, "2kΩ"),
             (COMP_WIRE, 7, 6, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 5, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 4, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 3, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 6, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 5, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 4, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 3, 2, DIR_UP, 0, ""),
         ],
         "ac_source": False,
         "ac_freq": 0,
         "ac_amplitude": 0,
     }),
    ("RC Charging Curve",
     "Capacitor charging through resistor — τ = RC",
     {
         "components": [
             (COMP_BATTERY, 2, 2, DIR_RIGHT, 5.0, "5V"),
             (COMP_WIRE, 2, 4, DIR_RIGHT, 0, ""),
             (COMP_RESISTOR, 2, 5, DIR_RIGHT, 1000.0, "1kΩ"),
             (COMP_WIRE, 2, 7, DIR_DOWN, 0, ""),
             (COMP_WIRE, 3, 7, DIR_DOWN, 0, ""),
             (COMP_CAPACITOR, 4, 7, DIR_DOWN, 0.001, "1mF"),
             (COMP_WIRE, 6, 7, DIR_LEFT, 0, ""),
             (COMP_WIRE, 6, 6, DIR_LEFT, 0, ""),
             (COMP_WIRE, 6, 5, DIR_LEFT, 0, ""),
             (COMP_WIRE, 6, 4, DIR_LEFT, 0, ""),
             (COMP_WIRE, 6, 3, DIR_LEFT, 0, ""),
             (COMP_WIRE, 6, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 5, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 4, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 3, 2, DIR_UP, 0, ""),
         ],
         "ac_source": False,
         "ac_freq": 0,
         "ac_amplitude": 0,
     }),
    ("LC Oscillator",
     "Energy oscillates between inductor and capacitor — f = 1/(2π√LC)",
     {
         "components": [
             (COMP_BATTERY, 2, 2, DIR_RIGHT, 5.0, "5V"),
             (COMP_SWITCH, 2, 4, DIR_RIGHT, 0, "S1"),
             (COMP_WIRE, 2, 6, DIR_RIGHT, 0, ""),
             (COMP_WIRE, 2, 7, DIR_DOWN, 0, ""),
             (COMP_INDUCTOR, 3, 7, DIR_DOWN, 0.1, "100mH"),
             (COMP_WIRE, 5, 7, DIR_DOWN, 0, ""),
             (COMP_CAPACITOR, 6, 7, DIR_DOWN, 0.001, "1mF"),
             (COMP_WIRE, 8, 7, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 6, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 5, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 4, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 3, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 7, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 6, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 5, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 4, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 3, 2, DIR_UP, 0, ""),
         ],
         "ac_source": False,
         "ac_freq": 0,
         "ac_amplitude": 0,
     }),
    ("RLC Resonance",
     "Damped oscillation — AC source drives RLC series circuit",
     {
         "components": [
             (COMP_BATTERY, 2, 2, DIR_RIGHT, 5.0, "AC 5V"),
             (COMP_WIRE, 2, 4, DIR_RIGHT, 0, ""),
             (COMP_RESISTOR, 2, 5, DIR_RIGHT, 50.0, "50Ω"),
             (COMP_WIRE, 2, 7, DIR_DOWN, 0, ""),
             (COMP_INDUCTOR, 3, 7, DIR_DOWN, 0.05, "50mH"),
             (COMP_WIRE, 5, 7, DIR_DOWN, 0, ""),
             (COMP_CAPACITOR, 6, 7, DIR_DOWN, 0.0001, "100μF"),
             (COMP_WIRE, 8, 7, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 6, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 5, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 4, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 3, DIR_LEFT, 0, ""),
             (COMP_WIRE, 8, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 7, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 6, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 5, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 4, 2, DIR_UP, 0, ""),
             (COMP_WIRE, 3, 2, DIR_UP, 0, ""),
         ],
         "ac_source": True,
         "ac_freq": 10.0,
         "ac_amplitude": 5.0,
     }),
    ("Wheatstone Bridge",
     "Balanced bridge — null galvanometer when R1/R2 = R3/R4",
     {
         "components": [
             (COMP_BATTERY, 1, 4, DIR_RIGHT, 10.0, "10V"),
             (COMP_WIRE, 1, 6, DIR_DOWN, 0, ""),
             # Top-right branch: R1
             (COMP_RESISTOR, 2, 6, DIR_DOWN, 100.0, "R1 100Ω"),
             # Middle node right
             (COMP_WIRE, 4, 6, DIR_DOWN, 0, ""),
             # Bottom-right branch: R2
             (COMP_RESISTOR, 5, 6, DIR_DOWN, 200.0, "R2 200Ω"),
             (COMP_WIRE, 7, 6, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 5, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 4, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 3, DIR_LEFT, 0, ""),
             (COMP_WIRE, 7, 2, DIR_UP, 0, ""),
             # Bottom-left branch: R4
             (COMP_RESISTOR, 5, 2, DIR_UP, 400.0, "R4 400Ω"),
             # Middle node left
             (COMP_WIRE, 4, 2, DIR_UP, 0, ""),
             # Top-left branch: R3
             (COMP_RESISTOR, 2, 2, DIR_UP, 200.0, "R3 200Ω"),
             (COMP_WIRE, 1, 2, DIR_RIGHT, 0, ""),
             (COMP_WIRE, 1, 3, DIR_RIGHT, 0, ""),
             # Bridge galvanometer (wire across middle)
             (COMP_RESISTOR, 4, 3, DIR_RIGHT, 500.0, "Rg 500Ω"),
             (COMP_WIRE, 4, 4, DIR_RIGHT, 0, ""),
             (COMP_WIRE, 4, 5, DIR_RIGHT, 0, ""),
         ],
         "ac_source": False,
         "ac_freq": 0,
         "ac_amplitude": 0,
     }),
]


# ── Circuit solver ──────────────────────────────────────────────────────

def _build_circuit(sim):
    """Build node graph and component list from placed components.

    Assigns node IDs to each grid position that has a component endpoint.
    Components connect from their position to the next position along their
    direction.
    """
    components = sim["components"]
    node_map = {}  # (row, col) -> node_id
    next_node = [0]

    def get_node(r, c):
        key = (r, c)
        if key not in node_map:
            node_map[key] = next_node[0]
            next_node[0] += 1
        return node_map[key]

    edges = []  # (node_a, node_b, comp_type, value, label, row, col)

    for comp in components:
        ctype, row, col, direction, value, label = comp
        dr, dc = DIR_DELTA[direction]
        node_a = get_node(row, col)
        node_b = get_node(row + dr, col + dc)
        edges.append((node_a, node_b, ctype, value, label, row, col))

    sim["node_map"] = node_map
    sim["inv_node_map"] = {v: k for k, v in node_map.items()}
    sim["edges"] = edges
    sim["n_nodes"] = next_node[0]


def _solve_dc(sim):
    """Solve circuit using Modified Nodal Analysis for DC steady state.

    Sets up and solves:  [G  B] [v]   [i]
                         [C  D] [j] = [e]

    where G is conductance matrix, v is node voltages, j is branch currents
    through voltage sources, and B/C/D handle voltage source constraints.
    """
    n_nodes = sim["n_nodes"]
    edges = sim["edges"]

    if n_nodes == 0:
        return

    # Find voltage sources (batteries)
    vsources = []
    for idx, (na, nb, ctype, val, label, r, c) in enumerate(edges):
        if ctype == COMP_BATTERY:
            vsources.append((idx, na, nb, val))

    n_vs = len(vsources)
    size = n_nodes + n_vs

    # Build MNA matrices as flat lists
    A = [[0.0] * size for _ in range(size)]
    b = [0.0] * size

    for idx, (na, nb, ctype, val, label, r, c) in enumerate(edges):
        if ctype == COMP_WIRE:
            # Wire = very low resistance (high conductance)
            g = 1000.0
            A[na][na] += g
            A[nb][nb] += g
            A[na][nb] -= g
            A[nb][na] -= g
        elif ctype == COMP_RESISTOR:
            g = 1.0 / max(val, 0.001)
            A[na][na] += g
            A[nb][nb] += g
            A[na][nb] -= g
            A[nb][na] -= g
        elif ctype == COMP_LED:
            # LED modeled as resistor + voltage drop
            g = 1.0 / 100.0  # ~100 ohm forward resistance
            A[na][na] += g
            A[nb][nb] += g
            A[na][nb] -= g
            A[nb][na] -= g
        elif ctype == COMP_SWITCH:
            switch_states = sim.get("switch_states", {})
            key = (r, c)
            if switch_states.get(key, True):  # Default closed
                g = 1000.0  # Closed = wire
            else:
                g = 1e-9  # Open = near-infinite resistance
            A[na][na] += g
            A[nb][nb] += g
            A[na][nb] -= g
            A[nb][na] -= g
        elif ctype == COMP_CAPACITOR:
            # In DC steady state, capacitor = open circuit
            # But for transient, use companion model: G = C/dt
            dt = sim.get("dt", 0.001)
            g = val / dt if val > 0 else 1e-9
            A[na][na] += g
            A[nb][nb] += g
            A[na][nb] -= g
            A[nb][na] -= g
            # Companion current source from previous voltage
            cap_key = (r, c)
            v_prev = sim.get("cap_voltages", {}).get(cap_key, 0.0)
            i_hist = g * v_prev
            b[na] += i_hist
            b[nb] -= i_hist
        elif ctype == COMP_INDUCTOR:
            # Companion model: inductor as current source + resistance
            # V = L * di/dt  =>  i(t+dt) = i(t) + (V/L)*dt
            # Companion: conductance = dt/L, current source = i_prev
            dt = sim.get("dt", 0.001)
            g = dt / max(val, 1e-6)
            A[na][na] += g
            A[nb][nb] += g
            A[na][nb] -= g
            A[nb][na] -= g
            ind_key = (r, c)
            i_prev = sim.get("ind_currents", {}).get(ind_key, 0.0)
            b[na] -= i_prev
            b[nb] += i_prev

    # Voltage source stamps
    for vs_idx, (edge_idx, na, nb, voltage) in enumerate(vsources):
        col_j = n_nodes + vs_idx
        # AC modulation
        if sim.get("ac_source", False):
            t = sim.get("time", 0.0)
            freq = sim.get("ac_freq", 1.0)
            amp = sim.get("ac_amplitude", voltage)
            voltage = amp * math.sin(2.0 * math.pi * freq * t)

        A[na][col_j] += 1.0
        A[nb][col_j] -= 1.0
        A[col_j][na] += 1.0
        A[col_j][nb] -= 1.0
        b[col_j] = voltage

    # Ground node 0 (set voltage = 0)
    # Find a ground node — use node 0 or any explicit ground
    gnd_node = 0
    for idx, (na, nb, ctype, val, label, r, c) in enumerate(edges):
        if ctype == COMP_GROUND:
            gnd_node = na
            break

    # Make ground row: clear row and set diagonal to 1
    for j in range(size):
        A[gnd_node][j] = 0.0
    A[gnd_node][gnd_node] = 1.0
    b[gnd_node] = 0.0

    # Solve Ax = b using Gaussian elimination with partial pivoting
    voltages, source_currents = _gauss_solve(A, b, n_nodes, n_vs)

    if voltages is not None:
        sim["node_voltages"] = voltages
        sim["source_currents"] = source_currents

        # Compute branch currents
        branch_currents = {}
        for idx, (na, nb, ctype, val, label, r, c) in enumerate(edges):
            va = voltages[na] if na < len(voltages) else 0
            vb = voltages[nb] if nb < len(voltages) else 0
            dv = va - vb

            if ctype == COMP_WIRE:
                current = dv * 1000.0
            elif ctype == COMP_RESISTOR:
                current = dv / max(val, 0.001)
            elif ctype == COMP_LED:
                current = dv / 100.0
            elif ctype == COMP_SWITCH:
                switch_states = sim.get("switch_states", {})
                key = (r, c)
                if switch_states.get(key, True):
                    current = dv * 1000.0
                else:
                    current = dv * 1e-9
            elif ctype == COMP_CAPACITOR:
                dt = sim.get("dt", 0.001)
                g = val / dt if val > 0 else 1e-9
                v_prev = sim.get("cap_voltages", {}).get((r, c), 0.0)
                current = g * (dv - v_prev)
            elif ctype == COMP_INDUCTOR:
                dt = sim.get("dt", 0.001)
                g = dt / max(val, 1e-6)
                i_prev = sim.get("ind_currents", {}).get((r, c), 0.0)
                current = g * dv + i_prev
            elif ctype == COMP_BATTERY:
                # Find in vsources
                current = 0.0
                for vs_idx, (eidx, vna, vnb, vv) in enumerate(vsources):
                    if eidx == idx:
                        current = source_currents[vs_idx] if vs_idx < len(source_currents) else 0
                        break
            else:
                current = 0.0

            branch_currents[(r, c)] = current

        sim["branch_currents"] = branch_currents

        # Update reactive component states
        cap_voltages = sim.get("cap_voltages", {})
        for idx, (na, nb, ctype, val, label, r, c) in enumerate(edges):
            if ctype == COMP_CAPACITOR:
                va = voltages[na] if na < len(voltages) else 0
                vb = voltages[nb] if nb < len(voltages) else 0
                cap_voltages[(r, c)] = va - vb
        sim["cap_voltages"] = cap_voltages

        ind_currents = sim.get("ind_currents", {})
        for idx, (na, nb, ctype, val, label, r, c) in enumerate(edges):
            if ctype == COMP_INDUCTOR:
                ind_currents[(r, c)] = branch_currents.get((r, c), 0.0)
        sim["ind_currents"] = ind_currents


def _gauss_solve(A, b, n_nodes, n_vs):
    """Solve linear system via Gaussian elimination with partial pivoting."""
    size = n_nodes + n_vs
    if size == 0:
        return [], []

    # Augmented matrix
    aug = [row[:] + [bi] for row, bi in zip(A, b)]

    for col in range(size):
        # Partial pivoting
        max_val = abs(aug[col][col])
        max_row = col
        for row in range(col + 1, size):
            if abs(aug[row][col]) > max_val:
                max_val = abs(aug[row][col])
                max_row = row
        if max_val < 1e-15:
            continue
        if max_row != col:
            aug[col], aug[max_row] = aug[max_row], aug[col]

        pivot = aug[col][col]
        if abs(pivot) < 1e-15:
            continue

        for row in range(col + 1, size):
            factor = aug[row][col] / pivot
            for j in range(col, size + 1):
                aug[row][j] -= factor * aug[col][j]

    # Back substitution
    x = [0.0] * size
    for row in range(size - 1, -1, -1):
        if abs(aug[row][row]) < 1e-15:
            continue
        x[row] = aug[row][size]
        for j in range(row + 1, size):
            x[row] -= aug[row][j] * x[j]
        x[row] /= aug[row][row]

    voltages = x[:n_nodes]
    source_currents = x[n_nodes:]
    return voltages, source_currents


# ── Simulation state ────────────────────────────────────────────────────

def _init_circuit(settings):
    """Create simulation state from preset settings."""
    sim = {
        "components": list(settings["components"]),
        "ac_source": settings.get("ac_source", False),
        "ac_freq": settings.get("ac_freq", 1.0),
        "ac_amplitude": settings.get("ac_amplitude", 5.0),
        "time": 0.0,
        "dt": 0.001,
        "step": 0,
        "speed": 5,
        "node_map": {},
        "inv_node_map": {},
        "edges": [],
        "n_nodes": 0,
        "node_voltages": [],
        "source_currents": [],
        "branch_currents": {},
        "cap_voltages": {},
        "ind_currents": {},
        "switch_states": {},
        "charge_particles": [],
        "voltage_history": [],
        "current_history": [],
        "scope_data": [],
        "scope_data2": [],
        "power_total": 0.0,
    }

    # Initialize switches as closed
    for comp in sim["components"]:
        ctype, row, col, direction, value, label = comp
        if ctype == COMP_SWITCH:
            sim["switch_states"][(row, col)] = True

    _build_circuit(sim)
    _solve_dc(sim)
    _spawn_charge_particles(sim)
    return sim


def _spawn_charge_particles(sim):
    """Create animated charge particles along wires/components."""
    particles = []
    for comp in sim["components"]:
        ctype, row, col, direction, value, label = comp
        # Place a charge particle at each component
        current = sim["branch_currents"].get((row, col), 0.0)
        if abs(current) > 0.001:
            particles.append({
                "row": float(row),
                "col": float(col),
                "direction": direction,
                "phase": random.random(),
                "comp_row": row,
                "comp_col": col,
            })
    sim["charge_particles"] = particles


def _step_circuit(sim):
    """Advance circuit simulation by one time step."""
    sim["time"] += sim["dt"]
    sim["step"] += 1

    _solve_dc(sim)

    # Animate charge particles
    for p in sim["charge_particles"]:
        current = sim["branch_currents"].get((p["comp_row"], p["comp_col"]), 0.0)
        speed = min(abs(current) * 0.02, 0.5)
        if current < 0:
            speed = -speed
        p["phase"] = (p["phase"] + speed) % 1.0

    # Respawn particles periodically
    if sim["step"] % 50 == 0:
        _spawn_charge_particles(sim)

    # Record history for oscilloscope
    if sim["step"] % 2 == 0:
        # Track voltage across first capacitor/inductor or total source voltage
        v_track = 0.0
        i_track = 0.0
        found_reactive = False

        for comp in sim["components"]:
            ctype, row, col, direction, value, label = comp
            if ctype in (COMP_CAPACITOR, COMP_INDUCTOR) and not found_reactive:
                node_a = sim["node_map"].get((row, col))
                dr, dc = DIR_DELTA[direction]
                node_b = sim["node_map"].get((row + dr, col + dc))
                if node_a is not None and node_b is not None:
                    voltages = sim.get("node_voltages", [])
                    if node_a < len(voltages) and node_b < len(voltages):
                        v_track = voltages[node_a] - voltages[node_b]
                i_track = sim["branch_currents"].get((row, col), 0.0)
                found_reactive = True

        if not found_reactive:
            # Track battery voltage and current
            for comp in sim["components"]:
                ctype, row, col, direction, value, label = comp
                if ctype == COMP_BATTERY:
                    node_a = sim["node_map"].get((row, col))
                    dr, dc = DIR_DELTA[direction]
                    node_b = sim["node_map"].get((row + dr, col + dc))
                    if node_a is not None and node_b is not None:
                        voltages = sim.get("node_voltages", [])
                        if node_a < len(voltages) and node_b < len(voltages):
                            v_track = voltages[node_a] - voltages[node_b]
                    i_track = sim["branch_currents"].get((row, col), 0.0)
                    break

        sim["scope_data"].append(v_track)
        sim["scope_data2"].append(i_track)
        if len(sim["scope_data"]) > 300:
            sim["scope_data"] = sim["scope_data"][-300:]
            sim["scope_data2"] = sim["scope_data2"][-300:]

    # Compute total power
    power = 0.0
    for comp in sim["components"]:
        ctype, row, col, direction, value, label = comp
        if ctype == COMP_RESISTOR:
            i = sim["branch_currents"].get((row, col), 0.0)
            power += i * i * value
    sim["power_total"] = power


# ── Mode integration ────────────────────────────────────────────────────

def _enter_circuit_mode(self):
    """Enter Electric Circuit Simulator mode — show preset menu."""
    self.circuit_mode = True
    self.circuit_menu = True
    self.circuit_menu_sel = 0
    self.circuit_sim = None
    self.circuit_running = False
    self.circuit_view = 0  # 0=schematic, 1=voltage heatmap, 2=oscilloscope


def _exit_circuit_mode(self):
    """Exit Electric Circuit Simulator mode."""
    self.circuit_mode = False
    self.circuit_menu = False
    self.circuit_sim = None


def _circuit_init(self, preset_idx):
    """Initialize circuit from selected preset."""
    _, _, settings = CIRCUIT_PRESETS[preset_idx]
    self.circuit_sim = _init_circuit(settings)
    self.circuit_menu = False
    self.circuit_running = True
    self.circuit_preset_name = CIRCUIT_PRESETS[preset_idx][0]


def _circuit_step(self):
    """Advance circuit simulation by configured number of sub-steps."""
    if not self.circuit_sim or not self.circuit_running:
        return
    for _ in range(self.circuit_sim["speed"]):
        _step_circuit(self.circuit_sim)


def _handle_circuit_menu_key(self, key):
    """Handle keys on the preset selection menu."""
    n = len(CIRCUIT_PRESETS)
    if key == curses.KEY_UP or key == ord('k'):
        self.circuit_menu_sel = (self.circuit_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN or key == ord('j'):
        self.circuit_menu_sel = (self.circuit_menu_sel + 1) % n
        return True
    if key in (curses.KEY_ENTER, 10, 13, ord('\n')):
        _circuit_init(self, self.circuit_menu_sel)
        return True
    if key == ord('q') or key == 27:
        _exit_circuit_mode(self)
        self.mode_browser = True
        return True
    return True


def _handle_circuit_key(self, key):
    """Handle keys during circuit simulation."""
    if key == ord('q') or key == 27:
        _exit_circuit_mode(self)
        self.mode_browser = True
        return True
    if key == ord(' '):
        self.circuit_running = not self.circuit_running
        return True
    if key == ord('n'):
        if not self.circuit_running:
            _step_circuit(self.circuit_sim)
        return True
    if key == ord('+') or key == ord('='):
        self.circuit_sim["speed"] = min(self.circuit_sim["speed"] + 1, 30)
        return True
    if key == ord('-'):
        self.circuit_sim["speed"] = max(self.circuit_sim["speed"] - 1, 1)
        return True
    if key == ord('v'):
        self.circuit_view = (self.circuit_view + 1) % 3
        return True
    if key == ord('s') or key == ord('S'):
        # Toggle switches
        sim = self.circuit_sim
        for comp in sim["components"]:
            ctype, row, col, direction, value, label = comp
            if ctype == COMP_SWITCH:
                k = (row, col)
                sim["switch_states"][k] = not sim["switch_states"].get(k, True)
        self._flash("Switches toggled")
        return True
    if key == curses.KEY_UP:
        # Increase AC frequency
        if self.circuit_sim.get("ac_source"):
            self.circuit_sim["ac_freq"] = min(
                self.circuit_sim["ac_freq"] + 1.0, 200.0)
            self._flash(f"f = {self.circuit_sim['ac_freq']:.1f} Hz")
        return True
    if key == curses.KEY_DOWN:
        # Decrease AC frequency
        if self.circuit_sim.get("ac_source"):
            self.circuit_sim["ac_freq"] = max(
                self.circuit_sim["ac_freq"] - 1.0, 0.5)
            self._flash(f"f = {self.circuit_sim['ac_freq']:.1f} Hz")
        return True
    if key == ord('r'):
        # Reset with current preset
        _circuit_init(self, self.circuit_menu_sel)
        return True
    if key == ord('R'):
        # Back to menu
        self.circuit_menu = True
        self.circuit_running = False
        return True
    return True


# ── Drawing ─────────────────────────────────────────────────────────────

def _draw_circuit_menu(self, max_y, max_x):
    """Draw the preset selection menu."""
    title = "╔══ ELECTRIC CIRCUIT SIMULATOR ══╗"
    subtitle = "Build circuits · watch current flow · measure voltages"
    try:
        cy = max(1, max_y // 2 - len(CIRCUIT_PRESETS) - 3)
        cx = max(0, (max_x - len(title)) // 2)
        self.stdscr.addstr(cy, cx, title, curses.A_BOLD | curses.color_pair(3))
        self.stdscr.addstr(cy + 1, max(0, (max_x - len(subtitle)) // 2),
                           subtitle, curses.color_pair(7))

        y = cy + 3
        for i, (name, desc, _) in enumerate(CIRCUIT_PRESETS):
            if y >= max_y - 2:
                break
            marker = "▸ " if i == self.circuit_menu_sel else "  "
            attr = curses.A_BOLD | curses.color_pair(3) if i == self.circuit_menu_sel else curses.color_pair(7)
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


def _draw_circuit(self, max_y, max_x):
    """Draw the active circuit simulation."""
    sim = self.circuit_sim
    if not sim:
        return

    # Layout: circuit view on left, stats on right
    stats_w = 34
    view_w = max(10, max_x - stats_w - 2)
    view_h = max(5, max_y - 3)

    # ── Title bar ──
    title = f" Electric Circuit — {self.circuit_preset_name} "
    try:
        self.stdscr.addstr(0, 0, title[:max_x], curses.A_BOLD | curses.color_pair(3))
        ac_str = " [AC]" if sim.get("ac_source") else " [DC]"
        px = min(len(title), max_x - len(ac_str) - 1)
        if px > 0:
            ac_color = curses.color_pair(1) if sim.get("ac_source") else curses.color_pair(4)
            self.stdscr.addstr(0, px, ac_str, curses.A_BOLD | ac_color)
    except curses.error:
        pass

    if self.circuit_view == 0:
        _draw_schematic(self, sim, 1, 0, view_h, view_w)
    elif self.circuit_view == 1:
        _draw_voltage_heatmap(self, sim, 1, 0, view_h, view_w)
    else:
        _draw_oscilloscope(self, sim, 1, 0, view_h, view_w)

    # ── Stats panel ──
    _draw_circuit_stats(self, sim, 1, view_w + 1, view_h, stats_w)

    # ── Footer ──
    paused = " PAUSED" if not self.circuit_running else ""
    ac_hint = " ↑↓ freq ·" if sim.get("ac_source") else ""
    hint = f" space pause · v view · s switch ·{ac_hint} +/- speed · r reset · q quit{paused}"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                           curses.A_DIM | curses.color_pair(7))
    except curses.error:
        pass


def _draw_schematic(self, sim, top, left, height, width):
    """Draw circuit schematic with animated charge flow."""
    components = sim["components"]
    branch_currents = sim.get("branch_currents", {})
    node_voltages = sim.get("node_voltages", [])
    node_map = sim.get("node_map", {})

    # Scale circuit to fit view
    if not components:
        return

    min_r = min(c[1] for c in components)
    max_r = max(c[1] for c in components)
    min_c = min(c[2] for c in components)
    max_c = max(c[2] for c in components)

    grid_h = max_r - min_r + 2
    grid_w = max_c - min_c + 2

    # Scale factors
    scale_y = max(1, (height - 2) // max(grid_h, 1))
    scale_x = max(2, (width - 2) // max(grid_w, 1))

    # Cap scales to reasonable values
    scale_y = min(scale_y, 4)
    scale_x = min(scale_x, 8)

    # Draw components
    for comp in components:
        ctype, row, col, direction, value, label = comp
        sy = top + 1 + (row - min_r) * scale_y
        sx = left + 2 + (col - min_c) * scale_x

        if sy >= top + height - 1 or sx >= left + width - 2:
            continue
        if sy < top or sx < left:
            continue

        current = branch_currents.get((row, col), 0.0)

        # Color by current magnitude
        abs_i = abs(current)
        if abs_i < 0.001:
            cp = curses.color_pair(7) | curses.A_DIM
        elif abs_i < 0.01:
            cp = curses.color_pair(4)   # blue - low
        elif abs_i < 0.05:
            cp = curses.color_pair(6)   # cyan
        elif abs_i < 0.1:
            cp = curses.color_pair(2)   # green
        elif abs_i < 0.5:
            cp = curses.color_pair(3)   # yellow
        else:
            cp = curses.color_pair(1)   # red - high

        # Draw component character
        try:
            if ctype == COMP_WIRE:
                if direction in (DIR_RIGHT, DIR_LEFT):
                    for dx in range(scale_x):
                        self.stdscr.addstr(sy, sx + dx, "─", cp)
                else:
                    for dy in range(scale_y):
                        self.stdscr.addstr(sy + dy, sx, "│", cp)
            elif ctype == COMP_BATTERY:
                if direction in (DIR_RIGHT, DIR_LEFT):
                    mid = sx + scale_x // 2
                    self.stdscr.addstr(sy, mid - 1, "─╠", cp)
                    self.stdscr.addstr(sy, mid + 1, "╣─",
                                       curses.A_BOLD | curses.color_pair(1))
                    # + and - signs
                    if sy > top:
                        self.stdscr.addstr(sy - 1, mid - 1, "−",
                                           curses.A_DIM | curses.color_pair(7))
                        self.stdscr.addstr(sy - 1, mid + 1, "+",
                                           curses.A_BOLD | curses.color_pair(1))
                else:
                    mid = sy + scale_y // 2
                    self.stdscr.addstr(mid - 1, sx, "╦",
                                       curses.A_BOLD | curses.color_pair(1))
                    self.stdscr.addstr(mid + 1, sx, "╩", cp)
                # Label
                if label and sy > top:
                    self.stdscr.addstr(sy - 1 if direction in (DIR_RIGHT, DIR_LEFT) else sy,
                                       sx + 3, label[:8],
                                       curses.A_DIM | curses.color_pair(3))
            elif ctype == COMP_RESISTOR:
                if direction in (DIR_RIGHT, DIR_LEFT):
                    mid = sx + scale_x // 2
                    chars = "┤╍╍├"
                    self.stdscr.addstr(sy, max(left, mid - 1), chars[:min(4, width - (mid - 1 - left))],
                                       curses.A_BOLD | curses.color_pair(3))
                else:
                    mid = sy + scale_y // 2
                    self.stdscr.addstr(max(top, mid - 1), sx, "┬",
                                       curses.A_BOLD | curses.color_pair(3))
                    self.stdscr.addstr(min(top + height - 2, mid + 1), sx, "┴",
                                       curses.A_BOLD | curses.color_pair(3))
                # Label
                if label:
                    lx = sx + 2 if direction in (DIR_RIGHT, DIR_LEFT) else sx + 2
                    ly = sy if direction in (DIR_RIGHT, DIR_LEFT) else mid
                    if lx + len(label) < left + width and ly < top + height:
                        self.stdscr.addstr(ly, lx, label[:8],
                                           curses.A_DIM | curses.color_pair(7))
            elif ctype == COMP_CAPACITOR:
                if direction in (DIR_RIGHT, DIR_LEFT):
                    mid = sx + scale_x // 2
                    self.stdscr.addstr(sy, mid, "││",
                                       curses.A_BOLD | curses.color_pair(6))
                else:
                    mid = sy + scale_y // 2
                    self.stdscr.addstr(mid, sx, "═",
                                       curses.A_BOLD | curses.color_pair(6))
                if label:
                    self.stdscr.addstr(sy, sx + 2, label[:8],
                                       curses.A_DIM | curses.color_pair(6))
            elif ctype == COMP_INDUCTOR:
                if direction in (DIR_RIGHT, DIR_LEFT):
                    mid = sx + scale_x // 2
                    self.stdscr.addstr(sy, max(left, mid - 1), "∿∿∿",
                                       curses.A_BOLD | curses.color_pair(5))
                else:
                    mid = sy + scale_y // 2
                    for dy in range(-1, 2):
                        ry = mid + dy
                        if top <= ry < top + height:
                            self.stdscr.addstr(ry, sx, "∿",
                                               curses.A_BOLD | curses.color_pair(5))
                if label:
                    self.stdscr.addstr(sy, sx + 2, label[:8],
                                       curses.A_DIM | curses.color_pair(5))
            elif ctype == COMP_LED:
                if direction in (DIR_RIGHT, DIR_LEFT):
                    mid = sx + scale_x // 2
                    # LED glows when current flows
                    glow = curses.A_BOLD | curses.color_pair(2) if abs_i > 0.001 else curses.A_DIM | curses.color_pair(7)
                    self.stdscr.addstr(sy, mid, "▷", glow)
                    if abs_i > 0.01 and sy > top:
                        # Glow effect
                        self.stdscr.addstr(sy - 1, mid, "✦",
                                           curses.A_BOLD | curses.color_pair(2))
                else:
                    mid = sy + scale_y // 2
                    glow = curses.A_BOLD | curses.color_pair(2) if abs_i > 0.001 else curses.A_DIM | curses.color_pair(7)
                    self.stdscr.addstr(mid, sx, "▽", glow)
            elif ctype == COMP_SWITCH:
                switch_states = sim.get("switch_states", {})
                closed = switch_states.get((row, col), True)
                if direction in (DIR_RIGHT, DIR_LEFT):
                    mid = sx + scale_x // 2
                    if closed:
                        self.stdscr.addstr(sy, mid, "─●─",
                                           curses.A_BOLD | curses.color_pair(2))
                    else:
                        self.stdscr.addstr(sy, mid, "─╱ ",
                                           curses.color_pair(1))
                else:
                    mid = sy + scale_y // 2
                    if closed:
                        self.stdscr.addstr(mid, sx, "●",
                                           curses.A_BOLD | curses.color_pair(2))
                    else:
                        self.stdscr.addstr(mid, sx, "╱",
                                           curses.color_pair(1))
                if label:
                    self.stdscr.addstr(sy, sx + 2, label[:8],
                                       curses.A_DIM | curses.color_pair(7))
            elif ctype == COMP_GROUND:
                self.stdscr.addstr(sy, sx, "⏚",
                                   curses.A_BOLD | curses.color_pair(7))
        except curses.error:
            pass

    # Draw animated charge particles
    phase_offset = (sim.get("step", 0) * 0.05) % 1.0
    charge_char = "•"
    for comp in components:
        ctype, row, col, direction, value, label = comp
        current = branch_currents.get((row, col), 0.0)
        if abs(current) < 0.002:
            continue

        sy = top + 1 + (row - min_r) * scale_y
        sx = left + 2 + (col - min_c) * scale_x
        dr, dc = DIR_DELTA[direction]

        # Place charge dot along the component path
        phase = (phase_offset + row * 0.1 + col * 0.07) % 1.0
        if current < 0:
            phase = 1.0 - phase

        if direction in (DIR_RIGHT, DIR_LEFT):
            cx = sx + int(phase * scale_x)
            cy = sy
        else:
            cx = sx
            cy = sy + int(phase * scale_y)

        if top <= cy < top + height - 1 and left <= cx < left + width - 1:
            charge_cp = curses.A_BOLD | curses.color_pair(3)
            try:
                self.stdscr.addstr(cy, cx, charge_char, charge_cp)
            except curses.error:
                pass

    # Draw node voltages at junctions
    for (r, c), node_id in node_map.items():
        if node_id < len(node_voltages):
            v = node_voltages[node_id]
            sy = top + 1 + (r - min_r) * scale_y
            sx = left + 2 + (c - min_c) * scale_x

            # Show voltage at node junctions (where multiple components meet)
            # Count components at this node
            count = 0
            for comp in components:
                cr, cc = comp[1], comp[2]
                d = comp[3]
                ddr, ddc = DIR_DELTA[d]
                if (cr, cc) == (r, c) or (cr + ddr, cc + ddc) == (r, c):
                    count += 1

            if count >= 2 and abs(v) > 0.001:
                v_str = f"{v:.1f}V"
                lx = sx - len(v_str) // 2
                ly = sy + 1
                if top <= ly < top + height - 1 and left <= lx < left + width - len(v_str):
                    # Color by voltage
                    if abs(v) > 8:
                        vcp = curses.color_pair(1)
                    elif abs(v) > 4:
                        vcp = curses.color_pair(3)
                    elif abs(v) > 1:
                        vcp = curses.color_pair(6)
                    else:
                        vcp = curses.color_pair(4)
                    try:
                        self.stdscr.addstr(ly, lx, v_str, curses.A_DIM | vcp)
                    except curses.error:
                        pass

    # Box border
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


def _draw_voltage_heatmap(self, sim, top, left, height, width):
    """Draw voltage as a color heatmap across the circuit grid."""
    components = sim["components"]
    node_voltages = sim.get("node_voltages", [])
    node_map = sim.get("node_map", {})

    if not components or not node_voltages:
        try:
            self.stdscr.addstr(top + 2, left + 2, "No solution yet...",
                               curses.color_pair(7))
        except curses.error:
            pass
        return

    try:
        self.stdscr.addstr(top, left + 1, "Voltage Heatmap",
                           curses.A_BOLD | curses.color_pair(7))
    except curses.error:
        pass

    min_r = min(c[1] for c in components)
    max_r = max(c[1] for c in components)
    min_c = min(c[2] for c in components)
    max_c = max(c[2] for c in components)

    grid_h = max_r - min_r + 2
    grid_w = max_c - min_c + 2

    scale_y = max(1, (height - 4) // max(grid_h, 1))
    scale_x = max(2, (width - 4) // max(grid_w, 1))
    scale_y = min(scale_y, 4)
    scale_x = min(scale_x, 8)

    # Find voltage range
    v_min = min(node_voltages) if node_voltages else 0
    v_max = max(node_voltages) if node_voltages else 1
    v_range = v_max - v_min if v_max > v_min else 1.0

    heatmap_chars = " ░▒▓█"
    heat_colors = [
        curses.color_pair(4),   # blue (low)
        curses.color_pair(6),   # cyan
        curses.color_pair(2),   # green
        curses.color_pair(3),   # yellow
        curses.color_pair(1),   # red (high)
    ]

    for (r, c), node_id in node_map.items():
        if node_id >= len(node_voltages):
            continue
        v = node_voltages[node_id]
        norm = (v - v_min) / v_range
        norm = max(0.0, min(1.0, norm))

        ci = int(norm * (len(heatmap_chars) - 1))
        color_idx = int(norm * (len(heat_colors) - 1))

        sy = top + 2 + (r - min_r) * scale_y
        sx = left + 2 + (c - min_c) * scale_x

        if top < sy < top + height - 1 and left < sx < left + width - 2:
            ch = heatmap_chars[ci]
            cp = heat_colors[color_idx]
            try:
                # Draw a block around the node
                for dy in range(-1, 2):
                    for dx in range(-1, 3):
                        py = sy + dy
                        px = sx + dx
                        if top < py < top + height - 1 and left < px < left + width - 2:
                            self.stdscr.addstr(py, px, ch, cp)
                # Label with voltage
                v_str = f"{v:.1f}"
                if sx + len(v_str) < left + width - 2:
                    self.stdscr.addstr(sy, sx, v_str[:6],
                                       curses.A_BOLD | cp)
            except curses.error:
                pass

    # Legend
    ly = top + height - 2
    try:
        legend = f"  {v_min:.1f}V "
        for i, ch in enumerate(heatmap_chars):
            legend += ch * 3
        legend += f" {v_max:.1f}V"
        self.stdscr.addstr(ly, left + 1, legend[:width - 2],
                           curses.color_pair(7))
    except curses.error:
        pass


def _draw_oscilloscope(self, sim, top, left, height, width):
    """Draw oscilloscope view — voltage and current over time."""
    scope_data = sim.get("scope_data", [])
    scope_data2 = sim.get("scope_data2", [])

    plot_h = max(3, (height - 6) // 2)
    plot_w = max(10, width - 4)

    try:
        self.stdscr.addstr(top, left + 1, "Oscilloscope",
                           curses.A_BOLD | curses.color_pair(2))
    except curses.error:
        pass

    # ── Voltage trace ──
    try:
        self.stdscr.addstr(top + 1, left + 1, "Voltage (V)",
                           curses.A_BOLD | curses.color_pair(3))
    except curses.error:
        pass

    if scope_data:
        data = scope_data[-plot_w:]
        mn = min(data)
        mx = max(data)
        rng = mx - mn if mx > mn else 1.0

        # Draw zero line
        if mn < 0 < mx:
            zero_y = top + 2 + int((mx) / rng * (plot_h - 1))
            if top + 2 <= zero_y < top + 2 + plot_h:
                for ci in range(min(len(data), plot_w)):
                    try:
                        self.stdscr.addstr(zero_y, left + 2 + ci, "·",
                                           curses.A_DIM | curses.color_pair(7))
                    except curses.error:
                        pass

        # Draw trace
        for ci, val in enumerate(data):
            if ci >= plot_w:
                break
            bar_y = int((mx - val) / rng * (plot_h - 1))
            bar_y = max(0, min(bar_y, plot_h - 1))
            row = top + 2 + bar_y
            try:
                self.stdscr.addstr(row, left + 2 + ci, "█",
                                   curses.color_pair(3))
            except curses.error:
                pass

        # Scale labels
        try:
            self.stdscr.addstr(top + 2, left, f"{mx:>5.1f}",
                               curses.A_DIM | curses.color_pair(7))
            self.stdscr.addstr(top + 2 + plot_h - 1, left, f"{mn:>5.1f}",
                               curses.A_DIM | curses.color_pair(7))
        except curses.error:
            pass

    # ── Current trace ──
    cur_top = top + 3 + plot_h
    try:
        self.stdscr.addstr(cur_top, left + 1, "Current (A)",
                           curses.A_BOLD | curses.color_pair(6))
    except curses.error:
        pass

    if scope_data2:
        data2 = scope_data2[-plot_w:]
        mn2 = min(data2)
        mx2 = max(data2)
        rng2 = mx2 - mn2 if mx2 > mn2 else 1.0

        # Draw zero line
        if mn2 < 0 < mx2:
            zero_y = cur_top + 1 + int((mx2) / rng2 * (plot_h - 1))
            if cur_top + 1 <= zero_y < cur_top + 1 + plot_h:
                for ci in range(min(len(data2), plot_w)):
                    try:
                        self.stdscr.addstr(zero_y, left + 2 + ci, "·",
                                           curses.A_DIM | curses.color_pair(7))
                    except curses.error:
                        pass

        for ci, val in enumerate(data2):
            if ci >= plot_w:
                break
            bar_y = int((mx2 - val) / rng2 * (plot_h - 1))
            bar_y = max(0, min(bar_y, plot_h - 1))
            row = cur_top + 1 + bar_y
            try:
                self.stdscr.addstr(row, left + 2 + ci, "█",
                                   curses.color_pair(6))
            except curses.error:
                pass

        try:
            self.stdscr.addstr(cur_top + 1, left, f"{mx2:>.3f}",
                               curses.A_DIM | curses.color_pair(7))
            self.stdscr.addstr(cur_top + plot_h, left, f"{mn2:>.3f}",
                               curses.A_DIM | curses.color_pair(7))
        except curses.error:
            pass

    # Time axis
    try:
        t = sim.get("time", 0)
        self.stdscr.addstr(cur_top + plot_h + 1, left + 2,
                           f"t = {t:.3f}s" + "  " + "─" * min(20, plot_w - 12) + "→ time",
                           curses.A_DIM | curses.color_pair(7))
    except curses.error:
        pass


def _draw_circuit_stats(self, sim, top, left, height, width):
    """Draw statistics panel on the right side."""
    y = top
    w = width

    def put(row, text, attr=curses.color_pair(7)):
        try:
            self.stdscr.addstr(row, left, text[:w], attr)
        except curses.error:
            pass

    put(y, "─── Circuit Stats ───", curses.A_BOLD | curses.color_pair(3))
    y += 1
    put(y, f" Step:      {sim['step']:>8d}")
    y += 1
    put(y, f" Time:      {sim['time']:>8.3f}s")
    y += 1
    put(y, f" Speed:     {sim['speed']:>8d}x")
    y += 1

    if sim.get("ac_source"):
        put(y, f" Frequency: {sim['ac_freq']:>7.1f}Hz",
            curses.color_pair(1))
        y += 1
        put(y, f" Amplitude: {sim['ac_amplitude']:>7.1f}V",
            curses.color_pair(1))
        y += 1
        # Current source voltage
        t = sim.get("time", 0)
        v_now = sim["ac_amplitude"] * math.sin(2.0 * math.pi * sim["ac_freq"] * t)
        put(y, f" V_source:  {v_now:>7.2f}V",
            curses.color_pair(3))
        y += 1
    y += 1

    put(y, "─── Node Voltages ───", curses.A_BOLD | curses.color_pair(3))
    y += 1

    node_voltages = sim.get("node_voltages", [])
    inv_map = sim.get("inv_node_map", {})
    shown = 0
    for nid in range(min(len(node_voltages), 12)):
        if y >= top + height - 8:
            break
        v = node_voltages[nid]
        pos = inv_map.get(nid, (0, 0))
        if abs(v) > 0.001:
            put(y, f" N{nid}({pos[0]},{pos[1]}): {v:>7.2f}V",
                curses.color_pair(3) if v > 0 else curses.color_pair(4))
            y += 1
            shown += 1
    if shown == 0:
        put(y, " (no voltages)", curses.A_DIM)
        y += 1
    y += 1

    put(y, "─── Branch Currents ──", curses.A_BOLD | curses.color_pair(3))
    y += 1

    branch_currents = sim.get("branch_currents", {})
    components = sim.get("components", [])
    shown = 0
    for comp in components:
        ctype, row, col, direction, value, label = comp
        if ctype in (COMP_WIRE, COMP_GROUND):
            continue
        if y >= top + height - 4:
            break
        i = branch_currents.get((row, col), 0.0)
        name = label if label else COMP_NAMES.get(ctype, "?")
        # Format current with appropriate unit
        if abs(i) >= 1.0:
            i_str = f"{i:>7.2f}A"
        elif abs(i) >= 0.001:
            i_str = f"{i * 1000:>6.1f}mA"
        else:
            i_str = f"{i * 1e6:>6.0f}μA"
        put(y, f" {name[:10]:10s} {i_str}",
            curses.color_pair(6))
        y += 1
        shown += 1
    if shown == 0:
        put(y, " (no currents)", curses.A_DIM)
        y += 1
    y += 1

    # Power dissipation
    put(y, "─── Power ───", curses.A_BOLD | curses.color_pair(3))
    y += 1
    p = sim.get("power_total", 0)
    if p >= 1.0:
        p_str = f"{p:.2f}W"
    elif p >= 0.001:
        p_str = f"{p * 1000:.1f}mW"
    else:
        p_str = f"{p * 1e6:.0f}μW"
    put(y, f" P_total: {p_str}",
        curses.color_pair(1) if p > 1 else curses.color_pair(3))
    y += 2

    # Reactive component states
    cap_voltages = sim.get("cap_voltages", {})
    ind_currents = sim.get("ind_currents", {})
    if cap_voltages or ind_currents:
        put(y, "─── Reactive State ──", curses.A_BOLD | curses.color_pair(3))
        y += 1
        for (r, c), vc in cap_voltages.items():
            if y >= top + height - 2:
                break
            put(y, f" C({r},{c}): {vc:>7.2f}V",
                curses.color_pair(6))
            y += 1
        for (r, c), il in ind_currents.items():
            if y >= top + height - 2:
                break
            if abs(il) >= 0.001:
                put(y, f" L({r},{c}): {il * 1000:>6.1f}mA",
                    curses.color_pair(5))
            else:
                put(y, f" L({r},{c}): {il * 1e6:>6.0f}μA",
                    curses.color_pair(5))
            y += 1

    # View indicator
    views = ["Schematic", "Voltage Map", "Oscilloscope"]
    vy = top + height - 1
    put(vy, f" View: {views[self.circuit_view]} (v)",
        curses.A_DIM | curses.color_pair(7))


# ── Registration ────────────────────────────────────────────────────────

def register(App):
    """Register Electric Circuit Simulator mode methods on the App class."""
    App._enter_circuit_mode = _enter_circuit_mode
    App._exit_circuit_mode = _exit_circuit_mode
    App._circuit_init = _circuit_init
    App._circuit_step = _circuit_step
    App._handle_circuit_menu_key = _handle_circuit_menu_key
    App._handle_circuit_key = _handle_circuit_key
    App._draw_circuit_menu = _draw_circuit_menu
    App._draw_circuit = _draw_circuit
    App.CIRCUIT_PRESETS = CIRCUIT_PRESETS
