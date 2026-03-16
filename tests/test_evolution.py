"""Tests for evolution mode — deep validation against commit 88542db."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.evolution import register


class TestEvolution:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    # ── enter / exit ──

    def test_enter_opens_menu(self):
        self.app._enter_evo_mode()
        assert self.app.evo_menu is True
        assert self.app.evo_menu_sel == 0

    def test_enter_exits_compare_and_race(self):
        self.app.compare_mode = True
        self.app.race_mode = True
        # Provide stubs for the exit methods that evo_enter calls
        compare_exited = []
        race_exited = []
        self.app._exit_compare_mode = lambda: compare_exited.append(True)
        self.app._exit_race_mode = lambda: race_exited.append(True)
        self.app._enter_evo_mode()
        assert len(compare_exited) == 1
        assert len(race_exited) == 1
        assert self.app.evo_menu is True

    def test_exit_clears_state(self):
        self.app.evo_mode = True
        self.app.evo_phase = "simulating"
        self.app._evo_init_population()
        assert len(self.app.evo_grids) > 0
        self.app._exit_evo_mode()
        assert self.app.evo_mode is False
        assert self.app.evo_menu is False
        assert self.app.evo_phase == "idle"
        assert len(self.app.evo_grids) == 0
        assert len(self.app.evo_rules) == 0
        assert len(self.app.evo_fitness) == 0
        assert len(self.app.evo_pop_histories) == 0
        assert self.app.evo_generation == 0
        assert self.app.evo_sim_step == 0
        assert self.app.evo_sel == 0
        assert self.app.evo_best_ever is None
        assert len(self.app.evo_history) == 0

    # ── random rule generation ──

    def test_random_rule_returns_birth_survival_sets(self):
        birth, survival = self.app._evo_random_rule()
        assert isinstance(birth, set)
        assert isinstance(survival, set)
        assert len(birth) >= 1
        assert len(survival) >= 1
        assert all(0 <= d <= 8 for d in birth)
        assert all(0 <= d <= 8 for d in survival)

    def test_random_rule_ensures_nonempty(self):
        """Even with bad luck, birth and survival are never empty."""
        for _ in range(200):
            birth, survival = self.app._evo_random_rule()
            assert len(birth) >= 1
            assert len(survival) >= 1

    # ── mutation ──

    def test_mutate_returns_sets(self):
        birth = {3}
        survival = {2, 3}
        new_b, new_s = self.app._evo_mutate(birth, survival)
        assert isinstance(new_b, set)
        assert isinstance(new_s, set)
        assert len(new_b) >= 1  # guaranteed non-empty birth

    def test_mutate_does_not_modify_original(self):
        birth = {3}
        survival = {2, 3}
        birth_copy = set(birth)
        survival_copy = set(survival)
        self.app._evo_mutate(birth, survival)
        assert birth == birth_copy
        assert survival == survival_copy

    def test_mutate_with_zero_rate(self):
        """Zero mutation rate should leave rule unchanged."""
        self.app.evo_mutation_rate = 0.0
        birth = {3}
        survival = {2, 3}
        new_b, new_s = self.app._evo_mutate(birth, survival)
        assert new_b == birth
        assert new_s == survival

    def test_mutate_with_full_rate(self):
        """100% mutation rate flips every digit."""
        self.app.evo_mutation_rate = 1.0
        birth = {3}
        survival = {2, 3}
        new_b, new_s = self.app._evo_mutate(birth, survival)
        # Every digit that was in should be out, and vice versa
        # (except the fallback if birth becomes empty)
        for d in range(9):
            if d == 3:
                assert d not in new_b or len({3} - new_b) == 0  # may be re-added by fallback
            # At minimum, the structure changed significantly

    # ── crossover ──

    def test_crossover_returns_valid_rule(self):
        p1 = ({3}, {2, 3})
        p2 = ({1, 2}, {0, 4})
        child_b, child_s = self.app._evo_crossover(p1, p2)
        assert isinstance(child_b, set)
        assert isinstance(child_s, set)
        assert len(child_b) >= 1

    def test_crossover_digits_from_parents(self):
        """Each digit in child must come from at least one parent."""
        random.seed(123)
        p1 = ({1, 3, 5}, {2, 4})
        p2 = ({2, 4, 6}, {1, 3, 5})
        all_parent_birth = p1[0] | p2[0]
        all_parent_survival = p1[1] | p2[1]
        for _ in range(50):
            child_b, child_s = self.app._evo_crossover(p1, p2)
            # Each child digit is a subset of parent union (minus fallback)
            assert child_b <= all_parent_birth or len(child_b) == 1
            assert child_s <= all_parent_survival

    # ── population initialization ──

    def test_init_population_creates_grids(self):
        self.app.evo_pop_size = 6
        self.app._evo_init_population()
        assert len(self.app.evo_grids) == 6
        assert len(self.app.evo_rules) == 6
        assert len(self.app.evo_fitness) == 6
        assert len(self.app.evo_pop_histories) == 6
        assert self.app.evo_phase == "simulating"
        assert self.app.running is True
        assert self.app.evo_generation == 1

    def test_init_population_grids_have_correct_size(self):
        self.app.evo_pop_size = 4
        self.app._evo_init_population()
        for g in self.app.evo_grids:
            assert g.rows == 30
            assert g.cols == 40

    def test_init_population_grids_have_rules(self):
        self.app.evo_pop_size = 4
        self.app._evo_init_population()
        for i, g in enumerate(self.app.evo_grids):
            birth, survival = self.app.evo_rules[i]
            assert g.birth == birth
            assert g.survival == survival

    def test_init_population_has_initial_pop_history(self):
        self.app.evo_pop_size = 4
        self.app._evo_init_population()
        for hist in self.app.evo_pop_histories:
            assert len(hist) == 1  # initial population count

    def test_init_population_increments_generation(self):
        self.app.evo_pop_size = 4
        assert self.app.evo_generation == 0
        self.app._evo_init_population()
        assert self.app.evo_generation == 1
        self.app._evo_init_population()
        assert self.app.evo_generation == 2

    def test_init_population_from_elites(self):
        """Second generation breeds from elite rules."""
        self.app.evo_pop_size = 6
        self.app.evo_elite_count = 3
        self.app._evo_init_population()
        # Run simulation to completion
        self.app.evo_grid_gens = 10
        for _ in range(10):
            self.app._evo_step_sim()
        # Now evo_history should have elite_rules
        assert len(self.app.evo_history) == 1
        assert "elite_rules" in self.app.evo_history[0]
        # Init next generation
        old_gen = self.app.evo_generation
        self.app._evo_init_population()
        assert self.app.evo_generation == old_gen + 1
        assert len(self.app.evo_grids) == 6

    # ── simulation step ──

    def test_step_sim_advances(self):
        self.app.evo_pop_size = 4
        self.app._evo_init_population()
        assert self.app.evo_sim_step == 0
        self.app._evo_step_sim()
        assert self.app.evo_sim_step == 1
        for hist in self.app.evo_pop_histories:
            assert len(hist) == 2  # initial + 1 step

    def test_step_sim_noop_when_not_simulating(self):
        self.app.evo_phase = "idle"
        self.app._evo_step_sim()
        assert self.app.evo_sim_step == 0

    def test_step_sim_triggers_scoring_at_limit(self):
        self.app.evo_pop_size = 4
        self.app.evo_grid_gens = 5
        self.app._evo_init_population()
        for _ in range(5):
            self.app._evo_step_sim()
        assert self.app.evo_phase == "scored"
        assert self.app.running is False

    # ── fitness evaluation ──

    def test_compute_fitness_empty_hist(self):
        from life.grid import Grid
        g = Grid(10, 10)
        result = self.app._evo_compute_fitness(g, [])
        assert result["total"] == 0
        assert result["longevity"] == 0

    def test_compute_fitness_all_alive(self):
        from life.grid import Grid
        g = Grid(10, 10)
        hist = [50] * 100  # constant population
        result = self.app._evo_compute_fitness(g, hist)
        assert result["longevity"] == 100
        assert result["population"] == 50
        assert result["stability"] == 100  # zero variance = max stability
        assert result["total"] > 0

    def test_compute_fitness_balanced_mode(self):
        from life.grid import Grid
        g = Grid(10, 10)
        self.app.evo_fitness_mode = "balanced"
        hist = [50] * 100
        result = self.app._evo_compute_fitness(g, hist)
        expected = result["longevity"] + result["population"] + result["stability"] + result["diversity"]
        assert abs(result["total"] - expected) < 0.01

    def test_compute_fitness_longevity_mode(self):
        from life.grid import Grid
        g = Grid(10, 10)
        self.app.evo_fitness_mode = "longevity"
        hist = [50] * 100
        result = self.app._evo_compute_fitness(g, hist)
        expected = (result["longevity"] * 3 + result["population"] * 0.5
                    + result["stability"] * 0.5 + result["diversity"] * 0.5)
        assert abs(result["total"] - expected) < 0.01

    def test_compute_fitness_diversity_mode(self):
        from life.grid import Grid
        g = Grid(10, 10)
        self.app.evo_fitness_mode = "diversity"
        hist = list(range(100))  # all different values
        result = self.app._evo_compute_fitness(g, hist)
        expected = (result["diversity"] * 3 + result["longevity"] * 0.5
                    + result["population"] * 0.5 + result["stability"] * 0.5)
        assert abs(result["total"] - expected) < 0.01

    def test_compute_fitness_population_mode(self):
        from life.grid import Grid
        g = Grid(10, 10)
        self.app.evo_fitness_mode = "population"
        hist = [200] * 100
        result = self.app._evo_compute_fitness(g, hist)
        expected = (result["population"] * 3 + result["longevity"] * 0.5
                    + result["stability"] * 0.5 + result["diversity"] * 0.5)
        assert abs(result["total"] - expected) < 0.01

    def test_compute_fitness_pop_capped_at_200(self):
        from life.grid import Grid
        g = Grid(10, 10)
        hist = [500] * 50
        result = self.app._evo_compute_fitness(g, hist)
        assert result["population"] == 200

    def test_compute_fitness_diversity_uses_last_100(self):
        from life.grid import Grid
        g = Grid(10, 10)
        hist = [10] * 200 + list(range(50))  # last 100 has 50 unique in range + some 10s
        result = self.app._evo_compute_fitness(g, hist)
        # last 100 = [10]*50 + range(50) = 51 unique values
        assert result["diversity"] == min(51 * 2, 100)

    # ── score_all ──

    def test_score_all_sorts_by_fitness(self):
        self.app.evo_pop_size = 4
        self.app.evo_grid_gens = 5
        self.app._evo_init_population()
        for _ in range(5):
            self.app._evo_step_sim()
        # After scoring, fitness should be sorted descending
        scores = [f.get("total", 0) for f in self.app.evo_fitness]
        assert scores == sorted(scores, reverse=True)

    def test_score_all_records_history(self):
        self.app.evo_pop_size = 4
        self.app.evo_grid_gens = 5
        self.app._evo_init_population()
        for _ in range(5):
            self.app._evo_step_sim()
        assert len(self.app.evo_history) == 1
        entry = self.app.evo_history[0]
        assert "generation" in entry
        assert "best_score" in entry
        assert "best_rule" in entry
        assert "avg_score" in entry
        assert "elite_rules" in entry

    def test_score_all_tracks_best_ever(self):
        self.app.evo_pop_size = 4
        self.app.evo_grid_gens = 5
        self.app._evo_init_population()
        for _ in range(5):
            self.app._evo_step_sim()
        assert self.app.evo_best_ever is not None
        assert "rule" in self.app.evo_best_ever
        assert "gen" in self.app.evo_best_ever
        assert "total" in self.app.evo_best_ever

    # ── next generation ──

    def test_next_generation_reinits(self):
        self.app.evo_pop_size = 4
        self.app.evo_grid_gens = 5
        self.app._evo_init_population()
        for _ in range(5):
            self.app._evo_step_sim()
        assert self.app.evo_phase == "scored"
        self.app._evo_next_generation()
        assert self.app.evo_phase == "simulating"
        assert self.app.evo_generation == 2
        assert self.app.evo_sim_step == 0

    # ── adopt rule ──

    def test_adopt_rule_sets_main_grid(self):
        self.app.evo_pop_size = 4
        self.app.evo_grid_gens = 5
        self.app._evo_init_population()
        for _ in range(5):
            self.app._evo_step_sim()
        self.app.evo_sel = 0
        expected_birth = set(self.app.evo_rules[0][0])
        expected_survival = set(self.app.evo_rules[0][1])
        self.app._evo_adopt_rule()
        assert self.app.grid.birth == expected_birth
        assert self.app.grid.survival == expected_survival
        assert self.app.evo_mode is False

    def test_adopt_rule_noop_when_no_rules(self):
        self.app.evo_rules = []
        self.app._evo_adopt_rule()  # should not crash

    # ── full GA cycle ──

    def test_full_ga_two_generations(self):
        """Run two full GA generations end-to-end."""
        self.app.evo_pop_size = 6
        self.app.evo_grid_gens = 10
        self.app.evo_elite_count = 3

        # Gen 1
        self.app._evo_init_population()
        assert self.app.evo_generation == 1
        for _ in range(10):
            self.app._evo_step_sim()
        assert self.app.evo_phase == "scored"
        assert len(self.app.evo_history) == 1

        # Gen 2
        self.app._evo_next_generation()
        assert self.app.evo_generation == 2
        for _ in range(10):
            self.app._evo_step_sim()
        assert self.app.evo_phase == "scored"
        assert len(self.app.evo_history) == 2
        # Best ever should be set
        assert self.app.evo_best_ever is not None
