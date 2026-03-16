"""Tests for life.modes.aquarium — ASCII Aquarium mode."""
import curses
from tests.conftest import make_mock_app
from life.modes.aquarium import (
    register,
    AQUARIUM_PRESETS,
    FISH_SPECIES,
    BUBBLE_CHARS,
    SAND_CHARS,
    SEAWEED_CHARS,
)


def _make_app():
    app = make_mock_app()
    app.aquarium_mode = False
    app.aquarium_menu = False
    app.aquarium_menu_sel = 0
    app.aquarium_running = False
    app.aquarium_speed = 1
    app.aquarium_show_info = False
    app.aquarium_fish = []
    app.aquarium_seaweed = []
    app.aquarium_bubbles = []
    app.aquarium_food = []
    app.aquarium_sand = []
    register(type(app))
    return app


# ── enter / exit ──────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_aquarium_mode()
    assert app.aquarium_menu is True
    assert app.aquarium_mode is True


def test_exit_cleanup():
    app = _make_app()
    app.aquarium_mode = True
    app._aquarium_init("tropical")
    assert len(app.aquarium_fish) > 0
    app._exit_aquarium_mode()
    assert app.aquarium_mode is False
    assert app.aquarium_fish == []
    assert app.aquarium_seaweed == []
    assert app.aquarium_bubbles == []
    assert app.aquarium_food == []
    assert app.aquarium_sand == []


# ── init presets ──────────────────────────────────────────────────────────

def test_init_goldfish():
    app = _make_app()
    app._aquarium_init("goldfish")
    assert app.aquarium_running is True
    assert 4 <= len(app.aquarium_fish) <= 7


def test_init_tropical():
    app = _make_app()
    app._aquarium_init("tropical")
    assert 10 <= len(app.aquarium_fish) <= 16


def test_init_koi():
    app = _make_app()
    app._aquarium_init("koi")
    assert 6 <= len(app.aquarium_fish) <= 10


def test_init_deep():
    app = _make_app()
    app._aquarium_init("deep")
    assert 5 <= len(app.aquarium_fish) <= 8


def test_init_all_presets():
    for _name, _desc, key in AQUARIUM_PRESETS:
        app = _make_app()
        app._aquarium_init(key)
        assert app.aquarium_running is True
        assert app.aquarium_generation == 0
        assert len(app.aquarium_fish) > 0
        assert len(app.aquarium_seaweed) > 0
        assert len(app.aquarium_sand) > 0
        assert len(app.aquarium_bubbles) > 0


def test_init_sand():
    app = _make_app()
    app._aquarium_init("tropical")
    assert len(app.aquarium_sand) == app.aquarium_cols


def test_init_seaweed():
    app = _make_app()
    app._aquarium_init("tropical")
    for sw in app.aquarium_seaweed:
        assert "x" in sw
        assert "height" in sw
        assert "phase" in sw


def test_init_fish_structure():
    app = _make_app()
    app._aquarium_init("tropical")
    for fish in app.aquarium_fish:
        assert "species" in fish
        assert "x" in fish
        assert "y" in fish
        assert "vx" in fish
        assert "color" in fish
        assert "bob_phase" in fish
        assert "target_y" in fish


# ── spawn_fish ────────────────────────────────────────────────────────────

def test_spawn_fish():
    app = _make_app()
    app._aquarium_init("tropical")
    count_before = len(app.aquarium_fish)
    app._aquarium_spawn_fish([0, 1, 2], 2, 30)
    assert len(app.aquarium_fish) == count_before + 1


# ── step ──────────────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._aquarium_init("tropical")
    app._aquarium_step()
    assert app.aquarium_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.aquarium_mode = True
    app._aquarium_init("tropical")
    for _ in range(10):
        app._aquarium_step()
    assert app.aquarium_generation == 10


def test_step_fish_move():
    """Fish x positions should change over steps."""
    app = _make_app()
    app._aquarium_init("tropical")
    initial_xs = [f["x"] for f in app.aquarium_fish]
    for _ in range(20):
        app._aquarium_step()
    final_xs = [f["x"] for f in app.aquarium_fish]
    assert initial_xs != final_xs


def test_step_bubbles_rise():
    """Bubbles should move upward (decreasing y)."""
    app = _make_app()
    app._aquarium_init("tropical")
    if app.aquarium_bubbles:
        initial_y = app.aquarium_bubbles[0]["y"]
        app._aquarium_step()
        # Bubble y should decrease (moving up)
        assert app.aquarium_bubbles[0]["y"] < initial_y


def test_step_food_sinks():
    """Food should sink (increasing y)."""
    app = _make_app()
    app._aquarium_init("tropical")
    app.aquarium_food.append({"x": 50.0, "y": 5.0, "age": 0})
    app._aquarium_step()
    assert app.aquarium_food[0]["y"] > 5.0


def test_step_food_ages_out():
    """Old food should be removed."""
    app = _make_app()
    app._aquarium_init("tropical")
    app.aquarium_food.append({"x": 50.0, "y": 30.0, "age": 299})
    app._aquarium_step()
    # Should still be there at age 300
    old_food = [f for f in app.aquarium_food if f["age"] >= 300]
    assert len(old_food) == 0


def test_step_startled_decays():
    app = _make_app()
    app._aquarium_init("tropical")
    app.aquarium_startled = 3.0
    app._aquarium_step()
    assert app.aquarium_startled < 3.0


