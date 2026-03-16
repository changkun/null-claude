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

## Tectonic Plates

**Background** — Plate tectonics is the unifying theory of geology, explaining earthquakes, volcanism, mountain building, and ocean basin formation through the motion and interaction of rigid lithospheric plates over the asthenosphere. This simulation models Voronoi-tessellated plates with distinct velocities, reproducing convergent (subduction, mountain building), divergent (rifting, mid-ocean ridges), and transform boundaries over geological timescales.

**Formulation** — The simulation operates on a wrapped 2D grid with Voronoi-based plates:

```
Plate assignment: Voronoi tessellation from seed points
Each plate has: velocity (vr, vc), continental/oceanic flag

Per time step (1 MY):
  1. Shift plate cells by velocity (fractional accumulator)
  2. At boundaries, compute convergence = dot(relative_velocity, boundary_normal)
  3. Apply geological processes:
     Convergent (convergence > 0.1):
       Continental-continental: uplift += convergence * rand(40,120)  [capped at 9000m]
       Oceanic under continental: volcanic arc, random volcano spawning
       Oceanic-oceanic: trench deepening, island arc behind
     Divergent (convergence < -0.1):
       Continental rift or mid-ocean ridge (new crust at -2500 to -1500m)
     Transform: minor random elevation changes
  4. Volcanic eruptions at hotspots and active vents
  5. Erosion: blend 3% toward neighbor average, extra erosion above 5000m
  6. Isostatic rebound for trenches below -9000m

Elevation range: -11000m (Mariana Trench analog) to 9000m (Himalaya analog)
```

**What to look for** — "Pangaea Breakup" shows a supercontinent fragmenting as plates radiate outward, creating rift valleys that become oceans. "Continental Collision" produces a growing mountain range at the convergence zone. Toggle plate view with "p" to see the distinct Voronoi plates colored by identity. Volcanic activity (marked with "^") clusters along convergent boundaries.

**References**
- Vine, F.J. and Matthews, D.H. "Magnetic anomalies over oceanic ridges," *Nature*, 1963. https://doi.org/10.1038/199947a0
- Turcotte, D.L. and Schubert, G. *Geodynamics*, 3rd ed., Cambridge University Press, 2014. https://doi.org/10.1017/CBO9780511843877


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
