# Physics & Waves

From electromagnetic fields to gravitational orbits — continuous physical systems discretized for the terminal.


---

## Wave Equation

**Background** — The 2D wave equation describes how disturbances propagate through elastic media such as membranes, water surfaces, and acoustic fields. Originally studied by d'Alembert in 1747 and extended to two dimensions by Euler, it remains one of the foundational PDEs of mathematical physics. This simulator lets you watch ripples spread, interfere, and reflect across a discrete membrane.

**Formulation** — The simulation uses the standard second-order finite-difference scheme:

```
u_next[r][c] = damping * (2*u[r][c] - u_prev[r][c] + c^2 * Laplacian(u))

Laplacian(u) = u[r-1][c] + u[r+1][c] + u[r][c-1] + u[r][c+1] - 4*u[r][c]

Parameters:
  c       — wave speed (0.05 to 0.50), controls propagation rate
  damping — per-step energy loss (0.95 to 1.0), where 1.0 = lossless
  boundary — "reflect" (Neumann, du/dn=0), "absorb" (Dirichlet, u=0),
             or "wrap" (periodic)
```

Initial conditions include Gaussian center drops (`exp(-(dx^2+dy^2)*2)`), corner pulses, random drops, expanding rings, cross patterns, and a double-slit setup with a continuous plane-wave source at `0.5*sin(t)`.

**What to look for** — Watch circular wavefronts expand from a Gaussian drop, observe interference fringes behind the double slit, and notice how reflecting boundaries create standing waves while absorbing boundaries dissipate energy at the edges. Reducing damping below 1.0 causes the membrane to gradually lose energy, mimicking real material losses.

**References**
- Strikwerda, J.C. *Finite Difference Schemes and Partial Differential Equations*, 2nd ed., SIAM, 2004. https://doi.org/10.1137/1.9780898717938
- Courant, R., Friedrichs, K., and Lewy, H. "On the partial difference equations of mathematical physics," *Mathematische Annalen*, 1928. https://doi.org/10.1007/BF01448839


---

## Ising Model

**Background** — The Ising model, introduced by Wilhelm Lenz in 1920 and solved in 1D by his student Ernst Ising in 1925, is the most studied model in statistical mechanics. Each site on a lattice holds a spin (+1 or -1) that interacts with its nearest neighbors. Despite its simplicity, the 2D Ising model exhibits a genuine phase transition between ordered (ferromagnetic) and disordered (paramagnetic) states at the critical temperature Tc = 2/ln(1+sqrt(2)) ~ 2.269, as solved exactly by Lars Onsager in 1944.

**Formulation** — The simulation uses the Metropolis single-spin-flip algorithm:

```
Hamiltonian:
  H = -J * sum_<ij> s_i * s_j  -  h * sum_i s_i

  J = 1 (coupling constant, implicit)
  h = external magnetic field

Metropolis update (one sweep = N random flip attempts):
  1. Pick random site (r, c)
  2. Compute dE = 2 * s * (sum_4_neighbors + h)
  3. If dE <= 0 or rand() < exp(-dE / T):  flip spin

Observables:
  Magnetization: <m> = (1/N) * sum_i s_i
  Energy/spin:   E/N = (-1/N) * sum_<ij> s_i*s_j  -  (h/N) * sum_i s_i
```

Boundary conditions are periodic (toroidal). Presets span temperatures from T=0.5 (deep ordered phase) to T=5.0 (fully disordered), with external field options.

**What to look for** — Below Tc, large single-color domains form as spins align. Near Tc (~2.27), you see critical fluctuations: fractal-like domain boundaries with long-range correlations. Above Tc, the lattice appears as random noise. Applying an external field biases magnetization even above Tc.

**References**
- Onsager, L. "Crystal statistics. I. A two-dimensional model with an order-disorder transition," *Physical Review*, 1944. https://doi.org/10.1103/PhysRev.65.117
- Newman, M.E.J. and Barkema, G.T. *Monte Carlo Methods in Statistical Physics*, Oxford University Press, 1999. https://global.oup.com/academic/product/9780198517979


---

## Kuramoto Oscillators

**Background** — The Kuramoto model, proposed by Yoshiki Kuramoto in 1975, describes synchronization in populations of coupled oscillators. It has been applied to explain coordinated flashing of fireflies, pacemaker cells in the heart, power-grid synchronization, and neuron firing. The model exhibits a phase transition: below a critical coupling strength, oscillators remain incoherent; above it, they spontaneously synchronize.

**Formulation** — Each oscillator on a 2D grid has a phase theta and a natural frequency omega:

```
dtheta_i/dt = omega_i + (K/4) * sum_j sin(theta_j - theta_i) + noise

  omega_i  — natural frequency, drawn from N(0, freq_spread)
  K        — coupling strength (0.0 to 10.0)
  sum_j    — over 4 nearest neighbors (von Neumann neighborhood, periodic)
  noise    — Gaussian noise with amplitude noise_amp
  dt       — integration time step (0.01 to 0.5)

Order parameter:
  r = |1/N * sum_j exp(i * theta_j)|
  r ~ 0 means incoherence, r ~ 1 means full synchronization
```

Natural frequencies are drawn from a Gaussian distribution. Special initializations include linear phase gradients (traveling waves), spiral patterns (vortex dynamics), and chimera states (half synchronized, half random with different frequency distributions).

**What to look for** — Watch the order parameter r climb as coupling K increases. With "Gentle Sync" (K=0.5), coherent islands slowly emerge. With "Strong Sync" (K=3.0), global synchronization is rapid. The "Chimera State" preset shows the remarkable coexistence of synchronized and desynchronized regions. Phase is rendered as a rainbow color wheel.

**References**
- Kuramoto, Y. "Self-entrainment of a population of coupled nonlinear oscillators," *International Symposium on Mathematical Problems in Theoretical Physics*, Springer, 1975. https://doi.org/10.1007/BFb0013365
- Strogatz, S.H. "From Kuramoto to Crawford: exploring the onset of synchronization in populations of coupled oscillators," *Physica D*, 2000. https://doi.org/10.1016/S0167-2789(00)00094-4


---

## Quantum Walk

**Background** — Quantum walks are the quantum-mechanical analog of classical random walks, first studied by Aharonov, Davidovich, and Zagury in 1993. Unlike classical walkers that diffuse as sqrt(t), quantum walkers spread ballistically as t, offering a quadratic speedup. Quantum walks underpin algorithms for graph search and are a universal model of quantum computation.

**Formulation** — The simulation implements a discrete-time quantum walk on a 2D grid with 4 internal (coin) directions:

```
Each step:
  1. COIN operation — apply a 4x4 unitary to the internal state at each cell
  2. SHIFT operation — translate each direction component one cell

Coin operators:
  Hadamard (H x H):  H[i][j] = (-1)^(bitwise_dot(i,j)) / 2
  Grover diffusion:   G[i][j] = -delta(i,j) + 1/2
  DFT (4x4 Fourier): F[j][k] = omega^(jk) / 2,  omega = exp(i*pi/2)

Shift directions: 0=up(r-1), 1=right(c+1), 2=down(r+1), 3=left(c-1)
Boundaries: periodic (wrap) or absorbing (amplitude lost at edges)

Probability: P(r,c) = sum_d |psi_d(r,c)|^2
Decoherence: with probability p, collapse amplitude to random phase
             preserving magnitude — transitions from quantum to classical
```

**What to look for** — The Hadamard coin produces a characteristic diamond-shaped probability distribution that spreads much faster than classical diffusion. The Grover coin creates a more isotropic pattern. Increasing decoherence gradually transitions the quantum walk into a classical random walk, visible as the sharp interference peaks smear into a smooth Gaussian.

**References**
- Aharonov, Y., Davidovich, L., and Zagury, N. "Quantum random walks," *Physical Review A*, 1993. https://doi.org/10.1103/PhysRevA.48.1687
- Kempe, J. "Quantum random walks: an introductory overview," *Contemporary Physics*, 2003. https://doi.org/10.1080/00107151031000110776


---

## Lightning (Dielectric Breakdown)

**Background** — The Dielectric Breakdown Model (DBM), introduced by Niemeyer, Pietronero, and Wiesmann in 1984, simulates how electrical discharge channels grow through an insulating medium. It explains the branching fractal structure of lightning bolts, electrical treeing in power cables, and Lichtenberg figures. The parameter eta controls the fractal dimension of the resulting pattern.

**Formulation** — The simulation solves for the electrostatic potential and grows the discharge channel probabilistically:

```
1. Solve Laplace's equation for potential phi via Gauss-Seidel relaxation:
   phi[r][c] = average of 4 neighbors
   Boundary conditions:
     Channel cells: phi = 0 (conductor)
     Ground plane:  phi = 1 (opposite electrode)
     Other edges:   Neumann (zero gradient)

2. Find growth candidates: empty cells adjacent to the channel

3. Assign growth probability proportional to (phi)^eta:
   P(candidate) = phi(r,c)^eta / sum(phi^eta for all candidates)

4. Select one candidate by weighted random sampling, add to channel

5. Re-solve potential field and repeat

Parameters:
  eta — branching exponent (0.1 to 10.0)
        Low eta: dense branching, bushy fractal
        High eta: sparse, direct paths (DLA-like)
```

**What to look for** — Low eta values (~1.0) produce densely branched, bushy lightning bolts reminiscent of natural lightning. High eta values produce straighter, less branched paths. The discharge channel is colored by age: bright yellow for fresh growth, fading through cyan to dim blue for older segments. The faint potential field is visible as dim dots in the background.

**References**
- Niemeyer, L., Pietronero, L., and Wiesmann, H.J. "Fractal dimension of dielectric breakdown," *Physical Review Letters*, 1984. https://doi.org/10.1103/PhysRevLett.52.1033
- Wiesmann, H.J. and Zeller, H.R. "A fractal model of dielectric breakdown and prebreakdown in solid dielectrics," *Journal of Applied Physics*, 1986. https://doi.org/10.1063/1.337022


---

## Chladni Plate Vibrations

**Background** — In 1787, Ernst Chladni demonstrated that sand sprinkled on a vibrating metal plate migrates to the nodal lines (where displacement is zero), forming beautiful geometric patterns. These Chladni figures reveal the normal modes of the plate and inspired Germain and Kirchhoff's plate vibration theory. The patterns depend on the driving frequency and plate geometry.

**Formulation** — The simulator solves the 2D plate vibration equation with a center-driven excitation:

```
Plate equation:
  d^2z/dt^2 = -c^2 * Laplacian^2(z) - gamma * dz/dt + A*sin(2*pi*f*t)*delta(center)

Biharmonic operator (13-point stencil):
  Laplacian^2(z) = 20*z[r][c]
    - 8*(z[r-1][c] + z[r+1][c] + z[r][c-1] + z[r][c+1])
    + 2*(z[r-1][c-1] + z[r-1][c+1] + z[r+1][c-1] + z[r+1][c+1])
    + z[r-2][c] + z[r+2][c] + z[r][c-2] + z[r][c+2]

Parameters:
  c       — plate stiffness (default 1.0)
  gamma   — damping coefficient (default 0.02)
  A       — drive amplitude (default 0.5)
  f       — drive frequency, related to mode numbers: f = sqrt(m^2 + n^2) * 0.3
  (m, n)  — mode numbers (1-9 each), determining nodal line geometry

Integration: Velocity Verlet, clamped boundary conditions (edges fixed at zero)
Sand migration: sand flows from high-amplitude to low-amplitude regions
```

**What to look for** — Sand accumulates along nodal lines, producing the classic Chladni figures. Mode (1,2) creates a simple pattern with a few nodal lines; higher modes like (5,5) produce intricate geometric tilings. The "Harmonic Sweep" preset gradually increases frequency, letting you watch patterns dissolve and reform as new resonances are excited. Three visualization modes show sand density, plate displacement, and vibrational energy.

**References**
- Chladni, E.F.F. *Entdeckungen uber die Theorie des Klanges*, Leipzig, 1787. https://en.wikipedia.org/wiki/Chladni_figure
- Waller, M.D. "Vibrations of free square plates," *Proceedings of the Physical Society*, 1939. https://doi.org/10.1088/0959-5309/51/5/312


---

## Magnetic Field Lines

**Background** — Charged particles moving through electromagnetic fields trace out trajectories governed by the Lorentz force. This simulation visualizes cyclotron orbits, ExB drift, magnetic mirror trapping, and other fundamental plasma physics phenomena. These effects are essential to understanding particle accelerators, tokamak fusion reactors, the Van Allen radiation belts, and mass spectrometers.

**Formulation** — Particles are integrated using the Boris push algorithm, which exactly preserves the gyration phase-space volume:

```
Boris push (for each particle with charge q, mass m):
  1. Half-step electric acceleration:
     v_minus = v + (q/m)*E * dt/2

  2. Magnetic rotation:
     t = (q/m)*Bz * dt/2
     s = 2*t / (1 + t^2)
     v' = v_minus + v_minus x t_vec   (cross product approximation in 2D)
     v_plus = v_minus + v' x s_vec

  3. Second half-step electric acceleration:
     v_new = v_plus + (q/m)*E * dt/2

  4. Position update: x_new = x + v_new * dt

Field configurations:
  Uniform:     Bz = const
  Dipole:      Bz ~ 1/r^3
  Bottle:      Bz = B0 * (1 + mirror_ratio * (2y/rows - 1)^2)
  Quadrupole:  Bz ~ r (linearly increasing)
  Shear:       Bz varies linearly with x
```

**What to look for** — In "Cyclotron Motion," particles trace circular orbits whose radius depends on velocity. The "ExB Drift" preset shows how crossed electric and magnetic fields cause particles to drift perpendicular to both. In the "Magnetic Bottle," particles bounce between regions of strong B-field, demonstrating magnetic mirror trapping. The "Mixed Charges" preset shows opposite-charge particles gyrating in opposite directions.

**References**
- Boris, J.P. "Relativistic plasma simulation — optimization of a hybrid code," *Proc. Fourth Conference on Numerical Simulation of Plasmas*, 1970. https://apps.dtic.mil/sti/citations/ADA023511
- Chen, F.F. *Introduction to Plasma Physics and Controlled Fusion*, 3rd ed., Springer, 2016. https://doi.org/10.1007/978-3-319-22309-4


---

## FDTD Electromagnetic Waves

**Background** — The Finite-Difference Time-Domain (FDTD) method, introduced by Kane Yee in 1966, directly solves Maxwell's equations on a staggered grid. It is the workhorse of computational electromagnetics, used to design antennas, photonic crystals, radar cross-sections, and optical waveguides. This simulator implements 2D TM-mode propagation with PML absorbing boundaries.

**Formulation** — The Yee algorithm staggers E and H fields in both space and time:

```
2D TM mode (Ez, Hx, Hy):
  Hx(n+1/2) = Hx(n-1/2) - (dt/mu0) * dEz/dy
  Hy(n+1/2) = Hy(n-1/2) + (dt/mu0) * dEz/dx
  Ez(n+1)   = C1*Ez(n) + C2*(dHy/dx - dHx/dy)

  where:
    C1 = (1 - 0.5*sigma*dt/eps) / (1 + 0.5*sigma*dt/eps)
    C2 = (dt/eps) / (1 + 0.5*sigma*dt/eps)

  eps   — relative permittivity (1.0 for free space, 4.0 for glass)
  sigma — conductivity (0 for lossless, 100 for perfect conductor)

PML absorbing boundary:
  sigma = 0.8 * (depth/pml_width)^2   (graded conductivity)

Soft sources inject sinusoidal signals:
  Ez[src] += amp * sin(2*pi*freq*t + phase) * ramp(t)
  ramp(t) = 1 - exp(-(t/10)^2)   (Gaussian envelope for smooth start)

Courant number: dt/dx = 0.5 (stable for 2D)
```

**What to look for** — The "Double Slit" preset shows classic wave diffraction with interference fringes behind the barrier. The "Dielectric Lens" preset demonstrates wave focusing by a convex lens (eps=4.0). The "Phased Array" creates a steered beam through progressive phase shifts. Conductors (sigma=100) appear as white blocks that perfectly reflect waves. The PML boundaries absorb outgoing waves with minimal reflection.

**References**
- Yee, K.S. "Numerical solution of initial boundary value problems involving Maxwell's equations in isotropic media," *IEEE Transactions on Antennas and Propagation*, 1966. https://doi.org/10.1109/TAP.1966.1138693
- Taflove, A. and Hagness, S.C. *Computational Electrodynamics: The Finite-Difference Time-Domain Method*, 3rd ed., Artech House, 2005. https://us.artechhouse.com/Computational-Electrodynamics-Third-Edition-P1929.aspx


---

## Double Pendulum

**Background** — The double pendulum is perhaps the simplest mechanical system that exhibits deterministic chaos. Two pendulums connected end-to-end obey Newton's laws exactly, yet tiny differences in initial conditions lead to wildly divergent trajectories over time. This sensitivity is famously called the "butterfly effect." The simulator runs two nearly identical pendulums side by side to visualize this exponential divergence.

**Formulation** — The equations of motion are integrated with the 4th-order Runge-Kutta (RK4) method:

```
State: [theta1, theta2, omega1, omega2]

Equations of motion (Lagrangian mechanics):
  d(omega1)/dt = [-g*M*sin(t1) - m2*g*sin(t1 - 2*t2)
                  - 2*sin(delta)*m2*(omega2^2*l2 + omega1^2*l1*cos(delta))]
                 / [l1*(2*M - m2*(1 + cos(2*delta)))]

  d(omega2)/dt = [2*sin(delta)*(omega1^2*l1*M + g*M*cos(t1)
                  + omega2^2*l2*m2*cos(delta))]
                 / [l2*(2*M - m2*(1 + cos(2*delta)))]

  where: delta = t2 - t1,  M = m1 + m2

Parameters:
  m1, m2  — bob masses (1.0 to 3.0)
  l1, l2  — arm lengths (0.8 to 1.5)
  g       — gravitational acceleration (1.0 to 30.0, default 9.81)
  dt      — integration time step (0.001 to 0.02, default 0.005)
  perturb — angular offset between the two pendulums (1e-6 to 0.01 rad)

Tip position: x = l1*sin(t1) + l2*sin(t2), y = l1*cos(t1) + l2*cos(t2)
```

**What to look for** — The "Classic Chaos" preset starts both pendulums at 135 degrees with a 0.001-radian difference. Initially their trails overlap perfectly, but after a few seconds, the divergence becomes visible and then dramatic. The "Butterfly Effect" preset uses a perturbation of only 1e-6 radians. The "Max Chaos" preset starts near the unstable equilibrium (179 degrees) for the most violent behavior.

**References**
- Shinbrot, T. et al. "Chaos in a double pendulum," *American Journal of Physics*, 1992. https://doi.org/10.1119/1.16860
- Strogatz, S.H. *Nonlinear Dynamics and Chaos*, 2nd ed., Westview Press, 2014. https://doi.org/10.1201/9780429492563


---

## Cloth Simulation

**Background** — Cloth simulation using mass-spring systems and Verlet integration was pioneered by Provot (1995) and became a staple of real-time graphics. Point masses connected by distance constraints approximate fabric behavior under gravity and wind, with tearing occurring when springs stretch beyond a threshold. This approach is fast enough for interactive use while producing visually convincing fabric dynamics.

**Formulation** — The simulation uses position-based Verlet integration with iterative constraint satisfaction:

```
Verlet integration (for each non-pinned point):
  velocity = (position - old_position) * damping
  old_position = position
  position += velocity + gravity_vector + wind_vector

Constraint relaxation (iterated 5 times per step):
  For each spring connecting points p1 and p2 with rest length L:
    dist = |p2 - p1|
    if dist > L * tear_threshold:
      remove constraint (tear)
    else:
      correction = (L - dist) / dist * 0.5
      if both free: move each by half the correction
      if one pinned: move only the free point by full correction

Parameters:
  gravity      — downward acceleration (0.0 to 2.0)
  wind         — horizontal force with random variation
  damping      — velocity retention per step (0.9 to 1.0)
  tear_threshold — maximum stretch ratio before breaking (1.5 to 10.0)
```

Presets include hanging cloth (top row pinned), curtain (two corners), flag (left edge pinned, strong wind), hammock (four corners), net (wide spacing), and silk (fine mesh, low tear threshold).

**What to look for** — The "Flag" preset shows cloth billowing in the wind with characteristic ripple waves. Use "x" to tear constraints at the cursor and watch the fabric rip realistically. The "Silk" preset tears easily, producing dramatic ripping effects. Constraint colors shift from white (relaxed) through yellow (moderate tension) to red (near breaking point).

**References**
- Provot, X. "Deformation constraints in a mass-spring model to describe rigid cloth behavior," *Graphics Interface*, 1995. https://doi.org/10.20380/GI1995.31
- Jakobsen, T. "Advanced Character Physics," *Game Developers Conference*, 2001. https://www.cs.cmu.edu/afs/cs/academic/class/15462-s13/www/lec_slides/Jakobsen.pdf


---

## Plate Tectonics & Mantle Convection

**Background** — Plate tectonics is the unifying theory of geology, explaining earthquakes, volcanism, mountain building, and ocean basin formation through the motion and interaction of rigid lithospheric plates driven by mantle convection. This simulation couples Rayleigh-Bénard thermal convection in the mantle with rigid plate dynamics on the surface, reproducing the full spectrum of plate boundary interactions — divergent ridges, convergent subduction/collision zones, and transform faults — along with hotspot volcanism, oceanic crust aging, and the Wilson Cycle of supercontinent assembly and breakup. It pairs with the Planetary Atmosphere & Weather System mode to provide complementary solid-Earth and atmospheric perspectives on planetary dynamics.

**Formulation** — The simulation operates on a wrapped 2D grid with mantle convection driving plate motion:

```
Mantle convection (Rayleigh-Bénard analog):
  T_core = 1.0 (normalized), T_surface = 0.1
  Thermal diffusion: D = 0.06, 4-neighbor Laplacian
  Buoyancy-driven flow: velocity ∝ 0.12 × dT/dr (hot rises, cold sinks)
  Viscous drag on flow: 0.03
  Bottom heating: cells at base → T_core, top cooling: cells at surface → T_surface
  Plume detection threshold: T > 0.75

Plate mechanics:
  Mantle drag coefficient: 0.04 (couples plate velocity to underlying flow)
  Ridge push: 0.02, Slab pull: 0.06 (dominant driving force)
  Oceanic crust aging: density += 0.005/tick from base 0.3
  Continental density: 0.15 (buoyant, resists subduction)

Boundary processes:
  Convergent (relative velocity > 0.08):
    Continental-continental: orogenesis at 120 m/tick [capped 9000m]
    Oceanic-continental: subduction → volcanic arc (P=0.025/tick) + trench
    Oceanic-oceanic: island arc formation
  Divergent (relative velocity < -0.05):
    Mid-ocean ridge: new crust at -1800m elevation
    Continental rifting
  Transform:
    Stress accumulation: 0.02/tick
    Earthquake rupture at stress > 0.8, releases 60% of accumulated stress

Hotspot volcanism:
  Deep plume detection from mantle T > 0.75
  Eruption probability: 0.008/tick, adds 200m elevation
  Plate moves over fixed plume → volcanic chain (Hawaiian analog)

Wilson Cycle:
  Continental clustering detection → supercontinent state
  Mantle insulation heating beneath supercontinent
  Thermal repulsion force: 0.003 drives breakup

Erosion & isostasy:
  Smoothing: 0.025 blend toward neighbor average
  Peak erosion: 15 m/tick for high mountains
  Isostatic rebound: 30 m/tick for deep trenches

Elevation range: -11000m (Mariana Trench analog) to 9000m (Himalaya analog)
```

**What to look for** — Switch between the three views with `v`: the **tectonic map** shows elevation-colored topography with `^` volcanoes, `*`/`+` earthquakes, `@` hotspots, `v` trenches, and `|` ridges. The **mantle cross-section** reveals convection cells as temperature heatmaps (blue→green→red) with flow vector arrows showing hot material rising and cold material sinking. The **sparkline view** tracks 10 metrics over time. "Supercontinent Breakup Pangaea" demonstrates the Wilson Cycle as mantle heat trapped beneath a supercontinent drives rifting. "Subduction Zone Cascade" shows an oceanic plate diving beneath a continent, generating a volcanic arc and deep trench. "Yellowstone Hotspot Plume" traces a volcanic chain as the plate drifts over a fixed deep plume.

**References**
- Turcotte, D.L. and Schubert, G. *Geodynamics*, 3rd ed., Cambridge University Press, 2014. https://doi.org/10.1017/CBO9780511843877
- Vine, F.J. and Matthews, D.H. "Magnetic anomalies over oceanic ridges," *Nature*, 1963. https://doi.org/10.1038/199947a0
- Wilson, J.T. "Did the Atlantic close and then re-open?" *Nature*, 1966. https://doi.org/10.1038/211676a0


---

## Volcanic Eruption

**Background** — Volcanic eruptions involve complex interactions between magma chamber pressure, lava rheology, pyroclastic density currents, and atmospheric ash dispersion. This simulation models the full eruption cycle: pressure buildup in a magma chamber, eruption through vents, gravity-driven lava flow with temperature-dependent viscosity, explosive pyroclastic surges, ballistic ejecta, and wind-driven ash clouds.

**Formulation** — The multi-layered physics engine operates on a 2D grid:

```
Magma chamber dynamics:
  pressure += recharge_rate * speed   (capped at max_pressure)
  Eruption occurs when pressure > threshold (0.4 for hawaiian, 0.6 for explosive)
  eruption_intensity = (pressure - threshold) / (1 - threshold) * vent_strength

Lava flow (gravity-driven fluid over terrain):
  effective_elevation = terrain + cooled_rock + lava_depth
  Flow to lower neighbors proportionally to elevation difference
  flow_rate = 0.08 * temp_factor * speed
  temp_factor = max(0.05, (temp - 400) / 800)   [viscosity increases as lava cools]
  Lava cools at 3 deg/step; solidifies below 500 C into rock

Pyroclastic density current:
  Flow rate = 0.25 * speed, can flow slightly uphill (-0.05 tolerance)
  Dissipation: 4% per step, deposits ash where density > 0.1

Ejecta particles (ballistic):
  dr/dt = vr,  vr += 0.15 * speed   (gravity)
  dc/dt = vc + wind * 0.05

Ash dispersion (semi-Lagrangian advection + diffusion):
  new_ash[r][c] = ash[r - wind_v][c - wind_u] * 0.92
  Diffusion: 3% of ash spreads to 4 neighbors
  Settling: ash *= 0.995 per step

Cone geometry: height = peak * (1 - dist/radius)^1.3
```

**What to look for** — "Strombolian" produces moderate eruptions with lava fountains. "Plinian" generates massive explosive columns with pyroclastic surges (deadly fast-moving clouds). "Hawaiian" features fluid lava flows from shield volcanos with secondary flank vents. "Caldera" shows multiple ring vents erupting simultaneously. Cycle through visualization layers (terrain, lava, temperature, ash, pyroclastic) with "v" to examine each phenomenon separately.

**References**
- Sparks, R.S.J. et al. *Volcanic Plumes*, John Wiley & Sons, 1997. https://doi.org/10.1002/0470023449
- Cashman, K.V. and Mangan, M.T. "Physical aspects of magmatic degassing." *Reviews in Mineralogy* 30, 1994. https://doi.org/10.1515/9781501509674-012


---

## Black Hole Accretion Disk

**Background** — Black holes are regions of spacetime where gravity is so extreme that nothing, not even light, can escape from within the event horizon. Matter spiraling into a black hole forms a hot accretion disk, and magnetic fields can launch relativistic jets along the polar axis. This simulation models the accretion disk, gravitational lensing of background stars, relativistic jets, and Hawking radiation in a simplified 2D framework.

**Formulation** — Three particle types are tracked with different physics:

```
Disk particles (Keplerian orbits with relativistic corrections):
  Gravitational acceleration: a = -GM/r^2  (toward center)
  Frame dragging (Lense-Thirring): a_drag = spin*M/(r^3) * 0.5
  Relativistic precession: a *= (1 + 3*M/r^2 * 0.01)
  Viscous drag for angular momentum transport: v *= (1 - 0.001*accretion_rate*dt)
  Innermost stable orbit: r_isco = 3*rs * (1 - spin*0.3)
  Temperature: T = min(1, M / (r*0.5 + 1))
  Accreted when r < rs (Schwarzschild radius)

Jet particles:
  Mild gravitational pull, magnetic collimation: vx -= 0.02*dx*dt
  Launched when disk matter crosses horizon (probability ~ jet_power)

Hawking radiation:
  Radial escape with quantum randomness: v += gauss(0, 0.1) * dt
  Spawned near the event horizon at r ~ 1.0-1.5 * rs

Gravitational lensing of background stars:
  deflection = M * 0.15 / (dist^2 + rs)
  apparent_position = true_position + deflection * direction
  amplification = 1 + M*0.02 / (|dist - 2.5*rs| + 0.5)

Kerr spin parameter: 0.0 (Schwarzschild) to 0.99 (near-extremal Kerr)
```

**What to look for** — The accretion disk glows brightest near the innermost orbit, with temperature-coded colors from cool blue to hot red. The photon ring marks the orbit of light at 1.5*rs. Relativistic jets emerge along the polar axis, collimated by magnetic forces. Background stars are visibly distorted near the black hole, with amplification producing bright arcs near the Einstein ring radius. The "Kerr Black Hole" preset shows pronounced frame-dragging effects.

**References**
- Luminet, J.-P. "Image of a spherical black hole with thin accretion disk," *Astronomy and Astrophysics*, 1979. https://doi.org/10.1051/0004-6361/201629441
- Thorne, K.S. *Black Holes and Time Warps*, W.W. Norton, 1994. https://wwnorton.com/books/9780393312768


---

## Solar System Orrery

**Background** — An orrery is a mechanical model of the solar system showing the relative positions and motions of the planets. This simulation computes true Keplerian orbits for all eight planets using accurate orbital elements, solving Kepler's equation at each timestep. It also models the asteroid belt and long-period comets, providing an interactive planetarium.

**Formulation** — Orbits are computed from classical orbital mechanics:

```
Kepler's equation (solved by Newton-Raphson iteration):
  M = E - e*sin(E)
  where M = mean anomaly, E = eccentric anomaly, e = eccentricity

True anomaly:
  nu = 2 * atan2(sqrt(1+e)*sin(E/2), sqrt(1-e)*cos(E/2))

Orbital radius:
  r = a * (1 - e*cos(E))

Mean anomaly evolves as:
  M(t) = M0 + (2*pi/T) * t

Planet data (actual orbital elements):
  Mercury: a=0.387 AU, e=0.206, T=0.241 yr
  Venus:   a=0.723 AU, e=0.007, T=0.615 yr
  Earth:   a=1.000 AU, e=0.017, T=1.000 yr
  Mars:    a=1.524 AU, e=0.093, T=1.881 yr
  Jupiter: a=5.203 AU, e=0.048, T=11.86 yr
  Saturn:  a=9.537 AU, e=0.054, T=29.46 yr
  Uranus:  a=19.19 AU, e=0.047, T=84.01 yr
  Neptune: a=30.07 AU, e=0.009, T=164.8 yr

Asteroid belt: a ~ 2.1-3.3 AU, T = a^(3/2)  (Kepler's third law)
Comets: high eccentricity (e ~ 0.85-0.97), large semi-major axis
```

**What to look for** — Mercury's highly eccentric orbit (e=0.206) visibly deviates from circular. The asteroid belt fills the gap between Mars and Jupiter. The "Comet Flyby" preset shows a long-period comet plunging through the inner solar system with a growing tail. The "Grand Alignment" starts all planets near conjunction. Zoom levels let you examine inner planets in detail or see the full system out to Neptune.

**References**
- Murray, C.D. and Dermott, S.F. *Solar System Dynamics*, Cambridge University Press, 1999. https://doi.org/10.1017/CBO9781139174817
- Meeus, J. *Astronomical Algorithms*, 2nd ed., Willmann-Bell, 1998. https://www.willbell.com/math/mc1.htm


---

## Aurora Borealis

**Background** — The aurora borealis (northern lights) is produced when charged particles from the solar wind, guided by Earth's magnetic field lines into the polar regions, collide with atmospheric gases. Oxygen emits green (557.7 nm, at 100-200 km altitude) and red (630 nm, at 200-400 km), while nitrogen produces purple/blue emissions. This simulation models auroral curtains, solar wind particles, and pulsating displays.

**Formulation** — The aurora is rendered through layered curtain structures:

```
Curtain model:
  Each curtain has: center_x, width, brightness, drift speed, fold points
  Vertical intensity: sin(band_fraction * pi)   [peaks at band center]

  Wave shape at each row:
    offset = sum_k[ amp_k * sin(row_frac * freq_k * 6 + t*speed + phase_k) ]

  Horizontal intensity: exp(-dist^2 * 2)   [Gaussian falloff from center]

  Total brightness = horizontal * vertical * curtain_brightness * global_intensity

Altitude bands (mapped to screen rows):
  N2 purple (200-300 km):  rows 5%-20%, magenta
  O green (100-200 km):    rows 15%-55%, green (dominant emission)
  O red (200-400 km):      rows 8%-25%, red (faint)
  N2 blue (80-120 km):     rows 40%-70%, blue/violet

Pulsating aurora: brightness *= 0.5 + 0.5*sin(t * pulse_freq * 2*pi + phase)

Solar wind particles:
  Drift downward with velocity proportional to wind_strength
  Curve toward magnetic field lines: vx += (mid_x - x) * 0.0005

Substorm dynamics: random brightness bursts with probability ~ 0.02 * wind_strength
```

**What to look for** — "Quiet Arc" shows a gentle green band slowly drifting across the sky. "Substorm Breakup" features explosive brightening with rapid curtain movement. "Pulsating Aurora" displays rhythmic on-off flickering of discrete patches. "Coronal Mass Ejection" produces an intense multi-color display with all altitude bands visible. Toggle magnetic field lines with "f" to see the guiding geometry.

**References**
- Akasofu, S.-I. "The development of the auroral substorm," *Planetary and Space Science*, 1964. https://doi.org/10.1016/0032-0633(64)90151-5
- Brekke, A. *Physics of the Upper Polar Atmosphere*, 2nd ed., Springer, 2013. https://doi.org/10.1007/978-3-642-27401-5


---

## Pendulum Wave

**Background** — The pendulum wave apparatus consists of uncoupled pendulums with incrementally different lengths, so each oscillates at a slightly different frequency. When released simultaneously, they produce mesmerizing patterns: traveling waves, standing waves, apparent chaos, and periodic realignment. This demonstration, popular in physics museums worldwide, beautifully illustrates the relationship between frequency, phase, and the superposition of simple harmonic motions.

**Formulation** — Each pendulum follows the exact solution for simple harmonic motion:

```
For pendulum i (i = 0, 1, ..., N-1):
  Period:  T_i = realign_time / (N_base + i)
  Length:  L_i = g * (T_i / (2*pi))^2       [from T = 2*pi*sqrt(L/g)]
  Angle:   theta_i(t) = A * cos(omega_i * t)
  Angular frequency: omega_i = sqrt(g / L_i)

  N_base = 51 (base number of oscillations for the longest pendulum)
  A = 0.4 radians (~23 degrees, small-angle regime)
  g = 9.81 m/s^2

At t = 0:     all pendulums at theta = A (synchronized)
At t = T_realign: all return to synchronization

Preset configurations:
  Classic:  15 pendulums, realign_time = 60s
  Dense:    24 pendulums, realign_time = 60s
  Grand:    32 pendulums, realign_time = 60s
```

**What to look for** — When released, the pendulums quickly dephase into what appears to be random motion. But beautiful order emerges: traveling waves (all pendulums form a sinusoidal shape), apparent standing waves, and chaotic-looking scatter. The cycle percentage in the status bar tracks progress toward the next full realignment. The wave indicator at the bottom shows instantaneous phase relationships. The "Grand Ensemble" preset with 32 pendulums produces the richest patterns.

**References**
- Flaten, J.A. and Parendo, K.A. "Pendulum waves: a lesson in aliasing," *American Journal of Physics*, 2001. https://doi.org/10.1119/1.1349543
- Berg, R.E. "Pendulum waves: A demonstration of wave motion using pendula." *American Journal of Physics* 59(2), 1991. https://doi.org/10.1119/1.16505


---

## Tornado & Supercell Storm

**Background** — Tornadoes form within supercell thunderstorms when a rotating updraft (mesocyclone) extends a vortex downward to the ground. The EF (Enhanced Fujita) scale classifies tornadoes by damage intensity. This simulation models the complete storm structure: rotating mesocyclone cloud, descending funnel, rain curtains, debris lofting, lightning, and a destruction path.

**Formulation** — The tornado is modeled as a time-varying vortex with coupled meteorological elements:

```
Vortex dynamics:
  Position drift: x += sin(t*0.15)*0.08 + sin(wobble_phase)*wobble_amp*0.05
  Pulsating radius: eff_radius = base_radius + 0.3*sin(t*1.5)
  Mesocyclone: cloud_angle += rotation_speed * dt

Rain particle physics:
  Inward spiral near vortex:
    strength = (1 - dist/storm_radius) * 0.3
    vx += (-dx/dist * strength)
    vy += 0.05  (gravity)

Debris dynamics:
  Spawned at ground level when touch_ground = true
  Forces:
    Tangential (rotation): a_t = (-dy/dist) * f * rotation_speed * 0.15
    Inward pull:           a_in = -(dx/dist) * f * 0.2
    Updraft:               a_up = -updraft_strength * f * 0.15
    Gravity:               vy += 0.04
    Drag:                  v *= 0.97

Lightning generation (branching):
  Start from cloud layer, random walk downward
  Branch with probability 0.2, capped at 30 segments
  Flash duration: 3 frames

Storm presets: EF3 (strong), Rope (narrow), Outbreak (severe),
               Rain-Wrapped (hidden), Night (dark), Dust Devil (dry, no rain)
```

