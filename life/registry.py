"""Mode registry and categories for the mode browser."""

MODE_CATEGORIES = [
    "Classic CA",
    "Particle & Swarm",
    "Physics & Waves",
    "Fluid Dynamics",
    "Chemical & Biological",
    "Game Theory & Social",
    "Fractals & Chaos",
    "Procedural & Computational",
    "Complex Simulations",
    "Meta Modes",
]

MODE_REGISTRY = [
    # ── Classic CA ──
    {"name": "Game of Life", "key": "—", "category": "Classic CA",
     "desc": "Conway's classic cellular automaton", "attr": None, "enter": None, "exit": None},
    {"name": "Wolfram 1D Automaton", "key": "1", "category": "Classic CA",
     "desc": "Elementary CA rules 0-255", "attr": "wolfram_mode", "enter": "_enter_wolfram_mode", "exit": "_exit_wolfram_mode"},
    {"name": "Langton's Ant", "key": "2", "category": "Classic CA",
     "desc": "Turmite that creates emergent highways", "attr": "ant_mode", "enter": "_enter_ant_mode", "exit": "_exit_ant_mode"},
    {"name": "Hexagonal Grid", "key": "3", "category": "Classic CA",
     "desc": "6-neighbor Conway variant on hex grid", "attr": "hex_mode", "enter": "_enter_hex_browser", "exit": "_exit_hex_browser"},
    {"name": "Wireworld", "key": "4", "category": "Classic CA",
     "desc": "Circuit simulation with electron heads/tails", "attr": "ww_mode", "enter": "_enter_ww_mode", "exit": "_exit_ww_mode"},
    {"name": "Cyclic CA", "key": "U", "category": "Classic CA",
     "desc": "Cyclic cellular automaton with N states", "attr": "cyclic_mode", "enter": "_enter_cyclic_mode", "exit": "_exit_cyclic_mode"},
    {"name": "Hodgepodge Machine", "key": "~", "category": "Classic CA",
     "desc": "BZ-like excitable medium automaton", "attr": "hodge_mode", "enter": "_enter_hodge_mode", "exit": "_exit_hodge_mode"},
    {"name": "Lenia", "key": "7", "category": "Classic CA",
     "desc": "Continuous cellular automaton with smooth kernels", "attr": "lenia_mode", "enter": "_enter_lenia_mode", "exit": "_exit_lenia_mode"},
    {"name": "Turmites", "key": "Q", "category": "Classic CA",
     "desc": "2D Turing machines with colored states", "attr": "turmite_mode", "enter": "_enter_turmite_mode", "exit": "_exit_turmite_mode"},
    {"name": "3D Game of Life", "key": "Ctrl+Shift+L", "category": "Classic CA",
     "desc": "Volumetric 3D cellular automaton with ASCII ray casting", "attr": "gol3d_mode", "enter": "_enter_gol3d_mode", "exit": "_exit_gol3d_mode"},
    # ── Particle & Swarm ──
    {"name": "Falling Sand", "key": "5", "category": "Particle & Swarm",
     "desc": "Particle physics sandbox with sand/water/fire", "attr": "sand_mode", "enter": "_enter_sand_mode", "exit": "_exit_sand_mode"},
    {"name": "Boids Flocking", "key": "9", "category": "Particle & Swarm",
     "desc": "Flocking simulation with separation/alignment/cohesion", "attr": "boids_mode", "enter": "_enter_boids_mode", "exit": "_exit_boids_mode"},
    {"name": "Particle Life", "key": "0", "category": "Particle & Swarm",
     "desc": "Attraction-based colored particle system", "attr": "plife_mode", "enter": "_enter_plife_mode", "exit": "_exit_plife_mode"},
    {"name": "Physarum Slime Mold", "key": "8", "category": "Particle & Swarm",
     "desc": "Agent-based slime mold network formation", "attr": "physarum_mode", "enter": "_enter_physarum_mode", "exit": "_exit_physarum_mode"},
    {"name": "Ant Colony Optimization", "key": "A", "category": "Particle & Swarm",
     "desc": "Swarm pathfinding with pheromone trails", "attr": "aco_mode", "enter": "_enter_aco_mode", "exit": "_exit_aco_mode"},
    {"name": "N-Body Gravity", "key": "Y", "category": "Particle & Swarm",
     "desc": "Gravitational orbital mechanics simulation", "attr": "nbody_mode", "enter": "_enter_nbody_mode", "exit": "_exit_nbody_mode"},
    {"name": "Diffusion-Limited Aggregation", "key": "D", "category": "Particle & Swarm",
     "desc": "Crystal growth via random particle sticking", "attr": "dla_mode", "enter": "_enter_dla_mode", "exit": "_exit_dla_mode"},
    # ── Physics & Waves ──
    {"name": "Wave Equation", "key": "!", "category": "Physics & Waves",
     "desc": "2D wave propagation and interference", "attr": "wave_mode", "enter": "_enter_wave_mode", "exit": "_exit_wave_mode"},
    {"name": "Ising Model", "key": "#", "category": "Physics & Waves",
     "desc": "Magnetic spin system with temperature", "attr": "ising_mode", "enter": "_enter_ising_mode", "exit": "_exit_ising_mode"},
    {"name": "Kuramoto Oscillators", "key": "(", "category": "Physics & Waves",
     "desc": "Coupled phase oscillator synchronization", "attr": "kuramoto_mode", "enter": "_enter_kuramoto_mode", "exit": "_exit_kuramoto_mode"},
    {"name": "Quantum Walk", "key": "^", "category": "Physics & Waves",
     "desc": "Quantum interference on a lattice", "attr": "qwalk_mode", "enter": "_enter_qwalk_mode", "exit": "_exit_qwalk_mode"},
    {"name": "Lightning", "key": "—", "category": "Physics & Waves",
     "desc": "Dielectric breakdown lightning bolt patterns", "attr": "lightning_mode", "enter": "_enter_lightning_mode", "exit": "_exit_lightning_mode"},
    {"name": "Chladni Plate Vibrations", "key": "Ctrl+L", "category": "Physics & Waves",
     "desc": "Acoustic vibration nodal patterns", "attr": "chladni_mode", "enter": "_enter_chladni_mode", "exit": "_exit_chladni_mode"},
    {"name": "Magnetic Field Lines", "key": "Ctrl+N", "category": "Physics & Waves",
     "desc": "Dipole magnetic field visualization", "attr": "magfield_mode", "enter": "_enter_magfield_mode", "exit": "_exit_magfield_mode"},
    {"name": "FDTD Electromagnetic Waves", "key": "Ctrl+E", "category": "Physics & Waves",
     "desc": "Finite-difference time-domain EM propagation", "attr": "fdtd_mode", "enter": "_enter_fdtd_mode", "exit": "_exit_fdtd_mode"},
    {"name": "Double Pendulum", "key": "Ctrl+P", "category": "Physics & Waves",
     "desc": "Chaotic double pendulum phase traces", "attr": "dpend_mode", "enter": "_enter_dpend_mode", "exit": "_exit_dpend_mode"},
    {"name": "Cloth Simulation", "key": "'", "category": "Physics & Waves",
     "desc": "Spring-mass cloth with gravity and wind", "attr": "cloth_mode", "enter": "_enter_cloth_mode", "exit": "_exit_cloth_mode"},
    # ── Fluid Dynamics ──
    {"name": "Lattice Boltzmann Fluid", "key": "F", "category": "Fluid Dynamics",
     "desc": "Fluid flow simulation via lattice Boltzmann method", "attr": "fluid_mode", "enter": "_enter_fluid_mode", "exit": "_exit_fluid_mode"},
    {"name": "Navier-Stokes", "key": "Ctrl+D", "category": "Fluid Dynamics",
     "desc": "Incompressible fluid dye advection", "attr": "ns_mode", "enter": "_enter_ns_mode", "exit": "_exit_ns_mode"},
    {"name": "Rayleigh-Benard Convection", "key": "Ctrl+R", "category": "Fluid Dynamics",
     "desc": "Thermal convection rolls and plumes", "attr": "rbc_mode", "enter": "_enter_rbc_mode", "exit": "_exit_rbc_mode"},
    {"name": "SPH Fluid", "key": "Ctrl+A", "category": "Fluid Dynamics",
     "desc": "Smoothed particle hydrodynamics simulation", "attr": "sph_mode", "enter": "_enter_sph_mode", "exit": "_exit_sph_mode"},
    {"name": "MHD Plasma", "key": "}", "category": "Fluid Dynamics",
     "desc": "Magnetohydrodynamic plasma turbulence", "attr": "mhd_mode", "enter": "_enter_mhd_mode", "exit": "_exit_mhd_mode"},
    # ── Chemical & Biological ──
    {"name": "Reaction-Diffusion Textures", "key": "6", "category": "Chemical & Biological",
     "desc": "Gray-Scott texture generator: coral, mitosis, fingerprints, worms & more", "attr": "rd_mode", "enter": "_enter_rd_mode", "exit": "_exit_rd_mode"},
    {"name": "BZ Reaction", "key": "`", "category": "Chemical & Biological",
     "desc": "Belousov-Zhabotinsky chemical spirals", "attr": "bz_mode", "enter": "_enter_bz_mode", "exit": "_exit_bz_mode"},
    {"name": "Chemotaxis", "key": "{", "category": "Chemical & Biological",
     "desc": "Bacterial colony formation with chemotaxis", "attr": "chemo_mode", "enter": "_enter_chemo_mode", "exit": "_exit_chemo_mode"},
    {"name": "Forest Fire", "key": "O", "category": "Chemical & Biological",
     "desc": "Fire spread with growth and lightning strikes", "attr": "fire_mode", "enter": "_enter_fire_mode", "exit": "_exit_fire_mode"},
    {"name": "SIR Epidemic", "key": "E", "category": "Chemical & Biological",
     "desc": "Disease spread model (Susceptible/Infected/Recovered)", "attr": "sir_mode", "enter": "_enter_sir_mode", "exit": "_exit_sir_mode"},
    {"name": "Lotka-Volterra", "key": "J", "category": "Chemical & Biological",
     "desc": "Predator-prey population dynamics", "attr": "lv_mode", "enter": "_enter_lv_mode", "exit": "_exit_lv_mode"},
    {"name": "Spiking Neural Network", "key": ")", "category": "Chemical & Biological",
     "desc": "Izhikevich neuron model with spike propagation", "attr": "snn_mode", "enter": "_enter_snn_mode", "exit": "_exit_snn_mode"},
    {"name": "Cellular Potts Model", "key": "Ctrl+T", "category": "Chemical & Biological",
     "desc": "Tissue/cell simulation with adhesion energy", "attr": "cpm_mode", "enter": "_enter_cpm_mode", "exit": "_exit_cpm_mode"},
    # ── Game Theory & Social ──
    {"name": "Spatial Prisoner's Dilemma", "key": "@", "category": "Game Theory & Social",
     "desc": "Cooperation vs defection on a grid", "attr": "spd_mode", "enter": "_enter_spd_mode", "exit": "_exit_spd_mode"},
    {"name": "Schelling Segregation", "key": "K", "category": "Game Theory & Social",
     "desc": "Neighborhood preference-driven segregation", "attr": "schelling_mode", "enter": "_enter_schelling_mode", "exit": "_exit_schelling_mode"},
    {"name": "Rock-Paper-Scissors", "key": "&", "category": "Game Theory & Social",
     "desc": "Cyclic dominance spatial competition", "attr": "rps_mode", "enter": "_enter_rps_mode", "exit": "_exit_rps_mode"},
    {"name": "Stock Market", "key": "S", "category": "Game Theory & Social",
     "desc": "Agent-based market with emergent bubbles & crashes", "attr": "mkt_mode", "enter": "_enter_mkt_mode", "exit": "_exit_mkt_mode"},
    # ── Fractals & Chaos ──
    {"name": "Abelian Sandpile", "key": "P", "category": "Fractals & Chaos",
     "desc": "Self-organized criticality with toppling", "attr": "sandpile_mode", "enter": "_enter_sandpile_mode", "exit": "_exit_sandpile_mode"},
    {"name": "Strange Attractors", "key": "|", "category": "Fractals & Chaos",
     "desc": "Lorenz, Rossler, and other chaotic ODEs", "attr": "attractor_mode", "enter": "_enter_attractor_mode", "exit": "_exit_attractor_mode"},
    {"name": "Fractal Explorer", "key": "Ctrl+B", "category": "Fractals & Chaos",
     "desc": "Mandelbrot and Julia set zoom explorer", "attr": "fractal_mode", "enter": "_enter_fractal_mode", "exit": "_exit_fractal_mode"},
    {"name": "Snowflake Growth", "key": "*", "category": "Fractals & Chaos",
     "desc": "Reiter crystal growth model", "attr": "snowflake_mode", "enter": "_enter_snowflake_mode", "exit": "_exit_snowflake_mode"},
    {"name": "Erosion Patterns", "key": "$", "category": "Fractals & Chaos",
     "desc": "Dielectric breakdown fractal branching", "attr": "erosion_mode", "enter": "_enter_erosion_mode", "exit": "_exit_erosion_mode"},
    {"name": "Chaos Game / IFS Fractals", "key": "Ctrl+G", "category": "Fractals & Chaos",
     "desc": "Iterated function system fractal generation", "attr": "ifs_mode", "enter": "_enter_ifs_mode", "exit": "_exit_ifs_mode"},
    {"name": "L-System Fractal Garden", "key": "/", "category": "Fractals & Chaos",
     "desc": "Botanical morphogenesis with seasons, wind, mutation & light competition", "attr": "lsystem_mode", "enter": "_enter_lsystem_mode", "exit": "_exit_lsystem_mode"},
    # ── Procedural & Computational ──
    {"name": "Wave Function Collapse", "key": "X", "category": "Procedural & Computational",
     "desc": "Constraint-based procedural tile generation", "attr": "wfc_mode", "enter": "_enter_wfc_mode", "exit": "_exit_wfc_mode"},
    {"name": "Maze Generation", "key": "L", "category": "Procedural & Computational",
     "desc": "Recursive backtracker maze with pathfinding", "attr": "maze_mode", "enter": "_enter_maze_mode", "exit": "_exit_maze_mode"},
    {"name": "Voronoi Diagram", "key": "%", "category": "Procedural & Computational",
     "desc": "Spatial partitioning with colored regions", "attr": "voronoi_mode", "enter": "_enter_voronoi_mode", "exit": "_exit_voronoi_mode"},
    {"name": "Terrain Generation", "key": ";", "category": "Procedural & Computational",
     "desc": "Procedural landscape with erosion simulation", "attr": "terrain_mode", "enter": "_enter_terrain_mode", "exit": "_exit_terrain_mode"},
    {"name": "3D Terrain Flythrough", "key": "Ctrl+Y", "category": "Procedural & Computational",
     "desc": "First-person 3D flight over procedural terrain", "attr": "flythrough_mode", "enter": "_enter_flythrough_mode", "exit": "_exit_flythrough_mode"},
    {"name": "SDF Ray Marching", "key": "Ctrl+Shift+R", "category": "Procedural & Computational",
     "desc": "Real-time 3D SDF volume rendering with ASCII shading", "attr": "raymarch_mode", "enter": "_enter_raymarch_mode", "exit": "_exit_raymarch_mode"},
    {"name": "Shader Toy", "key": "Ctrl+Shift+S", "category": "Procedural & Computational",
     "desc": "Programmable pixel shader engine with ASCII output", "attr": "shadertoy_mode", "enter": "_enter_shadertoy_mode", "exit": "_exit_shadertoy_mode"},
    # ── Audio & Visual ──
    {"name": "Music Visualizer", "key": "Ctrl+Shift+M", "category": "Audio & Visual",
     "desc": "Audio-reactive ASCII visualizer with spectrum, waveform & particles", "attr": "musvis_mode", "enter": "_enter_musvis_mode", "exit": "_exit_musvis_mode"},
    {"name": "Snowfall & Blizzard", "key": "Ctrl+Shift+B", "category": "Audio & Visual",
     "desc": "Realistic snowfall with wind dynamics, accumulation, drifting & blizzard controls", "attr": "snowfall_mode", "enter": "_enter_snowfall_mode", "exit": "_exit_snowfall_mode"},
    {"name": "Matrix Digital Rain", "key": "Ctrl+Shift+Z", "category": "Audio & Visual",
     "desc": "Iconic falling green character streams with bright heads and fading tails", "attr": "matrix_mode", "enter": "_enter_matrix_mode", "exit": "_exit_matrix_mode"},
    # ── Complex Simulations ──
    {"name": "Traffic Flow", "key": "T", "category": "Complex Simulations",
     "desc": "Nagel-Schreckenberg highway traffic model", "attr": "traffic_mode", "enter": "_enter_traffic_mode", "exit": "_exit_traffic_mode"},
    {"name": "Galaxy Formation", "key": "\"", "category": "Complex Simulations",
     "desc": "N-body spiral galaxy dynamics", "attr": "galaxy_mode", "enter": "_enter_galaxy_mode", "exit": "_exit_galaxy_mode"},
    {"name": "Smoke & Fire", "key": "\\", "category": "Complex Simulations",
     "desc": "Fluid-based smoke and fire particles", "attr": "smokefire_mode", "enter": "_enter_smokefire_mode", "exit": "_exit_smokefire_mode"},
    {"name": "Fireworks", "key": "Ctrl+F", "category": "Complex Simulations",
     "desc": "Particle explosion fireworks display", "attr": "fireworks_mode", "enter": "_enter_fireworks_mode", "exit": "_exit_fireworks_mode"},
    # ── Meta Modes ──
    {"name": "Compare Rules", "key": "V", "category": "Meta Modes",
     "desc": "Side-by-side rule comparison view", "attr": "compare_mode", "enter": "_enter_compare_mode", "exit": "_exit_compare_mode"},
    {"name": "Multi-Rule Race", "key": "Z", "category": "Meta Modes",
     "desc": "Race 2-4 rules simultaneously", "attr": "race_mode", "enter": "_enter_race_mode", "exit": "_exit_race_mode"},
    {"name": "Puzzle / Challenge", "key": "C", "category": "Meta Modes",
     "desc": "Solve cellular automata challenges", "attr": "puzzle_mode", "enter": "_enter_puzzle_mode", "exit": "_exit_puzzle_mode"},
    {"name": "Evolution / GA", "key": "—", "category": "Meta Modes",
     "desc": "Genetic algorithm rule evolution", "attr": "evo_mode", "enter": "_enter_evo_mode", "exit": "_exit_evo_mode"},
    # ── Artificial Life ──
    {"name": "Artificial Life Ecosystem", "key": "Ctrl+Shift+A", "category": "Chemical & Biological",
     "desc": "Neural-net creatures forage, flee, reproduce & evolve", "attr": "alife_mode", "enter": "_enter_alife_mode", "exit": "_exit_alife_mode"},
    # ── FPS Raycaster ──
    {"name": "Doom Raycaster", "key": "Ctrl+Shift+D", "category": "Procedural & Computational",
     "desc": "Walkable 3D maze with ASCII raycasting, WASD movement & minimap", "attr": "doomrc_mode", "enter": "_enter_doomrc_mode", "exit": "_exit_doomrc_mode"},
    # ── Tectonic Plates ──
    {"name": "Tectonic Plates", "key": "Ctrl+Shift+T", "category": "Physics & Waves",
     "desc": "Continental drift with colliding plates, mountains, rifts & volcanoes", "attr": "tectonic_mode", "enter": "_enter_tectonic_mode", "exit": "_exit_tectonic_mode"},
    # ── Atmospheric Weather ──
    {"name": "Atmospheric Weather", "key": "Ctrl+Shift+W", "category": "Fluid Dynamics",
     "desc": "Dynamic weather with pressure systems, wind, clouds, rain & fronts", "attr": "weather_mode", "enter": "_enter_weather_mode", "exit": "_exit_weather_mode"},
    # ── Ocean Currents ──
    {"name": "Ocean Currents", "key": "Ctrl+Shift+O", "category": "Fluid Dynamics",
     "desc": "Thermohaline circulation with temperature, salinity, currents & plankton blooms", "attr": "ocean_mode", "enter": "_enter_ocean_mode", "exit": "_exit_ocean_mode"},
    # ── Volcanic Eruption ──
    {"name": "Volcanic Eruption", "key": "Ctrl+Shift+V", "category": "Physics & Waves",
     "desc": "Magma pressure, eruptions, lava flows, pyroclastic currents & ash dispersion", "attr": "volcano_mode", "enter": "_enter_volcano_mode", "exit": "_exit_volcano_mode"},
    # ── Black Hole Accretion Disk ──
    {"name": "Black Hole Accretion Disk", "key": "—", "category": "Physics & Waves",
     "desc": "Accretion disk, gravitational lensing, relativistic jets & Hawking radiation", "attr": "blackhole_mode", "enter": "_enter_blackhole_mode", "exit": "_exit_blackhole_mode"},
    # ── Solar System Orrery ──
    {"name": "Solar System Orrery", "key": "Ctrl+Shift+Y", "category": "Physics & Waves",
     "desc": "Overhead solar system view with Keplerian orbits, all 8 planets & asteroid belt", "attr": "orrery_mode", "enter": "_enter_orrery_mode", "exit": "_exit_orrery_mode"},
    # ── Aurora Borealis ──
    {"name": "Aurora Borealis", "key": "Ctrl+Shift+N", "category": "Physics & Waves",
     "desc": "Northern Lights with solar wind, magnetic field lines & shimmering curtains of color", "attr": "aurora_mode", "enter": "_enter_aurora_mode", "exit": "_exit_aurora_mode"},
    # ── Pendulum Wave ──
    {"name": "Pendulum Wave", "key": "Ctrl+Shift+P", "category": "Physics & Waves",
     "desc": "Row of uncoupled pendulums with incremental lengths producing mesmerizing wave patterns", "attr": "pwave_mode", "enter": "_enter_pwave_mode", "exit": "_exit_pwave_mode"},
    # ── Tornado & Supercell Storm ──
    {"name": "Tornado & Supercell Storm", "key": "—", "category": "Physics & Waves",
     "desc": "Rotating supercell thunderstorm with tornado vortex, debris, rain curtains & lightning", "attr": "tornado_mode", "enter": "_enter_tornado_mode", "exit": "_exit_tornado_mode"},
    # ── Sorting Algorithm Visualizer ──
    {"name": "Sorting Algorithm Visualizer", "key": "Ctrl+Shift+X", "category": "Procedural & Computational",
     "desc": "Animated bar-chart visualization of classic sorting algorithms with color-coded comparisons & swaps", "attr": "sortvis_mode", "enter": "_enter_sortvis_mode", "exit": "_exit_sortvis_mode"},
    # ── DNA Helix & Genetic Algorithm ──
    {"name": "DNA Helix & Genetic Algorithm", "key": "Ctrl+Shift+G", "category": "Procedural & Computational",
     "desc": "Rotating 3D ASCII double helix with live genetic algorithm evolving bit-string organisms toward a fitness target", "attr": "dnahelix_mode", "enter": "_enter_dnahelix_mode", "exit": "_exit_dnahelix_mode"},
    # ── Fourier Epicycle Drawing ──
    {"name": "Fourier Epicycle Drawing", "key": "Ctrl+Shift+F", "category": "Procedural & Computational",
     "desc": "Draw a path, then watch spinning epicycles reconstruct it via Discrete Fourier Transform", "attr": "fourier_mode", "enter": "_enter_fourier_mode", "exit": "_exit_fourier_mode"},
    # ── Fluid Rope / Honey Coiling ──
    {"name": "Fluid Rope / Honey Coiling", "key": "Ctrl+Shift+H", "category": "Fluid Dynamics",
     "desc": "Viscous fluid pouring simulation with rope coiling, folding & buckling patterns", "attr": "fluidrope_mode", "enter": "_enter_fluidrope_mode", "exit": "_exit_fluidrope_mode"},
    # ── Lissajous Curve / Harmonograph ──
    {"name": "Lissajous Curve / Harmonograph", "key": "Ctrl+Shift+J", "category": "Fractals & Chaos",
     "desc": "Coupled pendulum oscillator tracing decaying Lissajous figures and harmonograph spirals in real-time ASCII", "attr": "lissajous_mode", "enter": "_enter_lissajous_mode", "exit": "_exit_lissajous_mode"},
    # ── Maze Solving Algorithm Visualizer ──
    {"name": "Maze Solver Visualizer", "key": "Ctrl+Shift+K", "category": "Procedural & Computational",
     "desc": "Watch BFS, DFS, A* & Wall Follower solve mazes with color-coded exploration", "attr": "mazesolver_mode", "enter": "_enter_mazesolver_mode", "exit": "_exit_mazesolver_mode"},
    # ── Ant Farm Simulation ──
    {"name": "Ant Farm Simulation", "key": "Ctrl+Shift+Q", "category": "Chemical & Biological",
     "desc": "Side-view ant colony with tunnel digging, pheromone trails, foraging & emergent architecture", "attr": "antfarm_mode", "enter": "_enter_antfarm_mode", "exit": "_exit_antfarm_mode"},
    # ── Kaleidoscope / Symmetry Pattern Generator ──
    {"name": "Kaleidoscope / Symmetry Patterns", "key": "—", "category": "Audio & Visual",
     "desc": "Mesmerizing kaleidoscopic patterns with N-fold symmetry, color cycling & interactive painting", "attr": "kaleido_mode", "enter": "_enter_kaleido_mode", "exit": "_exit_kaleido_mode"},
    # ── ASCII Aquarium / Fish Tank ──
    {"name": "ASCII Aquarium / Fish Tank", "key": "—", "category": "Audio & Visual",
     "desc": "Relaxing zen-mode fish tank with procedural fish, swaying seaweed, bubbles & caustic light", "attr": "aquarium_mode", "enter": "_enter_aquarium_mode", "exit": "_exit_aquarium_mode"},
    # ── Particle Collider / Hadron Collider ──
    {"name": "Particle Collider / Hadron Collider", "key": "—", "category": "Physics & Math",
     "desc": "CERN-inspired particle accelerator ring with collisions, decay showers, energy readouts & particle detection", "attr": "collider_mode", "enter": "_enter_collider_mode", "exit": "_exit_collider_mode"},
    # ── Screensaver / Demo Reel ──
    {"name": "Screensaver / Demo Reel", "key": "Ctrl+Shift+C", "category": "Meta Modes",
     "desc": "Auto-cycling showcase that plays through all modes with smooth transitions", "attr": "screensaver_mode", "enter": "_enter_screensaver_mode", "exit": "_exit_screensaver_mode"},
    # ── Parameter Space Explorer ──
    {"name": "Parameter Space Explorer", "key": "Ctrl+Shift+E", "category": "Meta Modes",
     "desc": "Grid of live simulations with varied parameters for visual parameter space exploration", "attr": "pexplorer_mode", "enter": "_enter_param_explorer_mode", "exit": "_exit_param_explorer_mode"},
    # ── Evolution Lab ──
    {"name": "Evolution Lab", "key": "—", "category": "Meta Modes",
     "desc": "Automated GA breeds CA rules scored by entropy, symmetry & stability — discovery engine", "attr": "elab_mode", "enter": "_enter_elab_mode", "exit": "_exit_elab_mode"},
    # ── Evolutionary Playground ──
    {"name": "Evolutionary Playground", "key": "Ctrl+Shift+I", "category": "Meta Modes",
     "desc": "Breed novel CA rules through interactive natural selection with crossover & mutation", "attr": "ep_mode", "enter": "_enter_evo_playground", "exit": "_exit_evo_playground"},
    # ── Live Rule Editor ──
    {"name": "Live Rule Editor", "key": "—", "category": "Meta Modes",
     "desc": "Type Python expressions to define custom CA rules and watch them run live", "attr": "re_mode", "enter": "_enter_rule_editor_mode", "exit": "_exit_rule_editor_mode"},
    # ── Simulation Mashup ──
    {"name": "Simulation Mashup", "key": "Ctrl+M", "category": "Meta Modes",
     "desc": "Layer two simulations on the same grid with coupling for emergent behavior", "attr": "mashup_mode", "enter": "_enter_mashup_mode", "exit": "_exit_mashup_mode"},
    # ── Battle Royale ──
    {"name": "Battle Royale", "key": "Ctrl+Shift+U", "category": "Meta Modes",
     "desc": "4 CA factions fight for territory — last faction standing wins", "attr": "br_mode", "enter": "_enter_battle_royale", "exit": "_exit_battle_royale"},
    # ── Simulation Portal ──
    {"name": "Simulation Portal", "key": "Ctrl+J", "category": "Meta Modes",
     "desc": "Spatial gateways connecting two simulations at a boundary with cross-talk", "attr": "portal_mode", "enter": "_enter_portal_mode", "exit": "_exit_portal_mode"},
    # ── Split-Screen Dual Simulation ──
    {"name": "Split-Screen Dual Simulation", "key": "—", "category": "Meta Modes",
     "desc": "Run any two simulations side-by-side with independent state and toggle-able focus", "attr": "split_mode", "enter": "_enter_split_mode", "exit": "_exit_split_mode"},
    # ── Simulation Observatory ──
    {"name": "Simulation Observatory", "key": "Ctrl+O", "category": "Meta Modes",
     "desc": "Tiled split-screen running 4-9 simulations simultaneously with synced controls", "attr": "obs_mode", "enter": "_enter_observatory_mode", "exit": "_exit_observatory_mode"},
    # ── Layer Compositing ──
    {"name": "Layer Compositing", "key": "Ctrl+K", "category": "Meta Modes",
     "desc": "Stack 2-4 simulations as transparent layers with blend modes (add, XOR, mask, multiply)", "attr": "comp_mode", "enter": "_enter_comp_mode", "exit": "_exit_comp_mode"},
    # ── Cinematic Demo Reel ──
    {"name": "Cinematic Demo Reel", "key": "—", "category": "Meta Modes",
     "desc": "Auto-playing director with crossfade transitions, camera moves & parameter sweeps", "attr": "cinem_mode", "enter": "_enter_cinematic_demo_mode", "exit": "_exit_cinematic_demo_mode"},
    # ── Topology Mode ──
    {"name": "Topology Mode", "key": "Ctrl+W", "category": "Meta Modes",
     "desc": "Cycle grid surface: plane, torus, Klein bottle, Möbius strip, projective plane", "attr": None, "enter": "_topology_cycle", "exit": None},
    # ── Visual Post-Processing Pipeline ──
    {"name": "Visual FX Pipeline", "key": "Ctrl+V", "category": "Meta Modes",
     "desc": "Composable ASCII visual effects: scanlines, bloom, trails, edge detect, color cycling, CRT", "attr": None, "enter": None, "exit": None},
    # ── Simulation Recording & Export ──
    {"name": "Recording & Export", "key": "Ctrl+X", "category": "Meta Modes",
     "desc": "Record terminal frames and export as asciinema .cast or plain-text flipbook", "attr": "cast_recording", "enter": "_cast_rec_toggle", "exit": "_cast_rec_stop"},
    # ── Simulation Scripting & Choreography ──
    {"name": "Scripting & Choreography", "key": "Ctrl+U", "category": "Meta Modes",
     "desc": "Programmable show director: timed mode transitions, parameter sweeps, effect toggles", "attr": "script_mode", "enter": "_enter_scripting_mode", "exit": "_exit_scripting_mode"},
    # ── Neural Cellular Automata ──
    {"name": "Neural Cellular Automata", "key": "—", "category": "Meta Modes",
     "desc": "Per-cell neural networks learn to grow target patterns via evolutionary strategies", "attr": "nca_mode", "enter": "_enter_nca_mode", "exit": "_exit_nca_mode"},
    # ── Timeline Branching ──
    {"name": "Timeline Branching", "key": "Ctrl+F (scrub)", "category": "Meta Modes",
     "desc": "Fork alternate timelines from any past frame and watch original vs branch evolve side-by-side", "attr": "tbranch_mode", "enter": None, "exit": "_tbranch_exit"},
    # ── Ancestor Search (Reverse-Engineering) ──
    {"name": "Ancestor Search", "key": "—", "category": "Meta Modes",
     "desc": "Reverse-engineer predecessors of any pattern; detect Garden of Eden states with no ancestor", "attr": "anc_mode", "enter": "_enter_ancestor_search", "exit": "_exit_ancestor_search"},
    # ── Hyperbolic Cellular Automata ──
    {"name": "Hyperbolic Cellular Automata", "key": "Ctrl+H", "category": "Classic CA",
     "desc": "Game of Life on hyperbolic tilings ({5,4}, {7,3}, etc.) rendered as a Poincaré disk", "attr": "hyp_mode", "enter": "_enter_hyp_mode", "exit": "_exit_hyp_mode"},
    # ── Graph-Based Cellular Automata ──
    {"name": "Graph Cellular Automata", "key": "G", "category": "Classic CA",
     "desc": "Game of Life on arbitrary network topologies: small-world, scale-free, random & more", "attr": "gca_mode", "enter": "_enter_gca_mode", "exit": "_exit_gca_mode"},
    # ── Self-Modifying Rules CA ──
    {"name": "Self-Modifying Rules CA", "key": "—", "category": "Meta Modes",
     "desc": "Each cell carries its own rule DNA that mutates, spreads & competes — rules from rules", "attr": "smr_mode", "enter": "_enter_smr_mode", "exit": "_exit_smr_mode"},
    # ── Morphogenesis ──
    {"name": "Morphogenesis", "key": "—", "category": "Chemical & Biological",
     "desc": "Embryonic development from a single cell — division, differentiation, morphogen gradients & body plans", "attr": "morpho_mode", "enter": "_enter_morpho_mode", "exit": "_exit_morpho_mode"},
    # ── Artificial Chemistry ──
    {"name": "Artificial Chemistry", "key": "—", "category": "Chemical & Biological",
     "desc": "Primordial soup of abstract molecules — spontaneous polymerization, autocatalytic cycles & self-replicator emergence", "attr": "achem_mode", "enter": "_enter_achem_mode", "exit": "_exit_achem_mode"},
    # ── Immune System ──
    {"name": "Immune System Simulation", "key": "—", "category": "Chemical & Biological",
     "desc": "Adaptive immune response — pathogens invade, innate & adaptive cells coordinate, memory forms, antigens mutate", "attr": "immune_mode", "enter": "_enter_immune_mode", "exit": "_exit_immune_mode"},
    # ── Coral Reef Ecosystem ──
    {"name": "Coral Reef Ecosystem", "key": "—", "category": "Chemical & Biological",
     "desc": "Multi-species marine ecosystem with coral growth, bleaching cascades, trophic interactions & recovery dynamics", "attr": "reef_mode", "enter": "_enter_reef_mode", "exit": "_exit_reef_mode"},
    # ── Civilization & Cultural Evolution ──
    {"name": "Civilization & Cultural Evolution", "key": "—", "category": "Game Theory & Social",
     "desc": "Tribes emerge, develop tech, trade, and compete — civilizations rise and fall with cultural diffusion", "attr": "civ_mode", "enter": "_enter_civ_mode", "exit": "_exit_civ_mode"},
    # ── Ecosystem Evolution & Speciation ──
    {"name": "Ecosystem Evolution & Speciation", "key": "—", "category": "Chemical & Biological",
     "desc": "Landscape-scale macro-evolution with speciation, phylogenetic trees, food webs & mass extinctions", "attr": "evoeco_mode", "enter": "_enter_evoeco_mode", "exit": "_exit_evoeco_mode"},
    # ── Mycelium Network / Wood Wide Web ──
    {"name": "Mycelium Network / Wood Wide Web", "key": "—", "category": "Chemical & Biological",
     "desc": "Underground fungal networks connect trees — hyphae branch, shuttle nutrients, fruit mushrooms & respond to seasons", "attr": "mycelium_mode", "enter": "_enter_mycelium_mode", "exit": "_exit_mycelium_mode"},
    # ── Neural Network Training Visualizer ──
    {"name": "Neural Network Training Visualizer", "key": "—", "category": "Procedural & Computational",
     "desc": "Watch a neural network learn XOR, spirals & more — live neurons, gradient flow, decision boundary & loss curves", "attr": "nntrain_mode", "enter": "_enter_nntrain_mode", "exit": "_exit_nntrain_mode"},
    # ── Primordial Soup / Origin of Life ──
    {"name": "Primordial Soup / Origin of Life", "key": "—", "category": "Chemical & Biological",
     "desc": "Abiogenesis — molecules polymerize, membranes self-assemble, protocells divide & compete", "attr": "psoup_mode", "enter": "_enter_psoup_mode", "exit": "_exit_psoup_mode"},
    # ── Quantum Circuit Simulator ──
    {"name": "Quantum Circuit Simulator", "key": "Ctrl+Q", "category": "Procedural & Computational",
     "desc": "Build & simulate quantum circuits with Bloch spheres, entanglement links & measurement histograms", "attr": "qcirc_mode", "enter": "_enter_qcirc_mode", "exit": "_exit_qcirc_mode"},
    # ── Electric Circuit Simulator ──
    {"name": "Electric Circuit Simulator", "key": "—", "category": "Physics & Waves",
     "desc": "Grid-based circuit builder — batteries, resistors, capacitors, inductors, LEDs & switches with real-time current flow, voltage heatmap & oscilloscope", "attr": "circuit_mode", "enter": "_enter_circuit_mode", "exit": "_exit_circuit_mode"},
    # ── Molecular Dynamics / Phase Transitions ──
    {"name": "Molecular Dynamics / Phase Transitions", "key": "—", "category": "Physics & Waves",
     "desc": "Lennard-Jones particles self-organize into crystals, melt into liquids & evaporate — real-time phase transitions", "attr": "moldyn_mode", "enter": "_enter_moldyn_mode", "exit": "_exit_moldyn_mode"},
    # ── Tierra Digital Organisms ──
    {"name": "Tierra Digital Organisms", "key": "—", "category": "Procedural & Computational",
     "desc": "Self-replicating assembly programs competing in shared memory — parasites, immunity & symbiosis evolve", "attr": "tierra_mode", "enter": "_enter_tierra_mode", "exit": "_exit_tierra_mode"},
    # ── Magnetism & Spin Glass ──
    {"name": "Magnetism & Spin Glass", "key": "—", "category": "Physics & Waves",
     "desc": "Continuous-spin lattice with frustrated bonds, domain walls, glassy freezing & phase transitions", "attr": "spinglass_mode", "enter": "_enter_spinglass_mode", "exit": "_exit_spinglass_mode"},
]


