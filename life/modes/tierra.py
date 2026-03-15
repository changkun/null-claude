"""Tierra-style Digital Organisms — self-replicating assembly programs in shared memory.

Inspired by Tom Ray's Tierra (1990), this simulates a "primordial soup" of tiny
programs that copy themselves into shared memory, mutate during replication, and
evolve parasitism, immunity, and symbiosis.  The ASCII visualization shows memory
as a colored grid where each organism's code occupies a contiguous block, with
real-time stats on species diversity, genome lengths, and population dynamics.

Presets
-------
1. Genesis          – single ancestor, low mutation
2. Cambrian Burst   – high mutation, rapid diversification
3. Arms Race        – moderate mutation, reaper favors large genomes
4. Parasite World   – tiny ancestor, high copy-error → parasites emerge fast
5. Symbiosis Lab    – two ancestor species seeded together
"""

import curses
import math
import random

# ── Instruction set (simplified Tierran opcodes) ──────────────────────────
# Each instruction is an integer 0-15
OP_NOP0   = 0   # template marker 0
OP_NOP1   = 1   # template marker 1
OP_FIND   = 2   # search for complement template ahead
OP_MOV_H  = 3   # move head to found address
OP_COPY   = 4   # copy instruction from read-head to write-head
OP_INC    = 5   # increment register
OP_DEC    = 6   # decrement register
OP_JMP    = 7   # jump to address in register
OP_JMPZ   = 8   # jump if register zero
OP_ALLOC  = 9   # allocate daughter cell
OP_SPLIT  = 10  # divide — daughter becomes independent
OP_PUSH   = 11  # push register onto stack
OP_POP    = 12  # pop stack into register
OP_SWAP   = 13  # swap registers
OP_CALL   = 14  # call subroutine
OP_RET    = 15  # return from subroutine

NUM_OPS = 16

OP_CHARS = "01FMCID><ASPRWLR"
OP_NAMES = [
    "nop0", "nop1", "find", "movH", "copy", "inc", "dec", "jmp",
    "jmpz", "alloc", "split", "push", "pop", "swap", "call", "ret",
]

# ── Ancestor genome (self-replicator, ~40 instructions) ──────────────────
# A minimal self-copier: find own start, find own end, allocate space,
# copy loop, then split.
ANCESTOR_GENOME = [
    OP_NOP1, OP_NOP1, OP_NOP1, OP_NOP1,   # start template 1111
    OP_ALLOC,                                # allocate daughter
    OP_PUSH,                                 # save alloc address
    OP_FIND,                                 # find end template
    OP_NOP0, OP_NOP0, OP_NOP0, OP_NOP1,     # complement of end (0001)
    OP_MOV_H,                                # set read limit
    OP_POP,                                  # restore daughter addr
    # ── copy loop ──
    OP_NOP0, OP_NOP0, OP_NOP1, OP_NOP0,     # loop template 0010
    OP_COPY,                                 # copy one instruction
    OP_INC,                                  # advance read head
    OP_INC,                                  # advance write head
    OP_DEC,                                  # decrement counter
    OP_JMPZ,                                 # if done → skip to split
    OP_NOP0, OP_NOP1, OP_NOP0, OP_NOP0,     # complement of loop
    OP_JMP,                                  # else jump back to loop
    OP_NOP0, OP_NOP0, OP_NOP1, OP_NOP0,     # complement = loop label
    # ── divide ──
    OP_SPLIT,                                # create new organism
    OP_JMP,                                  # jump back to start
    OP_NOP1, OP_NOP1, OP_NOP1, OP_NOP1,     # complement of start
    # ── end template ──
    OP_NOP1, OP_NOP1, OP_NOP0, OP_NOP0,     # end template 1100
    OP_RET,                                  # (sentinel)
]

SMALL_ANCESTOR = [
    OP_NOP1, OP_NOP1, OP_NOP0,
    OP_ALLOC,
    OP_FIND, OP_NOP0, OP_NOP1,
    OP_MOV_H,
    OP_NOP0, OP_NOP0, OP_NOP1,  # copy loop label
    OP_COPY, OP_INC, OP_DEC,
    OP_JMPZ, OP_NOP1, OP_NOP0,
    OP_JMP, OP_NOP0, OP_NOP0, OP_NOP1,
    OP_SPLIT,
    OP_JMP, OP_NOP1, OP_NOP1, OP_NOP0,
    OP_NOP0, OP_NOP1, OP_NOP1,
    OP_RET,
]

