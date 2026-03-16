"""Tests for wolfram mode."""
import curses
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.wolfram import register


class TestWolfram:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_wolfram_mode()
        assert self.app.wolfram_menu is True
        assert self.app.wolfram_menu_sel == 0

    def test_init_center_seed(self):
        self.app.wolfram_mode = True
        self.app.wolfram_seed_mode = "center"
        self.app._wolfram_init()
        assert len(self.app.wolfram_rows) == 1
        row0 = self.app.wolfram_rows[0]
        assert row0[len(row0) // 2] == 1
        assert sum(row0) == 1

    def test_init_random_seed(self):
        self.app.wolfram_mode = True
        self.app.wolfram_seed_mode = "random"
        self.app._wolfram_init()
        assert len(self.app.wolfram_rows) == 1
        # Random seed should have at least some alive cells
        assert len(self.app.wolfram_rows[0]) > 0

    def test_init_gol_row_seed_empty_grid(self):
        """GoL row seed with empty grid should fall back to center cell."""
        self.app.wolfram_mode = True
        self.app.wolfram_seed_mode = "gol_row"
        self.app._wolfram_init()
        assert len(self.app.wolfram_rows) == 1
        row0 = self.app.wolfram_rows[0]
        # Empty grid -> fallback to center
        assert row0[len(row0) // 2] == 1
        assert sum(row0) == 1

    def test_init_gol_row_seed_with_cells(self):
        """GoL row seed with alive cells in the grid should pick them up."""
        self.app.wolfram_mode = True
        self.app.wolfram_seed_mode = "gol_row"
        mid_r = self.app.grid.rows // 2
        # Set some cells alive in the middle row
        self.app.grid.set_alive(mid_r, 0)
        self.app.grid.set_alive(mid_r, 5)
        self.app.grid.set_alive(mid_r, 10)
        self.app._wolfram_init()
        row0 = self.app.wolfram_rows[0]
        assert row0[0] == 1
        assert row0[5] == 1
        assert row0[10] == 1
        assert sum(row0) == 3

    def test_init_width_from_terminal(self):
        """Width should be terminal width minus 2."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        expected_width = 120 - 2  # MockStdscr cols=120
        assert self.app.wolfram_width == expected_width
        assert len(self.app.wolfram_rows[0]) == expected_width

    def test_init_width_minimum(self):
        """Width should be at least 10 even if terminal is tiny."""
        from tests.conftest import MockStdscr
        self.app.stdscr = MockStdscr(rows=5, cols=8)
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        assert self.app.wolfram_width == 10

    def test_step_no_crash(self):
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        for _ in range(10):
            self.app._wolfram_step()
        assert len(self.app.wolfram_rows) == 11

    def test_step_empty_rows_noop(self):
        """Step on empty wolfram_rows should not crash."""
        self.app.wolfram_rows = []
        self.app._wolfram_step()
        assert self.app.wolfram_rows == []

    def test_step_rule_30_deterministic(self):
        random.seed(42)
        self.app.wolfram_mode = True
        self.app.wolfram_rule = 30
        self.app.wolfram_seed_mode = "center"
        self.app._wolfram_init()
        self.app._wolfram_step()
        # Rule 30 from center seed: 010 -> second row should have 111
        row1 = self.app.wolfram_rows[1]
        w = len(row1)
        mid = w // 2
        assert row1[mid - 1] == 1
        assert row1[mid] == 1
        assert row1[mid + 1] == 1

    def test_apply_rule(self):
        # Rule 30: binary 00011110
        assert self.app._wolfram_apply_rule(30, 0, 0, 0) == 0
        assert self.app._wolfram_apply_rule(30, 0, 0, 1) == 1
        assert self.app._wolfram_apply_rule(30, 0, 1, 0) == 1
        assert self.app._wolfram_apply_rule(30, 0, 1, 1) == 1
        assert self.app._wolfram_apply_rule(30, 1, 0, 0) == 1
        assert self.app._wolfram_apply_rule(30, 1, 0, 1) == 0
        assert self.app._wolfram_apply_rule(30, 1, 1, 0) == 0
        assert self.app._wolfram_apply_rule(30, 1, 1, 1) == 0

    def test_exit_cleanup(self):
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app._wolfram_step()
        self.app._exit_wolfram_mode()
        assert self.app.wolfram_mode is False
        assert self.app.wolfram_menu is False
        assert self.app.wolfram_running is False
        assert self.app.wolfram_rows == []


class TestApplyRuleExhaustive:
    """Verify _wolfram_apply_rule against known truth tables for several rules."""

    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))

    def _truth_table(self, rule_num):
        """Return the expected outputs for all 8 input patterns of a rule.

        Patterns are ordered: 000, 001, 010, 011, 100, 101, 110, 111
        (index 0-7) matching the bit positions in the rule number.
        """
        return [(rule_num >> i) & 1 for i in range(8)]

    @pytest.mark.parametrize("rule_num", [0, 30, 54, 73, 90, 110, 150, 184, 255])
    def test_all_inputs_match_truth_table(self, rule_num):
        expected = self._truth_table(rule_num)
        inputs = [
            (0, 0, 0),  # idx 0
            (0, 0, 1),  # idx 1
            (0, 1, 0),  # idx 2
            (0, 1, 1),  # idx 3
            (1, 0, 0),  # idx 4
            (1, 0, 1),  # idx 5
            (1, 1, 0),  # idx 6
            (1, 1, 1),  # idx 7
        ]
        for i, (l, c, r) in enumerate(inputs):
            result = self.app._wolfram_apply_rule(rule_num, l, c, r)
            assert result == expected[i], (
                f"Rule {rule_num}: input ({l},{c},{r}) expected {expected[i]} got {result}"
            )


class TestRule30KnownOutput:
    """Verify Rule 30 produces the correct output for a small grid with known initial conditions.

    Reference: Wolfram MathWorld / A New Kind of Science, Chapter 2.
    Starting from a single center cell on a width-11 grid with wrapping:
    Gen 0: ...0 0 0 0 0 1 0 0 0 0 0...
    Gen 1: ...0 0 0 0 1 1 1 0 0 0 0...
    Gen 2: ...0 0 0 1 1 0 0 1 0 0 0...
    Gen 3: ...0 0 1 1 0 1 1 1 1 0 0...
    Gen 4: ...0 1 1 0 0 1 0 0 0 1 0...
    """

    def setup_method(self):
        self.app = make_mock_app(cols=13)  # width = 13-2 = 11
        register(type(self.app))
        self.app.wolfram_rule = 30
        self.app.wolfram_seed_mode = "center"
        self.app._wolfram_init()
        assert self.app.wolfram_width == 11

    def test_gen0(self):
        assert self.app.wolfram_rows[0] == [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0]

    def test_gen1(self):
        self.app._wolfram_step()
        assert self.app.wolfram_rows[1] == [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0]

    def test_gen2(self):
        for _ in range(2):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[2] == [0, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0]

    def test_gen3(self):
        for _ in range(3):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[3] == [0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0]

    def test_gen4(self):
        for _ in range(4):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[4] == [0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0]


class TestRule90Sierpinski:
    """Rule 90 (XOR rule) should produce Sierpinski triangle pattern.

    Rule 90: new = left XOR right. From center seed on width-11 grid:
    Gen 0: 00000100000
    Gen 1: 00001010000
    Gen 2: 00010001000
    Gen 3: 00101010100
    Gen 4: 01000000010
    """

    def setup_method(self):
        self.app = make_mock_app(cols=13)  # width = 11
        register(type(self.app))
        self.app.wolfram_rule = 90
        self.app.wolfram_seed_mode = "center"
        self.app._wolfram_init()

    def test_gen0(self):
        assert self.app.wolfram_rows[0] == [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0]

    def test_gen1(self):
        self.app._wolfram_step()
        assert self.app.wolfram_rows[1] == [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0]

    def test_gen2(self):
        for _ in range(2):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[2] == [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]

    def test_gen3(self):
        for _ in range(3):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[3] == [0, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0]

    def test_gen4(self):
        for _ in range(4):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[4] == [0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0]


class TestRule110:
    """Rule 110 is Turing-complete. Verify first few generations from center seed.

    Rule 110 = 01101110 in binary.
    Width-11 grid from center seed:
    Gen 0: 00000100000
    Gen 1: 00001100000  (Rule 110: 010->1, 001->1, 000->0)
    Gen 2: 00011100000
    Gen 3: 00110100000
    """

    def setup_method(self):
        self.app = make_mock_app(cols=13)  # width = 11
        register(type(self.app))
        self.app.wolfram_rule = 110
        self.app.wolfram_seed_mode = "center"
        self.app._wolfram_init()

    def test_gen1(self):
        self.app._wolfram_step()
        assert self.app.wolfram_rows[1] == [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0]

    def test_gen2(self):
        for _ in range(2):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[2] == [0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0]

    def test_gen3(self):
        for _ in range(3):
            self.app._wolfram_step()
        assert self.app.wolfram_rows[3] == [0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0]


class TestTrivialRules:
    """Rule 0 kills everything, Rule 255 fills everything."""

    def setup_method(self):
        self.app = make_mock_app(cols=13)  # width = 11
        register(type(self.app))
        self.app.wolfram_seed_mode = "center"

    def test_rule_0_kills_all(self):
        self.app.wolfram_rule = 0
        self.app._wolfram_init()
        self.app._wolfram_step()
        assert sum(self.app.wolfram_rows[1]) == 0

    def test_rule_255_fills_all(self):
        self.app.wolfram_rule = 255
        self.app._wolfram_init()
        self.app._wolfram_step()
        assert sum(self.app.wolfram_rows[1]) == 11  # all cells alive


class TestWrappingBehavior:
    """Verify that the automaton wraps around at edges."""

    def setup_method(self):
        self.app = make_mock_app(cols=9)  # width = 7
        register(type(self.app))

    def test_wrap_left_edge(self):
        """A cell at position 0 should see the rightmost cell as its left neighbor."""
        self.app.wolfram_rule = 90  # XOR: new = left XOR right
        self.app.wolfram_rows = [[1, 0, 0, 0, 0, 0, 0]]
        self.app._wolfram_step()
        row1 = self.app.wolfram_rows[1]
        # Position 0: left=row[6]=0, center=1, right=row[1]=0 -> 010 for rule 90 -> 0
        # Position 1: left=row[0]=1, center=0, right=row[2]=0 -> 100 for rule 90 -> 0
        # Position 6: left=row[5]=0, center=0, right=row[0]=1 -> 001 for rule 90 -> 0
        # Wait, let's check rule 90 truth table:
        # 90 = 01011010
        # idx 0 (000) -> 0, idx 1 (001) -> 1, idx 2 (010) -> 0, idx 3 (011) -> 1
        # idx 4 (100) -> 1, idx 5 (101) -> 0, idx 6 (110) -> 1, idx 7 (111) -> 0
        # Position 0: left=0, center=1, right=0 -> idx=010=2 -> 0
        # But wait, rule 90: left XOR right. So pos 0: 0 XOR 0 = 0
        # Position 6: left=0, center=0, right=1 -> idx=001=1 -> 1
        assert row1[6] == 1  # wrapping causes right neighbor of pos 6 = pos 0

    def test_wrap_right_edge(self):
        """A cell at the last position should see position 0 as its right neighbor."""
        self.app.wolfram_rule = 90
        self.app.wolfram_rows = [[0, 0, 0, 0, 0, 0, 1]]
        self.app._wolfram_step()
        row1 = self.app.wolfram_rows[1]
        # Position 0: left=row[6]=1, center=0, right=row[1]=0 -> idx=100=4 -> 1
        assert row1[0] == 1  # wrapping causes left neighbor of pos 0 = pos 6


class TestKeyHandling:
    """Test key handling in wolfram mode."""

    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))

    def test_handle_key_minus1_noop(self):
        """Key -1 should be handled but do nothing."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        assert self.app._handle_wolfram_key(-1) is True

    def test_handle_key_quit(self):
        """Pressing q should exit wolfram mode."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("q"))
        assert self.app.wolfram_mode is False

    def test_handle_key_escape(self):
        """Pressing Escape should exit wolfram mode."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app._handle_wolfram_key(27)
        assert self.app.wolfram_mode is False

    def test_handle_key_space_toggle(self):
        """Space toggles running state."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        assert self.app.wolfram_running is False
        self.app._handle_wolfram_key(ord(" "))
        assert self.app.wolfram_running is True
        self.app._handle_wolfram_key(ord(" "))
        assert self.app.wolfram_running is False

    def test_handle_key_n_step(self):
        """Pressing n should advance one step."""
        self.app.wolfram_mode = True
        self.app.wolfram_rule = 30
        self.app.wolfram_seed_mode = "center"
        self.app._wolfram_init()
        assert len(self.app.wolfram_rows) == 1
        self.app._handle_wolfram_key(ord("n"))
        assert len(self.app.wolfram_rows) == 2
        # n also pauses
        self.app.wolfram_running = True
        self.app._handle_wolfram_key(ord("n"))
        assert self.app.wolfram_running is False

    def test_handle_key_dot_step(self):
        """Pressing . should also advance one step."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("."))
        assert len(self.app.wolfram_rows) == 2

    def test_handle_key_r_reset(self):
        """Pressing r should reset the automaton."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        for _ in range(5):
            self.app._wolfram_step()
        assert len(self.app.wolfram_rows) == 6
        self.app._handle_wolfram_key(ord("r"))
        assert len(self.app.wolfram_rows) == 1

    def test_handle_key_R_opens_menu(self):
        """Pressing R should open the rule menu."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("R"))
        assert self.app.wolfram_menu is True
        assert self.app.wolfram_mode is False

    def test_handle_key_m_opens_menu(self):
        """Pressing m should also open the rule menu."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("m"))
        assert self.app.wolfram_menu is True
        assert self.app.wolfram_mode is False

    def test_handle_key_right_increments_rule(self):
        """Right arrow or l should increment the rule."""
        self.app.wolfram_mode = True
        self.app.wolfram_rule = 30
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("l"))
        assert self.app.wolfram_rule == 31

    def test_handle_key_left_decrements_rule(self):
        """Left arrow or h should decrement the rule."""
        self.app.wolfram_mode = True
        self.app.wolfram_rule = 30
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("h"))
        assert self.app.wolfram_rule == 29

    def test_handle_key_left_at_zero(self):
        """Rule 0 should not go below 0."""
        self.app.wolfram_mode = True
        self.app.wolfram_rule = 0
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("h"))
        assert self.app.wolfram_rule == 0

    def test_handle_key_right_at_255(self):
        """Rule 255 should not go above 255."""
        self.app.wolfram_mode = True
        self.app.wolfram_rule = 255
        self.app._wolfram_init()
        self.app._handle_wolfram_key(ord("l"))
        assert self.app.wolfram_rule == 255

    def test_handle_key_speed_increase(self):
        """Pressing > should increase speed."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        initial_speed = self.app.speed_idx
        self.app._handle_wolfram_key(ord(">"))
        assert self.app.speed_idx == initial_speed + 1

    def test_handle_key_speed_decrease(self):
        """Pressing < should decrease speed."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app.speed_idx = 3
        self.app._handle_wolfram_key(ord("<"))
        assert self.app.speed_idx == 2

    def test_handle_key_speed_min_clamp(self):
        """Speed should not go below 0."""
        self.app.wolfram_mode = True
        self.app._wolfram_init()
        self.app.speed_idx = 0
        self.app._handle_wolfram_key(ord("<"))
        assert self.app.speed_idx == 0


class TestMenuKeyHandling:
    """Test key handling in the Wolfram rule menu."""

    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))
        self.app._enter_wolfram_mode()

    def test_menu_key_minus1_noop(self):
        assert self.app._handle_wolfram_menu_key(-1) is True

    def test_menu_navigate_down(self):
        assert self.app.wolfram_menu_sel == 0
        self.app._handle_wolfram_menu_key(ord("j"))
        assert self.app.wolfram_menu_sel == 1

    def test_menu_navigate_up(self):
        self.app.wolfram_menu_sel = 2
        self.app._handle_wolfram_menu_key(ord("k"))
        assert self.app.wolfram_menu_sel == 1

    def test_menu_navigate_wraps(self):
        """Navigation should wrap around."""
        n = len(self.app.WOLFRAM_PRESETS) + 3
        self.app.wolfram_menu_sel = 0
        self.app._handle_wolfram_menu_key(ord("k"))
        assert self.app.wolfram_menu_sel == n - 1

    def test_menu_quit(self):
        self.app._handle_wolfram_menu_key(ord("q"))
        assert self.app.wolfram_menu is False

    def test_menu_escape(self):
        self.app._handle_wolfram_menu_key(27)
        assert self.app.wolfram_menu is False

    def test_menu_select_preset(self):
        """Selecting a preset should set the rule and start the automaton."""
        self.app.wolfram_menu_sel = 0  # Rule 30
        self.app._handle_wolfram_menu_key(10)  # Enter
        assert self.app.wolfram_rule == 30
        assert self.app.wolfram_mode is True
        assert self.app.wolfram_menu is False
        assert len(self.app.wolfram_rows) == 1

    def test_menu_select_second_preset(self):
        """Selecting preset index 1 should pick Rule 90."""
        self.app.wolfram_menu_sel = 1  # Rule 90
        self.app._handle_wolfram_menu_key(10)
        assert self.app.wolfram_rule == 90

    def test_menu_toggle_seed_mode(self):
        """Selecting the seed toggle item should cycle seed modes."""
        n = len(self.app.WOLFRAM_PRESETS)
        self.app.wolfram_menu_sel = n + 1  # seed toggle
        assert self.app.wolfram_seed_mode == "center"
        self.app._handle_wolfram_menu_key(10)
        assert self.app.wolfram_seed_mode == "gol_row"
        self.app._handle_wolfram_menu_key(10)
        assert self.app.wolfram_seed_mode == "random"
        self.app._handle_wolfram_menu_key(10)
        assert self.app.wolfram_seed_mode == "center"

    def test_menu_start_button(self):
        """Selecting the start button should launch the automaton with current settings."""
        n = len(self.app.WOLFRAM_PRESETS)
        self.app.wolfram_rule = 110
        self.app.wolfram_menu_sel = n + 2  # Start button
        self.app._handle_wolfram_menu_key(10)
        assert self.app.wolfram_mode is True
        assert self.app.wolfram_menu is False
        assert self.app.wolfram_rule == 110

    def test_menu_custom_rule_none(self):
        """Custom rule with cancelled prompt should not change anything."""
        n = len(self.app.WOLFRAM_PRESETS)
        self.app.wolfram_menu_sel = n  # Custom rule input
        self.app.wolfram_rule = 30
        self.app._handle_wolfram_menu_key(10)
        # _prompt_text returns None by default in mock, so rule unchanged
        assert self.app.wolfram_rule == 30
        assert self.app.wolfram_menu is True  # stays in menu


class TestRegister:
    """Verify that register() binds all expected functions."""

    def test_all_methods_bound(self):
        app = make_mock_app()
        register(type(app))
        methods = [
            "_wolfram_apply_rule",
            "_wolfram_init",
            "_wolfram_step",
            "_enter_wolfram_mode",
            "_exit_wolfram_mode",
            "_handle_wolfram_menu_key",
            "_handle_wolfram_key",
            "_draw_wolfram_menu",
            "_draw_wolfram",
        ]
        for name in methods:
            assert hasattr(app, name), f"Missing method: {name}"
            assert callable(getattr(app, name)), f"Not callable: {name}"


class TestDeterminism:
    """Verify that the same seed and rule produce identical output across runs."""

    def setup_method(self):
        self.app = make_mock_app(cols=22)  # width = 20
        register(type(self.app))

    def _run_generations(self, rule, n_gens):
        self.app.wolfram_rule = rule
        self.app.wolfram_seed_mode = "center"
        self.app._wolfram_init()
        for _ in range(n_gens):
            self.app._wolfram_step()
        return [row[:] for row in self.app.wolfram_rows]

    def test_rule_30_reproducible(self):
        rows_a = self._run_generations(30, 20)
        rows_b = self._run_generations(30, 20)
        assert rows_a == rows_b

    def test_rule_110_reproducible(self):
        rows_a = self._run_generations(110, 20)
        rows_b = self._run_generations(110, 20)
        assert rows_a == rows_b
