"""Mode: crispr — CRISPR-Cas9 Gene Editing & Repair simulation.

Models the molecular mechanics of CRISPR gene editing on a 2D DNA strand
visualization: guide RNA scanning along a double helix searching for PAM
sequences (NGG), Cas9 binding and R-loop formation, double-strand break (DSB)
cutting, competing DNA repair pathways (NHEJ error-prone rejoining with indel
mutations vs HDR template-directed precise repair), off-target cleavage at
partially-matching sites, base editing (nCas9 + deaminase, C→T without DSB),
prime editing (nCas9 + RT), and — at the population level — gene drive
propagation through a breeding population showing super-Mendelian inheritance
spreading an edited allele.

Three views:
  1) DNA strand map — double helix with base pairs, gRNA-Cas9 scanning,
     PAM highlights, cut sites, repair activity, edit annotations
  2) Population gene drive — 2D grid of diploid organisms colored by
     genotype, breeding with Mendelian/super-Mendelian inheritance
  3) Time-series sparkline graphs (cuts, repairs, indels, HDR success,
     off-target hits, edited fraction, drive allele freq, fitness, etc.)

Six presets:
  Precise Gene Knockout, HDR Knock-In, Off-Target Mutagenesis,
  Gene Drive Spread, Base Editing (nCas9), Prime Editing
"""
import curses
import math
import random

# ══════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════

_BASES = "ACGT"
_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
_PAM = "NGG"  # Cas9 PAM sequence (N = any base)

# Guide RNA length
_GUIDE_LEN = 20
# Minimum match score (out of _GUIDE_LEN) to attempt binding
_MIN_MATCH_ON = 18   # on-target threshold
_MIN_MATCH_OFF = 14  # off-target threshold

# Cas9 complex states
_CAS_SCANNING = 0
_CAS_PAM_FOUND = 1
_CAS_RLOOP = 2
_CAS_CUTTING = 3
_CAS_RELEASED = 4
_CAS_NICKASE = 5     # nCas9 — nicks one strand only
_CAS_BASE_EDIT = 6   # base editing — deaminase active
_CAS_PRIME_EDIT = 7  # prime editing — RT active

_CAS_STATE_NAMES = {
    _CAS_SCANNING: "scan", _CAS_PAM_FOUND: "PAM", _CAS_RLOOP: "R-loop",
    _CAS_CUTTING: "cut", _CAS_RELEASED: "done", _CAS_NICKASE: "nick",
    _CAS_BASE_EDIT: "base-ed", _CAS_PRIME_EDIT: "prime-ed",
}

# DSB repair states
_DSB_UNREPAIRED = 0
_DSB_NHEJ_ACTIVE = 1
_DSB_HDR_ACTIVE = 2
_DSB_REPAIRED_NHEJ = 3
_DSB_REPAIRED_HDR = 4
_DSB_NICK_ONLY = 5

# Repair timing (ticks)
_NHEJ_DURATION = 8
_HDR_DURATION = 18
_RLOOP_DURATION = 5
_CUT_DURATION = 3
_BASE_EDIT_DURATION = 6
_PRIME_EDIT_DURATION = 10

# Probabilities
_NHEJ_PROB = 0.70         # probability NHEJ wins over HDR
_NHEJ_INDEL_PROB = 0.85   # probability NHEJ introduces indel
_HDR_SUCCESS_PROB = 0.80   # probability HDR succeeds (vs aborted)
_OFF_TARGET_CUT_PROB = 0.4 # reduced efficiency at off-target sites
_SCAN_SPEED = 3            # bases per tick scanned

# Gene drive
_DRIVE_CONVERSION_PROB = 0.95  # probability heterozygote converts WT allele
_BREEDING_PROB = 0.06          # per organism per tick
_MUTATION_RATE = 0.005         # spontaneous resistance mutation
_FITNESS_COST = 0.02           # fitness cost of drive allele

# Organism genotypes
_GT_WT_WT = 0          # wild-type homozygote
_GT_WT_EDIT = 1        # heterozygote (one edited allele)
_GT_EDIT_EDIT = 2      # edited homozygote
_GT_WT_DISRUPTED = 3   # one disrupted (NHEJ indel) allele
_GT_DISRUPTED = 4      # homozygous disrupted
_GT_RESISTANT = 5      # drive-resistant (modified PAM)
_GT_EMPTY = 6          # empty grid cell

_GT_NAMES = {
    _GT_WT_WT: "WT/WT", _GT_WT_EDIT: "WT/Ed", _GT_EDIT_EDIT: "Ed/Ed",
    _GT_WT_DISRUPTED: "WT/Dis", _GT_DISRUPTED: "Dis/Dis",
    _GT_RESISTANT: "Resist", _GT_EMPTY: "",
}

_GT_CHARS = {
    _GT_WT_WT: "●●", _GT_WT_EDIT: "●○", _GT_EDIT_EDIT: "○○",
    _GT_WT_DISRUPTED: "●×", _GT_DISRUPTED: "××",
    _GT_RESISTANT: "▪▪", _GT_EMPTY: "  ",
}

# ══════════════════════════════════════════════════════════════════════
#  Presets
# ══════════════════════════════════════════════════════════════════════

CRISPR_PRESETS = [
    ("Precise Gene Knockout",
     "Single Cas9 targets one gene — NHEJ dominates, creates frameshift knockout",
     {"mode": "knockout", "num_cas9": 3, "hdr_template": False,
      "off_target_sites": 1, "nickase": False, "base_edit": False,
      "prime_edit": False, "gene_drive": False, "nhej_prob": 0.85,
      "scan_speed": 3, "guide_mismatches": 0}),

    ("HDR Knock-In",
     "Cas9 + HDR donor template — precise insertion of reporter gene at target locus",
     {"mode": "hdr", "num_cas9": 3, "hdr_template": True,
      "off_target_sites": 1, "nickase": False, "base_edit": False,
      "prime_edit": False, "gene_drive": False, "nhej_prob": 0.45,
      "scan_speed": 3, "guide_mismatches": 0}),

    ("Off-Target Mutagenesis",
     "Promiscuous guide RNA with multiple partial-match sites — collateral damage",
     {"mode": "offtarget", "num_cas9": 5, "hdr_template": False,
      "off_target_sites": 6, "nickase": False, "base_edit": False,
      "prime_edit": False, "gene_drive": False, "nhej_prob": 0.80,
      "scan_speed": 4, "guide_mismatches": 3}),

    ("Gene Drive Spread",
     "Super-Mendelian inheritance drives edited allele through breeding population",
     {"mode": "drive", "num_cas9": 2, "hdr_template": True,
      "off_target_sites": 1, "nickase": False, "base_edit": False,
      "prime_edit": False, "gene_drive": True, "nhej_prob": 0.15,
      "scan_speed": 3, "guide_mismatches": 0}),

    ("Base Editing (nCas9)",
     "Nickase Cas9 + cytidine deaminase — C→T conversion without double-strand break",
     {"mode": "base_edit", "num_cas9": 3, "hdr_template": False,
      "off_target_sites": 2, "nickase": True, "base_edit": True,
      "prime_edit": False, "gene_drive": False, "nhej_prob": 0.10,
      "scan_speed": 3, "guide_mismatches": 1}),

    ("Prime Editing",
     "nCas9-RT fusion — writes new sequence via pegRNA without DSB or donor template",
     {"mode": "prime_edit", "num_cas9": 3, "hdr_template": False,
      "off_target_sites": 1, "nickase": True, "base_edit": False,
      "prime_edit": True, "gene_drive": False, "nhej_prob": 0.05,
      "scan_speed": 2, "guide_mismatches": 0}),
]


