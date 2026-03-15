"""Quantum Circuit Simulator & Visualizer — build and simulate quantum circuits in ASCII.

Qubit state vectors rendered as mini Bloch-sphere projections, gate operations
animated as they transform states, entanglement shown via colored link indicators,
and measurement triggers probabilistic wavefunction collapse with a running histogram.

Presets:
  1. Bell State (|Φ+⟩)        — H on q0, CNOT → maximal entanglement
  2. GHZ State                 — 3-qubit H+CNOT chain → tripartite entanglement
  3. Quantum Teleportation     — teleport q0 state via Bell pair + classical bits
  4. Deutsch-Jozsa (3-qubit)   — single query determines constant vs balanced
  5. Grover's Search (2-qubit) — amplitude amplification finds marked item
  6. Quantum Fourier Transform — 3-qubit QFT circuit
"""
import curses
import math
import random
import cmath

# ── Presets ──────────────────────────────────────────────────────────────

QCIRC_PRESETS = [
    ("Bell State |Φ+⟩", "H on q0 then CNOT — maximal entanglement",
     {"n_qubits": 2,
      "gates": [("H", [0], []), ("CNOT", [0, 1], [])],
      "desc": "Creates (|00⟩+|11⟩)/√2"}),
    ("GHZ State", "3-qubit entangled state",
     {"n_qubits": 3,
      "gates": [("H", [0], []), ("CNOT", [0, 1], []), ("CNOT", [0, 2], [])],
      "desc": "Creates (|000⟩+|111⟩)/√2"}),
    ("Quantum Teleportation", "Teleport q0 via Bell pair + classical bits",
     {"n_qubits": 3,
      "gates": [
          ("X", [0], []),          # prepare |1⟩ state to teleport
          ("H", [1], []),          # create Bell pair on q1,q2
          ("CNOT", [1, 2], []),
          ("CNOT", [0, 1], []),    # Alice's operations
          ("H", [0], []),
          ("M", [0], []),          # measure q0
          ("M", [1], []),          # measure q1
          ("CX", [1, 2], []),      # classical-controlled X
          ("CZ", [0, 2], []),      # classical-controlled Z
      ],
      "desc": "Teleports |1⟩ from q0 to q2"}),
    ("Deutsch-Jozsa (3-qubit)", "Single query: constant or balanced?",
     {"n_qubits": 4,
      "gates": [
          ("X", [3], []),          # ancilla to |1⟩
          ("H", [0], []), ("H", [1], []), ("H", [2], []), ("H", [3], []),
          # balanced oracle: CNOT from each input to output
          ("CNOT", [0, 3], []),
          ("CNOT", [1, 3], []),
          ("H", [0], []), ("H", [1], []), ("H", [2], []),
          ("M", [0], []), ("M", [1], []), ("M", [2], []),
      ],
      "desc": "Balanced oracle → all 1s on measurement"}),
    ("Grover's Search (2-qubit)", "Amplitude amplification finds |11⟩",
     {"n_qubits": 2,
      "gates": [
          ("H", [0], []), ("H", [1], []),
          # oracle: mark |11⟩ with CZ
          ("CZ_GATE", [0, 1], []),
          # diffusion operator
          ("H", [0], []), ("H", [1], []),
          ("X", [0], []), ("X", [1], []),
          ("CZ_GATE", [0, 1], []),
          ("X", [0], []), ("X", [1], []),
          ("H", [0], []), ("H", [1], []),
          ("M", [0], []), ("M", [1], []),
      ],
      "desc": "Finds marked state |11⟩ with high probability"}),
    ("Quantum Fourier Transform", "3-qubit QFT circuit",
     {"n_qubits": 3,
      "gates": [
          ("X", [0], []),          # prepare input |100⟩ = |4⟩
          ("H", [0], []),
          ("CP", [1, 0], [math.pi / 2]),   # controlled-phase π/2
          ("CP", [2, 0], [math.pi / 4]),   # controlled-phase π/4
          ("H", [1], []),
          ("CP", [2, 1], [math.pi / 2]),
          ("H", [2], []),
          ("SWAP", [0, 2], []),
      ],
      "desc": "Quantum Fourier Transform of |4⟩"}),
]

