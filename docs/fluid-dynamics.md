# Fluid Dynamics

The motion of liquids, gases, and plasmas — from kitchen honey to interstellar magnetohydrodynamics.

This document covers the ten fluid dynamics simulation modes in Life Simulator. Each mode implements a distinct physical model, discretized for real-time ASCII visualization in the terminal. The models range from kinetic theory (Lattice Boltzmann) to continuum mechanics (Navier-Stokes), from astrophysical plasmas (MHD) to everyday viscous threads (fluid rope coiling).

---

## Lattice Boltzmann Fluid

**Background.** The Lattice Boltzmann Method (LBM) originated in the late 1980s as an alternative to directly solving the Navier-Stokes equations. Instead of tracking macroscopic velocity and pressure, LBM models the fluid as populations of fictitious particles streaming and colliding on a discrete lattice. The method was pioneered by McNamara and Zanetti (1988) and refined by Qian, d'Humieres, and Lallemand into the D2Q9 model used here. LBM is prized for its natural handling of complex boundaries and its inherent parallelism.

**Formulation.** The simulation uses the D2Q9 lattice (2 dimensions, 9 velocity directions) with the BGK (Bhatnagar-Gross-Krook) single-relaxation-time collision operator.

```
Lattice velocities (D2Q9):
  Direction i:  0   1   2   3   4   5   6   7   8
  ex:           0   1   0  -1   0   1  -1  -1   1
  ey:           0   0   1   0  -1   1   1  -1  -1

Weights:
  w_0 = 4/9,  w_{1..4} = 1/9,  w_{5..8} = 1/36

Equilibrium distribution:
  f_i^eq = w_i * rho * (1 + 3*(e_i . u) + 4.5*(e_i . u)^2 - 1.5*|u|^2)

BGK collision:
  f_i(x + e_i, t+1) = f_i(x, t) + omega * (f_i^eq - f_i)

where:
  rho = sum_i f_i          (density)
  u   = sum_i e_i * f_i / rho  (macroscopic velocity)
  omega = relaxation parameter (0.5 < omega < 2.0)
  nu  = (1/omega - 0.5) / 3    (kinematic viscosity)
```

Obstacle boundaries use the bounce-back rule: incoming distributions reverse direction. Inflow uses Zou-He-style equilibrium forcing; outflow copies from the interior. The lid-driven cavity preset instead enforces a moving wall velocity at the top boundary.

**What to look for.** At low omega (high viscosity), flow is smooth and laminar. Increase omega toward 1.9 and the flow transitions to turbulence with vortex shedding visible in the vorticity view. The Von Karman Street preset produces the classic alternating vortex wake behind a cylinder. Switch visualization modes (speed, vorticity, density) to see different aspects of the same flow. The Reynolds number displayed approximates Re = u_0 * L / nu.

**Presets:** Wind Tunnel (omega=1.4), Von Karman Street (omega=1.85), Lid-Driven Cavity (omega=1.5), Channel Flow (omega=1.6), Obstacle Course (omega=1.5), Turbulence (omega=1.9).

**References.**
- Qian, Y.H., d'Humieres, D., and Lallemand, P. "Lattice BGK Models for Navier-Stokes Equation." *Europhysics Letters*, 17(6), 1992. https://doi.org/10.1209/0295-5075/17/6/001
- McNamara, G.R. and Zanetti, G. "Use of the Boltzmann Equation to Simulate Lattice-Gas Automata." *Physical Review Letters*, 61(20), 1988. https://doi.org/10.1103/PhysRevLett.61.2332

---

## Navier-Stokes

**Background.** The Navier-Stokes equations are the fundamental description of viscous fluid motion, formulated by Claude-Louis Navier (1822) and George Gabriel Stokes (1845). This mode solves the 2D incompressible Navier-Stokes equations using Jos Stam's "Stable Fluids" method, which guarantees unconditional stability regardless of time step or viscosity. The approach splits each time step into diffusion, advection, and pressure projection.

**Formulation.** The velocity step proceeds as diffuse-project-advect-project, and the dye/scalar field follows a separate diffuse-advect cycle.

```
Incompressible Navier-Stokes:
  du/dt = -(u . grad)u - grad(p)/rho + nu * laplacian(u)
  div(u) = 0

Stam splitting (per timestep dt):

  1. Diffusion (implicit Gauss-Seidel, 20 iterations):
     x[r][c] = (x0[r][c] + a * sum_neighbors(x)) / (1 + a * n_neighbors)
     where a = dt * nu * N^2

  2. Pressure projection (Gauss-Seidel, 20 iterations):
     div = -0.5 * (h_x*(vx[c+1]-vx[c-1]) + h_y*(vy[r+1]-vy[r-1]))
     p[r][c] = (div + sum_neighbors(p)) / n_neighbors
     Then: vx -= 0.5 * (p[c+1] - p[c-1]) * cols
            vy -= 0.5 * (p[r+1] - p[r-1]) * rows

  3. Advection (semi-Lagrangian, bilinear interpolation):
     Trace particle backward: x_src = x - dt*N*vx, y_src = y - dt*N*vy
     Interpolate d[r][c] from d0 at (x_src, y_src)

Parameters:
  nu       = 0.0001   (kinematic viscosity)
  diffusion = 0.00001  (dye diffusion coefficient)
  dt       = 0.1       (time step)
  iterations = 20      (Gauss-Seidel relaxation count)
```

