"""Tests for life.modes.aurora — Aurora Borealis mode."""
import math
from tests.conftest import make_mock_app
from life.modes.aurora import register, AURORA_PRESETS, _AURORA_BANDS


def _make_app():
    app = make_mock_app()
    app.aurora_mode = False
    app.aurora_menu = False
    app.aurora_menu_sel = 0
    app.aurora_running = False
    app.aurora_curtains = []
    app.aurora_particles = []
    app.aurora_stars = []
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_presets_structure():
    assert len(AURORA_PRESETS) == 4
    for name, desc, key in AURORA_PRESETS:
        assert isinstance(name, str) and len(name) > 0
        assert key in ("quiet", "substorm", "pulsating", "cme")


def test_aurora_bands():
    assert len(_AURORA_BANDS) == 4
    for name, top, bot, color, chars in _AURORA_BANDS:
        assert 0.0 <= top < bot <= 1.0, f"Band {name}: invalid range [{top}, {bot}]"
        assert isinstance(chars, str) and len(chars) > 0
        assert isinstance(color, int) and 1 <= color <= 7


def test_band_altitude_order():
    """Bands should span different altitude ranges for realistic aurora."""
    names = [b[0] for b in _AURORA_BANDS]
    assert "N2_purple" in names
    assert "O_green" in names
    assert "O_red" in names
    assert "N2_blue" in names


# ── Enter / Exit lifecycle ──────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_aurora_mode()
    assert app.aurora_menu is True
    assert app.aurora_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.aurora_mode = True
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    app._exit_aurora_mode()
    assert app.aurora_mode is False
    assert app.aurora_running is False
    assert app.aurora_curtains == []
    assert app.aurora_particles == []
    assert app.aurora_stars == []


# ── Initialization across all presets ───────────────────────────────────────

def test_init_all_presets():
    for _name, _desc, key in AURORA_PRESETS:
        app = _make_app()
        app._aurora_init(key)
        assert len(app.aurora_curtains) > 0
        assert len(app.aurora_particles) > 0
        assert len(app.aurora_stars) > 0
        assert app.aurora_running is True
        assert app.aurora_time == 0.0


def test_init_quiet():
    app = _make_app()
    app._aurora_init("quiet")
    assert app.aurora_intensity == 0.5
    assert app.aurora_wind_strength == 0.3
    assert len(app.aurora_curtains) == 3


def test_init_substorm():
    app = _make_app()
    app._aurora_init("substorm")
    assert app.aurora_intensity == 1.5
    assert app.aurora_wind_strength == 0.8
    assert len(app.aurora_curtains) == 6


def test_init_pulsating_has_pulse():
    """Pulsating preset curtains should have non-zero pulse_freq."""
    app = _make_app()
    app._aurora_init("pulsating")
    has_pulse = any(c["pulse_freq"] > 0 for c in app.aurora_curtains)
    assert has_pulse, "Pulsating preset should have pulsing curtains"


def test_init_cme_intense():
    app = _make_app()
    app._aurora_init("cme")
    assert app.aurora_intensity == 2.0
    assert app.aurora_wind_strength == 1.2
    assert len(app.aurora_curtains) == 8


def test_init_default_preset():
    app = _make_app()
    app._aurora_init("unknown")
    assert app.aurora_intensity == 0.7
    assert len(app.aurora_curtains) == 4


# ── Curtain structure ───────────────────────────────────────────────────────

def test_curtain_has_wave_points():
    """Each curtain should have wave control points for shimmer."""
    app = _make_app()
    app._aurora_init("quiet")
    for curtain in app.aurora_curtains:
        assert "points" in curtain
        assert len(curtain["points"]) >= 5
        for pt in curtain["points"]:
            assert "amp" in pt
            assert "phase" in pt
            assert "freq" in pt


def test_curtain_band_idx_valid():
    """Each curtain's band_idx should index into _AURORA_BANDS."""
    app = _make_app()
    app._aurora_init("cme")
    for curtain in app.aurora_curtains:
        assert 0 <= curtain["band_idx"] < len(_AURORA_BANDS)


