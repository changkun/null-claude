# Procedural & Computational

Algorithms made visible — from constraint solving to ray marching, neural networks to digital evolution.

---

## Wave Function Collapse

**Background**

Wave Function Collapse (WFC) is a constraint-satisfaction algorithm inspired by quantum mechanics and first described by Maxim Gumin in 2016. Originally developed for procedural texture synthesis, it generates globally coherent patterns from local adjacency rules. The algorithm is widely used in game development for procedurally generating tile maps, dungeon layouts, and texture patterns.

**Formulation**

```
Given:
  T          = set of tile types {0, 1, ..., N-1}
  A(t, d)    = set of tiles allowed adjacent to tile t in direction d
               where d in {N, S, E, W}
  grid[r][c] = set of possible tiles for cell (r, c), initially T

Algorithm (one step):
  1. OBSERVE: find uncollapsed cell with minimum entropy
     entropy(r, c) = |grid[r][c]|
     candidates = {(r, c) : collapsed[r][c] == -1 and entropy is minimal}

  2. COLLAPSE: pick random cell from candidates, pick random tile from its possibilities
     grid[r][c] = {tile}

  3. PROPAGATE (BFS from collapsed cell):
     for each neighbor (nr, nc) in direction d:
       allowed = union of A(t, d) for all t in grid[r][c]
       grid[nr][nc] = grid[nr][nc] intersect allowed
       if |grid[nr][nc]| == 0: CONTRADICTION
       if |grid[nr][nc]| reduced: continue propagating from (nr, nc)

Adjacency symmetry is enforced:
  if B in A(A_tile, N) then A_tile in A(B, S)
```

**What to look for**

Watch entropy visualized as brightness: uncollapsed cells with fewer remaining options appear lighter. Contradictions occur when no valid tile remains for a cell -- the propagation cascade has over-constrained a region. Different preset tile sets (Island, City, Dungeon) produce radically different spatial structures from the same algorithm. Increasing steps-per-frame reveals how constraint propagation creates coherent large-scale patterns from purely local rules.

**References**

- Gumin, M. "WaveFunctionCollapse." GitHub repository, 2016. https://github.com/mxgmn/WaveFunctionCollapse
- Karth, I. and Smith, A.M. "WaveFunctionCollapse is Constraint Solving in the Wild." *Proceedings of FDG*, 2017. https://doi.org/10.1145/3102071.3110566

---

## Maze Generation

**Background**

Maze generation algorithms construct perfect mazes -- connected graphs where exactly one path exists between any two cells. Three classical approaches are implemented: the recursive backtracker (depth-first search), Prim's algorithm (randomized minimum spanning tree), and Kruskal's algorithm (union-find based edge merging). These algorithms date to the early study of graph theory and remain foundational in computer science education.

**Formulation**

```
Grid: odd-dimensioned array where odd-indexed cells are passages, even-indexed are walls.

Recursive Backtracker (DFS):
  1. Start at cell (1,1), mark visited, push onto stack
  2. While stack not empty:
     - current = stack.top()
     - neighbors = unvisited cells 2 steps away (N/S/E/W)
     - if neighbors exist:
         pick random neighbor (nr, nc)
         carve wall between current and neighbor
         mark neighbor visited, push onto stack
     - else: pop stack (backtrack)

Prim's Algorithm:
  1. Start at cell (1,1), add frontier edges
  2. While frontier edges exist:
     - pick random edge (from, to)
     - if 'to' unvisited: carve wall, add new frontier edges from 'to'

Kruskal's Algorithm:
  1. Mark all odd-indexed cells as passages, assign unique set IDs
  2. List all possible edges between adjacent passages, shuffle
  3. For each edge (c1, c2):
     - if set(c1) != set(c2): carve wall, merge sets

Pathfinding (after generation):
  A*:       f(n) = g(n) + h(n), where h = Manhattan distance to end
  Dijkstra: f(n) = g(n), uniform cost
  BFS:      FIFO queue, guarantees shortest path
  DFS:      LIFO stack, explores deeply before backtracking
```

**What to look for**

The recursive backtracker produces long, winding corridors with a bias toward depth. Prim's algorithm creates shorter, more branching passages. Kruskal's generates uniform spanning trees. During solving, compare how A* (guided by Manhattan distance heuristic) explores far fewer cells than BFS or DFS to find the same path. The solver visualization colors explored cells, frontier cells, and the final solution path distinctly.

**References**

- Buck, J. *Mazes for Programmers.* Pragmatic Bookshelf, 2015. https://pragprog.com/titles/jbmaze/mazes-for-programmers/
- Cormen, T.H. et al. *Introduction to Algorithms,* 3rd ed. MIT Press, 2009. (Ch. 22-24: Graph algorithms) https://mitpress.mit.edu/books/introduction-algorithms-third-edition

---

## Voronoi Diagram

**Background**

Voronoi diagrams partition space into regions closest to a set of seed points, a construction first studied by Dirichlet (1850) and formalized by Voronoi (1908). This implementation models crystal growth: seeds expand outward with anisotropic growth rates determined by preferred crystallographic angles, producing realistic grain boundary patterns found in metals and ceramics.

**Formulation**

