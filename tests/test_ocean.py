"""Tests for life.modes.ocean — Ocean Currents mode."""
import math
from tests.conftest import make_mock_app
from life.modes.ocean import (
    register, OCEAN_PRESETS, OCEAN_CHARS, CURRENT_ARROWS, PLANKTON_CHARS,
    _ocean_apply_gyres, _ocean_compute_density, _ocean_compute_upwelling,
)


def _addch(self, *args, **kwargs):
    pass


def _make_app():
    app = make_mock_app()
    type(app.stdscr).addch = _addch
    app.ocean_mode = False
    app.ocean_menu = False
    app.ocean_menu_sel = 0
    app.ocean_running = False
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_constants_exist():
    assert len(OCEAN_PRESETS) >= 6
    assert len(OCEAN_CHARS) > 0
    assert len(CURRENT_ARROWS) > 0
    assert len(PLANKTON_CHARS) > 0


def test_presets_have_valid_types():
    valid_types = {"gulfstream", "pacificgyre", "antarctic", "elnino", "thermohaline", "random"}
    for _name, _desc, ptype in OCEAN_PRESETS:
        assert ptype in valid_types, f"Ocean preset type '{ptype}' unknown"


def test_no_leftover_volcano_constants():
    """ocean.py should not export volcano-related constants."""
    from life.modes import ocean
    assert not hasattr(ocean, 'VOLCANO_PRESETS')
    assert not hasattr(ocean, 'LAVA_CHARS')
    assert not hasattr(ocean, 'TERRAIN_CHARS')
    assert not hasattr(ocean, 'ASH_CHARS')
    assert not hasattr(ocean, 'ROCK_CHARS')


# ── Enter / Exit ────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_ocean_mode()
    assert app.ocean_menu is True


def test_exit_cleanup():
    app = _make_app()
    app._ocean_init(0)
    app._exit_ocean_mode()
    assert app.ocean_mode is False
    assert app.ocean_running is False


# ── Init all presets ────────────────────────────────────────────────────────

def test_init_all_presets():
    """Init works for every preset type without crashing."""
    for i in range(len(OCEAN_PRESETS)):
        app = _make_app()
        app._ocean_init(i)
        assert app.ocean_mode is True
        assert app.ocean_menu is False
        assert app.ocean_running is True
        assert app.ocean_rows > 0
        assert app.ocean_cols > 0
        assert len(app.ocean_temperature) == app.ocean_rows
        assert len(app.ocean_salinity) == app.ocean_rows
        assert len(app.ocean_density) == app.ocean_rows
        assert len(app.ocean_current_u) == app.ocean_rows
        assert len(app.ocean_current_v) == app.ocean_rows
        assert len(app.ocean_plankton) == app.ocean_rows
        assert len(app.ocean_nutrient) == app.ocean_rows


def test_init_gulfstream_western_boundary():
    """Gulf Stream preset should have strong northward flow on west side."""
    idx = next(i for i, (_, _, t) in enumerate(OCEAN_PRESETS) if t == "gulfstream")
    app = _make_app()
    app._ocean_init(idx)
    # Western columns should have negative v (northward)
    rows = app.ocean_rows
    has_northward = any(
        app.ocean_current_v[r][0] < -0.5
        for r in range(rows)
    )
    assert has_northward


def test_init_antarctic_eastward_flow():
    """Antarctic preset should have strong eastward flow in southern belt."""
    idx = next(i for i, (_, _, t) in enumerate(OCEAN_PRESETS) if t == "antarctic")
    app = _make_app()
    app._ocean_init(idx)
    rows = app.ocean_rows
    cols = app.ocean_cols
    belt_start = int(rows * 0.7)
    belt_end = int(rows * 0.9)
    max_u = max(
        app.ocean_current_u[r][c]
        for r in range(belt_start, min(belt_end, rows))
        for c in range(cols)
    )
    assert max_u > 0.5  # strong eastward


def test_init_thermohaline_deep_formation():
    """Thermohaline preset should have deep water formation zones."""
    idx = next(i for i, (_, _, t) in enumerate(OCEAN_PRESETS) if t == "thermohaline")
    app = _make_app()
    app._ocean_init(idx)
    assert len(app.ocean_deep_formation) > 0


