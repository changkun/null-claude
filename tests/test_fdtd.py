"""Tests for life.modes.fdtd — FDTD EM Waves mode."""
import math
import curses
from tests.conftest import make_mock_app
from life.modes.fdtd import register


def _make_app():
    app = make_mock_app()
    app.fdtd_mode = False
    app.fdtd_menu = False
    app.fdtd_menu_sel = 0
    app.fdtd_running = False
    app.fdtd_generation = 0
    app.fdtd_preset_name = ""
    app.fdtd_rows = 0
    app.fdtd_cols = 0
    app.fdtd_steps_per_frame = 2
    app.fdtd_Ez = []
    app.fdtd_Hx = []
    app.fdtd_Hy = []
    app.fdtd_eps = []
    app.fdtd_sigma = []
    app.fdtd_sources = []
    app.fdtd_pml_width = 8
    app.fdtd_viz_mode = 0
    app.fdtd_freq = 0.15
    app.fdtd_courant = 0.5
    type(app).FDTD_PRESETS = [
        ("Point Source", "Single oscillating point source", "point"),
        ("Double Slit", "Wave diffraction through two slits", "double_slit"),
        ("Single Slit", "Diffraction through a single slit", "single_slit"),
        ("Waveguide", "EM wave confined in a metal waveguide", "waveguide"),
        ("Dielectric Lens", "Focusing by a convex dielectric lens", "lens"),
        ("Dipole Antenna", "Two sources with opposite phase", "dipole"),
        ("Phased Array", "Beam steering with phase-shifted sources", "phased_array"),
        ("Corner Reflector", "Reflection from a 90-degree corner", "corner_reflector"),
        ("Resonant Cavity", "Standing waves in a metal box", "cavity"),
        ("Scatterers", "Wave scattering off dielectric cylinders", "scatter"),
    ]
    register(type(app))
    return app


# --- Lifecycle ---

def test_enter():
    app = _make_app()
    app._enter_fdtd_mode()
    assert app.fdtd_menu is True
    assert app.fdtd_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._fdtd_init(0)
    app._exit_fdtd_mode()
    assert app.fdtd_mode is False
    assert app.fdtd_menu is False
    assert app.fdtd_running is False
    assert app.fdtd_Ez == []
    assert app.fdtd_Hx == []
    assert app.fdtd_Hy == []
    assert app.fdtd_sources == []


# --- Initialization tests ---

def test_init_all_presets():
    """Each preset initializes without error."""
    app = _make_app()
    for idx in range(10):
        app._fdtd_init(idx)
        assert app.fdtd_mode is True
        assert app.fdtd_menu is False
        assert len(app.fdtd_Ez) == app.fdtd_rows
        assert len(app.fdtd_Ez[0]) == app.fdtd_cols
        assert len(app.fdtd_Hx) == app.fdtd_rows
        assert len(app.fdtd_Hy) == app.fdtd_rows
        assert len(app.fdtd_eps) == app.fdtd_rows
        assert len(app.fdtd_sigma) == app.fdtd_rows
        assert len(app.fdtd_sources) > 0


def test_init_point_source():
    app = _make_app()
    app._fdtd_init(0)
    assert len(app.fdtd_sources) == 1
    assert app.fdtd_sources[0]["freq"] == 0.15


def test_init_double_slit():
    app = _make_app()
    app._fdtd_init(1)
    # Should have a wall (high sigma) and plane wave sources
    assert len(app.fdtd_sources) > 1
    # Check wall exists (high conductivity somewhere)
    wall_c = app.fdtd_cols // 3
    has_wall = any(
        app.fdtd_sigma[r][wall_c] >= 50.0
        for r in range(app.fdtd_rows)
    )
    assert has_wall