```
Parameters:
  seeds[i]  = (r, c)         position of seed i
  angle[i]  = theta           preferred growth direction (radians)
  aniso     = A in [0, 0.9]   anisotropy strength

Growth probability for frontier cell (r, c) belonging to grain i:
  dr = r - seeds[i].r
  dc = c - seeds[i].c
  angle_to_cell = atan2(dr, dc)
  diff = |angle_to_cell - angle[i]|
  if diff > pi: diff = 2*pi - diff

  P(claim) = max(0.1, 1.0 - A * diff / pi)

Each step:
  1. Shuffle frontier randomly (ensures natural growth)
  2. For each frontier cell: claim with probability P
  3. Claimed cells add their unclaimed 8-neighbors to frontier

Grain boundary detection:
  Cell (r, c) is a boundary if any 8-neighbor belongs to a different grain.

Seed placement modes: random, edge, bicrystal, center
```

**What to look for**

With anisotropy at zero, grains grow as roughly circular Voronoi cells. As anisotropy increases, grains elongate along their preferred angles, producing faceted crystals resembling real metallographic micrographs. Grain boundaries (highlighted as distinct characters) form triple junctions where three grains meet, a universal feature of polycrystalline materials. The bicrystal mode with just two seeds demonstrates how misorientation angle affects boundary morphology.

**References**

- Aurenhammer, F. "Voronoi Diagrams: A Survey of a Fundamental Geometric Data Structure." *ACM Computing Surveys* 23(3), 1991. https://doi.org/10.1145/116873.116880
- Anderson, M.P. et al. "Computer Simulation of Grain Growth -- I. Kinetics." *Acta Metallurgica* 32(5), 1984. https://doi.org/10.1016/0001-6160(84)90151-2

---

## Terrain Generation

**Background**

Procedural terrain generation combines layered noise functions with geological erosion simulation to produce realistic landscapes. The technique originates from Perlin's gradient noise (1985) and has been extended with hydraulic and thermal erosion models used in films and games. This implementation couples tectonic uplift, thermal weathering, hydraulic erosion, and vegetation dynamics into a continuous geological simulation.

**Formulation**

```
Terrain generation (layered value noise):
  height(r, c) = sum over octaves:
    smooth_noise(frequency_i, amplitude_i)
  where each octave uses bilinear interpolation on a sparse random grid.
  Typical octave stack: freq = {3, 6, 12, 24}, amp = {0.5, 0.3, 0.15, 0.05}

Tectonic uplift (per step):
  factor(r, c) = max(0.2, 1.0 - 0.6 * dist_to_center / max_dist)
  h(r, c) += uplift_rate * factor * (0.8 + 0.4 * rand())

Thermal erosion (talus slope failure):
  talus_threshold = 0.06
  for each neighbor (nr, nc):
    diff = h(r,c) - h(nr,nc)
    if diff > talus_threshold:
      veg_factor = max(0.1, 1.0 - vegetation(r,c) * 0.8)
      hard_factor = 1.0 / (0.5 + hardness(r,c))
      transfer = thermal_rate * (diff - threshold) * 0.5 * veg_factor * hard_factor
      h(r,c) -= transfer;  h(nr,nc) += transfer

Hydraulic erosion (rain-driven):
  Find steepest downhill neighbor
  erode_amt = rain_rate * slope * veg_factor * noise
  Deposit 60% downstream, 40% lost to sea (net sediment transport)

Vegetation dynamics:
  Below sea level:      v = 0 (submerged)
  Coastal (< sea+0.05): v grows slowly, max 0.2
  Alpine (> 0.85):      v decays (too cold)
  Temperate:            v grows proportional to (1 - slope_penalty)
```

**What to look for**

Over geological epochs, observe the competition between uplift (building mountains) and erosion (wearing them down). Vegetation stabilizes slopes -- increasing vegetation growth rate dramatically reduces erosion. Toggle between four views: topographic (elevation bands with vegetation overlay), raw elevation, vegetation density, and erosion activity (red = steep active slopes, blue = stable flats). Terrain types include continental shelves, archipelagos, alpine ranges, rift valleys, and coastal gradients.

**References**

- Musgrave, F.K., Kolb, C.E., and Mace, R.S. "The Synthesis and Rendering of Eroded Fractal Terrains." *SIGGRAPH* 1989. https://doi.org/10.1145/74334.74337
- Cordonnier, G. et al. "Large Scale Terrain Generation from Tectonic Uplift and Fluvial Erosion." *Computer Graphics Forum* 35(2), 2016. https://doi.org/10.1111/cgf.12820

---

## 3D Terrain Flythrough

**Background**

First-person terrain flythrough renders procedural landscapes in real-time pseudo-3D using perspective projection and height-field raycasting, a technique pioneered in the Voxel Space engine (Comanche, 1992). This mode generates a 256x256 heightmap with cosine-interpolated layered noise, then renders a first-person view with altitude zones, distance fog, and a day/night cycle.

**Formulation**

```
Heightmap generation: same layered noise as Terrain Generation, but with
  cosine interpolation: f_smooth = (1 - cos(f * pi)) * 0.5
  on a 256x256 tile-wrapping grid.

Camera model:
  position = (cam_x, cam_y, cam_z)  -- y is altitude
  orientation = (yaw, pitch)
  movement: dx = cos(yaw) * speed,  dz = sin(yaw) * speed
  minimum altitude = terrain_height(cam_x, cam_z) + 2.0

Perspective projection (per screen column):
  ray_yaw = yaw + (col / view_w - 0.5) * FOV
  ray_dir = (cos(ray_yaw), sin(ray_yaw))

  For each row below horizon:
    frac = rows_below_horizon / (view_h - horizon_row)
    dist = min_dist + (max_dist - min_dist) * (1 - frac)^0.5
    world_pos = camera + ray_dir * dist * pitch_factor
    terrain_h = bilinear_interpolate(heightmap, world_pos)

Height-based biome rendering:
  < 0.15: deep water    0.15-0.25: shallow    0.25-0.30: beach
  0.30-0.50: grass      0.50-0.65: forest     0.65-0.80: rock
  0.80-0.90: mountain   > 0.90: snow caps

Distance fog: beyond 50 units, characters fade to dots
Day/night: time cycles 0.0-1.0 (midnight-midnight), affects sky color and dimming
```

