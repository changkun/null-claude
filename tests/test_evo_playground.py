"""Tests for life.modes.evo_playground — Evolutionary Playground mode."""
from tests.conftest import make_mock_app
from life.modes.evo_playground import register


def _make_app():
    app = make_mock_app()
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_evo_playground()
    assert app.ep_menu is True
    assert app.ep_mode is False


def test_step_no_crash():
    app = _make_app()
    app._ep_init()
    assert app.ep_mode is True
    assert len(app.ep_sims) > 0
    for _ in range(10):
        app._ep_step()
    assert app.ep_sim_generation == 10


def test_exit_cleanup():
    app = _make_app()
    app._ep_init()
    app._exit_evo_playground()
    assert app.ep_mode is False
    assert app.ep_sims == []
    assert app.ep_genomes == []
    assert app.ep_selected == set()


def test_genomes_have_valid_birth_survival():
    """Every generated genome should have non-empty birth set."""
    from life.modes.evo_playground import _random_genome
    for _ in range(20):
        g = _random_genome()
        assert len(g["birth"]) > 0, "Genome birth set must not be empty"
        assert len(g["survival"]) > 0, "Genome survival set must not be empty"
        assert g["neighborhood"] in ("moore", "von_neumann", "hex")
        assert g["num_states"] >= 2


def test_crossover_produces_valid_offspring():
    """Crossover of two genomes should produce a genome with valid fields."""
    from life.modes.evo_playground import _random_genome, _crossover
    g1 = _random_genome()
    g2 = _random_genome()
    child = _crossover(g1, g2)
    assert len(child["birth"]) > 0
    assert isinstance(child["survival"], set)
    assert child["neighborhood"] in ("moore", "von_neumann", "hex")


def test_mutation_preserves_structure():
    """Mutation should preserve genome structure and keep birth non-empty."""
    from life.modes.evo_playground import _random_genome, _mutate
    for _ in range(20):
        g = _random_genome()
        mutated = _mutate(g, rate=0.5)  # high rate
        assert len(mutated["birth"]) > 0
        assert isinstance(mutated["survival"], set)
        assert mutated["neighborhood"] in ("moore", "von_neumann", "hex")
        assert mutated["num_states"] >= 2


def test_breed_requires_two_parents():
    """Breeding with fewer than 2 parents should flash an error, not crash."""
    app = _make_app()
    app._ep_init()
    app.ep_selected = {0}  # only 1 parent
    app._ep_breed()
    assert "at least 2" in app.message.lower()


def test_step_updates_population_history():
    """Each step should append population to the history."""
    app = _make_app()
    app._ep_init()
    initial_hist_lens = [len(h) for h in app.ep_pop_histories]
    app._ep_step()
    for i, h in enumerate(app.ep_pop_histories):
        assert len(h) == initial_hist_lens[i] + 1
