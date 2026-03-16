"""Tests for life.modes.orrery — Solar System Orrery mode."""
import math
from tests.conftest import make_mock_app
from life.modes.orrery import (
    register, ORRERY_PRESETS, _ORRERY_PLANETS, _orrery_solve_kepler,
)


def _make_app():
    app = make_mock_app()
    app.orrery_mode = False
    app.orrery_menu = False
    app.orrery_menu_sel = 0
    app.orrery_running = False
    app.orrery_dt = 0.002
    app.orrery_trail_len = 60
    app.orrery_planets = []
    app.orrery_asteroids = []
    app.orrery_comets = []
    app.orrery_bg_stars = []
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_planet_data():
    assert len(_ORRERY_PLANETS) == 8
    names = [p["name"] for p in _ORRERY_PLANETS]
    assert names == ["Mercury", "Venus", "Earth", "Mars",
                     "Jupiter", "Saturn", "Uranus", "Neptune"]


def test_planet_kepler_third_law():
    """Verify T^2 ~ a^3 for each planet (Kepler's third law)."""
    for p in _ORRERY_PLANETS:
        a, T = p["a"], p["T"]
        ratio = T * T / (a ** 3)
        assert 0.8 < ratio < 1.2, f"{p['name']}: T^2/a^3 = {ratio:.3f}, expected ~1.0"


def test_planet_eccentricities():
    """All eccentricities should be in [0, 1)."""
    for p in _ORRERY_PLANETS:
        assert 0 <= p["e"] < 1, f"{p['name']} has invalid eccentricity {p['e']}"


def test_presets_structure():
    assert len(ORRERY_PRESETS) == 6
    for name, desc, key in ORRERY_PRESETS:
        assert isinstance(name, str)
        assert key in ("full", "inner", "outer", "neighbors", "comet", "alignment")


# ── Kepler's equation solver ────────────────────────────────────────────────

def test_solve_kepler_circular():
    """For e=0, E should equal M."""
    for M in [0.0, 1.0, math.pi, 5.0]:
        E = _orrery_solve_kepler(M, 0.0)
        assert abs(E - M) < 1e-5, f"Circular orbit: E={E}, M={M}"


def test_solve_kepler_moderate_eccentricity():
    """For moderate e, verify M = E - e*sin(E)."""
    for e in [0.1, 0.3, 0.5, 0.7]:
        for M in [0.5, 1.5, 3.0, 5.5]:
            E = _orrery_solve_kepler(M, e)
            residual = abs(M - (E - e * math.sin(E)))
            assert residual < 1e-5, f"e={e}, M={M}: residual={residual}"


def test_solve_kepler_high_eccentricity():
    """Should converge even for high eccentricity (e.g. comets)."""
    E = _orrery_solve_kepler(3.0, 0.95)
    residual = abs(3.0 - (E - 0.95 * math.sin(E)))
    assert residual < 1e-4


# ── Enter / Exit lifecycle ──────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_orrery_mode()
    assert app.orrery_menu is True


def test_exit_cleanup():
    app = _make_app()
    app.orrery_mode = True
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    app._exit_orrery_mode()
    assert app.orrery_mode is False
    assert app.orrery_planets == []
    assert app.orrery_asteroids == []
    assert app.orrery_comets == []


# ── Initialization across all presets ───────────────────────────────────────

def test_init_all_presets():
    for _name, _desc, key in ORRERY_PRESETS:
        app = _make_app()
        app._orrery_init(key)
        assert len(app.orrery_planets) > 0
        assert app.orrery_running is True
        assert app.orrery_time == 0.0


def test_init_inner_planets():
    app = _make_app()
    app._orrery_init("inner")
    assert len(app.orrery_planets) == 4
    names = {p["name"] for p in app.orrery_planets}
    assert names == {"Mercury", "Venus", "Earth", "Mars"}
    assert app.orrery_zoom == "inner"
    assert len(app.orrery_asteroids) == 0


