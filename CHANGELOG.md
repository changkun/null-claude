# Changelog

All notable changes to this project are documented in this file.

## 2026-03-15

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