**What to look for** — The funnel cloud narrows from the wide mesocyclone base to a tight ground contact, with visible rotation in the shading pattern. Debris orbits the vortex, occasionally lofted high into the storm. Lightning illuminates the entire cloud structure. The "Night Tornado" preset hides the funnel in darkness, revealed only by lightning flashes. The "Dust Devil" preset shows a weaker, rain-free vortex with only debris.

**References**
- Bluestein, H.B. *Severe Convective Storms and Tornadoes: Observations and Dynamics*, Springer, 2013. https://doi.org/10.1007/978-3-642-05381-8
- Doswell, C.A. III. "The Operational Meteorology of Convective Weather," *NOAA Technical Memorandum*, 1985. https://www.spc.noaa.gov/publications/doswell/ops-meteo2.htm


---

## Electric Circuit Simulator

**Background** — Electric circuits are described by Kirchhoff's laws (conservation of charge and energy), Ohm's law, and the constitutive relations of reactive components. This simulator uses Modified Nodal Analysis (MNA) to solve DC circuits and transient analysis for RC, LC, and RLC circuits. Users can build circuits from batteries, resistors, capacitors, inductors, LEDs, and switches, and observe real-time current flow, voltage heatmaps, and oscilloscope traces.

**Formulation** — The simulator solves circuit equations at each timestep:

```
Kirchhoff's laws (at each node):
  sum(currents_in) = sum(currents_out)

Component equations:
  Resistor:   V = I * R                     (Ohm's law)
  Capacitor:  I = C * dV/dt                 (discretized: I = C*(V_new - V_old)/dt)
  Inductor:   V = L * dI/dt                 (discretized: V = L*(I_new - I_old)/dt)
  Battery:    V_node1 - V_node2 = V_source
  LED:        forward-biased: small resistance; reverse: open circuit
  Switch:     open (infinite R) or closed (zero R)

Transient integration: Backward Euler for stability
  Capacitor companion model: I_eq = C/dt * V + I_history
  Inductor companion model:  V_eq = L/dt * I + V_history

Presets:
  Simple DC Loop:    9V battery + 100 Ohm resistor → I = 90mA
  Voltage Divider:   12V with 1k + 2k Ohm → V_out = 8V
  RC Charging:       V(t) = V0 * (1 - exp(-t/RC)), tau = R*C
  LC Oscillator:     f = 1 / (2*pi*sqrt(L*C))
  RLC Resonance:     damped sinusoid, Q = (1/R)*sqrt(L/C)
  Wheatstone Bridge: balanced when R1/R2 = R3/R4
```

**What to look for** — Animated charge-flow particles move along wires, speeding up through high-current segments. The "RC Charging" preset shows the classic exponential voltage rise on the oscilloscope. The "LC Oscillator" demonstrates energy sloshing between capacitor (electric field) and inductor (magnetic field). The "RLC Resonance" preset shows damped oscillations with the Q-factor determining how many cycles persist.

**References**
- Ho, C.-W. et al. "The modified nodal approach to network analysis," *IEEE Transactions on Circuits and Systems*, 1975. https://doi.org/10.1109/TCS.1975.1084079
- Horowitz, P. and Hill, W. *The Art of Electronics*, 3rd ed., Cambridge University Press, 2015. https://artofelectronics.net/


---

## Molecular Dynamics / Phase Transitions

**Background** — Molecular dynamics simulates the motion of particles interacting via pairwise potentials. The Lennard-Jones potential, proposed by John Lennard-Jones in 1924, captures the essential physics of noble gases: short-range repulsion from electron cloud overlap and long-range attraction from van der Waals forces. With temperature control, you can observe the three states of matter and their transitions from a single force law.

**Formulation** — Particles interact via the Lennard-Jones 6-12 potential with velocity-Verlet integration:

```
Lennard-Jones potential:
  V(r) = 4*epsilon * [(sigma/r)^12 - (sigma/r)^6]

Force (per pair):
  F(r) = 24*epsilon * [2*(sigma/r)^12 - (sigma/r)^6] / r^2  * r_vec
  Truncated at cutoff = 2.5*sigma

Velocity-Verlet integration:
  v(t + dt/2) = v(t) + F(t)/(2m) * dt
  r(t + dt) = r(t) + v(t + dt/2) * dt
  Recompute forces F(t + dt)
  v(t + dt) = v(t + dt/2) + F(t + dt)/(2m) * dt

Periodic boundary conditions (minimum image convention):
  dx -= box_L * round(dx / box_L)

Temperature:  T = 2*KE / N_dof,  N_dof = 2N - 2
Berendsen thermostat:  v *= 1 + 0.1*(sqrt(T_target/T) - 1)
Pressure:  P = (N*T + virial/2) / Area,  virial = sum(F*r)

Phase classification (heuristic):
  T < 0.4 and high RDF order → SOLID
  0.4 < T < 1.2             → LIQUID
  T > 1.2                   → GAS

Reduced units: sigma = 1, epsilon = 1, mass = 1, dt = 0.005
```

**What to look for** — "Crystal Growth" (T=0.1) shows particles freezing into a hexagonal lattice; the radial distribution function (RDF) displays sharp crystalline peaks. "Melting Point" (T=0.75) shows the lattice breaking apart. "Boiling" (T=1.5) demonstrates explosive evaporation as hot particles escape the liquid. Use the arrow keys to change temperature in real time and watch solid melt into liquid, then boil into gas. The RDF view reveals structural order through pair correlation peaks.

**References**
- Lennard-Jones, J.E. "On the determination of molecular fields," *Proceedings of the Royal Society A*, 1924. https://doi.org/10.1098/rspa.1924.0082
- Allen, M.P. and Tildesley, D.J. *Computer Simulation of Liquids*, 2nd ed., Oxford University Press, 2017. https://doi.org/10.1093/oso/9780198803195.001.0001


---

## Magnetism & Spin Glass

**Background** — While the Ising model uses discrete spins, the XY model and spin glasses use continuous spin angles. A spin glass has random bond signs (positive = ferromagnetic, negative = antiferromagnetic), leading to frustration: not all interactions can be simultaneously satisfied. This produces a complex energy landscape with many metastable states, slow relaxation (aging), and no long-range order. The concept, introduced by Edwards and Anderson in 1975, has deep connections to combinatorial optimization and neural networks.

**Formulation** — Continuous-angle spins on a 2D square lattice with Metropolis dynamics:

```
Hamiltonian:
  H = -sum_<ij> J_ij * cos(theta_i - theta_j) - h * sum_i cos(theta_i)

  J_ij — coupling constant per bond:
    Ferromagnetic:     J = +1 (all bonds)
    Antiferromagnetic: J = -1 (all bonds)
    Spin glass (±J):   J = +1 or -1 randomly (Edwards-Anderson model)
    Frustrated:        J = +1 with prob 0.6, -1 with prob 0.4

Metropolis update (one sweep = N trial rotations):
  1. Pick random site (r, c)
  2. Propose: theta_new = theta_old + uniform(-delta, +delta)
     delta = min(pi, 0.3 + T*0.5)   [adapts to temperature]
  3. Compute dE from 4 neighbor interactions + field term
  4. Accept if dE <= 0 or rand() < exp(-dE/T)

Observables:
  Magnetization: |m| = sqrt((sum cos(theta))^2 + (sum sin(theta))^2) / N
  Energy/spin:   E/N from Hamiltonian
  Susceptibility: chi = N * (<m^2> - <m>^2) / T   [from fluctuations]
```

Spin directions are rendered as 8-directional arrows, color-coded by local energy density. Domain walls (sites with large angular difference from neighbors) are highlighted in bright white.

**What to look for** — "Ferromagnetic" shows uniform domains growing at low T. "Spin Glass (plus-minus J)" at low temperature shows a mosaic of frozen, frustrated domains that never fully order. "Quench to Glass" starts hot and drops to T=0.05, freezing a disordered state; watch the slow aging dynamics as the system explores its rugged energy landscape. "Vortex Patterns" reveals topological defects where the spin angle winds by 2-pi around a point. The statistics view shows magnetization, energy, and susceptibility time series.

**References**
- Edwards, S.F. and Anderson, P.W. "Theory of spin glasses," *Journal of Physics F*, 1975. https://doi.org/10.1088/0305-4608/5/5/017
- Mezard, M., Parisi, G., and Virasoro, M.A. *Spin Glass Theory and Beyond*, World Scientific, 1987. https://doi.org/10.1142/0271


---

## Particle Collider / Hadron Collider

**Background** — Particle colliders accelerate beams of particles to near the speed of light and smash them together, converting kinetic energy into new particles via E=mc^2. The Large Hadron Collider (LHC) at CERN, operational since 2008, discovered the Higgs boson in 2012 at a center-of-mass energy of 13.6 TeV. This simulation models counter-rotating beam bunches in a synchrotron ring, stochastic collisions at interaction points, and the resulting particle showers and detector events.

**Formulation** — Beam particles orbit an elliptical ring with collisions at interaction points:

```
Beam dynamics:
  angle(t+1) = angle(t) + speed * direction
  Beams alternate clockwise and counter-clockwise
  Trail length: 6 positions (fading)

Collision detection:
  At each of 4 interaction points (cardinal positions on ring):
    if rand() < collision_rate:
      Check for clockwise and counter-clockwise beams within 0.4 radians
      If both present: trigger collision event

Particle shower generation:
  N_shower particles: 4-8 (lepton), 6-16 (proton), 12-25 (heavy ion)
  Each shower particle:
    velocity = random direction * random speed * 1.8 (x-stretched for aspect ratio)
    deceleration: v *= 0.96 per step (detector material interaction)
    lifetime: 8-30 steps

Detected particles (stochastic identification):
  Known particles with masses (GeV/c^2):
    Photon (0), Electron (0.000511), Muon (0.106), Pion (0.135-0.140),
    Kaon (0.494), Proton (0.938), W boson (80.4), Z boson (91.2),
    Higgs boson (125.1), Top quark (173.0)
  Measurement: mass_observed = mass_true * uniform(0.92, 1.08)
  Rare particles (Higgs, Top): discovery_rate varies by preset

Preset energies:
  LHC:       13.6 TeV, 12 bunches
  Heavy Ion:  5.36 TeV, 8 bunches
  Lepton:     0.209 TeV, 16 bunches (future e+e- collider)
  Discovery:  14.0 TeV, 20 bunches (enhanced rare particle rate)
```

**What to look for** — Counter-rotating beams (shown in blue and green) circulate around the ring. When they collide at a detector point, a bright flash appears followed by a spray of shower particles. The event log accumulates detected particles with measured masses and energies. The "Discovery Mode" preset has an enhanced rate for rare particles like the Higgs boson. Use "c" to force a collision at a random interaction point. Four detector stations (inspired by ATLAS, CMS, ALICE, and LHCb) surround the ring.

**References**
- The ATLAS Collaboration. "Observation of a new particle in the search for the Standard Model Higgs boson," *Physics Letters B*, 2012. https://doi.org/10.1016/j.physletb.2012.08.020
- Evans, L. and Bryant, P. "LHC Machine," *Journal of Instrumentation*, 2008. https://doi.org/10.1088/1748-0221/3/08/S08001


---

## Spacetime Fabric

**Background** — In general relativity, spacetime is not a fixed stage on which physics plays out — it is a dynamic participant, curving and warping in response to the matter and energy it contains. Einstein's field equations couple the geometry of spacetime (the metric tensor) to the stress-energy tensor of matter. This mode brings that idea into the cellular automaton domain: the grid itself is no longer a passive substrate but a dynamical entity that curves around live cell clusters, producing gravitational lensing, time dilation, geodesic motion, frame dragging, and gravitational waves. Every other mode in the project treats the grid as flat and fixed; this is the first where the topology responds to the simulation state.

**Formulation** — The simulation couples a standard Game of Life (B3/S23) cellular automaton to a scalar approximation of curved spacetime:

```
1. Mass density field (Gaussian-smoothed from live cells):
   For each live cell at (r,c), accumulate mass to neighbors within radius 4:
     mass[r+dr][c+dc] += 1 / (1 + dr² + dc²)

2. Spacetime curvature (Poisson equation approximation):
     curvature[r][c] = (mass[r][c] / max_mass) * G
   where G is the adjustable gravity strength (0.1 to 2.0)

3. Time dilation (Schwarzschild-like):
     dilation[r][c] = sqrt(max(0.01, 1 - 1.5 * curvature[r][c]))
   Cells near massive clusters accumulate time slower:
     tick_accumulator[r][c] += dilation[r][c]
   A cell only updates its CA rule when its accumulator reaches 1.0.

4. Geodesic motion (curvature gradient):
     displacement_r = (curv[r+1][c] - curv[r-1][c]) * 0.5 * G * 3.0
     displacement_c = (curv[r][c+1] - curv[r][c-1]) * 0.5 * G * 3.0
   Live cells advect toward regions of higher curvature.

5. Frame dragging (angular momentum from neighbor asymmetry):
     angular[r][c] = cross product of local neighbor gradient
   Spread with 1/(1+d²) falloff within radius 3, scaled by drag coefficient.
   Adds tangential displacement perpendicular to radial pull.

6. Gravitational waves (2D wave equation on metric perturbation):
     velocity[r][c] = (velocity[r][c] + c² * Laplacian(gwave) + source) * damping
     gwave[r][c] += velocity[r][c]
   where source = (mass - prev_mass) * wave_strength * 0.5
   damping = 0.97, c² = 0.2

Combined step order: mass → curvature → dilation → angular momentum →
  gravitational waves → geodesic advection → CA update (every ca_interval steps)
```

