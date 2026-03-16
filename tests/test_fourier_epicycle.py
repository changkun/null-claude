"""Tests for life.modes.fourier_epicycle — Fourier Epicycle mode."""
import math
import curses
from tests.conftest import make_mock_app
from life.modes.fourier_epicycle import (
    register,
    FOURIER_PRESETS,
    _fourier_dft,
    _fourier_generate_preset_path,
)


def _make_app():
    app = make_mock_app()
    app.fourier_mode = False
    app.fourier_menu = False
    app.fourier_menu_sel = 0
    app.fourier_running = False
    app.fourier_phase = "menu"
    app.fourier_path = []
    app.fourier_coeffs = []
    app.fourier_trace = []
    register(type(app))
    return app


# ── Entry / Exit ──

def test_enter():
    app = _make_app()
    app._enter_fourier_mode()
    assert app.fourier_menu is True
    assert app.fourier_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.fourier_mode = True
    app._fourier_init("circle")
    app._exit_fourier_mode()
    assert app.fourier_mode is False
    assert app.fourier_path == []
    assert app.fourier_coeffs == []
    assert app.fourier_trace == []


# ── DFT correctness ──

def test_dft_empty():
    assert _fourier_dft([]) == []


def test_dft_single_point():
    coeffs = _fourier_dft([(1.0, 0.0)])
    assert len(coeffs) == 1
    # DC component should be (1, 0)
    freq, amp, phase, re, im = coeffs[0]
    assert abs(re - 1.0) < 1e-10
    assert abs(im) < 1e-10


def test_dft_circle_reconstruction():
    """DFT of a circle should produce one dominant frequency."""
    N = 64
    points = [(math.cos(2 * math.pi * i / N), math.sin(2 * math.pi * i / N)) for i in range(N)]
    coeffs = _fourier_dft(points)
    # Sorted by amplitude desc — first should have amp ~1.0
    assert len(coeffs) == N
    assert coeffs[0][1] > 0.9  # dominant amplitude


def test_dft_preserves_point_count():
    points = [(float(i), float(i * 2)) for i in range(16)]
    coeffs = _fourier_dft(points)
    assert len(coeffs) == 16


def test_dft_sorted_by_amplitude_descending():
    N = 32
    points = [(math.cos(2 * math.pi * i / N), math.sin(2 * math.pi * i / N)) for i in range(N)]
    coeffs = _fourier_dft(points)
    amps = [c[1] for c in coeffs]
    assert amps == sorted(amps, reverse=True)


# ── Preset path generation ──

def test_generate_circle_path():
    pts = _fourier_generate_preset_path("circle", 50.0, 20.0, 10.0)
    assert len(pts) == 128
    # All points should be approximately distance 10 from center
    for x, y in pts:
        dist = math.sqrt((x - 50) ** 2 + (y - 20) ** 2)
        assert abs(dist - 10.0) < 0.01


def test_generate_square_path():
    pts = _fourier_generate_preset_path("square", 0.0, 0.0, 5.0)
    assert len(pts) == 128


def test_generate_star_path():
    pts = _fourier_generate_preset_path("star", 0.0, 0.0, 10.0)
    assert len(pts) == 128


def test_generate_figure8_path():
    pts = _fourier_generate_preset_path("figure8", 0.0, 0.0, 10.0)
    assert len(pts) == 128


def test_generate_heart_path():
    pts = _fourier_generate_preset_path("heart", 0.0, 0.0, 10.0)
    assert len(pts) == 128


def test_generate_spiralsquare_path():
    pts = _fourier_generate_preset_path("spiralsquare", 0.0, 0.0, 10.0)
    assert len(pts) == 128


def test_generate_unknown_defaults_to_circle():
    pts = _fourier_generate_preset_path("nonexistent", 0.0, 0.0, 10.0)
    assert len(pts) == 128


# ── Init ──

