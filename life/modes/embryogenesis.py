"""Mode: embryogenesis — Embryogenesis & Gastrulation simulation.

Model the development of a multicellular organism from a single fertilized egg
through cleavage, blastula formation, gastrulation (invagination), and tissue
differentiation — all driven by morphogen gradients, cell-cell signaling, and
differential gene expression.

Three visualization views:
  1. Cross-section — cell types with morphogen overlay, cavity, germ layers
  2. Fate map — lineage/germ layer coloring with axis indicators
  3. Time-series graphs — cell count, differentiation, morphogen levels,
     cavity size, axis polarity sparklines
"""
import curses
import math
import random

# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

EMBRYO_PRESETS = [
    ("Normal Development",
     "Standard embryogenesis from zygote through gastrulation & neurulation",
     "normal"),
    ("Axis Duplication (Spemann Organizer)",
     "Transplanted organizer induces a secondary axis — conjoined twin embryo",
     "axis_dup"),
    ("Neural Tube Defect",
     "Reduced folate / BMP overexpression blocks neural plate folding",
     "ntd"),
    ("Morphogen Knockout",
     "Nodal signaling abolished — no mesoderm induction, failed gastrulation",
     "knockout"),
    ("Twinning Event",
     "Early blastomere separation produces monozygotic twins",
     "twinning"),
    ("Accelerated Gastrulation",
     "High morphogen production & fast cell cycles — rapid development",
     "fast"),
]

# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

# Cell fates / types
FATE_ZYGOTE      = 0
FATE_PLURIPOTENT = 1
FATE_ECTODERM    = 2
FATE_MESODERM    = 3
FATE_ENDODERM    = 4
FATE_NEURAL      = 5
FATE_NOTOCHORD   = 6
FATE_CAVITY      = 7   # blastocoel / archenteron lumen marker (not a real cell)

FATE_NAMES = {
    FATE_ZYGOTE: "Zygote", FATE_PLURIPOTENT: "Pluripotent",
    FATE_ECTODERM: "Ectoderm", FATE_MESODERM: "Mesoderm",
    FATE_ENDODERM: "Endoderm", FATE_NEURAL: "Neural",
    FATE_NOTOCHORD: "Notochord", FATE_CAVITY: "Cavity",
}

FATE_CHARS = {
    FATE_ZYGOTE: "@@", FATE_PLURIPOTENT: "\u25cf\u25cf",
    FATE_ECTODERM: "\u2593\u2593", FATE_MESODERM: "\u2592\u2592",
    FATE_ENDODERM: "\u2591\u2591", FATE_NEURAL: "NN",
    FATE_NOTOCHORD: "==", FATE_CAVITY: "  ",
}

# Morphogen indices
MORPH_BMP   = 0   # dorsal-ventral axis (high = ventral/epidermal)
MORPH_WNT   = 1   # anterior-posterior axis (high = posterior)
MORPH_NODAL = 2   # left-right axis & mesoderm/endoderm inducer
MORPH_NAMES = ["BMP", "Wnt", "Nodal"]

# Development stages
STAGE_ZYGOTE     = 0
STAGE_CLEAVAGE   = 1
STAGE_MORULA     = 2
STAGE_BLASTULA   = 3
STAGE_GASTRULA   = 4
STAGE_NEURULA    = 5
STAGE_NAMES = {
    STAGE_ZYGOTE: "Zygote", STAGE_CLEAVAGE: "Cleavage",
    STAGE_MORULA: "Morula", STAGE_BLASTULA: "Blastula",
    STAGE_GASTRULA: "Gastrula", STAGE_NEURULA: "Neurula",
}

# Views
VIEW_CROSS   = "cross"
VIEW_FATE    = "fate"
VIEW_GRAPH   = "graph"
VIEWS = [VIEW_CROSS, VIEW_FATE, VIEW_GRAPH]

_NBRS4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_NBRS8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
           (0, 1), (1, -1), (1, 0), (1, 1)]


# ══════════════════════════════════════════════════════════════════════
#  Embryo Cell
# ══════════════════════════════════════════════════════════════════════

class _Cell:
    __slots__ = ("r", "c", "fate", "lineage_id", "generation", "age",
                 "division_timer", "polarity_angle", "adhesion",
                 "bmp_internal", "wnt_internal", "nodal_internal",
                 "committed", "energy", "parent_id", "uid")

    def __init__(self, r, c, fate, uid, parent_id=0, generation=0):
        self.r = r
        self.c = c
        self.fate = fate
        self.lineage_id = uid   # original lineage
        self.generation = generation
        self.age = 0
        self.division_timer = 0.0
        self.polarity_angle = random.uniform(0, 2 * math.pi)
        self.adhesion = 1.0
        self.bmp_internal = 0.0
        self.wnt_internal = 0.0
        self.nodal_internal = 0.0
        self.committed = False
        self.energy = 1.0
        self.parent_id = parent_id
        self.uid = uid


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════

def _sparkline(values, width):
    if not values:
        return " " * width
    n = len(values)
    if n > width:
        step = n / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values[-width:]
    lo = min(sampled) if sampled else 0
    hi = max(sampled) if sampled else 1
    rng = hi - lo if hi > lo else 1
    blocks = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    out = []
    for v in sampled:
        idx = int((v - lo) / rng * 7.99)
        idx = max(0, min(7, idx))
        out.append(blocks[idx])
    return "".join(out).ljust(width)


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _dist(r1, c1, r2, c2):
    return math.sqrt((r1 - r2) ** 2 + (c1 - c2) ** 2)


