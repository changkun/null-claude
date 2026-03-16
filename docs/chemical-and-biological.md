# Chemical & Biological Systems

Life at every scale — from molecular reactions to ecosystem dynamics and the origin of life itself.

---

## Reaction-Diffusion Textures

**Background** — The Gray-Scott model simulates two chemical species, U and V, that diffuse at different rates and react autocatalytically: U + 2V -> 3V. Discovered numerically by Pearson (1993) and explored extensively by Gray and Scott, this system produces an astonishing menagerie of self-organising patterns — spots, stripes, coral, worms, mitosis — from just two parameters. These patterns closely resemble biological pigmentation, seashell markings, and animal coat textures, vindicating Turing's 1952 prediction that chemical instabilities can break spatial symmetry.

**Formulation** — The simulation solves the coupled PDEs on a 2D grid with periodic (wrapping) boundaries:

```
dU/dt = Du * laplacian(U) - U*V^2 + f*(1 - U)
dV/dt = Dv * laplacian(V) + U*V^2 - (f + k)*V

Where:
  U, V     = concentrations of the two species, clamped to [0, 1]
  Du, Dv   = diffusion coefficients (Du > Dv, typically Du=0.21, Dv=0.105)
  f        = feed rate (replenishment of U from reservoir), range 0.001-0.100
  k        = kill rate (removal of V), range 0.001-0.100
  laplacian = 5-point discrete stencil: U[r-1][c] + U[r+1][c] + U[r][c-1] + U[r][c+1] - 4*U[r][c]
  dt       = time step (forward Euler integration)
```

Seeding is done by placing circular patches of V (with U=0.5) into a uniform U=1, V=0 background. Each preset selects a (f, k) pair from the parameter space that produces a distinct pattern class — from "spots" at f=0.0300, k=0.0620 to "coral" at f=0.0545, k=0.0620 to "fingerprints" at f=0.0545, k=0.0620 with slight variations.

**What to look for** — Watch how V concentration (displayed as ASCII density glyphs) self-organises from random circular seeds into regular patterns. Tiny changes in f or k produce wildly different morphologies: increase k to watch spots shrink and die; decrease f to see stripes break into labyrinthine worms. Mouse clicks inject V perturbations. Five color schemes (ocean, thermal, organic, purple, monochrome) let you see the concentration field from different perspectives.

**References**
- Pearson, J. E. "Complex Patterns in a Simple System." *Science* 261 (1993): 189-192. https://doi.org/10.1126/science.261.5118.189
- Gray, P. & Scott, S. K. "Autocatalytic reactions in the isothermal, continuous stirred tank reactor." *Chemical Engineering Science* 38 (1983): 29-43. https://doi.org/10.1016/0009-2509(83)80132-8

---

## BZ Reaction

**Background** — The Belousov-Zhabotinsky (BZ) reaction is the most famous example of a chemical oscillator. Discovered by Boris Belousov in 1951 and characterised by Anatol Zhabotinsky in the 1960s, it produces stunning spiral and target wave patterns in a dish of cerium/malonic-acid solution. The simulation uses an Oregonator-inspired three-variable model (activator, inhibitor, recovery) that captures the essential excitable-medium dynamics responsible for these self-organising waves.

**Formulation** — Three coupled fields evolve on a 2D grid with wrapping boundaries:

```
da/dt = a * (alpha - a - beta*c) + D * laplacian(a)     (activator)
db/dt = a - b                                             (inhibitor)
dc/dt = gamma * (a - c)                                   (recovery)

Where:
  a = activator concentration (autocatalytic, excitable)
  b = inhibitor concentration (tracks activator with delay)
  c = recovery variable (slowly follows activator, suppresses re-excitation)
  alpha = activator self-amplification rate (0.6-1.4)
  beta  = inhibitor feedback strength (0.7-1.2)
  gamma = recovery rate (0.5-1.2)
  D     = diffusion coefficient for activator (0.10-0.35)
  dt    = 0.05 (Euler step)
  laplacian = 5-point stencil, wrapping boundaries
```

Initial conditions include spiral seeds (broken wavefronts that curl), center Gaussian blobs (expanding rings), random seed patches, and random noise fields.

**What to look for** — Spiral waves rotate around their free ends, annihilating when they collide — a hallmark of excitable media. Target waves expand as concentric rings from point sources. Increasing alpha sharpens wavefronts; decreasing gamma creates slower, broader waves. The "Turbulent" preset (alpha=1.4, D=0.1) shows spiral breakup into spatiotemporal chaos. Phase-based coloring maps activation states to a BZ-like color wheel: bright yellow wavefronts, cyan transitions, magenta refractory zones, and dark quiescent regions.

**References**
- Zhabotinsky, A. M. "A history of chemical oscillations and waves." *Chaos* 1 (1991): 379-386. https://doi.org/10.1063/1.857857
- Field, R. J. & Noyes, R. M. "Oscillations in chemical systems. IV. Limit cycle behavior in a model of a real chemical reaction." *Journal of Chemical Physics* 60 (1974): 1877-1884. https://doi.org/10.1063/1.1682069

---

## Chemotaxis

**Background** — Bacterial colony morphogenesis is one of the most accessible demonstrations of pattern formation in biology. When bacteria are inoculated on agar plates with varying nutrient concentrations, they produce fractal-like structures: compact Eden clusters in rich media, DLA-like tendrils under starvation, and concentric rings through chemotactic signaling. This simulation couples three continuum fields — bacteria density, nutrient concentration, and chemoattractant signal — to reproduce the full range of observed colony morphologies.

**Formulation** — Three fields interact via reaction-diffusion-advection on a grid with zero-flux boundaries:

```
dB/dt = g * B * N * (1 - B)   +  m * laplacian(B)  +  chi_flux
         (logistic growth)        (random motility)    (chemotaxis)

dN/dt = Dn * laplacian(N)  -  cons * B * N
         (nutrient diffusion)    (consumption)

dS/dt = Sp * B  -  Sd * S  +  0.1 * laplacian(S)
         (production)  (decay)   (signal diffusion)

Where:
  B    = bacteria density [0, 1]
  N    = nutrient concentration [0, 1], initially 1.0 everywhere
  S    = chemoattractant signal [0, 1]
  g    = growth rate (0.4-0.8)
  m    = motility / random diffusion (0.005-0.08)
  chi  = chemotaxis strength (0.0-0.6)
  cons = nutrient consumption rate (0.3-0.6)
  Sp   = signal production rate (0.0-0.5)
  Sd   = signal decay rate (0.02-0.1)
  Dn   = nutrient diffusion coefficient (0.04-0.08)
  dt   = 0.1 (Euler step)
```

