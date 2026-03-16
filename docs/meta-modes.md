# Meta Modes

Tools for exploring, combining, evolving, and recording simulations — the laboratory around the laboratory.

---

## Compare Rules

**Source:** `life/modes/compare_rules.py`

### Background

Compare Rules displays two cellular automata side by side, each running a different B/S ruleset on the same initial configuration. This makes it easy to see how small rule changes produce dramatically different long-term behavior. Population sparklines beneath each panel give an at-a-glance view of growth trajectories.

### How it works

The screen is split vertically at the midpoint. Both grids share a viewport origin (scroll position), so the same spatial region is visible in each panel. The left panel uses the current active rule; the right panel uses a second rule chosen from presets or typed as a custom B/S string. Each generation, both grids step independently, and population histories are recorded into separate ring buffers rendered as Unicode sparklines.

### What to explore

- Compare Conway's Life (B3/S23) against HighLife (B36/S23) to see replicator emergence.
- Try a rule that dies quickly on the left against one that fills the grid on the right.
- Watch population sparklines diverge or converge over hundreds of generations.

---

## Multi-Rule Race

**Source:** `life/modes/race_rules.py`

### Background

Multi-Rule Race pits 2--4 cellular automata rulesets against each other in a timed competition. All grids start from identical random initial conditions and run for a configurable number of generations. A live scoreboard tracks population, peak population, oscillation period, extinction generation, and a composite score.

### How it works

Grids are arranged in a tiled layout (1x2, 2x2, or 2+1 depending on count). Each grid runs independently with its own B/S rule. The system tracks per-grid state hashes for cycle detection. When the race duration expires or all but one rule go extinct, the race ends. Final scores combine population, peak, and longevity metrics. A progress bar shows elapsed generations versus the configurable maximum (10--10,000).

### What to explore

- Race explosive rules (Seeds B2/S) against stable ones (Life B3/S23) to see who survives.
- Set a long duration (5000+ generations) to discover which rules have staying power.
- Watch for oscillation detection: the scoreboard reports periodicity when found.

---

## Puzzle / Challenge

**Source:** `life/modes/puzzle.py`

### Background

Puzzle mode presents a series of cellular automata challenges: build a still life, construct an oscillator with a minimum period, reach a target population, escape a bounding box, cause extinction, or survive for a given number of generations. Each puzzle constrains how many cells you may place.

### How it works

The mode has three phases: *planning* (place cells on a blank grid with draw/erase tools), *running* (the simulation advances while win/loss conditions are checked each step), and *result* (score displayed). Win detection uses state-hash cycle detection for still-life and oscillator puzzles, population thresholds for growth puzzles, and bounding-box geometry for escape puzzles. Scoring rewards efficiency: `score = 100 * max_cells / cells_used + speed_bonus`.

### What to explore

- The "escape box" puzzle type: your pattern must send live cells outside a dotted boundary.
- Try to beat your best score by using fewer cells. Hints are available with `?`.
- Attempt the extinction puzzles, which require building patterns that self-destruct.

---

## Evolution / GA

**Source:** `life/modes/evolution.py`

### Background

Evolution mode uses a genetic algorithm to breed Life-like rulesets. A population of candidate B/S rules runs in parallel on small grids; after a configurable number of simulation generations, each is scored on longevity, population stability, diversity, and average population. The top performers reproduce through crossover and mutation.

### How it works

```
for each generation:
    for each individual in population:
        initialize 30x40 grid with 20% random fill
        simulate for grid_gens steps
        record population history
    score all individuals (weighted sum of 4 fitness components)
    sort by fitness; keep top elite_count as parents
    breed next generation: crossover pairs of parents, mutate offspring
```

Crossover is uniform per-digit: for each neighbor count 0--8, the child inherits the birth/survival bit from a randomly chosen parent. Mutation flips individual digits with a configurable rate. Four fitness modes (balanced, longevity, diversity, population) reweight the scoring components.

### What to explore

- Set fitness to "diversity" and watch the GA discover chaotic, visually rich rules.
- Adopt a discovered rule into the main simulator with `a` to explore it at full resolution.
- Increase mutation rate to 30%+ for more exploration; decrease to 5% for refinement.

### References

- Holland, J. H. (1975). *Adaptation in Natural and Artificial Systems*. University of Michigan Press. https://doi.org/10.7551/mitpress/1090.001.0001

---

## Screensaver / Demo Reel

**Source:** `life/modes/screensaver.py`

### Background

Screensaver mode auto-cycles through all simulation modes in the system, running each for a configurable interval before transitioning to the next. It functions as an unattended demo reel that showcases the full range of available simulations.

### How it works

A playlist is built from the mode registry, filtered by category, favorites, or "all modes." The screensaver saves its own state, exits the current sub-mode, enters the next one, and attempts to auto-select a preset by simulating an Enter keypress on the mode's menu. Transitions use a dissolve effect: random block characters are drawn over the screen at decreasing density. A fade-in overlay displays the mode name and category for 3 seconds before fading out. The interval between mode switches is adjustable from 5 to 120 seconds.

### What to explore

- Use "All Modes -- Shuffle" for a randomized tour of every simulation.
- Press `i` to toggle the persistent info overlay showing mode name and countdown.
- Pause with Space to linger on an interesting simulation, then resume cycling.

---

## Parameter Space Explorer

**Source:** `life/modes/param_explorer.py`

### Background

Parameter Space Explorer displays a grid of live simulation thumbnails, each running the same model with linearly interpolated parameter values across two axes. By selecting an interesting tile and pressing Enter, you zoom into a neighborhood of that parameter combination, iteratively narrowing in on compelling regions of the parameter landscape.

### How it works

The explorer supports pluggable simulation engines. Currently implemented are Gray-Scott Reaction-Diffusion (feed vs. kill rate) and a Lenia-like smooth CA (mu vs. sigma). For an NxM tile grid, parameter values are evenly spaced across the visible range on each axis. Each tile runs its own independent mini-simulation. When the user zooms in, the visible range shrinks to 40% of the current span, centered on the selected tile's parameters. Zooming out expands by 150%. Preset bookmarks jump to known interesting parameter combinations.

### What to explore

- In Gray-Scott mode, zoom into the boundary between "spots" and "worms" around feed=0.04, kill=0.063.
- Use the `p` key to cycle through named presets (Coral Growth, Mitosis, Spirals, etc.).
- Increase steps-per-frame with `+` to accelerate convergence on slow-forming patterns.

---

## Evolution Lab

**Source:** `life/modes/evolution_lab.py`

### Background

Evolution Lab extends the basic Evolution mode with analytics-driven fitness scoring (Shannon entropy, symmetry, periodicity, stability), multi-state genomes (Moore and von Neumann neighborhoods, 2--5 cell states), manual "favorite" protection from culling, and persistent save/load of discovered organisms to disk.

### How it works

Genomes encode birth/survival sets, neighborhood type, and state count. Fitness is computed from five analytics metrics with configurable weight presets (balanced, beauty, chaos, complexity, stability). The beauty preset, for example, weights symmetry at 3x. Organisms marked as favorites are immune to culling and always appear as parents in the next generation. The breeding pipeline is: sort by fitness (favorites first), select elite parents, fill remaining slots with crossover + mutation. Organisms can be saved to `~/.life_saves/evolution_lab.json` and reloaded as seeds for future runs.