# ══════════════════════════════════════════════════════════════════════
#  Data classes
# ══════════════════════════════════════════════════════════════════════

class _Cas9Complex:
    __slots__ = ('pos', 'state', 'timer', 'target_pos', 'match_score',
                 'is_nickase', 'is_base_editor', 'is_prime_editor',
                 'direction', 'bound')

    def __init__(self, pos, is_nickase=False, is_base_editor=False,
                 is_prime_editor=False):
        self.pos = pos
        self.state = _CAS_SCANNING
        self.timer = 0
        self.target_pos = -1
        self.match_score = 0
        self.is_nickase = is_nickase
        self.is_base_editor = is_base_editor
        self.is_prime_editor = is_prime_editor
        self.direction = random.choice([-1, 1])
        self.bound = False


class _DSBSite:
    __slots__ = ('pos', 'state', 'timer', 'repair_type', 'indel_size',
                 'hdr_success', 'is_off_target', 'nick_only')

    def __init__(self, pos, is_off_target=False, nick_only=False):
        self.pos = pos
        self.state = _DSB_NICK_ONLY if nick_only else _DSB_UNREPAIRED
        self.timer = 0
        self.repair_type = None
        self.indel_size = 0
        self.hdr_success = False
        self.is_off_target = is_off_target
        self.nick_only = nick_only


class _Edit:
    __slots__ = ('pos', 'edit_type', 'old_bases', 'new_bases', 'tick')

    def __init__(self, pos, edit_type, old_bases, new_bases, tick):
        self.pos = pos
        self.edit_type = edit_type  # 'nhej_indel', 'hdr', 'base_edit', 'prime_edit'
        self.old_bases = old_bases
        self.new_bases = new_bases
        self.tick = tick


# ══════════════════════════════════════════════════════════════════════
#  DNA sequence helpers
# ══════════════════════════════════════════════════════════════════════

def _random_seq(length):
    """Generate a random DNA sequence."""
    return [random.choice(_BASES) for _ in range(length)]


def _complement_seq(seq):
    """Return the complementary strand."""
    return [_COMPLEMENT[b] for b in seq]


def _find_pam_sites(seq):
    """Find all NGG PAM sites in the sequence (positions of the N)."""
    sites = []
    for i in range(len(seq) - 2):
        if seq[i + 1] == "G" and seq[i + 2] == "G":
            sites.append(i)
    return sites


def _match_score(guide, seq, pos):
    """Score how well a guide matches the sequence upstream of PAM at pos.
    Returns number of matching bases (0 to _GUIDE_LEN)."""
    start = pos - _GUIDE_LEN
    if start < 0:
        return 0
    matches = 0
    for i in range(_GUIDE_LEN):
        if start + i < len(seq) and guide[i] == seq[start + i]:
            matches += 1
    return matches


def _generate_guide_for_target(seq, target_pam_pos):
    """Generate a guide RNA that perfectly matches upstream of target PAM."""
    start = target_pam_pos - _GUIDE_LEN
    if start < 0:
        start = 0
    guide = seq[start:start + _GUIDE_LEN]
    while len(guide) < _GUIDE_LEN:
        guide.append(random.choice(_BASES))
    return guide


def _introduce_mismatches(guide, n_mismatches):
    """Introduce n random mismatches into the guide."""
    guide = list(guide)
    positions = random.sample(range(len(guide)), min(n_mismatches, len(guide)))
    for p in positions:
        others = [b for b in _BASES if b != guide[p]]
        guide[p] = random.choice(others)
    return guide


# ══════════════════════════════════════════════════════════════════════
#  Enter / Exit
# ══════════════════════════════════════════════════════════════════════

def _enter_crispr_mode(self):
    """Enter CRISPR mode — show preset menu."""
    self.crispr_menu = True
    self.crispr_menu_sel = 0
    self._flash("CRISPR-Cas9 Gene Editing & Repair — select scenario")


def _exit_crispr_mode(self):
    """Exit CRISPR mode."""
    self.crispr_mode = False
    self.crispr_menu = False
    self.crispr_running = False
    for attr in list(vars(self)):
        if attr.startswith('crispr_') and attr not in ('crispr_mode',):
            try:
                delattr(self, attr)
            except AttributeError:
                pass
    self._flash("CRISPR mode OFF")


# ══════════════════════════════════════════════════════════════════════
#  Initialization
# ══════════════════════════════════════════════════════════════════════