def test_step_all_presets():
    for _name, _desc, key in AQUARIUM_PRESETS:
        app = _make_app()
        app._aquarium_init(key)
        for _ in range(30):
            app._aquarium_step()
        assert app.aquarium_generation == 30


# ── handle_aquarium_menu_key ──────────────────────────────────────────────

def test_menu_navigate():
    app = _make_app()
    app._enter_aquarium_mode()
    app._handle_aquarium_menu_key(curses.KEY_DOWN)
    assert app.aquarium_menu_sel == 1
    app._handle_aquarium_menu_key(curses.KEY_UP)
    assert app.aquarium_menu_sel == 0


def test_menu_wrap():
    app = _make_app()
    app._enter_aquarium_mode()
    app._handle_aquarium_menu_key(curses.KEY_UP)
    assert app.aquarium_menu_sel == len(AQUARIUM_PRESETS) - 1


def test_menu_select():
    app = _make_app()
    app._enter_aquarium_mode()
    app._handle_aquarium_menu_key(10)
    assert app.aquarium_running is True
    assert app.aquarium_menu is False


def test_menu_quit():
    app = _make_app()
    app._enter_aquarium_mode()
    app._handle_aquarium_menu_key(27)
    assert app.aquarium_mode is False


# ── handle_aquarium_key ───────────────────────────────────────────────────

def test_key_space_toggle():
    app = _make_app()
    app._aquarium_init("tropical")
    assert app.aquarium_running is True
    app._handle_aquarium_key(ord(' '))
    assert app.aquarium_running is False


def test_key_feed():
    app = _make_app()
    app._aquarium_init("tropical")
    count_before = len(app.aquarium_food)
    app._handle_aquarium_key(ord('f'))
    assert len(app.aquarium_food) > count_before


def test_key_tap_glass():
    app = _make_app()
    app._aquarium_init("tropical")
    app._handle_aquarium_key(ord('t'))
    assert app.aquarium_startled == 3.0


def test_key_speed():
    app = _make_app()
    app._aquarium_init("tropical")
    app.aquarium_speed = 1
    app._handle_aquarium_key(ord('+'))
    assert app.aquarium_speed == 2
    app._handle_aquarium_key(ord('-'))
    assert app.aquarium_speed == 1


def test_key_speed_bounds():
    app = _make_app()
    app._aquarium_init("tropical")
    app.aquarium_speed = 5
    app._handle_aquarium_key(ord('+'))
    assert app.aquarium_speed == 5  # max
    app.aquarium_speed = 1
    app._handle_aquarium_key(ord('-'))
    assert app.aquarium_speed == 1  # min


def test_key_add_fish():
    app = _make_app()
    app._aquarium_init("tropical")
    count = len(app.aquarium_fish)
    app._handle_aquarium_key(ord('a'))
    assert len(app.aquarium_fish) == count + 1


def test_key_remove_fish():
    app = _make_app()
    app._aquarium_init("tropical")
    count = len(app.aquarium_fish)
    app._handle_aquarium_key(ord('d'))
    assert len(app.aquarium_fish) == count - 1


def test_key_add_bubble():
    app = _make_app()
    app._aquarium_init("tropical")
    count = len(app.aquarium_bubbles)
    app._handle_aquarium_key(ord('b'))
    assert len(app.aquarium_bubbles) == count + 1


def test_key_info_toggle():
    app = _make_app()
    app._aquarium_init("tropical")
    app._handle_aquarium_key(ord('i'))
    assert app.aquarium_show_info is True


def test_key_escape_to_menu():
    app = _make_app()
    app._aquarium_init("tropical")
    app._handle_aquarium_key(27)
    assert app.aquarium_menu is True
    assert app.aquarium_running is False


def test_key_quit():
    app = _make_app()
    app._aquarium_init("tropical")
    app._handle_aquarium_key(ord('q'))
    assert app.aquarium_mode is False


def test_key_return_to_menu():
    app = _make_app()
    app._aquarium_init("tropical")
    app._handle_aquarium_key(ord('R'))
    assert app.aquarium_menu is True
    assert app.aquarium_running is False


# ── draw (no crash) ──────────────────────────────────────────────────────

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_aquarium_mode()
    app._draw_aquarium_menu(40, 120)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._aquarium_init("tropical")
    for _ in range(5):
        app._aquarium_step()
    app._draw_aquarium(40, 120)


def test_draw_with_info():
    app = _make_app()
    app._aquarium_init("tropical")
    app.aquarium_show_info = True
    app._draw_aquarium(40, 120)


def test_draw_with_food():
    app = _make_app()
    app._aquarium_init("tropical")
    app.aquarium_food.append({"x": 50.0, "y": 15.0, "age": 0})
    app._draw_aquarium(40, 120)


def test_draw_all_presets():
    for _name, _desc, key in AQUARIUM_PRESETS:
        app = _make_app()
        app._aquarium_init(key)
        for _ in range(3):
            app._aquarium_step()
        app._draw_aquarium(40, 120)


# ── constants ─────────────────────────────────────────────────────────────

def test_sand_chars_exist():
    assert len(SAND_CHARS) > 0


def test_seaweed_chars_exist():
    assert len(SEAWEED_CHARS) > 0


def test_fish_species_structure():
    for sp in FISH_SPECIES:
        assert "name" in sp
        assert "left" in sp
        assert "right" in sp
        assert "speed" in sp
        assert len(sp["left"]) > 0
        assert len(sp["right"]) > 0
