"""Tests for life.modes.artificial_life — Artificial Life mode."""
import math
import random

from tests.conftest import make_mock_app
from life.modes.artificial_life import (
    register,
    ALIFE_PRESETS,
    ALIFE_HERB_CHARS,
    ALIFE_PRED_CHARS,
    ALIFE_OMNI_CHARS,
)


def _make_app():
    app = make_mock_app()
    app.alife_mode = False
    app.alife_menu = False
    app.alife_menu_sel = 0
    app.alife_running = False
    app.alife_generation = 0
    app.alife_tick = 0
    app.alife_preset_name = ""
    app.alife_rows = 0
    app.alife_cols = 0
    app.alife_creatures = []
    app.alife_food = []
    app.alife_next_id = 0
    app.alife_food_regrow = 0.02
    app.alife_mutation_rate = 0.15
    app.alife_speed_scale = 1.0
    app.alife_gen_max = 0
    app.alife_total_births = 0
    app.alife_total_deaths = 0
    app.alife_pop_history = []
    app.alife_herb_history = []
    app.alife_pred_history = []
    app.alife_show_stats = True
    register(type(app))
    return app


# ── Constants validation ─────────────────────────────────────────────────────

def test_presets_count():
    assert len(ALIFE_PRESETS) == 6


def test_presets_have_three_fields():
    for p in ALIFE_PRESETS:
        assert len(p) == 3  # (name, desc, ptype)


def test_herb_chars_original():
    """ALIFE_HERB_CHARS should be lists matching the original monolith."""
    assert ALIFE_HERB_CHARS == ["\u00b7", "o", "O", "0", "@"]
    assert len(ALIFE_HERB_CHARS) == 5


def test_pred_chars_original():
    assert ALIFE_PRED_CHARS == [":", "x", "X", "%", "&"]
    assert len(ALIFE_PRED_CHARS) == 5


def test_omni_chars_original():
    assert ALIFE_OMNI_CHARS == [",", "s", "S", "$", "#"]
    assert len(ALIFE_OMNI_CHARS) == 5


def test_register_sets_class_constants():
    app = _make_app()
    assert type(app).ALIFE_PRESETS == ALIFE_PRESETS
    assert type(app).ALIFE_HERB_CHARS == ALIFE_HERB_CHARS
    assert type(app).ALIFE_PRED_CHARS == ALIFE_PRED_CHARS
    assert type(app).ALIFE_OMNI_CHARS == ALIFE_OMNI_CHARS


# ── Enter / exit ─────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_alife_mode()
    assert app.alife_menu is True
    assert app.alife_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._alife_init(5)  # Primordial Soup (fewest creatures)
    app._exit_alife_mode()
    assert app.alife_mode is False
    assert app.alife_menu is False
    assert app.alife_running is False
    assert app.alife_creatures == []
    assert app.alife_food == []
    assert app.alife_pop_history == []


# ── Init per preset ──────────────────────────────────────────────────────────

def test_init_soup_preset():
    app = _make_app()
    app._alife_init(5)  # Primordial Soup
    assert app.alife_mode is True
    assert app.alife_running is True
    assert app.alife_menu is False
    assert app.alife_preset_name == "Primordial Soup"
    assert len(app.alife_creatures) > 0
    assert len(app.alife_food) > 0


def test_init_grassland():
    app = _make_app()
    app._alife_init(0)
    assert app.alife_preset_name == "Grassland"
    n_herb = sum(1 for cr in app.alife_creatures if cr["diet"] == 0)
    assert n_herb == 40


def test_init_predprey():
    app = _make_app()
    app._alife_init(1)
    assert app.alife_preset_name == "Predator-Prey"
    n_pred = sum(1 for cr in app.alife_creatures if cr["diet"] == 1)
    assert n_pred == 8


def test_init_reef():
    app = _make_app()
    app._alife_init(3)  # Coral Reef
    n_omni = sum(1 for cr in app.alife_creatures if cr["diet"] == 2)
    assert n_omni == 10