The dye field is passively advected through the velocity field and undergoes slow dissipation (multiplied by 0.999 each step). Users can interactively inject dye and momentum at the cursor position, and place or remove circular obstacles.

**What to look for.** The Vortex Pair preset shows two counter-rotating vortices that orbit and merge. The Karman Vortices preset demonstrates vortex shedding behind a circular obstacle, with dye bands making the alternating wake visible. The Shear Layer preset seeds Kelvin-Helmholtz instability: opposing flows create rolling vortices along the interface. Reduce viscosity to see finer turbulent structures; increase it to see smooth laminar flow.

**References.**
- Stam, J. "Stable Fluids." *Proceedings of SIGGRAPH 1999*, ACM, 1999. https://doi.org/10.1145/311535.311548
- Stam, J. "Real-Time Fluid Dynamics for Games." *Game Developers Conference*, 2003. https://www.dgp.toronto.edu/public_user/stam/reality/Research/pdf/GDC03.pdf

---

## Rayleigh-Benard Convection

**Background.** When a fluid layer is heated from below and cooled from above, it remains still until the temperature difference exceeds a critical threshold. Beyond that threshold, buoyancy overcomes viscous drag and the fluid organizes into convection cells -- rising hot plumes and sinking cold sheets. This phenomenon was studied experimentally by Henri Benard (1900) and analyzed theoretically by Lord Rayleigh (1916). It governs patterns in boiling water, Earth's mantle convection, solar granulation, and atmospheric weather cells.

**Formulation.** The simulation uses a 2D Boussinesq approximation: density variations are ignored except in the buoyancy term.

```
Boussinesq equations (simplified):

  Temperature:
    dT/dt = kappa * laplacian(T) - (u . grad)T

  Velocity:
    dvx/dt = nu * laplacian(vx) - (u . grad)vx
    dvy/dt = nu * laplacian(vy) - (u . grad)vy - Ra * C * (T - T_ref)

  Divergence reduction:
    4 Gauss-Seidel iterations pushing divergence to neighbors

where:
  Ra     = Rayleigh number (500 to 10000, controls convective vigor)
  Pr     = Prandtl number (nu/kappa: 0.025 for plasma, 0.71 for air, 10 for mantle)
  kappa  = 1.0 (thermal diffusivity, normalized)
  nu     = Pr  (kinematic viscosity)
  T_ref  = 0.5 * (T_hot + T_cold)
  C      = Ra * dt * 0.0001 (scaled buoyancy coefficient)

Boundary conditions:
  Top:    T = T_cold = 0.0, no-slip (vx = vy = 0)
  Bottom: T = T_hot  = 1.0, no-slip
  Sides:  Periodic in x

Advection uses first-order upwind differencing.
Velocities are clamped to [-5, 5] for stability.
```

**What to look for.** The Classic preset (Ra=2000, Pr=0.71) produces steady convection rolls that emerge from small sinusoidal perturbations. Increase Ra with the +/- keys to see rolls become unsteady and eventually turbulent. The Mantle preset (Pr=10) models Earth's interior: high viscosity produces broad, slow-moving cells. The Solar preset (Pr=0.025, Ra=10000) simulates stellar convection with vigorous, small-scale turbulence. Switch to vorticity view to see the roll boundaries where shear is strongest.

**Presets:** Classic Rolls (Ra=2000), Gentle Flow (Ra=500), Turbulent (Ra=8000), Hexagonal Cells (Ra=3000), Mantle Convection (Ra=1200, Pr=10), Solar Convection (Ra=10000, Pr=0.025), Asymmetric Heating (Ra=3000), Random (Ra=4000).

**References.**
- Rayleigh, Lord. "On Convection Currents in a Horizontal Layer of Fluid, When the Higher Temperature Is on the Under Side." *Philosophical Magazine*, 32(192), 1916. https://doi.org/10.1080/14786441608635602
- Chandrasekhar, S. *Hydrodynamic and Hydromagnetic Stability*. Oxford University Press, 1961. https://doi.org/10.1093/oso/9780198512790.001.0001

---

## SPH Fluid

**Background.** Smoothed Particle Hydrodynamics (SPH) represents a fluid as a collection of discrete particles, each carrying mass, velocity, and thermodynamic quantities. Originally invented by Gingold and Monaghan (1977) for astrophysical simulations, SPH was adapted for free-surface flows by Muller, Charypar, and Gross (2003). Unlike grid-based methods, SPH naturally handles splashing, fragmentation, and topological changes -- making it ideal for dam breaks, droplets, and fountains.

**Formulation.** Each particle stores position (x, y), velocity (vx, vy), density (rho), and pressure (P). The algorithm proceeds in five stages per timestep.

```
SPH Kernels:
  Poly6 (density):     W(r,h) = 315/(64*pi*h^9) * (h^2 - r^2)^3
  Spiky (pressure):    grad W = -45/(pi*h^6) * (h - r)^2 * r_hat
  Viscosity (laplacian): lap W = 45/(pi*h^6) * (h - r)

Algorithm per timestep:
  1. Density:  rho_i = sum_j m * W_poly6(|r_i - r_j|, h)

  2. Pressure (equation of state):
     P_i = k * (rho_i - rho_0)

  3. Forces:
     F_pressure = -sum_j m*(P_i+P_j)/(2*rho_j) * grad W_spiky
     F_viscosity = mu * sum_j m/rho_j * (v_j - v_i) * lap W_visc
     a_i = (F_pressure + F_viscosity) / rho_i + g

  4. Integration (symplectic Euler):
     v_i += a_i * dt
     x_i += v_i * dt

  5. Boundary collisions:
     Reflect with damping factor at walls

Default parameters:
  h (smoothing radius) = 1.5
  rho_0 (rest density)  = 1000
  k (gas constant)      = 2000
  mu (viscosity)        = 250
  g (gravity)           = 9.8
  dt                    = 0.003
  damping               = 0.5
```

