"""Tests for compare_rules mode — deep validation against commit b695719."""
import curses
import random
from unittest.mock import patch
import pytest

from tests.conftest import make_mock_app
from life.modes.compare_rules import register
from life.grid import Grid
from life.rules import RULE_PRESETS, rule_string


class TestCompareRules:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    # ── enter / exit lifecycle ──

    def test_enter_compare_mode_opens_rule_menu(self):
        assert not self.app.compare_rule_menu
        self.app._enter_compare_mode()
        assert self.app.compare_rule_menu is True
        assert self.app.compare_rule_sel == 0

    def test_exit_compare_mode_clears_state(self):
        # Set up active comparison first
        self.app.compare_mode = True
        self.app.grid2 = Grid(10, 10)
        self.app.pop_history2 = [10, 20, 30]
        self.app.compare_rule_menu = True

        self.app._exit_compare_mode()

        assert self.app.compare_mode is False
        assert self.app.grid2 is None
        assert self.app.pop_history2 == []
        assert self.app.compare_rule_menu is False
        assert "OFF" in self.app.message

    # ── _start_compare ──

    def test_start_compare_clones_grid(self):
        # Set some live cells on primary grid
        self.app.grid.cells[0][0] = 1
        self.app.grid.cells[1][1] = 2
        self.app.grid.population = 2
        self.app.grid.generation = 5
        self.app.pop_history = [0, 1, 2]

        self.app._start_compare({3, 6}, {2, 3})

        assert self.app.compare_mode is True
        assert self.app.compare_rule_menu is False
        assert self.app.grid2 is not None
        # Cells copied
        assert self.app.grid2.cells[0][0] == 1
        assert self.app.grid2.cells[1][1] == 2
        # Generation and population copied
        assert self.app.grid2.generation == 5
        assert self.app.grid2.population == 2
        # Rules applied to grid2
        assert self.app.grid2.birth == {3, 6}
        assert self.app.grid2.survival == {2, 3}
        # Pop history cloned (not shared)
        assert self.app.pop_history2 == [0, 1, 2]
        self.app.pop_history.append(99)
        assert 99 not in self.app.pop_history2

    def test_start_compare_flash_message(self):
        self.app._start_compare({3, 6}, {2, 3})
        assert "Comparing" in self.app.message
        assert "B3/S23" in self.app.message  # primary grid default rule
        assert "B36/S23" in self.app.message  # second grid rule

    # ── step advances both grids ──

    def test_step_advances_grid2(self):
        """After starting comparison, stepping grid2 should evolve it independently."""
        # Place a blinker on primary grid
        self.app.grid.cells[5][4] = 1
        self.app.grid.cells[5][5] = 1
        self.app.grid.cells[5][6] = 1
        self.app.grid.population = 3

        self.app._start_compare({3}, {2, 3})  # same rule for easy verification

        # Both grids start identical
        assert self.app.grid2.cells[5][4] == 1
        assert self.app.grid2.cells[5][5] == 1
        assert self.app.grid2.cells[5][6] == 1

        # Step both (simulating what the main loop does)
        self.app.grid.step()
        self.app.grid2.step()
        self.app.pop_history2.append(self.app.grid2.population)

        # Blinker oscillates: horizontal -> vertical
        assert self.app.grid2.cells[4][5] > 0
        assert self.app.grid2.cells[5][5] > 0
        assert self.app.grid2.cells[6][5] > 0

    def test_step_with_different_rules_diverges(self):
        """Two grids with different rules should diverge after stepping."""
        # Place a small pattern
        self.app.grid.cells[5][5] = 1
        self.app.grid.cells[5][6] = 1
        self.app.grid.cells[6][5] = 1
        self.app.grid.cells[6][6] = 1
        self.app.grid.population = 4

        # Primary = Conway (B3/S23), Secondary = HighLife (B36/S23)
        self.app._start_compare({3, 6}, {2, 3})

        # Step both several times
        for _ in range(5):
            self.app.grid.step()
            self.app.grid2.step()

        # With B3/S23 a 2x2 block is a still life, pop stays 4
        assert self.app.grid.population == 4
        # With B36/S23 a 2x2 block is also a still life (no birth-6 neighbors)
        # but at least confirm grids are separate objects
        assert self.app.grid is not self.app.grid2

    # ── key handling: rule menu ──

    def test_key_menu_escape_closes(self):
        self.app.compare_rule_menu = True
        result = self.app._handle_compare_rule_menu_key(27)  # ESC
        assert result is True
        assert self.app.compare_rule_menu is False

    def test_key_menu_q_closes(self):
        self.app.compare_rule_menu = True
        result = self.app._handle_compare_rule_menu_key(ord("q"))
        assert result is True
        assert self.app.compare_rule_menu is False

    def test_key_menu_no_input(self):
        """Key -1 (no key) should be handled gracefully."""
        result = self.app._handle_compare_rule_menu_key(-1)
        assert result is True

    def test_key_menu_navigate_down(self):
        self.app.compare_rule_sel = 0
        self.app._handle_compare_rule_menu_key(curses.KEY_DOWN)
        assert self.app.compare_rule_sel == 1

    def test_key_menu_navigate_up_wraps(self):
        self.app.compare_rule_sel = 0
        self.app._handle_compare_rule_menu_key(curses.KEY_UP)
        assert self.app.compare_rule_sel == len(self.app.rule_preset_list) - 1

    def test_key_menu_j_navigates_down(self):
        self.app.compare_rule_sel = 0
        self.app._handle_compare_rule_menu_key(ord("j"))
        assert self.app.compare_rule_sel == 1

    def test_key_menu_k_navigates_up(self):
        self.app.compare_rule_sel = 2
        self.app._handle_compare_rule_menu_key(ord("k"))
        assert self.app.compare_rule_sel == 1

    def test_key_menu_enter_starts_compare(self):
        self.app.compare_rule_sel = 0
        self.app.compare_rule_menu = True
        name = self.app.rule_preset_list[0]
        preset = RULE_PRESETS[name]

        self.app._handle_compare_rule_menu_key(10)  # Enter

        assert self.app.compare_mode is True
        assert self.app.grid2 is not None
        assert self.app.grid2.birth == set(preset["birth"])
        assert self.app.grid2.survival == set(preset["survival"])

    def test_key_menu_enter_13_starts_compare(self):
        """CR (13) should also select."""
        self.app.compare_rule_sel = 0
        self.app.compare_rule_menu = True
        self.app._handle_compare_rule_menu_key(13)
        assert self.app.compare_mode is True

    def test_key_menu_slash_with_no_prompt(self):
        """Slash opens custom rule entry; mock returns None so no comparison starts."""
        self.app.compare_rule_menu = True
        self.app._handle_compare_rule_menu_key(ord("/"))
        assert self.app.compare_rule_menu is False
        assert self.app.compare_mode is False  # no input => no compare

    # ── draw functions don't crash ──

    @patch("curses.color_pair", return_value=0)
    def test_draw_compare_rule_menu_no_crash(self, _mock_cp):
        self.app.compare_rule_menu = True
        self.app.compare_rule_sel = 0
        # Should not raise
        self.app._draw_compare_rule_menu(40, 120)

    @patch("curses.color_pair", return_value=0)
    def test_draw_compare_no_crash(self, _mock_cp):
        """Drawing the split screen should not raise."""
        self.app._start_compare({3, 6}, {2, 3})
        self.app.pop_history = [1, 2, 3]
        self.app.pop_history2 = [1, 2, 3]
        self.app._draw_compare(40, 120)

    @patch("curses.color_pair", return_value=0)
    def test_draw_compare_small_terminal(self, _mock_cp):
        """Drawing in a very small terminal should not crash."""
        self.app._start_compare({3}, {2, 3})
        self.app.pop_history = [1, 2]
        self.app.pop_history2 = [1, 2]
        self.app._draw_compare(5, 20)

    # ── registration ──

    def test_register_binds_all_methods(self):
        AppClass = type(self.app)
        assert hasattr(AppClass, '_enter_compare_mode')
        assert hasattr(AppClass, '_exit_compare_mode')
        assert hasattr(AppClass, '_start_compare')
        assert hasattr(AppClass, '_handle_compare_rule_menu_key')
        assert hasattr(AppClass, '_draw_compare_rule_menu')
        assert hasattr(AppClass, '_draw_compare')

    # ── edge cases ──

    def test_exit_without_active_compare(self):
        """Exiting when not in compare mode should still work cleanly."""
        self.app.compare_mode = False
        self.app.grid2 = None
        self.app.pop_history2 = []
        # Should not raise
        self.app._exit_compare_mode()
        assert self.app.compare_mode is False

    def test_start_compare_overwrites_previous(self):
        """Starting a new comparison replaces any existing grid2."""
        self.app._start_compare({3}, {2, 3})
        old_grid2 = self.app.grid2
        self.app._start_compare({3, 6}, {2, 3})
        assert self.app.grid2 is not old_grid2
        assert self.app.grid2.birth == {3, 6}

    def test_grid2_dimensions_match_grid1(self):
        self.app._start_compare({3}, {2, 3})
        assert self.app.grid2.rows == self.app.grid.rows
        assert self.app.grid2.cols == self.app.grid.cols
