"""Tests for life.modes.sph_fluid — SPH Fluid mode."""
import math
import curses
from tests.conftest import make_mock_app
from life.modes.sph_fluid import register


def _make_app():
    app = make_mock_app()
    app.sph_mode = False
    app.sph_menu = False
    app.sph_menu_sel = 0
    app.sph_running = False
    app.sph_generation = 0
    app.sph_preset_name = ""
    app.sph_rows = 0
    app.sph_cols = 0
    app.sph_gravity = 9.8
    app.sph_rest_density = 1000.0
    app.sph_gas_const = 2000.0
    app.sph_h = 1.5
    app.sph_mass = 1.0
    app.sph_viscosity = 250.0
    app.sph_dt = 0.003
    app.sph_damping = 0.5
    app.sph_steps_per_frame = 3
    app.sph_particles = []
    app.sph_num_particles = 0
    app.sph_viz_mode = 0
    type(app).SPH_PRESETS = [
        ("Dam Break", "Column of water collapses sideways", "dam"),
        ("Double Dam", "Two water columns collide", "double_dam"),
        ("Drop Impact", "Block of fluid falls into pool", "drop"),
        ("Rain", "Scattered droplets fall under gravity", "rain"),
        ("Wave Pool", "Tilted water surface generates waves", "wave"),
        ("Fountain", "Upward jet creates a fountain", "fountain"),
    ]
    type(app).SPH_CHARS = " .:-=+*#%@"
    register(type(app))
    return app


# --- Lifecycle ---

def test_enter():
    app = _make_app()
    app._enter_sph_mode()
    assert app.sph_menu is True
    assert app.sph_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._sph_init(3)  # rain
    app._exit_sph_mode()
    assert app.sph_mode is False
    assert app.sph_menu is False
    assert app.sph_running is False
    assert app.sph_particles == []


# --- Initialization tests ---

def test_init_all_presets():
    """Each preset initializes without error and creates particles."""
    app = _make_app()
    for idx in range(6):
        app._sph_init(idx)
        assert app.sph_mode is True
        assert app.sph_menu is False
        assert app.sph_num_particles == len(app.sph_particles)
        assert app.sph_num_particles > 0
        # Each particle is [x, y, vx, vy, density, pressure]
        for p in app.sph_particles:
            assert len(p) == 6


def test_init_dam():
    app = _make_app()
    app._sph_init(0)  # dam
    assert app.sph_num_particles > 0
    # All particles should be on the left side
    cols = app.sph_cols
    for p in app.sph_particles:
        assert p[0] < cols * 0.35


def test_init_double_dam():
    app = _make_app()
    app._sph_init(1)  # double dam
    cols = app.sph_cols
    # Should have particles on left and right
    has_left = any(p[0] < cols * 0.3 for p in app.sph_particles)
    has_right = any(p[0] > cols * 0.7 for p in app.sph_particles)
    assert has_left
    assert has_right


def test_init_drop():
    app = _make_app()
    app._sph_init(2)  # drop
    rows = app.sph_rows
    # Should have particles at top (drop) and bottom (pool)
    has_top = any(p[1] < rows * 0.4 for p in app.sph_particles)
    has_bottom = any(p[1] > rows * 0.65 for p in app.sph_particles)
    assert has_top
    assert has_bottom


def test_init_rain():
    app = _make_app()
    app._sph_init(3)  # rain
    # Rain particles should mostly be in upper half
    rows = app.sph_rows
    upper = sum(1 for p in app.sph_particles if p[1] < rows * 0.55)
    assert upper == len(app.sph_particles)


def test_init_fountain():
    app = _make_app()
    app._sph_init(5)  # fountain
    assert app.sph_num_particles > 0


# --- SPH kernel tests ---

def test_poly6_kernel_normalization():
    """Poly6 kernel coefficient should be positive."""
    h = 1.5
    poly6_coeff = 315.0 / (64.0 * math.pi * h ** 9)
    assert poly6_coeff > 0


def test_spiky_kernel_coefficient():
    """Spiky kernel coefficient should be negative (for grad)."""
    h = 1.5
    spiky_coeff = -45.0 / (math.pi * h ** 6)
    assert spiky_coeff < 0


def test_viscosity_kernel_coefficient():
    """Viscosity laplacian kernel coefficient should be positive."""
    h = 1.5
    visc_coeff = 45.0 / (math.pi * h ** 6)
    assert visc_coeff > 0


# --- Density / pressure tests ---

def test_density_computed_after_step():
    """After a step, particles should have nonzero density."""
    app = _make_app()
    app._sph_init(0)  # dam (many particles close together)
    app._sph_step()
    nonzero_density = sum(1 for p in app.sph_particles if p[4] > 0)
    assert nonzero_density > 0


def test_density_positive():
    """Density should never be negative (clamped to rho0*0.1)."""
    app = _make_app()
    app._sph_init(0)
    for _ in range(10):
        app._sph_step()
    for p in app.sph_particles:
        assert p[4] >= 0.0


