"""Tests for race mode — deep validation against commit febddaa."""
import curses
import random
import pytest
from unittest.mock import patch
from tests.conftest import make_mock_app
from life.modes.race_rules import register
from life.rules import RULE_PRESETS, rule_string


def _mock_color_pair(n):
    return 0


class TestRaceRules:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    # ── Enter ──

    def test_enter_race_mode_opens_menu(self):
        self.app._enter_race_mode()
        assert self.app.race_rule_menu is True
        assert self.app.race_rule_sel == 0
        assert self.app.race_selected_rules == []

    def test_enter_race_mode_exits_compare_first(self):
        """If compare_mode is active, entering race should exit it."""
        self.app.compare_mode = True
        called = []
        type(self.app)._exit_compare_mode = lambda s: called.append(True)
        self.app._enter_race_mode()
        assert len(called) == 1
        assert self.app.race_rule_menu is True

    # ── Rule menu key handling ──

    def test_menu_key_noop_on_minus_one(self):
        self.app._enter_race_mode()
        assert self.app._handle_race_rule_menu_key(-1) is True

    def test_menu_key_escape_cancels(self):
        self.app._enter_race_mode()
        self.app._handle_race_rule_menu_key(27)
        assert self.app.race_rule_menu is False
        assert self.app.race_selected_rules == []

    def test_menu_key_q_cancels(self):
        self.app._enter_race_mode()
        self.app._handle_race_rule_menu_key(ord("q"))
        assert self.app.race_rule_menu is False

    def test_menu_key_up_down_navigation(self):
        self.app._enter_race_mode()
        n = len(self.app.rule_preset_list)
        # Down wraps
        self.app._handle_race_rule_menu_key(ord("j"))
        assert self.app.race_rule_sel == 1
        # Up wraps back
        self.app._handle_race_rule_menu_key(ord("k"))
        assert self.app.race_rule_sel == 0
        # Up from 0 wraps to end
        self.app._handle_race_rule_menu_key(curses.KEY_UP)
        assert self.app.race_rule_sel == n - 1

    def test_menu_key_space_toggles_selection(self):
        self.app._enter_race_mode()
        # Select first rule
        self.app._handle_race_rule_menu_key(ord(" "))
        assert len(self.app.race_selected_rules) == 1
        name0 = self.app.rule_preset_list[0]
        assert self.app.race_selected_rules[0][0] == name0
        # Toggle off
        self.app._handle_race_rule_menu_key(ord(" "))
        assert len(self.app.race_selected_rules) == 0

    def test_menu_key_space_max_four(self):
        self.app._enter_race_mode()
        # Select 4 different rules
        for i in range(4):
            self.app.race_rule_sel = i
            self.app._handle_race_rule_menu_key(ord(" "))
        assert len(self.app.race_selected_rules) == 4
        # Trying to add a 5th should flash and not add
        self.app.race_rule_sel = 4
        self.app._handle_race_rule_menu_key(ord(" "))
        assert len(self.app.race_selected_rules) == 4
        assert "Max 4" in self.app.message

    def test_menu_key_enter_requires_two_rules(self):
        self.app._enter_race_mode()
        # Select only 1 rule
        self.app._handle_race_rule_menu_key(ord(" "))
        assert len(self.app.race_selected_rules) == 1
        # Enter should flash error
        self.app._handle_race_rule_menu_key(10)
        assert "at least 2" in self.app.message
        assert self.app.race_mode is False

    def test_menu_key_enter_starts_race_with_two_rules(self):
        self.app._enter_race_mode()
        self.app.grid.set_alive(5, 5)
        # Select 2 rules
        self.app.race_rule_sel = 0
        self.app._handle_race_rule_menu_key(ord(" "))
        self.app.race_rule_sel = 1
        self.app._handle_race_rule_menu_key(ord(" "))
        # Start race
        self.app._handle_race_rule_menu_key(10)
        assert self.app.race_mode is True
        assert self.app.race_rule_menu is False
        assert len(self.app.race_grids) == 2

    def test_menu_key_g_changes_max_gens(self):
        self.app._enter_race_mode()
        type(self.app)._prompt_text = lambda s, p: "1000"
        self.app._handle_race_rule_menu_key(ord("g"))
        assert self.app.race_max_gens == 1000

    def test_menu_key_g_rejects_out_of_range(self):
        self.app._enter_race_mode()
        type(self.app)._prompt_text = lambda s, p: "5"
        self.app._handle_race_rule_menu_key(ord("g"))
        assert self.app.race_max_gens == 500
        assert "between 10 and 10000" in self.app.message

    def test_menu_key_g_rejects_non_numeric(self):
        self.app._enter_race_mode()
        type(self.app)._prompt_text = lambda s, p: "abc"
        self.app._handle_race_rule_menu_key(ord("g"))
        assert "Invalid number" in self.app.message

    # ── _start_race ──

    def test_start_race_clones_grid(self):
        """Each race grid should be a copy of the main grid."""
        self.app.grid.set_alive(3, 3)
        self.app.grid.set_alive(3, 4)
        self.app.grid.set_alive(3, 5)
        self.app._enter_race_mode()
        presets = list(RULE_PRESETS.keys())
        for name in presets[:2]:
            p = RULE_PRESETS[name]
            self.app.race_selected_rules.append(
                (name, set(p["birth"]), set(p["survival"]))
            )
        self.app._start_race()
        assert len(self.app.race_grids) == 2
        for g in self.app.race_grids:
            assert g.cells[3][3] > 0
            assert g.cells[3][4] > 0
            assert g.cells[3][5] > 0
            assert g.rows == self.app.grid.rows
            assert g.cols == self.app.grid.cols

    def test_start_race_sets_rules_on_grids(self):
        self.app._enter_race_mode()
        presets = list(RULE_PRESETS.keys())
        for name in presets[:2]:
            p = RULE_PRESETS[name]
            self.app.race_selected_rules.append(
                (name, set(p["birth"]), set(p["survival"]))
            )
        self.app._start_race()
        for i, g in enumerate(self.app.race_grids):
            _, birth, survival = self.app.race_selected_rules[i]
            assert g.birth == birth
            assert g.survival == survival

    def test_start_race_initializes_stats(self):
        self.app._enter_race_mode()
        presets = list(RULE_PRESETS.keys())
        for name in presets[:3]:
            p = RULE_PRESETS[name]
            self.app.race_selected_rules.append(
                (name, set(p["birth"]), set(p["survival"]))
            )
        self.app._start_race()
        assert len(self.app.race_stats) == 3
        for s in self.app.race_stats:
            assert s["extinction_gen"] is None
            assert s["osc_period"] is None
            assert "peak_pop" in s
        assert len(self.app.race_state_hashes) == 3
        assert self.app.race_finished is False
        assert self.app.race_winner is None

    # ── _step_race ──

    def _setup_running_race(self, num_rules=2):
        """Helper: set up a race with live cells and start it."""
        # Place a blinker
        self.app.grid.set_alive(10, 10)
        self.app.grid.set_alive(10, 11)
        self.app.grid.set_alive(10, 12)
        self.app._enter_race_mode()
        presets = list(RULE_PRESETS.keys())
        for name in presets[:num_rules]:
            p = RULE_PRESETS[name]
            self.app.race_selected_rules.append(
                (name, set(p["birth"]), set(p["survival"]))
            )
        self.app._start_race()

    def test_step_race_advances_generation(self):
        self._setup_running_race()
        gen_before = [g.generation for g in self.app.race_grids]
        self.app._step_race()
        for i, g in enumerate(self.app.race_grids):
            assert g.generation == gen_before[i] + 1

    def test_step_race_updates_pop_history(self):
        self._setup_running_race()
        for _ in range(5):
            self.app._step_race()
        for hist in self.app.race_pop_histories:
            # Initial pop + 5 steps = 6 entries
            assert len(hist) == 6

    def test_step_race_tracks_peak_pop(self):
        self._setup_running_race()
        for _ in range(20):
            self.app._step_race()
        for stats in self.app.race_stats:
            assert stats["peak_pop"] >= 0

    def test_step_race_detects_extinction(self):
        """A grid that goes to 0 population should record extinction."""
        self.app._enter_race_mode()
        presets = list(RULE_PRESETS.keys())
        for name in presets[:2]:
            p = RULE_PRESETS[name]
            self.app.race_selected_rules.append(
                (name, set(p["birth"]), set(p["survival"]))
            )
        self.app._start_race()
        self.app._step_race()
        for stats in self.app.race_stats:
            assert stats["extinction_gen"] is not None

    def test_step_race_extinct_grid_stays_frozen(self):
        """Once extinct, further steps should append 0 but not call g.step()."""
        self.app._enter_race_mode()
        presets = list(RULE_PRESETS.keys())
        for name in presets[:2]:
            p = RULE_PRESETS[name]
            self.app.race_selected_rules.append(
                (name, set(p["birth"]), set(p["survival"]))
            )
        self.app._start_race()
        self.app._step_race()
        gen_after_extinct = [g.generation for g in self.app.race_grids]
        self.app._step_race()
        for i, g in enumerate(self.app.race_grids):
            if self.app.race_stats[i]["extinction_gen"] is not None:
                assert g.generation == gen_after_extinct[i]

    def test_step_race_finishes_after_max_gens(self):
        self._setup_running_race()
        self.app.race_max_gens = 10
        for _ in range(15):
            self.app._step_race()
        assert self.app.race_finished is True
        assert self.app.race_winner is not None

    # ── _finish_race ──

    def test_finish_race_computes_scores(self):
        self._setup_running_race()
        self.app.race_max_gens = 5
        for _ in range(10):
            self.app._step_race()
        assert self.app.race_finished is True
        for stats in self.app.race_stats:
            assert "final_score" in stats
            assert isinstance(stats["final_score"], int)

    def test_finish_race_stops_running(self):
        self._setup_running_race()
        self.app.running = True
        self.app.race_max_gens = 3
        for _ in range(5):
            self.app._step_race()
        assert self.app.running is False

    def test_finish_race_winner_message(self):
        self._setup_running_race()
        self.app.race_max_gens = 3
        for _ in range(5):
            self.app._step_race()
        assert "Winner" in self.app.message
        assert self.app.race_winner != ""

    # ── Exit ──

    def test_exit_race_mode_clears_state(self):
        self._setup_running_race()
        for _ in range(3):
            self.app._step_race()
        self.app._exit_race_mode()
        assert self.app.race_mode is False
        assert self.app.race_grids == []
        assert self.app.race_pop_histories == []
        assert self.app.race_rule_menu is False
        assert self.app.race_selected_rules == []
        assert self.app.race_finished is False
        assert self.app.race_winner is None
        assert self.app.race_stats == []
        assert self.app.race_state_hashes == []
        assert "Race mode OFF" in self.app.message

    # ── Draw functions (smoke tests — just ensure no crash) ──

    @patch("curses.color_pair", return_value=0)
    def test_draw_race_rule_menu_no_crash(self, _mock_cp):
        self.app._enter_race_mode()
        self.app._draw_race_rule_menu(40, 120)

    @patch("curses.color_pair", return_value=0)
    def test_draw_race_no_grids_no_crash(self, _mock_cp):
        self.app.race_grids = []
        self.app._draw_race(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.modes.race_rules.color_for_age", return_value=0)
    def test_draw_race_with_grids_no_crash(self, _mock_cfa, _mock_cp):
        self._setup_running_race()
        for _ in range(3):
            self.app._step_race()
        self.app._draw_race(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.modes.race_rules.color_for_age", return_value=0)
    def test_draw_race_finished_no_crash(self, _mock_cfa, _mock_cp):
        self._setup_running_race()
        self.app.race_max_gens = 3
        for _ in range(5):
            self.app._step_race()
        assert self.app.race_finished
        self.app._draw_race(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.modes.race_rules.color_for_age", return_value=0)
    def test_draw_race_small_terminal_no_crash(self, _mock_cfa, _mock_cp):
        self._setup_running_race()
        self.app._draw_race(5, 10)

    @patch("curses.color_pair", return_value=0)
    @patch("life.modes.race_rules.color_for_age", return_value=0)
    def test_draw_race_four_grids_no_crash(self, _mock_cfa, _mock_cp):
        self._setup_running_race(num_rules=4)
        for _ in range(3):
            self.app._step_race()
        self.app._draw_race(40, 120)

    # ── Oscillation detection ──

    def test_oscillation_detected_for_blinker(self):
        """A blinker under Conway rules should be detected as period-2 oscillator."""
        conway_name = None
        for name, preset in RULE_PRESETS.items():
            if set(preset["birth"]) == {3} and set(preset["survival"]) == {2, 3}:
                conway_name = name
                break
        assert conway_name is not None, "Conway's Life preset not found"

        self.app.grid.set_alive(15, 15)
        self.app.grid.set_alive(15, 16)
        self.app.grid.set_alive(15, 17)
        self.app._enter_race_mode()
        p = RULE_PRESETS[conway_name]
        self.app.race_selected_rules.append(
            (conway_name, set(p["birth"]), set(p["survival"]))
        )
        presets = list(RULE_PRESETS.keys())
        other = [n for n in presets if n != conway_name][0]
        p2 = RULE_PRESETS[other]
        self.app.race_selected_rules.append(
            (other, set(p2["birth"]), set(p2["survival"]))
        )
        self.app._start_race()
        for _ in range(10):
            self.app._step_race()
        assert self.app.race_stats[0]["osc_period"] == 2