# ── Presets ───────────────────────────────────────────────────────────────
TIERRA_PRESETS = [
    ("Genesis", "Single ancestor, low mutation — watch self-replicators fill memory",
     {"mutation_rate": 0.002, "cosmic_ray_rate": 0.0001,
      "reaper_bias": "oldest", "ancestors": "single",
      "mem_size": 4096, "max_organisms": 300, "slice_size": 20}),
    ("Cambrian Burst", "High mutation — rapid diversification and speciation",
     {"mutation_rate": 0.015, "cosmic_ray_rate": 0.001,
      "reaper_bias": "oldest", "ancestors": "single",
      "mem_size": 4096, "max_organisms": 300, "slice_size": 20}),
    ("Arms Race", "Moderate mutation, reaper favors large genomes — size pressure",
     {"mutation_rate": 0.005, "cosmic_ray_rate": 0.0005,
      "reaper_bias": "large_first", "ancestors": "single",
      "mem_size": 6144, "max_organisms": 400, "slice_size": 30}),
    ("Parasite World", "Tiny ancestor + high copy-error → parasites emerge fast",
     {"mutation_rate": 0.010, "cosmic_ray_rate": 0.0005,
      "reaper_bias": "oldest", "ancestors": "small",
      "mem_size": 3072, "max_organisms": 400, "slice_size": 15}),
    ("Symbiosis Lab", "Two ancestor species seeded together — cooperation or war?",
     {"mutation_rate": 0.005, "cosmic_ray_rate": 0.0003,
      "reaper_bias": "errors_first", "ancestors": "dual",
      "mem_size": 4096, "max_organisms": 350, "slice_size": 20}),
]

# ── Color palette for species (by genome hash) ───────────────────────────
_SPECIES_COLORS = [
    curses.COLOR_GREEN, curses.COLOR_CYAN, curses.COLOR_YELLOW,
    curses.COLOR_MAGENTA, curses.COLOR_RED, curses.COLOR_BLUE,
    curses.COLOR_WHITE,
]

# ── Organism class ────────────────────────────────────────────────────────
class Organism:
    __slots__ = (
        "genome", "ip", "rh", "wh", "regs", "stack", "mem_start",
        "mem_len", "daughter_start", "daughter_len", "age", "errors",
        "species_id", "executed", "alive",
    )

    def __init__(self, genome, mem_start, mem_len):
        self.genome = genome
        self.ip = 0
        self.rh = 0          # read head (offset into genome)
        self.wh = 0          # write head (absolute address)
        self.regs = [0, 0]   # two registers
        self.stack = []
        self.mem_start = mem_start
        self.mem_len = mem_len
        self.daughter_start = -1
        self.daughter_len = 0
        self.age = 0
        self.errors = 0
        self.species_id = _genome_hash(genome)
        self.executed = 0
        self.alive = True


def _genome_hash(genome):
    """Simple hash for species identification."""
    h = 0
    for i, op in enumerate(genome):
        h = (h * 31 + op + i) & 0xFFFFFFFF
    return h