**What to look for**

The non-linear depth mapping (square root) gives a natural perspective where nearby terrain has high detail and the horizon fades gradually. Fly over canyon terrain types to see the carved V-shape valleys. The day/night cycle transitions through dawn (yellow), day (cyan sky with sun arc), dusk (red), and night (stars and moon). Different terrain presets (hills, mountains, canyon, islands, glacial, alien) demonstrate how the same noise framework produces vastly different landscapes through post-processing transforms.

**References**

- Comanche engine, NovaLogic, 1992. (Voxel Space rendering technique) https://en.wikipedia.org/wiki/Voxel_Space
- Perlin, K. "An Image Synthesizer." *SIGGRAPH* 1985. https://doi.org/10.1145/325165.325247

---

## SDF Ray Marching

**Background**

Signed Distance Field (SDF) ray marching is a rendering technique where the distance to the nearest surface guides ray advancement, enabling efficient rendering of implicit surfaces, fractals, and boolean CSG operations. Popularized by Inigo Quilez through ShaderToy (2013+), it has become the standard technique for real-time fractal rendering. This implementation renders six SDF scenes with Blinn-Phong shading and soft shadows.

**Formulation**

```
Core ray marching loop (64 iterations max):
  t = 0
  for each step:
    p = camera_pos + ray_dir * t
    d = SDF(p)
    if d < 0.002: HIT
    t += d
    if t > 30.0: MISS

SDF primitives:
  Sphere:   SDF = |p| - R
  Torus:    q = (sqrt(px^2 + pz^2) - R, py)
            SDF = |q| - r
  Box:      d = |p| - half_extents
            SDF = |max(d, 0)| + min(max(dx, dy, dz), 0)

  Mandelbulb fractal (8 iterations):
    z = p; dr = 1
    r = |z|;  if r > 2: break
    theta = acos(zz/r) * power
    phi = atan2(zy, zx) * power
    zr = r^power
    dr = r^(power-1) * power * dr + 1
    z = zr * (sin(theta)*cos(phi), sin(theta)*sin(phi), cos(theta)) + p
    SDF = 0.5 * ln(r) * r / dr

  Smooth blend (smooth union):
    h = clamp(0.5 + 0.5*(d2-d1)/k, 0, 1)
    SDF = lerp(d2, d1, h) - k*h*(1-h)     where k = 0.5

Surface normal (central differences, epsilon = 0.001):
  n = normalize(SDF(p+ex) - SDF(p-ex), SDF(p+ey) - SDF(p-ey), SDF(p+ez) - SDF(p-ez))

Lighting (Blinn-Phong):
  diffuse  = max(0, n . L)
  half_vec = normalize(L - ray_dir)
  specular = (max(0, n . half_vec))^32 * 0.5
  ambient  = 0.15
  brightness = ambient + diffuse * shadow * 0.75 + specular * shadow

Soft shadows (32 steps, k = 8):
  t = 0.05; res = 1.0
  d = SDF(origin + L * t)
  res = min(res, k * d / t)
  t += max(d, 0.02)
  shadow = clamp(res, 0, 1)
```

**What to look for**

The Mandelbulb preset reveals infinite self-similar detail as you zoom in -- adjust the power parameter (default 8) to morph between different fractal shapes. The smooth blend scene demonstrates how SDFs enable organic transitions between geometries impossible with mesh-based rendering. Observe how soft shadows create penumbra effects where the shadow factor smoothly decreases near occluder edges. The color mapping uses surface normal direction: green for Y-facing, cyan for Z-facing, magenta for X-facing surfaces.

**References**

- Hart, J.C. "Sphere Tracing: A Geometric Method for the Antialiased Ray Tracing of Implicit Surfaces." *The Visual Computer* 12(10), 1996. https://doi.org/10.1007/s003710050084
- Quilez, I. "Distance Functions." 2008-2024. https://iquilezles.org/articles/distfunctions/

---

## Shader Toy

**Background**

Shader Toy implements real-time per-pixel mathematical animations inspired by the ShaderToy web platform created by Inigo Quilez and Pol Jeremias in 2013. Each preset defines a fragment shader as a pure function of normalized screen coordinates (nx, ny) and time t, producing visual effects through trigonometric composition, distance fields, and iterative transforms. The simulator renders these to ASCII with configurable color palettes.

**Formulation**

