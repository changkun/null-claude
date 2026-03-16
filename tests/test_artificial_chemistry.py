"""Tests for artificial_chemistry mode."""
from tests.conftest import make_mock_app
from life.modes.artificial_chemistry import (
    register, _complement, _can_concatenate, _can_cleave,
    _template_match, ALPHABET, MAX_MOL_LEN,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.achem_mode = False
    app.achem_menu = False
    app.achem_menu_sel = 0
    app.achem_running = False
    app.achem_grid = []
    app.achem_energy = []
    app.achem_mol_history = []
    return app


def test_enter():
    app = _make_app()
    app._enter_achem_mode()
    assert app.achem_menu is True


def test_step_no_crash():
    app = _make_app()
    app.achem_mode = True
    app._achem_init(0)
    assert app.achem_mode is True
    for _ in range(10):
        app._achem_step()


def test_exit_cleanup():
    app = _make_app()
    app._achem_init(0)
    app._exit_achem_mode()
    assert app.achem_mode is False
    assert app.achem_grid == []


def test_complement_symmetry():
    """Complement applied twice gives back the original character."""
    for ch in ALPHABET:
        assert _complement(_complement(ch)) == ch


def test_can_concatenate_length_limit():
    """Concatenation should respect MAX_MOL_LEN."""
    short = "AB"
    long_mol = "A" * (MAX_MOL_LEN - 1)
    assert _can_concatenate(short, "C") is True
    assert _can_concatenate(long_mol, "BC") is False


def test_can_cleave_minimum_length():
    """Only molecules with length >= 3 can be cleaved."""
    assert _can_cleave("AB") is False
    assert _can_cleave("ABC") is True


def test_template_match():
    """Template match succeeds when target is exact complement."""
    template = "AB"
    target = _complement("A") + _complement("B")
    assert _template_match(template, target) is True
    assert _template_match(template, "ZZ") is False


def test_init_populates_grid():
    """After init, the grid should contain some molecules."""
    app = _make_app()
    app._achem_init(0)
    mol_count = sum(1 for r in range(app.achem_rows)
                    for c in range(app.achem_cols)
                    if app.achem_grid[r][c] is not None)
    assert mol_count > 0