### What to explore

- Use the "beauty" fitness preset to evolve rules that produce symmetric, visually striking patterns.
- Favorite a promising organism and watch its traits propagate through subsequent generations.
- Save an organism, restart with "Start (From Saved)" to continue evolving from your best discoveries.

### References

- Mordvintsev, A. et al. (2020). "Growing Neural Cellular Automata." *Distill*. https://distill.pub/2020/growing-ca/

---

## Evolutionary Playground

**Source:** `life/modes/evo_playground.py`

### Background

Evolutionary Playground is a human-in-the-loop genetic algorithm where you are the fitness function. A grid of live simulations runs with different randomly generated CA rules. You watch them, select the most visually interesting ones as parents, and press `b` to breed the next generation through crossover and mutation.

### How it works

The population fills the terminal as a tiled grid of mini-simulations. Genomes include birth/survival sets, neighborhood type (Moore, von Neumann, or hexagonal), and multi-state cell counts. Selection is manual: navigate with arrow keys, press Enter to toggle a tile as a parent. Breeding requires at least 2 parents. Children inherit traits via uniform crossover and per-digit mutation. The mutation rate is adjustable. Discovered rules can be saved to `~/.life_saves/evolved_rules.json` or adopted directly into the main simulator.

### What to explore

- Select parents with contrasting behaviors (one chaotic, one stable) to see what crossover produces.
- Increase mutation rate to 25%+ for more novelty per generation.
- After several generations of selective breeding, adopt the best rule into the main Life grid.

---

## Live Rule Editor

**Source:** `life/modes/rule_editor.py`

### Background

Live Rule Editor provides an interactive REPL where you type Python expressions to define custom cellular automaton birth and survival rules. The expressions execute in real time on a grid, giving immediate visual feedback. Variables available include `neighbors` (list of 8 neighbor states), `age`, `x`, `y`, `step`, and `random()`.

### How it works

Birth and survival expressions are compiled with Python's `compile()` into code objects, then evaluated per-cell each generation using a restricted `eval()` sandbox (no `__builtins__`). The sandbox exposes `sum`, `len`, `min`, `max`, `any`, `all`, `abs`, `math`, and `random`. Expressions like `sum(neighbors) == 3 and age < 10` let you create age-dependent rules, positional biases, or stochastic behavior. Ten starter snippets are provided. Rules can be saved to and loaded from `~/.life_saves/custom_rules.json`.

### What to explore

- Try `sum(neighbors) == 3 or (sum(neighbors) == 2 and random() < 0.05)` for stochastic Life.
- Create position-dependent rules: `sum(neighbors) == 3 and (x + y) % 3 == 0`.
- Use the `a` key to translate your expression into a standard B/S rule and apply it to the main grid.

---

## Simulation Mashup

**Source:** `life/modes/mashup.py`

### Background

Simulation Mashup layers two different simulation engines on the same grid with emergent coupling. Each engine's density field influences the other: boids steer toward wave gradients, fire ignition probability increases near dense Life populations, Ising spin flips are biased by reaction-diffusion concentrations, and so on.

### How it works

Eight mini-simulation engines are implemented (Game of Life, Wave Equation, Reaction-Diffusion, Forest Fire, Boids, Ising Model, Rock-Paper-Scissors, Physarum). Each exposes `init`, `step(state, other_density, coupling_strength)`, and `density` functions. On each tick, simulation A receives B's density map as a coupling input and vice versa. The coupling strength (0.0--1.0) controls how strongly each simulation influences the other. Rendering overlays both density fields with color-coding: cyan for A, red for B, magenta for overlap.

### What to explore

- "Boids + Wave Equation": watch flocking agents create ripples and steer along wave gradients.
- Adjust coupling with `+`/`-` to find the sweet spot between independence and lock-in.
- Set coupling to 0 with `0` to see both simulations run independently for comparison.

---

## Battle Royale

**Source:** `life/modes/battle_royale.py`

### Background

Battle Royale places four cellular automata factions on a shared grid, each starting in a corner with its own B/S rule. Factions compete for territory through birth, survival, and conquest mechanics. The last faction standing wins.

### How it works

The grid tracks per-cell ownership (faction index or neutral) and age. Each generation: empty cells check which factions could birth there using their respective birth sets, with the highest neighbor count winning ties. Alive cells check survival using their faction's survival set. A conquest mechanic triggers when enemy neighbor density exceeds own-faction density by more than 1 and the dominant enemy has 3+ neighbors. Territory percentages are displayed in a live scoreboard with a stacked bar chart. Eight factions are available, color-coded in 256-color mode.

### What to explore

- "Classic Showdown" pits Life, HighLife, Day&Night, and Seeds in a four-way battle.
- Watch Seeds (B2/S) explode quickly but burn out, while Life slowly consolidates territory.
- Try "Custom Battle" to pick any 4 of the 8 available factions.

---

## Simulation Portal

**Source:** `life/modes/portal.py`

### Background

Simulation Portal splits the screen into two halves (vertically or horizontally), each running a different simulation engine. A visible seam connects them: density information bleeds across the boundary with a configurable depth, creating emergent cross-talk where one simulation feeds energy into the other at the interface.

### How it works

Boundary influence is computed by extracting the edge columns (or rows) of one simulation's density field, attenuating linearly with distance from the seam, and injecting them into the other simulation's coupling input. The "bleed" parameter (1--20 cells) controls how deep the cross-talk extends. Two influence builders handle the directionality: A's right edge maps to B's left edge, and B's left edge maps to A's right edge (with a flip function). Near-seam cells are rendered in magenta to visualize the cross-talk zone.

### What to explore

- Toggle orientation with `o` to see how vertical vs. horizontal seams change the interaction.
- Increase bleed depth with `b` to let the simulations influence each other more deeply.
- Try "Wave + Forest Fire": wave amplitude ignites fire at the boundary.

---

## Split-Screen Dual Simulation

**Source:** `life/modes/split_screen.py`

### Background

Split-Screen Dual Simulation runs any two of the eight mini-simulation engines side by side with optional bidirectional coupling. Each pane has its own state, generation counter, and density grid. Unlike Observatory (which tiles 2–9 viewports with no coupling) or Mashup (which couples two engines on the same grid), Split-Screen offers a spectrum from clean uncoupled comparison to full cross-domain emergence — a fluid simulation's density can drive a cellular automaton's birth threshold, a particle swarm's positions can seed a reaction-diffusion pattern, or an Ising model's magnetization can modulate a wave equation's damping.

### How it works

The terminal is divided vertically at the midpoint. A single-character `│` divider separates the panes. Each pane wraps one of the eight engines from the mashup module (Game of Life, Wave, Reaction-Diffusion, Forest Fire, Boids, Ising, Rock-Paper-Scissors, Physarum) via the shared `_ENGINES` registry, reusing `init`, `step`, and `density` functions.

