"""Tests for self_modifying_rules mode."""
import curses
from unittest.mock import patch
from tests.conftest import make_mock_app
from life.modes.self_modifying_rules import (
    register, _genome_to_bs, _bs_to_genome, _genome_label,
    _mutate_genome, _majority_genome, _smr_step_fn,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.smr_mode = False
    app.smr_menu = False
    app.smr_menu_sel = 0
    app.smr_running = False
    return app


def test_enter():
    app = _make_app()
    app._enter_smr_mode()
    assert app.smr_menu is True


def test_step_no_crash():
    app = _make_app()
    app.smr_mode = True
    with patch("life.modes.self_modifying_rules._init_smr_colors"):
        app._smr_init(0)
    assert app.smr_mode is True
    for _ in range(10):
        app._smr_step()


def test_exit_cleanup():
    app = _make_app()
    with patch("life.modes.self_modifying_rules._init_smr_colors"):
        app._smr_init(0)
    app._exit_smr_mode()
    assert app.smr_mode is False


def test_genome_roundtrip():
    """Converting birth/survival sets to genome and back is lossless."""
    birth = {3, 6}
    surv = {2, 3}
    genome = _bs_to_genome(birth, surv)
    b_out, s_out = _genome_to_bs(genome)
    assert b_out == frozenset(birth)
    assert s_out == frozenset(surv)


def test_genome_label_format():
    """Genome label matches B.../S... format."""
    genome = _bs_to_genome({3}, {2, 3})
    label = _genome_label(genome)
    assert label == "B3/S23"


def test_majority_genome():
    """Majority genome picks the most common."""
    g1 = (8, 12)
    g2 = (4, 6)
    genomes = [g1, g1, g1, g2]
    result = _majority_genome(genomes)
    assert result == g1


def test_step_fn_births_and_deaths():
    """A single step should produce births or deaths with seed population."""
    rows, cols = 10, 10
    genome = _bs_to_genome({3}, {2, 3})
    alive = [[None]*cols for _ in range(rows)]
    age = [[0]*cols for _ in range(rows)]
    # Place a small cluster
    for r in range(3, 6):
        for c in range(3, 6):
            alive[r][c] = genome
            age[r][c] = 1
    new_alive, new_age, stats = _smr_step_fn(alive, age, rows, cols, 0.0)
    # With a 3x3 block, some cells survive and some new births should appear
    assert stats["total_alive"] > 0