```
For each pixel at normalized coords (nx, ny) in [-1, 1] and time t:
  val = shader(nx, ny, t)    -- returns value in [0, 1]
  char = shade_chars[int(val * N)]
  color = palette_map(val)

Shader functions (selection of 10 presets):

  Plasma Waves:
    v = sin(nx*10*A + t) + sin((ny*10*B + t)*0.7)
      + sin((nx*10 + ny*10 + t)*0.5)
      + sin(sqrt(nx^2*100 + ny^2*100)*A + t)
    val = (v/4 + 1) * 0.5

  Tunnel Zoom:
    r = sqrt(dx^2 + dy^2) + epsilon
    angle = atan2(dy, dx)
    val = (sin(1/(r*A) + t*2) * cos(angle*3*B + t) + 1) * 0.5

  Metaballs:
    val = sum over 5 balls:
      cx_i = sin(t * (0.3 + i*0.17) * A) * 0.5
      cy_i = cos(t * (0.4 + i*0.13) * B) * 0.5
      0.03 / ((nx-cx)^2 + (ny-cy)^2 + 0.01)
    val = min(1, val * 0.15)

  Spiral Galaxy:
    r = sqrt(nx^2 + ny^2);  angle = atan2(ny, nx)
    spiral = sin(angle*2*A - r*10*B + t*1.5)
    arm = max(0, spiral) * max(0, 1 - r*1.2)
    core = max(0, 0.3 - r) * 3
    val = arm + core + ripple_term

Parameters A, B in [0.1, 3.0] modulate each shader's spatial frequency.
Color modes: Rainbow, Fire, Ocean, Mono.
```

**What to look for**

Parameters A and B act as spatial frequency multipliers -- increasing them creates finer detail in the pattern. The Metaballs shader demonstrates implicit surface visualization: watch five moving charge points create smooth organic merges where their fields overlap. The Kaleidoscope preset uses modular angular arithmetic to create symmetric patterns from a simple distance function. Compare how the same mathematical output maps to different aesthetics across the four color palettes.

**References**

- Quilez, I. and Jeremias, P. "ShaderToy." https://www.shadertoy.com, 2013.
- Gonzalez-Vivo, P. and Lowe, J. *The Book of Shaders.* 2015. https://thebookofshaders.com

---

## Doom Raycaster

**Background**

The Doom-style raycaster reproduces the rendering technique used by Wolfenstein 3D (id Software, 1992), where a single ray is cast per screen column to determine wall distance and projected height. This was one of the first real-time 3D rendering methods for consumer hardware. The implementation adds fisheye correction, distance-based wall shading, floor rendering, and a minimap overlay.

**Formulation**

```
Camera model:
  position = (px, py) in map coordinates
  angle = pa (player angle in radians)
  FOV = field of view (radians)

For each screen column x in [0, screen_w):
  ray_angle = (pa - FOV/2) + (x / screen_w) * FOV

  Ray stepping (step_size = 0.02, max_depth):
    ray_x = px + cos(ray_angle) * dist
    ray_y = py + sin(ray_angle) * dist
    if map[int(ray_y)][int(ray_x)] == '#': HIT

  Fisheye correction:
    dist_corrected = dist * cos(ray_angle - pa)

  Wall projection:
    wall_height = screen_h / dist_corrected
    ceiling = (screen_h - wall_height) / 2
    floor = ceiling + wall_height

  Rendering per column:
    y < ceiling:  empty (ceiling)
    ceiling <= y <= floor:  wall char by shade_wall[dist/depth]
    y > floor:    floor char by shade_floor[brightness]

  Wall color by distance:
    < 25% depth: bold magenta    < 50%: yellow
    < 75%: dim                   else: very dim

Collision detection with wall sliding:
  margin = 0.2 (player radius)
  Try full movement, then X-only, then Y-only
  Check all four corners of player bounding box
```

**What to look for**

The fisheye correction eliminates the barrel distortion that would otherwise occur when projecting rays at angles away from the view center. Notice how wall shading characters transition from solid blocks at close range to sparse dots at distance, creating a convincing depth effect in pure ASCII. Wall sliding allows smooth movement along walls instead of abrupt stops. The implementation directly descends from the column-based rendering that powered the early 1990s FPS revolution.

**References**

- Permadi, F. "Ray-Casting Tutorial." 1996. https://permadi.com/1996/05/ray-casting-tutorial/
- Sanglard, F. *Game Engine Black Book: Wolfenstein 3D.* Self-published, 2017. https://fabiensanglard.net/gebbwolf3d/

---

## Sorting Algorithm Visualizer

**Background**

Sorting algorithm visualization transforms abstract computational complexity into observable behavior. First popularized by Ronald Baecker's film "Sorting Out Sorting" (1981), animated sorting has become a standard pedagogical tool. This implementation pre-computes all comparison and swap operations for six algorithms, then replays them as animated bar charts with per-step highlighting.

**Formulation**

```
Algorithms and their complexities:

  Bubble Sort:     O(n^2) comparisons, O(n^2) swaps
    for i in [0, n):
      for j in [0, n-i-1):
        if a[j] > a[j+1]: swap(a[j], a[j+1])

  Quicksort (Lomuto partition):  O(n log n) average, O(n^2) worst
    partition(lo, hi):
      pivot = a[hi]; i = lo
      for j in [lo, hi): if a[j] <= pivot: swap(a[i], a[j]); i++
      swap(a[i], a[hi]); return i

  Merge Sort:      O(n log n) guaranteed
    Divide array in half, recursively sort, merge by comparing heads

  Heap Sort:       O(n log n) in-place
    Build max-heap, repeatedly extract maximum to sorted position

  Radix Sort (LSD): O(d * (n + k)) where d = digits, k = 10
    For each digit position (units, tens, ...):
      counting sort by current digit

  Shell Sort:      O(n^(3/2)) with gap/2 sequence
    gap = n/2; while gap > 0:
      insertion sort with stride = gap; gap /= 2

Each operation recorded as a step tuple:
  ("cmp", i, j, array_state)   -- comparison
  ("swap", i, j, array_state)  -- element exchange
  ("write", i, array_state)    -- overwrite (merge/radix)
  ("sorted", idx, array_state) -- mark position final
```