# ── Gate definitions ─────────────────────────────────────────────────────
# Each gate: display symbol, number of qubits, unitary matrix builder

GATE_SYMBOLS = {
    "H": "H", "X": "X", "Y": "Y", "Z": "Z", "T": "T", "S": "S",
    "CNOT": "⊕", "CX": "⊕", "CZ": "●", "CZ_GATE": "●",
    "CP": "P", "SWAP": "×", "M": "M",
}

ISQRT2 = 1.0 / math.sqrt(2.0)


def _apply_gate(state_vec, n_qubits, gate_name, qubits, params):
    """Apply a gate to the state vector (in-place mutation of a copy)."""
    n = len(state_vec)

    if gate_name == "H":
        q = qubits[0]
        new = [complex(0)] * n
        for i in range(n):
            bit = (i >> (n_qubits - 1 - q)) & 1
            j = i ^ (1 << (n_qubits - 1 - q))
            if bit == 0:
                new[i] += state_vec[i] * ISQRT2
                new[j] += state_vec[i] * ISQRT2
            else:
                new[j] += state_vec[i] * ISQRT2
                new[i] += -state_vec[i] * ISQRT2
        return new

    if gate_name == "X":
        q = qubits[0]
        new = list(state_vec)
        for i in range(n):
            j = i ^ (1 << (n_qubits - 1 - q))
            if i < j:
                new[i], new[j] = state_vec[j], state_vec[i]
        return new

    if gate_name == "Y":
        q = qubits[0]
        new = [complex(0)] * n
        for i in range(n):
            bit = (i >> (n_qubits - 1 - q)) & 1
            j = i ^ (1 << (n_qubits - 1 - q))
            if bit == 0:
                new[j] += state_vec[i] * 1j
            else:
                new[j] += state_vec[i] * (-1j)
        return new

    if gate_name == "Z":
        q = qubits[0]
        new = list(state_vec)
        for i in range(n):
            if (i >> (n_qubits - 1 - q)) & 1:
                new[i] = -state_vec[i]
        return new

    if gate_name == "T":
        q = qubits[0]
        new = list(state_vec)
        phase = cmath.exp(1j * math.pi / 4)
        for i in range(n):
            if (i >> (n_qubits - 1 - q)) & 1:
                new[i] = state_vec[i] * phase
        return new

    if gate_name == "S":
        q = qubits[0]
        new = list(state_vec)
        for i in range(n):
            if (i >> (n_qubits - 1 - q)) & 1:
                new[i] = state_vec[i] * 1j
        return new

    if gate_name in ("CNOT", "CX"):
        ctrl, tgt = qubits[0], qubits[1]
        new = list(state_vec)
        for i in range(n):
            if (i >> (n_qubits - 1 - ctrl)) & 1:
                j = i ^ (1 << (n_qubits - 1 - tgt))
                if i < j:
                    new[i], new[j] = state_vec[j], state_vec[i]
        return new

    if gate_name in ("CZ", "CZ_GATE"):
        ctrl, tgt = qubits[0], qubits[1]
        new = list(state_vec)
        for i in range(n):
            if ((i >> (n_qubits - 1 - ctrl)) & 1) and \
               ((i >> (n_qubits - 1 - tgt)) & 1):
                new[i] = -state_vec[i]
        return new

    if gate_name == "CP":
        ctrl, tgt = qubits[0], qubits[1]
        theta = params[0] if params else math.pi / 2
        phase = cmath.exp(1j * theta)
        new = list(state_vec)
        for i in range(n):
            if ((i >> (n_qubits - 1 - ctrl)) & 1) and \
               ((i >> (n_qubits - 1 - tgt)) & 1):
                new[i] = state_vec[i] * phase
        return new

    if gate_name == "SWAP":
        q0, q1 = qubits[0], qubits[1]
        new = list(state_vec)
        for i in range(n):
            b0 = (i >> (n_qubits - 1 - q0)) & 1
            b1 = (i >> (n_qubits - 1 - q1)) & 1
            if b0 != b1:
                j = i ^ (1 << (n_qubits - 1 - q0)) ^ (1 << (n_qubits - 1 - q1))
                if i < j:
                    new[i], new[j] = state_vec[j], state_vec[i]
        return new

    if gate_name == "M":
        # Measurement — collapse qubit
        q = qubits[0]
        prob_one = 0.0
        for i in range(n):
            if (i >> (n_qubits - 1 - q)) & 1:
                prob_one += abs(state_vec[i]) ** 2
        outcome = 1 if random.random() < prob_one else 0
        new = [complex(0)] * n
        norm = 0.0
        for i in range(n):
            bit = (i >> (n_qubits - 1 - q)) & 1
            if bit == outcome:
                new[i] = state_vec[i]
                norm += abs(state_vec[i]) ** 2
        if norm > 1e-12:
            scale = 1.0 / math.sqrt(norm)
            for i in range(n):
                new[i] *= scale
        return new

    # Fallback: identity
    return list(state_vec)


