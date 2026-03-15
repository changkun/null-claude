"""Simulation modes package — each mode is a separate module."""

def register_all_modes(App):
    """Register all mode methods on the App class."""
    from life.modes.aco import register as reg_aco
    reg_aco(App)
    from life.modes.artificial_life import register as reg_alife
    reg_alife(App)
    from life.modes.ant import register as reg_ant
    reg_ant(App)
    from life.modes.ant_farm import register as reg_antfarm
    reg_antfarm(App)
    from life.modes.aquarium import register as reg_aquarium
    reg_aquarium(App)
    from life.modes.strange_attractors import register as reg_attractor
    reg_attractor(App)
    from life.modes.aurora import register as reg_aurora
    reg_aurora(App)
    from life.modes.black_hole import register as reg_blackhole
    reg_blackhole(App)
    from life.modes.blueprint import register as reg_blueprint
    reg_blueprint(App)
    from life.modes.boids import register as reg_boids
    reg_boids(App)
    from life.modes.bz_reaction import register as reg_bz
    reg_bz(App)
    from life.modes.chemotaxis import register as reg_chemo
    reg_chemo(App)
    from life.modes.chladni import register as reg_chladni
    reg_chladni(App)
    from life.modes.cloth import register as reg_cloth
    reg_cloth(App)
    from life.modes.particle_collider import register as reg_collider
    reg_collider(App)
    from life.modes.compare_rules import register as reg_compare
    reg_compare(App)
    from life.modes.cellular_potts import register as reg_cpm
    reg_cpm(App)
    from life.modes.cyclic_ca import register as reg_cyclic
    reg_cyclic(App)
    from life.modes.dla import register as reg_dla
    reg_dla(App)
    from life.modes.dna_helix import register as reg_dnahelix
    reg_dnahelix(App)
    from life.modes.doom_raycaster import register as reg_doomrc
    reg_doomrc(App)
    from life.modes.double_pendulum import register as reg_dpend
    reg_dpend(App)
    from life.modes.erosion import register as reg_erosion
    reg_erosion(App)
    from life.modes.evolution import register as reg_evo
    reg_evo(App)
    from life.modes.evo_playground import register as reg_ep
    reg_ep(App)
    from life.modes.fdtd import register as reg_fdtd
    reg_fdtd(App)
    from life.modes.forest_fire import register as reg_fire
    reg_fire(App)
    from life.modes.fireworks import register as reg_fireworks
    reg_fireworks(App)
    from life.modes.fluid_lbm import register as reg_fluid
    reg_fluid(App)
    from life.modes.fluid_rope import register as reg_fluidrope
    reg_fluidrope(App)
    from life.modes.flythrough_3d import register as reg_flythrough
    reg_flythrough(App)
    from life.modes.fourier_epicycle import register as reg_fourier
    reg_fourier(App)
    from life.modes.fractal_explorer import register as reg_fractal
    reg_fractal(App)
    from life.modes.galaxy import register as reg_galaxy
    reg_galaxy(App)
    from life.modes.game_of_life_3d import register as reg_gol3d
    reg_gol3d(App)
    from life.modes.hex_grid import register as reg_hex
    reg_hex(App)
    from life.modes.hodgepodge import register as reg_hodge
    reg_hodge(App)
    from life.modes.ifs_fractals import register as reg_ifs
    reg_ifs(App)
    from life.modes.ising import register as reg_ising
    reg_ising(App)
    from life.modes.isometric import register as reg_iso
    reg_iso(App)
    from life.modes.kaleidoscope import register as reg_kaleido
    reg_kaleido(App)
    from life.modes.kuramoto import register as reg_kuramoto
    reg_kuramoto(App)
    from life.modes.lenia import register as reg_lenia
    reg_lenia(App)
    from life.modes.lightning import register as reg_lightning
    reg_lightning(App)
    from life.modes.lissajous import register as reg_lissajous
    reg_lissajous(App)
    from life.modes.lsystem import register as reg_lsystem
    reg_lsystem(App)
    from life.modes.lotka_volterra import register as reg_lv
    reg_lv(App)
    from life.modes.magnetic_field import register as reg_magfield
    reg_magfield(App)
    from life.modes.matrix_rain import register as reg_matrix
    reg_matrix(App)
    from life.modes.maze import register as reg_maze
    reg_maze(App)
    from life.modes.maze_solver import register as reg_mazesolver
    reg_mazesolver(App)
    from life.modes.mhd_plasma import register as reg_mhd
    reg_mhd(App)
    from life.modes.multiplayer_mode import register as reg_mp
    reg_mp(App)
    from life.modes.music_visualizer import register as reg_musvis
    reg_musvis(App)
    from life.modes.nbody import register as reg_nbody
    reg_nbody(App)
    from life.modes.navier_stokes import register as reg_ns
    reg_ns(App)
    from life.modes.ocean import register as reg_ocean
    reg_ocean(App)
    from life.modes.orrery import register as reg_orrery
    reg_orrery(App)
    from life.modes.physarum import register as reg_physarum
    reg_physarum(App)
    from life.modes.param_explorer import register as reg_pexplorer
    reg_pexplorer(App)
    from life.modes.particle_life import register as reg_plife
    reg_plife(App)
    from life.modes.puzzle import register as reg_puzzle
    reg_puzzle(App)
    from life.modes.pendulum_wave import register as reg_pwave
    reg_pwave(App)
    from life.modes.quantum_walk import register as reg_qwalk
    reg_qwalk(App)
    from life.modes.race_rules import register as reg_race
    reg_race(App)
    from life.modes.ray_marching import register as reg_raymarch
    reg_raymarch(App)
    from life.modes.rayleigh_benard import register as reg_rbc
    reg_rbc(App)
    from life.modes.reaction_diffusion import register as reg_rd
    reg_rd(App)
    from life.modes.rock_paper_scissors import register as reg_rps
    reg_rps(App)
    from life.modes.falling_sand import register as reg_sand
    reg_sand(App)
    from life.modes.sandpile import register as reg_sandpile
    reg_sandpile(App)
    from life.modes.schelling import register as reg_schelling
    reg_schelling(App)
    from life.modes.screensaver import register as reg_screensaver
    reg_screensaver(App)
    from life.modes.shader_toy import register as reg_shadertoy
    reg_shadertoy(App)
    from life.modes.sir_epidemic import register as reg_sir
    reg_sir(App)
    from life.modes.smoke_fire import register as reg_smokefire
    reg_smokefire(App)
    from life.modes.spiking_neural import register as reg_snn
    reg_snn(App)
    from life.modes.snowfall import register as reg_snowfall
    reg_snowfall(App)
    from life.modes.snowflake import register as reg_snowflake
    reg_snowflake(App)
    from life.modes.sorting_visualizer import register as reg_sortvis
    reg_sortvis(App)
    from life.modes.prisoners_dilemma import register as reg_spd
    reg_spd(App)
    from life.modes.sph_fluid import register as reg_sph
    reg_sph(App)
    from life.modes.tectonic import register as reg_tectonic
    reg_tectonic(App)
    from life.modes.terrain import register as reg_terrain
    reg_terrain(App)
    from life.modes.tornado import register as reg_tornado
    reg_tornado(App)
    from life.modes.traffic import register as reg_traffic
    reg_traffic(App)
    from life.modes.turmites import register as reg_turmite
    reg_turmite(App)
    from life.modes.volcano import register as reg_volcano
    reg_volcano(App)
    from life.modes.voronoi import register as reg_voronoi
    reg_voronoi(App)
    from life.modes.wave_equation import register as reg_wave
    reg_wave(App)
    from life.modes.weather import register as reg_weather
    reg_weather(App)
    from life.modes.wave_function_collapse import register as reg_wfc
    reg_wfc(App)
    from life.modes.wolfram import register as reg_wolfram
    reg_wolfram(App)
    from life.modes.wireworld import register as reg_ww
    reg_ww(App)
    from life.dashboard import register as reg_dashboard
    reg_dashboard(App)