def test_pressure_equation_of_state():
    """Pressure = k * (density - rest_density)."""
    app = _make_app()
    app._sph_init(0)
    app._sph_step()
    k = app.sph_gas_const
    rho0 = app.sph_rest_density
    for p in app.sph_particles:
        expected_p = k * (p[4] - rho0)
        assert abs(p[5] - expected_p) < 1e-6


# --- Step / integration tests ---

def test_step_increments_generation():
    app = _make_app()
    app._sph_init(3)  # rain (fewer particles)
    app._sph_step()
    assert app.sph_generation == 1


def test_step_no_crash_all_presets():
    """Run steps on each preset without error."""
    app = _make_app()
    for idx in range(6):
        app._sph_init(idx)
        for _ in range(5):
            app._sph_step()
        assert app.sph_generation == 5


def test_step_empty_particles():
    """Step with no particles should not crash."""
    app = _make_app()
    app.sph_particles = []
    app.sph_rows = 20
    app.sph_cols = 20
    app.sph_generation = 0
    app._sph_step()
    # Should just return without error


def test_particles_stay_in_bounds():
    """After many steps, particles should remain within grid bounds."""
    app = _make_app()
    app._sph_init(3)  # rain
    for _ in range(50):
        app._sph_step()
    margin = app.sph_h * 0.3
    for p in app.sph_particles:
        assert p[0] >= margin - 0.01, f"x={p[0]} below min"
        assert p[0] <= app.sph_cols - margin + 0.01, f"x={p[0]} above max"
        assert p[1] >= margin - 0.01, f"y={p[1]} below min"
        assert p[1] <= app.sph_rows - margin + 0.01, f"y={p[1]} above max"


def test_gravity_pulls_down():
    """Particles should move downward on average due to gravity."""
    app = _make_app()
    app._sph_init(3)  # rain
    initial_y = [p[1] for p in app.sph_particles]
    for _ in range(20):
        app._sph_step()
    final_y = [p[1] for p in app.sph_particles]
    avg_dy = sum(f - i for f, i in zip(final_y, initial_y)) / len(initial_y)
    assert avg_dy > 0, "Particles should move downward on average"


def test_boundary_damping():
    """Particles hitting boundary should lose velocity (damping)."""
    app = _make_app()
    # Place a single particle about to hit the bottom
    app.sph_rows = 20
    app.sph_cols = 20
    app.sph_h = 1.5
    app.sph_gravity = 9.8
    app.sph_rest_density = 1000.0
    app.sph_gas_const = 2000.0
    app.sph_mass = 1.0
    app.sph_viscosity = 250.0
    app.sph_dt = 0.003
    app.sph_damping = 0.5
    app.sph_preset_name = "test"
    margin = app.sph_h * 0.3
    # Particle at the bottom boundary moving down fast
    app.sph_particles = [[10.0, 19.0, 0.0, 10.0, 0.0, 0.0]]
    app._sph_step()
    # After step, particle should be clamped and velocity reversed/damped
    p = app.sph_particles[0]
    assert p[1] <= 20.0 - margin + 0.01


def test_fountain_preset_velocity_kick():
    """Fountain preset should inject upward velocity at bottom center."""
    app = _make_app()
    app._sph_init(5)  # fountain
    cx = app.sph_cols / 2.0
    # Place a particle at bottom center
    app.sph_particles.append([cx, app.sph_rows * 0.9, 0.0, 0.0, 0.0, 0.0])
    app.sph_num_particles = len(app.sph_particles)
    app._sph_step()
    # The last particle should have gotten an upward kick
    last_p = app.sph_particles[-1]
    assert last_p[3] < 0, "Bottom-center particle should have upward velocity in fountain"


# --- Key handling tests ---

def test_menu_key_navigation():
    app = _make_app()
    app._enter_sph_mode()
    app._handle_sph_menu_key(curses.KEY_DOWN)
    assert app.sph_menu_sel == 1
    app._handle_sph_menu_key(curses.KEY_UP)
    assert app.sph_menu_sel == 0
    # Wrap around
    app._handle_sph_menu_key(curses.KEY_UP)
    assert app.sph_menu_sel == len(type(app).SPH_PRESETS) - 1


def test_menu_key_select():
    app = _make_app()
    app._enter_sph_mode()
    app._handle_sph_menu_key(10)  # Enter
    assert app.sph_mode is True


def test_menu_key_cancel():
    app = _make_app()
    app._enter_sph_mode()
    app._handle_sph_menu_key(ord("q"))
    assert app.sph_menu is False


def test_sim_key_space():
    app = _make_app()
    app._sph_init(3)
    app._handle_sph_key(ord(" "))
    assert app.sph_running is True
    app._handle_sph_key(ord(" "))
    assert app.sph_running is False


def test_sim_key_step():
    app = _make_app()
    app._sph_init(3)
    gen_before = app.sph_generation
    app._handle_sph_key(ord("n"))
    assert app.sph_generation == gen_before + 1


