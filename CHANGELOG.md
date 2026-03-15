# Changelog

All notable changes to this project are documented in this file.

## 2026-03-15

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