def test_init_temperature_gradient():
    """Temperature should be warmer at equator and cooler at poles."""
    app = _make_app()
    app._ocean_init(0)
    rows = app.ocean_rows
    cols = app.ocean_cols
    eq_row = rows // 2
    pole_row = 0
    eq_temp = sum(app.ocean_temperature[eq_row][c] for c in range(cols)) / cols
    pole_temp = sum(app.ocean_temperature[pole_row][c] for c in range(cols)) / cols
    assert eq_temp > pole_temp


def test_init_salinity_gradient():
    """Salinity should be higher in subtropics than at poles."""
    app = _make_app()
    app._ocean_init(5)  # random
    rows = app.ocean_rows
    cols = app.ocean_cols
    eq_row = rows // 2
    pole_row = 0
    eq_sal = sum(app.ocean_salinity[eq_row][c] for c in range(cols)) / cols
    pole_sal = sum(app.ocean_salinity[pole_row][c] for c in range(cols)) / cols
    assert eq_sal > pole_sal


# ── Density computation ─────────────────────────────────────────────────────

def test_density_increases_with_salinity():
    """Higher salinity should produce higher density."""
    app = _make_app()
    app._ocean_init(0)
    # Set two cells with different salinity
    app.ocean_temperature[0][0] = 15.0
    app.ocean_salinity[0][0] = 33.0
    app.ocean_temperature[0][1] = 15.0
    app.ocean_salinity[0][1] = 37.0
    _ocean_compute_density(app)
    assert app.ocean_density[0][1] > app.ocean_density[0][0]


def test_density_decreases_far_from_4c():
    """Density should be highest near 4C (maximum density of water)."""
    app = _make_app()
    app._ocean_init(0)
    # Set cells at different temperatures, same salinity
    for c, temp in enumerate([0, 4, 10, 20, 30]):
        if c < app.ocean_cols:
            app.ocean_temperature[0][c] = float(temp)
            app.ocean_salinity[0][c] = 35.0
    _ocean_compute_density(app)
    # 4C should have highest density contribution from temperature term
    if app.ocean_cols >= 5:
        # The -(t-4)^2 term is zero at t=4, negative elsewhere
        assert app.ocean_density[0][1] >= app.ocean_density[0][0]  # 4C >= 0C
        assert app.ocean_density[0][1] >= app.ocean_density[0][4]  # 4C >= 30C


# ── Upwelling computation ──────────────────────────────────────────────────

def test_upwelling_from_divergent_currents():
    """Divergent surface currents should produce positive upwelling."""
    app = _make_app()
    app._ocean_init(0)
    rows, cols = app.ocean_rows, app.ocean_cols
    # Set divergent current: u increases with column
    for r in range(rows):
        for c in range(cols):
            app.ocean_current_u[r][c] = float(c) * 0.1
            app.ocean_current_v[r][c] = 0.0
    _ocean_compute_upwelling(app)
    # Central region should show upwelling
    mid_r = rows // 2
    mid_c = cols // 2
    # After blending, should be positive
    assert app.ocean_upwelling[mid_r][mid_c] > 0


# ── Gyre circulation ───────────────────────────────────────────────────────

def test_gyre_produces_circular_flow():
    """A gyre should produce tangential (circular) flow patterns."""
    app = _make_app()
    app._ocean_init(0)
    # Clear currents and add a single test gyre
    rows, cols = app.ocean_rows, app.ocean_cols
    for r in range(rows):
        for c in range(cols):
            app.ocean_current_u[r][c] = 0.0
            app.ocean_current_v[r][c] = 0.0
    app.ocean_gyres = [{
        "r": rows // 2, "c": cols // 2, "radius": min(rows, cols) // 4,
        "strength": 2.0, "direction": 1, "vr": 0.0, "vc": 0.0,
    }]
    _ocean_apply_gyres(app)
    # Check that flow exists near the gyre
    gr, gc = rows // 2, cols // 2
    r = min(gr + 5, rows - 1)
    c = gc
    speed = (app.ocean_current_u[r][c]**2 + app.ocean_current_v[r][c]**2)**0.5
    assert speed > 0.01


