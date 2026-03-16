# Particle & Swarm Systems

Emergent collective behavior from simple individual rules — flocking, foraging, and self-organization.

---

## Active Matter

### Background

Active matter is a class of non-equilibrium systems composed of self-propelled units that extract energy from their environment and convert it into directed motion. Unlike passive particles governed by detailed balance, active particles break time-reversal symmetry at the individual level, producing collective phenomena with no equilibrium analogue. The field spans biological systems (bacterial suspensions, cytoskeletal filaments, bird flocks) and synthetic ones (Janus colloids, vibrated granular rods, light-activated swimmers).

Two landmark theoretical frameworks define the field. The Vicsek model (1995) showed that point particles with constant speed and local alignment interactions undergo a genuine phase transition from disordered gas to long-range-ordered flock — remarkable because the Mermin-Wagner theorem forbids such order in equilibrium 2D systems. Motility-induced phase separation (MIPS), formalized by Cates and Tailleur (2015), demonstrated that particles which simply slow down in crowds will spontaneously phase-separate into dense liquid-like clusters and dilute gas, with no attractive interactions required.

### Formulation

Each particle has position (r, c) on a toroidal domain, heading angle θ, velocity (vr, vc), and fuel level f. The simulation uses spatial hashing for O(N) neighbor lookup.

```
Per-timestep update for particle i:

1. NEIGHBOR SEARCH (spatial grid, cell_size = max(align_r, repel_r)):
   For each neighbor j within grid cell and 8 adjacent cells:
     dr = r_j - r_i  (with toroidal minimum-image convention)
     dc = c_j - c_i
     dist = sqrt(dr² + dc²)

2. ALIGNMENT TORQUE (if dist < align_r):
   Polar:    accumulate sin(θ_j), cos(θ_j)
   Nematic:  accumulate sin(2θ_j), cos(2θ_j)  (double-angle trick)
   target = atan2(sin_sum, cos_sum)  [÷2 for nematic]
   θ_new += align_w * angular_diff(target, θ) * 0.3

3. SHORT-RANGE REPULSION (if dist < repel_r):
   overlap = 1 - dist/repel_r
   F_repel -= (dr, dc)/dist * overlap * repel_w

4. CONTRACTILE/EXTENSILE DIPOLE (if |contract| > 0 and dist < align_r):
   Project self-propulsion direction onto pair axis:
     dot = e_i · n_ij
   Contractile (>0) pulls along axis, extensile (<0) pushes:
     F_dipole += n_ij * contract * dot / (dist + 0.5)

5. SELF-ROTATION: θ_new += spin_w

6. RUN-AND-TUMBLE: with probability τ, θ_new = random in [0, 2π)

7. ANGULAR NOISE: θ_new += N(0, η)

8. MIPS SLOWDOWN (when τ > 0 and neighbors present):
   local_density = n_neighbors / (π * align_r²)
   prop_speed = v₀ / (1 + 5 * local_density)

9. VELOCITY UPDATE:
   v_new = propulsion + F_repel + F_dipole
   v_new = v_new * (1 - friction) + v_old * friction * 0.5
   |v_new| clamped to 3 * v₀

10. POSITION UPDATE (toroidal):
    r_new = (r + vr) mod rows
    c_new = (c + vc) mod cols
```

The order parameter ψ quantifies collective alignment: ψ = |Σ exp(iθ)| / N for polar (Vicsek), ψ = |Σ exp(2iθ)| / N for nematic. ψ → 1 indicates long-range order; ψ → 0 indicates disorder.

### Presets

- **Bacterial Turbulence**: Dense pushers (extensile dipoles, contract = −0.3) with nematic alignment. Produces chaotic vortex streets and jet-like flows characteristic of dense bacterial suspensions like *B. subtilis*.
- **Active Nematics**: Rod-like extensile particles (contract = −0.5) with strong nematic alignment. Nucleates ±½ topological defect pairs that unbind and annihilate — the hallmark of active nematic turbulence observed in microtubule-kinesin mixtures.
- **Motility-Induced Clustering**: Run-and-tumble particles (τ = 0.05) with no alignment interaction. Pure MIPS: particles slow down in crowds, accumulate, slow further — a positive feedback loop producing dense liquid drops in dilute gas.
- **Vicsek Flocking**: Polar aligning particles with moderate noise. Demonstrates the Vicsek phase transition: below critical noise, the system orders into a coherent flock with giant number fluctuations.
- **Active Spinner Gas**: Self-rotating disks (spin_w = 0.3) with odd-elastic collisions. Models systems with broken parity symmetry, producing chiral edge currents and odd-viscosity effects.
- **Contractile Gel**: Puller particles (contract = +0.5) forming asters and contractile networks, modeling actomyosin gel dynamics where molecular motors pull filaments inward.

