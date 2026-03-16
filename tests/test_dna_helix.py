"""Tests for life.modes.dna_helix — DNA Helix & GA mode."""
import curses
from tests.conftest import make_mock_app
from life.modes.dna_helix import register, DNAHELIX_PRESETS


def _make_app():
    app = make_mock_app()
    app.dnahelix_mode = False
    app.dnahelix_menu = False
    app.dnahelix_menu_sel = 0
    app.dnahelix_running = False
    app.dnahelix_speed = 1
    app.dnahelix_show_info = False
    app.dnahelix_population = []
    app.dnahelix_target = []
    app.dnahelix_best_genome = []
    app.dnahelix_fitness_history = []
    app.dnahelix_solved = False
    register(type(app))
    return app


# ── Entry / Exit ──

def test_enter():
    app = _make_app()
    app._enter_dnahelix_mode()
    assert app.dnahelix_menu is True
    assert app.dnahelix_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.dnahelix_mode = True
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app._exit_dnahelix_mode()
    assert app.dnahelix_mode is False
    assert app.dnahelix_population == []
    assert app.dnahelix_target == []
    assert app.dnahelix_best_genome == []
    assert app.dnahelix_fitness_history == []
    assert app.dnahelix_solved is False


# ── GA Initialization ──

def test_init_classic():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    assert app.dnahelix_genome_len == 32
    assert app.dnahelix_pop_size == 40
    assert len(app.dnahelix_population) == 40
    assert all(len(g) == 32 for g in app.dnahelix_population)
    assert len(app.dnahelix_target) == 32


def test_init_onemax():
    app = _make_app()
    app.dnahelix_preset_name = "onemax"
    app._dnahelix_init("onemax")
    assert app.dnahelix_genome_len == 64
    assert app.dnahelix_target == [1] * 64


def test_init_royal():
    app = _make_app()
    app.dnahelix_preset_name = "royal"
    app._dnahelix_init("royal")
    assert app.dnahelix_target == [1] * 64


def test_init_all_presets():
    """All 6 presets initialize without error."""
    app = _make_app()
    for _, _, key in DNAHELIX_PRESETS:
        app.dnahelix_preset_name = key
        app._dnahelix_init(key)
        assert len(app.dnahelix_population) > 0
        assert len(app.dnahelix_target) == app.dnahelix_genome_len


def test_init_unknown_preset_defaults():
    app = _make_app()
    app.dnahelix_preset_name = "unknown"
    app._dnahelix_init("unknown")
    assert app.dnahelix_genome_len == 32
    assert app.dnahelix_pop_size == 40


# ── Fitness function ──

def test_fitness_perfect_match():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    # Perfect match
    fit = app._dnahelix_fitness(app.dnahelix_target[:])
    assert fit == 1.0


def test_fitness_no_match():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    # Opposite of target
    anti = [1 - b for b in app.dnahelix_target]
    fit = app._dnahelix_fitness(anti)
    assert fit == 0.0


def test_fitness_royal_road():
    app = _make_app()
    app.dnahelix_preset_name = "royal"
    app._dnahelix_init("royal")
    # All ones = perfect for royal road
    fit = app._dnahelix_fitness([1] * 64)
    assert fit == 1.0
    # All zeros = no blocks match
    fit = app._dnahelix_fitness([0] * 64)
    assert fit == 0.0


def test_fitness_royal_road_partial():
    app = _make_app()
    app.dnahelix_preset_name = "royal"
    app._dnahelix_init("royal")
    # First block all 1s, rest all 0s
    genome = [1] * 8 + [0] * 56
    fit = app._dnahelix_fitness(genome)
    assert fit == 1.0 / 8.0  # 1 out of 8 blocks


# ── GA step ──

def test_step_no_crash():
    app = _make_app()
    app.dnahelix_mode = True
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    for _ in range(10):
        app._dnahelix_step()
    assert app.dnahelix_generation == 10


