"""Tests for life.modes.topology — Topology Mode."""
from tests.conftest import make_mock_app
from life.modes.topology import register, TOPOLOGY_INFO
from life.grid import Grid


def _make_app():
    app = make_mock_app()
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    # Topology is a cross-cutting feature, not a menu mode
    assert hasattr(app, '_topology_cycle')
    assert hasattr(app, '_topology_set')
    assert app.grid.topology == Grid.TOPO_TORUS


def test_step_no_crash():
    app = _make_app()
    # Cycle through all topologies 10 times
    for _ in range(10):
        app._topology_cycle(1)
    # Should have cycled through 5 topologies twice
    assert app.grid.topology in Grid.TOPOLOGIES


def test_exit_cleanup():
    app = _make_app()
    app._topology_set("klein_bottle")
    assert app.grid.topology == Grid.TOPO_KLEIN
    # Reset to default
    app._topology_set("torus")
    assert app.grid.topology == Grid.TOPO_TORUS


def test_cycle_visits_all_topologies():
    """Cycling forward through all topologies visits each one exactly once."""
    app = _make_app()
    n = len(Grid.TOPOLOGIES)
    visited = set()
    for _ in range(n):
        app._topology_cycle(1)
        visited.add(app.grid.topology)
    assert visited == set(Grid.TOPOLOGIES)


def test_cycle_backward():
    """Cycling backward yields a different sequence than forward."""
    app = _make_app()
    app._topology_cycle(-1)
    topo_back = app.grid.topology
    # Reset
    app._topology_set("torus")
    app._topology_cycle(1)
    topo_forward = app.grid.topology
    # They should be different (unless only 2 topologies, but there are 5)
    assert topo_back != topo_forward


def test_topology_info_complete():
    """Every topology in Grid.TOPOLOGIES has metadata in TOPOLOGY_INFO."""
    for topo in Grid.TOPOLOGIES:
        assert topo in TOPOLOGY_INFO, f"Missing TOPOLOGY_INFO for {topo}"
        info = TOPOLOGY_INFO[topo]
        assert "label" in info
        assert "symbol" in info
        assert "desc" in info
        assert "edges" in info
        edges = info["edges"]
        assert set(edges.keys()) == {"top", "bottom", "left", "right"}


def test_set_invalid_topology_ignored():
    """Setting an invalid topology name does not change the grid."""
    app = _make_app()
    original = app.grid.topology
    app._topology_set("nonexistent_topology")
    assert app.grid.topology == original