### What to look for

In **Bacterial Turbulence**, watch for turbulent vortex patterns with a characteristic length scale — switch to Vorticity view (v) to see the counter-rotating vortex pairs. **Active Nematics** produces pairs of comet-shaped (+½) and trefoil (−½) topological defects that self-propel and annihilate; the defect density reaches a statistical steady state. **MIPS** shows dramatic phase separation: initially uniform particles coarsen into a few large dense clusters via Ostwald ripening, with a sharp interface between dense and dilute phases visible in Density view. **Vicsek Flocking** exhibits a sharp order-disorder transition — use e/E to tune noise through the critical point and watch the order parameter ψ jump. In **Spinner Gas**, particles form rotating clusters with chiral symmetry breaking. **Contractile Gel** produces aster-like radial structures where particles converge.

### References

- Vicsek, T., Czirók, A., Ben-Jacob, E., Cohen, I. & Shochet, O. "Novel type of phase transition in a system of self-driven particles." *Physical Review Letters*, 75(6), 1226-1229, 1995. https://doi.org/10.1103/PhysRevLett.75.1226
- Cates, M. E. & Tailleur, J. "Motility-induced phase separation." *Annual Review of Condensed Matter Physics*, 6, 219-244, 2015. https://doi.org/10.1146/annurev-conmatphys-031214-014710
- Marchetti, M. C., et al. "Hydrodynamics of soft active matter." *Reviews of Modern Physics*, 85(3), 1143-1189, 2013. https://doi.org/10.1103/RevModPhys.85.1143

---

## Granular Dynamics

### Background

Granular materials — sand, grains, powders, cereals — are sometimes called "the fourth state of matter" because they exhibit solid-like, liquid-like, and gas-like behavior depending on conditions, yet fit none of these categories. A sandpile can support weight like a solid (via force chains), flow like a liquid (avalanches, hopper discharge), or behave like a gas (dilute inelastic particles). The Discrete Element Method (DEM), introduced by Cundall and Strack (1979), models each grain as an individual particle subject to contact forces, gravity, and friction. From these simple ingredients emerge rich phenomena: force chain networks (branching stress paths visible under photoelastic imaging), jamming transitions (where a flowing granular medium suddenly arrests), avalanche cascades exhibiting self-organized criticality, arching and clogging in hoppers, and the Brazil nut effect (large grains rising to the top when shaken via granular convection).

This mode fills the gap between the project's rule-based Falling Sand cellular automaton (which uses material-type swap rules) and its continuum fluid modes (Navier-Stokes, LBM). Here every grain is a physical particle with Hertzian contact, Coulomb friction, and inertia.

### Formulation

Each grain has position (r, c), velocity (vr, vc), radius, mass (proportional to area, m = πr²), accumulated contact force magnitude, and a large-grain flag. Spatial hashing (cell size 2.0) provides O(N) neighbor lookup.

```
Contact force between grains i and j (if overlapping):
    dr = r_j - r_i,  dc = c_j - c_i
    dist = sqrt(dr² + dc²)
    overlap = (rad_i + rad_j) - dist

    Normal direction: n = (dr, dc) / dist

    Hertzian normal force:
        F_n = k * overlap^1.5                    (nonlinear spring)

    Normal damping (dashpot):
        v_rel_n = (v_j - v_i) · n
        F_damp = -0.3 * k * v_rel_n * sqrt(overlap)
        F_n_total = max(0, F_n + F_damp)         (no tensile contact)

    Coulomb friction (regularized):
        v_rel_t = (v_j - v_i) · t                (tangential relative velocity)
        F_t_max = μ * F_n_total                   (Coulomb limit)
        F_t = clamp(-0.5 * k * v_rel_t * sqrt(overlap), -F_t_max, F_t_max)

    Apply equal and opposite forces to i and j.

Wall collisions:
    Axis-aligned walls: same Hertzian + friction formulation
    Line-segment walls (hopper funnel): project particle center onto segment,
        compute overlap from closest point, apply normal + friction forces

Velocity and position update (symplectic Euler):
    a = gravity + F_contact / mass + shake_oscillation
    v_new = (v + a) * (1 - damping)
    |v_new| clamped to 3.0
    r_new = r + v_new
    Hard boundary clamp with restitution coefficient

Shaking (Brazil nut):
    shake_offset = A * sin(gen * ω * 2π)         (sinusoidal vertical oscillation)

Drum rotation:
    gravity direction rotates: θ += ω_drum per step
    g_r = |g| * cos(θ),  g_c = |g| * sin(θ)
```