Chemotactic flux uses an upwind scheme: bacteria flow toward higher-signal neighbors proportional to the signal gradient, weighted by local bacterial density and chemotaxis strength chi.

**What to look for** — The "Eden Cluster" preset (high growth, zero chemotaxis) produces compact circular colonies. "DLA Tendrils" (high consumption, moderate chemotaxis) creates branching fractal structures as bacteria compete for scarce nutrients. "Concentric Rings" (strong chemotaxis, high signal production) generates periodic wave-like patterns. Toggle between bacteria, nutrient, and signal views to see the depletion zones and chemical gradients driving morphology.

**References**
- Ben-Jacob, E. et al. "Generic modelling of cooperative growth patterns in bacterial colonies." *Nature* 368 (1994): 46-49. https://doi.org/10.1038/368046a0
- Keller, E. F. & Segel, L. A. "Model for chemotaxis." *Journal of Theoretical Biology* 30 (1971): 225-234. https://doi.org/10.1016/0022-5193(71)90050-6

---

## Forest Fire

**Background** — The Drossel-Schwaab forest fire model (1992) is a cellular automaton that demonstrates self-organised criticality in ecology. Trees grow on empty cells at rate p, catch fire from burning neighbors or random lightning strikes at rate f, burn for one step, and leave ash. The ratio p/f controls the system: when regrowth is much faster than ignition, the forest reaches a critical density where fire sizes follow a power law — large fires are rare but inevitable, echoing the statistics of real wildland fires.

**Formulation** — Each cell occupies one of five states:

```
States:  0 = empty,  1 = tree,  2 = burning,  3 = ash,  4 = ember

Transition rules (applied synchronously each step):
  tree -> burning     if any 8-neighbor is burning or ember
  tree -> burning     with probability p_lightning (spontaneous ignition)
  burning -> ember    (fire cools)
  ember -> ash        (fire dies)
  ash -> empty        with probability ash_decay
  empty -> tree       with probability p_grow

Parameters:
  p_grow      = tree growth probability per step (0.003-0.02)
  p_lightning = lightning strike probability per tree per step (0.0001-0.001)
  ash_decay   = probability ash decays to empty per step (0.05-0.50)
  initial_density = fraction of cells starting as trees (0.3-0.9)
```

**What to look for** — Watch the forest cycle between dense canopy and catastrophic burns. The tree density sparkline at the bottom reveals oscillatory dynamics: long growth phases punctuated by sudden crashes. Increase p_grow to accelerate recovery; increase p_lightning to trigger more frequent, smaller fires. The "Wildfire" preset with high density and low lightning produces rare but devastating conflagrations — a hallmark of self-organised criticality.

**References**
- Drossel, B. & Schwabl, F. "Self-organized critical forest-fire model." *Physical Review Letters* 69 (1992): 1629-1632. https://doi.org/10.1103/PhysRevLett.69.1629
- Bak, P. et al. "A forest-fire model and some thoughts on turbulence." *Physics Letters A* 147 (1990): 297-300. https://doi.org/10.1016/0375-9601(90)90451-S

---

## SIR Epidemic

**Background** — The SIR (Susceptible-Infected-Recovered) model, introduced by Kermack and McKendrick in 1927, is the foundational framework for mathematical epidemiology. This spatially explicit, agent-based implementation goes beyond mean-field ODE models by capturing local transmission chains, herd immunity thresholds, and the stochastic nature of disease propagation. Individuals occupy grid cells, and infection spreads through proximity with distance-weighted probability.

**Formulation** — Each occupied cell has state S (susceptible), I (infected), R (recovered), or D (dead):

```
Infection:
  For each infected cell at (r, c), scan all cells within radius R:
    p_infect = trans_prob * (1 - dist / (R + 1))
    susceptible neighbor becomes infected with probability p_infect

Recovery:
  Each infected cell has a countdown timer = recovery_time
  Timer decrements by 1 each step
  When timer reaches 0:
    die with probability mortality_rate -> state D
    otherwise -> state R

Reinfection (optional):
  Recovered cells revert to susceptible with probability 0.005 per step

Parameters:
  trans_prob      = base transmission probability (0.15-0.60)
  infection_radius = spatial reach of infection (1.5-5.0 cells)
  recovery_time   = steps until recovery (8-40)
  mortality_rate  = probability of death upon recovery (0.0-0.15)
  population_density = fraction of grid occupied (0.3-1.0)
```

**What to look for** — The epidemic curve (bar chart in status area) shows the classic SIR peak-and-decline. "Measles" (high transmission, large radius) sweeps through rapidly; "Sparse Rural" (low density) shows slow, fragmented spread. The "Vaccination" preset demonstrates herd immunity by pre-seeding Recovered cells. "Reinfection Wave" produces oscillatory endemic dynamics as immunity wanes. Adjust transmission probability mid-run to simulate interventions.

**References**
- Kermack, W. O. & McKendrick, A. G. "A contribution to the mathematical theory of epidemics." *Proceedings of the Royal Society A* 115 (1927): 700-721. https://doi.org/10.1098/rspa.1927.0118
- Anderson, R. M. & May, R. M. *Infectious Diseases of Humans.* Oxford University Press, 1991. https://global.oup.com/academic/product/9780198540403

---

## Lotka-Volterra

**Background** — The Lotka-Volterra predator-prey model, independently developed by Alfred Lotka (1925) and Vito Volterra (1926), describes the cyclic population dynamics of interacting species. This spatial, agent-based implementation places grass, prey (herbivores), and predators on a grid. Each agent moves, eats, loses energy, reproduces when well-fed, and dies when starved. The emergent population oscillations — prey boom, predator boom, prey crash, predator crash — reproduce the classic Lotka-Volterra cycles without any explicit differential equations.

**Formulation** — Three entity types interact on a toroidal grid:

```
Grid cells: grass (0), empty/regrowing (-1), prey (1), predator (2)

Grass:
  empty -> grass after grass_regrow steps (countdown timer)

Prey (herbivores):
  Move to random 4-neighbor (prefer grass cells)
  Eat grass: energy += prey_gain
  Lose 1 energy per step (starvation if energy <= 0 -> death)
  Reproduce when energy >= prey_breed:
    split energy equally, offspring placed at vacated cell

Predators:
  Move to random 4-neighbor (prefer prey cells)
  Eat prey: energy += pred_gain (prey dies)
  Lose 1 energy per step
  Reproduce when energy >= pred_breed:
    split energy equally

Parameters:
  grass_regrow    = steps for grass to regrow (3-15)
  prey_gain       = energy gained from eating grass (3-8)
  pred_gain       = energy gained from eating prey (15-30)
  prey_breed      = energy threshold for prey reproduction (6-15)
  pred_breed      = energy threshold for predator reproduction (10-25)
  prey_density    = initial fraction of prey (0.05-0.20)
  pred_density    = initial fraction of predators (0.01-0.05)
```

