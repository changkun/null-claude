"""Tests for life.modes.weather — Atmospheric Weather mode."""
import math
from tests.conftest import make_mock_app
from life.modes.weather import (
    register, WEATHER_PRESETS, CLOUD_CHARS,
    _weather_apply_pressure_centers, _weather_compute_wind, _weather_update_clouds,
)


def _addch(self, *args, **kwargs):
    pass


def _make_app():
    app = make_mock_app()
    type(app.stdscr).addch = _addch
    app.weather_mode = False
    app.weather_menu = False
    app.weather_menu_sel = 0
    app.weather_running = False
    app.weather_coriolis = 0.15
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_constants_exist():
    assert len(WEATHER_PRESETS) >= 6
    assert len(CLOUD_CHARS) > 0


def test_presets_have_valid_types():
    valid_types = {"cyclone", "fronts", "highpressure", "monsoon", "arctic", "random"}
    for _name, _desc, ptype in WEATHER_PRESETS:
        assert ptype in valid_types, f"Weather preset type '{ptype}' unknown"


# ── Enter / Exit ────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_weather_mode()
    assert app.weather_menu is True


def test_exit_cleanup():
    app = _make_app()
    app._weather_init(0)
    app._exit_weather_mode()
    assert app.weather_mode is False
    assert app.weather_running is False


# ── Init all presets ────────────────────────────────────────────────────────

def test_init_all_presets():
    """Init works for every preset type without crashing."""
    for i in range(len(WEATHER_PRESETS)):
        app = _make_app()
        app._weather_init(i)
        assert app.weather_mode is True
        assert app.weather_menu is False
        assert app.weather_running is True
        assert app.weather_rows > 0
        assert app.weather_cols > 0
        assert len(app.weather_pressure) == app.weather_rows
        assert len(app.weather_temperature) == app.weather_rows
        assert len(app.weather_humidity) == app.weather_rows
        assert len(app.weather_wind_u) == app.weather_rows
        assert len(app.weather_wind_v) == app.weather_rows
        assert len(app.weather_cloud) == app.weather_rows
        assert len(app.weather_precip) == app.weather_rows


def test_init_cyclone_low_pressure():
    """Cyclone preset should have a low-pressure center."""
    idx = next(i for i, (_, _, t) in enumerate(WEATHER_PRESETS) if t == "cyclone")
    app = _make_app()
    app._weather_init(idx)
    has_low = any(c["type"] == "low" for c in app.weather_centers)
    assert has_low


def test_init_fronts_has_cold_front():
    """Fronts preset should include a cold front."""
    idx = next(i for i, (_, _, t) in enumerate(WEATHER_PRESETS) if t == "fronts")
    app = _make_app()
    app._weather_init(idx)
    has_cold = any(f["type"] == "cold" for f in app.weather_fronts)
    assert has_cold


def test_init_highpressure_dry():
    """High pressure preset should have reduced humidity."""
    idx = next(i for i, (_, _, t) in enumerate(WEATHER_PRESETS) if t == "highpressure")
    app = _make_app()
    app._weather_init(idx)
    avg_h = sum(
        app.weather_humidity[r][c]
        for r in range(app.weather_rows)
        for c in range(app.weather_cols)
    ) / (app.weather_rows * app.weather_cols)
    # Should be below average due to 0.6 multiplier
    assert avg_h < 0.6


def test_init_temperature_gradient():
    """Temperature should be warmer at center (equator) and cooler at edges (poles)."""
    app = _make_app()
    app._weather_init(0)
    rows = app.weather_rows
    cols = app.weather_cols
    # Average temp at equator vs poles
    eq_row = rows // 2
    pole_row = 0
    eq_temp = sum(app.weather_temperature[eq_row][c] for c in range(cols)) / cols
    pole_temp = sum(app.weather_temperature[pole_row][c] for c in range(cols)) / cols
    assert eq_temp > pole_temp


# ── Pressure centers ────────────────────────────────────────────────────────

def test_pressure_centers_applied():
    """Pressure field should reflect the centers."""
    app = _make_app()
    app._weather_init(0)  # cyclone
    # Find the low pressure center
    low_center = next(c for c in app.weather_centers if c["type"] == "low")
    cr, cc = int(low_center["r"]), int(low_center["c"])
    # Pressure at center should be below 1013.25
    if 0 <= cr < app.weather_rows and 0 <= cc < app.weather_cols:
        assert app.weather_pressure[cr][cc] < 1013.25


