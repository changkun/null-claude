"""Tests for life.modes.pendulum_wave — Pendulum Wave mode."""
import curses
import math
from unittest.mock import patch

from tests.conftest import make_mock_app
from life.modes.pendulum_wave import register, PWAVE_PRESETS


def _make_app():
    app = make_mock_app()
    app.pwave_mode = False
    app.pwave_menu = False
    app.pwave_menu_sel = 0
    app.pwave_running = False
    app.pwave_max_trail = 40
    app.pwave_lengths = []
    app.pwave_angles = []
    app.pwave_trail = []
    register(type(app))
    return app


# ── Enter / Exit ──

def test_enter():
    app = _make_app()
    app._enter_pwave_mode()
    assert app.pwave_menu is True
    assert app.pwave_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.pwave_mode = True
    app.pwave_preset_name = "classic"
    app._pwave_init("classic")
    assert len(app.pwave_lengths) > 0
    app._exit_pwave_mode()
    assert app.pwave_mode is False
    assert app.pwave_running is False
    assert app.pwave_lengths == []
    assert app.pwave_angles == []
    assert app.pwave_trail == []


# ── Preset initialization ──

def test_all_presets_init():
    """Every preset key initializes without error and produces correct pendulum count."""
    expected_counts = {
        "classic": 15, "dense": 24, "wide": 12,
        "quick": 15, "slow": 18, "grand": 32,
    }
    for _name, _desc, key in PWAVE_PRESETS:
        app = _make_app()
        app._pwave_init(key)
        assert app.pwave_running is True
        assert app.pwave_n_pendulums == expected_counts[key], f"preset {key}"
        assert len(app.pwave_lengths) == expected_counts[key]
        assert len(app.pwave_angles) == expected_counts[key]
        assert len(app.pwave_trail) == expected_counts[key]


def test_unknown_preset_falls_back():
    app = _make_app()
    app._pwave_init("nonexistent")
    assert app.pwave_n_pendulums == 15
    assert app.pwave_running is True


def test_init_resets_state():
    """Calling _pwave_init twice resets generation and time."""
    app = _make_app()
    app._pwave_init("classic")
    for _ in range(5):
        app._pwave_step()
    assert app.pwave_generation == 5
    app._pwave_init("classic")
    assert app.pwave_generation == 0
    assert app.pwave_time == 0.0


# ── Pendulum length physics ──

def test_lengths_decreasing():
    """Pendulum lengths must decrease: shorter pendulums oscillate faster."""
    app = _make_app()
    app._pwave_init("classic")
    for i in range(len(app.pwave_lengths) - 1):
        assert app.pwave_lengths[i] > app.pwave_lengths[i + 1]


def test_length_formula_matches_shm():
    """Verify L_i = g * (T / (2*pi*(N_base + i)))^2 for each pendulum."""
    app = _make_app()
    app._pwave_init("dense")
    g = app.pwave_g
    T = app.pwave_realign_time
    N_base = 51
    for i, L in enumerate(app.pwave_lengths):
        period_i = T / (N_base + i)
        expected_L = g * (period_i / (2 * math.pi)) ** 2
        assert abs(L - expected_L) < 1e-12, f"pendulum {i}: {L} != {expected_L}"


def test_oscillation_counts_at_realign_time():
    """At t = realign_time, pendulum i should complete exactly (N_base + i) oscillations,
    meaning its phase should be a multiple of 2*pi."""
    app = _make_app()
    app._pwave_init("classic")
    g = app.pwave_g
    T = app.pwave_realign_time
    for i, L in enumerate(app.pwave_lengths):
        omega = math.sqrt(g / L)
        phase = omega * T
        # phase should be (N_base + i) * 2 * pi
        expected_cycles = 51 + i
        actual_cycles = phase / (2 * math.pi)
        assert abs(actual_cycles - expected_cycles) < 1e-9, (
            f"pendulum {i}: expected {expected_cycles} cycles, got {actual_cycles:.6f}"
        )


# ── Step physics ──

def test_step_no_crash():
    app = _make_app()
    app.pwave_mode = True
    app.pwave_preset_name = "classic"
    app._pwave_init("classic")
    for _ in range(10):
        app._pwave_step()
    assert app.pwave_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._pwave_init("classic")
    dt = app.pwave_dt
    app._pwave_step()
    assert abs(app.pwave_time - dt) < 1e-12


def test_shm_angle_formula():
    """theta(t) = A * cos(omega * t) for each pendulum."""
    app = _make_app()
    app._pwave_init("classic")
    start_angle = 0.4
    for _ in range(20):
        app._pwave_step()
    t = app.pwave_time
    g = app.pwave_g
    for i in range(app.pwave_n_pendulums):
        L = app.pwave_lengths[i]
        omega = math.sqrt(g / L)
        expected = start_angle * math.cos(omega * t)
        assert abs(app.pwave_angles[i] - expected) < 1e-12, f"pendulum {i}"


def test_angles_start_at_max_displacement():
    """All pendulums start at 0.4 radians."""
    app = _make_app()
    app._pwave_init("classic")
    for angle in app.pwave_angles:
        assert angle == 0.4


