# Changelog

All notable changes to this project are documented in this file.

## 2026-03-15

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

### Added: ASCII Aquarium / Fish Tank (Ctrl+Shift+Y)

A relaxing, screensaver-style "zen mode" — the project's first purely ambient simulation.

**What it does:**
- 8 fish species with unique ASCII sprites (Minnow, Guppy, Tetra, Angelfish, Clownfish, Pufferfish, Swordfish, Whale), each with distinct size, speed, and directional art
- 4 presets: Tropical Reef, Deep Ocean, Koi Pond, Goldfish Bowl
- Procedural environment: swaying seaweed, rising bubble streams, surface light ripples, caustic light patterns, sandy bottom with height variation
- Interactive: feed fish (`f`), tap glass to startle (`t`), add/remove fish (`a`/`d`), add bubble streams (`b`), adjust speed (`+`/`-`), toggle info (`i`), pause (`Space`)

**Why:** The project had 60+ modes covering physics, biology, fractals, and chaos — but nothing purely ambient or meditative. This fills the "zen mode" gap.

**Category:** Audio & Visual (~560 lines added to life.py)

## Previous additions (selected)

| Date | Mode | Key |
|------|------|-----|
| — | ASCII Aquarium / Fish Tank | Ctrl+Shift+Y |
| — | Kaleidoscope / Symmetry Patterns | Ctrl+Shift+V |
| — | Ant Farm Simulation | — |
| — | Matrix Digital Rain | — |
| — | Maze Solving Algorithm Visualizer | — |
| — | Lissajous Curve / Harmonograph | — |
| — | Fluid Rope / Honey Coiling | — |
| — | Snowfall & Blizzard | — |
| — | Fourier Epicycle Drawing | — |
| — | DNA Helix & Genetic Algorithm | — |
| — | Sorting Algorithm Visualizer | — |
