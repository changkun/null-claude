"""Tests for timeline_branch mode."""
from tests.conftest import make_mock_app
from life.modes.timeline_branch import register


def _make_app():
    app = make_mock_app()
    register(type(app))
    # Additional attrs needed
    app._push_history = lambda: None
    app._record_pop = lambda: None
    return app


def test_enter():
    app = _make_app()
    app._tbranch_fork_from_current()
    assert app.tbranch_mode is True
    assert app.tbranch_grid is not None


def test_step_no_crash():
    app = _make_app()
    app._tbranch_fork_from_current()
    for _ in range(10):
        app._tbranch_step()
    assert app.tbranch_grid.generation > 0


def test_exit_cleanup():
    app = _make_app()
    app._tbranch_fork_from_current()
    app._tbranch_exit()
    assert app.tbranch_mode is False
    assert app.tbranch_grid is None


def test_fork_creates_independent_grid():
    """Forked grid evolves independently from the original."""
    app = _make_app()
    # Place a glider on original grid
    app.grid.set_alive(1, 2)
    app.grid.set_alive(2, 3)
    app.grid.set_alive(3, 1)
    app.grid.set_alive(3, 2)
    app.grid.set_alive(3, 3)
    app._tbranch_fork_from_current()

    # Step only the branch grid
    initial_main_gen = app.grid.generation
    app._tbranch_step()
    app._tbranch_step()

    # Main grid should not have advanced
    assert app.grid.generation == initial_main_gen
    # Branch grid should have advanced
    assert app.tbranch_grid.generation == initial_main_gen + 2
    # Branch pop history should have grown
    assert len(app.tbranch_pop_history) >= 2


def test_fork_copies_rule_set():
    """Forked grid inherits the birth/survival rules of the original."""
    app = _make_app()
    app.grid.birth = {3, 6}
    app.grid.survival = {2, 3}
    app._tbranch_fork_from_current()
    assert app.tbranch_grid.birth == {3, 6}
    assert app.tbranch_grid.survival == {2, 3}