Coupling is controlled by a `split_coupling` parameter (0.0–1.0). At 0.0 the panes are fully independent. At higher values, each simulation receives the *other* pane's density map as input before stepping (Jacobi-style: both densities are snapshotted before either steps, so neither has temporal priority). All eight engines already accept `(state, other_density, coupling_strength)` in their step functions — Split-Screen simply wires the cross-pane density exchange. When coupling is active, the vertical divider shows a `⇄` bidirectional arrow at its center, and the title bar displays the current coupling percentage.

A preset menu offers 8 curated pairings (e.g., "Game of Life vs Lenia-style RD", "Boids vs Physarum") for quick launch, plus a two-step custom picker that lets you choose any left and right engine independently. Focus state (`split_focus`) determines which pane's title bar is highlighted with a reverse-video diamond marker; Tab swaps focus. The `r` key resets only the focused pane, reinitializing its engine state and zeroing its generation counter while the other pane continues undisturbed.

### What to explore

- Compare "Game of Life vs Boids" to see grid-based discrete dynamics next to free-roaming agent behavior.
- Use `s` to swap panes and see how visual placement affects your perception of the two simulations.
- Reset one pane with `r` while the other runs to compare fresh vs. evolved states of the same engine.
- Use the custom picker to pair any two engines — try "Ising vs Rock-Paper-Scissors" for two spatial competition models.
- Press `c` to cycle coupling (0% → 20% → 50% → 80% → 100% → off) and watch cross-domain patterns emerge — a Wave/Ising pairing at 50% coupling produces magnetization waves that don't exist in either simulation alone.
- Fine-tune coupling with `+`/`-` (5% increments) to find the critical threshold where one simulation begins to entrain the other.
- Try "Reaction-Diffusion vs Physarum" with high coupling — the RD spots become food sources for the slime mold network.

---

## Simulation Observatory

**Source:** `life/modes/observatory.py`

### Background

Simulation Observatory runs 2--9 independent simulations simultaneously in a tiled split-screen layout. Unlike Mashup, there is no coupling between viewports. The focus is on visual comparison: press a number key to expand any viewport to full screen, then press `0` to return to the grid view.

### How it works

Viewports are arranged in auto-calculated grid layouts (1x2, 2x2, 2x3, or 3x3) based on the number of simulations selected. Each viewport wraps one of the eight mini-simulation engines from the mashup module. All viewports step in lockstep each frame. The focus mechanism simply switches between the tiled draw function and a full-screen draw function for the selected viewport index.

### What to explore

- The "Everything" preset runs all 8 engines at once in a 3x3 grid.
- Focus on the Physarum viewport (`8`) to see trail networks form at full resolution.
- Compare fluid-like simulations (Wave, RD, Physarum) side by side in the "Fluid Trio" preset.

---

## Layer Compositing

**Source:** `life/modes/layer_compositing.py`

### Background

Layer Compositing stacks 2--4 independent simulations as transparent layers with configurable blend modes (add, XOR, mask, multiply, screen) and per-layer opacity and tick rate. The result is a single composited viewport where multiple simulation dynamics interweave visually.

### How it works

Each layer wraps an independent simulation engine. On each frame, layers whose `generation % tick_mult == 0` are stepped. The compositing engine iterates over every cell, applying blend functions sequentially from the base layer upward:

```
for each cell (r, c):
    val = layer[0].density * layer[0].opacity
    for layer in layers[1:]:
        val = blend_fn(val, layer.density * layer.opacity)
    dominant_layer = argmax(layer_contributions)
```

The dominant layer determines the cell's display color. Blend modes include `screen` (inverse multiply, good for lightening) and `mask` (layer A visible only where layer B exceeds a threshold).

### What to explore

- "Breathing Shapes": Reaction-Diffusion masked by Game of Life creates pulsing organic forms.
- Use Tab to cycle focus between layers, then `+`/`-` to adjust opacity in real time.
- Press `b` to cycle blend modes on the focused layer and see the visual effect immediately.

---

## Cinematic Demo Reel

**Source:** `life/modes/cinematic_demo.py`

### Background

Cinematic Demo Reel is an autonomous director that sequences through simulation engines with smooth crossfade transitions, animated camera moves (zoom, pan), and title card overlays. It plays like a screensaver but with deliberate cinematographic intent.

### How it works

Each "act" specifies a simulation engine, duration (10--14 seconds), camera path, and color theme. Camera parameters (zoom, pan_x, pan_y) are interpolated with a smooth ease-in-out function: `t = t^2 * (3 - 2t)`. The view window maps screen coordinates to a subregion of the simulation grid based on the current zoom and pan. Crossfade transitions blend the previous act's density field with the new one over 1.5 seconds. Title cards display the act name for 3 seconds with a 1-second fade-out. Five curated playlists are provided, including a "Random Director" mode that shuffles acts.

### What to explore

- "The Grand Tour" visits all 8 engines in sequence with varied camera paths.
- "Fluid Dreams" focuses on Wave, Reaction-Diffusion, and Physarum for a meditative experience.
- Press `n`/`p` to skip forward or backward through acts manually.

---

## Topology Mode

**Source:** `life/modes/topology.py`

### Background

Topology Mode changes the grid's boundary conditions, transforming the surface on which any simulation runs. Five topologies are supported: plane (hard edges), torus (both axes wrap), Klein bottle (rows wrap with horizontal flip), Mobius strip (columns wrap with vertical flip), and projective plane (both axes wrap with flips).

### How it works

The Grid class implements neighbor lookups that consult the `topology` attribute. For twist-wrapping topologies, when a coordinate wraps past an edge, the opposite axis is mirrored: on a Klein bottle, a cell going off the top row reappears at the bottom with its column reflected (`c' = cols - 1 - c`). The topology mode draws visual edge indicators: thin lines for walls, double lines for seamless wraps, and wavy lines with arrow glyphs for twist wraps. Corner markers and midpoint arrows communicate the surface's non-orientable nature.

### What to explore

- Run a glider on a Mobius strip (Ctrl+W to cycle topology) and watch it return mirror-reversed.
- Compare pattern evolution on torus vs. Klein bottle: the flip creates asymmetric interference.
- Try the projective plane with a symmetric initial pattern to see how double-twist affects symmetry.

---

## Visual FX Pipeline

**Source:** `life/modes/post_processing.py`

### Background

The Visual FX Pipeline provides six stackable post-processing effects (scanlines, bloom, motion trails, edge detection, color cycling, CRT distortion) that layer on top of any active simulation mode. Effects compose freely and operate entirely in terminal character space.

### How it works

Effects are applied after the simulation's draw call, operating directly on the curses screen buffer via `inch()` and `chgat()`. Scanlines dim every other row. Bloom makes occupied cells bold and paints dim glow characters in adjacent empty cells. Trails maintain a ring buffer of past frame occupancy maps; older frames are rendered with progressively lighter block characters. Edge detection builds an occupancy bitmap and erases interior cells (those with all four cardinal neighbors occupied). Color cycling rotates color pair indices modulo 5 based on a frame counter. CRT adds vignette darkening, scanlines, and a rounded bezel border.