**What to look for** — The population bar chart shows the characteristic quarter-cycle phase lag: prey peaks lead predator peaks. "Boom and Bust" amplifies oscillations; "Stable Ecosystem" maintains tighter cycles. Watch spatial patterns: predators cluster around prey herds, creating traveling waves of predation. If predators overgraze, they crash and prey explode — the cycle restarts. Adjust grass regrowth to see bottom-up trophic control, or predator breeding threshold for top-down control.

**References**
- Lotka, A. J. *Elements of Physical Biology.* Williams & Wilkins, 1925. https://archive.org/details/elementsofphysic017171mbp
- Volterra, V. "Fluctuations in the abundance of a species considered mathematically." *Nature* 118 (1926): 558-560. https://doi.org/10.1038/118558a0

---

## Spiking Neural Network

**Background** — Eugene Izhikevich's 2003 neuron model achieves biological fidelity comparable to Hodgkin-Huxley models at the computational cost of an integrate-and-fire model. With just two differential equations and four parameters (a, b, c, d), it reproduces all 20 known neurocomputational properties: regular spiking, fast spiking, chattering, bursting, and more. This simulation places Izhikevich neurons on a 2D grid with local synaptic connections, producing emergent network phenomena: traveling waves, spiral activity, synchronised bursts, and avalanche dynamics.

**Formulation** — Each neuron on the grid follows the Izhikevich equations:

```
dv/dt = 0.04*v^2 + 5*v + 140 - u + I
du/dt = a * (b*v - u)

Spike rule: if v >= 30 mV then v = c, u = u + d

Where:
  v = membrane potential (mV), initialised near -65
  u = recovery variable, initialised at b*v
  I = synaptic input + noise

Synaptic input:
  I = sum over 8-neighbors: weight * (+1 if excitatory fired, -1 if inhibitory fired)
    + noise_amp * N(0, 1)    (Gaussian thalamic noise)

Neuron types:
  Excitatory (regular spiking): a=0.02, b=0.2, c=-65, d=8
  Inhibitory (fast spiking):    a=0.1,  b=0.2, c=-65, d=2
  Chattering:                   a=0.02, b=0.2, c=-50, d=2

Parameters:
  excit_ratio   = fraction of excitatory neurons (0.6-0.9)
  weight        = synaptic weight (2.0-20.0)
  noise_amp     = thalamic noise amplitude (1.0-10.0)
  dt            = integration sub-step (0.5-1.0 ms)
```

Integration uses Euler method with sub-steps (1/dt iterations per logical step) for numerical stability. Fire history decays exponentially (factor 0.85) to produce a glow-trail visualization.

**What to look for** — Excitatory neurons fire in bright yellow; inhibitory neurons in cyan. The glow trail (red-to-magenta decay) shows wave propagation paths. "Cortical Column" produces irregular, asynchronous activity. "Traveling Waves" show coherent activity fronts sweeping across the network. Increase synaptic weight to push the network toward synchronised bursts (epileptic-like); increase noise to desynchronize. The fire rate indicator shows network activity level: sustained ~2-5% is healthy; >10% suggests pathological synchrony.

**References**
- Izhikevich, E. M. "Simple model of spiking neurons." *IEEE Transactions on Neural Networks* 14 (2003): 1569-1572. https://doi.org/10.1109/TNN.2003.820440
- Izhikevich, E. M. "Which model to use for cortical spiking neurons?" *IEEE Transactions on Neural Networks* 15 (2004): 1063-1070. https://doi.org/10.1109/TNN.2004.832719

---

## Cellular Potts Model

**Background** — The Cellular Potts Model (CPM), also called the Glazier-Graner-Hogeweg model, simulates multicellular tissue dynamics using an energy-minimization approach. Originally developed by Graner and Glazier (1992) to explain cell sorting in embryonic tissue, it represents each biological cell as a connected domain of lattice pixels. Cells grow, shrink, and migrate through stochastic Metropolis-algorithm pixel copy attempts, accepting or rejecting boundary changes based on energy (Hamiltonian) differences. This elegant framework captures cell sorting, wound healing, tumor invasion, and collective cell migration.

**Formulation** — The system evolves through single-pixel Metropolis steps:

```
Hamiltonian:
  H = H_adhesion + H_area + H_chemotaxis

  H_adhesion = sum over all neighbor pairs: J[type_i][type_j] * delta(cell_i != cell_j)
    J[i][j] = adhesion energy between cell type i and type j
    Lower J = stronger adhesion (cells prefer to touch)

  H_area = lambda_area * sum over all cells: (area - target_area)^2
    Penalizes deviation from target cell size

  H_chemotaxis = -lambda_chem * chemical_field[r][c]
    Biases cell extension toward chemical gradients (when enabled)

Metropolis step:
  1. Pick random pixel (r, c) with cell ID = target
  2. Pick random 4-neighbor (nr, nc) with cell ID = source
  3. If source == target: skip
  4. Propose copying source ID into (r, c)
  5. Compute delta_H = H_after - H_before
  6. Accept if delta_H <= 0, else accept with probability exp(-delta_H / T)
  7. Update area cache

Parameters:
  Temperature T     = stochastic fluctuation level (5.0-12.0)
  lambda_area       = area constraint strength (1.5-3.0)
  target_area       = preferred cell size in pixels (20-60)
  J matrix          = type-type adhesion energies
  lambda_chem       = chemotaxis strength (0 or 200)
  steps_per_frame   = 500-1000 Metropolis attempts per visual update
```

**What to look for** — In "Cell Sorting," two randomly intermixed cell types segregate into domains — the Steinberg differential adhesion hypothesis in action. "Wound Healing" shows a cell sheet edge advancing to fill empty space. "Tumor Growth" demonstrates invasive expansion of high-proliferation cells. Watch boundary pixels (bold) define cell outlines; interior pixels (dimmer) show cell body. Temperature controls membrane fluctuations: high T = motile, ruffled edges; low T = smooth, rigid cells.

