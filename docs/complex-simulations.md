# Complex Simulations & Audio-Visual

Multi-physics systems and aesthetic visualizations — where science meets art in the terminal.

---


## Traffic Flow (Nagel-Schreckenberg Model)

**Background.** The Nagel-Schreckenberg (NaSch) model, introduced in 1992, is a foundational cellular automaton for traffic simulation. It reproduces the spontaneous formation of phantom traffic jams -- stop-and-go waves that appear with no external cause. Each lane is a one-dimensional lattice with periodic boundaries, and each cell is either empty or occupied by a car carrying an integer velocity. This implementation extends the basic model with multi-lane lane-changing (STCA symmetric rule), scenario-based road features (bottlenecks, on-ramps, incidents), and a real-time fundamental diagram overlay showing the flow-density phase transition.

**Formulation.** The NaSch update applies four rules simultaneously to all cars each timestep:

```
1. Acceleration:   v(t+1) = min(v(t) + 1, vmax)
2. Braking:        v(t+1) = min(v(t+1), gap)
                   where gap = (distance to next car ahead) - 1
3. Randomization:  with probability p_slow:
                       v(t+1) = max(v(t+1) - 1, 0)
4. Movement:       position(t+1) = (position(t) + v(t+1)) mod L
```

**Lane-changing (STCA).** Before the NaSch update, vehicles evaluate adjacent lanes using the Symmetric Two-Cell Asymmetric rule:

```
Change lane if ALL of:
  - gap_current < v + 1          (not enough room ahead)
  - gap_target > gap_current     (target lane is better)
  - gap_back_target >= vmax      (won't cut off car behind)
  - target cell is empty
```

**Scenario types.** Each preset selects one of four road configurations:

- **open** — periodic ring road (standard NaSch boundary conditions)
- **bottleneck** — speed limit drops to vmax=2 in the centre third of the road, causing flow breakdown and upstream queuing
- **onramp** — a slip road injects cars into lane 0 at a configurable rate, disrupting mainline flow with merging disturbances
- **incident** — a permanent obstacle (stalled vehicle) blocks one lane at the road midpoint, producing a rubbernecking cascade

**Parameters:**

```
  vmax    — maximum speed (cells/step), typically 5
  p_slow  — stochastic braking probability, range [0, 1]
  density — fraction of cells initially occupied (ρ)
  L       — lane length (adapts to terminal width)

Diagnostics:
  avg_speed = Σv_i / N_cars
  flow (J)  = Σv_i / (lanes × L)
  density (ρ_measured) = N_cars / (lanes × L)
```

**Fundamental diagram.** The flow vs. density scatter plot (drawn in ASCII on the right side of the road view) reveals the characteristic inverted-V shape: flow rises linearly in the free-flow regime (ρ < 0.15), peaks near the critical density, then collapses as stop-and-go waves dominate. A filled circle marks the current operating point.

**Space-time diagram.** Toggled with `v`, this view plots position (x-axis) against time (y-axis, newest at bottom), with color/density encoding average speed. Phantom jams appear as dark bands propagating upstream (to the left) — the hallmark kinematic wave of the NaSch model.

**Presets (10):** Open Highway, Moderate Flow, Rush Hour, Gridlock, Bottleneck, On-Ramp Merge, Incident, Cautious Drivers, Aggressive Drivers, Wide Highway (8 lanes).

**Controls:** `Space`=play/pause, `n`=step, `v`=view toggle (road/space-time), `f`=fundamental diagram on/off, `l`=lane-changing on/off, `d/D`=decrease/increase density, `p/P`=adjust braking probability, `+/-`=simulation speed, `r`=reset, `R`=menu.

**What to look for.** At low density (ρ < 0.15), all cars cruise at vmax and flow increases linearly with density. Near a critical density (ρ ~ 0.35-0.45), phantom jams nucleate from the randomization step and propagate backward as kinematic waves — visible as upstream-moving dark bands in the space-time view. At high density, persistent stop-and-go waves dominate. Raising p_slow increases jam frequency; lowering it creates smoother flow that collapses more catastrophically. In the Bottleneck preset, watch for flow breakdown at the speed-limit transition. In On-Ramp Merge, observe how merging vehicles create disturbances that propagate upstream on the mainline. Toggle lane-changing off to see how single-lane dynamics differ — jams form more readily without the pressure-relief valve of lane changes.

**References.**
- Nagel, K. & Schreckenberg, M. "A cellular automaton model for freeway traffic." *Journal de Physique I*, 2(12), 2221-2229, 1992. https://doi.org/10.1051/jp1:1992277
- Chowdhury, D., Santen, L. & Schadschneider, A. "Statistical physics of vehicular traffic and some related systems." *Physics Reports*, 329(4-6), 199-329, 2000. https://doi.org/10.1016/S0370-1573(99)00117-9
- Rickert, M., Nagel, K., Schreckenberg, M. & Latour, A. "Two lane traffic simulations using cellular automata." *Physica A*, 231(4), 534-550, 1996. https://doi.org/10.1016/0378-4371(95)00442-4

---

## Galaxy Formation

**Background.** This N-body simulation models the gravitational dynamics of spiral galaxies. Particles representing stars and gas orbit within an analytic dark matter halo whose gravitational potential follows an NFW (Navarro-Frenk-White) profile. The simulation demonstrates how logarithmic spiral arms, velocity dispersion, tidal interactions, and gas pressure give rise to the rich morphological diversity observed in galaxies -- from grand-design spirals to ellipticals and mergers.

**Formulation.** Each particle i carries state [x, y, vx, vy, mass, type] and evolves via leapfrog integration:

```
Halo force (NFW-like profile):
  r     = sqrt((x - cx)^2 + (y - cy)^2)
  F_halo = -G * M_halo * r / (r + r_s)^2

Grid-based particle-particle gravity (binned to 4-cell resolution):
  F_pp  = G * m_bin / (d^2 + epsilon^2)
  where d = distance to bin center-of-mass, epsilon = softening

Gas pressure (for gas particles, type > 0.5):
  If local_density > 3.0:
    F_pressure = 0.5 * (density - 3.0) * (outward direction)
  Gas cooling: v *= 0.998 per step

Circular orbital velocity (initialization):
  v_circ = sqrt(G * M_halo * r / (r + r_s)^2 + 0.1)

Spiral arm placement (logarithmic spiral perturbation):
  angle = base_angle + arm_index * (2*pi / N_arms) + 0.3 * ln(1 + r) * N_arms

Leapfrog integration:
  v(t + dt/2) = v(t) + a(t) * dt
  x(t + dt)   = x(t) + v(t + dt/2) * dt

Parameters:
  G           — gravitational constant (default 1.0, range 0.1-5.0)
  M_halo      — dark matter halo mass (300-1000)
  r_s         — halo scale radius (15-30)
  dt          — timestep (default 0.03)
  epsilon     — softening length (1.0)
```

**What to look for.** In the Milky Way and Grand Design presets, watch spiral arms wind up over time. The Whirlpool preset features a companion galaxy on an infall trajectory producing tidal tails. The Merger preset shows two disk galaxies colliding, producing a burst of tidal debris. Elliptical galaxies maintain a pressure-supported spheroid with no net rotation. Toggling the dark matter halo overlay (h key) reveals the NFW density profile underlying all dynamics. Gas particles experience drag and pressure, collecting in spiral arm density peaks.

**References.**
- Navarro, J.F., Frenk, C.S. & White, S.D.M. "The Structure of Cold Dark Matter Halos." *The Astrophysical Journal*, 462, 563, 1996. https://doi.org/10.1086/177173
- Toomre, A. & Toomre, J. "Galactic Bridges and Tails." *The Astrophysical Journal*, 178, 623-666, 1972. https://doi.org/10.1086/151823

---

## Smoke & Fire

**Background.** This mode simulates combustion and buoyant fluid dynamics on an Eulerian grid. Temperature, smoke density, fuel, and velocity fields interact through simplified Navier-Stokes-like advection, diffusion, and buoyancy. The approach follows the seminal work of Stam (1999) on stable fluids, adapted for real-time ASCII rendering. Fire sources inject heat, which rises through buoyancy, consumes fuel through combustion, and generates smoke that dissipates over time.

**Formulation.** Five scalar fields are evolved each timestep: temperature T, smoke S, fuel F, and velocity (vx, vy).

```
Buoyancy (heat rises):
  vy -= buoyancy * T

Wind and turbulence:
  vx += wind
  vx += random(-0.5, 0.5) * turbulence * (1 + T * 2)
  vy += random(-0.5, 0.5) * turbulence * 0.5

Velocity damping:
  vx *= 0.85,  vy *= 0.85

Combustion (fuel burns when T > 0.2 and F > 0.01):
  burn = min(F, 0.05 * T)
  F   -= burn
  T   += burn * 3.0     (heat release)

Fire spread (when T > 0.4, to 4-connected neighbors):
  If neighbor has fuel > 0.1 and T < 0.3:
    neighbor.F -= 0.002
    neighbor.T += 0.05 * T

Smoke production:  S += T * smoke_rate * 0.3
Cooling:           T -= cooling * (1 + height_fraction * 0.5)
Smoke dissipation: S *= 0.985;  S -= 0.003

Semi-Lagrangian advection (bilinear interpolation):
  source = (r - vy, c - vx)
  T_new = 0.4 * T_local + 0.6 * T_sampled
  S_new = 0.4 * S_local + 0.6 * S_sampled

Diffusion (4-neighbor averaging):
  T = 0.8 * T + 0.2 * mean(T_neighbors)
  S = 0.85 * S + 0.15 * mean(S_neighbors)

Presets:           buoyancy  turbulence  cooling  smoke_rate  wind
  Campfire         0.15      0.04        0.012    0.3         0.0
  Wildfire         0.12      0.06        0.008    0.4         0.02
  Explosion        0.25      0.12        0.02     0.6         0.0
  Candles          0.10      0.02        0.018    0.15        0.0
  Inferno          0.20      0.08        0.006    0.5         0.01
  Smokestack       0.18      0.05        0.01     0.5         0.03
```

**What to look for.** The Campfire preset shows a steady flickering flame with a rising smoke plume. Wildfire demonstrates fire spread across a fuel-laden landscape with wind-driven propagation. The Explosion preset creates a radial blast wave with outward velocity. Increasing turbulence produces chaotic, billowing flames; increasing buoyancy makes flames taller and thinner. Fire sources flicker stochastically with intensity modulated by 0.7 + random * 0.3. Users can interactively place fire sources and fuel patches.

**References.**
- Stam, J. "Stable Fluids." *Proceedings of SIGGRAPH '99*, ACM, 121-128, 1999. https://doi.org/10.1145/311535.311548
- Nguyen, D.Q., Fedkiw, R. & Jensen, H.W. "Physically Based Modeling and Animation of Fire." *ACM Transactions on Graphics*, 21(3), 721-728, 2002. https://doi.org/10.1145/566654.566643

---

## Fireworks

**Background.** This particle system simulates pyrotechnic displays using Newtonian projectile dynamics. Rockets launch upward against gravity, explode at apogee into bursts of sparks following various geometric patterns, and fade with trailing afterimages. The simulation captures the physics of ballistic trajectories, air drag, and gravitational settling that give real fireworks their characteristic arc and droop.

**Formulation.** Two entity types are simulated: rockets and spark particles.