def test_init_circle():
    app = _make_app()
    app._fourier_init("circle")
    assert app.fourier_phase == "playing"
    assert app.fourier_running is True
    assert len(app.fourier_path) == 128
    assert len(app.fourier_coeffs) == 128
    assert app.fourier_time == 0.0


def test_init_all_presets():
    app = _make_app()
    for _, _, key in FOURIER_PRESETS:
        app._fourier_init(key)
        if key == "freedraw":
            assert app.fourier_phase == "drawing"
        else:
            assert app.fourier_phase == "playing"
            assert len(app.fourier_coeffs) > 0


def test_init_freedraw():
    app = _make_app()
    app._fourier_init("freedraw")
    assert app.fourier_phase == "drawing"
    assert app.fourier_running is False
    assert app.fourier_path == []


# ── Step ──

def test_step_no_crash():
    app = _make_app()
    app.fourier_mode = True
    app._fourier_init("circle")
    for _ in range(10):
        app._fourier_step()
    assert len(app.fourier_trace) == 10


def test_step_advances_time():
    app = _make_app()
    app._fourier_init("circle")
    t0 = app.fourier_time
    app._fourier_step()
    assert app.fourier_time > t0


def test_step_appends_trace():
    app = _make_app()
    app._fourier_init("square")
    for _ in range(5):
        app._fourier_step()
    assert len(app.fourier_trace) == 5


def test_step_trace_truncation():
    app = _make_app()
    app._fourier_init("circle")
    N = len(app.fourier_path)
    max_trace = N * 2
    for _ in range(max_trace + 50):
        app._fourier_step()
    assert len(app.fourier_trace) <= max_trace


def test_step_no_coeffs_safe():
    app = _make_app()
    app._fourier_init("circle")
    app.fourier_coeffs = []
    app._fourier_step()  # should not crash
    assert len(app.fourier_trace) == 0


def test_step_no_path_safe():
    app = _make_app()
    app._fourier_init("circle")
    app.fourier_path = []
    app._fourier_step()  # should not crash


# ── Free draw playback ──

def test_start_playback_from_drawing():
    app = _make_app()
    app._fourier_init("freedraw")
    # Simulate drawing some points
    app.fourier_path = [(float(i), float(i * 2)) for i in range(20)]
    app._fourier_start_playback()
    assert app.fourier_phase == "playing"
    assert app.fourier_running is True
    assert len(app.fourier_coeffs) == 20


def test_start_playback_too_few_points():
    app = _make_app()
    app._fourier_init("freedraw")
    app.fourier_path = [(0.0, 0.0), (1.0, 1.0)]  # only 2 points
    app._fourier_start_playback()
    # Should not start playback
    assert app.fourier_phase == "drawing"


# ── Menu key handling ──

def test_menu_key_down():
    app = _make_app()
    app._enter_fourier_mode()
    app._handle_fourier_menu_key(curses.KEY_DOWN)
    assert app.fourier_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_fourier_mode()
    app._handle_fourier_menu_key(curses.KEY_UP)
    assert app.fourier_menu_sel == len(FOURIER_PRESETS) - 1


def test_menu_key_enter_starts():
    app = _make_app()
    app._enter_fourier_mode()
    app._handle_fourier_menu_key(10)
    assert app.fourier_mode is True


def test_menu_key_quit():
    app = _make_app()
    app._enter_fourier_mode()
    app._handle_fourier_menu_key(ord('q'))
    assert app.fourier_menu is False


# ── Simulation key handling ──

def test_key_space_toggles():
    app = _make_app()
    app._fourier_init("circle")
    app.fourier_running = True
    app._handle_fourier_key(ord(' '))
    assert app.fourier_running is False


def test_key_n_steps():
    app = _make_app()
    app._fourier_init("circle")
    n_before = len(app.fourier_trace)
    app._handle_fourier_key(ord('n'))
    assert len(app.fourier_trace) == n_before + 1


def test_key_r_resets():
    app = _make_app()
    app._fourier_init("circle")
    for _ in range(5):
        app._fourier_step()
    app._handle_fourier_key(ord('r'))
    assert app.fourier_time == 0.0
    assert app.fourier_trace == []