The Fountain preset applies a continuous upward velocity kick to particles near the bottom center, creating a sustained jet that falls back under gravity.

**What to look for.** The Dam Break preset shows a column of water collapsing under gravity and splashing against the far wall. Watch for the wavefront, the splashback, and eventual sloshing equilibrium. The Drop preset shows a dense block falling into a pool, generating a crown splash. Increase gravity with +/- to see more energetic dynamics; the particles respond immediately because SPH is a Lagrangian method. The density visualization reveals pressure waves propagating through the fluid.

**Presets:** Dam Break, Double Dam, Drop Impact, Rainfall, Wave, Fountain.

**References.**
- Muller, M., Charypar, D., and Gross, M. "Particle-Based Fluid Simulation for Interactive Applications." *Proceedings of the 2003 ACM SIGGRAPH/Eurographics Symposium on Computer Animation*, 2003. https://doi.org/10.2312/SCA03/154-159
- Monaghan, J.J. "Smoothed Particle Hydrodynamics." *Annual Review of Astronomy and Astrophysics*, 30, 1992. https://doi.org/10.1146/annurev.aa.30.090192.002551

---

## MHD Plasma

**Background.** Magnetohydrodynamics (MHD) describes the behavior of electrically conducting fluids -- plasmas, liquid metals, and salt water -- in the presence of magnetic fields. The coupling between fluid flow and magnetic field produces phenomena with no analogue in ordinary fluids: magnetic reconnection, Alfven waves, and the formation of current sheets. Hannes Alfven received the 1970 Nobel Prize in Physics for founding MHD theory. This mode solves the resistive MHD equations in 2D using explicit finite differences.

**Formulation.** The simulation evolves five coupled fields: density (rho), velocity (vx, vy), and magnetic field (Bx, By).

```
Resistive MHD equations:
  d(rho)/dt = -div(rho*v) + 0.01 * laplacian(rho)     (continuity)
  dv/dt     = -(v.grad)v - grad(p)/rho + (JxB)/rho + nu*laplacian(v)  (momentum)
  dB/dt     = curl(v x B) + eta * laplacian(B)          (induction)

where:
  J = curl(B) = dBy/dx - dBx/dy     (current density, z-component only in 2D)
  p = p_coeff * rho                  (isothermal equation of state)

  Lorentz force (2D):
    Fx = Jz * By
    Fy = -Jz * Bx

  Induction equation (2D):
    Ez = vx*By - vy*Bx               (z-component of v x B)
    dBx/dt = -dEz/dy + eta * laplacian(Bx)
    dBy/dt =  dEz/dx + eta * laplacian(By)

Spatial discretization: 5-point stencil, central differences, periodic BCs
Time integration: explicit Euler, dt = 0.02
Velocity and B clamped to [-2, 2] for stability

Typical parameters:
  eta (resistivity): 0.005 - 0.050
  nu  (viscosity):   0.005 - 0.050
  p_coeff:           0.5 - 2.0
```

**What to look for.** The Harris Current Sheet preset initializes anti-parallel magnetic fields (Bx = tanh(y)) separated by a thin current layer. Over time, the tearing instability breaks the sheet into magnetic islands -- this is magnetic reconnection, the same process that powers solar flares. The Orszag-Tang Vortex is a classic MHD turbulence benchmark: initially smooth velocity and magnetic fields cascade into shock-like structures and current sheets. Switch to the "current" view to see where Jz concentrates -- these are reconnection sites. The "magnetic" view colors field lines by direction, revealing the topology of magnetic flux.

**Presets:** Harris Current Sheet, Orszag-Tang Vortex, Magnetic Island, MHD Blast Wave, Kelvin-Helmholtz (MHD), Double Current Sheet, Flux Rope, Random Turbulence.

**References.**
- Orszag, S.A. and Tang, C.M. "Small-Scale Structure of Two-Dimensional Magnetohydrodynamic Turbulence." *Journal of Fluid Mechanics*, 90(1), 1979. https://doi.org/10.1017/S0022112079000100
- Biskamp, D. *Magnetic Reconnection in Plasmas*. Cambridge University Press, 2000. https://doi.org/10.1017/CBO9780511599958

---

## Atmospheric Weather

**Background.** Weather systems arise from the interplay of solar heating, the Coriolis effect, moisture transport, and pressure gradients. This mode simulates synoptic-scale (hundreds of kilometers) atmospheric dynamics using a semi-Lagrangian advection scheme with parameterized physics. Pressure centers (highs and lows) drive geostrophic winds; fronts create temperature contrasts that trigger precipitation. The model captures the qualitative behavior described by the Norwegian cyclone model developed by Vilhelm Bjerknes and the Bergen School in the 1920s.

**Formulation.** The simulation tracks six fields: pressure, temperature, humidity, wind (u and v components), cloud density, and precipitation.