Force chain visualization accumulates contact force magnitudes on a grid with 0.7× decay per step for visual persistence.

### Presets

- **Hopper Flow**: Funnel geometry with converging walls and a narrow outlet. Grains arch and clog at the aperture — tilt gravity laterally (t/T) to restart flow. Demonstrates the Beverloo scaling law for granular discharge and the intermittent clog-flow transition.
- **Avalanche Slope**: Sandpile initialized near the angle of repose. Adding grains (click) triggers cascading avalanches with power-law size distributions characteristic of self-organized criticality (Bak-Tang-Wiesenfeld).
- **Brazil Nut Effect**: Mixed small and large grains under vertical shaking. Large grains (shown as yellow diamonds) migrate to the surface via granular convection cells — the same mechanism that sorts breakfast cereal in the box.
- **Force Chain Network**: Densely packed grains under strong gravity with high stiffness. Switch to Force Chains view (v) to see the branching stress network — bright filaments carry most of the load while many grains bear almost none, as observed in photoelastic disk experiments.
- **Granular Gas**: Dilute inelastic particles with no gravity and high restitution. Exhibits clustering instability — initially uniform particles spontaneously form dense clumps separated by voids, driven by the inelastic collapse mechanism where energy dissipation concentrates particles.
- **Drum Rotation**: Grains in a container with slowly rotating gravity direction, modeling a rotating drum. Produces radial segregation (large grains migrate outward), avalanching surface flow, and S-shaped dynamic angle of repose.

### What to look for

In **Hopper Flow**, watch for the dramatic transition between free flow and complete arrest — a single arch of 5–8 grains spanning the aperture can halt all flow. Tilting gravity breaks the arch and restarts discharge. In **Force Chain Network**, the force chains view reveals that stress transmission in granular matter is highly heterogeneous: a few branching filaments carry enormous loads while adjacent grains are nearly stress-free. The **Brazil Nut** preset shows convection-driven size segregation developing over ~100 generations of shaking — large grains ride convection cells upward. **Granular Gas** starts uniform but rapidly develops dense clusters separated by expanding voids, a hallmark of inelastic collapse. **Avalanche Slope** demonstrates self-organized criticality: small grain additions produce avalanches spanning a wide range of sizes.

### References

- Cundall, P. A. & Strack, O. D. L. "A discrete numerical model for granular assemblies." *Géotechnique*, 29(1), 47-65, 1979. https://doi.org/10.1680/geot.1979.29.1.47
- Jaeger, H. M., Nagel, S. R. & Behringer, R. P. "Granular solids, liquids, and gases." *Reviews of Modern Physics*, 68(4), 1259-1273, 1996. https://doi.org/10.1103/RevModPhys.68.1259
- Bak, P., Tang, C. & Wiesenfeld, K. "Self-organized criticality: An explanation of the 1/f noise." *Physical Review Letters*, 59(4), 381-384, 1987. https://doi.org/10.1103/PhysRevLett.59.381

---

## Falling Sand

### Background

Falling sand simulations belong to the family of cellular automaton models that approximate granular material dynamics under gravity. Popularized in the early 2000s through browser-based "falling sand games," the genre traces its conceptual roots to lattice gas automata and granular physics. Each cell contains an element type — sand, water, fire, stone, oil, plant, or steam — and the system's richness arises from pairwise interaction rules between these materials.

### Formulation

The simulation processes cells bottom-to-top with randomized column order to avoid directional bias. Each element obeys type-specific rules:

```
Element behaviors (per tick):

SAND:   Try move to (r+1, c). If blocked, try diagonal (r+1, c +/- 1).
        Swaps with water or oil below (density sorting).

WATER:  Try fall (r+1, c), then diagonal, then flow sideways (r, c +/- 1).
        Sinks below oil (density: water > oil).

FIRE:   Rises upward with P(move_up) = 0.7, lateral drift in {-1, 0, 0, 1}.
        Lifetime = 12 + rand(0..8) ticks.
        Ignites adjacent plant (P = 0.4), oil (P = 0.5).
        Evaporates adjacent water to steam (P = 0.08).
        Dying fire produces steam with P = 0.2.

PLANT:  Grows into empty neighbor cells when adjacent to water (P = 0.05).
        Growth directions: up, diagonal-up, sideways.

OIL:    Liquid behavior (fall, diagonal, sideways). Floats above water.
        Highly flammable (fire ignition P = 0.5).

STEAM:  Rises with lateral drift. Condenses to water after 15 + rand(0..10) ticks
        with P(condense) = 0.4, otherwise vanishes.

STONE:  Static. Immovable barrier.
```

### What to look for

Watch sand pile into natural-looking heaps and slide along diagonal slopes. Water finds its own level and flows around obstacles, while oil floats on top forming a visible density interface. Fire propagates through plant matter in realistic wavefronts, and the steam-condensation cycle creates a simple water cycle. The "hourglass" preset demonstrates granular flow through a narrow aperture, a classic problem in granular physics.

### References

- Bak, P., Tang, C., & Wiesenfeld, K. "Self-organized criticality." *Physical Review A*, 38(1), 364-374, 1988. https://doi.org/10.1103/PhysRevA.38.364
- Batty, M. "Cities and Complexity." MIT Press, 2005. (Chapter on cellular automata and urban simulation.) https://mitpress.mit.edu/books/cities-and-complexity

---

## Boids Flocking

### Background

Boids is Craig Reynolds' 1986 algorithm for simulating the coordinated motion of animal groups — bird flocks, fish schools, insect swarms. Reynolds showed that three local steering rules, applied independently by each agent, are sufficient to produce globally coherent flocking behavior without any centralized control. The model became foundational in computer graphics (used in films from *Batman Returns* onward) and remains central to swarm intelligence research.

### Formulation

Each boid has position (r, c) and velocity (vr, vc) on a toroidal grid. At each step, three steering forces are computed using pairwise toroidal distances:

```
For each boid i, accumulate steering from all neighbors j:

SEPARATION (radius R_s, weight W_s):
    If dist(i,j) < R_s:  steer_sep += -(dr, dc) / dist^2

ALIGNMENT (radius R_a, weight W_a):
    If dist(i,j) < R_a:  accumulate velocity of j
    steer_ali = (avg_neighbor_vel - vel_i) * W_a

COHESION (radius R_c, weight W_c):
    If dist(i,j) < R_c:  accumulate relative position of j
    steer_coh = avg_neighbor_offset * W_c * 0.1

Velocity update:
    v_new = v_old + (steer_sep * W_s + steer_ali + steer_coh) * 0.1
    |v_new| clamped to max_speed
    Minimum speed enforced at 0.1 (random direction if below)

Position update (toroidal wrap):
    pos_new = (pos_old + v_new) mod grid_size
```

Default parameters: R_s = 3.0, R_a = 8.0, R_c = 10.0, W_s = 1.5, W_a = 1.0, W_c = 1.0, max_speed = 1.0. Presets include configurations for tight murmurations, slow fish schools, fast swarms, and long-range migratory flocks.

### What to look for

Observe how coherent flocking emerges from purely local interactions. Increasing separation radius fragments the flock into smaller groups. Raising alignment weight produces long parallel streams. Boosting cohesion creates tight, almost spherical clusters. The transition between ordered flocking and disordered swarming as parameters change mirrors phase transitions studied in active matter physics.

### References

- Reynolds, C. W. "Flocks, herds and schools: A distributed behavioral model." *ACM SIGGRAPH Computer Graphics*, 21(4), 25-34, 1987. https://doi.org/10.1145/37402.37406
- Vicsek, T., et al. "Novel type of phase transition in a system of self-driven particles." *Physical Review Letters*, 75(6), 1226-1229, 1995. https://doi.org/10.1103/PhysRevLett.75.1226

---

## Particle Life

### Background

Particle Life (also called "Primordial Soup") was popularized by Jeffrey Ventrella and later by Tom Molinari's viral simulations. It extends simple particle systems by assigning each particle a type and defining attraction/repulsion strengths between all type pairs via a random matrix. Despite having no explicit chemistry, the system spontaneously produces lifelike behaviors: clustering, orbiting, chasing, and symbiotic co-rotation that evoke biological organisms.