**What to look for**

Bubble sort's quadratic nature is immediately visible as the algorithm makes many passes with diminishing effect. Quicksort shows dramatic pivot-based partitioning with recursive subdivision. Merge sort's merge phase creates satisfying sorted runs that double in length. Radix sort operates digit-by-digit with no comparisons, producing wave-like reorganization patterns. The info panel tracks comparisons vs. swaps -- compare merge sort's high write count against quicksort's lower total operations.

**References**

- Baecker, R. "Sorting Out Sorting" (film). University of Toronto, 1981. https://www.youtube.com/watch?v=SJwEwA5gOkM
- Sedgewick, R. and Wayne, K. *Algorithms,* 4th ed. Addison-Wesley, 2011. https://algs4.cs.princeton.edu/home/

---

## DNA Helix & Genetic Algorithm

**Background**

Genetic algorithms (GAs), introduced by John Holland in 1975, optimize by mimicking natural selection: a population of candidate solutions undergoes selection, crossover, and mutation over generations. This mode visualizes a binary GA evolving toward a target genome, rendered as a rotating double helix. The Royal Road fitness function, designed by Mitchell et al. (1992), specifically tests the GA's ability to discover building blocks.

**Formulation**

```
Genome: binary string of length L (32, 48, 64, or 128 bits)
Population: N individuals (10 to 60)

Fitness functions:
  Standard:   f(genome) = (matching bits with target) / L
  Royal Road:  block_size = 8;  n_blocks = L / 8
               f(genome) = (complete matching 8-bit blocks) / n_blocks

Selection: tournament selection, size 3
  Pick 3 random individuals, select the fittest

Crossover (single-point, rate = crossover_rate):
  cx = random point in [1, L-1]
  child = parent1[:cx] + parent2[cx:]

Mutation (per-bit, rate = mutation_rate):
  for each bit i in child:
    if rand() < mutation_rate: child[i] = 1 - child[i]

Elitism: best individual always survives to next generation

Preset configurations:
  Classic:      L=32,  N=40,  mutation=0.02,  crossover=0.7
  OneMax:       L=64,  N=50,  mutation=0.015, crossover=0.8
  Long Strand:  L=128, N=60,  mutation=0.005, crossover=0.7
  Hyper-Mutate: L=32,  N=40,  mutation=0.10,  crossover=0.6
  Minimal Pop:  L=48,  N=10,  mutation=0.03,  crossover=0.7
  Royal Road:   L=64,  N=50,  mutation=0.02,  crossover=0.75
```

**What to look for**

The fitness history curve reveals the characteristic GA trajectory: rapid initial improvement as easy bits are found, followed by a plateau as the algorithm searches for remaining mismatches. The Hyper-Mutation preset shows how excessive mutation (10%) prevents convergence -- fitness oscillates chaotically. The Minimal Population preset demonstrates genetic drift in small populations. The Royal Road fitness function produces staircase-like jumps as complete 8-bit schema blocks snap into place, illustrating Holland's building block hypothesis.

**References**

- Holland, J.H. *Adaptation in Natural and Artificial Systems.* University of Michigan Press, 1975. https://doi.org/10.7551/mitpress/1090.001.0001
- Mitchell, M., Forrest, S., and Holland, J.H. "The Royal Road for Genetic Algorithms: Fitness Landscapes and GA Performance." *Proceedings of the First European Conference on Artificial Life*, 1992. https://doi.org/10.7551/mitpress/2090.003.0019

---

## Fourier Epicycle Drawing

**Background**

Fourier epicycles demonstrate that any closed curve can be approximated by a sum of rotating circles, a consequence of the Discrete Fourier Transform (DFT) first formalized by Joseph Fourier in 1807. This visualization computes the DFT of a sampled path and reconstructs it as a chain of orbiting circles, directly illustrating how frequency decomposition works. The concept was popularized by 3Blue1Brown's 2019 video "But what is a Fourier series?"

**Formulation**

```
Input: N sample points P[n] = (x_n, y_n) along a closed curve

Discrete Fourier Transform:
  For each frequency k in [0, N):
    Re_k = (1/N) * sum_{n=0}^{N-1} [ x_n * cos(2*pi*k*n/N) + y_n * sin(2*pi*k*n/N) ]
    Im_k = (1/N) * sum_{n=0}^{N-1} [ y_n * cos(2*pi*k*n/N) - x_n * sin(2*pi*k*n/N) ]
    amplitude_k = sqrt(Re_k^2 + Im_k^2)
    phase_k = atan2(Im_k, Re_k)

  Coefficients sorted by amplitude (largest first)

Reconstruction (epicycle chain):
  At time t:
    (x, y) = (0, 0)
    for i in [0, num_circles):
      angle = freq_i * t + phase_i
      x += amplitude_i * cos(angle)
      y += amplitude_i * sin(angle)
    trace.append((x, y))

  Time step: dt = 2*pi / N (one full cycle reproduces the original path)

Preset shapes: circle, square, star, figure-8, heart, spiral-square
Free-draw mode: user draws path with cursor, DFT computed on completion
```