```
Pressure field:
  P(r,c) = 1013.25 + sum_centers[ dP * intensity * exp(-dist^2 / (2*R^2)) ]

Geostrophic wind (from pressure gradient + Coriolis deflection):
  u = -dP/dc * 0.5
  v = -dP/dr * 0.5
  u_new = u + f * v      (f = coriolis * sign(latitude))
  v_new = v - f * u
  coriolis = 0.15

Temperature/humidity advection (semi-Lagrangian):
  Trace back: src = (r,c) - (v,u) * 0.3 * speed
  Bilinear interpolation from source position

Cloud formation:
  tendency = humidity * 0.6 + lift * 0.3 - 0.3
  lift = (1013.25 - P) / 50     (low pressure = rising air)
  cloud += convergence * 0.1    (wind convergence enhances clouds)
  cloud = cloud * 0.8 + target * 0.2

Precipitation:
  if cloud > 0.6 and humidity > 0.65:
    precip = (cloud - 0.5) * humidity * 2.0
    type = snow if T < 2C, else rain
  Precipitation depletes humidity

Frontal effects:
  Cold front: T -= 0.5*strength, humidity += 0.05*strength
  Warm front: T += 0.3*strength, humidity += 0.08*strength
  Both reduce pressure along the front line
```

**What to look for.** The Cyclone preset shows a deep low-pressure center (960 hPa) with counterclockwise winds (Northern Hemisphere). Watch precipitation bands spiral inward. The Fronts preset demonstrates cold and warm fronts: the cold front (marked with triangles) pushes under warm air, triggering intense but narrow precipitation. The Arctic Outbreak shows a polar high driving cold air southward against a stationary warm air mass. Switch between layers (pressure, temperature, wind, humidity) to see different aspects of the same weather system. New pressure centers occasionally spawn, and fronts weaken over time.

**Presets:** Cyclone, Weather Fronts, High Pressure Dome, Monsoon, Arctic Outbreak, Random Weather.

**References.**
- Bjerknes, J. and Solberg, H. "Life Cycle of Cyclones and the Polar Front Theory of Atmospheric Circulation." *Geofysiske Publikationer*, 3(1), 1922. https://www.ngfweb.no/docs/NGF_GP_Vol03_no1.pdf
- Holton, J.R. *An Introduction to Dynamic Meteorology*, 4th ed. Elsevier Academic Press, 2004. https://doi.org/10.1016/C2009-0-63394-8

---

## Ocean Currents

**Background.** Ocean circulation is driven by wind forcing at the surface and density differences caused by temperature and salinity variations at depth -- the thermohaline circulation. Western boundary currents like the Gulf Stream are intensified by the Coriolis effect (western intensification, explained by Henry Stommel in 1948). This mode simulates both wind-driven gyres and thermohaline deep water formation, along with a simple biological model of plankton growth in nutrient-rich upwelling zones.

**Formulation.** The simulation evolves temperature, salinity, current velocity, nutrient concentration, and plankton density on a 2D grid.

```
Gyre circulation (applied to current field):
  For each gyre center (r_g, c_g) with radius R and strength S:
    falloff = exp(-dist^2 / (2*R^2))
    radial_scale = (dist/R) * exp(0.5 - dist/R)
    Tangential velocity: perpendicular to radius vector, magnitude = S * radial_scale * falloff

Coriolis deflection:
  u += coriolis * sign(lat) * v * 0.1
  v -= coriolis * sign(lat) * u * 0.1

Seawater density (simplified UNESCO equation):
  rho = 1000 + 0.8*S - 0.003*(T-4)^2 + 0.01*S*(35-S)

Thermohaline forcing:
  density gradient drives baroclinic currents:
    du -= d(rho)/dc * 0.0005
    dv -= d(rho)/dr * 0.0005

Deep water formation zones:
  Sinking: T decreases, S increases, downwelling
  Upwelling: nutrients increase, cold water rises

Advection: semi-Lagrangian with bilinear interpolation
  src = (r,c) - (v,u) * 0.25 * speed

Plankton dynamics (logistic + grazing):
  growth = 0.04 * nutrient * light * temp_factor * (1 - plankton)
  decay  = 0.015 * plankton
  grazing = 0.02 * plankton^2
  plankton += growth - decay - grazing
  Plankton consumes nutrients; dead plankton recycles 30% back

Upwelling = horizontal current divergence:
  div = d(u)/dc + d(v)/dr
  Positive divergence -> upwelling -> nutrient enrichment
```

**What to look for.** The Gulf Stream preset shows a strong northward western boundary current with mesoscale eddies spinning off the jet. The Thermohaline Conveyor shows warm surface water flowing north, cooling and sinking at the poles, then returning at depth -- the "great ocean conveyor belt." The El Nino preset demonstrates how weakened trade winds allow warm water to spread eastward, suppressing upwelling and devastating plankton productivity on the eastern coast. Switch to the plankton layer to see blooms forming in upwelling zones where cold, nutrient-rich water reaches the surface.

**Presets:** Gulf Stream, Pacific Gyre, Antarctic Circumpolar, El Nino, Thermohaline Conveyor, Random Ocean.

**References.**
- Stommel, H. "The Westward Intensification of Wind-Driven Ocean Currents." *Transactions, American Geophysical Union*, 29(2), 1948. https://doi.org/10.1029/TR029i002p00202
- Rahmstorf, S. "Ocean Circulation and Climate During the Past 120,000 Years." *Nature*, 419, 2002. https://doi.org/10.1038/nature01211

---

## Fluid Rope / Honey Coiling