def test_angles_bounded():
    """Angles should always be between -0.4 and 0.4."""
    app = _make_app()
    app._pwave_init("classic")
    for _ in range(200):
        app._pwave_step()
    for angle in app.pwave_angles:
        assert -0.4 - 1e-10 <= angle <= 0.4 + 1e-10


def test_realignment():
    """At t = realign_time, all pendulums should return to ~start angle (cos(2*pi*n) = 1)."""
    app = _make_app()
    app._pwave_init("classic")
    # Step until time is approximately realign_time
    steps_needed = int(app.pwave_realign_time / app.pwave_dt)
    for _ in range(steps_needed):
        app._pwave_step()
    # All angles should be near 0.4
    for i, angle in enumerate(app.pwave_angles):
        assert abs(angle - 0.4) < 0.01, (
            f"pendulum {i} at realignment: angle={angle:.6f}, expected ~0.4"
        )


# ── Key handling ──

def test_menu_key_down():
    app = _make_app()
    app._enter_pwave_mode()
    assert app.pwave_menu_sel == 0
    app._handle_pwave_menu_key(curses.KEY_DOWN)
    assert app.pwave_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_pwave_mode()
    app._handle_pwave_menu_key(curses.KEY_UP)
    assert app.pwave_menu_sel == len(PWAVE_PRESETS) - 1


def test_menu_enter_starts_sim():
    app = _make_app()
    app._enter_pwave_mode()
    app._handle_pwave_menu_key(10)  # Enter
    assert app.pwave_menu is False
    assert app.pwave_mode is True
    assert app.pwave_running is True
    assert len(app.pwave_lengths) > 0


def test_menu_quit():
    app = _make_app()
    app._enter_pwave_mode()
    app._handle_pwave_menu_key(27)  # Escape
    assert app.pwave_mode is False
    assert app.pwave_menu is False


def test_sim_key_space_toggles():
    app = _make_app()
    app._pwave_init("classic")
    app.pwave_running = True
    app._handle_pwave_key(ord(' '))
    assert app.pwave_running is False
    app._handle_pwave_key(ord(' '))
    assert app.pwave_running is True


def test_sim_key_speed():
    app = _make_app()
    app._pwave_init("classic")
    initial_speed = app.pwave_speed
    app._handle_pwave_key(ord('+'))
    assert app.pwave_speed == initial_speed + 1
    app._handle_pwave_key(ord('-'))
    assert app.pwave_speed == initial_speed


def test_sim_key_speed_bounds():
    app = _make_app()
    app._pwave_init("classic")
    for _ in range(20):
        app._handle_pwave_key(ord('+'))
    assert app.pwave_speed == 10
    for _ in range(20):
        app._handle_pwave_key(ord('-'))
    assert app.pwave_speed == 1


def test_sim_key_info_toggle():
    app = _make_app()
    app._pwave_init("classic")
    assert app.pwave_show_info is False
    app._handle_pwave_key(ord('i'))
    assert app.pwave_show_info is True
    app._handle_pwave_key(ord('i'))
    assert app.pwave_show_info is False


def test_sim_key_step():
    app = _make_app()
    app._pwave_init("classic")
    gen_before = app.pwave_generation
    app._handle_pwave_key(ord('n'))
    assert app.pwave_generation == gen_before + 1


def test_sim_key_reset():
    app = _make_app()
    app._pwave_init("classic")
    app.pwave_preset_name = "Classic Wave"
    for _ in range(10):
        app._pwave_step()
    app._handle_pwave_key(ord('r'))
    assert app.pwave_generation == 0
    assert app.pwave_time == 0.0


def test_sim_key_back_to_menu():
    app = _make_app()
    app._pwave_init("classic")
    app.pwave_running = True
    app._handle_pwave_key(ord('R'))
    assert app.pwave_menu is True
    assert app.pwave_running is False


def test_sim_key_quit():
    app = _make_app()
    app._pwave_init("classic")
    app.pwave_mode = True
    app._handle_pwave_key(ord('q'))
    assert app.pwave_mode is False


def test_unrecognized_key_returns_false():
    app = _make_app()
    app._pwave_init("classic")
    result = app._handle_pwave_key(ord('z'))
    assert result is False


# ── Drawing (smoke tests) ──

def _mock_color_pair(n):
    return n


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_menu_no_crash(_cp):
    app = _make_app()
    app._enter_pwave_mode()
    app._draw_pwave_menu(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_sim_no_crash(_cp):
    app = _make_app()
    app._pwave_init("classic")
    for _ in range(3):
        app._pwave_step()
    app._draw_pwave(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_sim_small_terminal(_cp):
    """Drawing on a very small terminal should not crash."""
    app = _make_app()
    app._pwave_init("classic")
    app._draw_pwave(8, 15)  # too small, should return early


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_with_info_panel(_cp):
    app = _make_app()
    app._pwave_init("classic")
    app.pwave_show_info = True
    for _ in range(3):
        app._pwave_step()
    app._draw_pwave(40, 120)


@patch('curses.color_pair', side_effect=_mock_color_pair)
def test_draw_all_presets(_cp):
    """Drawing each preset should not crash."""
    for _name, _desc, key in PWAVE_PRESETS:
        app = _make_app()
        app._pwave_init(key)
        for _ in range(5):
            app._pwave_step()
        app._draw_pwave(40, 120)
