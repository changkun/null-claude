"""Tests for morphogenesis mode."""
from tests.conftest import make_mock_app
from life.modes.morphogenesis import (
    register, _make_genome, _mutate_genome, CELL_STEM, CELL_EMPTY,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.morpho_mode = False
    app.morpho_menu = False
    app.morpho_menu_sel = 0
    app.morpho_running = False
    app.morpho_cells = []
    app.morpho_genome_map = []
    app.morpho_morph_A = []
    app.morpho_morph_B = []
    app.morpho_nutrient = []
    app.morpho_age = []
    return app


def test_enter():
    app = _make_app()
    app._enter_morpho_mode()
    assert app.morpho_menu is True


def test_step_no_crash():
    app = _make_app()
    app.morpho_mode = True
    app._morpho_init(0)
    assert app.morpho_mode is True
    for _ in range(10):
        app._morpho_step()


def test_exit_cleanup():
    app = _make_app()
    app._morpho_init(0)
    app._exit_morpho_mode()
    assert app.morpho_mode is False
    assert app.morpho_cells == []


def test_zygote_placed_at_center():
    """Init places a stem cell (zygote) at the grid center."""
    app = _make_app()
    app._morpho_init(0)
    cr = app.morpho_rows // 2
    cc = app.morpho_cols // 2
    assert app.morpho_cells[cr][cc] == CELL_STEM
    assert app.morpho_genome_map[cr][cc] is not None


def test_genome_mutation_changes_values():
    """Mutating a genome with rate 1.0 should change at least some values."""
    g = _make_genome()
    mutated = _mutate_genome(g, rate=1.0)
    # With rate=1.0, every field is mutated. At least one should differ.
    diffs = sum(1 for k in g if g[k] != mutated[k])
    assert diffs > 0


def test_morphogen_diffusion_after_steps():
    """After several steps, morphogen A should diffuse away from the zygote."""
    app = _make_app()
    app._morpho_init(0)
    # Run a few steps to let morphogens diffuse
    for _ in range(20):
        app._morpho_step()
    # Morphogen A at center should be positive
    cr = app.morpho_rows // 2
    cc = app.morpho_cols // 2
    # Check a cell near center has non-zero morphogen
    total_mA = sum(app.morpho_morph_A[cr][c] for c in range(max(0, cc-3), min(app.morpho_cols, cc+4)))
    assert total_mA > 0