### Formulation

Each particle has position (r, c), velocity (vr, vc), and a discrete type t in {0, ..., N-1}. An N x N interaction matrix A[i][j] in [-1, 1] defines the force between types. Forces are computed pairwise on a toroidal domain:

```
For each particle pair (i, j) with types (t_i, t_j):
    d = toroidal_distance(i, j)
    if d > max_radius or d < 0.01: skip

    rel_dist = d / max_radius          (normalized to [0, 1])

    Force profile:
        if rel_dist < 0.3:
            force = (rel_dist / 0.3) - 1.0      (short-range repulsion)
        else:
            force = A[t_i][t_j] * (1.0 - |2.0 * rel_dist - 1.3| / 0.7)
            force = clamp(force, -1, 1)

    F_i += normalize(dr, dc) * force * force_scale

Velocity update:
    v_new = (v_old + F) * (1 - friction)
    |v_new| clamped to 2.0

Position update:
    pos_new = (pos_old + v_new) mod grid_size
```

Presets: Primordial Soup (6 types, random rules), Symbiosis (4 types, seed 42), Clusters (3 types, high friction 0.6), Predator-Prey (5 types, low friction 0.3), Galaxy (4 types, large radius 25), Chaos (8 types, high force 0.07).

### What to look for

The force profile is key: universal short-range repulsion prevents collapse, while the type-dependent mid-range zone creates the diversity. With certain random matrices, "organisms" spontaneously form — tight clusters that orbit each other, predator-type particles chasing prey-types, or stable symbiotic pairs. Pressing `x` re-randomizes the interaction matrix, dramatically reshaping the ecosystem in real time. Higher friction yields more stable structures; lower friction produces chaotic, high-energy dynamics.

### References

- Ventrella, J. "Clusters." 2017. https://ventrella.com/Clusters/
- Chan, B. W.-C. "Lenia: Biology of Artificial Life." *Complex Systems* 28(3), 2019. https://doi.org/10.25088/ComplexSystems.28.3.251

---

## Physarum Slime Mold

### Background

This model simulates the transport network behavior of *Physarum polycephalum*, a slime mold that constructs near-optimal networks between food sources. Jeff Jones (2010) developed the agent-based model used here, where mobile agents deposit a chemical trail, sense the trail gradient, and steer toward higher concentrations. The resulting patterns — branching networks, rings, and Voronoi-like tessellations — have been shown to approximate minimum spanning trees and even replicate the Tokyo rail network.

### Formulation

Each agent has position (r, c) and a heading angle theta. A 2D trail map T[r][c] stores chemical concentration in [0, 1].

```
Agent update (sense-rotate-move-deposit):
    1. SENSE at three positions ahead:
       F_left  = T[pos + sensor_dist * dir(theta + sensor_angle)]
       F_center = T[pos + sensor_dist * dir(theta)]
       F_right = T[pos + sensor_dist * dir(theta - sensor_angle)]

    2. ROTATE toward strongest signal:
       if F_center > F_left and F_center > F_right:  keep heading
       elif F_center < F_left and F_center < F_right: random turn +/- turn_speed
       elif F_left > F_right:  theta += turn_speed
       elif F_right > F_left:  theta -= turn_speed

    3. MOVE: pos_new = pos + move_speed * dir(theta)   (toroidal wrap)

    4. DEPOSIT: T[pos_new] = min(1.0, T[pos_new] + deposit_amount)

Trail diffusion and decay (per tick):
    T_new[r][c] = max(0, (3x3 box blur of T at (r,c)) / 9 - decay_rate)
```

Parameters: sensor_angle (SA), sensor_distance (SD), turn_speed (TS), move_speed (MS), deposit amount, decay rate. Default Physarum preset: SA=0.40, SD=9.0, TS=0.45, deposit=0.5, decay=0.015.

### What to look for

Initially chaotic agents rapidly self-organize into branching network structures. The sensor angle controls network topology: narrow angles (SA < 0.3) produce tight, rope-like strands, while wider angles yield broader, more diffuse patterns. Higher decay rates force agents to reinforce only the strongest paths, producing sparser networks. The system exhibits positive feedback — trails attract more agents, which deposit more trail — counterbalanced by decay, creating a dynamic equilibrium.