**What to look for**

Start with all circles enabled, then use [ and ] to reduce the count. With few circles, only the coarse shape is visible; adding circles progressively refines the approximation. The square preset is particularly instructive: it requires many high-frequency harmonics for sharp corners, so reducing circles rounds the corners (the Gibbs phenomenon). The heart preset demonstrates how a non-trivial parametric curve decomposes into a manageable number of epicycles. The free-draw mode lets you sketch any shape and see its Fourier decomposition.

**References**

- Fourier, J. *Theorie analytique de la chaleur.* 1822. https://archive.org/details/thorieanalytiq00four
- Sanderson, G. (3Blue1Brown) "But what is a Fourier series? From heat flow to drawing with circles." YouTube, 2019. https://www.youtube.com/watch?v=r6sGWTCMz2k

---

## Maze Solver Visualizer

**Background**

This mode focuses on comparing pathfinding algorithms by generating a maze instantly and then animating the solving process step-by-step. Four algorithms are implemented: A* (optimal, heuristic-guided), BFS (optimal, exhaustive), DFS (non-optimal, depth-first), and the right-hand wall follower (a simple rule requiring no memory of visited cells). These algorithms represent fundamentally different search strategies with distinct performance characteristics.

**Formulation**

```
Maze generation: recursive backtracker (instant, pre-computed)

Solving algorithms:

  A* Search:
    priority queue ordered by f = g + h
    g = steps from start;  h = |end_r - r| + |end_c - c| (Manhattan distance)
    Optimal and complete; explores fewest cells when heuristic is admissible

  BFS (Breadth-First Search):
    FIFO queue
    Explores in concentric wavefronts from start
    Guarantees shortest path; explores all cells at distance d before d+1

  DFS (Depth-First Search):
    LIFO stack
    Explores as deep as possible before backtracking
    NOT guaranteed to find shortest path; may explore many dead ends

  Wall Follower (right-hand rule):
    Directions: right=0, down=1, left=2, up=3
    Priority: try turn right, then straight, then left, then reverse
    for turn in [+1, 0, -1, +2]:
      new_dir = (current_dir + turn) % 4
      if passable: move and update direction
    Works only on simply-connected mazes (no loops)

Path reconstruction: trace parent pointers from end to start
```

**What to look for**

Compare the explored cell count across algorithms on the same maze. A* typically explores a narrow corridor toward the goal, while BFS floods outward uniformly. DFS may find a long, winding path quickly or get trapped in dead ends far from the goal. The wall follower traces the maze boundary, often visiting cells multiple times -- its trail shows characteristic repeated visits to corridors. The frontier (cells in the queue, shown as highlighted blocks) reveals each algorithm's search strategy: A*'s frontier clusters near the goal, BFS's frontier forms a wavefront, DFS's frontier is a single deep tendril.

**References**

- Hart, P.E., Nilsson, N.J., and Raphael, B. "A Formal Basis for the Heuristic Determination of Minimum Cost Paths." *IEEE Transactions on Systems Science and Cybernetics* 4(2), 1968. https://doi.org/10.1109/TSSC.1968.300136
- Even, S. *Graph Algorithms,* 2nd ed. Cambridge University Press, 2011. https://doi.org/10.1017/CBO9781139015165

---

## Neural Network Training Visualizer

**Background**

This mode implements a complete feed-forward neural network with backpropagation in pure Python (no external libraries), visualizing the training process in real time. The network architecture, weight connections, gradient flow, decision boundary, and loss/accuracy curves are all displayed simultaneously. The implementation follows Rumelhart, Hinton, and Williams' 1986 backpropagation algorithm, the foundation of modern deep learning.

**Formulation**

```
Network: fully connected layers, sizes configurable (e.g., 2-8-8-3)

Weight initialization (Xavier):
  scale = sqrt(2 / (fan_in + fan_out))
  w[l][j][i] ~ Normal(0, scale)

Forward pass:
  a[0] = input
  for each layer l:
    z[l][j] = sum_i(w[l][j][i] * a[l-1][i]) + b[l][j]
    a[l][j] = activation(z[l][j])
  Output layer: sigmoid (binary) or softmax (multi-class)

Activation functions:
  sigmoid(x) = 1 / (1 + exp(-x));     deriv: s * (1-s)
  relu(x) = max(0, x);                deriv: 1 if x > 0 else 0
  tanh(x) = tanh(x);                  deriv: 1 - t^2

Loss functions:
  Binary:      L = 0.5 * sum(output - target)^2
  Multi-class: L = -sum(target * log(output))  (cross-entropy with softmax)

Backpropagation:
  Output deltas:
    Binary:  delta[L] = (out - target) * activation'(out)
    Softmax: delta[L] = out - target

  Hidden deltas:
    delta[l][i] = sum_j(w[l+1][j][i] * delta[l+1][j]) * activation'(a[l+1][i])

  Weight update (SGD):
    grad = delta[l][j] * a[l-1][i]
    w[l][j][i] -= learning_rate * grad

Tasks:
  XOR (4 points), Spiral (3-class, 150 points), Circle (80 points),
  Two Moons (120 points), Sine Regression (60 points), Gaussian Clusters (120 points)

Visualization: neuron activation mapped to fill characters (empty to full circle),
  weight magnitude to line thickness, gradient flow animated as pulsing arrows
```

**What to look for**

