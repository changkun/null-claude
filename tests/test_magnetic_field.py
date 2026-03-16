"""Tests for life.modes.magnetic_field — Magnetic Field Lines mode."""
import math
import curses
from tests.conftest import make_mock_app
from life.modes.magnetic_field import register


def _make_app():
    app = make_mock_app()
    app.magfield_mode = False
    app.magfield_menu = False
    app.magfield_menu_sel = 0
    app.magfield_running = False
    app.magfield_generation = 0
    app.magfield_preset_name = ""
    app.magfield_rows = 0
    app.magfield_cols = 0
    app.magfield_steps_per_frame = 3
    app.magfield_dt = 0.02
    app.magfield_particles = []
    app.magfield_trails = []
    app.magfield_max_trail = 300
    app.magfield_Bz = 1.0
    app.magfield_Ex = 0.0
    app.magfield_Ey = 0.0
    app.magfield_field_type = 0
    app.magfield_show_field = True
    app.magfield_num_particles = 12
    app.magfield_viz_mode = 0
    type(app).MAGFIELD_PRESETS = [
        ("Cyclotron Orbits", "Circular orbits in uniform magnetic field", "cyclotron"),
        ("E x B Drift", "Crossed electric and magnetic fields", "exb"),
        ("Magnetic Bottle", "Mirror confinement with converging field lines", "bottle"),
        ("Dipole Field", "Planetary magnetosphere-like dipole", "dipole"),
        ("Quadrupole", "Linear focusing quadrupole field", "quadrupole"),
        ("Mixed Charges", "Positive and negative charges together", "mixed"),
        ("Magnetic Shear", "Spatially varying magnetic field", "shear"),
        ("Hall Effect", "Drift in crossed E and B fields", "hall"),
    ]
    register(type(app))
    return app


# --- Lifecycle ---

def test_enter():
    app = _make_app()
    app._enter_magfield_mode()
    assert app.magfield_menu is True
    assert app.magfield_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._magfield_init(0)
    app._exit_magfield_mode()
    assert app.magfield_mode is False
    assert app.magfield_menu is False
    assert app.magfield_running is False
    assert app.magfield_particles == []
    assert app.magfield_trails == []


# --- Initialization tests for each preset ---

def test_init_all_presets():
    """Each preset initializes without error and creates particles."""
    app = _make_app()
    for idx in range(8):
        app._magfield_init(idx)
        assert app.magfield_mode is True
        assert len(app.magfield_particles) > 0
        assert len(app.magfield_trails) == len(app.magfield_particles)
        # Each particle has [x, y, vx, vy, charge, mass]
        for p in app.magfield_particles:
            assert len(p) == 6
            assert p[5] > 0  # mass > 0


def test_init_cyclotron():
    app = _make_app()
    app._magfield_init(0)
    assert app.magfield_field_type == 0  # uniform
    assert app.magfield_Bz == 1.5
    assert len(app.magfield_particles) == 10


def test_init_exb():
    app = _make_app()
    app._magfield_init(1)
    assert app.magfield_Ey == -1.5
    assert len(app.magfield_particles) == 8


def test_init_bottle():
    app = _make_app()
    app._magfield_init(2)
    assert app.magfield_field_type == 2
    assert len(app.magfield_particles) == 12


def test_init_dipole():
    app = _make_app()
    app._magfield_init(3)
    assert app.magfield_field_type == 1
    assert len(app.magfield_particles) == 10


def test_init_mixed_charges():
    app = _make_app()
    app._magfield_init(5)  # mixed
    positive = sum(1 for p in app.magfield_particles if p[4] > 0)
    negative = sum(1 for p in app.magfield_particles if p[4] < 0)
    assert positive > 0
    assert negative > 0


# --- Field calculation tests ---

def test_uniform_field():
    """Uniform field should return constant Bz."""
    app = _make_app()
    app._magfield_init(0)  # cyclotron (uniform)
    cx = app.magfield_cols / 2.0
    cy = app.magfield_rows / 2.0
    Bz1, _, _ = app._magfield_get_field(0.0, 0.0)
    Bz2, _, _ = app._magfield_get_field(cx, cy)
    Bz3, _, _ = app._magfield_get_field(float(app.magfield_cols - 1), float(app.magfield_rows - 1))
    assert abs(Bz1 - Bz2) < 1e-10
    assert abs(Bz2 - Bz3) < 1e-10


def test_dipole_field_stronger_near_center():
    """Dipole field B ~ 1/r^3, so field should be stronger near center."""
    app = _make_app()
    app._magfield_init(3)  # dipole
    cx = app.magfield_cols / 2.0
    cy = app.magfield_rows / 2.0
    Bz_close, _, _ = app._magfield_get_field(cx + 2, cy + 2)
    Bz_far, _, _ = app._magfield_get_field(cx + 20, cy + 20)
    assert abs(Bz_close) > abs(Bz_far)