**Background.** When a viscous fluid like honey is poured from a height onto a surface, the falling thread does not simply pile up. Instead, it coils, folds, and meanders in regular patterns -- a phenomenon known as the liquid rope coiling instability. The coiling frequency depends on the fall height, flow rate, and viscosity. This was first systematically studied by G.I. Taylor (1968) and later analyzed in detail by Ribe, Habibi, and Bonn. The same physics governs how shampoo coils in your palm and how lava ropes form on volcanic flows.

**Formulation.** The simulation models a falling viscous thread that coils upon contact with an accumulating pool below.

```
Rope dynamics:
  Pour point: (pour_x * cols, pour_y * rows)  -- top center nozzle
  Surface:    pour_y + pour_height             -- where coiling occurs

  Coiling motion:
    coil_angle += coil_speed * dt
    land_x = base_x + coil_radius * cos(coil_angle)

  Stream shape (each segment i of N):
    frac = i / (N-1)
    target_x = pour_x * (1 - frac^2) + land_x * frac^2
    wobble = sin(t*3 + i*0.5) * 0.3 * frac * viscosity
    segment_x = target_x + wobble

  Fall speed (gravitational acceleration along stream):
    speed_i = 0.5 + frac * 2.0

Pool accumulation:
  deposit = flow_rate * dt * 0.8
  Gaussian spread around landing point: radius ~ coil_radius * 1.5
  deposit_col += deposit * (1 - |dx|/(spread+1))^2

Viscous spreading:
  spread_rate = 0.02 / max(0.3, viscosity)
  pool[c] += (avg_neighbors - pool[c]) * spread_rate

  Pool height capped at 35% of screen height

Parameters by preset:
  Honey:     viscosity=1.0, flow_rate=1.0, height=0.70, coil_speed=2.5, coil_radius=3.0
  Chocolate: viscosity=0.7, flow_rate=1.3, height=0.60, coil_speed=3.5, coil_radius=2.5
  Shampoo:   viscosity=0.5, flow_rate=1.5, height=0.55, coil_speed=5.0, coil_radius=2.0
  Lava:      viscosity=2.0, flow_rate=0.6, height=0.80, coil_speed=1.2, coil_radius=4.5

dt = 0.02
```

**What to look for.** The Honey preset produces slow, wide coils -- the thread is thick and viscous, so it resists bending and makes large loops. The Shampoo preset coils much faster with a tighter radius because the lower viscosity allows the thread to buckle more readily. Try adjusting the pour height (h/H keys): taller falls produce faster coiling because the thread velocity at impact is higher. Move the surface laterally (s/S keys) to see the thread transition from coiling to folding to meandering -- the same regime transitions observed in laboratory experiments. The Lava preset shows the slowest, broadest coiling pattern with maximum viscosity.

**References.**
- Ribe, N.M. "Coiling of Viscous Jets." *Proceedings of the Royal Society A*, 460(2051), 2004. https://doi.org/10.1098/rspa.2004.1353
- Habibi, M., Maleki, M., Golestanian, R., Ribe, N.M., and Bonn, D. "Dynamics of Liquid Rope Coiling." *Physical Review E*, 74(6), 2006. https://doi.org/10.1098/rspa.2004.1353

---

## Fluid of Life (CA + LBM Coupled)

**Background.** Cellular automata and fluid dynamics are two of the most productive frameworks for studying emergent complexity, but they are almost always studied in isolation. The Game of Life operates on a discrete grid with discrete time; Navier-Stokes (or its kinetic surrogate, Lattice Boltzmann) operates on continuous fields. The Fluid of Life mode couples them into a single system: live cells are buoyant particles that inject momentum into a surrounding fluid, and the fluid velocity field advects cells to new grid positions before the next CA generation is applied. This two-way coupling produces qualitatively new phenomena — gliders that curve along streamlines, oscillators that generate vortex streets, and guns that pump coherent fluid jets — that exist only at the intersection of discrete life and continuous flow.

The idea of coupling particle-like automata with continuum fluid has roots in the immersed boundary method (Peskin, 1972), where elastic structures interact with viscous flow. Here the "structure" is the CA itself: living cells exert force on the fluid (buoyancy), and the fluid exerts force on the cells (advection). The result is a hybrid system where neither layer alone predicts the emergent behavior.

**Formulation.** The fluid uses the D2Q9 Lattice Boltzmann method (same formulation as the standalone LBM mode). The CA uses standard Conway B3/S23 rules. The coupling is:

```
Two-way coupling:

  Cell → Fluid (buoyancy forcing during BGK collision):
    If cell[r][c] is alive:
      uy[r][c] -= buoyancy_strength    (upward force, negative y)

  Fluid → Cell (semi-Lagrangian advection):
    For each live cell at (r, c):
      dx = ux[r][c] * advection_strength
      dy = uy[r][c] * advection_strength
      nr = r + round(dy * 20)    (scaled displacement)
      nc = c + round(dx * 20)
      Move cell to (nr, nc) if target is empty and not a wall
      On collision: cell stays at original position

  Interactive objects inject additional forces:
    Fan (4 directions): constant force ±0.05 in chosen axis
    Heater:  uy -= buoyancy * 3   (strong upward)
    Cooler:  uy += buoyancy * 3   (strong downward)
    Wall:    LBM bounce-back + blocks cell movement

Timing:
  LBM runs fluidlife_steps_per_frame sub-steps each frame (1–10)
  Advection runs every frame
  CA runs every ca_interval frames (1–20)

LBM parameters per preset:
  omega     = 1.4 – 1.8   (relaxation, controls viscosity via nu = (1/omega - 0.5)/3)
  inflow    = 0.01 – 0.08  (left boundary equilibrium velocity)
  buoyancy  = 0.0005 – 0.0020
  advection = 0.10 – 0.25  (velocity-to-displacement scaling)
```