```
Rocket dynamics:
  vr += gravity           (deceleration during ascent)
  vc += wind
  r  += vr,  c += vc
  Explode when: fuse <= 0 OR vr >= 0 (apex reached)

Spark dynamics after burst:
  vr += gravity * k       (k = 1.5 for willow, 0.8 for others)
  vc += wind
  vr += random(-0.02, 0.02)   (jitter)
  vc += random(-0.02, 0.02)
  vr *= drag              (drag = 0.97 for willow, 0.985 for others)
  vc *= drag
  r  += vr,  c += vc

Burst patterns:
  Spherical:  N=30-60 sparks, angle ~ U(0, 2*pi), speed ~ U(0.3, 1.2)
  Ring:       N=24-40 sparks, angle = 2*pi*i/N, uniform speed
              Optional inner ring at 50% radius
  Willow:     N=40-70 sparks, long life (30-55 ticks), high gravity
  Crossette:  4-6 sub-rockets that each re-explode as spherical bursts

Parameters:
  gravity     — downward acceleration (default 0.05)
  launch_rate — probability of auto-launch per tick (0.04-0.18)
  wind        — horizontal drift per tick
  fuse        — random height in [rows/4, rows*2/3]

Trail rendering: 6-element position history, oldest entries dimmer
Life fraction:   life / max_life determines spark brightness
```

**What to look for.** The Finale preset uses a high launch rate with all burst patterns randomized, creating dense overlapping displays. Willow shells produce long, drooping trails that trace parabolic arcs under high gravity multiplier. Crossette shells create a cascade effect: each sub-rocket travels outward before detonating into its own secondary burst. Increasing gravity shortens burst radius and makes sparks fall faster; wind causes coherent lateral drift across all active particles. Trail rendering creates persistence-of-vision streaks.