### What to explore

- Enable bloom + trails together for a neon glow effect on any simulation.
- Edge detection transforms dense patterns into outline-only contour maps.
- CRT distortion makes any simulation look like it is running on a vintage monitor.

---

## Recording & Export

**Source:** `life/modes/recording.py`

### Background

Recording & Export captures terminal frames during any simulation and exports them as asciinema v2 `.cast` files (playable in any terminal or embeddable on the web) or plain-text flipbooks. It operates as a background capture system toggled with Ctrl+X.

### How it works

When recording is active, each frame the system reads every cell of the curses window via `inch()`, groups runs of identical attributes, and emits ANSI escape sequences for color and style changes. A parallel plain-text capture strips all ANSI codes. Frame capture respects an FPS budget (default 10 fps) and a safety cap of 3000 frames. The `.cast` exporter writes asciinema v2 format: a JSON header line followed by `[elapsed, "o", data]` event lines. A blinking red REC indicator is drawn in the top-right corner during recording.

### What to explore

- Record a Battle Royale match and play it back with `asciinema play recording.cast`.
- Export as both formats simultaneously to get a web-embeddable `.cast` and a searchable `.txt`.
- Recordings are saved to `~/.life_saves/` with timestamped filenames.

---

## Scripting & Choreography

**Source:** `life/modes/scripting.py`

### Background

Scripting & Choreography provides a line-based DSL (`.show` files) for orchestrating timed sequences of mode transitions, parameter sweeps, visual effect toggles, speed changes, and labels. Think of it as a programmable director for the entire simulation platform.

### How it works

The DSL parser tokenizes each line into commands: `mode`, `wait`, `effect`, `topology`, `set`, `sweep`, `transition`, `speed`, `color`, `label`, and `loop`. The execution engine maintains a program counter and processes commands sequentially until it hits a blocking command (`wait` or `sweep`). Sweeps interpolate parameters over time using smooth ease-in-out curves. Crossfade transitions blend the previous simulation's density field with the new one. The `loop` command resets the program counter to zero. Five built-in example scripts are included. Users can also load `.show` files from disk.

### What to explore

- Run "Full Tour" for a scripted presentation of all 8 engines with effects and transitions.
- Write your own `.show` file to create a custom demo with precise timing and parameter control.
- Press `s` during playback to view the script source with the current instruction highlighted.

---

## Neural Cellular Automata

**Source:** `life/modes/neural_ca.py`

### Background

Neural Cellular Automata replaces lookup-table rules with per-cell neural networks. Each cell perceives its neighborhood through Sobel-like convolution kernels, processes the signal through a two-layer neural network (perception to hidden via ReLU, hidden to state update via residual connection), and updates its multi-channel state. The network weights are trained via Evolution Strategies to reproduce a target pattern from a small seed.

### How it works

```
perception = [identity, sobel_x, sobel_y] * 3 channels = 9 inputs
hidden = ReLU(W1 @ perception + b1)        # 8 neurons
update = W2 @ hidden + b2                   # 3 channels
new_state = old_state + update              # residual
alive_mask: cell dies if no neighbor has alpha > 0.1
```

Training uses antithetic Evolution Strategies: generate N/2 random perturbations (and their negatives), grow each candidate from seed for 30 steps, compute MSE loss against the target, and estimate a gradient for weight update. The system has 107 learnable parameters. Users can draw custom target patterns or select from presets (circle, square, diamond, cross, ring, heart).

### What to explore

- Train on the "heart" target and watch the seed grow into a heart shape over 50+ training generations.
- Press `g` to regrow from seed with current weights to test robustness.
- Draw a custom target with `d`, then train -- the NCA will learn to approximate any binary shape.

### References

- Mordvintsev, A. et al. (2020). "Growing Neural Cellular Automata." *Distill*. https://distill.pub/2020/growing-ca/

---

## Timeline Branching

**Source:** `life/modes/timeline_branch.py`

### Background

Timeline Branching lets you fork alternate realities from any point in a simulation's history. Scrub back through the timeline, fork the grid state into a branch (optionally with a different rule), and watch both the original and branched timelines evolve side by side in a split view with a real-time divergence metric.

### How it works

Forking deep-copies the primary grid (cells, rules, topology) into a secondary grid. Both grids advance in lockstep from the fork point. The split view renders them side by side with dual sparklines and a divergence bar that computes the fraction of cells differing between the two grids: `divergence = count(cell_a != cell_b) / total_cells * 100%`. The fork menu offers two options: "Fork with same rules" (to study sensitivity to initial conditions) or "Fork with different rule" (to compare rule behavior from identical starting states). The fork-point generation and rule labels are displayed in a status bar.

### What to explore

- Fork from a complex state and apply a different rule to the branch to see how quickly they diverge.
- Fork with the same rule to demonstrate sensitivity to initial conditions (chaos in CA dynamics).
- Use the divergence percentage to quantify how "far apart" two timelines have drifted.

---

## Ancestor Search

**Source:** `life/modes/ancestor_search.py`

### Background

Ancestor Search reverse-engineers cellular automata: given a target pattern, it searches backwards in time to find predecessor states that evolve into the target after one CA step. It can also detect Garden of Eden patterns -- configurations with no possible predecessor under the current rule.

### How it works

The search engine uses simulated annealing with stochastic restarts. Candidates are flat binary grids. Fitness is the count of cells matching the target after one forward CA step (perfect = all cells match). Each generation applies adaptive-rate mutations and occasional crossover with the global best. Simulated annealing acceptance allows uphill moves with probability `exp(delta / temperature)`, where temperature cools by 0.3% per generation. After 200 restarts with no perfect solution, an exhaustive local search (500 multi-flip attempts) runs to confirm Garden of Eden status. The three-panel display shows the target, the best candidate ancestor, and either a confirmed solution or the evolved-best for comparison.

### What to explore

- Search for ancestors of the "glider" pattern: multiple valid predecessors exist.
- Try the "r-pentomino" (a methuselah): finding its ancestors reveals the complexity of backward search.
- Draw a custom pattern and check whether it is a Garden of Eden -- a state that can never arise naturally.

---

## Self-Modifying Rules CA

**Source:** `life/modes/self_modifying_rules.py`

### Background

Self-Modifying Rules creates a cellular automaton where each living cell carries its own rule DNA encoded as a pair of 9-bit genomes (birth and survival bitstrings). When a cell is born, it inherits a possibly mutated rule from the majority of its live neighbors. This produces emergent speciation, ecological niches, and evolutionary arms races without any external fitness function.

### How it works

Each cell's genome is a `(birth_bits, survival_bits)` pair. Alive cells check survival using their own genome's survival set. Dead cells check birth using the majority genome among their live neighbors' birth sets. Newborn cells inherit the majority genome with a per-event mutation probability; mutation flips random bits in the 9-bit birth and survival bitstrings. Species are identified by unique genomes and color-coded via a hash function into 8 distinct terminal colors. The info panel tracks species count, births, deaths, total mutations, and displays sparklines for diversity and population over time. Eight presets are provided, ranging from "Life vs HighLife" (two-species competition) to "Cambrian Explosion" (8 random seed species) to "Blank Canvas" (every cell gets a random genome).