# ── Mode dispatch table ────────────────────────────────────────────────────
# Convention-based routing: given attr "foo_mode", prefix is "foo", and
# method names are derived as _handle_foo_key, _draw_foo, _foo_step, etc.
# Only non-standard names need explicit overrides.

# Attrs that are NOT routed through the dispatch table (handled explicitly):
_EXPLICIT_MODES = {
    None,               # Game of Life, Topology, Visual FX
    'cast_recording',   # toggle, not a simulation mode
    'compare_mode',     # special draw condition (grid2)
    'race_mode',        # special draw condition (race_grids)
    'puzzle_mode',      # multi-phase key dispatch
    'iso_mode',         # overlay on GoL, no menu
    'hex_mode',         # overlay on GoL, no menu
    'heatmap_mode',     # overlay on GoL, no menu
    'pattern_search_mode',  # overlay on GoL, no menu
    'blueprint_mode',   # overlay on GoL, no menu
    'mp_mode',          # multi-phase key dispatch, not in registry
    'tbranch_mode',     # special draw condition, enter=None
    'screensaver_mode', # non-standard key dispatch (requires running)
    'evo_mode',         # uses self.running not evo_running, custom step
    'script_mode',      # draw has extra overlay (_draw_script_source)
}

# Per-mode overrides for non-standard method names or behavior.
# Keys: attr value.  Values: dict of overrides.
_DISPATCH_OVERRIDES = {
    # ── Non-standard method names ──
    'anc_mode': {
        'keys': '_handle_ancestor_search_key',
        'draw': '_draw_ancestor_search',
        'menu_attr': '_anc_no_menu',  # anc handles menu internally in key handler
    },
    'split_mode': {
        'keys': '_handle_split_key',
        'menu_keys': '_handle_split_menu_key',
        'draw': '_draw_split',
        'menu_draw': '_draw_split_menu',
        'step': '_split_step',
    },
    'obs_mode': {
        'keys': '_handle_observatory_key',
        'menu_keys': '_handle_observatory_menu_key',
        'draw': '_draw_observatory',
        'menu_draw': '_draw_observatory_menu',
        'step': '_observatory_step',
    },
    'cinem_mode': {
        'keys': '_handle_cinematic_key',
        'menu_keys': '_handle_cinematic_menu_key',
        'draw': '_draw_cinematic',
        'menu_draw': '_draw_cinematic_menu',
        'step': '_cinematic_step',
    },
    'br_mode': {
        'step': '_br_do_step',
        'draw': '_draw_battle_royale',
    },
    # ── No auto-step (no running state or purely interactive) ──
    'fractal_mode': {'no_step': True},
    'qcirc_mode': {'no_step': True},
    # ── Custom running checks ──
    'elab_mode': {'running_check': '_is_elab_auto_stepping'},
    'nca_mode': {'running_check': '_is_nca_auto_stepping'},
    'nntrain_mode': {'running_check': '_is_nntrain_auto_stepping'},
    'wfc_mode': {'running_check': '_is_wfc_auto_stepping'},
    'sortvis_mode': {'running_check': '_is_sortvis_auto_stepping'},
    'mazesolver_mode': {'running_check': '_is_mazesolver_auto_stepping'},
    'dnahelix_mode': {'running_check': '_is_dnahelix_auto_stepping'},
    'anc_mode|running': {'running_check': '_is_anc_auto_stepping'},
    # ── No delay (real-time or self-timed modes) ──
    'flythrough_mode': {'use_delay': False},
    'raymarch_mode': {'use_delay': False},
    'shadertoy_mode': {'use_delay': False},
    'musvis_mode': {'use_delay': False},
    'alife_mode': {'use_delay': False},
    'doomrc_mode': {'use_delay': False},
    'tectonic_mode': {'use_delay': False},
    'weather_mode': {'use_delay': False},
    'ocean_mode': {'use_delay': False},
    'volcano_mode': {'use_delay': False},
    'blackhole_mode': {'use_delay': False},
    'orrery_mode': {'use_delay': False},
    'aurora_mode': {'use_delay': False},
    'pwave_mode': {'use_delay': False},
    'tornado_mode': {'use_delay': False},
    'sortvis_mode|delay': {'use_delay': False},
    'fourier_mode': {'use_delay': False},
    'snowfall_mode': {'use_delay': False},
    'matrix_mode': {'use_delay': False},
    'fluidrope_mode': {'use_delay': False},
    'lissajous_mode': {'use_delay': False},
    'mazesolver_mode|delay': {'use_delay': False},
    'antfarm_mode': {'use_delay': False},
    'kaleido_mode': {'use_delay': False},
    'aquarium_mode': {'use_delay': False},
    'collider_mode': {'use_delay': False},
    'dnahelix_mode|delay': {'use_delay': False},
    'ns_mode': {'use_delay': False},
    'dpend_mode': {'use_delay': False},
    'chladni_mode': {'use_delay': False},
    'ifs_mode': {'use_delay': False},
    'cpm_mode': {'use_delay': False},
    'magfield_mode': {'use_delay': False},
    'fdtd_mode': {'use_delay': False},
    'sph_mode': {'use_delay': False},
    'rbc_mode': {'use_delay': False},
}