# ── Virtual machine: execute one instruction slice ────────────────────────
def _execute_slice(org, memory, mem_size, mutation_rate, slice_size):
    """Execute up to `slice_size` instructions for one organism."""
    for _ in range(slice_size):
        if not org.alive:
            return
        if org.ip < 0 or org.ip >= org.mem_len:
            org.errors += 1
            org.ip = 0
            continue

        op = memory[(org.mem_start + org.ip) % mem_size]
        org.ip += 1
        org.executed += 1
        org.age += 1

        if op == OP_NOP0 or op == OP_NOP1:
            pass  # template markers — no-op during execution

        elif op == OP_FIND:
            # Collect template (sequence of NOP0/NOP1 after this instruction)
            tmpl = []
            pos = org.ip
            while pos < org.mem_len:
                t = memory[(org.mem_start + pos) % mem_size]
                if t == OP_NOP0 or t == OP_NOP1:
                    tmpl.append(t)
                    pos += 1
                else:
                    break
            if not tmpl:
                org.errors += 1
                continue
            org.ip = pos  # skip past template
            # Search forward for complement
            complement = [1 - t for t in tmpl]
            found = False
            for offset in range(1, org.mem_len):
                idx = (org.mem_start + pos + offset) % mem_size
                match = True
                for k, c in enumerate(complement):
                    if memory[(idx + k) % mem_size] != c:
                        match = False
                        break
                if match:
                    org.regs[0] = (pos + offset) % org.mem_len
                    found = True
                    break
            if not found:
                org.errors += 1

        elif op == OP_MOV_H:
            org.rh = org.regs[0]

        elif op == OP_COPY:
            if org.daughter_start >= 0 and org.wh < org.daughter_len:
                src = memory[(org.mem_start + org.rh) % mem_size]
                # Mutation during copy
                if random.random() < mutation_rate:
                    src = random.randint(0, NUM_OPS - 1)
                memory[(org.daughter_start + org.wh) % mem_size] = src
                org.rh += 1
                org.wh += 1
            else:
                org.errors += 1

        elif op == OP_INC:
            org.regs[0] = (org.regs[0] + 1) & 0xFFFF

        elif op == OP_DEC:
            org.regs[0] = (org.regs[0] - 1) & 0xFFFF

        elif op == OP_JMP:
            # Jump to template complement
            tmpl = []
            pos = org.ip
            while pos < org.mem_len:
                t = memory[(org.mem_start + pos) % mem_size]
                if t == OP_NOP0 or t == OP_NOP1:
                    tmpl.append(t)
                    pos += 1
                else:
                    break
            if tmpl:
                complement = [1 - t for t in tmpl]
                for offset in range(org.mem_len):
                    idx = org.mem_start + offset
                    match = True
                    for k, c in enumerate(complement):
                        if memory[(idx + k) % mem_size] != c:
                            match = False
                            break
                    if match:
                        org.ip = offset
                        break
            else:
                org.ip = org.regs[0] % org.mem_len

        elif op == OP_JMPZ:
            # Read template for target, jump if counter is zero
            tmpl = []
            pos = org.ip
            while pos < org.mem_len:
                t = memory[(org.mem_start + pos) % mem_size]
                if t == OP_NOP0 or t == OP_NOP1:
                    tmpl.append(t)
                    pos += 1
                else:
                    break
            org.ip = pos
            if org.regs[0] == 0:
                if tmpl:
                    complement = [1 - t for t in tmpl]
                    for offset in range(org.mem_len):
                        idx = org.mem_start + offset
                        match = True
                        for k, c in enumerate(complement):
                            if memory[(idx + k) % mem_size] != c:
                                match = False
                                break
                        if match:
                            org.ip = offset
                            break

        elif op == OP_ALLOC:
            # Request allocation — sets daughter start/len
            desired = org.mem_len
            org.regs[0] = desired  # set counter for copy loop
            # Actual allocation deferred to the soup manager
            org.daughter_len = desired

        elif op == OP_SPLIT:
            pass  # Handled by soup manager after slice

        elif op == OP_PUSH:
            if len(org.stack) < 8:
                org.stack.append(org.regs[0])

        elif op == OP_POP:
            if org.stack:
                org.regs[0] = org.stack.pop()
            else:
                org.errors += 1

        elif op == OP_SWAP:
            org.regs[0], org.regs[1] = org.regs[1], org.regs[0]

        elif op == OP_CALL:
            if len(org.stack) < 8:
                org.stack.append(org.ip)
            org.ip = org.regs[0] % org.mem_len

        elif op == OP_RET:
            if org.stack:
                org.ip = org.stack.pop() % org.mem_len
            else:
                org.ip = 0


# ── Soup manager functions ────────────────────────────────────────────────

