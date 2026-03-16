"""Mode: protein_folding — Protein Folding & Misfolding simulation.

2D lattice HP (hydrophobic-polar) protein folding with Monte Carlo energy
minimization, misfolding & prion-like aggregation into amyloid fibrils,
chaperone rescue (GroEL/GroES analog), and heat shock response.

Three views:
  1) Spatial fold map — chain topology with residue coloring, contact map
     overlay, chaperones, fibrils, and heat shock field
  2) Energy landscape — folding funnel with current state, native energy,
     contact map matrix
  3) Time-series sparkline graphs — 10 metrics

Six presets:
  Normal Folding, Prion Propagation, Heat Shock Stress,
  Chaperone Deficiency, Amyloid Cascade, Intrinsically Disordered Protein
"""
import curses
import math
import random


# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

PROTEIN_FOLDING_PRESETS = [
    ("Normal Folding",
     "Single chain folds via Monte Carlo HP model — hydrophobic collapse to native state",
     "normal"),
    ("Prion Propagation",
     "Misfolded protein recruits native proteins into amyloid conformation — templated misfolding cascade",
     "prion"),
    ("Heat Shock Stress",
     "Temperature spike denatures proteins — heat shock factor triggers chaperone upregulation",
     "heatshock"),
    ("Chaperone Deficiency",
     "Reduced GroEL/GroES — misfolding accumulates without rescue, aggregation dominates",
     "chaperone_def"),
    ("Amyloid Cascade (Alzheimer's analog)",
     "Amyloidogenic sequence prone to beta-sheet misfolding — fibril nucleation and elongation",
     "amyloid"),
    ("Intrinsically Disordered Protein",
     "Low hydrophobic content — no stable fold, samples broad conformational ensemble",
     "disordered"),
]


# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

_NEIGHBORS_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]

# HP model energy
_HH_CONTACT_ENERGY = -1.0   # H-H topological contact (non-bonded neighbors)
_HP_CONTACT_ENERGY = -0.1   # H-P contact (weak)
_PP_CONTACT_ENERGY = 0.0    # P-P contact (none)
_BACKBONE_PENALTY = 5.0     # self-intersection penalty (effectively forbidden)
_HBOND_ENERGY = -0.3        # hydrogen bond contribution

# Monte Carlo
_MC_STEPS_PER_TICK = 8      # pivot/crankshaft attempts per tick
_BOLTZMANN_K = 1.0          # Boltzmann constant (arbitrary units)
_BASE_TEMP = 1.0            # baseline temperature

# Misfolding
_MISFOLD_PROB = 0.003       # spontaneous misfolding probability per tick per protein
_PRION_RECRUIT_RADIUS = 4   # radius for templated misfolding recruitment
_PRION_RECRUIT_PROB = 0.05  # probability of recruitment per contact per tick
_FIBRIL_JOIN_RADIUS = 3     # radius for fibril elongation
_FIBRIL_JOIN_PROB = 0.08    # probability misfolded protein joins fibril

# Chaperone (GroEL/GroES)
_CHAPERONE_SPEED = 0.8      # movement per tick
_CHAPERONE_RESCUE_RADIUS = 3
_CHAPERONE_RESCUE_PROB = 0.12  # probability of rescuing a misfolded protein
_CHAPERONE_CYCLE_TIME = 15  # ticks to refold a captured protein
_CHAPERONE_SPAWN_RATE = 0.01  # base rate of new chaperone appearance

# Heat shock
_HEAT_SHOCK_DIFFUSE = 0.10
_HEAT_SHOCK_DECAY = 0.008
_HEAT_SHOCK_DENATURE_PROB = 0.02  # per tick per protein at high temp
_HEAT_SHOCK_CHAPERONE_BOOST = 3.0  # multiplier for chaperone spawn rate under stress

# Simulation limits
_MAX_PROTEINS = 30
_MAX_FIBRILS = 12
_MAX_CHAPERONES = 15
_DEFAULT_CHAIN_LEN = 20

# Sequences: H = hydrophobic, P = polar
_SEQUENCES = {
    "normal":      "HPHPPHHPHPPHPHHPHHPH",
    "prion":       "HHPHHPHHPHHPHHPHHPHH",
    "heatshock":   "HPHPPHHPHPPHPHHPHHPH",
    "chaperone_def": "HPHPPHHPHPPHPHHPHHPH",
    "amyloid":     "HHHPHHHHPHHHHPHHHPHH",
    "disordered":  "PPPHPPPPPHPPPPPPHPPP",
}


# ══════════════════════════════════════════════════════════════════════
#  Data classes
# ══════════════════════════════════════════════════════════════════════

class _Residue:
    """A single amino acid residue on the lattice."""
    __slots__ = ('r', 'c', 'kind')  # kind: 'H' or 'P'

    def __init__(self, r, c, kind):
        self.r = r
        self.c = c
        self.kind = kind


class _Protein:
    """A protein chain on the 2D lattice."""
    __slots__ = ('residues', 'state', 'energy', 'native_energy',
                 'native_contacts', 'ox', 'oy', 'age',
                 'capture_timer', 'sequence')

    def __init__(self, residues, sequence, ox=0, oy=0):
        self.residues = residues      # list of _Residue
        self.sequence = sequence
        self.state = 'folding'        # folding | native | misfolded | captured
        self.energy = 0.0
        self.native_energy = 0.0
        self.native_contacts = 0
        self.ox = ox                  # offset x in world space
        self.oy = oy                  # offset y in world space
        self.age = 0
        self.capture_timer = 0


class _Chaperone:
    """GroEL/GroES-like chaperone protein."""
    __slots__ = ('r', 'c', 'state', 'timer', 'captured_protein')

    def __init__(self, r, c):
        self.r = r
        self.c = c
        self.state = 'free'  # free | folding
        self.timer = 0
        self.captured_protein = None


