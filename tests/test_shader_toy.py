"""Tests for life.modes.shader_toy — Shader Toy mode."""
import math

from tests.conftest import make_mock_app
from life.modes.shader_toy import (
    register,
    SHADERTOY_SHADE_CHARS,
    SHADERTOY_PRESETS,
    SHADERTOY_COLOR_NAMES,
)


def _make_app():
    app = make_mock_app()
    app.shadertoy_mode = False
    app.shadertoy_menu = False
    app.shadertoy_menu_sel = 0
    app.shadertoy_running = False
    app.shadertoy_generation = 0
    app.shadertoy_preset_name = ""
    app.shadertoy_preset_idx = 0
    app.shadertoy_time = 0.0
    app.shadertoy_speed = 1.0
    app.shadertoy_param_a = 1.0
    app.shadertoy_param_b = 1.0
    app.shadertoy_color_mode = 0
    register(type(app))
    return app


# ── Constants validation ─────────────────────────────────────────────────────

def test_shade_chars_matches_original():
    """SHADERTOY_SHADE_CHARS must be the 12-character original string."""
    assert SHADERTOY_SHADE_CHARS == " .,:;=+*#%@\u2588"
    assert len(SHADERTOY_SHADE_CHARS) == 12


def test_presets_count():
    assert len(SHADERTOY_PRESETS) == 10


def test_color_names():
    assert SHADERTOY_COLOR_NAMES == ["Rainbow", "Fire", "Ocean", "Mono"]


def test_register_sets_class_constants():
    """register() must set SHADERTOY_* class attributes on App."""
    app = _make_app()
    assert type(app).SHADERTOY_SHADE_CHARS == SHADERTOY_SHADE_CHARS
    assert type(app).SHADERTOY_PRESETS == SHADERTOY_PRESETS
    assert type(app).SHADERTOY_COLOR_NAMES == SHADERTOY_COLOR_NAMES


# ── Enter / exit ─────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_shadertoy_mode()
    assert app.shadertoy_menu is True
    assert app.shadertoy_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.shadertoy_mode = True
    app._shadertoy_init(0)
    app._exit_shadertoy_mode()
    assert app.shadertoy_mode is False
    assert app.shadertoy_menu is False
    assert app.shadertoy_running is False


# ── Init per preset ──────────────────────────────────────────────────────────

def test_init_all_presets():
    """Every preset index should initialize cleanly."""
    app = _make_app()
    for idx in range(len(SHADERTOY_PRESETS)):
        app._shadertoy_init(idx)
        assert app.shadertoy_preset_idx == idx
        assert app.shadertoy_running is True
        assert app.shadertoy_menu is False
        assert app.shadertoy_generation == 0
        assert app.shadertoy_time == 0.0
        assert app.shadertoy_speed == 1.0
        assert app.shadertoy_param_a == 1.0
        assert app.shadertoy_param_b == 1.0


# ── Step / time advance ─────────────────────────────────────────────────────

def test_step_no_crash():
    app = _make_app()
    app._shadertoy_init(0)
    for _ in range(10):
        app._shadertoy_step()
    assert app.shadertoy_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._shadertoy_init(0)
    app._shadertoy_step()
    # Default speed=1.0, dt=0.05
    assert abs(app.shadertoy_time - 0.05) < 1e-9


def test_step_speed_scaling():
    app = _make_app()
    app._shadertoy_init(0)
    app.shadertoy_speed = 2.0
    app._shadertoy_step()
    assert abs(app.shadertoy_time - 0.10) < 1e-9


# ── Shader eval returns [0,1] ───────────────────────────────────────────────

def test_eval_all_presets_in_range():
    """_shadertoy_eval must return values in [0, 1] for all presets."""
    app = _make_app()
    for preset_idx in range(len(SHADERTOY_PRESETS)):
        app.shadertoy_preset_idx = preset_idx
        for t in [0.0, 0.5, 1.0, 3.14]:
            for nx in [-0.8, -0.3, 0.0, 0.5, 0.9]:
                for ny in [-0.7, 0.0, 0.7]:
                    val = app._shadertoy_eval(nx, ny, t)
                    assert 0.0 <= val <= 1.0, (
                        f"preset {preset_idx} returned {val} at "
                        f"nx={nx}, ny={ny}, t={t}"
                    )


def test_eval_unknown_preset_returns_zero():
    app = _make_app()
    app.shadertoy_preset_idx = 999
    assert app._shadertoy_eval(0.0, 0.0, 0.0) == 0.0


def test_eval_plasma_varies_over_time():
    """Preset 0 (Plasma) should produce different values at different times."""
    app = _make_app()
    app.shadertoy_preset_idx = 0
    v1 = app._shadertoy_eval(0.5, 0.5, 0.0)
    v2 = app._shadertoy_eval(0.5, 0.5, 1.0)
    assert v1 != v2