### What to explore

- "Mutation Storm" starts with a single Life rule but high mutation creates rapid speciation -- watch dozens of species emerge.
- Adjust mutation rate with `+`/`-` in real time: low rates produce stable ecosystems, high rates produce constant turnover.
- The species panel shows which B/S rules are currently winning the ecological competition.

---

## Long-Exposure Photography

**Source:** `life/modes/long_exposure.py`

### Background

Long-Exposure Photography composites hundreds of simulation frames into a single artistic still image, like astrophotography for cellular automata. Where Ghost Trail shows fading echoes of the last few frames, Long Exposure accumulates an entire time window (10–1000 generations) into a permanent composite that reveals the full trajectory, flow patterns, and density structure of any simulation.

### How it works

When capture is active, every rendered frame is accumulated into a per-pixel buffer that tracks seven values: total R/G/B (for additive and average blending), hit count (how many frames occupied this pixel), and peak R/G/B (for max blending). The system captures from both the truecolor buffer (`tc_buf`) and the curses screen, so it works with all 130+ modes regardless of their rendering path.

When the exposure window is reached (or the user manually freezes), the accumulation buffer is composited into a final image using one of three blend modes:

- **Additive**: base color is the per-pixel average, scaled by a density factor (0.3 + 0.7 × density) with a luminance boost (up to +80 RGB) for high-traffic areas. This creates glowing trails where activity was concentrated.
- **Max**: each pixel shows the brightest color it ever displayed during the exposure. Good for capturing peak moments and transient flashes.
- **Average**: simple arithmetic mean of all frames. Reveals the steady-state palette and suppresses transient noise.

The frozen composite renders as a full-screen truecolor image using density-mapped glyphs (`· ░ ▒ ▓ █`), creating a topographic density map where glyph weight corresponds to how frequently each pixel was active. Very low-density pixels (< 1% of max) are rendered as faint dots with dimmed colors.

Export produces two files: a JSON file containing per-pixel coordinates, RGB values, and density fractions (machine-readable, suitable for further processing), and an ANSI art `.ans` file with embedded 24-bit color escapes (viewable with `cat` in any truecolor terminal).

### What to explore

- Capture a 500-frame exposure of Boids or N-Body to see orbital trajectories materialize as luminous trails.
- Use **max** blend on Reaction-Diffusion to capture the full wavefront propagation in a single image.
- Try **average** blend on a chaotic rule (Seeds, B2/S) to reveal the statistical density structure.
- Combine with Ghost Trail active for both real-time echoes and long-term accumulation simultaneously.
- Export the `.ans` file and view it in a truecolor terminal for a shareable artwork snapshot.

---

## Ghost Trail / Temporal Echo

**Source:** `life/modes/ghost_trail.py`

### Background

Ghost Trail adds a temporal echo rendering layer that overlays fading afterimages from previous frames onto any simulation mode. It makes motion visible: particles leave streaks, wavefronts show their propagation paths, cellular automata reveal their recent evolution, and flocking agents draw luminous trails. The feature enhances all 125+ modes at once without modifying any mode logic.

### How it works

Each draw cycle, the system captures a snapshot of every occupied cell on screen — both curses-rendered cells (via `inch()`) and truecolor cells (from `tc_buf`). Snapshots are stored in a ring buffer sized to `trail_depth + 1` frames.