def _measure_probabilities(state_vec, n_qubits):
    """Return list of (basis_label, probability) for non-zero amplitudes."""
    result = []
    for i, amp in enumerate(state_vec):
        p = abs(amp) ** 2
        if p > 1e-10:
            label = format(i, f'0{n_qubits}b')
            result.append((label, p))
    result.sort(key=lambda x: x[0])
    return result


def _bloch_angles(amp0, amp1):
    """Compute Bloch sphere theta, phi from qubit amplitudes α|0⟩ + β|1⟩."""
    a, b = abs(amp0), abs(amp1)
    theta = 2.0 * math.acos(min(1.0, a))
    if b > 1e-10:
        phi = cmath.phase(amp1) - cmath.phase(amp0)
    else:
        phi = 0.0
    return theta, phi


def _mini_bloch(theta, phi, size=3):
    """Return a list of strings representing a tiny Bloch sphere projection."""
    # Project onto XZ plane: x = sin(theta)*cos(phi), z = cos(theta)
    x = math.sin(theta) * math.cos(phi)
    z = math.cos(theta)
    lines = []
    for row in range(size * 2 + 1):
        chars = []
        for col in range(size * 2 + 1):
            dy = (row - size) / size  # -1..1
            dx = (col - size) / size
            dist = math.sqrt(dx * dx + dy * dy)
            px = int(round(x * size)) + size
            pz = int(round(-z * size)) + size  # z up → row down
            if row == pz and col == px:
                chars.append("*")
            elif abs(dist - 1.0) < 0.35:
                chars.append(".")
            elif dist < 1.0 and (row == size or col == size):
                chars.append("·")
            else:
                chars.append(" ")
        lines.append("".join(chars))
    return lines


def _reduced_density(state_vec, n_qubits, qubit):
    """Get reduced density matrix diagonal for single qubit (amp0, amp1)."""
    n = len(state_vec)
    a0 = complex(0)
    a1 = complex(0)
    p0 = 0.0
    p1 = 0.0
    for i in range(n):
        bit = (i >> (n_qubits - 1 - qubit)) & 1
        if bit == 0:
            p0 += abs(state_vec[i]) ** 2
            a0 += state_vec[i]
        else:
            p1 += abs(state_vec[i]) ** 2
            a1 += state_vec[i]
    # Normalize
    norm0 = math.sqrt(p0) if p0 > 1e-12 else 0
    norm1 = math.sqrt(p1) if p1 > 1e-12 else 0
    return (norm0, norm1 * cmath.exp(1j * (cmath.phase(a1) - cmath.phase(a0) if abs(a0) > 1e-12 else 0)))


def _entanglement_pairs(state_vec, n_qubits):
    """Detect entangled pairs by checking if reduced state is mixed."""
    pairs = []
    for q in range(n_qubits):
        # Check purity of reduced density matrix
        p0 = 0.0
        p1 = 0.0
        n = len(state_vec)
        for i in range(n):
            if (i >> (n_qubits - 1 - q)) & 1:
                p1 += abs(state_vec[i]) ** 2
            else:
                p0 += abs(state_vec[i]) ** 2
        purity = p0 * p0 + p1 * p1
        if purity < 0.99:  # not a pure single-qubit state → entangled
            pairs.append(q)
    # Return pairs of entangled qubits
    if len(pairs) >= 2:
        return [(pairs[i], pairs[j]) for i in range(len(pairs))
                for j in range(i + 1, len(pairs))]
    return []


# ── Color pairs for entanglement links ─────────────────────────────────