# ── Wind computation ────────────────────────────────────────────────────────

def test_wind_nonzero_near_gradient():
    """Wind should be nonzero where there's a pressure gradient."""
    app = _make_app()
    app._weather_init(0)  # cyclone creates strong gradient
    rows, cols = app.weather_rows, app.weather_cols
    max_wind = max(
        abs(app.weather_wind_u[r][c]) + abs(app.weather_wind_v[r][c])
        for r in range(rows)
        for c in range(cols)
    )
    assert max_wind > 0.1


def test_wind_arrow_calm():
    app = _make_app()
    app._weather_init(0)
    arrow = app._weather_wind_arrow(0.0, 0.0)
    assert arrow == '\u00b7'


def test_wind_arrow_direction():
    app = _make_app()
    app._weather_init(0)
    # Strong eastward wind
    arrow = app._weather_wind_arrow(5.0, 0.0)
    assert arrow == '\u2192'  # right arrow


# ── Cloud and precipitation ─────────────────────────────────────────────────

def test_clouds_form_in_low_pressure():
    """Low pressure areas should develop clouds."""
    idx = next(i for i, (_, _, t) in enumerate(WEATHER_PRESETS) if t == "cyclone")
    app = _make_app()
    app._weather_init(idx)
    # After initial cloud computation, check for clouds
    has_cloud = any(
        app.weather_cloud[r][c] > 0.1
        for r in range(app.weather_rows)
        for c in range(app.weather_cols)
    )
    assert has_cloud


def test_precip_type_rain_or_snow():
    """Precipitation type should be 0 (none), 1 (rain), or 2 (snow)."""
    app = _make_app()
    app._weather_init(0)
    for _ in range(10):
        app._weather_step()
    for r in range(app.weather_rows):
        for c in range(app.weather_cols):
            assert app.weather_precip_type[r][c] in (0, 1, 2)


def test_precip_snow_when_cold():
    """Snow (type 2) should only occur when temperature < 2.0."""
    app = _make_app()
    # Use arctic for cold temperatures
    idx = next(i for i, (_, _, t) in enumerate(WEATHER_PRESETS) if t == "arctic")
    app._weather_init(idx)
    for _ in range(20):
        app._weather_step()
    for r in range(app.weather_rows):
        for c in range(app.weather_cols):
            if app.weather_precip_type[r][c] == 2:
                assert app.weather_temperature[r][c] < 2.0


# ── Step simulation ─────────────────────────────────────────────────────────

def test_step_no_crash():
    app = _make_app()
    app._weather_init(0)
    for _ in range(10):
        app._weather_step()
    assert app.weather_generation == 10


def test_step_all_presets():
    """10 steps of every preset runs without crash."""
    for i in range(len(WEATHER_PRESETS)):
        app = _make_app()
        app._weather_init(i)
        for _ in range(10):
            app._weather_step()
        assert app.weather_generation == 10


def test_step_hour_increments():
    app = _make_app()
    app._weather_init(0)
    for _ in range(24):
        app._weather_step()
    assert app.weather_hour == 24


def test_step_pressure_centers_move():
    """Pressure centers should move over time."""
    idx = next(i for i, (_, _, t) in enumerate(WEATHER_PRESETS) if t == "cyclone")
    app = _make_app()
    app._weather_init(idx)
    initial_positions = [(c["r"], c["c"]) for c in app.weather_centers]
    for _ in range(20):
        app._weather_step()
    final_positions = [(c["r"], c["c"]) for c in app.weather_centers[:len(initial_positions)]]
    # At least one center should have moved
    moved = any(
        abs(ip[0] - fp[0]) > 0.1 or abs(ip[1] - fp[1]) > 0.1
        for ip, fp in zip(initial_positions, final_positions)
    )
    assert moved


def test_step_humidity_bounded():
    """Humidity should stay in [0, 1] range."""
    app = _make_app()
    app._weather_init(0)
    for _ in range(20):
        app._weather_step()
    for r in range(app.weather_rows):
        for c in range(app.weather_cols):
            assert 0.0 <= app.weather_humidity[r][c] <= 1.0


def test_step_wind_clamped():
    """Wind values should be clamped to [-15, 15]."""
    app = _make_app()
    app._weather_init(0)
    for _ in range(20):
        app._weather_step()
    for r in range(app.weather_rows):
        for c in range(app.weather_cols):
            assert -15.0 <= app.weather_wind_u[r][c] <= 15.0
            assert -15.0 <= app.weather_wind_v[r][c] <= 15.0