def test_key_bracket_adjusts_circles():
    app = _make_app()
    app._fourier_init("circle")
    n_circles = app.fourier_num_circles
    app._handle_fourier_key(ord('['))
    assert app.fourier_num_circles == n_circles - 1
    app._handle_fourier_key(ord(']'))
    assert app.fourier_num_circles == n_circles


def test_key_c_toggles_circles():
    app = _make_app()
    app._fourier_init("circle")
    app.fourier_show_circles = True
    app._handle_fourier_key(ord('c'))
    assert app.fourier_show_circles is False


def test_key_i_toggles_info():
    app = _make_app()
    app._fourier_init("circle")
    app.fourier_show_info = True
    app._handle_fourier_key(ord('i'))
    assert app.fourier_show_info is False


def test_key_q_exits():
    app = _make_app()
    app.fourier_mode = True
    app._fourier_init("circle")
    app._handle_fourier_key(ord('q'))
    assert app.fourier_mode is False


def test_key_m_returns_to_menu():
    app = _make_app()
    app._fourier_init("circle")
    app._handle_fourier_key(ord('m'))
    assert app.fourier_menu is True
    assert app.fourier_running is False


# ── Drawing key handling ──

def test_drawing_key_d_toggles_pen():
    app = _make_app()
    app._fourier_init("freedraw")
    app.fourier_drawing = False
    app._handle_fourier_key(ord('d'))
    assert app.fourier_drawing is True
    assert len(app.fourier_path) == 1  # point added on pen down


def test_drawing_key_arrow_moves_cursor():
    app = _make_app()
    app._fourier_init("freedraw")
    y0 = app.fourier_cursor_y
    app._handle_fourier_key(curses.KEY_UP)
    assert app.fourier_cursor_y == y0 - 1


def test_drawing_key_x_clears():
    app = _make_app()
    app._fourier_init("freedraw")
    app.fourier_path = [(1.0, 2.0), (3.0, 4.0)]
    app.fourier_drawing = True
    app._handle_fourier_key(ord('x'))
    assert app.fourier_path == []
    assert app.fourier_drawing is False


def test_drawing_key_enter_starts_playback():
    app = _make_app()
    app._fourier_init("freedraw")
    app.fourier_path = [(float(i), float(i)) for i in range(10)]
    app._handle_fourier_key(10)  # Enter
    assert app.fourier_phase == "playing"


# ── Drawing (no crash) ──

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_fourier_mode()
    app._draw_fourier_menu(40, 120)


def test_draw_fourier_no_crash():
    app = _make_app()
    app._fourier_init("circle")
    app.fourier_show_info = True
    app.fourier_show_circles = True
    for _ in range(5):
        app._fourier_step()
    app._draw_fourier(40, 120)


def test_draw_fourier_drawing_phase():
    app = _make_app()
    app._fourier_init("freedraw")
    app.fourier_path = [(10.0, 10.0), (11.0, 11.0)]
    app._draw_fourier(40, 120)


def test_draw_fourier_small_terminal():
    app = _make_app()
    app._fourier_init("circle")
    app._draw_fourier(5, 5)  # very small


# ── No leaked data ──

def test_no_snowfall_presets_leaked():
    """fourier_epicycle.py should not contain SNOWFALL_PRESETS."""
    import life.modes.fourier_epicycle as mod
    assert not hasattr(mod, 'SNOWFALL_PRESETS')


def test_no_snowflake_chars_leaked():
    import life.modes.fourier_epicycle as mod
    assert not hasattr(mod, '_SNOWFLAKE_CHARS_SMALL')


# ── Presets data ──

def test_presets_structure():
    assert len(FOURIER_PRESETS) == 7
    for name, desc, key in FOURIER_PRESETS:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str)
        assert key in ("circle", "square", "star", "figure8", "heart", "spiralsquare", "freedraw")