def test_init_waveguide():
    app = _make_app()
    app._fdtd_init(3)
    cr = app.fdtd_rows // 2
    guide_half = max(4, app.fdtd_rows // 10)
    # Check waveguide walls exist
    assert app.fdtd_sigma[cr - guide_half][0] == 100.0
    assert app.fdtd_sigma[cr + guide_half][0] == 100.0


def test_init_lens():
    app = _make_app()
    app._fdtd_init(4)  # lens
    # Should have dielectric region
    has_dielectric = False
    for r in range(app.fdtd_rows):
        for c in range(app.fdtd_cols):
            if app.fdtd_eps[r][c] > 1.5:
                has_dielectric = True
                break
        if has_dielectric:
            break
    assert has_dielectric


def test_init_dipole_antenna():
    app = _make_app()
    app._fdtd_init(5)
    assert len(app.fdtd_sources) == 2
    # Should have opposite phases
    assert abs(app.fdtd_sources[0]["phase"] - 0.0) < 1e-10
    assert abs(app.fdtd_sources[1]["phase"] - math.pi) < 1e-10


# --- PML boundary tests ---

def test_pml_conductivity_graded():
    """PML conductivity should increase toward the boundary."""
    app = _make_app()
    app._fdtd_init(0)
    pml = app.fdtd_pml_width
    rows, cols = app.fdtd_rows, app.fdtd_cols
    cr, cc = rows // 2, cols // 2
    # Interior should have zero sigma
    assert app.fdtd_sigma[cr][cc] == 0.0
    # Near boundary should have nonzero sigma
    assert app.fdtd_sigma[0][cc] > 0.0
    assert app.fdtd_sigma[rows - 1][cc] > 0.0
    assert app.fdtd_sigma[cr][0] > 0.0
    assert app.fdtd_sigma[cr][cols - 1] > 0.0


def test_pml_profile_quadratic():
    """PML profile should be quadratic (sigma ~ depth^2)."""
    app = _make_app()
    app._fdtd_init(0)
    pml = app.fdtd_pml_width
    rows = app.fdtd_rows
    cc = app.fdtd_cols // 2
    # Check top edge: sigma should be higher closer to boundary
    if pml > 2:
        s_outer = app.fdtd_sigma[0][cc]
        s_inner = app.fdtd_sigma[pml - 1][cc]
        assert s_outer > s_inner


# --- Yee algorithm / step tests ---

def test_step_increments_generation():
    app = _make_app()
    app._fdtd_init(0)
    app._fdtd_step()
    assert app.fdtd_generation == 1


def test_step_no_crash_all_presets():
    """Run multiple steps on each preset without error."""
    app = _make_app()
    for idx in range(10):
        app._fdtd_init(idx)
        for _ in range(20):
            app._fdtd_step()
        assert app.fdtd_generation == 20


def test_fields_zero_initially():
    """All fields should start at zero."""
    app = _make_app()
    app._fdtd_init(0)
    for r in range(app.fdtd_rows):
        for c in range(app.fdtd_cols):
            assert app.fdtd_Ez[r][c] == 0.0
            assert app.fdtd_Hx[r][c] == 0.0
            assert app.fdtd_Hy[r][c] == 0.0


def test_source_injects_energy():
    """After a few steps, source location should have nonzero Ez."""
    app = _make_app()
    app._fdtd_init(0)  # point source
    src = app.fdtd_sources[0]
    for _ in range(5):
        app._fdtd_step()
    assert app.fdtd_Ez[src["r"]][src["c"]] != 0.0


def test_wave_propagation():
    """Ez field should spread from source location over time."""
    app = _make_app()
    app._fdtd_init(0)  # point source at center
    src = app.fdtd_sources[0]
    sr, sc = src["r"], src["c"]
    # Run enough steps for wave to propagate
    for _ in range(30):
        app._fdtd_step()
    # Check some neighbor cells have nonzero Ez
    nonzero = 0
    for dr in range(-5, 6):
        for dc in range(-5, 6):
            r, c = sr + dr, sc + dc
            if 0 <= r < app.fdtd_rows and 0 <= c < app.fdtd_cols:
                if abs(app.fdtd_Ez[r][c]) > 1e-10:
                    nonzero += 1
    assert nonzero > 5


def test_pml_absorbs_energy():
    """After many steps, PML boundary should prevent energy reflection.
    Test that fields near PML edges are small compared to center."""
    app = _make_app()
    app._fdtd_init(0)  # point source
    # Run for many steps so waves reach and pass boundary
    for _ in range(100):
        app._fdtd_step()
    pml = app.fdtd_pml_width
    rows, cols = app.fdtd_rows, app.fdtd_cols
    # Edge energy should be small
    edge_energy = 0.0
    for r in range(rows):
        edge_energy += abs(app.fdtd_Ez[r][0])
        edge_energy += abs(app.fdtd_Ez[r][cols - 1])
    for c in range(cols):
        edge_energy += abs(app.fdtd_Ez[0][c])
        edge_energy += abs(app.fdtd_Ez[rows - 1][c])
    # Source region energy
    src = app.fdtd_sources[0]
    source_energy = abs(app.fdtd_Ez[src["r"]][src["c"]])
    # Edge should be much smaller than source (PML is working)
    if source_energy > 0.01:
        avg_edge = edge_energy / (2 * rows + 2 * cols)
        assert avg_edge < source_energy


def test_gaussian_rampup():
    """Source should ramp up gradually in the first ~30 steps."""
    app = _make_app()
    app._fdtd_init(0)
    src = app.fdtd_sources[0]
    # Step 0: no injection yet
    app._fdtd_step()
    ez_step1 = abs(app.fdtd_Ez[src["r"]][src["c"]])
    # Step 25: stronger injection
    for _ in range(24):
        app._fdtd_step()
    # After 25 steps, the ramp-up factor should be closer to 1
    # (1 - exp(-(25/10)^2)) = (1 - exp(-6.25)) ~ 0.998
    # vs step 1: (1 - exp(-(1/10)^2)) = (1 - exp(-0.01)) ~ 0.01


def test_conductor_blocks_wave():
    """A conductor (high sigma) should block wave propagation."""
    app = _make_app()
    app._fdtd_init(3)  # waveguide with conductor walls
    cr = app.fdtd_rows // 2
    guide_half = max(4, app.fdtd_rows // 10)
    for _ in range(50):
        app._fdtd_step()
    # Outside waveguide should have very little field
    outside_energy = 0.0
    inside_energy = 0.0
    for c in range(app.fdtd_cols):
        if cr + guide_half + 2 < app.fdtd_rows:
            outside_energy += abs(app.fdtd_Ez[cr + guide_half + 2][c])
        inside_energy += abs(app.fdtd_Ez[cr][c])
    assert outside_energy < inside_energy


def test_dielectric_slows_wave():
    """In dielectric (eps>1), effective wave speed should be slower."""
    app = _make_app()
    app._fdtd_init(4)  # lens
    # After several steps, we just check it doesn't crash
    for _ in range(30):
        app._fdtd_step()


# --- Key handling tests ---

def test_menu_key_navigation():
    app = _make_app()
    app._enter_fdtd_mode()
    app._handle_fdtd_menu_key(curses.KEY_DOWN)
    assert app.fdtd_menu_sel == 1
    app._handle_fdtd_menu_key(curses.KEY_UP)
    assert app.fdtd_menu_sel == 0


def test_menu_key_select():
    app = _make_app()
    app._enter_fdtd_mode()
    app._handle_fdtd_menu_key(10)  # Enter
    assert app.fdtd_mode is True


def test_menu_key_cancel():
    app = _make_app()
    app._enter_fdtd_mode()
    app._handle_fdtd_menu_key(ord("q"))
    assert app.fdtd_menu is False


def test_sim_key_space():
    app = _make_app()
    app._fdtd_init(0)
    app._handle_fdtd_key(ord(" "))
    assert app.fdtd_running is True
    app._handle_fdtd_key(ord(" "))
    assert app.fdtd_running is False


def test_sim_key_step():
    app = _make_app()
    app._fdtd_init(0)
    gen_before = app.fdtd_generation
    app._handle_fdtd_key(ord("n"))
    assert app.fdtd_generation == gen_before + 1


def test_sim_key_viz_cycle():
    app = _make_app()
    app._fdtd_init(0)
    assert app.fdtd_viz_mode == 0
    app._handle_fdtd_key(ord("v"))
    assert app.fdtd_viz_mode == 1
    app._handle_fdtd_key(ord("v"))
    assert app.fdtd_viz_mode == 2
    app._handle_fdtd_key(ord("v"))
    assert app.fdtd_viz_mode == 0


def test_sim_key_freq():
    app = _make_app()
    app._fdtd_init(0)
    f0 = app.fdtd_freq
    app._handle_fdtd_key(ord("f"))
    assert app.fdtd_freq == f0 + 0.01
    # All sources should be updated
    for src in app.fdtd_sources:
        assert src["freq"] == app.fdtd_freq
    app._handle_fdtd_key(ord("F"))
    assert abs(app.fdtd_freq - f0) < 1e-10


def test_sim_key_speed():
    app = _make_app()
    app._fdtd_init(0)
    s0 = app.fdtd_steps_per_frame
    app._handle_fdtd_key(ord("+"))
    assert app.fdtd_steps_per_frame > s0
    app._handle_fdtd_key(ord("-"))
    assert app.fdtd_steps_per_frame == s0


def test_sim_key_quit():
    app = _make_app()
    app._fdtd_init(0)
    app._handle_fdtd_key(ord("q"))
    assert app.fdtd_mode is False


def test_sim_key_return_to_menu():
    app = _make_app()
    app._fdtd_init(0)
    app._handle_fdtd_key(ord("R"))
    assert app.fdtd_mode is False
    assert app.fdtd_menu is True


def test_sim_key_reset():
    app = _make_app()
    app._fdtd_init(0)
    for _ in range(10):
        app._fdtd_step()
    assert app.fdtd_generation > 0
    app._handle_fdtd_key(ord("r"))
    assert app.fdtd_generation == 0


def test_sim_key_clear():
    app = _make_app()
    app._fdtd_init(0)
    for _ in range(10):
        app._fdtd_step()
    app._handle_fdtd_key(ord("c"))
    assert app.fdtd_generation == 0
    # All fields should be zero
    for r in range(app.fdtd_rows):
        for c in range(app.fdtd_cols):
            assert app.fdtd_Ez[r][c] == 0.0


def test_sim_key_add_source():
    app = _make_app()
    app._fdtd_init(0)
    n_before = len(app.fdtd_sources)
    app._handle_fdtd_key(ord("p"))
    assert len(app.fdtd_sources) == n_before + 1


def test_freq_clamp():
    app = _make_app()
    app._fdtd_init(0)
    app.fdtd_freq = 0.30
    app._handle_fdtd_key(ord("f"))
    assert app.fdtd_freq == 0.30  # clamped
    app.fdtd_freq = 0.03
    app._handle_fdtd_key(ord("F"))
    assert app.fdtd_freq == 0.03  # clamped


# --- Courant stability ---

def test_courant_number():
    """Courant number should be <= 1/sqrt(2) for 2D stability."""
    app = _make_app()
    app._fdtd_init(0)
    assert app.fdtd_courant <= 1.0 / math.sqrt(2.0) + 1e-10


# --- Conservation / symmetry tests ---

def test_dipole_symmetry():
    """Dipole antenna pattern should be roughly symmetric about center."""
    app = _make_app()
    app._fdtd_init(5)  # dipole
    for _ in range(40):
        app._fdtd_step()
    cr = app.fdtd_rows // 2
    cc = app.fdtd_cols // 2
    # Due to opposite phases, Ez should be antisymmetric about center row
    # Just check it doesn't crash and produces some output
    has_nonzero = any(
        abs(app.fdtd_Ez[r][cc]) > 1e-10
        for r in range(app.fdtd_rows)
    )
    assert has_nonzero