Presets configure four parameters — gravity (G), lensing strength, frame drag coefficient, and gravitational wave amplitude — to highlight different GR phenomena:
- **Binary Orbit**: Two dense clusters with strong gravity, moderate lensing
- **Gravitational Lens**: Central mass with approaching gliders that curve around it
- **Spacetime Soup**: Random fill with strong gravity — structure emerges from curvature
- **Glider Geodesics**: Still-life masses with gliders following curved paths
- **Frame Drag Vortex**: Rotating pattern that drags neighbors into co-rotation
- **Gravitational Waves**: Collapsing clusters that emit metric ripples

**What to look for** — In the Fabric visualization, watch for directional arrows (→↗↑ etc.) showing the gravitational pull field around dense clusters. Gravitational waves appear as blue/cyan ripples expanding from sudden mass changes (cell death events). In the Time Dilation view, cells near massive regions glow red (nearly frozen) while isolated cells remain cyan (full speed) — you can see the CA evolving at different rates across the grid. The Curvature heatmap reveals the gravitational potential wells. Try the Binary Orbit preset to watch two clusters warp the space between them, or Glider Geodesics to see gliders bend around massive still lifes.

**References**
- Misner, C.W., Thorne, K.S., and Wheeler, J.A. *Gravitation*. W.H. Freeman, 1973. ISBN 978-0-7167-0344-0
- Hartle, J.B. *Gravity: An Introduction to Einstein's General Relativity*. Addison-Wesley, 2003. ISBN 978-0-8053-8662-2
- Regge, T. "General Relativity Without Coordinates," *Il Nuovo Cimento*, 1961. https://doi.org/10.1007/BF02733251


---

## Quantum Game of Life

**Background** — The Quantum Game of Life is the natural quantum generalization of Conway's Game of Life. Where classical Life cells are strictly alive or dead, quantum cells exist in superposition — a complex linear combination of |1⟩ (alive) and |0⟩ (dead). The classical B3/S23 rules are lifted to a unitary operator that continuously rotates cell amplitudes rather than applying discrete thresholds. This produces interference patterns, entanglement between neighboring cells, and probabilistic measurement collapse — phenomena with no classical analogue. The mode sits at the intersection of quantum computing and complex systems theory, drawing on work by Bleh, Calarco, and Montangero on quantum cellular automata.

**Formulation** — Each cell stores a complex alive-amplitude `a = re + i·im`. The probability of being alive is `P = |a|² = re² + im²`, with dead-amplitude `√(1 - P)`.

```
Quantum state per cell:
  |ψ⟩ = a|1⟩ + √(1−|a|²)|0⟩    where a ∈ ℂ, |a|² ≤ 1

Evolution (per step):
  1. Compute expected alive neighbours: n = Σ P(neighbour)
  2. Compute rotation angle θ from GoL rules:
     - Birth signal:    B(n) = exp(-(n-3)²/0.8)        peaked at n=3
     - Survival signal: S(n) = max(exp(-(n-2)²/0.8),
                                    exp(-(n-3)²/0.8))   peaked at n=2,3
     - θ depends on current P:
       P < 0.3 (mostly dead):  θ = B(n) · 0.4π          (birth)
       P > 0.7 (mostly alive): θ = (S(n) - 0.5) · 0.3π  (survive/die)
       else (superposition):   θ = mixed birth+survival   (interference)
  3. Apply rotation:
     new_re = cos(θ)·re + sin(θ)·√(1−P)
     new_im = cos(θ)·im

Entanglement:
  When |θ| > 0.05, cells that contributed to each other's evolution
  gain pairwise entanglement strength:
    E(c₁,c₂) += |θ| · P(neighbour) · 0.1     (capped at 1.0)
  Entanglement decays by factor 0.95 per step.

Measurement (click):
  Collapse cell to |1⟩ with probability P, or |0⟩ with probability 1−P.
  Entangled partners partially collapse proportional to entanglement strength.

Environmental decoherence (rate d, adjustable 0–1):
  Each step, each cell has probability d of undergoing spontaneous measurement,
  collapsing to a classical state and propagating decoherence to partners.
```

**Visualization modes** (cycle with `v`):
- **Probability**: Density characters (`· ░▒▓█`) show P(alive), color hue encodes phase angle of the alive-amplitude
- **Phase**: Color encodes complex phase angle (red→yellow→green→cyan→blue→magenta), brightness encodes amplitude magnitude
- **Entanglement**: Background shows dim probability field; colored links and endpoint markers (●/◉) show pairwise entanglement strength between correlated cells

**Presets** — Six configurations showcase different quantum phenomena:
- **Quantum Glider**: Superposition of a glider at two translated positions with a π/3 phase offset — produces interference fringes as the two copies evolve
- **Schrödinger's Blinker**: Period-2 oscillator in superposition of both horizontal and vertical phases simultaneously — the quantum version of the simplest oscillator
- **Entangled Gosper Gun**: Classic Gosper glider gun with phase-varying birth sites — glider streams carry correlated quantum states
- **Quantum Soup**: 30% of cells initialized with random amplitude (up to 0.8) and random phase — watch decoherence crystallize classical structures from quantum chaos
- **Bell State Pair**: Two cells separated by 10 columns, each with amplitude 1/√2, maximally entangled — measuring one instantly collapses the other
- **Quantum Garden of Eden**: Uniform low-amplitude (0.15) superposition across the entire grid with a slowly varying phase gradient — a state with no classical predecessor

**Controls**: `Space` play/pause, `n` single step, `v` cycle view mode, `d`/`D` increase/decrease decoherence rate, `+`/`-` adjust steps per frame, `click` measure a cell, `r` reset current preset, `R` return to preset menu.

**What to look for** — In the Quantum Glider preset, watch the two glider copies interfere as they evolve — bright regions where amplitudes constructively interfere and dark gaps where they cancel. Switch to Phase view to see the π/3 offset between the two copies. With the Bell State Pair, click one cell and watch the other instantly collapse — then switch to Entanglement view to see the correlation link vanish. Try increasing decoherence (`d` key) on the Quantum Soup to watch a quantum superposition gradually crystallize into recognizable classical Life structures like blinkers and blocks. The Entangled Gosper Gun produces the most visually complex dynamics — streams of quantum gliders carrying phase information from the gun's birth events.

**References**
- Bleh, D., Calarco, T., and Montangero, S. "Quantum Game of Life," *EPL (Europhysics Letters)*, 97(2), 2012. https://doi.org/10.1209/0295-5075/97/20012
- Meyer, D.A. "From quantum cellular automata to quantum lattice gases," *Journal of Statistical Physics*, 85, 1996. https://doi.org/10.1007/BF02199356
- Venegas-Andraca, S.E. "Quantum walks: a comprehensive review," *Quantum Information Processing*, 11(5), 2012. https://doi.org/10.1007/s11128-012-0432-5


---

## Time Crystal

**Background** — Discrete time crystals (DTCs) are a phase of matter that spontaneously breaks discrete time-translation symmetry. First proposed theoretically by Frank Wilczek in 2012 and experimentally realized in 2016–2017 using trapped ions and nitrogen-vacancy centers in diamond, DTCs exhibit a striking phenomenon: when driven periodically at frequency ω, the system responds at a subharmonic frequency ω/2 (period-doubling). This subharmonic response is robust against perturbations to the drive — a genuine symmetry breaking, not merely a resonance effect. The key ingredients are many-body localization (MBL) from quenched disorder, which prevents the system from absorbing energy and heating to infinite temperature, and Ising interactions that stabilize the collective spin-flip oscillation. This mode simulates a spin-1/2 lattice under Floquet driving, reproducing the hallmark DTC signatures.

**Formulation** — Each cell holds a spin on the Bloch sphere parameterized by (σᶻ, φ), evolving under a two-phase Floquet protocol:

```
Floquet period (two half-steps):

  Phase 1 — Ising interaction + disorder (drive_period = 0):
    For each spin (r, c):
      h_eff = h_disorder[r][c] + J * Σ_neighbors J_disorder[r][c] * σᶻ(neighbor)
      Decompose spin: sx = √(1 - σᶻ²) cos(φ),  sy = √(1 - σᶻ²) sin(φ)
      Precess transverse components around z by angle h_eff * dt:
        sx' = sx cos(θ) - sy sin(θ)
        sy' = sx sin(θ) + sy cos(θ)
      Small transverse mixing: σᶻ' = σᶻ + 0.02 * h_eff * dt * sx'
      Reconstruct φ from (sx', sy')

  Phase 2 — Imperfect π-pulse (drive_period = 1):
    Rotation angle: α = π - ε   (ε = drive imperfection)
    For each spin, rotate Bloch vector around x-axis by α:
      sx' = sx
      sy' = sy cos(α) - σᶻ sin(α)
      σᶻ' = sy sin(α) + σᶻ cos(α)
    Record stroboscopic snapshot for oscillation analysis.

Parameters:
  ε        — drive imperfection (0.0 to 0.5), deviation from perfect π-pulse
  J        — Ising coupling strength (0.0 to 3.0)
  disorder — quenched disorder strength (0.0 to 2.0)
  dt = 0.5   (interaction time per half-period)

Quenched disorder:
  h_disorder[r][c] ~ N(0, disorder)           local field
  J_disorder[r][c] ~ 1 + N(0, 0.3 * disorder) coupling variation

DTC order parameter:
  Compare last two stroboscopic snapshots:
    order = Σ |σᶻ_current - σᶻ_previous| / Σ (|σᶻ_current| + |σᶻ_previous|)
  Perfect period-doubling → order ≈ 1.0

Oscillation amplitude (per cell, from stroboscopic history):
  Count sign alternations over last 16 Floquet periods
  amplitude = alternating_magnitude / total_magnitude
```

**Presets** — Six configurations span the DTC phase diagram:
- **Clean DTC**: Uniform coupling (J=1.0), small drive error (ε=0.03), no disorder — textbook period-doubling from Ising interactions alone
- **Disordered DTC (MBL)**: Strong quenched disorder (0.5) with J=0.8 — many-body localization protects the DTC from thermalization
- **Melting Crystal**: Large drive error (ε=0.20) near the phase boundary — fragile oscillations that gradually decay as the system absorbs energy
- **Domain Walls**: Alternating horizontal stripe domains — watch subharmonic breathing at domain boundaries
- **Period-4 Attempt**: Enhanced coupling (J=1.5) with checkerboard initial conditions — seeking higher-order T/4 subharmonic response
- **Random Spins**: Fully random initial spins with moderate disorder — spontaneous DTC formation from a disordered initial state

**Visualization modes** (cycle with `v`):
- **Spin**: Current σᶻ expectation — warm colors (red/yellow) for spin-up, cool colors (blue) for spin-down, brightness proportional to polarization magnitude
- **Oscillation**: DTC amplitude per cell — green indicates strong period-doubling, yellow moderate, blue negligible
- **Stroboscopic**: System state sampled every full Floquet period — in a DTC phase, this view alternates uniformly between two states

**Controls**: `Space` play/pause, `n`/`.` single step, `v` cycle view, `e`/`E` increase/decrease drive error ε, `j`/`J` increase/decrease Ising coupling, `d`/`D` increase/decrease disorder, `+`/`-` adjust speed, `click` flip a spin (test robustness), `r` reset, `R` return to menu.

**What to look for** — In the Clean DTC preset, start the simulation and watch the global DTC order parameter in the title bar climb toward 1.0 as period-doubling establishes itself. Switch to Oscillation view to see green cells indicating robust subharmonic response. Now increase ε (press `e` repeatedly) — at around ε≈0.15–0.20, the DTC melts as the system can no longer maintain coherent period-doubling. Click individual cells to flip their spins and observe how quickly the DTC self-heals — this robustness against local perturbations is the defining feature distinguishing a DTC from trivial oscillation. Compare the Clean DTC (which eventually thermalizes without disorder) to the Disordered DTC (where many-body localization prevents heating indefinitely). The Domain Walls preset reveals how DTC behavior nucleates differently at boundaries between spin domains.