ENT_COLORS = [3, 4, 5, 6, 2]  # cyan, blue, magenta, yellow, green

# ── Mode functions ──────────────────────────────────────────────────────


def _enter_qcirc_mode(self):
    """Enter quantum circuit mode — show preset menu."""
    self.qcirc_menu = True
    self.qcirc_menu_sel = 0
    self.qcirc_running = False
    self._flash("Quantum Circuit Simulator — select a circuit")


def _exit_qcirc_mode(self):
    """Exit quantum circuit mode."""
    self.qcirc_mode = False
    self.qcirc_menu = False
    self.qcirc_running = False
    self.qcirc_state = None
    self._flash("Quantum Circuit OFF")


def _qcirc_init(self, preset_idx):
    """Initialize circuit from preset."""
    name, _desc, config = QCIRC_PRESETS[preset_idx]
    self.qcirc_preset_idx = preset_idx
    self.qcirc_preset_name = name
    self.qcirc_n_qubits = config["n_qubits"]
    self.qcirc_gates = list(config["gates"])
    self.qcirc_desc = config.get("desc", "")
    n = 1 << self.qcirc_n_qubits
    self.qcirc_state = [complex(0)] * n
    self.qcirc_state[0] = complex(1)  # |00...0⟩
    self.qcirc_gate_idx = 0
    self.qcirc_step_count = 0
    self.qcirc_running = False
    self.qcirc_menu = False
    self.qcirc_histogram = {}
    self.qcirc_total_shots = 0
    self.qcirc_anim_tick = 0
    self.qcirc_measured_bits = {}
    self.qcirc_speed = 8  # frames between steps when auto-running
    self._flash(f"Quantum Circuit: {name} — Space=run, n=step, m=measure×100")


def _qcirc_step(self):
    """Apply the next gate in the circuit."""
    if self.qcirc_gate_idx >= len(self.qcirc_gates):
        return False
    gate_name, qubits, params = self.qcirc_gates[self.qcirc_gate_idx]
    self.qcirc_state = _apply_gate(
        self.qcirc_state, self.qcirc_n_qubits, gate_name, qubits, params)
    if gate_name == "M":
        q = qubits[0]
        # Record measured value
        for i, amp in enumerate(self.qcirc_state):
            if abs(amp) ** 2 > 0.5:
                bit = (i >> (self.qcirc_n_qubits - 1 - q)) & 1
                self.qcirc_measured_bits[q] = bit
                break
    self.qcirc_gate_idx += 1
    self.qcirc_step_count += 1
    return True


def _qcirc_run_full(self):
    """Run all remaining gates."""
    while self.qcirc_gate_idx < len(self.qcirc_gates):
        _qcirc_step(self)


def _qcirc_measure_shots(self, n_shots=100):
    """Run circuit n_shots times and accumulate histogram."""
    config = QCIRC_PRESETS[self.qcirc_preset_idx][2]
    nq = config["n_qubits"]
    gates = config["gates"]
    for _ in range(n_shots):
        n = 1 << nq
        sv = [complex(0)] * n
        sv[0] = complex(1)
        for gate_name, qubits, params in gates:
            sv = _apply_gate(sv, nq, gate_name, qubits, params)
        # Measure all qubits
        probs = _measure_probabilities(sv, nq)
        # Sample from distribution
        r = random.random()
        cumulative = 0.0
        outcome = probs[-1][0] if probs else "0" * nq
        for label, p in probs:
            cumulative += p
            if r < cumulative:
                outcome = label
                break
        self.qcirc_histogram[outcome] = self.qcirc_histogram.get(outcome, 0) + 1
        self.qcirc_total_shots += 1


def _handle_qcirc_menu_key(self, key):
    """Handle key input in preset menu."""
    if key == curses.KEY_UP:
        self.qcirc_menu_sel = (self.qcirc_menu_sel - 1) % len(QCIRC_PRESETS)
        return True
    elif key == curses.KEY_DOWN:
        self.qcirc_menu_sel = (self.qcirc_menu_sel + 1) % len(QCIRC_PRESETS)
        return True
    elif key in (ord('\n'), ord(' ')):
        _qcirc_init(self, self.qcirc_menu_sel)
        return True
    elif key == ord('q'):
        _exit_qcirc_mode(self)
        return True
    return False