**References**
- Graner, F. & Glazier, J. A. "Simulation of biological cell sorting using a two-dimensional extended Potts model." *Physical Review Letters* 69 (1992): 2013-2016. https://doi.org/10.1103/PhysRevLett.69.2013
- Swat, M. H. et al. "Multi-scale modeling of tissues using CompuCell3D." *Methods in Cell Biology* 110 (2012): 325-366. https://doi.org/10.1016/B978-0-12-388403-9.00013-8

---

## Artificial Life Ecosystem

**Background** — This mode implements a complete artificial ecosystem with neuroevolution. Creatures with heritable genomes — encoding speed, size, sensory range, diet type, and a small neural network brain — navigate a 2D environment, eat food or each other, reproduce with mutation, and die from starvation or old age. Over hundreds of generations, natural selection shapes the population: herbivores evolve efficient foraging strategies, predators develop pursuit behaviors, and arms races emerge between prey evasion and predator tracking. The system demonstrates open-ended evolution in a minimal substrate.

**Formulation** — Each creature has a 6-input, 4-hidden, 2-output neural network brain:

```
Neural network (forward pass):
  Inputs: [nearest_food_dr, nearest_food_dc, nearest_threat_dr, nearest_threat_dc, energy_norm, bias=1.0]
  Hidden: h[j] = tanh(sum_i(inputs[i] * W1[j*6 + i]))   for j in 0..3
  Output: (dr, dc) = (tanh(sum_j(h[j] * W2[o*4 + j])))  for o in 0..1
  Total weights: 6*4 + 4*2 = 32

Movement:
  velocity = 0.3 * old_velocity + 0.7 * brain_output * speed * speed_scale

Energy dynamics:
  cost_per_step = (|vr| + |vc|) * 0.3 * size + 0.1 * size
  eating food:   energy += food_value * 50
  eating prey:   energy += prey_energy * 0.6 + prey_size * 20

Reproduction (when energy > 0.75 * max_energy, age > 60, random < 0.02/size):
  Parent energy halved; child inherits mutated traits
  Trait mutation: trait += gaussian(0, 0.1) * mutation_rate * 3
  Brain mutation: weight += gaussian(0, 0.3) with probability mutation_rate
  Rare diet mutation: probability mutation_rate * 0.1

Diet types: 0=herbivore, 1=predator, 2=omnivore
```

**What to look for** — Watch population sparklines for Lotka-Volterra-like oscillations between herbivores and predators. Average trait statistics reveal evolutionary trends: speed often increases under predation pressure; size evolves toward an energy-efficiency optimum. "Evolution Lab" (high mutation) produces rapid adaptation visible within minutes. When the population crashes to zero, five fresh herbivores respawn — a reboot of evolution. The stats panel tracks generation depth, revealing how many reproductive generations have elapsed.

**References**
- Sims, K. "Evolving virtual creatures." *SIGGRAPH Conference Proceedings* (1994): 15-22. https://doi.org/10.1145/192161.192170
- Stanley, K. O. & Miikkulainen, R. "Evolving neural networks through augmenting topologies." *Evolutionary Computation* 10 (2002): 99-127. https://doi.org/10.1162/106365602320169811

---

## Ant Farm Simulation

**Background** — This mode simulates a side-view ant colony, inspired by real glass-walled ant farms (formicaria). Ants dig tunnels through layered soil, forage for surface food, communicate via pheromone trails, and bring resources back to the queen chamber. The colony exhibits emergent architecture: tunnel networks, storage chambers, and systematic exploration — all arising from simple local rules without central planning. The simulation captures the essence of swarm intelligence studied by Deneubourg, Bonabeau, and others.

**Formulation** — Ants are individual agents with state-based behavior:

```
Ant states: explore, forage, return_food, dig

Explore:
  Move to random passable neighbor (air, chamber, queen cell)
  Weight by: 1.0 + food_pheromone * 5.0
  Dig into dirt with probability 0.08; clay with probability 0.02 * dig_strength
  Leave home_pheromone += 0.5 (capped at 10.0)
  Switch to forage when near surface (probability 0.3)
  Switch to dig randomly (probability 0.02 when deep enough)

Forage:
  Walk along surface, pick up food on contact
  food found -> state = return_food, total_food += 1

Return_food:
  Navigate toward queen using: home_pheromone * 2.0 + (50 - distance_to_queen)
  Leave food_pheromone += 1.0 trail
  Dig toward queen if blocked (probability 0.15)
  Deliver food -> eggs += 1; every 5 eggs, spawn new ant (up to 60)

Pheromone dynamics:
  decay: pheromone *= 0.995 per step (exponential evaporation)
  floor: values below 0.01 set to 0.0

Grid cells: AIR, DIRT, CLAY, ROCK, CHAMBER, QUEEN_CELL, FOOD_STORE
  Soil layers: shallow=dots, medium=colons, deep=hashes
  Clay requires higher dig_strength; rock is impassable
```

**What to look for** — Watch the colony self-organise: ants first dig a starter tunnel from surface to queen, then branch out seeking food. Pheromone trails (faint dots and commas) guide returning foragers, creating positive feedback loops that establish main highways. The "Rocky" preset forces creative tunnel routing around obstacles. "Rainy" adds precipitation that occasionally spawns surface food. Drop food with 'f' and watch ants discover and exploit it via trail recruitment. Chamber formation happens at tunnel junctions when ants excavate wider spaces.

**References**
- Bonabeau, E. et al. *Swarm Intelligence: From Natural to Artificial Systems.* Oxford University Press, 1999. https://global.oup.com/academic/product/9780195131581
- Deneubourg, J.-L. et al. "The self-organizing exploratory pattern of the Argentine ant." *Journal of Insect Behavior* 3 (1990): 159-168. https://doi.org/10.1007/BF01417909

---

## Morphogenesis

**Background** — This mode simulates embryonic development from a single fertilized egg. A zygote divides, daughter cells respond to morphogen gradients, differentiate into distinct germ layers (ectoderm, mesoderm, endoderm), and self-organise into body plans. The simulation implements core developmental biology concepts: reaction-diffusion morphogen signaling, gene regulatory networks (per-cell genomes), inductive signaling by organiser cells, programmed cell death (apoptosis) for tissue sculpting, and regeneration. The approach draws on Turing's morphogenesis theory (1952) and Wolpert's positional information model.

**Formulation** — Two morphogen fields, a nutrient field, and per-cell genomes drive development:

```
Morphogen diffusion:
  dA/dt = Da * laplacian(A) + production_A - decay_A * A
  dB/dt = Db * laplacian(B) + production_B - decay_B * B
  dN/dt = 0.02 * laplacian(N) - 0.1 * (living_cell) + nutr_rate * (1-N) * 0.05

  Da = 0.05-0.09,  Db = 0.04-0.09  (morphogen diffusion)
  decay_A = 0.015-0.03,  decay_B = 0.01-0.025
  Signal cells produce extra morphogen A (+0.3)

Per-cell genome (heritable, mutable):
  div_rate         = 0.12   (division probability per step)
  div_nutrient     = 0.3    (nutrient threshold for division)
  morph_A_prod     = 0.0-0.8 (morphogen A production)
  morph_B_prod     = 0.0-0.3 (morphogen B production)
  diff_thresh_A    = 0.4    (A threshold for differentiation)
  diff_thresh_B    = 0.4    (B threshold for differentiation)
  apoptosis        = 0.002  (background death rate)
  mutation_rate    = 0.02   (per-division mutation probability)

Differentiation rules (for stem cells):
  A > thresh_A and B < thresh_B  ->  ectoderm
  B > thresh_B and A < thresh_A  ->  endoderm
  A > 0.7*thresh_A and B > 0.7*thresh_B  ->  mesoderm
  Neural induction: A > 0.6, B < 0.2, age > 15, adjacent ecto >= 2  ->  neural

Cell types: stem(@), ectoderm(#), mesoderm(%), endoderm(&), neural(*), signal(<>), dead(..)
```

**What to look for** — "Radial Embryo" produces concentric tissue layers from a central egg. "Bilateral Body Plan" uses a dorsal organiser to establish left-right symmetry. "Gastrulation" shows cells folding inward. "Neural Tube Formation" demonstrates induction: ectoderm near the organiser becomes neural tissue. "Regeneration" cuts the embryo at generation 100 and watches it regrow. Switch views (cells, morphA, morphB, nutrient) to see the invisible chemical landscapes driving visible pattern formation.

**References**
- Turing, A. M. "The chemical basis of morphogenesis." *Philosophical Transactions of the Royal Society B* 237 (1952): 37-72. https://doi.org/10.1098/rstb.1952.0012
- Wolpert, L. "Positional information and the spatial pattern of cellular differentiation." *Journal of Theoretical Biology* 25 (1969): 1-47. https://doi.org/10.1016/S0022-5193(69)80016-0

---

## Artificial Chemistry

**Background** — Artificial chemistry systems explore how complex molecular organization can emerge from simple reaction rules. This simulation models a primordial soup where abstract molecules (strings over an 8-letter alphabet A-H) drift, collide, and react through pattern-matching rules: concatenation, cleavage, template-directed replication, and catalysis. Over time, autocatalytic cycles form — sets of molecules that catalyze each other's production — and occasionally genuine self-replicators emerge, echoing hypotheses about the origin of life from Eigen's hypercycle theory and Kauffman's autocatalytic sets.

**Formulation** — Molecules are character strings of length 1-16 on a 2D grid:

```
Reaction types (when two adjacent molecules collide):
  1. Template replication (if enabled):
     Template mol1 (len >= 3) + raw material mol2 (len >= 2)
     Product = complement of mol1 (each char mapped: A<->E, B<->F, C<->G, D<->H)
     Cost: 0.3 energy from template, 0.2 from material
     Mutation: each output char has mutation_rate chance of random substitution

  2. Catalysis (if enabled):
     Catalyst mol1 (len >= 3) must contain complement of mol2's first 2 chars
     Product: mol2 with each char shifted +1 in alphabet (A->B, B->C, ...)
     Cost: 0.1 energy from catalyst; product gains 0.2

  3. Concatenation:
     mol1 + mol2 -> mol1+mol2  (if combined length <= 16)
     Probability: react_prob * 0.5,  requires energy > 0.3
     Energy: min(1.0, e1 + e2*0.5 + 0.3)

  4. Spontaneous cleavage:
     Molecules of length >= 4 split at random point
     Probability: cleave_prob * 0.3

Energy dynamics:
  All molecules lose energy_decay per step (0.003-0.01)
  Depleted molecules degrade: lose last char, then disappear
  Food monomers injected at edges at rate food_rate

Autocatalytic cycle detection (every 20 steps):
  Build catalytic graph: A -> B means A catalyzes production of B
  Search for cycles of length 2-4 via DFS
```

**What to look for** — "RNA World" (high template bias) favors replication — watch for replicator sequences (marked with diamond glyphs). "Metabolism First" (catalysis only, no templates) emphasizes autocatalytic cycles. Monitor the stats line: species diversity, longest polymer, cycle count, and replicator count chart the soup's chemical evolution. "Lipid World" enables clustering — long polymers attract nearby monomers, forming proto-compartments. Toggle between soup view (molecule type), energy view, and diversity view (colored by first character) to see different aspects of the chemistry.

**References**
- Kauffman, S. A. *The Origins of Order.* Oxford University Press, 1993. https://global.oup.com/academic/product/9780195079517
- Eigen, M. & Schuster, P. "The hypercycle: A principle of natural self-organization." *Naturwissenschaften* 64 (1977): 541-565. https://doi.org/10.1007/BF00450633

---

## Immune System Simulation

**Background** — This mode simulates the vertebrate immune response as a spatial agent-based model. Pathogens (bacteria or viruses) invade, replicate, and mutate. Innate immune cells (macrophages, neutrophils) rush to infection sites via chemotaxis on a cytokine gradient. Adaptive immune cells (T-cells, B-cells) recognize specific antigen shapes, proliferate when activated, and form long-lived memory cells for faster secondary responses. Pathogen mutation drives an evolutionary arms race. The model captures key immunological concepts: clonal selection, affinity maturation, vaccination, autoimmunity, and cytokine storms.

**Formulation** — Entities interact on a 2D grid with a diffusible cytokine field:

```
Antigen recognition:
  Antigens and receptors are 6-bit integers (0-63)
  Match quality = 1.0 - hamming_distance(receptor XOR antigen) / 6
  Activation threshold: match > 0.67 (at most 2 bits different)

Cytokine field:
  Produced at infection sites (bacteria, infected tissue, debris)
  Diffuses via 5-point Laplacian with coefficient D
  Decays at rate cytokine_decay (0.005-0.03)
  Innate cells follow gradient: move to highest-cytokine empty neighbor

Entity behaviors:
  Bacteria: replicate to adjacent empty/tissue cells at replicate_rate
            mutate antigen (flip random bit) at mutate_rate
  Virus:    infect adjacent tissue -> infected state
            infected tissue releases viral copies at replicate_rate
  Macrophage: phagocytose adjacent pathogen/debris (kills + produces cytokine)
              move up cytokine gradient
  Neutrophil: fast responder, kills pathogens, shorter lifespan
  T-cell:    scan adjacent cells, kill if antigen matches receptor
             proliferate on activation (clone with same receptor)
  B-cell:    produce antibodies if antigen match found
             proliferate on activation, generate memory cells
  Memory:    long-lived, rapidly reactivate on antigen re-encounter
  Antibody:  drifts, marks pathogens for destruction (opsonization)

Vaccination preset: pre-seeds memory cells with receptors matching pathogen antigen
Autoimmune: self-antigen = 0; some immune cells have receptor ~ 0 (attack self)
Cytokine storm: very low cytokine decay -> runaway positive feedback
```

**What to look for** — "Bacterial Invasion" shows innate immunity rushing to contain the front. "Viral Outbreak" demonstrates the critical role of T-cells in clearing infected tissue. "Vaccination" produces a dramatically faster secondary response — memory cells activate within steps rather than requiring clonal expansion. "Autoimmune" shows immune cells attacking healthy tissue (yellow self-damage). "Cytokine Storm" demonstrates immune overreaction: excessive cytokine production recruits too many cells, causing collateral tissue destruction worse than the pathogen itself.

**References**
- Perelson, A. S. & Weisbuch, G. "Immunology for physicists." *Reviews of Modern Physics* 69 (1997): 1219-1268. https://doi.org/10.1103/RevModPhys.69.1219
- Murphy, K. & Weaver, C. *Janeway's Immunobiology.* 9th ed., Garland Science, 2016. https://www.garlandscience.com/product/isbn/9780815345053

---

## Coral Reef Ecosystem

**Background** — Coral reefs are among Earth's most biodiverse and threatened ecosystems. This simulation models a reef as a multi-trophic spatial system: coral polyps grow branching and massive structures, symbiotic zooxanthellae provide photosynthetic energy, herbivorous fish and urchins graze algae, predators control herbivore populations, and environmental stressors (ocean warming, acidification) trigger bleaching cascades. The simulation captures the delicate balance that maintains reef health and the tipping-point dynamics that can flip a reef from coral-dominated to algae-dominated states.

**Formulation** — A 2D grid of sessile organisms and mobile entities interact under environmental forcing:

```
Coral dynamics:
  Photosynthesis: energy_gain = zooxanthellae * light_at_depth * 0.05
                  light_at_depth = base_light * max(0.1, 1.0 - 0.7 * depth_fraction)
  Acid stress: energy_gain *= max(0.2, 1.0 - (8.1 - pH) / 1.0)
  Health: h += energy_gain - 0.01 per step
  Bleaching: if temp > 28C, probability = (temp - 28) / 3 * 0.08
             zooxanthellae -= 0.15; if zoox < 0.1 -> bleached state
  Recovery: if temp < 28.5C, zooxanthellae slowly recolonize (+0.005/step)
  Growth: if health > 0.6, probability 0.015 * health to spread to adjacent water/turf
  Death: if health <= 0 -> dead coral skeleton

Algae dynamics:
  Turf algae spread onto water/dead coral at rate 0.02 * nutrients
  Turf -> macroalgae in high nutrients (probability 0.008 * nutrients)
  Macroalgae smother adjacent coral (health -= 0.05)
  Coralline algae (CCA) facilitate coral recruitment (probability 0.003)

Mobile entities:
  Herbivorous fish: graze algae (+20 energy), reproduce when energy > 120
  Predators: hunt herbivores (detection range 2, probability 0.1)
  Crown-of-thorns starfish: eat coral directly, reproduce in high nutrients
  Urchins: graze algae (slower but thorough)
  Cleaner wrasse: boost adjacent coral health (+0.02)
  Plankton: drift, feed coral polyps (+0.005 health)

Environmental parameters:
  temperature = 26-30C (with optional warming trend)
  acidity (pH) = 7.8-8.1 (with optional acidification trend)
  light_level = 0.8-1.0
  nutrient_level = 0.3-0.7 (high nutrients favor algae)
```

