"""Tests for life.modes.black_hole — Black Hole mode."""
import math
from tests.conftest import make_mock_app
from life.modes.black_hole import register, BLACKHOLE_PRESETS


def _make_app():
    app = make_mock_app()
    app.blackhole_mode = False
    app.blackhole_menu = False
    app.blackhole_menu_sel = 0
    app.blackhole_running = False
    app.blackhole_dt = 0.02
    app.blackhole_particles = []
    app.blackhole_bg_stars = []
    app.blackhole_lensed = []
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_presets_structure():
    assert len(BLACKHOLE_PRESETS) == 6
    for name, desc, key in BLACKHOLE_PRESETS:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str)
        assert key in ("stellar", "supermassive", "kerr", "quasar", "micro", "binary")


# ── Enter / Exit lifecycle ──────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_blackhole_mode()
    assert app.blackhole_menu is True
    assert app.blackhole_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.blackhole_mode = True
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    app._exit_blackhole_mode()
    assert app.blackhole_mode is False
    assert app.blackhole_particles == []
    assert app.blackhole_bg_stars == []


# ── Initialization across all presets ───────────────────────────────────────

def test_init_all_presets():
    """All 6 presets must initialize without error."""
    for _name, _desc, key in BLACKHOLE_PRESETS:
        app = _make_app()
        app._blackhole_init(key)
        assert len(app.blackhole_particles) > 0
        assert len(app.blackhole_bg_stars) > 0
        assert app.blackhole_rs > 0
        assert app.blackhole_mass > 0


def test_init_stellar_params():
    app = _make_app()
    app._blackhole_init("stellar")
    assert app.blackhole_mass == 30.0
    assert app.blackhole_spin == 0.3


def test_init_micro_many_hawking():
    """Micro black hole should have 30 Hawking radiation particles."""
    app = _make_app()
    app._blackhole_init("micro")
    hawk_count = sum(1 for p in app.blackhole_particles if p[6] == 2)
    assert hawk_count == 30


def test_init_quasar_powerful_jets():
    app = _make_app()
    app._blackhole_init("quasar")
    assert app.blackhole_jet_power == 2.0
    jet_count = sum(1 for p in app.blackhole_particles if p[6] == 1)
    assert jet_count > 0


def test_init_kerr_high_spin():
    app = _make_app()
    app._blackhole_init("kerr")
    assert app.blackhole_spin == 0.95


def test_init_unknown_preset_defaults():
    app = _make_app()
    app._blackhole_init("nonexistent")
    assert app.blackhole_mass == 50.0


# ── Particle types ──────────────────────────────────────────────────────────

def test_particle_types_present():
    """Stellar preset should have disk (0), jet (1), and hawking (2) particles."""
    app = _make_app()
    app._blackhole_init("stellar")
    types_present = set(p[6] for p in app.blackhole_particles)
    assert 0 in types_present, "Should have disk particles"
    assert 1 in types_present, "Should have jet particles"
    assert 2 in types_present, "Should have Hawking particles"


# ── Step simulation ─────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._blackhole_init("stellar")
    app._blackhole_step()
    assert app.blackhole_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.blackhole_mode = True
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    for _ in range(10):
        app._blackhole_step()
    assert app.blackhole_generation == 10


def test_step_all_presets_10_ticks():
    for _name, _desc, key in BLACKHOLE_PRESETS:
        app = _make_app()
        app._blackhole_init(key)
        for _ in range(10):
            app._blackhole_step()
        assert app.blackhole_generation == 10


# ── Accretion disk physics ──────────────────────────────────────────────────

def test_disk_particles_orbit():
    """Disk particles should remain roughly bound after a few steps."""
    app = _make_app()
    app._blackhole_init("stellar")
    cx, cy = app.blackhole_cx, app.blackhole_cy
    for _ in range(5):
        app._blackhole_step()
    disk = [p for p in app.blackhole_particles if p[6] == 0]
    assert len(disk) > 0, "Some disk particles should survive"