def test_bottle_field_stronger_at_edges():
    """Magnetic bottle: B should be stronger at top/bottom edges."""
    app = _make_app()
    app._magfield_init(2)  # bottle
    cx = app.magfield_cols / 2.0
    cy = app.magfield_rows / 2.0
    Bz_center, _, _ = app._magfield_get_field(cx, cy)
    Bz_edge, _, _ = app._magfield_get_field(cx, 1.0)  # near top
    assert abs(Bz_edge) > abs(Bz_center)


def test_quadrupole_field_grows_with_distance():
    """Quadrupole: B should increase with distance from center."""
    app = _make_app()
    app._magfield_init(4)  # quadrupole
    cx = app.magfield_cols / 2.0
    cy = app.magfield_rows / 2.0
    Bz_close, _, _ = app._magfield_get_field(cx + 1, cy)
    Bz_far, _, _ = app._magfield_get_field(cx + 15, cy)
    assert abs(Bz_far) > abs(Bz_close)


def test_shear_field_varies_with_x():
    """Magnetic shear: B should vary linearly with x."""
    app = _make_app()
    app._magfield_init(6)  # shear
    cy = app.magfield_rows / 2.0
    Bz_left, _, _ = app._magfield_get_field(5.0, cy)
    Bz_right, _, _ = app._magfield_get_field(float(app.magfield_cols - 5), cy)
    assert Bz_right > Bz_left


# --- Boris integrator tests ---

def test_step_increments_generation():
    app = _make_app()
    app._magfield_init(0)
    app._magfield_step()
    assert app.magfield_generation == 1


def test_step_no_crash_all_presets():
    """Run 50 steps on each preset without error."""
    app = _make_app()
    for idx in range(8):
        app._magfield_init(idx)
        for _ in range(50):
            app._magfield_step()
        assert app.magfield_generation == 50


def test_particles_stay_in_bounds():
    """After many steps, particles should remain within grid bounds."""
    app = _make_app()
    app._magfield_init(0)
    for _ in range(200):
        app._magfield_step()
    for p in app.magfield_particles:
        assert 0 <= p[0] < app.magfield_cols, f"x={p[0]} out of bounds"
        assert 0 <= p[1] < app.magfield_rows, f"y={p[1]} out of bounds"


def test_trails_recorded():
    """Trails should be recorded for each particle."""
    app = _make_app()
    app._magfield_init(0)
    for _ in range(10):
        app._magfield_step()
    for trail in app.magfield_trails:
        assert len(trail) == 10


def test_trail_max_length():
    """Trails should be truncated to max_trail."""
    app = _make_app()
    app._magfield_init(0)
    app.magfield_max_trail = 20
    for _ in range(50):
        app._magfield_step()
    for trail in app.magfield_trails:
        assert len(trail) <= 20


def test_cyclotron_orbit_radius():
    """In uniform B, a single charged particle should orbit with r = mv/(qB)."""
    app = _make_app()
    app.magfield_rows = 100
    app.magfield_cols = 100
    app.magfield_Bz = 2.0
    app.magfield_Ex = 0.0
    app.magfield_Ey = 0.0
    app.magfield_field_type = 0
    app.magfield_preset_name = "test"
    app.magfield_dt = 0.01
    app.magfield_max_trail = 5000
    cx, cy = 50.0, 50.0
    speed = 5.0
    # Single particle: q=1, m=1, v=speed in x
    app.magfield_particles = [[cx, cy, speed, 0.0, 1.0, 1.0]]
    app.magfield_trails = [[]]
    # Expected radius = m*v/(q*B) = 1*5/(1*2) = 2.5
    expected_r = speed / 2.0
    # Run for a full orbit period T = 2*pi*m/(q*B) = pi
    period = 2 * math.pi / 2.0  # = pi
    n_steps = int(period / app.magfield_dt) + 1
    for _ in range(n_steps):
        app._magfield_step()
    # Check the particle returned close to start
    p = app.magfield_particles[0]
    dist = math.sqrt((p[0] - cx)**2 + (p[1] - cy)**2)
    # With dt=0.01 Boris integrator should be accurate
    assert dist < 1.0, f"Particle didn't return to start: dist={dist}"


# --- Key handling tests ---

def test_menu_key_navigation():
    app = _make_app()
    app._enter_magfield_mode()
    app._handle_magfield_menu_key(curses.KEY_DOWN)
    assert app.magfield_menu_sel == 1
    app._handle_magfield_menu_key(curses.KEY_UP)
    assert app.magfield_menu_sel == 0