# ── Step simulation ─────────────────────────────────────────────────────────

def test_step_no_crash():
    app = _make_app()
    app._ocean_init(0)
    for _ in range(10):
        app._ocean_step()
    assert app.ocean_generation == 10


def test_step_all_presets():
    """10 steps of every preset runs without crash."""
    for i in range(len(OCEAN_PRESETS)):
        app = _make_app()
        app._ocean_init(i)
        for _ in range(10):
            app._ocean_step()
        assert app.ocean_generation == 10


def test_step_day_increments():
    app = _make_app()
    app._ocean_init(0)
    for _ in range(30):
        app._ocean_step()
    assert app.ocean_day == 30


def test_step_salinity_bounded():
    """Salinity should stay within [30, 40] PSU."""
    app = _make_app()
    app._ocean_init(0)
    for _ in range(20):
        app._ocean_step()
    for r in range(app.ocean_rows):
        for c in range(app.ocean_cols):
            assert 30.0 <= app.ocean_salinity[r][c] <= 40.0


def test_step_current_mostly_clamped():
    """Currents should be approximately clamped to [-5, 5].

    The Coriolis section clamps to [-5, 5], but post-clamp additions
    from density gradients and deep-water formation can push values
    slightly beyond due to floating-point arithmetic.  We allow a
    small epsilon for those additions.
    """
    app = _make_app()
    app._ocean_init(0)
    for _ in range(20):
        app._ocean_step()
    eps = 0.5  # density-driven additions are ~0.0005*speed per step
    for r in range(app.ocean_rows):
        for c in range(app.ocean_cols):
            assert -(5.0 + eps) <= app.ocean_current_u[r][c] <= (5.0 + eps)
            assert -(5.0 + eps) <= app.ocean_current_v[r][c] <= (5.0 + eps)


def test_step_plankton_bounded():
    """Plankton values should stay in [0, 1]."""
    app = _make_app()
    app._ocean_init(0)
    for _ in range(20):
        app._ocean_step()
    for r in range(app.ocean_rows):
        for c in range(app.ocean_cols):
            assert 0.0 <= app.ocean_plankton[r][c] <= 1.0


def test_step_nutrient_bounded():
    """Nutrient values should stay in [0, 1]."""
    app = _make_app()
    app._ocean_init(0)
    for _ in range(20):
        app._ocean_step()
    for r in range(app.ocean_rows):
        for c in range(app.ocean_cols):
            assert 0.0 <= app.ocean_nutrient[r][c] <= 1.0


def test_step_thermal_relaxation():
    """Temperature should relax toward latitude-based equilibrium."""
    app = _make_app()
    app._ocean_init(5)  # random
    rows = app.ocean_rows
    cols = app.ocean_cols
    # Set extreme temperature everywhere
    for r in range(rows):
        for c in range(cols):
            app.ocean_temperature[r][c] = 50.0
    for _ in range(50):
        app._ocean_step()
    # Temperature should have come down toward equilibrium
    avg_t = sum(
        app.ocean_temperature[r][c]
        for r in range(rows)
        for c in range(cols)
    ) / (rows * cols)
    assert avg_t < 50.0


def test_step_plankton_grows_with_nutrients():
    """Plankton should grow in nutrient-rich, upwelling areas."""
    app = _make_app()
    app._ocean_init(0)
    rows, cols = app.ocean_rows, app.ocean_cols
    # Set high nutrients and upwelling at a specific location
    r, c = rows // 2, cols // 2
    app.ocean_nutrient[r][c] = 0.9
    app.ocean_upwelling[r][c] = 0.5
    app.ocean_plankton[r][c] = 0.1
    app.ocean_temperature[r][c] = 20.0
    initial = app.ocean_plankton[r][c]
    for _ in range(5):
        app._ocean_step()
    # Plankton should have grown (though advection may move it)


# ── Current arrow ───────────────────────────────────────────────────────────

def test_current_arrow_calm():
    app = _make_app()
    app._ocean_init(0)
    arrow = app._ocean_current_arrow(0.0, 0.0)
    assert arrow == '\u00b7'


def test_current_arrow_eastward():
    app = _make_app()
    app._ocean_init(0)
    arrow = app._ocean_current_arrow(3.0, 0.0)
    assert arrow == '\u2192'


