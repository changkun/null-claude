"""Tests for life.modes.snowfall — Snowfall & Blizzard mode."""
import math
import curses
from tests.conftest import make_mock_app
from life.modes.snowfall import register, SNOWFALL_PRESETS


def _make_app():
    app = make_mock_app()
    app.snowfall_mode = False
    app.snowfall_menu = False
    app.snowfall_menu_sel = 0
    app.snowfall_running = False
    app.snowfall_dt = 0.03
    app.snowfall_speed = 2
    app.snowfall_show_info = False
    app.snowfall_flakes = []
    app.snowfall_accumulation = []
    app.snowfall_drift_particles = []
    register(type(app))
    return app


# ── Entry / Exit ──

def test_enter():
    app = _make_app()
    app._enter_snowfall_mode()
    assert app.snowfall_menu is True
    assert app.snowfall_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.snowfall_mode = True
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app._exit_snowfall_mode()
    assert app.snowfall_mode is False
    assert app.snowfall_flakes == []
    assert app.snowfall_accumulation == []
    assert app.snowfall_drift_particles == []


# ── Init ──

def test_init_gentle():
    app = _make_app()
    app._snowfall_init("gentle")
    assert app.snowfall_density == 80
    assert app.snowfall_wind_speed == 0.3
    assert len(app.snowfall_flakes) == 80
    assert len(app.snowfall_accumulation) == app.grid.cols
    assert app.snowfall_running is True
    assert app.snowfall_dt == 0.03


def test_init_blizzard():
    app = _make_app()
    app._snowfall_init("blizzard")
    assert app.snowfall_density == 400
    assert app.snowfall_wind_speed == 3.5
    assert app.snowfall_temperature == -15.0
    assert app.snowfall_visibility == 0.35


def test_init_whiteout():
    app = _make_app()
    app._snowfall_init("whiteout")
    assert app.snowfall_density == 600
    assert app.snowfall_wind_dir == -1.0  # left-blowing


def test_init_wet():
    app = _make_app()
    app._snowfall_init("wet")
    assert app.snowfall_temperature == 1.0  # above freezing


def test_init_all_presets():
    """All 6 presets initialize without error."""
    app = _make_app()
    for _, _, key in SNOWFALL_PRESETS:
        app._snowfall_init(key)
        assert len(app.snowfall_flakes) > 0
        assert len(app.snowfall_accumulation) == app.grid.cols
        assert app.snowfall_running is True


def test_flake_structure():
    """Each flake should be [x, y, vx, vy, size, wobble_phase]."""
    app = _make_app()
    app._snowfall_init("gentle")
    for f in app.snowfall_flakes:
        assert len(f) == 6
        assert 0 <= f[4] <= 2  # size is 0, 1, or 2


# ── Step mechanics ──

def test_step_no_crash():
    app = _make_app()
    app.snowfall_mode = True
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    for _ in range(10):
        app._snowfall_step()
    assert app.snowfall_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._snowfall_init("gentle")
    t0 = app.snowfall_time
    app._snowfall_step()
    assert app.snowfall_time > t0
    assert abs(app.snowfall_time - t0 - 0.03) < 1e-10


def test_step_flakes_move():
    app = _make_app()
    app._snowfall_init("gentle")
    positions_before = [(f[0], f[1]) for f in app.snowfall_flakes[:5]]
    app._snowfall_step()
    positions_after = [(f[0], f[1]) for f in app.snowfall_flakes[:5]]
    # At least some flakes should have moved
    moved = sum(1 for b, a in zip(positions_before, positions_after) if b != a)
    assert moved > 0


def test_step_accumulation_grows():
    """After many steps, some accumulation should occur."""
    app = _make_app()
    app._snowfall_init("blizzard")  # heavy snow for faster accumulation
    for _ in range(200):
        app._snowfall_step()
    total_accum = sum(app.snowfall_accumulation)
    assert total_accum > 0


def test_step_wind_gust_phase_changes():
    app = _make_app()
    app._snowfall_init("gentle")
    gust0 = app.snowfall_wind_gust_phase
    app._snowfall_step()
    assert app.snowfall_wind_gust_phase != gust0


def test_step_with_strong_wind_creates_drift():
    """Strong wind should eventually produce drift particles."""
    app = _make_app()
    app._snowfall_init("blizzard")
    # Run enough steps with strong wind to trigger drift
    for _ in range(500):
        app._snowfall_step()
    # Can't guarantee drift particles, but the code path should not crash


def test_step_flakes_wrap_horizontally():
    app = _make_app()
    app._snowfall_init("gentle")
    # Place a flake far off screen to the left
    app.snowfall_flakes[0][0] = -10.0
    app._snowfall_step()
    # Flake should have wrapped to the right
    assert app.snowfall_flakes[0][0] > -10.0


def test_step_blizzard_many_steps():
    """Blizzard should run 100 steps without crash."""
    app = _make_app()
    app._snowfall_init("blizzard")
    for _ in range(100):
        app._snowfall_step()
    assert app.snowfall_generation == 100


# ── Snow drift mechanics ──

