"""Tests for spin_glass mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.spin_glass import register, SPINGLASS_PRESETS


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.spinglass_mode = False
    app.spinglass_menu = False
    app.spinglass_menu_sel = 0
    app.spinglass_running = False
    app.spinglass_grid = []
    app.spinglass_coupling = []
    return app


def test_enter():
    app = _make_app()
    app._enter_spinglass_mode()
    assert app.spinglass_menu is True


def test_step_no_crash():
    app = _make_app()
    app.spinglass_mode = True
    app._spinglass_init(0)
    assert app.spinglass_mode is True
    for _ in range(10):
        app._spinglass_step()


def test_exit_cleanup():
    app = _make_app()
    app._spinglass_init(0)
    app._exit_spinglass_mode()
    assert app.spinglass_mode is False
    assert app.spinglass_grid == []


def test_all_presets_init():
    """Every preset initializes without error."""
    for idx in range(len(SPINGLASS_PRESETS)):
        app = _make_app()
        app._spinglass_init(idx)
        assert app.spinglass_mode is True
        assert len(app.spinglass_grid) > 0
        assert len(app.spinglass_coupling) == 2  # (j_right, j_down)


def test_ferromagnet_orders_at_low_temp():
    """A ferromagnet at low T should develop high magnetization."""
    random.seed(42)
    # Use small terminal size so grid is small and orders quickly
    app = make_mock_app(rows=14, cols=20)
    register(type(app))
    app.spinglass_mode = False
    app.spinglass_menu = False
    app.spinglass_menu_sel = 0
    app.spinglass_running = False
    app.spinglass_grid = []
    app.spinglass_coupling = []
    app._spinglass_init(0)
    app.spinglass_temperature = 0.05
    for _ in range(200):
        app._spinglass_step()
    # At very low T on a small grid, ferromagnet should be well-ordered
    assert app.spinglass_magnetization > 0.5, \
        f"FM at T=0.05 should order, got |m|={app.spinglass_magnetization:.3f}"


def test_high_temp_disorders():
    """At high temperature, magnetization should be low."""
    random.seed(42)
    app = _make_app()
    app._spinglass_init(5)  # Hot Disorder, T=5.0
    for _ in range(30):
        app._spinglass_step()
    assert app.spinglass_magnetization < 0.5, \
        f"Hot disordered phase should have low |m|, got {app.spinglass_magnetization:.3f}"


def test_step_advances_generation():
    """Each step should increment the generation counter."""
    app = _make_app()
    app._spinglass_init(0)
    gen_before = app.spinglass_generation
    app._spinglass_step()
    assert app.spinglass_generation == gen_before + 1


def test_energy_tracks_ordering():
    """Energy should be negative for ordered ferromagnet."""
    random.seed(42)
    app = _make_app()
    app._spinglass_init(0)
    app.spinglass_temperature = 0.05
    for _ in range(50):
        app._spinglass_step()
    # Ferromagnet at very low T should have very negative energy
    assert app.spinglass_energy < 0.0, \
        f"Ordered FM should have negative energy, got {app.spinglass_energy:.3f}"