**What to look for.** The Glider Stream preset places five SE-traveling gliders in a gentle rightward wind. Watch them curve — the wind adds a rightward component to their natural diagonal trajectory, producing arcing paths. The Blinker Vortices preset arranges 24 blinkers in a grid; each oscillation cycle pulses buoyancy on and off, stirring the fluid into a lattice of counter-rotating vortices visible in the vorticity view. The Gosper Gun Jet preset fires a stream of gliders that collectively pump a coherent fluid jet across the domain. The Convection Cells preset seeds heaters along the bottom and coolers along the top, driving Rayleigh-Bénard-like convection rolls that carry CA cells in rising and falling streams.

Use the interactive tools to experiment: place a wall to deflect a glider stream, add a heater beneath an oscillator to loft it upward, or create a fan tunnel to accelerate structures. Switch visualization modes to see the coupled view (age-colored cells + velocity arrows), fluid speed field, pure CA, or vorticity.

**Presets:** Glider Stream (ω=1.6), Blinker Vortices (ω=1.5), Gosper Gun Jet (ω=1.7), Thermal Soup (ω=1.4), Wind Tunnel (ω=1.8), Convection Cells (ω=1.5).

**References.**
- Peskin, C.S. "Flow Patterns around Heart Valves: A Numerical Method." *Journal of Computational Physics*, 10(2), 1972. https://doi.org/10.1016/0021-9991(72)90065-4
- Qian, Y.H., d'Humieres, D., and Lallemand, P. "Lattice BGK Models for Navier-Stokes Equation." *Europhysics Letters*, 17(6), 1992. https://doi.org/10.1209/0295-5075/17/6/001
- Berlekamp, E.R., Conway, J.H., and Guy, R.K. *Winning Ways for Your Mathematical Plays*, Vol. 2. A K Peters, 2003.

---

## Ferrofluid Dynamics

**Background.** A ferrofluid is a colloidal suspension of magnetic nanoparticles (~10 nm diameter) coated with a surfactant and dispersed in a carrier liquid. Invented by Steve Papell at NASA in 1963 for magnetically controlled rocket fuel, ferrofluids exhibit some of the most visually striking self-organization in condensed matter physics. When a uniform magnetic field is applied perpendicular to the surface of a ferrofluid pool, the flat surface becomes unstable above a critical field strength and erupts into a regular hexagonal array of spikes — the Rosensweig instability, first analyzed by Ronald Rosensweig in 1985. The instability arises because the magnetic pressure at a surface perturbation peak is stronger than at a trough (the field concentrates at tips), creating a positive feedback that is opposed by surface tension and gravity. The critical field B_crit marks the balance point; above it, the surface spontaneously breaks translational symmetry into a lattice of sharp spikes.

Ferrofluids also exhibit labyrinthine stripe patterns when confined as a thin film in a perpendicular field (competing short-range surface tension and long-range dipolar repulsion create meandering domain walls), and chain/columnar structures when a uniform field aligns the magnetic dipoles into pearl-chain aggregates. This mode captures all three regimes — Rosensweig spikes, labyrinthine domains, and dipolar chains — in a single simulation framework, filling a gap between the project's discrete Ising magnetic model and its continuum MHD plasma solver.

**Formulation.** Each grid cell stores a fluid height h ∈ [0, 1], a vertical velocity v, and a local magnetisation magnitude M. The dynamics combine five forces:

```
Per-cell forces:

  1. Magnetic body force (Kelvin force):
     F_mag = μ * h * (B_local - B_crit)
     If B_local > B_crit (supercritical):
       F_mag += 0.5 * μ * (B_local - B_crit)^2 * h
     This creates positive feedback: taller regions in a supercritical
     field experience stronger upward force, driving spike growth.

  2. Field gradient force:
     F_grad = μ * h * |∇B| * 0.3
     Draws fluid toward field maxima (paramagnetic attraction).

  3. Surface tension (Laplacian smoothing):
     F_surface = γ * (avg_neighbors(h) - h)
     Opposes sharp height gradients, stabilising short wavelengths.

  4. Gravity:
     F_grav = -g * h
     Opposes spike growth, sets the characteristic spike height.

  5. Dipolar chaining (for chain/spike presets):
     F_chain = 0.02 * μ * B * sum_neighbors(h_neighbor - h)
     Neighbouring magnetised regions attract, promoting columnar alignment.

Velocity update (damped):
  v_new = v * damping + F_total
  v_new clamped to [-0.5, 0.5]

Height update:
  h_new = h + v_new
  h_new clamped to [0.0, 1.0]

Magnetisation (linear susceptibility):
  M = μ * B_local

Post-step corrections:
  Labyrinthine preset: long-range dipolar repulsion via Moore-neighborhood
    difference creates stripe domains:
    repulsion = sum_8neighbors(h_self - h_neighbor)
    v += 0.015 * μ * B * repulsion

  Chain preset: directional alignment bias along field angle θ:
    Neighbours along field direction attract more strongly than
    perpendicular neighbours, promoting columnar structure.

Field configurations:
  Uniform:     B(r,c) = B₀ + gx*(c - c_mid) + gy*(r - r_mid)
  Point source: B(r,c) = B₀ * 8 / (dist_to_center + 3)
  Dual source:  B = sum of two point sources at 1/3 and 2/3 of width
  Sweeping:     B oscillates with sin/cos of generation count

Parameters:
  B₀        = 0.0–2.0   (applied field strength)
  B_crit    = 0.45       (Rosensweig threshold)
  γ         = 0.05–0.12  (surface tension)
  g         = 0.01–0.04  (gravity)
  μ         = 0.6–0.8    (magnetic susceptibility)
  damping   = 0.97       (viscous dissipation)
```

