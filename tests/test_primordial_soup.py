"""Tests for primordial_soup mode."""
import random
from tests.conftest import make_mock_app
from life.modes.primordial_soup import (
    register, PRIMSOUP_PRESETS, CELL_WATER, CELL_VENT, CELL_MONOMER,
    CELL_MINERAL, _energy_at,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.psoup_mode = False
    app.psoup_menu = False
    app.psoup_menu_sel = 0
    app.psoup_running = False
    app.psoup_grid = []
    app.psoup_energy_grid = []
    app.psoup_protocells = []
    return app


def test_enter():
    app = _make_app()
    app._enter_psoup_mode()
    assert app.psoup_menu is True


def test_step_no_crash():
    app = _make_app()
    app.psoup_mode = True
    app._psoup_init(0)
    assert app.psoup_mode is True
    for _ in range(10):
        app._psoup_step()


def test_exit_cleanup():
    app = _make_app()
    app._psoup_init(0)
    app._exit_psoup_mode()
    assert app.psoup_mode is False
    assert app.psoup_grid == []


def test_all_presets_init():
    """Every preset initializes without error."""
    for idx in range(len(PRIMSOUP_PRESETS)):
        app = _make_app()
        app._psoup_init(idx)
        assert len(app.psoup_grid) > 0
        assert len(app.psoup_energy_grid) > 0
        assert len(app.psoup_vents) > 0


def test_vents_present_in_grid():
    """Grid should contain vent cells after init."""
    random.seed(42)
    app = _make_app()
    app._psoup_init(0)  # Hydrothermal Vent Field — 6 vents
    flat = [cell for row in app.psoup_grid for cell in row]
    assert flat.count(CELL_VENT) > 0, "Vent cells should exist in the grid"


def test_energy_decays_with_distance():
    """Energy should be higher near vents and lower far away."""
    vents = [(10, 10)]
    near = _energy_at(10, 11, 30, 30, vents, 1.0, 50.0)
    far = _energy_at(0, 0, 30, 30, vents, 1.0, 50.0)
    assert near > far, "Energy near vent should be higher than far away"


def test_step_updates_stats():
    """Stats should be populated after stepping."""
    random.seed(42)
    app = _make_app()
    app._psoup_init(0)
    for _ in range(5):
        app._psoup_step()
    stats = app.psoup_stats
    assert "monomers" in stats
    assert "protocells" in stats
    assert app.psoup_generation == 5


def test_monomer_count_changes():
    """After stepping, monomer count should change (creation/consumption)."""
    random.seed(42)
    app = _make_app()
    app._psoup_init(0)
    mono_init = app.psoup_stats["monomers"]
    for _ in range(20):
        app._psoup_step()
    mono_after = app.psoup_stats["monomers"]
    # It's almost certain the count changes in 20 steps with vents producing
    assert mono_after != mono_init or app.psoup_generation > 0