class _Fibril:
    """An amyloid fibril aggregate."""
    __slots__ = ('positions', 'length')

    def __init__(self, r, c):
        self.positions = [(r, c)]
        self.length = 1


# ══════════════════════════════════════════════════════════════════════
#  HP model energy calculation
# ══════════════════════════════════════════════════════════════════════

def _compute_energy(residues):
    """Compute HP lattice energy: count non-bonded H-H contacts."""
    occupied = {}
    for i, res in enumerate(residues):
        occupied[(res.r, res.c)] = i

    energy = 0.0
    contacts = 0
    for i, res in enumerate(residues):
        for dr, dc in _NEIGHBORS_4:
            nr, nc = res.r + dr, res.c + dc
            j = occupied.get((nr, nc))
            if j is not None and abs(j - i) > 1:  # non-bonded
                ki, kj = res.kind, residues[j].kind
                if ki == 'H' and kj == 'H':
                    energy += _HH_CONTACT_ENERGY
                    contacts += 1
                elif (ki == 'H' and kj == 'P') or (ki == 'P' and kj == 'H'):
                    energy += _HP_CONTACT_ENERGY
                else:
                    energy += _PP_CONTACT_ENERGY
    # Each pair counted twice
    energy /= 2.0
    contacts //= 2
    return energy, contacts


def _is_valid_chain(residues):
    """Check no self-intersection and all bonds are unit length."""
    seen = set()
    for i, res in enumerate(residues):
        pos = (res.r, res.c)
        if pos in seen:
            return False
        seen.add(pos)
        if i > 0:
            prev = residues[i - 1]
            dr = abs(res.r - prev.r)
            dc = abs(res.c - prev.c)
            if dr + dc != 1:
                return False
    return True


def _create_straight_chain(sequence, start_r, start_c):
    """Create a straight horizontal chain."""
    residues = []
    for i, kind in enumerate(sequence):
        residues.append(_Residue(start_r, start_c + i, kind))
    return residues


def _pivot_move(residues, temperature):
    """Attempt a pivot move on the chain. Returns new residues if accepted."""
    n = len(residues)
    if n < 3:
        return residues

    # Pick pivot point (not endpoints)
    pivot_idx = random.randint(1, n - 2)
    # Pick direction: fold left or right part
    fold_left = random.random() < 0.5
    # Pick rotation: 90, 180, or 270 degrees
    rotation = random.choice([1, 2, 3])  # quarter turns

    new_residues = [_Residue(r.r, r.c, r.kind) for r in residues]
    pr, pc = residues[pivot_idx].r, residues[pivot_idx].c

    if fold_left:
        indices = range(0, pivot_idx)
    else:
        indices = range(pivot_idx + 1, n)

    for idx in indices:
        dr = residues[idx].r - pr
        dc = residues[idx].c - pc
        for _ in range(rotation):
            dr, dc = -dc, dr  # 90 degree rotation
        new_residues[idx] = _Residue(pr + dr, pc + dc, residues[idx].kind)

    if not _is_valid_chain(new_residues):
        return residues

    # Metropolis criterion
    old_e, _ = _compute_energy(residues)
    new_e, _ = _compute_energy(new_residues)
    dE = new_e - old_e

    if dE <= 0:
        return new_residues
    else:
        if temperature > 0.01:
            prob = math.exp(-dE / (_BOLTZMANN_K * temperature))
            if random.random() < prob:
                return new_residues
        return residues


def _crankshaft_move(residues, temperature):
    """Attempt a crankshaft move (2-bead flip)."""
    n = len(residues)
    if n < 4:
        return residues

    # Pick two consecutive internal residues
    i = random.randint(1, n - 3)
    j = i + 1

    # Check if i-1 and j+1 are adjacent (forming a U-shape)
    r0, c0 = residues[i - 1].r, residues[i - 1].c
    r3, c3 = residues[j + 1].r, residues[j + 1].c
    if abs(r0 - r3) + abs(c0 - c3) != 2:
        return residues

    # Flip the two middle residues
    new_residues = [_Residue(r.r, r.c, r.kind) for r in residues]
    # Reflect across the line connecting i-1 and j+1
    mid_r = (r0 + r3) / 2.0
    mid_c = (c0 + c3) / 2.0

    for idx in (i, j):
        new_r = int(2 * mid_r - residues[idx].r)
        new_c = int(2 * mid_c - residues[idx].c)
        new_residues[idx] = _Residue(new_r, new_c, residues[idx].kind)

    if not _is_valid_chain(new_residues):
        return residues

    old_e, _ = _compute_energy(residues)
    new_e, _ = _compute_energy(new_residues)
    dE = new_e - old_e

    if dE <= 0:
        return new_residues
    else:
        if temperature > 0.01:
            prob = math.exp(-dE / (_BOLTZMANN_K * temperature))
            if random.random() < prob:
                return new_residues
        return residues


# ══════════════════════════════════════════════════════════════════════
#  Field diffusion
# ══════════════════════════════════════════════════════════════════════

def _diffuse_field(field, rows, cols, coeff):
    """Simple 4-neighbor Laplacian diffusion."""
    buf = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            val = field[r][c]
            total = 0.0
            cnt = 0
            for dr, dc in _NEIGHBORS_4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    total += field[nr][nc]
                    cnt += 1
            buf[r][c] = val + coeff * (total / cnt - val) if cnt > 0 else val
    for r in range(rows):
        for c in range(cols):
            field[r][c] = max(0.0, buf[r][c])


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_protein_folding_mode(self):
    """Enter protein folding mode — show preset menu."""
    self.protfold_mode = True
    self.protfold_menu = True
    self.protfold_menu_sel = 0