When rendering echoes, the system iterates from the most recent past frame to the oldest. For each cell that was occupied in a past frame but is *not* occupied in the current frame (and hasn't been claimed by a newer echo), a dimmed truecolor glyph is emitted into `tc_buf`. Echo glyphs progress from dense to sparse with age: `▓ → ▒ → ░ → ·`.

Color dimming is RGB-aware: truecolor cells decay their original RGB values by the decay factor; curses-only cells derive a base color from the active colormap. Two decay curves are available:
- **Exponential** (default): `factor = 0.65^age` — rapid falloff, sharp trails
- **Linear**: `factor = 1 - age/(depth+1)` — even fade, longer visible tails

The entire pipeline hooks into `_tc_refresh()`, running once per draw cycle before the truecolor buffer is rendered to the terminal.

### What to explore

- Toggle ghost trail on Boids or N-Body to see orbital paths and flocking trajectories materialize.
- Use exponential decay on Physarum to highlight active growth fronts while old trails vanish quickly.
- Switch to linear decay on slow simulations (Ising, Lenia) for a smoother, longer-lasting echo effect.
- Increase trail depth to 15–20 frames on fast-moving simulations for dramatic light-painting effects.
- Combine with the Visual FX Pipeline (bloom + ghost trail) for neon afterglow aesthetics.

---

## Parameter Tuner

**Source:** `life/modes/param_tuner.py`

### Background

Parameter Tuner adds a real-time HUD overlay for interactively adjusting any simulation mode's constants while it runs. Instead of restarting a mode with different parameters, you press `P` to open a translucent panel listing the active mode's tunable values — diffusion rates, gravity constants, coupling strengths, temperatures, thresholds — and tweak them live with immediate visual feedback.

### How it works

The system has two layers. First, an explicit parameter registry (`TUNABLE_PARAMS`) defines curated min/max/step/format metadata for 33 modes covering ~100 individual parameters: Boids (7 params for separation/alignment/cohesion radii and weights), Physarum (sensor angle, distance, turn/move speed, deposit, decay), Reaction-Diffusion (feed/kill rates, diffusion coefficients), Ising (temperature, external field), N-Body (gravity, timestep, softening), and many more.

Second, an auto-detection fallback scans any mode's `self.{prefix}_*` attributes for numeric values, filters out structural/internal attributes via a suffix blocklist, and generates reasonable ranges and step sizes based on magnitude. This means all 132 modes can benefit from the tuner even without explicit definitions.

The HUD draws on the right side of the screen with:
- Parameter names with current formatted values
- Visual progress bars showing position within the valid range
- Scroll support for modes with many parameters
- Footer with control hints

Key handling intercepts arrow keys and vim-style navigation only when the tuner is active; all other keys pass through to the simulation, which keeps running underneath.

### What to explore

- Open Boids and crank Separation Weight to 5x while watching the flock explode apart, then drop it to 0.1 and watch them collide.
- In Reaction-Diffusion, sweep the feed rate from 0.02 to 0.06 to watch the pattern transition from spots to worms to spirals to chaos.
- Use `[`/`]` for 10x step adjustments to quickly sweep across a parameter's full range.
- Try the auto-detected parameters on modes without explicit definitions — the tuner discovers numeric attributes automatically.

---

## Auto-Discovery

**Source:** `life/modes/auto_discovery.py`

### Background

Auto-Discovery is an autonomous pattern exploration engine that searches the vast cellular automaton rule space for visually striking emergent behavior without human intervention. Where Evolution Lab requires manual fitness preset selection and Evolutionary Playground relies on human-in-the-loop selection, Auto-Discovery is fully autonomous: it generates, simulates, scores, curates, and breeds candidate configurations in a continuous loop, building a gallery of the most interesting patterns it finds.

### How it works

The engine operates in a generate-evaluate-breed cycle:

1. **Generate**: A batch of candidate configurations is created, each with a randomized B/S ruleset, neighborhood type (Moore or von Neumann), and one of six initial condition styles (random, symmetric, clustered, sparse, striped, central). The batch is displayed as a tiled grid of live mini-simulations.

2. **Evaluate**: Each candidate runs for a configurable number of steps (default 150) and is scored on five visual complexity metrics:
   - **Entropy** — Shannon entropy of the cell density grid, measuring structural complexity
   - **Symmetry** — horizontal, vertical, and rotational symmetry detection, measuring emergent order
   - **Stability** — coefficient of variation of the population time series, rewarding the sweet spot between static and chaotic
   - **Periodicity** — state hash cycle detection, rewarding oscillating patterns
   - **Longevity** — sustained activity without extinction or grid saturation

3. **Curate**: Candidates exceeding a configurable score threshold are added to a persistent gallery (with deduplication). The gallery is sorted by composite score and bounded to a maximum size.

4. **Breed**: The next batch is produced through crossover and mutation from gallery entries and current top performers, continuously exploring the neighborhood of known-good configurations.

The gallery browser provides a sortable list view with preview thumbnails, the ability to adopt any discovered rule into the main simulation grid, and save/load to disk (`~/.life_saves/auto_discovery_gallery.json`).

### What to explore

- Let it run unattended for several rounds — the gallery accumulates increasingly refined patterns as breeding favors high-scoring configurations.
- Press `g` to browse the gallery, then Enter to adopt a discovered rule into the main Life grid at full resolution.
- Adjust mutation rate to balance exploration (high mutation, more novelty) vs. exploitation (low mutation, refinement of known good rules).
- Save the gallery with `W` and reload it later to continue evolving from your best discoveries.
- Compare with Evolution Lab: Auto-Discovery explores a broader space (varied seed styles, autonomous curation) while Evolution Lab offers more manual control over fitness weights.

---

## Mode Morph Transitions

**Source:** `life/modes/morph_transition.py`

### Background

Mode Morph Transitions replaces the hard cut between simulation modes with a smooth crossfade. When you switch modes (manually or via screensaver auto-cycling), the outgoing mode's final frame is captured and faded out over a configurable number of frames while the new mode fades in underneath. This turns mode-switching into a visually seamless experience, especially effective during demo-reel playback through all 130+ modes.

### How it works

The transition engine hooks into two points in the main loop pipeline:

1. **Capture** (`_morph_on_mode_exit`): Just before `_exit_current_modes` clears the old mode, the system snapshots every occupied cell on screen — both truecolor RGB cells from `tc_buf` and curses character cells via `inch()`. The snapshot is stored as a dictionary mapping `(y, x)` positions to `(char, r, g, b)` tuples.

2. **Blend** (`_morph_on_refresh`): After `_tc_refresh` renders the new mode's frame, the transition engine overlays the captured old frame with decreasing opacity. For truecolor cells, RGB values are scaled by `alpha_old = 1 - easing(progress/duration)`. For curses-only cells, a grey value is derived from the alpha. Cells where the new mode already has content are skipped, so new content always takes visual priority. Output is emitted as raw ANSI 24-bit color escapes directly to stdout.

Three easing curves control the fade profile:
- **Linear**: constant fade rate
- **Smooth**: cubic smooth-step `t²(3 - 2t)` for a natural feel (default)
- **Ease-in-out**: quintic `16t⁵` / `1 - 16(1-t)⁵` for dramatic slow-start-slow-end

Duration is configurable from 10 to 120 frames (default 45, roughly 1.5 seconds at 30 fps). The feature requires zero changes to any individual mode file — it operates entirely through the app-level dispatch and refresh hooks.

### What to explore

- Toggle morph transitions on with `G` (Shift+G), then switch between modes to see the crossfade in action.
- Use `[` / `]` to shorten or lengthen the transition duration — short (10 frames) feels snappy, long (90+ frames) feels dreamlike.
- Cycle easing curves with `Ctrl+T` to compare linear (mechanical), smooth (natural), and ease-in-out (cinematic) fade profiles.
- Enable morph transitions alongside the screensaver/demo-reel mode for an unattended visual showcase with seamless mode changes.

---

## Rule Mutation Engine

**Source:** `life/modes/rule_mutation.py`

### Background

Rule Mutation Engine turns the simulator from a tool you explore manually into one that explores *itself*. It runs a live genetic algorithm on cellular automaton birth/survival rulesets, continuously mutating rules each generation and keeping mutations that increase Shannon entropy and spatial complexity. The user watches as the simulation autonomously discovers its most visually complex behaviors, with a lineage sidebar showing the ancestry of the current rule.

Where Auto-Discovery evaluates batches of candidates offline in a tiled grid, Rule Mutation Engine operates on a single live simulation — you see the mutation happen in real time as rules shift, populations fluctuate, and the fitness score climbs. It is a "genetic algorithm for interestingness" running directly on screen.

### How it works

The engine operates in a two-phase cycle:

1. **Stable phase** (40 generations): The current rule runs undisturbed. Shannon entropy, population, periodicity, and symmetry metrics are collected every 2 steps. At the end of the window, a composite fitness score is computed and the full grid state is saved as a revert checkpoint.

2. **Evaluation phase** (40 generations): A candidate rule is produced by randomly flipping digits in the birth/survival sets at the configured mutation rate. The candidate rule is applied to the live grid and evaluated for another 40 steps. At the end:
   - **Accept** if the candidate's fitness meets or exceeds the current fitness (within a −0.02 margin), plus a 5% random acceptance chance for exploration (simulated annealing).
   - **Hard reject** if the grid goes extinct (population = 0) or saturates (>85% alive). On extinction, the grid is reverted from the saved checkpoint and re-seeded if needed.
   - **Soft reject** if fitness dropped and the static periodicity detector shows a frozen or short-cycle pattern.

**Fitness function** — a weighted composite of four signals:
- **Shannon entropy** (×40): the dominant factor, measuring structural diversity in the density field.
- **Population dynamics** (up to +35): rewards moderate density (5–60% alive) and population variance (coefficient of variation 0.02–0.5).
- **Periodicity scoring** (−20 to +10): penalises static grids and short cycles, rewards complex oscillations.
- **Partial symmetry bonus** (+10): rewards partial (20–80%) horizontal, vertical, and rotational symmetry — more visually interesting than none or full.

**Lineage tracking**: Every mutation attempt is recorded as a `LineageNode` with rule string, fitness score, generation, parent rule, and accept/reject status. The sidebar displays the ancestry as a scrolling list with ✓/✗ markers.

### Presets

| Preset | Initial rule | Mutation rate | Strategy |
|--------|-------------|---------------|----------|
| Entropy Climber | B3/S23 | 0.12 | Start from Conway's Life, hill-climb entropy |
| Chaos Seeker | Random | 0.25 | Aggressive mutations from a random starting point |
| Gentle Drift | B36/S23 | 0.06 | Slow, careful evolution from HighLife |
| Complexity Hunter | B3/S23 | 0.15 | Balanced mutation with diversity bonus |
| From Nothing | B/S (empty) | 0.30 | Discover viable rules from an empty ruleset |
| Day & Night Explorer | B3678/S34678 | 0.10 | Explore the neighborhood of Day & Night |

### What to explore

- Run Entropy Climber and watch the rule gradually depart from standard Life, discovering increasingly complex behavior.
- Try From Nothing to see viable birth/survival rules emerge from a blank ruleset — the lineage sidebar shows the evolutionary path.
- Use `e` to pause evolution while the simulation keeps running, freezing on a particularly interesting rule to observe its long-term dynamics.
- Adjust mutation rate with `+`/`-` to balance exploration (high rate, more novelty) vs. refinement (low rate, incremental improvement).
- Press `a` to adopt the currently evolved rule into the main Game of Life grid for full-resolution exploration.
- Compare with Auto-Discovery: Rule Mutation runs a single live simulation with continuous in-place mutation, while Auto-Discovery evaluates batches in parallel with crossover breeding.

---

## 2D Spatial Frequency Spectrum

**Source:** `life/modes/spectrum.py`

### Background

The 2D Spatial Frequency Spectrum overlay performs a Discrete Fourier Transform on any running simulation's grid and displays the frequency-domain magnitude as a colorful panel. It reveals hidden periodic structures — standing waves, lattice patterns, rotational symmetry, oscillation frequencies — that are invisible in the spatial domain. Like ghost trail and long-exposure, it works as a universal overlay on all 130+ modes without modifying any mode logic.

### How it works

The overlay samples the current simulation state into an N×N grid (default 32×32) via `_get_minimap_data()`, the same universal sampling interface used by the minimap. The 2D DFT is computed using a separable approach:

```
For each row:    X_row[k] = Σ_n x[n] · e^(-j2πkn/N)
For each column: X[k_r, k_c] = Σ_n X_row[n, k_c] · e^(-j2πk_r·n/N)
```

Pre-computed twiddle factor tables (`cos_table`, `sin_table`) avoid redundant trigonometric calls, bringing the complexity to O(N³) for the full 2D transform. The second pass handles complex-valued input from the row transform using the identity `(a + bi)(cos θ - i sin θ) = (a cos θ + b sin θ) + i(b cos θ - a sin θ)`.

The resulting magnitude spectrum is DC-centered by swapping quadrants (shifting by N/2 in both axes), so the zero-frequency component appears at the center of the panel. Log-magnitude scaling (`log1p`) compresses the wide dynamic range for perceptual clarity, and values are normalised to [0, 1] for colormap lookup.

Rendering uses the inferno colormap via `colormap_rgb()` into the truecolor buffer (`tc_buf`), producing a smooth gradient from black (no energy) through purple and orange to yellow (peak energy). A bordered panel is drawn in the bottom-left corner, sized to at most 1/3 of the terminal in each dimension. A status badge in the top-right corner shows the current DFT resolution.

Caching recomputes the spectrum every 3 draw frames to stay responsive without introducing lag on larger resolutions.

### What to explore

- Toggle the spectrum on Game of Life glider guns to see the directional frequency signature of repeating structures.
- Run it on Wave Equation simulations to watch standing wave modes appear as bright spots in the frequency domain.
- Compare Reaction-Diffusion spots vs. worms: spots produce ring-like spectra (isotropic), worms produce directional bands.
- Increase resolution to 64×64 with `}` for finer frequency discrimination on large grids.
- Decrease to 8×8 with `{` for a fast, coarse overview that updates with minimal lag.
- Combine with ghost trail for simultaneous temporal and spectral analysis of any simulation.

---

## Phase Transition Detector

**Source:** `life/analytics.py` (engine), `life/app.py` (UI)

### Background

Phase transitions — moments when a system's qualitative behavior shifts abruptly — are the most scientifically interesting events in any simulation. Entropy collapses, symmetry breaking, the onset of oscillation, population crashes, and chaos-to-order transitions are all signatures of critical phenomena. The Phase Transition Detector monitors running analytics streams and automatically identifies these moments, bookmarking them for later review.

### How it works

The detector is a global overlay (not a mode) that works across all 140+ simulation engines with zero per-mode configuration. When enabled via **Ctrl+P**, it watches five analytics channels every generation:

| Channel | Detection method | Threshold |
|---------|-----------------|-----------|
| Entropy | Z-score against rolling 200-generation baseline | \|z\| > 2.5 |
| Population | Z-score against rolling 200-generation baseline | \|z\| > 3.0 |
| Symmetry | Absolute change in averaged symmetry score | Δ > 0.25 |
| Periodicity | Edge detection (period appears/disappears) | Binary |
| Stability | Classification transition (ordered ↔ chaotic) | Phase boundary crossing |

A cooldown of 20 generations between same-type detections prevents noisy rapid-fire alerts. When a transition is detected:

1. A **timestamped bookmark** is automatically added to the bookmark timeline (e.g., `⚡ chaos→order @gen 847`).
2. A **2-second flash banner** appears centered at the top of the screen with a blink effect.
3. An **audio ping** (880 Hz, 80 ms) plays if sound is enabled.

The Rule Mutation Engine has dedicated integration: when the detector is active during rule mutation, accepted mutations are fed to the detector so it can flag when a mutation crosses a phase boundary.

### Controls

| Key | Action |
|-----|--------|
| **Ctrl+P** | Toggle detector on/off |
| **Ctrl+T** | Open phase transition bookmark browser |
| **↑/↓** or **k/j** | Navigate bookmark list |
| **Enter** | Jump to selected bookmark |
| **Esc** | Close bookmark browser |

### What to explore

- Run Conway's Life from a random fill and watch the detector flag the initial chaos→order transition as gliders and still lifes emerge from the primordial noise.
- Enable the detector alongside the Rule Mutation Engine to see which mutations trigger phase boundary crossings.
- Use Reaction-Diffusion and sweep parameters — the detector will bookmark the exact generation where spots transition to worms to spirals.
- After a long session, press **Ctrl+T** to browse all detected transitions and jump between the most interesting moments, turning hours of observation into a curated highlight reel.
- Combine with the analytics overlay (**Ctrl+K**) to see transition counts and recent events in real time.

---

## Sim-in-a-Cell (Recursive Nested Simulation)

**Source:** `life/modes/recursive_sim.py`

### Background

Sim-in-a-Cell introduces multi-scale emergence: every cell in a macro-level grid contains a complete, independently running micro-simulation. The micro-simulation's aggregate density feeds upward to determine the macro cell's state, while the macro cell's state feeds back down into its micro-simulation as an external coupling signal. The result is two levels of reality influencing each other simultaneously — patterns at the micro scale drive macro-scale dynamics, and macro-scale context reshapes micro-scale behavior.

Any two of the eight mashup engines (Game of Life, Wave, Reaction-Diffusion, Fire, Boids, Ising, Rock-Paper-Scissors, Physarum) can be combined as macro and micro engines, creating 64 cross-scale combinations. Eight curated presets highlight especially interesting pairings.

### How it works

```
each generation:
    for each macro cell (r,c):
        compute macro cell density as external signal
        scale by coupling strength → uniform field for micro grid
        step the micro-simulation with external influence
        aggregate micro-grid density → rsim_micro_densities[r][c]
    build density field from all micro densities
    step the macro engine with micro density field as external input
    refresh macro density cache
```

The macro grid dimensions are fitted to the terminal (up to 30×40). Each macro cell hosts a micro-grid of configurable size (6×6, 8×8, 10×10, or 12×12). Bidirectional coupling strength is adjustable from 0 (fully independent) to 1 (maximum influence) with a default of 0.5.

In overview mode, each macro cell is rendered as a 2-character-wide block. The glyph (`░▒▓█`) encodes micro density; color encodes macro state (magenta = both active, cyan = macro alive, green = micro active). A movable cursor lets you select any cell to zoom into.

In zoom mode, the selected cell's micro-simulation is rendered full-screen with scaled-up blocks. A minimap in the corner shows your position in the macro grid. Arrow keys navigate between neighboring cells without returning to the overview.

### Controls

| Key | Action |
|-----|--------|
| **Space** | Play / pause |
| **n** or **.** | Single step |
| **+** / **-** | Increase / decrease coupling strength |
| **0** | Set coupling to zero (independent) |
| **>** / **<** | Increase / decrease simulation speed |
| **Enter** or **z** | Zoom into selected cell |
| **Esc** or **Backspace** | Back to overview (when zoomed) |
| **Arrow keys** / **hjkl** | Move cursor (overview) or navigate neighbor cells (zoom) |
| **r** | Reset simulation |
| **R** or **Esc** | Return to preset menu (overview) |
| **q** | Exit mode |

### What to explore

- Start with "GoL ← RD Cells" to see a Game of Life grid where each cell's alive/dead state is driven by the churning patterns of a Reaction-Diffusion micro-world.
- Try "GoL ← GoL Cells" for true recursive Life — Game of Life all the way down.
- Set coupling to 0 and watch macro and micro evolve independently, then slowly increase coupling to see cross-scale synchronization emerge.
- Zoom into individual cells and watch how neighboring macro-cell states visibly influence a cell's internal dynamics.
- Compare "Ising ← RPS Cells" (magnetic spins driven by rock-paper-scissors competition) with "RPS ← Wave Cells" (competitive dynamics driven by wave interference) to see how the choice of micro engine fundamentally changes macro-scale behavior.
- Use small cell sizes (6×6) for faster iteration and larger macro grids, or large cell sizes (12×12) for richer micro-simulation detail.

---

## Symbiosis Multi-Physics

**Source:** `life/modes/symbiosis.py`

### Background

Symbiosis Multi-Physics is a co-simulation mode where 3–8 distinct simulation engines run simultaneously on overlapping layers of the same grid, interacting through shared environmental fields. Unlike Mashup mode (which blends rules into a single engine) or Split Screen (side-by-side comparison), Symbiosis preserves each engine's independent dynamics while coupling them through four physical fields: temperature, chemical concentration, and flow velocity (u/v components). This creates true cross-domain emergent phenomena — organisms following chemical trails shaped by fluid currents, reactions accelerating in warm zones created by friction, currents deflected by growing biological structures.

### How it works

Each engine runs its own simulation step independently, producing a density grid per layer. After each generation, every engine's density is used to update the shared environmental fields according to engine-specific contribution rules:

- **Wave** → raises temperature (kinetic energy), creates flow gradients
- **Reaction-Diffusion** → deposits chemical concentration
- **Fire** → raises temperature (combustion heat)
- **Boids** → create flow fields (flock velocity) and deposit chemical pheromones
- **Physarum** → deposits chemical trail pheromone
- **Ising** → raises temperature from spin frustration energy
- **RPS** → deposits chemical from competition intensity
- **Game of Life** → raises temperature from population density

The fields then feed back into each engine through coupling densities — each engine type responds to different fields (e.g., fire responds to chemical fuel and wind, boids follow chemical gradients and are carried by flow currents, physarum is attracted to chemicals but avoids heat). Fields decay and diffuse spatially each step for smooth, natural-looking interactions.

Visualization uses RGB-layered color channels: each engine is assigned a color (red, green, cyan, yellow, magenta, or white), with the dominant layer at each cell determining the displayed color. When two layers overlap with similar intensity, magenta is used to indicate mixing. Density is shown using five-level Unicode block characters (░▒▓█).

### Presets

| Preset | Engines | Description |
|--------|---------|-------------|
| **Fluid-Chemical-Biological** | Wave + RD + Physarum | Waves drive chemical reactions; chemicals guide slime mold; slime creates wave disturbances |
| **Fire-Ising-Boids** | Fire + Ising + Boids | Fire heats spins; magnetic domains steer flocks; flock density fuels combustion |
| **Wave-RPS-GoL** | Wave + RPS + GoL | Waves modulate dominance; RPS competition seeds life; life emits wave pulses |
| **Full Ecosystem** | RD + Boids + Fire + Physarum | Chemistry, organisms, fire, and fungal networks interacting through shared fields |
| **Quantum-Classical Bridge** | Wave + Ising + RD | Wave interference shapes spin domains; spin alignment catalyzes reactions; reactions emit waves |
| **Predator Ecosystem** | Boids + Physarum + RPS + GoL | Flocks, slime trails, cyclic competition, and cellular life in one shared world |
| **Custom** | Pick 3–8 engines | Checkbox selection from the full engine catalogue |

### Controls

| Key | Action |
|-----|--------|
| **Space** | Play / pause |
| **n** or **.** | Single step |
| **1**–**8** | Solo layer N (press again to unsolo) |
| **!**–**\*** (Shift+1–8) | Mute / unmute layer N |
| **a** | Show all layers |
| **f** | Toggle environmental field overlay |
| **F** | Cycle through field views (temperature → chemical → flow_u → flow_v) |
| **+** / **-** | Increase / decrease coupling strength |
| **0** | Set coupling to zero (independent engines) |
| **>** / **<** | Increase / decrease simulation speed |
| **r** | Reset simulation |
| **R** | Return to preset menu |
| **q** or **Esc** | Exit mode |

### What to explore

- Start with "Fluid-Chemical-Biological" to see the canonical three-way interaction: waves create flow that shapes chemical gradients, which in turn guide physarum growth, whose structures then disturb the wave field.
- Use the field overlay (**f**/**F**) to watch the invisible environmental fields that mediate cross-engine coupling — see temperature hotspots from fire, chemical trails from physarum, flow vectors from wave gradients.
- Solo individual layers (**1**–**8**) to see how each engine behaves in isolation while still being influenced by the shared fields, then show all (**a**) to see the combined picture.
- Try "Full Ecosystem" (4 engines) for a richer interaction network where chemistry, organisms, fire, and fungal networks create complex feedback loops.
- Adjust coupling from 0 (independent) to 1.0 (maximum) to see how cross-domain influence changes emergent behavior. At zero coupling, engines evolve independently; at high coupling, they become strongly correlated.
- Build a custom combination to test unusual pairings — what happens when Ising spins interact with boid flocks through temperature fields?