def _init_soup(settings):
    """Initialize the primordial soup."""
    mem_size = settings["mem_size"]
    memory = [random.randint(0, NUM_OPS - 1) for _ in range(mem_size)]
    organisms = []
    owner = [-1] * mem_size  # which organism index owns each cell

    ancestor = ANCESTOR_GENOME if settings["ancestors"] != "small" else SMALL_ANCESTOR
    genome = list(ancestor)
    start = 0

    # Place first ancestor
    for i, op in enumerate(genome):
        memory[start + i] = op

    org = Organism(genome, start, len(genome))
    organisms.append(org)
    for i in range(len(genome)):
        owner[start + i] = 0

    if settings["ancestors"] == "dual":
        # Place second ancestor (slightly different)
        genome2 = list(SMALL_ANCESTOR)
        start2 = mem_size // 2
        for i, op in enumerate(genome2):
            memory[start2 + i] = op
        org2 = Organism(genome2, start2, len(genome2))
        organisms.append(org2)
        for i in range(len(genome2)):
            owner[start2 + i] = 1

    return {
        "memory": memory,
        "mem_size": mem_size,
        "organisms": organisms,
        "owner": owner,
        "generation": 0,
        "births": 0,
        "deaths": 0,
        "species_counts": {},
        "max_organisms": settings["max_organisms"],
        "mutation_rate": settings["mutation_rate"],
        "cosmic_ray_rate": settings["cosmic_ray_rate"],
        "reaper_bias": settings["reaper_bias"],
        "slice_size": settings["slice_size"],
        "history": [],  # population snapshots
        "speed": 1,
    }


def _find_free_block(owner, mem_size, length):
    """Find a contiguous free block in memory."""
    # Try random positions first
    for _ in range(50):
        start = random.randint(0, mem_size - 1)
        ok = True
        for i in range(length):
            if owner[(start + i) % mem_size] != -1:
                ok = False
                break
        if ok:
            return start
    # Linear scan fallback
    run = 0
    best_start = -1
    for i in range(mem_size * 2):
        idx = i % mem_size
        if owner[idx] == -1:
            run += 1
            if run >= length:
                best_start = (idx - length + 1) % mem_size
                return best_start
        else:
            run = 0
    return -1


def _reap(soup):
    """Kill an organism to make room (reaper queue)."""
    organisms = soup["organisms"]
    if not organisms:
        return
    bias = soup["reaper_bias"]
    if bias == "oldest":
        # Kill oldest
        idx = 0
        best_age = organisms[0].age
        for i, o in enumerate(organisms):
            if o.age > best_age:
                best_age = o.age
                idx = i
    elif bias == "large_first":
        # Kill largest genome
        idx = 0
        best = organisms[0].mem_len
        for i, o in enumerate(organisms):
            if o.mem_len > best:
                best = o.mem_len
                idx = i
    elif bias == "errors_first":
        # Kill most error-prone
        idx = 0
        best = organisms[0].errors
        for i, o in enumerate(organisms):
            if o.errors > best:
                best = o.errors
                idx = i
    else:
        idx = 0

    _kill_organism(soup, idx)


def _kill_organism(soup, idx):
    """Remove organism at index idx."""
    org = soup["organisms"][idx]
    owner = soup["owner"]
    mem_size = soup["mem_size"]
    # Free memory
    for i in range(org.mem_len):
        addr = (org.mem_start + i) % mem_size
        if owner[addr] == idx:
            owner[addr] = -1
    # Also free daughter memory if allocated
    if org.daughter_start >= 0:
        for i in range(org.daughter_len):
            addr = (org.daughter_start + i) % mem_size
            if owner[addr] == idx:
                owner[addr] = -1

    soup["organisms"].pop(idx)
    soup["deaths"] += 1

    # Re-index owner array
    for i in range(len(owner)):
        if owner[i] > idx:
            owner[i] -= 1
        elif owner[i] == idx:
            owner[i] = -1