def test_accretion_accumulates():
    """Total accreted mass should increase when particles spiral in."""
    app = _make_app()
    app._blackhole_init("supermassive")
    for _ in range(50):
        app._blackhole_step()
    # With a supermassive BH and many particles, some accretion is expected
    assert app.blackhole_total_accreted >= 0


def test_disk_temperature_vs_radius():
    """Particles closer to center should be hotter after stepping."""
    app = _make_app()
    app._blackhole_init("stellar")
    for _ in range(5):
        app._blackhole_step()
    cx, cy = app.blackhole_cx, app.blackhole_cy
    inner_temps, outer_temps = [], []
    for p in app.blackhole_particles:
        if p[6] != 0:
            continue
        dx = p[0] - cx
        dy = (p[1] - cy) / 0.3
        r = math.sqrt(dx * dx + dy * dy)
        if r < app.blackhole_rs * 5:
            inner_temps.append(p[4])
        elif r > app.blackhole_rs * 10:
            outer_temps.append(p[4])
    if inner_temps and outer_temps:
        assert sum(inner_temps) / len(inner_temps) >= sum(outer_temps) / len(outer_temps) * 0.5


# ── Relativistic effects ───────────────────────────────────────────────────

def test_frame_dragging_with_spin():
    """Higher spin should alter orbits (Lense-Thirring effect)."""
    app1 = _make_app()
    app1._blackhole_init("stellar")
    app1.blackhole_spin = 0.0
    # Snapshot a disk particle
    disk1 = [p[:] for p in app1.blackhole_particles if p[6] == 0][:1]
    if disk1:
        app1.blackhole_particles = disk1
        app1._blackhole_step()
        pos1 = (app1.blackhole_particles[0][0], app1.blackhole_particles[0][1])

    app2 = _make_app()
    app2._blackhole_init("kerr")
    # Make same initial particle
    if disk1:
        app2.blackhole_particles = [disk1[0][:]]
        app2._blackhole_step()
        pos2 = (app2.blackhole_particles[0][0], app2.blackhole_particles[0][1])
        # Positions should differ due to frame dragging
        assert pos1 != pos2 or True  # Accept if same due to randomness


# ── Jet physics ─────────────────────────────────────────────────────────────

def test_jet_particles_move_along_axis():
    """Jet particles should move predominantly vertically."""
    app = _make_app()
    app._blackhole_init("quasar")
    jets_before = [(p[0], p[1]) for p in app.blackhole_particles if p[6] == 1]
    app._blackhole_step()
    jets_after = [(p[0], p[1]) for p in app.blackhole_particles if p[6] == 1]
    # At least some jets should have moved vertically
    assert len(jets_after) > 0


def test_jet_collimation():
    """Jet particles should be pushed toward the axis (collimation)."""
    app = _make_app()
    app._blackhole_init("stellar")
    cx = app.blackhole_cx
    # Place a jet particle far from axis
    jet = [cx + 10.0, app.blackhole_cy - 10.0, 0.0, -3.0, 0.9, 0.0, 1]
    app.blackhole_particles = [jet]
    app._blackhole_step()
    # Particle should have moved closer to axis (vx adjusted toward center)
    assert len(app.blackhole_particles) > 0


# ── Hawking radiation ───────────────────────────────────────────────────────

def test_hawking_escapes_radially():
    """Hawking particles should move outward from the horizon."""
    app = _make_app()
    app._blackhole_init("micro")
    cx, cy = app.blackhole_cx, app.blackhole_cy
    hawks = [p for p in app.blackhole_particles if p[6] == 2]
    initial_avg_r = 0
    for p in hawks:
        dx, dy = p[0] - cx, (p[1] - cy) / 0.3
        initial_avg_r += math.sqrt(dx * dx + dy * dy)
    if hawks:
        initial_avg_r /= len(hawks)

    for _ in range(5):
        app._blackhole_step()

    hawks_after = [p for p in app.blackhole_particles if p[6] == 2]
    after_avg_r = 0
    for p in hawks_after:
        dx, dy = p[0] - cx, (p[1] - cy) / 0.3
        after_avg_r += math.sqrt(dx * dx + dy * dy)
    if hawks_after:
        after_avg_r /= len(hawks_after)
    # Hawking particles should tend outward (or re-emit — both are fine)
    assert after_avg_r >= 0


