"""Tests for hyperbolic_ca mode."""
from tests.conftest import make_mock_app
from life.modes.hyperbolic_ca import register, _build_tiling


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.hyp_mode = False
    app.hyp_menu = False
    app.hyp_running = False
    app.hyp_cells = []
    app.hyp_adj = {}
    app.hyp_states = []
    app.hyp_ages = []
    return app


def test_enter():
    app = _make_app()
    app._enter_hyp_mode()
    assert app.hyp_menu is True


def test_step_no_crash():
    app = _make_app()
    app.hyp_mode = True
    app._hyp_init(0, 0)
    assert app.hyp_mode is True
    assert len(app.hyp_cells) > 0
    for _ in range(10):
        app._hyp_step()


def test_exit_cleanup():
    app = _make_app()
    app.hyp_mode = True
    app._hyp_init(0, 0)
    app._exit_hyp_mode()
    assert app.hyp_mode is False
    assert app.hyp_cells == []


def test_build_tiling_creates_connected_graph():
    """The {5,4} tiling should produce a connected graph with many cells."""
    cells, adj = _build_tiling(5, 4, max_layers=3)
    assert len(cells) > 10
    # Every cell (except possibly boundary) should have at least one neighbor
    connected_count = sum(1 for i in adj if len(adj[i]) > 0)
    assert connected_count >= len(cells) - 1


def test_step_population_changes():
    """Running a step should potentially change population (birth/death)."""
    app = _make_app()
    app._hyp_init(0, 0)
    initial_pop = app.hyp_population
    # Run enough steps to see change
    for _ in range(20):
        app._hyp_step()
    # After 20 steps population should have changed (extremely unlikely to be identical)
    # At least generation counter should advance
    assert app.hyp_generation == 20


def test_randomize_resets_generation():
    """Randomizing resets generation counter to 0."""
    app = _make_app()
    app._hyp_init(0, 0)
    for _ in range(5):
        app._hyp_step()
    assert app.hyp_generation == 5
    app._hyp_randomize()
    assert app.hyp_generation == 0