def test_init_all_presets():
    """All preset indices should initialize without error."""
    app = _make_app()
    for idx in range(len(ALIFE_PRESETS)):
        app._alife_init(idx)
        assert app.alife_mode is True
        assert app.alife_tick == 0
        assert app.alife_generation == 0


# ── Creature creation ────────────────────────────────────────────────────────

def test_make_creature_defaults():
    app = _make_app()
    app.alife_next_id = 0
    cr = app._alife_make_creature(10.0, 20.0)
    assert cr["id"] == 0
    assert cr["r"] == 10.0
    assert cr["c"] == 20.0
    assert cr["diet"] == 0
    assert cr["energy"] > 0
    assert cr["age"] == 0
    assert cr["kills"] == 0
    assert cr["children"] == 0
    assert len(cr["brain"]) == 6 * 4 + 4 * 2  # 32 weights


def test_make_creature_id_increments():
    app = _make_app()
    app.alife_next_id = 0
    c1 = app._alife_make_creature(5.0, 5.0)
    c2 = app._alife_make_creature(6.0, 6.0)
    assert c1["id"] == 0
    assert c2["id"] == 1


def test_make_creature_clamps_traits():
    """Speed, size, sense should be clamped to valid ranges."""
    app = _make_app()
    app.alife_next_id = 0
    cr = app._alife_make_creature(0, 0, speed=100.0, size=100.0, sense=100.0)
    assert cr["speed"] <= 3.0
    assert cr["size"] <= 3.0
    assert cr["sense"] <= 15.0
    cr2 = app._alife_make_creature(0, 0, speed=0.01, size=0.01, sense=0.1)
    assert cr2["speed"] >= 0.3
    assert cr2["size"] >= 0.5
    assert cr2["sense"] >= 2.0


def test_make_creature_custom_brain():
    app = _make_app()
    app.alife_next_id = 0
    brain = [0.5] * 32
    cr = app._alife_make_creature(0, 0, brain=brain)
    assert cr["brain"] is brain


# ── Neural network ───────────────────────────────────────────────────────────

def test_brain_forward_shape():
    app = _make_app()
    brain = [0.0] * 32
    inputs = [0.0, 0.0, 0.0, 0.0, 0.5, 1.0]
    dr, dc = app._alife_brain_forward(brain, inputs)
    assert isinstance(dr, float)
    assert isinstance(dc, float)
    assert -1.0 <= dr <= 1.0
    assert -1.0 <= dc <= 1.0