def test_init_outer_planets():
    app = _make_app()
    app._orrery_init("outer")
    assert len(app.orrery_planets) == 4
    names = {p["name"] for p in app.orrery_planets}
    assert names == {"Jupiter", "Saturn", "Uranus", "Neptune"}
    assert app.orrery_zoom == "outer"


def test_init_neighbors():
    app = _make_app()
    app._orrery_init("neighbors")
    names = {p["name"] for p in app.orrery_planets}
    assert names == {"Venus", "Earth", "Mars"}
    assert app.orrery_show_info is True


def test_init_comet_preset():
    app = _make_app()
    app._orrery_init("comet")
    assert len(app.orrery_comets) == 1
    assert app.orrery_comets[0]["e"] == 0.967  # highly eccentric


def test_init_alignment():
    app = _make_app()
    app._orrery_init("alignment")
    # All planets should start with small mean anomaly (near-aligned)
    for p in app.orrery_planets:
        assert abs(p["M0"]) < 0.2


def test_init_full_asteroid_belt():
    app = _make_app()
    app._orrery_init("full")
    assert len(app.orrery_asteroids) > 0
    for ast in app.orrery_asteroids:
        assert 2.0 <= ast["a"] <= 3.4
        assert 0 <= ast["e"] <= 0.25


# ── Scale and positioning ──────────────────────────────────────────────────

def test_get_scale():
    app = _make_app()
    app._orrery_init("full")
    cx, cy, scale = app._orrery_get_scale()
    assert cx > 0 and cy > 0
    assert scale > 0


def test_get_scale_inner_zoom():
    app = _make_app()
    app._orrery_init("inner")
    _, _, scale_inner = app._orrery_get_scale()
    app.orrery_zoom = "full"
    _, _, scale_full = app._orrery_get_scale()
    assert scale_inner > scale_full, "Inner zoom should have larger scale"


def test_body_pos_earth():
    """Earth at t=0 should be at approximately 1 AU from the Sun."""
    app = _make_app()
    app._orrery_init("full")
    earth = None
    for p in app.orrery_planets:
        if p["name"] == "Earth":
            earth = p
            break
    assert earth is not None
    sc, sr, r, nu = app._orrery_body_pos(earth, 0.0)
    assert 0.98 < r < 1.02, f"Earth orbital radius = {r}, expected ~1.0 AU"


def test_body_pos_changes_with_time():
    """Planet position should change over time."""
    app = _make_app()
    app._orrery_init("full")
    earth = [p for p in app.orrery_planets if p["name"] == "Earth"][0]
    sc0, sr0, _, _ = app._orrery_body_pos(earth, 0.0)
    sc1, sr1, _, _ = app._orrery_body_pos(earth, 0.25)  # quarter year
    assert (sc0, sr0) != (sc1, sr1), "Earth should move over 0.25 years"


def test_body_pos_full_orbit():
    """After one full period, planet should return to nearly same position."""
    app = _make_app()
    app._orrery_init("full")
    earth = [p for p in app.orrery_planets if p["name"] == "Earth"][0]
    sc0, sr0, r0, nu0 = app._orrery_body_pos(earth, 0.0)
    sc1, sr1, r1, nu1 = app._orrery_body_pos(earth, 1.0)  # one year
    assert abs(r0 - r1) < 0.01, "Radius should match after one period"


# ── Step simulation ─────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._orrery_init("full")
    app._orrery_step()
    assert app.orrery_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.orrery_mode = True
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    for _ in range(10):
        app._orrery_step()
    assert app.orrery_generation == 10


def test_step_all_presets():
    for _name, _desc, key in ORRERY_PRESETS:
        app = _make_app()
        app._orrery_init(key)
        for _ in range(10):
            app._orrery_step()
        assert app.orrery_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._orrery_init("full")
    app._orrery_step()
    assert app.orrery_time > 0


def test_step_updates_trails():
    app = _make_app()
    app._orrery_init("full")
    for _ in range(5):
        app._orrery_step()
    for planet in app.orrery_planets:
        assert len(planet["trail"]) == 5