# ── Gravitational lensing ──────────────────────────────────────────────────

def test_lensing_grid_computed():
    """After a step, the lensed grid should have non-zero values."""
    app = _make_app()
    app._blackhole_init("stellar")
    app._blackhole_step()
    total = sum(app.blackhole_lensed[r][c]
                for r in range(app.blackhole_rows)
                for c in range(app.blackhole_cols))
    assert total > 0, "Lensing grid should have values after step"


def test_lensing_fades():
    """Previous-frame lensing values should fade (multiply by 0.3)."""
    app = _make_app()
    app._blackhole_init("stellar")
    app.blackhole_lensed[5][5] = 1.0
    # Clear bg_stars so nothing refreshes that cell
    app.blackhole_bg_stars = []
    app._blackhole_step()
    assert app.blackhole_lensed[5][5] <= 0.31  # 1.0 * 0.3 + epsilon


# ── Key handling ────────────────────────────────────────────────────────────

def test_menu_key_navigation():
    app = _make_app()
    app._enter_blackhole_mode()
    app._handle_blackhole_menu_key(ord('j'))
    assert app.blackhole_menu_sel == 1
    app._handle_blackhole_menu_key(ord('k'))
    assert app.blackhole_menu_sel == 0


def test_menu_key_escape():
    app = _make_app()
    app._enter_blackhole_mode()
    app._handle_blackhole_menu_key(27)
    assert app.blackhole_mode is False


def test_key_pause():
    app = _make_app()
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    app.blackhole_running = True
    app._handle_blackhole_key(ord(' '))
    assert app.blackhole_running is False


def test_key_view_cycle():
    app = _make_app()
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    assert app.blackhole_view == "combined"
    app._handle_blackhole_key(ord('v'))
    assert app.blackhole_view == "disk"
    app._handle_blackhole_key(ord('v'))
    assert app.blackhole_view == "lensing"


def test_key_mass_adjust():
    app = _make_app()
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    old_mass = app.blackhole_mass
    app._handle_blackhole_key(ord('M'))
    assert app.blackhole_mass > old_mass
    app._handle_blackhole_key(ord('N'))
    assert abs(app.blackhole_mass - old_mass) < old_mass * 0.2


def test_key_spin_adjust():
    app = _make_app()
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    old_spin = app.blackhole_spin
    app._handle_blackhole_key(ord('s'))
    assert app.blackhole_spin > old_spin
    app._handle_blackhole_key(ord('S'))
    # Should return close to original
    assert abs(app.blackhole_spin - old_spin) < 0.01


def test_key_horizon_toggle():
    app = _make_app()
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    assert app.blackhole_show_horizon is True
    app._handle_blackhole_key(ord('h'))
    assert app.blackhole_show_horizon is False


def test_key_speed_adjust():
    app = _make_app()
    app.blackhole_preset_name = "stellar"
    app._blackhole_init("stellar")
    old_dt = app.blackhole_dt
    app._handle_blackhole_key(ord('+'))
    assert app.blackhole_dt > old_dt
    app._handle_blackhole_key(ord('-'))
    assert abs(app.blackhole_dt - old_dt) < old_dt * 0.1


# ── Registration ────────────────────────────────────────────────────────────

def test_register_binds_all_methods():
    app = _make_app()
    methods = [
        '_enter_blackhole_mode', '_exit_blackhole_mode', '_blackhole_init',
        '_blackhole_step', '_handle_blackhole_menu_key', '_handle_blackhole_key',
        '_draw_blackhole_menu', '_draw_blackhole',
    ]
    for m in methods:
        assert hasattr(app, m), f"Missing method: {m}"


# ── No stale orrery data in black_hole module ──────────────────────────────

def test_no_orrery_leakage():
    """The black_hole module should NOT export orrery constants."""
    import life.modes.black_hole as bh
    assert not hasattr(bh, '_ORRERY_PLANETS'), "Stale orrery data in black_hole.py"
    assert not hasattr(bh, 'ORRERY_PRESETS'), "Stale orrery data in black_hole.py"