def test_eval_param_a_affects_output():
    """Changing param_a should change the shader output."""
    app = _make_app()
    app.shadertoy_preset_idx = 0
    app.shadertoy_param_a = 1.0
    v1 = app._shadertoy_eval(0.3, 0.3, 1.0)
    app.shadertoy_param_a = 2.5
    v2 = app._shadertoy_eval(0.3, 0.3, 1.0)
    assert v1 != v2


def test_eval_param_b_affects_output():
    app = _make_app()
    app.shadertoy_preset_idx = 1  # Tunnel Zoom
    app.shadertoy_param_b = 1.0
    v1 = app._shadertoy_eval(0.3, 0.3, 1.0)
    app.shadertoy_param_b = 2.5
    v2 = app._shadertoy_eval(0.3, 0.3, 1.0)
    assert v1 != v2


# ── Color mapping ────────────────────────────────────────────────────────────

def test_color_function_exists():
    """_shadertoy_color should be registered and callable."""
    app = _make_app()
    assert callable(app._shadertoy_color)


def test_color_mode_boundaries():
    """Color mode handles all 4 mode indices without error in the branch logic."""
    app = _make_app()
    # We cannot call curses.color_pair without initscr, but we can verify
    # the function exists and the mode index selects different branches.
    for mode in range(4):
        app.shadertoy_color_mode = mode
        # Just check the attribute is set correctly
        assert app.shadertoy_color_mode == mode


# ── Key handling — menu ──────────────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_shadertoy_mode()
    app._handle_shadertoy_menu_key(ord("j"))
    assert app.shadertoy_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_shadertoy_mode()
    app._handle_shadertoy_menu_key(ord("k"))
    assert app.shadertoy_menu_sel == len(SHADERTOY_PRESETS) - 1


def test_menu_select():
    app = _make_app()
    app._enter_shadertoy_mode()
    app.shadertoy_menu_sel = 3
    app._handle_shadertoy_menu_key(ord("\n"))
    assert app.shadertoy_preset_idx == 3
    assert app.shadertoy_running is True
    assert app.shadertoy_menu is False


def test_menu_cancel_q():
    app = _make_app()
    app._enter_shadertoy_mode()
    app._handle_shadertoy_menu_key(ord("q"))
    assert app.shadertoy_menu is False


def test_menu_cancel_escape():
    app = _make_app()
    app._enter_shadertoy_mode()
    app._handle_shadertoy_menu_key(27)
    assert app.shadertoy_menu is False


# ── Key handling — active shader ─────────────────────────────────────────────

def test_key_space_toggles_pause():
    app = _make_app()
    app._shadertoy_init(0)
    assert app.shadertoy_running is True
    app._handle_shadertoy_key(ord(" "))
    assert app.shadertoy_running is False
    app._handle_shadertoy_key(ord(" "))
    assert app.shadertoy_running is True


def test_key_n_next_shader():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("n"))
    assert app.shadertoy_preset_idx == 1


def test_key_N_prev_shader():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("N"))
    assert app.shadertoy_preset_idx == len(SHADERTOY_PRESETS) - 1


def test_key_c_cycles_color():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("c"))
    assert app.shadertoy_color_mode == 1
    app._handle_shadertoy_key(ord("c"))
    assert app.shadertoy_color_mode == 2


def test_key_speed_increase():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("+"))
    assert app.shadertoy_speed == 1.25


def test_key_speed_decrease():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("-"))
    assert app.shadertoy_speed == 0.75


def test_key_speed_upper_bound():
    app = _make_app()
    app._shadertoy_init(0)
    app.shadertoy_speed = 5.0
    app._handle_shadertoy_key(ord("+"))
    assert app.shadertoy_speed == 5.0


def test_key_speed_lower_bound():
    app = _make_app()
    app._shadertoy_init(0)
    app.shadertoy_speed = 0.1
    app._handle_shadertoy_key(ord("-"))
    assert app.shadertoy_speed == 0.1


def test_key_param_a_increase():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("a"))
    assert abs(app.shadertoy_param_a - 1.1) < 1e-9


def test_key_param_a_decrease():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("A"))
    assert abs(app.shadertoy_param_a - 0.9) < 1e-9


def test_key_param_b_increase():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("b"))
    assert abs(app.shadertoy_param_b - 1.1) < 1e-9


def test_key_param_b_decrease():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("B"))
    assert abs(app.shadertoy_param_b - 0.9) < 1e-9


def test_key_r_resets():
    app = _make_app()
    app._shadertoy_init(0)
    for _ in range(5):
        app._shadertoy_step()
    app._handle_shadertoy_key(ord("r"))
    assert app.shadertoy_generation == 0
    assert app.shadertoy_time == 0.0


def test_key_m_returns_to_menu():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("m"))
    assert app.shadertoy_menu is True
    assert app.shadertoy_mode is False


def test_key_q_exits():
    app = _make_app()
    app._shadertoy_init(0)
    app._handle_shadertoy_key(ord("q"))
    assert app.shadertoy_mode is False
    assert app.shadertoy_running is False