def _crispr_init(self, preset_idx: int):
    """Initialize the CRISPR simulation with the given preset."""
    name, _desc, settings = CRISPR_PRESETS[preset_idx]

    max_y, max_x = self.stdscr.getmaxyx()

    self.crispr_preset_name = name
    self.crispr_preset_idx = preset_idx
    self.crispr_generation = 0
    self.crispr_settings = dict(settings)
    self.crispr_view = "dna"  # dna | population | graphs
    self.crispr_menu = False
    self.crispr_running = True

    # ── DNA sequence ──
    dna_len = max(80, max_x - 10)
    self.crispr_dna_len = dna_len
    self.crispr_dna = _random_seq(dna_len)
    self.crispr_dna_comp = _complement_seq(self.crispr_dna)
    self.crispr_dna_original = list(self.crispr_dna)

    # Find all PAM sites
    all_pams = _find_pam_sites(self.crispr_dna)

    # Select on-target PAM (one with enough upstream space for guide)
    valid_pams = [p for p in all_pams if p >= _GUIDE_LEN]
    if not valid_pams:
        # Force a PAM site
        pos = _GUIDE_LEN + 5
        self.crispr_dna[pos + 1] = "G"
        self.crispr_dna[pos + 2] = "G"
        self.crispr_dna_comp = _complement_seq(self.crispr_dna)
        valid_pams = [pos]
        all_pams = _find_pam_sites(self.crispr_dna)

    self.crispr_target_pam = random.choice(valid_pams)

    # Generate guide RNA matching the target
    self.crispr_guide = _generate_guide_for_target(
        self.crispr_dna, self.crispr_target_pam)

    # Introduce mismatches for off-target preset
    if settings["guide_mismatches"] > 0:
        self.crispr_guide = _introduce_mismatches(
            self.crispr_guide, settings["guide_mismatches"])

    # Identify off-target sites (partial matches)
    self.crispr_off_targets = []
    n_off = settings["off_target_sites"]
    for pam_pos in all_pams:
        if pam_pos == self.crispr_target_pam:
            continue
        score = _match_score(self.crispr_guide, self.crispr_dna, pam_pos)
        if score >= _MIN_MATCH_OFF:
            self.crispr_off_targets.append((pam_pos, score))
    self.crispr_off_targets.sort(key=lambda x: x[1], reverse=True)
    self.crispr_off_targets = self.crispr_off_targets[:n_off]

    # Ensure we have enough off-target sites for the preset
    while len(self.crispr_off_targets) < n_off:
        # Create an off-target site by placing a PAM with partial match
        pos = random.randint(_GUIDE_LEN + 3, dna_len - 5)
        if pos == self.crispr_target_pam:
            continue
        if any(abs(pos - ot[0]) < 5 for ot in self.crispr_off_targets):
            continue
        self.crispr_dna[pos + 1] = "G"
        self.crispr_dna[pos + 2] = "G"
        # Copy some of the guide upstream with mismatches
        start = pos - _GUIDE_LEN
        if start >= 0:
            for i in range(_GUIDE_LEN):
                if start + i < dna_len:
                    if random.random() < 0.75:  # 75% match = ~15/20
                        self.crispr_dna[start + i] = self.crispr_guide[i]
            self.crispr_dna_comp = _complement_seq(self.crispr_dna)
            score = _match_score(self.crispr_guide, self.crispr_dna, pos)
            self.crispr_off_targets.append((pos, score))

    # ── Cas9 complexes ──
    self.crispr_cas9_list = []
    for _ in range(settings["num_cas9"]):
        start_pos = random.randint(0, dna_len - 1)
        c = _Cas9Complex(
            start_pos,
            is_nickase=settings.get("nickase", False),
            is_base_editor=settings.get("base_edit", False),
            is_prime_editor=settings.get("prime_edit", False),
        )
        self.crispr_cas9_list.append(c)

    # ── DSB sites and edits ──
    self.crispr_dsb_sites = []
    self.crispr_edits = []

    # ── HDR template ──
    self.crispr_hdr_template = settings.get("hdr_template", False)
    if self.crispr_hdr_template:
        # HDR template: modified sequence to insert at target
        tgt_start = max(0, self.crispr_target_pam - _GUIDE_LEN)
        self.crispr_hdr_seq = list(self.crispr_dna[tgt_start:tgt_start + _GUIDE_LEN])
        # Modify a few bases to represent the knock-in
        for i in range(min(6, len(self.crispr_hdr_seq))):
            idx = len(self.crispr_hdr_seq) // 2 - 3 + i
            if 0 <= idx < len(self.crispr_hdr_seq):
                others = [b for b in _BASES if b != self.crispr_hdr_seq[idx]]
                self.crispr_hdr_seq[idx] = random.choice(others)
    else:
        self.crispr_hdr_seq = None

    # ── Population grid for gene drive ──
    self.crispr_gene_drive = settings.get("gene_drive", False)
    if self.crispr_gene_drive:
        pop_rows = max(15, (max_y - 6) // 1)
        pop_cols = max(20, (max_x - 2) // 3)
    else:
        pop_rows = 10
        pop_cols = 15
    self.crispr_pop_rows = pop_rows
    self.crispr_pop_cols = pop_cols
    self.crispr_pop = [[_GT_EMPTY] * pop_cols for _ in range(pop_rows)]
    self.crispr_pop_fitness = [[1.0] * pop_cols for _ in range(pop_rows)]
    self.crispr_pop_age = [[0] * pop_cols for _ in range(pop_rows)]

    # Populate: mostly WT, seed a few edited for gene drive
    density = 0.70 if self.crispr_gene_drive else 0.50
    for r in range(pop_rows):
        for c in range(pop_cols):
            if random.random() < density:
                self.crispr_pop[r][c] = _GT_WT_WT
                self.crispr_pop_fitness[r][c] = 1.0
                self.crispr_pop_age[r][c] = random.randint(0, 20)

    if self.crispr_gene_drive:
        # Seed a few edited heterozygotes (gene drive carriers)
        n_seeds = max(3, int(pop_rows * pop_cols * density * 0.03))
        placed = 0
        attempts = 0
        while placed < n_seeds and attempts < 500:
            r = random.randint(0, pop_rows - 1)
            c = random.randint(0, pop_cols - 1)
            if self.crispr_pop[r][c] == _GT_WT_WT:
                self.crispr_pop[r][c] = _GT_WT_EDIT
                self.crispr_pop_fitness[r][c] = 1.0 - _FITNESS_COST
                placed += 1
            attempts += 1

    # ── Statistics ──
    self.crispr_stats = {
        "total_cuts": 0, "on_target_cuts": 0, "off_target_cuts": 0,
        "nhej_repairs": 0, "hdr_repairs": 0, "indels": 0,
        "base_edits": 0, "prime_edits": 0, "nicks": 0,
        "drive_conversions": 0, "resistance_mutations": 0,
    }

    # ── Time-series history ──
    self.crispr_history = {
        'total_cuts': [], 'on_target': [], 'off_target': [],
        'nhej_count': [], 'hdr_count': [], 'indel_count': [],
        'edit_fraction': [], 'drive_freq': [], 'wt_freq': [],
        'fitness_avg': [],
    }

    # ── Scroll offset for DNA view ──
    self.crispr_scroll = max(0, self.crispr_target_pam - max_x // 4)

    # ── Event log for display ──
    self.crispr_event_log = []


# ══════════════════════════════════════════════════════════════════════
#  Simulation step
# ══════════════════════════════════════════════════════════════════════

def _crispr_step(self):
    """Advance the CRISPR simulation by one tick."""
    gen = self.crispr_generation
    settings = self.crispr_settings
    dna = self.crispr_dna
    dna_len = self.crispr_dna_len
    guide = self.crispr_guide
    scan_speed = settings.get("scan_speed", _SCAN_SPEED)

    # ── Update Cas9 complexes ──
    for cas9 in self.crispr_cas9_list:
        if cas9.state == _CAS_SCANNING:
            # Move along DNA
            cas9.pos += cas9.direction * scan_speed
            if cas9.pos < 0:
                cas9.pos = 0
                cas9.direction = 1
            elif cas9.pos >= dna_len - 3:
                cas9.pos = dna_len - 4
                cas9.direction = -1

            # Check for PAM at current position range
            for offset in range(scan_speed + 1):
                check_pos = cas9.pos + offset * cas9.direction
                if check_pos < 0 or check_pos >= dna_len - 2:
                    continue
                # Check NGG PAM
                if dna[check_pos + 1] == "G" and dna[check_pos + 2] == "G":
                    score = _match_score(guide, dna, check_pos)
                    is_on_target = (check_pos == self.crispr_target_pam)

                    if is_on_target and score >= _MIN_MATCH_ON:
                        cas9.state = _CAS_PAM_FOUND
                        cas9.target_pos = check_pos
                        cas9.match_score = score
                        cas9.timer = 0
                        cas9.bound = True
                        break
                    elif not is_on_target and score >= _MIN_MATCH_OFF:
                        # Off-target binding (reduced probability)
                        if random.random() < _OFF_TARGET_CUT_PROB * (score / _GUIDE_LEN):
                            cas9.state = _CAS_PAM_FOUND
                            cas9.target_pos = check_pos
                            cas9.match_score = score
                            cas9.timer = 0
                            cas9.bound = True
                            break

            # Random direction change
            if random.random() < 0.05:
                cas9.direction *= -1

        elif cas9.state == _CAS_PAM_FOUND:
            cas9.timer += 1
            if cas9.timer >= 2:
                cas9.state = _CAS_RLOOP
                cas9.timer = 0

        elif cas9.state == _CAS_RLOOP:
            cas9.timer += 1
            if cas9.timer >= _RLOOP_DURATION:
                # Check if site already has a DSB
                already_cut = any(d.pos == cas9.target_pos
                                  for d in self.crispr_dsb_sites)
                if already_cut:
                    cas9.state = _CAS_RELEASED
                    cas9.timer = 0
                    cas9.bound = False
                    continue

                is_off = (cas9.target_pos != self.crispr_target_pam)

                if cas9.is_base_editor:
                    cas9.state = _CAS_BASE_EDIT
                    cas9.timer = 0
                elif cas9.is_prime_editor:
                    cas9.state = _CAS_PRIME_EDIT
                    cas9.timer = 0
                elif cas9.is_nickase and not cas9.is_base_editor and not cas9.is_prime_editor:
                    # Pure nickase — nick one strand
                    dsb = _DSBSite(cas9.target_pos, is_off_target=is_off,
                                   nick_only=True)
                    self.crispr_dsb_sites.append(dsb)
                    self.crispr_stats["nicks"] += 1
                    cas9.state = _CAS_RELEASED
                    cas9.timer = 0
                    cas9.bound = False
                    _add_event(self, gen, f"Nick at pos {cas9.target_pos}"
                               + (" (off-target)" if is_off else ""))
                else:
                    cas9.state = _CAS_CUTTING
                    cas9.timer = 0

        elif cas9.state == _CAS_CUTTING:
            cas9.timer += 1
            if cas9.timer >= _CUT_DURATION:
                is_off = (cas9.target_pos != self.crispr_target_pam)
                dsb = _DSBSite(cas9.target_pos, is_off_target=is_off)
                self.crispr_dsb_sites.append(dsb)
                self.crispr_stats["total_cuts"] += 1
                if is_off:
                    self.crispr_stats["off_target_cuts"] += 1
                    _add_event(self, gen,
                               f"DSB at {cas9.target_pos} OFF-TARGET "
                               f"(match {cas9.match_score}/{_GUIDE_LEN})")
                else:
                    self.crispr_stats["on_target_cuts"] += 1
                    _add_event(self, gen,
                               f"DSB at {cas9.target_pos} on-target")
                cas9.state = _CAS_RELEASED
                cas9.timer = 0
                cas9.bound = False

        elif cas9.state == _CAS_BASE_EDIT:
            cas9.timer += 1
            if cas9.timer >= _BASE_EDIT_DURATION:
                # C→T (or G→A on complement) in editing window (pos -4 to -8)
                edit_start = cas9.target_pos - 8
                edit_end = cas9.target_pos - 4
                old_bases = []
                new_bases = []
                edited = False
                for i in range(max(0, edit_start), min(dna_len, edit_end + 1)):
                    old_bases.append(dna[i])
                    if dna[i] == "C":
                        dna[i] = "T"
                        new_bases.append("T")
                        edited = True
                    else:
                        new_bases.append(dna[i])
                if edited:
                    self.crispr_dna_comp = _complement_seq(dna)
                    self.crispr_stats["base_edits"] += 1
                    edit = _Edit(edit_start, 'base_edit',
                                 ''.join(old_bases), ''.join(new_bases), gen)
                    self.crispr_edits.append(edit)
                    _add_event(self, gen,
                               f"Base edit C→T at {edit_start}-{edit_end}")
                # Also nick the non-edited strand
                is_off = (cas9.target_pos != self.crispr_target_pam)
                dsb = _DSBSite(cas9.target_pos, is_off_target=is_off,
                               nick_only=True)
                self.crispr_dsb_sites.append(dsb)
                cas9.state = _CAS_RELEASED
                cas9.timer = 0
                cas9.bound = False

        elif cas9.state == _CAS_PRIME_EDIT:
            cas9.timer += 1
            if cas9.timer >= _PRIME_EDIT_DURATION:
                # Prime editing: nick + RT writes new sequence
                edit_pos = max(0, cas9.target_pos - 5)
                edit_len = min(6, dna_len - edit_pos)
                old_bases = dna[edit_pos:edit_pos + edit_len]
                new_bases = []
                for i in range(edit_len):
                    if random.random() < 0.5:
                        others = [b for b in _BASES if b != old_bases[i]]
                        new_bases.append(random.choice(others))
                    else:
                        new_bases.append(old_bases[i])
                for i in range(edit_len):
                    dna[edit_pos + i] = new_bases[i]
                self.crispr_dna_comp = _complement_seq(dna)
                self.crispr_stats["prime_edits"] += 1
                edit = _Edit(edit_pos, 'prime_edit',
                             ''.join(old_bases), ''.join(new_bases), gen)
                self.crispr_edits.append(edit)
                _add_event(self, gen,
                           f"Prime edit at {edit_pos}: "
                           f"{''.join(old_bases)}→{''.join(new_bases)}")
                is_off = (cas9.target_pos != self.crispr_target_pam)
                dsb = _DSBSite(cas9.target_pos, is_off_target=is_off,
                               nick_only=True)
                self.crispr_dsb_sites.append(dsb)
                cas9.state = _CAS_RELEASED
                cas9.timer = 0
                cas9.bound = False

        elif cas9.state == _CAS_RELEASED:
            cas9.timer += 1
            if cas9.timer >= 10:
                # Respawn as scanning from random position
                cas9.state = _CAS_SCANNING
                cas9.pos = random.randint(0, dna_len - 1)
                cas9.timer = 0
                cas9.direction = random.choice([-1, 1])

    # ── Update DSB repair ──
    nhej_prob = settings.get("nhej_prob", _NHEJ_PROB)
    completed_dsbs = []
    for dsb in self.crispr_dsb_sites:
        if dsb.nick_only:
            dsb.timer += 1
            if dsb.timer >= 5:
                completed_dsbs.append(dsb)
            continue

        if dsb.state == _DSB_UNREPAIRED:
            dsb.timer += 1
            if dsb.timer >= 3:
                # Choose repair pathway
                if random.random() < nhej_prob or not self.crispr_hdr_template:
                    dsb.state = _DSB_NHEJ_ACTIVE
                    dsb.repair_type = "nhej"
                else:
                    dsb.state = _DSB_HDR_ACTIVE
                    dsb.repair_type = "hdr"
                dsb.timer = 0

        elif dsb.state == _DSB_NHEJ_ACTIVE:
            dsb.timer += 1
            if dsb.timer >= _NHEJ_DURATION:
                dsb.state = _DSB_REPAIRED_NHEJ
                self.crispr_stats["nhej_repairs"] += 1
                # Introduce indel?
                if random.random() < _NHEJ_INDEL_PROB:
                    indel_size = random.choice([-3, -2, -1, 1, 2, 3, -1, 1])
                    dsb.indel_size = indel_size
                    self.crispr_stats["indels"] += 1
                    # Modify DNA at cut site
                    cut_pos = dsb.pos
                    if indel_size > 0:
                        # Insertion
                        insert = [random.choice(_BASES) for _ in range(indel_size)]
                        old = dna[cut_pos] if cut_pos < dna_len else "?"
                        for ib in reversed(insert):
                            if cut_pos < dna_len:
                                dna[cut_pos] = ib
                        edit = _Edit(cut_pos, 'nhej_indel', old,
                                     ''.join(insert), gen)
                        self.crispr_edits.append(edit)
                    else:
                        # Deletion
                        del_start = max(0, cut_pos + indel_size)
                        old_bases = ''.join(dna[del_start:cut_pos + 1])
                        for i in range(del_start, min(cut_pos + 1, dna_len)):
                            dna[i] = "-"
                        edit = _Edit(del_start, 'nhej_indel',
                                     old_bases, "-" * abs(indel_size), gen)
                        self.crispr_edits.append(edit)
                    self.crispr_dna_comp = _complement_seq(
                        [b if b != "-" else "N" for b in dna])
                    _add_event(self, gen,
                               f"NHEJ repair at {dsb.pos} — "
                               f"indel {indel_size:+d}bp"
                               + (" (off-target)" if dsb.is_off_target else ""))
                else:
                    _add_event(self, gen,
                               f"NHEJ repair at {dsb.pos} — perfect rejoin")

        elif dsb.state == _DSB_HDR_ACTIVE:
            dsb.timer += 1
            if dsb.timer >= _HDR_DURATION:
                dsb.state = _DSB_REPAIRED_HDR
                self.crispr_stats["hdr_repairs"] += 1
                if random.random() < _HDR_SUCCESS_PROB and self.crispr_hdr_seq:
                    dsb.hdr_success = True
                    # Apply HDR template
                    tgt_start = max(0, dsb.pos - _GUIDE_LEN)
                    old_bases = ''.join(
                        dna[tgt_start:tgt_start + len(self.crispr_hdr_seq)])
                    for i, b in enumerate(self.crispr_hdr_seq):
                        if tgt_start + i < dna_len:
                            dna[tgt_start + i] = b
                    self.crispr_dna_comp = _complement_seq(dna)
                    edit = _Edit(tgt_start, 'hdr', old_bases,
                                 ''.join(self.crispr_hdr_seq), gen)
                    self.crispr_edits.append(edit)
                    _add_event(self, gen,
                               f"HDR repair at {dsb.pos} — "
                               f"template knock-in success")
                else:
                    _add_event(self, gen,
                               f"HDR repair at {dsb.pos} — template failed, "
                               f"precise rejoin")

        # Remove completed repairs after a while
        if dsb.state in (_DSB_REPAIRED_NHEJ, _DSB_REPAIRED_HDR):
            dsb.timer += 1
            if dsb.timer >= _NHEJ_DURATION + 15:
                completed_dsbs.append(dsb)

    for dsb in completed_dsbs:
        if dsb in self.crispr_dsb_sites:
            self.crispr_dsb_sites.remove(dsb)

    # ── Gene drive population dynamics ──
    if self.crispr_gene_drive:
        _update_population(self)

    # ── Record metrics ──
    h = self.crispr_history
    h['total_cuts'].append(self.crispr_stats['total_cuts'])
    h['on_target'].append(self.crispr_stats['on_target_cuts'])
    h['off_target'].append(self.crispr_stats['off_target_cuts'])
    h['nhej_count'].append(self.crispr_stats['nhej_repairs'])
    h['hdr_count'].append(self.crispr_stats['hdr_repairs'])
    h['indel_count'].append(self.crispr_stats['indels'])

    # Edit fraction: how many bases differ from original
    diffs = sum(1 for i in range(self.crispr_dna_len)
                if dna[i] != self.crispr_dna_original[i])
    h['edit_fraction'].append(diffs / max(1, self.crispr_dna_len))

    # Population frequencies
    if self.crispr_gene_drive:
        total = 0
        wt_count = 0
        edit_count = 0
        fit_sum = 0.0
        for r in range(self.crispr_pop_rows):
            for c in range(self.crispr_pop_cols):
                gt = self.crispr_pop[r][c]
                if gt != _GT_EMPTY:
                    total += 1
                    fit_sum += self.crispr_pop_fitness[r][c]
                    if gt == _GT_WT_WT:
                        wt_count += 1
                    elif gt in (_GT_WT_EDIT, _GT_EDIT_EDIT):
                        edit_count += 1
        total = max(1, total)
        h['drive_freq'].append(edit_count / total)
        h['wt_freq'].append(wt_count / total)
        h['fitness_avg'].append(fit_sum / total)
    else:
        h['drive_freq'].append(0)
        h['wt_freq'].append(1.0)
        h['fitness_avg'].append(1.0)

    self.crispr_generation += 1


def _add_event(self, tick, msg):
    """Add an event to the log (keep last 20)."""
    self.crispr_event_log.append((tick, msg))
    if len(self.crispr_event_log) > 20:
        self.crispr_event_log = self.crispr_event_log[-20:]


# ══════════════════════════════════════════════════════════════════════
#  Population dynamics (gene drive)
# ══════════════════════════════════════════════════════════════════════

_NBRS8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
           (0, 1), (1, -1), (1, 0), (1, 1)]


def _update_population(self):
    """Update the breeding population for gene drive spread."""
    rows = self.crispr_pop_rows
    cols = self.crispr_pop_cols
    pop = self.crispr_pop
    fitness = self.crispr_pop_fitness
    age = self.crispr_pop_age

    # Age organisms and die
    for r in range(rows):
        for c in range(cols):
            if pop[r][c] != _GT_EMPTY:
                age[r][c] += 1
                # Death probability increases with age
                death_prob = 0.002 + 0.001 * max(0, age[r][c] - 50)
                # Fitness-dependent death
                death_prob /= max(0.1, fitness[r][c])
                if random.random() < death_prob:
                    pop[r][c] = _GT_EMPTY
                    age[r][c] = 0

    # Breeding: each organism can breed with adjacent
    births = []
    for r in range(rows):
        for c in range(cols):
            if pop[r][c] == _GT_EMPTY:
                continue
            if random.random() > _BREEDING_PROB * fitness[r][c]:
                continue
            # Find empty neighbor for offspring
            empty_nbrs = []
            partner_nbrs = []
            for dr, dc in _NBRS8:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if pop[nr][nc] == _GT_EMPTY:
                        empty_nbrs.append((nr, nc))
                    elif pop[nr][nc] != _GT_EMPTY:
                        partner_nbrs.append((nr, nc))
            if not empty_nbrs or not partner_nbrs:
                continue
            pr, pc = random.choice(partner_nbrs)
            er, ec = random.choice(empty_nbrs)

            # Determine offspring genotype
            parent1_gt = pop[r][c]
            parent2_gt = pop[pr][pc]
            child_gt = _breed(parent1_gt, parent2_gt)

            # Gene drive: if heterozygote, drive converts WT → edited
            if child_gt == _GT_WT_EDIT:
                if random.random() < _DRIVE_CONVERSION_PROB:
                    child_gt = _GT_EDIT_EDIT
                    self.crispr_stats["drive_conversions"] += 1
                elif random.random() < _MUTATION_RATE:
                    child_gt = _GT_RESISTANT
                    self.crispr_stats["resistance_mutations"] += 1

            # Resistance mutation
            if child_gt == _GT_WT_WT and random.random() < _MUTATION_RATE * 0.1:
                child_gt = _GT_RESISTANT

            child_fitness = 1.0
            if child_gt in (_GT_WT_EDIT, _GT_EDIT_EDIT):
                child_fitness = 1.0 - _FITNESS_COST
            elif child_gt == _GT_DISRUPTED:
                child_fitness = 0.7
            elif child_gt == _GT_WT_DISRUPTED:
                child_fitness = 0.85

            births.append((er, ec, child_gt, child_fitness))

    for er, ec, gt, fit in births:
        if pop[er][ec] == _GT_EMPTY:
            pop[er][ec] = gt
            fitness[er][ec] = fit
            age[er][ec] = 0


def _breed(gt1, gt2):
    """Mendelian cross of two genotypes (simplified)."""
    alleles1 = _gt_to_alleles(gt1)
    alleles2 = _gt_to_alleles(gt2)
    a1 = random.choice(alleles1)
    a2 = random.choice(alleles2)
    return _alleles_to_gt(a1, a2)


def _gt_to_alleles(gt):
    """Convert genotype to list of two alleles ('wt', 'ed', 'dis', 'res')."""
    if gt == _GT_WT_WT:
        return ['wt', 'wt']
    elif gt == _GT_WT_EDIT:
        return ['wt', 'ed']
    elif gt == _GT_EDIT_EDIT:
        return ['ed', 'ed']
    elif gt == _GT_WT_DISRUPTED:
        return ['wt', 'dis']
    elif gt == _GT_DISRUPTED:
        return ['dis', 'dis']
    elif gt == _GT_RESISTANT:
        return ['res', 'res']
    return ['wt', 'wt']


def _alleles_to_gt(a1, a2):
    """Convert two alleles back to a genotype."""
    pair = tuple(sorted([a1, a2]))
    mapping = {
        ('wt', 'wt'): _GT_WT_WT,
        ('ed', 'wt'): _GT_WT_EDIT,
        ('ed', 'ed'): _GT_EDIT_EDIT,
        ('dis', 'wt'): _GT_WT_DISRUPTED,
        ('dis', 'dis'): _GT_DISRUPTED,
        ('dis', 'ed'): _GT_WT_DISRUPTED,
        ('res', 'res'): _GT_RESISTANT,
        ('res', 'wt'): _GT_RESISTANT,
        ('ed', 'res'): _GT_RESISTANT,
        ('dis', 'res'): _GT_RESISTANT,
    }
    return mapping.get(pair, _GT_WT_WT)


# ══════════════════════════════════════════════════════════════════════
#  Key handlers
# ══════════════════════════════════════════════════════════════════════

def _handle_crispr_menu_key(self, key):
    """Handle keys in the preset selection menu."""
    if key in ('w', 'KEY_UP'):
        self.crispr_menu_sel = (self.crispr_menu_sel - 1) % len(CRISPR_PRESETS)
    elif key in ('s', 'KEY_DOWN'):
        self.crispr_menu_sel = (self.crispr_menu_sel + 1) % len(CRISPR_PRESETS)
    elif key in ('\n', ' '):
        self._crispr_init(self.crispr_menu_sel)
    elif key in ('q', '\x1b'):
        self._exit_crispr_mode()


def _handle_crispr_key(self, key):
    """Handle keys while simulation is running."""
    if key == ' ':
        self.crispr_running = not self.crispr_running
    elif key == 'v':
        views = ['dna', 'population', 'graphs']
        idx = views.index(self.crispr_view)
        self.crispr_view = views[(idx + 1) % len(views)]
    elif key == 'r':
        self._crispr_init(self.crispr_preset_idx)
    elif key in ('q', '\x1b'):
        self._exit_crispr_mode()
    elif key == 'KEY_LEFT':
        self.crispr_scroll = max(0, self.crispr_scroll - 5)
    elif key == 'KEY_RIGHT':
        self.crispr_scroll = min(
            max(0, self.crispr_dna_len - 40),
            self.crispr_scroll + 5)


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Menu
# ══════════════════════════════════════════════════════════════════════

def _draw_crispr_menu(self, max_y, max_x):
    """Draw the preset selection menu."""
    try:
        self.stdscr.addstr(
            0, 0, " CRISPR-Cas9 Gene Editing & Repair "[:max_x - 1],
            curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    try:
        self.stdscr.addstr(
            1, 0, " Select a scenario:"[:max_x - 1],
            curses.color_pair(7))
    except curses.error:
        pass

    for i, (pname, desc, _settings) in enumerate(CRISPR_PRESETS):
        y = 3 + i * 2
        if y >= max_y - 2:
            break
        marker = "►" if i == self.crispr_menu_sel else " "
        line = f"{marker} {pname}"
        if i == self.crispr_menu_sel:
            attr = curses.color_pair(3) | curses.A_BOLD
        else:
            attr = curses.color_pair(7)
        try:
            self.stdscr.addstr(y, 1, line[:max_x - 2], attr)
        except curses.error:
            pass
        # Description on next line
        if y + 1 < max_y - 2:
            try:
                self.stdscr.addstr(y + 1, 4, desc[:max_x - 5],
                                   curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

    hint = " [↑/↓]=select [Enter]=start [q]=back"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — DNA strand view
# ══════════════════════════════════════════════════════════════════════

def _draw_crispr_dna(self, max_y, max_x):
    """Draw the DNA strand map with Cas9 complexes and repair sites."""
    dna = self.crispr_dna
    dna_comp = self.crispr_dna_comp
    dna_len = self.crispr_dna_len
    scroll = self.crispr_scroll
    gen = self.crispr_generation

    # Title
    try:
        title = f" CRISPR — {self.crispr_preset_name} — Gen {gen} "
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    # Visible window of DNA
    vis_width = max_x - 6
    vis_start = scroll
    vis_end = min(dna_len, vis_start + vis_width)

    # ── Row 1: Position ruler ──
    y_ruler = 2
    ruler = ""
    for i in range(vis_start, vis_end):
        if i % 10 == 0:
            s = str(i)
            ruler += s[0] if len(s) > 0 else " "
        elif i % 10 < len(str((i // 10) * 10)):
            s = str((i // 10) * 10)
            ruler += s[i % 10] if i % 10 < len(s) else " "
        else:
            ruler += " "
    try:
        self.stdscr.addstr(y_ruler, 4, ruler[:vis_width],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass

    # ── Build annotation layers ──
    # Target site highlight
    target_pam = self.crispr_target_pam
    guide_start = target_pam - _GUIDE_LEN

    # ── Row 2: Guide RNA (if aligned) ──
    y_guide = 3
    try:
        self.stdscr.addstr(y_guide, 0, "gRNA", curses.color_pair(4) | curses.A_DIM)
    except curses.error:
        pass
    for i in range(vis_start, vis_end):
        x = 4 + (i - vis_start)
        if x >= max_x - 1:
            break
        if guide_start <= i < guide_start + _GUIDE_LEN:
            gi = i - guide_start
            ch = self.crispr_guide[gi]
            # Color: green if matches, red if mismatch
            if i < dna_len and ch == dna[i]:
                cp = 2  # green
            else:
                cp = 1  # red
            try:
                self.stdscr.addstr(y_guide, x, ch, curses.color_pair(cp))
            except curses.error:
                pass
        elif target_pam <= i <= target_pam + 2:
            # PAM annotation
            pam_ch = "NGG"[i - target_pam]
            try:
                self.stdscr.addstr(y_guide, x, pam_ch,
                                   curses.color_pair(3) | curses.A_BOLD)
            except curses.error:
                pass

    # ── Row 3: Sense strand (5'→3') ──
    y_sense = 5
    try:
        self.stdscr.addstr(y_sense, 0, "5'", curses.color_pair(6))
    except curses.error:
        pass
    for i in range(vis_start, vis_end):
        x = 4 + (i - vis_start)
        if x >= max_x - 1:
            break
        base = dna[i]
        cp = _base_color(base)

        # Highlight edits
        is_edited = (base != self.crispr_dna_original[i])
        attr = curses.A_BOLD if is_edited else 0

        # Highlight target region
        if guide_start <= i < guide_start + _GUIDE_LEN:
            attr |= curses.A_UNDERLINE

        # Highlight PAM
        if target_pam <= i <= target_pam + 2:
            cp = 3
            attr |= curses.A_BOLD

        try:
            self.stdscr.addstr(y_sense, x, base, curses.color_pair(cp) | attr)
        except curses.error:
            pass

    try:
        self.stdscr.addstr(y_sense, min(max_x - 3, 4 + vis_end - vis_start + 1),
                           "3'", curses.color_pair(6))
    except curses.error:
        pass

    # ── Row 4: Base pair bonds ──
    y_bonds = 6
    for i in range(vis_start, vis_end):
        x = 4 + (i - vis_start)
        if x >= max_x - 1:
            break
        # Check for DSB at this position
        is_dsb = False
        dsb_state = None
        for dsb in self.crispr_dsb_sites:
            if abs(dsb.pos - i) <= 1 and not dsb.nick_only:
                is_dsb = True
                dsb_state = dsb.state
                break
        if is_dsb:
            if dsb_state == _DSB_UNREPAIRED:
                ch, cp = "✂", 1   # red scissors
            elif dsb_state == _DSB_NHEJ_ACTIVE:
                ch, cp = "⚡", 3   # yellow — NHEJ
            elif dsb_state == _DSB_HDR_ACTIVE:
                ch, cp = "⚙", 2   # green — HDR
            elif dsb_state == _DSB_REPAIRED_NHEJ:
                ch, cp = "▪", 3
            elif dsb_state == _DSB_REPAIRED_HDR:
                ch, cp = "▪", 2
            else:
                ch, cp = "│", 7
            try:
                self.stdscr.addstr(y_bonds, x, ch,
                                   curses.color_pair(cp) | curses.A_BOLD)
            except curses.error:
                pass
        else:
            # Normal hydrogen bond
            bond = "│" if dna[i] in ("A", "T") else "║"  # AT=2bonds, GC=3bonds
            try:
                self.stdscr.addstr(y_bonds, x, bond,
                                   curses.color_pair(7) | curses.A_DIM)
            except curses.error:
                pass

    # ── Row 5: Antisense strand (3'→5') ──
    y_anti = 7
    try:
        self.stdscr.addstr(y_anti, 0, "3'", curses.color_pair(6))
    except curses.error:
        pass
    for i in range(vis_start, vis_end):
        x = 4 + (i - vis_start)
        if x >= max_x - 1:
            break
        base = dna_comp[i] if i < len(dna_comp) else "N"
        cp = _base_color(base)
        is_edited = (dna[i] != self.crispr_dna_original[i])
        attr = curses.A_BOLD if is_edited else 0
        try:
            self.stdscr.addstr(y_anti, x, base, curses.color_pair(cp) | attr)
        except curses.error:
            pass
    try:
        self.stdscr.addstr(y_anti, min(max_x - 3, 4 + vis_end - vis_start + 1),
                           "5'", curses.color_pair(6))
    except curses.error:
        pass

    # ── Row 6: Cas9 positions ──
    y_cas9 = 9
    try:
        self.stdscr.addstr(y_cas9, 0, "Cas9", curses.color_pair(5) | curses.A_DIM)
    except curses.error:
        pass
    for cas9 in self.crispr_cas9_list:
        pos = cas9.target_pos if cas9.bound else cas9.pos
        if vis_start <= pos < vis_end:
            x = 4 + (pos - vis_start)
            if x >= max_x - 1:
                continue
            state_name = _CAS_STATE_NAMES.get(cas9.state, "?")
            if cas9.state == _CAS_SCANNING:
                ch, cp = "→" if cas9.direction > 0 else "←", 5
            elif cas9.state == _CAS_PAM_FOUND:
                ch, cp = "◆", 3
            elif cas9.state == _CAS_RLOOP:
                ch, cp = "◈", 4
            elif cas9.state == _CAS_CUTTING:
                ch, cp = "✂", 1
            elif cas9.state in (_CAS_BASE_EDIT, _CAS_PRIME_EDIT):
                ch, cp = "✎", 2
            elif cas9.state == _CAS_NICKASE:
                ch, cp = "╱", 4
            else:
                ch, cp = "·", 7
            try:
                self.stdscr.addstr(y_cas9, x, ch,
                                   curses.color_pair(cp) | curses.A_BOLD)
            except curses.error:
                pass

    # ── Off-target sites annotation ──
    y_off = 10
    try:
        self.stdscr.addstr(y_off, 0, "OT:", curses.color_pair(1) | curses.A_DIM)
    except curses.error:
        pass
    for ot_pos, ot_score in self.crispr_off_targets:
        if vis_start <= ot_pos < vis_end:
            x = 4 + (ot_pos - vis_start)
            if x < max_x - 1:
                try:
                    self.stdscr.addstr(y_off, x, "▼",
                                       curses.color_pair(1) | curses.A_BOLD)
                except curses.error:
                    pass

    # ── Edit annotations ──
    y_edits = 11
    if self.crispr_edits:
        try:
            self.stdscr.addstr(y_edits, 0, "Edit",
                               curses.color_pair(2) | curses.A_DIM)
        except curses.error:
            pass
        for edit in self.crispr_edits[-20:]:
            if vis_start <= edit.pos < vis_end:
                x = 4 + (edit.pos - vis_start)
                if x < max_x - 1:
                    if edit.edit_type == 'nhej_indel':
                        ch, cp = "×", 1
                    elif edit.edit_type == 'hdr':
                        ch, cp = "✓", 2
                    elif edit.edit_type == 'base_edit':
                        ch, cp = "β", 4
                    elif edit.edit_type == 'prime_edit':
                        ch, cp = "π", 5
                    else:
                        ch, cp = "?", 7
                    try:
                        self.stdscr.addstr(y_edits, x, ch,
                                           curses.color_pair(cp) | curses.A_BOLD)
                    except curses.error:
                        pass

    # ── Event log ──
    y_log = 13
    try:
        self.stdscr.addstr(y_log, 0, " Event Log ",
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass
    for ei, (tick, msg) in enumerate(reversed(self.crispr_event_log)):
        y = y_log + 1 + ei
        if y >= max_y - 3:
            break
        line = f"[{tick:4d}] {msg}"
        # Color based on event type
        if "OFF-TARGET" in msg or "off-target" in msg:
            cp = 1
        elif "HDR" in msg or "success" in msg:
            cp = 2
        elif "NHEJ" in msg or "indel" in msg:
            cp = 3
        elif "Base edit" in msg or "Prime edit" in msg:
            cp = 4
        else:
            cp = 7
        try:
            self.stdscr.addstr(y, 1, line[:max_x - 2],
                               curses.color_pair(cp) | curses.A_DIM)
        except curses.error:
            pass

    # ── Statistics bar ──
    stats = self.crispr_stats
    stat_line = (f" Cuts:{stats['total_cuts']} "
                 f"On:{stats['on_target_cuts']} "
                 f"Off:{stats['off_target_cuts']} "
                 f"NHEJ:{stats['nhej_repairs']} "
                 f"HDR:{stats['hdr_repairs']} "
                 f"Indels:{stats['indels']} ")
    if stats['base_edits']:
        stat_line += f"BaseEd:{stats['base_edits']} "
    if stats['prime_edits']:
        stat_line += f"PrimeEd:{stats['prime_edits']} "
    try:
        self.stdscr.addstr(max_y - 2, 0, stat_line[:max_x - 1],
                           curses.color_pair(6))
    except curses.error:
        pass

    # ── Controls hint ──
    hint = " [v]iew [←/→]scroll [Space]pause [r]eset [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass


def _base_color(base):
    """Return curses color pair for a DNA base."""
    if base == "A":
        return 2   # green
    elif base == "T":
        return 1   # red
    elif base == "C":
        return 4   # blue
    elif base == "G":
        return 3   # yellow
    else:
        return 7   # white


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Population / Gene Drive view
# ══════════════════════════════════════════════════════════════════════

def _draw_crispr_population(self, max_y, max_x):
    """Draw the population grid for gene drive visualization."""
    gen = self.crispr_generation

    # Title
    try:
        title = f" Gene Drive Population — Gen {gen} "
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    rows = self.crispr_pop_rows
    cols = self.crispr_pop_cols

    # Count genotypes
    counts = {gt: 0 for gt in range(7)}
    total = 0
    for r in range(rows):
        for c in range(cols):
            gt = self.crispr_pop[r][c]
            counts[gt] = counts.get(gt, 0) + 1
            if gt != _GT_EMPTY:
                total += 1

    # Legend
    y_legend = 1
    legend_items = [
        (_GT_WT_WT, "●● WT/WT", 7),
        (_GT_WT_EDIT, "●○ WT/Ed", 2),
        (_GT_EDIT_EDIT, "○○ Ed/Ed", 4),
        (_GT_WT_DISRUPTED, "●× WT/Dis", 3),
        (_GT_DISRUPTED, "×× Dis/Dis", 1),
        (_GT_RESISTANT, "▪▪ Resist", 5),
    ]
    x_leg = 0
    for gt, label, cp in legend_items:
        cnt = counts.get(gt, 0)
        s = f" {label}:{cnt} "
        if x_leg + len(s) >= max_x:
            break
        try:
            self.stdscr.addstr(y_legend, x_leg, s,
                               curses.color_pair(cp))
        except curses.error:
            pass
        x_leg += len(s)

    # Grid
    y_start = 3
    for r in range(rows):
        y = y_start + r
        if y >= max_y - 3:
            break
        for c in range(cols):
            x = 1 + c * 3
            if x + 2 >= max_x:
                break
            gt = self.crispr_pop[r][c]
            ch = _GT_CHARS.get(gt, "  ")
            if gt == _GT_WT_WT:
                cp = 7
            elif gt == _GT_WT_EDIT:
                cp = 2
            elif gt == _GT_EDIT_EDIT:
                cp = 4
            elif gt == _GT_WT_DISRUPTED:
                cp = 3
            elif gt == _GT_DISRUPTED:
                cp = 1
            elif gt == _GT_RESISTANT:
                cp = 5
            else:
                cp = 7
            try:
                self.stdscr.addstr(y, x, ch, curses.color_pair(cp))
            except curses.error:
                pass

    # Frequency bar at bottom
    total = max(1, total)
    wt_frac = counts.get(_GT_WT_WT, 0) / total
    ed_frac = (counts.get(_GT_WT_EDIT, 0) + counts.get(_GT_EDIT_EDIT, 0)) / total
    dis_frac = (counts.get(_GT_WT_DISRUPTED, 0) + counts.get(_GT_DISRUPTED, 0)) / total
    res_frac = counts.get(_GT_RESISTANT, 0) / total

    bar_w = max_x - 4
    bar_y = max_y - 3
    try:
        self.stdscr.addstr(bar_y, 0, "Freq", curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass

    x = 4
    # WT segment
    wt_w = int(wt_frac * bar_w)
    for i in range(wt_w):
        if x + i < max_x - 1:
            try:
                self.stdscr.addstr(bar_y, x + i, "█", curses.color_pair(7))
            except curses.error:
                pass
    x += wt_w
    # Edited segment
    ed_w = int(ed_frac * bar_w)
    for i in range(ed_w):
        if x + i < max_x - 1:
            try:
                self.stdscr.addstr(bar_y, x + i, "█", curses.color_pair(2))
            except curses.error:
                pass
    x += ed_w
    # Disrupted segment
    dis_w = int(dis_frac * bar_w)
    for i in range(dis_w):
        if x + i < max_x - 1:
            try:
                self.stdscr.addstr(bar_y, x + i, "█", curses.color_pair(1))
            except curses.error:
                pass
    x += dis_w
    # Resistant segment
    res_w = int(res_frac * bar_w)
    for i in range(res_w):
        if x + i < max_x - 1:
            try:
                self.stdscr.addstr(bar_y, x + i, "█", curses.color_pair(5))
            except curses.error:
                pass

    # Drive stats
    drive_stats = (f" Drive conversions: {self.crispr_stats['drive_conversions']} "
                   f"| Resistance: {self.crispr_stats['resistance_mutations']} "
                   f"| Edited allele freq: {ed_frac:.1%}")
    try:
        self.stdscr.addstr(max_y - 2, 0, drive_stats[:max_x - 1],
                           curses.color_pair(6))
    except curses.error:
        pass

    hint = " [v]iew [Space]pause [r]eset [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Sparkline graphs
# ══════════════════════════════════════════════════════════════════════

def _draw_crispr_graphs(self, max_y, max_x):
    """Draw time-series sparkline graphs."""
    gen = self.crispr_generation

    try:
        title = f" CRISPR Metrics — {self.crispr_preset_name} — Gen {gen} "
        self.stdscr.addstr(0, 0, title[:max_x - 1],
                           curses.color_pair(6) | curses.A_BOLD)
    except curses.error:
        pass

    hist = self.crispr_history
    graph_w = max(10, max_x - 30)

    labels = [
        ("Total Cuts",      'total_cuts',    1),
        ("On-Target",       'on_target',     2),
        ("Off-Target",      'off_target',    1),
        ("NHEJ Repairs",    'nhej_count',    3),
        ("HDR Repairs",     'hdr_count',     2),
        ("Indels",          'indel_count',   1),
        ("Edit Fraction",   'edit_fraction', 4),
        ("Drive Allele",    'drive_freq',    2),
        ("WT Frequency",    'wt_freq',       7),
        ("Avg Fitness",     'fitness_avg',   5),
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
                bar_idx = int((v - mn) / rng * (n_bars - 1))
                bar_idx = max(0, min(n_bars - 1, bar_idx))
                try:
                    self.stdscr.addstr(base_y, x, bars[bar_idx], color)
                except curses.error:
                    pass

    hint = " [v]iew [Space]pause [r]eset [q]uit"
    try:
        self.stdscr.addstr(max_y - 1, 2, hint[:max_x - 3],
                           curses.color_pair(7) | curses.A_DIM)
    except curses.error:
        pass


# ══════════════════════════════════════════════════════════════════════
#  Drawing — Main dispatch
# ══════════════════════════════════════════════════════════════════════

def _draw_crispr(self, max_y, max_x):
    """Route to the correct view."""
    if self.crispr_view == "dna":
        _draw_crispr_dna(self, max_y, max_x)
    elif self.crispr_view == "population":
        _draw_crispr_population(self, max_y, max_x)
    elif self.crispr_view == "graphs":
        _draw_crispr_graphs(self, max_y, max_x)


# ══════════════════════════════════════════════════════════════════════
#  Registration
# ══════════════════════════════════════════════════════════════════════

def register(App):
    """Register CRISPR mode methods on the App class."""
    App._enter_crispr_mode = _enter_crispr_mode
    App._exit_crispr_mode = _exit_crispr_mode
    App._crispr_init = _crispr_init
    App._crispr_step = _crispr_step
    App._handle_crispr_menu_key = _handle_crispr_menu_key
    App._handle_crispr_key = _handle_crispr_key
    App._draw_crispr_menu = _draw_crispr_menu
    App._draw_crispr = _draw_crispr
    App.CRISPR_PRESETS = CRISPR_PRESETS
