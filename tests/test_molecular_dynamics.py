"""Tests for molecular_dynamics mode."""
import math
from tests.conftest import make_mock_app
from life.modes.molecular_dynamics import (
    register, MOLDYN_PRESETS, _init_sim, _step, _compute_forces,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.moldyn_mode = False
    app.moldyn_menu = False
    app.moldyn_menu_sel = 0
    app.moldyn_sim = None
    app.moldyn_running = False
    app.moldyn_view = 0
    app.mode_browser = False
    return app


def test_enter():
    app = _make_app()
    app._enter_moldyn_mode()
    assert app.moldyn_menu is True
    assert app.moldyn_mode is True


def test_step_no_crash():
    app = _make_app()
    app.moldyn_mode = True
    app._moldyn_init(5)  # Gas preset — fastest
    assert app.moldyn_sim is not None
    app.moldyn_running = True
    for _ in range(10):
        app._moldyn_step()


def test_exit_cleanup():
    app = _make_app()
    app._moldyn_init(5)
    app._exit_moldyn_mode()
    assert app.moldyn_mode is False
    assert app.moldyn_sim is None


def test_all_presets_init():
    """Every preset initializes without error."""
    for idx in range(len(MOLDYN_PRESETS)):
        app = _make_app()
        app._moldyn_init(idx)
        assert app.moldyn_sim is not None
        assert app.moldyn_sim["n"] > 0


def test_energy_conservation_nve():
    """With thermostat off, total energy should be roughly conserved."""
    settings = {"temperature": 1.0, "density": 0.4, "n_particles": 20,
                "init": "lattice", "thermostat": False}
    sim = _init_sim(settings)
    # Let it equilibrate a bit
    for _ in range(20):
        _step(sim)
    e0 = (sim["ke"] + sim["pe"]) / sim["n"]
    for _ in range(50):
        _step(sim)
    e1 = (sim["ke"] + sim["pe"]) / sim["n"]
    # Energy drift should be small (Verlet is symplectic)
    assert abs(e1 - e0) < 0.5, f"Energy drift too large: {abs(e1 - e0)}"


def test_temperature_approaches_target():
    """With thermostat on, temperature should approach target."""
    settings = {"temperature": 1.0, "density": 0.4, "n_particles": 30,
                "init": "random", "thermostat": True}
    sim = _init_sim(settings)
    for _ in range(100):
        _step(sim)
    # Temperature should be within ~50% of target
    assert sim["temp"] > 0.3
    assert sim["temp"] < 3.0


def test_step_advances_counter():
    """Each step should increment the step counter."""
    settings = MOLDYN_PRESETS[5][2]  # Gas
    sim = _init_sim(settings)
    assert sim["step"] == 0
    _step(sim)
    assert sim["step"] == 1