**References**
- Wilczek, F. "Quantum Time Crystals," *Physical Review Letters*, 109, 2012. https://doi.org/10.1103/PhysRevLett.109.160401
- Else, D.V., Bauer, B., and Nayak, C. "Floquet Time Crystals," *Physical Review Letters*, 117, 2016. https://doi.org/10.1103/PhysRevLett.117.090402
- Zhang, J. et al. "Observation of a discrete time crystal," *Nature*, 543, 2017. https://doi.org/10.1038/nature21413
- Choi, S. et al. "Observation of discrete time-crystalline order in a disordered dipolar many-body system," *Nature*, 543, 2017. https://doi.org/10.1038/nature21426


---

## Topological Solitons

**Background** — Topological defects are singular configurations in continuous order-parameter fields that cannot be smoothed away by local perturbations — they are protected by topology. In the two-dimensional XY model, the relevant defects are point vortices carrying integer winding numbers: a vortex (q = +1) where the angle field winds by +2π around a closed loop, and an antivortex (q = −1) with −2π winding. These defects interact via a Coulomb-like logarithmic potential and can only be created or destroyed in opposite-charge pairs, conserving total topological charge. At the Berezinskii-Kosterlitz-Thouless (BKT) transition temperature, bound vortex–antivortex pairs unbind and proliferate, destroying quasi-long-range order in one of the most celebrated examples of a topological phase transition. When Dzyaloshinskii-Moriya interaction (DMI) is added, the field can support magnetic skyrmions — particle-like topological solitons with integer skyrmion number that are currently of intense interest for spintronic memory and logic applications.

**Formulation** — The simulation evolves a continuous angle field θ(r,c) ∈ [−π, π) on a 2D periodic lattice using overdamped Landau-Lifshitz-Gilbert dynamics:

```
∂θ/∂t = K·∇²θ + D·(DMI torque) − H_ext·sin(θ) + η(T)

Angle-wrapped Laplacian:
  ∇²θ ≈ Δ(θ_up, θ) + Δ(θ_down, θ) + Δ(θ_left, θ) + Δ(θ_right, θ)
  where Δ(a, b) = angle_diff(a, b) wraps to [−π, π)

DMI torque (antisymmetric exchange):
  τ_DMI = D·[sin(Δ(θ_right, θ)) − sin(Δ(θ_left, θ))
            + sin(Δ(θ_down, θ)) − sin(Δ(θ_up, θ))]

Zeeman coupling:
  τ_ext = −H_ext·sin(θ)

Thermal noise:
  η ~ N(0, √(2·T·dt))

Topological charge per plaquette:
  q = (1/2π)·[Δ(θ_01, θ_00) + Δ(θ_11, θ_01) + Δ(θ_10, θ_11) + Δ(θ_00, θ_10)]
  q ≈ +1 → vortex, q ≈ −1 → antivortex

Parameters:
  K     — stiffness / exchange coupling (0.1 to 3.0)
  T     — temperature / noise strength (0.0 to 2.0)
  D     — DMI strength (0.0 to 2.0), stabilises skyrmions
  H_ext — external Zeeman field (0.0 to 2.0)
  dt    = 0.15 (integration timestep)
```

Vortex imprinting uses superposed atan2 phase profiles with toroidal wrapping. Skyrmion textures are initialized as radial hedgehog profiles with θ varying from π at the core to 0 at the boundary.

**Presets** — Six configurations explore different regimes of topological defect physics:
- **Vortex Gas**: Random vortex–antivortex pairs in the XY field (T=0.1, K=1.0) — watch opposite-charge defects orbit each other via the log potential and annihilate on contact
- **BKT Transition**: Start near the Berezinskii-Kosterlitz-Thouless transition (T=0.5) — increase temperature to watch bound pairs unbind and proliferate, decrease to rebind them
- **Skyrmion Lattice**: DMI-stabilised magnetic skyrmions (D=0.5, H=0.3) — particle-like topological solitons that resist annihilation due to the energy barrier from antisymmetric exchange
- **Domain Walls**: Ising-like domain walls between ordered regions (K=1.5) — watch walls coarsen and straighten as the system minimizes gradient energy
- **Vortex Dipoles**: Tightly bound vortex–antivortex pairs (separation ≈ 3 cells) that propagate as composite solitons — the bound pair moves perpendicular to its dipole axis
- **Turbulent Defects**: High-temperature disordered field (T=0.8, K=0.8) producing a dense tangle of interacting defects — topological turbulence

**Visualization modes** (cycle with `v`):
- **Field**: Angle θ mapped to a hue wheel via directional arrows (→↗↑↖←↙↓↘), with ⊕ markers for vortices (red) and ⊖ for antivortices (blue). Defect trail positions are dimmed.
- **Charge**: Topological charge density — vortices and antivortices shown as bold glyphs, with fading trail dots (·) marking their motion history over the last ~80 timesteps.
- **Energy**: Local gradient energy density displayed as density glyphs (· ░▒▓█), colored from blue (low) through white and yellow to red (high). Reveals domain walls and defect cores as high-energy features.

**Controls**: `Space` play/pause, `n`/`.` single step, `v` cycle view, `t`/`T` increase/decrease temperature, `k`/`K` increase/decrease stiffness, `d`/`D` increase/decrease DMI, `h`/`H` increase/decrease external field, `+`/`-` adjust steps per frame, left-click place vortex, right-click place antivortex, `c` clear trails, `r` reset, `R` return to menu, `q` exit mode.

**What to look for** — Start with the Vortex Gas preset and watch how opposite-charge defects spiral toward each other and annihilate, reducing the total defect count over time. The title bar tracks ⊕ (vortex) and ⊖ (antivortex) counts along with the net topological charge Q, which is conserved (always zero for pair-created defects). Switch to the BKT Transition preset and slowly increase temperature with `t` — at around T ≈ 0.9 (depending on stiffness), you'll see the sudden proliferation of free vortices as the BKT transition unbinds pairs. The Skyrmion Lattice preset demonstrates how DMI creates an energy barrier that prevents skyrmion collapse; try reducing DMI with `D` to watch skyrmions shrink and eventually annihilate. Place your own vortex–antivortex pairs by clicking and watch them interact. In Charge view, the trail system reveals the trajectories defects follow before annihilation.

**References**
- Berezinskii, V.L. "Destruction of Long-range Order in One-dimensional and Two-dimensional Systems Possessing a Continuous Symmetry Group," *Soviet Physics JETP*, 34, 1972.
- Kosterlitz, J.M. and Thouless, D.J. "Ordering, metastability and phase transitions in two-dimensional systems," *Journal of Physics C*, 6, 1973. https://doi.org/10.1088/0022-3719/6/7/010
- Nagaosa, N. and Tokura, Y. "Topological properties and dynamics of magnetic skyrmions," *Nature Nanotechnology*, 8, 2013. https://doi.org/10.1038/nnano.2013.243
- Fert, A., Reyren, N., and Cros, V. "Magnetic skyrmions: advances in physics and potential applications," *Nature Reviews Materials*, 2, 2017. https://doi.org/10.1038/natrevmat.2017.31


---

## Spin Ice & Emergent Magnetic Monopoles

**Background** — Spin ice is a class of geometrically frustrated magnets in which local "ice rules" (analogous to Bernal-Fowler rules in water ice) constrain spin configurations. In a square-ice lattice, each vertex has four edges carrying arrow-spins, and the ground state requires exactly two arrows pointing in and two pointing out (2-in/2-out). Violations of this constraint behave as emergent magnetic monopole quasiparticles — fractionalized excitations that carry effective magnetic charge, are connected by observable Dirac strings, and interact via a Coulomb potential. First identified experimentally in pyrochlore materials like Dy₂Ti₂O₇ (Harris et al. 1997, Castelnovo et al. 2008), spin ice represents one of the most striking examples of emergent fractionalization in condensed matter physics.

This mode is scientifically distinct from the existing Ising Model (which has no geometric frustration or emergent fractionalized excitations) and the Magnetic Field Lines mode (which visualizes classical dipole fields rather than lattice-based emergent phenomena).

**Formulation** — The simulation uses a square-ice lattice where horizontal edges connect vertex (r,c) to (r,c+1) and vertical edges connect vertex (r,c) to (r+1,c). Each edge carries a spin σ = ±1 representing the arrow direction.

```
Vertex charge:
  Q(r,c) = (number of out-arrows) − (number of in-arrows)
  Q = 0  → ice rule satisfied (neutral vertex)
  Q > 0  → positive monopole (more out than in)
  Q < 0  → negative monopole / antimonopole (more in than out)

Energy:
  E = J * Σ_vertices Q(r,c)² − h * Σ_horizontal_edges σ(r,c)

Parameters:
  J     — ice-rule coupling strength (default 4.0), penalizes violations quadratically
  T     — temperature (0.01 to 20.0), controls thermal fluctuation strength
  h     — applied magnetic field (−5.0 to 5.0), favors horizontal arrow alignment
```

Dynamics proceed via Monte Carlo Metropolis sweeps: each sweep attempts to flip every edge once. A flip is accepted if it lowers the energy; otherwise it is accepted with probability exp(−ΔE/T). The energy change is computed locally from the two vertices sharing the flipped edge, giving O(1) cost per flip attempt.

**Presets** — Six configurations explore different regimes of spin-ice physics:
- **Equilibrium Ice**: Low temperature (T=0.5) starting from a perfect ice-rule ground state — watch rare thermal fluctuations create and quickly annihilate monopole pairs while the system maintains near-perfect 2-in/2-out order
- **Monopole Gas**: High temperature (T=8.0) producing a dense Coulomb plasma of monopoles and antimonopoles — the lattice is heavily disordered with ice-rule satisfaction dropping well below 100%
- **Field Quench**: Starts from an ordered ice state, then at sweep 20 a sudden field (h=3.0) is applied — watch the avalanche of monopole creation as the system reorders to align with the field
- **Dirac Strings**: Moderate temperature (T=1.5) with 3 injected monopole-antimonopole pairs — Dirac string visualization enabled by default, showing dotted lines connecting paired monopoles
- **Kagome Ice**: Triangular frustrated variant with random initial conditions — explores ice-rule physics on a different lattice geometry with 2-in/1-out constraints
- **Pauling Entropy**: Very low temperature (T=0.01) in a perfect ice state — demonstrates the residual entropy of the ice manifold (S/kB ≈ ln(3/2)/ln(2) ≈ 0.585 per vertex), first calculated by Linus Pauling in 1935

**Visualization** — The lattice is drawn with Unicode arrows (→←↑↓) on edges colored cyan. Vertices display their charge state: neutral vertices as dim dots (·), positive monopoles as bold red ⊕, and negative antimonopoles as bold blue ⊖. When Dirac string display is enabled, dotted magenta lines (∙) connect nearest monopole-antimonopole pairs via greedy distance matching.

**Controls**: `Space` play/pause, `n`/`.` single step, `t`/`T` decrease/increase temperature, `f`/`F` decrease/increase applied field, `d` toggle Dirac string display, `c` toggle charge display, `+`/`-` adjust sweeps per frame, `r` reset current preset, `R` return to preset menu, `q` exit mode.

**What to look for** — Start with Equilibrium Ice and watch the lattice maintain almost perfect ice-rule order at low temperature — the title bar shows ice-rule satisfaction near 100%. Increase temperature with `T` and watch monopoles proliferate as the system crosses over from the ice-rule regime to the monopole gas. In the Dirac Strings preset, enable string display with `d` and watch how the dotted lines connecting monopole-antimonopole pairs stretch and contract as the monopoles diffuse through the lattice. The Field Quench preset provides the most dramatic dynamics: after the field kicks in at sweep 20, a cascade of spin flips creates a wave of monopoles that propagates across the lattice before the system settles into a field-aligned state. In the Pauling Entropy preset, note how the energy remains very low but the system still has exponentially many ground states — this is the macroscopic degeneracy that gives water ice its anomalous residual entropy.

**References**
- Harris, M.J. et al. "Geometrical Frustration in the Ferromagnetic Pyrochlore Ho₂Ti₂O₇," *Physical Review Letters*, 79, 1997. https://doi.org/10.1103/PhysRevLett.79.2554
- Castelnovo, C., Moessner, R., and Sondhi, S.L. "Magnetic monopoles in spin ice," *Nature*, 451, 2008. https://doi.org/10.1038/nature06433
- Bramwell, S.T. and Gingras, M.J.P. "Spin Ice State in Frustrated Magnetic Pyrochlore Materials," *Science*, 294, 2001. https://doi.org/10.1126/science.1064761
- Pauling, L. "The Structure and Entropy of Ice and of Other Crystals with Some Randomness of Atomic Arrangement," *Journal of the American Chemical Society*, 57, 1935. https://doi.org/10.1021/ja01315a102


---

## Earthquake & Seismic Wave Propagation