def _soup_step(soup):
    """Advance the soup by one generation (all organisms get a time slice)."""
    organisms = soup["organisms"]
    memory = soup["memory"]
    mem_size = soup["mem_size"]
    owner = soup["owner"]

    # Cosmic rays — random bit flips in memory
    n_rays = int(mem_size * soup["cosmic_ray_rate"])
    for _ in range(n_rays):
        addr = random.randint(0, mem_size - 1)
        memory[addr] = random.randint(0, NUM_OPS - 1)

    # Execute each organism
    new_organisms = []
    for oi in range(len(organisms)):
        org = organisms[oi]
        if not org.alive:
            continue

        # Handle pending allocation
        if org.daughter_len > 0 and org.daughter_start < 0:
            block = _find_free_block(owner, mem_size, org.daughter_len)
            if block >= 0:
                org.daughter_start = block
                org.wh = 0
                for i in range(org.daughter_len):
                    owner[(block + i) % mem_size] = oi

        _execute_slice(org, memory, mem_size,
                       soup["mutation_rate"], soup["slice_size"])

        # Check for split
        last_op = memory[(org.mem_start + max(0, org.ip - 1)) % mem_size]
        if last_op == OP_SPLIT and org.daughter_start >= 0:
            # Harvest daughter genome from memory
            daughter_genome = []
            for i in range(org.daughter_len):
                daughter_genome.append(
                    memory[(org.daughter_start + i) % mem_size])
            child = Organism(daughter_genome, org.daughter_start,
                             org.daughter_len)
            new_organisms.append(child)
            org.daughter_start = -1
            org.daughter_len = 0
            soup["births"] += 1

    # Add children
    for child in new_organisms:
        if len(organisms) >= soup["max_organisms"]:
            _reap(soup)
        ci = len(organisms)
        organisms.append(child)
        # Update owner for child
        for i in range(child.mem_len):
            addr = (child.mem_start + i) % soup["mem_size"]
            owner[addr] = ci

    # Remove dead organisms
    i = 0
    while i < len(organisms):
        if not organisms[i].alive or organisms[i].errors > 200:
            _kill_organism(soup, i)
        else:
            i += 1

    soup["generation"] += 1

    # Update species counts
    counts = {}
    for org in organisms:
        sid = org.species_id
        counts[sid] = counts.get(sid, 0) + 1
    soup["species_counts"] = counts

    # Record history snapshot (every 10 generations)
    if soup["generation"] % 10 == 0:
        soup["history"].append({
            "gen": soup["generation"],
            "pop": len(organisms),
            "species": len(counts),
            "births": soup["births"],
            "deaths": soup["deaths"],
        })
        if len(soup["history"]) > 200:
            soup["history"] = soup["history"][-200:]


# ── Mode integration ─────────────────────────────────────────────────────

def _enter_tierra_mode(self):
    """Enter Tierra digital organisms mode — show preset menu."""
    self.tierra_mode = True
    self.tierra_menu = True
    self.tierra_menu_sel = 0
    self.tierra_soup = None
    self.tierra_running = False
    self.tierra_view = "memory"   # memory | stats | phylo
    self.tierra_scroll = 0


def _exit_tierra_mode(self):
    """Exit Tierra mode."""
    self.tierra_mode = False
    self.tierra_menu = False
    self.tierra_soup = None


def _tierra_init(self, preset_idx):
    """Initialize soup from selected preset."""
    _, _, settings = TIERRA_PRESETS[preset_idx]
    self.tierra_soup = _init_soup(settings)
    self.tierra_menu = False
    self.tierra_running = True


def _tierra_step(self):
    """Advance simulation by one or more steps."""
    if not self.tierra_soup or not self.tierra_running:
        return
    for _ in range(self.tierra_soup["speed"]):
        _soup_step(self.tierra_soup)


def _handle_tierra_menu_key(self, key):
    """Handle keys on the preset selection menu."""
    n = len(TIERRA_PRESETS)
    if key == curses.KEY_UP or key == ord('k'):
        self.tierra_menu_sel = (self.tierra_menu_sel - 1) % n
    elif key == curses.KEY_DOWN or key == ord('j'):
        self.tierra_menu_sel = (self.tierra_menu_sel + 1) % n
    elif key in (curses.KEY_ENTER, 10, 13, ord('\n')):
        _tierra_init(self, self.tierra_menu_sel)
    elif key == ord('q') or key == 27:
        _exit_tierra_mode(self)
        self.mode_browser = True


