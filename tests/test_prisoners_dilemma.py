"""Tests for Prisoner's Dilemma mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.prisoners_dilemma import register, _spd_compute_scores, _spd_step, _spd_count


class TestSPDPresets:
    """Validate presets match the canonical 345e6ea format."""

    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))

    def test_presets_exist(self):
        assert hasattr(type(self.app), 'SPD_PRESETS')
        assert len(self.app.SPD_PRESETS) >= 8

    def test_preset_tuple_format(self):
        """Each preset is (name, desc, T, R, P, S, init_coop_frac)."""
        for i, p in enumerate(self.app.SPD_PRESETS):
            assert len(p) == 7, f"Preset {i} has {len(p)} elements, expected 7"
            name, desc, T, R, P, S, init_coop = p
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(T, (int, float))
            assert isinstance(R, (int, float))
            assert isinstance(P, (int, float))
            assert isinstance(S, (int, float))
            assert 0.0 <= init_coop <= 1.0

    def test_classic_pd_ordering(self):
        """Classic PD requires T > R > P > S (or >= for weak variants)."""
        # At least the first preset (Classic) should follow T > R >= P >= S
        _name, _desc, T, R, P, S, _ic = self.app.SPD_PRESETS[0]
        assert T > R, "Classic PD: T should exceed R"
        assert R >= P, "Classic PD: R should be >= P"

    def test_preset_names_unique(self):
        names = [p[0] for p in self.app.SPD_PRESETS]
        assert len(names) == len(set(names))


class TestSPDInit:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._spd_init(0)
        assert self.app.spd_mode is True
        assert self.app.spd_generation == 0
        assert len(self.app.spd_grid) > 0
        assert self.app.spd_steps_per_frame == 1
        assert hasattr(self.app, 'spd_coop_count')

    def test_init_all_presets(self):
        for i in range(len(self.app.SPD_PRESETS)):
            self.app._spd_init(i)
            assert self.app.spd_mode is True
            assert self.app.spd_generation == 0

    def test_grid_contains_only_0_and_1(self):
        self.app._spd_init(0)
        for row in self.app.spd_grid:
            for v in row:
                assert v in (0, 1), f"Grid cell value {v} is not 0 or 1"

    def test_initial_cooperation_fraction(self):
        """Initial cooperator fraction should be approximately init_coop."""
        random.seed(123)
        self.app._spd_init(0)
        init_coop = self.app.spd_init_coop_frac
        total = self.app.spd_rows * self.app.spd_cols
        coop = self.app.spd_coop_count
        actual_frac = coop / total
        # Should be within 10% of target for reasonable grid sizes
        assert abs(actual_frac - init_coop) < 0.15, \
            f"Expected ~{init_coop}, got {actual_frac}"

    def test_scores_computed_on_init(self):
        self.app._spd_init(0)
        # Scores should be non-trivial (not all zero)
        total_score = sum(self.app.spd_scores[r][c]
                         for r in range(self.app.spd_rows)
                         for c in range(self.app.spd_cols))
        assert total_score > 0

    def test_counts_correct_on_init(self):
        self.app._spd_init(0)
        coop = self.app.spd_coop_count
        defect = self.app.spd_defect_count
        total = self.app.spd_rows * self.app.spd_cols
        assert coop + defect == total

    def test_parameters_match_preset(self):
        preset = self.app.SPD_PRESETS[2]  # Strong Dilemma
        self.app._spd_init(2)
        assert self.app.spd_temptation == preset[2]
        assert self.app.spd_reward == preset[3]
        assert self.app.spd_punishment == preset[4]
        assert self.app.spd_sucker == preset[5]


class TestSPDComputeScores:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_all_cooperators_score(self):
        """If everyone cooperates, each cell scores 8*R (8 Moore neighbors)."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        R = self.app.spd_reward
        # Set all to cooperators
        self.app.spd_grid = [[0] * cols for _ in range(rows)]
        self.app._spd_compute_scores()
        # Interior cells (toroidal, all are interior) should score 8*R
        assert self.app.spd_scores[5][5] == pytest.approx(8 * R)

    def test_all_defectors_score(self):
        """If everyone defects, each cell scores 8*P."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        P = self.app.spd_punishment
        self.app.spd_grid = [[1] * cols for _ in range(rows)]
        self.app._spd_compute_scores()
        assert self.app.spd_scores[5][5] == pytest.approx(8 * P)

    def test_lone_defector_gets_temptation(self):
        """A single defector surrounded by cooperators gets 8*T."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        T = self.app.spd_temptation
        # All cooperators
        self.app.spd_grid = [[0] * cols for _ in range(rows)]
        # One defector
        self.app.spd_grid[5][5] = 1
        self.app._spd_compute_scores()
        assert self.app.spd_scores[5][5] == pytest.approx(8 * T)

    def test_lone_cooperator_gets_sucker(self):
        """A single cooperator surrounded by defectors gets 8*S."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        S = self.app.spd_sucker
        # All defectors
        self.app.spd_grid = [[1] * cols for _ in range(rows)]
        # One cooperator
        self.app.spd_grid[5][5] = 0
        self.app._spd_compute_scores()
        assert self.app.spd_scores[5][5] == pytest.approx(8 * S)

    def test_toroidal_wrapping(self):
        """Score computation should use toroidal (wrapping) boundaries."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        R = self.app.spd_reward
        # All cooperators
        self.app.spd_grid = [[0] * cols for _ in range(rows)]
        self.app._spd_compute_scores()
        # Corner cell should also score 8*R (wraps around)
        assert self.app.spd_scores[0][0] == pytest.approx(8 * R)