### References

- Jones, J. "Characteristics of pattern formation and evolution in approximations of Physarum transport networks." *Artificial Life*, 16(2), 127-153, 2010. https://doi.org/10.1162/artl.2010.16.2.16202
- Tero, A., et al. "Rules for biologically inspired adaptive network design." *Science*, 327(5964), 439-442, 2010. https://doi.org/10.1126/science.1187936

---

## Ant Colony Optimization

### Background

Ant Colony Optimization (ACO) was introduced by Marco Dorigo in 1992, inspired by the foraging behavior of real ant colonies. Ants deposit pheromone trails when returning from food sources, and other ants probabilistically follow stronger trails. This positive feedback loop, balanced by pheromone evaporation, allows the colony to collectively discover and reinforce efficient paths. ACO has been applied to combinatorial optimization problems including the traveling salesman problem and network routing.

### Formulation

Ants have position (r, c), heading angle, and a boolean food-carrying flag. A pheromone grid P[r][c] stores concentration values. Food sources have position and finite quantity.

```
Ant behavior (per tick):

IF carrying food (returning to nest):
    1. DEPOSIT pheromone: P[r][c] += deposit_strength  (capped at 1.0)
    2. STEER toward nest:
       target_angle = atan2(nest_r - r, nest_c - c)
       heading += (target_angle - heading) * 0.3 + rand(-0.2, 0.2)
    3. If within 2.0 of nest: drop food, increment counter, random new heading

ELSE (searching for food):
    1. SENSE pheromone in three directions (dist=3.0, angle=0.5 rad):
       F_left  = P[ahead_left]
       F_center = P[ahead]
       F_right = P[ahead_right]
    2. STEER: turn 0.3 rad toward stronger pheromone signal
       + random wander: heading += rand(-0.15, 0.15)
    3. If within 2.5 of food source with quantity > 0:
       pick up food, food.quantity -= 1, turn toward nest

MOVE: pos += dir(heading) * 1.0  (toroidal wrap)

Pheromone update:
    blended = P[r][c] * (1 - diffusion) + (3x3 avg) * diffusion
    P_new[r][c] = max(0, blended - evaporation)
```

Parameters: evaporation rate, deposit strength, diffusion rate. Depleted food sources are removed.

### What to look for

Watch the initial random wandering phase give way to structured trail formation. Once the first ant discovers food and returns, its pheromone trail biases nearby ants, creating a positive feedback loop. Over time, the shortest paths to food sources accumulate the strongest pheromone, while longer paths evaporate. Increasing evaporation makes the colony more exploratory; decreasing it makes trails more persistent but risks locking into suboptimal paths.

### References

- Dorigo, M. "Optimization, Learning and Natural Algorithms." PhD Thesis, Politecnico di Milano, 1992. https://en.wikipedia.org/wiki/Ant_colony_optimization_algorithms
- Dorigo, M. & Stutzle, T. "Ant Colony Optimization." MIT Press, 2004. https://mitpress.mit.edu/books/ant-colony-optimization

---

## N-Body Gravity

### Background

The N-body gravitational problem — computing the motion of N masses under mutual gravitational attraction — is one of the oldest problems in computational physics, dating to Newton's work on planetary orbits. No general closed-form solution exists for N > 2 (proved by Poincare), making numerical integration essential. This simulation uses the velocity Verlet integrator, a symplectic method that conserves energy better than naive Euler integration, combined with gravitational softening to handle close encounters.

### Formulation

Each body has position (r, c), velocity (vr, vc), and mass m. The simulation uses velocity Verlet (leapfrog) integration:

```
Gravitational acceleration on body i from body j:
    dr = r_j - r_i,  dc = c_j - c_i
    dist^2 = dr^2 + dc^2 + epsilon^2      (softening prevents singularity)
    a_i += G * m_j * (dr, dc) / (dist^2 * sqrt(dist^2))

Velocity Verlet integration (per timestep dt):
    1. Compute accelerations a(t) from current positions
    2. v_half = v(t) + 0.5 * dt * a(t)
    3. r(t+dt) = r(t) + dt * v_half
    4. Compute accelerations a(t+dt) from new positions
    5. v(t+dt) = v_half + 0.5 * dt * a(t+dt)

Collision merging:
    if dist(i,j) < 0.3 + 0.1 * ln(1 + m_i + m_j):
        Merge by conservation of momentum:
        m_new = m_i + m_j
        v_new = (m_i * v_i + m_j * v_j) / m_new
        r_new = (m_i * r_i + m_j * r_j) / m_new

Orbital velocity (circular orbit):
    v = sqrt(G * M_central / r)
```

