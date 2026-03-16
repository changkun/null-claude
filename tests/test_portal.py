"""Tests for life.modes.portal — Portal System mode."""
from tests.conftest import make_mock_app
from life.modes.portal import (
    register, PORTAL_PRESETS,
    _portal_build_boundary_influence, _portal_flip_influence,
)


def _make_app():
    app = make_mock_app()
    app.portal_mode = False
    app.portal_menu = False
    app.portal_menu_sel = 0
    app.portal_menu_phase = 0
    app.portal_running = False
    app.portal_sim_a = None
    app.portal_sim_b = None
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_portal_mode()
    assert app.portal_menu is True
    assert app.portal_menu_phase == 0


def test_step_no_crash():
    app = _make_app()
    app._portal_init("rd", "boids", "vertical")
    assert app.portal_mode is True
    assert app.portal_sim_a is not None
    assert app.portal_sim_b is not None
    for _ in range(10):
        app._portal_step()
    assert app.portal_generation == 10


def test_exit_cleanup():
    app = _make_app()
    app._portal_init("gol", "wave", "horizontal")
    app._exit_portal_mode()
    assert app.portal_mode is False
    assert app.portal_running is False
    assert app.portal_sim_a is None
    assert app.portal_sim_b is None


def test_both_orientations():
    """Portal works for both vertical and horizontal orientation."""
    for orient in ("vertical", "horizontal"):
        app = _make_app()
        app._portal_init("gol", "wave", orient)
        assert app.portal_orientation == orient
        for _ in range(5):
            app._portal_step()
        assert app.portal_generation == 5


def test_boundary_influence_shape():
    """Boundary influence output has correct dimensions."""
    rows, cols = 10, 10
    density = [[0.5] * cols for _ in range(rows)]
    influence = _portal_build_boundary_influence(
        density, rows, cols, "vertical", cols // 2, 3
    )
    assert len(influence) == rows
    assert len(influence[0]) == cols


def test_coupling_affects_step():
    """Different coupling strengths can be set and used during step."""
    app = _make_app()
    app._portal_init("gol", "wave", "vertical")
    app.portal_coupling = 0.0
    for _ in range(5):
        app._portal_step()
    gen_zero = app.portal_generation
    app.portal_coupling = 1.0
    for _ in range(5):
        app._portal_step()
    assert app.portal_generation == gen_zero + 5


def test_all_presets_init():
    """All preset portal configurations can be initialized."""
    for name, id_a, id_b, orient, desc in PORTAL_PRESETS:
        app = _make_app()
        app._portal_init(id_a, id_b, orient)
        assert app.portal_mode is True
        assert app.portal_sim_a is not None
        assert app.portal_sim_b is not None