The decision boundary view reveals how the network partitions input space. For XOR, watch the 2-2-1 network learn a non-linear boundary that no single perceptron can produce. The spiral task requires deeper networks (2-8-8-3) to create the complex interleaving boundaries needed for three-class separation. The loss curve shows characteristic training dynamics: initial plateau (random weights), rapid descent (gradient catches), and potential oscillation (learning rate too high). Adjust learning rate with [ and ] to observe its effect on convergence stability.

**References**

- Rumelhart, D.E., Hinton, G.E., and Williams, R.J. "Learning representations by back-propagating errors." *Nature* 323, 1986. https://doi.org/10.1038/323533a0
- Goodfellow, I., Bengio, Y., and Courville, A. *Deep Learning.* MIT Press, 2016. https://www.deeplearningbook.org/

---

## Quantum Circuit Simulator

**Background**

This mode simulates quantum circuits using full state-vector simulation, applying unitary gate operations to a 2^n-dimensional complex amplitude vector. Six preset circuits demonstrate fundamental quantum computing concepts: Bell state entanglement, GHZ states, quantum teleportation, the Deutsch-Jozsa algorithm, Grover's search, and the Quantum Fourier Transform. Qubit states are visualized as mini Bloch sphere projections, and repeated measurement builds probability histograms.

**Formulation**

```
State vector: |psi> = sum_{i=0}^{2^n - 1} alpha_i |i>
  where alpha_i are complex amplitudes, sum |alpha_i|^2 = 1
  Initial state: |00...0> (alpha_0 = 1, all others 0)

Gate operations (applied to state vector):

  Hadamard H on qubit q:
    |0> -> (|0> + |1>) / sqrt(2)
    |1> -> (|0> - |1>) / sqrt(2)

  Pauli-X (NOT):  |0> <-> |1>
  Pauli-Z:        |1> -> -|1>
  S gate:         |1> -> i|1>
  T gate:         |1> -> e^(i*pi/4)|1>

  CNOT (controlled-X): flips target if control is |1>
  CZ (controlled-Z):   applies Z to target if control is |1>
  CP (controlled-phase): |11> -> e^(i*theta)|11>
  SWAP:                  |01> <-> |10>

  Measurement on qubit q:
    P(outcome=1) = sum |alpha_i|^2 for all i where bit q is 1
    Collapse: zero out non-matching amplitudes, renormalize

Bloch sphere projection for qubit q:
  Compute reduced amplitudes (alpha_0, alpha_1) by tracing over other qubits
  theta = 2 * acos(|alpha_0|)
  phi = phase(alpha_1) - phase(alpha_0)
  Display: project (sin(theta)*cos(phi), cos(theta)) onto 2D circle

Entanglement detection:
  purity = p0^2 + p1^2 where p0, p1 are reduced state probabilities
  if purity < 0.99: qubit is entangled (mixed reduced state)

Histogram: run circuit N times (100 or 1000 shots), sample from output distribution
```

**What to look for**

The Bell State circuit produces exactly two outcomes (|00> and |11>) with 50% probability each, while individual qubit measurements are completely random -- the hallmark of entanglement. In Grover's Search, watch the amplitude of the marked state |11> amplify from 25% to nearly 100% after one iteration of the oracle + diffusion operator. The Quantum Fourier Transform produces a uniform superposition of all basis states when applied to |100> (the binary representation of 4). The Bloch sphere projections show qubit states moving from the north pole (|0>) through the equator (superposition) during Hadamard gates.

**References**

- Nielsen, M.A. and Chuang, I.L. *Quantum Computation and Quantum Information.* Cambridge University Press, 2000. https://doi.org/10.1017/CBO9780511976667
- Mermin, N.D. *Quantum Computer Science: An Introduction.* Cambridge University Press, 2007. https://doi.org/10.1017/CBO9780511813870

---

## Tierra Digital Organisms

**Background**