Parameters: G (gravitational constant, default 1.0), dt (timestep, default 0.02), epsilon (softening, default 0.5). Presets include solar system, binary star, galaxy collision, random cluster, Chenciner-Montgomery figure-eight three-body orbit, and Lagrange point configurations.

### What to look for

The solar system preset demonstrates stable Keplerian orbits with inner planets moving faster than outer ones. The binary star preset shows mutual orbital motion. Galaxy collision produces dramatic tidal tails and merging structures. The figure-eight preset showcases the remarkable Chenciner-Montgomery solution (2000) where three equal masses trace a figure-8 — watch how sensitive it is to perturbation. The Lagrange preset places test particles at the L4/L5 triangular equilibrium points, 60 degrees ahead of and behind a planet.

### References

- Aarseth, S. J. "Gravitational N-Body Simulations." Cambridge University Press, 2003. https://doi.org/10.1017/CBO9780511535246
- Chenciner, A. & Montgomery, R. "A remarkable periodic solution of the three-body problem in the case of equal masses." *Annals of Mathematics*, 152, 881-901, 2000. https://doi.org/10.2307/2661357

---

## Diffusion-Limited Aggregation

### Background

Diffusion-Limited Aggregation (DLA) was introduced by Witten and Sander in 1981 to model growth processes controlled by diffusion. Random walkers undergo Brownian motion until they contact a growing crystal, at which point they stick irreversibly. The resulting structures are branching fractals with a fractal dimension of approximately 1.7 in two dimensions. DLA models phenomena including electrodeposition, mineral dendrites, dielectric breakdown, and bacterial colony growth.

### Formulation

A grid stores crystal cells (positive integer = generation attached) and empty cells (0). Walkers perform random walks until they adhere to the crystal aggregate:

```
Walker step:
    1. Random displacement: dr, dc in {-1, 0, 1} (8-connected)
       Optional bias: if |bias_r| > 0, force dr toward bias with P = |bias_r|
    2. Move: (r, c) += (dr, dc), reject if target is crystal
    3. Adjacency check (8-connected neighborhood):
       if any neighbor is crystal AND rand() < stickiness:
           attach walker to crystal (grid[r][c] = generation)
           update max_radius
    4. Kill walker if dist(walker, center) > spawn_radius + 20

Walker spawning:
    Walkers spawn on a ring at radius = max_crystal_radius + 10
    Maintained at constant population (default 300-500)

Symmetry (snowflake mode, k-fold):
    On attachment at offset (dr, dc) from center:
    for angle = 0, 2*pi/k, ..., 2*pi*(k-1)/k:
        (rr, rc) = center + rotate(dr, dc, angle)
        attach crystal at (rr, rc)
    For k=6: additional mirror reflections for full hexagonal symmetry

Stickiness: P(attach | adjacent) = stickiness parameter (default 1.0)
    Lower stickiness (e.g., 0.7) allows walkers to penetrate deeper,
    producing more branching.
```

Presets: Crystal Growth (single seed), Multi-Seed (5 seeds), Snowflake (6-fold symmetry, stickiness 0.7), Electrodeposition (bottom-edge cathode with upward bias -0.15), Line Seed, Ring Seed.

### What to look for

The fundamental DLA branching pattern arises because outer tips of the crystal are more accessible to random walkers than inner fjords, creating a screening effect that produces fractal branching. Reducing stickiness below 1.0 allows walkers to diffuse past tips into concavities, producing denser, more compact structures. The electrodeposition preset adds a downward drift, creating vertically aligned dendritic structures reminiscent of metal deposition on electrodes. The snowflake preset applies 6-fold rotational symmetry with mirror reflections, generating structures remarkably similar to real ice crystals.

### References

- Witten, T. A. & Sander, L. M. "Diffusion-limited aggregation, a kinetic critical phenomenon." *Physical Review Letters*, 47(19), 1400-1403, 1981. https://doi.org/10.1103/PhysRevLett.47.1400
- Meakin, P. "Fractals, Scaling and Growth Far from Equilibrium." Cambridge University Press, 1998. https://doi.org/10.1017/CBO9780511806179