def _diffuse_field(field, rows, cols, coeff, decay=0.0):
    """In-place diffusion + decay on a 2D float field."""
    buf = [[0.0] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            val = field[r][c]
            total = 0.0
            cnt = 0
            for dr, dc in _NBRS4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    total += field[nr][nc]
                    cnt += 1
            avg = total / cnt if cnt > 0 else val
            buf[r][c] = val + coeff * (avg - val) - decay * val
            if buf[r][c] < 0.001:
                buf[r][c] = 0.0
    for r in range(rows):
        for c in range(cols):
            field[r][c] = buf[r][c]


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_embryo_mode(self):
    self.embryo_mode = True
    self.embryo_menu = True
    self.embryo_menu_sel = 0


def _exit_embryo_mode(self):
    self.embryo_mode = False
    self.embryo_menu = False
    self.embryo_running = False
    for attr in list(vars(self)):
        if attr.startswith("embryo_") and attr != "embryo_mode":
            try:
                delattr(self, attr)
            except AttributeError:
                pass


# ══════════════════════════════════════════════════════════════════════
#  Preset parameters
# ══════════════════════════════════════════════════════════════════════

def _get_embryo_params(preset_id):
    defaults = {
        "division_rate": 0.04,        # base probability per tick
        "division_slowdown": 0.92,    # multiplier each generation
        "max_cells": 600,
        "morph_diffusion": 0.12,      # morphogen diffusion coefficient
        "morph_decay": 0.008,         # morphogen decay per tick
        "bmp_source_strength": 0.06,  # ventral BMP production
        "wnt_source_strength": 0.05,  # posterior Wnt production
        "nodal_source_strength": 0.05,# left/vegetal Nodal production
        "fate_bmp_threshold": 0.30,   # BMP level for ectoderm commitment
        "fate_nodal_threshold": 0.30, # Nodal level for mesoderm/endoderm
        "fate_nodal_high": 0.55,      # High Nodal → endoderm
        "neural_bmp_low": 0.12,       # Low BMP → neural induction
        "gastrulation_start": 80,     # tick when invagination begins
        "invagination_strength": 0.4, # cell movement toward blastopore
        "convergent_extension": 0.3,  # mediolateral intercalation strength
        "adhesion_same": 1.0,         # adhesion between same-type cells
        "adhesion_diff": 0.3,         # adhesion between different types
        "cavity_formation_tick": 40,  # when blastocoel starts forming
        "neurulation_start": 160,     # when neural plate folds
        "organizer_strength": 0.0,    # extra Nodal/anti-BMP from organizer
        "organizer2": False,          # second organizer for axis duplication
        "organizer2_pos": None,
        "nodal_enabled": True,        # can disable for knockout
        "bmp_multiplier": 1.0,        # for NTD: increased BMP
        "twinning": False,            # split at 2-cell stage
        "speed_mult": 1.0,            # time acceleration
    }
    overrides = {
        "normal": {},
        "axis_dup": {
            "organizer_strength": 0.08,
            "organizer2": True,
            "max_cells": 700,
        },
        "ntd": {
            "bmp_multiplier": 2.2,
            "neural_bmp_low": 0.05,   # harder to get low BMP for neural
        },
        "knockout": {
            "nodal_enabled": False,
            "nodal_source_strength": 0.0,
        },
        "twinning": {
            "twinning": True,
            "max_cells": 700,
        },
        "fast": {
            "division_rate": 0.07,
            "division_slowdown": 0.95,
            "speed_mult": 1.8,
            "morph_diffusion": 0.15,
            "bmp_source_strength": 0.08,
            "wnt_source_strength": 0.07,
            "nodal_source_strength": 0.07,
            "gastrulation_start": 50,
            "neurulation_start": 110,
            "cavity_formation_tick": 25,
        },
    }
    params = dict(defaults)
    if preset_id in overrides:
        params.update(overrides[preset_id])
    return params


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _embryo_init(self, preset_idx):
    name, desc, preset_id = EMBRYO_PRESETS[preset_idx]
    self.embryo_preset_name = name
    self.embryo_preset_id = preset_id
    self.embryo_preset_idx = preset_idx

    max_y, max_x = self.stdscr.getmaxyx()
    self.embryo_rows = max(20, max_y - 4)
    self.embryo_cols = max(30, (max_x - 1) // 2)

    self.embryo_generation = 0
    self.embryo_view = VIEW_CROSS
    self.embryo_running = False
    self.embryo_menu = False
    self.embryo_next_uid = 1
    self.embryo_morph_overlay = 0  # 0=none, 1=BMP, 2=Wnt, 3=Nodal

    params = _get_embryo_params(preset_id)
    self.embryo_params = params

    rows, cols = self.embryo_rows, self.embryo_cols

    # Morphogen fields (3 fields: BMP, Wnt, Nodal)
    self.embryo_bmp = [[0.0] * cols for _ in range(rows)]
    self.embryo_wnt = [[0.0] * cols for _ in range(rows)]
    self.embryo_nodal = [[0.0] * cols for _ in range(rows)]

    # Cell occupancy grid (-1 = empty, else cell index for fast lookup)
    self.embryo_grid = [[-1] * cols for _ in range(rows)]

    # Cavity grid (True = cavity space)
    self.embryo_cavity = [[False] * cols for _ in range(rows)]

    # Start with a single zygote at center
    cr, cc = rows // 2, cols // 2
    uid = self.embryo_next_uid
    self.embryo_next_uid += 1
    zygote = _Cell(cr, cc, FATE_ZYGOTE, uid)
    zygote.lineage_id = uid
    self.embryo_cells = [zygote]
    self.embryo_grid[cr][cc] = 0

    # Stage tracking
    self.embryo_stage = STAGE_ZYGOTE
    self.embryo_blastopore_r = cr + 6   # vegetal pole
    self.embryo_blastopore_c = cc
    self.embryo_organizer_r = cr + 5
    self.embryo_organizer_c = cc

    # Second organizer for axis duplication preset
    if params["organizer2"]:
        self.embryo_organizer2_r = cr - 2
        self.embryo_organizer2_c = cc + 6
    else:
        self.embryo_organizer2_r = None
        self.embryo_organizer2_c = None

    # Twinning: will split after first division
    self.embryo_twinning_done = False

    # History for sparkline graphs
    self.embryo_history = {
        "cell_count": [],
        "pluripotent": [],
        "ectoderm": [],
        "mesoderm": [],
        "endoderm": [],
        "neural": [],
        "avg_bmp": [],
        "avg_nodal": [],
        "cavity_size": [],
        "stage": [],
    }
    self.embryo_max_history = 300


# ══════════════════════════════════════════════════════════════════════
#  Development stage transitions
# ══════════════════════════════════════════════════════════════════════

def _update_stage(self):
    n = len(self.embryo_cells)
    gen = self.embryo_generation
    params = self.embryo_params

    if n <= 1:
        self.embryo_stage = STAGE_ZYGOTE
    elif n <= 8:
        self.embryo_stage = STAGE_CLEAVAGE
    elif n <= 32:
        self.embryo_stage = STAGE_MORULA
    elif gen < params["gastrulation_start"]:
        self.embryo_stage = STAGE_BLASTULA
    elif gen < params["neurulation_start"]:
        self.embryo_stage = STAGE_GASTRULA
    else:
        self.embryo_stage = STAGE_NEURULA


# ══════════════════════════════════════════════════════════════════════
#  Simulation step
# ══════════════════════════════════════════════════════════════════════

def _embryo_step(self):
    cells = self.embryo_cells
    grid = self.embryo_grid
    cavity = self.embryo_cavity
    rows, cols = self.embryo_rows, self.embryo_cols
    params = self.embryo_params
    gen = self.embryo_generation

    bmp_field = self.embryo_bmp
    wnt_field = self.embryo_wnt
    nodal_field = self.embryo_nodal

    # ── 0. Update stage ──
    _update_stage(self)
    stage = self.embryo_stage

    # ── 1. Morphogen secretion from source regions ──
    _secrete_morphogens(self, cells, bmp_field, wnt_field, nodal_field,
                        rows, cols, params, gen, stage)

    # ── 2. Morphogen diffusion & decay ──
    diff_coeff = params["morph_diffusion"]
    decay = params["morph_decay"]
    _diffuse_field(bmp_field, rows, cols, diff_coeff, decay)
    _diffuse_field(wnt_field, rows, cols, diff_coeff, decay)
    if params["nodal_enabled"]:
        _diffuse_field(nodal_field, rows, cols, diff_coeff, decay)

    # ── 3. Cell morphogen uptake & fate determination ──
    for cell in cells:
        if 0 <= cell.r < rows and 0 <= cell.c < cols:
            cell.bmp_internal = cell.bmp_internal * 0.9 + 0.1 * bmp_field[cell.r][cell.c]
            cell.wnt_internal = cell.wnt_internal * 0.9 + 0.1 * wnt_field[cell.r][cell.c]
            cell.nodal_internal = cell.nodal_internal * 0.9 + 0.1 * nodal_field[cell.r][cell.c]

    if stage >= STAGE_BLASTULA:
        _determine_fates(cells, params, stage)

    # ── 4. Cell division ──
    if len(cells) < params["max_cells"]:
        _cell_division(self, cells, grid, rows, cols, params, gen, stage)

    # ── 5. Cavity formation (blastocoel) ──
    if gen >= params["cavity_formation_tick"] and stage >= STAGE_BLASTULA:
        _form_cavity(self, cells, grid, cavity, rows, cols, gen, params)

    # ── 6. Gastrulation movements ──
    if stage >= STAGE_GASTRULA:
        _gastrulation_movements(self, cells, grid, cavity, rows, cols, params, gen)

    # ── 7. Neurulation (neural plate folding) ──
    if stage >= STAGE_NEURULA:
        _neurulation(self, cells, grid, rows, cols, params)

    # ── 8. Differential adhesion sorting (Steinberg) ──
    if stage >= STAGE_BLASTULA:
        _adhesion_sorting(cells, grid, rows, cols, params)

    # ── 9. Twinning event ──
    if params["twinning"] and not self.embryo_twinning_done and len(cells) >= 2:
        _do_twinning(self, cells, grid, rows, cols)
        self.embryo_twinning_done = True

    # ── 10. Rebuild occupancy grid ──
    _rebuild_grid(cells, grid, rows, cols)

    # ── 11. Age cells ──
    for cell in cells:
        cell.age += 1

    self.embryo_generation = gen + 1

    # ── 12. Record history ──
    _record_history(self, cells, bmp_field, nodal_field, cavity, rows, cols)


# ── Morphogen secretion ──

def _secrete_morphogens(self, cells, bmp_field, wnt_field, nodal_field,
                        rows, cols, params, gen, stage):
    # BMP: secreted from ventral cells (bottom half)
    # In early stages, gradient comes from vegetal pole region
    mid_r = rows // 2
    mid_c = cols // 2
    bmp_str = params["bmp_source_strength"] * params["bmp_multiplier"]
    wnt_str = params["wnt_source_strength"]
    nodal_str = params["nodal_source_strength"]

    for cell in cells:
        r, c = cell.r, cell.c
        if not (0 <= r < rows and 0 <= c < cols):
            continue

        # BMP: ventral/epidermal — stronger in lower hemisphere
        ventral_bias = (r - mid_r) / max(1, rows // 2)
        if ventral_bias > 0:
            bmp_field[r][c] = min(1.0, bmp_field[r][c] + bmp_str * ventral_bias)

        # Wnt: posterior gradient — stronger toward blastopore
        if stage >= STAGE_BLASTULA:
            bp_r, bp_c = self.embryo_blastopore_r, self.embryo_blastopore_c
            d = _dist(r, c, bp_r, bp_c)
            if d < 10:
                wnt_field[r][c] = min(1.0, wnt_field[r][c] + wnt_str / (1 + d * 0.3))

        # Nodal: from organizer region (dorsal lip)
        if params["nodal_enabled"] and stage >= STAGE_BLASTULA:
            org_r, org_c = self.embryo_organizer_r, self.embryo_organizer_c
            d = _dist(r, c, org_r, org_c)
            if d < 8:
                nodal_field[r][c] = min(1.0, nodal_field[r][c] + nodal_str / (1 + d * 0.25))

            # Organizer also antagonizes BMP (chordin/noggin analog)
            org_str = params["organizer_strength"]
            if org_str > 0 and d < 6:
                bmp_field[r][c] = max(0, bmp_field[r][c] - org_str / (1 + d * 0.3))

            # Second organizer for axis duplication
            if self.embryo_organizer2_r is not None:
                d2 = _dist(r, c, self.embryo_organizer2_r, self.embryo_organizer2_c)
                if d2 < 8:
                    nodal_field[r][c] = min(1.0, nodal_field[r][c] + nodal_str * 0.8 / (1 + d2 * 0.25))
                if d2 < 6 and org_str > 0:
                    bmp_field[r][c] = max(0, bmp_field[r][c] - org_str * 0.8 / (1 + d2 * 0.3))


# ── Cell fate determination (French Flag model) ──

def _determine_fates(cells, params, stage):
    bmp_thresh = params["fate_bmp_threshold"]
    nodal_thresh = params["fate_nodal_threshold"]
    nodal_high = params["fate_nodal_high"]
    neural_low = params["neural_bmp_low"]
    nodal_enabled = params["nodal_enabled"]

    for cell in cells:
        if cell.committed and cell.fate >= FATE_ECTODERM:
            # Already committed — only neural upgrade possible
            if stage >= STAGE_NEURULA and cell.fate == FATE_ECTODERM:
                if cell.bmp_internal < neural_low:
                    cell.fate = FATE_NEURAL
                    cell.committed = True
            continue

        if cell.fate == FATE_ZYGOTE:
            cell.fate = FATE_PLURIPOTENT

        # French Flag positional information via morphogen thresholds
        if nodal_enabled and cell.nodal_internal >= nodal_high:
            cell.fate = FATE_ENDODERM
            cell.committed = True
        elif nodal_enabled and cell.nodal_internal >= nodal_thresh:
            cell.fate = FATE_MESODERM
            cell.committed = True
            # High Wnt + mesoderm → notochord
            if cell.wnt_internal > 0.35 and cell.nodal_internal > nodal_thresh * 1.2:
                if random.random() < 0.15:
                    cell.fate = FATE_NOTOCHORD
        elif cell.bmp_internal >= bmp_thresh:
            cell.fate = FATE_ECTODERM
            cell.committed = True
        elif cell.bmp_internal < neural_low and stage >= STAGE_GASTRULA:
            cell.fate = FATE_NEURAL
            cell.committed = True


# ── Cell division ──

def _cell_division(self, cells, grid, rows, cols, params, gen, stage):
    new_cells = []
    div_rate = params["division_rate"] * params["speed_mult"]
    slowdown = params["division_slowdown"]

    # In early cleavage: rapid symmetric divisions
    if stage <= STAGE_CLEAVAGE:
        div_rate *= 3.0
    elif stage == STAGE_MORULA:
        div_rate *= 2.0

    for cell in cells:
        effective_rate = div_rate * (slowdown ** cell.generation)
        if effective_rate < 0.002:
            continue

        cell.division_timer += effective_rate
        if cell.division_timer < 1.0:
            continue
        cell.division_timer = 0.0

        if len(cells) + len(new_cells) >= params["max_cells"]:
            break

        # Find an empty neighbor for the daughter cell
        candidates = []
        for dr, dc in _NBRS8:
            nr, nc = cell.r + dr, cell.c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if grid[nr][nc] == -1 and not self.embryo_cavity[nr][nc]:
                    candidates.append((nr, nc))

        if not candidates:
            # Try 2-step away
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    if abs(dr) <= 1 and abs(dc) <= 1:
                        continue
                    nr, nc = cell.r + dr, cell.c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if grid[nr][nc] == -1 and not self.embryo_cavity[nr][nc]:
                            candidates.append((nr, nc))
            if not candidates:
                cell.division_timer = 0.5
                continue

        nr, nc = random.choice(candidates)
        uid = self.embryo_next_uid
        self.embryo_next_uid += 1
        daughter = _Cell(nr, nc, cell.fate, uid,
                         parent_id=cell.uid, generation=cell.generation + 1)
        daughter.lineage_id = cell.lineage_id
        daughter.bmp_internal = cell.bmp_internal * 0.8
        daughter.wnt_internal = cell.wnt_internal * 0.8
        daughter.nodal_internal = cell.nodal_internal * 0.8
        daughter.committed = cell.committed

        # Asymmetric division: daughter may get different morphogen exposure
        if stage >= STAGE_BLASTULA and random.random() < 0.3:
            daughter.committed = False
            daughter.bmp_internal *= 0.5
            daughter.nodal_internal *= 0.5

        new_cells.append(daughter)
        if 0 <= nr < rows and 0 <= nc < cols:
            grid[nr][nc] = len(cells) + len(new_cells) - 1

    cells.extend(new_cells)


# ── Cavity formation ──

def _form_cavity(self, cells, grid, cavity, rows, cols, gen, params):
    if len(cells) < 16:
        return

    # Find center of mass
    if not cells:
        return
    cr = sum(c.r for c in cells) / len(cells)
    cc = sum(c.c for c in cells) / len(cells)

    # Blastocoel forms in center of cell mass
    radius = min(4, max(1, int(math.sqrt(len(cells)) * 0.25)))
    if gen > params["gastrulation_start"]:
        radius = max(1, radius - 1)  # cavity shrinks during gastrulation

    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr * dr + dc * dc <= radius * radius:
                r, c = int(cr) + dr, int(cc) + dc
                if 0 <= r < rows and 0 <= c < cols:
                    if grid[r][c] == -1:
                        cavity[r][c] = True

    # During gastrulation, archenteron forms: invaginating pocket from blastopore
    if self.embryo_stage >= STAGE_GASTRULA:
        bp_r = self.embryo_blastopore_r
        bp_c = self.embryo_blastopore_c
        arch_depth = min(6, max(1, (gen - params["gastrulation_start"]) // 8))
        for i in range(1, arch_depth + 1):
            ar = bp_r - i
            for dc in range(-1, 2):
                ac = bp_c + dc
                if 0 <= ar < rows and 0 <= ac < cols:
                    if grid[ar][ac] == -1:
                        cavity[ar][ac] = True


# ── Gastrulation movements ──

def _gastrulation_movements(self, cells, grid, cavity, rows, cols, params, gen):
    bp_r = self.embryo_blastopore_r
    bp_c = self.embryo_blastopore_c
    inv_str = params["invagination_strength"]
    ce_str = params["convergent_extension"]

    for cell in cells:
        # Endoderm/mesoderm cells involute: move toward and through blastopore
        if cell.fate in (FATE_ENDODERM, FATE_MESODERM):
            dr = bp_r - cell.r
            dc = bp_c - cell.c
            d = math.sqrt(dr * dr + dc * dc) if (dr != 0 or dc != 0) else 1
            if d < 12:
                # Involute: move toward blastopore, then inward
                move_r = int(round(dr / d * inv_str))
                move_c = int(round(dc / d * inv_str))
                if d < 3:
                    # Past blastopore: move inward (upward in cross-section)
                    move_r = -1 if random.random() < inv_str else 0

                nr, nc = cell.r + move_r, cell.c + move_c
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr][nc] == -1:
                        grid[cell.r][cell.c] = -1
                        cell.r = nr
                        cell.c = nc

        # Convergent extension: mesoderm cells intercalate mediolaterally
        if cell.fate == FATE_MESODERM and random.random() < ce_str * 0.3:
            # Move toward midline (center column)
            mid_c = cols // 2
            dc = 1 if cell.c < mid_c else -1 if cell.c > mid_c else 0
            nc = cell.c + dc
            if 0 <= nc < cols and grid[cell.r][nc] == -1:
                grid[cell.r][cell.c] = -1
                cell.c = nc

        # Epiboly: ectoderm spreads to cover embryo
        if cell.fate == FATE_ECTODERM and random.random() < 0.15:
            # Move outward from center
            cr = sum(c.r for c in cells) / max(1, len(cells))
            cc_avg = sum(c.c for c in cells) / max(1, len(cells))
            dr = cell.r - cr
            dc = cell.c - cc_avg
            d = math.sqrt(dr * dr + dc * dc) if (dr or dc) else 1
            move_r = int(round(dr / d * 0.8))
            move_c = int(round(dc / d * 0.8))
            nr, nc = cell.r + move_r, cell.c + move_c
            if 0 <= nr < rows and 0 <= nc < cols:
                if grid[nr][nc] == -1:
                    grid[cell.r][cell.c] = -1
                    cell.r = nr
                    cell.c = nc


# ── Neurulation ──

def _neurulation(self, cells, grid, rows, cols, params):
    # Neural cells move toward dorsal midline and fold inward
    mid_c = cols // 2
    for cell in cells:
        if cell.fate != FATE_NEURAL:
            continue
        # Move toward midline
        if random.random() < 0.2:
            dc = 1 if cell.c < mid_c else -1 if cell.c > mid_c else 0
            nc = cell.c + dc
            if 0 <= nc < cols and grid[cell.r][nc] == -1:
                grid[cell.r][cell.c] = -1
                cell.c = nc
        # Fold inward (upward in cross-section view) once near midline
        if abs(cell.c - mid_c) <= 2 and random.random() < 0.1:
            nr = cell.r - 1
            if 0 <= nr < rows and grid[nr][cell.c] == -1:
                grid[cell.r][cell.c] = -1
                cell.r = nr


# ── Differential adhesion sorting ──

def _adhesion_sorting(cells, grid, rows, cols, params):
    """Steinberg differential adhesion — cells swap to maximize
    same-type neighbor contacts."""
    same_adh = params["adhesion_same"]
    diff_adh = params["adhesion_diff"]

    sample = random.sample(cells, min(40, len(cells)))
    for cell in sample:
        if random.random() > 0.25:
            continue

        # Calculate current adhesion score
        curr_score = _adhesion_score(cell, cells, grid, rows, cols, same_adh, diff_adh)

        # Try swapping with a random neighbor
        nbrs = []
        for dr, dc in _NBRS4:
            nr, nc = cell.r + dr, cell.c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                idx = grid[nr][nc]
                if idx >= 0 and idx < len(cells):
                    nbrs.append(cells[idx])

        if not nbrs:
            continue

        other = random.choice(nbrs)
        if other.fate == cell.fate:
            continue  # no benefit swapping same type

        # Score if swapped
        cell.r, other.r = other.r, cell.r
        cell.c, other.c = other.c, cell.c
        new_score = (_adhesion_score(cell, cells, grid, rows, cols, same_adh, diff_adh) +
                     _adhesion_score(other, cells, grid, rows, cols, same_adh, diff_adh))
        old_score = curr_score + _adhesion_score(other, cells, grid, rows, cols, same_adh, diff_adh)

        if new_score <= old_score:
            # Revert swap
            cell.r, other.r = other.r, cell.r
            cell.c, other.c = other.c, cell.c


def _adhesion_score(cell, cells, grid, rows, cols, same_adh, diff_adh):
    score = 0.0
    for dr, dc in _NBRS4:
        nr, nc = cell.r + dr, cell.c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            idx = grid[nr][nc]
            if idx >= 0 and idx < len(cells):
                if cells[idx].fate == cell.fate:
                    score += same_adh
                else:
                    score += diff_adh
    return score


# ── Twinning ──

def _do_twinning(self, cells, grid, rows, cols):
    """Separate 2-cell embryo into two isolated groups."""
    if len(cells) < 2:
        return
    # Move second cell far from first
    c0 = cells[0]
    c1 = cells[1]
    offset = max(8, cols // 4)
    new_c = c1.c + offset
    if new_c >= cols:
        new_c = c1.c - offset
    new_c = max(0, min(cols - 1, new_c))
    if grid[c1.r][new_c] == -1:
        grid[c1.r][c1.c] = -1
        c1.c = new_c
        c1.lineage_id = c1.uid  # new lineage


# ── Rebuild grid ──

def _rebuild_grid(cells, grid, rows, cols):
    for r in range(rows):
        for c in range(cols):
            grid[r][c] = -1
    for i, cell in enumerate(cells):
        if 0 <= cell.r < rows and 0 <= cell.c < cols:
            grid[cell.r][cell.c] = i


# ── Record history ──

def _record_history(self, cells, bmp_field, nodal_field, cavity, rows, cols):
    h = self.embryo_history
    mx = self.embryo_max_history

    n = len(cells)
    h["cell_count"].append(n)
    fate_counts = {FATE_PLURIPOTENT: 0, FATE_ECTODERM: 0, FATE_MESODERM: 0,
                   FATE_ENDODERM: 0, FATE_NEURAL: 0}
    for cell in cells:
        if cell.fate in fate_counts:
            fate_counts[cell.fate] += 1
    h["pluripotent"].append(fate_counts[FATE_PLURIPOTENT])
    h["ectoderm"].append(fate_counts[FATE_ECTODERM])
    h["mesoderm"].append(fate_counts[FATE_MESODERM])
    h["endoderm"].append(fate_counts[FATE_ENDODERM])
    h["neural"].append(fate_counts[FATE_NEURAL])

    # Average morphogen levels
    bmp_sum = sum(bmp_field[c.r][c.c] for c in cells if 0 <= c.r < rows and 0 <= c.c < cols)
    nodal_sum = sum(nodal_field[c.r][c.c] for c in cells if 0 <= c.r < rows and 0 <= c.c < cols)
    h["avg_bmp"].append(bmp_sum / max(1, n))
    h["avg_nodal"].append(nodal_sum / max(1, n))

    # Cavity size
    cav_count = sum(1 for r in range(rows) for c in range(cols) if cavity[r][c])
    h["cavity_size"].append(cav_count)

    # Stage as numeric
    h["stage"].append(self.embryo_stage)

    # Trim
    for k in h:
        if len(h[k]) > mx:
            h[k] = h[k][-mx:]


# ══════════════════════════════════════════════════════════════════════
#  Key handlers
# ══════════════════════════════════════════════════════════════════════

def _handle_embryo_menu_key(self, key):
    presets = EMBRYO_PRESETS
    if key == curses.KEY_DOWN or key == ord("j"):
        self.embryo_menu_sel = (self.embryo_menu_sel + 1) % len(presets)
    elif key == curses.KEY_UP or key == ord("k"):
        self.embryo_menu_sel = (self.embryo_menu_sel - 1) % len(presets)
    elif key in (10, 13, curses.KEY_ENTER):
        _embryo_init(self, self.embryo_menu_sel)
    elif key == ord("q") or key == 27:
        self.embryo_menu = False
        _exit_embryo_mode(self)
    return True


def _handle_embryo_key(self, key):
    if key == ord("q") or key == 27:
        _exit_embryo_mode(self)
        return True
    if key == ord(" "):
        self.embryo_running = not self.embryo_running
        return True
    if key == ord("n") or key == ord("."):
        _embryo_step(self)
        return True
    if key == ord("r"):
        _embryo_init(self, self.embryo_preset_idx)
        return True
    if key == ord("R") or key == ord("m"):
        self.embryo_running = False
        self.embryo_menu = True
        self.embryo_menu_sel = 0
        return True
    if key == ord("v"):
        idx = VIEWS.index(self.embryo_view) if self.embryo_view in VIEWS else 0
        self.embryo_view = VIEWS[(idx + 1) % len(VIEWS)]
        return True
    if key == ord("o"):
        # Cycle morphogen overlay: none -> BMP -> Wnt -> Nodal -> none
        self.embryo_morph_overlay = (self.embryo_morph_overlay + 1) % 4
        return True
    if key == ord("g"):
        # Force gastrulation (advance to gastrula stage timing)
        self.embryo_generation = max(self.embryo_generation,
                                     self.embryo_params["gastrulation_start"])
        return True
    return True


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Menu
# ══════════════════════════════════════════════════════════════════════

def _draw_embryo_menu(self, max_y, max_x):
    self.stdscr.erase()
    title = "\u2550\u2550 Embryogenesis & Gastrulation \u2550\u2550 Select Scenario \u2550\u2550"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    for i, (name, desc, _pid) in enumerate(EMBRYO_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        marker = "\u25b6" if i == self.embryo_menu_sel else " "
        attr = (curses.color_pair(3) | curses.A_BOLD
                if i == self.embryo_menu_sel else curses.color_pair(7))
        try:
            self.stdscr.addstr(y, 2, f" {marker} {name:40s}"[:max_x - 3], attr)
        except curses.error:
            pass
        desc_attr = (curses.color_pair(6) if i == self.embryo_menu_sel
                     else curses.color_pair(7) | curses.A_DIM)
        try:
            self.stdscr.addstr(y + 1, 6, desc[:max_x - 8], desc_attr)
        except curses.error:
            pass

    leg_y = 3 + len(EMBRYO_PRESETS) * 2 + 1
    legend = [
        "Cleavage:     Zygote \u2192 rapid mitosis \u2192 morula \u2192 hollow blastula",
        "Morphogens:   BMP (dorsal-ventral) + Wnt (anterior-posterior) + Nodal (mesoderm/endoderm)",
        "Gastrulation: Invagination forms 3 germ layers (ectoderm/mesoderm/endoderm)",
        "Neurulation:  Low BMP + organizer signals \u2192 neural plate folding \u2192 neural tube",
    ]
    for i, line in enumerate(legend):
        if leg_y + i < max_y - 2:
            try:
                self.stdscr.addstr(leg_y + i, 4, line[:max_x - 6],
                                   curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

    if max_y - 1 > 0:
        hint = " [j/k]=navigate  [Enter]=select  [q/Esc]=cancel"
        try:
            self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Cross-section view (View 1)
# ══════════════════════════════════════════════════════════════════════

def _draw_embryo_cross(self, max_y, max_x):
    grid = self.embryo_grid
    cavity = self.embryo_cavity
    cells = self.embryo_cells
    rows, cols = self.embryo_rows, self.embryo_cols
    overlay = self.embryo_morph_overlay

    # Color pairs for cell types
    fate_colors = {
        FATE_ZYGOTE: curses.color_pair(7) | curses.A_BOLD,
        FATE_PLURIPOTENT: curses.color_pair(7),
        FATE_ECTODERM: curses.color_pair(5) | curses.A_BOLD,     # cyan/blue
        FATE_MESODERM: curses.color_pair(2) | curses.A_BOLD,     # red
        FATE_ENDODERM: curses.color_pair(4) | curses.A_BOLD,     # yellow
        FATE_NEURAL: curses.color_pair(3) | curses.A_BOLD,       # green
        FATE_NOTOCHORD: curses.color_pair(6) | curses.A_BOLD,    # magenta
    }

    morph_fields = [None, self.embryo_bmp, self.embryo_wnt, self.embryo_nodal]
    morph_colors_hi = [None,
                       curses.color_pair(2),  # BMP = red
                       curses.color_pair(4),  # Wnt = yellow
                       curses.color_pair(5)]  # Nodal = cyan

    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, (max_x - 1) // 2)

    for vr in range(draw_rows):
        for vc in range(draw_cols):
            sx = vc * 2
            sy = vr + 2
            if sy >= max_y - 1 or sx + 1 >= max_x:
                continue

            idx = grid[vr][vc]
            if idx >= 0 and idx < len(cells):
                cell = cells[idx]
                ch = FATE_CHARS.get(cell.fate, "\u00b7\u00b7")
                attr = fate_colors.get(cell.fate, curses.color_pair(7))

                # Morphogen overlay tinting
                if overlay > 0 and morph_fields[overlay] is not None:
                    val = morph_fields[overlay][vr][vc]
                    if val > 0.2:
                        attr = morph_colors_hi[overlay]
                        if val > 0.5:
                            attr |= curses.A_BOLD
            elif cavity[vr][vc]:
                ch = "\u00b7 " if self.embryo_stage >= STAGE_GASTRULA else "  "
                attr = curses.color_pair(7) | curses.A_DIM
            else:
                # Empty — show morphogen if overlay active
                if overlay > 0 and morph_fields[overlay] is not None:
                    val = morph_fields[overlay][vr][vc]
                    if val > 0.05:
                        blocks = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587"
                        bi = int(val * 6.99)
                        bi = max(0, min(6, bi))
                        ch = blocks[bi] + blocks[bi]
                        attr = morph_colors_hi[overlay] | curses.A_DIM
                    else:
                        ch = "  "
                        attr = curses.color_pair(7)
                else:
                    ch = "  "
                    attr = curses.color_pair(7)

            try:
                self.stdscr.addstr(sy, sx, ch[:2], attr)
            except curses.error:
                pass

    # Axis labels
    if max_y > 4:
        try:
            self.stdscr.addstr(2, min(draw_cols * 2 + 1, max_x - 10),
                               " Dorsal", curses.color_pair(7) | curses.A_DIM)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(min(draw_rows, max_y - 3), min(draw_cols * 2 + 1, max_x - 10),
                               " Ventral", curses.color_pair(7) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Fate map view (View 2)
# ══════════════════════════════════════════════════════════════════════

def _draw_embryo_fate(self, max_y, max_x):
    cells = self.embryo_cells
    grid = self.embryo_grid
    cavity = self.embryo_cavity
    rows, cols = self.embryo_rows, self.embryo_cols

    # Color by lineage (hash lineage_id to color)
    lineage_colors = {}
    color_list = [1, 2, 3, 4, 5, 6]

    draw_rows = min(rows, max_y - 3)
    draw_cols = min(cols, (max_x - 1) // 2)

    # Left half: lineage coloring
    half_w = draw_cols // 2
    for vr in range(draw_rows):
        for vc in range(half_w):
            sx = vc * 2
            sy = vr + 2
            if sy >= max_y - 1 or sx + 1 >= max_x:
                continue

            idx = grid[vr][vc]
            if idx >= 0 and idx < len(cells):
                cell = cells[idx]
                lid = cell.lineage_id
                if lid not in lineage_colors:
                    lineage_colors[lid] = color_list[len(lineage_colors) % len(color_list)]
                cp = lineage_colors[lid]
                ch = "\u2588\u2588"
                attr = curses.color_pair(cp)
            elif cavity[vr][vc]:
                ch = "  "
                attr = curses.color_pair(7) | curses.A_DIM
            else:
                ch = "  "
                attr = curses.color_pair(7)

            try:
                self.stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    # Divider
    div_x = half_w * 2
    for vr in range(draw_rows):
        sy = vr + 2
        if sy < max_y - 1 and div_x < max_x:
            try:
                self.stdscr.addstr(sy, div_x, "\u2502", curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

    # Right half: germ layer coloring
    germ_colors = {
        FATE_ZYGOTE: curses.color_pair(7),
        FATE_PLURIPOTENT: curses.color_pair(7),
        FATE_ECTODERM: curses.color_pair(5) | curses.A_BOLD,
        FATE_MESODERM: curses.color_pair(2) | curses.A_BOLD,
        FATE_ENDODERM: curses.color_pair(4) | curses.A_BOLD,
        FATE_NEURAL: curses.color_pair(3) | curses.A_BOLD,
        FATE_NOTOCHORD: curses.color_pair(6) | curses.A_BOLD,
    }

    right_offset = div_x + 1
    for vr in range(draw_rows):
        for vc in range(half_w):
            sx = right_offset + vc * 2
            sy = vr + 2
            if sy >= max_y - 1 or sx + 1 >= max_x:
                continue

            idx = grid[vr][vc + half_w] if vc + half_w < cols else -1
            if idx >= 0 and idx < len(cells):
                cell = cells[idx]
                ch = "\u2588\u2588"
                attr = germ_colors.get(cell.fate, curses.color_pair(7))
            elif vc + half_w < cols and cavity[vr][vc + half_w]:
                ch = "  "
                attr = curses.color_pair(7) | curses.A_DIM
            else:
                ch = "  "
                attr = curses.color_pair(7)

            try:
                self.stdscr.addstr(sy, sx, ch, attr)
            except curses.error:
                pass

    # Labels
    try:
        self.stdscr.addstr(max_y - 2, 1, "Lineage", curses.color_pair(7) | curses.A_DIM)
        self.stdscr.addstr(max_y - 2, right_offset + 1, "Germ Layer", curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass

    # Germ layer legend
    leg_x = right_offset + 1
    leg_y = 2
    legend_items = [
        ("Ecto", curses.color_pair(5) | curses.A_BOLD),
        ("Meso", curses.color_pair(2) | curses.A_BOLD),
        ("Endo", curses.color_pair(4) | curses.A_BOLD),
        ("Neur", curses.color_pair(3) | curses.A_BOLD),
        ("Noto", curses.color_pair(6) | curses.A_BOLD),
    ]
    lx = min(max_x - 30, draw_cols * 2 + 2)
    if lx > 0:
        for i, (lbl, la) in enumerate(legend_items):
            ly = 2 + i
            if ly < max_y - 2 and lx + len(lbl) + 2 < max_x:
                try:
                    self.stdscr.addstr(ly, lx, f"\u2588 {lbl}", la)
                except curses.error:
                    pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Graph view (View 3)
# ══════════════════════════════════════════════════════════════════════

def _draw_embryo_graph(self, max_y, max_x):
    h = self.embryo_history
    if not h["cell_count"]:
        try:
            self.stdscr.addstr(3, 2, "No data yet — press Space to start",
                               curses.color_pair(7))
        except curses.error:
            pass
        return

    metrics = [
        ("Cell Count",   h["cell_count"],   curses.color_pair(7) | curses.A_BOLD),
        ("Pluripotent",  h["pluripotent"],   curses.color_pair(7)),
        ("Ectoderm",     h["ectoderm"],      curses.color_pair(5) | curses.A_BOLD),
        ("Mesoderm",     h["mesoderm"],       curses.color_pair(2) | curses.A_BOLD),
        ("Endoderm",     h["endoderm"],       curses.color_pair(4) | curses.A_BOLD),
        ("Neural",       h["neural"],         curses.color_pair(3) | curses.A_BOLD),
        ("Avg BMP",      h["avg_bmp"],        curses.color_pair(2)),
        ("Avg Nodal",    h["avg_nodal"],      curses.color_pair(5)),
        ("Cavity Size",  h["cavity_size"],    curses.color_pair(7) | curses.A_DIM),
        ("Dev Stage",    h["stage"],          curses.color_pair(6)),
    ]

    row = 2
    spark_w = max(10, min(60, max_x - 35))

    for label, values, color in metrics:
        if row >= max_y - 2:
            break
        spark = _sparkline(values, spark_w)
        try:
            self.stdscr.addstr(row, 2, f"{label:14s}", color)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(row, 17, spark[:spark_w], color)
        except curses.error:
            pass
        # Current value
        val = values[-1] if values else 0
        if isinstance(val, float):
            val_str = f"{val:.3f}"
        else:
            val_str = str(val)
        try:
            self.stdscr.addstr(row, min(max_x - 8, 17 + spark_w + 1),
                               val_str[:7], curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        row += 2


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Main dispatch
# ══════════════════════════════════════════════════════════════════════

def _draw_embryo(self, max_y, max_x):
    self.stdscr.erase()

    view = self.embryo_view
    h = self.embryo_history
    state = "RUN" if self.embryo_running else "PAUSED"

    n = len(self.embryo_cells)
    stage_name = STAGE_NAMES.get(self.embryo_stage, "?")
    morph_name = ["off", "BMP", "Wnt", "Nodal"][self.embryo_morph_overlay]

    # Title bar
    title = (f" {self.embryo_preset_name}  gen={self.embryo_generation}"
             f"  cells={n}  stage={stage_name}"
             f"  [{state}]  view={view}  morph={morph_name}")
    try:
        self.stdscr.addstr(0, 0, title[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    if view == VIEW_CROSS:
        _draw_embryo_cross(self, max_y, max_x)
    elif view == VIEW_FATE:
        _draw_embryo_fate(self, max_y, max_x)
    else:
        _draw_embryo_graph(self, max_y, max_x)

    # Help bar
    if max_y - 1 > 0:
        hint = " [Space]=play [n]=step [v]=view [o]=morph overlay [g]=gastrulate [r]=reset [R]=menu [q]=exit"
        try:
            self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    App.EMBRYO_PRESETS = EMBRYO_PRESETS
    App._enter_embryo_mode = _enter_embryo_mode
    App._exit_embryo_mode = _exit_embryo_mode
    App._embryo_init = _embryo_init
    App._embryo_step = _embryo_step
    App._handle_embryo_menu_key = _handle_embryo_menu_key
    App._handle_embryo_key = _handle_embryo_key
    App._draw_embryo_menu = _draw_embryo_menu
    App._draw_embryo = _draw_embryo
