"""Tests for ancestor_search mode."""
from tests.conftest import make_mock_app
from life.modes.ancestor_search import (
    register, AncestorSearchEngine, _step_flat, _fitness,
    _grid_to_flat, _flat_to_cells,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_ancestor_search()
    assert app.anc_mode is True
    assert app.anc_menu is True


def test_step_no_crash():
    app = _make_app()
    app._enter_ancestor_search()
    # Load a preset to start search
    app._anc_load_preset(0)  # block
    assert app.anc_engine is not None
    for _ in range(10):
        app._anc_step()


def test_exit_cleanup():
    app = _make_app()
    app._enter_ancestor_search()
    app._anc_load_preset(0)
    app._exit_ancestor_search()
    assert app.anc_mode is False
    assert app.anc_engine is None


def test_step_flat_applies_life_rules():
    """_step_flat correctly applies B3/S23 (Conway Life) rules on a large enough grid."""
    # A 5x5 grid with a vertical blinker in the center (avoids toroidal edge effects)
    flat = [0, 0, 0, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 1, 0, 0,
            0, 0, 0, 0, 0]
    birth = {3}
    survival = {2, 3}
    result = _step_flat(flat, 5, 5, birth, survival)
    # Should become horizontal blinker in center row:
    expected = [0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
                0, 1, 1, 1, 0,
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0]
    assert result == expected


def test_fitness_perfect_score():
    """Perfect candidate gives perfect fitness."""
    target = [1, 0, 1, 0]
    candidate = [1, 0, 1, 0]
    assert _fitness(candidate, target, 2, 2) == 4


def test_search_engine_finds_block_ancestor():
    """AncestorSearchEngine can find a predecessor for a block (still life)."""
    # A 2x2 block is a still life, so it is its own ancestor
    rows, cols = 6, 6
    target_cells = [[0]*cols for _ in range(rows)]
    target_cells[2][2] = 1
    target_cells[2][3] = 1
    target_cells[3][2] = 1
    target_cells[3][3] = 1
    target_flat = _grid_to_flat(target_cells, rows, cols)

    engine = AncestorSearchEngine(target_flat, rows, cols, {3}, {2, 3})
    for _ in range(200):
        engine.step()
        if engine.solutions:
            break

    # The block is its own ancestor, so the engine should find at least one solution
    assert len(engine.solutions) > 0