# ── Color functions ─────────────────────────────────────────────────────────

def test_temp_color_returns_int():
    app = _make_app()
    app._weather_init(0)
    for temp in [-20, -5, 5, 15, 25, 35]:
        color = app._weather_temp_color(temp)
        assert isinstance(color, int)


def test_pressure_color_returns_int():
    app = _make_app()
    app._weather_init(0)
    for p in [960, 995, 1010, 1020, 1040]:
        color = app._weather_pressure_color(p)
        assert isinstance(color, int)


# ── Menu key handling ───────────────────────────────────────────────────────

def test_menu_key_down():
    app = _make_app()
    app._enter_weather_mode()
    app._handle_weather_menu_key(ord('j'))
    assert app.weather_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_weather_mode()
    app._handle_weather_menu_key(ord('k'))
    assert app.weather_menu_sel == len(WEATHER_PRESETS) - 1


def test_menu_key_enter():
    app = _make_app()
    app._enter_weather_mode()
    app._handle_weather_menu_key(10)
    assert app.weather_mode is True
    assert app.weather_menu is False


def test_menu_key_escape():
    app = _make_app()
    app._enter_weather_mode()
    app._handle_weather_menu_key(27)
    assert app.weather_menu is False
    assert app.weather_mode is False


# ── Game key handling ───────────────────────────────────────────────────────

def test_key_space_pause():
    app = _make_app()
    app._weather_init(0)
    app._handle_weather_key(ord(' '))
    assert app.weather_running is False


def test_key_speed_up():
    app = _make_app()
    app._weather_init(0)
    initial = app.weather_speed_scale
    app._handle_weather_key(ord('+'))
    assert app.weather_speed_scale > initial


def test_key_layer_cycle():
    app = _make_app()
    app._weather_init(0)
    assert app.weather_layer == "default"
    app._handle_weather_key(ord('l'))
    assert app.weather_layer == "pressure"
    app._handle_weather_key(ord('l'))
    assert app.weather_layer == "temp"
    app._handle_weather_key(ord('l'))
    assert app.weather_layer == "wind"
    app._handle_weather_key(ord('l'))
    assert app.weather_layer == "humidity"
    app._handle_weather_key(ord('l'))
    assert app.weather_layer == "default"


def test_key_help_toggle():
    app = _make_app()
    app._weather_init(0)
    assert app.weather_show_help is True
    app._handle_weather_key(ord('?'))
    assert app.weather_show_help is False


def test_key_restart():
    app = _make_app()
    app._weather_init(0)
    for _ in range(5):
        app._weather_step()
    app._handle_weather_key(ord('r'))
    assert app.weather_generation == 0


def test_key_menu_return():
    app = _make_app()
    app._weather_init(0)
    app._handle_weather_key(ord('m'))
    assert app.weather_menu is True
    assert app.weather_running is False


def test_key_escape_exits():
    app = _make_app()
    app._weather_init(0)
    app._handle_weather_key(27)
    assert app.weather_mode is False


# ── Advection correctness ──────────────────────────────────────────────────

def test_bilinear_interpolation_preserves_uniform():
    """If temperature is uniform, advection should preserve it."""
    app = _make_app()
    app._weather_init(0)
    # Set uniform temperature
    for r in range(app.weather_rows):
        for c in range(app.weather_cols):
            app.weather_temperature[r][c] = 20.0
    # One step of advection
    app._weather_step()
    # Temperature should still be close to 20.0 (some drift from fronts is OK)
    avg_t = sum(
        app.weather_temperature[r][c]
        for r in range(app.weather_rows)
        for c in range(app.weather_cols)
    ) / (app.weather_rows * app.weather_cols)
    # Should be within a few degrees
    assert abs(avg_t - 20.0) < 5.0


# ── No leftover ocean constants ─────────────────────────────────────────────

def test_no_leftover_ocean_constants():
    """weather.py should not export ocean-related constants."""
    from life.modes import weather
    assert not hasattr(weather, 'OCEAN_PRESETS')
    assert not hasattr(weather, 'OCEAN_CHARS')
    assert not hasattr(weather, 'CURRENT_ARROWS')
    assert not hasattr(weather, 'PLANKTON_CHARS')