def _build_dispatch_table():
    """Build the mode dispatch table from MODE_REGISTRY + convention overrides.

    Returns a list of dicts, each with:
        attr         - mode flag attribute (e.g. 'wolfram_mode')
        prefix       - short name (e.g. 'wolfram')
        menu_attr    - menu flag (e.g. 'wolfram_menu')
        keys         - key handler method name
        menu_keys    - menu key handler method name
        draw         - draw method name
        menu_draw    - menu draw method name
        step         - step method name
        running_attr - running flag attribute
        use_delay    - whether to sleep(SPEEDS[speed_idx]) before stepping
        no_step      - if True, no auto-step after key handling
        running_check - optional method name for custom is-running check
    """
    table = []
    seen = set()
    for entry in MODE_REGISTRY:
        attr = entry.get('attr')
        if attr is None or attr in _EXPLICIT_MODES or attr in seen:
            continue
        seen.add(attr)

        # Derive prefix: 'wolfram_mode' -> 'wolfram'
        prefix = attr.replace('_mode', '')

        # Merge all overrides for this attr (including "|" keyed extras)
        overrides = {}
        for key, val in _DISPATCH_OVERRIDES.items():
            base = key.split('|')[0]
            if base == attr:
                overrides.update(val)

        md = {
            'attr': attr,
            'prefix': prefix,
            'menu_attr': overrides.get('menu_attr', f'{prefix}_menu'),
            'keys': overrides.get('keys', f'_handle_{prefix}_key'),
            'menu_keys': overrides.get('menu_keys', f'_handle_{prefix}_menu_key'),
            'draw': overrides.get('draw', f'_draw_{prefix}'),
            'menu_draw': overrides.get('menu_draw', f'_draw_{prefix}_menu'),
            'step': overrides.get('step', f'_{prefix}_step'),
            'running_attr': overrides.get('running_attr', f'{prefix}_running'),
            'use_delay': overrides.get('use_delay', True),
            'no_step': overrides.get('no_step', False),
            'running_check': overrides.get('running_check'),
        }
        table.append(md)
    return table


MODE_DISPATCH = _build_dispatch_table()