def test_brain_forward_zero_weights():
    """Zero weights should produce tanh(0) = 0."""
    app = _make_app()
    brain = [0.0] * 32
    dr, dc = app._alife_brain_forward(brain, [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    assert dr == 0.0
    assert dc == 0.0


def test_brain_forward_nonzero_output():
    """Non-zero weights should produce non-zero outputs."""
    app = _make_app()
    brain = [1.0] * 32
    inputs = [1.0, 0.0, 0.0, 0.0, 0.5, 1.0]
    dr, dc = app._alife_brain_forward(brain, inputs)
    assert dr != 0.0 or dc != 0.0


def test_brain_forward_bounded():
    """Outputs must be in [-1, 1] due to tanh."""
    app = _make_app()
    random.seed(42)
    for _ in range(50):
        brain = [random.gauss(0, 2.0) for _ in range(32)]
        inputs = [random.gauss(0, 1.0) for _ in range(6)]
        dr, dc = app._alife_brain_forward(brain, inputs)
        assert -1.0 <= dr <= 1.0
        assert -1.0 <= dc <= 1.0


# ── Mutation ─────────────────────────────────────────────────────────────────

def test_mutate_brain_preserves_length():
    app = _make_app()
    app.alife_mutation_rate = 0.5
    brain = [0.0] * 32
    mutated = app._alife_mutate_brain(brain)
    assert len(mutated) == 32


def test_mutate_brain_returns_new_list():
    app = _make_app()
    app.alife_mutation_rate = 0.5
    brain = [1.0] * 32
    mutated = app._alife_mutate_brain(brain)
    assert mutated is not brain


def test_mutate_brain_changes_some_weights():
    """With high mutation rate, at least some weights should change."""
    app = _make_app()
    app.alife_mutation_rate = 1.0  # mutate every weight
    random.seed(42)
    brain = [0.0] * 32
    mutated = app._alife_mutate_brain(brain)
    assert any(m != 0.0 for m in mutated)


# ── Step / simulation ────────────────────────────────────────────────────────

def test_step_no_crash():
    app = _make_app()
    app._alife_init(5)  # Primordial Soup
    for _ in range(10):
        app._alife_step()
    assert app.alife_generation == 10


def test_step_increments_tick():
    app = _make_app()
    app._alife_init(5)
    app._alife_step()
    assert app.alife_tick == 1


def test_step_tracks_population():
    app = _make_app()
    app._alife_init(5)
    app._alife_step()
    assert len(app.alife_pop_history) == 1
    assert len(app.alife_herb_history) == 1
    assert len(app.alife_pred_history) == 1


def test_step_respawns_on_extinction():
    """If all creatures die, the step should respawn some."""
    app = _make_app()
    app._alife_init(5)
    app.alife_creatures = []  # force extinction
    app._alife_step()
    assert len(app.alife_creatures) >= 5


def test_step_creatures_age():
    app = _make_app()
    app._alife_init(5)
    initial_ages = [cr["age"] for cr in app.alife_creatures]
    app._alife_step()
    for cr in app.alife_creatures:
        # All surviving creatures should be age 1 (started at 0)
        assert cr["age"] >= 1


def test_step_energy_decreases():
    """Creatures should lose energy each step from movement/metabolism."""
    app = _make_app()
    app._alife_init(5)
    # Pick one creature
    cr = app.alife_creatures[0]
    initial_energy = cr["energy"]
    # Remove all food so it can't eat
    for r in range(app.alife_rows):
        for c in range(app.alife_cols):
            app.alife_food[r][c] = 0.0
    app._alife_step()
    # The creature (if alive) should have less energy
    alive = [c for c in app.alife_creatures if c["id"] == cr["id"]]
    if alive:
        assert alive[0]["energy"] < initial_energy


def test_step_food_regrows():
    app = _make_app()
    app._alife_init(5)
    # Zero out all food
    for r in range(app.alife_rows):
        for c in range(app.alife_cols):
            app.alife_food[r][c] = 0.5  # partially filled
    app._alife_step()
    # At least some cells should have increased
    has_growth = False
    for r in range(app.alife_rows):
        for c in range(app.alife_cols):
            if app.alife_food[r][c] > 0.5:
                has_growth = True
                break
        if has_growth:
            break
    assert has_growth


def test_step_population_history_capped():
    app = _make_app()
    app._alife_init(5)
    for _ in range(250):
        app._alife_step()
    assert len(app.alife_pop_history) <= 200


def test_step_no_crash_with_zero_dimensions():
    """Should return early without crashing if rows or cols is 0."""
    app = _make_app()
    app._alife_init(5)
    app.alife_rows = 0
    app.alife_cols = 0
    app._alife_step()  # should not raise


# ── Key handling — menu ──────────────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_alife_mode()
    import curses as _c
    app._handle_alife_menu_key(ord("j"))
    assert app.alife_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_alife_mode()
    app._handle_alife_menu_key(ord("k"))
    assert app.alife_menu_sel == len(ALIFE_PRESETS) - 1


def test_menu_select():
    app = _make_app()
    app._enter_alife_mode()
    app.alife_menu_sel = 1
    app._handle_alife_menu_key(10)  # Enter
    assert app.alife_mode is True
    assert app.alife_preset_name == "Predator-Prey"


def test_menu_cancel():
    app = _make_app()
    app._enter_alife_mode()
    app._handle_alife_menu_key(ord("q"))
    assert app.alife_menu is False


# ── Key handling — active sim ────────────────────────────────────────────────

def test_key_space_toggles():
    app = _make_app()
    app._alife_init(5)
    assert app.alife_running is True
    app._handle_alife_key(ord(" "))
    assert app.alife_running is False


def test_key_n_single_step():
    app = _make_app()
    app._alife_init(5)
    old_gen = app.alife_generation
    app._handle_alife_key(ord("n"))
    assert app.alife_generation == old_gen + 1


def test_key_s_toggles_stats():
    app = _make_app()
    app._alife_init(5)
    assert app.alife_show_stats is True
    app._handle_alife_key(ord("s"))
    assert app.alife_show_stats is False


def test_key_plus_increases_food_regrow():
    app = _make_app()
    app._alife_init(5)
    old_rate = app.alife_food_regrow
    app._handle_alife_key(ord("+"))
    assert app.alife_food_regrow > old_rate


def test_key_minus_decreases_food_regrow():
    app = _make_app()
    app._alife_init(5)
    old_rate = app.alife_food_regrow
    app._handle_alife_key(ord("-"))
    assert app.alife_food_regrow < old_rate


def test_key_f_scatters_food():
    app = _make_app()
    app._alife_init(5)
    # Zero food first
    for r in range(app.alife_rows):
        for c in range(app.alife_cols):
            app.alife_food[r][c] = 0.0
    app._handle_alife_key(ord("f"))
    total = sum(app.alife_food[r][c] for r in range(app.alife_rows) for c in range(app.alife_cols))
    assert total > 0


def test_key_speed_scale():
    app = _make_app()
    app._alife_init(5)
    old = app.alife_speed_scale
    app._handle_alife_key(ord(">"))
    assert app.alife_speed_scale > old
    old = app.alife_speed_scale
    app._handle_alife_key(ord("<"))
    assert app.alife_speed_scale < old


def test_key_r_resets():
    app = _make_app()
    app._alife_init(0)  # Grassland
    for _ in range(5):
        app._alife_step()
    app._handle_alife_key(ord("r"))
    assert app.alife_tick == 0
    assert app.alife_generation == 0


def test_key_m_returns_to_menu():
    app = _make_app()
    app._alife_init(5)
    app._handle_alife_key(ord("m"))
    assert app.alife_menu is True
    assert app.alife_mode is False


def test_key_q_exits():
    app = _make_app()
    app._alife_init(5)
    app._handle_alife_key(ord("q"))
    assert app.alife_mode is False
    assert app.alife_running is False


# ── Reproduction and death ───────────────────────────────────────────────────

def test_creature_dies_when_energy_zero():
    """A creature with zero energy should die on next step."""
    app = _make_app()
    app._alife_init(5)
    for cr in app.alife_creatures:
        cr["energy"] = 0.0
    initial_ids = {cr["id"] for cr in app.alife_creatures}
    app._alife_step()
    surviving_ids = {cr["id"] for cr in app.alife_creatures}
    # Most original creatures should be dead (respawns have new ids)
    dead = initial_ids - surviving_ids
    assert len(dead) > 0


def test_creature_dies_of_old_age():
    """A creature exceeding max age should die."""
    app = _make_app()
    app._alife_init(5)
    for cr in app.alife_creatures:
        cr["age"] = 99999  # way past max
        cr["energy"] = 100.0  # keep energy high
    app._alife_step()
    # All originals should be dead (they were too old)
    assert app.alife_total_deaths > 0


def test_reproduction_when_energy_high():
    """High-energy, old-enough creatures should eventually reproduce."""
    app = _make_app()
    app._alife_init(5)
    random.seed(42)
    # Give creatures high energy and enough age
    for cr in app.alife_creatures:
        cr["energy"] = cr["max_energy"]
        cr["age"] = 100
    births_before = app.alife_total_births
    # Run many steps to get at least one reproduction
    for _ in range(100):
        # Keep energy topped up
        for cr in app.alife_creatures:
            cr["energy"] = cr["max_energy"]
            cr["age"] = 100
        app._alife_step()
    assert app.alife_total_births > births_before