**Background** — Earthquakes arise from the sudden release of accumulated tectonic stress along faults, where friction locks plates until stress exceeds the fault's yield strength and slip cascades across a rupture zone. The Burridge-Knopoff (1967) spring-block model captures this stick-slip instability with a one- or two-dimensional chain of blocks connected by springs and resting on a frictional surface driven at constant velocity. Despite its simplicity, the model reproduces the key statistical signatures of natural seismicity: the Gutenberg-Richter power-law frequency-magnitude distribution, Omori's law of aftershock decay, and characteristic earthquake recurrence cycles. This places earthquake dynamics squarely within the framework of self-organized criticality — the system naturally evolves toward a critical state where perturbations of all sizes can occur.

This mode fills a gap between the existing Tectonic Plates mode (large-scale plate motion over geological time) and Wave Equation mode (generic wave propagation) by focusing on the fault-scale rupture dynamics and seismic radiation that neither covers.

**Formulation** — The simulation uses a 2D lattice of spring-blocks with heterogeneous static friction thresholds:

```
Tectonic loading (each step):
  stress[r][c] += tectonic_rate

Rupture condition:
  stress[r][c] >= strength[r][c]  →  block fails (stick-slip)

Stress transfer (spring coupling):
  released = stress[r][c] * dynamic_drop
  stress[r][c] -= released
  stress[neighbor] += released * coupling  (for 4 von Neumann neighbors)

Strength reset (fault healing):
  strength[r][c] = base_strength * (1 + heterogeneity * (rand - 0.5))

Cascade: failures checked iteratively until no new ruptures (max 50 iterations)

Magnitude estimation:
  M ≈ (2/3) * log₁₀(n_ruptured_blocks) + 1.0

Seismic wave propagation (finite-difference wave equation):
  u_next[r][c] = damping * (2*u[r][c] - u_prev[r][c] + c² * Laplacian(u))
  P-wave speed: 1.5 cells/step, S-wave speed: 0.9 cells/step

Parameters:
  tectonic_rate  — stress loading per step (0.001 to 0.1)
  base_strength  — mean static friction threshold
  heterogeneity  — spatial variation in strength (0 to 1)
  coupling       — fraction of released stress transferred to neighbors
  dynamic_drop   — fraction of stress released during slip (0.85)
  damping        — wave energy dissipation per step (0.96)
```

**Presets**

| Preset | Key parameters | What it demonstrates |
|--------|---------------|---------------------|
| **Strike-Slip Fault** | Balanced coupling (0.15), moderate heterogeneity (0.4) | San Andreas-style lateral rupture with regular earthquake cycles |
| **Subduction Zone** | High coupling (0.25), high strength (1.4), slow loading | Megathrust earthquakes — long quiet periods punctuated by large cascades |
| **Swarm Seismicity** | Low strength (0.7), high heterogeneity (0.6), fast loading | Many small events clustering in space and time (volcanic/geothermal) |
| **Tsunami Generation** | Ruptures inject energy into a shallow-water wave field | Seafloor displacement creates expanding wave rings (separate wave grid) |
| **Induced Seismicity** | Central injection point raises pore pressure, reducing effective strength | Fluid injection triggers earthquakes near the well, expanding outward |
| **Coulomb Stress Transfer** | Ruptures apply angular cos(2θ) stress lobes to surrounding fault | One earthquake loads adjacent segments, triggering cascading sequences |

**Views** — Two display modes toggled with `v`:
- **Fault view**: Stress/rupture heatmap where characters scale with stress ratio (dim → green → yellow → red █ for active rupture). The Induced Seismicity preset shows the injection point as ◉.
- **Wave view**: Seismic wave propagation — P-waves (blue), S-waves (green), tsunami waves (cyan) spreading from rupture sources with Unicode density characters.

**Controls**: `Space` play/pause, `n`/`.` single step, `t`/`T` decrease/increase tectonic loading rate, `c`/`C` decrease/increase spring coupling, `v` toggle fault/wave view, `+`/`-` adjust steps per frame, `r` reset current preset, `R` return to preset menu, `q` exit mode.

**What to look for** — Start with Strike-Slip Fault and watch the characteristic earthquake cycle: uniform green stress buildup, scattered yellow patches approaching failure, then sudden red rupture cascades that release stress and reload the fault. The info bar shows a running b-value estimate from the Gutenberg-Richter distribution — values near 1.0 indicate realistic scaling. Switch to Subduction Zone for dramatic contrast: long quiet intervals followed by massive cascades that rupture most of the fault. In Swarm Seismicity, the high loading rate and low strength produce nearly continuous small events — notice how they cluster spatially. The Tsunami preset is best viewed in wave mode (`v`): watch concentric shallow-water waves expand from submarine ruptures. The Induced Seismicity preset shows earthquakes nucleating near the injection point (◉) and migrating outward as pore pressure diffuses. Coulomb Stress Transfer demonstrates earthquake triggering — one rupture's stress lobes load adjacent fault segments, producing sequences of events that march along the fault.

**References**
- Burridge, R. and Knopoff, L. "Model and theoretical seismicity," *Bulletin of the Seismological Society of America*, 57(3), 1967. https://doi.org/10.1785/BSSA0570030341
- Gutenberg, B. and Richter, C.F. "Frequency of earthquakes in California," *Bulletin of the Seismological Society of America*, 34(4), 1944. https://doi.org/10.1785/BSSA0340040185
- Omori, F. "On the after-shocks of earthquakes," *Journal of the College of Science, Imperial University of Tokyo*, 7, 1894.
- Bak, P. and Tang, C. "Earthquakes as a self-organized critical phenomenon," *Journal of Geophysical Research*, 94(B11), 1989. https://doi.org/10.1029/JB094iB11p15635
- King, G.C.P., Stein, R.S., and Lin, J. "Static stress changes and the triggering of earthquakes," *Bulletin of the Seismological Society of America*, 84(3), 1994. https://doi.org/10.1785/BSSA0840030935


---

## Geometric Optics & Light

**Background** — Geometric optics, or ray optics, treats light as rays that travel in straight lines and bend at interfaces between media according to Snell's law (described by Ibn Sahl in 984 and formalized by Willebrord Snellius in 1621). This framework explains reflection, refraction, total internal reflection, chromatic dispersion, and lens focusing — phenomena that underpin telescopes, microscopes, fiber optics, and solar concentrators. While wave optics is needed for diffraction and interference at small scales, geometric optics remains the workhorse of optical system design.

**Formulation** — The simulation traces rays through a 2D scene of optical elements using parametric ray-segment intersection:

```
Ray-segment intersection:
  Ray: P(t) = (px, py) + t * (dx, dy),  t > 0
  Segment: S(u) = (x1, y1) + u * (x2-x1, y2-y1),  u ∈ [0, 1]
  Solve for t and u via Cramer's rule; accept if t > 0.01 and 0 ≤ u ≤ 1

Reflection (mirrors):
  d_reflected = d - 2(d · n̂) n̂

Snell's law refraction (prisms, glass blocks):
  n₁ sin θ_i = n₂ sin θ_t

  Vector form:
    cos θ_i = -(d · n̂)          [flip n̂ if cos θ_i < 0]
    ratio = n₁ / n₂
    sin²θ_t = ratio² (1 - cos²θ_i)
    If sin²θ_t > 1: total internal reflection (reflect instead)
    cos θ_t = √(1 - sin²θ_t)
    d_refracted = ratio · d + (ratio · cos θ_i - cos θ_t) · n̂

Chromatic dispersion:
  n(λ) = n_base + Δn(λ)
  Spectral offsets Δn: red(-0.008), orange(-0.004), yellow(0),
                       green(+0.005), cyan(+0.010), blue(+0.016), violet(+0.024)
  Approximates Cauchy's equation: n(λ) ≈ A + B/λ²

Thin lens deflection:
  h = perpendicular distance from ray hit to lens center
  θ_deflection = -atan(h / f)     [f = focal length]
  d_new = normalize(d + sign · sin(θ) · n̂)

Diffraction grating (1st order):
  Δθ = asin(λ / (d_slit × 1000))
  Splits ray into ±1st order beams with wavelength-dependent angles

Parameters:
  n_air   = 1.00   (refractive index of air)
  n_glass = 1.52   (crown glass)
  n_fiber = 1.48   (fiber optic core)
  max_bounces = 200
  ray_step    = 0.3 cells
```

**Presets**

| Preset | Configuration | What it demonstrates |
|--------|--------------|---------------------|
| **Rainbow Prism** | Single glass prism (n=1.52), white light source (7 spectral rays) | Chromatic dispersion — white light splits into rainbow spectrum |
| **Telescope** | Two convex lenses (f=15, f=8) aligned on optical axis | Refracting telescope — parallel rays converge to eyepiece focus |
| **Microscope** | Objective (f=6) + eyepiece (f=12), nearby point source | Compound magnification from diverging source through two lens stages |
| **Fiber Optic Cable** | 12 mirror segments forming curved waveguide | Total internal reflection guiding light through bends |
| **Hall of Mirrors** | 6 flat mirrors at various angles, omnidirectional source | Multiple specular reflections creating complex ray patterns |
| **Solar Concentrator** | 14-segment parabolic mirror, parallel downward rays | Caustic focusing — all rays converge to a single focal point |

**Controls**: `Tab`/`e` cycle element selection, `WASD`/arrows move selected element, `[`/`]` rotate, `f`/`F` adjust focal length, `h` toggle caustic heatmap, `Space` animate source wobble, `+`/`-` adjust speed, `r` reset current preset, `R` return to preset menu, `q` exit mode.

**What to look for** — Start with Rainbow Prism and watch white light enter the prism as a single beam, then emerge as seven distinct spectral colors fanned out by wavelength-dependent refraction — violet bends most, red least. Rotate the prism with `[`/`]` to see total internal reflection kick in at steep angles. The Telescope preset shows how two properly spaced lenses can collimate diverging light. In Fiber Optic Cable, rays bounce off the waveguide walls via total internal reflection, demonstrating the principle behind optical fibers. The Solar Concentrator is best viewed with the caustic heatmap (`h`): the parabolic mirror focuses parallel rays to a bright focal point, with the heatmap revealing the intensity distribution. Hall of Mirrors produces the most complex ray patterns — move mirrors with arrow keys to create kaleidoscopic interference paths.

**References**
- Hecht, E. *Optics*, 5th ed., Pearson, 2017. ISBN 978-0133977226
- Born, M. and Wolf, E. *Principles of Optics*, 7th ed., Cambridge University Press, 1999. https://doi.org/10.1017/CBO9781139644181
- Saleh, B.E.A. and Teich, M.C. *Fundamentals of Photonics*, 3rd ed., Wiley, 2019. https://doi.org/10.1002/9781119506874


---

## Tokamak Fusion Plasma Confinement

**Background** — A tokamak (from the Russian acronym for "toroidal chamber with magnetic coils") is the leading design for achieving controlled thermonuclear fusion. First developed by Soviet physicists Tamm and Sakharov in the 1950s, the tokamak confines hydrogen plasma in a toroidal (doughnut-shaped) magnetic field created by external coils (toroidal field) and the plasma's own current (poloidal field). The helical field lines trace out nested flux surfaces, and particles follow these surfaces, remaining confined. The key figure of merit is the Lawson triple product n*T*tau_E — when it exceeds ~3x10^21 m^-3 keV s, the fusion plasma becomes self-sustaining (ignition). ITER, currently under construction in France, aims to demonstrate Q=10 (10x more fusion power than input heating). This simulation models the poloidal cross-section of a tokamak, capturing the essential physics of plasma heating, confinement, transport, and instabilities.

**Formulation** — The simulation tracks radial profiles of temperature T(rho) and density n(rho) on normalized flux coordinates rho in [0,1], where rho=0 is the magnetic axis and rho=1 is the last closed flux surface (LCFS):

```
Geometry (poloidal cross-section):
  Elongation kappa = 1.7, triangularity delta = 0.33
  Shafranov shift: axis displaced outward by 0.08*(1-|z/a|)
  Aspect ratio R/a = 3.0

Safety factor profile:
  q(rho) = q_axis + (q_edge - q_axis) * rho^2
  q_axis ~ 0.85-1.5 (preset-dependent), q_edge = 3.5

Energy balance (per flux surface):
  dW/dt = P_ohmic + P_NBI + P_alpha - P_bremsstrahlung - P_line_rad - W/tau_E

Heating:
  P_ohmic    ~ eta * j^2,  eta ~ T^{-3/2}  (Spitzer resistivity)
  P_NBI      ~ P_0 * exp(-(rho - 0.3)^2 / (2 * 0.3^2))  (Gaussian deposition)
  P_alpha    ~ 0.04 * n^2 * T^2  (DT fusion reactivity, simplified)

Losses:
  P_brems    ~ 0.005 * n^2 * sqrt(T)
  P_line_rad ~ 0.002 * n * T * Z_eff

Transport (radial diffusion):
  D_total = D_classical + D_anomalous + D_turbulent_fluctuation
  D_classical = 0.005, D_anomalous = 0.03 (L-mode) or 0.005 (H-mode edge)
  Laplacian diffusion: T_new = T + D * (T[i-1] + T[i+1] - 2*T[i])

Confinement:
  tau_E = 80 ticks (L-mode), 200 ticks (H-mode)
  L-H transition when P_heat > 0.6 (normalized threshold)

Lawson criterion:
  Triple product = n_core * T_core * tau_E (normalized to ignition = 1.0)
  Q = P_fusion / P_input

Instabilities:
  Sawtooth: q_axis < 1 triggers crash every 40 ticks — core T,n flatten to q=1 surface
  ELM: pedestal collapse every 25 ticks, ejects 15% of edge energy
  Disruption: thermal quench (5 ticks) + current quench (20 ticks)
  Runaway electrons: Dreicer acceleration when T,n collapse post-disruption
```