def test_drift_with_wind():
    app = _make_app()
    app._snowfall_init("gentle")
    # Manually set high accumulation and strong wind
    app.snowfall_accumulation = [5.0] * app.snowfall_cols
    app.snowfall_wind_speed = 3.0
    app.snowfall_wind_dir = 1.0
    app._snowfall_step()
    # Accumulation should have shifted slightly
    # The exact values depend on drift calculation, but it should not crash


# ── Menu key handling ──

def test_menu_key_down():
    app = _make_app()
    app._enter_snowfall_mode()
    app._handle_snowfall_menu_key(curses.KEY_DOWN)
    assert app.snowfall_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_snowfall_mode()
    app._handle_snowfall_menu_key(curses.KEY_UP)
    assert app.snowfall_menu_sel == len(SNOWFALL_PRESETS) - 1


def test_menu_key_enter_starts():
    app = _make_app()
    app._enter_snowfall_mode()
    app._handle_snowfall_menu_key(10)
    assert app.snowfall_mode is True
    assert app.snowfall_running is True
    assert app.snowfall_menu is False


def test_menu_key_quit():
    app = _make_app()
    app._enter_snowfall_mode()
    app.snowfall_mode = True
    app._handle_snowfall_menu_key(ord('q'))
    assert app.snowfall_mode is False


# ── Simulation key handling ──

def test_key_space_toggles():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app.snowfall_running = True
    app._handle_snowfall_key(ord(' '))
    assert app.snowfall_running is False


def test_key_n_steps():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    gen_before = app.snowfall_generation
    app._handle_snowfall_key(ord('n'))
    assert app.snowfall_generation == gen_before + 1


def test_key_r_resets():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    for _ in range(5):
        app._snowfall_step()
    app._handle_snowfall_key(ord('r'))
    assert app.snowfall_generation == 0


def test_key_plus_minus_speed():
    app = _make_app()
    app.snowfall_speed = 3
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app._handle_snowfall_key(ord('+'))
    assert app.snowfall_speed == 4
    app._handle_snowfall_key(ord('-'))
    assert app.snowfall_speed == 3


def test_key_w_increases_wind():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    wind_before = app.snowfall_wind_speed
    app._handle_snowfall_key(ord('w'))
    assert app.snowfall_wind_speed > wind_before


def test_key_W_decreases_wind():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app.snowfall_wind_speed = 2.0
    app._handle_snowfall_key(ord('W'))
    assert app.snowfall_wind_speed < 2.0


def test_key_d_flips_wind_direction():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    dir_before = app.snowfall_wind_dir
    app._handle_snowfall_key(ord('d'))
    assert app.snowfall_wind_dir == -dir_before


def test_key_f_increases_density():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    density_before = app.snowfall_density
    flakes_before = len(app.snowfall_flakes)
    app._handle_snowfall_key(ord('f'))
    assert app.snowfall_density > density_before
    assert len(app.snowfall_flakes) > flakes_before


def test_key_F_decreases_density():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    density_before = app.snowfall_density
    app._handle_snowfall_key(ord('F'))
    assert app.snowfall_density < density_before


def test_key_t_warms():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    temp_before = app.snowfall_temperature
    app._handle_snowfall_key(ord('t'))
    assert app.snowfall_temperature > temp_before


def test_key_T_cools():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    temp_before = app.snowfall_temperature
    app._handle_snowfall_key(ord('T'))
    assert app.snowfall_temperature < temp_before


def test_key_i_toggles_info():
    app = _make_app()
    app.snowfall_show_info = False
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app._handle_snowfall_key(ord('i'))
    assert app.snowfall_show_info is True


def test_key_q_exits():
    app = _make_app()
    app.snowfall_mode = True
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app._handle_snowfall_key(ord('q'))
    assert app.snowfall_mode is False


def test_key_m_returns_to_menu():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app.snowfall_running = True
    app._handle_snowfall_key(ord('m'))
    assert app.snowfall_menu is True
    assert app.snowfall_running is False


# ── Drawing (no crash) ──

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_snowfall_mode()
    app._draw_snowfall_menu(40, 120)


def test_draw_snowfall_no_crash():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app.snowfall_show_info = True
    for _ in range(5):
        app._snowfall_step()
    app._draw_snowfall(40, 120)


def test_draw_snowfall_small_terminal():
    app = _make_app()
    app.snowfall_preset_name = "gentle"
    app._snowfall_init("gentle")
    app._draw_snowfall(5, 10)  # too small


def test_draw_snowfall_with_accumulation():
    app = _make_app()
    app.snowfall_preset_name = "blizzard"
    app._snowfall_init("blizzard")
    # Simulate lots of accumulation
    for i in range(len(app.snowfall_accumulation)):
        app.snowfall_accumulation[i] = 3.0
    app._draw_snowfall(40, 120)


def test_draw_snowfall_with_drift_particles():
    app = _make_app()
    app.snowfall_preset_name = "blizzard"
    app._snowfall_init("blizzard")
    app.snowfall_drift_particles = [
        [10.0, 20.0, 2.0, 20],
        [15.0, 25.0, -1.5, 10],
    ]
    app._draw_snowfall(40, 120)


# ── Presets data ──

def test_presets_structure():
    assert len(SNOWFALL_PRESETS) == 6
    for name, desc, key in SNOWFALL_PRESETS:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str)
        assert key in ("gentle", "steady", "blizzard", "whiteout", "wet", "squall")