def test_menu_key_select():
    app = _make_app()
    app._enter_magfield_mode()
    app._handle_magfield_menu_key(10)  # Enter
    assert app.magfield_mode is True


def test_menu_key_cancel():
    app = _make_app()
    app._enter_magfield_mode()
    app._handle_magfield_menu_key(ord("q"))
    assert app.magfield_menu is False


def test_sim_key_space():
    app = _make_app()
    app._magfield_init(0)
    app._handle_magfield_key(ord(" "))
    assert app.magfield_running is True
    app._handle_magfield_key(ord(" "))
    assert app.magfield_running is False


def test_sim_key_bfield():
    app = _make_app()
    app._magfield_init(0)
    initial_b = app.magfield_Bz
    app._handle_magfield_key(ord("b"))
    assert app.magfield_Bz == initial_b + 0.2
    app._handle_magfield_key(ord("B"))
    assert abs(app.magfield_Bz - initial_b) < 1e-10


def test_sim_key_viz_cycle():
    app = _make_app()
    app._magfield_init(0)
    assert app.magfield_viz_mode == 0
    app._handle_magfield_key(ord("v"))
    assert app.magfield_viz_mode == 1
    app._handle_magfield_key(ord("v"))
    assert app.magfield_viz_mode == 2
    app._handle_magfield_key(ord("v"))
    assert app.magfield_viz_mode == 0


def test_sim_key_field_toggle():
    app = _make_app()
    app._magfield_init(0)
    assert app.magfield_show_field is True
    app._handle_magfield_key(ord("f"))
    assert app.magfield_show_field is False
    app._handle_magfield_key(ord("f"))
    assert app.magfield_show_field is True


def test_sim_key_clear_trails():
    app = _make_app()
    app._magfield_init(0)
    for _ in range(10):
        app._magfield_step()
    assert any(len(t) > 0 for t in app.magfield_trails)
    app._handle_magfield_key(ord("c"))
    assert all(len(t) == 0 for t in app.magfield_trails)


def test_sim_key_add_particle():
    app = _make_app()
    app._magfield_init(0)
    n_before = len(app.magfield_particles)
    app._handle_magfield_key(ord("p"))
    assert len(app.magfield_particles) == n_before + 1
    assert len(app.magfield_trails) == n_before + 1


def test_sim_key_dt():
    app = _make_app()
    app._magfield_init(0)
    dt0 = app.magfield_dt
    app._handle_magfield_key(ord("+"))
    assert app.magfield_dt > dt0
    app._handle_magfield_key(ord("-"))
    assert abs(app.magfield_dt - dt0) < 0.001


def test_sim_key_trail_length():
    app = _make_app()
    app._magfield_init(0)
    mt0 = app.magfield_max_trail
    app._handle_magfield_key(ord("]"))
    assert app.magfield_max_trail == mt0 + 50
    app._handle_magfield_key(ord("["))
    assert app.magfield_max_trail == mt0


def test_sim_key_quit():
    app = _make_app()
    app._magfield_init(0)
    app._handle_magfield_key(ord("q"))
    assert app.magfield_mode is False


def test_sim_key_return_to_menu():
    app = _make_app()
    app._magfield_init(0)
    app._handle_magfield_key(ord("R"))
    assert app.magfield_mode is False
    assert app.magfield_menu is True


def test_sim_key_reset():
    app = _make_app()
    app._magfield_init(0)
    for _ in range(20):
        app._magfield_step()
    assert app.magfield_generation > 0
    app._handle_magfield_key(ord("r"))
    assert app.magfield_generation == 0


def test_sim_key_efield_toggle():
    app = _make_app()
    app._magfield_init(1)  # ExB has nonzero E field
    assert abs(app.magfield_Ey) > 0.01
    app._handle_magfield_key(ord("e"))
    assert abs(app.magfield_Ex) + abs(app.magfield_Ey) < 0.02
    app._handle_magfield_key(ord("e"))
    assert abs(app.magfield_Ex) + abs(app.magfield_Ey) > 0.01


def test_noop_key():
    app = _make_app()
    app._magfield_init(0)
    result = app._handle_magfield_key(-1)
    assert result is True


def test_steps_per_frame():
    app = _make_app()
    app._magfield_init(0)
    spf0 = app.magfield_steps_per_frame
    app._handle_magfield_key(ord(">"))
    assert app.magfield_steps_per_frame == spf0 + 1
    app._handle_magfield_key(ord("<"))
    assert app.magfield_steps_per_frame == spf0


def test_step_via_n_key():
    app = _make_app()
    app._magfield_init(0)
    gen_before = app.magfield_generation
    app._handle_magfield_key(ord("n"))
    assert app.magfield_generation == gen_before + app.magfield_steps_per_frame