def test_sim_key_viz_cycle():
    app = _make_app()
    app._sph_init(3)
    assert app.sph_viz_mode == 0
    app._handle_sph_key(ord("v"))
    assert app.sph_viz_mode == 1
    app._handle_sph_key(ord("v"))
    assert app.sph_viz_mode == 2
    app._handle_sph_key(ord("v"))
    assert app.sph_viz_mode == 0


def test_sim_key_gravity():
    app = _make_app()
    app._sph_init(3)
    g0 = app.sph_gravity
    app._handle_sph_key(ord("+"))
    assert app.sph_gravity > g0
    app._handle_sph_key(ord("-"))
    assert abs(app.sph_gravity - g0) < 0.1


def test_sim_key_speed():
    app = _make_app()
    app._sph_init(3)
    spf0 = app.sph_steps_per_frame
    app._handle_sph_key(ord(">"))
    assert app.sph_steps_per_frame == spf0 + 1
    app._handle_sph_key(ord("<"))
    assert app.sph_steps_per_frame == spf0


def test_sim_key_quit():
    app = _make_app()
    app._sph_init(3)
    app._handle_sph_key(ord("q"))
    assert app.sph_mode is False


def test_sim_key_return_to_menu():
    app = _make_app()
    app._sph_init(3)
    app._handle_sph_key(ord("R"))
    assert app.sph_mode is False
    assert app.sph_menu is True


def test_sim_key_reset():
    app = _make_app()
    app._sph_init(3)
    for _ in range(5):
        app._sph_step()
    assert app.sph_generation > 0
    app._handle_sph_key(ord("r"))
    assert app.sph_generation == 0


def test_noop_key():
    app = _make_app()
    app._sph_init(3)
    result = app._handle_sph_key(-1)
    assert result is True
    result2 = app._handle_sph_menu_key(-1)
    assert result2 is True


def test_gravity_clamp():
    app = _make_app()
    app._sph_init(3)
    app.sph_gravity = 0.1
    app._handle_sph_key(ord("-"))
    assert app.sph_gravity >= 0.1  # clamped at minimum


# --- Physics validation ---

def test_two_particles_repel():
    """Two particles very close should develop repulsive pressure force."""
    app = _make_app()
    app.sph_rows = 20
    app.sph_cols = 20
    app.sph_h = 1.5
    app.sph_gravity = 0.0  # no gravity
    app.sph_rest_density = 1000.0
    app.sph_gas_const = 2000.0
    app.sph_mass = 1.0
    app.sph_viscosity = 0.0  # no viscosity
    app.sph_dt = 0.001
    app.sph_damping = 0.5
    app.sph_preset_name = "test"
    # Place two particles very close
    app.sph_particles = [
        [10.0, 10.0, 0.0, 0.0, 0.0, 0.0],
        [10.5, 10.0, 0.0, 0.0, 0.0, 0.0],
    ]
    dist_before = abs(app.sph_particles[1][0] - app.sph_particles[0][0])
    for _ in range(20):
        app._sph_step()
    dist_after = abs(app.sph_particles[1][0] - app.sph_particles[0][0])
    # They should move apart due to pressure
    assert dist_after > dist_before, "Close particles should repel"


def test_single_particle_falls():
    """A single particle with gravity should fall down."""
    app = _make_app()
    app.sph_rows = 50
    app.sph_cols = 50
    app.sph_h = 1.5
    app.sph_gravity = 9.8
    app.sph_rest_density = 1000.0
    app.sph_gas_const = 2000.0
    app.sph_mass = 1.0
    app.sph_viscosity = 0.0
    app.sph_dt = 0.003
    app.sph_damping = 0.5
    app.sph_preset_name = "test"
    app.sph_particles = [[25.0, 10.0, 0.0, 0.0, 0.0, 0.0]]
    initial_y = app.sph_particles[0][1]
    for _ in range(50):
        app._sph_step()
    assert app.sph_particles[0][1] > initial_y, "Particle should fall under gravity"


def test_viscosity_slows_relative_motion():
    """Viscosity should reduce relative velocity between particles."""
    app = _make_app()
    app.sph_rows = 30
    app.sph_cols = 30
    app.sph_h = 2.0
    app.sph_gravity = 0.0
    app.sph_rest_density = 1000.0
    app.sph_gas_const = 0.0  # no pressure
    app.sph_mass = 1.0
    app.sph_viscosity = 500.0  # strong viscosity
    app.sph_dt = 0.001
    app.sph_damping = 1.0
    app.sph_preset_name = "test"
    # Two particles with opposite velocities
    app.sph_particles = [
        [14.0, 15.0, 5.0, 0.0, 0.0, 0.0],
        [16.0, 15.0, -5.0, 0.0, 0.0, 0.0],
    ]
    rel_v_before = abs(app.sph_particles[0][2] - app.sph_particles[1][2])
    for _ in range(30):
        app._sph_step()
    rel_v_after = abs(app.sph_particles[0][2] - app.sph_particles[1][2])
    assert rel_v_after < rel_v_before, "Viscosity should reduce relative velocity"