**Presets**

| Preset | Configuration | What it demonstrates |
|--------|--------------|---------------------|
| **Stable Ohmic Confinement** | No NBI, q_axis=1.5, L-mode | Resistive heating alone — plasma reaches modest temperature, stable but below fusion-relevant conditions |
| **H-Mode Transition** | NBI power 0.8, ELMs enabled | Auxiliary heating triggers L-H bifurcation — edge pedestal forms, confinement doubles, periodic ELM crashes regulate edge pressure |
| **Plasma Disruption** | Density 1.6 > limit 1.5, impurity 8% | Greenwald density limit breach — thermal quench dumps core energy in 5 ticks, current quench follows, massive wall loading |
| **ITER-Scale Burning Plasma** | NBI 1.2, alpha heating, B=1.5T, H-mode | Self-heated plasma approaching ignition — alpha power exceeds NBI, Q>10, Lawson bar climbs toward 1.0 |
| **Sawtooth Oscillations** | q_axis=0.85, NBI 0.4 | Internal kink mode — watch core temperature rise then periodically crash as q=1 reconnection flattens the profile |
| **Runaway Electron Beam** | Post-disruption at tick 20, low T/n | Dreicer field accelerates electrons when collisionality drops — exponentially growing runaway fraction strikes the wall |

**Controls**: `Space` play/pause, `v` cycle views (plasma/energy/graphs), `n` step, `b` toggle NBI heating, `d` trigger disruption, `+`/`-` speed, `r` restart, `R` return to preset menu, `q` exit mode.

**What to look for** — Start with Stable Ohmic Confinement to see the baseline: plasma heats slowly via resistive dissipation, temperature saturates as Bremsstrahlung losses balance heating. Switch to H-Mode Transition and watch the dramatic L-H bifurcation — when NBI pushes heating past the threshold, the edge suddenly steepens and confinement doubles, visible as the Lawson bar jumping upward. ELMs then periodically crash the edge pedestal, dumping bursts of energy to the SOL. The ITER-Scale preset is the most visually rewarding: alpha self-heating creates a positive feedback loop where hotter plasma fuses more, producing more alphas, heating further — watch Q climb past 10 and the Lawson triple product approach ignition. Sawtooth Oscillations show the mesmerizing periodic core crashes — temperature builds then suddenly redistributes outward. The Disruption preset demonstrates the catastrophic loss of confinement: the thermal quench dumps stored energy to the wall in just 5 ticks, followed by a slower current decay. The Runaway Electron Beam is the most dramatic failure mode — post-disruption, a beam of relativistic electrons forms and strikes the wall.

**References**
- Wesson, J. *Tokamaks*, 4th ed., Oxford University Press, 2011. https://doi.org/10.1093/acprof:oso/9780199592234.001.0001
- Freidberg, J.P. *Plasma Physics and Fusion Energy*, Cambridge University Press, 2007. https://doi.org/10.1017/CBO9780511755705
- Lawson, J.D. "Some criteria for a power producing thermonuclear reactor," *Proceedings of the Physical Society B*, 1957. https://doi.org/10.1088/0370-1301/70/1/303
- ITER Organization. "ITER — the way to new energy." https://www.iter.org


---

## Nuclear Reactor Physics & Meltdown Dynamics

**Background** — Nuclear fission power converts the binding energy released when heavy nuclei (U-235, Pu-239) split into kinetic energy of fission fragments and neutrons, ultimately producing heat. A fission chain reaction is self-sustaining when each fission event produces, on average, exactly one neutron that goes on to cause another fission — a condition called criticality (k-eff = 1.0). Subcritical (k < 1) means the reaction dies out; supercritical (k > 1) means exponential growth. Reactor control is the art of keeping k-eff precisely at 1.0 while extracting heat safely. This simulation models a pressurized water reactor (PWR) cross-section with the key physics that govern both normal operation and accident scenarios, including the mechanisms behind the three major nuclear accidents: Chernobyl (1986), Three Mile Island (1979), and Fukushima Daiichi (2011).

**Reactor geometry** — The 2D cross-section is a circular vessel containing:
- **Fuel cells**: U-235 fissile material arranged in a lattice pattern (`(r+c) % 3 == 0`)
- **Moderator cells**: Light water or graphite that thermalizes fast neutrons to increase fission probability (`(r+c) % 3 == 1`, absent in breeder preset)
- **Coolant channels**: Water flowing through the core to remove heat (`(r+c) % 3 == 2`)
- **Control rod channels**: 5 vertical columns of neutron-absorbing material (boron/hafnium), adjustable from fully inserted (0) to fully withdrawn (1)
- **Reflector ring**: Returns escaping neutrons back into the core (albedo 0.85)
- **Vessel wall**: Steel pressure boundary

**Neutron transport** — Neutron flux φ evolves via diffusion with sources and sinks:

```
φ_new = φ + D × ∇²φ + S_prompt + S_delayed - Σ_a × φ - Σ_Xe × Xe × φ

where:
  D = 0.25              diffusion coefficient
  ∇²φ                   4-neighbor Laplacian
  S_prompt = ν × Σ_f × φ × (1-β) × doppler × void_fb
  S_delayed = λ × C     delayed neutrons from precursor decay
  ν = 2.5               neutrons per fission
  Σ_f = 0.08 × enrich   fission cross-section
  Σ_a = 0.03            parasitic absorption
  Σ_Xe = 0.60           xenon-135 absorption (enormous)
  β = 0.0065            delayed neutron fraction
  λ = 0.08              precursor decay constant
```

The delayed neutron fraction β = 0.0065 is critical to reactor control — it slows the response time from microseconds (prompt neutron lifetime) to seconds (precursor half-lives), making human/mechanical control possible.

**Xenon-135 poisoning** — The most important fission product for reactor dynamics:

```
dI/dt = γ_I × φ - λ_I × I          (I-135: produced by fission, decays to Xe)
dXe/dt = λ_I × I + γ_Xe × φ - λ_Xe × Xe - σ_Xe × φ × Xe

where:
  γ_I = 0.006    I-135 fission yield
  γ_Xe = 0.003   Xe-135 direct fission yield
  λ_I = 0.0003   I-135 decay rate (half-life ~6.6 hours)
  λ_Xe = 0.0001  Xe-135 decay rate (half-life ~9.2 hours)
  σ_Xe = 0.60    Xe-135 absorption (2.6 × 10⁶ barns in reality)
```

At steady state, xenon burnup (σ_Xe × φ × Xe) balances production. On shutdown, burnup stops instantly but iodine continues decaying to xenon for hours, causing Xe concentration to *rise* — the "xenon pit." Attempting to restart during a xenon pit requires pulling control rods dangerously far out. This is exactly what happened at Chernobyl on April 26, 1986: operators withdrew nearly all rods to overcome xenon poisoning, then a sudden power surge in the RBMK's positive-void-coefficient core caused a prompt-critical excursion.

**Reactivity feedback** — Two temperature-dependent feedback mechanisms:

```
Doppler:  rate_modifier = 1 + α_D × max(0, T_fuel - 0.3)     α_D = -0.003 (always negative)
Void:     rate_modifier = 1 + α_v × void × 10                 α_v = -0.015 (PWR) or +0.012 (RBMK)
```

- **Doppler broadening** (always stabilizing): Hotter fuel broadens U-238 resonance absorption peaks, capturing more neutrons before they can cause fission.
- **Void coefficient** (design-dependent): In a PWR, steam voids reduce moderation, which reduces fission — a self-limiting negative feedback. In an RBMK like Chernobyl, the graphite moderator is separate from the water coolant, so steam voids reduce neutron absorption without reducing moderation — a dangerous positive feedback that amplifies power excursions.

**Thermal hydraulics** — Coupled heat generation and removal:

```
dT_fuel/dt = q_fission + q_decay + k∇²T - h(T_fuel - T_cool) × coolant × (1-void)
dT_cool/dt = h(T_fuel - T_cool) × 0.5 - flow × (T_cool - T_inlet) × coolant_level

where:
  q_fission = 0.15 × φ          heat from fission
  q_decay = 0.07 × P_history    decay heat (7% of operating power)
  k = 0.04                       fuel conductivity
  h = 0.08                       convective coefficient
  flow = 0.05 (pumps on) or 0.0025 (natural circulation)
  T_inlet = 0.15                 coolant inlet temperature
```

**Failure cascade sequence** — The progression from normal to catastrophe:

1. **Loss of coolant** (LOCA) or **loss of flow** (blackout) → reduced heat removal
2. **Coolant boiling** (T_cool > 0.55) → steam void formation
3. **Void feedback** → in RBMK: positive feedback accelerates fission; in PWR: negative feedback helps but may not be enough
4. **Cladding failure** (T_fuel > 0.80) → fission product release
5. **Zirconium-steam reaction** (T_fuel > 0.75) → hydrogen generation (H₂_rate = 0.005 × (T-0.75)), the gas that exploded at Fukushima
6. **Fuel melting** (T_fuel > 0.95) → loss of geometry, corium formation
7. **Corium slumping** → gravity-driven downward flow (P=0.02/tick)
8. **Containment pressurization** → steam + hydrogen → potential breach at P > 0.95

**Presets**

| Preset | Configuration | What it demonstrates |
|--------|--------------|---------------------|
| **Normal Power Operation** | rod_pos=0.45, PWR void coeff, SCRAM enabled | Steady-state criticality — watch k-eff hover near 1.0, xenon reach equilibrium, stable temperatures |
| **Control Rod Withdrawal Accident** | rod_pos=0.85, SCRAM disabled | Supercritical excursion — excess reactivity from withdrawn rods drives exponential flux growth |
| **Xenon Poisoning Restart (Chernobyl)** | rod_pos=0.90, RBMK +void coeff, high Xe/I, SCRAM disabled | The Chernobyl scenario — rods nearly fully out to overcome xenon pit, positive void coefficient creates runaway feedback |
| **Loss-of-Coolant Accident (TMI)** | Active LOCA breach, coolant draining | Three Mile Island analog — watch coolant level drop, fuel uncover, void fraction rise, partial meltdown |
| **Station Blackout (Fukushima)** | Pumps off, rod_pos=0.10, decay heat active | Fukushima scenario — reactor scrammed successfully but decay heat with no forced cooling slowly boils off coolant |
| **Breeder Reactor Fast Spectrum** | No moderator, enrichment 1.4×, fast neutrons | Fast reactor — no thermalization, higher enrichment compensates, breeding Pu-239 from U-238 blanket |

**Controls**: `Space` play/pause, `v` cycle views (cross-section/thermal/graphs), `+`/`-` adjust control rods, `s` emergency SCRAM, `n` step, `r` restart, `R`/`m` return to preset menu, `q` exit mode.

**What to look for** — Start with Normal Power Operation: watch neutron flux stabilize as the control rods balance fission production against absorption, observe xenon building to equilibrium over ~100 ticks, and note how Doppler feedback self-corrects small perturbations. Switch to the Xenon Poisoning Restart to see the Chernobyl mechanism in action: the initially suppressed flux suddenly surges as xenon burns away and the positive void coefficient amplifies the excursion — note how quickly the situation becomes unrecoverable with rods nearly fully withdrawn and SCRAM disabled. The LOCA preset shows the TMI scenario: coolant drains, void fraction climbs, fuel temperatures steadily rise toward melting — switch to the temperature view to watch the thermal front propagate. The Station Blackout preset is the most insidious: the reactor is safely shutdown (rods in), but the relentless 7% decay heat slowly boils away coolant with only natural circulation (5% of normal flow) available — watch the temperature creep upward over hundreds of ticks. The Breeder preset shows how a fast-spectrum reactor operates without a moderator, relying on higher enrichment and fast-neutron fission.

**References**
- Lamarsh, J.R. and Baratta, A.J. *Introduction to Nuclear Engineering*, 4th ed., Pearson, 2017.
- Todreas, N.E. and Kazimi, M.S. *Nuclear Systems I: Thermal Hydraulic Fundamentals*, 2nd ed., CRC Press, 2011. https://doi.org/10.1201/b14887
- GRS (Gesellschaft für Anlagen- und Reaktorsicherheit). "The Accident and the Safety of RBMK Reactors," GRS-121, 1996.