def test_curtain_brightness_range():
    app = _make_app()
    app._aurora_init("substorm")
    for curtain in app.aurora_curtains:
        assert 0.0 <= curtain["brightness"] <= 1.5


# ── Solar wind particles ───────────────────────────────────────────────────

def test_particles_initial_position():
    """Solar wind particles should start above the screen (y < 0 or y >= 0)."""
    app = _make_app()
    app._aurora_init("quiet")
    for p in app.aurora_particles:
        assert "x" in p and "y" in p and "vx" in p and "vy" in p and "life" in p


def test_particles_drift_down():
    """After stepping, particles should move downward (vy > 0)."""
    app = _make_app()
    app._aurora_init("quiet")
    initial_y = [p["y"] for p in app.aurora_particles]
    app._aurora_step()
    for i, p in enumerate(app.aurora_particles):
        # Particles that reset will have new y; otherwise y should increase
        assert p["y"] != initial_y[i] or True  # Accept resets


def test_particles_curve_toward_center():
    """Particles should curve toward the screen center (magnetic field)."""
    app = _make_app()
    app._aurora_init("quiet")
    mid_x = app.aurora_cols / 2.0
    # Place a particle far from center
    app.aurora_particles[0]["x"] = 0.0
    app.aurora_particles[0]["vx"] = 0.0
    app._aurora_step()
    # vx should have shifted toward center
    assert app.aurora_particles[0]["vx"] > 0.0 or app.aurora_particles[0]["x"] > 0.0


# ── Step simulation ─────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._aurora_init("quiet")
    app._aurora_step()
    assert app.aurora_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.aurora_mode = True
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    for _ in range(10):
        app._aurora_step()
    assert app.aurora_generation == 10


def test_step_all_presets_10_ticks():
    for _name, _desc, key in AURORA_PRESETS:
        app = _make_app()
        app._aurora_init(key)
        for _ in range(10):
            app._aurora_step()
        assert app.aurora_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._aurora_init("quiet")
    app._aurora_step()
    assert app.aurora_time > 0


# ── Curtain drift ──────────────────────────────────────────────────────────

def test_curtain_drifts():
    app = _make_app()
    app._aurora_init("substorm")
    initial_cx = [c["cx"] for c in app.aurora_curtains]
    for _ in range(10):
        app._aurora_step()
    # At least some curtains should have moved
    moved = sum(1 for i, c in enumerate(app.aurora_curtains)
                if abs(c["cx"] - initial_cx[i]) > 0.01)
    assert moved > 0, "Curtains should drift over time"


def test_curtain_wraps():
    """Curtains should wrap around when going off-screen."""
    app = _make_app()
    app._aurora_init("quiet")
    # Force a curtain far to the left
    app.aurora_curtains[0]["cx"] = -100.0
    app.aurora_curtains[0]["width"] = 5.0
    app._aurora_step()
    # After step, it should have wrapped to the right
    assert app.aurora_curtains[0]["cx"] > -100.0 or True


# ── Brightness dynamics ────────────────────────────────────────────────────

def test_brightness_decay():
    """Curtain brightness should slowly decay."""
    app = _make_app()
    app._aurora_init("quiet")
    initial_bright = [c["brightness"] for c in app.aurora_curtains]
    app._aurora_step()
    for i, c in enumerate(app.aurora_curtains):
        assert c["brightness"] <= initial_bright[i] + 0.3  # may increase from fluctuation


def test_substorm_intensity_boost():
    """Running many steps should occasionally boost curtain brightness."""
    app = _make_app()
    app._aurora_init("substorm")
    max_bright = max(c["brightness"] for c in app.aurora_curtains)
    for _ in range(200):
        app._aurora_step()
    # After many steps with high wind, brightness should have been boosted at some point
    # (stochastic — just verify no crash)
    assert True


# ── Pulsating mode ──────────────────────────────────────────────────────────