Tierra, created by ecologist Thomas Ray in 1990, is a landmark artificial life system where self-replicating machine-code programs compete for memory and CPU time in a shared "primordial soup." Programs mutate during replication, leading to the spontaneous emergence of parasites (programs that exploit others' copy routines), immunity, and hyper-parasites. This implementation faithfully reproduces the Tierran instruction set, virtual machine, and reaper queue in a terminal-based visualization.

**Formulation**

```
Memory: circular array of size M (3072-6144), each cell holds one opcode (0-15)
Instruction set (16 opcodes):
  NOP0(0), NOP1(1): template markers for addressing
  FIND(2):   search forward for complement of following template
  MOV_H(3):  move head to found address
  COPY(4):   copy instruction from read-head to write-head
  INC(5), DEC(6): increment/decrement register
  JMP(7):    jump to template complement
  JMPZ(8):   jump if register zero
  ALLOC(9):  allocate daughter cell (request contiguous free block)
  SPLIT(10): divide — daughter becomes independent organism
  PUSH(11), POP(12): stack operations
  SWAP(13), CALL(14), RET(15): register/subroutine operations

Ancestor genome (~36 instructions): minimal self-copier
  1. Find own start template (1111)
  2. Allocate daughter space (ALLOC)
  3. Find end template, set copy limit
  4. Copy loop: COPY, INC read, INC write, DEC counter, JMPZ exit, JMP loop
  5. SPLIT to create independent daughter
  6. JMP back to start

Mutation:
  Copy mutation: during COPY, each instruction has probability P_mut of being
    replaced by random opcode (0.002 to 0.015 depending on preset)
  Cosmic rays: per step, P_cosmic * mem_size random memory cells are overwritten

Reaper queue (population control, when max_organisms reached):
  "oldest":       kill organism with highest age
  "large_first":  kill organism with largest genome
  "errors_first": kill organism with most execution errors

Species identification: hash(genome) = sum(op_i * 31^i) mod 2^32

Presets:
  Genesis:        mutation=0.002, cosmic=0.0001, reaper=oldest
  Cambrian Burst: mutation=0.015, cosmic=0.001,  reaper=oldest
  Arms Race:      mutation=0.005, cosmic=0.0005, reaper=large_first
  Parasite World: mutation=0.010, cosmic=0.0005, reaper=oldest (small ancestor)
  Symbiosis Lab:  mutation=0.005, cosmic=0.0003, reaper=errors_first (dual ancestors)
```

**What to look for**

In the memory view, watch colored blocks expand as organisms replicate and fill free space (shown as dim dots). Species diversity (shown in stats view) typically follows a pattern: initial monoculture, then diversification as mutations accumulate, then possible mass extinction events when a successful parasite emerges. The Parasite World preset with its small ancestor and high mutation rate produces parasites rapidly -- these are short programs that lack their own copy loop but hijack a host's COPY instruction. The Arms Race preset with large-first reaping creates evolutionary pressure toward genome compaction. The phylogenetic view shows genome-length distributions, revealing whether evolution is driving toward shorter (parasitic) or longer (complex) programs.

**References**

- Ray, T.S. "An Approach to the Synthesis of Life." *Artificial Life II,* Addison-Wesley, 1991. https://doi.org/10.7551/mitpress/1428.003.0010
- Adami, C. *Introduction to Artificial Life.* Springer, 1998. https://doi.org/10.1007/978-1-4612-1650-6

---

## Living Labyrinth

**Background**

The Living Labyrinth is a playable roguelike where the dungeon itself is a cellular automaton. Unlike all other modes in this project where the user observes a simulation, here the user is a *participant* -- an agent (`@`) navigating through a maze whose walls grow and decay by CA rules. The concept merges two traditions: roguelike dungeon crawlers (Rogue, 1980; Brogue, 2009) where procedural generation creates each run's unique challenge, and cellular automata as generative systems for dynamic environments. The result is a game where the dungeon is alive and the optimal path changes every turn.

**Formulation**

```
Maze generation (recursive backtracker + opening):
  1. Generate perfect maze on odd-dimensioned grid via DFS
  2. For each internal wall cell adjacent to 2+ floor cells:
     open with probability 0.3 (creates loops for CA to exploit)

CA evolution (Moore neighborhood, toroidal boundary):
  For each cell (r, c) not frozen:
    count = number of alive Moore neighbors (8-connected)
    if alive:  survive if count in S, else die
    if dead:   birth if count in B, else stay dead
  Wall age tracks generations survived (used for rendering)

8 rule presets:
  Maze:       B3/S12345    — stable corridors, slow drift
  Coral:      B3/S45678    — crystalline growth, stable clusters
  Anneal:     B4678/S35678 — smoothing, fills gaps gradually
  Day&Night:  B3678/S34678 — symmetric rule, balanced growth/decay
  Stains:     B3678/S235678— spreading blobs, moderate hostility
  Diamoeba:   B35678/S5678 — amoeboid masses, unpredictable
  Slow Decay: B3/S238      — structures erode slowly over time
  Life:       B3/S23       — classic Conway, chaotic and fast

Items (radius-based effects):
  Freeze:  set frozen_mask[r][c] = 10 for cells within radius 5
           (frozen cells skip CA update for 10 turns)
  Reverse: restore cells within radius 6 to state from 5 turns ago
           (uses circular history buffer of depth 10)
  Mutate:  for cells within radius 7, flip alive<->dead with P=0.4
           (creates openings through walls, or new obstacles)

Scoring:
  Level complete: speed_bonus + level_bonus
  speed_bonus = max(0, 500 - 2 * turns_taken)
  level_bonus = level_number * 100
  Rules auto-cycle every 3 levels for gameplay variety
```

**What to look for**

Each rule preset creates fundamentally different gameplay. The Maze rule (B3/S12345) preserves most corridor structure with slow drift, making it the easiest starting point. Anneal (B4678/S35678) gradually fills open spaces, creating a slowly tightening challenge. Day & Night is symmetric and creates large stable regions interspersed with chaotic borders. Life (B3/S23) is the most hostile -- structures dissipate rapidly, and the dungeon can become nearly impassable within a few turns. Watch wall age rendering: newly grown walls appear as light stipple (`░░`) while old walls become solid blocks (`██`), giving visual feedback about which walls are ephemeral versus structural. Items create dramatic local effects -- a well-timed Freeze locks a safe corridor, while Mutate can blast through a sealed passage at the cost of unpredictable side effects. The tension between CA evolution speed (adjustable with +/-) and player movement creates the core strategic challenge.

**References**

- Toy, M. et al. *Rogue.* UC Berkeley, 1980. (Original roguelike establishing the genre) https://en.wikipedia.org/wiki/Rogue_(video_game)
- Walker, B. *Brogue.* 2009-2020. (Modern roguelike with procedural dungeon generation and emergent systems) https://sites.google.com/site/broguegame/
- Wolfram, S. *A New Kind of Science.* Wolfram Media, 2002. (Comprehensive survey of CA behavior classes) https://www.wolframscience.com/nks/