**What to look for.** The Rosensweig Spikes preset starts with a flat fluid surface at supercritical field (B=0.6 > B_crit=0.45). Within a few hundred steps, small random perturbations amplify into a hexagonal spike array — the classic normal-field instability. Watch the spike count stabilize as surface tension limits the spatial frequency. Increase B with the `b` key to see spikes grow taller and sharper; decrease below B_crit to watch them collapse back to a flat surface.

The Labyrinthine Maze preset models a thin ferrofluid film. The competing forces — surface tension (short-range smoothing) vs. dipolar repulsion (long-range domain alternation) — produce meandering stripe domains reminiscent of magnetic garnet films. The pattern never settles into a static equilibrium; domains continuously rearrange.

The Chain Columns preset scatters random droplets that coalesce into elongated columnar structures aligned with the field direction. Rotate the field angle with `a`/`A` to see the chains reorient in real time.

Switch views with `v`: top-down (height glyphs with spike markers for tall features), side (cross-section profile through the middle row showing the spike silhouette), and magnetisation (M intensity field showing where the magnetic response is strongest). Click to drop additional fluid and watch it get pulled toward existing spikes by the field gradient.

**Presets:** Rosensweig Spikes (B=0.6, γ=0.08), Labyrinthine Maze (B=0.5, γ=0.12), Chain Columns (B=0.7, γ=0.05), Field-Responsive Art (sweeping gradient), Hedgehog Spikes (point-source B=0.8), Dual Magnets (two-source interference B=0.65).

**References.**
- Rosensweig, R.E. *Ferrohydrodynamics*. Cambridge University Press, 1985. (Reprinted by Dover, 2013.) https://doi.org/10.1017/CBO9780511564109
- Cowley, M.D. and Rosensweig, R.E. "The Interfacial Stability of a Ferromagnetic Fluid." *Journal of Fluid Mechanics*, 30(4), 1967. https://doi.org/10.1017/S0022112067001740
- Richter, R. and Barashenkov, I.V. "Two-Dimensional Solitons on the Surface of Magnetic Fluids." *Physical Review Letters*, 94(18), 2005. https://doi.org/10.1103/PhysRevLett.94.184503

---

## Superfluid Helium

**Background.** Below the lambda point (T_λ ≈ 2.17 K), liquid helium-4 undergoes a phase transition into a superfluid state — a macroscopic quantum phenomenon first observed by Pyotr Kapitsa and independently by John Allen and Don Misener in 1937. The superfluid component flows without viscosity and its circulation is quantized in units of κ = h/m_He ≈ 9.97 × 10⁻⁴ cm²/s. Rotation and turbulence in He-II manifest not as smooth vorticity but as a tangle of discrete vortex filaments, each carrying exactly one quantum of circulation. When two vortex filaments of opposite sign approach, they reconnect — a topological event that redistributes energy and emits Kelvin waves (helical displacement oscillations) along the vortex cores. These Kelvin waves cascade to smaller scales and eventually radiate phonons into the fluid, providing the primary dissipation mechanism in quantum turbulence.

The two-fluid model, developed by Laszlo Tisza (1938) and refined by Lev Landau (1941), describes He-II as an interpenetrating mixture of a superfluid component (density ρ_s, zero viscosity, zero entropy) and a normal component (density ρ_n, finite viscosity, carries all entropy). The ratio ρ_s/ρ varies from 0 at T_λ to 1 at absolute zero. This two-fluid picture predicts a remarkable phenomenon: second sound — temperature waves that propagate as coupled oscillations of entropy and superfluid/normal counterflow, distinct from ordinary (first) sound pressure waves. Second sound was predicted by Tisza and Landau and first observed by Vasily Peshkov in 1944.

This mode bridges the project's quantum physics modes (which are discrete/lattice-based) and classical fluid modes (which have continuous vorticity), simulating quantized vortex dynamics with reconnection, Kelvin wave cascades, two-fluid counterflow, second sound propagation, and the lambda-point phase transition.

**Formulation.** Vortices are modeled as point objects in 2D (cross-sections of 3D filaments), each carrying a signed circulation charge q = ±1. Each vortex stores position (x, y), charge, and Kelvin wave state (phase, amplitude).