def test_step_advances_generation():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app._dnahelix_step()
    assert app.dnahelix_generation == 1
    assert app.dnahelix_phase != 0.0  # phase advances


def test_step_maintains_population_size():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    for _ in range(10):
        app._dnahelix_step()
    assert len(app.dnahelix_population) == app.dnahelix_pop_size


def test_step_records_fitness_history():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    for _ in range(5):
        app._dnahelix_step()
    # init evaluate + 5 steps = 6 entries
    assert len(app.dnahelix_fitness_history) == 6


def test_step_does_nothing_when_solved():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app.dnahelix_solved = True
    gen_before = app.dnahelix_generation
    app._dnahelix_step()
    assert app.dnahelix_generation == gen_before  # no advance


def test_elitism_preserves_best():
    """The best individual from one generation should survive into the next."""
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    # Get best before step
    best_before = app.dnahelix_best_genome[:]
    best_fit_before = app.dnahelix_best_fitness
    app._dnahelix_step()
    # Best fitness should not decrease (elitism)
    assert app.dnahelix_best_fitness >= best_fit_before


# ── Menu key handling ──

def test_menu_key_down():
    app = _make_app()
    app._enter_dnahelix_mode()
    app._handle_dnahelix_menu_key(curses.KEY_DOWN)
    assert app.dnahelix_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_dnahelix_mode()
    app._handle_dnahelix_menu_key(curses.KEY_UP)
    assert app.dnahelix_menu_sel == len(DNAHELIX_PRESETS) - 1


def test_menu_key_enter_starts():
    app = _make_app()
    app._enter_dnahelix_mode()
    app._handle_dnahelix_menu_key(10)
    assert app.dnahelix_mode is True
    assert app.dnahelix_running is True
    assert app.dnahelix_menu is False


def test_menu_key_quit():
    app = _make_app()
    app._enter_dnahelix_mode()
    app.dnahelix_mode = True
    app._handle_dnahelix_menu_key(ord('q'))
    assert app.dnahelix_mode is False


# ── Simulation key handling ──

def test_key_space_toggles_running():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app.dnahelix_running = True
    app._handle_dnahelix_key(ord(' '))
    assert app.dnahelix_running is False


def test_key_n_steps():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    gen_before = app.dnahelix_generation
    app._handle_dnahelix_key(ord('n'))
    assert app.dnahelix_generation == gen_before + 1


def test_key_r_resets():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    for _ in range(5):
        app._dnahelix_step()
    app._handle_dnahelix_key(ord('r'))
    assert app.dnahelix_generation == 0


def test_key_plus_minus_speed():
    app = _make_app()
    app.dnahelix_speed = 5
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app._handle_dnahelix_key(ord('+'))
    assert app.dnahelix_speed == 6
    app._handle_dnahelix_key(ord('-'))
    assert app.dnahelix_speed == 5


def test_key_q_exits():
    app = _make_app()
    app.dnahelix_mode = True
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app._handle_dnahelix_key(ord('q'))
    assert app.dnahelix_mode is False


# ── Drawing (no crash) ──

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_dnahelix_mode()
    app._draw_dnahelix_menu(40, 120)


def test_draw_dnahelix_no_crash():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app.dnahelix_show_info = True
    for _ in range(5):
        app._dnahelix_step()
    app._draw_dnahelix(40, 120)


def test_draw_dnahelix_small_terminal():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app._draw_dnahelix(5, 10)  # too small


def test_draw_dnahelix_solved():
    app = _make_app()
    app.dnahelix_preset_name = "classic"
    app._dnahelix_init("classic")
    app.dnahelix_solved = True
    app._draw_dnahelix(40, 120)


# ── Presets data ──

def test_presets_structure():
    assert len(DNAHELIX_PRESETS) == 6
    for name, desc, key in DNAHELIX_PRESETS:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str)
        assert key in ("classic", "onemax", "long", "hyper", "minimal", "royal")