**References.**
- Reeves, W.T. "Particle Systems -- A Technique for Modeling a Class of Fuzzy Objects." *ACM Transactions on Graphics*, 2(2), 91-108, 1983. https://doi.org/10.1145/357318.357320
- Sims, K. "Particle Animation and Rendering Using Data Parallel Computation." *Computer Graphics (SIGGRAPH '90 Proceedings)*, 24(4), 405-413, 1990. https://doi.org/10.1145/97880.97923

---


## Sonification Engine (Generative Soundscape)

**Source:** `life/modes/sonification.py`

**Background.** The sonification engine is a cross-cutting audio layer that attaches to any running simulation mode and maps its spatial dynamics to a real-time generative music composition. Rather than a standalone mode, it operates as a toggleable overlay (Ctrl+A) that transforms the simulator from a purely visual experience into a synesthetic one — Conway's Game of Life sounds fundamentally different from a fluid simulation or a strange attractor. The engine synthesizes four simultaneous voices (bass, melody, harmony, rhythm) using additive waveform synthesis, with musical parameters driven by frame-by-frame analysis of the simulation's spatial state.

**Formulation.** Five core mappings translate simulation metrics to musical parameters:

```
1. Population density → Pitch register:
   density_shift = (density - 0.3) * 18 semitones
   pitch_mult = 2^(density_shift / 12)
   Applied to bass, melody, and harmony root frequencies.
   Bass clamped to [30, 500] Hz.
   Effect: sparse simulations rumble in sub-bass; dense ones climb into mid-range.

2. Entropy → Chord complexity:
   entropy < 0.15:  open fifth [0, 7]
   entropy < 0.3:   triad [0, 4, 7]
   entropy < 0.5:   seventh [0, 4, 7, 11]
   entropy < 0.7:   ninth [0, 4, 7, 11, 14]
   entropy >= 0.7:  extended [0, 2, 4, 7, 9, 11, 14]
   Entropy is Shannon entropy of the row density distribution, normalized
   to [0, 1]. Ordered patterns stay consonant; chaos produces rich harmony.

3. Spatial clusters → Stereo panning:
   Column profile is scanned for contiguous density peaks (threshold > 0.03).
   Each cluster's centroid maps to a pan position: pan = centroid / n_cols.
   Falls back to quadrant-based panning when no clusters are detected.
   Per-voice stereo placement:
     Bass:    always centered (pan 0.5)
     Melody:  panned to primary (loudest) cluster
     Harmony: chord voices spread across detected clusters (round-robin)
     Rhythm:  panned opposite to melody (1.0 - primary_pan)
   More clusters = wider stereo image.

4. Rate of change (delta) → Rhythm density:
   delta = |density(t) - density(t-1)|
   scaled = min(1.0, delta * 5.0)
   Pattern index = floor(scaled * N_patterns)
   Patterns range from sparse 4-on-floor to dense 16th-note syncopation.
   Rhythm voice mix level also scales with delta.

5. Center of mass → Melody contour:
   register_shift = (0.5 - cy) * 8 semitones
   Higher center of mass = higher melodic register.
   Column density peaks select scale degrees for arpeggiated melody.

Voice synthesis:
  Bass:    0.8 * sin(phase) + 0.2 * sawtooth(phase), portamento between frames
  Melody:  weighted mix of sine, sawtooth, pulse (per category profile)
           Per-step envelope with 3ms attack/decay ramps
  Harmony: sine pad, per-voice stereo from cluster positions
  Rhythm:  0.6 * noise + 0.4 * sin(perc_phase), gated by pattern, fast decay

Master volume = 0.08 + 0.4 * density + 0.2 * min(1.0, delta * 10)
Voice levels normalized: bass ~35%, melody ~30%, harmony ~20%, rhythm ~15%
  (adjusted by drone level, activity, entropy, and delta)

Audio output: 22050 Hz, S16LE stereo, via paplay/aplay/afplay
Frame duration: delay * 0.8 * tempo_mult, clamped to [0.04, 1.5] seconds

Audio profiles per category (12 defined):
  Category              base_freq  scale              tempo  drone
  Classic CA            220 Hz     pentatonic          1.0    0.0
  Particle & Swarm      330 Hz     minor pent + b7     1.5    0.0
  Physics & Waves       196 Hz     major               0.8    0.3
  Fluid Dynamics        110 Hz     in-sen              0.6    0.5
  Chemical & Biological 261 Hz     harmonic minor      0.9    0.2
  Fractals & Chaos      174 Hz     whole-tone-ish      0.7    0.4
  (and 6 more)
```

**What to look for.** Toggle sonification with Ctrl+A during any running simulation. In a Game of Life glider gun, you'll hear a steady low-register pulse with sparse rhythm; as the field fills, the pitch register climbs and chord complexity increases. In Boids, the melody pans across the stereo field as the flock moves. In Reaction-Diffusion, high entropy produces extended 9th/13th chords while stable Turing patterns stay in simple triads. In chaotic rules like Seeds (B2/S), expect dense syncopated rhythms and wide chord voicings. The status bar shows the current root note, melody note count, cluster count (pan:N), and frame number.

**References.**
- Hermann, T., Hunt, A. & Neuhoff, J.G. *The Sonification Handbook*. Logos Publishing House, 2011. https://sonification.de/handbook/
- Vickers, P. & Hogg, B. "Sonification Abstraite/Sonification Concrète: An 'Aesthetic Perspective Space' for Classifying Auditory Displays." *Journal of the Audio Engineering Society*, 2006.

---

## Music Visualizer

**Background.** This mode generates synthetic audio waveforms from musical tone sequences and visualizes them through six rendering modes: spectrum analyzer, oscilloscope waveform, beat-reactive particles, a combined view, a bass-driven tunnel effect, and frequency rain. The audio pipeline synthesizes additive harmonics, simulates an FFT spectrum, and implements a simple beat detection algorithm based on energy thresholds.

**Formulation.** Audio synthesis and analysis are performed each frame:

```
Waveform synthesis (additive harmonics):
  sample(t) = 0.6 * sin(2*pi * f * t)
            + 0.25 * sin(2*pi * 2f * t)
            + 0.1  * sin(2*pi * 3f * t)
            + 0.05 * sin(2*pi * 5f * t)
            + noise ~ N(0, 0.05)
  Amplitude modulation: sample *= 0.7 + 0.3 * sin(2*pi * 0.5 * t)

  where f = base frequency from tone pattern, cycling at 4 notes/sec
  Tone patterns rotate every 2 seconds

Simulated FFT (spectrum bins):
  For each harmonic h with amplitude a:
    bin = floor(f * h / max_freq * N_bars)
    spectrum[bin +/- 1] += a * falloff   (falloff: 1.0 center, 0.4 adjacent)
  Bass rumble: spectrum[0..3] += 0.3 * (0.5 + 0.5 * sin(2*pi * 2 * t)) * sens

Peak decay:
  peak[i] = max(spectrum[i], peak[i] * 0.95)

Beat detection:
  beat_avg = beat_avg * 0.9 + energy * 0.1
  Beat triggers when: energy > beat_avg * 1.5 AND energy > 0.15
  On beat: spawn 5-15 particles radially from center

Band energies:
  bass = mean(spectrum[0 : N/3])
  mid  = mean(spectrum[N/3 : 2N/3])
  high = mean(spectrum[2N/3 : N])

Tunnel effect (view mode 4):
  For each pixel at (dx, dy) from center:
    angle = atan2(dy, dx)
    depth = 1.0 / distance
    u = angle/pi + t * 0.5
    v = depth + t * (1 + bass * 3)
    pattern = sin(u * 8) * sin(v * 4), modulated by bass energy
    brightness = min(1, 2 / (distance + 0.5))
```

**What to look for.** The spectrum view shows FFT bars colored by frequency band (bass/mid/high) with floating peak indicators that decay slowly. Beat detection triggers particle bursts and border flashes on the waveform view. The tunnel view warps with bass energy, creating a zoom-in effect on heavy beats. Four color schemes (Spectrum, Fire, Ocean, Neon) map intensity to different palettes. Sensitivity control scales all amplitudes linearly.

**References.**
- Smith, J.O. "Spectral Audio Signal Processing." W3K Publishing, 2011. https://ccrma.stanford.edu/~jos/sasp/
- Scheirer, E.D. "Tempo and beat analysis of acoustic musical signals." *Journal of the Acoustical Society of America*, 103(1), 588-601, 1998. https://doi.org/10.1121/1.421129

---

## Snowfall & Blizzard

**Background.** This mode simulates snowfall with realistic particle dynamics including wind gusts, ground accumulation, snow drifting, and temperature-dependent flake behavior. Each snowflake is an independent particle affected by gravity, wind, and lateral wobble. Snow accumulates column by column on the ground and can be redistributed by wind, forming drifts. The simulation captures the visual character of weather ranging from gentle flurries to arctic whiteouts.

**Formulation.** Each snowflake carries state [x, y, vx, vy, size, wobble_phase]:

```
Wind gusts (sinusoidal variation):
  gust = 0.4 * sin(phase) + 0.2 * sin(2.3 * phase + 1.0)
  effective_wind = wind_speed * wind_dir + gust

Lateral wobble:
  wobble_phase += dt * (2.0 + size * 0.5)
  wobble = sin(wobble_phase) * (0.15 + size * 0.05)

Velocity update:
  target_vx = effective_wind * (0.6 + size * 0.1)
  vx += (target_vx - vx) * 0.1      (smooth wind response)
  vx += wobble * 0.1
  vy  = 0.3 + size * 0.2 + random(-0.05, 0.05)
  If temperature > 0: vy *= 0.8      (wet snow falls slower)

Accumulation (per-column height):
  When flake hits ground_level:
    accumulation[col] += 0.02 + size * 0.01

Snow drifting (when |wind| > 0.5):
  transfer = accumulation[i] * |wind| * 0.002
  accumulation[i] -= transfer
  accumulation[i + wind_dir] += transfer
  Smoothing: a[i] = 0.98*a[i] + 0.01*(a[i-1] + a[i+1])

Ground drift particles (when |wind| > 1.0):
  Spawn from snow pile tops, blown horizontally

Presets:         density  wind   temp    visibility  max_accum
  Gentle            80    0.3    -3C     1.00        rows/4
  Steady           180    1.2    -8C     0.75        rows/3
  Blizzard         400    3.5    -15C    0.35        rows/2
  Whiteout         600    5.0    -25C    0.15        rows/2
  Wet Snow         120    0.5    +1C     0.85        rows/5
  Squall           350    2.5    -10C    0.45        rows/3

Flake sizes: 0=small, 1=medium, 2=large
  Warmer temperatures bias toward larger (wetter) flakes
```

**What to look for.** In gentle mode, individual flakes trace sinusoidal paths as they drift down. At blizzard intensity, the sheer particle count and horizontal wind create near-horizontal streaks with greatly reduced visibility. Snow accumulates into uneven drifts shaped by wind direction -- reversing wind direction (d key) gradually reshapes the terrain. Warm temperatures produce slower, heavier flakes. Ground-level drift particles are blown off snow pile peaks in high wind, adding texture near the surface.

**References.**
- Fearing, P. "Computer Modelling of Fallen Snow." *Proceedings of SIGGRAPH '00*, ACM, 37-46, 2000. https://doi.org/10.1145/344779.344936
- Moeslund, T.B., Madsen, C.B., Aagaard, M. & Lerche, D. "Modeling Falling and Accumulating Snow." *Vision, Video and Graphics*, 2005. https://doi.org/10.2312/egs20051023

---

## Matrix Digital Rain

**Background.** Inspired by the iconic cascading green characters from the 1999 film *The Matrix*, this mode renders columns of falling character streams with head-glow, brightness decay, and stochastic character mutation. The algorithm creates an illusion of depth through layered streams with varying speeds and lengths within each column.

**Formulation.** Each column maintains a list of independent streams:

```
Stream state: {y, speed, length, chars[], age, mutate_rate}

Stream spawning:
  speed       ~ U(0.3, 1.5)
  length      ~ randint(4, max(5, rows/2))
  mutate_rate ~ U(0.02, 0.1)
  New streams spawn with probability: density * 0.02 per column per step

Stream update:
  y += speed
  For each char in stream:
    If random() < mutate_rate: replace with random char from pool
  Remove stream when: (y - length) > rows + 5

Brightness model (per character cell):
  fraction = index / (length - 1)     (0 = head, 1 = tail)
  brightness:
    index == 0:     4 (head — rendered white)
    fraction < 0.2: 3 (near head — bright green)
    fraction < 0.5: 2 (mid — normal green)
    else:           1 (tail — dim green)

  Later streams overwrite earlier (front layering)

Character pools:
  Katakana:  half-width katakana block (U+FF66-FF9D)
  Digits:    0-9
  Latin:     A-Z
  Symbols:   =+*#@!?%&<>{}[]
  Binary mode: "01" only

Color modes: green (classic), blue, rainbow
  Rainbow: color_pair = (col * 7 + generation) % 6 + 1

Presets:    density  speed  chars
  Classic   0.40     2      full set
  Dense     0.75     3      full set
  Sparse    0.15     1      no symbols
  Katakana  0.40     2      katakana only
  Binary    0.50     2      "01" only
  Rainbow   0.40     2      full set, rainbow color
```

**What to look for.** The white "head" of each stream creates the illusion of an advancing cursor, while the dimming tail fades into the background. Character mutation (flickering) makes streams appear to continuously decode new data. Dense mode fills most columns, creating a near-solid wall of falling text. Sparse mode leaves large gaps, emphasizing individual stream trajectories. In rainbow mode, column position modulates color, creating diagonal color bands that scroll with the animation frame counter.

**References.**
- Pimenta, S. & Poovaiah, R. "On defining visual rhythms for digital media." *Design Thoughts*, 2010. https://doi.org/10.1080/14626268.2010.521913
- Original concept design by Simon Whiteley for *The Matrix* (1999, Warner Bros.)

---

## Kaleidoscope / Symmetry Patterns

**Background.** This mode generates mesmerizing symmetry patterns by plotting procedural seed elements and reflecting them across N-fold rotational symmetry axes. Drawing from mathematical concepts in group theory (dihedral groups D_n), each point is replicated N times around the center with additional mirror reflections, producing the characteristic symmetry of physical kaleidoscopes. Seven procedural animation styles and an interactive paint mode are available.

**Formulation.** The core symmetry operation maps a single plotted point to 2N reflected copies:

```
Symmetry reflection (dihedral group D_n):
  Given point at polar coordinates (r, theta) from center:
  For k = 0 to N-1:
    angle_1 = theta + k * (2*pi / N)
    angle_2 = -theta + 2*k * (2*pi / N) / N    (mirror reflection)
    Plot at both (r, angle_1) and (r, angle_2)
  Aspect ratio correction: x_screen = x * 2.0 (terminal chars ~2x tall)

Procedural seed styles:
  Crystal:   radial line segments, length oscillating with sin(t * freq)
  Wave:      sinusoidal radial waves: amp * sin(r * 0.2 * freq - t * 2 + phase)
  Line:      rotating line with intensity pulsing: 0.6 + 0.4 * sin(step * 0.3 + t)
  Burst:     expanding/contracting pulses: radius ~ (1 + sin(t * freq)) / 2
  Petal:     rose curves: r = R * |sin(freq * angle + t/2 + phase)|
  Spiral:    Archimedean spiral: r = step * radius * 3, angle = step * freq + t * 1.5
  Ring:      concentric pulsing rings with sinusoidal gating

Fade: intensity -= 0.04 per step (toggleable)
Color shift: palette index drifts continuously at 0.01/step

Symmetry orders: 4, 6, 8, 12
Palettes: Jewel Tones, Ice, Fire, Forest, Neon, Monochrome

Presets:      symmetry  style     palette
  Snowflake   6-fold    crystal   Ice
  Mandala     8-fold    wave      Jewel Tones
  Diamond     4-fold    line      Jewel Tones
  Starburst   12-fold   burst     Neon
  Flower      6-fold    petal     Forest
  Vortex      8-fold    spiral    Fire
  Hypnotic    4-fold    ring      Monochrome
  Paint       6-fold    manual    Jewel Tones (no auto, no fade)
```

**What to look for.** Higher symmetry orders (8, 12) produce dense, mandala-like patterns, while 4-fold symmetry creates simpler diamond grids. The Petal style traces rose curves whose lobe count depends on the frequency parameter, producing flower-like forms. Spiral seeds wind outward in Archimedean paths replicated across all axes. Enabling fade creates a trailing afterimage effect; disabling it builds up persistent structures. In Paint mode, cursor movement is mirrored in real time across all symmetry axes, allowing interactive pattern creation.

**References.**
- Coxeter, H.S.M. *Regular Polytopes*, 3rd ed. Dover Publications, 1973. https://store.doverpublications.com/products/9780486614809
- Lu, P.J. & Steinhardt, P.J. "Decagonal and Quasi-Crystalline Tilings in Medieval Islamic Architecture." *Science*, 315(5815), 1106-1110, 2007. https://doi.org/10.1126/science.1135491

---

## ASCII Aquarium / Fish Tank

**Background.** This mode renders a self-contained aquarium ecosystem with procedurally animated fish, swaying seaweed, rising bubbles, interactive feeding, and a sandy bottom terrain. Each fish species has distinct ASCII art sprites for left and right facing orientations, characteristic swimming speeds, and vertical bobbing behavior. The simulation models basic ecological behaviors including food-seeking, startle responses, and wrap-around swimming.

**Formulation.** The aquarium maintains several entity lists updated each tick:

```
Fish dynamics:
  x += vx * startle_multiplier    (startle_mult = 2.5 when startled, else 1.0)
  Wrap: if x > cols + body_len, x = -body_len (and vice versa)
  Direction reversal: 0.5% chance per tick
  Vertical bobbing:
    bob_phase += 0.08
    y = target_y + bob_amp * sin(bob_phase)
  Depth change: 1% chance per tick, new target_y ~ U(water_top, sand_row)
  Startle decay: startled -= 0.1 per tick

Food-seeking behavior:
  If food exists within distance 15:
    Turn toward nearest food
    Adjust target_y toward food's y (10% per tick)
  Eat food when distance < 2

Bubble dynamics:
  y += vy                         (vy ~ U(-0.8, -0.3))
  x += sin(age * 0.3) * 0.15     (lateral wobble)
  Growth: 5% chance per tick to increase char size
  Stream spawning: 30% chance per update cycle from stream origin

Food particles:
  y += 0.15 (slow sinking)
  x += sin(age * 0.2) * 0.1 (gentle drift)
  Removed after 300 ticks

Seaweed animation:
  Sway driven by sin(time * speed + phase) per segment

Presets:
  Tropical Reef:  10-16 fish, species 0-5 (diverse small fish)
  Deep Ocean:     5-8 fish, species 5-7 (large, slow species)
  Koi Pond:       6-10 fish, species 3-4 (medium ornamental)
  Goldfish Bowl:  4-7 fish, species 1-2 (classic goldfish)

Caustic light effect: phase advances at 0.05/tick for surface shimmer
```

**What to look for.** Fish swim back and forth with a natural bobbing motion driven by sinusoidal oscillation. Dropping food (f key) causes nearby fish to break from their patrol pattern and converge on the sinking particles. Tapping the glass (t key) startles all fish, causing them to reverse direction at 2.5x speed before gradually calming. Bubble streams rise from the bottom with gentle lateral oscillation and occasionally spawn new bubbles. Seaweed sways continuously with per-plant phase offsets creating asynchronous motion. Sand terrain is procedurally generated with varying heights per column.

**References.**
- Reynolds, C.W. "Flocks, Herds, and Schools: A Distributed Behavioral Model." *Computer Graphics (SIGGRAPH '87 Proceedings)*, 21(4), 25-34, 1987. https://doi.org/10.1145/37402.37406
- Tu, X. & Terzopoulos, D. "Artificial Fishes: Physics, Locomotion, Perception, Behavior." *Proceedings of SIGGRAPH '94*, ACM, 43-50, 1994. https://doi.org/10.1145/192161.192170

---

## Cellular Symphony

**Background.** Cellular Symphony bridges cellular automata and the auditory domain, treating the grid as a step sequencer: each row is a beat, each alive cell is a voice, and the column position determines pitch. The result is a synesthetic experience where spatial CA patterns — gliders, oscillators, still lifes — produce characteristic musical textures without any explicit composition. The approach draws on sonification research that maps multidimensional data to audio parameters (pitch, timbre, amplitude) to reveal structure invisible to the eye alone. Different CA rulesets produce radically different sonic characters: Conway's Life yields chaotic jazz-like phrases, Seeds produces staccato bursts, and Maze generates thick sustained clusters.

**Formulation.** The sequencer scans one grid row per beat at configurable BPM (20–300). For each alive cell in the current row:

```
Pitch mapping (column → frequency):
  intervals = SCALES[scale]           (pentatonic, chromatic, blues, whole_tone)
  num_notes = len(intervals) * octave_range
  idx       = col * num_notes / total_cols
  octave, degree = divmod(idx, len(intervals))
  semitones = octave * 12 + intervals[degree]
  freq      = 130.81 * 2^(semitones / 12)     (base = C3)

Timbre shaping (neighbor count → harmonic richness):
  nbrs = Moore neighborhood count (0–8)
  Fundamental:           always present
  +octave harmonic:      amplitude 0.3  when nbrs >= 3
  +fifth-above-octave:   amplitude 0.15 when nbrs >= 5
  +double-octave:        amplitude 0.08 when nbrs >= 7
  Waveform options: sine, sawtooth, square, triangle

Amplitude shaping (cell age → loudness):
  age = min(cell_value, 10)
  amp_scale = 0.4 + 0.6 * (age / 10)

Synthesis:
  Voices capped at 16 simultaneous
  Per-voice amplitude = volume / num_voices
  Attack/release ramp = 8 ms (anti-click)
  Note duration = min(beat_interval * 0.8, 2.0 s)
  Output: S16LE mono PCM at 22050 Hz

CA stepping:
  Grid advances one generation after a full row-scan cycle
  (i.e., after all rows have been sequenced once)
```

Seven rule presets are provided, each annotated with its musical character:

| Rule | Birth | Survival | Character |
|------|-------|----------|-----------|
| Conway's Life | 3 | 2,3 | chaotic jazz |
| Seeds | 2 | — | staccato bursts |
| Day & Night | 3,6,7,8 | 3,4,6,7,8 | dense chords |
| Diamoeba | 3,5,6,7,8 | 5,6,7,8 | evolving drones |
| HighLife | 3,6 | 2,3 | melodic drift |
| Maze | 3 | 1,2,3,4,5 | thick clusters |
| Anneal | 4,6,7,8 | 3,5,6,7,8 | ambient wash |

**What to look for.** The scan row sweeps down the grid (highlighted in blue), and you can *hear* structural features: gliders produce repeating melodic fragments that shift pitch as they move across columns; blinkers create rhythmic pulses at fixed pitches; random regions generate dense, noisy clusters that thin out as the CA stabilizes. Switching scales changes the harmonic flavor — pentatonic naturally avoids dissonance, while chromatic exposes every column as a distinct pitch. The voice activity meter at the bottom shows instantaneous polyphony. In paint mode, drawing a diagonal line of cells creates an ascending or descending scale run on the next scan pass.

**References.**
- Hermann, T., Hunt, A. & Neuhoff, J.G. *The Sonification Handbook*. Logos Verlag, 2011. https://sonification.de/handbook/
- Xenakis, I. *Formalized Music: Thought and Mathematics in Composition*. Pendragon Press, 1992.
- Burraston, D. & Edmonds, E. "Cellular Automata in Generative Electronic Music and Sonic Art: A Historical and Technical Review." *Digital Creativity*, 16(3), 165-185, 2005. https://doi.org/10.1080/14626260500370882

---

## Wildfire Spread & Firefighting

**Source:** `life/modes/wildfire.py`

**Background.** This mode simulates wildfire propagation using a Rothermel-inspired model on heterogeneous terrain. Unlike the existing Forest Fire mode (a simple percolation-based cellular automaton with binary states), this simulation tracks continuous fire intensity, models crown fire transitions, computes wind- and slope-driven spread rates, launches embers for long-range spotting ignitions, generates advected smoke plumes, and deploys autonomous firefighting agents. Six fuel types — grass, shrub, timber, urban, water, and rock — each carry distinct spread rates, heat content, moisture extinction thresholds, crown fire thresholds, and ember production probabilities. The terrain is procedurally generated with octave noise elevation and preset-specific fuel distributions.

**Formulation.** Fire intensity evolves on an 8-connected grid. Each cell maintains: intensity (continuous, ≥0), fuel type, fuel moisture, elevation, burned status, crown fire flag, and smoke density.

```
Spread from neighbor n to cell (r,c):
  base     = I_n × spread_rate_fuel(n) × global_spread / dist(n)
  wind     = max(0.1, 1.0 + 0.5 × dot(wind_vec(n), direction_to(r,c)))
  slope    = clamp(1.0 + slope_factor × Δh / (3 × dist), 0.2, 3.0)
  moisture = (1 - (m / m_ext)^1.5)  if m < m_ext, else 0
  crown    = 1.5 if neighbor is crown fire, else 1.0

  contribution = base × wind × slope × moisture × crown
  spread_in = Σ max(0, contribution)  over all 8 neighbors

Intensity update (existing fire):
  I(t+1) = I(t) + 0.3 × spread_in − burnout × (1 + 0.1 × I(t))
  If already burned: additional −0.5 × burnout (fuel exhaustion)

New ignition (I(t) = 0):
  threshold = 0.15 + moisture × 0.5
  If spread_in > threshold:  I(t+1) = 0.5 × spread_in

Crown fire transition:
  Crown when I ≥ fuel-specific crown_thr AND I ≥ global crown_intensity
```

**Fuel properties:**

```
  Fuel Type  spread  heat  moist_ext  crown_thr  ember_prod
  Grass       1.8    0.6     0.25      999 (n/a)    0.02
  Shrub       1.2    1.0     0.30       3.5          0.05
  Timber      0.7    1.8     0.35       2.5          0.10
  Urban       0.4    2.5     0.15       2.0          0.08
  Water       0.0    0.0     1.00      999 (n/a)     0.0
  Rock        0.0    0.0     1.00      999 (n/a)     0.0
```

**Ember spotting.** Cells with intensity > 1.5 launch embers with probability `fuel_ember × ember_prob × intensity`. Embers travel downwind with angular perturbation (±0.5 rad) at random range (3 to `ember_range` cells). Embers ignite dry, unburned, non-firebreak cells where moisture < 0.8 × moisture extinction, starting fires at intensity 0.8–1.3.

**Smoke plume.** Smoke production = intensity × 0.15 (×2 for crown fire). Existing smoke decays by `smoke_decay` per step. Smoke advects downwind by 0.8× wind velocity. Smoke density affects rendering opacity.

**Firefighter agents.** Two agent types autonomously seek the nearest fire within a search radius:
- **Break agents** cut firebreaks: set firebreak flag on cells 1–3 ahead of the fire front in the wind direction, permanently blocking fire spread through those cells.
- **Water agents** suppress fire: reduce intensity (÷2) and increase local moisture (+0.05) in a 3×3 area around target cells.
After acting, agents incur a cooldown (5 steps for break, 3 for water) before they can act again.

**Fuel moisture dynamics.** Active fire (intensity > 0.5) dries 8 neighboring cells by `0.005 × intensity` per step, progressively lowering ignition thresholds ahead of the fire front.

**Presets (6):**

| Preset | Wind | Moisture | Elevation | Terrain | Behavior |
|--------|------|----------|-----------|---------|----------|
| Grassland Brushfire | 1.5 E | 0.10 | 3 m | Flat grass | Fast, low-intensity, wide front |
| Mountain Wildfire | 0.8 NE | 0.20 | 25 m | Steep timber | Slope-driven runs, heavy spotting |
| Urban-Wildland Interface | 1.2 E | 0.12 | 8 m | Mixed urban-veg | Structure ignitions, firefighter defense |
| Prescribed Burn | 0.5 E | 0.22 | 4 m | Grass/shrub | Low intensity, containment lines |
| Firestorm | 2.0 NE | 0.05 | 15 m | Dense fuel | Crown fire, mass spotting, multiple ignitions |
| Canyon Wind Event | 2.5 S | 0.08 | 20 m | Canyon channel | Downslope wind acceleration |

**Controls:** `Space`=play/pause, `n`=step, `v`=cycle views (fire/elevation/fuel/moisture), `w/W`=wind speed, `d/D`=wind direction, `+/-`=simulation speed, `r`=reset, `R`=menu, `q`=exit.

**What to look for.** In Grassland Brushfire, the fire front advances rapidly but at low intensity, leaving a wide ash footprint. Mountain Wildfire demonstrates slope-driven acceleration — fire races uphill and launches embers far downwind, creating secondary fronts ahead of the main blaze. The Urban-Wildland Interface shows structure-to-vegetation-to-structure fire chains, with firefighter agents attempting to defend buildings. Prescribed Burn demonstrates controlled fire management: break agents cut firebreaks and water agents suppress escaping flames. Firestorm creates extreme conditions with crown fire transitions visible as intensified coloring and doubled smoke production. Canyon Wind Event shows channeled winds accelerating fire through the narrow canyon with reduced spread on the ridges. Toggle views to see how elevation drives spread patterns, how fuel type distribution creates corridors, and how moisture is progressively depleted ahead of the front.

**References.**
- Rothermel, R.C. "A Mathematical Model for Predicting Fire Spread in Wildland Fuels." USDA Forest Service Research Paper INT-115, 1972. https://www.fs.usda.gov/treesearch/pubs/32533
- Finney, M.A. "FARSITE: Fire Area Simulator — Model Development and Evaluation." USDA Forest Service Research Paper RMRS-RP-4, 1998. https://doi.org/10.2737/RMRS-RP-4
- Albini, F.A. "Estimating Wildfire Behavior and Effects." USDA Forest Service General Technical Report INT-30, 1976. https://www.fs.usda.gov/treesearch/pubs/29574
- Linn, R.R. & Cunningham, P. "Numerical simulations of grass fires using a coupled atmosphere-fire model." *Journal of Geophysical Research*, 110, D13107, 2005. https://doi.org/10.1029/2004JD005597

---

## City Growth & Urban Simulation

**Source:** `life/modes/city_growth.py`

**Background.** This mode simulates emergent urban development where residential, commercial, and industrial zones self-organize around road networks via land-value gradients, population pressure, and zoning attraction/repulsion rules. Unlike simple cellular automata that model individual buildings or traffic, this simulation captures the macro-scale dynamics of urban morphology — how cities grow organically from small settlements into complex metropolitan structures through feedback loops between land value, transportation access, population density, and zoning compatibility. The model draws on urban economics (Alonso's bid-rent theory, von Thünen's land use rings) and complex systems approaches to city formation.

**Formulation.** The simulation operates on a 2D grid where each cell has a zone type, density level (0–5), land value, traffic load, and population count. Eight zone types are defined:

```
Zone types:
  Empty (0)       — undeveloped land
  Road (1)        — transportation network
  Residential (2) — housing, carries population
  Commercial (3)  — shops, offices, employment
  Industrial (4)  — factories, warehouses
  Park (5)        — green space, amenity bonus
  Water (6)       — natural water bodies
  Ruin (7)        — decayed infrastructure

Density levels (for Residential/Commercial/Industrial):
  0 = vacant, 1 = sparse, 2 = low, 3 = medium, 4 = high, 5 = maximum
```

**Land value computation.** Each step, land values are recalculated for all cells based on multiple factors:

```
Land value update:
  road_access    = count of road neighbors × road_value_bonus
  commercial_prox = Σ (1/distance) for commercial cells within radius
  industrial_nimby = -penalty for each industrial cell within radius
  park_amenity    = bonus for each park cell within radius
  traffic_penalty = -congestion × traffic_penalty_factor
  centrality      = bonus inversely proportional to distance from city center

  value = base + road_access + commercial_prox + industrial_nimby
          + park_amenity + traffic_penalty + centrality
  value = clamp(value, 0, max_value)
```

**Traffic simulation.** Population generates commuter traffic along roads. Traffic accumulates on road cells proportional to nearby residential population and decays each step. Congestion (traffic exceeding capacity) depresses surrounding land values and drives population migration.

**Organic road growth.** New roads extend toward underserved population clusters — cells with high residential density but poor road access attract road construction. Roads grow incrementally from existing road endpoints toward demand.

**Zone self-organization.** Empty cells adjacent to roads may develop into zones based on probabilistic rules:

```
Zone placement probability:
  Residential: higher when land value is moderate, road-adjacent,
               away from industrial, near parks
  Commercial:  higher when land value is high, high road access,
               near other commercial (agglomeration)
  Industrial:  higher when land value is low, road-adjacent,
               away from residential (NIMBY separation)
```

**Gentrification.** High land value converts low-density residential into commercial zones, displacing population to lower-value areas — a positive feedback loop that concentrates commerce in high-value corridors.

**Infrastructure decay.** Zones with low population, low traffic, or low land value gradually decay. Abandoned zones deteriorate into ruins over time. Ruins adjacent to active zones can be reclaimed (redeveloped) with a probability proportional to surrounding activity.

**Population migration.** Residents move away from congested, low-value, industrial-adjacent areas toward high-value, well-connected, park-adjacent neighborhoods.

**Presets (6):**

| Preset | Character | Initial Layout |
|--------|-----------|----------------|
| Medieval Town | Dense core, organic street pattern, walls | Small central market, radiating roads |
| Suburban Sprawl | Low density, car-dependent, wide spread | Scattered residential, highway grid |
| Dense Metropolis | High density, transit-oriented, vertical | Large commercial core, dense grid |
| Coastal City | Water boundary, port industry, waterfront value | Coastline with harbor and beachfront |
| Post-Apocalyptic Regrowth | Ruins reclaimed, sparse population | Mostly ruins with small survivor clusters |
| Megacity | Massive scale, multiple centers, congestion | Multiple nuclei, extensive road network |

**View modes (4, cycle with `v`):**
1. **Zone map** — zone types shown as colored Unicode characters (▪ residential, ◆ commercial, ▲ industrial, ♣ park, · road, ~ water, ░ ruin)
2. **Land value heatmap** — intensity-mapped gradient showing economic geography
3. **Traffic heatmap** — congestion visualization revealing bottlenecks
4. **Population density** — where people actually live

**Controls:** `Space`=play/pause, `n`=step, `v`=cycle views, `+/-`=simulation speed, `r`=reset, `R`=menu, `q`=exit.

**What to look for.** In Medieval Town, watch the organic street network grow outward from the central market, with commercial zones clustering along main roads and residential filling in behind. Suburban Sprawl demonstrates low-density residential spreading far from the center with commercial strips along highways — note the high per-capita traffic. Dense Metropolis shows intense land-value peaks in the commercial core with steep gradients outward, and gentrification waves converting residential edges to commercial. Coastal City reveals how the water boundary concentrates development along the shore and creates a port-industrial zone separated from waterfront residential by land value. Post-Apocalyptic Regrowth is fascinating to watch as small survivor clusters slowly reclaim ruins, rebuilding road connections and re-establishing trade networks. Megacity showcases multiple competing centers with congestion corridors between them. Toggle to the traffic heatmap to see how road networks become saturated, then watch how new roads grow to relieve pressure. The land value view reveals the economic geography underlying all zone placement decisions.

**References.**
- Alonso, W. *Location and Land Use*. Harvard University Press, 1964.
- Batty, M. "The Size, Scale, and Shape of Cities." *Science*, 319(5864), 769-771, 2008. https://doi.org/10.1126/science.1151419
- Portugali, J. *Self-Organization and the City*. Springer, 2000. https://doi.org/10.1007/978-3-662-04099-7
- Waddell, P. "UrbanSim: Modeling Urban Development for Land Use, Transportation, and Environmental Planning." *Journal of the American Planning Association*, 68(3), 297-314, 2002. https://doi.org/10.1080/01944360208976274

---


## Termite Mound Construction & Stigmergy

**Background.** Termite mounds are among the most impressive examples of emergent architecture in biology. Individual termites are simple agents with no blueprint or central coordinator, yet colonies of *Macrotermes* and *Amitermes* construct elaborate mounds with ventilation shafts, brood chambers, fungus gardens, and royal chambers — structures that can reach several meters in height. The key mechanism is *stigmergy* (Grassé, 1959): indirect coordination where an agent's modification of the environment stimulates further work by other agents. A termite deposits a soil pellet laced with pheromone; the pheromone attracts other termites to deposit nearby, creating a positive feedback loop that bootstraps pillars, arches, and walls from purely local rules.

**Formulation.** The simulation runs on a 2D grid with three pheromone layers (build, dig, trail) and eight material types. Each tick proceeds in two phases:

**Phase 1 — Pheromone diffusion and evaporation:**

```
For each pheromone layer P ∈ {build, dig, trail}:
  P'(r,c) = P(r,c) × (1 − evap_rate)
           + diffuse_rate × (avg_neighbors(P, r, c) − P(r,c))
  P'(r,c) = clamp(P'(r,c), 0, 1)
```

where `avg_neighbors` averages the 4-connected (von Neumann) neighbor values. Default evaporation rate is 0.02; diffusion rate is 0.15. Trail pheromone evaporates 1.5× faster to prevent long-term path saturation.

**Phase 2 — Termite agent actions:** Each termite evaluates its 8-connected neighborhood and selects the cell with the highest weighted score based on its role:

```
score(nr, nc) = w_build × ph_build(nr, nc)   [if builder/worker]
              + w_dig   × ph_dig(nr, nc)      [if digger/worker]
              + w_trail × ph_trail(nr, nc)     [all roles]
              + w_home  × home_bias(nr, nc)    [navigation]
              + random_jitter
```

Builders deposit material (converting air → wall) when local build pheromone exceeds a threshold *and* at least one adjacent cell is already solid (structural support rule). Diggers remove material (wall/soil → air/chamber) when local dig pheromone exceeds its threshold. Workers perform both roles with lower efficiency. Soldiers patrol the perimeter, reinforcing walls. Fungus tenders maintain fungus garden cells below the surface. Queens remain stationary, continuously emitting build and dig pheromones to seed construction activity.

**Structural support rule.** Material can only be deposited adjacent to existing structure (soil, wall, surface, or royal chamber), preventing floating construction and producing architecturally realistic buttressing patterns.

**Ventilation shafts (cathedral preset).** Dig pheromone is seeded in vertical columns above chambers. As diggers excavate upward through the mound, they create passive ventilation channels — mimicking the chimney effect observed in *Macrotermes* cathedral mounds where warm air rises through internal channels and exits through porous upper walls.

**Magnetic alignment (magnetic preset).** The magnetic preset constrains build pheromone to a narrow N-S band while spreading dig pheromone E-W, suppressing lateral growth and producing the thin, compass-aligned wedge shape characteristic of *Amitermes meridionalis* mounds that minimize solar heating at midday.

**Mega-colony multi-queen structure.** The mega preset distributes 3–5 colony centers across the grid, each with its own queen and termite population. Independent mounds grow simultaneously and may eventually merge through tunnel connections.

**Presets (6):**

| Preset | Character | Initial Configuration |
|--------|-----------|----------------------|
| Cathedral Mound | Towering spire, ventilation shafts | Builders clustered at center, vertical build-pheromone column |
| Magnetic Termite Mound | Flat N-S aligned wedge | Narrow build band, wide E-W dig zone |
| Underground Network | Subsurface tunnels, foraging galleries | Mostly diggers below surface, radial dig-pheromone gradient |
| Fungus Farming Colony | Humidity-controlled fungus chambers | Mixed roles with 30% fungus tenders, subsurface dig seeds |
| Defensive Fortress | Thick outer walls, soldier patrols | Ring of build pheromone for walls, soldiers on perimeter |
| Mega-Colony | Multi-queen, 3–5 interconnected mounds | Multiple colony centers with independent populations |

**View modes (3, cycle with `v`):**
1. **Mound** — full material rendering with termite agents overlaid as colored dots (yellow = worker, green = builder, red = digger, white = soldier, magenta = fungus tender, cyan = queen)
2. **Pheromone** — build pheromone (yellow) vs dig pheromone (blue) concentration heatmap, showing the invisible chemical landscape guiding construction
3. **Structure** — structural analysis highlighting exterior walls vs interior chamber walls vs tunnels

**Controls:** `Space`=play/pause, `n`=step, `v`=cycle views, `+/-`=simulation speed, `r`=reset, `R`=menu, `q`=exit.

**What to look for.** In Cathedral Mound, watch pillars emerge from the ground surface as builders follow build-pheromone gradients upward, then observe diggers carve ventilation shafts through the growing structure. The mound self-organizes into a layered architecture: royal chamber at the base, brood chambers above, and porous upper walls. Magnetic Termite Mound produces a strikingly flat, elongated shape — toggle to the pheromone view to see how the constrained build zone creates the compass alignment. Underground Network is fascinating from the structure view: watch tunnel branches radiate outward from the central nest as diggers follow pheromone gradients into virgin soil. Fungus Farming Colony shows specialized chamber formation — fungus tenders maintain garden cells that appear as distinct colored regions below the surface. Defensive Fortress demonstrates wall thickening as builders reinforce the perimeter ring while soldiers patrol. Mega-Colony is the most dramatic: independent mounds grow at separate centers and may eventually connect through subsurface tunnels. Switch between all three views frequently — the pheromone view reveals the invisible signaling landscape that drives all visible construction.

**References.**
- Grassé, P.-P. "La reconstruction du nid et les coordinations interindividuelles chez *Bellicositermes natalensis* et *Cubitermes* sp. La théorie de la stigmergie." *Insectes Sociaux*, 6(1), 41-80, 1959. https://doi.org/10.1007/BF02223791
- Camazine, S. et al. *Self-Organization in Biological Systems*. Princeton University Press, 2001.
- Bonabeau, E., Dorigo, M. & Theraulaz, G. *Swarm Intelligence: From Natural to Artificial Systems*. Oxford University Press, 1999.
- Turner, J. S. *The Extended Organism: The Physiology of Animal-Built Structures*. Harvard University Press, 2000.

---


## Deep Sea Hydrothermal Vent Ecosystem

**Background.** Hydrothermal vents are fissures on the ocean floor where geothermally heated water erupts into near-freezing deep-ocean seawater. Discovered in 1977 along the Galápagos Rift, these systems host some of Earth's most extreme ecosystems — thriving without sunlight through chemosynthesis, where microbes oxidize hydrogen sulfide (H₂S) and other reduced chemicals as their primary energy source. "Black smokers" emit superheated fluid (up to 400°C) laden with metal sulfides that precipitate on contact with 2°C ambient water, gradually building towering chimney structures. The surrounding fauna — giant tube worms (*Riftia pachyptila*), vent shrimp (*Rimicaris exoculata*), mussels (*Bathymodiolus*), crabs, and octopuses — form a food web rooted entirely in chemosynthetic bacterial production. This simulation models the coupled thermal, chemical, geological, and ecological dynamics of a deep-sea vent field.

**Formulation.** The simulation operates on a 2D grid representing a vertical cross-section of the ocean floor and water column. Three continuous scalar fields evolve each timestep:

```
Temperature field T(x,y):
  T(t+1) = T(t) + D_T · ∇²T  +  buoyancy advection  +  vent injection
  where D_T = thermal diffusion coefficient
  Buoyancy: hot fluid rises at rate proportional to (T - T_ambient)
  Vent sources inject T_vent at chimney positions each tick

H₂S concentration field S(x,y):
  S(t+1) = S(t) + D_S · ∇²S  -  λ_S · S  +  vent injection
  where λ_S = decay/oxidation rate, D_S = diffusion coefficient

Mineral concentration field M(x,y):
  M(t+1) = M(t) + D_M · ∇²M  -  λ_M · M  +  vent injection
  Minerals precipitate into solid chimney when M > threshold AND T gradient is steep
```

**Chimney growth.** When dissolved mineral concentration exceeds a precipitation threshold at a cell where hot vent fluid meets cold water (steep temperature gradient), mineral material solidifies — converting the cell to chimney rock. This positive feedback loop (chimney constrains flow → concentrates minerals → more precipitation) produces the characteristic tall, narrow chimney morphology of black smokers.

**Ocean current drift.** A global current vector rotates slowly over time, advecting the temperature, H₂S, and mineral plume fields laterally. This disperses plume material downstream and transports larvae between vent sites.

**Tectonic events.** At a configurable rate, the simulation generates tectonic disturbances: new fissures open (activating new vent sources), existing chimneys collapse (converting chimney cells back to water/rubble), and vent activity waxes or wanes (modulating injection temperature and chemical flux).

**Fauna model.** Six organism types inhabit the vent field, each with type-specific behavior:

| Organism | Role | Behavior |
|----------|------|----------|
| Chemosynthetic microbes | Primary producer | Reproduce in high-H₂S, high-temperature zones; metabolize H₂S for energy; thermophilic (prefer 40–120°C) |
| Tube worms | Sessile symbiont | Anchor near vents; harbor internal chemosynthetic bacteria; grow/shrink based on local H₂S supply |
| Mussels | Filter feeder | Cluster at vent bases; filter microbes from water; sessile once established |
| Shrimp | Mobile grazer | Chemotax toward H₂S gradients; graze on microbe colonies; avoid extreme heat |
| Crabs | Scavenger | Roam the seafloor; consume microbes, mussels, and detritus |
| Octopuses | Apex predator | Rare; hunt crabs and shrimp; roam large territories |

Organisms have energy budgets, reproduce when energy exceeds a threshold (with a carrying-capacity check), and die when energy reaches zero or temperature exceeds their tolerance. Some creatures exhibit bioluminescence — rendered as flickering cyan highlights.

**Presets (6):**

| Preset | Character | Initial Configuration |
|--------|-----------|----------------------|
| Classic Black Smoker | Tall iron-sulfide chimneys, 350°C fluid, dark mineral clouds | 2–3 chimneys, fast precipitation, full fauna suite |
| White Smoker Garden | Lower temperature (150–250°C), barium/calcium deposits, lush fauna | Many small vents, slower chimney growth, dense tube worm colonies |
| Lost City (Alkaline Vents) | Tall carbonate towers, warm (40–90°C), alkaline, hydrogen-rich | Tall initial structures, low H₂S, high mineral content, slow chemistry |
| Mid-Ocean Ridge | Active spreading center, multiple vent fields | High tectonic rate, scattered vent clusters, frequent fissure events |
| Vent Field Colonization | Pioneer species colonize newly opened vents | Bare basalt start, vents activate gradually, fauna arrives via larval drift |
| Dying Vent Succession | Waning vent activity, community collapse | Initially active vents with established fauna; activity declines over time |

**View modes (3, cycle with `v`):**
1. **Ecosystem** — full terrain rendering with chimney structures, fauna icons, thermal plume coloring (red/yellow for hot fluid), and bioluminescent creature highlights against a dark ocean background
2. **Thermal heatmap** — temperature field visualization from deep blue (2°C ambient) through cyan, green, yellow to bright red/white (350°C+ vent fluid)
3. **Chemistry** — H₂S concentration (green) and dissolved mineral concentration (yellow/brown) overlaid, showing the chemical landscape that drives both chimney growth and the food web

**Controls:** `Space`=play/pause, `n`=step, `v`=cycle views, `+/-`=simulation speed, `r`=reset, `R`=menu, `q`=exit.

**What to look for.** In Classic Black Smoker, watch chimney structures grow upward from the seafloor as mineral precipitation builds layer by layer — the chimneys constrain the plume, concentrating minerals and accelerating their own growth. Tube worms cluster in the warm zone just outside the lethal-temperature boundary, while shrimp swarm through the H₂S gradient. Switch to the thermal view to see the buoyant plume billow upward and drift with the current. White Smoker Garden produces a gentler, more biologically productive scene — lower temperatures mean a wider habitable zone and denser fauna. Lost City is visually distinct: tall, pale carbonate towers with warm (not superheated) fluid and a different chemical regime. Mid-Ocean Ridge is the most dynamic — frequent tectonic events open new fissures and collapse existing chimneys, forcing fauna to migrate. Vent Field Colonization shows ecological succession in action: microbes arrive first, followed by tube worms, then grazers and predators. Dying Vent Succession is the inverse — watch the community unravel as chemical energy dwindles, with apex predators disappearing first and chemosynthetic microbes persisting longest.

**References.**
- Van Dover, C. L. *The Ecology of Deep-Sea Hydrothermal Vents*. Princeton University Press, 2000.
- Kelley, D. S. et al. "An off-axis hydrothermal vent field near the Mid-Atlantic Ridge at 30°N." *Nature*, 412, 145–149, 2001. https://doi.org/10.1038/35084000
- Luther, G. W. et al. "Chemical speciation drives hydrothermal vent ecology." *Nature*, 410, 813–816, 2001. https://doi.org/10.1038/35071069
- Corliss, J. B. et al. "Submarine thermal springs on the Galápagos Rift." *Science*, 203(4385), 1073–1083, 1979. https://doi.org/10.1126/science.203.4385.1073


---


## Stellar Lifecycle & Supernova

**Background.** Stars are the fundamental engines of the universe — forging elements in their cores, sculpting galaxies with their radiation and winds, and seeding interstellar space with heavy elements when they die. A star's life is determined almost entirely by its birth mass: low-mass stars burn hydrogen slowly for billions of years and fade as white dwarfs, while massive stars blaze through their fuel in millions of years and detonate as core-collapse supernovae, leaving neutron stars or black holes. The Hertzsprung-Russell diagram — plotting stellar luminosity against surface temperature — reveals the evolutionary tracks stars follow from birth to death. This simulation models the full stellar lifecycle from gas cloud collapse through nucleosynthesis to remnant formation, with supernova shockwaves triggering new generations of star formation in a self-sustaining cycle.

**Formulation.** Each star is an agent with mass, position, velocity, hydrogen fuel fraction, surface temperature, luminosity, radius, and a 6-element fusion shell composition vector. The key physical relations:

```
Mass-luminosity relation (main sequence):
  L = M^3.5       (in solar units)

Main sequence lifetime:
  τ = M^{-2.5}    (massive stars die young)

Surface temperature scaling:
  T = 5778 · M^{0.505}  K

Radius scaling:
  R = M^{0.8}     (main sequence)
  R = M^{0.8} · 10   (red giant)
  R = M^{0.8} · 20   (supergiant)
```

**Stellar evolution stages.** Stars progress through up to 12 stages depending on mass:

| Stage | Trigger | Properties |
|-------|---------|------------|
| Gas Cloud | Initial state | Low temperature (~100 K), extended radius, near-zero luminosity |
| Protostar | Gas density + shockwave compression | Contracting, warming (2000–5000 K) |
| Main Sequence | Age > 30 ticks | Stable hydrogen fusion; L, T, R from mass relations |
| Subgiant | Fuel ≤ 10% | Expanding, cooling slightly (T × 0.85) |
| Red Giant | Fuel ≤ 2%, M < 8 M☉ | Radius × 10, luminosity × 5, T drops to ~3000 K |
| Supergiant | Fuel ≤ 2%, M ≥ 8 M☉ | Radius × 20, luminosity × 10, onion-shell fusion |
| Supernova | Fuel exhausted (supergiant) | Luminosity spike (10⁶ × M), expanding shockwave |
| Planetary Nebula | Fuel exhausted (red giant) | Expanding shell of ejected gas |
| White Dwarf | Nebula radius > 8 | M capped at 1.4 M☉ (Chandrasekhar limit), slowly cooling |
| Neutron Star | Post-supernova, 8 < M < 25 M☉ | M = 1.4 M☉, tiny radius, extreme temperature |
| Black Hole | Post-supernova, M > 25 M☉ | M = 0.3 × M_initial, zero luminosity |

**Hydrogen burning.** On the main sequence, fuel decreases at rate proportional to M^{2.5} — a 20 M☉ star burns fuel ~1800× faster than a 1 M☉ star. The fuel fraction drives shell composition: as hydrogen depletes, helium accumulates, then heavier elements build up in massive stars through successive fusion stages (H → He → C → O → Si → Fe).

**Supernova feedback.** When a supergiant exhausts its fuel, it detonates as a core-collapse supernova:
1. A shockwave is created at the star's position with strength proportional to initial mass
2. The shockwave expands at 1.2 cells/tick, decaying in strength by 8% per tick
3. Where the shockwave front intersects dense gas (density > 0.3), it probabilistically triggers collapse of new gas cloud fragments into protostars
4. The supernova ejects enriched gas into a 6-cell radius, replenishing the interstellar medium

This creates a self-sustaining cycle: supernovae compress gas → new stars form → massive ones evolve fast → more supernovae.

**Binary mass transfer.** A configurable fraction of stars form gravitationally bound pairs. When one partner evolves to red giant or supergiant while the other remains on the main sequence (or is a compact remnant), mass transfers from the expanded star to its companion at a steady rate. This can rejuvenate the accreting star or drive it toward its own premature evolution.

**Wolf-Rayet winds.** Stars with wind strength > 2.0 (set by initial mass and the preset's wind scale) lose mass continuously during the supergiant phase, stripping their outer envelopes before detonation — producing the characteristic Wolf-Rayet phenomenon of ultra-luminous, rapidly evolving massive stars.

**Gas dynamics.** A 2D density grid represents the interstellar medium. Gas clouds are seeded as circular regions with Gaussian-like falloff profiles. Every 5 ticks, the gas field undergoes 4-neighbor diffusion (coefficient 0.02) with mild dissipation (factor 0.92), slowly spreading and fading. Supernova ejecta and planetary nebula shedding inject fresh gas, maintaining the reservoir for future star formation.

**Spectral classification.** Stars are assigned OBAFGKM spectral class from surface temperature:

| Class | Temperature | Color (terminal) |
|-------|-------------|-------------------|
| O | > 30,000 K | Cyan/blue, bold |
| B | 10,000–30,000 K | Cyan/blue, bold |
| A | 7,500–10,000 K | White, bold |
| F | 6,000–7,500 K | White, bold |
| G | 5,200–6,000 K | Yellow, bold |
| K | 3,700–5,200 K | Red |
| M | < 3,700 K | Red |

**Presets (6):**

| Preset | Character | Initial Configuration |
|--------|-----------|----------------------|
| Open Cluster Nursery | Young stellar nursery — gas clouds collapsing into protostars | 60 stars (0.3–8 M☉), dense gas (0.6), all start as gas clouds, 10% binaries |
| Red Giant Graveyard | Aging cluster of evolved stars shedding nebulae | 40 stars (0.8–5 M☉), sparse gas (0.15), start as red giants with 2–15% fuel remaining |
| Supernova Chain Reaction | Massive stars near end of life — cascading detonations | 50 stars (5–40 M☉), moderate gas (0.4), start as supergiants with 1–8% fuel, chain explosions trigger new formation |
| Binary Star Mass Transfer | Close binary pairs exchanging mass via Roche lobe overflow | 30 stars (1–15 M☉), sparse gas (0.1), 80% binary fraction, main sequence start |
| Globular Cluster Evolution | Ancient dense cluster with thousands of stars at various ages | 120 stars (0.2–3 M☉), minimal gas (0.05), main sequence start with varied ages, 15% binaries |
| Wolf-Rayet Wind Bubble | Ultra-massive stars with fierce stellar winds carving bubbles | 25 stars (20–80 M☉), moderate gas (0.3), 5× wind scale, rapid mass loss before explosion |

**View modes (3, cycle with `v`):**
1. **Star Field** — spatial view of the stellar nursery: gas cloud density rendered as ASCII art (`.:-=+*#%@`), stars as colored glyphs by stage (~ gas cloud, + protostar, * main sequence, O red giant, # supergiant, @ supernova, % planetary nebula, . white dwarf, : neutron star, o black hole), expanding supernova explosion rings, expanding nebula shells, binary link markers, and shockwave fronts
2. **HR Diagram** — live Hertzsprung-Russell plot with log₁₀(luminosity) on the Y axis (10^{-4} to 10^{+7} L☉) and log₁₀(temperature) on the X axis (reversed: hot O stars at left, cool M stars at right), dotted main sequence guide line, spectral class labels along the temperature axis, stars plotted as colored glyphs by evolutionary stage, and a legend panel
3. **Core Cross-Section** — concentric onion-layer visualization of the selected star's internal fusion shells (H → He → C → O → Si → Fe), drawn as filled circles with aspect-ratio correction, color-coded by element, with a composition legend showing relative shell fractions, star properties panel (mass, stage, spectral class, temperature, luminosity, radius, age, fuel), and an energy output bar indicator

**Controls:** `Space`=play/pause, `v`=cycle views, `s`=select star (cycle), `+/-`=simulation speed, `r`=reset to menu, `q`=exit.

**What to look for.** In Open Cluster Nursery, watch the gas clouds flicker and collapse one by one into protostars (+ symbols), then ignite as main sequence stars (*) — the most massive ones will be blue (O/B class) at the hot end of the HR diagram, while the numerous low-mass stars cluster as red M dwarfs at the cool end. Switch to the HR diagram to see the population track the classic main sequence band. As time progresses, the most massive stars peel off the main sequence first, swelling into red giants (O) and supergiants (#) — watch them migrate to the upper-right of the HR diagram. When a supergiant detonates (@), the expanding shockwave ring compresses surrounding gas and triggers a new burst of star formation. In Supernova Chain Reaction, the chain detonations are particularly dramatic — each explosion seeds gas that enables the next generation. Switch to Core Cross-Section view and cycle through stars with `s` to see the onion-layer structure of a massive supergiant: hydrogen envelope surrounding helium, carbon, oxygen, silicon, and (just before detonation) an inert iron core. Binary Star Mass Transfer shows pairs linked by dashes, with the expanded partner visibly feeding its companion. Wolf-Rayet Wind Bubble features the most massive stars in the simulation — watch their mass erode from wind losses before they explode spectacularly.

**References.**
- Kippenhahn, R., Weigert, A. & Weiss, A. *Stellar Structure and Evolution*. 2nd ed., Springer, 2012. https://doi.org/10.1007/978-3-642-30304-3
- Salpeter, E. E. "The luminosity function and stellar evolution." *Astrophysical Journal*, 121, 161–167, 1955. https://doi.org/10.1086/145971
- Woosley, S. E. & Weaver, T. A. "The evolution and explosion of massive stars." *Reviews of Modern Physics*, 74(4), 1015–1071, 2002. https://doi.org/10.1103/RevModPhys.74.1015
- Hertzsprung, E. "Über die Sterne der Unterabteilungen c und ac." *Astronomische Nachrichten*, 179(24), 373–380, 1909. https://doi.org/10.1002/asna.19091792402


---


## Tide Pool & Intertidal Ecosystem

**Background.** The rocky intertidal zone — the narrow band of shore between high and low tide marks — is one of ecology's most studied natural laboratories. Twice daily, the tide transforms this strip from a wave-battered submarine habitat into a sun-baked, desiccating terrestrial one. Species survive by partitioning the shore into vertical zones based on their tolerance to exposure: barnacles and limpets cement themselves high where few competitors survive the drying, mussels dominate the mid-zone in dense beds, sea stars patrol below as keystone predators, and kelp forests anchor the permanently wet low zone. Paine's (1966) classic removal experiments showed that a single predator — the ochre sea star *Pisaster ochraceus* — prevents competitive exclusion by mussels, maintaining the species diversity of the entire community. Connell (1972) demonstrated that the upper limits of species distributions are set by physical stress (desiccation, heat), while lower limits are set by biotic interactions (predation, competition). This simulation models these dual gradients — physical stress from above, biological pressure from below — driven by the rhythmic pulse of a sinusoidal tide.

**Formulation.** The simulation operates on a 2D grid representing a vertical rocky shore cross-section, with elevation increasing upward (row 0 = spray zone, row N = subtidal). The tide is modeled as a sinusoidal oscillation:

```
Tide level (0–1):
  L(t) = 0.5 + A · sin(2πt / T)

where:
  A = tidal amplitude (fraction of vertical range, 0.20–0.45)
  T = tidal period (180–300 ticks per full cycle)

Water line row:
  W(t) = (1 - L(t)) · N_rows

Wave surge noise:
  δ(t) = 0.03·sin(0.7t) + 0.02·sin(1.3t)

Final level:
  L_eff(t) = clamp(L(t) + δ(t), 0, 1)
```

The shore is divided into 5 zonation bands computed from terminal height:

| Zone | Rows | Ecological Character |
|------|------|---------------------|
| Spray | 0–10% | Splashed but rarely submerged; lichens, cyanobacteria |
| High Intertidal | 10–30% | Brief submersion at high tide; barnacles, limpets, periwinkles |
| Mid Intertidal | 30–55% | Alternating exposure/submersion; mussels, anemones, sea stars |
| Low Intertidal | 55–80% | Mostly submerged; kelp, urchins, hermit crabs |
| Subtidal | 80–100% | Permanently submerged; full marine community |

**Terrain.** The substrate is rock with two special features: **tide pools** (depressions that retain water at low tide, concentrated in mid/low zones) and **sand patches** (in low/subtidal, avoided by most mobile organisms except hermit crabs). Algae grows on wet, illuminated rock surfaces.

**Physical stress fields.** Two scalar fields — temperature and moisture — are updated per cell each tick:

```
If submerged or in tide pool:
  temp(r,c)  ← max(0, temp - 0.05)         (cooling)
  moist(r,c) ← min(1, moist + 0.1)         (wetting)

If exposed:
  elev = 1 - r/N                            (higher = more exposed)
  temp(r,c)  ← min(1, temp + 0.02·(1+elev)) (heating)
  moist(r,c) ← max(0, moist - 0.03·(1+elev))(drying)

Splash zone (up to 5% of rows above waterline):
  30% chance per cell: moist += 0.05        (spray moisture)
```

**Algae dynamics.** Algae density (0–1 per cell) grows on rock and pool tiles:

```
growth = 0.005 · light(r) · moisture(r,c)
  where light(r) = max(0.1, 1 - r/(2·N))

Decay if moisture < 0.2: algae -= 0.01
Rock becomes algae-covered at density > 0.3, reverts at < 0.1
```

Grazers (urchins eat 0.1/tick, limpets eat 0.05/tick) keep algae in check, creating visible grazing halos and bloom/crash cycles.

**Species ecology.** Eight species in two categories — sessile (attached to rock) and mobile (free-moving):

| Species | Type | Preferred Zone | Feeding | Stress Tolerance | Special Mechanic |
|---------|------|---------------|---------|-----------------|-----------------|
| Barnacle | Sessile | High | Filter feed when submerged (+0.01/tick) | Moderate desiccation tolerance | Cements to rock |
| Mussel | Sessile | Mid | Filter feed when submerged (+0.012/tick) | Good desiccation tolerance | Grows in size; competes for rock space |
| Anemone | Sessile | Mid-Low | Filter feed when submerged (+0.008/tick) | Poor desiccation tolerance | Anchors in pools |
| Kelp | Sessile | Low-Subtidal | Photosynthesis (light-dependent, +0.015×light) | Very poor exposure tolerance | Grows in size; grazed by urchins |
| Limpet | Mobile | High-Mid | Grazes algae (0.05/tick) | High exposure tolerance | Tolerates drying (stress +0.003 vs +0.015) |
| Sea Star | Mobile | Mid-Low | Predates mussels/barnacles (-0.3 prey energy, +0.15 own) | Poor exposure tolerance | Keystone predator; "wave of death" fronts |
| Urchin | Mobile | Low-Subtidal | Grazes algae (0.1/tick) and kelp (-0.1 kelp energy) | Poor exposure tolerance | Creates urchin barrens |
| Hermit Crab | Mobile | Mid-Low | Scavenges (+0.003/tick) | Moderate exposure tolerance | Vacancy-chain shell swaps |

**Organism lifecycle.** All organisms have energy (0–2.0+), age, and stress (0–1.0). Death occurs when energy ≤ 0, stress ≥ 1.0, or age exceeds lifespan (2000 for sessile, 3000 for mobile). Reproduction triggers when energy > 1.5 (sessile, 1% chance/tick) or > 1.6 (mobile, 0.8% chance/tick), budding/spawning a new individual in an adjacent cell. Sessile reproduction requires an unoccupied rock cell.

**Hermit crab vacancy chains.** Empty shells are tracked as (row, col, size) tuples. Each tick, hermit crabs check adjacent cells for shells larger than their current one. On finding one, they swap — dropping their old shell at their current position. Dead crabs release their shells. New crab offspring need shells to reproduce; without available shells, they receive tiny (0.2) makeshift shells. In the Hermit Crab Shell Economy preset, 40 crabs and 20 initial shells create dense, observable vacancy chain dynamics — a single large shell dropped into the population can trigger a cascade of swaps.

**Sea star wasting disease.** In the Sea Star Wasting Event preset, all sea stars begin with elevated stress (0.4–0.7) and accumulate additional disease stress (+0.005/tick). At stress > 0.7, they also hemorrhage energy (-0.02/tick). As stars die, their keystone predation is removed — mussels expand unchecked through the mid-zone, outcompeting barnacles and anemones for rock space. This reproduces the trophic cascade observed in the real 2013–2015 Sea Star Wasting Syndrome epidemic along the Pacific coast.

**Presets (6):**

| Preset | Character | Initial Configuration |
|--------|-----------|----------------------|
| Pacific Rocky Shore | Classic temperate intertidal with full zonation | Balanced populations (60 barnacles, 40 mussels, 25 anemones, 30 kelp, 20 limpets, 15 sea stars, 20 urchins, 15 hermit crabs), standard tidal range (A=0.35, T=240) |
| Tropical Coral Flat | Warm shallow reef flat with low tidal range | Low amplitude (A=0.20), long period (T=300), more urchins (35) and anemones (40), fewer mussels (15) and kelp (15), more tide pools |
| Mussel Bed Dominance | Dense mussel beds competing for rock space | 80 mussels dense-seeded in mid zone, 30 barnacles, standard tidal range |
| Sea Star Wasting Event | Disease-stressed stars, cascading trophic effects | 30 sea stars with initial stress 0.4–0.7, ongoing disease stress accumulation, standard populations otherwise |
| Extreme Tidal Range | Bay of Fundy–scale exposure/submersion | High amplitude (A=0.45), short period (T=180), dramatic water level swings exposing and drowning huge vertical range |
| Hermit Crab Shell Economy | Dense hermit population with vacancy chain dynamics | 40 hermit crabs, 20 scattered empty shells of varying sizes, standard other populations |

**View modes (3, cycle with `v`):**
1. **Shore** — spatial ecosystem rendering: rock (#), sand (:), tide pools (~), algae (./%); organisms as colored glyphs (^ barnacle, M mussel, * anemone, X sea star, o urchin, | kelp, @ hermit crab, n limpet); animated water line with > indicator; splash spray dots above waterline; zone labels (SPRAY/HIGH/MID/LOW/SUBTIDAL) on right edge; info bar showing sessile/mobile counts, shell count, and tide state
2. **Cross-Section** — 5 horizontal zonation bands showing zone name, characteristic species list, current population count, submersion state ([submerged]/[exposed]), and density bar chart; animated water level label moves vertically with tide
3. **Graphs** — tide level sparkline (Unicode block elements ▁▂▃▄▅▆▇█), per-species population time series with mini sparklines for top 4 species by current count, average community stress history; all graphs show last 200 ticks

**Controls:** `Space`=play/pause, `n`/`.`=step, `v`=cycle views, `+/-`=simulation speed, `r`=reset, `R`/`m`=menu, `q`=exit.

**What to look for.** In Pacific Rocky Shore, watch the tide pulse up and down — as water recedes, the exposed mid-zone organisms begin accumulating desiccation stress (barnacle ^ and mussel M glyphs turn red when stressed). Sea stars (X) hunt only when submerged, creating "wave of death" fronts that sweep through mussel beds at high tide. Switch to Graphs view to see the tide sparkline drive anti-correlated stress peaks. Mussel Bed Dominance shows competitive exclusion in action — dense mussel beds spread through budding, outcompeting barnacles for rock attachment sites. Sea Star Wasting Event is the most dramatic ecological story: watch stars gradually die off (their X glyphs vanishing), then switch to Graphs to see mussel populations explode as predation pressure disappears — a textbook trophic cascade. Extreme Tidal Range creates the most visually dynamic water movement: the waterline sweeps across nearly half the screen each cycle, alternately drowning and exposing huge swaths of shore. Hermit Crab Shell Economy is best watched in Shore view — track the @ symbols as they encounter empty shells and swap, dropping their old shells for other crabs to find. In Tropical Coral Flat, the gentle tide (low amplitude, long period) creates a more stable, species-rich community with less stress oscillation.

**References.**
- Connell, J. H. "Community interactions on marine rocky intertidal shores." *Annual Review of Ecology and Systematics*, 3, 169–192, 1972. https://doi.org/10.1146/annurev.es.03.110172.001125
- Paine, R. T. "Food web complexity and species diversity." *The American Naturalist*, 100(910), 65–75, 1966. https://doi.org/10.1086/282400
- Paine, R. T. "Intertidal community structure: experimental studies on the relationship between a dominant competitor and its principal predator." *Oecologia*, 15, 93–120, 1974. https://doi.org/10.1007/BF00345739
- Menge, B. A. "Organization of the New England rocky intertidal community: role of predation, competition, and environmental heterogeneity." *Ecological Monographs*, 46(4), 355–393, 1976. https://doi.org/10.2307/1942563
- Denny, M. W. & Wethey, D. S. "Physical processes that generate patterns in marine communities." In *Marine Community Ecology* (eds. Bertness, M. D. et al.), 3–37, Sinauer, 2001.
- Lewis, J. R. *The Ecology of Rocky Shores*. English Universities Press, 1964.

---

## Spider Orb Web Construction & Prey Capture

**Background.** Orb-weaving spiders (family Araneidae) construct geometrically regular webs that are marvels of biological engineering — radial frame threads provide structural support while sticky spiral threads capture prey. The spider sits at the hub or on a signal thread, reading vibrations transmitted through the silk network to detect, locate, and identify trapped prey. This simulation models the complete lifecycle: web construction (frame → radii → auxiliary spiral → capture spiral), prey interception via collision with sticky threads, vibration-based prey triangulation, wind-driven elastic deformation of the thread network, thread degradation and repair, and adaptive geometry based on capture history.

**Web construction.** The web is built as a graph of nodes and threads:

```
1. Frame:    4 anchor nodes form a rectangular boundary (SILK_FRAME, strength=1.0, elasticity=0.3)
2. Radii:    N radial threads from central hub to frame (SILK_RADIAL, strength=0.8, elasticity=0.4)
             Intermediate nodes placed at regular intervals along each radius
3. Aux:      Inner spiral connecting radial nodes (SILK_AUX, strength=0.4, elasticity=0.2)
             Non-sticky scaffold for spider locomotion
4. Sticky:   Outer spiral connecting radial nodes (SILK_STICKY, strength=0.5, elasticity=0.8)
             Capture zone — glue droplets trap prey on contact
```

The tangle weaver preset adds random cross-threads between nodes within half the web radius, producing an irregular 3D-style cobweb.

**Silk types.** Four silk types with distinct mechanical properties:

| Silk Type | Strength | Elasticity | Sticky | Role |
|-----------|----------|------------|--------|------|
| Frame | 1.0 | 0.3 | No | Structural boundary, anchors to environment |
| Radial | 0.8 | 0.4 | No | Load-bearing spokes from hub to frame |
| Auxiliary | 0.4 | 0.2 | No | Inner scaffold spiral, spider walkway |
| Sticky | 0.5 | 0.8 | Yes | Outer capture spiral with glue droplets |

**Vibration propagation.** When prey struggles, it generates vibration at its capture node. Waves propagate through the thread adjacency graph:

```
Node vibration decay:   v(t+1) = v(t) × 0.85
Thread vibration decay: v(t+1) = v(t) × 0.80

Transfer per hop:
  attenuation = max(0.1, 1.0 - distance × 0.02)
  thread_vibration = max(current, source × 0.3 × attenuation)
  neighbor_vibration = max(current, transfer × 0.5)
```

The spider detects the node with maximum vibration (threshold > 0.05) and checks for trapped, unwrapped prey within distance 3 of that node.

**Prey mechanics.** Five insect types with distinct properties:

| Prey | Glyph | Struggle | Mass | Spawn Weight |
|------|-------|----------|------|--------------|
| Moth | m | 0.7 | 0.6 | 3 |
| Fly | f | 0.5 | 0.3 | 4 |
| Mosquito | : | 0.3 | 0.1 | 3 |
| Beetle | B | 0.9 | 0.8 | 1 |
| Butterfly | W | 0.4 | 0.4 | 1 |

Prey spawn at random screen edges, fly with random walk + slight center attraction + wind drift, and stick to SILK_STICKY threads via point-to-segment collision (distance < 0.8). Trapped prey snap to the nearest thread node and generate an initial vibration burst of mass × 1.5. Struggle decays at ×0.995/tick; wrapping by the spider further suppresses it at ×0.9/tick.

**Wind physics.** Elastic spring model on the thread network:

```
Base wind:  wx = strength × sin(t × 0.02) × 0.5
            wy = strength × cos(t × 0.015) × 0.3

Gusts:      3% chance/tick, duration 10–40 ticks
            gust_strength = base × (1.5 + rand × 2.0)
            Storm preset: gust_strength × 2.0

Node forces:
  Wind:     v += wind × 0.01
  Restore:  v += (rest_pos - pos) × 0.05
  Spring:   F = k × stretch × direction / distance
            k = 0.02 × (1.0 + elasticity)
  Damping:  v × 0.85 each tick
```

**Thread degradation.** Threads break probabilistically based on accumulated stress:

```
Break probability:
  + 0.05 × (tension - strength) / strength    if tension > strength
  + 0.002                                      if storm preset
  + 0.001                                      if sticky silk and age > 500
  + 0.005                                      if already stressed
```

Threads enter STRESSED state when tension > 0.7 × strength. Broken threads are removed from the adjacency graph, blocking vibration propagation through that path.

**Spider AI.** State machine with energy and silk management:

| State | Behavior | Energy Cost |
|-------|----------|-------------|
| WAITING | At hub, monitors vibrations, regenerates (+0.002 energy, +0.05 silk/tick) | None |
| RUSHING | Moves toward trapped prey at speed min(1.5, dist×0.3) | -0.003/tick |
| WRAPPING | Wraps prey (+0.05 wrapped/tick, -0.3 silk/tick), suppresses struggle | -0.002/tick |
| REPAIRING | Moves to broken threads, repairs (-3.0 silk each, restored at 70% strength) | -0.002/tick |
| RESTING | Returns to hub, fast regeneration (+0.005 energy, +0.1 silk/tick) | None |

Energy < 0.1 forces RESTING state. Successful capture grants +0.2 energy and records the angular zone (8 bins) for adaptive behavior.

**Presets (6):**

| Preset | Character | Configuration |
|--------|-----------|--------------|
| Garden Orb Weaver | Classic orb web, sheltered garden | 24 radii, 1.2 spiral spacing, moderate wind, prey rate 0.02 |
| Morning Dew Web | Calm dawn, dew on silk | Wind 0.01, prey rate 0.01, slow peaceful web |
| Storm Damage & Repair | Fierce gusts shred the web | Wind 0.5, gusts ×2, prey rate 0.015, frequent breakage |
| Prey Bonanza | Insect swarm overwhelms web | Prey rate 0.08, wind 0.05, rapid silk depletion |
| Cobweb Tangle Weaver | Irregular 3D tangle web | 40 radii, 0.8 spacing, extra random cross-threads, prey rate 0.025 |
| Golden Silk Orbweaver | Nephila-style giant web | Radius ×0.48, 32 radii, 150 silk reserve, prey rate 0.03 |

**View modes (3, cycle with `v`):**
1. **Web Structure** — thread network drawn with Unicode line characters (`─│╲╱·`), junction dots at nodes, vibration ripples (`○` high / `∙` medium), prey glyphs color-coded (green free, red trapped, dim wrapped `●`), spider `◆` colored by state (green waiting, red rushing, yellow wrapping, cyan repairing), wind direction arrow with magnitude bar, spider state label
2. **Vibration Heatmap** — threads colored by vibration intensity (`·`=none, `░`=low, `▒`=medium, `▓`=high, `█`=peak), trapped prey as `◎`, spider as `◆`, legend bar
3. **Time-Series Graphs** — four sparkline graphs (Unicode block elements `▁▂▃▄▅▆▇█`) showing cumulative captures, web integrity %, silk reserves, and trapped prey count over last 200 ticks; stats summary with total captures, silk level, energy %, and current state

**Controls:** `Space`=play/pause, `n`/`.`=step, `v`=cycle views, `+/-`=simulation speed, `r`=reset, `R`/`m`=menu, `q`=exit.

**What to look for.** In Garden Orb Weaver, watch the web gently flex in the wind while the spider waits at the hub. When a prey insect (colored green) drifts into a sticky spiral thread, it snaps to the nearest node and begins struggling — vibration ripples (`○∙`) radiate outward through the thread network. The spider turns red and rushes along the radial threads toward the trapped prey, then turns yellow while wrapping it in silk. Switch to Vibration Heatmap view to see wave propagation clearly — trapped prey appear as bright `◎` spots with `▓█` intensity fading outward through connected threads. Storm Damage & Repair is the most dramatic preset: violent gusts deform the web, threads snap (gaps appear in the spiral), and the spider enters repair mode, patching broken sections with weaker replacement silk. Watch the Graphs view — web integrity drops during gusts and recovers as the spider repairs. Prey Bonanza overwhelms the web with insects; the spider can't wrap them all before silk runs out, and some prey struggle free. Morning Dew Web is serene — barely any wind, slow prey arrival, the web stays pristine. Golden Silk Orbweaver builds a noticeably larger web with more silk reserves. Cobweb Tangle Weaver produces a messy, irregular web with cross-threads in all directions — vibrations propagate differently through the tangled structure.

**References.**
- Vollrath, F. "Spider webs and silks." *Scientific American*, 266(3), 70–76, 1992. https://doi.org/10.1038/scientificamerican0392-70
- Wirth, E. & Barth, F. G. "Forces in the spider orb web." *Journal of Comparative Physiology A*, 171, 359–371, 1992. https://doi.org/10.1007/BF00223966
- Masters, W. M. & Markl, H. "Vibration signal transmission in spider orb webs." *Science*, 213(4505), 363–365, 1981. https://doi.org/10.1126/science.213.4505.363
- Zschokke, S. & Vollrath, F. "Web construction patterns in a range of orb-weaving spiders (Araneae)." *European Journal of Entomology*, 92(3), 523–541, 1995.
- Ko, F. K. & Jovicic, J. "Modeling of mechanical properties and structural design of spider web." *Biomacromolecules*, 5(3), 780–785, 2004. https://doi.org/10.1021/bm0345099