def _handle_tierra_key(self, key):
    """Handle keys during simulation."""
    if key == ord('q') or key == 27:
        _exit_tierra_mode(self)
        self.mode_browser = True
    elif key == ord(' '):
        self.tierra_running = not self.tierra_running
    elif key == ord('n'):
        if not self.tierra_running:
            _soup_step(self.tierra_soup)
    elif key == ord('+') or key == ord('='):
        self.tierra_soup["speed"] = min(self.tierra_soup["speed"] + 1, 20)
    elif key == ord('-'):
        self.tierra_soup["speed"] = max(self.tierra_soup["speed"] - 1, 1)
    elif key == ord('v'):
        views = ["memory", "stats", "phylo"]
        idx = views.index(self.tierra_view)
        self.tierra_view = views[(idx + 1) % len(views)]
    elif key == ord('m'):
        # Trigger manual mutation burst
        soup = self.tierra_soup
        for _ in range(20):
            addr = random.randint(0, soup["mem_size"] - 1)
            soup["memory"][addr] = random.randint(0, NUM_OPS - 1)
    elif key == ord('r'):
        # Reap one organism manually
        if self.tierra_soup["organisms"]:
            _reap(self.tierra_soup)
    elif key == curses.KEY_UP:
        self.tierra_scroll = max(0, self.tierra_scroll - 1)
    elif key == curses.KEY_DOWN:
        self.tierra_scroll += 1


# ── Drawing ──────────────────────────────────────────────────────────────

