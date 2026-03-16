"""Tests for ecosystem_evolution mode."""
from tests.conftest import make_mock_app
from life.modes.ecosystem_evolution import register, EVOECO_PRESETS, BIOME_CAPACITY


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.evoeco_mode = False
    app.evoeco_menu = False
    app.evoeco_menu_sel = 0
    app.evoeco_running = False
    return app


def test_enter():
    app = _make_app()
    app._enter_evoeco_mode()
    assert app.evoeco_menu is True


def test_step_no_crash():
    app = _make_app()
    app.evoeco_mode = True
    app._evoeco_init(0)
    assert app.evoeco_mode is True
    for _ in range(10):
        app._evoeco_step()


def test_exit_cleanup():
    app = _make_app()
    app._evoeco_init(0)
    app._exit_evoeco_mode()
    assert app.evoeco_mode is False


def test_init_creates_species():
    """After init, there should be founder species on the map."""
    app = _make_app()
    app._evoeco_init(0)
    assert len(app.evoeco_species) > 0
    # Each species should have a name and traits
    for sp in app.evoeco_species:
        assert "name" in sp
        assert "traits" in sp


def test_species_have_populations():
    """After init, population list should contain entries with positive size."""
    app = _make_app()
    app._evoeco_init(0)
    assert len(app.evoeco_pops) > 0
    total_pop = sum(p["size"] for p in app.evoeco_pops)
    assert total_pop > 0


def test_generation_advances():
    """Running steps should advance the generation counter."""
    app = _make_app()
    app._evoeco_init(0)
    for _ in range(5):
        app._evoeco_step()
    assert app.evoeco_generation == 5