def _handle_qcirc_key(self, key):
    """Handle key input during simulation."""
    if key == ord(' '):
        self.qcirc_running = not self.qcirc_running
        return True
    elif key == ord('n'):
        _qcirc_step(self)
        return True
    elif key == ord('f'):
        _qcirc_run_full(self)
        return True
    elif key == ord('m'):
        _qcirc_measure_shots(self, 100)
        return True
    elif key == ord('M'):
        _qcirc_measure_shots(self, 1000)
        return True
    elif key == ord('r'):
        _qcirc_init(self, self.qcirc_preset_idx)
        return True
    elif key == ord('R'):
        _enter_qcirc_mode(self)
        return True
    elif key == ord('+') or key == ord('='):
        self.qcirc_speed = max(1, self.qcirc_speed - 2)
        return True
    elif key == ord('-'):
        self.qcirc_speed = min(30, self.qcirc_speed + 2)
        return True
    elif key == ord('q'):
        _exit_qcirc_mode(self)
        return True
    return False


def _draw_qcirc_menu(self, max_y, max_x):
    """Draw preset selection menu."""
    self.stdscr.erase()
    title = "╔══ Quantum Circuit Simulator ══╗"
    if max_x > len(title) + 2:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(5) | curses.A_BOLD)
    subtitle = "Select a preset circuit:"
    self.stdscr.addstr(3, max(0, (max_x - len(subtitle)) // 2), subtitle,
                       curses.color_pair(6))
    for i, (name, desc, _cfg) in enumerate(QCIRC_PRESETS):
        y = 5 + i * 2
        if y >= max_y - 3:
            break
        attr = curses.A_REVERSE | curses.A_BOLD if i == self.qcirc_menu_sel \
            else curses.A_NORMAL
        marker = " > " if i == self.qcirc_menu_sel else "   "
        line = f"{marker}{i + 1}. {name}"
        try:
            self.stdscr.addstr(y, 2, line[:max_x - 4], attr | curses.color_pair(3))
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8], curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass

    help_y = max_y - 2
    help_text = "↑/↓ select  ·  Enter/Space start  ·  q quit"
    try:
        self.stdscr.addstr(help_y, max(0, (max_x - len(help_text)) // 2),
                           help_text[:max_x - 1], curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass
    self.stdscr.noutrefresh()


def _draw_qcirc(self, max_y, max_x):
    """Draw quantum circuit visualization."""
    self.stdscr.erase()
    if self.qcirc_state is None:
        return

    nq = self.qcirc_n_qubits
    gates = self.qcirc_gates
    gate_idx = self.qcirc_gate_idx
    sv = self.qcirc_state

    # Auto-step when running
    if self.qcirc_running:
        self.qcirc_anim_tick += 1
        if self.qcirc_anim_tick >= self.qcirc_speed:
            self.qcirc_anim_tick = 0
            if not _qcirc_step(self):
                self.qcirc_running = False

    # ── Layout ──
    # Top section: circuit diagram
    # Middle: qubit state + Bloch spheres
    # Bottom: measurement histogram + status

    y = 0

    # Title
    title = f" Quantum Circuit: {self.qcirc_preset_name} "
    try:
        self.stdscr.addstr(y, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(5) | curses.A_BOLD)
    except curses.error:
        pass
    y += 1

    # ── Circuit diagram ──
    circuit_start_y = y
    wire_start_x = 6
    gate_width = 5
    max_gates_visible = max(1, (max_x - wire_start_x - 10) // gate_width)
    # Scroll window for gates
    scroll_start = max(0, gate_idx - max_gates_visible + 2)
    visible_gates = gates[scroll_start:scroll_start + max_gates_visible]

    for q in range(nq):
        row = circuit_start_y + q * 2
        if row >= max_y - 10:
            break
        # Qubit label
        label = f"q{q}|0>"
        try:
            self.stdscr.addstr(row, 0, label[:5], curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

        # Wire line
        wire_end = min(max_x - 1, wire_start_x + len(visible_gates) * gate_width + 2)
        for cx in range(wire_start_x, wire_end):
            try:
                self.stdscr.addstr(row, cx, "─", curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

        # Gates on this wire
        for gi, (gname, gqubits, gparams) in enumerate(visible_gates):
            actual_gi = scroll_start + gi
            gx = wire_start_x + gi * gate_width + 2
            if gx >= max_x - 3:
                break

            is_current = (actual_gi == gate_idx)  # next gate to execute
            is_done = (actual_gi < gate_idx)

            if q in gqubits:
                sym = GATE_SYMBOLS.get(gname, gname[0])
                if gname in ("CNOT", "CX") and q == gqubits[0]:
                    sym = "●"  # control dot
                elif gname in ("CNOT", "CX") and q == gqubits[1]:
                    sym = "⊕"  # target
                elif gname in ("CZ", "CZ_GATE") and q == gqubits[1]:
                    sym = "●"
                elif gname == "SWAP":
                    sym = "×"
                elif gname == "CP" and q == gqubits[0]:
                    sym = "●"

                if gname == "M":
                    color = curses.color_pair(2) | curses.A_BOLD  # red
                elif is_current:
                    color = curses.color_pair(4) | curses.A_BOLD  # bright
                elif is_done:
                    color = curses.color_pair(3)  # completed
                else:
                    color = curses.color_pair(6)  # pending

                try:
                    box = f"[{sym}]"
                    self.stdscr.addstr(row, gx, box[:3], color)
                except curses.error:
                    pass

                # Draw vertical connections for multi-qubit gates
                if len(gqubits) > 1 and q == gqubits[0]:
                    for vq in range(gqubits[0] + 1, gqubits[-1] + 1):
                        vy = circuit_start_y + vq * 2
                        if vy < max_y - 8 and vq not in gqubits:
                            try:
                                self.stdscr.addstr(vy, gx + 1, "│", color)
                            except curses.error:
                                pass
                        # Connect between rows
                        if vq != gqubits[-1] or vq in gqubits:
                            vy_between = circuit_start_y + (vq - 1) * 2 + 1
                            if 0 <= vy_between < max_y - 8:
                                try:
                                    self.stdscr.addstr(vy_between, gx + 1, "│",
                                                       color | curses.A_DIM)
                                except curses.error:
                                    pass

    y = circuit_start_y + nq * 2 + 1
    if y >= max_y - 2:
        y = max_y - 8

    # ── Separator ──
    sep = "─" * min(max_x - 1, 60)
    try:
        self.stdscr.addstr(y, 0, sep, curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass
    y += 1

    # ── State vector + Bloch spheres ──
    # Show amplitudes
    state_y = y
    probs = _measure_probabilities(sv, nq)
    ent_pairs = _entanglement_pairs(sv, nq)

    # Entanglement indicators
    if ent_pairs and y < max_y - 6:
        ent_str = "Entangled: "
        for ei, (qa, qb) in enumerate(ent_pairs[:4]):
            col_idx = ENT_COLORS[ei % len(ENT_COLORS)]
            ent_str_part = f"q{qa}~q{qb} "
            try:
                self.stdscr.addstr(y, 1 + len(ent_str) + ei * 6, ent_str_part,
                                   curses.color_pair(col_idx) | curses.A_BOLD)
            except curses.error:
                pass
        try:
            self.stdscr.addstr(y, 1, ent_str, curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass
        y += 1

    # State vector display
    sv_label = "State: "
    try:
        self.stdscr.addstr(y, 1, sv_label, curses.color_pair(6))
    except curses.error:
        pass
    sx = 1 + len(sv_label)
    for label, p in probs:
        amp = sv[int(label, 2)]
        amp_r = amp.real
        amp_i = amp.imag
        if abs(amp_i) < 1e-6:
            amp_str = f"{amp_r:+.3f}|{label}>"
        elif abs(amp_r) < 1e-6:
            amp_str = f"{amp_i:+.3f}i|{label}>"
        else:
            amp_str = f"({amp_r:+.2f}{amp_i:+.2f}i)|{label}>"
        if sx + len(amp_str) + 2 >= max_x:
            y += 1
            sx = 8
            if y >= max_y - 4:
                break
        try:
            self.stdscr.addstr(y, sx, amp_str, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass
        sx += len(amp_str) + 1
    y += 1

    # Probability bars
    if y < max_y - 4:
        bar_width = min(20, max(8, (max_x - 15) // max(1, len(probs))))
        try:
            self.stdscr.addstr(y, 1, "Prob: ", curses.color_pair(6))
        except curses.error:
            pass
        y += 1
        for label, p in probs:
            if y >= max_y - 3:
                break
            filled = int(p * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            pct = f" {p * 100:5.1f}%"
            try:
                self.stdscr.addstr(y, 2, f"|{label}> ", curses.color_pair(6))
                self.stdscr.addstr(y, 2 + nq + 4, bar, curses.color_pair(4) | curses.A_BOLD)
                self.stdscr.addstr(y, 2 + nq + 4 + bar_width, pct, curses.color_pair(3))
            except curses.error:
                pass
            y += 1

    # ── Bloch spheres (right side) ──
    bloch_x = max(max_x - 12 * nq - 2, max_x // 2 + 5)
    if bloch_x > 20 and bloch_x + 10 < max_x:
        bloch_y = circuit_start_y + 1
        for q in range(min(nq, 4)):
            amp0, amp1 = _reduced_density(sv, nq, q)
            theta, phi = _bloch_angles(amp0, amp1)
            lines = _mini_bloch(theta, phi, size=2)
            bx = bloch_x + q * 12
            try:
                self.stdscr.addstr(bloch_y, bx + 1, f"q{q}",
                                   curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass
            for li, line in enumerate(lines):
                ry = bloch_y + 1 + li
                if ry < max_y - 4 and bx + len(line) < max_x:
                    try:
                        self.stdscr.addstr(ry, bx, line,
                                           curses.color_pair(4))
                    except curses.error:
                        pass

    # ── Measurement histogram ──
    if self.qcirc_total_shots > 0 and y < max_y - 2:
        try:
            self.stdscr.addstr(y, 1, f"Histogram ({self.qcirc_total_shots} shots):",
                               curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass
        y += 1
        hist_bar_w = min(25, max(8, max_x - 20))
        sorted_hist = sorted(self.qcirc_histogram.items())
        for label, count in sorted_hist:
            if y >= max_y - 1:
                break
            frac = count / self.qcirc_total_shots
            filled = int(frac * hist_bar_w)
            bar = "▓" * filled + "░" * (hist_bar_w - filled)
            try:
                self.stdscr.addstr(y, 2, f"|{label}> ", curses.color_pair(6))
                self.stdscr.addstr(y, 2 + nq + 4, bar, curses.color_pair(2) | curses.A_BOLD)
                self.stdscr.addstr(y, 2 + nq + 4 + hist_bar_w,
                                   f" {count:4d} ({frac * 100:5.1f}%)",
                                   curses.color_pair(3))
            except curses.error:
                pass
            y += 1

    # ── Status bar ──
    gate_progress = f"Gate {gate_idx}/{len(gates)}"
    status_parts = [
        gate_progress,
        f"Qubits: {nq}",
        "DONE" if gate_idx >= len(gates) else ("RUNNING" if self.qcirc_running else "PAUSED"),
    ]
    status = "  │  ".join(status_parts)
    controls = " Space=run n=step f=all m=100shots M=1000 r=reset R=menu q=quit +/-=speed"
    try:
        self.stdscr.addstr(max_y - 2, 0, status[:max_x - 1],
                           curses.color_pair(5) | curses.A_BOLD)
        self.stdscr.addstr(max_y - 1, 0, controls[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    self.stdscr.noutrefresh()


# ── Registration ────────────────────────────────────────────────────────

def register(App):
    """Register quantum circuit mode on App class."""
    App.QCIRC_PRESETS = QCIRC_PRESETS
    App._enter_qcirc_mode = _enter_qcirc_mode
    App._exit_qcirc_mode = _exit_qcirc_mode
    App._qcirc_init = _qcirc_init
    App._qcirc_step = _qcirc_step
    App._qcirc_run_full = _qcirc_run_full
    App._qcirc_measure_shots = _qcirc_measure_shots
    App._handle_qcirc_menu_key = _handle_qcirc_menu_key
    App._handle_qcirc_key = _handle_qcirc_key
    App._draw_qcirc_menu = _draw_qcirc_menu
    App._draw_qcirc = _draw_qcirc