def _draw_tierra_menu(self, max_y, max_x):
    """Draw the preset selection menu."""
    title = "╔══ TIERRA: DIGITAL ORGANISMS ══╗"
    subtitle = "Self-replicating programs in shared memory"
    try:
        cy = max_y // 2 - len(TIERRA_PRESETS) - 3
        cx = max(0, (max_x - len(title)) // 2)
        self.stdscr.addstr(cy, cx, title, curses.A_BOLD | curses.color_pair(3))
        self.stdscr.addstr(cy + 1, max(0, (max_x - len(subtitle)) // 2),
                           subtitle, curses.color_pair(7))

        y = cy + 3
        for i, (name, desc, _) in enumerate(TIERRA_PRESETS):
            if y + 1 >= max_y:
                break
            attr = curses.A_REVERSE if i == self.tierra_menu_sel else 0
            line = f"  {name:20s} — {desc}"
            if len(line) > max_x - 4:
                line = line[:max_x - 7] + "..."
            self.stdscr.addstr(y, 2, line, attr | curses.color_pair(7))
            y += 1

        hint = "↑/↓ select · Enter start · q back"
        if y + 2 < max_y:
            self.stdscr.addstr(y + 2, max(0, (max_x - len(hint)) // 2),
                               hint, curses.color_pair(8))
    except curses.error:
        pass


def _draw_tierra(self, max_y, max_x):
    """Draw the active Tierra simulation."""
    soup = self.tierra_soup
    if not soup:
        return

    try:
        # Title bar
        gen = soup["generation"]
        pop = len(soup["organisms"])
        n_species = len(soup["species_counts"])
        status = "RUNNING" if self.tierra_running else "PAUSED"
        speed_str = f"x{soup['speed']}"
        title = (f" TIERRA  Gen:{gen:>6d}  Pop:{pop:>4d}"
                 f"  Species:{n_species:>3d}  [{status}] {speed_str} ")
        title = title[:max_x]
        self.stdscr.addstr(0, 0, title, curses.A_BOLD | curses.color_pair(3))

        if self.tierra_view == "memory":
            _draw_memory_view(self, soup, max_y, max_x)
        elif self.tierra_view == "stats":
            _draw_stats_view(self, soup, max_y, max_x)
        elif self.tierra_view == "phylo":
            _draw_phylo_view(self, soup, max_y, max_x)

        # Hint bar
        hint = "SPC:pause n:step +/-:speed v:view m:mutate r:reap q:quit"
        if max_y > 2:
            self.stdscr.addstr(max_y - 1, 0, hint[:max_x - 1],
                               curses.color_pair(8))
    except curses.error:
        pass


def _draw_memory_view(self, soup, max_y, max_x):
    """Draw memory as a colored grid — each cell is one memory address."""
    memory = soup["memory"]
    owner = soup["owner"]
    mem_size = soup["mem_size"]
    organisms = soup["organisms"]

    grid_w = max(1, max_x - 2)
    grid_h = max(1, max_y - 4)
    total_visible = grid_w * grid_h
    scroll_offset = self.tierra_scroll * grid_w

    # Build species→color mapping
    species_colors = {}
    color_idx = 0
    for org in organisms:
        if org.species_id not in species_colors:
            species_colors[org.species_id] = (color_idx % 7) + 1
            color_idx += 1

    # Build set of instruction pointers for highlighting
    ip_addrs = set()
    for org in organisms:
        ip_addrs.add((org.mem_start + org.ip) % mem_size)

    for row in range(grid_h):
        y = row + 1
        if y >= max_y - 1:
            break
        line_chars = []
        line_attrs = []
        for col in range(grid_w):
            addr = (scroll_offset + row * grid_w + col) % mem_size
            op = memory[addr]
            oi = owner[addr]
            ch = OP_CHARS[op]

            if oi >= 0 and oi < len(organisms):
                sid = organisms[oi].species_id
                cp = species_colors.get(sid, 7)
                attr = curses.color_pair(cp)
                if addr in ip_addrs:
                    attr |= curses.A_BOLD | curses.A_REVERSE
            else:
                # Free memory — dim
                attr = curses.color_pair(8)
                ch = '·'

            line_chars.append(ch)
            line_attrs.append(attr)

        for col in range(min(len(line_chars), max_x - 2)):
            try:
                self.stdscr.addch(y, col + 1, ord(line_chars[col]),
                                  line_attrs[col])
            except curses.error:
                pass

    # Memory utilization bar
    used = sum(1 for o in owner if o >= 0)
    pct = used * 100 // max(1, mem_size)
    bar_y = max_y - 2
    if bar_y > 1:
        bar = f" Mem: {'█' * (pct * 30 // 100)}{'░' * (30 - pct * 30 // 100)} {pct}% ({used}/{mem_size})"
        try:
            self.stdscr.addstr(bar_y, 0, bar[:max_x - 1], curses.color_pair(7))
        except curses.error:
            pass


def _draw_stats_view(self, soup, max_y, max_x):
    """Draw population statistics and species breakdown."""
    organisms = soup["organisms"]
    counts = soup["species_counts"]

    y = 2
    # Population stats
    stats_lines = [
        f"  Generation:     {soup['generation']}",
        f"  Population:     {len(organisms)}",
        f"  Total births:   {soup['births']}",
        f"  Total deaths:   {soup['deaths']}",
        f"  Species:        {len(counts)}",
        f"  Mutation rate:  {soup['mutation_rate']:.4f}",
        f"  Cosmic rays:    {soup['cosmic_ray_rate']:.5f}",
        "",
        "  ── Top Species ──",
    ]

    for line in stats_lines:
        if y >= max_y - 4:
            break
        try:
            self.stdscr.addstr(y, 0, line[:max_x - 1], curses.color_pair(7))
        except curses.error:
            pass
        y += 1

    # Sort species by count
    sorted_species = sorted(counts.items(), key=lambda x: -x[1])
    color_idx = 0
    for sid, cnt in sorted_species[:max_y - y - 4]:
        if y >= max_y - 4:
            break
        # Find genome length for this species
        glen = 0
        for org in organisms:
            if org.species_id == sid:
                glen = org.mem_len
                break
        pct = cnt * 100 // max(1, len(organisms))
        bar_len = min(cnt * 20 // max(1, len(organisms)), 20)
        bar = '█' * bar_len
        cp = (color_idx % 7) + 1
        line = f"  {sid & 0xFFFF:04X}  len:{glen:>3d}  n:{cnt:>4d} ({pct:>2d}%) {bar}"
        try:
            self.stdscr.addstr(y, 0, line[:max_x - 1],
                               curses.color_pair(cp))
        except curses.error:
            pass
        y += 1
        color_idx += 1

    # Population history sparkline
    if soup["history"] and y + 2 < max_y:
        y += 1
        try:
            self.stdscr.addstr(y, 0, "  ── Population History ──",
                               curses.color_pair(7))
        except curses.error:
            pass
        y += 1
        hist = soup["history"]
        w = min(max_x - 4, len(hist))
        recent = hist[-w:]
        if recent:
            max_pop = max(h["pop"] for h in recent)
            if max_pop > 0:
                sparks = " ▁▂▃▄▅▆▇█"
                line = "  "
                for h in recent:
                    idx = h["pop"] * 8 // max_pop
                    line += sparks[min(idx, 8)]
                try:
                    self.stdscr.addstr(y, 0, line[:max_x - 1],
                                       curses.color_pair(3))
                except curses.error:
                    pass

        # Species diversity sparkline
        y += 1
        if y < max_y - 2 and recent:
            max_sp = max(h["species"] for h in recent)
            if max_sp > 0:
                sparks = " ▁▂▃▄▅▆▇█"
                line = "  "
                for h in recent:
                    idx = h["species"] * 8 // max_sp
                    line += sparks[min(idx, 8)]
                try:
                    self.stdscr.addstr(y, 0, line[:max_x - 1],
                                       curses.color_pair(6))
                except curses.error:
                    pass


def _draw_phylo_view(self, soup, max_y, max_x):
    """Draw a genome-length distribution / phylogenetic overview."""
    organisms = soup["organisms"]
    if not organisms:
        try:
            self.stdscr.addstr(3, 2, "No organisms alive.",
                               curses.color_pair(7))
        except curses.error:
            pass
        return

    y = 2
    try:
        self.stdscr.addstr(y, 2, "── Genome Length Distribution ──",
                           curses.color_pair(7))
    except curses.error:
        pass
    y += 1

    # Build histogram of genome lengths
    lengths = {}
    for org in organisms:
        l = org.mem_len
        lengths[l] = lengths.get(l, 0) + 1

    sorted_lens = sorted(lengths.items())
    max_count = max(lengths.values()) if lengths else 1
    bar_max = max(1, max_x - 20)

    for glen, cnt in sorted_lens:
        if y >= max_y - 6:
            break
        bar_len = max(1, cnt * bar_max // max_count)
        bar = '█' * bar_len
        cp = (glen % 7) + 1
        line = f"  {glen:>3d}: {bar} ({cnt})"
        try:
            self.stdscr.addstr(y, 0, line[:max_x - 1],
                               curses.color_pair(cp))
        except curses.error:
            pass
        y += 1

    # Show some individual organisms
    y += 1
    if y < max_y - 3:
        try:
            self.stdscr.addstr(y, 2, "── Sample Organisms ──",
                               curses.color_pair(7))
        except curses.error:
            pass
        y += 1

        # Show up to 10 organisms sorted by age (oldest first)
        sampled = sorted(organisms, key=lambda o: -o.age)[:min(10, max_y - y - 2)]
        for org in sampled:
            if y >= max_y - 2:
                break
            genome_preview = "".join(OP_CHARS[g] for g in org.genome[:30])
            if len(org.genome) > 30:
                genome_preview += "…"
            line = (f"  [{org.species_id & 0xFFFF:04X}] age:{org.age:>5d}"
                    f" len:{org.mem_len:>3d} err:{org.errors:>3d} {genome_preview}")
            try:
                self.stdscr.addstr(y, 0, line[:max_x - 1],
                                   curses.color_pair(7))
            except curses.error:
                pass
            y += 1


# ── Registration ─────────────────────────────────────────────────────────

def register(App):
    """Register Tierra digital organisms mode methods on the App class."""
    App._enter_tierra_mode = _enter_tierra_mode
    App._exit_tierra_mode = _exit_tierra_mode
    App._tierra_init = _tierra_init
    App._tierra_step = _tierra_step
    App._handle_tierra_menu_key = _handle_tierra_menu_key
    App._handle_tierra_key = _handle_tierra_key
    App._draw_tierra_menu = _draw_tierra_menu
    App._draw_tierra = _draw_tierra
    App.TIERRA_PRESETS = TIERRA_PRESETS