class TestSPDStep:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_step_increments_generation(self):
        self.app._spd_init(0)
        self.app._spd_step()
        assert self.app.spd_generation == 1

    def test_step_no_crash(self):
        self.app._spd_init(0)
        for _ in range(10):
            self.app._spd_step()
        assert self.app.spd_generation == 10

    def test_step_preserves_grid_size(self):
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        self.app._spd_step()
        assert len(self.app.spd_grid) == rows
        assert len(self.app.spd_grid[0]) == cols

    def test_step_values_remain_binary(self):
        """Grid values should always be 0 or 1 after stepping."""
        self.app._spd_init(0)
        for _ in range(5):
            self.app._spd_step()
        for row in self.app.spd_grid:
            for v in row:
                assert v in (0, 1)

    def test_counts_updated_after_step(self):
        self.app._spd_init(0)
        self.app._spd_step()
        coop = self.app.spd_coop_count
        defect = self.app.spd_defect_count
        total = self.app.spd_rows * self.app.spd_cols
        assert coop + defect == total

    def test_all_cooperators_stable(self):
        """A grid of all cooperators should be stable (no one switches)."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        self.app.spd_grid = [[0] * cols for _ in range(rows)]
        self.app._spd_compute_scores()
        self.app._spd_count()
        self.app._spd_step()
        # Should still be all cooperators
        for row in self.app.spd_grid:
            for v in row:
                assert v == 0

    def test_all_defectors_stable(self):
        """A grid of all defectors should be stable."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        self.app.spd_grid = [[1] * cols for _ in range(rows)]
        self.app._spd_compute_scores()
        self.app._spd_count()
        self.app._spd_step()
        for row in self.app.spd_grid:
            for v in row:
                assert v == 1

    def test_strategy_adoption_from_best_neighbor(self):
        """A cell should adopt the strategy of its highest-scoring neighbor."""
        self.app._spd_init(0)
        rows, cols = self.app.spd_rows, self.app.spd_cols
        T = self.app.spd_temptation
        R = self.app.spd_reward
        # All cooperators except one defector at (5,5)
        self.app.spd_grid = [[0] * cols for _ in range(rows)]
        self.app.spd_grid[5][5] = 1
        self.app._spd_compute_scores()
        # The defector at (5,5) should have highest score in its neighborhood
        # since T > R. Its neighbors should adopt defection.
        assert self.app.spd_scores[5][5] > self.app.spd_scores[5][6]
        self.app._spd_step()
        # Neighbors of (5,5) should now be defectors
        assert self.app.spd_grid[5][6] == 1
        assert self.app.spd_grid[4][5] == 1


class TestSPDExitAndKeys:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_exit_cleanup(self):
        self.app._spd_init(0)
        assert self.app.spd_mode is True
        self.app._exit_spd_mode()
        assert self.app.spd_mode is False
        assert self.app.spd_running is False
        assert self.app.spd_grid == []
        assert self.app.spd_scores == []

    def test_enter_mode_sets_menu(self):
        self.app._enter_spd_mode()
        assert self.app.spd_menu is True
        assert self.app.spd_menu_sel == 0

    def test_handle_menu_key_navigation(self):
        self.app._enter_spd_mode()
        self.app._handle_spd_menu_key(ord("j"))
        assert self.app.spd_menu_sel == 1
        self.app._handle_spd_menu_key(ord("k"))
        assert self.app.spd_menu_sel == 0

    def test_handle_key_toggle_running(self):
        self.app._spd_init(0)
        assert self.app.spd_running is False
        self.app._handle_spd_key(ord(" "))
        assert self.app.spd_running is True

    def test_handle_key_single_step(self):
        self.app._spd_init(0)
        gen_before = self.app.spd_generation
        self.app._handle_spd_key(ord("n"))
        assert self.app.spd_generation == gen_before + 1

    def test_handle_key_temptation_control(self):
        self.app._spd_init(0)
        t_before = self.app.spd_temptation
        self.app._handle_spd_key(ord("t"))
        assert self.app.spd_temptation > t_before
        self.app._handle_spd_key(ord("T"))
        assert self.app.spd_temptation == pytest.approx(t_before, abs=0.001)

    def test_handle_key_speed_control(self):
        self.app._spd_init(0)
        assert self.app.spd_steps_per_frame == 1
        self.app._handle_spd_key(ord("+"))
        assert self.app.spd_steps_per_frame == 2
        self.app._handle_spd_key(ord("-"))
        assert self.app.spd_steps_per_frame == 1

    def test_handle_key_reset(self):
        random.seed(42)
        self.app._spd_init(0)
        for _ in range(5):
            self.app._spd_step()
        assert self.app.spd_generation > 0
        random.seed(42)
        self.app._handle_spd_key(ord("r"))
        assert self.app.spd_generation == 0

    def test_handle_key_exit(self):
        self.app._spd_init(0)
        self.app._handle_spd_key(ord("q"))
        assert self.app.spd_mode is False

    def test_handle_key_return_to_menu(self):
        self.app._spd_init(0)
        self.app._handle_spd_key(ord("R"))
        assert self.app.spd_mode is False
        assert self.app.spd_menu is True
