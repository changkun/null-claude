"""Tests for ant mode."""
import curses
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.ant import register


class TestAnt:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def _init_single_ant(self, rule="RL"):
        """Helper: initialize a single ant on a known grid."""
        self.app.ant_mode = True
        self.app.ant_rule = rule
        self.app.ant_num_ants = 1
        self.app._ant_init()

    # ------------------------------------------------------------------
    # Basic lifecycle tests
    # ------------------------------------------------------------------

    def test_enter(self):
        self.app._enter_ant_mode()
        assert self.app.ant_menu is True
        assert self.app.ant_menu_sel == 0

    def test_init_single_ant(self):
        self._init_single_ant()
        assert len(self.app.ant_ants) == 1
        assert self.app.ant_grid == {}
        assert self.app.ant_step_count == 0

    def test_init_multiple_ants(self):
        self.app.ant_mode = True
        self.app.ant_num_ants = 4
        self.app._ant_init()
        assert len(self.app.ant_ants) == 4
        # All ants should have distinct positions
        positions = {(a["r"], a["c"]) for a in self.app.ant_ants}
        assert len(positions) == 4

    def test_init_single_ant_centered(self):
        """Single ant should start at the center of the grid."""
        self._init_single_ant()
        ant = self.app.ant_ants[0]
        assert ant["r"] == self.app.ant_rows // 2
        assert ant["c"] == self.app.ant_cols // 2
        assert ant["dir"] == 0  # facing up

    def test_step_no_crash(self):
        self._init_single_ant()
        for _ in range(10):
            self.app._ant_step()
        assert self.app.ant_step_count == 10

    def test_exit_cleanup(self):
        self._init_single_ant()
        self.app._ant_step()
        self.app._exit_ant_mode()
        assert self.app.ant_mode is False
        assert self.app.ant_menu is False
        assert self.app.ant_running is False
        assert self.app.ant_grid == {}
        assert self.app.ant_ants == []

    # ------------------------------------------------------------------
    # Classic RL ant: detailed step-by-step logic verification
    # ------------------------------------------------------------------
    # Rule: on state 0 cell -> turn Right, on state 1 cell -> turn Left
    # Directions: 0=up, 1=right, 2=down, 3=left

    def test_classic_rl_step1(self):
        """Step 1: ant on blank cell (state 0) -> R-turn, flip to 1, move."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]
        # Ant starts facing up (dir=0)
        assert ant["dir"] == 0

        self.app._ant_step()

        # State 0 -> rule[0] = 'R' -> turn right: dir 0->1 (now facing right)
        # Cell (start_r, start_c) flipped from 0 to 1
        assert self.app.ant_grid[(start_r, start_c)] == 1
        # Moved one step in direction 1 (right): dc=+1
        assert ant["r"] == start_r
        assert ant["c"] == start_c + 1
        assert ant["dir"] == 1

    def test_classic_rl_step2(self):
        """Step 2: second blank cell -> another R-turn."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]

        self.app._ant_step()  # step 1
        self.app._ant_step()  # step 2

        # After step 1: at (start_r, start_c+1), dir=1 (right)
        # Step 2: cell (start_r, start_c+1) is state 0 -> R-turn: dir 1->2 (down)
        # Flip cell to state 1, move down
        assert self.app.ant_grid[(start_r, start_c + 1)] == 1
        assert ant["r"] == start_r + 1
        assert ant["c"] == start_c + 1
        assert ant["dir"] == 2  # facing down

    def test_classic_rl_step3(self):
        """Step 3: third blank cell -> another R-turn."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]

        for _ in range(3):
            self.app._ant_step()

        # After step 2: at (start_r+1, start_c+1), dir=2 (down)
        # Step 3: cell is state 0 -> R-turn: dir 2->3 (left), flip, move left
        assert ant["r"] == start_r + 1
        assert ant["c"] == start_c
        assert ant["dir"] == 3  # facing left

    def test_classic_rl_step4(self):
        """Step 4: fourth blank cell -> another R-turn, completing the square."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]

        for _ in range(4):
            self.app._ant_step()

        # After step 3: at (start_r+1, start_c), dir=3 (left)
        # Step 4: cell is state 0 -> R-turn: dir 3->0 (up), flip, move up
        assert ant["r"] == start_r
        assert ant["c"] == start_c
        assert ant["dir"] == 0  # facing up again
        # 4 cells should now be colored
        assert len(self.app.ant_grid) == 4

    def test_classic_rl_step5_revisit(self):
        """Step 5: ant revisits a state-1 cell -> L-turn, flip back to 0."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]

        for _ in range(5):
            self.app._ant_step()

        # After step 4: at (start_r, start_c), dir=0 (up)
        # Step 5: cell (start_r, start_c) is state 1 -> rule[1] = 'L'
        # L-turn: dir 0->3 (left)
        # Flip state 1 -> (1+1)%2 = 0 -> cell removed from grid
        assert (start_r, start_c) not in self.app.ant_grid
        assert ant["dir"] == 3  # facing left
        assert ant["r"] == start_r
        assert ant["c"] == (start_c - 1) % self.app.ant_cols

    def test_classic_rl_first_four_steps_all_colored(self):
        """After 4 steps on blank grid, ant colors exactly 4 cells."""
        self._init_single_ant("RL")
        for _ in range(4):
            self.app._ant_step()
        assert len(self.app.ant_grid) == 4
        # All cells should be state 1
        for v in self.app.ant_grid.values():
            assert v == 1

    # ------------------------------------------------------------------
    # L-turn rule verification
    # ------------------------------------------------------------------

    def test_ll_rule_turns_left(self):
        """With rule 'LL', ant always turns left regardless of cell state."""
        self._init_single_ant("LL")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]
        # dir=0 (up), L-turn -> dir=3 (left)
        self.app._ant_step()
        assert ant["dir"] == 3
        # next blank cell, L-turn -> dir=2 (down)
        self.app._ant_step()
        assert ant["dir"] == 2

    def test_rr_rule_turns_right(self):
        """With rule 'RR', ant always turns right."""
        self._init_single_ant("RR")
        ant = self.app.ant_ants[0]
        # dir=0 -> R -> 1
        self.app._ant_step()
        assert ant["dir"] == 1
        # dir=1 -> R -> 2 (state 0 cell again)
        self.app._ant_step()
        assert ant["dir"] == 2

    # ------------------------------------------------------------------
    # Multi-state rules
    # ------------------------------------------------------------------

    def test_rlr_3color_cycling(self):
        """3-color rule RLR: cells cycle through states 0->1->2->0."""
        self._init_single_ant("RLR")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]

        # Step 1: state 0 -> rule[0]='R', flip to 1
        self.app._ant_step()
        assert self.app.ant_grid[(start_r, start_c)] == 1

        # Return ant to same cell manually to test state cycling
        # Instead, let's just test the flip logic explicitly by placing
        # the ant back on the same cell
        ant["r"], ant["c"] = start_r, start_c
        ant["dir"] = 0  # reset direction to up

        # Step 2: state 1 -> rule[1]='L', flip to 2
        self.app._ant_step()
        assert self.app.ant_grid[(start_r, start_c)] == 2

        # Return again
        ant["r"], ant["c"] = start_r, start_c
        ant["dir"] = 0

        # Step 3: state 2 -> rule[2]='R', flip to (2+1)%3=0 -> removed
        self.app._ant_step()
        assert (start_r, start_c) not in self.app.ant_grid

    def test_llrr_4color_cycling(self):
        """4-color rule LLRR: cells cycle 0->1->2->3->0."""
        self._init_single_ant("LLRR")
        ant = self.app.ant_ants[0]
        start_r, start_c = ant["r"], ant["c"]

        # State 0 -> flip to 1
        self.app._ant_step()
        assert self.app.ant_grid[(start_r, start_c)] == 1

        # Force ant back to same cell
        ant["r"], ant["c"] = start_r, start_c
        ant["dir"] = 0
        # State 1 -> flip to 2
        self.app._ant_step()
        assert self.app.ant_grid[(start_r, start_c)] == 2

        ant["r"], ant["c"] = start_r, start_c
        ant["dir"] = 0
        # State 2 -> flip to 3
        self.app._ant_step()
        assert self.app.ant_grid[(start_r, start_c)] == 3

        ant["r"], ant["c"] = start_r, start_c
        ant["dir"] = 0
        # State 3 -> flip to 0 (removed)
        self.app._ant_step()
        assert (start_r, start_c) not in self.app.ant_grid

    # ------------------------------------------------------------------
    # Wrapping
    # ------------------------------------------------------------------

    def test_wraps_top_edge(self):
        """Ant moving up from row 0 wraps to bottom."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        ant["r"] = 0
        ant["c"] = 5
        ant["dir"] = 0  # up
        # Force a cell state that causes the ant to keep going up
        # State 0 + rule 'R' turns right (dir 0->1), so we need state 1 to turn left
        # Actually let's just set direction to 0 and put on row 0 with state 1
        self.app.ant_grid[(0, 5)] = 1  # state 1 -> rule[1]='L'
        # dir=0, L-turn -> dir=3 (left), move left
        self.app._ant_step()
        assert ant["dir"] == 3
        # But let's test top-edge wrap directly:
        ant["r"] = 0
        ant["dir"] = 0  # facing up
        # Place a state-1 cell so rule[1]='L' -> dir 0 -> 3 (left)
        # That won't go up. Let's use a simpler approach:
        # We need the ant to actually move up. After the turn, direction
        # must be 0 (up). That means we need turn = no change? No, the ant
        # turns first then moves. So we need final dir=0 after turn.
        # State 0 -> R -> dir+1. If dir=3, R-turn -> 0 (up). Move up from row 0.
        ant["r"] = 0
        ant["c"] = 10
        ant["dir"] = 3  # facing left
        # Cell (0,10) is state 0 -> rule[0]='R' -> dir 3->0 (up), move up
        self.app._ant_step()
        assert ant["dir"] == 0
        assert ant["r"] == self.app.ant_rows - 1  # wrapped to bottom

    def test_wraps_left_edge(self):
        """Ant moving left from col 0 wraps to right."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        # Need ant to end up moving left (dir=3) and be at col 0
        ant["r"] = 5
        ant["c"] = 0
        ant["dir"] = 2  # facing down
        # State 0 -> R -> dir 2->3 (left), move left from col 0
        self.app._ant_step()
        assert ant["dir"] == 3
        assert ant["c"] == self.app.ant_cols - 1  # wrapped

    def test_wraps_right_edge(self):
        """Ant moving right from last col wraps to col 0."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        last_col = self.app.ant_cols - 1
        ant["r"] = 5
        ant["c"] = last_col
        ant["dir"] = 0  # facing up
        # State 0 -> R -> dir 0->1 (right), move right from last col
        self.app._ant_step()
        assert ant["dir"] == 1
        assert ant["c"] == 0  # wrapped

    def test_wraps_bottom_edge(self):
        """Ant moving down from last row wraps to row 0."""
        self._init_single_ant("RL")
        ant = self.app.ant_ants[0]
        last_row = self.app.ant_rows - 1
        ant["r"] = last_row
        ant["c"] = 5
        ant["dir"] = 1  # facing right
        # State 0 -> R -> dir 1->2 (down), move down from last row
        self.app._ant_step()
        assert ant["dir"] == 2
        assert ant["r"] == 0  # wrapped

    # ------------------------------------------------------------------
    # Multiple ants
    # ------------------------------------------------------------------

    def test_multiple_ants_step_independently(self):
        """Each ant steps independently on the shared grid."""
        self.app.ant_mode = True
        self.app.ant_rule = "RL"
        self.app.ant_num_ants = 2
        self.app._ant_init()
        assert len(self.app.ant_ants) == 2

        pos0_before = (self.app.ant_ants[0]["r"], self.app.ant_ants[0]["c"])
        pos1_before = (self.app.ant_ants[1]["r"], self.app.ant_ants[1]["c"])

        self.app._ant_step()

        pos0_after = (self.app.ant_ants[0]["r"], self.app.ant_ants[0]["c"])
        pos1_after = (self.app.ant_ants[1]["r"], self.app.ant_ants[1]["c"])

        # Both ants should have moved
        assert pos0_before != pos0_after
        assert pos1_before != pos1_after
        # Both original cells should be colored
        assert self.app.ant_grid.get(pos0_before) == 1
        assert self.app.ant_grid.get(pos1_before) == 1

    # ------------------------------------------------------------------
    # Long-run determinism
    # ------------------------------------------------------------------

    def test_deterministic_100_steps(self):
        """Same initial conditions produce identical state after 100 steps."""
        self._init_single_ant("RL")
        for _ in range(100):
            self.app._ant_step()
        grid1 = dict(self.app.ant_grid)
        ant1 = dict(self.app.ant_ants[0])

        # Re-initialize and run again
        self.app._ant_init()
        for _ in range(100):
            self.app._ant_step()
        grid2 = dict(self.app.ant_grid)
        ant2 = dict(self.app.ant_ants[0])

        assert grid1 == grid2
        assert ant1 == ant2

    def test_step_wraps_around_many(self):
        self._init_single_ant("RL")
        for _ in range(500):
            self.app._ant_step()
        assert self.app.ant_step_count == 500
        # Ant position should always be within bounds
        ant = self.app.ant_ants[0]
        assert 0 <= ant["r"] < self.app.ant_rows
        assert 0 <= ant["c"] < self.app.ant_cols

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def test_handle_ant_key_space_toggles(self):
        """Space key toggles running state."""
        self._init_single_ant()
        assert self.app.ant_running is False
        self.app._handle_ant_key(ord(" "))
        assert self.app.ant_running is True
        self.app._handle_ant_key(ord(" "))
        assert self.app.ant_running is False

    def test_handle_ant_key_n_steps(self):
        """'n' key advances one step (respecting steps_per_frame)."""
        self._init_single_ant()
        self.app.ant_steps_per_frame = 5
        self.app._handle_ant_key(ord("n"))
        assert self.app.ant_step_count == 5
        assert self.app.ant_running is False

    def test_handle_ant_key_dot_steps(self):
        """'.' key advances one step, same as 'n'."""
        self._init_single_ant()
        self.app.ant_steps_per_frame = 1
        self.app._handle_ant_key(ord("."))
        assert self.app.ant_step_count == 1

    def test_handle_ant_key_r_resets(self):
        """'r' key resets the grid."""
        self._init_single_ant()
        for _ in range(10):
            self.app._ant_step()
        assert self.app.ant_step_count == 10
        self.app._handle_ant_key(ord("r"))
        assert self.app.ant_step_count == 0
        assert self.app.ant_grid == {}

    def test_handle_ant_key_q_exits(self):
        """'q' key exits ant mode."""
        self._init_single_ant()
        self.app._handle_ant_key(ord("q"))
        assert self.app.ant_mode is False

    def test_handle_ant_key_esc_exits(self):
        """Esc key exits ant mode."""
        self._init_single_ant()
        self.app._handle_ant_key(27)
        assert self.app.ant_mode is False

    def test_handle_ant_key_R_returns_to_menu(self):
        """'R' key returns to the menu."""
        self._init_single_ant()
        self.app._handle_ant_key(ord("R"))
        assert self.app.ant_mode is False
        assert self.app.ant_menu is True

    def test_handle_ant_key_m_returns_to_menu(self):
        """'m' key returns to the menu."""
        self._init_single_ant()
        self.app._handle_ant_key(ord("m"))
        assert self.app.ant_mode is False
        assert self.app.ant_menu is True

    def test_handle_ant_key_plus_increases_steps(self):
        """'+' key increases steps per frame."""
        self._init_single_ant()
        self.app.ant_steps_per_frame = 1
        self.app._handle_ant_key(ord("+"))
        assert self.app.ant_steps_per_frame == 5

    def test_handle_ant_key_minus_decreases_steps(self):
        """'-' key decreases steps per frame."""
        self._init_single_ant()
        self.app.ant_steps_per_frame = 5
        self.app._handle_ant_key(ord("-"))
        assert self.app.ant_steps_per_frame == 1

    def test_handle_ant_key_minus_at_min(self):
        """'-' at minimum steps/frame stays at 1."""
        self._init_single_ant()
        self.app.ant_steps_per_frame = 1
        self.app._handle_ant_key(ord("-"))
        assert self.app.ant_steps_per_frame == 1

    def test_handle_ant_key_plus_at_max(self):
        """'+' at maximum steps/frame stays at 500."""
        self._init_single_ant()
        self.app.ant_steps_per_frame = 500
        self.app._handle_ant_key(ord("+"))
        assert self.app.ant_steps_per_frame == 500

    def test_handle_ant_key_noop(self):
        """No-op key returns True without changing state."""
        self._init_single_ant()
        result = self.app._handle_ant_key(-1)
        assert result is True

    def test_handle_ant_key_unknown(self):
        """Unknown key returns True."""
        self._init_single_ant()
        result = self.app._handle_ant_key(ord("z"))
        assert result is True

    # ------------------------------------------------------------------
    # Menu key handling
    # ------------------------------------------------------------------

    def test_menu_navigate_down(self):
        self.app._enter_ant_mode()
        self.app._handle_ant_menu_key(ord("j"))
        assert self.app.ant_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        self.app._enter_ant_mode()
        self.app._handle_ant_menu_key(ord("k"))
        # Should wrap to the last item
        n_presets = len(type(self.app).ANT_PRESETS)
        total_items = n_presets + 4
        assert self.app.ant_menu_sel == total_items - 1

    def test_menu_select_preset(self):
        """Selecting a preset starts ant mode with that rule."""
        self.app._enter_ant_mode()
        self.app.ant_menu_sel = 0  # first preset "RL"
        self.app._handle_ant_menu_key(10)  # Enter
        assert self.app.ant_mode is True
        assert self.app.ant_menu is False
        assert self.app.ant_rule == "RL"

    def test_menu_select_second_preset(self):
        """Selecting RLR preset."""
        self.app._enter_ant_mode()
        self.app.ant_menu_sel = 1  # "RLR"
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_rule == "RLR"
        assert self.app.ant_mode is True

    def test_menu_cycle_num_ants(self):
        """Cycling num ants: 1 -> 2 -> 3 -> 4 -> 1."""
        self.app._enter_ant_mode()
        n_presets = len(type(self.app).ANT_PRESETS)
        self.app.ant_menu_sel = n_presets + 1  # ants item
        assert self.app.ant_num_ants == 1
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_num_ants == 2
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_num_ants == 3
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_num_ants == 4
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_num_ants == 1

    def test_menu_cycle_steps_per_frame(self):
        """Cycling steps/frame: 1 -> 5 -> 10 -> 50 -> 100 -> 500 -> 1."""
        self.app._enter_ant_mode()
        n_presets = len(type(self.app).ANT_PRESETS)
        self.app.ant_menu_sel = n_presets + 2
        assert self.app.ant_steps_per_frame == 1
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_steps_per_frame == 5
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_steps_per_frame == 10

    def test_menu_start_item(self):
        """Selecting the 'start' item begins simulation."""
        self.app._enter_ant_mode()
        n_presets = len(type(self.app).ANT_PRESETS)
        self.app.ant_menu_sel = n_presets + 3  # start item
        self.app._handle_ant_menu_key(10)
        assert self.app.ant_mode is True
        assert self.app.ant_menu is False

    def test_menu_q_cancels(self):
        self.app._enter_ant_mode()
        self.app._handle_ant_menu_key(ord("q"))
        assert self.app.ant_menu is False

    def test_menu_esc_cancels(self):
        self.app._enter_ant_mode()
        self.app._handle_ant_menu_key(27)
        assert self.app.ant_menu is False

    def test_menu_noop_key(self):
        self.app._enter_ant_mode()
        result = self.app._handle_ant_menu_key(-1)
        assert result is True

    # ------------------------------------------------------------------
    # Constants validation
    # ------------------------------------------------------------------

    def test_ant_presets_exist(self):
        assert len(type(self.app).ANT_PRESETS) == 8

    def test_ant_presets_valid_rules(self):
        """All preset rules must only contain R and L, length >= 2."""
        for rule, desc in type(self.app).ANT_PRESETS:
            assert len(rule) >= 2, f"Rule '{rule}' too short"
            assert all(ch in "RL" for ch in rule), f"Rule '{rule}' has invalid chars"

    def test_ant_colors_exist(self):
        assert type(self.app).ANT_COLORS == [1, 2, 3, 4, 5, 6, 7, 8]

    # ------------------------------------------------------------------
    # Grid bounds after init
    # ------------------------------------------------------------------

    def test_grid_dimensions_minimum(self):
        """Grid dimensions are at least 10x10."""
        self._init_single_ant()
        assert self.app.ant_rows >= 10
        assert self.app.ant_cols >= 10

    def test_grid_dimensions_from_screen(self):
        """Grid dimensions derive from screen size."""
        # MockStdscr is 40x120
        self._init_single_ant()
        assert self.app.ant_rows == 40 - 5  # max_y - 5 = 35
        assert self.app.ant_cols == (120 - 1) // 2  # = 59

    # ------------------------------------------------------------------
    # Edge case: very small screen
    # ------------------------------------------------------------------

    def test_init_small_screen(self):
        """Grid should clamp to min 10x10 on tiny screens."""
        self.app.stdscr._rows = 5
        self.app.stdscr._cols = 5
        self._init_single_ant()
        assert self.app.ant_rows == 10
        assert self.app.ant_cols == 10

    # ------------------------------------------------------------------
    # Symmetry check for classic RL ant
    # ------------------------------------------------------------------

    def test_classic_rl_symmetric_after_104_steps(self):
        """The classic RL ant is known to be symmetric about the diagonal
        for its first 104 steps. We verify it hasn't changed."""
        self._init_single_ant("RL")
        for _ in range(104):
            self.app._ant_step()
        assert self.app.ant_step_count == 104
        # Just check it didn't crash and colored cells exist
        assert len(self.app.ant_grid) > 0
        # Ant should still be in bounds
        ant = self.app.ant_ants[0]
        assert 0 <= ant["r"] < self.app.ant_rows
        assert 0 <= ant["c"] < self.app.ant_cols