```
Biot-Savart velocity (each vortex i):
  v_i = sum_{j != i} κ * q_j / (2π * r²_ij) * (ẑ × r̂_ij)

  where r_ij is the separation vector with toroidal wrapping,
  regularised: r² = max(|r_ij|², 0.5) to prevent core singularity.

  In components:
    vx_i += -dy_ij * κ * q_j / (2π * r²_ij)
    vy_i +=  dx_ij * κ * q_j / (2π * r²_ij)

Mutual friction (coupling to normal fluid):
  F_mf = α * (v_n - v_s)
  vx_i += α * (vn_x - vx_i)
  vy_i += α * (vn_y - vy_i)

  where α = mutual friction coefficient (0.0–1.0)
  and v_n = imposed normal fluid velocity (counterflow preset)

Position update:
  x_i += vx_i * dt,   y_i += vy_i * dt
  dt = 0.15 * ρ_s/ρ   (timestep scales with superfluid fraction)
  Toroidal boundary conditions

Reconnection:
  When opposite-sign vortices approach within d_crit = 1.5:
    Both vortices annihilate (topological charge conserved: +1 + -1 = 0)
    Energy released as entropy pulse: Gaussian heat deposit at midpoint
    Tracked by reconnection counter

Kelvin waves:
  Each vortex has oscillation state (phase θ, amplitude A):
    θ += ω,  where ω = 0.3 * ρ_s/ρ   (dispersion: ω ∝ k² ln(1/ka), simplified)
    A *= 0.995                          (cascade damping)
    Position perturbation: dx = 0.05 * A * cos(θ), dy = 0.05 * A * sin(θ)

Superfluid fraction (two-fluid model):
  ρ_s/ρ = 1 - (T/T_λ)^5.6   for T < T_λ
  ρ_s/ρ = 0                   for T >= T_λ

  The exponent 5.6 approximates the experimental He-4 curve;
  the exact behavior near T_λ follows the 3D XY universality class
  with critical exponent ν ≈ 0.6717.

Temperature ramping:
  T → T_target at rate 0.003 K/step (for lambda-point transition preset)

Second sound propagation (wave equation on entropy field):
  c₂² = 0.3 * (ρ_s/ρ) / (ρ_n/ρ)    (second sound speed squared)

  ∂²s/∂t² = c₂² ∇²s

  Discretised:
    rho_v[r][c] = rho_v[r][c] * 0.998 + c₂² * laplacian(entropy)
    entropy[r][c] += rho_v[r][c]

  Clamped: entropy ∈ [-0.5, 1.0], rho_v ∈ [-0.5, 0.5]
  When ρ_s → 0 or ρ_n → 0, second sound ceases (no propagation medium)

Counterflow vortex generation:
  Probability of spontaneous pair nucleation ∝ |v_n| * ρ_s/ρ * 0.05
  Capped at 200 vortices total

Above lambda point (ρ_s = 0):
  No superfluid dynamics; entropy field undergoes simple diffusion
  diffusion coefficient = 0.1

Velocity field (for visualisation):
  Coarse-grained Biot-Savart sum on a sampled grid (step = min(rows,cols)/30)
  Block-filled for rendering speed

Energy spectrum:
  Radial shell binning of |v|² from the velocity field
  Normalised to [0, 1] for display
  Reference: Kolmogorov k^(-5/3) scaling line
```

**What to look for.** The Quantum Turbulence preset (T=1.2 K, 25 vortex-antivortex pairs) produces a dense tangle that evolves through repeated reconnections. Watch the vortex count decrease as pairs annihilate, and switch to the energy view to see whether the spectrum follows the Kolmogorov k⁻⁵/³ scaling — a key prediction of Kolmogorov's 1941 theory that has been confirmed in superfluid turbulence experiments by Maurer and Tabeling (1998).

The Vortex Reconnection preset places four opposite-sign pairs aimed at each other. Watch them approach, reconnect (annihilate), and emit entropy pulses visible in the density view. The reconnection count in the info bar tracks these events.

The Kelvin Wave Cascade preset (T=0.8 K) arranges 16 positive vortices in a ring with mode-3 Kelvin wave perturbation. The helical oscillations slowly damp as energy cascades to smaller scales — this is the quantum analogue of the Richardson cascade in classical turbulence.

The Two-Fluid Counterflow preset (T=1.6 K) imposes a normal fluid velocity vn=0.3 rightward while the superfluid is stationary. The resulting mutual friction generates vortex pairs spontaneously — the counterflow instability first studied by Vinen (1957). Increase counterflow with `c` to see more vigorous pair production; decrease to let the tangle decay.

The Second Sound preset (T=1.4 K) initializes a Gaussian temperature pulse at the center. Watch the ring-shaped wave expand outward — this is second sound, a temperature wave unique to superfluids. Vortices scatter the wave, creating interference patterns. Inject additional pulses with `s`.

The Lambda Point Transition preset starts above T_λ (T=2.5 K, normal fluid) and cools toward 0.5 K. As T drops below 2.17 K, the superfluid fraction grows from zero, vortex dynamics activate, and the system transitions from diffusive thermal behavior to coherent quantum vortex dynamics. Watch ρ_s/ρ in the title bar increase from 0.00 to ~0.99.

**Presets:** Quantum Turbulence (T=1.2K, 25 pairs), Vortex Reconnection (T=1.0K, 4 aimed pairs), Kelvin Wave Cascade (T=0.8K, vortex ring with mode-3 perturbation), Two-Fluid Counterflow (T=1.6K, vn=0.3), Second Sound (T=1.4K, central temperature pulse), Lambda Point Transition (T=2.5→0.5K, cooling ramp).

**References.**
- Donnelly, R.J. *Quantized Vortices in Helium II*. Cambridge University Press, 1991. https://doi.org/10.1017/CBO9780511564123
- Barenghi, C.F., Skrbek, L., and Sreenivasan, K.R. "Introduction to Quantum Turbulence." *Proceedings of the National Academy of Sciences*, 111(Supplement 1), 2014. https://doi.org/10.1073/pnas.1400033111
- Vinen, W.F. "Mutual Friction in a Heat Current in Liquid Helium II." *Proceedings of the Royal Society A*, 240(1220), 1957. https://doi.org/10.1098/rspa.1957.0071
- Tisza, L. "Transport Phenomena in Helium II." *Nature*, 141, 1938. https://doi.org/10.1038/141913a0