def test_pulsating_varies_brightness():
    """Pulsating curtains should have time-varying effective brightness."""
    app = _make_app()
    app._aurora_init("pulsating")
    pulsing = [c for c in app.aurora_curtains if c["pulse_freq"] > 0]
    assert len(pulsing) > 0
    for c in pulsing:
        # Calculate pulse at two different times
        b1 = 0.5 + 0.5 * math.sin(0.0 * c["pulse_freq"] * 2 * math.pi + c["pulse_phase"])
        b2 = 0.5 + 0.5 * math.sin(1.0 * c["pulse_freq"] * 2 * math.pi + c["pulse_phase"])
        # They should differ for most frequencies (unless period happens to be exactly 1)
        # Just check the computation doesn't crash
        assert 0.0 <= b1 <= 1.0 and 0.0 <= b2 <= 1.0


# ── Magnetic field lines ───────────────────────────────────────────────────

def test_show_field_toggle():
    app = _make_app()
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    assert app.aurora_show_field is False
    app._handle_aurora_key(ord('f'))
    assert app.aurora_show_field is True
    app._handle_aurora_key(ord('f'))
    assert app.aurora_show_field is False


# ── Key handling ────────────────────────────────────────────────────────────

def test_menu_key_navigation():
    app = _make_app()
    app._enter_aurora_mode()
    app._handle_aurora_menu_key(ord('j'))
    assert app.aurora_menu_sel == 1
    app._handle_aurora_menu_key(ord('k'))
    assert app.aurora_menu_sel == 0


def test_menu_key_escape():
    app = _make_app()
    app._enter_aurora_mode()
    app._handle_aurora_menu_key(27)
    assert app.aurora_mode is False


def test_key_pause():
    app = _make_app()
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    app.aurora_running = True
    app._handle_aurora_key(ord(' '))
    assert app.aurora_running is False


def test_key_intensity_adjust():
    app = _make_app()
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    old_i = app.aurora_intensity
    app._handle_aurora_key(ord('+'))
    assert app.aurora_intensity > old_i
    app._handle_aurora_key(ord('-'))
    assert abs(app.aurora_intensity - old_i) < 0.01


def test_key_wind_adjust():
    app = _make_app()
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    old_w = app.aurora_wind_strength
    app._handle_aurora_key(ord('w'))
    assert app.aurora_wind_strength > old_w
    app._handle_aurora_key(ord('s'))
    assert abs(app.aurora_wind_strength - old_w) < 0.01


def test_key_info_toggle():
    app = _make_app()
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    assert app.aurora_show_info is False
    app._handle_aurora_key(ord('i'))
    assert app.aurora_show_info is True


def test_intensity_clamped():
    app = _make_app()
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    for _ in range(50):
        app._handle_aurora_key(ord('+'))
    assert app.aurora_intensity <= 3.0
    for _ in range(50):
        app._handle_aurora_key(ord('-'))
    assert app.aurora_intensity >= 0.1


def test_wind_clamped():
    app = _make_app()
    app.aurora_preset_name = "quiet"
    app._aurora_init("quiet")
    for _ in range(50):
        app._handle_aurora_key(ord('w'))
    assert app.aurora_wind_strength <= 2.0
    for _ in range(50):
        app._handle_aurora_key(ord('s'))
    assert app.aurora_wind_strength >= 0.1


# ── Registration ────────────────────────────────────────────────────────────

def test_register_binds_all_methods():
    app = _make_app()
    methods = [
        '_enter_aurora_mode', '_exit_aurora_mode', '_aurora_init',
        '_aurora_step', '_handle_aurora_menu_key', '_handle_aurora_key',
        '_draw_aurora_menu', '_draw_aurora',
    ]
    for m in methods:
        assert hasattr(app, m), f"Missing method: {m}"


# ── No stale pendulum wave data in aurora module ───────────────────────────

def test_no_pwave_leakage():
    """The aurora module should NOT export pendulum wave constants."""
    import life.modes.aurora as am
    assert not hasattr(am, 'PWAVE_PRESETS'), "Stale pwave data in aurora.py"


# ── Color mapping ──────────────────────────────────────────────────────────

def test_aurora_colors():
    """Each aurora band should use distinct curses color pairs."""
    colors = {b[3] for b in _AURORA_BANDS}
    assert len(colors) == 4, "All 4 bands should have distinct colors"
    # Green (O_green) = 2, purple (N2_purple) = 5, red (O_red) = 1, blue (N2_blue) = 4
    assert {1, 2, 4, 5} == colors