**What to look for** — "Healthy Reef" shows a balanced ecosystem with branching coral (YY) and massive coral (OO) dominating. "Bleaching Event" (starting at 29C with warming trend) triggers white bleached patches ([]); watch whether the reef recovers or flips to dead coral (##) colonized by algae (,,). "Algal Takeover" demonstrates what happens when herbivore fishing removes algae grazers. "Crown-of-Thorns Outbreak" shows coral-eating starfish (XX) devastating reef structure. Heat waves ('h' key) and herbivore additions ('f' key) let you intervene in real time.

**References**
- Hughes, T. P. et al. "Global warming and recurrent mass bleaching of corals." *Nature* 543 (2017): 373-377. https://doi.org/10.1038/nature21707
- Mumby, P. J. et al. "Thresholds and the resilience of Caribbean coral reefs." *Nature* 450 (2007): 98-101. https://doi.org/10.1038/nature06861

---

## Ecosystem Evolution & Speciation

**Background** — This mode simulates macro-evolution on a landscape scale. Populations spread across varied biomes (grassland, forest, desert, tundra, mountain, ocean), adapt to local conditions through trait evolution, and speciate through geographic isolation (allopatric speciation) or niche divergence (sympatric speciation). The model incorporates heritable multi-dimensional traits (size, speed, camouflage, thermal tolerance, aquatic affinity, aggression, fertility), multiple trophic levels (producer, herbivore, predator, apex), and emergent food webs. Environmental events — continental drift, climate shifts, volcanic eruptions, and mass extinctions — reshape the evolutionary landscape.

**Formulation** — Species populations occupy grid cells across a generated biome landscape:

```
Biome generation:
  Value-noise heightmap (5 octaves of smoothing) -> elevation
  Water threshold = 1 - land_pct; mountain threshold by mountain_pct
  Latitude-dependent biome assignment:
    Low latitude: desert; mid: forest; high: tundra
    Rivers flow downhill from mountains; swamps in low-lying areas
  Carrying capacity per biome: grassland=1.0, forest=0.8, desert=0.15, ocean=0.3, etc.
  Movement cost: grassland=1, forest=2, mountain=8, volcanic=10

Species traits (8 continuous values, heritable with Gaussian mutation):
  size (0.1-5.0), speed (0.1-3.0), camouflage (0-1), cold_tolerance (0-1),
  heat_tolerance (0-1), aquatic (0-1), aggression (0-1), fertility (0.2-3.0)

Fitness = biome_match(traits) * competition_factor * predation_survival
  Biome match depends on trait-biome alignment (e.g., aquatic for ocean)

Speciation:
  Allopatric: populations separated by barriers accumulate genetic distance
  Sympatric: trait divergence within a population exceeds threshold
  New species get unique ID, inheriting parent traits with variation

Trophic levels: Producer(0), Herbivore(1), Predator(2), Apex(3)
  Predation: higher-trophic species consume lower-trophic
  Rare trophic level shifts through extreme trait mutation

Events:
  Continental drift: landscape shifts mid-simulation
  Mass extinction: kill fraction of all populations at specified generation
  Climate shift: gradual temperature change affecting biome suitability
```

**What to look for** — "Island Archipelago" produces Darwin's-finches-like radiation: one founder species diversifies into specialists on each island. "Continental Drift" splits a population and shows divergent evolution on separated landmasses. "Mass Extinction & Recovery" at generation 150 wipes out most species, then survivors radiate into empty niches. The phylogenetic tree (when displayed) shows branching patterns: long branches indicate evolutionary stasis, rapid branching signals adaptive radiation. Species counts and extinction events reveal punctuated equilibrium dynamics.

**References**
- Mayr, E. *Systematics and the Origin of Species.* Columbia University Press, 1942. https://doi.org/10.4159/harvard.9780674431430
- Gavrilets, S. *Fitness Landscapes and the Origin of Species.* Princeton University Press, 2004. https://doi.org/10.1515/9780691187051

---

## Mycelium Network / Wood Wide Web

**Background** — Mycorrhizal fungi form vast underground networks connecting tree roots, enabling nutrient exchange and chemical signaling — the "Wood Wide Web" popularised by Suzanne Simard's research. This simulation renders a side-view cross-section of forest soil where fungal hyphae branch through soil layers, form mycorrhizal connections with tree roots, and shuttle carbon, phosphorus, and nitrogen between trees. "Mother trees" (mature, well-connected) become network hubs that support seedlings and stressed neighbors. Seasonal cycles drive growth, fruiting (mushroom emergence), and winter dormancy.

**Formulation** — A layered 2D grid with mobile nutrient packets:

```
Grid layers (top to bottom):
  Air -> Canopy/Trunk -> Surface (litter) -> Topsoil -> Subsoil -> Clay -> Rock

Cell types:
  HYPHA (~~): fungal strand, grows through soil toward roots and nutrients
  HYPHA_HUB (@@): thick junction where multiple hyphae meet
  MYCORRHIZA (<>): root-hypha interface (nutrient exchange point)
  ROOT (rr): tree root network
  ROOT_TIP (r>): actively growing root tip
  ORGANIC (%%): fallen leaves/wood
  DECOMPOSING (%%): organic matter being broken down
  MUSHROOM (/\): fruiting body (emerges on surface when conditions right)

Nutrient packets (mobile entities):
  Carbon (C): flows from tree to fungus (photosynthate payment)
  Phosphorus (P): flows from fungus to tree (mineral nutrient)
  Nitrogen (N): flows from fungus to tree (mineral nutrient)
  Signal (!): chemical distress signal from stressed trees
  Water (o): percolates downward through soil

Seasonal cycle (80 steps per season):
  Spring: growth_factor=1.3, new root tips, hyphae extend
  Summer: growth_factor=1.0, peak nutrient exchange
  Autumn: growth_factor=0.6, leaf fall (organic matter), mushroom fruiting
  Winter: growth_factor=0.15, dormancy, reduced activity

Moisture model:
  moisture_at_depth = base_moisture * (0.5 + 0.8 * depth_fraction)
  Hypha growth requires moisture > threshold
  Water pockets scattered in deeper soil

Key parameters per preset:
  num_trees (5-8), tree_maturity (0.2-0.9), hypha_density (0.02-0.12)
  soil_moisture (0.2-0.75), decomposer_rate (0.01-0.06), growth_rate (0.5-1.8)
```

**What to look for** — "Old-Growth Forest" starts with dense networks already connecting mature trees — watch nutrient packets flow along hyphal highways. "Young Plantation" builds connections from scratch — observe the slow, branching exploration of hyphae seeking root tips. "Drought Stress" triggers distress signals (!) that redirect nutrient flow toward struggling trees. "Fallen Giant" shows decomposers feasting on organic matter, recycling nutrients back into the network. Mushroom fruiting bodies (/\) appear on the surface in autumn when the underground mycelium is well-fed. Toggle views to see moisture distribution and nutrient flow paths.

**References**
- Simard, S. W. et al. "Net transfer of carbon between ectomycorrhizal tree species in the field." *Nature* 388 (1997): 579-582. https://doi.org/10.1038/38839
- Beiler, K. J. et al. "Architecture of the wood-wide web." *New Phytologist* 185 (2010): 543-553. https://doi.org/10.1111/j.1469-8137.2009.03069.x

---

## Primordial Soup / Origin of Life

**Background** — This mode simulates abiogenesis — the transition from prebiotic chemistry to the first living systems. Near hydrothermal vents, minerals catalyze the formation of simple organic monomers, which polymerize into chains (proto-RNA), develop autocatalytic replication, self-assemble into lipid vesicles, and ultimately combine into protocells capable of division and Darwinian evolution. The simulation draws on multiple origin-of-life hypotheses: the RNA World (Gilbert 1986), the metabolism-first iron-sulfur world (Wachtershauser 1988), and the lipid-world/membrane-first hypothesis.

**Formulation** — A 2D ocean grid with hydrothermal vents drives a hierarchy of chemical emergence:

```
Chemical progression:
  mineral -> monomer -> polymer -> replicator
  lipid -> vesicle + replicator -> PROTOCELL -> division

Vent activity:
  Vents produce minerals in adjacent cells (probability 0.15)
  Minerals -> monomers near vents (probability 0.05 * temp_modifier)

Temperature modifier:
  T < 0:   0.3 (ice slows but concentrates)
  T 0-30:  0.5 + T/60
  T 30-80: 1.0
  T > 80:  max(0.3, 1.0 - (T-80)/100)

Polymerization:
  Monomer with >= 2 monomer neighbors + energy > 0.2:
    probability = polymerize_rate * temp_mod * energy
    Consumes one adjacent monomer

  Ice concentration: monomers near >= 2 ice cells polymerize 1.5x faster

Replicator formation:
  Polymer with >= 1 polymer/replicator neighbor + energy > 0.3:
    probability = replicate_rate * 0.3 * temp_mod * energy

Self-replication:
  Replicator with >= 2 monomer neighbors:
    probability = replicate_rate * temp_mod
    Copy placed in adjacent water; monomer consumed
    UV degrades replicators (probability uv * 0.02)

Vesicle assembly:
  Lipid with >= 3 lipid neighbors:
    probability = lipid_assemble_rate * temp_mod
    Consumes 2 adjacent lipids

Protocell formation:
  Vesicle adjacent to replicator:
    probability = 0.08 * temp_mod -> PROTOCELL
    Consumes the replicator

Protocell division:
  energy > 120 and age > 10:
    Split into two protocells in adjacent water
    Daughter inherits fitness with possible mutation:
      fitness += uniform(-0.15, 0.2)
      genome_length += choice(-1, 0, 1)

Energy at position:
  base = max(0.01, (temperature + 20) / 120) * 0.1
  For each vent: base += vent_energy / (1 + distance * 0.3)
  Capped at 1.0
```

**What to look for** — "Hydrothermal Vent Field" shows the full abiogenesis pathway: watch minerals (::) become monomers (..), polymerize into chains (~~), evolve into replicators (rr), while lipids (oo) assemble into vesicles (()) that capture replicators to form protocells (@@). Protocells pulse with color as they metabolize and divide. "Frozen Comet Lake" demonstrates the ice-concentration hypothesis: freeze-thaw cycles force monomers together, accelerating polymerization. Lightning strikes ('l') inject bursts of organic molecules. Track the statistics: peak protocells, total divisions, and maximum generation depth reveal whether your primordial soup has crossed the threshold from chemistry to life.

**References**
- Gilbert, W. "Origin of life: The RNA world." *Nature* 319 (1986): 618. https://doi.org/10.1038/319618a0
- Martin, W. et al. "Hydrothermal vents and the origin of life." *Nature Reviews Microbiology* 6 (2008): 805-814. https://doi.org/10.1038/nrmicro2022

---

## Firefly Synchronization & Bioluminescence

**Background** — In the mangrove forests of Southeast Asia, thousands of male fireflies (*Pteroptyx malaccae*) flash in perfect unison — a phenomenon so striking that early Western observers refused to believe it was real. The mathematical explanation came from Peskin (1975), who modeled cardiac pacemaker cells as integrate-and-fire oscillators that advance each other's phase upon firing, and from Mirollo & Strogatz (1990), who proved that a population of such oscillators will *always* synchronize regardless of initial conditions, given sufficient coupling. The simulation implements this model with ecological grounding: species-specific flash patterns, spatial coupling with line-of-sight occlusion, predator-prey dynamics via *Photuris* femme fatale mimicry, and the Kuramoto order parameter as a real-time measure of collective coherence.

**Formulation** — Each firefly carries a phase variable φ ∈ [0, 1] that increments at its natural frequency ω each tick:

```
Phase dynamics (per tick):
  φ_i(t+1) = φ_i(t) + ω_i

Flash condition:
  If φ_i ≥ 1.0:
    FLASH — emit light pulse, reset φ_i = 0, enter refractory cooldown (3 ticks)

Mirollo-Strogatz coupling (on seeing a flash from firefly j):
  Δφ_i = ε / (1 + d_ij * 0.15)     if same species: × 1.5
  φ_i = min(φ_i + Δφ_i, 1.0)

Where:
  ω_i    = natural frequency (species-dependent, ~0.015–0.020 + Gaussian noise)
  ε      = coupling strength (preset-dependent, 0.03–0.08)
  d_ij   = Euclidean distance between fireflies i and j
  Coupling requires: d_ij ≤ perception_radius AND line-of-sight not blocked by trees

Species flash patterns (on/off fractions within one cycle):
  P. carolinus:  single pulse     [(0.00, 0.12)]
  P. pyralis:    double blink     [(0.00, 0.08), (0.15, 0.23)]
  P. consimilis: rhythmic triplet [(0.00, 0.06), (0.12, 0.18), (0.24, 0.30)]

Kuramoto order parameter (global sync measure):
  R(t) = (1/N) |Σ_i exp(i·2π·φ_i)|
  R = 0: fully desynchronized (uniform phase distribution)
  R = 1: perfectly synchronized (all phases identical)

Predator (Photuris femme fatale):
  - Does not couple (ε = 0)
  - Mimics flash pattern of a randomly chosen prey species
  - Moves toward attracted prey at speed 0.5/tick
  - Kills on contact (distance < 1.5)
  - Switches mimic species with probability 0.01/tick
```

Spatial efficiency is achieved via grid-based hashing (4×4 cell buckets) for O(n·k) neighbor lookup. Line-of-sight is approximated by checking the midpoint between flasher and observer for tree occlusion (for distances > 3).

**What to look for** — In "Southeast Asian Mangrove," watch the Kuramoto order parameter R climb from ~0.2 (random phases) toward 0.9+ (near-perfect synchrony) over 100–200 generations. The Sync Graph view shows this as a rising curve with a phase-distribution histogram narrowing from uniform to a sharp peak. Switch to Nightscape view to see synchronization waves spreading outward from initial clusters — first local neighborhoods lock in, then adjacent groups merge, until the entire field pulses as one. In "Appalachian Meadow," three species synchronize independently at different frequencies, producing a polyphonic light show. "Femme Fatale Hunting" adds red predator glyphs stalking through the meadow — watch the kill counter rise as *Photuris* mimics successfully lure prey. "Desynchronization Shock" starts fully synced, applies a random phase perturbation at generation 80, and lets you observe recovery dynamics — how quickly does R return to 1.0?

**References**
- Mirollo, R. E. & Strogatz, S. H. "Synchronization of pulse-coupled biological oscillators." *SIAM Journal on Applied Mathematics* 50 (1990): 1645-1662. https://doi.org/10.1137/0150098
- Peskin, C. S. *Mathematical Aspects of Heart Physiology.* Courant Institute, NYU, 1975.
- Strogatz, S. H. *Sync: The Emerging Science of Spontaneous Order.* Hyperion, 2003.
- Buck, J. "Synchronous rhythmic flashing of fireflies. II." *Quarterly Review of Biology* 63 (1988): 265-289. https://doi.org/10.1086/415929
- Kuramoto, Y. *Chemical Oscillations, Waves, and Turbulence.* Springer, 1984. https://doi.org/10.1007/978-3-642-69689-3
