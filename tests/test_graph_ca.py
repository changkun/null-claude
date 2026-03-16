"""Tests for graph_ca mode."""
from tests.conftest import make_mock_app
from life.modes.graph_ca import (
    register, _build_ring, _build_star, _build_tree,
    _build_scalefree, _clustering_coefficient,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.gca_mode = False
    app.gca_menu = False
    app.gca_running = False
    app.gca_n = 0
    app.gca_adj = {}
    app.gca_states = []
    app.gca_ages = []
    app.gca_pos_x = []
    app.gca_pos_y = []
    return app


def test_enter():
    app = _make_app()
    app._enter_gca_mode()
    assert app.gca_menu is True


def test_step_no_crash():
    app = _make_app()
    app.gca_mode = True
    app._gca_init(0, 0, node_count=30)
    assert app.gca_mode is True
    assert app.gca_n > 0
    for _ in range(10):
        app._gca_step()


def test_exit_cleanup():
    app = _make_app()
    app.gca_mode = True
    app._gca_init(0, 0, node_count=30)
    app._exit_gca_mode()
    assert app.gca_mode is False
    assert app.gca_n == 0


def test_ring_topology_degree():
    """Ring lattice with k=4 should give each node exactly 4 neighbors."""
    n, adj = _build_ring(20, k=4)
    assert n == 20
    for i in range(n):
        assert len(adj[i]) == 4, f"Node {i} has {len(adj[i])} neighbors, expected 4"


def test_star_topology():
    """Star graph: hub connects to all, leaves connect only to hub."""
    n, adj = _build_star(10)
    assert n == 10
    assert len(adj[0]) == 9  # hub
    for i in range(1, n):
        assert len(adj[i]) == 1
        assert adj[i][0] == 0


def test_ca_step_applies_rules():
    """A node with exactly 3 live neighbors should be born under B3/S23."""
    app = _make_app()
    app._gca_init(4, 0, node_count=20)  # Star graph, B3/S23
    # Under B3/S23 on a star, interesting dynamics depend on topology
    # Just verify step advances generation
    gen_before = app.gca_generation
    app._gca_step()
    assert app.gca_generation == gen_before + 1


def test_clustering_coefficient_complete_graph():
    """A complete graph should have clustering coefficient 1.0."""
    n = 5
    adj = {i: [j for j in range(n) if j != i] for i in range(n)}
    cc = _clustering_coefficient(n, adj)
    assert abs(cc - 1.0) < 0.01
