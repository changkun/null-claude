# Changelog

All notable changes to this project are documented in this file.

## 2026-03-16

### Feature: Add long-exposure photography mode for composite frame artwork

Added a "long-exposure photography" system that composites hundreds of simulation frames into a single artistic still image — like astrophotography for cellular automata. Blends frame data over a configurable time window using accumulation buffers, producing luminance trails, flow lines, and density maps rendered as a high-detail truecolor frame.

**`life/modes/long_exposure.py`** (new, ~415 lines):
- **Accumulation buffer**: each frame's truecolor RGB data is accumulated per-pixel, tracking total color, hit count, and peak intensity across the entire exposure window.
- **3 blend modes**: additive (luminance trails weighted by activity density, with brightness boost for high-traffic areas), max (peak intensity — captures the brightest moment at each pixel), average (mean color — reveals the steady-state palette).
- **Auto-freeze**: automatically freezes the composite and stops accumulation when the configurable exposure window (10–1000 frames) is reached.
- **Density-based glyphs**: renders frozen composites using `· ░ ▒ ▓ █` based on how frequently each pixel was occupied, creating topographic-style density maps.
- **Dual export**: frozen composites export as both machine-readable JSON (pixel coordinates, RGB, density) and ANSI art `.ans` files viewable with `cat` in any truecolor terminal.
- **Progress indicator**: real-time overlay badge with mini progress bar (`█░`) showing capture progress, blend mode, and frame count.

**`life/app.py`** (+30 lines):
- Init called from `__init__` alongside ghost trail.
- Frame accumulation hooked into `_tc_refresh()` — captures every rendered frame from any of the 130+ modes.
- Frozen composite renders as full-screen artwork in `_draw()` (before mode dispatch), replacing the live view.
- Key handling inserted after ghost trail handlers.
- Status bar shows active capture progress or frozen frame count.
- Help screen updated with all 5 new keybindings.

**`life/modes/__init__.py`** (+2 lines):
- Registered `long_exposure` module via the standard `register()` pattern.

**`tests/test_long_exposure.py`** (new, 31 tests):
- Covers initialization, key handling (start/stop/freeze/unfreeze/restart), accumulation (truecolor cells, multi-frame, max tracking, inactive/frozen guards), auto-freeze at window boundary, all 3 blend modes (additive density weighting, max peak selection, average arithmetic mean), composite rendering, indicator drawing, export with file verification, and method registration.

**Design:** Builds on the existing ghost trail, truecolor buffer, and colormap infrastructure. Where ghost trail shows fading echoes of recent frames, long exposure creates permanent, layered artwork from the full trajectory. The accumulation buffer tracks 7 values per pixel (3 totals, hit count, 3 maxima) to support all blend modes from a single capture pass.

**Controls:**
| Key | Action |
|-----|--------|
| `Ctrl+E` | Start/stop long-exposure capture |
| `Ctrl+F` | Freeze/unfreeze composite view |
| `[ ]` | Adjust exposure window (±50 frames, range 10–1000) |
| `{ }` | Cycle blend mode (additive → max → average) |
| `Ctrl+]` | Export frozen composite to `.json` + `.ans` files |

---

### Feature: Add braille-dot sparkline metrics HUD for real-time visualization

Added a toggleable overlay that renders live sparkline charts using Unicode braille characters (U+2800–U+28FF) for high-resolution mini-charts in a small terminal footprint. Four metrics — population, entropy, energy, and diversity index — update in real time as the simulation runs, turning every mode into a visual science experiment.

**`life/modes/sparkline_hud.py`** (new, ~340 lines):
- **Braille sparkline renderer**: each character encodes a 2×4 dot matrix, giving 60 data points × 12 vertical dot rows of resolution per chart (30 chars wide × 3 chars tall).
- **4 live charts**: Population (green), Entropy (magenta), Energy (yellow), Diversity Index (cyan) — each with auto-scaling axes and compact number formatting (k/M suffixes).
- **`SparklineHUDState`** class: 120-point history deques, frame counter, per-chart visibility toggles.
- **Energy metric**: sum of all cell values — equals population for binary grids, captures total excitation for multi-state grids.
- **Diversity metric**: normalized Shannon diversity index (entropy / ln(n_states)), giving a [0,1] measure of how evenly cells are distributed across states.
- Expensive metrics (energy, diversity) sampled every 2 frames with carry-forward to avoid per-frame grid scans.
- Panel drawn with box-drawing border, per-metric color-coded headers showing current value and min–max range.

**`life/app.py`** (+15 lines):
- `SparklineHUDState` instantiated in `__init__`.
- Sparkline HUD update + draw hook in the render loop, positioned before the analytics overlay.
- **Ctrl+V** toggles the HUD globally across all modes.
- Help screen updated with the new keybinding.

**`life/modes/__init__.py`** (+2 lines):
- Registered `sparkline_hud` module via the standard `register()` pattern.

**Design:** Follows the same non-invasive overlay pattern as the parameter tuner — registers methods on `App`, hooks into the render loop, and reads grid state without modifying any mode logic. The braille encoding packs ~160× more resolution than simple character-based sparklines into the same terminal area. Panel renders at top-left (py=2), safely above the analytics overlay at bottom-left.

**Controls:** `Ctrl+V` toggle on/off.

**Files added:** `life/modes/sparkline_hud.py`, `.ralph/round-371-thinker.json`, `.ralph/round-371-worker.json`, `.ralph/round-372-thinker.json`, `.ralph/round-372-worker.json`

---

### Feature: Add full simulation snapshot save/load system

Added a complete state serialization system that lets users save, browse, and restore full simulation snapshots — grid cells, ages, generation count, active mode, mode-specific parameters, viewport position, cursor, zoom, speed, colormap, heatmap state, and running state — to versioned JSON files on disk. This turns ephemeral terminal sessions into a persistent exploration journal that works across all 130+ modes.

**`life/constants.py`** (+1 line):
- Added `SNAPSHOT_DIR` constant (`~/.life_saves/snapshots/`) — keeps snapshots separate from grid-only saves.

**`life/app.py`** (+267 lines):
- **`_snapshot_detect_mode()`** — Detects the active mode by checking MODE_DISPATCH table and explicit mode flags (`evo_mode`, `ep_mode`, etc.).
- **`_snapshot_collect_mode_params(mode_attr)`** — Collects all mode-specific numeric/bool/string/set parameters by naming convention (prefix matching).
- **`_snapshot_restore_mode_params(params)`** — Restores collected parameters, handling set↔list JSON round-trip conversion.
- **`_save_snapshot()`** — Prompts for a name, serializes full state to a versioned `.snapshot.json` file.
- **`_load_snapshot()`** / **`_show_snapshot_menu(snaps)`** — Blocking menu with metadata preview (generation, mode name), scroll support, and delete capability (`d` key with confirmation).
- **`_apply_snapshot(data)`** — Cleanly exits the current mode via exit methods, restores grid state, viewport, display settings, enters the target mode via enter methods, restores mode-specific parameters, and resets tracking state (history, cycle detection, heatmap).
- **Keybindings**: `Ctrl+W` (save) and `Ctrl+O` (load) wired as global keys before analytics overlay dispatch.
- **Help screen** updated with the two new keybindings.

**`tests/test_snapshot.py`** (new, 17 tests):
- Mode detection: base Game of Life returns `None`, dispatch modes detected, explicit modes detected, first-active-wins ordering.
- Parameter collection: empty for base mode, captures prefixed attrs, converts sets to sorted lists.
- Parameter restoration: numeric values, set-from-list conversion, unknown attrs skipped safely.
- Snapshot application: grid state restored, topology/hex_mode restored, mode activation with params, previous mode deactivation, history clearing.
- JSON round-trip: full state survives serialize→deserialize→apply, including with active modes and parameters.

**Design:** The snapshot format is versioned (`"version": 1`) for forward compatibility. Mode detection uses the existing MODE_DISPATCH registry plus an explicit fallback list, so new modes added to the dispatch table are automatically supported. Parameter collection uses naming convention (prefix matching) rather than per-mode schemas, keeping maintenance cost at zero as modes are added.

**Controls:** `Ctrl+W` save snapshot, `Ctrl+O` load snapshot.

**Tests:** 5930 passed — all green (5913 existing + 17 new).

**Files added:** `tests/test_snapshot.py`, `.ralph/round-370-thinker.json`, `.ralph/round-370-worker.json`

---

### Rendering: Add ghost trail / temporal echo layer for all simulation modes

Added a rendering overlay that captures frame snapshots and composites fading afterimages from previous frames onto any active simulation mode. Particles leave streaks, wavefronts show propagation paths, cellular automata reveal their evolution — all without modifying any mode logic.

**`life/modes/ghost_trail.py`** (new, ~190 lines):
- Frame capture via `inch()` (curses cells) and `tc_buf.cells` (truecolor cells), stored as `(y, x) -> (char, r, g, b)` dicts in a ring buffer
- Echo injection: iterates stored frames newest-to-oldest, rendering dimmed truecolor glyphs (`▓▒░·`) at positions occupied in past frames but empty in the current frame
- Two decay curves: exponential (`0.65^age`, default) and linear; toggled with Ctrl+G
- RGB-aware dimming: truecolor cells decay their original RGB; curses-only cells derive color from the active colormap via `colormap_rgb()`
- Trail depth adjustable 1–20 frames with `<`/`>` keys
- Status badge overlay and status bar indicator (`GHOST(N)`)

**`life/app.py`** (+16 lines):
- `_ghost_trail_init()` call in `__init__` to set up state variables
- Ghost trail indicator drawn after post-processing indicator
- Key handling hook before post-processing pipeline dispatch
- Frame capture/inject hook in `_tc_refresh()` (runs once per draw cycle via `_ghost_frame_done` flag)
- `_ghost_frame_done` reset at top of `_draw()`
- Status bar shows `GHOST(depth)` when active

**`life/modes/__init__.py`** (+2 lines):
- Registered `ghost_trail` module in `register_all_modes()`

**Design:** Non-invasive — hooks into the existing truecolor pipeline at the `_tc_refresh()` boundary, capturing whatever the active mode drew and injecting echo cells into `tc_buf` before the truecolor render pass. Works with all 125+ modes. The `g` key toggles the feature; no mode needs to know about it.

**Controls:** `g` toggle on/off, `<`/`>` trail depth, Ctrl+G cycle decay curve.

**Tests:** 5913 passed, 6 skipped — all green.

**Files added:** `.ralph/round-369-thinker.json`, `.ralph/round-369-worker.json`

---

### Feature: Add real-time parameter tuning overlay for all simulation modes

Added an interactive HUD overlay (`P` key) that lets users adjust any mode's simulation constants in real-time while the simulation keeps running. This turns passive viewing into active exploration — sweep gravity, diffusion rates, coupling strengths, and temperatures with immediate visual feedback.

**`life/modes/param_tuner.py`** (new, ~350 lines):
- `TUNABLE_PARAMS` registry with curated min/max/step/format for 33 modes (~100 parameters total): Boids (7 params), Physarum (6), Reaction-Diffusion (5), Lotka-Volterra (5), SIR (4), Hodge (4), Kuramoto (3), N-Body (3), SPH (3), Traffic (3), Cloth (3), Forest Fire (3), BZ (3), and 20 more
- Auto-detection fallback: scans `self.{prefix}_*` for numeric attributes, generates reasonable ranges/steps — all 132 modes benefit even without explicit definitions
- HUD overlay with parameter names, formatted values, visual progress bars, and scrolling
- Controls: `↑`/`↓` or `j`/`k` to select, `←`/`→` or `h`/`l` to adjust, `[`/`]` for 10x steps, `0` to refresh, `P` to close

**`life/app.py`** (+16 lines):
- Added `param_tuner_active/sel/params` state variables
- `P` key intercept (only when a simulation mode is active)
- Overlay drawing in render loop after cast indicator
- Param tuner key handling before mode dispatch (arrow keys intercepted when active, all other keys pass through)

**`life/modes/__init__.py`** (+2 lines):
- Registered `param_tuner` module in `register_all_modes()`

**Design:** Non-invasive — the tuner reads/writes existing `self.*` attributes directly, so every mode works without modification. Arrow keys are only intercepted when the panel is open; the simulation continues running underneath.

**Files added:** `.ralph/round-368-thinker.json`, `.ralph/round-368-worker.json`

---

### Rendering: Add 24-bit truecolor support with perceptually uniform colormaps

Added a three-tier color rendering pipeline (truecolor → redefined 256-color → 8-color ANSI) that dramatically improves visual fidelity on modern terminals without breaking compatibility on older ones.

**`life/colors.py`** (rewritten, +430 lines):
- 8 perceptually uniform colormaps built from control points with linear interpolation: viridis, magma, inferno, plasma, ocean, thermal, terrain, amber
- `truecolor_available()`: detects 24-bit support via `$COLORTERM`
- `TrueColorBuffer`: collects 24-bit cell writes during a frame, batch-renders them after `curses.refresh()` using `\033[38;2;R;G;Bm` escape sequences to avoid curses buffer conflicts
- `tc_addstr()` / `colormap_addstr()`: convenience functions with automatic truecolor→256-color fallback via `_nearest_256()` (xterm cube + grayscale ramp)
- Enhanced `_init_colors()`: when `can_change_color()` is True, redefines color indices with precise RGB samples from colormaps — transparently upgrades all 132 modes

**`life/app.py`**:
- Added `TrueColorBuffer`, colormap state, and `_tc_refresh()` method
- Replaced all 35 `stdscr.refresh()` calls with `_tc_refresh()` for buffer overlay
- Added `K` key to cycle through 8 colormaps; updated hint bar

**5 modes with dedicated truecolor rendering paths:**
- `reaction_diffusion.py`: maps each color scheme to a colormap (ocean/thermal/viridis/plasma/inferno)
- `lenia.py`: continuous magma gradient for organic patterns
- `fluid_lbm.py`: inferno (speed), plasma (vorticity), viridis (density)
- `physarum.py`: amber gradient for bio-network trails
- `wave_equation.py`: diverging scheme — inferno for crests, ocean for troughs

**Design:** Non-breaking — all existing color pair references work unchanged. Every truecolor path has a `use_tc` guard with the original discrete-tier logic preserved in the else branch.

**Files added:** `.ralph/round-367-thinker.json`, `.ralph/round-367-worker.json`

---

### Architecture: Replace manual key/draw dispatch chains with data-driven mode routing table

Replaced the ~2,200 lines of `if/elif` dispatch chains in `app.py` with a declarative `MODE_DISPATCH` table built automatically from `MODE_REGISTRY`. This is the single largest structural improvement to the codebase to date.

**Problem:** Every mode's key handler and draw call was wired through sprawling `if self.xyz_mode` chains in `app.py`'s `run()` and `_draw()` methods. These had to be maintained by hand across 5+ insertion points, and the wiring test infrastructure (711 tests) had to regex-scan the source code to verify correctness. Three modes (Quantum Circuit, Mycelium Network, Tierra) were recently found completely broken because they were never wired in.

**Solution:** A data-driven routing dict in `registry.py` where each mode's `{flag, enter, exit, keys, draw, step, menu}` contract is derived automatically from `MODE_REGISTRY` using naming conventions, with an overrides dict for the ~15 modes with non-standard naming.

**`life/registry.py`** (+158 lines):
- `MODE_DISPATCH` table auto-built from `MODE_REGISTRY` via convention-based method name derivation
- `_DISPATCH_OVERRIDES` dict for modes with non-standard naming (e.g., `br_mode` → `_br_do_step`, `obs_mode` → `_handle_observatory_key`)

**`life/app.py`** (−2,172 lines, 8,190 → 6,018):
- `_dispatch_mode_key(key)` — routes key input to active mode's handler via dispatch table
- `_dispatch_mode_draw(max_y, max_x)` — routes drawing to active mode via dispatch table
- `_auto_step_mode(md)` — generic stepping with delay, step count, and custom running checks
- 8 `_is_*_auto_stepping()` helpers for modes with non-standard running conditions
- `_any_menu_open()` now iterates the dispatch table instead of a manual list
- ~1,200-line key dispatch `if/elif` chain → single `_dispatch_mode_key(key)` call + ~40 lines for 4 special cases
- ~1,000-line draw dispatch `if/elif` chain → single `_dispatch_mode_draw(max_y, max_x)` call + ~30 lines for special cases

**`tests/test_mode_wiring.py`** (rewritten, 711 → 1,165 tests):
- Old: regex-scanned source code to verify `if/elif` chains existed (fragile)
- New: verifies dispatch table structure directly (correctness by construction):
  - Every `MODE_REGISTRY` entry is dispatched or explicitly handled
  - All referenced methods exist on the App class
  - Enter/exit methods exist
  - Menu handlers set mode flags

**Key benefits:**
- Eliminates the class of bug that broke Quantum Circuit, Mycelium, and Tierra — modes can't be "forgotten" if registration is automatic
- Makes regex-based wiring tests unnecessary — correctness by construction
- Shrinks `app.py` by 26% (2,172 lines)
- Adding a new mode is now one step (add to `MODE_REGISTRY`) instead of editing 5+ places

**Files added:** `.ralph/round-366-thinker.json`, `.ralph/round-366-worker.json`

---

## 2026-03-15

### Infrastructure: Ralph Task Logs (All Remaining Rounds)

Added the four remaining `.ralph/round-364/365` thinker/worker JSON files to complete the session record. These logs capture the final two thinker proposals of the run — the Procedural Music / Generative Soundscape sonification rewrite (round 364) and the Electric Circuit Simulator (round 365) — along with their corresponding worker execution summaries. No simulation code was modified; this commit is purely a housekeeping flush of leftover orchestration artifacts.

**Files added:** `.ralph/round-364-thinker.json`, `.ralph/round-364-worker.json`, `.ralph/round-365-thinker.json`, `.ralph/round-365-worker.json`

---

### Added: Electric Circuit Simulator — Grid-Based Circuit Builder with Real-Time Analysis

A new physics mode implementing a continuous-value circuit simulator where users place
components on a grid and watch real-time current flow as animated charges, voltage as a
color heatmap, and waveforms on a built-in oscilloscope. Unlike Wireworld (a binary
cellular automaton for logic gates), this is a scientifically accurate analog circuit
simulator solving Kirchhoff's laws via Modified Nodal Analysis, with proper transient
response for reactive components.

**New file:** `life/modes/electric_circuit.py` (~750 lines)

**Circuit solver — Modified Nodal Analysis (MNA):**

| Concept | Implementation |
|---------|---------------|
| Linear system | MNA stamps for each component type; Gaussian elimination with partial pivoting |
| Resistor | Conductance stamp G = 1/R between nodes |
| Battery/voltage source | Extra MNA row enforcing V+ − V− = E |
| Capacitor | Companion model: conductance G = C/Δt with history current source (trapezoidal integration) |
| Inductor | Companion model: conductance G = Δt/L with history current source |
| AC source | Sinusoidal voltage modulation V(t) = V₀·sin(2πft) with adjustable frequency |
| Ground | Reference node fixed at 0V |

**8 component types:** Wire, Battery, Resistor, Capacitor, Inductor, LED, Switch (interactive toggle), Ground

**6 preset circuits:**

| Preset | What it demonstrates |
|--------|---------------------|
| Simple DC Loop | Battery + resistor — Ohm's law (V = IR) |
| Voltage Divider | Two resistors splitting voltage (V_out = V × R₂/(R₁+R₂)) |
| RC Charging Curve | Capacitor charging through resistor (τ = RC exponential) |
| LC Oscillator | Energy oscillating between inductor and capacitor (ω = 1/√LC) |
| RLC Resonance | AC-driven damped sinusoidal oscillation with resonance peak |
| Wheatstone Bridge | Balanced bridge circuit with galvanometer resistor |

**3 visualization views (cycle with `v`):**

| View | Description |
|------|-------------|
| Schematic | Components drawn with distinct Unicode symbols; animated charge particles flow along wires with speed/direction proportional to current; color-coded by current magnitude; node voltage labels at junctions |
| Voltage Heatmap | Color gradient from blue (0V) to red (max V) showing voltage distribution across the circuit |
| Oscilloscope | Dual-trace time-series plot showing voltage and current waveforms with axis labels and scaling |

**Interactive controls:** Space (pause), `s` (toggle switches), ↑/↓ (AC frequency),
+/− (simulation speed), `v` (cycle view), `r` (reset), `R` (back to menu)

**Integration points:**
- `life/app.py`: Circuit mode state variables, menu detection, key dispatch, draw routing
- `life/registry.py`: Registered under "Physics & Waves" category with `Ctrl+Shift+E` shortcut
- `life/modes/__init__.py`: Registration import

---

### Enhanced: Generative Soundscape — Multi-Voice Procedural Music Engine

Complete rewrite of the sonification layer (`life/modes/sonification.py`) from a basic
drone engine into a multi-voice generative music system. The Ctrl+S sonification toggle
now produces layered compositions — bass, melody, harmony, and rhythm — derived entirely
from each simulation frame's spatial state. Because it's a cross-cutting layer that reads
grid state generically, all 130+ existing modes gain a unique musical character without
any per-mode code changes.

**Changed file:** `life/modes/sonification.py` (rewritten, +499/−134 lines)

**Four simultaneous synthesis voices:**

| Voice | Source metric | Musical behavior |
|-------|-------------|-----------------|
| Bass | Rate of change (delta) | Root note with portamento; large deltas trigger 4th/5th harmonic jumps, small deltas hold steady |
| Melody | Column density profile | Spatial shape → arpeggiated sequence; highest-density columns become notes ordered left-to-right, with per-note envelopes and inter-note glide |
| Harmony | Cell density | Sustained chord pad; voicing expands with density: open 5th → triad → 7th → 9th → extended |
| Rhythm | Spatial entropy | Percussive noise bursts gated by 16-step patterns; 8 patterns from sparse 4-on-floor to dense syncopation |

**Additional musical mappings:**

| Metric | Maps to |
|--------|---------|
| Center-of-mass Y | Pitch register (higher mass → higher octave) |
| Center-of-mass X | Stereo panning |
| Symmetry | Pulse width modulation on waveforms |
| Activity level | Number of melody notes (2–8) and overall brightness |
| Delta | Root motion speed and volume surges |

**Frame-to-frame musical memory:** Persistent `_sonify_state` dict tracks root semitone,
bass frequency, melody notes, noise seed, and frame count across frames — enabling
portamento, harmonic progressions, and smooth transitions instead of per-frame randomness.

**Per-category audio profiles** extended with three new parameters (`melody_mode`,
`rhythm_feel`, `swing`) across all 12 category profiles, enabling distinct musical
character per simulation domain (e.g., Fluid Dynamics gets ambient legato glides;
Particle & Swarm gets staccato scattered percussion with swing).

**New musical data structures:**
- 8 rhythm gate patterns (16-step sequences) from minimal to full density
- 5 chord voicings (fifth → triad → seventh → ninth → extended) selected by density
- Root motion interval table for harmonic progression driven by rate of change

**Enhanced status indicator** shows current root note name, melody voice count, and
frame counter in the SOUNDSCAPE bar.

**Also changed:**
- `life/app.py`: Added `_sonify_state` dict and `_sonify_prev_density` float initialization; updated toggle flash message to reflect new engine name

---

### Added: Magnetism & Spin Glass — Continuous-Spin Lattice with Frustrated Interactions

A new physics mode simulating magnetic domains on a 2D lattice where each cell carries a
continuous XY-model spin angle (not just Ising ±1). Spins interact via configurable exchange
coupling — ferromagnetic (J>0), antiferromagnetic (J<0), random Edwards-Anderson ±J, or
frustrated (biased mix) — with thermal fluctuations governed by Metropolis-Hastings dynamics.
This fills a clear gap: the project has an Ising model (`ising.py`) with binary spins, but
nothing showing continuous-spin physics, frustrated magnetism, glassy dynamics, or aging
effects — phenomena qualitatively different from anything in the existing modes.

**New file:** `life/modes/spin_glass.py` (~600 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Spin model | XY model — continuous angle θ ∈ [0, 2π) per lattice site |
| Interactions | Nearest-neighbor exchange: E = −J·cos(θᵢ − θⱼ), with per-bond coupling constants |
| Coupling types | Ferromagnetic (J=+1), antiferromagnetic (J=−1), random ±1 (Edwards-Anderson), frustrated (60/40 mix) |
| Dynamics | Metropolis-Hastings with adaptive trial step size (small at low T, large at high T) |
| External field | Configurable field h coupling to cos(θ), adjustable at runtime |
| Observables | Vector magnetization (mx, my, |m|), energy per spin E/N, susceptibility χ from fluctuation-dissipation theorem |
| Domain walls | Detected via angular difference threshold (>0.6π) between neighboring spins |

**12 presets:**

| Preset | Description |
|--------|-------------|
| Ferromagnetic | Uniform J>0 — spins align, classic ordering |
| Antiferromagnetic | Uniform J<0 — checkerboard Néel order |
| Spin Glass (±J) | Random bonds — frustration, no long-range order |
| Frustrated Lattice | Triangular frustration — competing interactions |
| Critical FM | T near Tc — large fluctuating domains |
| Hot Disorder | T=5.0 — paramagnetic chaos |
| Quench to Glass | Start hot, T=0.05 — watch aging & frozen domains |
| Field-Cooled Glass | Spin glass in external field — partial alignment |
| Domain Coarsening | FM quench — watch domains grow via curvature |
| All Aligned + Heat | Start ordered, heat to disorder |
| Vortex Patterns | Low-T ferro — watch topological defects |
| Glass Aging | Very low T glass — frozen but slowly evolving |

**3 view modes:**

| View | What it shows |
|------|---------------|
| Spin Arrows | Directional Unicode arrows (→ ↗ ↑ ↖ ← ↙ ↓ ↘) color-coded by local energy density (cyan=low → magenta=frustrated), domain walls highlighted in bright white |
| Energy Density | Block-character heatmap of local energy (blue=low through red=high) |
| Statistics | Real-time scrolling plots of magnetization |m|, energy E/N, and susceptibility χ |

**Interactive controls:** `t`/`T` adjust temperature, `Q` instant quench to T=0.01, `a` anneal (+0.5), `f`/`F` adjust external field, `Space` pause/resume, `n` single step, `v` cycle views, `+`/`-` simulation speed, `r` reset, `R` back to menu, `q` quit. Accessible via `Ctrl+Shift+G` from the mode browser under "Physics & Waves."

**Also changed:**
- `life/modes/__init__.py`: Added import and registration call for spin_glass mode
- `life/registry.py`: Added registry entry under "Physics & Waves" category with `Ctrl+Shift+G` shortcut
- `life/app.py`: Added 24 state attributes, key dispatch block, and draw dispatch block for spinglass mode

---

### Added: Molecular Dynamics / Phase Transitions — Lennard-Jones Particle Simulation

A new physics mode that simulates classical molecular dynamics: particles interact via
the Lennard-Jones 6-12 potential V(r) = 4ε[(σ/r)¹² − (σ/r)⁶], producing short-range
repulsion and long-range attraction. With velocity-Verlet integration, periodic boundary
conditions, and a Berendsen-style velocity-rescaling thermostat, particles self-organize
into crystals at low temperature, melt into disordered liquids, and evaporate into gas —
all from a single pairwise force law. This fills a gap in the Physics & Waves category:
the project had wave equations, electromagnetic fields, and quantum circuits, but no
classical statistical mechanics showing emergent phase transitions from first principles.

**New file:** `life/modes/molecular_dynamics.py` (~810 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Force law | Lennard-Jones 6-12 potential with cutoff at 2.5σ, minimum-image convention for periodic boundaries |
| Integration | Velocity-Verlet (symplectic, time-reversible, energy-conserving) |
| Thermostat | Berendsen-style velocity rescaling with gentle coupling (τ = 0.1) for smooth temperature control |
| Boundary conditions | Periodic (particles wrap around; forces use minimum-image convention) |
| Phase detection | Heuristic classification from temperature + radial distribution function peak structure |
| Pressure | Virial equation: P = (NkT + ½ Σ r·F) / V |
| Observables | KE, PE, total energy, temperature, pressure, RDF g(r), speed distribution histogram |

**6 presets:**

| Preset | Description |
|--------|-------------|
| Crystal Growth | Cold start (T=0.1, ρ=0.8) — particles freeze into hexagonal lattice |
| Melting Point | Crystal just above melting (T=0.75) — watch long-range order break down |
| Supercooling / Nucleation | Quench from random config (T=0.3, ρ=0.6) — crystal islands nucleate and grow |
| Triple Point | Near solid-liquid-gas coexistence (T=0.69, ρ=0.45) |
| Boiling | Liquid heated past boiling (T=1.5) — explosive evaporation |
| Gas / Ideal Gas | High temperature, dilute (T=3.0, ρ=0.15) — random ballistic motion |

**3 view modes:**

| View | What it shows |
|------|---------------|
| Particle field | Particles color-coded by kinetic energy (blue=cold through red=hot), using Unicode density characters (·∘○●◉★) |
| Energy plot | Temperature and KE/particle time series with scrolling history |
| RDF g(r) | Radial distribution function — sharp peaks = crystalline order, broad peaks = liquid, flat = gas |

**Interactive controls:** `↑`/`↓` adjust target temperature, `Space` pause/resume, `n` single step, `v` cycle views, `t` toggle thermostat, `+`/`-` simulation speed, `r` reset, `R` back to menu, `q` quit. Accessible via `Ctrl+Shift+M` from the mode browser under "Physics & Waves."

**Also changed:**
- `life/modes/__init__.py`: Added import and registration call for molecular_dynamics mode
- `life/registry.py`: Added registry entry under "Physics & Waves" category with `Ctrl+Shift+M` shortcut
- `life/app.py`: Added 8 state attributes, key dispatch block, draw dispatch block, and `moldyn_menu` to `_any_menu_open`

---

### Added: Tierra Digital Organisms — Self-Replicating Assembly Programs in Shared Memory

A new computational evolution mode inspired by Tom Ray's Tierra system (1990) — one
of the most famous experiments in artificial life. Tiny programs written in a 16-instruction
assembly language live in shared memory, copy themselves (with mutations), and evolve
parasitism, immunity, and symbiosis through natural selection. This fills a clear gap:
the project has biological evolution (`ecosystem_evolution.py`, `primordial_soup.py`),
genetic algorithms (`evolution_lab.py`), and neural approaches (`neural_ca.py`) — but
no **computational evolution** where the evolving entities are programs themselves. It
bridges the CS modes (sorting visualizer, quantum circuit) with the artificial life modes.

**New file:** `life/modes/tierra.py` (~580 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Instruction set | 16 opcodes: NOP0/1, FIND, MOV_H, COPY, INC, DEC, JMP, JMPZ, ALLOC, SPLIT, PUSH, POP, SWAP, CALL, RET |
| Self-replicating ancestor | ~35-instruction genome that finds its own boundaries via template matching, allocates daughter memory, copies itself in a loop, then divides |
| Template matching | Organisms locate code by searching for complement patterns (NOP0↔NOP1), enabling addressing without absolute jumps |
| Mutation | Copy errors during replication (configurable rate) + cosmic ray background radiation (random memory bit-flips) |
| Reaper queue | 3 strategies to reclaim memory when population limit is reached: oldest-first, largest-first, most-errors-first |
| Memory ownership | Owner array tracks which organism owns each memory cell; contiguous free blocks are found via random probe + linear scan fallback |
| Species identification | Genome hashing for automatic species classification and population tracking |

**5 presets:**

| Preset | Description |
|--------|-------------|
| Genesis | Single ancestor, low mutation — watch self-replicators fill memory |
| Cambrian Burst | High mutation — rapid diversification and speciation |
| Arms Race | Moderate mutation, reaper favors large genomes — size pressure |
| Parasite World | Tiny ancestor + high copy-error — parasites emerge fast |
| Symbiosis Lab | Two ancestor species seeded together — cooperation or war? |

**3 view modes:**

| View | What it shows |
|------|---------------|
| Memory grid | Colored character grid of shared memory — each organism's code in its species color, instruction pointers highlighted with reverse video, free memory shown as dim dots |
| Stats | Population statistics, species breakdown with bar charts, population & diversity sparkline history |
| Phylo | Genome length histogram + sample organisms showing age, error count, and decoded genome preview |

**Interactive controls:** `Space` pause/resume, `n` single step, `+`/`-` speed, `v` cycle views, `m` mutation burst (20 cosmic rays), `r` manual reap, `↑`/`↓` scroll memory, `q` quit. Accessible via `Ctrl+Shift+T` from the mode browser under "Procedural & Computational."

**Also changed:**
- `life/modes/__init__.py`: Added import and registration call for tierra mode
- `life/registry.py`: Added registry entry under "Procedural & Computational" category

---

### Upgraded: L-System Fractal Garden — Botanical Morphogenesis with Seasons, Wind, Mutation & Light Competition

Massive overhaul of the L-System mode from a basic plant grower into a full botanical
ecosystem simulator. Plants now grow from formal Lindenmayer system grammars through
seasonal cycles (spring sprouting → summer bloom → autumn leaf-fall → winter dormancy),
compete for light via canopy overlap, reproduce through wind-dispersed seeds with
genetic mutation, and bend under sinusoidal wind forces. This bridges the gap between
the project's fractal modes (`fractal_explorer.py`, `ifs_fractals.py`) and its biological
simulations (`ecosystem_evolution.py`, `primordial_soup.py`) — modeling botanical
morphogenesis via the formal grammar rewriting systems that are the canonical method
for procedural plant generation in generative art.

**Rewritten file:** `life/modes/lsystem.py` (~855 lines, up from ~478)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| L-system grammars | Lindenmayer rewriting rules with turtle graphics interpretation — `F` draw, `+`/`-` turn, `[`/`]` push/pop state |
| 12 species library | Binary tree, fern, bush, seaweed, willow, pine, sakura, bonsai, alien tendril, coral, vine, cactus — each with unique grammar, branching angle, colors, and flowering/deciduous traits |
| Seasonal cycles | 4 seasons auto-advance every 30 steps: spring sprouts seeds, summer triggers flowering, autumn drops leaves as animated particles, winter kills weak plants and shows bare branches |
| Wind simulation | Sinusoidal bending force that scales with branch height, with natural fluctuation over time — adjustable from keyboard |
| Genetic mutation | Randomizes branching angle, length scale, and occasionally rewrites grammar rules during seed reproduction — produces novel morphologies over generations |
| Light competition | Per-column canopy overlap calculation; shaded plants lose health and grow slower, eventually dying — drives ecological dynamics |
| Seed dispersal | Mature healthy plants drop seeds that queue for next spring, with proximity checks to prevent crowding |
| Fallen leaf particles | Animated leaf-fall during autumn with wind-driven horizontal drift and time-to-live decay |

**13 presets:**

| Preset | Description |
|--------|-------------|
| Binary Tree | Symmetric branching tree structure |
| Fern | Naturalistic fern with curving fronds |
| Bush | Dense bushy shrub with many branches |
| Seaweed | Swaying underwater kelp strands |
| Willow | Drooping willow tree with long tendrils |
| Pine | Coniferous tree with short angled branches |
| Sakura | Cherry blossom tree with spring flowers |
| Bonsai | Carefully shaped miniature tree |
| Garden | Multiple species competing for light |
| Alien Flora | Exotic extraterrestrial vegetation with mutation |
| Competition | 7 species battle for light — survival of fittest |
| Coral Reef | Underwater coral and seaweed colony |
| Desert | Sparse cacti in arid landscape |

**Interactive controls:** `Space` play/pause, `n` single step, `w`/`W` decrease/increase wind, `s` advance season, `S` toggle auto-seasons, `m` toggle mutation, `a`/`A` adjust angle, `g`/`G` adjust growth rate, `←`/`→` light direction, `<`/`>` speed, `r` reset, `R` preset menu, `q` quit. Accessible via `/` from the main menu under "Fractals & Chaos."

**Also changed:**
- `life/app.py`: Added `LSYSTEM_PRESETS` class constant and 8 new state variables for wind, seasons, mutation, seed queue, and fallen leaves
- `life/registry.py`: Renamed mode to "L-System Fractal Garden" with updated description

---

### Added: Quantum Circuit Simulator & Visualizer — Interactive Quantum Computing in ASCII

A full quantum circuit simulator and visualizer where users build and simulate quantum
circuits in the terminal. A pure-Python state vector engine supports single- and
multi-qubit gates (H, X, Y, Z, S, T, CNOT, CZ, CP, SWAP, M), with measurement
triggering probabilistic wavefunction collapse. Per-qubit states are rendered as mini
Bloch sphere projections on the XZ plane, entanglement is detected via reduced density
matrix purity and highlighted with colored link indicators, and a running histogram
accumulates measurement statistics across hundreds or thousands of shots. This fills
the gap between `quantum_walk.py` (random walks on graphs) and the project's deep
coverage of physics — bringing actual quantum computation to life in the terminal and
strengthening the underdeveloped CS/computing category.

**New file:** `life/modes/quantum_circuit.py` (~798 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| State vector simulation | Full 2^n complex amplitude vector, gates applied via bit-manipulation loops — no external dependencies |
| Single-qubit gates | H (Hadamard), X/Y/Z (Pauli), S (π/2 phase), T (π/4 phase) — all implemented as in-place transforms |
| Multi-qubit gates | CNOT/CX (controlled-NOT), CZ (controlled-Z), CP (controlled-phase with arbitrary angle), SWAP |
| Measurement | Probabilistic wavefunction collapse — computes Born-rule probabilities, samples outcome, renormalizes |
| Bloch spheres | Per-qubit reduced density matrix → θ,φ angles → XZ-plane projection rendered as ASCII circle with `*` pointer |
| Entanglement detection | Computes purity of each qubit's reduced state; purity < 0.99 flags entanglement; pairs highlighted with colored indicators |
| Circuit diagram | Wire-based ASCII rendering with `[H]`, `[●]`, `[⊕]`, `[M]` symbols, vertical `│` connections for multi-qubit gates, color-coded progress (done/current/pending) |
| Probability bars | `█░` bar charts showing amplitude probabilities for each basis state |
| Measurement histogram | Run 100 or 1000 shots of the full circuit; `▓░` histogram with counts and percentages |

**6 presets:**

| Preset | Description |
|--------|-------------|
| Bell State \|Φ+⟩ | H + CNOT → (|00⟩+|11⟩)/√2 — maximal 2-qubit entanglement |
| GHZ State | 3-qubit H + CNOT chain → tripartite entanglement (|000⟩+|111⟩)/√2 |
| Quantum Teleportation | Teleport |1⟩ from q0 to q2 via Bell pair + classical-controlled corrections |
| Deutsch-Jozsa (3-qubit) | Single oracle query determines constant vs balanced — 4-qubit circuit with balanced oracle |
| Grover's Search (2-qubit) | Amplitude amplification finds marked state |11⟩ with high probability |
| Quantum Fourier Transform | 3-qubit QFT of |4⟩ using controlled-phase gates and SWAP |

**Interactive controls:** `Space` auto-run toggle, `n` single-step, `f` run all remaining gates, `m` measure ×100 shots, `M` measure ×1000 shots, `r` reset circuit, `R` return to preset menu, `+`/`-` adjust speed, `q` quit. Accessible via `Ctrl+Q` from the main menu under "Procedural & Computational."

---

### Added: Primordial Soup / Origin of Life — Abiogenesis Simulation

An abiogenesis simulation where simple molecules spontaneously form self-replicating
polymers near hydrothermal vents, lipid membranes self-assemble into vesicles, primitive
metabolism emerges from autocatalytic cycles, and competing protocells undergo Darwinian
selection — the transition from chemistry to biology. This fills the narrative gap
between the existing Chemical modes (reaction-diffusion, BZ reaction, artificial
chemistry) and the Biological modes (coral reef, ecosystem evolution), modeling how
life begins from raw chemistry.

**New file:** `life/modes/primordial_soup.py` (~889 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Energy gradients | Hydrothermal vents radiate energy that decays with distance — drives all reactions |
| Mineral → monomer | Dissolved minerals convert to organic monomers near energy sources |
| Polymerization | Monomers near other monomers + energy spontaneously form polymer chains |
| Replication | Polymers near other polymers/replicators undergo autocatalysis → self-replicating RNA-like molecules |
| Lipid assembly | Lipids self-assemble into vesicles when enough neighbors cluster together |
| Protocell formation | Vesicles that capture replicators become protocells with metabolism and energy budgets |
| Protocell division | Protocells split when energy exceeds threshold; daughter inherits genome with possible mutation |
| Darwinian selection | Fitness mutations during division — fitter protocells metabolize more efficiently, outcompete neighbors |
| Environmental controls | Temperature modifies reaction rates; UV creates/destroys molecules; ice concentrates organics via freeze-thaw |
| Nutrient recycling | Dead matter decomposes back into minerals and monomers |

**12 cell types:** water, rock, hydrothermal vent, mineral, monomer, polymer, replicator, lipid, vesicle, protocell, dead matter, ice.

**6 presets:**

| Preset | Description |
|--------|-------------|
| Hydrothermal Vent Field | Black smoker chimneys pour energy and minerals into the deep — classic abiogenesis |
| Warm Little Pond | Darwin's warm little pond — shallow, UV-irradiated, wet-dry cycling |
| Volcanic Tidepool | Geothermally heated tidepool with mineral-rich volcanic rock and UV exposure |
| Deep Ocean Seep | Cold methane seep on the abyssal plain — slow, steady chemistry |
| Frozen Comet Lake | Ice-covered lake with freeze-thaw cycles concentrating organics in eutectic veins |
| Chemical Garden | Semipermeable mineral chimneys with strong pH gradients — proton-motive abiogenesis |

**3 view modes:** soup (main simulation), energy (heat map of energy gradients), density (molecular complexity highlighting).

**Interactive controls:** `Space` play/pause, `n` single step, `v` cycle views, `h` heat burst (+15°C), `c` cool down (-15°C), `l` lightning strike (spawn monomers), `M` mineral injection, `u` toggle UV, `+`/`-` speed, `r` reset, `R` preset menu, `q` quit. Accessible via `Ctrl+Shift+P` from the main menu under "Chemical & Biological."

---

### Added: Neural Network Training Visualizer — Watch a Neural Network Learn in Real Time

A real-time ASCII visualization of a small neural network learning classification and
regression tasks. A pure-Python feed-forward network (`_MiniNet`) implements forward
pass, backpropagation, and SGD weight updates with no external dependencies. Three
visualization panels show the learning process from complementary angles: a network
diagram with color-coded neuron activations and animated gradient flow pulses along
weight connections, a 2D decision boundary heatmap that reshapes in real time as the
network learns, and loss/accuracy sparkline charts tracking training progress. This
fills the gap between `neural_ca.py` (neural cellular automata) and
`spiking_neural.py` (biological neurons) — visualizing the core machine-learning
training loop itself as a living animation.

**New file:** `life/modes/nn_training.py` (~790 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Neural network | Pure-Python `_MiniNet` class — feed-forward with backprop, Xavier init, configurable activations (sigmoid/relu/tanh) |
| Forward pass | Layer-by-layer matrix multiply with activation; softmax on multi-class output layers |
| Backpropagation | Output deltas (MSE for binary, cross-entropy for multi-class) propagated through hidden layers |
| Gradient flow viz | Weight connections colored by sign (green=positive, red=negative), animated `»`/`«` pulses proportional to gradient magnitude |
| Neuron rendering | Activation mapped to glyphs (`○◐◑●`) and colors (blue→cyan→green→yellow→red→white) |
| Decision boundary | 2D heatmap sampled across input space, updated every frame, with training data points overlaid |
| Loss/accuracy curves | Rolling sparkline bar charts showing training convergence over time |
| Data generators | Six task generators: XOR, spiral (3-class), circle, two-moons, sine regression, Gaussian clusters |

**6 presets:**

| Preset | Description |
|--------|-------------|
| XOR Gate | 2-2-1 network learns exclusive-or with sigmoid activation |
| Spiral Classification | 2-8-8-3 network separates three interleaved spirals (multi-class) |
| Circle Decision | 2-4-1 network learns inside-vs-outside circle boundary |
| Two Moons | 2-6-4-1 network separates crescent-shaped clusters |
| Sine Regression | 2-8-4-1 network fits a sine curve |
| Gaussian Clusters | 2-8-4-3 network classifies three Gaussian blobs (multi-class) |

**4 view modes:** all panels (default), network only, decision boundary only, loss curve only.

**Controls:** `Space` play/pause, `n` single step, `v` cycle views, `+`/`-` speed, `[`/`]` adjust learning rate, `r` reset, `R` preset menu, `q` quit. Accessible via `Ctrl+Shift+N` from the main menu under "Procedural & Computational."

---

### Added: Mycelium Network / Wood Wide Web — Underground Fungal Network Simulation

A side-view underground simulation of fungal mycorrhizal networks — the hidden
infrastructure of terrestrial ecosystems. Hyphae branch and spread through soil,
connect to tree roots via mycorrhizal junctions, and shuttle nutrients (carbon,
phosphorus, nitrogen) between trees. Older "mother trees" become network hubs
that send emergency nutrient transfers to stressed neighbors. Decomposers break
down fallen organic matter, releasing nutrients back into the soil. Seasonal
cycles drive growth, dormancy, and fruiting. This fills the gap between the
molecular scale (Artificial Chemistry) and the ecosystem scale (Coral Reef,
Ecosystem Evolution) — modeling the mutualistic underground network that
sustains forest ecosystems.

**New file:** `life/modes/mycelium.py` (~1060 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Soil layers | Surface, topsoil, subsoil, clay, and rock with depth-varying moisture profiles |
| Hyphal growth | Branching/spreading hyphae weighted by moisture, nutrients, and season — form thick hubs at junctions |
| Mycorrhizal connections | Form where hyphae meet root tips — bidirectional nutrient exchange interfaces |
| Root tip growth | Active root tips grow toward moisture and nutrients through soil |
| Nutrient packets | Mobile carbon (tree→fungus), phosphorus & nitrogen (fungus→tree), distress signals, and water drops flow along the network |
| Mother tree behavior | Mature trees with many connections become hubs — detect neighbor distress and send emergency nutrient transfers |
| Decomposition | Organic matter (fallen leaves, wood) breaks down over time, releasing nutrients into surrounding soil |
| Nutrient diffusion | Nutrients spread through soil layers via diffusion |
| Seasonal cycles | Spring growth surge, summer steady-state, autumn leaf fall and mushroom fruiting, winter dormancy and die-back |
| Fruiting bodies | Mushrooms emerge on the surface in autumn or high-moisture conditions, release spores that drift and colonize |
| Hyphal die-back | Drought and winter conditions cause peripheral hyphae to retract |

**6 presets:**

| Preset | Description |
|--------|-------------|
| Old-Growth Forest | Mature forest with deep mycelial networks and established mother trees |
| Young Plantation | Recently planted trees — watch mycorrhizal networks develop from scratch |
| Drought Stress | Dry conditions stress trees — watch the network shuttle emergency water |
| Fallen Giant | A large tree has fallen — decomposers feast and nutrients redistribute |
| Nutrient Hotspot | Mineral-rich soil patch drives intense fungal competition and growth |
| Four Seasons | Watch the network through seasonal cycles — growth, fruiting, dormancy |

**3 view modes:** network (default — cell types with color), moisture heatmap, nutrient heatmap.

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `w` rain, `d` drought, `o` drop organic matter, `s` advance season, `+`/`-` speed, `r` reset, `R` preset menu, `q` quit. Accessible via `Ctrl+Shift+W` from the main menu under "Chemical & Biological."

---

### Added: Ecosystem Evolution & Speciation — Landscape-Scale Macro-Evolution Simulation

Simulates landscape-scale macro-evolution where populations evolve across varied biomes,
speciate through geographic isolation (allopatric) and niche divergence (sympatric), develop
novel traits via mutation and recombination, compete for ecological niches, form emergent food
webs, and go extinct under environmental pressure. A real-time phylogenetic tree is rendered
alongside the spatial map showing species branching, radiation events, and mass extinctions.
This fills the "macro-evolution" gap between the individual-scale Artificial Life Ecosystem
and the human-scale Civilization mode, completing the biological hierarchy from chemistry
(Artificial Chemistry) → cells (Morphogenesis) → immune systems → **species & speciation** →
civilizations.

**New file:** `life/modes/ecosystem_evolution.py` (~1300 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Terrain generation | Value-noise heightmap producing 10 biome types: ocean, grassland, forest, desert, tundra, mountain, river, swamp, reef, volcanic |
| Trophic levels | 4 levels (producer, herbivore, predator, apex) with emergent food webs and trophic-level shifts |
| Evolvable traits | 8 traits (size, speed, camouflage, cold/heat tolerance, aquatic, aggression, fertility) that mutate and drive natural selection |
| Allopatric speciation | Geographically isolated populations diverge into new species when trait distance exceeds threshold |
| Sympatric speciation | Niche divergence across biomes creates new species; occasional trophic-level shifts |
| Population dynamics | Fitness-based reproduction and mortality varying by biome — competition and niche specialization emerge naturally |
| Mass extinction events | Configurable cataclysms that wipe ~70% of populations, followed by adaptive radiation into empty niches |
| Continental drift | Ocean barriers form mid-simulation, splitting populations and triggering allopatric speciation |
| Phylogenetic tree | Real-time tree displayed alongside the spatial map showing branching, extinction markers (†), and trophic symbols |

**6 presets:**

| Preset | Description |
|--------|-------------|
| Continental Drift | Two landmasses drift apart — allopatric speciation accelerates |
| Island Archipelago | Scattered islands each become evolutionary labs — Darwin's finches writ large |
| Adaptive Radiation | Single ancestral species colonizes an empty world — explosive diversification |
| Mass Extinction & Recovery | Rich ecosystem hit by cataclysm — survivors radiate into empty niches |
| Pangaea Supercontinent | One vast landmass — species spread freely, competition fierce |
| Random Landscape | Fully randomized terrain, species, and evolutionary parameters |

**4 view modes:** species (trophic symbols colored by species), biome (terrain), fitness (heatmap), food web (trophic-level coloring with interaction highlights).

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `l` toggle event log, `+`/`-` steps per frame, `r` reset, `R` preset menu, `q` quit. Accessible via `Ctrl+Shift+E` from the main menu under "Chemical & Biological."

---

### Added: Civilization & Cultural Evolution — Macro-Historical Simulation with Emergent Civilizations

Simulates a procedurally-generated world where tribes emerge on varied terrain, develop
technologies, establish trade routes, wage wars, and compete for resources. Cultural traits
diffuse across populations through settlement influence, civilizations rise and fall through
conquest and famine, and diplomacy shifts dynamically between trade partnerships and warfare.
This fills a clear gap at the macro-historical scale — the project had deep coverage of natural
sciences (physics, biology, chemistry, ecology) and individual economic agents (stock market),
but nothing where entire civilizations emerge, interact, and collapse over generational time.
The mode synthesizes terrain generation, agent-based modeling, diffusion dynamics, and game
theory into a single narratively rich simulation.

**New file:** `life/modes/civilization.py` (~1050 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Terrain generation | Value-noise heightmap producing 10 terrain types: water, plains, forests, hills, mountains, deserts, rivers, coasts, tundra, jungle |
| Agent-based tribes | Each tribe has population, resources (food/gold/production), cultural traits, tech tree progress, territory, and diplomacy state |
| Tech tree | 20-node tree from Fire and Tool-Making through Agriculture, Bronze Working, Navigation, Gunpowder, and Printing Press — each with gameplay effects |
| Cultural traits | 10 traits (Warlike, Peaceful, Nomadic, Agrarian, Mercantile, Religious, Artistic, Scientific, Expansionist, Isolationist) with diffusion from settlements |
| Diplomacy | Trade partnerships form between adjacent peaceful/mercantile tribes; war declarations based on aggression, population ratio, and traits; peace treaties and conquest |
| Resource economy | Per-tile food/gold/production yields modified by tech bonuses and cultural traits; trade income from partnerships |
| Territory | Tribes expand into unclaimed adjacent land; border conflicts transfer cells between warring tribes |
| Cultural diffusion | Trait influence radiates from settlements; tribes near strong foreign culture may adopt new traits |

**6 presets:**

| Preset | Description |
|--------|-------------|
| Pangaea | One large continent — early conflict and rapid tech diffusion |
| Archipelago | Scattered islands — navigation key, isolated cultures diverge |
| River Valleys | Fertile river basins — agriculture blooms, dense populations |
| Tundra & Steppe | Harsh northern plains — nomadic herders, slow development |
| Fertile Crescent | Central fertile zone ringed by desert & mountains — cradle of civilization |
| Random World | Fully randomized terrain and starting conditions |

**4 view modes:** political (territory ownership with settlement markers), terrain (raw heightmap-derived terrain), culture (dominant cultural trait influence), trade (active trade partnerships highlighted).

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `l` toggle event log, `+`/`-` steps per frame, `r` reset, `R` preset menu, `q` quit. Accessible via `Ctrl+Shift+V` from the main menu under "Game Theory & Social."

---

### Added: Coral Reef Ecosystem — Multi-Species Marine Ecosystem with Bleaching Cascades

Simulates a coral reef with multi-trophic interactions, habitat engineering, and environmental
stressors. Coral polyps grow branching and massive structures powered by symbiotic zooxanthellae
photosynthesis, herbivorous fish and sea urchins graze competing algae, predators patrol, and
crown-of-thorns starfish outbreaks can devastate the reef. Ocean warming triggers thermal
bleaching cascades (zooxanthellae expulsion), while acidification dissolves coral skeletons.
Recovery dynamics emerge from coralline algae facilitating coral recruitment and larval
settlement events. This fills a clear ecological niche — the project had single-organism
biology (morphogenesis, immune system) and simple predator-prey (Lotka-Volterra), but no
rich multi-trophic ecosystem with habitat engineering and environmental forcing.

**New file:** `life/modes/coral_reef.py` (~580 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Cell types | 12 types: branching coral, massive coral, bleached coral, dead coral skeleton, turf algae, macroalgae, coralline algae (CCA), sand, rock, sponge, anemone, water |
| Mobile entities | 7 types: herbivorous fish, predators, cleaner wrasse, crown-of-thorns starfish (COTS), sea urchins, sea turtles, plankton |
| Zooxanthellae symbiosis | Per-cell symbiont density drives photosynthetic energy gain; thermal stress expels symbionts, triggering bleaching |
| Light zonation | Depth-dependent light attenuation — branching coral dominates shallow zones, massive coral in deeper areas |
| Algae-coral competition | Turf and macroalgae spread on dead coral and smother live coral; herbivore grazing keeps algae in check |
| COTS outbreaks | Crown-of-thorns starfish consume live coral; reproduce faster in high-nutrient conditions |
| Ocean acidification | Low pH dissolves coral skeletons and inhibits calcification, compounding thermal stress |
| Coral recruitment | Coralline algae (CCA) facilitates new coral settlement; periodic larval recruitment events |

**6 presets:**

| Preset | Description |
|--------|-------------|
| Healthy Reef | Thriving coral with balanced trophic levels and clear water |
| Bleaching Event | Rising ocean temperatures trigger mass coral bleaching |
| Algal Takeover | Overfishing removes herbivores — algae smother the reef |
| Recovery | A damaged reef slowly recovering via coral recruitment |
| Crown-of-Thorns Outbreak | Coral-eating starfish population explosion devastates the reef |
| Acidification Crisis | Falling pH dissolves coral skeletons and inhibits calcification |

**3 view modes:** reef (normal ecosystem view with depth-tinted water), light (depth zonation showing photosynthetically available radiation), health (coral vitality heatmap showing health and zooxanthellae density).

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `h` heat wave, `c` cooling,
`f` release herbivorous fish, `N` nutrient pulse, `+`/`-` steps per frame, `r` reset,
`R` preset menu, `q` quit. Accessible via `Ctrl+Shift+R` from the main menu under
"Chemical & Biological."

---

### Added: Agent-Based Stock Market — Emergent Bubbles, Crashes & Price Discovery

Simulates a financial market populated by heterogeneous trader agents competing on a
limit order book. Fundamentalists trade toward fair value, chartists chase momentum,
noise traders act on herd sentiment, and market makers provide two-sided liquidity.
Price dynamics — bubbles, crashes, flash crashes, and mean-reversion — emerge naturally
from agent interactions rather than being scripted. This fills out the Game Theory & Social
category (previously the thinnest with only 3 modes) with something visually rich and
dynamically fascinating: complex market phenomena arising from simple agent rules.

**New file:** `life/modes/stock_market.py` (~950 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Agent types | 4 types: fundamentalists (value investors), chartists (trend followers), noise traders (herd-driven random), market makers (two-sided liquidity) |
| Limit order book | Bid/ask order matching each tick — agents submit limit orders based on their strategy |
| Price discovery | Last trade price from order book matching; random walk on fundamental value provides a moving anchor |
| Sentiment dynamics | Per-agent sentiment updated by strategy logic; global sentiment averaged across all agents influences herd behavior |
| Momentum tracking | Chartists compute recent returns over a lookback window to detect trends |
| OHLCV candles | Ticks aggregated into open/high/low/close/volume candles for charting |
| Wealth tracking | Per-agent cash + shares × price; wealth history recorded for visualization |

**6 presets:**

| Preset | Description |
|--------|-------------|
| Bull Run | Strong fundamentalist demand drives steady uptrend |
| Flash Crash | Chartist feedback loop triggers sudden collapse |
| Bubble & Pop | Herd mania inflates a bubble that eventually bursts |
| Efficient Market | Fundamentalists dominate — price tracks fair value |
| Herd Mania | Noise traders amplify sentiment waves |
| Market Maker Dominance | Market makers provide liquidity and stabilize spreads |

**4 view modes:** price chart (ASCII candlesticks with wicks, bodies, fundamental value line, and sparkline), order book depth (side-by-side bid/ask bar chart with spread display), agent wealth heatmap (grid of agents colored by type with intensity by wealth), sentiment map (agent sentiment visualization with bullish/bearish histogram).

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `+`/`-` steps per frame,
`<`/`>` speed, `r` reset, `R` preset menu, `q` quit. Accessible via `S` from the main
menu under "Game Theory & Social."

---

### Added: Immune System Simulation — Adaptive Immune Response with Pathogen Arms Race

Simulates a 2D spatial immune response: pathogens (bacteria/viruses) invade and replicate
while innate responders (macrophages, neutrophils) rush to infection sites via chemotaxis
on a diffusing cytokine gradient. Adaptive immune cells (T-cells, B-cells) recognize
pathogen antigen shapes using 6-bit Hamming-distance matching, proliferate via clonal
expansion on match, and form long-lived memory cells for faster secondary responses.
Pathogens mutate their antigens over time via bit-flips, driving an evolutionary arms race.
This completes a biological trifecta alongside the Morphogenesis and Artificial Chemistry
modes — the emergent coordination of immune cells from simple local rules is a natural fit
for a project exploring complexity from simplicity.

**New file:** `life/modes/immune_system.py` (~1040 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Entity types | 12 types: empty, tissue, infected tissue, bacteria, virus, macrophage, neutrophil, T-cell, B-cell, memory cell, antibody, debris |
| Cytokine gradient | Diffuses from infection sites across the grid — guides immune cell chemotaxis toward pathogens |
| Antigen/receptor matching | 6-bit antigen shapes with Hamming-distance similarity scoring — immune cells activate on high match |
| Innate immunity | Macrophages (long-lived phagocytes) and neutrophils (fast, short-lived killers) follow cytokine gradients |
| Adaptive immunity | T-cells kill on antigen match + clonal expansion; B-cells produce free antibodies + clonal expansion |
| Memory cells | Formed from activated T/B cells — reactivate rapidly on secondary exposure for faster clearance |
| Pathogen mutation | Antigens drift via random bit-flips, evading existing immune recognition — arms race dynamics |
| Bone marrow reinforcements | Innate cells replenished from edges when infection is detected |

**5 presets:**

| Preset | Description |
|--------|-------------|
| Bacterial Invasion | Bacteria flood in and replicate — innate immunity scrambles to contain |
| Viral Outbreak | Viruses infect tissue cells, hijack replication — adaptive response critical |
| Vaccination | Pre-seeded memory cells — watch the rapid secondary immune response |
| Autoimmune | Immune cells mistakenly attack healthy tissue — friendly fire |
| Cytokine Storm | Runaway positive feedback — immune overreaction causes collateral tissue damage |

**3 view modes:** cells (color-coded by entity type), cytokine heatmap (gradient intensity), antigen map (pathogen diversity).

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `p` inject pathogens,
`i` immune boost, `u` force pathogen mutation, `+`/`-` speed, `r` reset, `R` preset menu,
`q` quit. Accessible via `Ctrl+Shift+I` from the main menu under "Chemical & Biological."

---

### Added: Artificial Chemistry — Spontaneous Emergence of Self-Replicating Molecules

Simulates a primordial soup of abstract molecules that drift, collide, and react via
pattern-matching rules. Cells represent string-based molecules (sequences from an 8-letter
alphabet A–H) that undergo concatenation, cleavage, template-directed replication, and
catalysis. Over time, autocatalytic cycles form — sets of molecules that catalyze each
other's production — and occasionally genuine self-replicators emerge from the noise. This
is the natural next frontier for a project exploring emergent complexity: watching the
origin of life itself, one reaction at a time.

**New file:** `life/modes/artificial_chemistry.py` (~800 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Molecules | String-based (alphabet A–H, max length 16) — monomers, short polymers, long polymers, catalysts, replicators |
| Drift/diffusion | Molecules move randomly across the grid, simulating Brownian motion in the soup |
| Concatenation | Two adjacent molecules join end-to-end if combined length ≤ 16 and sufficient energy |
| Cleavage | Long molecules spontaneously split at random points, producing fragments |
| Template replication | Molecules ≥ 3 chars act as templates — produce complement copies (A↔E, B↔F, C↔G, D↔H) with mutation |
| Catalysis | Molecules with complement-matching subsequences catalyze transformation of neighbors |
| Autocatalytic cycles | Periodic scan of the catalytic network detects cycles of length 2–4 where molecules catalyze each other's production |
| Self-replicator detection | Template replication that produces true complements marks molecules as replicators |
| Energy system | Per-cell energy that decays over time — molecules with no energy degrade, food injected at edges |
| Clustering | Optional hydrophobic attraction — long molecules pull nearby monomers toward them (Lipid World preset) |

**8 presets:**

| Preset | Description |
|--------|-------------|
| Primordial Soup | Random monomers in warm broth — watch for spontaneous polymerization |
| Rich Broth | Dense soup with high reactivity — fast polymer formation |
| Sparse Tidepools | Low density pools — rare but significant encounters |
| RNA World | Template-directed replication dominates — origin of information |
| Metabolism First | Catalytic cycles before replication — energy-driven self-organization |
| Lipid World | Hydrophobic clustering — molecules aggregate into proto-cells |
| Volcanic Vent | Energy-rich environment with rapid turnover and high mutation |
| Minimal Abiogenesis | Fewest assumptions, maximum emergence |

**3 view modes:** soup (color-coded by molecule type/length), energy (heatmap), diversity (colored by first character).

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `e`/`E` reactivity,
`f`/`F` food rate, `u`/`U` mutation rate, `+`/`-` speed, `r` reset, `R` preset menu,
mouse-click to drop molecules, `q` quit. Accessible via `Ctrl+Shift+C` from the main
menu under "Chemical & Biological."

---

### Added: Morphogenesis — Embryonic Development from a Single Cell

Simulates biological embryonic development: a single fertilized "egg" cell divides,
differentiates, and self-organizes into a complex multicellular organism using morphogen
gradients, gene regulatory networks, and local cell-cell signaling. Each cell carries a
heritable genome controlling division rules, differentiation responses, morphogen production,
adhesion, and apoptosis — with mutation on division. This is the first mode to simulate the
developmental biology process of morphogenesis, turning the project's existing chemical and
biological themes (reaction-diffusion, chemotaxis, evolution) into a unified developmental
narrative where structured complexity emerges from ONE cell.

**New file:** `life/modes/morphogenesis.py` (~760 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Cell types | 7 types: stem, ectoderm, mesoderm, endoderm, neural, signaling center, apoptotic — each with distinct ASCII character and color |
| Genome | Per-cell heritable parameters: division rate, nutrient threshold, morphogen A/B production, differentiation thresholds, adhesion, apoptosis rate, mutation rate |
| Morphogen gradients | Dual fields (A and B) that diffuse, decay, and are produced by cells — drive differentiation decisions (high A → ecto, high B → endo, both → meso) |
| Nutrient field | Diffusing resource that cells consume — limits growth, creating natural size constraints |
| Division | Probability-based with nutrient gating, crowding limits, and growth slowdown at large population — daughter inherits mutated genome |
| Differentiation | Stem cells differentiate based on local morphogen concentrations crossing genome-encoded thresholds |
| Apoptosis | Programmed cell death shaped by crowding, nutrient starvation, and spatial sculpting for body boundaries |
| Organiser centers | Signaling cells placed strategically to establish body axes via high morphogen production |

**8 presets:**

| Preset | Description |
|--------|-------------|
| Radial Embryo | Single egg — radial symmetry, layered germ layers |
| Bilateral Body Plan | Left-right symmetry axis with dorsal organiser |
| Gastrulation | Invagination — cells fold inward to form gut tube |
| Neural Tube Formation | Dorsal ectoderm folds to create neural crest |
| Limb Bud Outgrowth | Outgrowth from a body wall with ZPA signaling |
| Regeneration | Cut in half at gen 100 — watch it regrow missing tissue |
| Somitogenesis | Segmented body plan via oscillating morphogen clock |
| Minimal Egg | Bare-bones: one cell, no organiser, pure emergence |

**4 view modes:** cells (colored by type), morphogen-A heatmap, morphogen-B heatmap, nutrient heatmap.

**Controls:** `Space` play/pause, `n` step, `v` cycle views, `u`/`U` mutation rate,
`f`/`F` nutrient rate, `+`/`-` speed, `r` reset, `R` preset menu, mouse-click to place
stem cells, `q` quit. Accessible via `Ctrl+Shift+M` from the main menu under "Chemical &
Biological."

---

### Added: Self-Modifying Rules CA — Cells Carry Their Own Evolving Rule DNA

A cellular automaton where rules aren't global — they live *inside* the cells. Each living cell
has its own birth/survival ruleset encoded as a pair of 9-bit integers (a "genome"). When a dead
cell is born, it inherits the majority neighbor's genome, possibly mutated. Living cells survive
or die by their own rules, not a shared one. Regions with different rules form competing species
that expand, contract, and coevolve — producing emergent speciation, ecological niches, and arms
races without any external fitness function.

This creates a genuinely new level of emergence: not just patterns from rules, but **rules from
rules**. It connects the project's themes of evolution (Evolution Lab), competition (Battle
Royale), and rule exploration into a single self-organizing system.

**New file:** `life/modes/self_modifying_rules.py` (~610 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Genome | Pair of 9-bit integers: `(birth_bits, survival_bits)` — bit *i* set means neighbor count *i* triggers |
| Birth | Dead cell with enough live neighbors inherits majority neighbor's genome (possibly mutated) |
| Survival | Live cell checks its *own* survival rule — no global rule |
| Mutation | Per-birth chance to flip random bits in the genome, creating new species |
| Species coloring | Hash of genome → 8 color slots with age-based brightness |

**8 presets:**

| Preset | Description |
|--------|-------------|
| Life vs HighLife | Two species: B3/S23 vs B36/S23 compete head-to-head |
| Three Kingdoms | Life, Day&Night, and Seeds in a 3-way territorial battle |
| Mutation Storm | Start with Life but high mutation (0.08) creates rapid speciation |
| Sparse Ecology | Low density, low mutation — fragile ecosystems form slowly |
| Cambrian Explosion | 8 random seed species with moderate mutation |
| Arms Race | Aggressive vs defensive rules under high mutation pressure |
| Single Seed | One species diversifies through mutation alone |
| Blank Canvas | Every cell gets a random genome — pure emergence from chaos |

**Info panel shows:** generation, population, species count, peak species, top 8 species with
color-coded genome labels (e.g. `B3/S23`), diversity sparkline, and population sparkline.

**Controls:** `Space` play/pause, `n` step, `r` randomize, `+`/`-` mutation rate, `[`/`]`
steps per frame, `q` quit. Accessible via `Ctrl+Shift+G` from the main menu under "Meta Modes."

---

### Added: Graph-Based Cellular Automata — Game of Life on Arbitrary Network Topologies

Runs CA rules on non-grid structures where neighbor counts and connectivity patterns create
entirely new emergent dynamics. This is the natural generalization beyond flat grids and
non-Euclidean tilings — arbitrary graph topologies where a "glider" on a scale-free network
behaves nothing like one on a regular grid. Each topology produces fundamentally different
dynamics: hub nodes in scale-free networks dominate evolution, small-world rewiring creates
long-range correlations, and caveman graphs produce isolated cluster dynamics with rare
inter-community signaling.

**New file:** `life/modes/graph_ca.py` (~910 lines)

**8 network topologies:**

| Topology | Description |
|----------|-------------|
| Ring Lattice | Regular ring where each node connects to K nearest neighbors |
| Small-World (WS) | Watts-Strogatz: ring lattice with random rewiring (p=0.3) |
| Scale-Free (BA) | Barabási-Albert preferential attachment network |
| Random (ER) | Erdős-Rényi random graph with edge probability p |
| Star Graph | Central hub connected to all other nodes |
| Binary Tree | Complete binary tree structure |
| Grid 2D | Standard 2D lattice graph (for comparison with classic Life) |
| Caveman Graph | Clusters of cliques connected in a ring |

**8 CA rule presets:**

| Rule | Description |
|------|-------------|
| B3/S23 (Life) | Classic Conway's Game of Life rules |
| B2/S34 (Pulse) | Pulsing growth for high-degree nodes |
| B3/S234 (Coral) | Slow coral-like growth |
| B23/S3 (Sparse) | Sparse dynamics — hard to sustain |
| B1/S12 (Dense) | Very active — suited for low-degree graphs |
| B2/S23 (Spread) | Fast spreading with moderate survival |
| B34/S345 (Hardy) | Tough survivors on high-connectivity nets |
| B2/S∅ (Seeds) | Explosive — no survival, pure birth |

**Force-directed ASCII visualization:**
- Fruchterman-Reingold layout algorithm (O(n²) repulsion + edge attraction with temperature cooling)
- Node characters scale with degree (`@` for hubs ≥8, `#` ≥5, `O` ≥3, `o` low-degree)
- Age-based coloring (6 color tiers) for alive cells, dim structural markers for dead cells
- Bresenham-style edge drawing between connected nodes (togglable)

**Real-time metrics panel:**
- Alive ratio and population count
- Clustering coefficient (local, averaged)
- Average path length (estimated via BFS from random sample of 50 nodes)
- Average and max degree
- Population sparkline history (last 100 generations)
- Degree distribution mini-histogram

**Interactive controls:**
- Two-phase menu: topology selection → rule selection, with mini graph preview
- Simulation: `space` pause, `s` single-step, `r` randomize, `c` clear
- `n` cycle rules, `t` switch topology (rebuilds graph), `l` re-layout
- `e` toggle edge drawing, `m` toggle metrics panel
- `+`/`-` adjust node count (10–200), `q` quit
- Registered under "Classic CA" category with `G` hotkey

**Modified files:**
- `life/app.py` — 31 state variables in `__init__`, key handler dispatch (menu + simulation), draw dispatch
- `life/modes/__init__.py` — import and register `graph_ca`
- `life/registry.py` — registry entry under "Classic CA" with `G`

---

### Added: Hyperbolic Cellular Automata — Game of Life on the Poincaré Disk

Runs cellular automata on hyperbolic tilings rendered as a Poincaré disk in the terminal.
While the project already supports non-Euclidean topologies (torus, Klein bottle, Möbius strip,
projective plane), those are all fundamentally flat grids with edge identifications. Hyperbolic
geometry is genuinely curved — cells tile with exponentially growing neighborhoods, producing
emergent behavior impossible on Euclidean grids. Gliders curve, still lifes contend with more
neighbors, and the infinite branching structure creates visually striking ASCII art.

**New file:** `life/modes/hyperbolic_ca.py` (~640 lines)

**Hyperbolic geometry engine:**

| Component | Description |
|-----------|-------------|
| **Möbius transformations** | Translate points within the Poincaré disk model using `(z + a) / (1 + conj(a) * z)` |
| **Hyperbolic distance** | Correct center-to-center distance for `{p,q}` Schläfli symbol tilings via `acosh(1 + 2r²/(1-r²))` |
| **BFS tiling generator** | `_build_tiling(p, q, max_layers)` with spatial grid proximity deduplication to handle floating-point imprecision when cells are reached from different parent polygons |
| **Boundary clipping** | Cells beyond disk radius 0.96 are discarded to keep rendering clean |

**6 tiling presets ({p,q} Schläfli symbols):**

| Tiling | Description |
|--------|-------------|
| `{5,4}` Pentagonal | Order-4 — 4 pentagons meet at each vertex |
| `{7,3}` Heptagonal | Order-3 — 3 heptagons per vertex |
| `{4,5}` Square | Order-5 — 5 squares per vertex |
| `{3,7}` Triangular | Order-7 — 7 triangles per vertex |
| `{6,4}` Hexagonal | Order-4 — 4 hexagons per vertex |
| `{8,3}` Octagonal | Order-3 — 3 octagons per vertex |

**8 rule presets (tuned for higher neighbor counts):**

| Rule | Description |
|------|-------------|
| B3/S23 (Life) | Classic Life — sparse in hyperbolic space |
| B2/S34 (Pulse) | Pulsing growth adapted to high-neighbor tilings |
| B3/S234 (Coral) | Slow coral growth — stable structures |
| B35/S2345 (Bloom) | Lush expansion — fills the disk |
| B2/S23 (Spread) | Fast-spreading with classic survival |
| B3/S345 (Hardy) | Tough survivors — high-neighbor adapted |
| B23/S34 (Wave) | Wave-like expansion and contraction |
| B2/S (Seeds) | Explosive chaotic growth, no survival |

**Poincaré disk ASCII renderer:**
- Maps complex-plane cell positions to terminal coordinates with aspect ratio correction
- Conformal size scaling — cells shrink toward the disk boundary (`@` → `#` → `*` → `.`)
- Age-based coloring (6 color tiers)
- Disk border rendered with `·` characters

**Interactive controls:**
- Two-phase menu: tiling selection → rule selection, with mini Poincaré disk preview
- Simulation: `space` pause, `s` single-step, `r` randomize, `c` clear, `n` cycle rules, `t` cycle tilings, `+`/`-` speed
- Registered under "Classic CA" category with `Ctrl+H` hotkey

**Modified files:**
- `life/app.py` — 22 state variables in `__init__`, key handler dispatch (menu + simulation), draw dispatch
- `life/modes/__init__.py` — import and register `hyperbolic_ca`
- `life/registry.py` — registry entry under "Classic CA" with `Ctrl+H`

---

### Added: Ancestor Search / Reverse-Engineering Mode — find predecessors of any pattern and detect Garden of Eden states

Given any frozen grid state, this mode searches backwards through CA time to find predecessor
configurations — grids that evolve INTO the target pattern after one step. Uses stochastic
search (simulated annealing + genetic operators) and declares **Garden of Eden** patterns when
exhaustive search finds no possible predecessor. This tackles a genuinely hard problem in
cellular automata theory: the inverse of the forward simulation.

**New file:** `life/modes/ancestor_search.py` (~830 lines)

**Search engine:**

| Component | Description |
|-----------|-------------|
| **Simulated annealing** | Temperature-controlled acceptance of worse candidates to escape local optima |
| **Genetic operators** | Mutation (adaptive rate based on fitness) and single-point crossover with elite |
| **Population management** | 8 parallel candidates with periodic restarts (replace worst half) |
| **Garden of Eden detection** | After 200+ restarts and 500 exhaustive local tries, declares no-ancestor with confidence score |
| **Solution deduplication** | MD5-based hashing prevents duplicate ancestor discoveries |

**User interface:**

| Feature | Description |
|---------|-------------|
| **Preset menu** | 8 classic patterns (block, blinker, glider, beehive, toad, loaf, boat, r-pentomino) plus custom drawing and "use current grid" |
| **Pattern editor** | Draw custom targets with cursor movement (arrows/hjkl), space to toggle, c to clear |
| **3-panel visualization** | TARGET (left) \| BEST ANCESTOR (center) \| SOLUTION/EVOLVED (right) with mismatch counts |
| **Progress bar** | Real-time fitness display (matching cells / total cells) with generation and eval counters |
| **Solution browser** | h/l to browse multiple discovered ancestors, a to apply selected ancestor to main grid |

**Search controls:** Space (pause/resume), n (single step), r (restart), +/- (resize grid), q (quit)

**Integration:** Registered as "Ancestor Search" under Meta Modes with `Ctrl+Shift+A` keybinding.
Works with any B/S ruleset — inherits rules from the current grid configuration.

**Files modified:** `life/app.py` (state init + key/draw dispatch), `life/modes/__init__.py` (registration), `life/registry.py` (mode entry)

---

### Added: Time-Travel Timeline Branching — fork alternate timelines from any past frame and compare divergent evolution side-by-side

Pause any running simulation, scrub backward through its history, then fork an alternate
timeline from any past frame — change the rule, draw new cells, or keep everything the same —
and watch both the original and the branched timeline evolve side-by-side in a split view with
live divergence tracking. Answers questions like "what if I had removed that glider at frame 200?"
or "how would B36/S23 differ from B3/S23 starting from this exact configuration?"

Builds on the existing time-travel scrubbing (rewind/fast-forward through history), the compare
mode infrastructure (split-view rendering), and the analytics overlay (sparklines, metrics).

**New file:** `life/modes/timeline_branch.py` (~478 lines)

**Fork workflow:**
1. Run simulation to build up history
2. Press `u` or `[`/`]` to scrub back to any past frame
3. Press `Ctrl+F` to open the fork menu
4. Choose: fork with same rules (what-if same conditions) or fork with different rule (prompts for B.../S... string)
5. Both timelines evolve side-by-side in lockstep with live divergence metrics

**Split-view features:**

| Feature | Description |
|---------|-------------|
| **Dual grid rendering** | Original timeline on left, branch on right, separated by a vertical divider |
| **Per-panel labels** | Shows rule string, generation count, and population for each timeline |
| **Dual population sparklines** | Independent sparkline charts for each timeline's population history |
| **Fork point indicator** | Shows fork generation and elapsed generations since fork |
| **Live divergence metric** | Percentage of cells that differ between original and branch, with visual bar (█░) |
| **Status bar** | Play/pause state, speed, rule comparison, generations since fork |
| **Context-sensitive hints** | Key bindings shown in bottom bar |

**Key controls (in branch split-view):**
- **Space** — play/pause both timelines in lockstep
- **n / .** — single-step both timelines
- **< / >** — change simulation speed
- **Arrow keys** — scroll viewport
- **Ctrl+F** — exit branch view

**Fork menu** (`Ctrl+F` while scrubbed back in history):
- Fork with same rules — identical starting conditions, useful for comparing timeline evolution
- Fork with different rule — prompts for a B.../S... rule string to apply to the branch
- Cancel

**Integration points in `life/app.py`:**
- State initialization via `_tbranch_init()` in `__init__`
- Key handler dispatch (before time-travel handler in main loop)
- Branch grid stepping (alongside compare/race stepping)
- Draw dispatch (branch split-view before compare mode)
- Fork menu draw (alongside other menu draws)
- Help overlay and timeline bar updated with `Ctrl+F=fork` hint
- Fork menu added to `_any_menu_open()` list

### Added: Neural Cellular Automata — per-cell neural networks learn to self-organize into target patterns via evolutionary strategies

A new mode where cell update rules are defined by small neural networks instead of lookup tables,
enabling cells to *learn* to self-organize into target patterns. Inspired by Google's "Growing
Neural Cellular Automata" (Mordvintsev et al. 2020), but implemented entirely in pure Python
for the terminal — no NumPy or PyTorch dependency.

This is the natural complement to Evolution Lab's genetic algorithm approach: where Evolution Lab
uses random mutation to discover rules, Neural CA uses gradient-free optimization (evolutionary
strategies) to train a neural network that controls cell behavior. The result: users can draw
a target shape, press train, and watch cells learn to grow it from a single seed.

**New file:** `life/modes/neural_ca.py` (~530 lines)

**Neural network architecture (per cell):**

| Layer | Description |
|-------|-------------|
| **Perception** | 3×3 Sobel convolution (identity + X/Y gradients) across 3 state channels → 9 perception inputs |
| **Hidden** | 9→8 dense layer with ReLU activation |
| **Output** | 8→3 dense layer producing residual state updates |
| **Total** | 107 learnable parameters |

**Training via Evolution Strategies (ES):**
- Antithetic sampling for variance reduction (each perturbation paired with its negative)
- Configurable population size (4–32), learning rate, and noise sigma
- Each candidate grows from seed for N steps, then MSE loss against target is computed
- Gradient estimated from loss-weighted perturbations; parameters updated via gradient descent
- Best-ever parameters tracked and restorable mid-training

**7 target presets:** circle, square, diamond, cross, ring, heart, custom (drawable)

**Interactive drawing mode:** cursor-based target sketching with:
- Arrow keys to move cursor, Space to toggle cells
- Brush tool (f) for 3×3 painting, eraser mode (e), clear (c)

**3 view modes:** NCA state, target pattern, side-by-side comparison

**Live loss sparkline** reusing `_sparkline` from `life/analytics.py` — shows training
progress as a Unicode chart inline with the simulation.

**Key controls:**
- **t** — toggle training; **Space** — toggle inference run; **s** — single step
- **r** — reset state to seed (keep weights); **R** — full reinit (new random weights)
- **d** — enter drawing mode; **g** — grow from seed; **b** — load best parameters
- **p** — cycle target preset; **v** — cycle view mode; **+/-** — speed; **Esc** — exit

**Configurable parameters** (via settings menu):
- Target pattern (7 presets)
- Grid dimensions (8–50 height, 8–60 width)
- Grow steps per evaluation (5–100)
- ES population size (4–32)
- Learning rate (0.001–0.2)
- Sigma / noise scale (0.005–0.1)

**Integration points:**
- `life/app.py` — 20 state variables for NCA engine, draw dispatch (menu + simulation view), key dispatch, simulation stepping in run loop
- `life/modes/__init__.py` — module registration
- `life/registry.py` — mode browser entry under "Meta Modes" (key: Ctrl+Shift+N)

**Design decisions:**
- Pure Python matrix operations (no NumPy) to maintain the project's zero-heavy-dependency philosophy — the 107-parameter network is small enough that nested-list arithmetic runs at interactive speed for typical grid sizes
- Evolutionary strategies chosen over backpropagation because ES only needs forward passes, avoiding the complexity of implementing autodiff in pure Python
- Stochastic cell update mask (50% per step) prevents synchronization artifacts and encourages robust learned behaviors, matching the original paper's approach
- Alive masking ensures dead regions stay dead unless a neighbor is alive, preventing phantom growth
- Torus wrapping on the grid enables seamless edge behavior consistent with the project's topology support

### Added: Evolution Lab — Interactive Rule Evolution System that breeds CA rules via genetic algorithm to discover novel emergent behaviors

A new meta-mode that turns the simulator from a playground into a laboratory. A population of
cellular automata rulesets runs in parallel on a tiled grid, with fitness scored automatically
by the analytics metrics already in place (Shannon entropy, symmetry, population stability).
Each generation, top performers reproduce via crossover and mutation while weak rules are culled.
Users can manually "favorite" organisms to protect them from selection pressure — human intuition
guiding machine search.

This is a synthesis of three existing systems:
1. **Analytics metrics** (`life/analytics.py`) — entropy, symmetry, stability classification become the fitness function
2. **Rule parsing/genomes** (B/S notation, neighborhoods, multi-state) — the genetic representation
3. **Tiled multi-sim views** — parallel visualization of the population

The result: an automated discovery engine that finds surprising, beautiful rule combinations
no human would design by hand. After 109 hand-crafted modes, this lets the machine create
mode 110 and beyond.

**New file:** `life/modes/evolution_lab.py` (~1048 lines)

**Genetic algorithm components:**

| Component | Description |
|-----------|-------------|
| **Genome** | Birth/survival digit sets, neighborhood type (Moore/von Neumann), state count (2–5) |
| **Crossover** | Uniform crossover — each birth/survival digit independently inherited from either parent |
| **Mutation** | Configurable rate (0–100%); flips birth/survival digits, occasionally mutates neighborhood/states |
| **Fitness** | Weighted sum of entropy, symmetry, stability, longevity, and diversity scores |
| **Selection** | Rank-based: top elite + all favorites reproduce; rest are culled |

**5 fitness presets** optimizing for different aesthetics:
- **balanced** — equal weight across all metrics
- **beauty** — 3× symmetry weight for visually striking patterns
- **chaos** — 3× entropy weight for maximum disorder
- **complexity** — high entropy + diversity for edge-of-chaos phenomena
- **stability** — 3× stability weight for self-sustaining oscillators

**Configurable parameters** (via settings menu):
- Population size (4–20 organisms)
- Evaluation generations (50–500 simulation steps per organism)
- Mutation rate (0–100%)
- Elite survivor count (how many top performers breed)
- Auto-advance toggle (continuous breeding vs. manual)

**Key controls:**
- **Space** — play/pause; **b** — force breed; **S** — skip to scoring
- **Arrow keys / WASD** — navigate organisms; **f / Enter** — favorite (protect from culling)
- **s** — save organism to disk; **p** — cycle fitness preset; **A** — toggle auto-advance
- **R** — return to settings menu; **q** — exit

**Persistence:** Discovered organisms can be saved to `evolution_lab.json` and reloaded as seed
populations for future runs, enabling long-running evolutionary campaigns across sessions.

**Integration points:**
- `life/app.py` — 25 state variables for evolution lab engine, draw dispatch (menu + tiled view), key dispatch, simulation stepping in run loop
- `life/modes/__init__.py` — module registration
- `life/registry.py` — mode browser entry under "Meta Modes" (key: Ctrl+Shift+E, category: Meta Modes)

**Design decisions:**
- Mini-simulations use a lightweight custom stepper (`_step_sim`) rather than the full Grid.step() to support multi-state decay and custom neighborhoods without polluting the main simulation engine
- Fitness scoring reuses `shannon_entropy`, `symmetry_score`, and `classify_stability` from `life/analytics.py` — the same metrics visible in the analytics overlay, ensuring what users see matches what the GA optimizes
- Population history tracked per-organism enables stability classification (coefficient of variation) and pattern richness (unique population values) as fitness dimensions
- Tiled view layout auto-adapts to terminal size, computing optimal grid arrangement to maximize cell visibility
- Favorites use index remapping after sort to maintain identity across generations

### Added: Real-Time Simulation Analytics Overlay — quantitative metrics HUD for measuring and classifying simulation behavior

A toggleable analytics panel (`Ctrl+K`) that works across all modes, overlaying live quantitative
metrics on the running simulation. Turns the simulator from a pure visual experience into a
scientific instrument where users can measure what they're seeing, spot phase transitions, and
identify mathematically interesting parameter regimes.

**New file:** `life/analytics.py` (~254 lines)

**Metrics displayed:**

| Metric | Description |
|--------|-------------|
| **Population** | Live cell count with rolling 60-frame Unicode sparkline history |
| **Shannon entropy** | Information-theoretic disorder metric (0 = uniform, higher = more disorder) |
| **Rate of change** | Average population delta per tick over 5-tick window with trend arrows (↑↓⇑⇓─) |
| **Periodicity** | Detects when the simulation enters a repeating cycle and reports the period length |
| **Symmetry score** | Horizontal, vertical, and 180° rotational symmetry (0–100%) with visual bar |
| **Stability class** | Categorizes state as: starting, extinct, static, oscillating, growing, dying, chaotic, or stable |
| **Grid density** | Population as percentage of total cells, with grid dimensions |

**Performance:** Expensive metrics (symmetry every 5 frames, entropy every 2 frames) are computed
at reduced intervals to avoid impacting simulation speed.

**Integration points in `life/app.py`:**
- Toggle with `Ctrl+K` (key code 11) — global across all modes
- Overlay drawn bottom-left as a bordered panel after all other overlays
- Metrics update on every simulation step (running or single-step)
- Analytics state resets on grid clear (`c`) and randomize (`r`)

### Added: Simulation Scripting & Choreography System — programmable show director for timed sequences of mode transitions, effects, and parameter sweeps

A new meta-mode (`Ctrl+U`) that lets users write and play back simple scripts to orchestrate
"shows" — timed sequences of mode transitions, parameter sweeps, effect toggles, and topology
changes. Think of it as a programmable director for the entire simulation platform.

The platform has 108+ modes, compositing, post-processing, portals, topology, and recording —
but until now no way for a user to *compose* these into a reproducible, timed performance.
The cinematic demo reel exists but is hardcoded; this gives users the same authoring power.
Scripts become a shareable artifact (like genome codes, but for entire performances), turning
the simulator from an exploration tool into a **creative authoring tool**.

**New file:** `life/modes/scripting.py` (~980 lines)

**Line-based DSL** supporting these commands:

| Command | Syntax | Description |
|---------|--------|-------------|
| `mode` | `mode <name>` | Switch simulation engine (gol, wave, rd, fire, boids, ising, rps, physarum + aliases) |
| `wait` | `wait <duration>` | Pause execution (e.g. `5s`, `500ms`) |
| `effect` | `effect <name> on\|off\|toggle` | Toggle post-processing effects (scanlines, bloom, trails, edge_detect, color_cycle, crt) |
| `topology` | `topology <name>` | Set grid topology (plane, torus, klein_bottle, mobius_strip, projective_plane) |
| `set` | `set <param> <value> [...]` | Set parameters inline (supports key-value pairs) |
| `sweep` | `sweep <param> <from> <to> over <dur>` | Animate a parameter over time with smooth hermite easing |
| `transition` | `transition crossfade\|cut\|fade <dur>` | Transition style between mode switches |
| `speed` | `speed <label>` | Set simulation speed (0.5x through 100x) |
| `color` | `color <1-7>` | Set display color |
| `label` | `label <text>` | Show a fading title card overlay (3s visible, 1s fade) |
| `loop` | `loop` | Jump back to start for infinite playback |

Comments (`#`) and blank lines are supported. Example `.show` script:

```
# Emergence — from simple rules to complex patterns
mode game_of_life
label Emergence
speed 2x
wait 5s
transition crossfade 2s
mode reaction_diffusion
effect bloom on
wait 6s
```

**5 built-in example scripts:** Emergence, Fluid Dreams, Life & Death, Speed Ramp, Full Tour

**Playback controls:**
- **Space** — pause/resume
- **n** — skip current wait/sweep
- **r** — restart from beginning
- **s** — toggle source code overlay (shows script with current-line indicator)
- **Esc** — exit scripting mode

**Script menu:**
- Arrow keys / j,k to navigate built-in scripts
- Enter to launch selected script
- "Load .show file from disk" option for user-authored scripts

**Integration points:**
- `life/app.py` — 28 state variables for script engine, draw dispatch (menu + playback + source overlay), run loop dispatch, `Ctrl+U` keybinding, help screen entry
- `life/modes/__init__.py` — registration
- `life/registry.py` — mode browser entry under "Meta Modes"

**Design decisions:**
- **Ctrl+U** keybinding (Ctrl+Y was already taken by 3D Terrain Flythrough)
- Script engine uses a program counter (`script_pc`) with immediate execution of non-blocking commands and blocking on `wait`/`sweep` — simple, debuggable, no coroutines needed
- Crossfade transitions blend density arrays from previous and current simulation for smooth visual handoffs
- Sweep animations use smooth hermite interpolation (`t² × (3 - 2t)`) for natural-feeling parameter ramps
- Reuses existing `_ENGINES` from mashup mode for simulation init/step/density, keeping the engine registry DRY
- Label overlay uses a timed fade (3s hold + 1s fade) for cinematic title cards without blocking script execution

### Added: Simulation Recording & Export System — capture any simulation as asciinema `.cast` or plain-text flipbook

A horizontal meta-feature that records terminal frames from any running simulation and exports them
as **asciinema v2 `.cast` files** (for playback via `asciinema play`, web embeds, or asciinema.org)
or **plain-text flipbook `.txt` files** (frames separated by form-feed characters with timestamps).

The project already had genome sharing for *configs*, but no way to capture the actual *visual
output*. This closes that gap — record a cinematic demo reel, a mesmerizing Reaction-Diffusion
pattern, or a 4-layer composite, then share the recording in a universally supported format.

**New file:** `life/modes/recording.py` (~426 lines)

**Frame capture engine:**
- Reads the curses window cell-by-cell after all drawing and overlays complete
- Converts curses attributes (color pairs, bold, dim, reverse, underline) to ANSI escape sequences
- Produces both ANSI-encoded and plain-text versions of each frame simultaneously

**Export formats:**

| Format | Extension | Description |
|--------|-----------|-------------|
| Asciinema v2 | `.cast` | JSON header + timestamped `[elapsed, "o", data]` events. Compatible with `asciinema play`, web embeds, asciinema.org |
| Plain-text flipbook | `.txt` | Frames separated by form-feed (`\f`) with timestamp headers. No ANSI escapes — safe for any text viewer |
| Both | `.cast` + `.txt` | Exports both formats simultaneously with the same timestamp |

**Recording controls:**
- **Ctrl+X** — global hotkey to start/stop recording (works in any simulation mode)
- FPS throttling (default 10 fps) — skips redundant captures when the simulation runs faster
- Safety cap at 3000 frames — auto-stops to prevent runaway memory usage
- Blinking `● REC Nf Ns` indicator in the top-right corner during recording

**Export menu** (shown on stop):
- Arrow keys / j,k to navigate; Enter to confirm; 1/2/3 for direct selection
- `d` to discard recording, Esc to cancel
- Files saved to `~/.life_saves/` with `recording_<timestamp>` naming

**Integration points:**
- `life/app.py` — state initialization via `_cast_rec_init()` in `__init__`; frame capture hook in main loop (after all drawing, before `getch()`); recording indicator overlay; export menu key interception; status bar `CAST(N)` indicator; help screen entry
- `life/modes/__init__.py` — registration
- `life/registry.py` — mode entry (Ctrl+X, "Meta Modes" category)

**Design decisions:**
- Captures *after* all drawing completes (including post-processing effects, topology edges, overlays) so recordings show exactly what the user sees
- Dual-track capture (ANSI + plain) avoids re-processing frames at export time
- Export menu intercepts keys before all other handlers to prevent accidental mode changes
- Uses the existing `SAVE_DIR` (`~/.life_saves/`) and `_flash()` for consistency with the rest of the save/load infrastructure

### Added: Layer Compositing System — stack 2-4 independent simulations as transparent layers with blend modes

A horizontal meta-feature that adds **depth** to the simulation ecosystem. Where Portal connects
two sims spatially at a seam and Mashup couples two sims on one grid globally, Compositing lets
simulations run independently on separate layers and merges them visually via blend operations —
like Photoshop layers, but live. A Reaction-Diffusion texture masked by Game of Life creates
organic breathing shapes; a Wave Equation added to Boids produces shimmering flocks.

**New file:** `life/modes/layer_compositing.py` (~757 lines)

**Blend modes:**

| Mode | Function | Description |
|------|----------|-------------|
| Add | `min(1, a + b)` | Sum intensities — bright overlaps |
| XOR | `abs(a - b)` | High where exactly one layer is active |
| Mask | `a if b > 0.15 else 0` | Lower layers visible only where top layer is active |
| Multiply | `a * b` | Darken — both layers must be active |
| Screen | `1 - (1-a)(1-b)` | Lighten — inverse multiply |

**7 presets** (2-, 3-, and 4-layer configurations):
- *Breathing Shapes* — Reaction-Diffusion masked by GoL
- *Shimmering Flock* — Wave + Boids
- *Crystal Lightning* — R-D XOR Fire
- *Spin Waves* — Ising × Wave
- *Slime Circuit* — RPS screened with Physarum
- *Triple Cascade* — GoL + Wave + Fire (3 layers)
- *Quad Stack* — GoL + Wave + Boids + Physarum (4 layers)

**Per-layer controls:** opacity (0–1), tick rate multiplier (×1–×8), blend mode cycling.
Custom layer builder lets users pick 2–4 simulations and blend modes interactively.

**Key distinction from Mashup:** zero simulation coupling — layers run independently and are
composited purely visually. This produces emergent visual patterns without altering simulation
dynamics.

**Controls:** `Space` play/pause, `n` step, `Tab` cycle focused layer, `+/-` opacity,
`t/T` tick rate, `b` blend mode, `r` reset, `R` menu, `</>` speed.

**Integration points:**
- `life/app.py` — 13 state variables; draw dispatch and key dispatch for menu + simulation
- `life/modes/__init__.py` — registration
- `life/registry.py` — mode entry (Ctrl+K, "Meta Modes" category)

**Design decisions:**
- Re-uses mini-simulation engines from Mashup mode (`_ENGINES`, `MASHUP_SIMS`) — no code duplication
- Each layer steps at its own tick rate via generation-modulo gating
- Compositing renders per-cell with dominant-layer coloring for visual clarity
- Menu system supports both preset selection and interactive custom layer building (up to 4 layers)

### Added: Visual Post-Processing Pipeline — composable ASCII visual effects that layer on top of ANY simulation mode

A horizontal meta-feature that adds 6 stackable terminal-space effects applied *after* any mode
renders, so they work universally across all 100+ simulation modes. Users open a toggle menu with
**Ctrl+V** and press **1–6** to combine effects freely. A compact `FX:SL+BL+TR` indicator appears
in the top-right when effects are active.

**New file:** `life/modes/post_processing.py` (~417 lines)

| # | Effect | Key | Description |
|---|--------|-----|-------------|
| 1 | Scanlines | `1` | Dims every other row for a retro CRT-phosphor look |
| 2 | Bloom / Glow | `2` | Bolds visible cells and paints dim `░` glow halos in empty neighbors |
| 3 | Motion Trails | `3` | Shows fading `▓▒░` echoes of previous frames where cells have moved |
| 4 | Edge Detection | `4` | Removes interior cells, leaving only boundary/silhouette outlines |
| 5 | Color Cycling | `5` | Rotates the age-based color pairs over time |
| 6 | CRT Distortion | `6` | Vignette darkening, odd-row scanlines, and a rounded bezel border |

**Integration points:**
- `life/app.py` — 5 state variables (`pp_active`, `pp_menu`, `pp_frame_count`, `pp_trail_buf`, `pp_trail_depth`); pipeline apply/draw calls inserted after `_draw()` and before overlay layers; key handling after topology handler
- `life/modes/__init__.py` — registration
- `life/registry.py` — mode registry entry (Ctrl+V, Meta Modes category)

**Design decisions:**
- Effects operate on the curses screen buffer after any mode renders — zero coupling to individual modes
- Applied before overlay layers (minimap, time-travel scrubber, etc.) so overlays remain unaffected
- Menu consumes all keys while open to prevent accidental mode changes
- Trail buffer stores configurable history depth (default 3 frames) with automatic pruning

### Added: Topology Mode — run any simulation on non-Euclidean surfaces (torus, Klein bottle, Möbius strip, projective plane)

A horizontal meta-feature that transforms how *all* existing simulations behave by changing
the grid's boundary conditions and cell connectivity. Users cycle through five surface types
with **Ctrl+W** and watch how patterns wrap, twist, and tile differently on each surface.

**Core engine:** `life/grid.py` — `_wrap(r, c)` method on `Grid`

The topology lives on the `Grid` object itself, so it automatically affects every simulation
that uses `_count_neighbours()`. Default is `torus`, which preserves 100% backward
compatibility (identical to the original modulo wrapping).

| Surface | Wrapping behavior | Visual edge indicator |
|---------|------------------|-----------------------|
| Plane | No wrapping — hard dead edges | Thin single lines (─ │) |
| Torus | Both axes wrap via modulo (default) | No indicator (default) |
| Klein bottle | Columns wrap normally; rows wrap with horizontal flip | Double lines + wavy twist lines with ⟵⟶ arrows |
| Möbius strip | Columns wrap with vertical flip; rows have hard edges | Mixed wall/twist borders with ↕ arrows |
| Projective plane | Both axes wrap with opposite-axis flips | Wavy twist lines on all edges |

**New file:** `life/modes/topology.py` (~269 lines)
- `TOPOLOGY_INFO` dict with labels, Unicode symbols, descriptions, and edge metadata per surface
- `_topology_cycle()` / `_topology_set()` — cycle or directly set the active topology
- `_topology_handle_key()` — Ctrl+W cycles forward
- `_draw_topology_indicator()` — shows topology name/symbol in top-right (hidden for default torus)
- `_draw_topology_edges()` — renders color-coded border characters: dim walls, cyan wraps, bold magenta twists with directional arrows at midpoints

**Integration points:**
- `life/app.py` — overlay drawing after sonification; universal key handler after time-travel
- `life/modes/__init__.py` — registration
- `life/registry.py` — mode registry entry (Ctrl+W, Meta Modes category)

**Design decisions:**
- Topology state on Grid, not App, so it automatically propagates to all neighbor-counting logic
- `_wrap()` returns `None` for off-grid coordinates (plane/Möbius edges), letting `_count_neighbours()` treat them as dead cells
- No UI clutter for the default torus — indicators only appear for non-default surfaces

### Added: Simulation Portal System — spatial gateways connecting two simulations at a boundary with cross-talk

A new meta-mode that creates a spatial boundary inside a single viewport where two different
simulation types run side-by-side. At the seam, each simulation's output bleeds into the other,
creating emergent cross-talk behavior that doesn't exist in either simulation alone. Unlike
Mashup mode (which couples whole simulations globally), portals create a *localized spatial
interface* — e.g., a Reaction-Diffusion system on the left feeding energy into Particle Life
on the right, with visible influence fading over a configurable bleed depth.

**New file:** `life/modes/portal.py` (~762 lines)

**8 curated portal presets** with descriptions:

| Preset | Orientation | Description |
|--------|-------------|-------------|
| RD ↔ Particle Life | vertical | Reaction-Diffusion feeds energy into Boids at the seam |
| Wave ↔ Forest Fire | vertical | Wave amplitude ignites fire; fire damps waves at the border |
| Game of Life ↔ Ising | vertical | Life births polarize spins; spin alignment births life |
| Physarum ↔ RPS | horizontal | Slime trails guide invasion; invasions deposit pheromone |
| Boids ↔ Wave | horizontal | Boids create ripples at boundary; waves steer boids |
| Fire ↔ Game of Life | vertical | Fire clears life; life regrows and fuels fire across the seam |
| Ising ↔ RD | horizontal | Spin domains modulate reaction feed rate at the interface |
| RPS ↔ Wave | vertical | Cyclic invasion creates wave pulses; waves bias dominance |

**Custom portal builder:** Pick any two of the 8 mini-engines, then choose vertical or horizontal
orientation for a fully custom portal setup.

**Boundary cross-talk algorithm:**
- Each simulation's edge density is sampled over a configurable bleed depth (1–20 cells)
- Influence fades linearly from the seam: cells at the boundary get full coupling, cells at
  bleed depth get zero
- A→B influence uses A's right/bottom edge mapped to B's left/top edge, and vice versa
- Coupling strength (0.0–1.0) scales the influence before it's passed to each engine's step function
- Reuses the existing `_ENGINES` dispatch table from Mashup mode for init/step/density functions

**Visual features:**
- Yellow `┃` (vertical) or `━` (horizontal) seam line at the portal boundary
- Sim A rendered in cyan, Sim B in red, with magenta highlights in the bleed zone
- Header bar showing mode, generation count, coupling strength, bleed depth, and play state
- Status bar with per-side average density statistics

**Controls:**

| Key | Action |
|-----|--------|
| `Space` | Play / pause |
| `n` / `.` | Single step |
| `+` / `-` | Increase / decrease coupling strength (±0.05) |
| `b` / `B` | Increase / decrease bleed depth (±1 cell) |
| `o` | Toggle orientation (vertical ↔ horizontal) |
| `0` | Set coupling to 0.0 (independent) |
| `5` | Set coupling to 0.5 (default) |
| `r` | Reset both simulations |
| `R` | Return to preset menu |
| `>` / `<` | Speed up / slow down |
| `q` / `Esc` | Exit portal mode |

**Integration points (4 files modified):**
- `life/modes/__init__.py` — registered the portal module
- `life/registry.py` — added `Simulation Portal` entry (Ctrl+J, Meta Modes category)
- `life/app.py` — portal state initialization (~25 attributes), draw dispatch for menu and
  simulation views, key handling and simulation advancement in the main loop

**Why:** The existing meta-modes (Observatory, Battle Royale, Mashup) combine simulations at
the *global* level — all cells share the same coupling. Portal mode introduces *spatial*
coupling: two physics stitched together at a visible border with localized cross-talk. This
creates visually novel emergent behavior at the interface that neither simulation produces
alone, and builds naturally on the mini-engine dispatch table, per-mode rendering pipeline,
and density-based coupling interface already established by prior meta-modes.

### Added: Simulation Genome Sharing System — encode any simulation's config as a compact, shareable seed string

A horizontal feature that lets users export any running simulation's complete configuration as a
short code (e.g., `RD-eNqr...`) and share it with others. Anyone can paste a genome code to
instantly reproduce that exact simulation setup — mode, parameters, rule set, speed, and (for
small Game of Life patterns) cell positions.

**New file:** `life/modes/genome.py` (~383 lines)

**How it works:**
1. Press `g` to open the genome menu
2. **Export**: Captures the active mode's configuration → JSON → zlib compress → base64url encode → compact string with a human-readable mode prefix (e.g., `RD`, `BOI`, `WAV`, `GOL`)
3. **Import**: Paste a genome code → decode → exit current mode → enter target mode → apply all saved parameters

**Encoding pipeline:**
- Scans all `self.<prefix>_*` attributes for the active mode (same pattern as time-travel snapshots)
- Filters out runtime state (grids, particles, threads, buffers, caches) via suffix/exact blocklists
- Keeps only serializable config values: numbers, short strings, booleans, small primitive lists
- For base Game of Life, also stores cell positions (up to 500 cells) with grid-size-aware centering on import
- Captures GoL birth/survival rule sets when a grid is present

**60+ mode abbreviations** for human-readable prefixes:

| Category | Examples |
|----------|----------|
| Classic CA | `GOL`, `WLF`, `ANT`, `HEX`, `WW`, `CYC` |
| Particle & Swarm | `BOI`, `PLF`, `PHY`, `ACO`, `NBD` |
| Physics & Waves | `WAV`, `ISG`, `KUR`, `QWK`, `LTN`, `CHL` |
| Fluid Dynamics | `FLD`, `NS`, `RBC`, `SPH`, `MHD` |
| Chemical & Bio | `RD`, `BZ`, `CHM`, `FIR`, `SIR`, `SNN` |
| Fractals & Procedural | `ATR`, `FRC`, `SNW`, `IFS`, `LSY`, `WFC` |
| Visual & Fun | `MTX`, `GAL`, `FRW`, `AQU`, `KAL`, `DNA` |
| Meta Modes | `CMP`, `RAC`, `PZL`, `EVO`, `MSH`, `BR` |

**Import handling:**
- Looks up mode in `MODE_REGISTRY` by reconstructed attribute name
- Exits current mode cleanly via `_exit_current_modes()`
- Enters target mode via its registered enter function
- Applies speed, rule sets, and all config parameters by attribute name
- Closes any menu the enter function may have opened
- Special-cases base GoL (no registry entry) with direct grid manipulation

**Controls:**

| Key | Action |
|-----|--------|
| `g` | Open genome menu (Export / Import) |
| `E` | Export current simulation as genome code |
| `I` | Import a genome code |

**Integration points in `life/app.py`:**
- `_genome_handle_key()` inserted in global key dispatch (before multiplayer)
- Help text entry added for `g` key

**Why:** The project has 100+ modes with deep parameter spaces, but discoveries are ephemeral —
close the terminal and they're gone. Recent commits added meta-modes for *viewing* simulations
(Observatory, Cinematic Demo, Sonification); this adds a way to *preserve and share* them. It
transforms the tool from a solo explorer into something with community potential — "check out
this code I found" becomes possible. As a horizontal feature, it works across all modes,
maximizing value per line of code.

### Added: Cinematic Demo Reel — auto-playing director with crossfade transitions, camera moves, and curated playlists

A new meta-mode that turns the terminal into an unattended screensaver showcase of the entire
simulation library. A virtual "director" sequences through simulations autonomously with smooth
crossfade transitions between acts, animated camera moves (zoom/pan via smoothstep interpolation),
and a fading title card overlay for each act. No interaction required — just launch a playlist
and watch.

**New file:** `life/modes/cinematic_demo.py` (~430 lines)

**8 cinematic acts**, each using a different simulation engine with unique duration and camera path:

| Act | Engine | Duration | Camera Move |
|-----|--------|----------|-------------|
| Emergence | Game of Life | 12s | Zoom in |
| Ripples | Wave Equation | 10s | Static |
| Morphogenesis | Reaction-Diffusion | 14s | Slow zoom out |
| Wildfire | Forest Fire | 10s | Pan right |
| Murmuration | Boids Flocking | 10s | Static |
| Phase Transition | Ising Model | 10s | Zoom in |
| Dominance Spirals | Rock-Paper-Scissors | 10s | Diagonal pan |
| Slime Intelligence | Physarum | 12s | Slow zoom out |

**5 curated playlists:**

| Playlist | Acts | Description |
|----------|------|-------------|
| The Grand Tour | All 8 | Every simulation engine in cinematic sequence |
| Fluid Dreams | Wave, RD, Physarum | Fluid-like phenomena |
| Life & Death | GoL, Fire, Ising | Creation and destruction |
| Swarm Logic | Boids, Physarum, RPS | Collective behavior emerges |
| Random Director | All 8 (shuffled) | Never the same show twice |

**Visual features:**
- **Crossfade transitions** (1.5s) — previous simulation's density blends into the new one
- **Camera moves** per act — zoom and pan via smoothstep (ease-in-out) interpolation
- **Title card overlay** — centered box showing act name/description, fades after 3 seconds
- **Progress bar status line** — playlist name, current act, countdown timer, generation count

**Controls:**

| Key | Action |
|-----|--------|
| `Ctrl+Shift+D` | Enter Cinematic Demo Reel |
| `Space` | Pause / resume playback |
| `n` / `→` | Skip to next act |
| `p` / `←` | Go to previous act |
| `r` | Restart current act |
| `Esc` / `q` | Exit to normal mode |

**Integration points in `life/app.py`:**
- Instance state: 22 `cinem_*` attributes for mode, menu, playlist, simulation, crossfade, camera
- Draw dispatch: `_draw_cinematic_menu()` and `_draw_cinematic()` before screensaver checks
- Key dispatch: `_handle_cinematic_menu_key()` and `_handle_cinematic_key()` before screensaver

**Architecture:** Reuses the `_ENGINES` dispatch table from `mashup.py` for simulation
init/step/density. Each act runs its own independent simulation at full internal resolution,
with the camera system selecting a viewport sub-region for display. Crossfades blend the
previous act's density buffer with the current one. Builds on the meta-mode pattern established
by Mashup, Battle Royale, and Observatory.

**Why:** Every existing mode requires manual selection and interaction. The Demo Reel fills the
gap of autonomous presentation — a kiosk/screensaver mode that showcases the breadth of the
simulation library without user intervention. It builds naturally on the Observatory and Mashup
infrastructure while adding cinematic production value (transitions, camera work, title cards).

### Added: Simulation Observatory — tiled split-screen running 4-9 simulations simultaneously with synced controls

A new meta-mode that displays multiple simulations side-by-side in a tiled grid, letting users
visually compare different cellular automata and simulation engines running in real time. With
95+ modes in the library, users previously had to view them one at a time — the Observatory
makes cross-simulation discovery possible by running up to 9 independent viewports on screen.

**New file:** `life/modes/observatory.py` (~591 lines)

**Layouts:**

| Layout | Grid | Viewports |
|--------|------|-----------|
| Side by Side | 2×1 | 2 |
| Quad | 2×2 | 4 |
| Wide | 3×2 | 6 |
| Full Grid | 3×3 | 9 |

**5 curated presets** for instant discovery:

| Preset | Simulations | Layout |
|--------|------------|--------|
| Fluid Trio | Wave Equation, Reaction-Diffusion, Physarum | 3×2 |
| Chaos Theory | Game of Life, Rock-Paper-Scissors, Ising Model, Forest Fire | 2×2 |
| Micro vs Macro | Boids, Physarum, Game of Life, Wave Equation | 2×2 |
| Nature's Patterns | Reaction-Diffusion, Forest Fire, Physarum, Rock-Paper-Scissors | 2×2 |
| Everything | All 8 simulation engines + 1 duplicate | 3×3 |

**Custom picker:** Choose a layout, then select simulations one by one from the full engine
list. Reuses the 8 mini-simulation engines from `mashup.py` (`_ENGINES` dispatch table),
keeping things DRY.

**Focus zoom:** Press `1`-`9` to expand any viewport to full screen for closer inspection,
`0` to return to the tiled view. Focused viewports show the simulation at full terminal
resolution.

**Controls:**

| Key | Action |
|-----|--------|
| `Ctrl+O` | Enter Observatory mode |
| `Space` | Play / pause all viewports |
| `n` / `.` | Single step all viewports |
| `1`-`9` | Focus-zoom viewport N |
| `0` | Unfocus (return to tiled view) |
| `>` / `<` | Speed up / slow down |
| `r` | Reset all viewports |
| `R` | Return to preset/layout menu |
| `q` / `Esc` | Exit Observatory |

**Integration points in `life/app.py`:**
- Instance state: 15 `obs_*` attributes for mode, menu, viewports, grid dimensions, and focus
- Draw dispatch: `_draw_observatory_menu()` and `_draw_observatory()` before mashup checks
- Key dispatch: `_handle_observatory_menu_key()` and `_handle_observatory_key()` before mashup

**Architecture:** Each viewport maintains independent simulation state (no coupling between
tiles). All viewports share global speed/pause controls and advance in lockstep. The mode
builds on the proven meta-mode pattern established by Mashup and Battle Royale.

**Why:** The project has accumulated 95+ simulation modes, but users can only view them one at
a time. Recent features (Time-Travel Scrubber, Sonification, Mashup Mode) have been
cross-cutting "meta" features. The Observatory is the natural culmination — any combination
of modes, running together, compared visually in real time. It showcases the breadth of the
simulation library and enables discovery of surprising visual similarities between unrelated
simulations.

### Added: Simulation Sonification Layer — maps any running simulation's visual state to real-time procedural audio

A horizontal feature (like the Time-Travel Scrubber) that turns all 99+ simulation modes into
audiovisual experiences without modifying any individual mode. When enabled, each frame's visual
state is analyzed and mapped to procedural audio parameters in real time.

**New file:** `life/modes/sonification.py` (~624 lines)

**Frame metrics extracted per tick:**
- **Density** — cell population / total cells
- **Activity** — velocity-based for particles, density-derived for grids
- **Spatial entropy** — row distribution uniformity (normalized Shannon entropy)
- **Center of mass (X, Y)** — normalized position of alive cells
- **Horizontal symmetry** — left-right mirror match score

**Audio parameter mapping:**

| Metric | Controls |
|--------|----------|
| Vertical center of mass | Pitch (higher when action is near top) |
| Entropy + density | Number of voices / harmonic richness |
| Category profile | Waveform mix (sine/sawtooth/pulse) |
| Horizontal center of mass | Stereo panning |
| Category profile | Tempo multiplier |
| Category profile | Drone layer level |
| Density | Master volume |

**12 category-specific audio profiles** — each simulation category gets a tailored sonic
character:

| Category | Character |
|----------|-----------|
| Fluid Dynamics | Flowing drones (low base, in-sen scale, heavy drone) |
| Particle & Swarm | Percussive clicks (pulse wave, fast tempo) |
| Fractals & Chaos | Evolving harmonics (mixed waveforms, whole-tone-ish) |
| Physics & Waves | Major scale, moderate drone |
| Chemical & Biological | Harmonic minor, organic feel |
| Classic CA | Clean pentatonic sine tones |
| Procedural & Computational | Whole tone scale, quick tempo |
| Game Theory & Social | Balanced pentatonic blend |
| Complex Simulations | Minor pentatonic, mixed waveforms |
| Audio & Visual | Major 9th arpeggio with drone |
| Physics & Math | Major scale, sawtooth-leaning |
| Meta Modes | Pure pentatonic sine |

**Synthesis pipeline:** Pure Python PCM generation (S16LE stereo at 22050 Hz) with soft
attack/release envelopes, equal-power stereo panning, and polyphony up to 16 voices. Playback
via `paplay`, `aplay`, or `afplay` (auto-detected). Audio runs in a daemon thread to avoid
blocking the main loop.

**Data extraction** handles three source types: standard Grid objects, 2D array state from
mode-specific attributes, and particle lists with velocity-based activity calculation.

**Integration points in `life/app.py`:**
- `threading` import added
- Instance state: `sonify_enabled`, `_sonify_thread`, `_sonify_stop`
- `_sonify_frame()` called each main-loop iteration (after time-travel auto-record)
- Sonification indicator overlay drawn after time-travel scrubber
- `Ctrl+S` toggle (key code 19) with audio player availability check
- Status bar shows `♫ SONIFY` when active

**Controls:**

| Key | Action |
|-----|--------|
| `Ctrl+S` | Toggle sonification on/off |

**Why:** The project already has a `SoundEngine` for procedural audio and 99 visual simulation
modes, but they aren't connected. This follows the proven "horizontal feature" pattern
established by the Time-Travel Scrubber — one feature that enhances every mode simultaneously.
It creates a synesthetic experience where fluid simulations produce flowing drones, particle
swarms generate percussive clicks, and fractals evolve harmonic textures, all without any
mode needing to know about audio.

### Added: Live Rule Editor — type Python expressions to define custom CA rules and watch them run in real time

A new meta-mode that turns users from passive viewers into active creators. Instead of choosing
from pre-built rules, users type Python expressions like `sum(neighbors) == 3` for birth and
`sum(neighbors) in (2, 3)` for survival, and the grid immediately starts running the custom
rule. Expressions can reference `neighbors`, `age`, `x`, `y`, `step`, and `random()` for
stochastic, positional, temporal, and age-dependent rules that go far beyond standard B/S
notation.

**New file:** `life/modes/rule_editor.py` (~430 lines)

**10 starter snippets** covering the spectrum from classic to exotic:

| Snippet | Birth | Survival |
|---------|-------|----------|
| Classic Life (B3/S23) | `sum(neighbors) == 3` | `sum(neighbors) in (2, 3)` |
| HighLife (B36/S23) | `sum(neighbors) in (3, 6)` | `sum(neighbors) in (2, 3)` |
| Day & Night | `sum(neighbors) in (3, 6, 7, 8)` | `sum(neighbors) in (3, 4, 6, 7, 8)` |
| Seeds (B2/S—) | `sum(neighbors) == 2` | `False` |
| Diamoeba | `sum(neighbors) in (3, 5, 6, 7, 8)` | `sum(neighbors) in (5, 6, 7, 8)` |
| Age-Dependent Decay | `sum(neighbors) == 3` | `sum(neighbors) in (2, 3) and age < 10` |
| Positional Bias | `sum(neighbors) == 3 and (x + y) % 3 == 0` | `sum(neighbors) in (2, 3)` |
| Stochastic Life | `sum(neighbors) == 3 or (... random() < 0.05)` | `sum(neighbors) in (2, 3)` |
| Pulse (step-dependent) | `sum(neighbors) == 3 or (... step % 10 < 3)` | `sum(neighbors) in (2, 3)` |
| Anneal (B4678/S35678) | `sum(neighbors) in (4, 6, 7, 8)` | `sum(neighbors) in (3, 5, 6, 7, 8)` |

**Inline editor** with Tab to cycle between Birth/Survival/Name fields, Enter to edit, full
cursor movement (arrows, Home/End, Ctrl+A/E/K/U), Esc to cancel. Expressions are compiled on
confirm and errors are shown inline.

**Save/load system:** Custom rules persist to `~/.life_saves/custom_rules.json`. The menu has
tabs for browsing snippets vs saved rules, with delete support via `x`.

**Sandboxed eval:** `__builtins__` is set to `{}` — only safe math/list builtins (`sum`, `len`,
`min`, `max`, `abs`, `any`, `all`, `int`, `float`, `math`) are exposed.

**Integration with other modes:**
- `i` = Import from Evolutionary Playground — converts an EP genome's birth/survival sets into
  expression form for fine-tuning
- `a` = Adopt to main GoL — probes the rule for each neighbor count 0–8 and sets `grid.birth`
  and `grid.survival` to the inferred B/S sets

**Controls:**

| Key | Action |
|-----|--------|
| `Space` | Play/pause simulation |
| `.` | Single step |
| `Enter` | Edit focused field |
| `Tab` | Cycle focus (Birth → Survival → Name) |
| `+` / `-` | Adjust speed |
| `r` | Randomize grid |
| `c` | Clear grid |
| `S` | Save current rule |
| `a` | Adopt rule to main GoL grid |
| `i` | Import from Evolutionary Playground |
| `m` | Back to snippet/load menu |
| `q` / `Esc` | Exit rule editor |

**Registration:**
- Registry: category "Meta Modes", hotkey `Ctrl+Shift+L`
- App: 24 state variables, menu/editor key dispatch, draw dispatch
- Modes `__init__.py`: registered via `rule_editor.register(App)`

**Why:** The project has 94+ modes but they're all pre-built — users can watch but not create.
The Live Rule Editor is the difference between a museum and a workshop. It pairs with the
Evolutionary Playground (evolve rules, then import and fine-tune expressions) and the Parameter
Space Explorer (explore your custom rules' parameter landscape). Expression-based rules also
unlock behaviors impossible in standard B/S notation: age-dependent decay, spatial patterning,
stochastic transitions, and temporal pulses.

### Added: Battle Royale Mode — 4 cellular automata factions compete for territory in real-time

A new meta-mode where four different cellular automata rules spawn in corners of a shared grid
and expand organically into neutral space. When factions collide at boundaries, cells fight
based on local neighborhood density — the denser faction overwrites weaker neighbors. A live
scoreboard tracks territory percentage per faction, and when a faction drops to zero cells it's
eliminated. Last faction standing wins.

**New file:** `life/modes/battle_royale.py` (~430 lines)

**8 available CA factions**, each with unique birth/survival rules:

| Faction | Rule (B/S) | Character |
|---------|-----------|-----------|
| Life | B3/S23 | Classic Conway |
| HighLife | B36/S23 | Replicators |
| Day & Night | B3678/S34678 | Symmetric |
| Seeds | B2/S— | Explosive growth |
| Morley | B368/S245 | Move rule |
| Maze | B3/S12345 | Space-filler |
| Amoeba | B357/S1358 | Organic |
| Diamoeba | B35678/S5678 | Diamond shapes |

**4 preset matchups** (Classic Showdown, Aggressive Mix, Territorial War, Survival of the
Fittest) plus a custom faction picker for any combination of 4.

**Combat system:** Each cell follows its faction's B/S rules for birth and survival. When enemy
density around a cell exceeds own-faction neighbors by more than 1 and the dominant enemy has
3+ neighbors, the cell is conquered and switches faction. Empty cells can be claimed by any
faction whose birth condition is met by its neighbor count — ties broken randomly.

**Corner spawning:** Each faction starts in a corner quadrant (~1/6 of grid dimensions) with
45% random fill density, giving each rule a critical mass to grow from before encountering
enemies.

**Scoring and elimination:**
- Real-time scoreboard shows cell count and territory percentage per faction
- Visual territory bar using color-coded segments
- Factions hitting 0 cells are marked eliminated (☠)
- Last faction standing wins; simultaneous elimination results in a draw

**Color-coded rendering:** 4 distinct color schemes (blue, red, green, yellow) with age-based
shading — newer cells are brighter, older territory is darker. Uses 16 color pairs (indices
140–155) with 256-color and 8-color fallback support.

**Controls:**

| Key | Action |
|-----|--------|
| `Space` | Play/pause |
| `n` / `.` | Single step |
| `r` | Rematch (same factions) |
| `R` | Return to faction selection menu |
| `<` / `>` | Adjust speed |
| `q` / `Esc` | Exit battle royale |

**Menu system:** Two-phase selection — preset list → (custom) pick 4 factions from the roster.
Arrow keys + Enter to navigate; Esc to go back a phase.

**Integration:**
- Registry: category "Meta Modes", hotkey `Ctrl+Shift+U`
- App: 17 state variables, menu/battle key dispatch, draw dispatch
- Modes `__init__.py`: registered via `battle_royale.register(App)`

**Why:** The project already has a Simulation Mashup mode for layering two simulations with
coupling, but Battle Royale turns multi-rule interaction into something dynamic and competitive.
Instead of passive overlay, factions actively fight for territory with emergent frontlines,
flanking maneuvers, and elimination cascades. Different CA rules have inherent strategic
advantages — Seeds explodes fast but dies easily, Maze fills space relentlessly, Life is
balanced — making faction selection a genuine strategic choice. It's a spectator sport for
cellular automata.

### Added: Simulation Mashup Mode — layer two simulations on the same grid for emergent cross-simulation behavior

A new meta-mode that lets users pick any two of 8 built-in simulation engines and run them
simultaneously on a shared grid, where each simulation's output density field influences the
other's dynamics via a tunable coupling parameter. The project has 96 standalone simulations
that never interact; Mashup mode turns 8 mini-engines into 28 unique pairings, creating a
combinatorial explosion of novel emergent behaviors from existing simulation concepts.

**New file:** `life/modes/mashup.py` (~530 lines)

**8 self-contained mini-simulation engines**, each with `init`, `step` (with coupling input),
and `density` functions:

| Engine | Coupling mechanism |
|--------|-------------------|
| Game of Life | Other density triggers spontaneous births |
| Wave Equation | Other density acts as a forcing/source term |
| Reaction-Diffusion (Gray-Scott) | Other density locally boosts feed rate |
| Forest Fire | Other density raises ignition probability |
| Boids Flocking | Steers agents toward gradient of other density |
| Ising Model | Other density acts as external magnetic field |
| Rock-Paper-Scissors | Other density modulates invasion probability |
| Physarum Slime Mold | Biases agents toward other density, adds to trail |

**8 curated preset combos** with descriptions (e.g., "Boids + Wave Equation", "Fire + Game of
Life", "Reaction-Diffusion + Ising") plus a custom picker for any arbitrary pairing.

**Rendering:** Both simulations overlay on the same grid using density characters (`░▒▓█`)
with color-coded dominance — cyan for Sim A, red for Sim B, magenta for overlap regions.
Brightness scales with intensity (DIM/normal/BOLD).

**Controls:**

| Key | Action |
|-----|--------|
| `Space` | Play/pause |
| `n` / `.` | Single step |
| `+` / `-` | Adjust coupling strength (0.0–1.0) |
| `0` | Decouple (independent simulations) |
| `5` | Default coupling (0.50) |
| `r` | Reset current mashup |
| `R` | Return to combo selection menu |
| `<` / `>` | Adjust speed |
| `q` / `Esc` | Exit mashup mode |

**Menu system:** Three-phase selection — preset list → (custom) pick Sim A → pick Sim B.
Arrow keys + Enter to navigate; Esc to go back a phase.

**Integration:**
- Registry: category "Meta Modes", hotkey `Ctrl+M`
- App: 20 state variables, menu/sim key dispatch, draw dispatch
- Modes `__init__.py`: registered via `mashup.register(App)`

**Architecture:** Each engine is a pure-Python mini-simulation with no external dependencies.
The coupling is symmetric — Sim A receives Sim B's density map and vice versa — with a
global coupling strength slider controlling influence magnitude. This keeps engines decoupled
and composable: adding a 9th engine automatically enables 8 new mashup pairs.

**Why:** The project has nearly 100 individual simulation modes, but they exist in isolation.
Mashup mode creates emergent value by combining existing concepts rather than adding more
standalone simulations. A single coupling slider lets users smoothly transition from
independent side-by-side execution to fully interacting systems, making it easy to discover
unexpected cross-domain phenomena like waves steering flocking boids or fire patterns
modulated by spin lattice phase transitions.

### Added: Universal Time-Travel History Scrubber — rewind, fast-forward, and step through any simulation's timeline

A horizontal feature that adds a 500-frame history buffer to all 80+ non-GoL simulation modes.
Every mode previously ran forward-only; now users can pause any simulation and scrub backward
and forward through its timeline frame-by-frame or in 10-frame jumps. A visual timeline bar
at the bottom of the screen shows playback position and status. This turns passive watching
into active exploration — users can catch fleeting patterns in chaos simulations, study exact
moments of phase transitions, or replay the instant a flock splits.

**New file:** `life/modes/time_travel.py` (~288 lines)

**Core design:**
- **Generic state snapshotting**: Automatically captures all `self.<prefix>_*` attributes for the active mode via `copy.deepcopy`, excluding UI state (`_mode`, `_menu`, `_running` suffixes)
- **Active mode detection**: Scans `MODE_REGISTRY` to find which mode is active and derives its attribute prefix — no per-mode configuration needed
- **History buffer**: Stores up to 500 frames with automatic oldest-frame trimming
- **Auto-recording**: `_tt_auto_record()` runs each frame, captures state whenever the generation counter advances
- **Mode-switch detection**: Clears history when the active mode changes

**Controls:**

| Key | Action |
|-----|--------|
| `u` | Rewind one frame |
| `[` | Scrub back 10 frames |
| `]` | Scrub forward 10 frames |
| `n` | Step forward one frame (when scrubbing) |
| `Space` | Resume simulation from scrubbed position (truncates future) |

**Visual timeline bar:**
- Rendered as an overlay on the bottom line of any active mode
- `█░` progress bar indicating position in history
- Displays frame count, LIVE/SCRUBBING status, and key hints

**Integration in `app.py`:**
- `_tt_auto_record()` called at the start of each main loop iteration
- `_tt_handle_key()` intercepts time-travel keys before mode-specific dispatch
- `_draw_tt_scrubber()` rendered as overlay after mode drawing
- History cleared in `_exit_current_modes()` on mode switch
- State variables (`tt_history`, `tt_max`, `tt_pos`, `_tt_last_gen`) added to `__init__`

**Why:** This is a force-multiplier for every existing mode. Rather than adding value to one
mode at a time, the history scrubber multiplies the value of all 80+ modes at once. It's
especially powerful for simulations with rare transient phenomena — phase transitions in Ising
models, sudden flocking splits in Boids, or emergent gliders in chaos CAs — where the
interesting moment is gone before you can study it.

### Added: Evolutionary Playground — breed novel CA rules through interactive natural selection

A new meta-mode that lets users discover novel cellular automata rules through an interactive
genetic algorithm. A grid of live-running simulations with randomly generated rules competes
side-by-side. Users select the most visually interesting ones as "parents," breed them via
crossover and mutation, and repeat — iteratively discovering emergent behaviors that no one
designed by hand. The fitness function is human aesthetic judgment.

**New file:** `life/modes/evo_playground.py` (~530 lines)

**Genetics engine:**
- **Genome**: birth set, survival set, neighborhood type (Moore/Von Neumann/Hex), state count (2–5)
- **Crossover**: uniform — each rule digit independently inherited from either parent
- **Mutation**: configurable rate (default 15%); each digit can flip; neighborhood and state count mutate at half rate
- **Population**: dynamically sized grid (2–4 rows × 2–5 cols) of mini CA simulations

**Features:**
- Settings menu to configure mutation rate and choose starting population (random or from saved rules)
- Live grid of independently running mini-simulations, each with a unique genome
- Arrow-key navigation with cursor highlight and mouse support (double-click to select)
- Select parents with Enter (star marker), breed next generation with `b`
- Save interesting rules to `~/.life_saves/evolved_rules.json` with `S`
- Adopt a rule into the main Game of Life grid with `a`
- Randomize population with `r` to start fresh
- Speed controls with `<`/`>`
- Density-glyph rendering with 8-level color tiers per tile

**Controls:**

| Key | Action |
|-----|--------|
| `Space` | Play/pause all simulations |
| `.` | Single step |
| `←→↑↓` / `wasd` | Navigate tile selection |
| `Enter` | Toggle parent selection on cursor tile |
| `b` | Breed: crossover + mutate selected parents into next generation |
| `S` | Save cursor rule to evolved_rules.json |
| `a` | Adopt cursor rule into main grid |
| `A` | Select/deselect all |
| `r` | Randomize (new random population) |
| `<`/`>` | Adjust global speed |
| Mouse click | Select tile; double-click to toggle parent |

**Integration:**
- Registry: category "Meta Modes", hotkey `Ctrl+Shift+I`
- App: 17 state variables, menu tracking, key dispatch, draw dispatch

**Why:** This is the natural next step after the Parameter Space Explorer — moving from
*exploring* known parameter spaces to *discovering* entirely new ones. It's also a content
engine: rules bred here can be saved as presets or promoted into standalone modes, making
every session a potential source of new simulation behaviors.

### Added: Parameter Space Explorer — visual navigation of simulation parameter landscapes

A new meta-mode that displays a grid of live simulation thumbnails, each running the same
simulation with slightly varied parameters. Instead of blindly twiddling knobs, users can
see an entire parameter neighborhood at once, click the most interesting tile, and zoom in
to explore its vicinity — turning parameter tuning into visual exploration.

**New file:** `life/modes/param_explorer.py` (~830 lines)

**Features:**
- Mode selection menu to choose which simulation to explore
- Auto-sized grid (2×2 to 5×6) of independently running mini-simulations
- X and Y axes each map to a tunable parameter, with values interpolated across the grid
- Zoom in: press Enter on a tile to re-center the grid around its parameters (40% of range)
- Zoom out: press `z` to widen the parameter range by 50%
- Presets: press `p` to cycle through known interesting parameter combinations
- Full reset with `r` to return to the complete parameter range
- Mouse support for tile selection (double-click to zoom)
- Speed control: `+`/`-` for steps per frame, `<`/`>` for global speed
- Density-glyph rendering with 8-level color tiers

**Explorable modes:**

| Mode | X-axis | Y-axis | Presets |
|------|--------|--------|---------|
| Reaction-Diffusion (Gray-Scott) | feed rate [0.01–0.08] | kill rate [0.04–0.07] | Coral Growth, Mitosis, Fingerprints, Spots, Worms, Spirals, Maze, Chaos |
| Smooth Life (continuous CA) | mu [0.05–0.45] | sigma [0.01–0.15] | Orbium, Geminium, Stable Blobs, Oscillators, Chaos |

**Controls:**

| Key | Action |
|-----|--------|
| `Space` | Play/pause all simulations |
| `n`/`.` | Single step |
| `←→↑↓` / `wasd` | Navigate tile selection |
| `Enter` | Zoom into selected tile's parameter neighborhood |
| `z` | Zoom out (widen parameter range) |
| `p` | Jump to next preset |
| `r` | Reset to full parameter range |
| `R`/`m` | Return to mode selection menu |
| `+`/`-` | Adjust steps per frame |
| `<`/`>` | Adjust global speed |
| Mouse click | Select tile; double-click to zoom |

**Integration:**
- Registry: category "Meta Modes", hotkey `Ctrl+Shift+E`
- App: init vars, draw dispatch, key handling dispatch, menu tracking
- Extensible: add new explorable modes by defining `init`/`step`/`sample` functions

**Architecture:** Each explorable mode is defined by a simple interface — `init(rows, cols, px, py)`,
`step(state, n)`, `sample(state, r, c)` — making it trivial to add more modes. The mini-simulations
are fully independent pure-Python implementations (no dependency on the main mode code), keeping
the explorer self-contained.

**Why:** This is a multiplier feature, not an additive one. Rather than adding mode #95, it
enhances all existing parameterized modes by making their parameter spaces visually explorable.
Complex systems like Gray-Scott reaction-diffusion have rich parameter spaces where tiny changes
produce wildly different patterns — this makes discovery intuitive rather than requiring blind
parameter guessing.

### Enhanced: Reaction-Diffusion Textures — Gray-Scott model with 15 presets and color schemes

Rewrites the existing reaction-diffusion mode into a full-featured Gray-Scott texture
generator. Users pick from 15 named parameter presets across 3 categories and watch
organic patterns (coral, mitosis, fingerprints, worms) self-organize in real-time with
colored ASCII shading.

**Modified files:**
- `life/modes/reaction_diffusion.py` — major rewrite (~490 lines)
- `life/app.py` — added `RD_PRESETS` (15 entries) and `RD_DENSITY` class attributes
- `life/registry.py` — updated mode name and description

**15 Gray-Scott presets in 3 categories:**

| Category | Presets |
|----------|---------|
| Classic Patterns | Coral Growth, Mitosis, Fingerprints, Spots, Worms |
| Exotic Patterns | Spirals, Maze, Chaos, Pulsing Spots, Negatons |
| Biological Analogues | Cell Division, Bacteria, Lichen, Bubbles, Ripples |

Each preset has tuned `(f, k)` feed/kill parameters that produce distinct self-organizing textures.

**Features:**
- 5 color schemes (ocean, thermal, organic, purple, monochrome) cycleable with `c`
- Circular seed patches with smooth falloff for natural initial conditions
- Interactive perturbation: `p` adds random V patches; mouse clicks inject chemical
- Category-grouped preset menu with dividers
- Adjustable feed/kill rates (`f`/`F`/`k`/`K`), steps per frame (`+`/`-`)
- Status bar with generation count, V concentration stats, diffusion constants

**Controls:**

| Key | Action |
|-----|--------|
| `Space` | Play/pause simulation |
| `n`/`.` | Single step |
| `f`/`F` | Increase/decrease feed rate |
| `k`/`K` | Increase/decrease kill rate |
| `c` | Cycle color scheme |
| `p` | Add random perturbation |
| `+`/`-` | Adjust steps per frame |
| `r` | Re-seed grid |
| `R`/`m` | Return to preset menu |
| Mouse click | Inject chemical at cursor |

**Why:** The project had 94 modes covering fractals, fluids, particles, and cellular
automata but lacked a classic reaction-diffusion system — one of the most visually
striking simulations in computational science. The Gray-Scott model fills this gap with
minimal code by producing an enormous variety of organic patterns from just two parameters.

### Added: Screensaver / Demo Reel mode — auto-cycling showcase of all simulation modes

Turns 91 simulation modes into a single cinematic experience you can launch and walk
away from. Cycles through modes on a configurable timer with smooth dissolve transitions
and an overlay showing mode name, category, and playback position.

**New file:** `life/modes/screensaver.py` (~530 lines)

**Features:**
- 12 presets: All Sequential, All Shuffle, Favorites Sequential/Shuffle, plus 8 category-specific playlists
- Configurable timer: 5–120 seconds per mode (default 15s), adjustable live with `+`/`-`
- Fade/dissolve transition between modes using block-character density effect
- Mode name/category overlay box that auto-fades after 3 seconds (toggle persistent with `i`)
- Status bar: current mode, playlist position, countdown to next, controls summary
- Auto-preset selection: automatically picks the first preset for each mode's menu so modes start without manual intervention
- Reshuffles playlist on loop when using shuffle presets
- State preservation across mode switches (saves/restores screensaver state around `_exit_current_modes`)

**Controls during playback:**

| Key | Action |
|-----|--------|
| `Space` | Pause/resume cycling |
| `n` / `Right` | Skip to next mode |
| `p` / `Left` | Go to previous mode |
| `+`/`-` | Adjust interval (±5s) |
| `i` | Toggle persistent info overlay |
| `Esc`/`q` | Exit back to dashboard |

**Integration:**
- Registry: mode #92, category "Meta Modes", hotkey `Ctrl+Shift+C`
- Dashboard: `s` hotkey launches screensaver directly; animated preview in mode list
- CLI: `--screensaver [PRESET]` and `--screensaver-interval SECONDS` flags
- Key/draw dispatch: screensaver handlers intercept before sub-mode and dashboard handlers; overlay draws after sub-mode content

**Why:** With 91 modes and a polished dashboard for browsing them, the natural next
piece is an auto-pilot showcase. This turns 45,000+ lines of simulation code into a
single visual showpiece — perfect for leaving on a terminal as ambient art.

### Added: TUI Dashboard — landing screen with live preview, categories, and favorites

Replaces the old "drop straight into Game of Life" startup with a polished home screen
that lets users discover, browse, and launch all 90+ simulation modes.

**New file:** `life/dashboard.py` (~880 lines)

**Features:**
- ASCII art "LIFE SIM" banner (auto-downsizes for narrow terminals)
- Left panel: all modes grouped by category with icons (⬡ Classic CA, ◎ Particle & Swarm, ≈ Fluid Dynamics, etc.)
- Right panel: mode info (name, category, description, hotkey) + live animated mini-preview of the selected mode
- 20+ unique preview animations (waves, particles, fractals, fire, matrix rain, fish tank, DNA helix, pendulums, colliders, etc.)
- Favorites: press `f` to star/unstar, `Tab` to filter to favorites only, persisted to `~/.life_saves/favorites.json`
- Live search: type to filter modes by name, description, or category
- Category cycling: `Ctrl+A` cycles through category filters
- `Enter` launches selected mode, `Esc` exits to default Game of Life
- `M` opens the legacy mode browser (still accessible as a hidden shortcut)

**Integration:**
- Dashboard auto-opens on startup unless `--pattern`, `--host`, `--connect`, or `--no-dashboard` is specified
- `m` key now opens the dashboard (previously opened the flat mode browser)
- Dashboard renders at highest priority in the draw loop (before mode browser)
- Dashboard key handling is first check in the run loop

**CLI:** `--no-dashboard` flag for users who prefer the old immediate-start behavior

**Why:** With 90+ modes, the old CLI-flag / in-app-mode-browser flow made discovery
hard. The dashboard transforms this from a CLI tool into a showcase application — a
visual "home base" for the entire simulation collection.

### Refactored: Split 51K-line monolith into modular package

The single-file `life.py` (51,228 lines, 987 functions) has been decomposed into a
104-file Python package under `life/`. The original entry point (`life.py`) is now a
10-line shim; all logic lives in the package.

**Package layout:**

| Module | Purpose | Lines |
|--------|---------|-------|
| `life/app.py` | App class core — init, run loop, draw dispatch | ~6,500 |
| `life/grid.py` | Grid class — toroidal cellular automaton grid | ~140 |
| `life/constants.py` | Speed tables, cell chars, zoom levels | ~30 |
| `life/patterns.py` | 13 preset patterns + 10 puzzle challenges | ~200 |
| `life/rules.py` | Rule presets, `rule_string()`, `parse_rule_string()` | ~40 |
| `life/colors.py` | Color palettes, age/mp/heat color helpers | ~330 |
| `life/utils.py` | Pattern recognition, RLE parsing, GIF encoder, sparkline | ~520 |
| `life/sound.py` | SoundEngine — procedural audio synthesis | ~175 |
| `life/multiplayer.py` | MultiplayerNet — TCP networking | ~380 |
| `life/registry.py` | MODE_CATEGORIES + MODE_REGISTRY (89 entries) | ~230 |
| `life/modes/*.py` | **91 mode files**, one per simulation mode | ~44,700 |

**Architecture:**

- Each mode file defines standalone functions (`enter`/`exit`/`step`/`draw`/`handle`)
  and a `register(App)` function that monkey-patches them onto the App class.
- `life/modes/__init__.py` has `register_all_modes()` which loads all 91 mode files.
- `life/__init__.py` uses lazy imports to avoid circular dependencies.
- Backward compatible: `./life.py` still works; `python -m life` also works.
- App class has 929 methods after all modes register.

**Why:** At 51K lines, the monolith was becoming impractical to navigate, test, or
extend. Every new simulation mode made the problem worse. The package structure makes
future mode additions trivial (add one file, register in `__init__.py`) and the
codebase navigable.

### Added: Particle Collider / Hadron Collider (Ctrl+Shift+Z)

A CERN-inspired particle physics simulation — beams orbit an elliptical accelerator ring and collide at detector interaction points, producing showers of decay products.

**What it does:**
- Elliptical accelerator ring drawn with box-drawing characters and pulsing energy animation
- Beam particles (clockwise and counter-clockwise) orbiting with trailing dots
- 4 detector interaction points modeled after real LHC experiments (ATLAS, CMS, ALICE, LHCb) with collision flash effects
- Collision showers: 4–25 decay product particles spray outward with physics-based deceleration and lifetime decay
- 12 detectable particles: Higgs boson, W/Z bosons, top/charm quarks, muons, taus, photons, gluons, pions, kaons, B mesons — with measured mass and energy
- 4 presets: LHC Standard (13.6 TeV p-p), Heavy Ion (dense showers), Electron-Positron (clean jets), Discovery Mode (high luminosity/rare particles)
- CERN-aesthetic UI: beam status readout, scrolling detector event log, flash detection banner
- Controls: `Space` (pause), `c` (force collision), `+`/`-` (speed), `r` (reset), `R` (menu), `i` (info overlay), `q` (quit)

**Why:** The project had physics modes (gravity, fluids, electromagnetism) but nothing at the subatomic scale. This adds high-energy particle physics with a fun, educational CERN aesthetic.

**Category:** Physics & Math (~550 lines added to life.py)

### Added: ASCII Aquarium / Fish Tank — Zen-mode fish tank with 8 species, seaweed, bubbles, and caustic lighting

Continuous ambient simulation: 8 species-typed fish (Minnow `><>`, Guppy `><°>`, Tetra `><((·>`, Angelfish `></\>`, Clownfish `><(((°>`, Pufferfish `><(°O°)>`, Swordfish `><=====<`, Whale `><((((((((°>`) with left/right sprites, sinusoidal bobbing, and periodic depth changes. Fish redirect toward food when within 15 columns. Tap-glass event doubles speed and reverses direction briefly. Seaweed sways with per-column `sin(t×speed + phase + seg×0.5)`. Bubbles rise with sinusoidal wobble through `[. o O ° ⊙]` ramp. Caustic light overlay from `sin×cos` product threshold. Surface ripples via `sin` threshold switching `~`/`≈`.

**Changed file:** `life.py` (+~560 lines)

**8 fish species:**

| Species | Sprite | Speed | Size |
|---------|--------|-------|------|
| Minnow | `><>` | 0.8–1.5 | tiny |
| Guppy | `><°>` | 0.6–1.2 | small |
| Tetra | `><((·>` | 0.7–1.3 | small |
| Angelfish | `></\>` | 0.3–0.7 | medium |
| Clownfish | `><(((°>` | 0.5–1.0 | medium |
| Pufferfish | `><(°O°)>` | 0.2–0.5 | medium |
| Swordfish | `><=====<` | 1.0–2.0 | large |
| Whale | `><((((((((°>` | 0.1–0.3 | large |

**4 presets:** Tropical Reef (species 0–5, 10–16 fish), Deep Ocean (species 5–7, 5–8 fish), Koi Pond (species 3–4, 6–10 fish), Goldfish Bowl (species 1–2, 4–7 fish)

**Interactive controls:** `Space` (pause), `f`/`F` (feed fish 3–7 pellets), `t`/`T` (tap glass to startle), `a`/`A` (add fish), `d`/`D` (remove fish), `b`/`B` (add bubble stream), `+`/`-` (speed), `i`/`I` (info overlay), `R` (preset menu), `q`/`Esc` (exit)

### Added: Kaleidoscope / Symmetry Pattern Generator — N-fold rotation+reflection symmetry with 7 animated seed styles

Generates animated symmetry patterns by computing seed geometry in a canonical half-sector and reflecting across all N axes. `_kaleido_plot_symmetric` converts Cartesian to polar, adds N rotational increments + mirror reflections for true kaleidoscopic symmetry. 7 seed styles: crystal (oscillating radial lines), wave (sinusoidal scan), line (rotating spoke), burst (pulsing ring), petal (rose curve), spiral (Archimedean arm), ring (concentric pulsing circles). Canvas cells store (intensity, color_index); fade pass −0.04/step creates temporal trails. Paint Mode: manual cursor-based drawing mirrored across all axes.

**Changed file:** `life.py` (+~450 lines)

**8 presets:**

| Preset | Symmetry | Seed | Palette |
|--------|----------|------|---------|
| Snowflake | 6-fold | crystal | Ice |
| Mandala | 8-fold | wave | Jewel Tones |
| Diamond | 4-fold | line | Jewel Tones |
| Star Burst | 12-fold | burst | Neon |
| Flower | 6-fold | petal | Forest |
| Vortex | 8-fold | spiral | Fire |
| Hypnotic | 4-fold | ring | Monochrome |
| Paint Mode | 6-fold | manual | Jewel Tones |

**Interactive controls:** `Space` (pause), `s` (cycle symmetry: 4→6→8→12), `c` (cycle palette), `f` (toggle fade), `p` (toggle paint mode), `b` (cycle brush size), arrows (paint cursor), `r` (reset), `+`/`-` (speed), `i` (info), `Esc` (preset menu)

### Added: Ant Farm Simulation — Side-view colony with 4-state FSM, dual pheromone trails, and colony growth

Side-view underground cross-section with sky, surface, and stratified soil (dirt/clay/rock). Queen chamber near surface with direct access tunnel. Each ant: 4-state finite machine (explore → forage → return_food → dig). Explore: weighted random walk boosted by food-pheromone (×5); digs dirt (8%) or clay (2% × dig_strength). Forage: surface walk + food pickup. Return: follows home-pheromone gradient + inverse Manhattan distance to queen. Colony growth: 1 new ant per 5 food deliveries (cap 60). Both pheromone grids decay 0.995/tick.

**Changed file:** `life.py` (+~500 lines)

**5 presets:**

| Preset | Soil profile | Starting ants | Special |
|--------|-------------|---------------|---------|
| Classic Colony | Standard stratified | 15 | Baseline |
| Deep Burrow | Rock below 60% depth | 20 | Deep tunnel routing |
| Sandy Soil | Normal, dig_strength=2 | 12 | Fast digging |
| Rocky Terrain | 12% + depth-scaled rock | 12 | Obstacle avoidance |
| Rainy Day | Standard | 15 | Rain active at start |

**Interactive controls:** `Space` (pause), `n` (step), `f` (drop food at cursor), `w` (toggle rain), `o` (place rock), `+`/`-` (speed), `r` (reset), `R`/`m` (preset menu), `i` (info), `Esc` (exit)

### Added: Matrix Digital Rain — Independent column streams with character mutation and 4-level brightness

Iconic falling-character rain: each column hosts multiple independent streams with own fall speed (0.3–1.5), length (4–rows/2), character array, and mutation rate (random char replacement per tick). 4 brightness tiers: head (white/bold), near-head (bright), mid (normal), tail (dim). New streams spawned at `density × 0.02` per column per step. 3 color modes: green, blue/cyan, rainbow (column-offset cycling). Character pools: katakana, digits, ASCII, symbols, or `01` for Binary Rain.

**Changed file:** `life.py` (+~350 lines)

**6 presets:**

| Preset | Density | Char pool | Color | Character |
|--------|---------|-----------|-------|-----------|
| Classic Green | 0.40 | Katakana+digits+latin+symbols | green | Standard rain |
| Dense Downpour | 0.75 | Full pool | green | Heavy rainfall |
| Sparse Drizzle | 0.15 | Katakana+digits+latin | green | Light drops |
| Katakana Only | 0.40 | Katakana | green | Japanese chars |
| Binary Rain | 0.50 | `01` | green | Binary code |
| Rainbow | 0.40 | Full pool | rainbow | Color-cycling |

**Interactive controls:** `Space` (pause), `n` (step), `d`/`D` (density ±0.05), `c` (cycle color mode), `+`/`-` or `s`/`S` (speed), `r` (reset), `R`/`m` (preset menu), `i` (info), `q`/`Esc` (exit)

### Added: Maze Solving Algorithm Visualizer — 4 pathfinding algorithms with step-by-step exploration animation

Generates perfect mazes via recursive backtracker DFS, then runs one of 4 pathfinding algorithms step by step. BFS (FIFO wavefront, shortest path), DFS (LIFO deep dive), A* (min-heap with Manhattan heuristic), Wall Follower (right-hand rule). Odd-dimensioned grid (wall/passage encoding). Path reconstruction via parent-map traceback. 3 sizes (small ≤21, medium ≤41, large = full terminal). 10 presets spanning all algorithm/size combinations.

**Changed file:** `life.py` (+~400 lines)

**10 presets:** BFS Small/Medium/Large, DFS Small/Large, A* Small/Medium/Large, Wall Follower Small/Medium

**Interactive controls:** `Space` (pause), `n` (step × speed), `s`/`S` (steps/frame 1–30), `r` (regenerate same preset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Lissajous Curve / Harmonograph — Parametric oscillator curves with intensity-accumulating canvas

Traces parametric curves from coupled oscillators: `x = A·exp(−d·t)·sin(fa·t + φ)`, `y = A·exp(−d·t)·sin(fb·t)`. Lateral Harmonograph mode adds 3rd/4th oscillators with independent frequencies for compound figures. Persistent canvas dictionary accretes intensity per hit (+0.15, cap 1.0) with interpolation points (+0.10), producing natural brightness buildup at intersections. 9-level character ramp (`` `.·:;+*#@` ``). Damping causes spiral collapse.

**Changed file:** `life.py` (+~380 lines)

**8 presets:**

| Preset | fa | fb | Phase | Damping | Character |
|--------|----|----|-------|---------|-----------|
| Classic 3:2 | 3.0 | 2.0 | π/4 | 0 | Clean closed Lissajous |
| Figure Eight | 2.0 | 1.0 | π/2 | 0 | Classic ∞ shape |
| Star | 5.0 | 4.0 | π/4 | 0 | Five-pointed star |
| Harmonograph | 2.01 | 3.0 | π/6 | 0.003 | Slow spiral decay |
| Lateral Harmonograph | 2.0 | 3.0 | π/4 | 0.002 | Four-oscillator compound |
| Rose Curve | 7.0 | 4.0 | 0 | 0 | Petal geometry |
| Decay Spiral | 10.0 | 9.0 | π/3 | 0.008 | Rapid high-freq collapse |
| Knot | 5.0 | 3.0 | π/7 | 0.001 | Dense overlapping knot |

**Interactive controls:** `Space` (pause), `n` (step), `a`/`A` (freq A ±0.1), `b`/`B` (freq B ±0.1), `p`/`P` (phase ±0.1), `d`/`D` (damping ±0.001), `c` (clear + restart), `+`/`-` (speed), `r` (reset), `R`/`m` (preset menu), `i` (info), `q` (exit)

### Added: Fluid Rope / Honey Coiling — Liquid rope coiling instability with viscous pool accumulation

Models the spiral buckling when a viscous stream falls onto a surface. Segmented falling stream interpolated between pour axis and coil landing point. Coil angle advances at fluid-specific angular speed; landing traces a circle of `coil_radius`. Pool accumulates at landing with Gaussian spread; viscous diffusion (`spread_rate = 0.02 / viscosity`) flattens it. Trail of 80 recent landing positions draws the coil pattern. Sinusoidal wobble along stream suggests weight-induced flex.

**Changed file:** `life.py` (+~350 lines)

**4 presets:**

| Preset | Viscosity | Flow rate | Coil speed | Character |
|--------|-----------|-----------|-----------|-----------|
| Honey | 1.0 | 1.0 | 2.5 rad/s | Slow, thick coils |
| Chocolate | 0.7 | 1.3 | 3.5 rad/s | Moderate viscosity |
| Shampoo | 0.5 | 1.5 | 5.0 rad/s | Fast thin coils |
| Lava | 2.0 | 0.6 | 1.2 rad/s | Very slow, wide coils |

**Interactive controls:** `Space` (pause), `n` (step), `h`/`H` (pour height ±0.05), `f`/`F` (flow rate ±0.1), `v`/`V` (viscosity ±0.1), `s`/`S` (surface drift ±0.5), `+`/`-` (speed), `r` (reset), `R`/`m` (preset menu), `i` (info), `q` (exit)

### Added: Snowfall & Blizzard — Size-dependent particles with dual-frequency wind gusts and accumulation physics

Each snowflake carries size class (small/medium/large), wobble phase, and velocity responding to a composite wind field from two superimposed sine waves. Larger flakes fall faster. Per-column accumulation tracked as continuous height → Unicode block characters (`▁▂▃▄▅▆▇█`). Wind above threshold shear-transfers snow between columns and launches surface drift particles. Visibility degrades progressively for blizzard/whiteout presets. Three character sets by size class: small (`·.,:;'`), medium (`°∘○◦*+~`), large (`❄❅❆✻✼◎`).

**Changed file:** `life.py` (+~400 lines)

**6 presets:**

| Preset | Density | Wind | Temp | Visibility |
|--------|---------|------|------|-----------|
| Gentle Snowfall | 80 | 0.3 | −3°C | 1.00 |
| Steady Winter Storm | 180 | 1.2 | −8°C | 0.75 |
| Heavy Blizzard | 400 | 3.5 | −15°C | 0.35 |
| Arctic Whiteout | 600 | 5.0 | −25°C | 0.15 |
| Wet Spring Snow | 120 | 0.5 | +1°C | 0.85 |
| Mountain Squall | 350 | 2.5 | −10°C | 0.45 |

**Interactive controls:** `Space` (pause), `n` (step), `w`/`W` (wind ±0.3), `d` (flip wind direction), `f`/`F` (density ±40), `t`/`T` (temperature ±1°C), `+`/`-` (speed), `i` (info), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Fourier Epicycle Drawing — DFT decomposition of closed paths into spinning circular harmonics

Complete DFT pipeline converting closed 2D paths into rotating epicycles. Coefficients (amplitude, phase per frequency k) sorted by amplitude descending so largest circles drawn first. Playback: `dt = 2π/N` per step, tip = Σ `amp_k × exp(i(k×t + phase_k))`. Active circle count adjustable live — reducing shows how higher harmonics add sharp features. Free-draw mode: cursor-based path input, DFT on Enter. 6 built-in shapes at 128 sample points. Heart uses cardioid formula `x = 16sin³(t)`.

**Changed file:** `life.py` (+~400 lines)

**7 presets:** Free Draw (cursor input → DFT), Circle (1 coefficient), Square (many harmonics for corners), Star (alternating radii), Figure Eight (lemniscate), Heart (classical cardioid), Spiral Square (polar curve)

**Interactive controls:** `Space` (play/pause), `n` (step), `+`/`-` (speed), `[`/`]` (remove/add epicycle frequency), `c` (toggle circle display), `i` (info), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit); free-draw: arrows (move cursor), `d` (toggle pen), `x` (clear), `Enter` (compute DFT + play)

### Added: DNA Helix & Genetic Algorithm — Rotating 3D ASCII helix synchronized with live GA convergence

Pairs a continuously animated 3D ASCII double-helix (sinusoidal strands, depth-based `●`/`○`, A/T/C/G base-pair bridges) with a live genetic algorithm. Helix rotation advances 0.15 rad per GA generation. GA: tournament selection (k=3), single-point crossover, bit-flip mutation, deterministic elitism. Two fitness modes: Hamming-distance matching and Royal Road (complete 8-bit schema blocks). Stats panel with sparkline fitness history + genome comparison.

**Changed file:** `life.py` (+~450 lines)

**6 presets:**

| Preset | Genome | Pop | Mutation | Fitness |
|--------|--------|-----|---------|---------|
| Classic Binary GA | 32 | 40 | 2% | Hamming vs random target |
| OneMax Challenge | 64 | 50 | 1.5% | Maximize 1-bits |
| Long Strand | 128 | 60 | 0.5% | Slow convergence |
| Hyper-Mutation | 32 | 40 | 10% | Chaotic exploration |
| Minimal Pop | 48 | 10 | 3% | Strong genetic drift |
| Royal Road | 64 | 50 | 2% | Schema-block staircase |

**Interactive controls:** `Space` (play/pause), `n` (step), `+`/`-` (steps/frame), `i` (toggle stats), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Sorting Algorithm Visualizer — 6 algorithms with pre-computed step audit trails and animated bar charts

Pre-computes a complete step-by-step audit trail for the chosen algorithm, then replays against a live animated bar chart. Step tuples carry full array snapshots and type tags (`cmp`, `swap`, `write`, `sorted`, `pivot`). Color coding: green (confirmed sorted), red (active swap), yellow (comparison), white (default). Array auto-scales to terminal width (up to 200 elements). Running comparison + swap/write counters.

**Changed file:** `life.py` (+~500 lines)

**6 algorithms:**

| Algorithm | Complexity | Strategy |
|-----------|-----------|----------|
| Bubble Sort | O(n²) | Adjacent compare-and-swap |
| Quicksort | O(n log n) avg | Lomuto partition with pivot marking |
| Merge Sort | O(n log n) | Recursive top-down element-by-element merge |
| Heap Sort | O(n log n) | Max-heap build then extract |
| Radix Sort (LSD) | O(nk) | Counting sort per decimal digit |
| Shell Sort | sub-O(n²) | Halving gap sequence insertion |

**Interactive controls:** `Space` (play/pause), `n` (step), `+`/`-` (step speed), `i` (info: comparisons, swaps, step index), `r` (re-shuffle same algorithm), `R`/`m` (algorithm menu), `q`/`Esc` (exit)

### Added: Tornado & Supercell Storm — Layered vortex physics with rain, debris, lightning, and mesocyclone

Six interconnected subsystems: tornado funnel (sinusoidal drift + wobble, pulsating radius), rain particles (200–500, inward spiral toward storm center), debris (tangential + radial + updraft forces, ∝ min(1, 2r/dist)), branching lightning (random-walk + 30% branch probability), mesocyclone cloud rotation, and destruction path (last 500 overrun cells). Funnel radius pulses via `base_r + 0.3×sin(t×1.5)`. Debris drag 0.97/step. Dust Devil preset: no rain, rotation speed 6.0.

**Changed file:** `life.py` (+~640 lines)

**6 presets:** EF3 Wedge (wide, heavy debris), Rope Tornado (thin, high wobble), Supercell Outbreak (largest storm radius), Rain-Wrapped (funnel hidden by 500 rain particles), Nighttime Storm (lightning-illuminated), Dust Devil (no rain, rapid rotation)

**Interactive controls:** `Space` (pause), `n` (step), `+`/`-` (speed), `L` (force lightning), `i` (info), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Pendulum Wave — Analytically computed lengths for exact realignment with SHM integration

Pendulum lengths computed analytically: pendulum `i` completes `N_base + i` oscillations in realignment period `T`, requiring `L_i = g × (T / (2π × (N_base + i)))²`. Exact SHM solution `θ(t) = A·cos(ω·t)` — zero drift, no numerical integration. Renders horizontal support bar, Bresenham strings, colored bobs, fading motion trails, and bottom wave-curve indicator plotting instantaneous bob positions. Speed multiplier 1–10 steps per frame.

**Changed file:** `life.py` (+~350 lines)

**6 presets:**

| Preset | Pendulums | Realign period | Character |
|--------|-----------|---------------|-----------|
| Classic Wave | 15 | 60 s | Elegant snake + convergence |
| Dense Array | 24 | 60 s | Rich fine wave structure |
| Wide Spread | 12 | 40 s | Dramatic phase shifts |
| Quick Cycle | 15 | 20 s | Full pattern in seconds |
| Slow Meditation | 18 | 120 s | Contemplative pace |
| Grand Ensemble | 32 | 60 s | Maximum complexity |

**Interactive controls:** `Space` (pause), `n` (step), `+`/`-` (speed multiplier), `i` (info), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Aurora Borealis (Northern Lights) — Altitude-stratified emission bands with curtain dynamics and solar wind

Physics-inspired rendering of Northern Lights with 4 altitude-stratified emission bands: high O (red), mid O (green), high N₂ (purple/magenta), low N₂ (blue/violet). Curtains as vertical shimmering bands with sinusoidal fold control points creating rippled-drape appearance. Solar wind particles (~60) fall with field-line curvature toward magnetic axis. Substorm breakup events trigger stochastic brightness spikes. Pulsating Aurora preset modulates brightness with per-curtain sine frequency. Magnetic field-line overlay toggle.

**Changed file:** `life.py` (+~450 lines)

**4 presets:** Quiet Arc (3 curtains, calm), Substorm Breakup (6 curtains, explosive + frequent spikes), Pulsating Aurora (5 curtains with pulse frequencies), Coronal Mass Ejection (8 curtains, maximum intensity)

**Interactive controls:** `Space` (pause), `n` (step), `+`/`-` (intensity), `w`/`s` (wind strength), `f` (toggle field lines), `i` (info), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Solar System Orrery — Analytical Keplerian mechanics with asteroid belt and comets

Faithful overhead-view orrery using analytical Kepler equation solver: Newton-Raphson `M = E − e·sin(E)` (50 steps, tol 10⁻⁶), true anomaly via half-angle atan2, heliocentric distance from `r = a(1 − e·cos E)`. Real orbital parameters for all 8 planets. Asteroid belt: 120 bodies at 2.1–3.3 AU with Kepler third-law periods. Comets: high-eccentricity orbits (e = 0.85–0.97) with trailing tails. Three zoom levels (inner 2 AU, outer 35 AU, full). Aspect-ratio-corrected projection.

**Changed file:** `life.py` (+~500 lines)

**6 presets:** Full Solar System (all 8 + asteroids + comets), Inner Planets (Mercury–Mars), Outer Planets (Jupiter–Neptune), Earth & Neighbors, Comet Flyby (long-period e=0.967), Grand Alignment (near conjunction start)

**Interactive controls:** `Space` (pause), `n` (step), `+`/`-` (time speed), `z` (cycle zoom), `o` (toggle orbits), `l` (toggle labels), `i` (info panel), `Tab` (cycle selected planet), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Black Hole Accretion Disk — Relativistic dynamics with frame-dragging, gravitational lensing, and jets

Particle-based relativistic astrophysics: Keplerian disk orbiting from ISCO outward, gravitational acceleration with relativistic correction `(1 + 3M/r²)`, Lense-Thirring frame-dragging ∝ `spin × M/r³`, viscous angular momentum transport. Accreted particles spawn bipolar jet particles. Hawking radiation particles near horizon (count ∝ 1/mass). Gravitational lensing of background star field with Einstein ring. Temperature-mapped ASCII coloring (blue→white→yellow→red). 5 visualization layers.

**Changed file:** `life.py` (+~550 lines)

**6 presets:** Stellar (mass 30, spin 0.3), Supermassive (mass 100, spin 0.6), Kerr Spinning (spin 0.95, maximum dragging), Quasar (mass 200, highest accretion), Micro Black Hole (mass 5, Hawking-dominant), Binary Merger (dual-center spiral)

**Interactive controls:** `Space` (pause), `n` (step), `+`/`-` (speed), `v` (cycle view layer), `h` (toggle event horizon), `p` (toggle photon ring), `i` (info), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Volcanic Eruption & Lava Flow — Multi-physics with magma chamber, pyroclastic currents, and ballistic ejecta

Full multi-physics volcanic simulator: magma chamber tracks pressure/recharge/volume/viscosity; eruption typed (Strombolian/Plinian/Hawaiian/Vulcanian) with different lava/ejecta ratios. Lava flows under gravity with temperature-dependent viscosity, cools and solidifies into permanent rock. Pyroclastic density currents hug terrain surface. Wind-advected ash + SO₂ gas diffuse across grid. Ballistic ejecta follow parabolic trajectories. Procedural terrain: radial cones, calderas, fissures. 6 visualization layers.

**Changed file:** `life.py` (+~600 lines)

**6 presets:** Strombolian (rhythmic mild eruptions), Plinian (catastrophic explosive), Hawaiian (fluid effusion), Vulcanian (viscous burst cycles), Caldera Collapse (4 ring vents), Fissure Eruption (6-vent linear rift)

**Interactive controls:** `Space` (pause), `n` (step), `+`/`-` (speed), `l` (cycle visualization layer), `i` (info overlay), `r` (reset), `R`/`m` (preset menu), `q`/`Esc` (exit)

### Added: Ocean Currents & Thermohaline Circulation — UNESCO equation of state with gyre circulation and plankton blooms

Coupled temperature, salinity, density, current, upwelling, nutrient, and plankton fields. Density from simplified UNESCO EOS (`ρ = 1000 + 0.8S − 0.003(T−4)² + 0.01S(35−S)`). Gyre circulation as Gaussian-weighted tangential flow with Coriolis correction. Deep-water formation zones cool/salinify, driving downwelling; divergent zones upwell nutrients. Semi-Lagrangian advection for all tracer fields. Plankton blooms where nutrients >0.4 and upwelling positive. 6 visualization layers.

**Changed file:** `life.py` (+~550 lines)

**6 presets:** Gulf Stream (western boundary current), Pacific Gyre (Kuroshio), Antarctic Circumpolar (eastward belt), El Niño (weakened trades, warm tongue), Thermohaline Conveyor (deep cold return), Random Ocean (2–5 random gyres)

**Interactive controls:** `L`/`V` (cycle visualization layer), `+`/`-` (speed), `Space` (pause), `?` (help), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: Atmospheric Weather System — Pressure-driven wind with Coriolis, fronts, clouds, and precipitation

Full 2D grid of pressure, temperature, humidity, wind, cloud density, and precipitation. Pressure from drifting Gaussian kernels. Wind from pressure gradient with latitude-dependent Coriolis deflection. Temperature/humidity advected semi-Lagrangianly, relaxed toward latitude equilibrium. Clouds diagnosed from humidity + lift + convergence. Precipitation (rain at T>0°C, snow at T≤0°C) when cloud >0.7. Frontal boundaries advect and enhance local temperature gradients + precipitation. 5 visualization layers.

**Changed file:** `life.py` (+~550 lines)

**6 presets:** Tropical Cyclone (960 hPa low, warm moist), Mid-Latitude Front (cold/warm fronts), High Pressure Dome (1040 hPa dry), Monsoon Season (thermal low + oceanic high), Arctic Outbreak (1045 hPa polar), Random Atmosphere (3–6 random centers)

**Interactive controls:** `L`/`V` (cycle visualization layer), `+`/`-` (speed), `Space` (pause), `?` (help), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: Tectonic Plate Simulation — Voronoi plates with convergent/divergent/transform boundary physics

Voronoi-partitioned plates with velocity vectors and fractional movement accumulators. Boundary classification by relative velocity: convergent (mountain building ∝ convergence × speed, subduction arcs with 2% volcanism), divergent (rifting, mid-ocean ridge creation), transform (stochastic earthquake noise). Volcanic hotspots accumulate + spread material. Laplacian erosion every 3 steps + isostatic rebound. 17-level elevation-character table from −11,000m trench to +9,000m peak. Optional plate-color overlay.

**Changed file:** `life.py` (+~550 lines)

**6 presets:** Pangaea Breakup (clustered continental), Island Arcs (mixed continental/oceanic), Continental Collision (two groups converging), Mid-Ocean Ridges (radially diverging), Ring of Fire (all converge toward ocean), Random Drift (fully random)

**Interactive controls:** `Space` (pause), `+`/`-` (speed ×0.25–5.0), `P` (toggle plate-color overlay), `?` (help), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: Doom-style First-Person Raycaster — DDA ray casting with fisheye correction, wall shading, and minimap

Column-based first-person raycasting on 16×16 tile maps using DDA (digital differential analysis). Perpendicular distance corrected for fisheye via `cos(ray_angle − player_angle)`. Wall height inversely proportional to distance, shaded through 5-char ramp (`█▓▒░·`). Floor gradient below walls. Full AABB collision with 0.2-unit margin and wall sliding. Top-left minimap shows full grid + player position. FOV 60° (π/3), max depth 16 units.

**Changed file:** `life.py` (+~400 lines)

**6 presets:** Dungeon (nested rooms + dead ends), Office (cubicle rows + atriums), Outdoor Ruins (sparse broken walls), Arena (open + pillar clusters), Maze (dense labyrinth), Fortress (thick castle walls)

**Interactive controls:** `W`/`S` (forward/back), `A`/`D` (strafe), `Q`/`E` or arrows (rotate), `M` (toggle minimap), `?` (help), `Space` (pause), `Esc` (exit)

### Added: Artificial Life Ecosystem — Neural-network-brained creatures with evolvable traits and reproduction

Digital terrarium where each creature is driven by a 6→4→2 feed-forward neural network with `tanh` activations. Six inputs: direction to nearest food/threat, energy fraction, bias. Two outputs produce `(dr, dc)` movement. Movement costs energy ∝ speed × size; reproduction at 85% max energy with brain-weight and trait mutation. Three types: herbivores, predators, omnivores. Food grid regenerates + spreads. 4-cell bucket grid for O(1) neighbor lookup. Population sparkline HUD tracks all three types.

**Changed file:** `life.py` (+~500 lines)

**6 presets:** Grassland (40 herbs), Predator-Prey (35 herb + 8 pred), Harsh Desert (low food, high mutation), Coral Reef (all 3 types), Evolution Lab (35% mutation), Primordial Soup (minimal seed)

**Interactive controls:** `Space` (pause), `N` (step), `S` (toggle stats HUD), `+`/`-` (food regrowth), `<`/`>` (speed), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: Music Visualizer — Self-contained audio-reactive display with synthetic signal generation

Fully self-contained audio-reactive visualization — no microphone needed. Synthesises pentatonic tones with harmonics + LFO envelope + Gaussian noise, maps to simulated 32-bin FFT spectrum. Beat detection via energy/average ratio threshold (1.5×) spawns particle bursts from center. Six view modes: Spectrum Bars (vertical chart + peak hold), Waveform Scope (oscilloscope trace), Beat Particles (center burst), Combined View (all three), Bass Tunnel (radial zoom from bass energy), Frequency Rain (per-bin falling columns). 4 color palettes.

**Changed file:** `life.py` (+~450 lines)

**Interactive controls:** `N`/`Shift+N` (next/prev view), `V` (cycle view within preset), `C` (cycle palette), `+`/`-` (sensitivity), `Space` (pause), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: Shader Toy — Real-time per-pixel math functions rendered as ASCII with 4 color palettes

Each terminal cell treated as a pixel: normalised coordinates `(nx, ny) ∈ [-1,1]²` and global time `t` fed into the active shader function (pure `math` ops), returning intensity → 12-char ASCII density ramp + 4 palettes (Rainbow, Fire, Ocean, Mono). Two live parameters `a`, `b` warp geometry without reloading. 10 shaders: Plasma Waves (4 summed sins), Tunnel Zoom (polar 1/r), Metaballs (5 potential blobs), Moiré Rings, Fractal Flame (8-iteration IFS), Warp Grid, Lava Lamp, Matrix Rain, Kaleidoscope (polar folding), Spiral Galaxy.

**Changed file:** `life.py` (+~400 lines)

**Interactive controls:** `N`/`Shift+N` (next/prev shader), `C` (cycle palette), `[`/`]` (param a ±0.1), `{`/`}` (param b ±0.1), `<`/`>` (speed 0.1–5.0), `Space` (pause), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: 3D Game of Life — 20³ voxel grid with 26-neighbor Moore rules and volumetric ASCII ray casting

Conway's Game of Life extended to a 20×20×20 voxel cube with 26-neighbour Moore rules. Volumetric ASCII ray caster: rays stepped through grid, hit voxels shaded with position-based hue, diffuse directional light, ambient occlusion (from 6-face neighbor count), and distance fog. Auto-orbiting camera. 8 presets with different birth/survival rule sets and initial densities (6–20%).

**Changed file:** `life.py` (+~450 lines)

**8 presets:**

| Preset | Birth | Survive | Density | Character |
|--------|-------|---------|---------|-----------|
| Classic 3D | {5} | {4,5} | 12% | Standard |
| Clouds | {5,6,7} | {4,5,6} | 10% | Diffuse |
| Crystal | {6} | {5,6,7} | 8% | Angular |
| Amoeba | {5} | {3,4,5} | 15% | Organic |
| Diamoeba 3D | {5,6,7} | {5,6,7,8} | 12% | Expanding |
| Sparse | {6,7,8} | {5,6,7} | 6% | Minimal |
| Pulse | {4} | {3,4} | 20% | Oscillating |
| Builder | {6} | {4,5,6} | 10% | Constructive |

**Interactive controls:** Arrows (orbit camera), `+`/`-` (zoom), `A` (toggle auto-rotation), `N` (single step), `Space` (pause), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: SDF Ray Marching 3D Renderer — Sphere-tracing with Blinn-Phong shading, soft shadows, and Mandelbulb fractal

Full sphere-tracing renderer: rays step through scene SDF (up to 128 iterations, hit threshold 0.001). Normals via central-differenced finite differences. Blinn-Phong shading (ambient 0.15, diffuse N·L, specular (N·H)^32). Optional 32-step soft-shadow ray march. Output mapped to 11-character density ramp (` .:-=+*#%@█`). Auto-orbiting camera. Mandelbulb scene exposes fractal power as live parameter (2–16).

**Changed file:** `life.py` (+~450 lines)

**6 presets:** Sphere (`|p|−1`), Torus (R=1.0, r=0.4), Multi-Shape (sphere+torus+box union), Mandelbulb (power-8 DE), Infinite Spheres (mod-3 domain repetition), Smooth Blend (smooth-min union k=0.5)

**Interactive controls:** Arrows (orbit camera ±0.1 rad), `+`/`-` (zoom 1.5–12.0), `A` (toggle auto-rotation), `S` (toggle shadows), `L`/`Shift+L` (light azimuth/elevation), `P`/`Shift+P` (Mandelbulb power ±1), `Space` (pause), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: 3D Terrain Flythrough — First-person perspective flight over procedural heightmaps with day/night cycle

Column-by-column raycaster projects a 256×256 tiled elevation field into screen space. Terrain generated from 4-layer cosine-interpolated noise with type-specific shaping (peak exponent, canyon carve, island peaks, U-valley, sine-fold alien). Altitude-based color bands (ocean → sand → grass → highland → snow). Continuous day/night cycle advances sun/moon arc, fades stars, tints sky. Camera auto-drifts with WASD flight controls, pitch/yaw, altitude, speed, and FOV adjustments.

**Changed file:** `life.py` (+~550 lines)

**6 presets:** Rolling Hills (gentle), Mountain Range (peak-sharpened), Desert Canyon (canyon carve), Volcanic Islands (radial peaks), Glacial Valley (U-shaped), Alien World (sine-fold)

**Interactive controls:** `W`/`A`/`S`/`D` (fly), arrows (pitch/yaw), `E`/`C` (altitude), `+`/`-` (speed), `F`/`Shift+F` (FOV), `T` (toggle day/night), `Shift+T` (advance time), `Space` (pause), `R` (reset), `M` (preset menu), `Q`/`Esc` (exit)

### Added: Real-Time Minimap Overlay — Universal downscaled grid overview for all 65+ modes

Toggleable overlay (Tab key, global) rendering a proportionally downscaled picture of the entire simulation grid in the top-right corner inside a Unicode box-drawing border. Universal `_get_minimap_data()` accessor detects active mode and returns `(rows, cols, sample_fn, viewport_rect)`, handling every storage format: sparse dicts, float/int/bool 2D arrays, particle lists, fractal buffers, WFC superposition grids. Capped at 40×20 characters, aspect-ratio-preserved. 5-glyph density ramp (` ░▒▓█`) with dim→cyan→bold green color. Yellow viewport rectangle when zoomed in. Suppressed when menus are open.

**Changed file:** `life.py` (+~250 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Universal accessor | Handles dict sparse, float/int/bool 2D, particle lists, fractal buffer, WFC, Wolfram rows, GoL cells |
| Dimensions | Max 40×20 characters, aspect-ratio-preserved |
| Density glyphs | ` ░▒▓█` at thresholds 0/0.2/0.45/0.7/1.0 |
| Viewport indicator | Yellow border when view covers subset of grid |
| Menu suppression | `_any_menu_open()` checks ~60 `*_menu` booleans |

**Interactive controls:** `Tab` (toggle minimap on/off, global across all modes)

### Added: Interactive Mode Browser — Searchable categorized launcher for all 65 simulation modes

Full-screen overlay (press `m`) presenting all 65 simulation modes in a scrollable, categorised, searchable list. `MODE_REGISTRY` (65 entries) stores each mode's name, key binding, category, description, and enter/exit methods. 10 categories with canonical ordering. Real-time substring search filters across name, description, and category as you type. Navigation: arrows/j/k, PgUp/PgDn (±10), Home/End. Enter cleanly exits current mode and launches selected one. Scrollbar glyph (█) on right edge.

**Changed file:** `life.py` (+~300 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Registry | 65 entries across 10 categories with enter/exit method references |
| Search | Real-time substring match against name+description+category |
| Mode transition | `_exit_current_modes()` iterates registry calling exit methods, then calls new mode's enter method |
| Categories | Classic CA, Particle & Swarm, Physics & Waves, Fluid Dynamics, Chemical & Biological, Game Theory & Social, Fractals & Chaos, Procedural & Computational, Complex Simulations, Meta Modes |

**Interactive controls:** `m` (open browser), `↑`/`↓` or `j`/`k` (navigate), PgUp/PgDn (±10), Home/End (first/last), typing (search filter), Backspace (delete search char), `Enter` (launch selected mode), `Esc` (close)

### Added: Smoothed Particle Hydrodynamics (SPH) — Particle-based Navier-Stokes with Poly6/Spiky/viscosity kernels

Full SPH fluid solver: density summation via Poly6 kernel W(r,h) = (315/64πh⁹)(h²−r²)³, pressure from isothermal EOS p = k(ρ−ρ₀), pressure gradient via Spiky kernel, viscosity diffusion via Laplacian kernel, symplectic Euler integration. Smoothing radius h=1.5, brute-force O(n²) interactions. Reflective wall boundaries with restitution damping. 3 visualization modes: density, velocity, pressure. Fountain preset adds continuous vy kick to bottom-center particles.

**Changed file:** `life.py` (+~420 lines)

**6 presets:**

| Preset | Configuration | Character |
|--------|--------------|-----------|
| Dam Break | Fluid column, left 25% | Gravitational collapse + spreading |
| Double Dam | Two columns, left + right | Head-on collision + splash |
| Dropping Block | Pool + block above | Impact splash + cavity |
| Rain | Random upper-half seeding | Scattered droplets accumulating |
| Wave Tank | Tilted initial water line | Sloshing between walls |
| Fountain | Small pool + upward velocity kick | Continuous jet with parabolic arcs |

**Interactive controls:** `Ctrl+A` (toggle mode), `Space` (play/pause), `n` (step), `v` (cycle view), `+`/`-` (gravity ×/÷1.2), `<`/`>` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: FDTD Electromagnetic Wave Propagation — 2D TM Yee algorithm with PML, lossy media, and dielectrics

2D TM-mode FDTD on a Yee staggered grid updating Ez, Hx, Hy per timestep. E-field update incorporates per-cell permittivity ε and conductivity σ for unified free-space and lossy media. Quadratically graded PML (6–10 cells, σ ramps 0→0.8) absorbs outgoing waves. Soft-injected sources with Gaussian ramp-up over 30 steps avoid transient artifacts. Phase offsets between sources produce beam steering and dipole patterns. 10 presets spanning point sources, diffraction, waveguides, lenses, and resonant cavities.

**Changed file:** `life.py` (+~500 lines)

**10 presets:**

| Preset | Geometry | Key effect |
|--------|----------|------------|
| Point Source | Single center source | Circular wavefronts, PML absorption |
| Double Slit | Wall + two slits + plane wave | Young-type interference |
| Single Slit | Wall + one slit + plane wave | Diffraction envelope |
| Waveguide | Conducting walls + point source | Guided mode propagation |
| Lens Focusing | Convex dielectric ε=4.0 | Refractive focusing |
| Antenna Dipole | Two in-phase+π sources | Dipole radiation pattern |
| Phased Array | 8 sources, progressive phase | Steered beam |
| Corner Reflector | Conducting L-reflector | Retroreflected beam |
| Resonant Cavity | Conducting box + interior source | Standing-wave resonance |
| Dielectric Scatter | Three high-ε cylinders | Forward scattering + shadow |

**Interactive controls:** `Ctrl+E` (toggle mode), `Space` (play/pause), `n` (step), `v` (cycle view: Ez/|E|/|H|), `f`/`F` (frequency ±0.01), `p` (add point source), `c` (clear fields), `+`/`-` (speed steps), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Magnetic Field Lines — Boris push integrator for charged particles in 4 field geometries

Full 2D charged-particle tracker using the Boris push — a symplectic integrator splitting the timestep into two half-electric kicks bracketing a magnetic rotation, guaranteeing exact energy conservation in pure B-fields. Four field geometries: uniform, dipole (∝ 1/r³), magnetic bottle (parabolic Bz profile with mirror force), quadrupole (focusing gradient). Reflective wall boundaries. Rolling trail deques (50–2000 points). Field-line overlay at 4×3 intervals. 3 trail visualizations: age-fade, velocity-color, energy-color.

**Changed file:** `life.py` (+~500 lines)

**8 presets:**

| Preset | Field | Particles | Character |
|--------|-------|-----------|-----------|
| Cyclotron Orbits | Uniform Bz=1.5 | 10 | Circular orbits at varying radii |
| E×B Drift | Uniform Bz=2.0, Ey=−1.5 | 8 | Horizontal drift ⊥ both fields |
| Magnetic Bottle | Bottle Bz=2.0 | 12 | Mirror trapping |
| Dipole Field | Dipole Bz=3.0 | 10 | Radiation-belt trajectories |
| Quadrupole Trap | Quadrupole Bz=2.0 | 14 | Complex orbital topology |
| Mixed Charges | Uniform Bz=2.0 | 12 | Alternating +/− spiral opposite |
| Magnetic Shear | Sheared uniform | 10 | Chaotic non-closing orbits |
| Hall Effect | Uniform Bz=2.5, Ex=1.0 | 10 | Hall drift direction |

**Interactive controls:** `Ctrl+N` (toggle mode), `Space` (play/pause), `n` (step), `b`/`B` (Bz ±0.2), `e` (toggle E-field), `f` (toggle field overlay), `v` (cycle trail view), `p` (spawn particle), `c` (clear trails), `+`/`-` (dt ×/÷1.5), `<`/`>` (steps/frame), `[`/`]` (trail ±50), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Cellular Potts Model (CPM) — Metropolis energy minimization with adhesion, area constraints, and chemotaxis

Each terminal cell is a lattice pixel belonging to a numbered biological cell. Metropolis step: propose neighbor copy, evaluate Hamiltonian change (contact adhesion J[type][type] + area elastic penalty λ(a−A)² + chemotaxis bias), accept/reject with Boltzmann exp(−ΔH/T). Hundreds of attempts per frame produce tissue morphologies: differential adhesion sorting, wound healing migration, tumor invasion, and chemotactic gradient climbing. Incremental per-cell area cache keeps the inner loop O(1). 3 visualization modes: cell type, cell ID, boundaries.

**Changed file:** `life.py` (+~450 lines)

**6 presets:**

| Preset | Description |
|--------|-------------|
| Cell Sorting | Two intermixed types sort by differential adhesion (Steinberg mechanism) |
| Wound Healing | Dense sheet migrates to fill empty gap |
| Tumor Growth | Weaker-adhesion tumor cells invade normal tissue |
| Checkerboard | Alternating types slowly round corners |
| Foam / Bubbles | Large-target-area cells with low surface tension coarsen |
| Chemotaxis | Cells climb diffusing chemical gradient |

**Interactive controls:** `Ctrl+T` (toggle mode), `Space` (play/pause), `n` (step), `v` (cycle view), `t`/`T` (temperature ±1.0), `a`/`A` (area constraint ±0.5), `<`/`>` (steps/frame ×2/÷2), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Chaos Game / IFS Fractal — Iterated function system with log-scaled density heatmap and color-by-transform

A single point randomly picks from a set of weighted affine contractions (`x'=ax+by+e`, `y'=cx+dy+f`) each step, tracing the IFS attractor over thousands of iterations. 2D density field accumulated with log-scale rendering (`·∙:;+*#%@`) for simultaneous visibility of sparse and dense regions. Adaptive bounding-box auto-scaler fits the fractal to the terminal. Color-by-transform mode assigns distinct colors per affine map, exposing self-similarity structure.

**Changed file:** `life.py` (+~350 lines)

**8 presets:**

| Preset | Transforms | Character |
|--------|-----------|-----------|
| Sierpinski Triangle | 3 | 3 contractions toward triangle vertices |
| Barnsley Fern | 4 | Stem + main leaf + two leaflets |
| Vicsek Snowflake | 5 | 4 corners + center at ratio 1/3 |
| Sierpinski Carpet | 8 | 8 edge/corner positions at ratio 1/3 |
| Dragon Curve | 2 | Heighway dragon rotations |
| Maple Leaf | 4 | Asymmetric leaf contractions |
| Koch Snowflake | IFS | Triangular snowflake as affine IFS |
| Crystal | 6+ | 6-fold symmetric contractions |

**Interactive controls:** `Ctrl+G` (toggle mode), `Space` (play/pause), `n` (accumulate batch), `c` (toggle color-by-transform), `>`/`<` (points/frame ×2/÷2), `x` (clear canvas), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Chladni Plate Vibration Patterns — Biharmonic plate equation with 13-point stencil and sand migration

Replicates Chladni figures — patterns sand makes on vibrating metal plates. Integrates `d²z/dt² = −c²∇⁴z − γ(dz/dt) + A·sin(ωt)·δ(center)` using velocity-Verlet. Biharmonic ∇⁴ approximated by 13-point stencil: `20z − 8(NSEW) + 2(diags) + (next-NSEW)`. Clamped 2-cell border boundary. Sand density flows from high-displacement cells toward low-displacement, accumulating on nodal lines. Harmonic Sweep auto-increments frequency through mode shapes.

**Changed file:** `life.py` (+~380 lines)

**8 presets:**

| Preset | Mode (m,n) | Character |
|--------|-----------|-----------|
| Classic (2,3) | 2, 3 | Elegant star-like figure |
| Simple (1,2) | 1, 2 | Basic cross pattern |
| Complex (3,5) | 3, 5 | Intricate high-mode |
| Symmetric (4,4) | 4, 4 | Square-symmetric |
| Cathedral (5,7) | 5, 7 | Dense cathedral-window |
| Butterfly (2,5) | 2, 5 | Butterfly-wing |
| Diamond (3,4) | 3, 4 | Diamond lattice |
| Harmonic Sweep | auto | Auto-cycles through frequencies |

**Interactive controls:** `Ctrl+L` (toggle mode), `Space` (play/pause), `n` (step), `m`/`N` (cycle mode numbers), `f`/`F` (frequency ±), `d`/`D` (damping ±), `+`/`-` (amplitude), `v` (cycle view: sand/displacement/energy), `s` (redistribute sand), `>`/`<` (speed), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Rayleigh-Bénard Convection — 2D Boussinesq approximation with Rayleigh-number-controlled convection rolls

Heated from below, cooled from above: buoyancy drives hot fluid up and cold down, self-organizing into rolls and cells. Simplified 2D Boussinesq: temperature advected/diffused, buoyancy ∝ `Ra × (T − T_ref)` drives vertical velocity. Velocity diffused with Prandtl-scaled viscosity, Gauss-Seidel pressure projection for incompressibility. Upwind advection for stability at high Ra. 3 visualization modes: temperature, velocity magnitude, vorticity.

**Changed file:** `life.py` (+~400 lines)

**8 presets:**

| Preset | Ra | Pr | Character |
|--------|----|----|-----------|
| Classic Rolls | 2000 | 0.71 | Steady convection rolls |
| Gentle Convection | 500 | 0.71 | Slow, wide cells |
| Turbulent Cells | 8000 | 0.71 | Vigorous convection |
| Bénard Hexagons | 3000 | 0.71 | Hexagonal cell formation |
| Mantle Convection | 1200 | 10.0 | Earth-like slow overturning |
| Solar Granulation | 10000 | 0.025 | Sun-surface rapid convection |
| Asymmetric Heating | 3000 | 0.71 | Hot spot on one side |
| Random Perturbation | 4000 | 0.71 | Random initial noise |

**Interactive controls:** `Ctrl+R` (toggle mode), `Space` (play/pause), `n` (step), `v` (cycle view), `+`/`-` (Ra ×/÷1.2), `>`/`<` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Double Pendulum Chaos — RK4 integration with trajectory trails and dual-pendulum divergence comparison

Full nonlinear double-pendulum Lagrangian ODEs for `[θ₁, θ₂, ω₁, ω₂]` integrated with 4th-order Runge-Kutta at dt=0.005s. Trajectory trails record lower bob position via Bresenham line drawing, decaying through `█▓▒░·` (up to 500–2000 points). Dual-pendulum mode runs a second integrator with tiny angle perturbation, showing exponential separation of trajectories with live divergence readout.

**Changed file:** `life.py` (+~450 lines)

**8 presets:**

| Preset | θ₁ | θ₂ | Masses | Perturbation | Character |
|--------|----|----|--------|-------------|-----------|
| Classic Chaos | 3π/4 | 3π/4 | 1:1 | 0.001 rad | Standard chaotic regime |
| Gentle Swing | 3π/20 | 3π/20 | 1:1 | 0.01 rad | Near-integrable |
| Heavy Lower | 3π/5 | 4π/5 | 1:3 | 0.001 rad | Bottom-heavy |
| Heavy Upper | 3π/5 | 4π/5 | 3:1 | 0.001 rad | Top-heavy |
| Maximum Chaos | ~π | ~π | 1.5:1 | 0.0001 rad | Near-vertical start |
| Near Identical | π/2 | 3π/4 | 1:1 | tiny | Divergence demo |
| Butterfly Effect | 17π/20 | π/2 | 1:1 | 1e-6 rad | Ultra-sensitive |
| Long Arms | 7π/10 | 3π/5 | 1:1 | 0.001 rad | Asymmetric arm lengths |

**Interactive controls:** `Ctrl+P` (toggle mode), `Space` (play/pause), `n` (step), `d` (toggle dual comparison), `c` (clear trails), `g`/`G` (gravity ±1), `+`/`-` (timestep ×/÷1.5), `[`/`]` (trail length ±100), `>`/`<` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Navier-Stokes Fluid Dynamics — Jos Stam stable fluids with semi-Lagrangian advection and obstacle placement

Full 2D incompressible Navier-Stokes solver following the Stam "Stable Fluids" architecture. Pipeline per timestep: diffuse velocity (Gauss-Seidel, 20 iterations) → project → advect velocity (semi-Lagrangian back-trace with bilinear interpolation) → project again → diffuse dye → advect dye. Obstacle-aware neighbor counting. Projection solves pressure-Poisson for divergence-free fields. 4 visualization modes: dye, velocity, vorticity, pressure. Interactive cursor-driven dye/velocity injection and obstacle placement.

**Changed file:** `life.py` (+~550 lines)

**6 presets:**

| Preset | Description | Initial conditions |
|--------|-------------|-------------------|
| Dye Playground | Empty canvas | Freehand painting |
| Vortex Pair | Counter-rotating vortices | Biot-Savart velocity from two point vortices |
| Jet Stream | Continuous jet from left | Horizontal velocity band + dye |
| Karman Vortices | Vortex shedding past obstacle | Circular obstacle + uniform inflow |
| Four Corners | Opposing corner sources | Diagonal velocity in each quadrant |
| Shear Layer | Kelvin-Helmholtz instability | Top/bottom opposing flow + perturbation |

**Interactive controls:** `Ctrl+D` (toggle mode), arrow keys/`hjkl` (move cursor), `Enter`/`f` (inject dye+velocity), `o` (place/remove obstacle), `v` (cycle view), `b`/`V` (viscosity ×2/÷2), `+`/`-` (injection strength ±10), `c`/`C` (clear dye/velocity), `>`/`<` (speed), `R` (preset menu), `q`/`Esc` (exit)

### Added: Mandelbrot/Julia Set Fractal Explorer — Infinite zoom with real-time Julia morphing and 5 color schemes

Interactive fractal visualization rendering Mandelbrot and Julia sets using Unicode density characters (` .:-=+*#%@█`) with per-character coloring. Each cell maps to the complex plane and iterates `z = z² + c` up to configurable max iterations. Pan/zoom with adaptive step sizes. Mandelbrot fixes z₀=0 varying c per pixel; Julia fixes c varying z₀. Julia constant nudgeable in real-time for live morphing between families. 5 color schemes: Classic, Ocean, Fire, Neon, Monochrome.

**Changed file:** `life.py` (+~400 lines)

**10 presets:**

| Preset | Type | Center/Constant | Zoom | Max iter |
|--------|------|-----------------|------|----------|
| Classic Mandelbrot | Mandelbrot | −0.5+0i | 1× | 80 |
| Seahorse Valley | Mandelbrot | −0.745+0.113i | 50× | 200 |
| Elephant Valley | Mandelbrot | 0.282+0.01i | 20× | 200 |
| Mini-brot | Mandelbrot | −1.749+0i | 500× | 500 |
| Spiral | Mandelbrot | −0.7463+0.1102i | 200× | 300 |
| Julia Dendrite | Julia | c = i | 1× | 100 |
| Julia Douady Rabbit | Julia | c = −0.123+0.745i | 1× | 100 |
| Julia San Marco | Julia | c = −0.75 | 1× | 100 |
| Julia Siegel Disk | Julia | c = −0.391−0.587i | 1× | 120 |
| Julia Dragon | Julia | c = −0.8+0.156i | 1× | 100 |

**Interactive controls:** `Ctrl+B` (toggle mode), arrow keys/`hjkl` (pan), `z`/`x` or `+`/`-` (zoom 1.5×), `i`/`I` (iterations ±20), `t` (toggle Mandelbrot/Julia), `c` (cycle color scheme), `a`/`A` (Julia Re ±0.01), `s`/`S` (Julia Im ±0.01), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Fireworks — Rocket physics with 4 burst patterns, trailing sparks, and crossette splits

Rockets carry position, velocity, fuse count, colour, and burst pattern. Gravity and wind applied per tick; at apogee or fuse expiry, `_fireworks_explode` spawns 24–70 spark particles per pattern. Sparks undergo gravity (1.5× for willow), wind, drag (0.97 willow / 0.985 others), and jitter. 6-frame position trail rendered with fading characters. Crossette particles explode again for two-stage aerial splits. Auto-launch samples against `launch_rate` per tick.

**Changed file:** `life.py` (+~350 lines)

**4 burst patterns:** spherical (radial), ring (annular), willow (high-drag drooping), crossette (secondary explosions)

**6 presets:**

| Preset | Gravity | Launch rate | Wind | Pattern |
|--------|---------|------------|------|---------|
| Grand Finale | 0.05 | 0.18 | 0.000 | All random |
| Gentle Evening | 0.04 | 0.04 | 0.005 | Spherical/willow |
| Crossette Show | 0.05 | 0.07 | 0.000 | Crossette only |
| Willow Garden | 0.06 | 0.06 | 0.003 | Willow only |
| Ring Parade | 0.05 | 0.07 | 0.000 | Ring only |
| Random Mix | 0.05 | 0.08 | 0.000 | All 4 equal |

**Interactive controls:** `Ctrl+F` (toggle mode), `Space` (play/pause), `n` (step), `f`/`Enter` (manual launch), `a` (toggle auto-launch), `g`/`G` (gravity ±0.01), `w`/`W` (wind ±0.005), `l`/`L` (launch rate ±0.02), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: L-System Plant Growth — Lindenmayer grammar rewriting with turtle-graphics rendering

Plants defined as (axiom, rewriting rules, branching angle) and grown generation-by-generation via string substitution. Turtle-graphics interpretation: `F` draws a segment, `+`/`-` rotate by angle, `[` pushes state (scaling length by 0.5), `]` pops and records leaf. Segments Bresenham-rasterised using angle-dependent box-drawing characters (`║│┃╎╏┊┆`, `─╌`, `╲\`, `╱/`). Color encodes depth: brown trunk → yellow wood → green canopy. Light-direction bias offsets turtle heading ±0.15 rad for phototropic lean.

**Changed file:** `life.py` (+~350 lines)

**7 presets:**

| Preset | Axiom | Angle | Max depth | Character |
|--------|-------|-------|-----------|-----------|
| Binary Tree | F | 30° | 8 | Symmetric branching |
| Fern | X | 22° | 7 | Curving fronds |
| Bush | F | 25.7° | 6 | Dense shrub |
| Seaweed | F | 18° | 7 | Kelp-like swaying |
| Willow | F | 20° | 7 | Drooping branches |
| Pine | F | 35° | 8 | Compact coniferous |
| Garden | mixed | 25–28° | 6 | Multi-plant scene |

**Interactive controls:** `/` (toggle mode), `Space` (play/pause), `n` (step), `a`/`A` (angle ±2°), `←`/`→` (light direction ±10°), `g`/`G` (growth rate ±0.1), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Infrastructure: Ralph Task Logs (Rounds 154–186)

Added orchestration logs (`.ralph/round-*-thinker.json` and `.ralph/round-*-worker.json`) for rounds 154–155, 156–162, and 163–186 across multiple commits. These JSON files capture the complete AI thinker-proposal / worker-execution dialogue that produced all simulation modes added in this session — from the early CA modes through the final complex simulations. No simulation code modified; purely session-history archival.

### Added: Galaxy Formation — N-body particles with NFW dark matter halo, gas pressure, and leapfrog integration

N-body particle simulation with three types (stars, gas, dark matter). Leapfrog integration with: NFW dark-matter halo acceleration centered on grid midpoint, short-range particle gravity from 5×5 bin neighborhoods (softening ε=1.0), gas pressure force above density threshold 3.0, and gas cooling damping (0.998/tick). Display uses Unicode density characters (`· ∘ ○ ◎ ● ◉ █`) colored by type. Four view modes: combined, stars-only, gas-only, velocity field.

**Changed file:** `life.py` (+~500 lines)

**8 presets:**

| Preset | Particles | Structure |
|--------|-----------|-----------|
| Milky Way | ~350 | 2-arm log spiral |
| Grand Design | ~490 | Tight 2-arm, dense gas disk |
| Whirlpool | ~340 | 2-arm + dwarf companion |
| Elliptical | 300 | Isotropic dispersion, 1.3× elongated |
| Dwarf Irregular | 80 | Chaotic low-density |
| Galaxy Merger | 240 | Two counter-rotating spirals |
| Ring Galaxy | 240 | Expanding ring + central cluster |
| Barred Spiral | 260 | Bar tilted 0.4 rad + trailing arms |

**Interactive controls:** `"` (toggle mode), `Space` (play/pause), `n` (step), `v` (cycle view), `g`/`G` (G ±0.1), `d`/`D` (dt ±0.002), `h` (toggle halo overlay), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Enhanced: Forest Fire — Ember/Ash Lifecycle & Population Sparkline

Extended from 3 states to 5: **empty → tree → burning → ember → ash → empty**. Embers carry residual heat, spreading fire to adjacent trees before collapsing to ash; ash decays stochastically at `ash_decay` rate. Two-stage decay creates more realistic cascading fire fronts with visible scorched patches. Added Unicode sparkline (`▁▂▃▄▅▆▇█`, 40 samples) tracking tree density history, making self-organised criticality visible. Two new presets: Critical Density (SOC demo) and Slow Burn (long-lived embers). Ember cells render as dim red `░░`; ash as dim gray `░░`.

**Changed file:** `life.py` (+~80 lines)

**New state machine:** empty (0) → tree (1) → burning (2) → ember (4) → ash (3) → empty (0)

**New control:** `a`/`A` — ash decay rate ±0.01 (range 0.01–1.0)

**2 new presets:** Critical Density (density 0.60, p_grow 0.020, p_lightning 0.00030, ash_decay 0.10), Slow Burn (density 0.65, p_grow 0.030, p_lightning 0.00040, ash_decay 0.03)

### Added: Cloth Simulation — Verlet integration with spring constraints, tearing, and tension-based rendering

Position-based dynamics on Verlet integration: each point mass stores current and previous position; velocity is implicit as their difference × damping. Each tick adds gravity and randomised wind, then runs 5–8 iterative constraint relaxation passes. Springs stretched beyond `rest_length × tear_threshold` are permanently removed. Constraints rendered via Bresenham with angle-based characters (`──`, `│`, `╲`, `╱`); color encodes tension: white (≤1.2×), yellow (1.2–1.5×), red (≥1.5×). Pinned points as `◆` (red); free as `●` (cyan).

**Changed file:** `life.py` (+~400 lines)

**6 presets:**

| Preset | Gravity | Wind | Damping | Pin config | Tear threshold |
|--------|---------|------|---------|------------|---------------|
| Hanging Cloth | 0.50 | 0.00 | 0.990 | Full top row | 3.0 |
| Curtain | 0.40 | 0.05 | 0.980 | Two top corners | 3.0 |
| Flag | 0.15 | 0.30 | 0.970 | Entire left edge | 3.0 |
| Hammock | 0.60 | 0.00 | 0.990 | Four corners | 3.0 |
| Net | 0.40 | 0.00 | 0.990 | Top row, 2× spacing | 5.0 |
| Silk Sheet | 0.30 | 0.02 | 0.960 | Full top row | 2.5 |

**Interactive controls:** `'` (toggle mode), `Space` (play/pause), `n` (step), `p` (toggle pin), `x` (tear at cursor), `g`/`G` (gravity ±0.05), `w`/`W` (wind ±0.05), `d`/`D` (damping ±0.005), `t`/`T` (tear threshold ±0.5), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Smoke & Fire Fluid Simulation — Buoyancy-driven combustion with advection, turbulence, and temperature rendering

Grid-based combustion and fluid simulation: heat sources ignite fuel cells, driving a buoyancy-advection-diffusion loop. Each tick computes buoyancy (heat rises), wind drift, stochastic turbulence, and velocity damping, then combustion: cells above 0.2 threshold burn fuel at `0.05 * temp`, releasing `burn * 3.0` heat. Temperature/smoke advected via bilinear velocity sampling (60% blend), then 4-neighbor diffusion (20% weight). Altitude-based cooling increases toward grid top. Five rendering tiers: white-hot (`█`), yellow (`▓`), orange (`▒`), red (`░`), dim gray smoke.

**Changed file:** `life.py` (+~380 lines)

**6 presets:**

| Preset | Buoyancy | Turbulence | Character |
|--------|----------|-----------|-----------|
| Campfire | 0.15 | 0.04 | Centered fuel log cluster |
| Wildfire Spread | 0.12 | 0.06 | Scattered ground fuel, left-edge ignition |
| Explosion Burst | 0.25 | 0.12 | Radial velocity shockwave |
| Candle Row | 0.10 | 0.02 | Six evenly spaced candles |
| Inferno | 0.20 | 0.08 | Full-width fuel bed |
| Smoke Stack | 0.18 | 0.05 | Chimney outline with stack source |

**Interactive controls:** `\` (toggle mode), `Space` (play/pause), `n` (step), `f`/`Enter` (add/remove fire source), `F` (deposit fuel), `b`/`B` (buoyancy ±0.02), `t`/`T` (turbulence ±0.01), `w`/`W` (wind ±0.01), `c`/`C` (cooling ±0.002), `>`/`<` (steps/frame), `R` (preset menu), `q`/`Esc` (exit)

### Enhanced: Abelian Sandpile — Identity Element & Random Fill

Two new presets bringing total from 7 to 9. **Identity Element**: computes the algebraic identity of the sandpile group via `e = topple(6 − topple(6·ones))` — a BFS-based toppling algorithm processes the formula, producing a striking four-fold-symmetric fractal pattern. Auto-drop disabled since the identity is a complete static display. **Random Fill**: initializes every cell with uniform random [0–3] grains, then sets center to 4, triggering cascading avalanches through the near-maximum substrate. Both presets share a pure-Python queue-based BFS toppling loop (avoiding recursion depth limits).

**Changed file:** `life.py` (+~80 lines)

**New presets:**

| Preset | Initial config | Auto-drop | Character |
|--------|---------------|-----------|-----------|
| Identity Element | Group identity fractal via topple formula | Disabled | Four-fold symmetric fractal |
| Random Fill | Random [0–3] per cell; center perturbed to 4 | Enabled | Cascading avalanches |

### Added: Terrain Generation & Erosion Landscape — Four coupled geological processes with procedural terrain

Geological timescale landscape simulator: procedural heightmap evolved through tectonic uplift (center-weighted + jitter), thermal erosion (rockslides above talus threshold, attenuated by vegetation), hydraulic erosion (steepest-downhill flow with 60% redeposition), and vegetation dynamics (elevation-band dependent growth feeding back to reduce erosion). Terrain generated with multi-octave smooth noise and type-specific shaping. 4 visualization views: topographic, elevation, vegetation, erosion.

**Changed file:** `life.py` (+~500 lines)

**Core mechanics:**

| Process | Key behavior |
|---------|-------------|
| Tectonic uplift | Center-weighted ±20% jitter; configurable rate |
| Thermal erosion | Material transfer on slopes > 0.06; reduced 80% by vegetation |
| Hydraulic erosion | Steepest-downhill neighbor; capped at 10% local height; 60% redeposited |
| Vegetation | Band-dependent growth; slope penalty; reduces both erosion types |

**6 presets:**

| Preset | Terrain type | Character |
|--------|-------------|-----------|
| Continental Drift | gentle + edge masking | Continental shelf |
| Island Archipelago | noise + Gaussian peaks | Island chains |
| Alpine Peaks | power-law exaggeration | Glacial carving |
| Rolling Plains | compressed midrange | Shallow streams |
| Rift Valley | V-trench + escarpments | Central rift |
| Coastal Cliffs | land/sea gradient | Cliff erosion |

**Interactive controls:** `;` (toggle mode), `Space` (play/pause), `n` (step), `v` (cycle view), `u`/`U` (uplift ±0.001), `t`/`T` (thermal ±0.005), `w`/`W` (rain ±0.002), `g`/`G` (vegetation ±0.002), `s`/`S` (sea level ±0.02), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Enhanced: Falling Sand — Oil and Steam Materials

Two new particle materials bringing total to 7. **Oil** (key `6`): liquid with explicit density ordering — water displaces oil upward via per-step swap; sand sinks through oil; fire ignites oil at 50% probability (higher than plant's 40%). **Steam** (key `7`): gas produced from fire death (20%) or fire touching water (8%); rises with lateral drift; survives 15–25 ticks; condenses to water (40%) or vanishes. Three new presets: Forest Fire (plant combustion), Oil Refinery (density layering + combustion), Waterfall (multi-stage cascading flow).

**Changed file:** `life.py` (+~120 lines)

**New materials:**

| Material | Behavior | Key interactions |
|----------|----------|-----------------|
| Oil | Liquid; falls/flows like water | Floats above water (swap); sand sinks through; fire ignites at 50% |
| Steam | Gas; rises with lateral drift (−1/0/0/+1) | From fire death (20%) or fire+water (8%); condenses to water (40%); lifetime 15–25 ticks |

**3 new presets:** Forest Fire (plant combustion propagation), Oil Refinery (oil/water density layering + combustion), Waterfall (cascading flow over stone ledges)

**Interactive controls:** `1`–`7` (select material: sand/water/fire/stone/plant/oil/steam), `0` (eraser)

### Added: Quantum Cellular Automaton (Quantum Walk) — Discrete-time quantum walk with coin operators and interference

Each cell carries a 4-component complex amplitude vector (one per cardinal direction). Each step applies a Coin operator mixing direction amplitudes, then a Shift moving each component one cell in its direction. Three coins: Hadamard H⊗H (balanced symmetric spread), Grover diffusion (strong constructive interference), DFT (asymmetric via complex 4th roots of unity). Optional decoherence randomly phases amplitudes. 4 views: probability |ψ|², phase (color wheel), real, imaginary.

**Changed file:** `life.py` (+~380 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| State | 4 complex amplitudes per cell (up, right, down, left) |
| Coin operators | Hadamard H⊗H, Grover diffusion, DFT (4×4) |
| Shift | Each direction component moves one cell in its direction |
| Boundaries | Periodic (wrapping) or Absorbing (amplitude lost at edge) |
| Decoherence | Per-element phase randomisation at configurable rate |

**8 presets:**

| Preset | Coin | Source | Boundary | Character |
|--------|------|--------|----------|-----------|
| Hadamard Single | Hadamard | center | Periodic | Symmetric spreading |
| Hadamard Absorbing | Hadamard | center | Absorbing | Edge-damped |
| Grover Diffusion | Grover | center | Periodic | Strong interference |
| DFT Fourier | DFT | center | Periodic | Asymmetric |
| Gaussian Packet | Hadamard | gaussian | Periodic | Wave packet |
| Dual Source | Grover | two points | Periodic | Interference pattern |
| Decoherent | Hadamard | center | Periodic | Gradual classical |
| DFT Gaussian Absorb | DFT | gaussian | Absorbing | Combined |

**Interactive controls:** `^` (toggle mode), `Space` (play/pause), `n` (step), `v` (cycle view), `d`/`D` (decoherence ±0.005), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Strange Attractor Visualization — 6 chaotic 3D systems with accumulating density heatmap

200 particles evolve through six chaotic 3D ODE systems, projected onto a 2D density heatmap via configurable rotation angles. RK2 (midpoint) integration with 300-step warm-up. Density rendered with logarithmic scaling (`log1p`) through hot colormap (blue→magenta→red→yellow). Auto-scaled bounding box with user zoom. Slow max-density decay (0.999/step) prevents normalization locking.

**Changed file:** `life.py` (+~450 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Integration | RK2 (midpoint method) |
| Projection | Sequential z-axis then x-axis rotation onto 2D plane |
| Rendering | Log-scaled density heatmap; auto-fit to 85% terminal area |

**8 presets (6 systems):**

| Preset | System | Key parameters | Character |
|--------|--------|---------------|-----------|
| Lorenz Classic | lorenz | σ=10, ρ=28, β=8/3 | Two-lobe butterfly |
| Lorenz High Rho | lorenz | σ=10, ρ=99.96 | More chaotic, elongated lobes |
| Rössler Spiral | rossler | a=0.2, b=0.2, c=5.7 | Band-spiral with folds |
| Rössler Funnel | rossler | a=0.5, b=1.0, c=3.0 | Wide funnel morphology |
| Thomas | thomas | b=0.208186 | 3-fold cyclic symmetry |
| Aizawa | aizawa | a=0.95, d=3.5 | Toroidal knot |
| Halvorsen | halvorsen | a=1.89 | 3-fold rotational symmetry |
| Chen | chen | a=35, c=28 | Double scroll |

**Interactive controls:** `|` (toggle mode), `Space` (play/pause), `n` (step), arrow keys/`hjkl` (rotate projection ±0.1 rad), `z`/`Z` (zoom in/out), `1`/`2` (primary param ±), `3`/`4` (secondary param ±), `d`/`D` (timestep ×0.8/×1.25), `c` (clear density), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Magnetohydrodynamics (MHD) Plasma — 2D resistive incompressible MHD with reconnection dynamics

2D resistive MHD equations: density ρ, velocity (vx,vy), magnetic field (Bx,By). Momentum includes advection, isothermal pressure gradient, Lorentz force (Jz×B/ρ), and viscous diffusion. Induction: frozen-flux term `∇×(v×B)` + resistive diffusion η·∇²B. Explicit Euler at dt=0.02 with periodic boundaries. Fields soft-clamped to ±2.0 per step. 4 visualization modes: current density Jz, plasma density, magnetic field magnitude (direction-colored), flow speed.

**Changed file:** `life.py` (+~500 lines)

**Core mechanics:**

| Equation | Key terms |
|----------|-----------|
| Continuity | `−∇·(ρv) + 0.01·∇²ρ` |
| Momentum | `−(v·∇)v − ∇p/ρ + (Jz×B)/ρ + ν·∇²v` |
| Induction | `∇×(v×B) + η·∇²B` |

**8 presets:**

| Preset | η | ν | Init | Character |
|--------|---|---|------|-----------|
| Harris Current Sheet | 0.008 | 0.005 | harris | Tearing instability |
| Orszag-Tang Vortex | 0.005 | 0.005 | orszag_tang | MHD turbulence benchmark |
| Magnetic Island | 0.010 | 0.008 | island | Tearing/island formation |
| Blast Wave | 0.005 | 0.005 | blast | Radial outward kick |
| Kelvin-Helmholtz | 0.008 | 0.010 | kh | Shear flow instability |
| Double Current Sheet | 0.010 | 0.005 | double_harris | Coupled reconnection |
| Magnetic Flux Rope | 0.006 | 0.006 | flux_rope | Twisted azimuthal field |
| Random Turbulence | 0.008 | 0.008 | random | Decaying MHD turbulence |

**Interactive controls:** `}` (toggle mode), `Space` (play/pause), `n` (step), `e`/`E` (η ±0.002), `w`/`W` (ν ±0.002), `v` (cycle view), `p` (inject perturbation), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Chemotaxis & Bacterial Colony Growth — 3-field PDE system with nutrient-dependent morphogenesis

3-field PDE system: bacteria B (logistic growth scaled by nutrients + motility diffusion + chemotactic upwind flux), nutrients N (diffusion − bacterial consumption), and chemoattractant signal S (bacteria-produced + diffusion − decay). Upwind scheme for chemotaxis stabilises advection against numerical oscillations. Reproduces principal colony morphologies: compact Eden clusters, DLA-like tendrils, dense branching, chemotactic rings, and swarming fronts.

**Changed file:** `life.py` (+~420 lines)

**Core mechanics:**

| Field | PDE |
|-------|-----|
| Bacteria B | `∂B/∂t = r·B·N·(1−B) + μ·∇²B + χ·Φ_chemo` |
| Nutrient N | `∂N/∂t = D_N·∇²N − k·B·N` |
| Signal S | `∂S/∂t = σ·B − δ·S + 0.1·∇²S` |

**8 presets:**

| Preset | r | μ | χ | k | Init | Character |
|--------|---|---|---|---|------|-----------|
| Eden Cluster | 0.8 | 0.010 | 0.0 | 0.30 | center | Dense compact disc |
| DLA Tendrils | 0.5 | 0.005 | 0.3 | 0.60 | center | Fractal branches |
| Dense Branching | 0.6 | 0.020 | 0.15 | 0.40 | center | Bushy morphology |
| Concentric Rings | 0.4 | 0.030 | 0.50 | 0.50 | center | Chemotactic ring waves |
| Swarming Colony | 0.7 | 0.080 | 0.40 | 0.30 | center | Rapid spreading front |
| Multi-Colony | 0.6 | 0.020 | 0.20 | 0.40 | multi | Competing colonies |
| Nutrient Gradient | 0.5 | 0.015 | 0.25 | 0.40 | gradient | Directional growth |
| Quorum Sensing | 0.5 | 0.010 | 0.60 | 0.35 | center | Density-dependent behavior |

**Interactive controls:** `{` (toggle mode), `Space` (play/pause), `n` (step), `g`/`G` (growth rate ±0.05), `c`/`C` (chemotaxis ±0.05), `d`/`D` (motility ±0.005), `v` (cycle view: bacteria/nutrient/signal), `p` (inoculate patch), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Belousov-Zhabotinsky (BZ) Reaction — 3-variable Oregonator chemical oscillator with spiral waves

3-variable Oregonator-inspired model: activator grows autocatalytically suppressed by recovery (`da = a(α−a−β·c) + D·∇²a`), inhibitor tracks activator (`db = a−b`), recovery driven by activator and decays (`dc = γ(a−c)`). Euler integration at dt=0.05 with 5-point Laplacian diffusion, toroidal boundaries. Phase-based rendering maps activator/recovery state to color wheel. 5 initialization types: spiral_seed, center_seed, random_seeds, random_noise, multi_spiral.

**Changed file:** `life.py` (+~400 lines)

**Core mechanics:**

| Parameter | Range | Effect |
|-----------|-------|--------|
| α (activator rate) | 0.1–3.0 | Autocatalytic growth strength |
| γ (recovery rate) | 0.1–3.0 | Return to excitability speed |
| D (diffusion) | 0.01–1.0 | Spatial spreading; higher = smoother waves |

**8 presets:**

| Preset | α | γ | D | Init | Character |
|--------|---|---|---|------|-----------|
| Classic Spirals | 1.0 | 1.0 | 0.20 | spiral_seed | Self-organizing spiral |
| Dense Spirals | 1.2 | 0.8 | 0.15 | random_seeds | Competing spirals |
| Slow Waves | 0.7 | 0.6 | 0.30 | center_seed | Large concentric rings |
| Turbulent | 1.4 | 1.0 | 0.10 | random_noise | Chaotic spiral breakup |
| Target Waves | 0.9 | 0.9 | 0.25 | center_seed | Bull's-eye rings |
| Multi-Spiral | 1.0 | 1.0 | 0.20 | multi_spiral | Four competing spirals |
| Gentle Ripples | 0.6 | 0.5 | 0.35 | random_noise | Soft undulations |
| Fast Chaos | 1.3 | 1.2 | 0.12 | random_seeds | Rapid fragmented arcs |

**Interactive controls:** `` ` `` (toggle mode), `Space` (play/pause), `n` (step), `a`/`A` (α ±0.1), `g`/`G` (γ ±0.1), `d`/`D` (diffusion ±0.02), `p` (add excitation patch), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Spiking Neural Network (Izhikevich) — 2D grid of coupled neurons with spike dynamics and glow trails

Every cell is an Izhikevich neuron: `v' = 0.04v² + 5v + 140 − u + I`, `u' = a(bv−u)`, spike at v=30mV with reset to `c`, `u += d`. Synaptic current I from 8 Moore neighbors (excitatory +weight, inhibitory −weight) plus Gaussian noise. Fire history with exponential decay provides afterglow trails. Per-neuron (a,b,c,d) tuples enable diverse firing: regular spiking, fast spiking, chattering, cortical-realistic distributions.

**Changed file:** `life.py` (+~420 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Neuron model | Izhikevich 2-variable: v (membrane), u (recovery) |
| Synaptic coupling | 8-neighbor Moore; excitatory +weight, inhibitory −weight |
| Integration | Euler sub-steps; total 1ms simulated per call |
| Visualization | 4-layer: firing (yellow/cyan), glow trails (red/magenta at 3 levels), subthreshold (faint cyan) |

**10 presets:**

| Preset | Exc% | Weight | Noise | Character |
|--------|------|--------|-------|-----------|
| Sparse Random Firing | 80% | 8.0 | 3.0 | Occasional spontaneous spikes |
| Synchronized Bursting | 80% | 18.0 | 5.0 | Rhythmic population bursts |
| Traveling Waves | 90% | 12.0 | 1.0 | Wave front propagation |
| Spiral Activity | 85% | 14.0 | 1.5 | Rotating spiral |
| Excitation Cascade | 95% | 15.0 | 4.0 | Dense avalanche dynamics |
| Inhibition-Dominated | 50% | 12.0 | 6.0 | Sparse patterns |
| Chattering Network | 80% | 10.0 | 4.0 | Fast rhythmic bursting |
| Cortical Column | 80% | 10.0 | 5.0 | Realistic RS/FS distribution |
| Noise-Driven | 80% | 6.0 | 12.0 | Stochastic thalamic input |
| Two-Cluster Sync | 80% | 14.0 | 3.0 | Dual band stimulation |

**Interactive controls:** `Space` (play/pause), `n` (step), `w`/`W` (weight ±1.0), `v`/`V` (noise ±0.5), `p` (stimulate 7×7 patch), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Kuramoto Coupled Oscillators — Phase synchronization with continuous order-disorder transition

Each grid cell is an autonomous oscillator with Gaussian-distributed natural frequency ωᵢ. Phase evolves via `θᵢ(t+dt) = θᵢ + dt·[ωᵢ + (K/4)·Σsin(θⱼ−θᵢ) + η]` with 4 von Neumann neighbors and periodic boundaries. Coupling K drives a continuous phase transition: below critical value oscillators remain incoherent, above it global synchronization sweeps the grid. Order parameter r = |1/N·Σexp(iθ)| measures transition in real time. Phase rendered through 6-color rainbow wheel with block-character density gradation.

**Changed file:** `life.py` (+~380 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Coupling | K/4 × Σsin(θⱼ−θᵢ) over von Neumann neighbors |
| Order parameter | r = |1/N·Σexp(iθ)|; 0 = incoherent, 1 = synchronized |
| Init modes | random, gradient (linear phase ramp), spiral (atan2 vortex), chimera (mixed sync/async) |

**12 presets:**

| Preset | K | σ | Noise | Init | Character |
|--------|---|---|-------|------|-----------|
| Gentle Sync | 0.5 | 1.0 | 0.0 | random | Slow coherent islands |
| Strong Sync | 3.0 | 1.0 | 0.0 | random | Rapid global lock-in |
| Critical Point | 1.5 | 1.0 | 0.0 | random | Order from chaos |
| Noisy Oscillators | 2.0 | 1.0 | 0.3 | random | Flickering domains |
| Narrow Band | 1.0 | 0.3 | 0.0 | random | Easy sync |
| Wide Band | 2.0 | 3.0 | 0.0 | random | Frustrated, hard to sync |
| Phase Gradient | 1.0 | 1.0 | 0.0 | gradient | Travelling wave |
| Spiral Seed | 1.5 | 0.5 | 0.0 | spiral | Topological vortex |
| Chimera State | 1.2 | 1.0 | 0.0 | chimera | Mixed sync/async |
| Frozen Random | 0.0 | 1.0 | 0.0 | random | K=0, independent |
| Fast Dynamics | 1.5 | 1.0 | 0.0 | random | Large dt |
| Noise Dominant | 0.5 | 1.0 | 1.0 | random | Noise overwhelms coupling |

**Interactive controls:** `Space` (play/pause), `n` (step), `c`/`C` (K ±0.1), `d`/`D` (dt ±0.01), `v`/`V` (noise ±0.05), `p` (perturb random patch), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: 2D Wave Equation — Finite-difference membrane simulator with reflection, absorption, and diffraction

Full membrane wave simulator: `u_next = 2·u − u_prev + c²·(Laplacian)` with per-step multiplicative damping. Three boundary conditions: reflect (Neumann zero-derivative), absorb (Dirichlet zero), wrap (periodic). Double-slit preset places a hard barrier wall with two openings and drives a sinusoidal plane wave to produce sustained diffraction. Wave speed kept ≤0.5 for numerical stability. Signed displacement mapped to 5-tier block palette with positive crests in cyan/yellow and negative troughs in magenta/blue.

**Changed file:** `life.py` (+~400 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Wave equation | Standard 5-point finite difference with Courant number c |
| Damping | Multiplicative per-step factor (0.95–1.0); 1.0 = lossless |
| Boundaries | Reflect (Neumann), Absorb (Dirichlet), Wrap (periodic) |
| Double slit | Barrier wall at cols/4 with two openings; continuous sine wave drive at left edge |

**12 presets:**

| Preset | c | Damping | Boundary | Initial condition |
|--------|---|---------|----------|-------------------|
| Center Drop | 0.45 | 0.999 | reflect | Gaussian drop at center |
| Reflecting Pool | 0.40 | 0.9995 | reflect | Standing waves |
| Absorbing Edges | 0.45 | 0.999 | absorb | No reflections |
| Wraparound Torus | 0.40 | 0.999 | wrap | Wraps across edges |
| Double Slit | 0.35 | 0.9995 | absorb | Driven diffraction |
| Corner Pulse | 0.45 | 0.999 | reflect | Pulse from corner |
| Rain Drops | 0.40 | 0.999 | reflect | Random multi-drop |
| Ring Wave | 0.40 | 0.999 | reflect | Annular displacement |
| Cross Pattern | 0.40 | 0.999 | reflect | Cross-shaped ridge |
| Undamped Pool | 0.40 | 1.000 | reflect | Energy conserved forever |
| Slow Ripple | 0.20 | 0.999 | reflect | Clear propagation |
| Fast Chaos | 0.48 | 0.998 | wrap | Max speed + random drops |

**Interactive controls:** `Space` (play/pause), `n` (step), `c`/`C` (wave speed ±0.05), `d`/`D` (damping ±0.001), `b` (cycle boundary), `p` (pluck — random Gaussian impulse), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Enhanced: Snowflake Crystal Growth — Six-Fold Symmetry & Diffusion Control

Two major upgrades: (1) True six-fold symmetry enforcement — when a cell freezes, its hex coordinates are transformed through all 12 symmetric images (6 rotations × 2 reflections) and all are frozen simultaneously, producing crystallographically correct snowflakes. (2) A diffusion rate parameter μ controlling vapor field smoothing — low μ creates steep gradients and narrow dendritic arms, high μ grows broad hexagonal plates. Visualization upgraded to 3-tier crystal renderer based on frozen neighbor count. A symmetry toggle (`s`) allows comparing constrained vs free growth mid-run. Presets expanded from 8 to 12.

**Changed file:** `life.py` (+~150 lines)

**New parameter:**

| Parameter | Symbol | Range | Effect |
|-----------|--------|-------|--------|
| Diffusion rate | μ | 0.05–1.0 | Low = dendritic arms, high = plate morphology |

**12 presets:**

| Preset | α | β | μ | Sym | Character |
|--------|---|---|---|-----|-----------|
| Classic Dendrite | 0.40 | 0.40 | 0.80 | ❄ | Balanced six-armed branching |
| Thin Needles | 0.30 | 0.30 | 0.90 | ❄ | Long thin branches |
| Broad Plates | 0.50 | 0.55 | 0.50 | ❄ | Wide faceted plates |
| Fernlike | 0.65 | 0.35 | 0.70 | ❄ | Highly branched ferns |
| Stellar Dendrite | 0.45 | 0.45 | 0.85 | ❄ | Classic star snowflake |
| Sectored Plate | 0.20 | 0.60 | 0.60 | ❄ | Sector-plate morphology |
| Simple Hexagon | 0.15 | 0.70 | 0.40 | ❄ | Compact hexagonal prism |
| Hollow Columns | 0.35 | 0.50 | 0.75 | ❄ | Hollow column morphology |
| Noisy Crystal | 0.40 | 0.40 | 0.80 | ~ | High γ, irregular natural |
| Asymmetric Growth | 0.40 | 0.40 | 0.80 | ~ | No symmetry, naturalistic |
| Fast Dendrite | 0.55 | 0.35 | 0.50 | ❄ | Rapid dense fractal arms |
| Sparse Frost | 0.25 | 0.25 | 0.90 | ❄ | Slow sparse crystal |

**Interactive controls:** `Space` (play/pause), `n` (step), `a`/`A` (α ±0.05), `d`/`D` (μ ±0.05), `s` (toggle 6-fold symmetry), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q` (exit)

### Added: Spatial Rock-Paper-Scissors — Cyclic dominance ecology with self-organizing spiral waves

Cyclic dominance ecology producing self-organizing spiral waves. Each step performs `floor(rows × cols × swap_rate)` interaction attempts: a random cell is chosen, then a random von Neumann neighbor. The attacker replaces the defender iff `defender == (attacker − 1) % N`. This asymmetric rule sustains persistent spiral waves rather than extinction. 3 or 5 species with three layout modes: random, blocks (vertical stripes), and seeds (circular minority clusters).

**Changed file:** `life.py` (+~280 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Dominance | Cyclic: species i beats (i−1) % N |
| Interactions | `swap_rate × grid_size` random attempts per step |
| Neighborhood | Von Neumann (4-connected), toroidal |

**6 presets:**

| Preset | Species | Swap rate | Layout | Character |
|--------|---------|-----------|--------|-----------|
| Classic Spiral Waves | 3 | 0.50 | random | Self-organizing spirals |
| Slow Spirals | 3 | 0.20 | random | Larger, slower spirals |
| Fast Chaos | 3 | 0.90 | random | Turbulent rapid dynamics |
| Territorial Blocks | 3 | 0.50 | blocks | Watch invasion fronts |
| Five Species | 5 | 0.50 | random | RPS-Lizard-Spock |
| Seeded Spirals | 3 | 0.40 | seeds | Circular clusters nucleate spirals |

**Interactive controls:** `Space` (play/pause), `n` (step), `s`/`S` (swap rate ±0.05), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Voronoi Crystal Growth — Competitive frontier growth with per-grain crystallographic anisotropy

Polycrystalline solidification where nucleation seeds expand via frontier-based growth. Each grain has a random preferred growth angle; growth probability = `max(0.1, 1.0 − aniso × (angular_deviation / π))`. Frontier cells processed in random order each step. 15 distinct 256-color grain colors (red through sea green); grain boundaries detected via 8-connected scan and rendered as grey `▒▒`. Seed layouts: random, edge (columnar), center (radial), bicrystal.

**Changed file:** `life.py` (+~350 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Anisotropy | Off-axis growth suppressed by `aniso × (deviation / π)`; range 0.0–0.9 |
| Frontier | Shuffled each step; successful claims add unclaimed 8-neighbors to frontier |
| Grain boundaries | Detected when 8-connected neighbor belongs to different grain |

**8 presets:**

| Preset | Seeds | Anisotropy | Layout | Character |
|--------|-------|-----------|--------|-----------|
| Fine Microstructure | 60 | 0.20 | random | Dense polycrystalline texture |
| Coarse Grains | 12 | 0.45 | random | Few large crystals with facets |
| Columnar Growth | 25 | 0.50 | edge | Columnar columns from left edge |
| Dendritic Arms | 20 | 0.70 | random | Branching faceted domains |
| Isotropic Foam | 35 | 0.00 | random | Soap-bubble-like cells |
| Sparse Nucleation | 6 | 0.35 | random | Large irregular territories |
| Bicrystal | 2 | 0.40 | bicrystal | Single grain boundary study |
| Radial Burst | 20 | 0.30 | center | Radial competitive growth |

**Interactive controls:** `Space` (play/pause), `n` (step), `a`/`A` (anisotropy ±0.05), `+`/`-` (steps/frame ±2), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Hydraulic Erosion — Shallow-water erosion with procedural terrain, rainfall, and sediment transport

Procedural heightmap terrain carved by five-stage physics: (1) uniform rainfall with ±20% spatial jitter; (2) effective height computation and downhill neighbor identification; (3) water flow to lower neighbors with erosion proportional to `solubility × slope × flow`; (4) sediment deposition when water pools or load exceeds threshold; (5) evaporation with remaining sediment deposited. Terrain generated with multi-octave smooth noise; 8 terrain types with additional shaping (ridges, cliffs, mesas, volcanoes). Height mapped to 8 color levels (deep blue → white peaks) with blue water overlay.

**Changed file:** `life.py` (+~450 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Erosion | `solubility × slope × flow`, capped at 10% local height per step |
| Deposition | When no downhill outlet or suspended load exceeds threshold |
| Boundaries | Edge cells drain at 50% per step to prevent flooding |

**8 presets:**

| Preset | Terrain type | Character |
|--------|-------------|-----------|
| River Valley | gentle | Wide meandering rivers |
| Mountain Gorge | steep | Deep narrow canyons |
| Coastal Plateau | plateau | Flat top with cliff edges |
| Badlands | rough | Dense dendritic networks |
| Alpine Peaks | alpine | Glacial-style carving |
| Rolling Hills | hills | Shallow streams |
| Canyon Lands | mesa | Slot canyon formation |
| Volcanic Island | volcano | Radial drainage |

**Interactive controls:** `Space` (play/pause), `n` (step), `w`/`W` (rain rate ±0.002), `e`/`E` (solubility ±0.002), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Lightning / Dielectric Breakdown — DBM with Gauss-Seidel potential field and configurable branching

Electrical discharge patterns modelled with the Dielectric Breakdown Model (DBM). An iterative Gauss-Seidel solver approximates Laplace's equation, establishing a potential field between the channel (fixed at 0) and the boundary (fixed at 1). Growth candidates (4-connected neighbors of channel) are weighted by `potential^eta` and selected via weighted random sampling. Channel age drives color: fresh = white/yellow `██`, fading through cyan `▓▓`, blue `▒▒`, dim blue `░░`.

**Changed file:** `life.py` (+~380 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Potential solver | Gauss-Seidel relaxation, `min(80, max(rows,cols))` iterations per step |
| Growth weighting | `potential^eta` — higher eta = straighter paths, lower = more branching |
| Source positions | `top`, `center`, `point` — determines seed location and ground boundary |

**8 presets:**

| Preset | eta | Source | Character |
|--------|-----|--------|-----------|
| Classic Lightning | 2.0 | top | Natural branching bolt |
| Sparse Bolt | 4.0 | top | Few branches, straighter |
| Dense Branching | 1.0 | top | Heavily branched |
| Lichtenberg Figure | 1.5 | center | Radial fractal |
| Point Discharge | 2.0 | point | Star-like from single point |
| Feathery Discharge | 0.5 | center | Maximum branching |
| Minimal Tree | 3.0 | top | Moderate branching |
| Ball Lightning | 3.5 | center | Sparse radial discharge |

**Interactive controls:** `Space` (play/pause), `n` (step), `e`/`E` (eta ±0.25), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Spatial Prisoner's Dilemma (Evolutionary Game Theory) — Imitation dynamics on a 2D grid with cooperator clusters

Spatial Prisoner's Dilemma on a periodic 2D grid. Scoring phase: every cell plays the PD payoff matrix against all 8 Moore neighbors (C-C→R, C-D→S, D-C→T, D-D→P). Update phase: each cell adopts the strategy of the highest-scoring neighbor — pure imitation dynamics producing characteristic cooperator-cluster patterns (Nowak & May, 1992). Cells rendered as color blocks scaled by score intensity.

**Changed file:** `life.py` (+~310 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Payoff matrix | R (mutual cooperation), T (temptation), P (mutual defection), S (sucker's payoff) |
| Update rule | Pure imitation — adopt strategy of highest-scoring Moore neighbor |
| Stats | Live cooperator/defector counts with cooperation percentage |

**8 presets:**

| Preset | T | R | P | S | Init C% | Character |
|--------|---|---|---|---|---------|-----------|
| Classic | 1.5 | 1.0 | 0.0 | 0.0 | 50% | Standard PD; cooperator clusters |
| Weak Dilemma | 1.2 | 1.0 | 0.0 | 0.0 | 50% | Low temptation; cooperation spreads |
| Strong Dilemma | 2.0 | 1.0 | 0.0 | 0.0 | 50% | High temptation; defection dominates |
| Snowdrift | 1.5 | 1.0 | 0.1 | 0.5 | 50% | Coexistence regime |
| Stag Hunt | 1.2 | 1.5 | 0.0 | 0.0 | 40% | High reward for cooperation |
| Critical Threshold | 1.65 | 1.0 | 0.0 | 0.0 | 50% | Phase transition; fragile clusters |
| Mostly Defectors | 1.4 | 1.0 | 0.0 | 0.0 | 15% | Few cooperators try to survive |
| Mostly Cooperators | 1.4 | 1.0 | 0.0 | 0.0 | 85% | Defectors try to invade |

**Interactive controls:** `@` (toggle mode), `Space` (play/pause), `n` (step), `t`/`T` (temptation ±0.05), `+`/`-` (speed), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Snowflake Growth (Reiter Crystal) — Hexagonal lattice crystal growth with deposition and diffusion

Reiter's 1995 crystal growth model on a hexagonal lattice using even-r offset coordinates with six-neighbour connectivity. Each step: (1) identify receptive cells (any frozen hex neighbor); (2) deposit α (+ noise ±γ) to receptive cells; (3) diffuse vapor among non-frozen cells via hex-neighbor averaging; (4) freeze cells with vapor ≥ 1.0. Seeds from a single frozen nucleus at grid center. Frozen ice rendered bright cyan; vapor density shown via block characters.

**Changed file:** `life.py` (+~320 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Lattice | Hexagonal (even-r offset, 6 neighbors) |
| Deposition | α per step to receptive cells, with optional noise ±γ |
| Diffusion | Hex-neighbor averaging for non-frozen cells |
| Freezing | Receptive cells with vapor ≥ 1.0 become permanently frozen |

**8 presets:**

| Preset | α | β (initial vapor) | Character |
|--------|---|-------------------|-----------|
| Classic Dendrite | 0.40 | 0.40 | Balanced six-fold branching |
| Thin Needles | 0.30 | 0.30 | Long thin branches |
| Broad Plates | 0.50 | 0.55 | Wide faceted plates |
| Fernlike | 0.65 | 0.35 | Highly branched fern shapes |
| Stellar Dendrite | 0.45 | 0.45 | Classic six-pointed star |
| Sectored Plate | 0.20 | 0.60 | High vapor, low deposition |
| Sparse Growth | 0.25 | 0.25 | Very slow sparse crystal |
| Noisy Crystal | 0.40 | 0.40 | High noise, irregular natural look |

**Interactive controls:** `*` (toggle mode), `Space` (play/pause), `n` (step), `a`/`A` (deposition rate ±0.05), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Traffic Flow (Nagel-Schreckenberg) — Minimal stochastic highway traffic model with phantom jams

Nagel-Schreckenberg cellular automaton: the minimal stochastic model of single-lane highway traffic. Four simultaneous rules per step: (1) Acceleration — speed +1 up to vmax; (2) Braking — reduce to gap if gap < speed; (3) Randomisation — with probability p_slow, speed −1 (driver hesitation); (4) Movement — advance by final speed. Multiple lanes run independently (no lane-changing). Car glyphs encode speed: `█` (stopped, red) → `▓` → `▒` → `░` → `◈` → `►` (fast, green).

**Changed file:** `life.py` (+~300 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Rules | Acceleration, braking, random slowdown, movement — all simultaneous |
| Road | Circular (periodic boundaries per lane) |
| Stats | Average speed and flow (total speed / total cells) live-tracked |

**8 presets:**

| Preset | vmax | p_slow | density | Lanes | Character |
|--------|------|--------|---------|-------|-----------|
| Light Traffic | 5 | 0.3 | 0.10 | 4 | Free flow at vmax |
| Moderate Traffic | 5 | 0.3 | 0.25 | 4 | Occasional slowdowns |
| Heavy Traffic | 5 | 0.3 | 0.40 | 4 | Phantom jams emerge |
| Congested | 5 | 0.3 | 0.55 | 4 | Stop-and-go waves |
| Slow Road | 2 | 0.3 | 0.35 | 4 | Low speed limit |
| Cautious Drivers | 5 | 0.5 | 0.25 | 4 | High braking probability |
| Aggressive Drivers | 5 | 0.1 | 0.30 | 4 | Low braking, smooth until not |
| Highway (8 lanes) | 5 | 0.3 | 0.25 | 8 | Wide highway |

**Interactive controls:** `T` (toggle mode), `Space` (play/pause), `n` (step), `d`/`D` (density ±0.05), `p`/`P` (brake probability ±0.05), `+`/`-` (speed), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Ising Model (Magnetic Spin) — Metropolis dynamics with phase transition at T≈2.27

The 2D Ising model: canonical statistical-mechanics lattice of interacting binary spins (+1/−1). Metropolis single-spin-flip: each generation performs N random flip attempts, accepting unconditionally when ΔE ≤ 0, else with Boltzmann probability exp(−ΔE/kT). Pre-computed Boltzmann factors avoid repeated `exp()` calls. Periodic boundaries; external field adds −h·s per site. After each sweep, magnetisation ⟨m⟩ and energy E/N recomputed.

**Changed file:** `life.py` (+~350 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Dynamics | Metropolis single-spin-flip; N random attempts per sweep |
| Acceptance | ΔE ≤ 0: always; else exp(−ΔE/kT) with pre-computed lookup |
| Boundary | Periodic (toroidal); 4 nearest neighbors |
| Observables | Magnetisation ⟨m⟩, energy per spin E/N (right+down pairs to avoid double-counting) |

**8 presets:**

| Preset | T | h | Init | Description |
|--------|---|---|------|-------------|
| Critical Point | 2.269 | 0.0 | random | Phase transition with fractal domains |
| Low Temperature | 1.0 | 0.0 | random | Ordered phase; large aligned domains |
| Very Cold | 0.5 | 0.0 | random | Near ground state |
| High Temperature | 4.0 | 0.0 | random | Disordered, random-looking |
| Quench to Cold | 0.1 | 0.0 | random | Rapid coarsening into domains |
| External Field | 2.0 | 0.5 | random | Field biases alignment near Tc |
| Domain Wall | 1.5 | 0.0 | half | Left up / right down; watch boundary evolve |
| All Up + Heat | 3.0 | 0.0 | all_up | Ordered start melts into disorder |

**Interactive controls:** `#` (toggle mode), `Space` (play/pause), `n` (step), `t`/`T` (temperature ±0.1), `f`/`F` (field ±0.1), `+`/`-` (sweeps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Hodgepodge Machine (BZ Reaction) — Gerhardt-Schuster discrete model with spiral waves and target patterns

Gerhardt-Schuster (1989) discrete model of the Belousov-Zhabotinsky oscillating chemical reaction. Each cell carries integer state in `[0, n−1]`: 0 = healthy, n−1 = ill, between = infected. Three simultaneous update rules: (1) ill cells reset to healthy; (2) healthy cells get `floor(a/k1) + floor(b/k2)` where a = infected neighbors, b = ill neighbors; (3) infected cells advance by `floor(avg_nonzero_states + g)`. Parameters `k1`, `k2` control susceptibility; `g` controls progression speed.

**Changed file:** `life.py` (+324 lines)

**Core mechanics:**

| Parameter | Role | Effect when increased |
|-----------|------|---------------------|
| `n_states` | Total states (10–255) | Longer infection cycle, slower spirals |
| `k1` | Infection weight from infected neighbors | Smaller = more susceptible healthy cells |
| `k2` | Infection weight from ill neighbors | Smaller = more susceptible healthy cells |
| `g` | Illness progression speed | Faster advance, tighter spiral arms |

**8 presets:**

| Preset | n_states | k1 | k2 | g | Character |
|--------|----------|----|----|---|-----------|
| Classic Spirals | 100 | 2 | 3 | 28 | Smooth iconic BZ spirals |
| Tight Spirals | 200 | 1 | 2 | 45 | Dense, tightly-wound waves |
| Target Waves | 100 | 3 | 3 | 18 | Concentric expanding rings |
| Chaotic Mix | 50 | 2 | 3 | 10 | Turbulent interacting wavefronts |
| Slow Waves | 150 | 1 | 1 | 55 | Large, slow-moving spirals |
| Fast Reaction | 60 | 3 | 4 | 8 | Rapid small-scale activity |
| Crystal Growth | 80 | 1 | 4 | 35 | Angular, geometric wave patterns |
| Thin Filaments | 255 | 2 | 3 | 80 | Delicate thin spiral arms |

**Interactive controls:** `~` (toggle mode), `Space` (play/pause), `n` (step), `g`/`G` (progression speed ±1), `s`/`S` (state count ±10), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Turmites (2D Turing Machine) — Generalized Langton's Ant with internal state and transition tables

Turmites generalize Langton's Ant: a single ant carries an internal state and reads the cell color. A transition table `table[state][color]` returns `(write_color, turn, new_state)` — the ant writes a new color, rotates (0=straight, 1=right, 2=U-turn, 3=left), advances state, then moves forward. Grid stored sparsely as `dict[(r,c) -> color]`; blank cells default to 0. Steps per frame selectable from {1, 5, 10, 50, 100, 500}.

**Changed file:** `life.py` (+403 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Transition table | `table[state][color] = (write_color, turn_code, new_state)` |
| Turn codes | 0=straight, 1=right (CW 90°), 2=U-turn (180°), 3=left (CCW 90°) |
| Grid storage | Sparse dict; cells cycling to 0 removed from memory |
| Rendering | Colored blocks by state; ant shown as directional arrow glyph |

**10 presets:**

| Preset | States | Colors | Behavior |
|--------|--------|--------|----------|
| Langton's Ant | 1 | 2 | Classic RL — highway after ~10,000 steps |
| Fibonacci Spiral | 2 | 2 | Fibonacci-like spiral arm growth |
| Square Builder | 2 | 2 | Expanding filled square |
| Snowflake | 3 | 2 | Symmetric crystal-like growth |
| Chaos | 2 | 2 | Complex chaotic, non-repeating |
| Highway Builder | 2 | 2 | Rapid highway construction |
| Spiral Growth | 3 | 2 | Expanding spiral with internal structure |
| Diamond | 2 | 2 | Diamond-shaped filled region |
| Worm Trail | 3 | 2 | Worm-like trailing path |
| 3-Color Spiral | 2 | 3 | Three-color spiral behavior |

**Interactive controls:** `Q` (toggle mode), `Space` (play/pause), `n` (step), `+`/`-` (cycle steps/frame through {1,5,10,50,100,500}), `r` (reset), `R`/`m` (preset menu), `<`/`>` (speed), `q`/`Esc` (exit)

### Added: Schelling Segregation Model — How mild preferences produce strong macro-level segregation

Thomas Schelling's 1971 model of residential segregation on a toroidal grid with Moore neighborhoods. Each occupied cell belongs to one of 2–4 groups. Every step identifies all unhappy agents (fraction of same-group neighbors below tolerance threshold) and relocates them to random vacancies. Even tolerances as low as 30% reliably produce near-total macro-level segregation from random initial distributions. A satisfaction bar shows real-time happy/unhappy split.

**Changed file:** `life.py` (+378 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Satisfaction test | `similar_neighbors / occupied_neighbors >= tolerance`; isolated agents always happy |
| Move rule | All unhappy agents simultaneously relocate to random empty cells per step |
| Grid encoding | 0 = empty; 1..`n_groups` = group identity |

**8 presets:**

| Preset | Tolerance | Density | Groups | Character |
|--------|-----------|---------|--------|-----------|
| Mild Preference | 30% | 90% | 2 | Fast segregation at low threshold |
| Classic Schelling | 37.5% | 90% | 2 | Original 1/3 threshold |
| Moderate Bias | 50% | 85% | 2 | Slower, stronger clustering |
| Strong Preference | 62.5% | 90% | 2 | Near-total segregation |
| Three Groups | 37.5% | 85% | 3 | Three competing populations |
| Four Cultures | 35% | 80% | 4 | Complex four-way boundaries |
| Sparse City | 40% | 50% | 2 | Abundant vacancies, faster diffusion |
| Packed Metropolis | 37.5% | 97% | 2 | Few vacancies, slow churn |

**Interactive controls:** `K` (toggle mode), `Space` (play/pause), `n` (step), `t`/`T` (tolerance ±2.5%), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Predator-Prey (Lotka-Volterra) Ecosystem — Grid-based agent simulation with emergent population oscillations

Three cell types coexist on a toroidal grid: grass (regrows on empty cells after a configurable timer), prey (seek adjacent grass, gain energy from eating, reproduce by splitting energy, die at 0 energy), and predators (hunt adjacent prey, gain energy from kills, starve without food). All prey are shuffled and moved in random order before predators act. Population oscillatory signature emerges from agent interactions alone — no equation is explicitly solved.

**Changed file:** `life.py` (+510 lines)

**Core mechanics:**

| Entity | Behavior |
|--------|----------|
| Empty (regrowing) | Counts down timer; converts to grass at 0 |
| Grass | Passive; eaten by prey, starts regrowth timer |
| Prey | Moves toward grass, eats for +`prey_gain` energy, −1/step, reproduces at threshold, dies at 0 |
| Predator | Hunts prey preferentially, +`pred_gain` energy, −1/step, reproduces at threshold, dies at 0 |

**8 presets:**

| Preset | grass_regrow | prey_breed | pred_breed | Character |
|--------|-------------|-----------|-----------|-----------|
| Classic Oscillation | 5 | 6 | 10 | Clear population cycles |
| Predator Boom | 4 | 6 | 12 | Prey crash then predator starvation |
| Prey Paradise | 3 | 5 | 10 | Few predators, prey explosion |
| Fast Dynamics | 2 | 4 | 7 | Rapid oscillations |
| Sparse Savanna | 12 | 8 | 14 | Slow regrowth, fragile ecosystem |
| Dense Jungle | 2 | 5 | 8 | Chaotic dynamics |
| Extinction Edge | 6 | 6 | 14 | Predators barely viable |
| Stable Coexistence | 4 | 7 | 12 | Long-term stable oscillations |

**Interactive controls:** `J` (toggle mode), `Space` (play/pause), `n` (step), `g`/`G` (grass regrowth ±1), `b`/`B` (prey breed ±1), `p`/`P` (pred breed ±1), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Cyclic Cellular Automaton — Greenberg-Hastings rotating spirals with configurable state count and threshold

Cells cycle through N discrete states, advancing to `(s+1) % N` only when ≥ `threshold` neighbors already hold the successor state. Starting from a random grid the rule self-organises into rotating spiral waves (low state count), concentric rings (high count), diamond patterns (Von Neumann neighborhood), or crystalline domains (high threshold). Fully synchronous update with toroidal wrapping. State-to-colour uses a 16-entry table cycling through 6 curses color pairs at three block-character intensities.

**Changed file:** `life.py` (+266 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| State count N | 2–16 discrete states |
| Threshold | Minimum successor-state neighbors to advance (1–8) |
| Neighbourhood | Moore (8-cell) or Von Neumann (4-cell), selectable |
| Update | Fully synchronous parallel |

**8 presets:**

| Preset | States | Threshold | Neighbourhood | Character |
|--------|--------|-----------|---------------|-----------|
| Classic Spirals | 8 | 1 | Moore | Rotating spirals |
| Fine Spirals | 14 | 1 | Moore | Thin delicate spirals |
| Turbulent | 5 | 1 | Moore | Fast chaotic waves |
| Slow Waves | 16 | 1 | Moore | Slow majestic spirals |
| Von Neumann | 8 | 1 | VN | Diamond-shaped waves |
| High Threshold | 8 | 3 | Moore | Sparse, requires 3 neighbors |
| Minimal | 4 | 1 | Moore | Simple fast cycling |
| Crystalline | 6 | 2 | VN | Geometric crystal growth |

**Interactive controls:** `Space` (play/pause), `n` (step), `t`/`T` (threshold ±1), `s`/`S` (state count ±1), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Forest Fire Cellular Automaton — Drossel-Schwabl model with self-organised criticality

Drossel–Schwabl Forest Fire CA, a two-parameter stochastic automaton exhibiting self-organised criticality. Burning cells become empty; trees catch fire if any Moore neighbor is burning, or spontaneously with probability `f` (lightning); empty cells grow trees with probability `p`. Fire spreads to all adjacent trees in a single generation and burns out immediately, producing sharp fire-front geometry.

**Changed file:** `life.py` (+269 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Growth probability `p` | Empty → Tree per step; range 0.001–1.0 |
| Lightning probability `f` | Tree → Burning (spontaneous); range 0.0001–0.1 |
| Neighbourhood | Moore (8-cell) for fire spread |
| Fire duration | 1 generation (burns out immediately) |

**8 presets:**

| Preset | Density | Growth `p` | Lightning `f` |
|--------|---------|-----------|---------------|
| Classic | 0.55 | 0.030 | 0.0005 |
| Dense Forest | 0.85 | 0.050 | 0.0002 |
| Dry Season | 0.30 | 0.010 | 0.0030 |
| Regrowth | 0.40 | 0.080 | 0.0010 |
| Tinderbox | 0.70 | 0.020 | 0.0050 |
| Savanna | 0.15 | 0.020 | 0.0020 |
| Rainforest | 0.95 | 0.060 | 0.0001 |
| Firestorm | 0.50 | 0.040 | 0.0100 |

**Interactive controls:** `Space` (play/pause), `n` (step), `p`/`P` (growth ±0.005), `l`/`L` (lightning ±0.0005), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Abelian Sandpile — Self-organised criticality with parallel toppling and open boundaries

Canonical example of self-organised criticality. Each step optionally drops grains at a configured location, then runs a parallel toppling loop: cells with ≥4 grains fire simultaneously, losing 4 and donating 1 to each von Neumann neighbor. Edge grains are permanently lost (open boundary). Toppling repeats until stable or iteration cap (1,000) reached. Four grain levels color-coded: empty, 1 blue `░░`, 2 green `▒▒`, 3 yellow `▓▓`, ≥4 red `██` bold during topple.

**Changed file:** `life.py` (+392 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Topple threshold | Fixed at 4 grains (standard Abelian rule) |
| Update scheme | Parallel — all unstable cells fire simultaneously each pass |
| Boundary | Open — edge grains lost on topple |
| Drop modes | center, random, corners (quarter-inset), cursor |
| Max topple iterations | 1,000 per step |

**7 presets:**

| Preset | Initial state | Drop mode |
|--------|---------------|-----------|
| Single Tower | Empty | center, 1 grain/step |
| Big Pile | 10,000 grains at centre | center, off |
| Random Rain | Empty | random, 1 grain/step |
| Four Corners | Empty | corners, 1 grain/step |
| Diamond Seed | Diamond of 3-grain cells | center, 1 grain/step |
| Checkerboard | Alternating 3-grain cells | off |
| Max Stable | All cells at 3; centre perturbed | off |

**Interactive controls:** `Space` (play/pause), `n` (step), `d` (cycle drop mode), `a`/`A` (add 100/1000 grains), `e` (drop at cursor), arrow keys/`hjkl` (move cursor), `+`/`-` (steps/frame 1–50), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Epidemic / SIR Disease Spread — Compartmental disease dynamics with distance-weighted transmission

Four-state SIR(D) compartmental disease model on a grid. Phase 1: each infected cell scans within configurable Euclidean radius and attempts transmission to susceptible neighbours using distance-weighted probability `p * (1 − dist/(radius+1))`. Phase 2: apply infections atomically. Phase 3: decrement recovery timers; on expiry transition to Recovered or Dead by mortality rate. Optional Phase 4: Recovered cells lose immunity stochastically (0.005/step) for endemic reinfection waves. Live horizontal bar chart shows S/I/R/D proportions.

**Changed file:** `life.py` (+364 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Transmission | Distance-weighted within Euclidean radius; base probability × (1 − dist/radius) |
| Recovery | Per-cell timer; on expiry: die with `mortality` probability, else recover |
| Reinfection | Optional: Recovered → Susceptible at 0.005/step |
| Population bar | Horizontal S/I/R/D segments, color-coded green/red/blue/dim |

**8 presets:**

| Preset | Density | Radius | Trans. | Recovery | Mortality | Reinfection |
|--------|---------|--------|--------|----------|-----------|-------------|
| Seasonal Flu | 1.0 | 1.5 | 0.25 | 25 | 0.00 | No |
| COVID-like | 0.8 | 2.0 | 0.35 | 30 | 0.02 | No |
| Deadly Plague | 0.7 | 1.5 | 0.40 | 40 | 0.15 | No |
| Measles | 1.0 | 3.0 | 0.60 | 15 | 0.01 | No |
| Reinfection Wave | 0.9 | 1.5 | 0.30 | 20 | 0.00 | Yes |
| Sparse Rural | 0.3 | 2.0 | 0.20 | 25 | 0.05 | No |
| Superspreader | 0.8 | 5.0 | 0.15 | 20 | 0.01 | No |
| Fast Burn | 1.0 | 2.0 | 0.50 | 8 | 0.00 | No |

**Interactive controls:** `Space` (play/pause), `n` (step), `t`/`T` (transmission ±0.05), `v`/`V` (recovery ±5), `d`/`D` (mortality ±0.02), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Diffusion-Limited Aggregation (DLA) — Fractal crystal growth from random walker attachment

Random walkers diffuse on an integer grid and irreversibly attach when adjacent to existing crystal, building fractal aggregates. Attachment is probabilistic (stickiness parameter), enabling tunable branching density. Optional per-axis drift bias enables directed growth (electrodeposition). Symmetric presets use rotated + reflected attachment positions for 6-fold dihedral D₆ snowflake symmetry. Crystal age drives color gradient (blue → cyan → green → yellow → white).

**Changed file:** `life.py` (+508 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Attachment | Probabilistic — walker adjacent to crystal sticks with probability `stickiness` (1.0 = always) |
| Drift bias | Per-axis bias deflects walkers directionally (e.g., −0.15 for upward electrodeposition) |
| Symmetry | `_dla_attach_symmetric` rotates hit offset by `2π/symmetry` and writes all positions; 6-fold adds mirror |
| Spawn radius | Grows with crystal extent; walkers killed if >20 cells beyond spawn radius |
| Visual | Age fraction → 5 color tiers; neighbor count → glyph density `░▒▓█` |

**6 presets:**

| Preset | Seed | Walkers | Stickiness | Symmetry | Character |
|--------|------|---------|------------|----------|-----------|
| Crystal Growth | Center point | 300 | 1.0 | 1 | Classic dendritic fractal |
| Multi-Seed | 5 points | 400 | 1.0 | 1 | Competing aggregates |
| Snowflake | Center point | 300 | 0.7 | 6 | 6-fold dihedral symmetry |
| Electrodeposition | Bottom edge | 500 | 1.0 | 1 | Upward drift bias |
| Line Seed | Horizontal strip | 400 | 1.0 | 1 | Forest-like vertical fronds |
| Ring Seed | Circle | 400 | 1.0 | 1 | Growth inward and outward |

**Interactive controls:** `Space` (play/pause), `n` (step), `s`/`S` (stickiness ±0.1), `w`/`W` (walker count ±50), `+`/`-` (steps/frame ±2), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: N-Body Gravity (Orbital Simulation) — Velocity Verlet integrator with softened gravity and collision merging

Full two-pass Velocity Verlet integrator for gravitational N-body dynamics with O(N²) pairwise force computation. Uses softened gravity `F = G·m₁·m₂ / (r² + ε²)^(3/2)` to prevent singularities. Bodies closer than `0.3 + 0.1·ln(1 + m_total)` cells merge via momentum conservation. Orbital trails maintained as fixed-length deques per body; center-of-mass viewport tracking keeps the system centered.

**Changed file:** `life.py` (+570 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Integration | Velocity Verlet (symplectic, two-pass acceleration) |
| Force law | Softened gravity with configurable G, ε |
| Collision | Distance threshold scales with mass; merged body inherits centroid + momentum |
| Trails | 30-step deque per body; merged bodies inherit constituent trails |

**6 presets:**

| Preset | Bodies | G | dt | Character |
|--------|--------|---|-----|-----------|
| Solar System | 7 | 1.0 | 0.02 | Central star + 6 planets on circular orbits |
| Binary Star | 22 | 1.0 | 0.02 | Two equal stars + 20 debris particles |
| Galaxy Collision | 82 | 0.5 | 0.03 | Two offset disk galaxies with opposing velocities |
| Random Cluster | 60 | 0.8 | 0.03 | Random masses and positions |
| Figure-Eight | 3 | 1.0 | 0.01 | Chenciner–Montgomery periodic 3-body orbit |
| Lagrange Points | 19 | 1.0 | 0.02 | Central mass + planet + Trojans at L4/L5 |

**Visual encoding:** `☉` (mass ≥100), `●` (≥10), `◆` (≥1), `·` (<1); brightness reflects speed; trail aging `· ∘ •`

**Interactive controls:** `Space` (play/pause), `n` (step), `g`/`G` (G ±0.1), `d`/`D` (dt ±0.005), `s`/`S` (softening ±0.1), `t` (toggle trails), `c` (toggle COM tracking), `+`/`-` (steps/frame), `r` (reset), `R` (preset menu), `q`/`Esc` (exit)

### Added: Maze Generation & Pathfinding — Animated generation and solving with 3+4 algorithms

Two-phase animated simulation: maze generation followed by pathfinding, both rendered step-by-step. The maze uses binary odd/even cell encoding (odd = passages, even = walls). Generation transitions automatically to solving when the work queue empties.

**Changed file:** `life.py` (+559 lines)

**3 generation algorithms:**

| Algorithm | Strategy |
|-----------|----------|
| Recursive Backtracker (DFS) | Stack-based; pick random unvisited neighbor 2 cells away, carve wall between, push; backtrack on dead end |
| Prim's | Frontier edge list; pop random edge, carve if target unvisited, add its new edges |
| Kruskal's | Union-find; pre-enumerate shuffled edges; carve if endpoints in different sets |

**4 solving algorithms:**

| Algorithm | Data structure | Heuristic |
|-----------|---------------|-----------|
| A* | Min-heap on `(f, g, r, c)` | Manhattan distance |
| Dijkstra | Min-heap on `(dist, r, c)` | Uniform cost |
| BFS | FIFO list | None (shortest path) |
| DFS | LIFO list | None (no length guarantee) |

**6 presets:** Classic DFS+A*, Prim+Dijkstra, Kruskal+BFS, Backtracker+DFS, Prim+A*, Kruskal+Dijkstra

**Visual encoding:** `██` dim white (wall), green `SS`/red `EE` (start/end), bold green `██` (solution), blue `░░` (explored), bold red `██` (generation head), yellow `▓▓` (backtracker trail)

**Interactive controls:** `Space` (play/pause), `n` (step), `s`/`S` (steps/frame 1–20), `r` (reseed), `R` (preset menu), `q`/`Esc` (exit)

### Added: Ant Colony Optimization (ACO) — Pheromone-based foraging with emergent trail networks

Pheromone-based foraging simulation where continuous-position ants perform biased random walks, depositing and sensing pheromone trails to guide the colony toward food. Each ant samples pheromone at three look-ahead points (left, center, right at ±0.5 rad) and steers toward the strongest signal. Ants carrying food home deposit pheromone with 30% angular correction toward nest. Two-stage pheromone dynamics: 3×3 Moore diffusion kernel + flat evaporation subtraction produces realistic trail narrowing.

**Changed file:** `life.py` (+411 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Sensor model | 3 sensors at ±0.5 rad, sampling 3 cells ahead |
| Trail deposition | Carrying ants deposit `deposit_strength` per step; clamped to 1.0 |
| Pheromone decay | 3×3 box diffusion + flat evaporation subtraction per step |
| Food sources | Placed randomly ≥25% grid distance from nest; finite reserves drain by 1.0 per collection |
| Walker count | `ratio × rows × cols` (minimum 20) |

**6 presets:**

| Preset | Evap | Deposit | Ants | Food sources | Character |
|--------|------|---------|------|-------------|-----------|
| Forager | 0.020 | 0.30 | 8% | 4 | Standard foraging |
| Highway | 0.005 | 0.60 | 12% | 3 | Strong persistent trails |
| Explorer | 0.050 | 0.20 | 10% | 6 | Spread-out exploration |
| Swarm | 0.015 | 0.40 | 25% | 5 | Dense ant coverage |
| Minimal | 0.010 | 0.50 | 4% | 2 | Sparse colony |
| Feast | 0.030 | 0.35 | 15% | 8 | Many food sources |

**Interactive controls:** `Space` (play/pause), `n` (step), `e`/`E` (evaporation ±0.005), `d`/`D` (deposit ±0.05), `s`/`S` (steps/frame), `r` (reseed), `R` (preset menu), `q`/`Esc` (exit)

### Added: Wave Function Collapse (WFC) — Step-by-step procedural generation with entropy-driven tile collapse

WFC procedural generation algorithm adapted for real-time terminal rendering. The grid initializes with every cell holding the full set of valid tile indices; each step the solver finds minimum-entropy uncollapsed cells, picks one, collapses it to a random tile, and runs BFS constraint propagation outward. Adjacency rules enforced bidirectionally. Uncollapsed cells display entropy-shaded blocks (`▓▓` → `▒▒` → `░░` → `!!`) revealing the wave front as it collapses.

**Changed file:** `life.py` (+433 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Entropy selection | Min-cardinality scan across uncollapsed cells; ties broken randomly |
| Collapse | Uniform random sample from possibility set; cell marked in `wfc_collapsed` |
| Propagation | BFS: neighbor possibilities intersected with union of allowed tiles from current cell |
| Auto-cascade | Cells reduced to one possibility immediately committed |
| Contradiction | Empty set halts run; `r` restarts |

**10 tile types:** grass (`░░` green), water (`██` blue), sand (`▓▓` yellow), forest (`╬╬` bold green), mountain (`∧∧` white), river (`~~` bold blue), town (`##` magenta), house (`⌂⌂` cyan), deep water (`≈≈` dim blue), path (`··` dim yellow)

**6 presets:**

| Preset | Tiles | Character |
|--------|-------|-----------|
| Island | water, sand, grass, forest, mountain | Land masses surrounded by ocean |
| Coastline | deep water, water, sand, grass | Layered shores |
| Village | grass, path, house, town, forest | Towns and paths among fields |
| Maze | wall, corridor | Winding corridors |
| Terrain | water, sand, grass, forest, mountain, river | Full landscape with rivers |
| Dungeon | wall, floor, corridor, door | Rooms and corridors |

**Interactive controls:** `X` (toggle mode), `Space` (auto-run toggle), `n` (single collapse step), `s`/`S` (steps per frame 1–50), `r` (restart), `R` (preset menu), `q` (exit)

### Added: Fluid Dynamics (Lattice Boltzmann) — D2Q9 LBM with BGK collision, Zou-He boundaries, and live vorticity

The largest single-commit addition in the pre-refactor monolith brings a full D2Q9 Lattice Boltzmann Method fluid solver. The solver stores the 9-component particle-distribution function `f[r][c][9]` and advances each tick through streaming (propagation), bounce-back (obstacle reflection), and BGK collision (relaxation toward Maxwell–Boltzmann equilibrium at rate ω). Left-boundary inflow uses Zou-He fixed-density equilibrium; right boundary uses zero-gradient outflow.

**Changed file:** `life.py` (+571 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Lattice | D2Q9 (9 discrete velocities + rest) |
| Collision | BGK single-relaxation: each component relaxes toward equilibrium at rate ω |
| Viscosity | ν = (1/ω − 0.5) / 3; ω range 0.50–1.99 |
| Boundaries | Solid: full bounce-back; Inflow: Zou-He at ρ=1, u=u₀; Outflow: zero-gradient copy; Cavity: moving top wall |

**3 visualization modes (cycle with `v`):**

| Mode | Description |
|------|-------------|
| Speed | Velocity magnitude → `░▒▓█` with blue→yellow→red color |
| Vorticity | Curl of velocity; CCW positive (red), CW (blue) |
| Density | Pressure deviation from ρ=1 in magenta/green |

**6 presets:**

| Preset | ω | u₀ | Obstacle | Character |
|--------|---|-----|---------|-----------|
| Wind Tunnel | 1.40 | 0.10 | Single cylinder | Steady flow + wake |
| Von Kármán Street | 1.85 | 0.12 | Smaller cylinder | Vortex shedding |
| Lid-Driven Cavity | 1.50 | 0.10 | 3-wall enclosure | Recirculating vortex |
| Channel Flow | 1.60 | 0.08 | Top+bottom walls | Poiseuille profile |
| Obstacle Course | 1.50 | 0.10 | 5 cylinders | Weaving flow |
| Turbulence | 1.90 | 0.15 | Small cylinder | High-speed chaos |

**Interactive controls:** `F` (toggle mode), `Space` (play/pause), `n` (step), `w`/`W` (ω ±0.05), `u`/`U` (inflow speed ±0.01), `v` (cycle view), `r` (reset), `R` (preset menu), `+`/`-` (steps/frame 1–20), `q` (exit)

### Added: Particle Life — N-body system with randomized attraction/repulsion matrix for emergent self-organization

Continuously-iterated N-body system where colored particle types interact through a randomized N×N attraction/repulsion matrix. Each particle carries `[row, col, vr, vc, type]` state; the force profile has two regimes: within 30% of `max_radius` a strong universal repulsion prevents overlap; beyond that a rule-matrix-derived force peaks at ~0.6× `max_radius` and fades to zero at the boundary. Friction damping and velocity clamping keep the system stable. Each type rendered with distinct Unicode symbols (`● ◆ ■ ▲ ★ ◉ ♦ ✦`).

**Changed file:** `life.py` (+383 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Force profile | 0–30% max_radius: repulsion `(rel/0.3 − 1.0)`; 30–100%: rule-matrix force `attraction × (1 − |2·rel − 1.3| / 0.7)` |
| Rule matrix | N×N values in [−1, 1]; some presets use fixed seeds for reproducibility |
| Physics | Toroidal distance wrapping, friction damping, velocity hard-clamp at 2.0 |

**6 presets:**

| Preset | Types | max_r | friction | Character |
|--------|-------|-------|----------|-----------|
| Primordial Soup | 6 | 15.0 | 0.50 | Random rules, classic emergent life |
| Symbiosis | 4 | 18.0 | 0.40 | Species that orbit and depend on each other |
| Clusters | 3 | 12.0 | 0.60 | Tight self-organizing clumps |
| Predator-Prey | 5 | 20.0 | 0.30 | Chasing and fleeing dynamics |
| Galaxy | 4 | 25.0 | 0.35 | Spiraling orbital structures |
| Chaos | 8 | 14.0 | 0.25 | High energy, many types, wild behavior |

**Interactive controls:** `0` (toggle mode), `Space` (play/pause), `n` (step), `f`/`F` (friction), `d`/`D` (interaction radius), `g`/`G` (force scale), `x` (re-randomize rule matrix), `r` (reseed), `R` (preset menu), `+`/`-` (steps/frame), `q` (exit)

### Added: Boids Flocking Simulation — Craig Reynolds' three-rule steering with emergent murmuration

Craig Reynolds' classic Boids algorithm implementing separation, alignment, and cohesion steering behaviors over a continuous toroidal arena. Each boid is a floating-point `[row, col, vr, vc]` velocity vector; on every tick the algorithm performs O(n²) pairwise scans using toroidal distance, accumulates three independent force channels, blends them with per-preset weights, then clamps velocity to a configurable maximum. Rendering maps each boid's velocity angle to one of eight directional Unicode arrows (`↑ ↗ → ↘ ↓ ↙ ← ↖`) with brightness proportional to speed.

**Changed file:** `life.py` (+389 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Separation | Inverse-square repulsion from close neighbors within `sep_radius` |
| Alignment | Velocity-matching with neighbors within `ali_radius` |
| Cohesion | Steer toward center-of-mass of neighbors within `coh_radius` |
| Speed limits | Velocity clamped at `max_speed`; minimum floor of 0.1 prevents stalling |
| Agent count | `max(30, rows × cols × ratio)` per preset |

**6 presets:**

| Preset | sep/ali/coh radii | Weights | max_spd | Character |
|--------|-------------------|---------|---------|-----------|
| Murmuration | 2.5/7/12 | 2.5/1.2/1.0 | 1.2 | Tight flocks, predator avoidance |
| Fish School | 3/6/10 | 1.5/1.5/1.8 | 0.6 | Slow, highly cohesive groups |
| Swarm | 2/10/15 | 1.0/0.8/0.5 | 1.5 | Fast, loosely coupled agents |
| Migration | 3/15/20 | 1.2/2.0/0.8 | 1.0 | Long-range directional movement |
| Dense Flock | 2/5/8 | 2.0/1.5/2.0 | 0.8 | Tightly packed formation |
| Chaos | 4/6/8 | 3.0/0.5/0.3 | 1.8 | High separation, near-zero cohesion |

**Interactive controls:** `9` (toggle mode), `Space` (play/pause), `n` (step), `s`/`S` (separation radius), `a`/`A` (alignment radius), `c`/`C` (cohesion radius), `+`/`-` (steps/frame), `r` (reseed), `R` (preset menu), `q` (exit)

### Added: Physarum Slime Mold Simulation — Agent-based trail-following with emergent vein networks

Particle-based simulation of *Physarum polycephalum*. Each agent is a floating-point triple `[row, col, heading]` operating on a shared continuous trail grid (values `[0, 1]`). Every step, each agent reads three sensors (left, centre, right) at configurable angular offsets, steers toward the strongest signal (or randomly when centre is weakest), advances, and deposits trail. Diffusion runs as a 3×3 box blur followed by uniform decay subtraction, producing characteristic vein-narrowing and branch-merging behavior.

**Changed file:** `life.py` (+~310 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Sensor model | Three sensors at `±sensor_angle` from heading, sampling trail grid at `sensor_dist` cells ahead |
| Steering | 4-case rule: straight when centre strongest; random ±`turn_speed` when centre weakest; turn toward stronger flank otherwise |
| Trail dynamics | Agent deposits `deposit` amount at landing cell; 3×3 box blur diffusion; uniform `decay` subtraction per step |
| Spawning | Agents placed in filled disk of radius `0.3·min(rows,cols)`, facing outward with ±0.5 rad jitter |

**6 presets:**

| Preset | SA | SD | TS | Description |
|--------|----|----|----|-------------|
| Explorer | 0.40 | 9.0 | 0.30 | Sparse network — long-range foraging |
| Dense Web | 0.30 | 5.0 | 0.40 | Thick interconnected veins |
| Tendrils | 0.60 | 12.0 | 0.20 | Thin branching filaments |
| Pulsing | 0.35 | 7.0 | 0.50 | Rhythmic contraction patterns |
| Maze Solver | 0.25 | 8.0 | 0.60 | Finds shortest paths between food |
| Galaxy | 0.80 | 10.0 | 0.15 | Spiral arm formation |

**Interactive controls:** `8` (toggle mode), `Space` (play/pause), `n` (step), `a`/`A` (sensor angle ±0.05), `s`/`S` (sensor distance ±1.0), `t`/`T` (turn speed ±0.05), `d`/`D` (decay ±0.005), `+`/`-` (steps/frame), `r` (reseed), `R`/`m` (preset menu), `<`/`>` (speed), `q`/`Esc` (exit)

### Added: Lenia Continuous Cellular Automaton — Smooth kernel convolution with Gaussian growth dynamics

Lenia generalises Conway's Game of Life following Bert Chan's 2020 formulation. Cell states are real values in `[0, 1]` rather than binary. A ring-shaped convolution kernel of radius `R` concentrates weight in an annular band peaking at distance `0.5R`, analogous to the alive-neighbor count in classic Life. The growth function `G(u) = 2·exp(−((u − µ) / σ)² / 2) − 1` produces a Gaussian bump so cells in the sweet-spot neighborhood grow while all others decay; update rule: `A(t+dt) = clip(A(t) + dt·G(U), 0, 1)`.

**Changed file:** `life.py` (+~320 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Kernel | `(2R+1)×(2R+1)` array, value at distance `r/R` = `exp(−((r−0.5)/0.15)²/2)`, zeroed outside unit circle, L1-normalised |
| Growth function | `G(u) = 2·exp(−((u−µ)/σ)²/2) − 1` mapping potential to `(−1, 1)` |
| Seeding | Circular blobs with cosine-falloff density and multiplicative noise (×0.8–1.2) |
| Rendering | 5-glyph density scale with warm organic gradient (dark green → bright green → orange → red → white) |

**6 preset species:**

| Species | R | µ | σ | dt | Description |
|---------|---|---|---|-----|-------------|
| Orbium | 13 | 0.150 | 0.015 | 0.10 | Smooth traveling glider |
| Geminium | 10 | 0.140 | 0.014 | 0.10 | Self-replicating twin organism |
| Scutium | 12 | 0.160 | 0.016 | 0.10 | Shield-shaped stationary life |
| Hydrogeminium | 15 | 0.150 | 0.017 | 0.05 | Fluid replicator with organic motion |
| Pentadecathlon | 8 | 0.120 | 0.012 | 0.10 | Pulsating ring oscillator |
| Wanderer | 10 | 0.130 | 0.020 | 0.08 | Erratic slow-moving blob |

**Interactive controls:** `7` (toggle mode), `Space` (play/pause), `n` (step), `u`/`U` (µ ±0.005), `s`/`S` (σ ±0.001), `d`/`D` (R ±1, rebuilds kernel), `t`/`T` (dt ±0.01), `+`/`-` (steps/frame), `r` (reseed), `R`/`m` (preset menu), `<`/`>` (speed), `q`/`Esc` (exit)

### Added: Reaction-Diffusion (Gray-Scott) — Two-chemical pattern formation with continuous concentration fields

Gray-Scott two-chemical reaction-diffusion system. Two continuous concentration grids, `U` and `V`, evolve via coupled PDEs: `dU/dt = Du·∇²U − UV² + f(1−U)` and `dV/dt = Dv·∇²V + UV² − (f+k)V`, using a 5-point discrete Laplacian with toroidal boundaries. Multiple simulation steps can be batched per render frame (default 4, adjustable 1–20) to accelerate pattern formation. Rendering maps V concentration linearly to 5 density glyphs and 8 color tiers.

**Changed file:** `life.py` (+~280 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Diffusion | 5-point discrete Laplacian with toroidal wrapping via negative index arithmetic |
| Seeding | 3×3 to `cols/12`-radius square patches of `U≈0.5, V≈0.25` at random positions; count scales as `max(3, rows×cols/800)` |
| Rendering | V concentration → 5 density glyphs (`  ░░ ▒▒ ▓▓ ██`) and 8 color tiers (dark blue → cyan → yellow → white) |
| Parameters | `Du = 0.16`, `Dv = 0.08`, `dt = 1.0` fixed; only `f` and `k` are live-tunable |

**6 presets:**

| Preset | f | k | Description |
|--------|---|---|-------------|
| Spots (α) | 0.035 | 0.065 | Circular spots that fill space |
| Stripes | 0.025 | 0.060 | Labyrinthine stripe patterns |
| Coral Growth | 0.055 | 0.062 | Branching coral-like tendrils |
| Mitosis | 0.0367 | 0.0649 | Self-replicating spots that divide |
| Worms | 0.078 | 0.061 | Moving worm-like solitons |
| Waves | 0.014 | 0.054 | Pulsating concentric wave patterns |

**Interactive controls:** `6` (toggle mode), `Space` (play/pause), `n` (step), `f`/`F` (feed rate ±0.001), `k`/`K` (kill rate ±0.001), `+`/`-` (steps per frame ±1), `r` (reseed), `R`/`m` (preset menu), `<`/`>` (speed), `q`/`Esc` (exit)

### Added: Falling Sand Particle Simulation — Five-element physics with gravity, combustion, and growth

Falling-sand style particle physics implemented as a sparse dictionary mapping `(row, col)` positions to `(element, age)` tuples. Each tick processes rows bottom-to-top so gravity resolves correctly in a single pass; within each row, columns are shuffled randomly to eliminate directional bias. Fire carries an age counter and expires after 12–20 ticks, produces flicker by toggling bold at 30% probability per frame, and ignites adjacent plants at 40% chance per contact.

**Changed file:** `life.py` (+~350 lines)

**5 element types:**

| Element | Glyph | Color | Behavior |
|---------|-------|-------|----------|
| Sand | `░░` | Yellow | Falls straight down; tries diagonal on block; sinks through water via swap |
| Water | `≈≈` | Blue | Falls then diagonals; flows sideways when fully blocked |
| Fire | `██` | Red→Yellow | Rises stochastically; ignites neighbors; expires after 12–20 ticks |
| Stone | `▓▓` | White | Static; never moved |
| Plant | `██` | Green | Grows near water; ignites when adjacent to fire |

**5 presets:**

| Preset | Description |
|--------|-------------|
| Hourglass | Stone-walled chamber split by narrow gap; top half filled with sand |
| Rainfall | Water sheet above staggered stone ledges |
| Bonfire | Randomised plant forest (60% fill) with fire at base |
| Sandbox | Empty grid — freehand drawing only |
| Lava Lamp | Sealed vessel with alternating rows of sand and water |

**Interactive controls:** `5` (toggle mode), `Space` (play/pause), `n` (step), `1`–`4`/`6` (select element brush), `0` (eraser), `+`/`-` (brush size 1–5), arrow keys/`hjkl` (move), `Enter`/`d` (paint), `r` (clear), `R` (preset menu), `<`/`>` (speed), `q`/`Esc` (exit)

### Added: Wireworld Cellular Automaton — 4-state CA for simulating digital logic circuits

Wireworld is a 4-state cellular automaton designed specifically for simulating digital logic circuits. Each cell holds one of four states — empty, conductor, electron head, or electron tail — and three deterministic transition rules model the flow of electron signals along conductor paths. Heads propagate forward by becoming tails; tails decay back into conductors; a conductor fires into a head only when it has exactly 1 or 2 head-state neighbors. This single conditional makes it possible to construct diodes, clocks, and all standard logic gates.

**Changed file:** `life.py` (+~414 lines)

**State transition table:**

| Current state | Next state | Condition |
|---------------|------------|-----------|
| Empty | Empty | Always |
| Electron head | Electron tail | Always |
| Electron tail | Conductor | Always |
| Conductor | Electron head | 1 or 2 head neighbors |
| Conductor | Conductor | 0 or 3+ head neighbors |

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Grid storage | Sparse `dict[(r,c) -> state]`; only non-empty cells stored |
| Step function | Builds candidate set from all current cells plus Moore neighborhood of every conductor |
| Drawing mode | Opens in edit mode by default; number keys `0`–`3` select brush (eraser/conductor/head/tail); cursor movement auto-paints |
| Rendering | Double-width `██` blocks: blue for electron heads, white for tails, yellow for conductors |

**7 presets:**

| Preset | Description |
|--------|-------------|
| Diode | One-way electron flow using fanout junction |
| Clock | Periodic electron emitter loop |
| OR gate | Output fires if any input carries a signal |
| AND gate | Output fires only when both inputs fire simultaneously |
| XOR gate | Output fires when exactly one input fires |
| Loop | Single electron circulating in a closed conductor loop |
| Empty grid | Blank canvas for drawing custom circuits |

**Interactive controls:** `4` (toggle mode), `Space` (play/pause), `n` (step), `e` (toggle draw mode), `0`–`3` (select brush), `Enter` (cycle cell state), arrow keys/`hjkl` (move/paint), `r` (clear), `R`/`m` (preset menu), `<`/`>` (speed), `q`/`Esc` (exit)

### Added: Hexagonal Grid Mode — 6-neighbor topology with offset-row hex coordinates

Hexagonal grid mode replaces the standard 8-neighbor Moore neighborhood with a 6-neighbor topology appropriate to a hexagonal tiling, toggled by `3`. Because Conway's B3/S23 rules are tuned for a square lattice, enabling hex mode simultaneously switches to **B2/S34** — a well-known hex-life rule that produces interesting emergent structures — and disabling it reverts to B3/S23 automatically.

**Changed file:** `life.py` (+~85 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Coordinate system | Offset-row (even-q) scheme with `HEX_NEIGHBORS_EVEN` / `HEX_NEIGHBORS_ODD` tables — parity-dependent 6 `(dr, dc)` pairs |
| Neighbor counting | `_count_neighbours` dispatches on `hex_mode` boolean to select 6-neighbor hex offsets or original 8-neighbor loop |
| Rendering | Odd grid rows shifted 1 screen column right for visual stagger; live cells render as `⬡` (U+2B22); dead cells as `·` (U+00B7) |
| Rule auto-switch | Toggling hex mode sets B2/S34; toggling off restores B3/S23 |

| Property | Square grid | Hex grid |
|----------|-------------|----------|
| Neighbor count | 8 (Moore) | 6 (offset-row) |
| Default rule | B3/S23 | B2/S34 |
| Live cell glyph | `██` | `⬡ ` |
| Dead cell glyph | (blank) | `· ` |
| Row stagger | none | odd rows +1 column |

**Interactive controls:** `3` (toggle hex grid on/off with auto rule switch), `R` (change rule while in hex mode); all existing GoL controls function identically

### Added: Langton's Ant Turmite — 2D Turing machine with emergent highways and fractal growth

Langton's Ant is a two-dimensional Turing machine where one or more "ants" traverse the grid by reading the color state of the cell they occupy, turning according to a rule string, advancing the cell to the next color state, and stepping forward. The classic `RL` rule spends roughly 10,000 steps in apparent chaos before abruptly locking into a repeating "highway" diagonal corridor — one of the most striking examples of emergent order from simple rules. Extended rule strings introduce additional color states, producing fractal spirals and symmetric filled shapes.

**Changed file:** `life.py` (+~369 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Grid storage | Sparse `dict[(r,c) -> color_state]`; only non-zero cells occupy memory; cells cycling to state 0 are removed |
| Step function | For each ant: read cell's color_state, look up rule character at `state % rule_len`, turn R or L, advance cell to `(state+1) % rule_len`, move forward with toroidal wrapping |
| Multi-ant | 2–4 ants placed symmetrically around grid center at spacing of `grid_rows // 8` |
| Steps per frame | Configurable 1–500 steps per display refresh for fast-forwarding to highway emergence |
| Rendering | Double-width `██` colored by state index using color pairs 1–8; ants overlaid as directional arrows (`▲ ▶ ▼ ◀`) |

**8 presets:**

| Rule | Colors | Character |
|------|--------|-----------|
| `RL` | 2 | Classic — highway after ~10,000 steps |
| `RLR` | 3 | Symmetric triangular patterns |
| `LLRR` | 4 | Grows a filled square |
| `LRRRRRLLR` | 9 | Intricate fractal growth |
| `RRLLLRLLLRRR` | 12 | Chaotic spiral expansion |
| `RRLL` | 4 | Diamond-shaped growth |
| `RLLR` | 4 | Square with internal structure |
| `LRRL` | 4 | Complex highway variant |

**Interactive controls:** `2` (toggle mode), `Space` (play/pause), `n` (step), `+`/`-` (steps per frame 1→500), `r` (reset), `R`/`m` (rule menu), `<`/`>` (speed), `q`/`Esc` (exit)

### Added: Wolfram 1D Elementary Cellular Automaton — All 256 elementary rules with cascading space-time rendering

Wolfram's elementary cellular automaton framework covers all 256 rules of the classic 1D CA formalism. Rather than evolving a 2D grid, each generation produces a single row derived from the previous one by examining every 3-cell neighborhood — so the full space-time history cascades top-to-bottom on screen, making patterns like the Sierpinski triangle or Rule 30's pseudorandom chaos visually immediate.

**Changed file:** `life.py` (+~379 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Rule computation | `_wolfram_apply_rule`: 3-cell neighborhood `(left, center, right)` assembled into a 3-bit index, used as bit-position lookup into the 8-bit rule number |
| Step function | `_wolfram_step` applies rule across every cell with toroidal boundary conditions, appending result as new row |
| Rendering | Most recent rows that fit the display shown, scrolling naturally; live cells render as `█`; row alternation uses color pairs 1 and 2 |
| Rule table display | Row 1 always shows the 8-entry lookup table (`111=# 110=. …`) for instant reference |

**12 presets:**

| Rule | Character |
|------|-----------|
| 30 | Chaotic / pseudorandom — used in Mathematica's RNG |
| 90 | Sierpinski triangle (bitwise XOR of neighbors) |
| 110 | Turing-complete — supports universal computation |
| 184 | Traffic flow model |
| 73 | Complex structures |
| 54 | Complex patterns with triangles |
| 150 | Sierpinski variant |
| 22 | Nested triangles |
| 126 | Complement of Rule 90 |
| 250 | Simple stripes |
| 0 | All cells die immediately |
| 255 | All cells become alive |

**3 seed modes:** `center` (single live cell in middle), `gol_row` (middle row of current GoL grid), `random` (each cell randomized)

**Interactive controls:** `1` (toggle mode), `Space` (play/pause), `n` (step), `←`/`→` (decrement/increment rule number), `r` (reset), `R`/`m` (rule menu), `<`/`>` (speed), `q`/`Esc` (exit)

---

## 2026-03-14

### Added: Genetic Algorithm Evolution Mode — Automated rule discovery through evolutionary search

Rule discovery in Life-like cellular automata is normally manual: the user types a B/S string, watches what happens, and iterates by intuition. This automates the process with a genetic algorithm that maintains a population of competing rulesets, simulates them in parallel, scores them against configurable fitness criteria, and breeds the survivors into the next generation.

**Changed file:** `life.py` (+~500 lines)

**Genetic operators:**

| Operator | Implementation |
|----------|---------------|
| Random rule generation | Each digit 0–8 included in birth/survival independently with 30% probability |
| Mutation | Each digit position flipped independently with configurable probability |
| Crossover | Uniform crossover — for each digit 0–8, pick from parent 1 or 2 with 50/50 probability |
| Selection | Top `elite_count` by fitness kept unchanged; remaining filled by crossover+mutation of elite pairs |

**Fitness criteria:**

| Criterion | Computation | Max |
|-----------|-------------|-----|
| Longevity | Steps where population > 0 | `grid_gens` |
| Population | Average population, capped at 200 | 200 |
| Stability | `max(0, 100 − CV × 100)` where CV = std/mean | 100 |
| Diversity | `min(unique pop values in last 100 steps × 2, 100)` | 100 |

**4 fitness weighting modes:** `balanced` (equal weights), `longevity` (3× longevity), `diversity` (3× diversity), `population` (3× population)

**Configuration:**

| Parameter | Default | Range |
|-----------|---------|-------|
| Population size | 12 | 4–24 |
| Sim generations | 200 | 50–2000 |
| Mutation rate | 15% | 0–100% |
| Elite survivors | 4 | 2–pop/2 |
| Fitness criteria | balanced | 4 modes |

**UI:** Upper region tiles all grids in a √N layout with rule labels; lower region shows scoreboard with rank, rule, score components, and population sparklines. Best-ever tracker persists across all GA generations. `★` marks the best, `●` marks elites.

**Interactive controls:** `E` (enter/exit evolution mode), `Space` (play/pause or breed next generation), `n` (step/breed), `s` (skip to end), `a` (adopt selected rule into main simulator), `f` (cycle fitness mode), `m` (set mutation rate), `↑`/`↓` (select individual)

### Added: Puzzle/Challenge Mode — 10 goal-directed challenges with cell budgets and scoring

Every other mode in the simulator is open-ended: the user sets things up and watches what happens. Puzzle mode reverses the relationship — it presents a specific cellular automaton objective, gives the player a limited cell budget, and scores them on how efficiently they achieve the goal. Ten built-in puzzles span six challenge types, with a three-phase gameplay loop (planning → running → result).

**Changed file:** `life.py` (+~350 lines)

**6 challenge types:**

| Type | Win condition | Fail conditions |
|------|--------------|-----------------|
| `still_life` | Grid reaches period-1 cycle with cells alive | Population 0; time limit |
| `oscillator` | Grid enters cycle with period ≥ min_period | Population 0; still life; time limit |
| `reach_population` | `population >= target` | Population 0; time limit |
| `escape_box` | Any live cell exits the initial bounding box | Population 0; time limit |
| `extinction` | `population == 0` | Cycle detected with pop > 0; time limit |
| `survive_gens` | Pattern survives N+ gens, not still or extinct | Extinction; still life; time limit |

**10 puzzles:**

| # | Name | Type | Budget | Goal |
|---|------|------|--------|------|
| 1 | First Still Life | still_life | 4 | Build a stable pattern |
| 2 | Blinker Builder | oscillator | 5 | Build an oscillator |
| 3 | Population Boom | reach_population | 5 | Reach population 20 |
| 4 | Spaceship Launch | escape_box | 6 | Escape 10×10 box |
| 5 | Extinction Event | extinction | 7 | Kill all cells |
| 6 | Higher Period | oscillator (≥3) | 20 | Period-3+ oscillator |
| 7 | Population Explosion | reach_population | 10 | Reach population 100 |
| 8 | Efficient Still Life | still_life | 6 | Stable with minimal cells |
| 9 | Speed Run | reach_population | 8 | Reach 50 quickly |
| 10 | Grand Challenge | survive_gens | 6 | Survive 500+ generations |

**Scoring:** `cell_bonus = 100 × max_cells / cells_used` + `gen_bonus = 50 × (limit − win_gen) / limit`; fewer cells and faster wins yield higher scores. Best scores tracked per puzzle for the session.

**Interactive controls:** `C` (enter/exit puzzle mode), `↑`/`↓` (navigate), `Enter` (start/next), `e`/`d`/`x` (place/draw/erase cells), `c` (clear), `?` (show hint), `Esc` (abort), `r` (retry)

### Added: 3D Isometric View Mode — Pseudo-3D cityscape where cell age becomes pillar height

The existing flat 2D representation treats every living cell as identical. Cell age — already tracked numerically and expressed through colour gradients — contains useful structural information: old cells belong to stable cores, young cells are the active frontier. This adds a pseudo-3D isometric cityscape renderer that makes age physically tangible by extruding each living cell into a vertical pillar whose height grows with age.

**Changed file:** `life.py` (+~180 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Projection | Oblique projection: each successive grid row shifted one column right and one row up on screen |
| Rendering order | Painter's algorithm — grid rows rendered back-to-front so closer pillars correctly occlude farther ones |
| Z-buffer | Sparse `zbuf` dict keyed on screen `(sy, sx)` accumulates glyph and colour data; only cells needing drawing write to it |
| Right-face shading | Each pillar has a right-face shade column using `_ISO_SHADE_MAP` (`█→▓`, `▓→▒`, `▒→░`) |

**Pillar height tiers:**

| Cell age | Pillar height | Characters (bottom → top) |
|----------|---------------|---------------------------|
| ≤ 1 (newborn) | 1 row | `█` |
| 2–3 (young) | 2 rows | `█`, `▓` |
| 4–8 (mature) | 3 rows | `█`, `▓`, `▒` |
| 9–20 (old) | 4 rows | `█`, `▓`, `▒`, `░` |
| > 20 (ancient) | 5 rows | `█`, `▓`, `▒`, `░`, `·` |

**Interactive controls:** `I` (toggle 3D isometric view on/off), arrow keys/`hjkl` (move cursor/pan viewport), `Space` (play/pause), `n` (single step), `H` (toggle heatmap overlay)

### Added: Zoom/Scale Mode — Multi-level density-glyph zoom for surveying large-scale pattern structure

The simulator has always rendered the grid at 1:1 scale — one terminal character per living cell. For small patterns this is ideal, but emergent large-scale structures (glider streams, oscillator fields, methuselah explosions) were impossible to survey without scrolling. This adds a multi-level zoom system that compresses each N×N block of grid cells into a single Unicode density glyph that encodes how many of those cells are alive.

**Changed file:** `life.py` (+~120 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Zoom levels | `ZOOM_LEVELS = [1, 2, 4, 8]`; each screen character represents a `zoom × zoom` block of grid cells |
| Density glyphs | 0% → space, 1–25% → `░░`, 26–50% → `▒▒`, 51–75% → `▓▓`, 76–100% → `██` |
| Overlay interop | Heatmap mode sums heat across the block; blueprint highlighting works at block level; pattern labels reposition by dividing coordinates by zoom factor |
| Cursor | Block containing cursor rendered with `A_REVERSE` |
| Key rebinding | Speed controls moved from `+`/`-` to `>`/`<` to free zoom keys |

**4 zoom levels:**

| Level | Grid cells per character | Use case |
|-------|--------------------------|----------|
| 1× | 1 × 1 | Editing, detailed inspection |
| 2× | 2 × 2 | Overview of medium-sized patterns |
| 4× | 4 × 4 | Surveying large evolving structures |
| 8× | 8 × 8 | Full-grid macro view |

**Interactive controls:** `+`/`=` (zoom in), `-`/`_` (zoom out), `0` (reset to 1:1), `>`/`<` (speed up/down)

### Added: Multiplayer Mode (TCP Networking) — Two-player competitive Game of Life over TCP with territory scoring

Two players on separate terminals claim halves of the same grid and battle for cellular dominance. The host binds a TCP port; the client connects. After a 30-second planning phase — where each player draws cells exclusively in their territory — the host runs an authoritative simulation for 200 generations. Newborn cells inherit ownership by majority-neighbor vote, creating fluid battle lines that shift with each generation. Built entirely on Python built-in modules (`socket`, `threading`, `queue`, `json`).

**Changed file:** `life.py` (+1,108 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Transport | `MultiplayerNet` class: TCP socket with newline-delimited JSON wire protocol, background I/O thread so curses loop never blocks |
| Message types | `hello`, `start_planning`, `place`, `ready`, `start_sim`, `state`, `finished`, `quit` |
| 4-phase flow | `idle` → `lobby` (waiting for peer) → `planning` (30 s timer) → `running` (200 gen) → `finished` (results) |
| Territory split | Grid halved vertically: P1 (Blue) owns the left, P2 (Red) the right; placement enforced per-player during planning |
| Real-time sync | Cell placements broadcast immediately as `place` messages; host broadcasts compact state every 3rd generation |
| Ownership propagation | `_mp_step()` applies GoL rules then recomputes owners: surviving cells keep theirs; newborn cells assigned by majority neighbor vote; ties produce contested (yellow) |
| Scoring | `base = owned_cells`; `territory_bonus = owned cells in opponent's half × 2`; final = `base + territory_bonus` |
| Host authority | Only the host runs `_mp_step()`; client receives and applies state, preventing divergence |

**Interactive controls (planning):** Arrow keys/`hjkl` (move cursor), `e` (toggle cell), `d` (draw mode), `r` (random fill own territory), `c` (clear own territory), `Enter` (mark ready)

**Interactive controls (game):** Running phase is view-only; `Enter` (host, finished — new round), `N` (open/exit multiplayer)

**CLI flags:** `--host [PORT]` (launch into host lobby), `--connect HOST:PORT` (connect as client)

### Added: Race Mode — Multi-rule evolutionary tournament on cloned grids

Race mode turns rule exploration into a competition. The user selects 2–4 Life-like rule sets from the preset library (or types custom `B.../S...` strings), and each rule is seeded with an identical copy of the current grid state. All grids then evolve simultaneously, step-for-step, while a live scoreboard tracks their diverging fates. A composite scoring formula crowns a winner once the configured generation limit is reached.

**Changed file:** `life.py` (+454 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Grid cloning | `_start_race()` deep-copies `cells`, `generation`, and `population` from the live grid into fresh `Grid` instances, each with a different `birth`/`survival` set |
| Simultaneous stepping | `_step_race()` advances every non-extinct grid each generation; extinct grids frozen |
| Extinction detection | Per-grid `extinction_gen` recorded on first generation population hits zero |
| Oscillation detection | State hash stored each generation; hash collision gives `osc_period = current_gen - first_seen_gen` |
| Scoring formula | `score = current_pop + survival_bonus + osc_bonus(50) + peak_pop // 2` |
| Layout | 2 grids: side-by-side (1×2); 3–4 grids: 2×2 tile layout with border separators |
| Progress bar | `█░` fill proportional to `gens_elapsed / race_max_gens` with percentage readout |
| Scoreboard | Columns: Rank, Rule, Pop, Peak, Osc period, Extinction gen, Score; sorted by live pop during race, final score after |

**Interactive controls:** `Z` (open rule selection / exit race mode), `Space` (toggle rule on/off, max 4), `/` (custom rule string), `g` (set race duration 10–10,000 gens), `Enter` (start race, requires ≥2 rules), `Esc`/`q` (cancel)

### Added: Sound/Music Mode — Grid-driven procedural audio synthesizer

The Game of Life grid becomes a real-time generative instrument. Each generation, living cells are scanned row-by-row: the row index determines pitch (top rows map to high frequencies, bottom rows to low), producing an evolving pentatonic melody driven entirely by the emergent patterns on screen. All audio is synthesized from scratch in pure Python — no external libraries, just `math`, `wave`, `struct`, and a subprocess pipe to whatever player the system provides.

**Changed file:** `life.py` (+204 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Pitch mapping | `_row_to_freq()` inverts row index so row 0 is highest pitch, wraps through multiple octaves using `_PENTATONIC = [0, 2, 4, 7, 9]` semitone offsets (C-D-E-G-A) from a 220 Hz base |
| Polyphony cap | At most 12 simultaneous voices; when more rows are active, evenly-spaced rows are sampled |
| Volume scaling | Master amplitude derived from live population density: `0.15 + 0.85 * density` |
| Waveform synthesis | `_synthesize()` sums per-frequency sine waves into a mixed S16LE mono PCM buffer; per-voice amplitude = `volume / len(freqs)` to prevent clipping |
| Click prevention | 5 ms linear attack and release ramps applied at start and end of each audio chunk |
| Tempo lock | Chunk duration = `max(0.05, min(speed_delay * 0.8, 2.0))` seconds, keeping audio rhythm synchronized to simulation speed |
| Player detection | `_detect_player()` probes for `paplay`, `aplay`, and `afplay` in order; macOS `afplay` requires a temp `.wav` file |
| Threading | Each chunk plays in a daemon thread; if a previous thread is still alive, the frame is skipped |

**Interactive controls:** `M` (toggle sound on/off; flashes "no audio player found" if none detected); status bar shows `♪ SOUND` when active

### Added: GIF Recording and Export — Zero-dependency animated GIF export of simulation runs

Press `G` to start recording, run or step the simulation for as long as you like, press `G` again, and a fully-formed animated GIF lands in `~/.life_saves/` — no external libraries, no Pillow, no ImageMagick. The entire GIF89a encoder, including LZW compression, is implemented from scratch using only Python's `struct` module.

**Changed file:** `life.py` (+238 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| GIF89a structure | `write_gif()` assembles header, logical screen descriptor, global color table, Netscape looping extension, per-frame graphic control extensions, image descriptors, and trailer byte |
| 8-color palette | `_GIF_PALETTE` maps indices 0–7 to background dark, five age-tier colors (green/cyan/yellow/magenta/red), a subtle grid grey, and spare white |
| Age-to-palette mapping | `_gif_age_index(age)` converts cell age integers to palette indices using the same tier thresholds as `color_for_age` |
| LZW compression | `_lzw_compress(pixels, min_code_size)` implements full variable-width LZW: maintains code table, emits clear codes on overflow (>4095), packs bits LSB-first |
| Sub-block framing | `_gif_sub_blocks(data)` splits compressed output into GIF sub-blocks of ≤255 bytes |
| Frame capture | `_capture_recording_frame()` snapshots `grid.cells` with a list comprehension for shallow copy of all cell ages |
| Speed-aware delay | `delay_cs = max(2, int(SPEEDS[self.speed_idx] * 100))` so GIF playback speed matches simulation speed |
| Cell rendering | Each cell rendered at `cell_size=4` pixels per side — clean blocky squares with no interpolation |
| Filename convention | `recording_gen{start}-{end}_{unix_timestamp}.gif` written to `~/.life_saves/` |

**Interactive controls:** `G` toggles recording on/off; status bar shows `⏺ REC(N)` with live frame count while active

### Added: Blueprint Mode — Interactive region capture and persistent personal pattern library

The built-in pattern library covers classic structures, but Game of Life creativity lives in what users construct themselves. Blueprint mode closes the loop between freehand grid editing and reusable patterns: select any rectangular region, capture whatever alive cells are inside it, name the result, and it is immediately available as a stamp — indistinguishable from built-in patterns throughout the UI, and persisted across sessions in a JSON file on disk.

**Changed file:** `life.py` (+293 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Persistence layer | `BLUEPRINT_FILE` points to `~/.life_saves/blueprints.json`; `_load_blueprints()` / `_save_blueprints()` handle JSON read/write with error recovery |
| Region selection | `W` anchors the selection at the cursor; cursor movement extends the rectangle; `_blueprint_region()` returns `(min_r, min_c, max_r, max_c)` |
| Cell capture | Collects alive cells within the bounding box, normalizes to (0,0) origin, prompts for name, sanitizes (lowercase, underscores, alphanum only), and refuses to overwrite built-in patterns |
| Unified lookup | `_get_pattern(name)` checks `PATTERNS` first, then `self.blueprints`, giving all code a single API for both sources |
| Pattern list rebuild | Merges `set(PATTERNS.keys()) | set(self.blueprints.keys())` into one sorted list after every create/delete |
| Deletion | `_delete_blueprint(name)` removes from memory, re-saves JSON, and rebuilds the list |

**Visual feedback:**

| Signal | Meaning |
|--------|---------|
| Green `░░` overlay | Empty cells inside the active selection rectangle |
| Green bold highlight | Alive cells inside the active selection rectangle |
| `📐 BLUEPRINT` | Status bar indicator when selection mode is active |
| `[BP]` prefix | Marks user blueprints in pattern/stamp menus |

**Interactive controls:** `W` (enter blueprint selection mode; move to expand; `Enter` to capture and name; `Esc` to cancel), `T` (open blueprint library; `↑`/`↓` navigate; `Enter` to stamp; `D`/`Delete` to remove; `q`/`Esc` to close)

### Added: Pattern Recognition Engine — Real-time identification of known Game of Life structures in any orientation

The simulation has always been a canvas for watching patterns emerge, but until now there was no way to know _what_ you were watching. This introduces a full pattern recognition subsystem that continuously scans the live grid and labels every known structure it finds — still lifes, oscillators, and spaceships — all color-coded by category and annotated with name tags rendered directly on the grid.

**Changed file:** `life.py` (+274 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Canonical normalization | `_normalise(cells)` shifts any cell-set to a (0,0) top-left origin for comparison |
| Orientation generation | `_orientations(cells)` produces up to 8 distinct variants (4 rotations × optional reflection), deduplicating by normalized form |
| Recognition database | `_build_recognition_db()` builds from `PATTERNS` plus 5 extra patterns (loaf, boat, tub, ship, pond), filtered to ≤15 cells for performance |
| Grid scan | `scan_patterns(grid)` iterates every alive cell as a candidate anchor; tries all orientations against the live `alive` set |
| Bounding-box guard | For each candidate match, extra alive cells in the bounding box disqualify the match, preventing false sub-pattern hits |
| Cell claiming | Matched cells added to a `claimed` set; no cell can belong to two patterns; larger patterns tried first |

**Recognized patterns:**

| Category | Patterns | Color |
|----------|----------|-------|
| Still lifes | block, beehive, loaf, boat, tub, ship, pond | Cyan |
| Oscillators | blinker, toad, beacon | Yellow |
| Spaceships | glider, lwss | Magenta |

**Interactive controls:** `F` toggles pattern search mode on/off; status bar shows `🔍 SEARCH(N)` with live match count; scan re-runs on every step and cell edit

### Added: Heatmap Visualization Mode — See where life has concentrated across every generation at a glance

The cell-aging color scheme shows how long individual cells have been continuously alive, but it resets whenever a cell dies. The heatmap overlay answers a different question: across the entire simulation so far, which positions have been alive most often? Glider highways, oscillator cores, and still-life clusters all leave distinct thermal signatures. Toggle it with `H`.

**Changed file:** `life.py` (+89 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Counter storage | `self.heatmap: list[list[int]]` — 2D grid matching dimensions, initialized to zero; `self.heatmap_max: int` tracks peak for normalisation |
| Per-generation accumulation | `_update_heatmap()` iterates all cells; inner loop checks `row_cells[c] > 0` and increments the counter, updating the peak inline |
| Gradient mapping | `color_for_heat(fraction)` selects from `HEAT_PAIRS_256` or `HEAT_PAIRS_8` based on `curses.COLORS >= 256` |
| 256-color tiers | 8 tiers: near-black blue → blue → bright blue → cyan → yellow → orange → red → white (xterm indices 17→19→27→51→226→208→196→231) |
| 8-color fallback | Graceful fallback using standard ANSI colors for terminals with fewer than 256 colors |
| Live-cell emphasis | Renderer applies `curses.A_BOLD` when `age > 0` on top of the heat color, distinguishing currently alive cells from historical hotspots |
| Counter reset | Both `c` (clear) and `r` (randomize) reset heatmap to all-zeros |
| Status indicator | `"  │  🔥 HEATMAP"` appended to status bar when active |

**Interactive controls:** `H` (toggle heatmap on/off), `c` (clear grid + reset heatmap), `r` (randomize grid + reset heatmap)

### Added: Time-Travel Timeline Bar with Bookmarks — Non-destructive VCR-style history scrubber replacing destructive rewind

The original rewind system was destructive: pressing `u` popped the most-recent state off a `deque`, consuming it. Scrubbing back five steps made those five states permanently unreachable. This replaces that model entirely. History is now stored in a plain `list` supporting random access, and a `timeline_pos` integer pointer marks where in that list the display currently sits. Rewinding moves the pointer without touching the list; resuming play from a scrubbed-back position truncates only the future portion before appending the new state.

A visual timeline bar renders above the population sparkline. When scrubbed back it shows a filled-block (`█`) segment proportional to how far through the saved buffer the current position is, followed by empty-block (`░`) characters representing the unvisited future. Saved bookmarks appear as `★` glyphs at their proportional positions on the bar.

**Changed file:** `life.py` (+148 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| History data structure | Changed from `collections.deque(maxlen=500)` to `list[tuple[dict, int]]` with manual `history_max = 500` cap |
| Non-destructive pointer | `timeline_pos: int \| None` — `None` means "live at head"; an integer is a 0-based index into `self.history` |
| Future truncation | `_push_history` checks `if self.timeline_pos is not None: self.history = self.history[:self.timeline_pos + 1]` before appending |
| 10-step scrubbing | `_scrub_back(10)` clamps to 0; `_scrub_forward(10)` returns to `None` (live) when index exceeds `len(history) - 1` |
| Timeline bar | Bar width = `max_x - label_widths`; bookmark glyphs located by scanning history for matching generation numbers |
| Bookmark storage | Each bookmark stores a `(generation, grid_dict, pop_len)` triple, kept sorted by generation number |
| Bookmark deduplication | `_add_bookmark` refuses duplicates by checking for an existing entry with the same generation number |

**Interactive controls:** `u` (rewind one step, non-destructive), `[` (scrub back 10 steps), `]` (scrub forward 10 steps), `b` (bookmark current generation), `B` (open bookmark list), `↑`/`↓` or `j`/`k` (navigate bookmarks), `Enter` (jump to bookmark), `D`/`Delete` (delete bookmark), `q`/`Esc` (close menu)

### Added: Multi-Grid Side-by-Side Comparison — Watch two rule sets diverge from the same seed

Running two simulations from an identical initial configuration and watching them evolve under different rule sets is the clearest possible demonstration of how sensitive cellular automata are to their rule parameters. This adds a full split-screen comparison mode, toggled with `V`, that forks the current live grid state into a second independent simulation running a user-chosen rule. Both grids step in perfect lockstep — whether via auto-play or manual single-stepping — so generation numbers stay synchronised and divergence is immediately visible.

**Changed file:** `life.py` (+231 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| State isolation | `grid2: Grid \| None` holds the second simulation; `pop_history2: list[int]` tracks its population independently |
| Forking | `_start_compare()` copies `grid.cells` row-by-row, copies `generation`, `population`, and the full `pop_history` list, then assigns the new `birth`/`survival` sets |
| Lockstep stepping | Both the auto-play loop and the single-step handler call `grid2.step()` and append to `pop_history2` immediately after advancing the primary grid |
| Split renderer | `_draw_compare()` computes `half_x = max_x // 2` as the divider column, allocates left and right cell columns per panel |
| Rule picker | `compare_rule_menu` flag routes key events to `_handle_compare_rule_menu_key`; supports preset selection, `Enter` to confirm, and `/` for custom entry |
| Dual sparklines | Each panel footer shows its own `sparkline(pop_history, spark_w)` independently |

**Interactive controls:** `V` (enter/exit comparison mode), `↑`/`↓` or `j`/`k` (navigate rule presets), `Enter` (confirm rule), `/` (custom `B.../S...` rule string), `q`/`Esc` (cancel picker), `Space`/`n` (advance both grids simultaneously)

### Added: RLE Pattern File Import — Load any pattern from the Game of Life community's standard file format

The app's built-in pattern library covers classic structures, but the broader Game of Life community has catalogued thousands of objects — spaceships, methuselahs, logic gates, self-replicators — almost all distributed as `.rle` files (Run Length Encoded), the interchange format used by LifeWiki and Golly. This adds a complete RLE parser and an import workflow bound to the `i` key, allowing users to download any pattern from the web and load it directly into the simulator. The parser handles the full metadata header, both the modern `B3/S23` rule notation and the older `S/B` legacy format, and auto-applies whatever rule the pattern embeds — so a HighLife pattern loaded from LifeWiki will automatically switch the engine to HighLife rules without any manual intervention.

**Changed file:** `life.py` (+136 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Metadata parsing | Line-by-line pre-scan reads `#N` (name), `#C`/`#c` (comments), and `#O` (author) before the header; unrecognised `#` tags are silently ignored |
| Header extraction | The `x = M, y = N [, rule = ...]` line is split on commas and `=`, populating a `parts` dict; `rule` is optional |
| Dual rule format support | If the rule value starts with `B`, it is used as-is (modern notation); if it contains `/` with digit-only parts, it is reinterpreted from legacy `S/B` order into `B.../S...` |
| RLE run-length decode | A single-pass character scan accumulates a numeric run count, then dispatches on `b`/`.` (skip columns), `o`/`A` (emit alive cells), and `$` (advance rows); the loop terminates at `!` |
| Centered placement | Offsets computed as `off_r = (grid.rows - height) // 2`, `off_c = (grid.cols - width) // 2`; cells placed with modular wrapping |
| Rule auto-apply | After parsing, if `rle["rule"]` is non-empty, `parse_rule_string()` is called and the result is applied to `grid.birth`/`grid.survival` |
| Status summary | Flash message reports pattern name, bounding box dimensions, and live cell count |

**Interactive controls:** `i` — prompt for RLE file path (supports `~` expansion); Enter at empty prompt or non-existent path cancels with error flash

### Added: Rule Editor for Life-Like Cellular Automata — Explore beyond Conway's with configurable birth/survival rules

Conway's Game of Life is one specific point in a vast space of two-state, totalistic cellular automata. This generalises the simulation engine to support the full family of "Life-like" rules — where any combination of neighbor counts can trigger birth or survival — and adds an interactive rule editor so users can explore that space without touching code. Nine curated presets cover a broad range of behaviors: stable-growth rules like HighLife (which supports a second replicator), chaotic rules like Day & Night (symmetric under alive/dead inversion), explosive rules like Seeds (no survival, pure birth), and slow-changing structures like Anneal. Rules persist in save files so an experiment can be resumed exactly, and the active rule is always visible in the status bar.

**Changed file:** `life.py` (+117 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Generalised step function | `Grid.step()` replaces hardcoded `n in (2, 3)` / `n == 3` checks with `n in self.survival` and `n in self.birth` set membership tests |
| Rule string format | `rule_string(birth, survival)` formats rules as `B{digits}/S{digits}` (e.g., `B3/S23`); `parse_rule_string()` validates and parses the same notation |
| Nine presets | `RULE_PRESETS` dict: Conway's Life, HighLife, Day & Night, Seeds, Life w/o Death, Diamoeba, 2x2, Morley, Anneal |
| Custom rule entry | Pressing `/` inside the rule menu calls `_prompt_text()` for a free-form rule string; invalid input is rejected with an error flash |
| Save/load persistence | `Grid.to_dict()` serialises the active rule string; `Grid.load_dict()` restores it, with graceful fallback to Conway's for older save files |
| Status bar display | The formatted rule string (e.g., `Rule: B36/S23`) is injected into the status line on every draw frame |

**9 rule presets:**

| Preset | Rule | Behavior |
|--------|------|----------|
| Conway's Life | B3/S23 | The classic — gliders, oscillators, spaceships |
| HighLife | B36/S23 | Supports a small self-replicator |
| Day & Night | B3678/S34678 | Symmetric under alive/dead inversion |
| Seeds | B2/S (none) | Explosive — no survival, every birth is a one-shot spark |
| Life w/o Death | B3/S012345678 | Cells never die — ink-blot growth |
| Diamoeba | B35678/S5678 | Amoeba-like expanding blobs |
| 2x2 | B36/S125 | Replicating blocks |
| Morley | B368/S245 | Complex long-lived dynamics |
| Anneal | B4678/S35678 | Slowly annealing domain walls |

**Interactive controls:** `R` — open rule editor; `↑`/`↓` or `j`/`k` — navigate presets; `Enter` — apply selected preset; `/` — type a custom `B.../S...` rule string; `q` / `Esc` — cancel

### Added: Stamp Mode — Non-destructive pattern overlay at cursor position

Until this commit, the only way to place a preset pattern was via the `p` key, which wiped the entire grid before placing the pattern at the center. Stamp mode introduces a second, non-destructive placement path: press `t` to open a pattern selector, choose a pattern, and it is overlaid centered on the current cursor without disturbing any existing cells. This makes it practical to compose complex scenes — placing multiple gliders aimed at each other, positioning an eater next to a glider gun, or layering oscillators — all within a single session without rebuilding from scratch.

**Changed file:** `life.py` (+43 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Separate menu state | New `self.stamp_menu` boolean, independent of `self.pattern_menu`, prevents the two modes from interfering |
| Cursor-centered placement | `_stamp_pattern()` computes `off_r = cursor_r - max_r // 2` and `off_c = cursor_c - max_c // 2` using the pattern's bounding box, then calls `grid.load_pattern()` with those offsets |
| Shared UI, forked behavior | The existing `_draw_pattern_menu()` and `_handle_menu_key()` are reused; the Enter handler branches on `stamp_menu` vs `pattern_menu` to decide whether to clear-and-place or overlay |
| No history wipe | Unlike normal pattern load, stamp mode does not call `pop_history.clear()`, preserving the population graph |

**Interactive controls:** `t` — open stamp pattern selector; `Enter` — stamp selected pattern at cursor; `q` / `Esc` — cancel without stamping

### Added: Generation Rewind/Undo — Step backwards through simulation history one generation at a time

The simulator already supports stepping forward manually with `n` and running at variable speeds, but there was no way to go back and inspect a past state — once a generation was computed it was gone. This feature adds a rewind buffer: before every generation advance the full grid state is serialized via `Grid.to_dict()` and pushed onto a bounded `deque`. Pressing `u` pops the most recent snapshot, restores the grid, trims the population history array back to the length it had at that moment, resets cycle detection, and flashes a confirmation showing the restored generation number. The buffer is capped at 500 entries so memory use stays bounded regardless of how long the simulation runs.

**Changed file:** `life.py` (+35 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| History buffer | `App.history: collections.deque[tuple[dict, int]]` with `maxlen=500`; each entry is a `(grid_dict, pop_history_length)` tuple |
| Snapshot | `_push_history()` calls `self.grid.to_dict()` and records `len(self.pop_history)` before every `grid.step()` call |
| Restore | `_rewind()` calls `self.history.pop()`, restores the grid with `self.grid.load_dict(grid_dict)`, slices `self.pop_history` back to the saved length, and resets cycle detection |
| Buffer cap | `deque(maxlen=500)` — oldest entries are automatically discarded when the buffer is full |
| Population history sync | The saved `pop_history_length` integer lets `_rewind()` trim the population graph precisely back to match the rewound generation |
| Integration points | `_push_history()` called in both the auto-play loop and the manual-step key handler |

**Interactive controls:** `u` (pause simulation and rewind one generation), `n` / `.` (step forward — each step is saved to the rewind buffer first), `Space` (resume play — history accumulates during auto-play too)

### Added: Draw/Erase Mode — Freehand continuous cell painting and erasing with modal cursor movement

Before this feature the only way to place cells manually was to move the cursor to each cell individually and press `e` to toggle it — a slow, one-click-at-a-time workflow poorly suited to drawing custom patterns. Draw mode and erase mode change this by making cursor movement itself the painting action. Activating draw mode with `d` immediately sets the cell under the cursor alive and enters a persistent mode where every subsequent cursor movement automatically sets each visited cell alive. Erase mode (`x`) works identically but sets cells dead. Both modes are fully symmetric: pressing `d` again while already in draw mode turns it off, and likewise for `x`; `Esc` exits either mode unconditionally. A visual indicator (`✏ DRAW` or `✘ ERASE`) appears in the status bar so the user always knows which mode is active.

**Changed file:** `life.py` (+59 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| Mode state | `App.draw_mode: str \| None` — holds `None`, `"draw"`, or `"erase"` |
| Paint-on-move | `_apply_draw_mode()` helper called after every cursor movement; calls `Grid.set_alive()` or `Grid.set_dead()` at the new cursor position when a mode is active |
| Mode activation | `d` / `x` key handlers set `draw_mode`, immediately paint/erase the current cursor cell, and flash a descriptive hint |
| Mode exit | Pressing the same mode key again, or pressing `Esc` (keycode 27), sets `draw_mode = None` |
| Cycle detection integration | `_reset_cycle_detection()` called on every paint and erase action to keep state history consistent |
| Status bar indicator | Mode string appended to the status line as `"  │  ✏ DRAW"` or `"  │  ✘ ERASE"` when active |

**Interactive controls:** `d` (toggle draw mode — paint alive cells while moving), `x` (toggle erase mode — clear cells while moving), `Esc` (exit either mode), arrow keys / `hjkl` (move cursor and paint/erase when a mode is active)

### Added: Cycle Detection — Auto-pause when the simulation reaches a fixed point or repeating loop

Conway's Game of Life patterns often quietly stabilize into still lifes, oscillators, or simply die out — but without feedback, a user watching a long-running evolution has no way to know when it has settled. This feature introduces automatic cycle detection: after every generation step the grid state is fingerprinted using an MD5 hash of all alive-cell positions, and that fingerprint is compared against a growing dictionary of previously-seen states. The moment a repeated state is recognized the simulation auto-pauses and displays a diagnostic flash message. Three distinct outcomes are distinguished: complete extinction (population reaches zero), a still life (the grid is identical to the previous generation, i.e. period 1), and a general oscillator (period N, where N is the difference between the current generation counter and the generation at which that state was first recorded). The detection history resets automatically whenever the grid is modified externally — via clear, randomize, cell toggle, pattern load, or save load — and also when the user resumes play after a pause.

**Changed file:** `life.py` (+45 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|---------------|
| State fingerprinting | `Grid.state_hash()` serializes alive-cell positions as a sorted list of `row * cols + col` integers, packs them into 4-byte little-endian words, and returns the MD5 hexdigest |
| History store | `App.state_history: dict[str, int]` maps each fingerprint to the generation number when it was first recorded |
| Period calculation | `period = current_generation - state_history[hash]`; period 1 means still life |
| Detection outcomes | Extinction (population == 0), still life (period == 1), oscillator (`"Cycle detected (period N)"`) |
| Reset triggers | Clear (`c`), randomize (`r`), cell toggle (`e`), draw/erase mode paint, pattern load, save load, and resuming play after a detection |
| Initial seed | The starting grid state is inserted into `state_history` at `run()` startup to correctly measure period-1 still lifes from the very first step |

**Interactive controls:** `Space` (resume play after detection — also clears history to allow fresh observation); `n` / `.` (manual step also participates in detection)

### Added: Population Sparkline Display — live Unicode mini-chart of population history above the status bar

A sparkline is a word-sized chart stripped of axes and labels — pure signal. This adds a row of Unicode block characters (`▁▂▃▄▅▆▇█`) directly in the terminal one line above the status bar. Each character represents the population at one past generation, auto-scaled so the minimum maps to `▁` and the maximum to `█`. The result turns the status bar area into a live oscilloscope: oscillators produce regular sawtooth waves, glider guns show a rising staircase punctuated by periodic drops, and chaotic patterns like the R-pentomino or acorn display an unmistakable explosion-then-settle shape. The sparkline width adapts to the terminal width dynamically, and history resets whenever the grid is fundamentally changed.

**Changed file:** `life.py` (~700 lines after this commit, +40 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Character set | `SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"` — 8 Unicode block elements (U+2581–U+2588) |
| Scaling | `idx = int((v − lo) / (hi − lo) * 7)` — linear map from population value to character index; range clamped to 1 when `hi == lo` to avoid division by zero |
| Width adaptation | `spark_width = max_x − 16` — reserves 14 characters for the `" Pop history: "` label; sparkline fills the rest of the terminal row |
| History window | `sparkline()` slices `values[-width:]` — only the most recent `spark_width` generations are shown, so the chart scrolls as the simulation advances |
| History tracking | `App.pop_history: list[int]` — appended via `_record_pop()` on simulation start, on every auto-advance step, and on every manual `n`/`.` step |
| History reset | `pop_history.clear()` + immediate `_record_pop()` triggered by: `c` (clear), `r` (randomize), pattern load from menu, and save-file load — so the chart always reflects the current continuous run |
| Viewport adjustment | `vis_rows` reduced from `max_y − 3` to `max_y − 4` to give the sparkline row its own screen line above the status bar |

**Also changed:**
- New module-level constant `SPARKLINE_CHARS`
- New module-level function `sparkline(values, width) -> str`
- New `App._record_pop()` helper method

### Added: Save/Load Feature — persist and restore grid states across sessions

Until now, any pattern built or evolved in the simulator was lost on exit. This commit adds a full save/load system so users can bookmark interesting configurations — mid-run methuselahs, hand-drawn patterns, stable configurations worth returning to — and reload them in a later session. Saves are plain JSON files stored in `~/.life_saves/`, human-readable and easy to copy or share. The serialization captures not just which cells are alive but also each cell's age (generation count since birth), so color tinting and behavioral context are preserved exactly on reload.

**Changed file:** `life.py` (~660 lines after this commit, +110 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Serialization format | JSON via `json.dump` / `json.load`; file schema: `{rows, cols, generation, cells: [[r, c, age], …], name}` |
| Storage location | `SAVE_DIR = os.path.expanduser("~/.life_saves")`; directory created with `os.makedirs(..., exist_ok=True)` on first save |
| Filename sanitization | Characters that are not alphanumeric, `-`, or `_` are replaced with `_` to produce safe filenames |
| Deserialization | `Grid.load_dict(data)` rebuilds `self.cells` from the sparse alive-cell list, recounting `self.population` in the process |
| Text input | `App._prompt_text()` switches curses to blocking mode (`nodelay(False)`), reads characters one at a time with backspace support, and returns the string on Enter or `None` on ESC |
| Load menu | Scans `~/.life_saves/*.json`, renders a scrollable highlighted list in the same visual style as the pattern selector; navigation via arrows or vim keys; corrupt files caught with `json.JSONDecodeError / KeyError / TypeError` |

**New keybindings:**

- `s` — open a text prompt on the bottom line; type a name and press Enter to save the current grid state to `~/.life_saves/<name>.json`; ESC cancels
- `o` — open an interactive load menu listing all saves in `~/.life_saves/`; arrow/vim navigation; Enter restores the selected state and pauses playback; ESC or `q` cancels

**Also changed:**
- Hint bar updated: `[s]=save [o]=load` added to the key reference line
- Help screen overlay updated with `s` (save) and `o` (open/load) entries
- New imports: `json`, `os`

### Added: Terminal-Based Conway's Game of Life Simulator — curses TUI with patterns, age-tinted cells & full interactivity

Conway's Game of Life needs no introduction, but this implementation goes well beyond a bare grid. Written as a single self-contained Python file with no external dependencies, it uses the standard-library `curses` module to render a live, color-tinted simulation directly in the terminal. Cells age visually across five color tiers — newborn cells glow green, then pass through cyan, yellow, and magenta before settling into red for the oldest survivors — giving an at-a-glance sense of stability and churn. The grid is toroidal (edges wrap), and the viewport automatically recenters on the cursor so the action stays in view. Thirteen classic patterns are built in and selectable from an interactive menu, and the simulator ships with CLI flags for headless scripting or quick demos.

**New file:** `life.py` (~550 lines)

**Core mechanics:**

| Concept | Implementation |
|---------|----------------|
| Evolution rule | Standard B3/S23: dead cells with exactly 3 live neighbours are born; live cells with 2 or 3 live neighbours survive; all others die |
| Cell age | `Grid.cells[r][c]` stores an integer: `0` = dead, `>0` = alive age in generations; incremented each step via `cells[r][c] + 1` |
| Neighbour counting | 8-neighbourhood loop over `dr, dc ∈ {-1,0,1}` with modular wrapping for toroidal boundary: `(r + dr) % rows` |
| Simulation speed | 8 discrete steps: 2.0 s → 1.0 → 0.5 → 0.25 → 0.1 → 0.05 → 0.02 → 0.01 s (0.5× to 100×); stored as `SPEEDS` index |
| Viewport | Recomputed every frame: `view_r = cursor_r − vis_rows // 2` — keeps cursor centred; cells rendered at `sx * 2` columns to approximate square aspect ratio using `██` (U+2588) |
| Age-to-color mapping | 5 tiers via `color_for_age()`: age ≤ 1 → green (pair 1), ≤ 3 → cyan (2), ≤ 8 → yellow (3), ≤ 20 → magenta (4), >20 → red (5) |

**13 presets:**

| Preset | Description |
|--------|-------------|
| `glider` | Small pattern that moves diagonally across the grid |
| `blinker` | Period-2 oscillator — 3 cells flip between horizontal and vertical |
| `toad` | Period-2 oscillator — two offset rows of 3 |
| `beacon` | Period-2 oscillator — two touching 2×2 blocks |
| `pulsar` | Period-3 oscillator — large 13×13 symmetric pattern |
| `pentadecathlon` | Period-15 oscillator — the longest-period common oscillator |
| `lwss` | Lightweight spaceship — travels horizontally |
| `glider_gun` | Gosper glider gun — 36-cell pattern that emits an endless stream of gliders |
| `r_pentomino` | 5-cell seed that churns chaotically and stabilises after 1,103 generations |
| `diehard` | 7-cell methuselah that vanishes completely after exactly 130 generations |
| `acorn` | 7-cell seed that takes 5,206 generations to stabilise |
| `block` | 2×2 still life — the simplest stable pattern |
| `beehive` | 6-cell still life in hexagonal arrangement |

**Interactive controls:**

- `Space` — toggle play/pause auto-advance
- `n` / `.` — step forward one generation (pauses if playing)
- `+` / `=` — increase simulation speed
- `-` / `_` — decrease simulation speed
- Arrow keys / `hjkl` — move cursor around the grid
- `e` — toggle the cell under the cursor alive/dead
- `p` — open the pattern selector menu (arrow/vim navigation, Enter to load)
- `r` — fill the grid randomly (~20% density)
- `c` — clear the entire grid and reset generation counter
- `?` / `h` — open the help screen overlay (any key to close)
- `q` — quit

**CLI flags:**

| Flag | Default | Purpose |
|------|---------|---------|
| `-p` / `--pattern` | none | Start with a named preset centered on the grid |
| `--rows` | 80 | Grid height in cells |
| `--cols` | 120 | Grid width in cells |
| `--list-patterns` | — | Print all preset names and descriptions, then exit |

### Initial Commit

Empty initial project commit.
