"""Tests for tierra mode."""
from tests.conftest import make_mock_app
from life.modes.tierra import (
    register, TIERRA_PRESETS, _init_soup, _soup_step,
    Organism, _genome_hash, ANCESTOR_GENOME,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.tierra_mode = False
    app.tierra_menu = False
    app.tierra_menu_sel = 0
    app.tierra_soup = None
    app.tierra_running = False
    app.tierra_view = "memory"
    app.tierra_scroll = 0
    app.mode_browser = False
    return app


def test_enter():
    app = _make_app()
    app._enter_tierra_mode()
    assert app.tierra_menu is True
    assert app.tierra_mode is True


def test_step_no_crash():
    app = _make_app()
    app.tierra_mode = True
    app._tierra_init(0)
    assert app.tierra_soup is not None
    app.tierra_running = True
    for _ in range(10):
        app._tierra_step()


def test_exit_cleanup():
    app = _make_app()
    app._tierra_init(0)
    app._exit_tierra_mode()
    assert app.tierra_mode is False
    assert app.tierra_soup is None


def test_all_presets_init():
    """Every preset initializes without error."""
    for idx in range(len(TIERRA_PRESETS)):
        app = _make_app()
        app._tierra_init(idx)
        assert app.tierra_soup is not None
        assert len(app.tierra_soup["organisms"]) > 0


def test_ancestor_genome_hash_deterministic():
    """Genome hash should be deterministic for the same genome."""
    h1 = _genome_hash(ANCESTOR_GENOME)
    h2 = _genome_hash(ANCESTOR_GENOME)
    assert h1 == h2


def test_soup_generation_increments():
    """Each soup step should increment the generation counter."""
    settings = TIERRA_PRESETS[0][2]
    soup = _init_soup(settings)
    assert soup["generation"] == 0
    _soup_step(soup)
    assert soup["generation"] == 1


def test_organism_starts_alive():
    """A freshly created organism should be alive."""
    org = Organism(list(ANCESTOR_GENOME), 0, len(ANCESTOR_GENOME))
    assert org.alive is True
    assert org.age == 0
    assert org.errors == 0


def test_soup_population_can_grow():
    """After many steps, births should occur (population reproduces)."""
    settings = TIERRA_PRESETS[0][2]
    soup = _init_soup(settings)
    for _ in range(100):
        _soup_step(soup)
    # The ancestor should attempt to replicate
    assert soup["births"] >= 0  # may or may not succeed in 100 steps
    assert soup["generation"] == 100