def _exit_protein_folding_mode(self):
    """Exit protein folding mode."""
    self.protfold_mode = False
    self.protfold_menu = False
    self.protfold_running = False
    for attr in list(vars(self)):
        if attr.startswith('protfold_') and attr not in ('protfold_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _protfold_init(self, preset_idx):
    """Initialize simulation for the chosen preset."""
    name, _desc, pid = PROTEIN_FOLDING_PRESETS[preset_idx]
    max_y, max_x = self.stdscr.getmaxyx()
    rows = max(20, max_y - 4)
    cols = max(40, max_x - 2)

    self.protfold_menu = False
    self.protfold_running = False
    self.protfold_preset_name = name
    self.protfold_preset_idx = preset_idx
    self.protfold_preset_id = pid
    self.protfold_rows = rows
    self.protfold_cols = cols
    self.protfold_generation = 0
    self.protfold_speed = 1
    self.protfold_view = "fold"  # fold | energy | graphs

    # Temperature
    self.protfold_temperature = _BASE_TEMP
    self.protfold_heat_shock = False

    # Heat shock field
    self.protfold_hsf = [[0.0] * cols for _ in range(rows)]

    # Proteins
    self.protfold_proteins = []
    self.protfold_sequence = _SEQUENCES.get(pid, _SEQUENCES["normal"])

    # Chaperones
    self.protfold_chaperones = []

    # Fibrils
    self.protfold_fibrils = []

    # Contact map overlay toggle
    self.protfold_show_contacts = False

    # History for sparklines
    self.protfold_history = {
        'native_contacts': [],
        'free_energy': [],
        'radius_gyration': [],
        'aggregation': [],
        'chaperone_activity': [],
        'temperature': [],
        'misfolded_frac': [],
        'fibril_length': [],
        'entropy': [],
        'folding_rate': [],
    }

    # Track folding events for rate calculation
    self.protfold_fold_events = 0

    _protfold_setup_preset(self, pid, rows, cols)
    self._flash(f"Protein Folding: {name}")


def _protfold_setup_preset(self, pid, rows, cols):
    """Configure initial conditions per preset."""
    seq = self.protfold_sequence
    mid_r = rows // 2
    mid_c = cols // 2

    if pid == "normal":
        # Single chain in center
        chain = _create_straight_chain(seq, mid_r, mid_c - len(seq) // 2)
        p = _Protein(chain, seq, 0, 0)
        p.energy, p.native_contacts = _compute_energy(chain)
        self.protfold_proteins.append(p)
        # A few chaperones
        for _ in range(3):
            r = random.randint(2, rows - 3)
            c = random.randint(2, cols - 3)
            self.protfold_chaperones.append(_Chaperone(r, c))

    elif pid == "prion":
        # Several native proteins + one misfolded seed
        for i in range(8):
            sr = mid_r + random.randint(-rows // 4, rows // 4)
            sc = mid_c + random.randint(-cols // 4, cols // 4)
            chain = _create_straight_chain(seq, 0, 0)
            p = _Protein(chain, seq, sc, sr)
            p.state = 'folding'
            # Do some quick folding to get them partially folded
            for _ in range(30):
                p.residues = _pivot_move(p.residues, 0.5)
            p.energy, p.native_contacts = _compute_energy(p.residues)
            if i == 0:
                p.state = 'misfolded'  # seed prion
            else:
                p.state = 'native'
            self.protfold_proteins.append(p)
        # Fewer chaperones
        for _ in range(2):
            r = random.randint(2, rows - 3)
            c = random.randint(2, cols - 3)
            self.protfold_chaperones.append(_Chaperone(r, c))

    elif pid == "heatshock":
        # Normal proteins, temperature will spike
        for i in range(6):
            sr = mid_r + random.randint(-rows // 4, rows // 4)
            sc = mid_c + random.randint(-cols // 4, cols // 4)
            chain = _create_straight_chain(seq, 0, 0)
            p = _Protein(chain, seq, sc, sr)
            for _ in range(40):
                p.residues = _pivot_move(p.residues, 0.5)
            p.energy, p.native_contacts = _compute_energy(p.residues)
            p.state = 'native'
            self.protfold_proteins.append(p)
        # Chaperones available
        for _ in range(4):
            r = random.randint(2, rows - 3)
            c = random.randint(2, cols - 3)
            self.protfold_chaperones.append(_Chaperone(r, c))
        # Schedule heat shock
        self.protfold_heat_shock = True
        self.protfold_temperature = _BASE_TEMP

    elif pid == "chaperone_def":
        # Normal proteins, very few chaperones
        for i in range(8):
            sr = mid_r + random.randint(-rows // 4, rows // 4)
            sc = mid_c + random.randint(-cols // 4, cols // 4)
            chain = _create_straight_chain(seq, 0, 0)
            p = _Protein(chain, seq, sc, sr)
            for _ in range(20):
                p.residues = _pivot_move(p.residues, 0.8)
            p.energy, p.native_contacts = _compute_energy(p.residues)
            p.state = 'folding'
            self.protfold_proteins.append(p)
        # Only 1 chaperone
        self.protfold_chaperones.append(_Chaperone(mid_r, mid_c))

    elif pid == "amyloid":
        # Amyloidogenic proteins prone to misfolding
        for i in range(10):
            sr = mid_r + random.randint(-rows // 4, rows // 4)
            sc = mid_c + random.randint(-cols // 4, cols // 4)
            chain = _create_straight_chain(seq, 0, 0)
            p = _Protein(chain, seq, sc, sr)
            for _ in range(15):
                p.residues = _pivot_move(p.residues, 1.0)
            p.energy, p.native_contacts = _compute_energy(p.residues)
            p.state = 'folding'
            self.protfold_proteins.append(p)
        # Seed one fibril
        fr = mid_r + random.randint(-3, 3)
        fc = mid_c + random.randint(-3, 3)
        fib = _Fibril(fr, fc)
        for i in range(3):
            fib.positions.append((fr, fc + i + 1))
            fib.length += 1
        self.protfold_fibrils.append(fib)
        # Minimal chaperones
        self.protfold_chaperones.append(_Chaperone(mid_r - 5, mid_c - 5))

    elif pid == "disordered":
        # IDP: low hydrophobic content, no stable fold
        for i in range(5):
            sr = mid_r + random.randint(-rows // 4, rows // 4)
            sc = mid_c + random.randint(-cols // 4, cols // 4)
            chain = _create_straight_chain(seq, 0, 0)
            p = _Protein(chain, seq, sc, sr)
            p.energy, p.native_contacts = _compute_energy(p.residues)
            p.state = 'folding'
            self.protfold_proteins.append(p)
        for _ in range(2):
            r = random.randint(2, rows - 3)
            c = random.randint(2, cols - 3)
            self.protfold_chaperones.append(_Chaperone(r, c))


# ══════════════════════════════════════════════════════════════════════
#  Simulation Step
# ══════════════════════════════════════════════════════════════════════

def _radius_of_gyration(residues):
    """Compute radius of gyration of the chain."""
    if not residues:
        return 0.0
    n = len(residues)
    cr = sum(r.r for r in residues) / n
    cc = sum(r.c for r in residues) / n
    rg2 = sum((r.r - cr) ** 2 + (r.c - cc) ** 2 for r in residues) / n
    return math.sqrt(rg2)


def _protfold_step(self):
    """Advance one tick of the protein folding simulation."""
    rows = self.protfold_rows
    cols = self.protfold_cols

    for _ in range(self.protfold_speed):
        self.protfold_generation += 1
        gen = self.protfold_generation
        temp = self.protfold_temperature
        proteins = self.protfold_proteins
        chaperones = self.protfold_chaperones
        fibrils = self.protfold_fibrils

        # ── 1. Heat shock dynamics ──
        if self.protfold_heat_shock:
            # Temperature ramps up then slowly decays
            if gen < 80:
                self.protfold_temperature = _BASE_TEMP + 3.0 * (gen / 80.0)
            elif gen < 150:
                self.protfold_temperature = _BASE_TEMP + 3.0 - 2.5 * ((gen - 80) / 70.0)
            else:
                self.protfold_temperature = max(_BASE_TEMP,
                    self.protfold_temperature - 0.005)
            temp = self.protfold_temperature

            # Heat shock field from high temperature
            if temp > _BASE_TEMP + 0.5:
                for r in range(rows):
                    for c in range(cols):
                        self.protfold_hsf[r][c] += (temp - _BASE_TEMP) * 0.01
                        self.protfold_hsf[r][c] = min(1.0, self.protfold_hsf[r][c])

        # Diffuse and decay heat shock field
        _diffuse_field(self.protfold_hsf, rows, cols, _HEAT_SHOCK_DIFFUSE)
        for r in range(rows):
            for c in range(cols):
                self.protfold_hsf[r][c] = max(0.0,
                    self.protfold_hsf[r][c] - _HEAT_SHOCK_DECAY)

        # ── 2. Monte Carlo folding for each protein ──
        for prot in proteins:
            prot.age += 1
            if prot.state == 'captured':
                prot.capture_timer -= 1
                if prot.capture_timer <= 0:
                    # Released from chaperone, try to refold
                    prot.state = 'folding'
                continue
            if prot.state == 'misfolded':
                continue  # misfolded proteins don't fold

            # MC steps
            for _ in range(_MC_STEPS_PER_TICK):
                if random.random() < 0.5:
                    prot.residues = _pivot_move(prot.residues, temp)
                else:
                    prot.residues = _crankshaft_move(prot.residues, temp)

            prot.energy, prot.native_contacts = _compute_energy(prot.residues)

            # Check if native state reached (energy threshold)
            max_possible = sum(1 for k in prot.sequence if k == 'H') // 2
            if max_possible > 0 and prot.native_contacts >= max_possible * 0.7:
                if prot.state == 'folding':
                    prot.state = 'native'
                    prot.native_energy = prot.energy
                    self.protfold_fold_events += 1

        # ── 3. Spontaneous misfolding ──
        misfold_prob = _MISFOLD_PROB * (1 + max(0, temp - _BASE_TEMP) * 2.0)
        for prot in proteins:
            if prot.state in ('native', 'folding'):
                if random.random() < misfold_prob:
                    prot.state = 'misfolded'

        # ── 4. Heat shock denaturation ──
        if temp > _BASE_TEMP + 1.0:
            denature_prob = _HEAT_SHOCK_DENATURE_PROB * (temp - _BASE_TEMP)
            for prot in proteins:
                if prot.state == 'native' and random.random() < denature_prob:
                    prot.state = 'misfolded'

        # ── 5. Prion-like templated misfolding ──
        misfolded = [p for p in proteins if p.state == 'misfolded']
        for mis in misfolded:
            mr, mc = mis.oy, mis.ox
            for prot in proteins:
                if prot.state == 'native':
                    pr, pc = prot.oy, prot.ox
                    dist = abs(mr - pr) + abs(mc - pc)
                    if dist < _PRION_RECRUIT_RADIUS:
                        if random.random() < _PRION_RECRUIT_PROB:
                            prot.state = 'misfolded'

        # ── 6. Fibril formation / elongation ──
        for mis in misfolded:
            mr, mc = mis.oy, mis.ox
            joined = False
            for fib in fibrils:
                if len(fib.positions) > 0:
                    # Check if near fibril end
                    er, ec = fib.positions[-1]
                    dist = abs(mr - er) + abs(mc - ec)
                    if dist <= _FIBRIL_JOIN_RADIUS and random.random() < _FIBRIL_JOIN_PROB:
                        # Extend fibril
                        fib.positions.append((mr, mc))
                        fib.length += 1
                        mis.state = 'native'  # consumed into fibril
                        mis.state = 'captured'  # remove from active
                        mis.capture_timer = 9999
                        joined = True
                        break
            if not joined and len(fibrils) < _MAX_FIBRILS:
                # Nucleate new fibril if enough misfolded nearby
                nearby_mis = sum(1 for p in proteins
                                 if p.state == 'misfolded' and p is not mis
                                 and abs(p.oy - mr) + abs(p.ox - mc) < _FIBRIL_JOIN_RADIUS)
                if nearby_mis >= 2 and random.random() < 0.02:
                    fib = _Fibril(mr, mc)
                    fibrils.append(fib)

        # ── 7. Chaperone dynamics ──
        # Spawn new chaperones under heat shock
        avg_hsf = 0.0
        hsf_count = 0
        for r in range(0, rows, 3):
            for c in range(0, cols, 3):
                avg_hsf += self.protfold_hsf[r][c]
                hsf_count += 1
        avg_hsf = avg_hsf / max(1, hsf_count)

        spawn_rate = _CHAPERONE_SPAWN_RATE
        if avg_hsf > 0.1:
            spawn_rate *= _HEAT_SHOCK_CHAPERONE_BOOST

        if len(chaperones) < _MAX_CHAPERONES and random.random() < spawn_rate:
            r = random.randint(2, rows - 3)
            c = random.randint(2, cols - 3)
            chaperones.append(_Chaperone(r, c))

        for chap in chaperones:
            if chap.state == 'folding':
                chap.timer -= 1
                if chap.timer <= 0:
                    # Release rescued protein
                    if chap.captured_protein is not None:
                        chap.captured_protein.state = 'folding'
                        chap.captured_protein.capture_timer = 0
                        # Reset chain to extended
                        seq = chap.captured_protein.sequence
                        chap.captured_protein.residues = _create_straight_chain(
                            seq, 0, 0)
                        chap.captured_protein = None
                    chap.state = 'free'
                continue

            # Move toward nearest misfolded protein
            nearest_mis = None
            best_dist = 999
            for prot in proteins:
                if prot.state == 'misfolded':
                    dist = abs(prot.oy - chap.r) + abs(prot.ox - chap.c)
                    if dist < best_dist:
                        best_dist = dist
                        nearest_mis = prot

            if nearest_mis is not None:
                # Move toward it
                dr = nearest_mis.oy - chap.r
                dc = nearest_mis.ox - chap.c
                dist = max(1, abs(dr) + abs(dc))
                chap.r += int(round(dr / dist * _CHAPERONE_SPEED))
                chap.c += int(round(dc / dist * _CHAPERONE_SPEED))
                chap.r = max(0, min(rows - 1, chap.r))
                chap.c = max(0, min(cols - 1, chap.c))

                # Try to rescue
                if best_dist <= _CHAPERONE_RESCUE_RADIUS:
                    if random.random() < _CHAPERONE_RESCUE_PROB:
                        chap.state = 'folding'
                        chap.timer = _CHAPERONE_CYCLE_TIME
                        chap.captured_protein = nearest_mis
                        nearest_mis.state = 'captured'
                        nearest_mis.capture_timer = _CHAPERONE_CYCLE_TIME
            else:
                # Random walk
                chap.r += random.randint(-1, 1)
                chap.c += random.randint(-1, 1)
                chap.r = max(0, min(rows - 1, chap.r))
                chap.c = max(0, min(cols - 1, chap.c))

        # ── 8. Update history ──
        total_contacts = sum(p.native_contacts for p in proteins if p.state != 'captured')
        total_energy = sum(p.energy for p in proteins if p.state != 'captured')
        active = [p for p in proteins if p.state != 'captured']
        n_active = max(1, len(active))

        avg_rg = sum(_radius_of_gyration(p.residues) for p in active) / n_active if active else 0.0

        n_misfolded = sum(1 for p in proteins if p.state == 'misfolded')
        n_total = max(1, len(proteins))
        total_fibril_len = sum(f.length for f in fibrils)

        chap_active = sum(1 for ch in chaperones if ch.state == 'folding')

        # Conformational entropy estimate: use Rg spread
        rg_values = [_radius_of_gyration(p.residues) for p in active]
        if len(rg_values) > 1:
            mean_rg = sum(rg_values) / len(rg_values)
            var_rg = sum((v - mean_rg) ** 2 for v in rg_values) / len(rg_values)
            entropy = math.log(1 + var_rg)
        else:
            entropy = math.log(1 + avg_rg)

        hist = self.protfold_history
        for key in hist:
            if len(hist[key]) > 300:
                hist[key] = hist[key][-200:]

        hist['native_contacts'].append(total_contacts / n_active)
        hist['free_energy'].append(total_energy / n_active)
        hist['radius_gyration'].append(avg_rg)
        hist['aggregation'].append(total_fibril_len)
        hist['chaperone_activity'].append(chap_active)
        hist['temperature'].append(temp)
        hist['misfolded_frac'].append(n_misfolded / n_total)
        hist['fibril_length'].append(total_fibril_len)
        hist['entropy'].append(entropy)
        hist['folding_rate'].append(self.protfold_fold_events)


# ══════════════════════════════════════════════════════════════════════
#  Key handling
# ══════════════════════════════════════════════════════════════════════

def _handle_protfold_menu_key(self, key):
    """Handle key input in the preset selection menu."""
    n = len(PROTEIN_FOLDING_PRESETS)
    if key == ord("q") or key == 27:
        self.protfold_mode = False
        self.protfold_menu = False
        return True
    if key == curses.KEY_UP or key == ord("k"):
        self.protfold_menu_sel = (self.protfold_menu_sel - 1) % n
        return True
    if key == curses.KEY_DOWN or key == ord("j"):
        self.protfold_menu_sel = (self.protfold_menu_sel + 1) % n
        return True
    if key in (10, 13, curses.KEY_ENTER):
        _protfold_init(self, self.protfold_menu_sel)
        return True
    return True


def _handle_protfold_key(self, key):
    """Handle key input during live simulation."""
    if key == ord(" "):
        self.protfold_running = not self.protfold_running
        self._flash("Running" if self.protfold_running else "Paused")
        return True

    if key == ord("n") or key == ord("."):
        _protfold_step(self)
        return True

    if key == ord("v"):
        views = ["fold", "energy", "graphs"]
        cur = views.index(self.protfold_view) if self.protfold_view in views else 0
        self.protfold_view = views[(cur + 1) % len(views)]
        self._flash(f"View: {self.protfold_view}")
        return True

    if key == ord("c"):
        self.protfold_show_contacts = not self.protfold_show_contacts
        self._flash(f"Contacts: {'ON' if self.protfold_show_contacts else 'OFF'}")
        return True

    if key == ord("t"):
        # Temperature bump
        self.protfold_temperature = min(6.0, self.protfold_temperature + 0.5)
        self._flash(f"Temp: {self.protfold_temperature:.1f}")
        return True

    if key == ord("T"):
        # Temperature decrease
        self.protfold_temperature = max(0.1, self.protfold_temperature - 0.5)
        self._flash(f"Temp: {self.protfold_temperature:.1f}")
        return True

    if key == ord("+") or key == ord("="):
        self.protfold_speed = min(20, self.protfold_speed + 1)
        self._flash(f"Speed: {self.protfold_speed}x")
        return True

    if key == ord("-") or key == ord("_"):
        self.protfold_speed = max(1, self.protfold_speed - 1)
        self._flash(f"Speed: {self.protfold_speed}x")
        return True

    if key == ord("r"):
        _protfold_init(self, self.protfold_preset_idx)
        return True

    if key == ord("R") or key == ord("m"):
        self.protfold_running = False
        self.protfold_menu = True
        self.protfold_menu_sel = 0
        return True

    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Menu
# ══════════════════════════════════════════════════════════════════════

def _draw_protfold_menu(self, max_y, max_x):
    """Draw the preset selection menu."""
    self.stdscr.erase()

    title = "── Protein Folding & Misfolding ── Select Scenario ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title[:max_x - 1],
                           curses.A_BOLD)
    except curses.error:
        pass

    sub = "HP lattice model — Monte Carlo folding, prion aggregation, chaperone rescue"
    try:
        self.stdscr.addstr(2, max(0, (max_x - len(sub)) // 2), sub[:max_x - 1],
                           curses.A_DIM)
    except curses.error:
        pass

    y = 4
    for i, (name, desc, _pid) in enumerate(PROTEIN_FOLDING_PRESETS):
        if y + 2 >= max_y - 2:
            break
        sel = i == self.protfold_menu_sel
        marker = "▸ " if sel else "  "
        attr = curses.A_REVERSE if sel else curses.A_NORMAL
        try:
            self.stdscr.addstr(y, 4, f"{marker}{name}"[:max_x - 5], attr | curses.A_BOLD)
            self.stdscr.addstr(y + 1, 8, desc[:max_x - 9], curses.A_DIM)
        except curses.error:
            pass
        y += 3

    controls = "↑/↓ select  ·  Enter start  ·  q quit"
    try:
        self.stdscr.addstr(max_y - 2, max(0, (max_x - len(controls)) // 2),
                           controls[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Live Simulation
# ══════════════════════════════════════════════════════════════════════

def _draw_protfold(self, max_y, max_x):
    """Draw the active simulation."""
    self.stdscr.erase()
    view = self.protfold_view

    if view == "fold":
        _draw_protfold_spatial(self, max_y, max_x)
    elif view == "energy":
        _draw_protfold_energy(self, max_y, max_x)
    elif view == "graphs":
        _draw_protfold_graphs(self, max_y, max_x)

    # Status bar
    n_prot = len(self.protfold_proteins)
    n_native = sum(1 for p in self.protfold_proteins if p.state == 'native')
    n_misf = sum(1 for p in self.protfold_proteins if p.state == 'misfolded')
    n_fold = sum(1 for p in self.protfold_proteins if p.state == 'folding')
    n_fib = sum(f.length for f in self.protfold_fibrils)

    status_parts = [
        f"Gen:{self.protfold_generation}",
        f"Prot:{n_prot}",
        f"Native:{n_native}",
        f"Folding:{n_fold}",
        f"Misfld:{n_misf}",
        f"Fibril:{n_fib}",
        f"T:{self.protfold_temperature:.1f}",
        f"Spd:{self.protfold_speed}x",
        "▶" if self.protfold_running else "⏸",
    ]
    status = "  ".join(status_parts)
    try:
        self.stdscr.addstr(max_y - 1, 0, status[:max_x - 1], curses.A_BOLD)
    except curses.error:
        pass

    hint = "SP:⏯  v:view  c:contacts  t/T:temp±  +/-:speed  r:reset  m:menu"
    try:
        self.stdscr.addstr(0, 0, hint[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass


def _draw_protfold_spatial(self, max_y, max_x):
    """Draw spatial fold map with chain topology, contacts, chaperones, fibrils."""
    rows = self.protfold_rows
    cols = self.protfold_cols
    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, max_x - 1)

    # Build display grid
    grid = [[' '] * draw_cols for _ in range(draw_rows)]
    colors = [[0] * draw_cols for _ in range(draw_rows)]

    # Heat shock field background
    for r in range(draw_rows):
        for c in range(draw_cols):
            hsf = self.protfold_hsf[r][c] if r < rows and c < cols else 0
            if hsf > 0.3:
                grid[r][c] = '·'
                colors[r][c] = 1  # red tint

    # Draw fibrils
    for fib in self.protfold_fibrils:
        for fr, fc in fib.positions:
            if 1 <= fr < draw_rows and 0 <= fc < draw_cols:
                grid[fr][fc] = '▓'
                colors[fr][fc] = 5  # magenta

    # Draw proteins
    for prot in self.protfold_proteins:
        if prot.state == 'captured':
            continue
        ox, oy = prot.ox, prot.oy
        residues = prot.residues

        # Determine color based on state
        if prot.state == 'native':
            state_color = 2  # green
        elif prot.state == 'misfolded':
            state_color = 1  # red
        else:  # folding
            state_color = 3  # yellow

        # Draw backbone bonds
        for i in range(len(residues) - 1):
            r1, c1 = residues[i].r + oy, residues[i].c + ox
            r2, c2 = residues[i + 1].r + oy, residues[i + 1].c + ox
            # Bond between consecutive residues
            mr = (r1 + r2) // 2
            mc = (c1 + c2) // 2
            if mr == r1 and mc == c1:
                pass  # same cell, skip
            elif 1 <= mr < draw_rows and 0 <= mc < draw_cols:
                if r1 == r2:
                    grid[mr][mc] = '─'
                else:
                    grid[mr][mc] = '│'
                colors[mr][mc] = state_color

        # Draw residues
        for i, res in enumerate(residues):
            r = res.r + oy
            c = res.c + ox
            if 1 <= r < draw_rows and 0 <= c < draw_cols:
                if res.kind == 'H':
                    grid[r][c] = '●'  # hydrophobic
                    if prot.state == 'native':
                        colors[r][c] = 4  # blue (hydrophobic core)
                    elif prot.state == 'misfolded':
                        colors[r][c] = 1
                    else:
                        colors[r][c] = 6  # cyan
                else:
                    grid[r][c] = '○'  # polar
                    colors[r][c] = state_color

        # Contact map overlay
        if self.protfold_show_contacts and prot.state != 'captured':
            occupied = {}
            for i, res in enumerate(residues):
                occupied[(res.r, res.c)] = i
            for i, res in enumerate(residues):
                for dr, dc in _NEIGHBORS_4:
                    nr, nc = res.r + dr, res.c + dc
                    j = occupied.get((nr, nc))
                    if j is not None and abs(j - i) > 1:
                        if res.kind == 'H' and residues[j].kind == 'H':
                            # Draw contact indicator
                            cr = res.r + oy
                            cc = res.c + ox
                            if 1 <= cr < draw_rows and 0 <= cc < draw_cols:
                                if grid[cr][cc] in ('●', '○'):
                                    grid[cr][cc] = '◆'
                                    colors[cr][cc] = 7  # white highlight

    # Draw chaperones
    for chap in self.protfold_chaperones:
        r, c = chap.r, chap.c
        if 1 <= r < draw_rows and 0 <= c < draw_cols:
            if chap.state == 'free':
                grid[r][c] = '◎'
                colors[r][c] = 2  # green
            else:
                grid[r][c] = '◉'
                colors[r][c] = 3  # yellow (busy)

    # Render
    for r in range(1, draw_rows):
        for c in range(draw_cols):
            ch = grid[r][c]
            cp = colors[r][c]
            try:
                if cp > 0:
                    self.stdscr.addstr(r, c, ch, curses.color_pair(cp))
                elif ch != ' ':
                    self.stdscr.addstr(r, c, ch, curses.A_DIM)
            except curses.error:
                pass


def _draw_protfold_energy(self, max_y, max_x):
    """Draw energy landscape view: folding funnel + contact map."""
    proteins = self.protfold_proteins
    active = [p for p in proteins if p.state != 'captured']

    # Title
    try:
        self.stdscr.addstr(1, 2, "Energy Landscape / Folding Funnel",
                           curses.A_BOLD)
    except curses.error:
        pass

    # Draw folding funnel visualization
    funnel_h = min(15, max_y - 10)
    funnel_w = min(40, max_x - 10)
    funnel_x = 3

    # Funnel shape: wider at top (high energy), narrow at bottom (native)
    for row in range(funnel_h):
        frac = row / max(1, funnel_h - 1)  # 0 at top, 1 at bottom
        width = int(funnel_w * (1 - frac * 0.7))
        offset = (funnel_w - width) // 2
        y = 3 + row
        if y >= max_y - 3:
            break

        # Draw funnel walls
        left_x = funnel_x + offset
        right_x = funnel_x + offset + width
        try:
            if left_x < max_x:
                self.stdscr.addstr(y, left_x, '╲', curses.color_pair(6))
            if right_x < max_x:
                self.stdscr.addstr(y, right_x, '╱', curses.color_pair(6))
        except curses.error:
            pass

        # Fill with energy gradient
        for cx in range(left_x + 1, min(right_x, max_x - 1)):
            depth_color = 4 if frac > 0.7 else (6 if frac > 0.3 else 1)
            try:
                self.stdscr.addstr(y, cx, '░', curses.color_pair(depth_color))
            except curses.error:
                pass

    # Place proteins on the funnel based on their energy
    if active:
        energies = [p.energy for p in active]
        min_e = min(energies) if energies else 0
        max_e = max(energies) if energies else 1
        rng_e = max_e - min_e if max_e > min_e else 1.0

        for prot in active:
            # Vertical position: energy maps to funnel depth
            e_frac = (prot.energy - min_e) / rng_e if rng_e > 0 else 0.5
            e_frac = 1.0 - e_frac  # lower energy = deeper
            row_pos = int(e_frac * (funnel_h - 1))
            row_pos = max(0, min(funnel_h - 1, row_pos))

            # Horizontal: radius of gyration gives spread
            rg = _radius_of_gyration(prot.residues)
            frac_depth = row_pos / max(1, funnel_h - 1)
            width = int(funnel_w * (1 - frac_depth * 0.7))
            offset = (funnel_w - width) // 2
            cx = funnel_x + offset + width // 2 + int((rg - 3) * 2)
            cx = max(funnel_x + offset + 1, min(funnel_x + offset + width - 1, cx))
            cy = 3 + row_pos

            if 0 <= cy < max_y - 3 and 0 <= cx < max_x:
                glyph = '★' if prot.state == 'native' else ('✕' if prot.state == 'misfolded' else '◆')
                cp = 2 if prot.state == 'native' else (1 if prot.state == 'misfolded' else 3)
                try:
                    self.stdscr.addstr(cy, cx, glyph, curses.color_pair(cp) | curses.A_BOLD)
                except curses.error:
                    pass

    # Energy labels
    try:
        self.stdscr.addstr(3, funnel_x + funnel_w + 3, "High E (unfolded)",
                           curses.color_pair(1))
        self.stdscr.addstr(3 + funnel_h - 1, funnel_x + funnel_w + 3, "Low E (native)",
                           curses.color_pair(2))
    except curses.error:
        pass

    # Legend
    legend_y = 3 + funnel_h + 1
    legends = [
        ("★ Native", 2), ("✕ Misfolded", 1), ("◆ Folding", 3),
    ]
    for i, (lbl, cp) in enumerate(legends):
        try:
            if legend_y < max_y - 3:
                self.stdscr.addstr(legend_y, 3 + i * 16, lbl,
                                   curses.color_pair(cp))
        except curses.error:
            pass

    # Contact map for first protein
    if active:
        prot = active[0]
        cm_y = 3
        cm_x = funnel_x + funnel_w + 25
        n_res = len(prot.residues)
        cm_size = min(n_res, min(max_y - cm_y - 5, max_x - cm_x - 3))

        if cm_size > 3 and cm_x + cm_size < max_x:
            try:
                self.stdscr.addstr(cm_y - 1, cm_x, f"Contact Map ({prot.state})",
                                   curses.A_BOLD)
            except curses.error:
                pass

            occupied = {}
            for i, res in enumerate(prot.residues):
                occupied[(res.r, res.c)] = i

            for i in range(min(n_res, cm_size)):
                for j in range(min(n_res, cm_size)):
                    y = cm_y + i
                    x = cm_x + j
                    if y >= max_y - 2 or x >= max_x - 1:
                        continue
                    if abs(i - j) <= 1:
                        ch = '·'
                        cp = 0
                    else:
                        # Check if residues i and j are lattice neighbors
                        ri, ci_r = prot.residues[i].r, prot.residues[i].c
                        rj, cj_r = prot.residues[j].r, prot.residues[j].c
                        if abs(ri - rj) + abs(ci_r - cj_r) == 1:
                            ki = prot.residues[i].kind
                            kj = prot.residues[j].kind
                            if ki == 'H' and kj == 'H':
                                ch = '█'
                                cp = 4
                            else:
                                ch = '▒'
                                cp = 6
                        else:
                            ch = '·'
                            cp = 0
                    try:
                        if cp > 0:
                            self.stdscr.addstr(y, x, ch, curses.color_pair(cp))
                        else:
                            self.stdscr.addstr(y, x, ch, curses.A_DIM)
                    except curses.error:
                        pass


def _draw_protfold_graphs(self, max_y, max_x):
    """Draw time-series sparkline graphs for protein folding metrics."""
    hist = self.protfold_history
    graph_w = max(10, max_x - 30)

    labels = [
        ("Native Contacts",    'native_contacts',    2),
        ("Free Energy",        'free_energy',         4),
        ("Radius of Gyration", 'radius_gyration',     6),
        ("Aggregation",        'aggregation',         5),
        ("Chaperone Activity", 'chaperone_activity',   2),
        ("Temperature",        'temperature',         1),
        ("Misfolded Frac",     'misfolded_frac',      1),
        ("Fibril Length",      'fibril_length',       5),
        ("Entropy",            'entropy',             3),
        ("Folding Rate",       'folding_rate',        7),
    ]

    bars = "▁▂▃▄▅▆▇█"
    n_bars = len(bars)

    for gi, (label, key, cp) in enumerate(labels):
        base_y = 2 + gi * 2
        if base_y + 1 >= max_y - 2:
            break

        data = hist.get(key, [])
        cur_val = data[-1] if data else 0
        if isinstance(cur_val, float):
            lbl = f"{label}: {cur_val:.3f}"
        else:
            lbl = f"{label}: {cur_val}"
        try:
            self.stdscr.addstr(base_y, 2, lbl[:24],
                               curses.color_pair(cp) | curses.A_BOLD)
        except curses.error:
            pass

        if data:
            visible = data[-graph_w:]
            mn = min(visible)
            mx = max(visible)
            rng = mx - mn if mx > mn else 1.0
            color = curses.color_pair(cp)
            for i, v in enumerate(visible):
                x = 26 + i
                if x >= max_x - 1:
                    break
                idx = int((v - mn) / rng * (n_bars - 1))
                idx = max(0, min(n_bars - 1, idx))
                try:
                    self.stdscr.addstr(base_y, x, bars[idx], color)
                except curses.error:
                    pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register protein folding mode methods on the App class."""
    App.PROTEIN_FOLDING_PRESETS = PROTEIN_FOLDING_PRESETS
    App._enter_protein_folding_mode = _enter_protein_folding_mode
    App._exit_protein_folding_mode = _exit_protein_folding_mode
    App._protfold_init = _protfold_init
    App._protfold_step = _protfold_step
    App._handle_protfold_menu_key = _handle_protfold_menu_key
    App._handle_protfold_key = _handle_protfold_key
    App._draw_protfold_menu = _draw_protfold_menu
    App._draw_protfold = _draw_protfold