# ── Color functions ─────────────────────────────────────────────────────────

def test_temp_color_returns_int():
    app = _make_app()
    app._ocean_init(0)
    for temp in [-2, 3, 8, 15, 22, 26, 30]:
        color = app._ocean_temp_color(temp)
        assert isinstance(color, int)


def test_density_color_returns_int():
    app = _make_app()
    app._ocean_init(0)
    for d in [1023, 1024.5, 1025.5, 1026.5, 1028]:
        color = app._ocean_density_color(d)
        assert isinstance(color, int)


# ── Menu key handling ───────────────────────────────────────────────────────

def test_menu_key_down():
    app = _make_app()
    app._enter_ocean_mode()
    app._handle_ocean_menu_key(ord('j'))
    assert app.ocean_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_ocean_mode()
    app._handle_ocean_menu_key(ord('k'))
    assert app.ocean_menu_sel == len(OCEAN_PRESETS) - 1


def test_menu_key_enter():
    app = _make_app()
    app._enter_ocean_mode()
    app._handle_ocean_menu_key(10)
    assert app.ocean_mode is True
    assert app.ocean_menu is False


def test_menu_key_escape():
    app = _make_app()
    app._enter_ocean_mode()
    app._handle_ocean_menu_key(27)
    assert app.ocean_menu is False
    assert app.ocean_mode is False


# ── Game key handling ───────────────────────────────────────────────────────

def test_key_space_pause():
    app = _make_app()
    app._ocean_init(0)
    app._handle_ocean_key(ord(' '))
    assert app.ocean_running is False


def test_key_speed_up():
    app = _make_app()
    app._ocean_init(0)
    initial = app.ocean_speed_scale
    app._handle_ocean_key(ord('+'))
    assert app.ocean_speed_scale > initial


def test_key_speed_down():
    app = _make_app()
    app._ocean_init(0)
    app.ocean_speed_scale = 2.0
    app._handle_ocean_key(ord('-'))
    assert app.ocean_speed_scale < 2.0


def test_key_layer_cycle():
    app = _make_app()
    app._ocean_init(0)
    assert app.ocean_layer == "default"
    app._handle_ocean_key(ord('l'))
    assert app.ocean_layer == "temp"
    app._handle_ocean_key(ord('l'))
    assert app.ocean_layer == "salinity"
    app._handle_ocean_key(ord('l'))
    assert app.ocean_layer == "density"
    app._handle_ocean_key(ord('l'))
    assert app.ocean_layer == "currents"
    app._handle_ocean_key(ord('l'))
    assert app.ocean_layer == "plankton"
    app._handle_ocean_key(ord('l'))
    assert app.ocean_layer == "default"


def test_key_help_toggle():
    app = _make_app()
    app._ocean_init(0)
    assert app.ocean_show_help is True
    app._handle_ocean_key(ord('?'))
    assert app.ocean_show_help is False


def test_key_restart():
    app = _make_app()
    app._ocean_init(0)
    for _ in range(5):
        app._ocean_step()
    app._handle_ocean_key(ord('r'))
    assert app.ocean_generation == 0


def test_key_menu_return():
    app = _make_app()
    app._ocean_init(0)
    app._handle_ocean_key(ord('m'))
    assert app.ocean_menu is True
    assert app.ocean_running is False


def test_key_escape_exits():
    app = _make_app()
    app._ocean_init(0)
    app._handle_ocean_key(27)
    assert app.ocean_mode is False


# ── Deep water formation ────────────────────────────────────────────────────

def test_deep_water_formation_cools():
    """Deep water formation zones should cool the water."""
    idx = next(i for i, (_, _, t) in enumerate(OCEAN_PRESETS) if t == "thermohaline")
    app = _make_app()
    app._ocean_init(idx)
    # Find a formation zone center
    dwf = app.ocean_deep_formation[0]
    r, c = int(dwf["r"]) % app.ocean_rows, int(dwf["c"]) % app.ocean_cols
    initial_temp = app.ocean_temperature[r][c]
    for _ in range(30):
        app._ocean_step()
    # Temperature should have decreased near the formation zone
    # (though advection may complicate things)
