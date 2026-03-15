"""Main application class and entry point."""
import argparse
import collections
import copy
import curses
import hashlib
import json
import math
import os
import random
import struct
import sys
import tempfile
import time

from life.constants import (
    SAVE_DIR, BLUEPRINT_FILE, SPEEDS, SPEED_LABELS,
    CELL_CHAR, HEX_CELL, HEX_DEAD, HEX_NEIGHBORS_EVEN, HEX_NEIGHBORS_ODD,
    ZOOM_LEVELS, DENSITY_CHARS, DEAD_CHAR, SPARKLINE_CHARS,
)
from life.patterns import PATTERNS, PUZZLES
from life.rules import RULE_PRESETS, rule_string, parse_rule_string
from life.colors import (
    AGE_COLORS, _init_colors, color_for_age, color_for_mp, color_for_heat,
    _GIF_PALETTE,
)
from life.utils import (
    _load_blueprints, _save_blueprints, scan_patterns, parse_rle,
    write_gif, sparkline,
)
from life.grid import Grid
from life.sound import SoundEngine
from life.multiplayer import MultiplayerNet, MP_DEFAULT_PORT, MP_SIM_GENS
from life.registry import MODE_CATEGORIES, MODE_REGISTRY


class App:
    def __init__(self, stdscr, pattern: str | None, grid_rows: int, grid_cols: int):
        self.stdscr = stdscr
        self.grid = Grid(grid_rows, grid_cols)
        self.running = False  # auto-play
        self.speed_idx = 2  # default 2× (0.5s)
        self.view_r = 0  # viewport top-left
        self.view_c = 0
        self.zoom_level = 1  # 1=normal, 2/4/8=zoomed out
        self.cursor_r = grid_rows // 2
        self.cursor_c = grid_cols // 2
        self.show_help = False
        self.message = ""
        self.message_time = 0.0
        self.pattern_menu = False
        self.stamp_menu = False  # stamp mode: overlay pattern at cursor
        # Dashboard state (initialized later by _dashboard_init)
        self.dashboard = False
        self.dashboard_sel = 0
        self.dashboard_scroll = 0
        self.dashboard_search = ""
        self.dashboard_category_filter = None
        self.dashboard_favorites = set()
        self.dashboard_show_favorites_only = False
        self.dashboard_preview_tick = 0
        self.dashboard_last_preview_time = 0.0
        self.dashboard_tab = 0
        # Mode browser state
        self.mode_browser = False
        self.mode_browser_sel = 0  # index into flattened visible list
        self.mode_browser_scroll = 0  # scroll offset
        self.mode_browser_search = ""  # search/filter string
        self.mode_browser_filtered: list[dict] = list(MODE_REGISTRY)  # filtered list
        self.pattern_list: list[str] = []
        self.pattern_sel = 0
        self.pop_history: list[int] = []
        # Cycle detection: map state_hash -> generation when first seen
        self.state_history: dict[str, int] = {}
        self.cycle_detected = False
        # Draw mode: None, "draw" (paint alive), or "erase" (paint dead)
        self.draw_mode: str | None = None
        # History buffer for rewind (stores (grid_dict, pop_len) tuples)
        self.history: list[tuple[dict, int]] = []
        self.history_max = 500
        # Timeline scrubbing position: None = "live" (at current grid), int = index into history
        self.timeline_pos: int | None = None
        # Bookmarks: list of (generation, grid_dict, pop_len) for notable moments
        self.bookmarks: list[tuple[int, dict, int]] = []
        self.bookmark_menu = False
        self.bookmark_sel = 0
        # Rule editor state
        self.rule_menu = False
        self.rule_preset_list = sorted(RULE_PRESETS.keys())
        self.rule_sel = 0
        # Comparison mode state
        self.compare_mode = False
        self.grid2: Grid | None = None  # second grid for comparison
        self.pop_history2: list[int] = []
        self.compare_rule_menu = False  # picking rule for grid2
        self.compare_rule_sel = 0
        # Race mode state: multi-rule evolution competition
        self.race_mode = False
        self.race_grids: list[Grid] = []         # 3-4 grids with different rules
        self.race_pop_histories: list[list[int]] = []
        self.race_rule_menu = False               # picking rules for race
        self.race_rule_sel = 0
        self.race_selected_rules: list[tuple[str, set, set]] = []  # (name, birth, survival)
        self.race_start_gen = 0
        self.race_max_gens = 500                  # race duration
        self.race_finished = False
        self.race_winner: str | None = None
        # Per-grid race stats: {grid_idx: {extinction_gen, osc_period, peak_pop}}
        self.race_stats: list[dict] = []
        self.race_state_hashes: list[dict] = []   # cycle detection per grid
        # Heatmap mode: cumulative cell activity overlay
        self.heatmap_mode = False
        self.heatmap = [[0] * grid_cols for _ in range(grid_rows)]
        self.heatmap_max = 0  # track peak for normalisation
        # Pattern search mode: detect and highlight known patterns
        self.pattern_search_mode = False
        self.detected_patterns: list[dict] = []
        self._pattern_scan_gen = -1  # generation of last scan
        # Blueprint mode: interactive region selection → save as reusable pattern
        self.blueprint_mode = False
        self.blueprint_anchor: tuple[int, int] | None = None  # (r, c) of selection start
        self.blueprints: dict = _load_blueprints()  # name -> {description, cells}
        self.blueprint_menu = False
        self.blueprint_sel = 0
        # GIF recording mode
        self.recording = False
        self.recorded_frames: list[list[list[int]]] = []
        self.recording_start_gen = 0
        # 3D isometric mode
        self.iso_mode = False
        # Sound/music mode
        self.sound_engine = SoundEngine()
        # Multiplayer mode state
        self.mp_mode = False
        self.mp_net: MultiplayerNet | None = None
        self.mp_role: str | None = None  # "host" or "client"
        self.mp_phase: str = "idle"  # idle/lobby/planning/running/finished
        self.mp_player: int = 0  # 1 = host/blue, 2 = client/red
        self.mp_owner: list[list[int]] = []  # 2D grid: 0=neutral, 1=P1, 2=P2
        self.mp_scores: list[int] = [0, 0]  # [P1, P2]
        self.mp_round: int = 0
        self.mp_planning_deadline: float = 0.0
        self.mp_ready: list[bool] = [False, False]
        self.mp_sim_gens: int = MP_SIM_GENS
        self.mp_start_gen: int = 0
        self.mp_territory_bonus: list[int] = [0, 0]  # cells in opponent's half
        self.mp_state_dirty = False  # host: state changed, needs broadcast
        self.mp_host_port: int = MP_DEFAULT_PORT
        self.mp_connect_addr: str = ""
        # Puzzle / challenge mode state
        self.puzzle_mode = False
        self.puzzle_menu = False           # puzzle selection menu
        self.puzzle_sel = 0                # selected puzzle index
        self.puzzle_phase: str = "idle"    # idle/planning/running/success/fail
        self.puzzle_current: dict | None = None  # current puzzle definition
        self.puzzle_placed_cells: set = set()  # cells placed by player during planning
        self.puzzle_start_pop: int = 0     # population at start of run
        self.puzzle_sim_gen: int = 0       # generations simulated so far
        self.puzzle_peak_pop: int = 0      # peak population during simulation
        self.puzzle_initial_bbox: tuple | None = None  # (min_r, min_c, max_r, max_c) for escape_box
        self.puzzle_state_hashes: dict = {}  # hash -> gen for cycle detection
        self.puzzle_win_gen: int | None = None  # generation when win condition was met
        self.puzzle_score: int = 0         # score for current puzzle
        self.puzzle_scores: dict = {}      # puzzle_id -> best score
        # Genetic algorithm evolution mode state
        self.evo_mode = False
        self.evo_menu = False              # settings menu before starting
        self.evo_pop_size = 12             # number of rulesets in population
        self.evo_grid_gens = 200           # generations to simulate each ruleset
        self.evo_mutation_rate = 0.15      # probability of mutating each digit
        self.evo_elite_count = 4           # top N survivors that reproduce
        self.evo_generation = 0            # current GA generation
        self.evo_grids: list[Grid] = []    # one grid per individual
        self.evo_rules: list[tuple[set, set]] = []  # (birth, survival) per individual
        self.evo_fitness: list[dict] = []  # fitness details per individual
        self.evo_pop_histories: list[list[int]] = []  # population history per grid
        self.evo_sim_step = 0              # current sim step within a generation
        self.evo_phase = "idle"            # idle/simulating/scored/adopting
        self.evo_sel = 0                   # selected individual for adoption
        self.evo_menu_sel = 0              # menu cursor
        self.evo_fitness_mode = "balanced" # balanced/longevity/diversity/population
        self.evo_best_ever: dict | None = None  # best fitness seen across all gens
        self.evo_history: list[dict] = []  # summary per generation
        # Evolutionary Playground mode state
        self.ep_mode = False
        self.ep_menu = False
        self.ep_menu_sel = 0
        self.ep_mutation_rate = 0.15
        self.ep_generation = 0
        self.ep_sims: list = []
        self.ep_genomes: list = []
        self.ep_pop_histories: list = []
        self.ep_selected: set = set()
        self.ep_cursor = 0
        self.ep_sim_generation = 0
        self.ep_running = False
        self.ep_grid_rows = 3
        self.ep_grid_cols = 4
        self.ep_tile_h = 6
        self.ep_tile_w = 8
        # Wolfram 1D elementary cellular automaton mode
        self.wolfram_mode = False
        self.wolfram_rule = 30           # current rule number (0-255)
        self.wolfram_rows: list[list[int]] = []  # computed rows of 1D automaton
        self.wolfram_running = False     # auto-advance
        self.wolfram_width = 0           # width of the automaton row
        self.wolfram_menu = False        # rule selection menu
        self.wolfram_menu_sel = 0        # selected preset in menu
        self.wolfram_seed_mode = "center"  # "center" or "gol_row"
        # Langton's Ant mode
        self.ant_mode = False
        self.ant_menu = False
        self.ant_menu_sel = 0
        self.ant_running = False
        self.ant_step_count = 0
        self.ant_grid: dict[tuple[int, int], int] = {}  # (r,c) -> color state
        self.ant_ants: list[dict] = []  # list of {r, c, dir, color_idx}
        self.ant_rule = "RL"            # rule string: R=right, L=left per color
        self.ant_num_ants = 1           # number of ants
        self.ant_rows = 0
        self.ant_cols = 0
        self.ant_steps_per_frame = 1    # how many steps per display frame
        # Hexagonal grid mode
        self.hex_mode = False
        # Wireworld mode
        self.ww_mode = False
        self.ww_menu = False
        self.ww_menu_sel = 0
        self.ww_running = False
        self.ww_generation = 0
        self.ww_grid: dict[tuple[int, int], int] = {}  # (r,c) -> state (1=conductor,2=head,3=tail)
        self.ww_rows = 0
        self.ww_cols = 0
        self.ww_cursor_r = 0
        self.ww_cursor_c = 0
        self.ww_drawing = True  # start in edit/drawing mode
        self.ww_draw_state = 1  # what state to paint (1=conductor,2=head,3=tail)
        # Falling-sand particle simulation mode
        self.sand_mode = False
        self.sand_menu = False
        self.sand_menu_sel = 0
        self.sand_running = False
        self.sand_generation = 0
        self.sand_grid: dict[tuple[int, int], tuple[int, int]] = {}  # (r,c) -> (element, age)
        self.sand_rows = 0
        self.sand_cols = 0
        self.sand_cursor_r = 0
        self.sand_cursor_c = 0
        self.sand_brush = 1       # current brush element type
        self.sand_brush_size = 1  # brush radius
        # Reaction-diffusion (Gray-Scott) mode
        self.rd_mode = False
        self.rd_menu = False
        self.rd_menu_sel = 0
        self.rd_running = False
        self.rd_generation = 0
        self.rd_rows = 0
        self.rd_cols = 0
        self.rd_U: list[list[float]] = []   # chemical U concentration grid
        self.rd_V: list[list[float]] = []   # chemical V concentration grid
        self.rd_feed = 0.035       # feed rate
        self.rd_kill = 0.065       # kill rate
        self.rd_Du = 0.16          # diffusion rate of U
        self.rd_Dv = 0.08          # diffusion rate of V
        self.rd_dt = 1.0           # time step
        self.rd_steps_per_frame = 4  # simulation steps per display frame
        self.rd_preset_name = ""
        # Lenia (continuous cellular automaton) mode
        self.lenia_mode = False
        self.lenia_menu = False
        self.lenia_menu_sel = 0
        self.lenia_running = False
        self.lenia_generation = 0
        self.lenia_rows = 0
        self.lenia_cols = 0
        self.lenia_grid: list[list[float]] = []   # continuous state [0,1]
        self.lenia_kernel: list[list[float]] = []  # convolution kernel
        self.lenia_R = 13          # kernel radius
        self.lenia_mu = 0.15       # growth center
        self.lenia_sigma = 0.015   # growth width
        self.lenia_dt = 0.1        # time step
        self.lenia_steps_per_frame = 1
        self.lenia_preset_name = ""
        # Physarum (slime mold) mode
        self.physarum_mode = False
        self.physarum_menu = False
        self.physarum_menu_sel = 0
        self.physarum_running = False
        self.physarum_generation = 0
        self.physarum_rows = 0
        self.physarum_cols = 0
        self.physarum_trail: list[list[float]] = []  # chemical trail [0,1]
        self.physarum_agents: list[list[float]] = []  # [row, col, angle]
        self.physarum_num_agents = 0
        self.physarum_sensor_angle = 0.4   # radians
        self.physarum_sensor_dist = 9.0
        self.physarum_turn_speed = 0.3     # radians per step
        self.physarum_move_speed = 1.0
        self.physarum_deposit = 0.5
        self.physarum_decay = 0.02
        self.physarum_steps_per_frame = 2
        self.physarum_preset_name = ""

        # ── Boids flocking simulation state ──
        self.boids_mode = False
        self.boids_menu = False
        self.boids_menu_sel = 0
        self.boids_running = False
        self.boids_generation = 0
        self.boids_rows = 0
        self.boids_cols = 0
        self.boids_agents: list[list[float]] = []  # [row, col, vr, vc]
        self.boids_num_agents = 0
        self.boids_separation_radius = 3.0
        self.boids_alignment_radius = 8.0
        self.boids_cohesion_radius = 10.0
        self.boids_separation_weight = 1.5
        self.boids_alignment_weight = 1.0
        self.boids_cohesion_weight = 1.0
        self.boids_max_speed = 1.0
        self.boids_steps_per_frame = 1
        self.boids_preset_name = ""

        # ── Particle Life state ──
        self.plife_mode = False
        self.plife_menu = False
        self.plife_menu_sel = 0
        self.plife_running = False
        self.plife_generation = 0
        self.plife_rows = 0
        self.plife_cols = 0
        self.plife_particles: list[list[float]] = []  # [row, col, vr, vc, type]
        self.plife_num_particles = 0
        self.plife_num_types = 6
        self.plife_rules: list[list[float]] = []  # num_types x num_types attraction matrix
        self.plife_max_radius = 15.0
        self.plife_friction = 0.5
        self.plife_force_scale = 0.05
        self.plife_steps_per_frame = 1
        self.plife_preset_name = ""

        # ── N-Body Gravity simulation state ──
        self.nbody_mode = False
        self.nbody_menu = False
        self.nbody_menu_sel = 0
        self.nbody_running = False
        self.nbody_generation = 0
        self.nbody_rows = 0
        self.nbody_cols = 0
        self.nbody_bodies: list[list[float]] = []  # [row, col, vr, vc, mass]
        self.nbody_num_bodies = 0
        self.nbody_grav_const = 1.0
        self.nbody_dt = 0.05
        self.nbody_softening = 0.5
        self.nbody_steps_per_frame = 2
        self.nbody_preset_name = ""
        self.nbody_trails: dict[int, list[tuple[int, int]]] = {}  # body_id -> list of (row, col)
        self.nbody_trail_len = 30
        self.nbody_show_trails = True
        self.nbody_center_mass = True  # auto-center on center of mass

        # ── Fluid Dynamics (LBM) state ──
        self.fluid_mode = False
        self.fluid_menu = False
        self.fluid_menu_sel = 0
        self.fluid_running = False
        self.fluid_generation = 0
        self.fluid_rows = 0
        self.fluid_cols = 0
        self.fluid_f: list[list[list[float]]] = []  # distribution functions [rows][cols][9]
        self.fluid_obstacle: list[list[bool]] = []   # obstacle grid
        self.fluid_omega = 1.0          # relaxation parameter (related to viscosity)
        self.fluid_inflow_speed = 0.1   # inlet velocity
        self.fluid_steps_per_frame = 3
        self.fluid_preset_name = ""
        self.fluid_viz_mode = 0         # 0=speed, 1=vorticity, 2=density

        # ── Wave Function Collapse state ──
        self.wfc_mode = False
        self.wfc_menu = False
        self.wfc_menu_sel = 0
        self.wfc_running = False
        self.wfc_generation = 0
        self.wfc_rows = 0
        self.wfc_cols = 0
        self.wfc_grid: list[list[set[int]]] = []   # each cell is a set of possible tile indices
        self.wfc_collapsed: list[list[int]] = []     # -1 = uncollapsed, >=0 = tile index
        self.wfc_num_tiles = 0
        self.wfc_adjacency: dict[int, dict[str, set[int]]] = {}  # tile -> direction -> allowed neighbors
        self.wfc_preset_name = ""
        self.wfc_steps_per_frame = 1
        self.wfc_contradiction = False
        self.wfc_complete = False

        # ── Maze Generation & Pathfinding state ──
        self.maze_mode = False
        self.maze_menu = False
        self.maze_menu_sel = 0
        self.maze_running = False
        self.maze_generation = 0
        self.maze_rows = 0
        self.maze_cols = 0
        self.maze_grid: list[list[int]] = []        # 0=wall, 1=passage
        self.maze_gen_algo = ""                      # generation algorithm name
        self.maze_solve_algo = ""                    # solving algorithm name
        self.maze_phase = "generating"               # "generating", "solving", "done"
        self.maze_gen_stack: list[tuple[int, int]] = []   # for recursive backtracker
        self.maze_gen_edges: list[tuple[int, int, int, int]] = []  # for Prim's/Kruskal's
        self.maze_gen_visited: set[tuple[int, int]] = set()
        self.maze_gen_sets: dict[tuple[int, int], int] = {}  # for Kruskal's
        self.maze_start: tuple[int, int] = (1, 1)
        self.maze_end: tuple[int, int] = (1, 1)
        self.maze_solve_queue: list = []             # frontier for pathfinding
        self.maze_solve_visited: set[tuple[int, int]] = set()
        self.maze_solve_parent: dict[tuple[int, int], tuple[int, int]] = {}
        self.maze_solve_path: list[tuple[int, int]] = []
        self.maze_solve_done = False
        self.maze_steps_per_frame = 3
        self.maze_preset_name = ""
        self.maze_gen_steps = 0
        self.maze_solve_steps = 0

        # ── Ant Colony Optimization state ──
        self.aco_mode = False
        self.aco_menu = False
        self.aco_menu_sel = 0
        self.aco_running = False
        self.aco_generation = 0
        self.aco_rows = 0
        self.aco_cols = 0
        self.aco_pheromone: list[list[float]] = []     # pheromone grid [0,1+]
        self.aco_ants: list[list[float]] = []           # [row, col, heading, has_food]
        self.aco_nest: tuple[int, int] = (0, 0)         # nest position
        self.aco_food: list[tuple[int, int, float]] = []  # food sources [(r, c, amount)]
        self.aco_num_ants = 0
        self.aco_evaporation = 0.02
        self.aco_deposit_strength = 0.3
        self.aco_diffusion = 0.01
        self.aco_steps_per_frame = 2
        self.aco_preset_name = ""
        self.aco_food_collected = 0

        # ── Diffusion-Limited Aggregation (DLA) state ──
        self.dla_mode = False
        self.dla_menu = False
        self.dla_menu_sel = 0
        self.dla_running = False
        self.dla_generation = 0
        self.dla_rows = 0
        self.dla_cols = 0
        self.dla_grid: list[list[int]] = []       # 0=empty, >0=crystal (age when attached)
        self.dla_walkers: list[list[int]] = []     # active random walkers [(row, col), ...]
        self.dla_num_walkers = 200                 # walkers alive at any time
        self.dla_spawn_radius = 0.0                # spawn ring radius (grows with crystal)
        self.dla_max_radius = 0.0                  # furthest crystal cell from center
        self.dla_stickiness = 1.0                  # probability of sticking on contact
        self.dla_steps_per_frame = 5
        self.dla_preset_name = ""
        self.dla_crystal_count = 0
        self.dla_seeds: list[tuple[int, int]] = []  # seed positions
        self.dla_symmetry = 1                      # rotational symmetry (1=none, 6=snowflake)
        self.dla_bias_r = 0.0                      # drift bias (row direction)
        self.dla_bias_c = 0.0                      # drift bias (col direction)

        # ── Epidemic / SIR Disease Spread state ──
        self.sir_mode = False
        self.sir_menu = False
        self.sir_menu_sel = 0
        self.sir_running = False
        self.sir_generation = 0
        self.sir_rows = 0
        self.sir_cols = 0
        self.sir_grid: list[list[int]] = []          # 0=S, 1=I, 2=R, 3=dead
        self.sir_infection_timer: list[list[int]] = []  # ticks remaining for infected
        self.sir_infection_radius = 1.5
        self.sir_transmission_prob = 0.3
        self.sir_recovery_time = 20
        self.sir_mortality_rate = 0.0
        self.sir_initial_infected = 5
        self.sir_population_density = 0.6
        self.sir_steps_per_frame = 1
        self.sir_preset_name = ""
        self.sir_counts: list[tuple[int, int, int, int]] = []  # history: (S, I, R, D)
        self.sir_reinfection = False  # if True, recovered can be reinfected

        # ── Abelian Sandpile state ──
        self.sandpile_mode = False
        self.sandpile_menu = False
        self.sandpile_menu_sel = 0
        self.sandpile_running = False
        self.sandpile_generation = 0
        self.sandpile_rows = 0
        self.sandpile_cols = 0
        self.sandpile_grid: list[list[int]] = []  # grain counts per cell
        self.sandpile_steps_per_frame = 1
        self.sandpile_preset_name = ""
        self.sandpile_total_grains = 0
        self.sandpile_topples = 0            # topples in last step
        self.sandpile_drop_mode = "center"   # "center", "random", "cursor"
        self.sandpile_drop_amount = 1        # grains per drop
        self.sandpile_auto_drop = True       # drop grain each step
        self.sandpile_cursor_r = 0
        self.sandpile_cursor_c = 0

        # ── Forest Fire state ──
        self.fire_mode = False
        self.fire_menu = False
        self.fire_menu_sel = 0
        self.fire_running = False
        self.fire_generation = 0
        self.fire_rows = 0
        self.fire_cols = 0
        self.fire_grid: list[list[int]] = []  # 0=empty, 1=tree, 2=burning, 3=ash, 4=ember
        self.fire_steps_per_frame = 1
        self.fire_preset_name = ""
        self.fire_p_grow = 0.05       # probability empty -> tree
        self.fire_p_lightning = 0.001  # probability tree spontaneously ignites
        self.fire_initial_density = 0.5  # initial tree density
        self.fire_ash_decay = 0.08    # probability ash -> empty (regrowth-ready)
        self.fire_counts: list[tuple[int, int, int, int]] = []  # history: (tree, fire, ash, empty)

        # ── Cyclic Cellular Automaton state ──
        self.cyclic_mode = False
        self.cyclic_menu = False
        self.cyclic_menu_sel = 0
        self.cyclic_running = False
        self.cyclic_generation = 0
        self.cyclic_rows = 0
        self.cyclic_cols = 0
        self.cyclic_grid: list[list[int]] = []
        self.cyclic_steps_per_frame = 1
        self.cyclic_preset_name = ""
        self.cyclic_n_states = 8
        self.cyclic_threshold = 1
        self.cyclic_neighborhood = "moore"  # "moore" or "von_neumann"

        # ── Spatial Prisoner's Dilemma (Evolutionary Game Theory) state ──
        self.spd_mode = False
        self.spd_menu = False
        self.spd_menu_sel = 0
        self.spd_running = False
        self.spd_generation = 0
        self.spd_rows = 0
        self.spd_cols = 0
        # Grid cell: 0=cooperator, 1=defector
        self.spd_grid: list[list[int]] = []
        # Payoff scores from last round
        self.spd_scores: list[list[float]] = []
        self.spd_steps_per_frame = 1
        self.spd_preset_name = ""
        self.spd_temptation = 1.5        # T: temptation to defect
        self.spd_reward = 1.0            # R: reward for mutual cooperation
        self.spd_punishment = 0.0        # P: punishment for mutual defection
        self.spd_sucker = 0.0            # S: sucker's payoff
        self.spd_init_coop_frac = 0.5    # initial fraction of cooperators
        self.spd_coop_count = 0          # number of cooperators
        self.spd_defect_count = 0        # number of defectors

        # ── Schelling Segregation state ──
        self.schelling_mode = False
        self.schelling_menu = False
        self.schelling_menu_sel = 0
        self.schelling_running = False
        self.schelling_generation = 0
        self.schelling_rows = 0
        self.schelling_cols = 0
        # Grid cell: 0=empty, 1..n_groups = group id
        self.schelling_grid: list[list[int]] = []
        self.schelling_steps_per_frame = 1
        self.schelling_preset_name = ""
        self.schelling_tolerance = 0.375      # fraction of similar neighbors needed
        self.schelling_density = 0.9          # fraction of cells occupied
        self.schelling_n_groups = 2           # number of groups
        self.schelling_happy_count = 0        # number of happy agents
        self.schelling_unhappy_count = 0      # number of unhappy agents
        self.schelling_counts: list[tuple[int, int]] = []  # (happy, unhappy) history

        # ── Ising Model (magnetic spin) state ──
        self.ising_mode = False
        self.ising_menu = False
        self.ising_menu_sel = 0
        self.ising_running = False
        self.ising_generation = 0
        self.ising_rows = 0
        self.ising_cols = 0
        self.ising_grid: list[list[int]] = []   # +1 or -1 spins
        self.ising_steps_per_frame = 1
        self.ising_preset_name = ""
        self.ising_temperature = 2.27           # kT / J
        self.ising_ext_field = 0.0              # external magnetic field h/J
        self.ising_magnetization = 0.0          # <m> = mean spin
        self.ising_energy = 0.0                 # <E> per spin

        # ── Hodgepodge Machine (BZ reaction) state ──
        self.hodge_mode = False
        self.hodge_menu = False
        self.hodge_menu_sel = 0
        self.hodge_running = False
        self.hodge_generation = 0
        self.hodge_rows = 0
        self.hodge_cols = 0
        self.hodge_grid: list[list[int]] = []
        self.hodge_steps_per_frame = 1
        self.hodge_preset_name = ""
        self.hodge_n_states = 100      # number of states (0=healthy, n-1=ill)
        self.hodge_k1 = 2              # infection weight
        self.hodge_k2 = 3              # illness weight
        self.hodge_g = 28              # speed of illness progression

        # ── Turmites (2D Turing Machine) state ──
        self.turmite_mode = False
        self.turmite_menu = False
        self.turmite_menu_sel = 0
        self.turmite_running = False
        self.turmite_step_count = 0
        self.turmite_grid: dict[tuple[int, int], int] = {}  # (r,c) -> color
        self.turmite_ants: list[dict] = []  # list of {r, c, dir, state}
        self.turmite_rows = 0
        self.turmite_cols = 0
        self.turmite_steps_per_frame = 1
        self.turmite_num_colors = 2
        self.turmite_num_states = 2
        # Transition table: table[state][color] = (write_color, turn, new_state)
        # turn: 0=none, 1=right, 2=u-turn, 3=left (clockwise increments)
        self.turmite_table: list[list[tuple[int, int, int]]] = []
        self.turmite_preset_name = ""

        # ── Traffic Flow (Nagel-Schreckenberg) state ──
        self.traffic_mode = False
        self.traffic_menu = False
        self.traffic_menu_sel = 0
        self.traffic_running = False
        self.traffic_generation = 0
        self.traffic_rows = 0           # number of lanes
        self.traffic_cols = 0           # road length (cells)
        self.traffic_grid: list[list[int]] = []  # -1=empty, 0..vmax=car speed
        self.traffic_steps_per_frame = 1
        self.traffic_preset_name = ""
        self.traffic_vmax = 5           # maximum velocity
        self.traffic_p_slow = 0.3       # random slowdown probability
        self.traffic_density = 0.3      # fraction of cells with cars
        self.traffic_flow = 0.0         # average flow (cars*speed)
        self.traffic_avg_speed = 0.0    # average speed of cars

        # ── Snowflake Growth (Reiter Crystal) state ──
        self.snowflake_mode = False
        self.snowflake_menu = False
        self.snowflake_menu_sel = 0
        self.snowflake_running = False
        self.snowflake_generation = 0
        self.snowflake_rows = 0
        self.snowflake_cols = 0
        self.snowflake_frozen: list[list[bool]] = []     # True = ice crystal
        self.snowflake_vapor: list[list[float]] = []     # diffusive vapor field
        self.snowflake_steps_per_frame = 1
        self.snowflake_preset_name = ""
        self.snowflake_alpha = 0.4       # vapor deposition rate onto receptive cells
        self.snowflake_beta = 0.4        # initial background vapor density
        self.snowflake_gamma = 0.0001    # noise amplitude
        self.snowflake_mu = 0.8          # diffusion rate (0-1, higher = faster diffusion)
        self.snowflake_symmetric = True  # enforce six-fold symmetry
        self.snowflake_frozen_count = 0  # number of frozen cells

        # ── Predator-Prey (Lotka-Volterra) state ──
        self.lv_mode = False
        self.lv_menu = False
        self.lv_menu_sel = 0
        self.lv_running = False
        self.lv_generation = 0
        self.lv_rows = 0
        self.lv_cols = 0
        # Grid cell: 0=grass, 1=prey, 2=predator, -1=empty
        self.lv_grid: list[list[int]] = []
        # Energy grid for prey and predators
        self.lv_energy: list[list[int]] = []
        self.lv_steps_per_frame = 1
        self.lv_preset_name = ""
        # Parameters
        self.lv_grass_regrow = 5          # steps for grass to regrow
        self.lv_prey_gain = 4             # energy gained by prey eating grass
        self.lv_pred_gain = 8             # energy gained by predator eating prey
        self.lv_prey_breed = 6            # energy threshold for prey reproduction
        self.lv_pred_breed = 10           # energy threshold for predator reproduction
        self.lv_prey_initial_energy = 4   # initial energy for prey
        self.lv_pred_initial_energy = 8   # initial energy for predators
        # Grass regrowth timer grid
        self.lv_grass_timer: list[list[int]] = []
        # Population history for chart
        self.lv_counts: list[tuple[int, int, int]] = []  # (grass, prey, pred)

        # ── Lightning / Dielectric Breakdown state ──
        self.lightning_mode = False
        self.lightning_menu = False
        self.lightning_menu_sel = 0
        self.lightning_running = False
        self.lightning_generation = 0
        self.lightning_rows = 0
        self.lightning_cols = 0
        self.lightning_grid: list[list[int]] = []       # 0=empty, 1=discharge channel
        self.lightning_potential: list[list[float]] = [] # electric potential field
        self.lightning_steps_per_frame = 1
        self.lightning_preset_name = ""
        self.lightning_eta = 2.0           # field exponent (controls branching)
        self.lightning_source = "top"      # source position: top, center, point
        self.lightning_channel_count = 0   # number of discharge cells
        self.lightning_age: list[list[int]] = []  # step when cell became channel

        # ── Hydraulic Erosion state ──
        self.erosion_mode = False
        self.erosion_menu = False
        self.erosion_menu_sel = 0
        self.erosion_running = False
        self.erosion_generation = 0
        self.erosion_rows = 0
        self.erosion_cols = 0
        self.erosion_terrain: list[list[float]] = []    # height map [0,1]
        self.erosion_water: list[list[float]] = []      # water depth
        self.erosion_sediment: list[list[float]] = []   # suspended sediment
        self.erosion_steps_per_frame = 3
        self.erosion_preset_name = ""
        self.erosion_rain_rate = 0.01       # rainfall per step
        self.erosion_evap_rate = 0.005      # evaporation per step
        self.erosion_solubility = 0.01      # erosion rate constant
        self.erosion_deposition = 0.02      # deposition rate constant
        self.erosion_total_eroded = 0.0     # cumulative erosion amount

        # ── Voronoi Crystal Growth state ──
        self.voronoi_mode = False
        self.voronoi_menu = False
        self.voronoi_menu_sel = 0
        self.voronoi_running = False
        self.voronoi_generation = 0
        self.voronoi_rows = 0
        self.voronoi_cols = 0
        self.voronoi_grid: list[list[int]] = []        # grain ID per cell (-1=empty)
        self.voronoi_seeds: list[tuple[int, int]] = []  # (row, col) of each seed
        self.voronoi_angles: list[float] = []           # preferred growth angle per grain
        self.voronoi_aniso: float = 0.3                 # anisotropy strength
        self.voronoi_num_seeds: int = 30                # number of nucleation seeds
        self.voronoi_frontier: list[tuple[int, int, int]] = []  # (r, c, grain_id)
        self.voronoi_steps_per_frame = 8
        self.voronoi_preset_name = ""
        self.voronoi_grain_count = 0

        # ── Spatial Rock-Paper-Scissors state ──
        self.rps_mode = False
        self.rps_menu = False
        self.rps_menu_sel = 0
        self.rps_running = False
        self.rps_generation = 0
        self.rps_rows = 0
        self.rps_cols = 0
        self.rps_grid: list[list[int]] = []       # 0=Rock, 1=Paper, 2=Scissors
        self.rps_steps_per_frame = 1
        self.rps_preset_name = ""
        self.rps_swap_rate: float = 0.5            # fraction of cells that attempt attack
        self.rps_num_species: int = 3              # 3 for classic, 5 for extended

        # ── 2D Wave Equation state ──
        self.wave_mode = False
        self.wave_menu = False
        self.wave_menu_sel = 0
        self.wave_running = False
        self.wave_generation = 0
        self.wave_rows = 0
        self.wave_cols = 0
        self.wave_u: list[list[float]] = []          # current displacement
        self.wave_u_prev: list[list[float]] = []     # previous displacement
        self.wave_steps_per_frame = 1
        self.wave_preset_name = ""
        self.wave_c: float = 0.3                     # wave speed
        self.wave_damping: float = 0.999             # damping factor per step
        self.wave_boundary: str = "reflect"          # reflect, absorb, wrap

        # ── Kuramoto Coupled Oscillators state ──
        self.kuramoto_mode = False
        self.kuramoto_menu = False
        self.kuramoto_menu_sel = 0
        self.kuramoto_running = False
        self.kuramoto_generation = 0
        self.kuramoto_rows = 0
        self.kuramoto_cols = 0
        self.kuramoto_phases: list[list[float]] = []      # phase of each oscillator [0, 2π)
        self.kuramoto_nat_freq: list[list[float]] = []    # natural frequency of each oscillator
        self.kuramoto_coupling: float = 1.0               # coupling strength K
        self.kuramoto_dt: float = 0.1                     # time step
        self.kuramoto_steps_per_frame: int = 1
        self.kuramoto_preset_name: str = ""
        self.kuramoto_freq_spread: float = 1.0            # spread of natural frequencies
        self.kuramoto_noise: float = 0.0                   # noise intensity

        # ── Spiking Neural Network (Izhikevich) state ──
        self.snn_mode = False
        self.snn_menu = False
        self.snn_menu_sel = 0
        self.snn_running = False
        self.snn_generation = 0
        self.snn_rows = 0
        self.snn_cols = 0
        self.snn_v: list[list[float]] = []           # membrane potential
        self.snn_u: list[list[float]] = []           # recovery variable
        self.snn_fired: list[list[bool]] = []        # fired this step
        self.snn_a: list[list[float]] = []           # Izhikevich param a
        self.snn_b: list[list[float]] = []           # Izhikevich param b
        self.snn_c_param: list[list[float]] = []     # reset voltage c
        self.snn_d: list[list[float]] = []           # reset recovery d
        self.snn_is_excitatory: list[list[bool]] = []  # True=excitatory, False=inhibitory
        self.snn_weight: float = 10.0                # synaptic weight
        self.snn_noise_amp: float = 5.0              # background noise amplitude
        self.snn_steps_per_frame: int = 1
        self.snn_preset_name: str = ""
        self.snn_fire_history: list[list[list[float]]] = []  # recent fire intensity for glow effect
        self.snn_dt: float = 0.5                     # simulation time step

        # ── Belousov-Zhabotinsky (BZ) Reaction state ──
        self.bz_mode = False
        self.bz_menu = False
        self.bz_menu_sel = 0
        self.bz_running = False
        self.bz_generation = 0
        self.bz_rows = 0
        self.bz_cols = 0
        self.bz_a: list[list[float]] = []   # activator concentration
        self.bz_b: list[list[float]] = []   # inhibitor concentration
        self.bz_c: list[list[float]] = []   # recovery variable
        self.bz_alpha: float = 1.0          # activator production rate
        self.bz_beta: float = 1.0           # inhibitor coupling
        self.bz_gamma: float = 1.0          # recovery rate
        self.bz_diffusion: float = 0.2      # diffusion coefficient
        self.bz_steps_per_frame: int = 1
        self.bz_preset_name: str = ""

        # ── Chemotaxis & Bacterial Colony Growth state ──
        self.chemo_mode = False
        self.chemo_menu = False
        self.chemo_menu_sel = 0
        self.chemo_running = False
        self.chemo_generation = 0
        self.chemo_rows = 0
        self.chemo_cols = 0
        self.chemo_bacteria: list[list[float]] = []
        self.chemo_nutrient: list[list[float]] = []
        self.chemo_signal: list[list[float]] = []
        self.chemo_growth_rate: float = 0.6
        self.chemo_nutrient_diff: float = 0.05
        self.chemo_motility: float = 0.02
        self.chemo_chemotaxis: float = 0.2
        self.chemo_signal_prod: float = 0.15
        self.chemo_signal_decay: float = 0.08
        self.chemo_consumption: float = 0.4
        self.chemo_steps_per_frame: int = 1
        self.chemo_preset_name: str = ""

        # ── Magnetohydrodynamics (MHD) Plasma state ──
        self.mhd_mode = False
        self.mhd_menu = False
        self.mhd_menu_sel = 0
        self.mhd_running = False
        self.mhd_generation = 0
        self.mhd_rows = 0
        self.mhd_cols = 0
        self.mhd_rho: list[list[float]] = []       # density
        self.mhd_vx: list[list[float]] = []        # velocity x
        self.mhd_vy: list[list[float]] = []        # velocity y
        self.mhd_bx: list[list[float]] = []        # magnetic field x
        self.mhd_by: list[list[float]] = []        # magnetic field y
        self.mhd_resistivity: float = 0.01
        self.mhd_viscosity: float = 0.01
        self.mhd_pressure_coeff: float = 1.0
        self.mhd_steps_per_frame: int = 1
        self.mhd_preset_name: str = ""
        self.mhd_view: str = "current"  # current, density, magnetic, velocity

        # ── Strange Attractor state ──
        self.attractor_mode = False
        self.attractor_menu = False
        self.attractor_menu_sel = 0
        self.attractor_running = False
        self.attractor_generation = 0
        self.attractor_rows = 0
        self.attractor_cols = 0
        self.attractor_preset_name: str = ""
        self.attractor_steps_per_frame: int = 50
        self.attractor_dt: float = 0.005
        self.attractor_type: str = "lorenz"
        self.attractor_density: list[list[float]] = []
        self.attractor_trails: list[tuple[float, float, float]] = []
        self.attractor_num_particles: int = 200
        self.attractor_params: dict = {}
        self.attractor_angle_x: float = 0.3   # rotation around x-axis
        self.attractor_angle_z: float = 0.0   # rotation around z-axis
        self.attractor_zoom: float = 1.0
        self.attractor_max_density: float = 1.0

        # ── Quantum Cellular Automaton (Quantum Walk) state ──
        self.qwalk_mode = False
        self.qwalk_menu = False
        self.qwalk_menu_sel = 0
        self.qwalk_running = False
        self.qwalk_generation = 0
        self.qwalk_rows = 0
        self.qwalk_cols = 0
        self.qwalk_preset_name: str = ""
        self.qwalk_steps_per_frame: int = 1
        self.qwalk_coin: str = "hadamard"
        self.qwalk_amp_re: list[list[list[float]]] = []  # [dir][r][c] real part
        self.qwalk_amp_im: list[list[list[float]]] = []  # [dir][r][c] imag part
        self.qwalk_prob: list[list[float]] = []  # cached probability grid
        self.qwalk_max_prob: float = 1.0
        self.qwalk_view: str = "probability"  # probability, phase, real, imaginary
        self.qwalk_boundary: str = "periodic"  # periodic, absorbing
        self.qwalk_decoherence: float = 0.0  # decoherence rate

        # ── Terrain Generation & Erosion Landscape state ──
        self.terrain_mode = False
        self.terrain_menu = False
        self.terrain_menu_sel = 0
        self.terrain_running = False
        self.terrain_generation = 0
        self.terrain_rows = 0
        self.terrain_cols = 0
        self.terrain_preset_name: str = ""
        self.terrain_steps_per_frame: int = 1
        self.terrain_heightmap: list[list[float]] = []
        self.terrain_vegetation: list[list[float]] = []  # 0=bare, 1=full cover
        self.terrain_hardness: list[list[float]] = []    # rock hardness
        self.terrain_thermal_rate: float = 0.02
        self.terrain_uplift_rate: float = 0.001
        self.terrain_veg_growth: float = 0.005

        # ── 3D Terrain Flythrough state ──
        self.flythrough_mode = False
        self.flythrough_menu = False
        self.flythrough_menu_sel = 0
        self.flythrough_running = False
        self.flythrough_generation = 0
        self.flythrough_preset_name: str = ""
        # Camera state: position (x, y, z) and orientation (yaw, pitch)
        self.flythrough_cam_x: float = 0.0
        self.flythrough_cam_y: float = 0.0
        self.flythrough_cam_z: float = 0.0
        self.flythrough_cam_yaw: float = 0.0    # radians, 0 = looking along +X
        self.flythrough_cam_pitch: float = -0.3  # radians, negative = looking down
        self.flythrough_cam_speed: float = 0.5
        self.flythrough_fov: float = 1.2  # field of view in radians
        # Terrain data
        self.flythrough_map_size: int = 256
        self.flythrough_heightmap: list[list[float]] = []
        # Day/night cycle
        self.flythrough_time: float = 0.3  # 0..1, 0.25=dawn, 0.5=noon, 0.75=dusk, 0=midnight
        self.flythrough_time_speed: float = 0.002
        self.flythrough_auto_time: bool = True
        self.terrain_rain_rate: float = 0.01
        self.terrain_sea_level: float = 0.25
        self.terrain_view: str = "topo"  # topo, elevation, vegetation, erosion
        self.terrain_total_uplift: float = 0.0
        self.terrain_total_eroded: float = 0.0

        # ── SDF Ray Marching state ──
        self.raymarch_mode = False
        self.raymarch_menu = False
        self.raymarch_menu_sel = 0
        self.raymarch_running = False
        self.raymarch_generation = 0
        self.raymarch_scene: str = "sphere"
        self.raymarch_scene_name: str = ""
        self.raymarch_cam_theta: float = 0.0
        self.raymarch_cam_phi: float = 0.4
        self.raymarch_cam_dist: float = 4.0
        self.raymarch_auto_rotate: bool = True
        self.raymarch_rotate_speed: float = 0.03
        self.raymarch_light_theta: float = 0.8
        self.raymarch_light_phi: float = 0.6
        self.raymarch_shadows: bool = True
        self.raymarch_mandelbulb_power: float = 8.0

        # ── Shader Toy state ──
        self.shadertoy_mode = False
        self.shadertoy_menu = False
        self.shadertoy_menu_sel = 0
        self.shadertoy_running = False
        self.shadertoy_generation = 0
        self.shadertoy_preset_name: str = ""
        self.shadertoy_preset_idx: int = 0
        self.shadertoy_time: float = 0.0
        self.shadertoy_speed: float = 1.0
        self.shadertoy_param_a: float = 1.0
        self.shadertoy_param_b: float = 1.0
        self.shadertoy_color_mode: int = 0  # 0=rainbow, 1=fire, 2=ocean, 3=mono

        # ── Music Visualizer state ──
        self.musvis_mode = False
        self.musvis_menu = False
        self.musvis_menu_sel = 0
        self.musvis_running = False
        self.musvis_generation = 0
        self.musvis_preset_name: str = ""
        self.musvis_preset_idx: int = 0
        self.musvis_time: float = 0.0
        self.musvis_spectrum: list = []       # FFT magnitude bins
        self.musvis_waveform: list = []       # Time-domain waveform samples
        self.musvis_beat_energy: float = 0.0  # Current beat energy level
        self.musvis_beat_avg: float = 0.0     # Running average for beat detection
        self.musvis_beat_flash: float = 0.0   # Flash intensity on beat
        self.musvis_particles: list = []      # Beat-reactive particles
        self.musvis_peak_history: list = []   # History of peak values for decay
        self.musvis_bass_energy: float = 0.0
        self.musvis_mid_energy: float = 0.0
        self.musvis_high_energy: float = 0.0
        self.musvis_color_mode: int = 0       # 0=spectrum, 1=fire, 2=ocean, 3=neon
        self.musvis_view_mode: int = 0        # 0=spectrum, 1=waveform, 2=particles, 3=combined
        self.musvis_sensitivity: float = 1.0
        self.musvis_tone_freq: float = 0.0    # Current generated tone frequency
        self.musvis_tone_phase: float = 0.0   # Tone oscillator phase
        self.musvis_num_bars: int = 32        # Number of spectrum bars

        # ── 3D Game of Life state ──
        self.gol3d_mode = False
        self.gol3d_menu = False
        self.gol3d_menu_sel = 0
        self.gol3d_running = False
        self.gol3d_generation = 0
        self.gol3d_preset_name: str = ""
        self.gol3d_size: int = 20
        self.gol3d_grid: list = []
        self.gol3d_birth: set = set()
        self.gol3d_survive: set = set()
        self.gol3d_cam_theta: float = 0.5
        self.gol3d_cam_phi: float = 0.5
        self.gol3d_cam_dist: float = 2.5
        self.gol3d_auto_rotate: bool = True
        self.gol3d_rotate_speed: float = 0.02
        self.gol3d_population: int = 0
        self.gol3d_density: float = 0.15

        # Smoke & Fire simulation mode
        self.smokefire_mode = False
        self.smokefire_menu = False
        self.smokefire_menu_sel = 0
        self.smokefire_running = False
        self.smokefire_generation = 0
        self.smokefire_rows = 0
        self.smokefire_cols = 0
        self.smokefire_preset_name: str = ""
        self.smokefire_steps_per_frame: int = 1
        self.smokefire_temp: list[list[float]] = []       # temperature grid 0.0-1.0
        self.smokefire_smoke: list[list[float]] = []      # smoke density 0.0-1.0
        self.smokefire_fuel: list[list[float]] = []       # fuel amount 0.0-1.0
        self.smokefire_vx: list[list[float]] = []         # horizontal velocity
        self.smokefire_vy: list[list[float]] = []         # vertical velocity (negative=up)
        self.smokefire_sources: list[tuple[int, int, float]] = []  # (r, c, intensity)
        self.smokefire_buoyancy: float = 0.15
        self.smokefire_turbulence: float = 0.04
        self.smokefire_cooling: float = 0.015
        self.smokefire_smoke_rate: float = 0.3
        self.smokefire_wind: float = 0.0
        self.smokefire_cursor_r: int = 0
        self.smokefire_cursor_c: int = 0

        # Cloth Simulation mode
        self.cloth_mode = False
        self.cloth_menu = False
        self.cloth_menu_sel = 0
        self.cloth_running = False
        self.cloth_generation = 0
        self.cloth_rows = 0
        self.cloth_cols = 0
        self.cloth_preset_name: str = ""
        self.cloth_steps_per_frame: int = 3
        self.cloth_points: list[list[float]] = []       # [[x, y, old_x, old_y, pinned], ...]
        self.cloth_grid_w: int = 0                       # grid width (columns of points)
        self.cloth_grid_h: int = 0                       # grid height (rows of points)
        self.cloth_constraints: list[list[int | float]] = []  # [[p1_idx, p2_idx, rest_length], ...]
        self.cloth_gravity: float = 0.5
        self.cloth_wind: float = 0.0
        self.cloth_damping: float = 0.99
        self.cloth_constraint_iters: int = 5
        self.cloth_spacing: float = 1.0
        self.cloth_cursor_r: int = 0
        self.cloth_cursor_c: int = 0
        self.cloth_tear_threshold: float = 3.0

        # ── Galaxy Formation state ──
        self.galaxy_mode = False
        self.galaxy_menu = False
        self.galaxy_menu_sel = 0
        self.galaxy_running = False
        self.galaxy_generation = 0
        self.galaxy_preset_name: str = ""
        self.galaxy_steps_per_frame: int = 2
        # Particles: [x, y, vx, vy, mass, type]
        # type: 0=star, 1=gas, 2=dark_matter
        self.galaxy_particles: list[list[float]] = []
        self.galaxy_halo_mass: float = 1000.0
        self.galaxy_halo_radius: float = 30.0
        self.galaxy_rotation_speed: float = 1.0
        self.galaxy_gas_density: float = 0.5
        self.galaxy_grav_const: float = 1.0
        self.galaxy_dt: float = 0.03
        self.galaxy_softening: float = 1.0
        self.galaxy_rows: int = 0
        self.galaxy_cols: int = 0
        self.galaxy_density: list[list[float]] = []
        self.galaxy_gas_grid: list[list[float]] = []
        self.galaxy_view: str = "combined"
        self.galaxy_show_halo: bool = False
        self.galaxy_arm_count: int = 2
        self.galaxy_total_ke: float = 0.0

        # ── L-System Plant Growth state ──
        self.lsystem_mode: bool = False
        self.lsystem_menu: bool = False
        self.lsystem_menu_sel: int = 0
        self.lsystem_running: bool = False
        self.lsystem_generation: int = 0
        self.lsystem_preset_name: str = ""
        self.lsystem_axiom: str = ""
        self.lsystem_rules: dict[str, str] = {}
        self.lsystem_angle: float = 25.0
        self.lsystem_growth_rate: float = 1.0
        self.lsystem_light_dir: float = 0.0  # angle in degrees, 0=up
        self.lsystem_max_depth: int = 0
        self.lsystem_current_depth: int = 0
        self.lsystem_string: str = ""
        self.lsystem_segments: list[tuple[float, float, float, float, int]] = []  # x1,y1,x2,y2,depth
        self.lsystem_leaves: list[tuple[float, float]] = []
        self.lsystem_seeds: list[tuple[float, float]] = []
        self.lsystem_rows: int = 0
        self.lsystem_cols: int = 0
        self.lsystem_steps_per_frame: int = 1
        self.lsystem_num_plants: int = 1
        self.lsystem_plants: list[dict] = []  # list of plant state dicts

        # ── Fractal Explorer mode ──
        self.fractal_mode: bool = False
        self.fractal_menu: bool = False
        self.fractal_menu_sel: int = 0
        self.fractal_running: bool = False
        self.fractal_generation: int = 0
        self.fractal_preset_name: str = ""
        self.fractal_rows: int = 0
        self.fractal_cols: int = 0
        self.fractal_type: str = "mandelbrot"  # "mandelbrot" or "julia"
        self.fractal_center_re: float = -0.5
        self.fractal_center_im: float = 0.0
        self.fractal_zoom: float = 1.0
        self.fractal_max_iter: int = 80
        self.fractal_julia_re: float = -0.7
        self.fractal_julia_im: float = 0.27015
        self.fractal_dirty: bool = True  # needs recomputation
        self.fractal_buffer: list[list[int]] = []  # iteration counts
        self.fractal_color_scheme: int = 0  # index into color schemes
        self.fractal_smooth: bool = True

        # ── Fireworks simulation mode ──
        self.fireworks_mode: bool = False
        self.fireworks_menu: bool = False
        self.fireworks_menu_sel: int = 0
        self.fireworks_running: bool = False
        self.fireworks_generation: int = 0
        self.fireworks_preset_name: str = ""
        self.fireworks_rows: int = 0
        self.fireworks_cols: int = 0
        self.fireworks_steps_per_frame: int = 2
        self.fireworks_gravity: float = 0.06
        self.fireworks_particles: list[list] = []  # [r, c, vr, vc, life, max_life, color, kind, trail]
        self.fireworks_rockets: list[list] = []     # [r, c, vr, vc, fuse, color, pattern]
        self.fireworks_auto_launch: bool = True
        self.fireworks_launch_rate: float = 0.08    # probability per tick
        self.fireworks_wind: float = 0.0
        self.fireworks_total_launched: int = 0
        self.fireworks_total_bursts: int = 0

        # ── Navier-Stokes Fluid Dynamics mode ──
        self.ns_mode: bool = False
        self.ns_menu: bool = False
        self.ns_menu_sel: int = 0
        self.ns_running: bool = False
        self.ns_generation: int = 0
        self.ns_preset_name: str = ""
        self.ns_rows: int = 0
        self.ns_cols: int = 0
        self.ns_steps_per_frame: int = 4
        self.ns_vx: list[list[float]] = []   # velocity x
        self.ns_vy: list[list[float]] = []   # velocity y
        self.ns_vx0: list[list[float]] = []  # previous velocity x
        self.ns_vy0: list[list[float]] = []  # previous velocity y
        self.ns_p: list[list[float]] = []    # pressure
        self.ns_div: list[list[float]] = []  # divergence
        self.ns_dye: list[list[float]] = []  # dye density for visualization
        self.ns_dye0: list[list[float]] = [] # previous dye
        self.ns_viscosity: float = 0.0001
        self.ns_diffusion: float = 0.00001
        self.ns_dt: float = 0.1
        self.ns_iterations: int = 20         # pressure solver iterations
        self.ns_viz_mode: int = 0            # 0=dye, 1=velocity, 2=vorticity, 3=pressure
        self.ns_cursor_r: int = 0
        self.ns_cursor_c: int = 0
        self.ns_prev_cursor_r: int = 0
        self.ns_prev_cursor_c: int = 0
        self.ns_inject_radius: int = 3
        self.ns_inject_strength: float = 80.0
        self.ns_dye_hue: float = 0.0        # current dye hue (cycles over time)
        self.ns_obstacles: list[list[bool]] = []

        # ── Double Pendulum mode state ──
        self.dpend_mode: bool = False
        self.dpend_menu: bool = False
        self.dpend_menu_sel: int = 0
        self.dpend_running: bool = False
        self.dpend_generation: int = 0
        self.dpend_preset_name: str = ""
        self.dpend_rows: int = 0
        self.dpend_cols: int = 0
        self.dpend_steps_per_frame: int = 5
        # Pendulum 1 state: [theta1, theta2, omega1, omega2]
        self.dpend_p1: list[float] = [0.0, 0.0, 0.0, 0.0]
        # Pendulum 2 state (for comparison)
        self.dpend_p2: list[float] = [0.0, 0.0, 0.0, 0.0]
        self.dpend_m1: float = 1.0   # mass of upper bob
        self.dpend_m2: float = 1.0   # mass of lower bob
        self.dpend_l1: float = 1.0   # length of upper arm
        self.dpend_l2: float = 1.0   # length of lower arm
        self.dpend_g: float = 9.81   # gravity
        self.dpend_dt: float = 0.005 # timestep
        self.dpend_dual: bool = True # show two pendulums side-by-side
        self.dpend_trail1: list[tuple[float, float]] = []  # trajectory of pendulum 1 tip
        self.dpend_trail2: list[tuple[float, float]] = []  # trajectory of pendulum 2 tip
        self.dpend_max_trail: int = 500
        self.dpend_perturb: float = 0.001  # initial angle difference for pendulum 2

        # ── Chaos Game / IFS Fractal mode state ──
        self.ifs_mode: bool = False
        self.ifs_menu: bool = False
        self.ifs_menu_sel: int = 0
        self.ifs_running: bool = False
        self.ifs_generation: int = 0
        self.ifs_preset_name: str = ""
        self.ifs_points: list[list[int]] = []     # density field (hit counts)
        self.ifs_rows: int = 0
        self.ifs_cols: int = 0
        self.ifs_steps_per_frame: int = 200
        self.ifs_x: float = 0.0                   # current point x
        self.ifs_y: float = 0.0                   # current point y
        self.ifs_transforms: list[tuple] = []     # list of (a,b,c,d,e,f, prob)
        self.ifs_total_points: int = 0
        self.ifs_colorize: bool = True            # color by transform index
        self.ifs_last_transform: int = 0          # index of last used transform
        self.ifs_color_field: list[list[int]] = []  # last transform index per cell

        # ── Chladni Plate Vibration Patterns mode state ──
        self.chladni_mode: bool = False
        self.chladni_menu: bool = False
        self.chladni_menu_sel: int = 0
        self.chladni_running: bool = False
        self.chladni_generation: int = 0
        self.chladni_preset_name: str = ""
        self.chladni_rows: int = 0
        self.chladni_cols: int = 0
        self.chladni_steps_per_frame: int = 3
        self.chladni_plate: list[list[float]] = []    # displacement field
        self.chladni_velocity: list[list[float]] = []  # velocity field (dz/dt)
        self.chladni_sand: list[list[float]] = []     # sand density field
        self.chladni_m: int = 2                       # mode number m
        self.chladni_n: int = 3                       # mode number n
        self.chladni_freq: float = 1.0                # drive frequency
        self.chladni_damping: float = 0.02            # damping coefficient
        self.chladni_drive_amp: float = 0.5           # drive amplitude
        self.chladni_dt: float = 0.05                 # timestep
        self.chladni_c: float = 1.0                   # wave speed
        self.chladni_viz_mode: int = 0                # 0=sand, 1=displacement, 2=energy
        self.chladni_time: float = 0.0                # simulation time
        self.chladni_sand_settle_rate: float = 0.1    # how fast sand moves to nodes

        # ── Cellular Potts Model (CPM) mode state ──
        self.cpm_mode: bool = False
        self.cpm_menu: bool = False
        self.cpm_menu_sel: int = 0
        self.cpm_running: bool = False
        self.cpm_generation: int = 0
        self.cpm_preset_name: str = ""
        self.cpm_rows: int = 0
        self.cpm_cols: int = 0
        self.cpm_steps_per_frame: int = 500
        self.cpm_grid: list[list[int]] = []       # cell ID at each pixel (0=medium)
        self.cpm_num_cells: int = 0               # total number of cells
        self.cpm_temperature: float = 10.0        # Boltzmann temperature (higher=more fluctuation)
        self.cpm_lambda_area: float = 1.0         # area constraint strength
        self.cpm_target_area: list[int] = []      # target area per cell ID
        self.cpm_cell_type: list[int] = []        # type index per cell ID (0=medium)
        self.cpm_J: list[list[float]] = []        # adhesion energy matrix J[type_a][type_b]
        self.cpm_num_types: int = 2               # number of cell types (excl. medium)
        self.cpm_viz_mode: int = 0                # 0=cell type, 1=cell ID, 2=boundaries
        self.cpm_chemotaxis: bool = False          # chemotaxis enabled
        self.cpm_chem_field: list[list[float]] = []  # chemical concentration
        self.cpm_chem_lambda: float = 0.0         # chemotaxis strength
        self.cpm_chem_decay: float = 0.01         # chemical decay rate
        self.cpm_chem_source_type: int = 0        # which cell type secretes
        self.cpm_area_cache: list[int] = []       # cached area per cell ID

        # ── FDTD Electromagnetic Wave Propagation state ──
        self.fdtd_mode: bool = False
        self.fdtd_menu: bool = False
        self.fdtd_menu_sel: int = 0
        self.fdtd_running: bool = False
        self.fdtd_generation: int = 0
        self.fdtd_preset_name: str = ""
        self.fdtd_rows: int = 0
        self.fdtd_cols: int = 0
        self.fdtd_steps_per_frame: int = 2
        self.fdtd_Ez: list[list[float]] = []    # Ez field component
        self.fdtd_Hx: list[list[float]] = []    # Hx field component
        self.fdtd_Hy: list[list[float]] = []    # Hy field component
        self.fdtd_eps: list[list[float]] = []   # permittivity grid
        self.fdtd_sigma: list[list[float]] = [] # conductivity grid (for PML/barriers)
        self.fdtd_sources: list[dict] = []      # point sources [{r, c, freq, phase, amp}]
        self.fdtd_pml_width: int = 8            # PML absorbing boundary width
        self.fdtd_viz_mode: int = 0             # 0=Ez field, 1=|E| intensity, 2=H magnitude
        self.fdtd_freq: float = 0.15            # default source frequency
        self.fdtd_courant: float = 0.5          # Courant number (c*dt/dx)

        # ── Magnetic Field Lines mode state ──
        self.magfield_mode: bool = False
        self.magfield_menu: bool = False
        self.magfield_menu_sel: int = 0
        self.magfield_running: bool = False
        self.magfield_generation: int = 0
        self.magfield_preset_name: str = ""
        self.magfield_rows: int = 0
        self.magfield_cols: int = 0
        self.magfield_steps_per_frame: int = 3
        self.magfield_dt: float = 0.02
        self.magfield_particles: list[list[float]] = []   # [[x,y,vx,vy,charge,mass], ...]
        self.magfield_trails: list[list[tuple[float, float]]] = []  # trail per particle
        self.magfield_max_trail: int = 300
        self.magfield_Bz: float = 1.0         # uniform B-field z-component
        self.magfield_Ex: float = 0.0         # uniform E-field x
        self.magfield_Ey: float = 0.0         # uniform E-field y
        self.magfield_field_type: int = 0     # 0=uniform, 1=dipole, 2=bottle, 3=quadrupole
        self.magfield_show_field: bool = True  # show field line overlay
        self.magfield_num_particles: int = 12
        self.magfield_viz_mode: int = 0       # 0=trails, 1=velocity color, 2=energy color

        # ── Rayleigh-Bénard Convection mode state ──
        self.rbc_mode: bool = False
        self.rbc_menu: bool = False
        self.rbc_menu_sel: int = 0
        self.rbc_running: bool = False
        self.rbc_generation: int = 0
        self.rbc_preset_name: str = ""
        self.rbc_rows: int = 0
        self.rbc_cols: int = 0
        self.rbc_steps_per_frame: int = 3
        self.rbc_T: list[list[float]] = []       # temperature field
        self.rbc_vx: list[list[float]] = []      # velocity x
        self.rbc_vy: list[list[float]] = []      # velocity y
        self.rbc_Ra: float = 1000.0              # Rayleigh number
        self.rbc_Pr: float = 0.71                # Prandtl number
        self.rbc_dt: float = 0.005               # timestep
        self.rbc_dx: float = 1.0                 # grid spacing
        self.rbc_T_hot: float = 1.0              # bottom temperature
        self.rbc_T_cold: float = 0.0             # top temperature
        self.rbc_viz_mode: int = 0               # 0=temperature, 1=velocity, 2=vorticity

        # ── Smoothed Particle Hydrodynamics (SPH) state ──
        self.sph_mode: bool = False
        self.sph_menu: bool = False
        self.sph_menu_sel: int = 0
        self.sph_running: bool = False
        self.sph_generation: int = 0
        self.sph_preset_name: str = ""
        self.sph_rows: int = 0
        self.sph_cols: int = 0
        self.sph_steps_per_frame: int = 3
        self.sph_particles: list[list[float]] = []  # [x, y, vx, vy, density, pressure]
        self.sph_num_particles: int = 0
        self.sph_gravity: float = 9.8
        self.sph_rest_density: float = 1000.0
        self.sph_gas_const: float = 2000.0
        self.sph_h: float = 1.5            # smoothing radius
        self.sph_mass: float = 1.0
        self.sph_viscosity: float = 250.0
        self.sph_dt: float = 0.003
        self.sph_damping: float = 0.5      # boundary collision damping
        self.sph_viz_mode: int = 0          # 0=density, 1=velocity, 2=pressure

        # ── Artificial Life Ecosystem state ──
        self.alife_mode = False
        self.alife_menu = False
        self.alife_menu_sel = 0
        self.alife_running = False
        self.alife_generation = 0
        self.alife_preset_name: str = ""
        self.alife_tick: int = 0
        self.alife_creatures: list[dict] = []   # list of creature dicts
        self.alife_food: list[list[float]] = [] # 2D food density grid
        self.alife_rows: int = 0
        self.alife_cols: int = 0
        self.alife_next_id: int = 0
        self.alife_pop_history: list[int] = []
        self.alife_herb_history: list[int] = []
        self.alife_pred_history: list[int] = []
        self.alife_gen_max: int = 0             # highest generation seen
        self.alife_total_births: int = 0
        self.alife_total_deaths: int = 0
        self.alife_food_regrow: float = 0.02
        self.alife_mutation_rate: float = 0.15
        self.alife_show_stats: bool = True
        self.alife_speed_scale: float = 1.0

        # ── Doom Raycaster state ──
        self.doomrc_mode = False
        self.doomrc_menu = False
        self.doomrc_menu_sel = 0
        self.doomrc_running = False
        self.doomrc_generation = 0
        self.doomrc_preset_name: str = ""
        self.doomrc_map: list[str] = []
        self.doomrc_map_h: int = 0
        self.doomrc_map_w: int = 0
        self.doomrc_px: float = 2.5       # player x
        self.doomrc_py: float = 2.5       # player y
        self.doomrc_pa: float = 0.0       # player angle (radians)
        self.doomrc_fov: float = 3.14159 / 3.0  # 60 degrees
        self.doomrc_depth: float = 16.0   # max render distance
        self.doomrc_show_map: bool = True  # minimap overlay
        self.doomrc_show_help: bool = True
        self.doomrc_speed: float = 0.15   # movement speed
        self.doomrc_rot_speed: float = 0.08
        self.doomrc_wall_chars: str = "█▓▒░·"  # near to far wall shading
        self.doomrc_floor_chars: str = "#x=-.  "  # far to near floor shading

        # ── Tectonic Plates state ──
        self.tectonic_mode = False
        self.tectonic_menu = False
        self.tectonic_menu_sel = 0
        self.tectonic_running = False
        self.tectonic_generation = 0
        self.tectonic_preset_name: str = ""
        self.tectonic_rows: int = 0
        self.tectonic_cols: int = 0
        self.tectonic_elevation: list[list[float]] = []   # height map
        self.tectonic_plate_id: list[list[int]] = []      # plate assignment per cell
        self.tectonic_plates: list[dict] = []              # plate data (vr, vc, color, name)
        self.tectonic_num_plates: int = 6
        self.tectonic_show_plates: bool = False            # color by plate id
        self.tectonic_show_help: bool = True
        self.tectonic_speed_scale: float = 1.0
        self.tectonic_volcanic: list[tuple[int, int]] = []  # active volcano cells
        self.tectonic_age: int = 0                         # millions of years

        # ── Atmospheric Weather state ──
        self.weather_mode = False
        self.weather_menu = False
        self.weather_menu_sel = 0
        self.weather_running = False
        self.weather_generation = 0
        self.weather_preset_name: str = ""
        self.weather_rows: int = 0
        self.weather_cols: int = 0
        self.weather_pressure: list[list[float]] = []
        self.weather_temperature: list[list[float]] = []
        self.weather_humidity: list[list[float]] = []
        self.weather_wind_u: list[list[float]] = []        # east-west wind component
        self.weather_wind_v: list[list[float]] = []        # north-south wind component
        self.weather_cloud: list[list[float]] = []         # cloud density 0-1
        self.weather_precip: list[list[float]] = []        # precipitation intensity
        self.weather_precip_type: list[list[int]] = []     # 0=none, 1=rain, 2=snow
        self.weather_centers: list[dict] = []              # pressure centers
        self.weather_fronts: list[dict] = []               # frontal boundaries
        self.weather_show_help: bool = True
        self.weather_speed_scale: float = 1.0
        self.weather_hour: int = 0
        self.weather_layer: str = "default"                # default/pressure/temp/wind/humidity
        self.weather_coriolis: float = 0.15                # Coriolis effect strength

        # ── Ocean Currents state ──
        self.ocean_mode = False
        self.ocean_menu = False
        self.ocean_menu_sel = 0
        self.ocean_running = False
        self.ocean_generation = 0
        self.ocean_preset_name: str = ""
        self.ocean_rows: int = 0
        self.ocean_cols: int = 0
        self.ocean_temperature: list[list[float]] = []      # sea surface temperature °C
        self.ocean_salinity: list[list[float]] = []          # salinity PSU (30-40)
        self.ocean_density: list[list[float]] = []           # derived density
        self.ocean_current_u: list[list[float]] = []         # east-west current m/s
        self.ocean_current_v: list[list[float]] = []         # north-south current m/s
        self.ocean_depth: list[list[float]] = []             # relative depth 0-1
        self.ocean_upwelling: list[list[float]] = []         # vertical velocity (positive=up)
        self.ocean_plankton: list[list[float]] = []          # plankton concentration 0-1
        self.ocean_nutrient: list[list[float]] = []          # nutrient concentration 0-1
        self.ocean_gyres: list[dict] = []                    # gyre centers
        self.ocean_deep_formation: list[dict] = []           # deep water formation zones
        self.ocean_show_help: bool = True
        self.ocean_speed_scale: float = 1.0
        self.ocean_day: int = 0
        self.ocean_layer: str = "default"                    # default/temp/salinity/density/currents/plankton

        # ── Volcanic Eruption state ──
        self.volcano_mode = False
        self.volcano_menu = False
        self.volcano_menu_sel = 0
        self.volcano_running = False
        self.volcano_generation = 0
        self.volcano_preset_name: str = ""
        self.volcano_rows: int = 0
        self.volcano_cols: int = 0
        self.volcano_terrain: list[list[float]] = []          # elevation 0-1
        self.volcano_lava: list[list[float]] = []             # lava thickness 0-1
        self.volcano_lava_temp: list[list[float]] = []        # lava temperature °C
        self.volcano_rock: list[list[float]] = []             # cooled rock deposits
        self.volcano_ash: list[list[float]] = []              # airborne ash concentration
        self.volcano_gas: list[list[float]] = []              # volcanic gas SO2
        self.volcano_pyroclastic: list[list[float]] = []      # pyroclastic density current
        self.volcano_vents: list[dict] = []                   # eruption vent positions
        self.volcano_chambers: list[dict] = []                # magma chambers
        self.volcano_particles: list[dict] = []               # ejecta particles in flight
        self.volcano_wind_u: float = 0.0                      # wind east-west
        self.volcano_wind_v: float = 0.0                      # wind north-south
        self.volcano_show_help: bool = True
        self.volcano_speed_scale: float = 1.0
        self.volcano_tick: int = 0
        self.volcano_layer: str = "default"
        self.volcano_eruption_log: list[str] = []

        # ── Black Hole Accretion Disk state ──
        self.blackhole_mode = False
        self.blackhole_menu = False
        self.blackhole_menu_sel = 0
        self.blackhole_running = False
        self.blackhole_generation = 0
        self.blackhole_preset_name: str = ""
        self.blackhole_rows: int = 0
        self.blackhole_cols: int = 0
        # Central black hole parameters
        self.blackhole_mass: float = 50.0           # determines event horizon size
        self.blackhole_spin: float = 0.5            # 0-1 Kerr parameter
        self.blackhole_cx: float = 0.0              # center x
        self.blackhole_cy: float = 0.0              # center y
        self.blackhole_rs: float = 3.0              # Schwarzschild radius (display units)
        # Accretion disk particles: [x, y, vx, vy, temp, age, type]
        # type: 0=disk, 1=jet, 2=hawking
        self.blackhole_particles: list[list[float]] = []
        self.blackhole_bg_stars: list[tuple[float, float, float]] = []  # background stars (x, y, brightness)
        self.blackhole_lensed: list[list[float]] = []   # lensed star grid
        self.blackhole_jet_power: float = 0.8
        self.blackhole_accretion_rate: float = 1.0
        self.blackhole_dt: float = 0.02
        self.blackhole_view: str = "combined"       # combined, disk, lensing, jets
        self.blackhole_total_accreted: float = 0.0
        self.blackhole_show_horizon: bool = True
        self.blackhole_photon_ring: bool = True

        # ── Solar System Orrery state ──
        self.orrery_mode = False
        self.orrery_menu = False
        self.orrery_menu_sel = 0
        self.orrery_running = False
        self.orrery_generation = 0
        self.orrery_preset_name: str = ""
        self.orrery_rows: int = 0
        self.orrery_cols: int = 0
        self.orrery_planets: list[dict] = []
        self.orrery_asteroids: list[dict] = []
        self.orrery_comets: list[dict] = []
        self.orrery_time: float = 0.0          # simulation time in years
        self.orrery_dt: float = 0.002          # time step in years
        self.orrery_speed_scale: float = 1.0
        self.orrery_zoom: str = "full"         # full, inner, outer
        self.orrery_show_orbits: bool = True
        self.orrery_show_labels: bool = True
        self.orrery_show_info: bool = False
        self.orrery_selected: int = -1         # selected planet index
        self.orrery_trail_len: int = 60
        self.orrery_bg_stars: list[tuple[int, int]] = []

        # ── Aurora Borealis state ──
        self.aurora_mode = False
        self.aurora_menu = False
        self.aurora_menu_sel = 0
        self.aurora_running = False
        self.aurora_generation = 0
        self.aurora_preset_name: str = ""
        self.aurora_rows: int = 0
        self.aurora_cols: int = 0
        self.aurora_curtains: list[dict] = []
        self.aurora_particles: list[dict] = []
        self.aurora_stars: list[tuple[int, int, str]] = []
        self.aurora_time: float = 0.0
        self.aurora_intensity: float = 1.0
        self.aurora_wind_strength: float = 0.5
        self.aurora_show_field: bool = False
        self.aurora_show_info: bool = False

        # ── Pendulum Wave state ──
        self.pwave_mode: bool = False
        self.pwave_menu: bool = False
        self.pwave_menu_sel: int = 0
        self.pwave_running: bool = False
        self.pwave_generation: int = 0
        self.pwave_preset_name: str = ""
        self.pwave_rows: int = 0
        self.pwave_cols: int = 0
        self.pwave_time: float = 0.0
        self.pwave_dt: float = 0.02
        self.pwave_n_pendulums: int = 24
        self.pwave_lengths: list[float] = []
        self.pwave_angles: list[float] = []
        self.pwave_g: float = 9.81
        self.pwave_base_length: float = 1.0
        self.pwave_realign_time: float = 60.0
        self.pwave_show_info: bool = False
        self.pwave_trail: list[list[tuple[int, int]]] = []
        self.pwave_max_trail: int = 40
        self.pwave_speed: int = 3

        # ── Tornado & Supercell Storm state ──
        self.tornado_mode: bool = False
        self.tornado_menu: bool = False
        self.tornado_menu_sel: int = 0
        self.tornado_running: bool = False
        self.tornado_generation: int = 0
        self.tornado_preset_name: str = ""
        self.tornado_rows: int = 0
        self.tornado_cols: int = 0
        self.tornado_time: float = 0.0
        self.tornado_dt: float = 0.03
        self.tornado_show_info: bool = False
        self.tornado_speed: int = 2
        # Vortex parameters
        self.tornado_vortex_x: float = 0.0
        self.tornado_vortex_y: float = 0.0
        self.tornado_vortex_radius: float = 3.0
        self.tornado_vortex_max_radius: float = 8.0
        self.tornado_vortex_height: float = 0.0
        self.tornado_rotation_speed: float = 2.0
        self.tornado_touch_ground: bool = False
        self.tornado_wobble_phase: float = 0.0
        self.tornado_wobble_amp: float = 1.5
        # Storm parameters
        self.tornado_storm_radius: float = 30.0
        self.tornado_rain_particles: list[list[float]] = []
        self.tornado_debris: list[list[float]] = []
        self.tornado_max_debris: int = 60
        self.tornado_max_rain: int = 200
        # Lightning
        self.tornado_lightning_active: bool = False
        self.tornado_lightning_timer: float = 0.0
        self.tornado_lightning_interval: float = 3.0
        self.tornado_lightning_segments: list[tuple[int, int, int, int]] = []
        self.tornado_lightning_flash: int = 0
        # Destruction path
        self.tornado_destruction: list[tuple[int, int]] = []
        self.tornado_max_destruction: int = 500
        # Mesocyclone cloud rotation
        self.tornado_cloud_angle: float = 0.0
        self.tornado_cloud_radius: float = 15.0
        # Wind field
        self.tornado_updraft_strength: float = 1.0
        self.tornado_downdraft_strength: float = 0.5

        # ── Sorting Algorithm Visualizer state ──
        self.sortvis_mode: bool = False
        self.sortvis_menu: bool = False
        self.sortvis_menu_sel: int = 0
        self.sortvis_running: bool = False
        self.sortvis_generation: int = 0
        self.sortvis_preset_name: str = ""
        self.sortvis_rows: int = 0
        self.sortvis_cols: int = 0
        self.sortvis_show_info: bool = False
        self.sortvis_speed: int = 1
        self.sortvis_array: list[int] = []
        self.sortvis_array_size: int = 60
        self.sortvis_steps: list[tuple] = []  # pre-computed sort steps
        self.sortvis_step_idx: int = 0
        self.sortvis_comparisons: int = 0
        self.sortvis_swaps: int = 0
        self.sortvis_highlight_cmp: tuple[int, ...] = ()  # indices being compared
        self.sortvis_highlight_swap: tuple[int, ...] = ()  # indices being swapped
        self.sortvis_sorted_indices: set[int] = set()  # indices known to be in final position
        self.sortvis_done: bool = False
        self.sortvis_algorithm: str = ""

        # ── DNA Helix & Genetic Algorithm state ──
        self.dnahelix_mode: bool = False
        self.dnahelix_menu: bool = False
        self.dnahelix_menu_sel: int = 0
        self.dnahelix_running: bool = False
        self.dnahelix_generation: int = 0
        self.dnahelix_preset_name: str = ""
        self.dnahelix_rows: int = 0
        self.dnahelix_cols: int = 0
        self.dnahelix_show_info: bool = False
        self.dnahelix_speed: int = 1
        self.dnahelix_phase: float = 0.0
        self.dnahelix_target: list[int] = []
        self.dnahelix_population: list[list[int]] = []
        self.dnahelix_pop_size: int = 40
        self.dnahelix_genome_len: int = 32
        self.dnahelix_best_genome: list[int] = []
        self.dnahelix_best_fitness: float = 0.0
        self.dnahelix_avg_fitness: float = 0.0
        self.dnahelix_mutation_rate: float = 0.02
        self.dnahelix_crossover_rate: float = 0.7
        self.dnahelix_solved: bool = False
        self.dnahelix_fitness_history: list[float] = []

        # ── Fourier Epicycle Drawing state ──
        self.fourier_mode: bool = False
        self.fourier_menu: bool = False
        self.fourier_menu_sel: int = 0
        self.fourier_running: bool = False
        self.fourier_phase: str = "menu"  # "menu", "drawing", "playing"
        self.fourier_preset_name: str = ""
        self.fourier_show_info: bool = True
        self.fourier_speed: int = 1
        self.fourier_path: list[tuple[float, float]] = []  # user-drawn points
        self.fourier_coeffs: list[tuple[float, float, float, float]] = []  # (freq, amp, phase, _)
        self.fourier_time: float = 0.0
        self.fourier_dt: float = 0.0
        self.fourier_trace: list[tuple[float, float]] = []  # reconstructed points
        self.fourier_num_circles: int = 0
        self.fourier_max_circles: int = 999
        self.fourier_cursor_x: int = 0
        self.fourier_cursor_y: int = 0
        self.fourier_drawing: bool = False  # mouse/key drawing active
        self.fourier_show_circles: bool = True

        # ── Snowfall & Blizzard state ──
        self.snowfall_mode: bool = False
        self.snowfall_menu: bool = False
        self.snowfall_menu_sel: int = 0
        self.snowfall_running: bool = False
        self.snowfall_generation: int = 0
        self.snowfall_preset_name: str = ""
        self.snowfall_rows: int = 0
        self.snowfall_cols: int = 0
        self.snowfall_time: float = 0.0
        self.snowfall_dt: float = 0.03
        self.snowfall_show_info: bool = False
        self.snowfall_speed: int = 2
        self.snowfall_flakes: list = []  # [x, y, vx, vy, size, wobble_phase]
        self.snowfall_accumulation: list = []  # height per column
        self.snowfall_wind_speed: float = 0.0
        self.snowfall_wind_dir: float = 1.0  # 1.0 = right, -1.0 = left
        self.snowfall_wind_gust_phase: float = 0.0
        self.snowfall_density: int = 200
        self.snowfall_temperature: float = -5.0  # Celsius
        self.snowfall_max_accumulation: float = 0.0
        self.snowfall_visibility: float = 1.0
        self.snowfall_drift_particles: list = []  # ground-level drift [x, y, vx, life]

        # ── Fluid Rope / Honey Coiling state ──
        self.fluidrope_mode: bool = False
        self.fluidrope_menu: bool = False
        self.fluidrope_menu_sel: int = 0
        self.fluidrope_running: bool = False
        self.fluidrope_generation: int = 0
        self.fluidrope_preset_name: str = ""
        self.fluidrope_rows: int = 0
        self.fluidrope_cols: int = 0
        self.fluidrope_time: float = 0.0
        self.fluidrope_dt: float = 0.02
        self.fluidrope_show_info: bool = False
        self.fluidrope_speed: int = 3
        self.fluidrope_pour_x: float = 0.5  # normalized 0-1
        self.fluidrope_pour_y: float = 0.1  # normalized from top
        self.fluidrope_pour_height: float = 0.7  # height of pour stream
        self.fluidrope_flow_rate: float = 1.0
        self.fluidrope_viscosity: float = 1.0
        self.fluidrope_rope_segments: list = []  # [(x, y, vx, vy), ...]
        self.fluidrope_pool: list = []  # accumulated fluid heights per column
        self.fluidrope_coil_angle: float = 0.0
        self.fluidrope_coil_radius: float = 0.0
        self.fluidrope_coil_speed: float = 0.0
        self.fluidrope_surface_move: float = 0.0  # surface movement speed
        self.fluidrope_surface_offset: float = 0.0
        self.fluidrope_trail: list = []  # recent landing positions for coil pattern

        # ── Lissajous Curve / Harmonograph state ──
        self.lissajous_mode: bool = False
        self.lissajous_menu: bool = False
        self.lissajous_menu_sel: int = 0
        self.lissajous_running: bool = False
        self.lissajous_generation: int = 0
        self.lissajous_preset_name: str = ""
        self.lissajous_rows: int = 0
        self.lissajous_cols: int = 0
        self.lissajous_time: float = 0.0
        self.lissajous_dt: float = 0.02
        self.lissajous_show_info: bool = False
        self.lissajous_speed: int = 2
        self.lissajous_trail: list = []  # [(x, y, intensity), ...]
        self.lissajous_max_trail: int = 4000
        self.lissajous_freq_a: float = 3.0
        self.lissajous_freq_b: float = 2.0
        self.lissajous_phase: float = 0.0  # phase offset in radians
        self.lissajous_damping: float = 0.0  # damping factor
        self.lissajous_amp_x: float = 0.9  # amplitude x (normalized)
        self.lissajous_amp_y: float = 0.9  # amplitude y (normalized)
        self.lissajous_freq_c: float = 0.0  # third oscillator freq (harmonograph)
        self.lissajous_freq_d: float = 0.0  # fourth oscillator freq (harmonograph)
        self.lissajous_phase2: float = 0.0  # second phase offset
        self.lissajous_canvas: dict = {}  # {(row, col): intensity}
        self.lissajous_pen_x: float = 0.0
        self.lissajous_pen_y: float = 0.0
        self.lissajous_clear_on_reset: bool = True

        # ── Maze Solver Visualizer state ──
        self.mazesolver_mode: bool = False
        self.mazesolver_menu: bool = False
        self.mazesolver_menu_sel: int = 0
        self.mazesolver_running: bool = False
        self.mazesolver_generation: int = 0
        self.mazesolver_rows: int = 0
        self.mazesolver_cols: int = 0
        self.mazesolver_grid: list[list[int]] = []  # 0=wall, 1=passage
        self.mazesolver_preset_name: str = ""
        self.mazesolver_algo: str = ""
        self.mazesolver_phase: str = "generating"  # generating, solving, done
        self.mazesolver_start: tuple[int, int] = (1, 1)
        self.mazesolver_end: tuple[int, int] = (1, 1)
        self.mazesolver_solve_queue: list = []
        self.mazesolver_solve_visited: set = set()
        self.mazesolver_solve_parent: dict = {}
        self.mazesolver_solve_path: list = []
        self.mazesolver_solve_done: bool = False
        self.mazesolver_solve_steps: int = 0
        self.mazesolver_frontier_set: set = set()  # current frontier for visualization
        self.mazesolver_speed: int = 3
        self.mazesolver_maze_size: str = "medium"  # small, medium, large
        # Wall follower state
        self.mazesolver_wf_pos: tuple[int, int] = (1, 1)
        self.mazesolver_wf_dir: int = 0  # 0=right,1=down,2=left,3=up
        self.mazesolver_wf_trail: list = []
        self.mazesolver_gen_stack: list = []
        self.mazesolver_gen_visited: set = set()

        # ── Matrix Digital Rain state ──
        self.matrix_mode: bool = False
        self.matrix_menu: bool = False
        self.matrix_menu_sel: int = 0
        self.matrix_running: bool = False
        self.matrix_generation: int = 0
        self.matrix_rows: int = 0
        self.matrix_cols: int = 0
        self.matrix_preset_name: str = ""
        self.matrix_speed: int = 2
        self.matrix_show_info: bool = False
        self.matrix_columns: list = []  # list of stream dicts per column
        self.matrix_density: float = 0.4  # probability a column has a stream
        self.matrix_time: float = 0.0
        self.matrix_char_pool: str = ""
        self.matrix_color_mode: str = "green"  # green, rainbow, blue

        # ── Ant Farm Simulation state ──
        self.antfarm_mode: bool = False
        self.antfarm_menu: bool = False
        self.antfarm_menu_sel: int = 0
        self.antfarm_running: bool = False
        self.antfarm_generation: int = 0
        self.antfarm_rows: int = 0
        self.antfarm_cols: int = 0
        self.antfarm_preset_name: str = ""
        self.antfarm_speed: int = 1
        self.antfarm_show_info: bool = False
        self.antfarm_grid: list = []
        self.antfarm_pheromone_food: list = []
        self.antfarm_pheromone_home: list = []
        self.antfarm_ants: list = []
        self.antfarm_food_surface: list = []
        self.antfarm_queen_pos: tuple = (0, 0)
        self.antfarm_sky_rows: int = 3
        self.antfarm_surface_row: int = 0
        self.antfarm_rain_drops: list = []
        self.antfarm_rain_active: bool = False
        self.antfarm_cursor_x: int = 0
        self.antfarm_total_food: int = 0
        self.antfarm_eggs: int = 0

        # ── Kaleidoscope / Symmetry Pattern Generator state ──
        self.kaleido_mode: bool = False
        self.kaleido_menu: bool = False
        self.kaleido_menu_sel: int = 0
        self.kaleido_running: bool = False
        self.kaleido_generation: int = 0
        self.kaleido_rows: int = 0
        self.kaleido_cols: int = 0
        self.kaleido_preset_name: str = ""
        self.kaleido_speed: int = 2
        self.kaleido_show_info: bool = False
        self.kaleido_symmetry: int = 6
        self.kaleido_canvas: dict = {}
        self.kaleido_time: float = 0.0
        self.kaleido_seeds: list = []
        self.kaleido_palette_idx: int = 0
        self.kaleido_color_shift: float = 0.0
        self.kaleido_painting: bool = False
        self.kaleido_cursor_r: int = 0
        self.kaleido_cursor_c: int = 0
        self.kaleido_auto_mode: bool = True
        self.kaleido_brush_size: int = 1
        self.kaleido_fade: bool = True

        # ── ASCII Aquarium / Fish Tank state ──
        self.aquarium_mode: bool = False
        self.aquarium_menu: bool = False
        self.aquarium_menu_sel: int = 0
        self.aquarium_running: bool = False
        self.aquarium_generation: int = 0
        self.aquarium_rows: int = 0
        self.aquarium_cols: int = 0
        self.aquarium_preset_name: str = ""
        self.aquarium_speed: int = 1
        self.aquarium_show_info: bool = False
        self.aquarium_fish: list = []
        self.aquarium_seaweed: list = []
        self.aquarium_bubbles: list = []
        self.aquarium_food: list = []
        self.aquarium_sand: list = []
        self.aquarium_time: float = 0.0
        self.aquarium_startled: float = 0.0
        self.aquarium_caustic_phase: float = 0.0

        # ── Particle Collider / Hadron Collider state ──
        self.collider_mode: bool = False
        self.collider_menu: bool = False
        self.collider_menu_sel: int = 0
        self.collider_running: bool = False
        self.collider_generation: int = 0
        self.collider_rows: int = 0
        self.collider_cols: int = 0
        self.collider_preset_name: str = ""
        self.collider_speed: int = 1
        self.collider_show_info: bool = False
        self.collider_time: float = 0.0
        self.collider_beams: list = []          # particles in the ring
        self.collider_showers: list = []         # decay product showers
        self.collider_trails: list = []          # fading trail positions
        self.collider_detections: list = []      # detected particle events
        self.collider_energy: float = 0.0        # current beam energy (TeV)
        self.collider_total_collisions: int = 0
        self.collider_ring_cx: float = 0.0       # ring center
        self.collider_ring_cy: float = 0.0
        self.collider_ring_rx: float = 0.0       # ring radii (x/y for ellipse)
        self.collider_ring_ry: float = 0.0
        self.collider_collision_points: list = []  # interaction points on ring
        self.collider_detector_log: list = []      # scrolling event log

        # ── Screensaver / Demo Reel state ──
        self.screensaver_mode: bool = False
        self.screensaver_menu: bool = False
        self.screensaver_menu_sel: int = 0
        self.screensaver_running: bool = False
        self.screensaver_generation: int = 0
        self.screensaver_time: float = 0.0
        self.screensaver_preset_name: str = ""
        self.screensaver_interval: int = 15  # seconds per mode
        self.screensaver_playlist: list = []
        self.screensaver_playlist_idx: int = 0
        self.screensaver_active_mode = None
        self.screensaver_mode_start_time: float = 0.0
        self.screensaver_transition_phase: float = 0.0
        self.screensaver_transition_buf: list = []
        self.screensaver_overlay_alpha: float = 0.0
        self.screensaver_paused: bool = False
        self.screensaver_show_overlay: bool = True
        # Parameter Space Explorer mode
        self.pexplorer_mode: bool = False
        self.pexplorer_menu: bool = False
        self.pexplorer_menu_sel: int = 0
        self.pexplorer_running: bool = False
        self.pexplorer_generation: int = 0
        self.pexplorer_sims: list = []

        # ── Minimap overlay state ──
        self.show_minimap = False  # toggled with Tab key

        self._rebuild_pattern_list()

        if pattern:
            self._place_pattern(pattern)



    def _place_pattern(self, name: str):
        pat = self._get_pattern(name)
        if not pat:
            self.message = f"Unknown pattern: {name}"
            self.message_time = time.monotonic()
            return
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = (self.grid.rows - max_r) // 2
        off_c = (self.grid.cols - max_c) // 2
        for r, c in pat["cells"]:
            self.grid.set_alive((r + off_r) % self.grid.rows, (c + off_c) % self.grid.cols)
        self.cursor_r = off_r + max_r // 2
        self.cursor_c = off_c + max_c // 2
        self.message = f"Loaded: {name}"
        self.message_time = time.monotonic()


    def _stamp_pattern(self, name: str):
        """Overlay a pattern centered on the current cursor without clearing the grid."""
        pat = self._get_pattern(name)
        if not pat:
            self._flash(f"Unknown pattern: {name}")
            return
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = self.cursor_r - max_r // 2
        off_c = self.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            self.grid.set_alive((r + off_r) % self.grid.rows, (c + off_c) % self.grid.cols)
        self._flash(f"Stamped: {name}")


    def _flash(self, msg: str):
        self.message = msg
        self.message_time = time.monotonic()

    # ── Minimap overlay ──


    def _any_menu_open(self) -> bool:
        """Return True if any menu or non-simulation overlay is active."""
        if self.mode_browser or self.show_help or self.blueprint_menu:
            return True
        # Check all mode-specific menus (pattern: self.X_menu = bool)
        _menu_attrs = [
            'puzzle_menu', 'pattern_menu', 'stamp_menu', 'bookmark_menu',
            'rule_menu', 'compare_rule_menu', 'race_rule_menu',
            'wolfram_menu', 'ant_menu', 'ww_menu', 'sand_menu', 'rd_menu',
            'lenia_menu', 'physarum_menu', 'boids_menu', 'plife_menu',
            'nbody_menu', 'fluid_menu', 'wfc_menu', 'aco_menu', 'maze_menu',
            'dla_menu', 'sandpile_menu', 'fire_menu', 'sir_menu',
            'cyclic_menu', 'ising_menu', 'hodge_menu', 'lv_menu',
            'schelling_menu', 'spd_menu', 'lightning_menu', 'erosion_menu',
            'voronoi_menu', 'rps_menu', 'wave_menu', 'kuramoto_menu',
            'bz_menu', 'chemo_menu', 'mhd_menu', 'attractor_menu',
            'qwalk_menu', 'terrain_menu', 'smokefire_menu', 'cloth_menu',
            'galaxy_menu', 'lsystem_menu', 'fractal_menu', 'fireworks_menu',
            'ns_menu', 'traffic_menu', 'snowflake_menu', 'turmite_menu',
            'evo_menu', 'chladni_menu', 'cpm_menu', 'fdtd_menu',
            'magfield_menu', 'rbc_menu', 'sph_menu', 'tectonic_menu',
            'volcano_menu', 'ocean_menu', 'weather_menu', 'blackhole_menu',
            'pexplorer_menu', 'ep_menu',
        ]
        for attr in _menu_attrs:
            if getattr(self, attr, False):
                return True
        return False


    def _get_minimap_data(self):
        """Return (rows, cols, sample_func, view_r, view_c, view_h, view_w) for current mode.

        sample_func(r, c) -> float 0.0-1.0 indicating activity.
        view_* describe the currently visible viewport rectangle.
        Returns None if minimap is not available.
        """
        # Helper to detect which mode is active and return its grid data
        # Dict-based grids
        if self.ant_mode and self.ant_rows > 0:
            g = self.ant_grid
            return (self.ant_rows, self.ant_cols,
                    lambda r, c: 1.0 if g.get((r, c), 0) > 0 else 0.0,
                    0, 0, self.ant_rows, self.ant_cols)
        if self.ww_mode and self.ww_rows > 0:
            g = self.ww_grid
            def _ww(r, c):
                s = g.get((r, c), 0)
                return (1.0 if s == 2 else 0.7 if s == 3 else 0.3 if s == 1 else 0.0)
            return (self.ww_rows, self.ww_cols, _ww,
                    0, 0, self.ww_rows, self.ww_cols)
        if self.sand_mode and self.sand_rows > 0:
            g = self.sand_grid
            return (self.sand_rows, self.sand_cols,
                    lambda r, c: 1.0 if g.get((r, c)) is not None else 0.0,
                    0, 0, self.sand_rows, self.sand_cols)
        if self.turmite_mode and self.turmite_rows > 0:
            g = self.turmite_grid
            return (self.turmite_rows, self.turmite_cols,
                    lambda r, c: 1.0 if g.get((r, c), 0) > 0 else 0.0,
                    0, 0, self.turmite_rows, self.turmite_cols)

        # Float 2D list grids
        if self.rd_mode and self.rd_rows > 0:
            V = self.rd_V
            return (self.rd_rows, self.rd_cols,
                    lambda r, c: min(1.0, V[r][c]),
                    0, 0, self.rd_rows, self.rd_cols)
        if self.lenia_mode and self.lenia_rows > 0:
            g = self.lenia_grid
            return (self.lenia_rows, self.lenia_cols,
                    lambda r, c: min(1.0, g[r][c]),
                    0, 0, self.lenia_rows, self.lenia_cols)
        if self.physarum_mode and self.physarum_rows > 0:
            t = self.physarum_trail
            return (self.physarum_rows, self.physarum_cols,
                    lambda r, c: min(1.0, t[r][c]),
                    0, 0, self.physarum_rows, self.physarum_cols)
        if self.wave_mode and self.wave_rows > 0:
            u = self.wave_u
            return (self.wave_rows, self.wave_cols,
                    lambda r, c: min(1.0, abs(u[r][c])),
                    0, 0, self.wave_rows, self.wave_cols)
        if self.kuramoto_mode and self.kuramoto_rows > 0:
            p = self.kuramoto_phases
            _two_pi = 2 * math.pi
            return (self.kuramoto_rows, self.kuramoto_cols,
                    lambda r, c: (p[r][c] % _two_pi) / _two_pi,
                    0, 0, self.kuramoto_rows, self.kuramoto_cols)
        if self.bz_mode and self.bz_rows > 0:
            a = self.bz_a
            return (self.bz_rows, self.bz_cols,
                    lambda r, c: min(1.0, max(0.0, a[r][c])),
                    0, 0, self.bz_rows, self.bz_cols)
        if self.attractor_mode and self.attractor_rows > 0:
            d = self.attractor_density
            mx = max(self.attractor_max_density, 1.0)
            return (self.attractor_rows, self.attractor_cols,
                    lambda r, c: min(1.0, d[r][c] / mx) if d and r < len(d) and c < len(d[0]) else 0.0,
                    0, 0, self.attractor_rows, self.attractor_cols)
        if self.terrain_mode and self.terrain_rows > 0:
            h = self.terrain_heightmap
            return (self.terrain_rows, self.terrain_cols,
                    lambda r, c: min(1.0, h[r][c]) if h else 0.0,
                    0, 0, self.terrain_rows, self.terrain_cols)
        if self.smokefire_mode and self.smokefire_rows > 0:
            t = self.smokefire_temp
            s = self.smokefire_smoke
            return (self.smokefire_rows, self.smokefire_cols,
                    lambda r, c: min(1.0, max(t[r][c], s[r][c])),
                    0, 0, self.smokefire_rows, self.smokefire_cols)
        if self.ns_mode and self.ns_rows > 0:
            d = self.ns_dye
            return (self.ns_rows, self.ns_cols,
                    lambda r, c: min(1.0, max(0.0, d[r][c])),
                    0, 0, self.ns_rows, self.ns_cols)
        if self.rbc_mode and self.rbc_rows > 0:
            T = self.rbc_T
            return (self.rbc_rows, self.rbc_cols,
                    lambda r, c: min(1.0, max(0.0, T[r][c])),
                    0, 0, self.rbc_rows, self.rbc_cols)
        if self.fdtd_mode and self.fdtd_rows > 0:
            Ez = self.fdtd_Ez
            return (self.fdtd_rows, self.fdtd_cols,
                    lambda r, c: min(1.0, abs(Ez[r][c])) if Ez and r < len(Ez) else 0.0,
                    0, 0, self.fdtd_rows, self.fdtd_cols)
        if self.chemo_mode and self.chemo_rows > 0:
            b = self.chemo_bacteria
            if b and len(b) > 0:
                return (self.chemo_rows, self.chemo_cols,
                        lambda r, c: min(1.0, b[r][c]) if r < len(b) and c < len(b[0]) else 0.0,
                        0, 0, self.chemo_rows, self.chemo_cols)
        if self.mhd_mode and self.mhd_rows > 0:
            rho = self.mhd_rho
            if rho and len(rho) > 0:
                return (self.mhd_rows, self.mhd_cols,
                        lambda r, c: min(1.0, max(0.0, rho[r][c])) if r < len(rho) and c < len(rho[0]) else 0.0,
                        0, 0, self.mhd_rows, self.mhd_cols)
        if self.fluid_mode and self.fluid_rows > 0 and self.fluid_f:
            f = self.fluid_f
            obs = self.fluid_obstacle
            def _fluid_sample(r, c):
                if r >= len(f) or c >= len(f[0]):
                    return 0.0
                if obs and r < len(obs) and c < len(obs[0]) and obs[r][c]:
                    return 0.8  # obstacle
                rho = sum(f[r][c])
                # LBM density is ~1.0 at rest; show deviations
                return min(1.0, max(0.0, abs(rho - 1.0) * 5 + 0.1))
            return (self.fluid_rows, self.fluid_cols, _fluid_sample,
                    0, 0, self.fluid_rows, self.fluid_cols)
        if self.erosion_mode and self.erosion_rows > 0 and self.erosion_terrain:
            h = self.erosion_terrain
            return (self.erosion_rows, self.erosion_cols,
                    lambda r, c: min(1.0, h[r][c]) if r < len(h) and c < len(h[0]) else 0.0,
                    0, 0, self.erosion_rows, self.erosion_cols)

        # Quantum walk (probability grid)
        if self.qwalk_mode and self.qwalk_rows > 0 and self.qwalk_prob:
            p = self.qwalk_prob
            return (self.qwalk_rows, self.qwalk_cols,
                    lambda r, c: min(1.0, p[r][c] * 10) if r < len(p) and c < len(p[0]) else 0.0,
                    0, 0, self.qwalk_rows, self.qwalk_cols)

        # Chladni patterns
        if self.chladni_mode:
            sand = getattr(self, 'chladni_sand', None)
            rows = getattr(self, 'chladni_rows', 0)
            cols = getattr(self, 'chladni_cols', 0)
            if sand and rows > 0 and cols > 0:
                return (rows, cols,
                        lambda r, c: min(1.0, sand[r][c]) if r < len(sand) and c < len(sand[0]) else 0.0,
                        0, 0, rows, cols)

        # Galaxy (density grid)
        if self.galaxy_mode and self.galaxy_rows > 0 and self.galaxy_density:
            d = self.galaxy_density
            return (self.galaxy_rows, self.galaxy_cols,
                    lambda r, c: min(1.0, d[r][c]) if r < len(d) and c < len(d[0]) else 0.0,
                    0, 0, self.galaxy_rows, self.galaxy_cols)

        # Integer 2D list grids (>0 = occupied)
        int_grid_modes = [
            ("dla_mode", "dla_rows", "dla_cols", "dla_grid"),
            ("sir_mode", "sir_rows", "sir_cols", "sir_grid"),
            ("sandpile_mode", "sandpile_rows", "sandpile_cols", "sandpile_grid"),
            ("fire_mode", "fire_rows", "fire_cols", "fire_grid"),
            ("cyclic_mode", "cyclic_rows", "cyclic_cols", "cyclic_grid"),
            ("hodge_mode", "hodge_rows", "hodge_cols", "hodge_grid"),
            ("lv_mode", "lv_rows", "lv_cols", "lv_grid"),
            ("spd_mode", "spd_rows", "spd_cols", "spd_grid"),
            ("schelling_mode", "schelling_rows", "schelling_cols", "schelling_grid"),
            ("lightning_mode", "lightning_rows", "lightning_cols", "lightning_grid"),
            ("voronoi_mode", "voronoi_rows", "voronoi_cols", "voronoi_grid"),
            ("rps_mode", "rps_rows", "rps_cols", "rps_grid"),
            ("maze_mode", "maze_rows", "maze_cols", "maze_grid"),
            ("cpm_mode", "cpm_rows", "cpm_cols", "cpm_grid"),
            ("traffic_mode", "traffic_rows", "traffic_cols", "traffic_grid"),
        ]
        for mode_attr, rows_attr, cols_attr, grid_attr in int_grid_modes:
            if getattr(self, mode_attr, False):
                rows = getattr(self, rows_attr, 0)
                cols = getattr(self, cols_attr, 0)
                g = getattr(self, grid_attr, None)
                if rows > 0 and cols > 0 and g and len(g) >= rows:
                    def _make_sampler(grid, nrows, ncols):
                        def _sample(r, c):
                            if r < nrows and c < ncols and r < len(grid) and c < len(grid[r]):
                                v = grid[r][c]
                                return 1.0 if v > 0 else 0.0
                            return 0.0
                        return _sample
                    return (rows, cols, _make_sampler(g, rows, cols),
                            0, 0, rows, cols)

        # Snowflake (bool frozen grid)
        if self.snowflake_mode and self.snowflake_rows > 0 and self.snowflake_frozen:
            g = self.snowflake_frozen
            return (self.snowflake_rows, self.snowflake_cols,
                    lambda r, c: 1.0 if r < len(g) and c < len(g[0]) and g[r][c] else 0.0,
                    0, 0, self.snowflake_rows, self.snowflake_cols)

        # ACO (pheromone float grid)
        if self.aco_mode and self.aco_rows > 0 and self.aco_pheromone:
            p = self.aco_pheromone
            return (self.aco_rows, self.aco_cols,
                    lambda r, c: min(1.0, p[r][c]) if r < len(p) and c < len(p[0]) else 0.0,
                    0, 0, self.aco_rows, self.aco_cols)

        # Ising (always occupied: +1/-1)
        if self.ising_mode and self.ising_rows > 0 and self.ising_grid:
            g = self.ising_grid
            return (self.ising_rows, self.ising_cols,
                    lambda r, c: 1.0 if g[r][c] > 0 else 0.3,
                    0, 0, self.ising_rows, self.ising_cols)

        # Particle-based modes: project to density grid
        particle_modes = [
            ("boids_mode", "boids_rows", "boids_cols", "boids_agents"),
            ("plife_mode", "plife_rows", "plife_cols", "plife_particles"),
            ("nbody_mode", "nbody_rows", "nbody_cols", "nbody_bodies"),
            ("sph_mode", "sph_rows", "sph_cols", "sph_particles"),
            ("magfield_mode", "magfield_rows", "magfield_cols", "magfield_particles"),
            ("fireworks_mode", "fireworks_rows", "fireworks_cols", "fireworks_particles"),
        ]
        for mode_attr, rows_attr, cols_attr, parts_attr in particle_modes:
            if getattr(self, mode_attr, False):
                rows = getattr(self, rows_attr, 0)
                cols = getattr(self, cols_attr, 0)
                parts = getattr(self, parts_attr, [])
                if rows > 0 and cols > 0 and parts:
                    # Build a quick density set from particle positions
                    occ = set()
                    for p in parts:
                        if isinstance(p, (list, tuple)) and len(p) >= 2:
                            pr = int(p[0]) if not isinstance(p, dict) else int(p.get("r", p.get("y", 0)))
                            pc = int(p[1]) if not isinstance(p, dict) else int(p.get("c", p.get("x", 0)))
                            if 0 <= pr < rows and 0 <= pc < cols:
                                occ.add((pr, pc))
                        elif isinstance(p, dict):
                            pr = int(p.get("r", p.get("y", p.get("row", 0))))
                            pc = int(p.get("c", p.get("x", p.get("col", 0))))
                            if 0 <= pr < rows and 0 <= pc < cols:
                                occ.add((pr, pc))
                    return (rows, cols,
                            lambda r, c, _o=occ: 1.0 if (r, c) in _o else 0.0,
                            0, 0, rows, cols)

        # Fractal mode
        if self.fractal_mode and self.fractal_rows > 0 and self.fractal_buffer:
            buf = self.fractal_buffer
            mx = max(self.fractal_max_iter, 1)
            return (self.fractal_rows, self.fractal_cols,
                    lambda r, c: buf[r][c] / mx if r < len(buf) and c < len(buf[0]) else 0.0,
                    0, 0, self.fractal_rows, self.fractal_cols)

        # WFC mode
        if self.wfc_mode and self.wfc_rows > 0 and self.wfc_grid:
            g = self.wfc_grid
            return (self.wfc_rows, self.wfc_cols,
                    lambda r, c: (1.0 if len(g[r][c]) == 1 else 0.3) if r < len(g) and c < len(g[0]) else 0.0,
                    0, 0, self.wfc_rows, self.wfc_cols)

        # Wolfram 1D CA — uses the accumulated row history
        if self.wolfram_mode:
            g = self.wolfram_rows  # list[list[int]], each entry is one generation
            if g and len(g) > 0:
                rows = len(g)
                cols = len(g[0])
                return (rows, cols,
                        lambda r, c: 1.0 if r < len(g) and c < len(g[r]) and g[r][c] > 0 else 0.0,
                        0, 0, rows, cols)

        # Default: Game of Life
        if self.grid.rows > 0 and self.grid.cols > 0:
            max_y, max_x = self.stdscr.getmaxyx()
            zoom = self.zoom_level
            vis_rows = max(1, max_y - 5)
            vis_cols = max(1, (max_x - 1) // 2)
            grid_vis_rows = vis_rows * zoom
            grid_vis_cols = vis_cols * zoom
            vr = self.cursor_r - grid_vis_rows // 2
            vc = self.cursor_c - grid_vis_cols // 2
            cells = self.grid.cells
            return (self.grid.rows, self.grid.cols,
                    lambda r, c: 1.0 if cells[r][c] > 0 else 0.0,
                    vr, vc, grid_vis_rows, grid_vis_cols)

        return None


    def _draw_minimap(self, max_y: int, max_x: int):
        """Draw a minimap overlay in the top-right corner of the screen."""
        data = self._get_minimap_data()
        if data is None:
            return

        grid_rows, grid_cols, sample_fn, view_r, view_c, view_h, view_w = data
        if grid_rows <= 0 or grid_cols <= 0:
            return

        # Calculate minimap dimensions (including 2-char border)
        # Each minimap cell is 1 char wide (not 2 like main grid) for compactness
        max_map_w = min(40, max_x // 3)  # max width in chars including border
        max_map_h = min(20, max_y // 3)  # max height including border
        inner_w = max(4, max_map_w - 2)
        inner_h = max(3, max_map_h - 2)

        # Maintain aspect ratio of the grid
        grid_aspect = grid_cols / max(1, grid_rows)
        if grid_aspect > inner_w / inner_h:
            # Wide grid: fit to width
            map_w = inner_w
            map_h = max(3, int(inner_w / grid_aspect))
        else:
            # Tall grid: fit to height
            map_h = inner_h
            map_w = max(4, int(inner_h * grid_aspect))

        # Total dimensions with border
        total_w = map_w + 2  # left border + content + right border
        total_h = map_h + 2  # top border + content + bottom border

        # Position: top-right corner with 1-char margin
        start_x = max_x - total_w - 1
        start_y = 1
        if start_x < 2 or start_y + total_h >= max_y - 2:
            return  # not enough room

        # Grid cells per minimap cell
        step_r = grid_rows / map_h
        step_c = grid_cols / map_w

        # Density glyphs for single-char cells
        MINI_GLYPHS = " ░▒▓█"

        # Draw border and label
        label = " MINIMAP "
        if map_w >= len(label):
            top_border = "┌" + label + "─" * (map_w - len(label)) + "┐"
        else:
            top_border = "┌" + "─" * map_w + "┐"
        bot_border = "└" + "─" * map_w + "┘"

        border_attr = curses.color_pair(6) | curses.A_DIM
        try:
            self.stdscr.addstr(start_y, start_x, top_border[:total_w], border_attr)
        except curses.error:
            pass
        try:
            self.stdscr.addstr(start_y + total_h - 1, start_x, bot_border[:total_w], border_attr)
        except curses.error:
            pass

        # Compute viewport rectangle in minimap coordinates
        vp_r0 = view_r / step_r if step_r > 0 else 0
        vp_c0 = view_c / step_c if step_c > 0 else 0
        vp_r1 = (view_r + view_h) / step_r if step_r > 0 else map_h
        vp_c1 = (view_c + view_w) / step_c if step_c > 0 else map_w

        # Check if viewport covers the whole grid (no zoom)
        full_view = (view_h >= grid_rows and view_w >= grid_cols)

        # Draw content rows
        for my in range(map_h):
            sy = start_y + 1 + my
            if sy >= max_y - 1:
                break

            # Left border
            try:
                self.stdscr.addstr(sy, start_x, "│", border_attr)
            except curses.error:
                pass

            for mx in range(map_w):
                sx = start_x + 1 + mx
                if sx >= max_x - 1:
                    break

                # Sample grid block for this minimap cell
                gr_start = int(my * step_r)
                gr_end = int((my + 1) * step_r)
                gc_start = int(mx * step_c)
                gc_end = int((mx + 1) * step_c)
                gr_end = max(gr_end, gr_start + 1)
                gc_end = max(gc_end, gc_start + 1)

                total = 0
                active = 0.0
                for gr in range(gr_start, min(gr_end, grid_rows)):
                    for gc in range(gc_start, min(gc_end, grid_cols)):
                        total += 1
                        try:
                            active += sample_fn(gr % grid_rows, gc % grid_cols)
                        except (IndexError, KeyError):
                            pass

                if total > 0:
                    density = active / total
                else:
                    density = 0.0

                # Pick glyph
                if density <= 0:
                    gi = 0
                elif density <= 0.2:
                    gi = 1
                elif density <= 0.45:
                    gi = 2
                elif density <= 0.7:
                    gi = 3
                else:
                    gi = 4
                ch = MINI_GLYPHS[gi]

                # Color based on density
                if density > 0.5:
                    attr = curses.color_pair(1) | curses.A_BOLD  # green bold
                elif density > 0.15:
                    attr = curses.color_pair(2)  # cyan
                elif density > 0:
                    attr = curses.color_pair(6) | curses.A_DIM  # dim
                else:
                    attr = curses.color_pair(0)

                # Highlight viewport rectangle (if zoomed in)
                if not full_view:
                    in_vp = (vp_r0 <= my < vp_r1 and vp_c0 <= mx < vp_c1)
                    on_vp_border = (in_vp and
                                    (my < vp_r0 + 1 or my >= vp_r1 - 1 or
                                     mx < vp_c0 + 1 or mx >= vp_c1 - 1))
                    if on_vp_border:
                        attr = curses.color_pair(3) | curses.A_BOLD  # yellow border
                        if gi == 0:
                            ch = "·"
                    elif in_vp and gi == 0:
                        ch = "·"
                        attr = curses.color_pair(3) | curses.A_DIM

                try:
                    self.stdscr.addstr(sy, sx, ch, attr)
                except curses.error:
                    pass

            # Right border
            try:
                self.stdscr.addstr(sy, start_x + map_w + 1, "│", border_attr)
            except curses.error:
                pass


    def _record_pop(self):
        self.pop_history.append(self.grid.population)


    def _scan_patterns(self):
        """Run pattern recognition on the current grid."""
        self.detected_patterns = scan_patterns(self.grid)
        self._pattern_scan_gen = self.grid.generation

    @staticmethod

    def _pattern_color(category: str) -> int:
        """Return curses color pair for a pattern category."""
        if category == "Still life":
            return curses.color_pair(30)
        if category == "Oscillator":
            return curses.color_pair(31)
        if category == "Spaceship":
            return curses.color_pair(32)
        return curses.color_pair(33)


    def _update_heatmap(self):
        """Increment heatmap counters for every currently alive cell."""
        cells = self.grid.cells
        hm = self.heatmap
        peak = self.heatmap_max
        for r in range(self.grid.rows):
            row_cells = cells[r]
            row_hm = hm[r]
            for c in range(self.grid.cols):
                if row_cells[c] > 0:
                    row_hm[c] += 1
                    if row_hm[c] > peak:
                        peak = row_hm[c]
        self.heatmap_max = peak


    def _rebuild_pattern_list(self):
        """Rebuild the combined pattern list from built-ins + blueprints."""
        self.pattern_list = sorted(set(PATTERNS.keys()) | set(self.blueprints.keys()))


    def _get_pattern(self, name: str) -> dict | None:
        """Get a pattern by name from built-ins or blueprints."""
        if name in PATTERNS:
            return PATTERNS[name]
        return self.blueprints.get(name)

    # ── Blueprint mode ──


    def _capture_blueprint(self):
        """Capture the selected region as a named blueprint pattern."""
        min_r, min_c, max_r, max_c = self._blueprint_region()
        # Collect alive cells in the region, normalised to (0,0) origin
        cells = []
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                gr = r % self.grid.rows
                gc = c % self.grid.cols
                if self.grid.cells[gr][gc] > 0:
                    cells.append((r - min_r, c - min_c))
        if not cells:
            self._flash("No alive cells in selection — blueprint not saved")
            self.blueprint_mode = False
            self.blueprint_anchor = None
            return
        width = max_c - min_c + 1
        height = max_r - min_r + 1
        self.blueprint_mode = False
        self.blueprint_anchor = None
        # Prompt for a name
        name = self._prompt_text(f"Blueprint name ({len(cells)} cells, {width}x{height})")
        if not name:
            self._flash("Blueprint cancelled")
            return
        # Sanitize name (lowercase, replace spaces with underscores)
        safe_name = name.strip().lower().replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        if not safe_name:
            self._flash("Invalid name")
            return
        # Don't overwrite built-in patterns
        if safe_name in PATTERNS:
            self._flash(f"Cannot overwrite built-in pattern '{safe_name}'")
            return
        desc = f"Custom blueprint ({len(cells)} cells, {width}x{height})"
        self.blueprints[safe_name] = {"description": desc, "cells": cells}
        _save_blueprints(self.blueprints)
        self._rebuild_pattern_list()
        self._flash(f"Saved blueprint: {safe_name}")


    def _stamp_blueprint(self, name: str):
        """Overlay a blueprint pattern centered on the current cursor."""
        pat = self._get_pattern(name)
        if not pat:
            self._flash(f"Unknown pattern: {name}")
            return
        max_r = max(r for r, c in pat["cells"]) if pat["cells"] else 0
        max_c = max(c for r, c in pat["cells"]) if pat["cells"] else 0
        off_r = self.cursor_r - max_r // 2
        off_c = self.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            gr = (r + off_r) % self.grid.rows
            gc = (c + off_c) % self.grid.cols
            self.grid.set_alive(gr, gc)
        self._flash(f"Stamped: {name}")


    def _delete_blueprint(self, name: str):
        """Delete a user-saved blueprint."""
        if name in self.blueprints:
            del self.blueprints[name]
            _save_blueprints(self.blueprints)
            self._rebuild_pattern_list()
            self._flash(f"Deleted blueprint: {name}")


    def _push_history(self):
        """Save the current grid state to the history buffer before advancing."""
        # If scrubbed back, truncate future history before pushing
        if self.timeline_pos is not None:
            self.history = self.history[:self.timeline_pos + 1]
            self.timeline_pos = None
        self.history.append((self.grid.to_dict(), len(self.pop_history)))
        # Enforce max size by trimming oldest entries
        if len(self.history) > self.history_max:
            self.history = self.history[-self.history_max:]


    def _rewind(self):
        """Restore the most recent state from the history buffer."""
        if not self.history:
            self._flash("No history to rewind")
            return
        # If live, start scrubbing from the end; if already scrubbed, go back one more
        if self.timeline_pos is None:
            self.timeline_pos = len(self.history) - 1
        else:
            if self.timeline_pos <= 0:
                self._flash("At oldest recorded state")
                return
            self.timeline_pos -= 1
        self._restore_timeline_pos()


    def _restore_timeline_pos(self):
        """Restore the grid state at the current timeline position."""
        grid_dict, pop_len = self.history[self.timeline_pos]
        self.grid.load_dict(grid_dict)
        self.pop_history = self.pop_history[:pop_len]
        self._reset_cycle_detection()
        self._flash(f"Gen {self.grid.generation}  ({self.timeline_pos + 1}/{len(self.history)})")


    def _scrub_back(self, steps: int = 10):
        """Scrub backward through the timeline by the given number of steps."""
        if not self.history:
            self._flash("No history to scrub")
            return
        if self.timeline_pos is None:
            self.timeline_pos = max(0, len(self.history) - steps)
        else:
            self.timeline_pos = max(0, self.timeline_pos - steps)
        self._restore_timeline_pos()


    def _scrub_forward(self, steps: int = 10):
        """Scrub forward through the timeline by the given number of steps."""
        if self.timeline_pos is None:
            self._flash("Already at latest state")
            return
        self.timeline_pos += steps
        if self.timeline_pos >= len(self.history):
            # Return to the latest recorded state
            self.timeline_pos = None
            grid_dict, pop_len = self.history[-1]
            self.grid.load_dict(grid_dict)
            self.pop_history = self.pop_history[:pop_len]
            self._reset_cycle_detection()
            self._flash(f"Latest → Gen {self.grid.generation} (press n/Space to continue)")
        else:
            self._restore_timeline_pos()


    def _add_bookmark(self):
        """Bookmark the current generation."""
        gen = self.grid.generation
        # Don't duplicate
        for bg, _, _ in self.bookmarks:
            if bg == gen:
                self._flash(f"Gen {gen} already bookmarked")
                return
        self.bookmarks.append((gen, self.grid.to_dict(), len(self.pop_history)))
        self.bookmarks.sort(key=lambda x: x[0])
        self._flash(f"★ Bookmarked Gen {gen}  ({len(self.bookmarks)} total)")


    def _jump_to_bookmark(self, idx: int):
        """Jump to a bookmarked state."""
        if idx < 0 or idx >= len(self.bookmarks):
            return
        gen, grid_dict, pop_len = self.bookmarks[idx]
        self.grid.load_dict(grid_dict)
        self.pop_history = self.pop_history[:pop_len]
        self.timeline_pos = None  # bookmarks jump to an independent snapshot
        self._reset_cycle_detection()
        self._flash(f"★ Jumped to bookmark Gen {gen}")


    def _reset_cycle_detection(self):
        """Reset cycle detection state (call when grid is modified externally)."""
        self.state_history.clear()
        self.cycle_detected = False


    def _check_cycle(self):
        """Check if the current grid state has been seen before. Auto-pauses on detection."""
        h = self.grid.state_hash()
        gen = self.grid.generation
        if h in self.state_history:
            period = gen - self.state_history[h]
            self.running = False
            self.cycle_detected = True
            if self.grid.population == 0:
                self._flash("Extinction detected — all cells dead")
            elif period == 1:
                self._flash("Still life detected")
            else:
                self._flash(f"Cycle detected (period {period})")
        else:
            self.state_history[h] = gen


    def run(self):
        _init_colors()
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(50)
        self._record_pop()
        # Seed initial state for cycle detection
        self.state_history[self.grid.state_hash()] = self.grid.generation

        while True:
            self._draw()
            # ── Screensaver overlay (drawn after sub-mode content) ──
            if self.screensaver_mode and self.screensaver_running and not self.screensaver_menu:
                _my, _mx = self.stdscr.getmaxyx()
                self._draw_screensaver(_my, _mx)
                self.stdscr.refresh()
            # ── Minimap overlay (drawn after mode-specific content, before next input) ──
            if self.show_minimap and not self._any_menu_open():
                _my, _mx = self.stdscr.getmaxyx()
                self._draw_minimap(_my, _mx)
                self.stdscr.refresh()

            key = self.stdscr.getch()

            # ── Minimap toggle (Tab key, global across all modes) ──
            if key == 9:  # Tab
                self.show_minimap = not self.show_minimap
                self._flash("Minimap ON" if self.show_minimap else "Minimap OFF")
                continue

            # ── Multiplayer network tick ──
            if self.mp_mode:
                self._mp_poll()
                if not self.mp_mode:
                    continue  # disconnected during poll
                if self.mp_phase == "lobby":
                    self._mp_lobby_tick()
                elif self.mp_phase == "planning":
                    self._mp_planning_tick()

            # ── Multiplayer input dispatch ──
            if self.mp_mode and self.mp_phase == "planning":
                self._handle_mp_planning_key(key)
                if self.draw_mode and key in (curses.KEY_UP, curses.KEY_DOWN,
                                               curses.KEY_LEFT, curses.KEY_RIGHT,
                                               ord("h"), ord("j"), ord("k"), ord("l")):
                    self._mp_apply_draw_mode()
                continue
            elif self.mp_mode and self.mp_phase == "running":
                self._handle_mp_running_key(key)
                # Simulation stepping (host-authoritative)
                if self.running:
                    delay = SPEEDS[self.speed_idx]
                    time.sleep(delay)
                    if self.mp_role == "host":
                        self._mp_sim_tick()
                continue
            elif self.mp_mode and self.mp_phase == "finished":
                self._handle_mp_finished_key(key)
                continue
            elif self.mp_mode and self.mp_phase == "lobby":
                # Lobby: only allow quit
                if key == ord("q"):
                    self._mp_exit()
                continue

            if self.screensaver_menu:
                if self._handle_screensaver_menu_key(key):
                    continue
            elif self.screensaver_mode and self.screensaver_running:
                if self._handle_screensaver_key(key):
                    self._screensaver_step()
                    continue

            if self.ep_menu:
                if self._handle_ep_menu_key(key):
                    continue
            elif self.ep_mode:
                if self._handle_ep_key(key):
                    if self.ep_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._ep_step()
                    continue

            if self.pexplorer_menu:
                if self._handle_pexplorer_menu_key(key):
                    continue
            elif self.pexplorer_mode:
                if self._handle_pexplorer_key(key):
                    if self.pexplorer_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._pexplorer_step()
                    continue

            if self.dashboard:
                if self._handle_dashboard_key(key):
                    continue
            if self.mode_browser:
                if self._handle_mode_browser_key(key):
                    continue
            elif self.puzzle_menu:
                if self._handle_puzzle_menu_key(key):
                    continue
            elif self.puzzle_mode and self.puzzle_phase == "planning":
                if self._handle_puzzle_planning_key(key):
                    continue
            elif self.puzzle_mode and self.puzzle_phase == "running":
                # Auto-step during running phase
                if key == 27:  # ESC to abort
                    self.running = False
                    self._puzzle_fail("Aborted by user.")
                elif self.running:
                    delay = SPEEDS[self.speed_idx]
                    time.sleep(delay)
                    self._puzzle_step()
                continue
            elif self.puzzle_mode and self.puzzle_phase in ("success", "fail"):
                if self._handle_puzzle_result_key(key):
                    continue
            elif self.wolfram_menu:
                if self._handle_wolfram_menu_key(key):
                    continue
            elif self.wolfram_mode:
                if self._handle_wolfram_key(key):
                    if self.wolfram_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._wolfram_step()
                    continue
            elif self.ant_menu:
                if self._handle_ant_menu_key(key):
                    continue
            elif self.ant_mode:
                if self._handle_ant_key(key):
                    if self.ant_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.ant_steps_per_frame):
                            self._ant_step()
                    continue
            elif self.ww_menu:
                if self._handle_ww_menu_key(key):
                    continue
            elif self.ww_mode:
                if self._handle_ww_key(key):
                    if self.ww_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._ww_step()
                    continue
            elif self.sand_menu:
                if self._handle_sand_menu_key(key):
                    continue
            elif self.sand_mode:
                if self._handle_sand_key(key):
                    if self.sand_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._sand_step()
                    continue
            elif self.rd_menu:
                if self._handle_rd_menu_key(key):
                    continue
            elif self.rd_mode:
                if self._handle_rd_key(key):
                    if self.rd_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.rd_steps_per_frame):
                            self._rd_step()
                    continue
            elif self.lenia_menu:
                if self._handle_lenia_menu_key(key):
                    continue
            elif self.lenia_mode:
                if self._handle_lenia_key(key):
                    if self.lenia_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.lenia_steps_per_frame):
                            self._lenia_step()
                    continue
            elif self.physarum_menu:
                if self._handle_physarum_menu_key(key):
                    continue
            elif self.physarum_mode:
                if self._handle_physarum_key(key):
                    if self.physarum_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.physarum_steps_per_frame):
                            self._physarum_step()
                    continue
            elif self.boids_menu:
                if self._handle_boids_menu_key(key):
                    continue
            elif self.boids_mode:
                if self._handle_boids_key(key):
                    if self.boids_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.boids_steps_per_frame):
                            self._boids_step()
                    continue
            elif self.plife_menu:
                if self._handle_plife_menu_key(key):
                    continue
            elif self.plife_mode:
                if self._handle_plife_key(key):
                    if self.plife_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.plife_steps_per_frame):
                            self._plife_step()
                    continue
            elif self.nbody_menu:
                if self._handle_nbody_menu_key(key):
                    continue
            elif self.nbody_mode:
                if self._handle_nbody_key(key):
                    if self.nbody_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.nbody_steps_per_frame):
                            self._nbody_step()
                    continue
            elif self.fluid_menu:
                if self._handle_fluid_menu_key(key):
                    continue
            elif self.fluid_mode:
                if self._handle_fluid_key(key):
                    if self.fluid_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.fluid_steps_per_frame):
                            self._fluid_step()
                    continue
            elif self.wfc_menu:
                if self._handle_wfc_menu_key(key):
                    continue
            elif self.wfc_mode:
                if self._handle_wfc_key(key):
                    if self.wfc_running and not self.wfc_complete and not self.wfc_contradiction:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.wfc_steps_per_frame):
                            self._wfc_step()
                    continue
            elif self.aco_menu:
                if self._handle_aco_menu_key(key):
                    continue
            elif self.aco_mode:
                if self._handle_aco_key(key):
                    if self.aco_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.aco_steps_per_frame):
                            self._aco_step()
                    continue
            elif self.maze_menu:
                if self._handle_maze_menu_key(key):
                    continue
            elif self.maze_mode:
                if self._handle_maze_key(key):
                    if self.maze_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.maze_steps_per_frame):
                            self._maze_step()
                    continue
            elif self.dla_menu:
                if self._handle_dla_menu_key(key):
                    continue
            elif self.dla_mode:
                if self._handle_dla_key(key):
                    if self.dla_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.dla_steps_per_frame):
                            self._dla_step()
                    continue
            elif self.sandpile_menu:
                if self._handle_sandpile_menu_key(key):
                    continue
            elif self.sandpile_mode:
                if self._handle_sandpile_key(key):
                    if self.sandpile_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.sandpile_steps_per_frame):
                            self._sandpile_step()
                    continue
            elif self.fire_menu:
                if self._handle_fire_menu_key(key):
                    continue
            elif self.fire_mode:
                if self._handle_fire_key(key):
                    if self.fire_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.fire_steps_per_frame):
                            self._fire_step()
                    continue
            elif self.sir_menu:
                if self._handle_sir_menu_key(key):
                    continue
            elif self.sir_mode:
                if self._handle_sir_key(key):
                    if self.sir_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.sir_steps_per_frame):
                            self._sir_step()
                    continue
            elif self.cyclic_menu:
                if self._handle_cyclic_menu_key(key):
                    continue
            elif self.cyclic_mode:
                if self._handle_cyclic_key(key):
                    if self.cyclic_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.cyclic_steps_per_frame):
                            self._cyclic_step()
                    continue
            elif self.ising_menu:
                if self._handle_ising_menu_key(key):
                    continue
            elif self.ising_mode:
                if self._handle_ising_key(key):
                    if self.ising_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.ising_steps_per_frame):
                            self._ising_step()
                    continue
            elif self.hodge_menu:
                if self._handle_hodge_menu_key(key):
                    continue
            elif self.hodge_mode:
                if self._handle_hodge_key(key):
                    if self.hodge_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.hodge_steps_per_frame):
                            self._hodge_step()
                    continue
            elif self.lv_menu:
                if self._handle_lv_menu_key(key):
                    continue
            elif self.lv_mode:
                if self._handle_lv_key(key):
                    if self.lv_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.lv_steps_per_frame):
                            self._lv_step()
                    continue
            elif self.schelling_menu:
                if self._handle_schelling_menu_key(key):
                    continue
            elif self.schelling_mode:
                if self._handle_schelling_key(key):
                    if self.schelling_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.schelling_steps_per_frame):
                            self._schelling_step()
                    continue
            elif self.spd_menu:
                if self._handle_spd_menu_key(key):
                    continue
            elif self.spd_mode:
                if self._handle_spd_key(key):
                    if self.spd_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.spd_steps_per_frame):
                            self._spd_step()
                    continue
            elif self.turmite_menu:
                if self._handle_turmite_menu_key(key):
                    continue
            elif self.turmite_mode:
                if self._handle_turmite_key(key):
                    if self.turmite_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.turmite_steps_per_frame):
                            self._turmite_step()
                    continue
            elif self.lightning_menu:
                if self._handle_lightning_menu_key(key):
                    continue
            elif self.lightning_mode:
                if self._handle_lightning_key(key):
                    if self.lightning_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.lightning_steps_per_frame):
                            self._lightning_step()
                    continue
            elif self.erosion_menu:
                if self._handle_erosion_menu_key(key):
                    continue
            elif self.erosion_mode:
                if self._handle_erosion_key(key):
                    if self.erosion_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.erosion_steps_per_frame):
                            self._erosion_step()
                    continue
            elif self.voronoi_menu:
                if self._handle_voronoi_menu_key(key):
                    continue
            elif self.voronoi_mode:
                if self._handle_voronoi_key(key):
                    if self.voronoi_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.voronoi_steps_per_frame):
                            self._voronoi_step()
                    continue
            elif self.rps_menu:
                if self._handle_rps_menu_key(key):
                    continue
            elif self.rps_mode:
                if self._handle_rps_key(key):
                    if self.rps_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.rps_steps_per_frame):
                            self._rps_step()
                    continue
            elif self.wave_menu:
                if self._handle_wave_menu_key(key):
                    continue
            elif self.wave_mode:
                if self._handle_wave_key(key):
                    if self.wave_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.wave_steps_per_frame):
                            self._wave_step()
                    continue
            elif self.kuramoto_menu:
                if self._handle_kuramoto_menu_key(key):
                    continue
            elif self.kuramoto_mode:
                if self._handle_kuramoto_key(key):
                    if self.kuramoto_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.kuramoto_steps_per_frame):
                            self._kuramoto_step()
                    continue
            elif self.snn_menu:
                if self._handle_snn_menu_key(key):
                    continue
            elif self.snn_mode:
                if self._handle_snn_key(key):
                    if self.snn_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.snn_steps_per_frame):
                            self._snn_step()
                    continue
            elif self.bz_menu:
                if self._handle_bz_menu_key(key):
                    continue
            elif self.bz_mode:
                if self._handle_bz_key(key):
                    if self.bz_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.bz_steps_per_frame):
                            self._bz_step()
                    continue
            elif self.chemo_menu:
                if self._handle_chemo_menu_key(key):
                    continue
            elif self.chemo_mode:
                if self._handle_chemo_key(key):
                    if self.chemo_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.chemo_steps_per_frame):
                            self._chemo_step()
                    continue
            elif self.mhd_menu:
                if self._handle_mhd_menu_key(key):
                    continue
            elif self.mhd_mode:
                if self._handle_mhd_key(key):
                    if self.mhd_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.mhd_steps_per_frame):
                            self._mhd_step()
                    continue
            elif self.attractor_menu:
                if self._handle_attractor_menu_key(key):
                    continue
            elif self.attractor_mode:
                if self._handle_attractor_key(key):
                    if self.attractor_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.attractor_steps_per_frame):
                            self._attractor_step()
                    continue
            elif self.qwalk_menu:
                if self._handle_qwalk_menu_key(key):
                    continue
            elif self.qwalk_mode:
                if self._handle_qwalk_key(key):
                    if self.qwalk_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.qwalk_steps_per_frame):
                            self._qwalk_step()
                    continue
            elif self.terrain_menu:
                if self._handle_terrain_menu_key(key):
                    continue
            elif self.terrain_mode:
                if self._handle_terrain_key(key):
                    if self.terrain_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.terrain_steps_per_frame):
                            self._terrain_step()
                    continue
            elif self.flythrough_menu:
                if self._handle_flythrough_menu_key(key):
                    continue
            elif self.flythrough_mode:
                if self._handle_flythrough_key(key):
                    if self.flythrough_running:
                        self._flythrough_step()
                    continue
            elif self.raymarch_menu:
                if self._handle_raymarch_menu_key(key):
                    continue
            elif self.raymarch_mode:
                if self._handle_raymarch_key(key):
                    if self.raymarch_running:
                        self._raymarch_step()
                    continue
            elif self.shadertoy_menu:
                if self._handle_shadertoy_menu_key(key):
                    continue
            elif self.shadertoy_mode:
                if self._handle_shadertoy_key(key):
                    if self.shadertoy_running:
                        self._shadertoy_step()
                    continue
            elif self.musvis_menu:
                if self._handle_musvis_menu_key(key):
                    continue
            elif self.musvis_mode:
                if self._handle_musvis_key(key):
                    if self.musvis_running:
                        self._musvis_step()
                    continue
            elif self.alife_menu:
                if self._handle_alife_menu_key(key):
                    continue
            elif self.alife_mode:
                if self._handle_alife_key(key):
                    if self.alife_running:
                        self._alife_step()
                    continue
            elif self.doomrc_menu:
                if self._handle_doomrc_menu_key(key):
                    continue
            elif self.doomrc_mode:
                if self._handle_doomrc_key(key):
                    if self.doomrc_running:
                        self._doomrc_step()
                    continue
            elif self.tectonic_menu:
                if self._handle_tectonic_menu_key(key):
                    continue
            elif self.tectonic_mode:
                if self._handle_tectonic_key(key):
                    if self.tectonic_running:
                        self._tectonic_step()
                    continue
            elif self.weather_menu:
                if self._handle_weather_menu_key(key):
                    continue
            elif self.weather_mode:
                if self._handle_weather_key(key):
                    if self.weather_running:
                        self._weather_step()
                    continue
            elif self.ocean_menu:
                if self._handle_ocean_menu_key(key):
                    continue
            elif self.ocean_mode:
                if self._handle_ocean_key(key):
                    if self.ocean_running:
                        self._ocean_step()
                    continue
            elif self.volcano_menu:
                if self._handle_volcano_menu_key(key):
                    continue
            elif self.volcano_mode:
                if self._handle_volcano_key(key):
                    if self.volcano_running:
                        self._volcano_step()
                    continue
            elif self.blackhole_menu:
                if self._handle_blackhole_menu_key(key):
                    continue
            elif self.blackhole_mode:
                if self._handle_blackhole_key(key):
                    if self.blackhole_running:
                        self._blackhole_step()
                    continue
            elif self.orrery_menu:
                if self._handle_orrery_menu_key(key):
                    continue
            elif self.orrery_mode:
                if self._handle_orrery_key(key):
                    if self.orrery_running:
                        self._orrery_step()
                    continue
            elif self.aurora_menu:
                if self._handle_aurora_menu_key(key):
                    continue
            elif self.aurora_mode:
                if self._handle_aurora_key(key):
                    if self.aurora_running:
                        self._aurora_step()
                    continue
            elif self.pwave_menu:
                if self._handle_pwave_menu_key(key):
                    continue
            elif self.pwave_mode:
                if self._handle_pwave_key(key):
                    if self.pwave_running:
                        for _ in range(self.pwave_speed):
                            self._pwave_step()
                    continue
            elif self.tornado_menu:
                if self._handle_tornado_menu_key(key):
                    continue
            elif self.tornado_mode:
                if self._handle_tornado_key(key):
                    if self.tornado_running:
                        for _ in range(self.tornado_speed):
                            self._tornado_step()
                    continue
            elif self.sortvis_menu:
                if self._handle_sortvis_menu_key(key):
                    continue
            elif self.sortvis_mode:
                if self._handle_sortvis_key(key):
                    if self.sortvis_running and not self.sortvis_done:
                        for _ in range(self.sortvis_speed):
                            self._sortvis_step()
                    continue
            elif self.fourier_menu:
                if self._handle_fourier_menu_key(key):
                    continue
            elif self.fourier_mode:
                if self._handle_fourier_key(key):
                    if self.fourier_running:
                        for _ in range(self.fourier_speed):
                            self._fourier_step()
                    continue
            elif self.snowfall_menu:
                if self._handle_snowfall_menu_key(key):
                    continue
            elif self.snowfall_mode:
                if self._handle_snowfall_key(key):
                    if self.snowfall_running:
                        for _ in range(self.snowfall_speed):
                            self._snowfall_step()
                    continue
            elif self.matrix_menu:
                if self._handle_matrix_menu_key(key):
                    continue
            elif self.matrix_mode:
                if self._handle_matrix_key(key):
                    if self.matrix_running:
                        for _ in range(self.matrix_speed):
                            self._matrix_step()
                    continue
            elif self.fluidrope_menu:
                if self._handle_fluidrope_menu_key(key):
                    continue
            elif self.fluidrope_mode:
                if self._handle_fluidrope_key(key):
                    if self.fluidrope_running:
                        for _ in range(self.fluidrope_speed):
                            self._fluidrope_step()
                    continue
            elif self.lissajous_menu:
                if self._handle_lissajous_menu_key(key):
                    continue
            elif self.lissajous_mode:
                if self._handle_lissajous_key(key):
                    if self.lissajous_running:
                        for _ in range(self.lissajous_speed):
                            self._lissajous_step()
                    continue
            elif self.mazesolver_menu:
                if self._handle_mazesolver_menu_key(key):
                    continue
            elif self.mazesolver_mode:
                if self._handle_mazesolver_key(key):
                    if self.mazesolver_running and not self.mazesolver_solve_done:
                        for _ in range(self.mazesolver_speed):
                            self._mazesolver_step()
                    continue
            elif self.antfarm_menu:
                if self._handle_antfarm_menu_key(key):
                    continue
            elif self.antfarm_mode:
                if self._handle_antfarm_key(key):
                    if self.antfarm_running:
                        for _ in range(self.antfarm_speed):
                            self._antfarm_step()
                    continue
            elif self.kaleido_menu:
                if self._handle_kaleido_menu_key(key):
                    continue
            elif self.kaleido_mode:
                if self._handle_kaleido_key(key):
                    if self.kaleido_running:
                        for _ in range(self.kaleido_speed):
                            self._kaleido_step()
                    continue
            elif self.aquarium_menu:
                if self._handle_aquarium_menu_key(key):
                    continue
            elif self.aquarium_mode:
                if self._handle_aquarium_key(key):
                    if self.aquarium_running:
                        for _ in range(self.aquarium_speed):
                            self._aquarium_step()
                    continue
            elif self.collider_menu:
                if self._handle_collider_menu_key(key):
                    continue
            elif self.collider_mode:
                if self._handle_collider_key(key):
                    if self.collider_running:
                        for _ in range(self.collider_speed):
                            self._collider_step()
                    continue
            elif self.dnahelix_menu:
                if self._handle_dnahelix_menu_key(key):
                    continue
            elif self.dnahelix_mode:
                if self._handle_dnahelix_key(key):
                    if self.dnahelix_running and not self.dnahelix_solved:
                        for _ in range(self.dnahelix_speed):
                            self._dnahelix_step()
                    continue
            elif self.gol3d_menu:
                if self._handle_gol3d_menu_key(key):
                    continue
            elif self.gol3d_mode:
                if self._handle_gol3d_key(key):
                    if self.gol3d_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._gol3d_step()
                    continue
            elif self.smokefire_menu:
                if self._handle_smokefire_menu_key(key):
                    continue
            elif self.smokefire_mode:
                if self._handle_smokefire_key(key):
                    if self.smokefire_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.smokefire_steps_per_frame):
                            self._smokefire_step()
                    continue
            elif self.cloth_menu:
                if self._handle_cloth_menu_key(key):
                    continue
            elif self.cloth_mode:
                if self._handle_cloth_key(key):
                    if self.cloth_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.cloth_steps_per_frame):
                            self._cloth_step()
                    continue
            elif self.galaxy_menu:
                if self._handle_galaxy_menu_key(key):
                    continue
            elif self.galaxy_mode:
                if self._handle_galaxy_key(key):
                    if self.galaxy_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.galaxy_steps_per_frame):
                            self._galaxy_step()
                    continue
            elif self.lsystem_menu:
                if self._handle_lsystem_menu_key(key):
                    continue
            elif self.lsystem_mode:
                if self._handle_lsystem_key(key):
                    if self.lsystem_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._lsystem_step()
                    continue
            elif self.fireworks_menu:
                if self._handle_fireworks_menu_key(key):
                    continue
            elif self.fireworks_mode:
                if self._handle_fireworks_key(key):
                    if self.fireworks_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.fireworks_steps_per_frame):
                            self._fireworks_step()
                    continue
            elif self.fractal_menu:
                if self._handle_fractal_menu_key(key):
                    continue
            elif self.fractal_mode:
                if self._handle_fractal_key(key):
                    continue
            elif self.ns_menu:
                if self._handle_ns_menu_key(key):
                    continue
            elif self.ns_mode:
                if self._handle_ns_key(key):
                    if self.ns_running:
                        for _ in range(self.ns_steps_per_frame):
                            self._ns_step()
                    continue
            elif self.dpend_menu:
                if self._handle_dpend_menu_key(key):
                    continue
            elif self.dpend_mode:
                if self._handle_dpend_key(key):
                    if self.dpend_running:
                        for _ in range(self.dpend_steps_per_frame):
                            self._dpend_step()
                    continue
            elif self.chladni_menu:
                if self._handle_chladni_menu_key(key):
                    continue
            elif self.chladni_mode:
                if self._handle_chladni_key(key):
                    if self.chladni_running:
                        for _ in range(self.chladni_steps_per_frame):
                            self._chladni_step()
                    continue
            elif self.ifs_menu:
                if self._handle_ifs_menu_key(key):
                    continue
            elif self.ifs_mode:
                if self._handle_ifs_key(key):
                    if self.ifs_running:
                        for _ in range(self.ifs_steps_per_frame):
                            self._ifs_step()
                    continue
            elif self.cpm_menu:
                if self._handle_cpm_menu_key(key):
                    continue
            elif self.cpm_mode:
                if self._handle_cpm_key(key):
                    if self.cpm_running:
                        for _ in range(self.cpm_steps_per_frame):
                            self._cpm_step()
                    continue
            elif self.magfield_menu:
                if self._handle_magfield_menu_key(key):
                    continue
            elif self.magfield_mode:
                if self._handle_magfield_key(key):
                    if self.magfield_running:
                        for _ in range(self.magfield_steps_per_frame):
                            self._magfield_step()
                    continue
            elif self.fdtd_menu:
                if self._handle_fdtd_menu_key(key):
                    continue
            elif self.fdtd_mode:
                if self._handle_fdtd_key(key):
                    if self.fdtd_running:
                        for _ in range(self.fdtd_steps_per_frame):
                            self._fdtd_step()
                    continue
            elif self.sph_menu:
                if self._handle_sph_menu_key(key):
                    continue
            elif self.sph_mode:
                if self._handle_sph_key(key):
                    if self.sph_running:
                        for _ in range(self.sph_steps_per_frame):
                            self._sph_step()
                    continue
            elif self.rbc_menu:
                if self._handle_rbc_menu_key(key):
                    continue
            elif self.rbc_mode:
                if self._handle_rbc_key(key):
                    if self.rbc_running:
                        for _ in range(self.rbc_steps_per_frame):
                            self._rbc_step()
                    continue
            elif self.traffic_menu:
                if self._handle_traffic_menu_key(key):
                    continue
            elif self.traffic_mode:
                if self._handle_traffic_key(key):
                    if self.traffic_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.traffic_steps_per_frame):
                            self._traffic_step()
                    continue
            elif self.snowflake_menu:
                if self._handle_snowflake_menu_key(key):
                    continue
            elif self.snowflake_mode:
                if self._handle_snowflake_key(key):
                    if self.snowflake_running:
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        for _ in range(self.snowflake_steps_per_frame):
                            self._snowflake_step()
                    continue
            elif self.evo_menu:
                if self._handle_evo_menu_key(key):
                    continue
            elif self.evo_mode:
                if self._handle_evo_key(key):
                    # Step evolution simulation
                    if self.running and self.evo_phase == "simulating":
                        delay = SPEEDS[self.speed_idx]
                        time.sleep(delay)
                        self._evo_step_sim()
                    continue
            elif self.blueprint_menu:
                if self._handle_blueprint_menu_key(key):
                    continue
            elif self.blueprint_mode:
                if self._handle_blueprint_mode_key(key):
                    continue
            elif self.bookmark_menu:
                if self._handle_bookmark_menu_key(key):
                    continue
            elif self.race_rule_menu:
                if self._handle_race_rule_menu_key(key):
                    continue
            elif self.compare_rule_menu:
                if self._handle_compare_rule_menu_key(key):
                    continue
            elif self.rule_menu:
                if self._handle_rule_menu_key(key):
                    continue
            elif self.pattern_menu or self.stamp_menu:
                if self._handle_menu_key(key):
                    continue
            elif self.show_help:
                if key != -1:
                    self.show_help = False
                continue
            else:
                if self._handle_key(key):
                    continue

            if self.running:
                delay = SPEEDS[self.speed_idx]
                time.sleep(delay)
                self._push_history()
                self.grid.step()
                self._update_heatmap()
                self._record_pop()
                self._check_cycle()
                if self.pattern_search_mode:
                    self._scan_patterns()
                # Step the second grid in comparison mode
                if self.compare_mode and self.grid2:
                    self.grid2.step()
                    self.pop_history2.append(self.grid2.population)
                # Step all race grids
                if self.race_mode and self.race_grids and not self.race_finished:
                    self._step_race()
                # Capture frame for GIF recording
                if self.recording:
                    self._capture_recording_frame()
                # Play sonification
                if self.sound_engine.enabled:
                    self.sound_engine.play_grid(self.grid, delay)

    # ── Key handling ──


    def _handle_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == ord("q"):
            sys.exit(0)
        if key == ord("?") or key == ord("h"):
            self.show_help = True
            return True
        if key == ord("m"):
            self._dashboard_init()
            return True
        if key == ord(" "):
            self.running = not self.running
            if self.running and self.cycle_detected:
                self._reset_cycle_detection()
            self._flash("Playing" if self.running else "Paused")
            return True
        if key == ord("n") or key == ord("."):
            self.running = False
            self._push_history()
            self.grid.step()
            self._update_heatmap()
            self._record_pop()
            self._check_cycle()
            if self.pattern_search_mode:
                self._scan_patterns()
            if self.compare_mode and self.grid2:
                self.grid2.step()
                self.pop_history2.append(self.grid2.population)
            if self.race_mode and self.race_grids and not self.race_finished:
                self._step_race()
            if self.recording:
                self._capture_recording_frame()
            if self.sound_engine.enabled:
                self.sound_engine.play_grid(self.grid, SPEEDS[self.speed_idx])
            return True
        if key == ord("u"):
            self.running = False
            self._rewind()
            return True
        if key == ord("["):
            self.running = False
            self._scrub_back(10)
            return True
        if key == ord("]"):
            self.running = False
            self._scrub_forward(10)
            return True
        if key == ord("b"):
            self._add_bookmark()
            return True
        if key == ord("B"):
            if self.bookmarks:
                self.bookmark_menu = True
                self.bookmark_sel = 0
            else:
                self._flash("No bookmarks yet (press b to bookmark)")
            return True
        if key == ord("+") or key == ord("="):
            # Zoom in (decrease zoom level)
            idx = ZOOM_LEVELS.index(self.zoom_level)
            if idx > 0:
                self.zoom_level = ZOOM_LEVELS[idx - 1]
            self._flash(f"Zoom: {self.zoom_level}:1" if self.zoom_level > 1 else "Zoom: 1:1 (normal)")
            return True
        if key == ord("-") or key == ord("_"):
            # Zoom out (increase zoom level)
            idx = ZOOM_LEVELS.index(self.zoom_level)
            if idx < len(ZOOM_LEVELS) - 1:
                self.zoom_level = ZOOM_LEVELS[idx + 1]
            self._flash(f"Zoom: {self.zoom_level}:1" if self.zoom_level > 1 else "Zoom: 1:1 (normal)")
            return True
        if key == ord("0"):
            self.zoom_level = 1
            self._flash("Zoom: 1:1 (normal)")
            return True
        if key == ord(">"):
            if self.speed_idx < len(SPEEDS) - 1:
                self.speed_idx += 1
            self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
            return True
        if key == ord("<"):
            if self.speed_idx > 0:
                self.speed_idx -= 1
            self._flash(f"Speed: {SPEED_LABELS[self.speed_idx]}")
            return True
        if key == ord("c"):
            self.grid.clear()
            self.running = False
            self.pop_history.clear()
            self._record_pop()
            self._reset_cycle_detection()
            self.heatmap = [[0] * self.grid.cols for _ in range(self.grid.rows)]
            self.heatmap_max = 0
            self._flash("Cleared")
            return True
        if key == ord("r"):
            self.grid.clear()
            self.running = False
            import random
            for r in range(self.grid.rows):
                for c in range(self.grid.cols):
                    if random.random() < 0.2:
                        self.grid.set_alive(r, c)
            self.pop_history.clear()
            self._record_pop()
            self._reset_cycle_detection()
            self.heatmap = [[0] * self.grid.cols for _ in range(self.grid.rows)]
            self.heatmap_max = 0
            self._flash("Randomised")
            return True
        if key == ord("R"):
            self.rule_menu = True
            return True
        if key == ord("p"):
            self.pattern_menu = True
            return True
        if key == ord("t"):
            self.stamp_menu = True
            return True
        if key == ord("s"):
            self._save_state()
            return True
        if key == ord("o"):
            self._load_state()
            return True
        if key == ord("i"):
            self._import_rle()
            return True
        if key == ord("H"):
            self.heatmap_mode = not self.heatmap_mode
            if self.heatmap_mode:
                self._flash("Heatmap ON (shows cumulative cell activity)")
            else:
                self._flash("Heatmap OFF")
            return True
        if key == ord("I"):
            self.iso_mode = not self.iso_mode
            if self.iso_mode:
                self._flash("3D Isometric view ON (cell height = age)")
            else:
                self._flash("3D Isometric view OFF")
            return True
        if key == ord("F"):
            if self.fluid_mode:
                self._exit_fluid_mode()
            else:
                self._enter_fluid_mode()
            return True
        if key == ord("X"):
            if self.wfc_mode:
                self._exit_wfc_mode()
            else:
                self._enter_wfc_mode()
            return True
        if key == ord("A"):
            if self.aco_mode:
                self._exit_aco_mode()
            else:
                self._enter_aco_mode()
            return True
        if key == ord("L"):
            if self.maze_mode:
                self._exit_maze_mode()
            else:
                self._enter_maze_mode()
            return True
        if key == ord("f") and not self.draw_mode:
            self.pattern_search_mode = not self.pattern_search_mode
            if self.pattern_search_mode:
                self._scan_patterns()
                n = len(self.detected_patterns)
                self._flash(f"Pattern search ON — {n} pattern{'s' if n != 1 else ''} found")
            else:
                self.detected_patterns.clear()
                self._flash("Pattern search OFF")
            return True
        if key == ord("V"):
            if self.compare_mode:
                self._exit_compare_mode()
            else:
                self._enter_compare_mode()
            return True
        if key == ord("Z"):
            if self.race_mode:
                self._exit_race_mode()
            else:
                self._enter_race_mode()
            return True
        if key == ord("W"):
            self._enter_blueprint_mode()
            return True
        if key == ord("T"):
            if self.traffic_mode:
                self._exit_traffic_mode()
            else:
                self._enter_traffic_mode()
            return True
        if key == ord("C"):
            if self.puzzle_mode:
                self._exit_puzzle_mode()
            else:
                self._enter_puzzle_mode()
            return True
        if key == ord("E"):
            if self.evo_mode:
                self._exit_evo_mode()
            else:
                self._enter_evo_mode()
            return True
        if key == ord("G"):
            self._toggle_recording()
            return True
        if key == ord("1"):
            if self.wolfram_mode:
                self._exit_wolfram_mode()
            else:
                self._enter_wolfram_mode()
            return True
        if key == ord("2"):
            if self.ant_mode:
                self._exit_ant_mode()
            else:
                self._enter_ant_mode()
            return True
        if key == ord("3"):
            self.hex_mode = not self.hex_mode
            self.grid.hex_mode = self.hex_mode
            if self.hex_mode:
                # Switch to B2/S3,4 — a common hex life rule that produces interesting patterns
                self.grid.birth = {2}
                self.grid.survival = {3, 4}
                self._flash("Hex grid ON (6 neighbors, rule B2/S34) — press R to change rule")
            else:
                # Restore standard Conway B3/S23
                self.grid.birth = {3}
                self.grid.survival = {2, 3}
                self._flash("Hex grid OFF (8 neighbors, rule B3/S23)")
            return True
        if key == ord("4"):
            if self.ww_mode:
                self._exit_ww_mode()
            else:
                self._enter_ww_mode()
            return True
        if key == ord("5"):
            if self.sand_mode:
                self._exit_sand_mode()
            else:
                self._enter_sand_mode()
            return True
        if key == ord("6"):
            if self.rd_mode:
                self._exit_rd_mode()
            else:
                self._enter_rd_mode()
            return True
        if key == ord("7"):
            if self.lenia_mode:
                self._exit_lenia_mode()
            else:
                self._enter_lenia_mode()
            return True
        if key == ord("8"):
            if self.physarum_mode:
                self._exit_physarum_mode()
            else:
                self._enter_physarum_mode()
            return True
        if key == ord("9"):
            if self.boids_mode:
                self._exit_boids_mode()
            else:
                self._enter_boids_mode()
            return True
        if key == ord("0"):
            if self.plife_mode:
                self._exit_plife_mode()
            else:
                self._enter_plife_mode()
            return True
        if key == ord("Y"):
            if self.nbody_mode:
                self._exit_nbody_mode()
            else:
                self._enter_nbody_mode()
            return True
        if key == ord("D"):
            if self.dla_mode:
                self._exit_dla_mode()
            else:
                self._enter_dla_mode()
            return True
        if key == ord("E"):
            if self.sir_mode:
                self._exit_sir_mode()
            else:
                self._enter_sir_mode()
            return True
        if key == ord("P"):
            if self.sandpile_mode:
                self._exit_sandpile_mode()
            else:
                self._enter_sandpile_mode()
            return True
        if key == ord("O"):
            if self.fire_mode:
                self._exit_fire_mode()
            else:
                self._enter_fire_mode()
            return True
        if key == ord("U"):
            if self.cyclic_mode:
                self._exit_cyclic_mode()
            else:
                self._enter_cyclic_mode()
            return True
        if key == ord("~"):
            if self.hodge_mode:
                self._exit_hodge_mode()
            else:
                self._enter_hodge_mode()
            return True
        if key == ord("#"):
            if self.ising_mode:
                self._exit_ising_mode()
            else:
                self._enter_ising_mode()
            return True
        if key == ord("*"):
            if self.snowflake_mode:
                self._exit_snowflake_mode()
            else:
                self._enter_snowflake_mode()
            return True
        if key == ord("J"):
            if self.lv_mode:
                self._exit_lv_mode()
            else:
                self._enter_lv_mode()
            return True
        if key == ord("K"):
            if self.schelling_mode:
                self._exit_schelling_mode()
            else:
                self._enter_schelling_mode()
            return True
        if key == ord("@"):
            if self.spd_mode:
                self._exit_spd_mode()
            else:
                self._enter_spd_mode()
            return True
        if key == ord("Q"):
            if self.turmite_mode:
                self._exit_turmite_mode()
            else:
                self._enter_turmite_mode()
            return True
        if key == ord("^"):
            if self.lightning_mode:
                self._exit_lightning_mode()
            else:
                self._enter_lightning_mode()
            return True
        if key == ord("$"):
            if self.erosion_mode:
                self._exit_erosion_mode()
            else:
                self._enter_erosion_mode()
            return True
        if key == ord("%"):
            if self.voronoi_mode:
                self._exit_voronoi_mode()
            else:
                self._enter_voronoi_mode()
            return True
        if key == ord("&"):
            if self.rps_mode:
                self._exit_rps_mode()
            else:
                self._enter_rps_mode()
            return True
        if key == ord("!"):
            if self.wave_mode:
                self._exit_wave_mode()
            else:
                self._enter_wave_mode()
            return True
        if key == ord("("):
            if self.kuramoto_mode:
                self._exit_kuramoto_mode()
            else:
                self._enter_kuramoto_mode()
            return True
        if key == ord(")"):
            if self.snn_mode:
                self._exit_snn_mode()
            else:
                self._enter_snn_mode()
            return True
        if key == ord("`"):
            if self.bz_mode:
                self._exit_bz_mode()
            else:
                self._enter_bz_mode()
            return True
        if key == ord("{"):
            if self.chemo_mode:
                self._exit_chemo_mode()
            else:
                self._enter_chemo_mode()
            return True
        if key == ord("}"):
            if self.mhd_mode:
                self._exit_mhd_mode()
            else:
                self._enter_mhd_mode()
            return True
        if key == ord("|"):
            if self.attractor_mode:
                self._exit_attractor_mode()
            else:
                self._enter_attractor_mode()
            return True
        if key == ord("^"):
            if self.qwalk_mode:
                self._exit_qwalk_mode()
            else:
                self._enter_qwalk_mode()
            return True
        if key == ord(";"):
            if self.terrain_mode:
                self._exit_terrain_mode()
            else:
                self._enter_terrain_mode()
            return True
        if key == ord("\\"):
            if self.smokefire_mode:
                self._exit_smokefire_mode()
            else:
                self._enter_smokefire_mode()
            return True
        if key == ord("'"):
            if self.cloth_mode:
                self._exit_cloth_mode()
            else:
                self._enter_cloth_mode()
            return True
        if key == ord('"'):
            if self.galaxy_mode:
                self._exit_galaxy_mode()
            else:
                self._enter_galaxy_mode()
            return True
        if key == ord("/"):
            if self.lsystem_mode:
                self._exit_lsystem_mode()
            else:
                self._enter_lsystem_mode()
            return True
        if key == 6:  # Ctrl+F — Fireworks
            if self.fireworks_mode:
                self._exit_fireworks_mode()
            else:
                self._enter_fireworks_mode()
            return True
        if key == 2:  # Ctrl+B — Fractal Explorer
            if self.fractal_mode:
                self._exit_fractal_mode()
            else:
                self._enter_fractal_mode()
            return True
        if key == 4:  # Ctrl+D — Navier-Stokes Fluid Dynamics
            if self.ns_mode:
                self._exit_ns_mode()
            else:
                self._enter_ns_mode()
            return True
        if key == 16:  # Ctrl+P — Double Pendulum
            if self.dpend_mode:
                self._exit_dpend_mode()
            else:
                self._enter_dpend_mode()
            return True
        if key == 18:  # Ctrl+R — Rayleigh-Bénard Convection
            if self.rbc_mode:
                self._exit_rbc_mode()
            else:
                self._enter_rbc_mode()
            return True
        if key == 12:  # Ctrl+L — Chladni Plate Vibration Patterns
            if self.chladni_mode:
                self._exit_chladni_mode()
            else:
                self._enter_chladni_mode()
            return True
        if key == 20:  # Ctrl+T — Cellular Potts Model
            if self.cpm_mode:
                self._exit_cpm_mode()
            else:
                self._enter_cpm_mode()
            return True
        if key == 7:  # Ctrl+G — Chaos Game / IFS Fractal
            if self.ifs_mode:
                self._exit_ifs_mode()
            else:
                self._enter_ifs_mode()
            return True
        if key == 14:  # Ctrl+N — Magnetic Field Lines
            if self.magfield_mode:
                self._exit_magfield_mode()
            else:
                self._enter_magfield_mode()
            return True
        if key == 5:  # Ctrl+E — FDTD Electromagnetic Wave Propagation
            if self.fdtd_mode:
                self._exit_fdtd_mode()
            else:
                self._enter_fdtd_mode()
            return True
        if key == 1:  # Ctrl+A — Smoothed Particle Hydrodynamics
            if self.sph_mode:
                self._exit_sph_mode()
            else:
                self._enter_sph_mode()
            return True
        if key == 25:  # Ctrl+Y — 3D Terrain Flythrough
            if self.flythrough_mode:
                self._exit_flythrough_mode()
            else:
                self._enter_flythrough_mode()
            return True
        if key == ord("M"):
            on = self.sound_engine.toggle()
            if on:
                if self.sound_engine._play_cmd is None:
                    self.sound_engine.enabled = False
                    self._flash("Sound OFF — no audio player found (need aplay/paplay/afplay)")
                else:
                    self._flash("♪ Sound ON (pentatonic synth)")
            else:
                self._flash("Sound OFF")
            return True
        if key == ord("N"):
            # Multiplayer: prompt for host or connect
            choice = self._prompt_text("Multiplayer: [H]ost or [C]onnect?")
            if choice and choice.upper().startswith("H"):
                self._mp_enter_host()
            elif choice and choice.upper().startswith("C"):
                self._mp_enter_client()
            return True
        if key == ord("e"):
            self.grid.toggle(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()
            if self.pattern_search_mode:
                self._scan_patterns()
            return True
        if key == ord("d"):
            if self.draw_mode == "draw":
                self.draw_mode = None
                self._flash("Draw mode OFF")
            else:
                self.draw_mode = "draw"
                self.grid.set_alive(self.cursor_r, self.cursor_c)
                self._reset_cycle_detection()
                self._flash("Draw mode ON (move to paint, d/Esc=exit)")
            return True
        if key == ord("x"):
            if self.draw_mode == "erase":
                self.draw_mode = None
                self._flash("Erase mode OFF")
            else:
                self.draw_mode = "erase"
                self.grid.set_dead(self.cursor_r, self.cursor_c)
                self._reset_cycle_detection()
                self._flash("Erase mode ON (move to erase, x/Esc=exit)")
            return True
        if key == 27:  # ESC
            if self.draw_mode:
                self.draw_mode = None
                self._flash("Draw/erase mode OFF")
            return True
        # Arrow keys / vim keys for cursor movement
        if key in (curses.KEY_UP, ord("k")):
            self.cursor_r = (self.cursor_r - 1) % self.grid.rows
            self._apply_draw_mode()
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.cursor_r = (self.cursor_r + 1) % self.grid.rows
            self._apply_draw_mode()
            return True
        if key in (curses.KEY_LEFT, ord("l") - 4):  # 'h' already used for help
            self.cursor_c = (self.cursor_c - 1) % self.grid.cols
            self._apply_draw_mode()
            return True
        if key in (curses.KEY_RIGHT, ord("l")):
            self.cursor_c = (self.cursor_c + 1) % self.grid.cols
            self._apply_draw_mode()
            return True
        return True


    def _apply_draw_mode(self):
        """If in draw/erase mode, paint or erase the cell under the cursor."""
        if self.draw_mode == "draw":
            self.grid.set_alive(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()
            if self.pattern_search_mode:
                self._scan_patterns()
        elif self.draw_mode == "erase":
            self.grid.set_dead(self.cursor_r, self.cursor_c)
            self._reset_cycle_detection()
            if self.pattern_search_mode:
                self._scan_patterns()


    def _toggle_recording(self):
        """Toggle GIF recording on/off."""
        if self.recording:
            self.recording = False
            if self.recorded_frames:
                self._export_gif()
            else:
                self._flash("Recording cancelled (no frames captured)")
        else:
            self.recording = True
            self.recorded_frames = []
            self.recording_start_gen = self.grid.generation
            self._capture_recording_frame()
            self._flash("Recording started (press G to stop & save GIF)")


    def _capture_recording_frame(self):
        """Capture the current grid state as a recording frame."""
        self.recorded_frames.append([row[:] for row in self.grid.cells])


    def _export_gif(self):
        """Export recorded frames as an animated GIF."""
        os.makedirs(SAVE_DIR, exist_ok=True)
        gen_start = self.recording_start_gen
        gen_end = self.grid.generation
        timestamp = int(time.time())
        filename = f"recording_gen{gen_start}-{gen_end}_{timestamp}.gif"
        filepath = os.path.join(SAVE_DIR, filename)
        n = len(self.recorded_frames)
        # Choose cell size: aim for reasonable image dimensions
        cell_size = 4
        # Speed-aware delay: map simulation speed to GIF frame delay
        delay_cs = max(2, int(SPEEDS[self.speed_idx] * 100))
        try:
            write_gif(filepath, self.recorded_frames,
                      cell_size=cell_size, delay_cs=delay_cs)
            self._flash(f"GIF saved: {filename} ({n} frames)")
        except OSError as e:
            self._flash(f"GIF export failed: {e}")
        self.recorded_frames = []


    def _handle_bookmark_menu_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q
            self.bookmark_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.bookmark_sel = (self.bookmark_sel - 1) % len(self.bookmarks)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.bookmark_sel = (self.bookmark_sel + 1) % len(self.bookmarks)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — jump to bookmark
            self.running = False
            self._jump_to_bookmark(self.bookmark_sel)
            self.bookmark_menu = False
            return True
        if key == ord("D") or key == curses.KEY_DC:  # D or Delete — remove bookmark
            if self.bookmarks:
                removed = self.bookmarks.pop(self.bookmark_sel)
                self._flash(f"Removed bookmark Gen {removed[0]}")
                if not self.bookmarks:
                    self.bookmark_menu = False
                else:
                    self.bookmark_sel = min(self.bookmark_sel, len(self.bookmarks) - 1)
            return True
        return True


    def _handle_menu_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q
            self.pattern_menu = False
            self.stamp_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.pattern_sel = (self.pattern_sel - 1) % len(self.pattern_list)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.pattern_sel = (self.pattern_sel + 1) % len(self.pattern_list)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter
            name = self.pattern_list[self.pattern_sel]
            if self.stamp_menu:
                self._stamp_pattern(name)
                self.stamp_menu = False
                self.running = False
                self._reset_cycle_detection()
            else:
                self.grid.clear()
                self._place_pattern(name)
                self.pattern_menu = False
                self.running = False
                self.pop_history.clear()
                self._record_pop()
                self._reset_cycle_detection()
            return True
        return True

    # ── Rule editor ──


    def _handle_rule_menu_key(self, key: int) -> bool:
        if key == -1:
            return True
        if key == 27 or key == ord("q"):  # ESC or q
            self.rule_menu = False
            return True
        if key in (curses.KEY_UP, ord("k")):
            self.rule_sel = (self.rule_sel - 1) % len(self.rule_preset_list)
            return True
        if key in (curses.KEY_DOWN, ord("j")):
            self.rule_sel = (self.rule_sel + 1) % len(self.rule_preset_list)
            return True
        if key in (10, 13, curses.KEY_ENTER):  # Enter — apply preset
            name = self.rule_preset_list[self.rule_sel]
            preset = RULE_PRESETS[name]
            self.grid.birth = set(preset["birth"])
            self.grid.survival = set(preset["survival"])
            self.rule_menu = False
            self._reset_cycle_detection()
            self._flash(f"Rule: {name} ({rule_string(self.grid.birth, self.grid.survival)})")
            return True
        if key == ord("/"):  # Custom rule entry
            self.rule_menu = False
            rs = self._prompt_text("Rule (e.g. B3/S23)")
            if rs:
                parsed = parse_rule_string(rs)
                if parsed:
                    self.grid.birth, self.grid.survival = parsed
                    self._reset_cycle_detection()
                    self._flash(f"Rule set: {rule_string(self.grid.birth, self.grid.survival)}")
                else:
                    self._flash("Invalid rule string (use format B.../S...)")
            return True
        return True


    def _draw_rule_menu(self, max_y: int, max_x: int):
        title = "── Rule Editor (Enter=apply, /=custom, q/Esc=cancel) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass
        current = rule_string(self.grid.birth, self.grid.survival)
        current_line = f"Current rule: {current}"
        try:
            self.stdscr.addstr(3, max(0, (max_x - len(current_line)) // 2), current_line,
                               curses.color_pair(6))
        except curses.error:
            pass
        for i, name in enumerate(self.rule_preset_list):
            y = 5 + i
            if y >= max_y - 1:
                break
            preset = RULE_PRESETS[name]
            rs = rule_string(preset["birth"], preset["survival"])
            line = f"  {name:<20s} {rs}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.rule_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass
        tip_y = 5 + len(self.rule_preset_list) + 1
        if tip_y < max_y - 1:
            tip = "Press / to type a custom rule string (e.g. B36/S23)"
            try:
                self.stdscr.addstr(tip_y, max(0, (max_x - len(tip)) // 2), tip,
                                   curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

    # ── 3D Isometric mode ──

    # Height tiers for isometric rendering: (max_age, pillar_chars_bottom_to_top)
    # Each pillar is drawn from bottom to top; taller pillars = older cells.
    _ISO_HEIGHT_TIERS = [
        (1,  ["█"]),                              # newborn: 1 row
        (3,  ["█", "▓"]),                         # young: 2 rows
        (8,  ["█", "▓", "▒"]),                    # mature: 3 rows
        (20, ["█", "▓", "▒", "░"]),               # old: 4 rows
    ]
    _ISO_MAX_HEIGHT = 5  # ancient: 5 rows
    _ISO_ANCIENT = ["█", "▓", "▒", "░", "·"]

    # Shade chars for the right face of the isometric column
    _ISO_SHADE_MAP = {"█": "▓", "▓": "▒", "▒": "░", "░": " ", "·": " "}


    def _start_compare(self, birth2: set, survival2: set):
        """Clone the current grid into a second grid with different rules and start comparison."""
        self.grid2 = Grid(self.grid.rows, self.grid.cols)
        # Copy cell state from the primary grid
        for r in range(self.grid.rows):
            for c in range(self.grid.cols):
                self.grid2.cells[r][c] = self.grid.cells[r][c]
        self.grid2.generation = self.grid.generation
        self.grid2.population = self.grid.population
        # Apply the chosen rule to the second grid
        self.grid2.birth = birth2
        self.grid2.survival = survival2
        self.pop_history2 = list(self.pop_history)
        self.compare_mode = True
        self.compare_rule_menu = False
        r1 = rule_string(self.grid.birth, self.grid.survival)
        r2 = rule_string(birth2, survival2)
        self._flash(f"Comparing: {r1} vs {r2}  (V to exit)")


    def _start_race(self):
        """Clone current grid into N grids with different rules and start the race."""
        self.race_grids = []
        self.race_pop_histories = []
        self.race_stats = []
        self.race_state_hashes = []
        for name, birth, survival in self.race_selected_rules:
            g = Grid(self.grid.rows, self.grid.cols)
            for r in range(self.grid.rows):
                for c in range(self.grid.cols):
                    g.cells[r][c] = self.grid.cells[r][c]
            g.generation = self.grid.generation
            g.population = self.grid.population
            g.birth = birth
            g.survival = survival
            self.race_grids.append(g)
            self.race_pop_histories.append([g.population])
            self.race_stats.append({
                "extinction_gen": None,
                "osc_period": None,
                "peak_pop": g.population,
            })
            self.race_state_hashes.append({g.state_hash(): g.generation})
        self.race_start_gen = self.grid.generation
        self.race_mode = True
        self.race_rule_menu = False
        self.race_finished = False
        self.race_winner = None
        n = len(self.race_selected_rules)
        self._flash(f"Race started! {n} rules competing for {self.race_max_gens} generations (Space=play, Z=exit)")


    def _step_race(self):
        """Advance all race grids by one generation and update stats."""
        gens_elapsed = 0
        for i, g in enumerate(self.race_grids):
            if self.race_stats[i]["extinction_gen"] is not None:
                # Already extinct — keep stepping but population stays 0
                self.race_pop_histories[i].append(0)
                continue
            g.step()
            pop = g.population
            self.race_pop_histories[i].append(pop)
            stats = self.race_stats[i]
            if pop > stats["peak_pop"]:
                stats["peak_pop"] = pop
            # Check extinction
            if pop == 0 and stats["extinction_gen"] is None:
                stats["extinction_gen"] = g.generation
            # Check oscillation via cycle detection
            if stats["osc_period"] is None:
                h = g.state_hash()
                hashes = self.race_state_hashes[i]
                if h in hashes:
                    stats["osc_period"] = g.generation - hashes[h]
                else:
                    hashes[h] = g.generation
            gens_elapsed = g.generation - self.race_start_gen
        # Check if race is over
        if gens_elapsed >= self.race_max_gens and not self.race_finished:
            self._finish_race()


    def _finish_race(self):
        """Determine winner based on scoring: population + survival + oscillation bonus."""
        self.race_finished = True
        self.running = False
        best_score = -1
        best_name = ""
        for i, (name, birth, survival) in enumerate(self.race_selected_rules):
            stats = self.race_stats[i]
            g = self.race_grids[i]
            # Scoring: weighted combination
            pop_score = g.population
            # Survival bonus: full marks if never went extinct
            survival_bonus = self.race_max_gens if stats["extinction_gen"] is None else stats["extinction_gen"] - self.race_start_gen
            # Oscillation bonus: detecting a cycle is interesting
            osc_bonus = 50 if stats["osc_period"] is not None and stats["osc_period"] > 1 else 0
            # Peak population bonus
            peak_bonus = stats["peak_pop"] // 2
            score = pop_score + survival_bonus + osc_bonus + peak_bonus
            stats["final_score"] = score
            rs = rule_string(birth, survival)
            if score > best_score:
                best_score = score
                best_name = f"{name} ({rs})"
        self.race_winner = best_name
        self._flash(f"Race complete! Winner: {best_name}")


    def _exit_current_modes(self):
        """Exit any currently active simulation mode."""
        for entry in MODE_REGISTRY:
            if entry["attr"] and getattr(self, entry["attr"], False):
                exit_fn = getattr(self, entry["exit"], None)
                if exit_fn:
                    exit_fn()


    def _mode_browser_apply_filter(self):
        """Filter MODE_REGISTRY by search string."""
        q = self.mode_browser_search.lower()
        if not q:
            self.mode_browser_filtered = list(MODE_REGISTRY)
        else:
            self.mode_browser_filtered = [
                m for m in MODE_REGISTRY
                if q in m["name"].lower() or q in m["desc"].lower() or q in m["category"].lower()
            ]
        # Clamp selection
        if self.mode_browser_filtered:
            self.mode_browser_sel = min(self.mode_browser_sel, len(self.mode_browser_filtered) - 1)
        else:
            self.mode_browser_sel = 0
        self.mode_browser_scroll = 0


    def _handle_mode_browser_key(self, key: int) -> bool:
        """Handle input in the mode browser/picker."""
        if key == -1:
            return True
        if key == 27:  # Esc
            self.mode_browser = False
            return True
        items = self.mode_browser_filtered
        n = len(items)
        # Arrow keys always navigate; j/k navigate only when not searching
        nav_up = key == curses.KEY_UP or (key == ord("k") and not self.mode_browser_search)
        nav_down = key == curses.KEY_DOWN or (key == ord("j") and not self.mode_browser_search)
        if nav_up:
            if n > 0:
                self.mode_browser_sel = (self.mode_browser_sel - 1) % n
            return True
        if nav_down:
            if n > 0:
                self.mode_browser_sel = (self.mode_browser_sel + 1) % n
            return True
        if key in (curses.KEY_PPAGE,):  # Page Up
            if n > 0:
                self.mode_browser_sel = max(0, self.mode_browser_sel - 10)
            return True
        if key in (curses.KEY_NPAGE,):  # Page Down
            if n > 0:
                self.mode_browser_sel = min(n - 1, self.mode_browser_sel + 10)
            return True
        if key in (curses.KEY_HOME,):
            self.mode_browser_sel = 0
            return True
        if key in (curses.KEY_END,):
            if n > 0:
                self.mode_browser_sel = n - 1
            return True
        if key in (10, 13, curses.KEY_ENTER):
            # Launch the selected mode
            if items:
                entry = items[self.mode_browser_sel]
                self.mode_browser = False
                # Exit any currently active mode first
                self._exit_current_modes()
                if entry["enter"] is not None:
                    enter_fn = getattr(self, entry["enter"], None)
                    if enter_fn:
                        enter_fn()
                else:
                    # Game of Life (default) — just flash
                    self._flash("Game of Life (default mode)")
            return True
        if key in (curses.KEY_BACKSPACE, 127, 8):
            if self.mode_browser_search:
                self.mode_browser_search = self.mode_browser_search[:-1]
                self._mode_browser_apply_filter()
            return True
        # Printable characters → search filter
        if 32 <= key <= 126:
            self.mode_browser_search += chr(key)
            self._mode_browser_apply_filter()
            return True
        return True


    def _draw_mode_browser(self, max_y: int, max_x: int):
        """Draw the categorized mode selection browser."""
        title = "── Mode Browser (Enter=launch, Esc=cancel, type to search) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        # Search bar
        search_label = f" Search: {self.mode_browser_search}█" if self.mode_browser_search else " Search: type to filter..."
        search_attr = curses.color_pair(6) if self.mode_browser_search else curses.color_pair(6) | curses.A_DIM
        try:
            self.stdscr.addstr(3, 2, search_label[:max_x - 4], search_attr)
        except curses.error:
            pass

        items = self.mode_browser_filtered
        n = len(items)
        if n == 0:
            try:
                self.stdscr.addstr(5, 4, "No matching modes found.", curses.color_pair(1))
            except curses.error:
                pass
            return

        # Build display lines grouped by category
        lines: list[tuple[str, int, dict | None]] = []  # (text, color_pair, mode_entry_or_None)
        current_cat = ""
        for entry in items:
            if entry["category"] != current_cat:
                current_cat = entry["category"]
                if lines:
                    lines.append(("", 0, None))  # blank separator
                lines.append((f"  ─── {current_cat} ───", 7, None))  # category header
            key_str = f"[{entry['key']:>6s}]" if entry["key"] != "—" else "[      ]"
            line = f"    {key_str}  {entry['name']:<30s}  {entry['desc']}"
            lines.append((line, 6, entry))

        # Calculate which lines are selectable (have an entry)
        selectable_indices = [i for i, (_, _, e) in enumerate(lines) if e is not None]

        # Map mode_browser_sel to selectable line index
        if self.mode_browser_sel >= len(selectable_indices):
            self.mode_browser_sel = max(0, len(selectable_indices) - 1)
        sel_line_idx = selectable_indices[self.mode_browser_sel] if selectable_indices else -1

        # Scrollable area
        list_start_y = 5
        visible_rows = max_y - list_start_y - 2  # leave room for footer
        if visible_rows < 1:
            return

        # Adjust scroll to keep selection visible
        if sel_line_idx >= 0:
            if sel_line_idx < self.mode_browser_scroll:
                self.mode_browser_scroll = sel_line_idx
            elif sel_line_idx >= self.mode_browser_scroll + visible_rows:
                self.mode_browser_scroll = sel_line_idx - visible_rows + 1
        self.mode_browser_scroll = max(0, min(self.mode_browser_scroll, max(0, len(lines) - visible_rows)))

        # Render visible lines
        for vi in range(visible_rows):
            li = self.mode_browser_scroll + vi
            if li >= len(lines):
                break
            text, cpair, entry = lines[li]
            y = list_start_y + vi
            if li == sel_line_idx:
                attr = curses.color_pair(7) | curses.A_REVERSE
            elif entry is None:
                # Category header or blank
                attr = curses.color_pair(cpair) | curses.A_BOLD if cpair else 0
            else:
                attr = curses.color_pair(cpair)
            try:
                self.stdscr.addstr(y, 0, text[:max_x - 1].ljust(max_x - 1), attr)
            except curses.error:
                pass

        # Scrollbar indicator
        if len(lines) > visible_rows:
            sb_frac = self.mode_browser_scroll / max(1, len(lines) - visible_rows)
            sb_pos = list_start_y + int(sb_frac * (visible_rows - 1))
            try:
                self.stdscr.addstr(sb_pos, max_x - 1, "█", curses.color_pair(7))
            except curses.error:
                pass

        # Footer
        count_text = f" {n} modes"
        footer = f" ↑↓/jk=navigate │ PgUp/PgDn=scroll │ Enter=launch │ Esc=cancel │{count_text}"
        try:
            self.stdscr.addstr(max_y - 1, 0, footer[:max_x - 1],
                               curses.color_pair(6) | curses.A_DIM)
        except curses.error:
            pass


    def _prompt_text(self, prompt: str) -> str | None:
        """Show a text prompt on the bottom line and return user input, or None on ESC."""
        self.stdscr.nodelay(False)
        max_y, max_x = self.stdscr.getmaxyx()
        y = max_y - 1
        buf = ""
        while True:
            try:
                self.stdscr.move(y, 0)
                self.stdscr.clrtoeol()
                display = f" {prompt}: {buf}"
                self.stdscr.addstr(y, 0, display[:max_x - 1], curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch == 27:  # ESC
                self.stdscr.nodelay(True)
                return None
            if ch in (10, 13, curses.KEY_ENTER):
                self.stdscr.nodelay(True)
                return buf.strip()
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                buf = buf[:-1]
            elif 32 <= ch < 127:
                buf += chr(ch)
        self.stdscr.nodelay(True)
        return None


    def _save_state(self):
        name = self._prompt_text("Save name (enter to cancel)")
        if not name:
            self._flash("Save cancelled")
            return
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        if not safe_name:
            self._flash("Invalid name")
            return
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = os.path.join(SAVE_DIR, safe_name + ".json")
        data = self.grid.to_dict()
        data["name"] = name
        with open(path, "w") as f:
            json.dump(data, f)
        self._flash(f"Saved: {safe_name}.json")


    def _load_state(self):
        if not os.path.isdir(SAVE_DIR):
            self._flash("No saves found")
            return
        saves = sorted(f for f in os.listdir(SAVE_DIR) if f.endswith(".json") and f != "blueprints.json")
        if not saves:
            self._flash("No saves found")
            return
        # Show a selection menu
        self._save_menu = True
        self._save_list = saves
        self._save_sel = 0
        self._show_save_menu()


    def _show_save_menu(self):
        """Run a blocking menu to select a save file."""
        self.stdscr.nodelay(False)
        while True:
            self.stdscr.erase()
            max_y, max_x = self.stdscr.getmaxyx()
            title = "── Load Save (Enter=load, q/Esc=cancel) ──"
            try:
                self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                                   curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass
            for i, fname in enumerate(self._save_list):
                y = 3 + i
                if y >= max_y - 1:
                    break
                label = fname.removesuffix(".json")
                line = f"  {label}"[:max_x - 2]
                attr = curses.color_pair(6)
                if i == self._save_sel:
                    attr = curses.color_pair(7) | curses.A_REVERSE
                try:
                    self.stdscr.addstr(y, 2, line, attr)
                except curses.error:
                    pass
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key == 27 or key == ord("q"):
                break
            if key in (curses.KEY_UP, ord("k")):
                self._save_sel = (self._save_sel - 1) % len(self._save_list)
            elif key in (curses.KEY_DOWN, ord("j")):
                self._save_sel = (self._save_sel + 1) % len(self._save_list)
            elif key in (10, 13, curses.KEY_ENTER):
                path = os.path.join(SAVE_DIR, self._save_list[self._save_sel])
                try:
                    with open(path) as f:
                        data = json.load(f)
                    self.grid.load_dict(data)
                    self.running = False
                    self.pop_history.clear()
                    self._record_pop()
                    self._reset_cycle_detection()
                    self._flash(f"Loaded: {self._save_list[self._save_sel].removesuffix('.json')}")
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    self._flash(f"Error loading save: {e}")
                break
        self.stdscr.nodelay(True)

    # ── RLE Import ──


    def _import_rle(self):
        """Prompt for an RLE file path and load the pattern."""
        path = self._prompt_text("RLE file path")
        if not path:
            self._flash("Import cancelled")
            return
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            self._flash(f"File not found: {path}")
            return
        try:
            with open(path, "r", errors="replace") as f:
                text = f.read()
        except OSError as e:
            self._flash(f"Error reading file: {e}")
            return
        rle = parse_rle(text)
        if not rle["cells"]:
            self._flash("No cells found in RLE file")
            return
        # Apply rule from RLE if present
        if rle["rule"]:
            parsed = parse_rule_string(rle["rule"])
            if parsed:
                self.grid.birth, self.grid.survival = parsed
        # Clear grid and place pattern centered
        self.grid.clear()
        off_r = (self.grid.rows - rle["height"]) // 2
        off_c = (self.grid.cols - rle["width"]) // 2
        for r, c in rle["cells"]:
            gr = (r + off_r) % self.grid.rows
            gc = (c + off_c) % self.grid.cols
            self.grid.set_alive(gr, gc)
        # Center cursor on the pattern
        self.cursor_r = (off_r + rle["height"] // 2) % self.grid.rows
        self.cursor_c = (off_c + rle["width"] // 2) % self.grid.cols
        self.running = False
        self.pop_history.clear()
        self._record_pop()
        self._reset_cycle_detection()
        label = rle["name"] or os.path.basename(path)
        self._flash(f"Imported: {label} ({rle['width']}×{rle['height']}, {len(rle['cells'])} cells)")

    # ── Drawing ──


    def _draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()

        if self.screensaver_menu:
            self._draw_screensaver_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ep_menu:
            self._draw_ep_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ep_mode:
            self._draw_ep(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.pexplorer_menu:
            self._draw_pexplorer_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.pexplorer_mode:
            self._draw_pexplorer(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.dashboard:
            self._draw_dashboard(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.mode_browser:
            self._draw_mode_browser(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.puzzle_menu:
            self._draw_puzzle_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.puzzle_mode and self.puzzle_current:
            self._draw_puzzle(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.blueprint_menu:
            self._draw_blueprint_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.bookmark_menu:
            self._draw_bookmark_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.show_help:
            self._draw_help(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wolfram_menu:
            self._draw_wolfram_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wolfram_mode:
            self._draw_wolfram(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ant_menu:
            self._draw_ant_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ant_mode:
            self._draw_ant(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ww_menu:
            self._draw_ww_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ww_mode:
            self._draw_ww(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sand_menu:
            self._draw_sand_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sand_mode:
            self._draw_sand(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rd_menu:
            self._draw_rd_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rd_mode:
            self._draw_rd(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lenia_menu:
            self._draw_lenia_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lenia_mode:
            self._draw_lenia(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.physarum_menu:
            self._draw_physarum_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.physarum_mode:
            self._draw_physarum(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.boids_menu:
            self._draw_boids_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.boids_mode:
            self._draw_boids(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.plife_menu:
            self._draw_plife_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.plife_mode:
            self._draw_plife(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.nbody_menu:
            self._draw_nbody_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.nbody_mode:
            self._draw_nbody(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fluid_menu:
            self._draw_fluid_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fluid_mode:
            self._draw_fluid(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wfc_menu:
            self._draw_wfc_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wfc_mode:
            self._draw_wfc(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.aco_menu:
            self._draw_aco_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.aco_mode:
            self._draw_aco(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.maze_menu:
            self._draw_maze_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.maze_mode:
            self._draw_maze(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.dla_menu:
            self._draw_dla_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.dla_mode:
            self._draw_dla(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sandpile_menu:
            self._draw_sandpile_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sandpile_mode:
            self._draw_sandpile(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fire_menu:
            self._draw_fire_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fire_mode:
            self._draw_fire(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sir_menu:
            self._draw_sir_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sir_mode:
            self._draw_sir(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.cyclic_menu:
            self._draw_cyclic_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.cyclic_mode:
            self._draw_cyclic(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ising_menu:
            self._draw_ising_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ising_mode:
            self._draw_ising(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.hodge_menu:
            self._draw_hodge_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.hodge_mode:
            self._draw_hodge(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lv_menu:
            self._draw_lv_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lv_mode:
            self._draw_lv(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.schelling_menu:
            self._draw_schelling_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.schelling_mode:
            self._draw_schelling(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.spd_menu:
            self._draw_spd_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.spd_mode:
            self._draw_spd(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lightning_menu:
            self._draw_lightning_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lightning_mode:
            self._draw_lightning(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.erosion_menu:
            self._draw_erosion_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.erosion_mode:
            self._draw_erosion(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.voronoi_menu:
            self._draw_voronoi_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.voronoi_mode:
            self._draw_voronoi(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rps_menu:
            self._draw_rps_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rps_mode:
            self._draw_rps(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wave_menu:
            self._draw_wave_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.wave_mode:
            self._draw_wave(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.kuramoto_menu:
            self._draw_kuramoto_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.kuramoto_mode:
            self._draw_kuramoto(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.snn_menu:
            self._draw_snn_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.snn_mode:
            self._draw_snn(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.bz_menu:
            self._draw_bz_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.bz_mode:
            self._draw_bz(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.chemo_menu:
            self._draw_chemo_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.chemo_mode:
            self._draw_chemo(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.mhd_menu:
            self._draw_mhd_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.mhd_mode:
            self._draw_mhd(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.attractor_menu:
            self._draw_attractor_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.attractor_mode:
            self._draw_attractor(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.qwalk_menu:
            self._draw_qwalk_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.qwalk_mode:
            self._draw_qwalk(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.terrain_menu:
            self._draw_terrain_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.terrain_mode:
            self._draw_terrain(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.flythrough_menu:
            self._draw_flythrough_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.flythrough_mode:
            self._draw_flythrough(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.raymarch_menu:
            self._draw_raymarch_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.raymarch_mode:
            self._draw_raymarch(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.shadertoy_menu:
            self._draw_shadertoy_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.shadertoy_mode:
            self._draw_shadertoy(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.musvis_menu:
            self._draw_musvis_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.musvis_mode:
            self._draw_musvis(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.alife_menu:
            self._draw_alife_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.alife_mode:
            self._draw_alife(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.doomrc_menu:
            self._draw_doomrc_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.doomrc_mode:
            self._draw_doomrc(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.tectonic_menu:
            self._draw_tectonic_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.tectonic_mode:
            self._draw_tectonic(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.weather_menu:
            self._draw_weather_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.weather_mode:
            self._draw_weather(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ocean_menu:
            self._draw_ocean_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ocean_mode:
            self._draw_ocean(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.volcano_menu:
            self._draw_volcano_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.volcano_mode:
            self._draw_volcano(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.blackhole_menu:
            self._draw_blackhole_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.blackhole_mode:
            self._draw_blackhole(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.orrery_menu:
            self._draw_orrery_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.orrery_mode:
            self._draw_orrery(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.aurora_menu:
            self._draw_aurora_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.aurora_mode:
            self._draw_aurora(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.pwave_menu:
            self._draw_pwave_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.pwave_mode:
            self._draw_pwave(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.tornado_menu:
            self._draw_tornado_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.tornado_mode:
            self._draw_tornado(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sortvis_menu:
            self._draw_sortvis_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sortvis_mode:
            self._draw_sortvis(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fourier_menu:
            self._draw_fourier_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fourier_mode:
            self._draw_fourier(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.snowfall_menu:
            self._draw_snowfall_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.snowfall_mode:
            self._draw_snowfall(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.matrix_menu:
            self._draw_matrix_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.matrix_mode:
            self._draw_matrix(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fluidrope_menu:
            self._draw_fluidrope_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fluidrope_mode:
            self._draw_fluidrope(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lissajous_menu:
            self._draw_lissajous_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lissajous_mode:
            self._draw_lissajous(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.mazesolver_menu:
            self._draw_mazesolver_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.mazesolver_mode:
            self._draw_mazesolver(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.antfarm_menu:
            self._draw_antfarm_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.antfarm_mode:
            self._draw_antfarm(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.kaleido_menu:
            self._draw_kaleido_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.kaleido_mode:
            self._draw_kaleido(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.aquarium_menu:
            self._draw_aquarium_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.aquarium_mode:
            self._draw_aquarium(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.collider_menu:
            self._draw_collider_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.collider_mode:
            self._draw_collider(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.dnahelix_menu:
            self._draw_dnahelix_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.dnahelix_mode:
            self._draw_dnahelix(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.gol3d_menu:
            self._draw_gol3d_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.gol3d_mode:
            self._draw_gol3d(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.smokefire_menu:
            self._draw_smokefire_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.smokefire_mode:
            self._draw_smokefire(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.cloth_menu:
            self._draw_cloth_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.cloth_mode:
            self._draw_cloth(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.galaxy_menu:
            self._draw_galaxy_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.galaxy_mode:
            self._draw_galaxy(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lsystem_menu:
            self._draw_lsystem_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.lsystem_mode:
            self._draw_lsystem(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fireworks_menu:
            self._draw_fireworks_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fireworks_mode:
            self._draw_fireworks(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fractal_menu:
            self._draw_fractal_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fractal_mode:
            self._draw_fractal(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ns_menu:
            self._draw_ns_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ns_mode:
            self._draw_ns(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.dpend_menu:
            self._draw_dpend_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.dpend_mode:
            self._draw_dpend(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.chladni_menu:
            self._draw_chladni_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.chladni_mode:
            self._draw_chladni(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ifs_menu:
            self._draw_ifs_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.ifs_mode:
            self._draw_ifs(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.cpm_menu:
            self._draw_cpm_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.cpm_mode:
            self._draw_cpm(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.magfield_menu:
            self._draw_magfield_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.magfield_mode:
            self._draw_magfield(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fdtd_menu:
            self._draw_fdtd_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.fdtd_mode:
            self._draw_fdtd(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sph_menu:
            self._draw_sph_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.sph_mode:
            self._draw_sph(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rbc_menu:
            self._draw_rbc_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rbc_mode:
            self._draw_rbc(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.turmite_menu:
            self._draw_turmite_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.turmite_mode:
            self._draw_turmite(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.traffic_menu:
            self._draw_traffic_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.traffic_mode:
            self._draw_traffic(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.snowflake_menu:
            self._draw_snowflake_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.snowflake_mode:
            self._draw_snowflake(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.evo_menu:
            self._draw_evo_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.evo_mode:
            self._draw_evo(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.race_rule_menu:
            self._draw_race_rule_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.compare_rule_menu:
            self._draw_compare_rule_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.rule_menu:
            self._draw_rule_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.pattern_menu or self.stamp_menu:
            self._draw_pattern_menu(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.mp_mode:
            self._draw_multiplayer(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.race_mode and self.race_grids:
            self._draw_race(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.compare_mode and self.grid2:
            self._draw_compare(max_y, max_x)
            self.stdscr.refresh()
            return

        if self.iso_mode:
            self._draw_iso(max_y, max_x)
            self.stdscr.refresh()
            return

        # Compute viewport
        # Each cell takes 2 columns on screen
        zoom = self.zoom_level
        vis_rows = max_y - 5  # leave room for timeline + sparkline + status + hint
        vis_cols = (max_x - 1) // 2

        # At zoom > 1, each screen cell covers zoom×zoom grid cells
        grid_vis_rows = vis_rows * zoom
        grid_vis_cols = vis_cols * zoom

        # Centre viewport on cursor
        self.view_r = self.cursor_r - grid_vis_rows // 2
        self.view_c = self.cursor_c - grid_vis_cols // 2

        # Build pattern highlight lookup: (gr, gc) -> category string
        pat_highlight = {}
        if self.pattern_search_mode and self.detected_patterns:
            for pat in self.detected_patterns:
                for cell in pat["cells"]:
                    pat_highlight[cell] = pat["category"]

        # Blueprint selection region bounds
        bp_min_r = bp_min_c = bp_max_r = bp_max_c = -1
        if self.blueprint_mode and self.blueprint_anchor:
            bp_min_r, bp_min_c, bp_max_r, bp_max_c = self._blueprint_region()

        if zoom == 1:
            # Normal 1:1 rendering
            hex_offset_cols = vis_cols - 1 if self.hex_mode else vis_cols
            for sy in range(min(vis_rows, self.grid.rows)):
                gr = (self.view_r + sy) % self.grid.rows
                for sx in range(min(hex_offset_cols, self.grid.cols)):
                    gc = (self.view_c + sx) % self.grid.cols
                    age = self.grid.cells[gr][gc]
                    is_cursor = (gr == self.cursor_r and gc == self.cursor_c)
                    in_blueprint = (self.blueprint_mode and self.blueprint_anchor and
                                    bp_min_r <= gr <= bp_max_r and bp_min_c <= gc <= bp_max_c)
                    # Hex mode: offset odd grid rows by 1 column for hex tiling
                    hex_shift = 1 if (self.hex_mode and gr % 2 == 1) else 0
                    px = sx * 2 + hex_shift
                    py = sy
                    if py >= max_y - 2 or px + 1 >= max_x:
                        continue
                    if self.heatmap_mode and self.heatmap_max > 0:
                        heat = self.heatmap[gr][gc]
                        if heat > 0:
                            frac = heat / self.heatmap_max
                            attr = color_for_heat(frac)
                            if age > 0:
                                attr |= curses.A_BOLD
                            if is_cursor:
                                attr |= curses.A_REVERSE
                            heat_ch = HEX_CELL if self.hex_mode else CELL_CHAR
                            try:
                                self.stdscr.addstr(py, px, heat_ch, attr)
                            except curses.error:
                                pass
                        else:
                            if is_cursor:
                                try:
                                    self.stdscr.addstr(py, px, "▒▒", curses.color_pair(6) | curses.A_DIM)
                                except curses.error:
                                    pass
                            elif in_blueprint:
                                try:
                                    self.stdscr.addstr(py, px, "░░", curses.color_pair(40) | curses.A_DIM)
                                except curses.error:
                                    pass
                    elif age > 0:
                        # Pattern search highlighting
                        pcat = pat_highlight.get((gr, gc))
                        if pcat:
                            attr = self._pattern_color(pcat) | curses.A_BOLD
                        else:
                            attr = color_for_age(age)
                        if in_blueprint:
                            attr = curses.color_pair(40) | curses.A_BOLD
                        if is_cursor:
                            attr |= curses.A_REVERSE
                        cell_ch = HEX_CELL if self.hex_mode else CELL_CHAR
                        try:
                            self.stdscr.addstr(py, px, cell_ch, attr)
                        except curses.error:
                            pass
                    else:
                        if is_cursor:
                            cursor_ch = HEX_CELL if self.hex_mode else "▒▒"
                            try:
                                self.stdscr.addstr(py, px, cursor_ch, curses.color_pair(6) | curses.A_DIM)
                            except curses.error:
                                pass
                        elif in_blueprint:
                            try:
                                self.stdscr.addstr(py, px, "░░", curses.color_pair(40) | curses.A_DIM)
                            except curses.error:
                                pass
                        elif self.hex_mode:
                            # Show hex grid structure with dots
                            try:
                                self.stdscr.addstr(py, px, HEX_DEAD, curses.color_pair(6) | curses.A_DIM)
                            except curses.error:
                                pass
        else:
            # Zoomed-out rendering: each screen cell covers zoom×zoom grid cells
            screen_rows = min(vis_rows, (self.grid.rows + zoom - 1) // zoom)
            screen_cols = min(vis_cols, (self.grid.cols + zoom - 1) // zoom)
            for sy in range(screen_rows):
                for sx in range(screen_cols):
                    px = sx * 2
                    py = sy
                    if py >= max_y - 2 or px + 1 >= max_x:
                        continue
                    # Compute density of the zoom×zoom block
                    alive_count = 0
                    total = 0
                    heat_sum = 0
                    max_age = 0
                    has_cursor = False
                    has_blueprint = False
                    base_r = self.view_r + sy * zoom
                    base_c = self.view_c + sx * zoom
                    for dr in range(zoom):
                        for dc in range(zoom):
                            gr = (base_r + dr) % self.grid.rows
                            gc = (base_c + dc) % self.grid.cols
                            total += 1
                            age = self.grid.cells[gr][gc]
                            if age > 0:
                                alive_count += 1
                                if age > max_age:
                                    max_age = age
                            if gr == self.cursor_r and gc == self.cursor_c:
                                has_cursor = True
                            if (self.blueprint_mode and self.blueprint_anchor and
                                    bp_min_r <= gr <= bp_max_r and bp_min_c <= gc <= bp_max_c):
                                has_blueprint = True
                            if self.heatmap_mode and self.heatmap_max > 0:
                                heat_sum += self.heatmap[gr][gc]
                    # Pick density glyph
                    if alive_count == 0:
                        density_idx = 0
                    else:
                        frac = alive_count / total
                        if frac <= 0.25:
                            density_idx = 1
                        elif frac <= 0.5:
                            density_idx = 2
                        elif frac <= 0.75:
                            density_idx = 3
                        else:
                            density_idx = 4
                    char = DENSITY_CHARS[density_idx]
                    # Determine color/attr
                    if self.heatmap_mode and self.heatmap_max > 0:
                        if heat_sum > 0:
                            heat_frac = (heat_sum / total) / self.heatmap_max
                            attr = color_for_heat(min(1.0, heat_frac))
                            if alive_count > 0:
                                attr |= curses.A_BOLD
                        else:
                            attr = curses.color_pair(6) | curses.A_DIM
                            if alive_count == 0 and not has_cursor and not has_blueprint:
                                continue
                    elif alive_count > 0:
                        attr = color_for_age(max_age)
                    elif has_blueprint:
                        attr = curses.color_pair(40) | curses.A_DIM
                        char = "░░"
                    elif has_cursor:
                        attr = curses.color_pair(6) | curses.A_DIM
                        char = "▒▒"
                    else:
                        continue  # empty, nothing to draw
                    if has_cursor:
                        attr |= curses.A_REVERSE
                    try:
                        self.stdscr.addstr(py, px, char, attr)
                    except curses.error:
                        pass

        # Draw pattern labels (name tags near detected patterns)
        if self.pattern_search_mode and self.detected_patterns:
            for pat in self.detected_patterns:
                # Label position: just above the pattern's top-left, or on top row
                label_gr = pat["r"]
                label_gc = pat["c"]
                # Convert to screen coords (accounting for zoom)
                sy = ((label_gr - self.view_r) % self.grid.rows) // zoom
                sx = ((label_gc - self.view_c) % self.grid.cols) // zoom
                lpy = sy - 1  # one row above
                lpx = sx * 2
                label = pat["name"]
                if lpy < 0:
                    lpy = sy + pat["h"]  # below if no room above
                if 0 <= lpy < vis_rows and 0 <= lpx < max_x - len(label):
                    attr = self._pattern_color(pat["category"]) | curses.A_DIM
                    try:
                        self.stdscr.addstr(lpy, lpx, label, attr)
                    except curses.error:
                        pass

        # Timeline bar
        timeline_y = max_y - 4
        if timeline_y > 0 and len(self.history) > 0:
            bar_label = " Timeline: "
            bookmark_info = f"  ★{len(self.bookmarks)}" if self.bookmarks else ""
            hist_len = len(self.history)
            # Determine current position in history
            if self.timeline_pos is not None:
                cur_pos = self.timeline_pos + 1  # 1-based
                pos_label = f" Gen {self.grid.generation} ({cur_pos}/{hist_len}){bookmark_info} "
            else:
                pos_label = f" LIVE Gen {self.grid.generation} ({hist_len} saved){bookmark_info} "
            bar_width = max_x - len(bar_label) - len(pos_label) - 1
            if bar_width > 2:
                if self.timeline_pos is not None:
                    # Show position within the history buffer
                    filled = max(1, int((self.timeline_pos + 1) / hist_len * bar_width))
                    empty = bar_width - filled
                    # Mark bookmark positions on the bar
                    bar_chars = list("█" * filled + "░" * empty)
                    for bg, _, _ in self.bookmarks:
                        # Find the approximate bar position for this bookmark
                        for hi, (hd, _) in enumerate(self.history):
                            if hd.get("generation") == bg:
                                bi = int(hi / hist_len * bar_width)
                                bi = min(bi, len(bar_chars) - 1)
                                bar_chars[bi] = "★"
                                break
                    bar_str = "".join(bar_chars)
                else:
                    # At live position — full bar
                    bar_chars = list("█" * bar_width)
                    for bg, _, _ in self.bookmarks:
                        for hi, (hd, _) in enumerate(self.history):
                            if hd.get("generation") == bg:
                                bi = int(hi / hist_len * bar_width)
                                bi = min(bi, len(bar_chars) - 1)
                                bar_chars[bi] = "★"
                                break
                    bar_str = "".join(bar_chars)
                try:
                    self.stdscr.addstr(timeline_y, 0, bar_label, curses.color_pair(6) | curses.A_DIM)
                    self.stdscr.addstr(timeline_y, len(bar_label), bar_str, curses.color_pair(7))
                    self.stdscr.addstr(timeline_y, len(bar_label) + len(bar_str), pos_label,
                                       curses.color_pair(6) | curses.A_DIM)
                except curses.error:
                    pass

        # Population sparkline
        spark_y = max_y - 3
        if spark_y > 0 and len(self.pop_history) > 1:
            spark_width = max_x - 16  # reserve space for label
            if spark_width > 0:
                spark_str = sparkline(self.pop_history, spark_width)
                label = " Pop history: "
                try:
                    self.stdscr.addstr(spark_y, 0, label, curses.color_pair(6) | curses.A_DIM)
                    self.stdscr.addstr(spark_y, len(label), spark_str, curses.color_pair(1))
                except curses.error:
                    pass

        # Status bar
        status_y = max_y - 2
        if status_y > 0:
            state = "▶ PLAY" if self.running else "⏸ PAUSE"
            speed = SPEED_LABELS[self.speed_idx]
            mode = ""
            if self.heatmap_mode:
                mode = "  │  🔥 HEATMAP"
            if self.pattern_search_mode:
                n = len(self.detected_patterns)
                mode += f"  │  🔍 SEARCH({n})"
            if self.blueprint_mode:
                mode += "  │  📐 BLUEPRINT"
            if self.recording:
                mode += f"  │  ⏺ REC({len(self.recorded_frames)})"
            if self.sound_engine.enabled:
                mode += "  │  ♪ SOUND"
            if self.hex_mode:
                mode += "  │  ⬡ HEX"
            if self.iso_mode:
                mode += "  │  🏙 ISO-3D"
            if self.show_minimap:
                mode += "  │  MAP"
            if self.draw_mode == "draw":
                mode += "  │  ✏ DRAW"
            elif self.draw_mode == "erase":
                mode += "  │  ✘ ERASE"
            rs = rule_string(self.grid.birth, self.grid.survival)
            zoom_str = f"  │  Zoom: {self.zoom_level}:1" if self.zoom_level > 1 else ""
            status = (
                f" Gen: {self.grid.generation}  │  "
                f"Pop: {self.grid.population}  │  "
                f"{state}  │  Speed: {speed}  │  "
                f"Rule: {rs}  │  "
                f"Cursor: ({self.cursor_r},{self.cursor_c}){zoom_str}{mode}"
            )
            status = status[:max_x - 1]
            try:
                self.stdscr.addstr(status_y, 0, status, curses.color_pair(7) | curses.A_BOLD)
            except curses.error:
                pass

        # Message / hint bar
        hint_y = max_y - 1
        if hint_y > 0:
            now = time.monotonic()
            if self.message and now - self.message_time < 3.0:
                hint = f" {self.message}"
            else:
                hint = " [Space]=play [n]=step [u]=rewind [/]=scrub10 [b]=bookmark [B]=bookmarks [p]=patterns [t]=stamp [W]=blueprint [T]=blueprints [e]=edit [d]=draw [F]=search [H]=heatmap [I]=3D [Tab]=minimap [1]=wolfram [2]=ant [3]=hex [M]=sound [R]=rules [V]=compare [Z]=race [C]=puzzles [N]=multiplayer [G]=record GIF [s]=save [o]=load [+/-]=zoom [0]=reset zoom [</>]=speed [?]=help [q]=quit"
            hint = hint[:max_x - 1]
            try:
                self.stdscr.addstr(hint_y, 0, hint, curses.color_pair(6) | curses.A_DIM)
            except curses.error:
                pass

        self.stdscr.refresh()


    def _draw_multiplayer(self, max_y: int, max_x: int):
        """Draw the multiplayer mode UI based on current phase."""
        if self.mp_phase == "lobby":
            self._draw_mp_lobby(max_y, max_x)
        elif self.mp_phase == "planning":
            self._draw_mp_planning(max_y, max_x)
        elif self.mp_phase == "running":
            self._draw_mp_game(max_y, max_x)
        elif self.mp_phase == "finished":
            self._draw_mp_finished(max_y, max_x)


    def _draw_bookmark_menu(self, max_y: int, max_x: int):
        title = "── Bookmarks (Enter=jump, D=delete, q/Esc=close) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        for i, (gen, grid_dict, pop_len) in enumerate(self.bookmarks):
            y = 3 + i
            if y >= max_y - 1:
                break
            pop = len(grid_dict.get("cells", []))
            line = f"  ★ Gen {gen:<8d}  Pop: {pop}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.bookmark_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass

    # ── Wolfram 1D Elementary Cellular Automaton mode ──────────────────────────

    WOLFRAM_PRESETS = [
        (30, "Rule 30 — chaotic / pseudorandom"),
        (90, "Rule 90 — Sierpinski triangle (XOR)"),
        (110, "Rule 110 — Turing-complete"),
        (184, "Rule 184 — traffic flow model"),
        (73, "Rule 73 — complex structures"),
        (54, "Rule 54 — complex with triangles"),
        (150, "Rule 150 — Sierpinski variant"),
        (22, "Rule 22 — nested triangles"),
        (126, "Rule 126 — complement of 90"),
        (250, "Rule 250 — simple stripes"),
        (0, "Rule 0 — all cells die"),
        (255, "Rule 255 — all cells alive"),
    ]


    def _draw_help(self, max_y: int, max_x: int):
        help_lines = [
            "╔══════════════════════════════════════════════╗",
            "║         Game of Life — Help                  ║",
            "╠══════════════════════════════════════════════╣",
            "║                                              ║",
            "║  Space     Play / Pause auto-advance         ║",
            "║  n / .     Step one generation                ║",
            "║  u         Rewind one generation              ║",
            "║  [ / ]     Scrub timeline back/forward 10     ║",
            "║  b         Bookmark current generation        ║",
            "║  B         List/jump to bookmarks             ║",
            "║  + / -     Zoom in / out (density glyphs)     ║",
            "║  0         Reset zoom to 1:1                  ║",
            "║  < / >     Decrease / increase speed          ║",
            "║  Arrows    Move cursor (also vim hjkl)        ║",
            "║  e         Toggle cell under cursor           ║",
            "║  d         Draw mode (paint while moving)     ║",
            "║  x         Erase mode (erase while moving)    ║",
            "║  Esc       Exit draw/erase mode               ║",
            "║  m         Mode browser (browse all modes)     ║",
            "║  p         Open pattern selector              ║",
            "║  t         Stamp pattern at cursor            ║",
            "║  R         Rule editor (B../S.. presets)      ║",
            "║  W         Blueprint: select region & save      ║",
            "║  T         Traffic Flow (Nagel-Schreckenberg) ║",
            "║  F         Fluid Dynamics (Lattice Boltzmann)  ║",
            "║  f         Pattern search (find known shapes) ║",
            "║  H         Toggle heatmap (cell activity)      ║",
            "║  I         Toggle 3D isometric view            ║",
            "║  Tab       Toggle minimap overlay              ║",
            "║  V         Compare two rules side-by-side     ║",
            "║  Z         Race 2-4 rules with scoreboard      ║",
            "║  N         Multiplayer (host or connect)       ║",
            "║  C         Puzzle / challenge mode              ║",
            "║  E         Evolution (genetic algorithm)        ║",
            "║  M         Toggle sound/music mode             ║",
            "║  1         Wolfram 1D automaton (Rules 0-255) ║",
            "║  2         Langton's Ant (turmite simulation) ║",
            "║  3         Hexagonal grid (6 neighbors)       ║",
            "║  4         Wireworld (circuit simulation)     ║",
            "║  5         Falling Sand (particle sim)        ║",
            "║  6         Reaction-Diffusion (Gray-Scott)    ║",
            "║  7         Lenia (continuous automaton)        ║",
            "║  8         Physarum (slime mold simulation)    ║",
            "║  9         Boids (flocking simulation)         ║",
            "║  A         Ant Colony (pheromone foraging)    ║",
            "║  L         Maze Generation & Pathfinding      ║",
            "║  Y         N-Body Gravity (orbital sim)        ║",
            "║  D         DLA (diffusion-limited aggregation) ║",
            "║  E         Epidemic / SIR disease spread      ║",
            "║  P         Abelian Sandpile (fractal grains)  ║",
            "║  O         Forest Fire (growth & lightning)  ║",
            "║  U         Cyclic Cellular Automaton         ║",
            "║  J         Predator-Prey (Lotka-Volterra)    ║",
            "║  K         Schelling Segregation Model       ║",
            "║  @         Prisoner's Dilemma (Game Theory)  ║",
            "║  Q         Turmites (2D Turing Machine)      ║",
            "║  #         Ising Model (magnetic spins)      ║",
            "║  &         Rock-Paper-Scissors (spiral waves)║",
            "║  !         Wave Equation (2D wave physics)  ║",
            "║  (         Kuramoto Oscillators (phase sync) ║",
            "║  )         Spiking Neural Network (neurons)  ║",
            "║  `         BZ Reaction (chemical spirals)   ║",
            "║  {         Chemotaxis (bacterial colonies)   ║",
            "║  }         MHD Plasma (magnetohydrodynamics) ║",
            "║  |         Strange Attractors (chaotic ODEs) ║",
            "║  ^         Quantum Walk (interference patterns)║",
            "║  \"         Galaxy Formation (spiral dynamics)║",
            "║  Ctrl+D    Navier-Stokes Fluid (dye advection)║",
            "║  Ctrl+R    Rayleigh-Bénard Convection cells   ║",
            "║  Ctrl+L    Chladni Plate vibration patterns  ║",
            "║  Ctrl+T    Cellular Potts Model (tissue sim)  ║",
            "║  Ctrl+G    Chaos Game / IFS Fractals          ║",
            "║  Ctrl+N    Magnetic Field Lines (particles)  ║",
            "║  G         Record/stop GIF (export frames)   ║",
            "║  i         Import RLE pattern file            ║",
            "║  r         Fill grid randomly                 ║",
            "║  s         Save grid state to file            ║",
            "║  o         Open/load a saved state            ║",
            "║  c         Clear grid                         ║",
            "║  q         Quit                               ║",
            "║  ? / h     Show this help                     ║",
            "║                                              ║",
            "║  Press any key to close help                  ║",
            "╚══════════════════════════════════════════════╝",
        ]
        start_y = max(0, (max_y - len(help_lines)) // 2)
        for i, line in enumerate(help_lines):
            y = start_y + i
            if y >= max_y:
                break
            x = max(0, (max_x - len(line)) // 2)
            try:
                self.stdscr.addstr(y, x, line, curses.color_pair(7))
            except curses.error:
                pass


    def _draw_pattern_menu(self, max_y: int, max_x: int):
        if self.stamp_menu:
            title = "── Stamp Pattern at Cursor (Enter=stamp, q/Esc=cancel) ──"
        else:
            title = "── Select Pattern (Enter=load, q/Esc=cancel) ──"
        try:
            self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                               curses.color_pair(7) | curses.A_BOLD)
        except curses.error:
            pass

        for i, name in enumerate(self.pattern_list):
            y = 3 + i
            if y >= max_y - 1:
                break
            pat = self._get_pattern(name)
            desc = pat["description"] if pat else ""
            is_bp = name in self.blueprints
            prefix = "[BP] " if is_bp else ""
            line = f"  {prefix}{name:<20s} {desc}"
            line = line[:max_x - 2]
            attr = curses.color_pair(6)
            if i == self.pattern_sel:
                attr = curses.color_pair(7) | curses.A_REVERSE
            try:
                self.stdscr.addstr(y, 2, line, attr)
            except curses.error:
                pass


    # ══════════════════════════════════════════════════════════════════════
    #  Wave Function Collapse (WFC) — Mode X
    # ══════════════════════════════════════════════════════════════════════

    # Tile characters for rendering collapsed cells
    # ── Reaction-Diffusion (Gray-Scott) Texture Generator ──────────────────
    # Two chemicals U, V on a continuous grid.
    # dU/dt = Du*∇²U - U*V² + f*(1-U)
    # dV/dt = Dv*∇²V + U*V² - (f+k)*V
    # Small parameter changes produce dramatically different self-organizing patterns.

    RD_PRESETS = [
        # (name, description, feed_rate, kill_rate)
        # ── Classic patterns ──
        ("Coral Growth",    "Branching coral-like tendrils that fill space",    0.0545, 0.062),
        ("Mitosis",         "Self-replicating spots that divide like cells",    0.0367, 0.0649),
        ("Fingerprints",    "Labyrinthine stripes like fingerprint whorls",     0.025,  0.060),
        ("Spots (α)",       "Circular spots that tile the plane",              0.035,  0.065),
        ("Worms",           "Moving worm-like solitons",                       0.078,  0.061),
        # ── Exotic patterns ──
        ("Spirals",         "Rotating spiral waves and vortices",              0.014,  0.054),
        ("Maze",            "Dense maze-like labyrinth pattern",               0.029,  0.057),
        ("Chaos",           "Turbulent chaotic mixing regime",                 0.026,  0.051),
        ("Pulsing Spots",   "Spots that breathe and oscillate in place",       0.025,  0.062),
        ("Negatons",        "Moving dark spots in a bright field",             0.046,  0.063),
        # ── Biological analogues ──
        ("Cell Division",   "Blobs that grow, pinch, and divide",             0.0378, 0.0649),
        ("Bacteria",        "Dense colony growth with fractal edges",          0.035,  0.057),
        ("Lichen",          "Slow-growing crusty lichen-like patches",         0.039,  0.065),
        ("Bubbles",         "Hollow ring-shaped bubble structures",            0.012,  0.052),
        ("Ripples",         "Expanding concentric wave rings",                 0.018,  0.051),
    ]

    # Unicode density glyphs for V concentration rendering
    RD_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]

    WFC_TILE_CHARS = [
        ("░░", 2),   # 0: grass/ground  (green)
        ("██", 4),   # 1: water          (blue)
        ("▓▓", 3),   # 2: sand/beach     (yellow)
        ("╬╬", 1),   # 3: forest/trees   (green bold)
        ("∧∧", 6),   # 4: mountains      (white)
        ("~~", 4),   # 5: river          (blue bold)
        ("##", 5),   # 6: town/building  (magenta)
        ("⌂⌂", 7),   # 7: house          (cyan)
        ("≈≈", 4),   # 8: deep water     (blue dim)
        ("··", 2),   # 9: path           (yellow dim)
    ]

    WFC_UNCOLLAPSED_CHAR = "??"

    # Presets define tile sets with adjacency rules
    # Each preset: (name, description, num_tiles, tile_names, adjacency_rules)
    # adjacency_rules: dict of tile_idx -> {"N": {allowed}, "S": {allowed}, "E": {allowed}, "W": {allowed}}
    WFC_PRESETS = [
        ("Island", "Land masses surrounded by ocean",
         5, ["water", "sand", "grass", "forest", "mountain"],
         {
             0: {"N": {0, 1}, "S": {0, 1}, "E": {0, 1}, "W": {0, 1}},           # water near water/sand
             1: {"N": {0, 1, 2}, "S": {0, 1, 2}, "E": {0, 1, 2}, "W": {0, 1, 2}},  # sand near water/sand/grass
             2: {"N": {1, 2, 3}, "S": {1, 2, 3}, "E": {1, 2, 3}, "W": {1, 2, 3}},  # grass near sand/grass/forest
             3: {"N": {2, 3, 4}, "S": {2, 3, 4}, "E": {2, 3, 4}, "W": {2, 3, 4}},  # forest near grass/forest/mountain
             4: {"N": {3, 4}, "S": {3, 4}, "E": {3, 4}, "W": {3, 4}},             # mountain near forest/mountain
         }),
        ("Coastline", "Detailed coast with rivers and beaches",
         4, ["deep water", "water", "sand", "grass"],
         {
             0: {"N": {0, 1}, "S": {0, 1}, "E": {0, 1}, "W": {0, 1}},           # deep near deep/water
             1: {"N": {0, 1, 2}, "S": {0, 1, 2}, "E": {0, 1, 2}, "W": {0, 1, 2}},  # water near deep/water/sand
             2: {"N": {1, 2, 3}, "S": {1, 2, 3}, "E": {1, 2, 3}, "W": {1, 2, 3}},  # sand near water/sand/grass
             3: {"N": {2, 3}, "S": {2, 3}, "E": {2, 3}, "W": {2, 3}},             # grass near sand/grass
         }),
        ("Village", "Towns and paths among fields",
         5, ["grass", "path", "house", "town", "forest"],
         {
             0: {"N": {0, 1, 4}, "S": {0, 1, 4}, "E": {0, 1, 4}, "W": {0, 1, 4}},     # grass near grass/path/forest
             1: {"N": {0, 1, 2, 3}, "S": {0, 1, 2, 3}, "E": {0, 1, 2, 3}, "W": {0, 1, 2, 3}},  # path near most
             2: {"N": {0, 1, 2, 3}, "S": {0, 1, 2, 3}, "E": {0, 1, 2, 3}, "W": {0, 1, 2, 3}},  # house near most
             3: {"N": {1, 2, 3}, "S": {1, 2, 3}, "E": {1, 2, 3}, "W": {1, 2, 3}},     # town near path/house/town
             4: {"N": {0, 4}, "S": {0, 4}, "E": {0, 4}, "W": {0, 4}},                 # forest near grass/forest
         }),
        ("Maze", "Winding corridors and walls",
         2, ["wall", "corridor"],
         {
             0: {"N": {0, 1}, "S": {0, 1}, "E": {0, 1}, "W": {0, 1}},  # wall near anything
             1: {"N": {0, 1}, "S": {0, 1}, "E": {0, 1}, "W": {0, 1}},  # corridor near anything
         }),
        ("Terrain", "Mountains, forests, grasslands, rivers",
         6, ["water", "sand", "grass", "forest", "mountain", "river"],
         {
             0: {"N": {0, 1, 5}, "S": {0, 1, 5}, "E": {0, 1, 5}, "W": {0, 1, 5}},
             1: {"N": {0, 1, 2}, "S": {0, 1, 2}, "E": {0, 1, 2}, "W": {0, 1, 2}},
             2: {"N": {1, 2, 3, 5}, "S": {1, 2, 3, 5}, "E": {1, 2, 3, 5}, "W": {1, 2, 3, 5}},
             3: {"N": {2, 3, 4}, "S": {2, 3, 4}, "E": {2, 3, 4}, "W": {2, 3, 4}},
             4: {"N": {3, 4}, "S": {3, 4}, "E": {3, 4}, "W": {3, 4}},
             5: {"N": {0, 2, 5}, "S": {0, 2, 5}, "E": {0, 2, 5}, "W": {0, 2, 5}},
         }),
        ("Dungeon", "Rooms and corridors in a dark dungeon",
         4, ["wall", "floor", "corridor", "door"],
         {
             0: {"N": {0, 1, 2, 3}, "S": {0, 1, 2, 3}, "E": {0, 1, 2, 3}, "W": {0, 1, 2, 3}},
             1: {"N": {0, 1, 3}, "S": {0, 1, 3}, "E": {0, 1, 3}, "W": {0, 1, 3}},
             2: {"N": {0, 2, 3}, "S": {0, 2, 3}, "E": {0, 2, 3}, "W": {0, 2, 3}},
             3: {"N": {1, 2}, "S": {1, 2}, "E": {1, 2}, "W": {1, 2}},
         }),
    ]

    # Tile display mapping per preset (index into WFC_TILE_CHARS or custom)
    WFC_PRESET_TILES = [
        [1, 2, 0, 3, 4],              # Island: water, sand, grass, forest, mountain
        [8, 1, 2, 0],                  # Coastline: deep water, water, sand, grass
        [0, 9, 7, 6, 3],              # Village: grass, path, house, town, forest
        [4, 0],                        # Maze: wall=water(blue), corridor=grass(green)
        [1, 2, 0, 3, 4, 5],           # Terrain: water, sand, grass, forest, mountain, river
        [4, 0, 9, 2],                  # Dungeon: wall=water, floor=grass, corridor=path, door=sand
    ]



# Register all simulation modes on the App class
from life.modes import register_all_modes
register_all_modes(App)


def main():
    parser = argparse.ArgumentParser(description="Conway's Game of Life — terminal edition")
    parser.add_argument(
        "-p", "--pattern",
        choices=sorted(PATTERNS.keys()),
        help="Start with a preset pattern",
    )
    parser.add_argument(
        "--rows", type=int, default=80,
        help="Grid height (default: 80)",
    )
    parser.add_argument(
        "--cols", type=int, default=120,
        help="Grid width (default: 120)",
    )
    parser.add_argument(
        "--list-patterns", action="store_true",
        help="List available patterns and exit",
    )
    parser.add_argument(
        "--no-dashboard", action="store_true",
        help="Skip the dashboard and start directly in Game of Life mode",
    )
    parser.add_argument(
        "--screensaver", nargs="?", const="all_shuffle", default=None,
        metavar="PRESET",
        help="Launch screensaver/demo reel mode (presets: all_sequential, all_shuffle, fav_sequential, fav_shuffle)",
    )
    parser.add_argument(
        "--screensaver-interval", type=int, default=15,
        metavar="SECONDS",
        help="Seconds per mode in screensaver mode (default: 15)",
    )
    parser.add_argument(
        "--host", type=int, nargs="?", const=MP_DEFAULT_PORT, default=None,
        metavar="PORT",
        help=f"Host a multiplayer game (default port: {MP_DEFAULT_PORT})",
    )
    parser.add_argument(
        "--connect", type=str, default=None,
        metavar="HOST:PORT",
        help="Connect to a multiplayer game (e.g. 192.168.1.5:7654)",
    )
    args = parser.parse_args()

    if args.list_patterns:
        print("Available patterns:")
        for name in sorted(PATTERNS.keys()):
            print(f"  {name:<20s} {PATTERNS[name]['description']}")
        sys.exit(0)

    def start(stdscr):
        app = App(stdscr, args.pattern, args.rows, args.cols)
        # Screensaver mode
        if args.screensaver is not None:
            app.screensaver_interval = args.screensaver_interval
            app._screensaver_init(args.screensaver)
        # Show dashboard on startup unless a pattern, multiplayer, or --no-dashboard is specified
        elif args.pattern is None and args.host is None and args.connect is None and not args.no_dashboard:
            app._dashboard_init()
        # Auto-start multiplayer if CLI flags given
        if args.host is not None:
            app.mp_host_port = args.host
            net = MultiplayerNet()
            if not net.start_host(args.host):
                app._flash(f"Cannot bind to port {args.host}")
            else:
                app.mp_net = net
                app.mp_mode = True
                app.mp_role = "host"
                app.mp_player = 1
                app.mp_phase = "lobby"
                app.running = False
                app._flash(f"Hosting on port {args.host} — waiting for opponent...")
        elif args.connect is not None:
            addr = args.connect
            if ":" in addr:
                parts = addr.rsplit(":", 1)
                host, port = parts[0], int(parts[1])
            else:
                host, port = addr, MP_DEFAULT_PORT
            net = MultiplayerNet()
            if not net.connect(host, port):
                app._flash(f"Cannot connect to {host}:{port}")
            else:
                app.mp_net = net
                app.mp_mode = True
                app.mp_role = "client"
                app.mp_player = 2
                app.mp_phase = "lobby"
                app.running = False
                app.mp_connect_addr = addr
                app._flash("Connected! Waiting for game setup...")
        app.run()

    try:
        curses.wrapper(start)
    except KeyboardInterrupt:
        pass




if __name__ == "__main__":
    main()
