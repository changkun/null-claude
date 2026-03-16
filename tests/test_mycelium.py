"""Tests for mycelium mode."""
import random
from tests.conftest import make_mock_app
from life.modes.mycelium import register, MYCELIUM_PRESETS, CELL_HYPHA, CELL_ROOT, CELL_TOPSOIL


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.mycelium_mode = False
    app.mycelium_menu = False
    app.mycelium_menu_sel = 0
    app.mycelium_running = False
    return app


def test_enter():
    app = _make_app()
    app._enter_mycelium_mode()
    assert app.mycelium_menu is True


def test_step_no_crash():
    app = _make_app()
    app.mycelium_mode = True
    app._mycelium_init(0)
    assert app.mycelium_mode is True
    for _ in range(10):
        app._mycelium_step()


def test_exit_cleanup():
    app = _make_app()
    app._mycelium_init(0)
    app._exit_mycelium_mode()
    assert app.mycelium_mode is False


def test_all_presets_init():
    """Each preset initializes without error and produces a non-empty grid."""
    for idx in range(len(MYCELIUM_PRESETS)):
        app = _make_app()
        app._mycelium_init(idx)
        assert len(app.mycelium_grid) > 0
        assert app.mycelium_rows > 0
        assert app.mycelium_cols > 0


def test_step_advances_generation():
    """Stepping increments the generation counter."""
    app = _make_app()
    app._mycelium_init(0)
    gen_before = app.mycelium_generation
    app._mycelium_step()
    assert app.mycelium_generation == gen_before + 1


def test_grid_contains_expected_cells():
    """Old-Growth Forest preset should have root and hypha cells."""
    random.seed(42)
    app = _make_app()
    app._mycelium_init(0)  # Old-Growth Forest
    flat = [cell for row in app.mycelium_grid for cell in row]
    # Should contain at least some roots and hyphae
    assert any(c == CELL_ROOT for c in flat) or any(c == CELL_HYPHA for c in flat), \
        "Old-Growth Forest should have root or hypha cells"
    # Topsoil should be present
    assert any(c == CELL_TOPSOIL for c in flat), "Should have topsoil"


def test_stats_updated_after_step():
    """Stats dict should be populated after stepping."""
    random.seed(42)
    app = _make_app()
    app._mycelium_init(0)
    for _ in range(5):
        app._mycelium_step()
    stats = app.mycelium_stats
    assert "hypha_cells" in stats
    assert "trees_alive" in stats
    # After steps on Old-Growth, there should be trees
    assert stats["trees_alive"] > 0
