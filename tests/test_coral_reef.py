"""Tests for coral_reef mode."""
from tests.conftest import make_mock_app
from life.modes.coral_reef import (
    register, CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE, CELL_WATER,
    _bleach_threshold,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.reef_mode = False
    app.reef_menu = False
    app.reef_menu_sel = 0
    app.reef_running = False
    app.reef_grid = []
    app.reef_entities = []
    return app


def test_enter():
    app = _make_app()
    app._enter_reef_mode()
    assert app.reef_menu is True


def test_step_no_crash():
    app = _make_app()
    app.reef_mode = True
    app._reef_init(0)
    assert app.reef_mode is True
    for _ in range(10):
        app._reef_step()


def test_exit_cleanup():
    app = _make_app()
    app._reef_init(0)
    app._exit_reef_mode()
    assert app.reef_mode is False
    assert app.reef_grid == []


def test_bleach_threshold_temperature_relationship():
    """Bleach probability increases with temperature above 28C."""
    assert _bleach_threshold(26.0) == 0.0
    assert _bleach_threshold(28.0) == 0.0
    assert _bleach_threshold(29.5) > 0
    assert _bleach_threshold(31.0) > _bleach_threshold(29.5)


def test_init_places_coral():
    """Healthy Reef preset should have coral cells on the grid."""
    app = _make_app()
    app._reef_init(0)
    coral_count = 0
    for r in range(app.reef_rows):
        for c in range(app.reef_cols):
            if app.reef_grid[r][c] in (CELL_CORAL_BRANCH, CELL_CORAL_MASSIVE):
                coral_count += 1
    assert coral_count > 0, "Healthy Reef should place coral on the grid"


def test_entities_include_herbivores():
    """Healthy Reef preset should spawn herbivorous fish."""
    app = _make_app()
    app._reef_init(0)
    from life.modes.coral_reef import ENT_HERB_FISH
    herb_count = sum(1 for e in app.reef_entities if e["type"] == ENT_HERB_FISH)
    assert herb_count > 0, "Should have herbivorous fish"