def test_trail_length_capped():
    app = _make_app()
    app.orrery_trail_len = 10
    app._orrery_init("full")
    for _ in range(20):
        app._orrery_step()
    for planet in app.orrery_planets:
        assert len(planet["trail"]) <= 10


def test_comet_trail_longer():
    app = _make_app()
    app.orrery_trail_len = 10
    app._orrery_init("comet")
    for _ in range(50):
        app._orrery_step()
    for comet in app.orrery_comets:
        # Comet trails can be up to 3x planet trail length
        assert len(comet["trail"]) <= 30


# ── Speed scale ─────────────────────────────────────────────────────────────

def test_speed_scale():
    app = _make_app()
    app._orrery_init("full")
    app.orrery_speed_scale = 5.0
    app._orrery_step()
    expected_dt = 0.002 * 5.0
    assert abs(app.orrery_time - expected_dt) < 1e-10


# ── Key handling ────────────────────────────────────────────────────────────

def test_menu_key_navigation():
    app = _make_app()
    app._enter_orrery_mode()
    app._handle_orrery_menu_key(ord('j'))
    assert app.orrery_menu_sel == 1
    app._handle_orrery_menu_key(ord('k'))
    assert app.orrery_menu_sel == 0


def test_menu_key_escape():
    app = _make_app()
    app._enter_orrery_mode()
    app._handle_orrery_menu_key(27)
    assert app.orrery_mode is False


def test_key_pause():
    app = _make_app()
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    app.orrery_running = True
    app._handle_orrery_key(ord(' '))
    assert app.orrery_running is False


def test_key_zoom_cycle():
    app = _make_app()
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    assert app.orrery_zoom == "full"
    app._handle_orrery_key(ord('z'))
    assert app.orrery_zoom == "inner"
    app._handle_orrery_key(ord('z'))
    assert app.orrery_zoom == "outer"
    app._handle_orrery_key(ord('z'))
    assert app.orrery_zoom == "full"


def test_key_orbit_toggle():
    app = _make_app()
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    assert app.orrery_show_orbits is True
    app._handle_orrery_key(ord('o'))
    assert app.orrery_show_orbits is False


def test_key_label_toggle():
    app = _make_app()
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    assert app.orrery_show_labels is True
    app._handle_orrery_key(ord('l'))
    assert app.orrery_show_labels is False


def test_key_speed_adjust():
    app = _make_app()
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    old = app.orrery_speed_scale
    app._handle_orrery_key(ord('+'))
    assert app.orrery_speed_scale > old
    app._handle_orrery_key(ord('-'))
    assert abs(app.orrery_speed_scale - old) < 0.01


def test_key_tab_select():
    app = _make_app()
    app.orrery_preset_name = "full"
    app._orrery_init("full")
    assert app.orrery_selected == -1
    app._handle_orrery_key(ord('\t'))
    assert app.orrery_selected == 0
    app._handle_orrery_key(ord('\t'))
    assert app.orrery_selected == 1
    app._handle_orrery_key(ord('u'))
    assert app.orrery_selected == -1


# ── Registration ────────────────────────────────────────────────────────────

def test_register_binds_all_methods():
    app = _make_app()
    methods = [
        '_enter_orrery_mode', '_exit_orrery_mode', '_orrery_solve_kepler',
        '_orrery_init', '_orrery_get_scale', '_orrery_body_pos',
        '_orrery_step', '_handle_orrery_menu_key', '_handle_orrery_key',
        '_draw_orrery_menu', '_draw_orrery',
    ]
    for m in methods:
        assert hasattr(app, m), f"Missing method: {m}"


# ── No stale aurora data in orrery module ───────────────────────────────────

def test_no_aurora_leakage():
    """The orrery module should NOT export aurora constants."""
    import life.modes.orrery as om
    assert not hasattr(om, 'AURORA_PRESETS'), "Stale aurora data in orrery.py"
    assert not hasattr(om, '_AURORA_BANDS'), "Stale aurora data in orrery.py"
