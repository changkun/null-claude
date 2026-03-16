"""Tests for puzzle mode -- deep validation against commit ab6def6."""
import curses
import random
from unittest.mock import patch
import pytest
from tests.conftest import make_mock_app
from life.modes.puzzle import register
from life.patterns import PUZZLES


class TestPuzzle:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    # ── PUZZLES data integrity ─────────────────────────────────────────

    def test_puzzles_count(self):
        """All 10 puzzles present."""
        assert len(PUZZLES) == 10

    def test_puzzles_ids(self):
        """IDs are 1..10."""
        assert [p["id"] for p in PUZZLES] == list(range(1, 11))

    def test_puzzle_types(self):
        """Each puzzle has a valid type."""
        valid = {"still_life", "oscillator", "reach_population",
                 "escape_box", "extinction", "survive_gens"}
        for p in PUZZLES:
            assert p["type"] in valid, f"Puzzle {p['id']} has unknown type {p['type']}"

    def test_puzzle_required_keys(self):
        """Every puzzle has the required keys."""
        required = {"id", "name", "description", "type", "max_cells",
                    "sim_gens", "goal_text", "hint"}
        for p in PUZZLES:
            missing = required - set(p.keys())
            assert not missing, f"Puzzle {p['id']} missing keys: {missing}"

    # ── Enter / Exit ───────────────────────────────────────────────────

    def test_enter_puzzle_mode(self):
        """_enter_puzzle_mode sets menu state."""
        self.app._enter_puzzle_mode()
        assert self.app.puzzle_menu is True
        assert self.app.puzzle_sel == 0
        assert self.app.puzzle_mode is False
        assert self.app.puzzle_phase == "idle"

    def test_exit_puzzle_mode(self):
        """_exit_puzzle_mode clears all puzzle state."""
        # First enter and start a puzzle
        self.app._enter_puzzle_mode()
        self.app._puzzle_start_planning(PUZZLES[0])
        assert self.app.puzzle_mode is True
        # Now exit
        self.app._exit_puzzle_mode()
        assert self.app.puzzle_mode is False
        assert self.app.puzzle_menu is False
        assert self.app.puzzle_phase == "idle"
        assert self.app.puzzle_current is None
        assert len(self.app.puzzle_placed_cells) == 0
        assert len(self.app.puzzle_state_hashes) == 0
        assert self.app.puzzle_win_gen is None
        assert "Puzzle mode OFF" in self.app.message

    # ── Puzzle selection (menu keys) ───────────────────────────────────

    def test_menu_navigate_down(self):
        """Down arrow advances selection."""
        self.app._enter_puzzle_mode()
        self.app._handle_puzzle_menu_key(curses.KEY_DOWN)
        assert self.app.puzzle_sel == 1

    def test_menu_navigate_up_wraps(self):
        """Up arrow from 0 wraps to last puzzle."""
        self.app._enter_puzzle_mode()
        self.app._handle_puzzle_menu_key(curses.KEY_UP)
        assert self.app.puzzle_sel == len(PUZZLES) - 1

    def test_menu_j_k_keys(self):
        """j/k keys work like down/up."""
        self.app._enter_puzzle_mode()
        self.app._handle_puzzle_menu_key(ord("j"))
        assert self.app.puzzle_sel == 1
        self.app._handle_puzzle_menu_key(ord("k"))
        assert self.app.puzzle_sel == 0

    def test_menu_enter_starts_planning(self):
        """Enter key starts planning for selected puzzle."""
        self.app._enter_puzzle_mode()
        self.app._handle_puzzle_menu_key(ord("j"))  # select puzzle 2
        self.app._handle_puzzle_menu_key(10)  # Enter
        assert self.app.puzzle_phase == "planning"
        assert self.app.puzzle_current["id"] == 2

    def test_menu_escape_closes(self):
        """Escape closes the menu."""
        self.app._enter_puzzle_mode()
        self.app._handle_puzzle_menu_key(27)
        assert self.app.puzzle_menu is False

    def test_menu_q_closes(self):
        """q key closes the menu."""
        self.app._enter_puzzle_mode()
        self.app._handle_puzzle_menu_key(ord("q"))
        assert self.app.puzzle_menu is False

    def test_menu_noop_key(self):
        """No-op key (-1) does nothing."""
        self.app._enter_puzzle_mode()
        result = self.app._handle_puzzle_menu_key(-1)
        assert result is True
        assert self.app.puzzle_sel == 0

    # ── Start planning ─────────────────────────────────────────────────

    def test_start_planning_state(self):
        """_puzzle_start_planning initializes all fields correctly."""
        puzzle = PUZZLES[0]
        self.app._puzzle_start_planning(puzzle)
        assert self.app.puzzle_current is puzzle
        assert self.app.puzzle_mode is True
        assert self.app.puzzle_menu is False
        assert self.app.puzzle_phase == "planning"
        assert len(self.app.puzzle_placed_cells) == 0
        assert len(self.app.puzzle_state_hashes) == 0
        assert self.app.puzzle_win_gen is None
        assert self.app.puzzle_sim_gen == 0
        assert self.app.puzzle_peak_pop == 0
        assert self.app.puzzle_score == 0
        assert self.app.puzzle_initial_bbox is None
        assert self.app.running is False
        assert self.app.cursor_r == self.app.grid.rows // 2
        assert self.app.cursor_c == self.app.grid.cols // 2

    def test_start_planning_clears_grid(self):
        """Grid is cleared on planning start."""
        self.app.grid.set_alive(5, 5)
        assert self.app.grid.population > 0
        self.app._puzzle_start_planning(PUZZLES[0])
        assert self.app.grid.population == 0

    # ── Planning phase key handling ────────────────────────────────────

    def test_planning_toggle_cell(self):
        """'e' toggles a cell on/off."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app._handle_puzzle_planning_key(ord("e"))
        pos = (self.app.cursor_r, self.app.cursor_c)
        assert pos in self.app.puzzle_placed_cells
        assert self.app.grid.cells[pos[0]][pos[1]] > 0
        # Toggle off
        self.app._handle_puzzle_planning_key(ord("e"))
        assert pos not in self.app.puzzle_placed_cells
        assert self.app.grid.cells[pos[0]][pos[1]] == 0

    def test_planning_max_cells_enforced(self):
        """Cannot place more than max_cells."""
        puzzle = PUZZLES[0]  # max_cells=4
        self.app._puzzle_start_planning(puzzle)
        # Place 4 cells
        for i in range(4):
            self.app.cursor_r = 10 + i
            self.app.cursor_c = 10
            self.app._handle_puzzle_planning_key(ord("e"))
        assert len(self.app.puzzle_placed_cells) == 4
        # Try to place a 5th
        self.app.cursor_r = 20
        self.app.cursor_c = 20
        self.app._handle_puzzle_planning_key(ord("e"))
        assert len(self.app.puzzle_placed_cells) == 4
        assert "Max" in self.app.message

    def test_planning_draw_mode(self):
        """'d' enters draw mode, draws on movement."""
        self.app._puzzle_start_planning(PUZZLES[1])  # max_cells=5
        self.app._handle_puzzle_planning_key(ord("d"))
        assert self.app.draw_mode == "draw"
        # Move to paint cells
        self.app._handle_puzzle_planning_key(curses.KEY_RIGHT)
        self.app._handle_puzzle_planning_key(curses.KEY_RIGHT)
        assert len(self.app.puzzle_placed_cells) >= 2
        # Toggle off
        self.app._handle_puzzle_planning_key(ord("d"))
        assert self.app.draw_mode is None

    def test_planning_erase_mode(self):
        """'x' enters erase mode, erases on movement."""
        self.app._puzzle_start_planning(PUZZLES[1])
        # Place some cells
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app.cursor_c = 26
        self.app._handle_puzzle_planning_key(ord("e"))
        assert len(self.app.puzzle_placed_cells) == 2
        # Enter erase mode at (15, 26)
        self.app._handle_puzzle_planning_key(ord("x"))
        assert self.app.draw_mode == "erase"
        # Move left to erase (15, 25)
        self.app._handle_puzzle_planning_key(curses.KEY_LEFT)
        assert (15, 25) not in self.app.puzzle_placed_cells

    def test_planning_clear(self):
        """'c' clears all placed cells."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app._handle_puzzle_planning_key(ord("e"))
        assert len(self.app.puzzle_placed_cells) == 1
        self.app._handle_puzzle_planning_key(ord("c"))
        assert len(self.app.puzzle_placed_cells) == 0
        assert self.app.grid.population == 0

    def test_planning_hint(self):
        """'?' shows the hint."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app._handle_puzzle_planning_key(ord("?"))
        assert "Hint:" in self.app.message

    def test_planning_escape_exits(self):
        """ESC exits puzzle mode from planning."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app._handle_puzzle_planning_key(27)
        assert self.app.puzzle_mode is False

    def test_planning_cursor_movement(self):
        """Arrow keys move cursor."""
        self.app._puzzle_start_planning(PUZZLES[0])
        r0, c0 = self.app.cursor_r, self.app.cursor_c
        self.app._handle_puzzle_planning_key(curses.KEY_UP)
        assert self.app.cursor_r == (r0 - 1) % self.app.grid.rows
        self.app._handle_puzzle_planning_key(curses.KEY_DOWN)
        assert self.app.cursor_r == r0
        self.app._handle_puzzle_planning_key(curses.KEY_LEFT)
        assert self.app.cursor_c == (c0 - 1) % self.app.grid.cols
        self.app._handle_puzzle_planning_key(curses.KEY_RIGHT)
        assert self.app.cursor_c == c0

    def test_planning_noop_key(self):
        """No-op key returns True."""
        self.app._puzzle_start_planning(PUZZLES[0])
        result = self.app._handle_puzzle_planning_key(-1)
        assert result is True

    # ── Puzzle run transition ──────────────────────────────────────────

    def test_run_no_cells_fails(self):
        """Cannot run with zero cells."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app._puzzle_run()
        assert self.app.puzzle_phase == "planning"
        assert "Place at least one cell" in self.app.message

    def test_run_too_many_cells(self):
        """Cannot run with more cells than max_cells."""
        puzzle = PUZZLES[0]  # max_cells=4
        self.app._puzzle_start_planning(puzzle)
        # Manually add too many cells
        for i in range(5):
            pos = (10 + i, 10)
            self.app.grid.set_alive(*pos)
            self.app.puzzle_placed_cells.add(pos)
        self.app._puzzle_run()
        assert self.app.puzzle_phase == "planning"
        assert "Too many cells" in self.app.message

    def test_run_transitions_to_running(self):
        """Valid run transitions to running phase."""
        self.app._puzzle_start_planning(PUZZLES[0])
        # Place cells (2x2 block)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        assert self.app.puzzle_phase == "running"
        assert self.app.running is True
        assert self.app.puzzle_start_pop == 4
        assert self.app.puzzle_sim_gen == 0
        assert self.app.puzzle_peak_pop == 4

    def test_run_escape_box_computes_bbox(self):
        """Running an escape_box puzzle computes initial bounding box."""
        puzzle = PUZZLES[3]  # escape_box, box_size=10
        self.app._puzzle_start_planning(puzzle)
        # Place a glider
        cells = [(14, 25), (15, 26), (16, 24), (16, 25), (16, 26)]
        for r, c in cells:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        assert self.app.puzzle_initial_bbox is not None
        min_r, min_c, max_r, max_c = self.app.puzzle_initial_bbox
        assert max_r - min_r == 10  # box_size
        assert max_c - min_c == 10

    # ── Win condition: still_life ──────────────────────────────────────

    def test_still_life_win_block(self):
        """A 2x2 block is detected as a still life (puzzle 1)."""
        puzzle = PUZZLES[0]  # still_life, max_cells=4
        self.app._puzzle_start_planning(puzzle)
        # Place a block
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        # Step until win
        for _ in range(5):
            if self.app.puzzle_phase != "running":
                break
            self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"
        assert self.app.puzzle_score > 0

    def test_still_life_fail_extinction(self):
        """A single cell dies -> fail for still_life puzzle."""
        puzzle = PUZZLES[0]
        self.app._puzzle_start_planning(puzzle)
        # Place a single cell (will die next gen)
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "fail"
        assert "died" in self.app.message

    # ── Win condition: oscillator ──────────────────────────────────────

    def test_oscillator_win_blinker(self):
        """A blinker (3 in a row) is detected as oscillator (puzzle 2)."""
        puzzle = PUZZLES[1]  # oscillator, min_period=2, max_cells=5
        self.app._puzzle_start_planning(puzzle)
        # Place a blinker
        for r, c in [(15, 24), (15, 25), (15, 26)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        for _ in range(10):
            if self.app.puzzle_phase != "running":
                break
            self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"

    def test_oscillator_still_life_detected_as_cycle(self):
        """A block (still life) has cycle_period=1 at gen 1, but the hash-based
        detection does not update stored gen, so at gen 2 it computes period=2
        and triggers a win. This matches the original monolith behavior."""
        puzzle = PUZZLES[1]  # oscillator, min_period=2
        self.app._puzzle_start_planning(puzzle)
        # Place a block (still life, period 1)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        # Gen 1: hash matches gen 0, period=1 < min_period=2, skipped
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "running"
        # Gen 2: hash still matches gen 0, period=2 >= min_period=2, win
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"

    def test_oscillator_fail_extinction(self):
        """Cells dying fails the oscillator puzzle."""
        puzzle = PUZZLES[1]
        self.app._puzzle_start_planning(puzzle)
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "fail"
        assert "died" in self.app.message

    # ── Win condition: reach_population ─────────────────────────────────

    def test_reach_population_win(self):
        """R-pentomino grows past 20 (puzzle 3)."""
        puzzle = PUZZLES[2]  # reach_population, target_pop=20, max_cells=5
        self.app._puzzle_start_planning(puzzle)
        # Place r-pentomino centered
        r0, c0 = 15, 25
        for dr, dc in [(0, 1), (0, 2), (1, 0), (1, 1), (2, 1)]:
            self.app.cursor_r = r0 + dr
            self.app.cursor_c = c0 + dc
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        for _ in range(100):
            if self.app.puzzle_phase != "running":
                break
            self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"

    def test_reach_population_fail_extinction(self):
        """Single cell dies -> fail for reach_population."""
        puzzle = PUZZLES[2]
        self.app._puzzle_start_planning(puzzle)
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "fail"
        assert "died" in self.app.message

    # ── Win condition: escape_box ──────────────────────────────────────

    def test_escape_box_win_glider(self):
        """A glider escapes a 10x10 box (puzzle 4)."""
        puzzle = PUZZLES[3]  # escape_box, box_size=10, max_cells=6
        self.app._puzzle_start_planning(puzzle)
        # Place a glider
        r0, c0 = 15, 25
        for dr, dc in [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]:
            self.app.cursor_r = r0 + dr
            self.app.cursor_c = c0 + dc
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        for _ in range(30):
            if self.app.puzzle_phase != "running":
                break
            self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"

    # ── Win condition: extinction ──────────────────────────────────────

    def test_extinction_win(self):
        """Cells that die out within sim_gens win extinction puzzle."""
        puzzle = PUZZLES[4]  # extinction, max_cells=7
        self.app._puzzle_start_planning(puzzle)
        # Place a single cell (dies immediately)
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"
        assert self.app.puzzle_win_gen == 1

    def test_extinction_fail_stable(self):
        """A stable pattern fails extinction puzzle."""
        puzzle = PUZZLES[4]
        self.app._puzzle_start_planning(puzzle)
        # Place a block (stable forever)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        for _ in range(5):
            if self.app.puzzle_phase != "running":
                break
            self.app._puzzle_step()
        assert self.app.puzzle_phase == "fail"
        assert "stabilised" in self.app.message

    # ── Win condition: survive_gens ────────────────────────────────────

    def test_survive_gens_fail_extinction(self):
        """A single cell dies -> fail for survive_gens."""
        puzzle = PUZZLES[9]  # survive_gens, target_gens=500
        self.app._puzzle_start_planning(puzzle)
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "fail"
        assert "extinct" in self.app.message.lower()

    def test_survive_gens_fail_still_life(self):
        """A block (still life) fails survive_gens."""
        puzzle = PUZZLES[9]
        self.app._puzzle_start_planning(puzzle)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        for _ in range(5):
            if self.app.puzzle_phase != "running":
                break
            self.app._puzzle_step()
        assert self.app.puzzle_phase == "fail"
        assert "still life" in self.app.message.lower()

    # ── Scoring ────────────────────────────────────────────────────────

    def test_score_capped_at_999(self):
        """Score never exceeds 999."""
        puzzle = PUZZLES[0]
        self.app._puzzle_start_planning(puzzle)
        # Place block
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"
        assert self.app.puzzle_score <= 999

    def test_score_fewer_cells_better(self):
        """Using fewer cells produces a higher base score."""
        # Puzzle 8: still_life, max_cells=6
        puzzle = PUZZLES[7]

        # Solve with 4 cells (block)
        self.app._puzzle_start_planning(puzzle)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        score_4 = self.app.puzzle_score

        # Solve with 6 cells (beehive)
        self.app._puzzle_start_planning(puzzle)
        for r, c in [(14, 25), (14, 26), (15, 24), (15, 27), (16, 25), (16, 26)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        score_6 = self.app.puzzle_score

        assert score_4 > score_6

    def test_best_score_tracked(self):
        """Best score for each puzzle ID is tracked."""
        puzzle = PUZZLES[0]
        self.app._puzzle_start_planning(puzzle)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert puzzle["id"] in self.app.puzzle_scores
        assert self.app.puzzle_scores[puzzle["id"]] == self.app.puzzle_score

    def test_fail_score_zero(self):
        """Failed puzzle has score 0."""
        self.app._puzzle_fail("test reason")
        assert self.app.puzzle_score == 0
        assert self.app.puzzle_phase == "fail"

    # ── Win/Fail handlers ──────────────────────────────────────────────

    def test_puzzle_win_stops_running(self):
        """_puzzle_win stops the simulation."""
        puzzle = PUZZLES[0]
        self.app._puzzle_start_planning(puzzle)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.running is False

    def test_puzzle_fail_stops_running(self):
        """_puzzle_fail stops the simulation."""
        self.app.running = True
        self.app._puzzle_fail("test")
        assert self.app.running is False
        assert self.app.puzzle_phase == "fail"

    # ── Result screen keys ─────────────────────────────────────────────

    def test_result_retry(self):
        """'r' retries the current puzzle."""
        puzzle = PUZZLES[0]
        self.app._puzzle_start_planning(puzzle)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"
        self.app._handle_puzzle_result_key(ord("r"))
        assert self.app.puzzle_phase == "planning"
        assert self.app.puzzle_current is puzzle

    def test_result_next_puzzle(self):
        """'n' advances to next puzzle."""
        puzzle = PUZZLES[0]
        self.app._puzzle_start_planning(puzzle)
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"
        self.app._handle_puzzle_result_key(ord("n"))
        assert self.app.puzzle_current["id"] == 2
        assert self.app.puzzle_phase == "planning"

    def test_result_next_at_last_puzzle(self):
        """'n' on last puzzle shows message."""
        puzzle = PUZZLES[-1]
        self.app._puzzle_start_planning(puzzle)
        # Manually set success state
        self.app.puzzle_phase = "success"
        self.app._handle_puzzle_result_key(ord("n"))
        assert "last puzzle" in self.app.message

    def test_result_quit(self):
        """'q' exits puzzle mode from result screen."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app.puzzle_phase = "success"
        self.app._handle_puzzle_result_key(ord("q"))
        assert self.app.puzzle_mode is False

    def test_result_escape_exits(self):
        """ESC exits puzzle mode from result screen."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app.puzzle_phase = "success"
        self.app._handle_puzzle_result_key(27)
        assert self.app.puzzle_mode is False

    def test_result_back_to_list(self):
        """'l' returns to puzzle list."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app.puzzle_phase = "success"
        self.app._handle_puzzle_result_key(ord("l"))
        assert self.app.puzzle_menu is True
        assert self.app.puzzle_mode is False

    def test_result_enter_next(self):
        """Enter key on result advances to next puzzle."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app.puzzle_phase = "success"
        self.app._handle_puzzle_result_key(10)
        assert self.app.puzzle_current["id"] == 2

    def test_result_noop(self):
        """No-op key on result screen returns True."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app.puzzle_phase = "success"
        result = self.app._handle_puzzle_result_key(-1)
        assert result is True

    # ── _puzzle_step edge cases ────────────────────────────────────────

    def test_puzzle_step_no_puzzle(self):
        """_puzzle_step does nothing if no puzzle current."""
        self.app.puzzle_current = None
        self.app._puzzle_step()  # should not raise

    def test_puzzle_step_not_running(self):
        """_puzzle_step does nothing if not in running phase."""
        self.app._puzzle_start_planning(PUZZLES[0])
        gen_before = self.app.grid.generation
        self.app._puzzle_step()  # phase is 'planning', not 'running'
        assert self.app.grid.generation == gen_before

    def test_peak_pop_tracked(self):
        """Peak population is tracked during simulation."""
        puzzle = PUZZLES[2]  # reach_population
        self.app._puzzle_start_planning(puzzle)
        r0, c0 = 15, 25
        for dr, dc in [(0, 1), (0, 2), (1, 0), (1, 1), (2, 1)]:
            self.app.cursor_r = r0 + dr
            self.app.cursor_c = c0 + dc
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        for _ in range(20):
            if self.app.puzzle_phase != "running":
                break
            self.app._puzzle_step()
        assert self.app.puzzle_peak_pop >= 5  # started with 5

    # ── Draw functions don't crash ─────────────────────────────────────

    @patch("curses.color_pair", return_value=0)
    def test_draw_puzzle_menu_no_crash(self, _mock_cp):
        """_draw_puzzle_menu runs without error."""
        self.app._enter_puzzle_mode()
        self.app._draw_puzzle_menu(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.colors.curses.color_pair", return_value=0)
    def test_draw_puzzle_planning_no_crash(self, _mc1, _mc2):
        """_draw_puzzle renders during planning."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app._draw_puzzle(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.colors.curses.color_pair", return_value=0)
    def test_draw_puzzle_running_no_crash(self, _mc1, _mc2):
        """_draw_puzzle renders during running."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._draw_puzzle(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.colors.curses.color_pair", return_value=0)
    def test_draw_puzzle_success_no_crash(self, _mc1, _mc2):
        """_draw_puzzle renders on success."""
        self.app._puzzle_start_planning(PUZZLES[0])
        for r, c in [(14, 24), (14, 25), (15, 24), (15, 25)]:
            self.app.cursor_r = r
            self.app.cursor_c = c
            self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"
        self.app._draw_puzzle(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.colors.curses.color_pair", return_value=0)
    def test_draw_puzzle_fail_no_crash(self, _mc1, _mc2):
        """_draw_puzzle renders on fail."""
        self.app._puzzle_start_planning(PUZZLES[0])
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "fail"
        self.app._draw_puzzle(40, 120)

    @patch("curses.color_pair", return_value=0)
    @patch("life.colors.curses.color_pair", return_value=0)
    def test_draw_puzzle_escape_box_bbox_preview(self, _mc1, _mc2):
        """_draw_puzzle shows bbox preview during escape_box planning."""
        puzzle = PUZZLES[3]
        self.app._puzzle_start_planning(puzzle)
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._draw_puzzle(40, 120)  # should not crash

    # ── Register function ──────────────────────────────────────────────

    def test_register_binds_all_methods(self):
        """register() attaches all puzzle methods to App class."""
        expected = [
            "_enter_puzzle_mode", "_exit_puzzle_mode",
            "_puzzle_start_planning", "_puzzle_run",
            "_puzzle_step", "_puzzle_win", "_puzzle_fail",
            "_handle_puzzle_menu_key", "_handle_puzzle_planning_key",
            "_handle_puzzle_result_key", "_draw_puzzle_menu", "_draw_puzzle",
        ]
        AppCls = type(self.app)
        for name in expected:
            assert hasattr(AppCls, name), f"Missing method {name}"

    # ── Gen bonus in scoring ───────────────────────────────────────────

    def test_gen_bonus_for_fast_win(self):
        """Winning earlier yields a gen_bonus in score."""
        # Extinction puzzle: single cell dies at gen 1, sim_gens=150
        puzzle = PUZZLES[4]
        self.app._puzzle_start_planning(puzzle)
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._handle_puzzle_planning_key(ord("e"))
        self.app._puzzle_run()
        self.app._puzzle_step()
        assert self.app.puzzle_phase == "success"
        # win_gen=1, sim_gens=150 -> remaining=149, gen_bonus = int(50*149/150) = 49
        # cell_bonus = int(100*7/1) = 700
        # total = min(999, 700+49) = 749
        assert self.app.puzzle_score == 749

    # ── All puzzle type coverage ───────────────────────────────────────

    def test_puzzle_type_distribution(self):
        """Verify the type distribution across 10 puzzles matches original."""
        types = [p["type"] for p in PUZZLES]
        assert types.count("still_life") == 2
        assert types.count("oscillator") == 2
        assert types.count("reach_population") == 3
        assert types.count("escape_box") == 1
        assert types.count("extinction") == 1
        assert types.count("survive_gens") == 1
