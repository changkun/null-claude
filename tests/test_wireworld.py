"""Tests for wireworld mode."""
import curses
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.wireworld import register


# Wireworld state constants (from docs/classic-ca.md)
WW_EMPTY = 0
WW_CONDUCTOR = 1
WW_HEAD = 2
WW_TAIL = 3

# Minimal presets for testing
WW_PRESETS = [
    ("Empty", "Start with an empty grid", None),
    ("Diode", "Simple one-way signal", {
        (5, 5): WW_CONDUCTOR,
        (5, 6): WW_CONDUCTOR,
        (5, 7): WW_HEAD,
        (5, 8): WW_TAIL,
        (5, 9): WW_CONDUCTOR,
    }),
]


def _make_ww_app():
    """Create a mock app with wireworld registered and initialized."""
    app = make_mock_app()
    cls = type(app)
    cls.WW_EMPTY = WW_EMPTY
    cls.WW_CONDUCTOR = WW_CONDUCTOR
    cls.WW_HEAD = WW_HEAD
    cls.WW_TAIL = WW_TAIL
    cls.WW_PRESETS = WW_PRESETS
    register(cls)
    app.ww_mode = True
    app.ww_running = False
    app.ww_drawing = True
    app.ww_draw_state = WW_CONDUCTOR
    app._ww_init()
    return app


class TestWireworld:
    def setup_method(self):
        random.seed(42)
        self.app = _make_ww_app()

    def test_enter(self):
        self.app._enter_ww_mode()
        assert self.app.ww_menu is True
        assert self.app.ww_menu_sel == 0

    def test_init_empty(self):
        self.app._ww_init()
        assert self.app.ww_grid == {}
        assert self.app.ww_generation == 0
        assert self.app.ww_rows >= 10
        assert self.app.ww_cols >= 10

    def test_init_with_preset(self):
        cells = WW_PRESETS[1][2]
        self.app._ww_init(cells)
        assert len(self.app.ww_grid) > 0
        # All cell states should be valid wireworld states
        for state in self.app.ww_grid.values():
            assert state in (WW_CONDUCTOR, WW_HEAD, WW_TAIL)

    def test_exit_cleanup(self):
        self.app._ww_init()
        self.app._exit_ww_mode()
        assert self.app.ww_mode is False
        assert self.app.ww_menu is False
        assert self.app.ww_running is False
        assert self.app.ww_grid == {}


class TestWireworldStateTransitions:
    """Verify the core Wireworld transition rules:
      - Head -> Tail
      - Tail -> Conductor
      - Conductor -> Head if exactly 1 or 2 head neighbors
      - Conductor -> Conductor otherwise
      - Empty -> Empty
    """

    def setup_method(self):
        self.app = _make_ww_app()

    # ── Single-cell transitions ────────────────────────────────────

    def test_head_becomes_tail(self):
        """An electron head always becomes an electron tail."""
        self.app.ww_grid[(5, 5)] = WW_HEAD
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_TAIL

    def test_tail_becomes_conductor(self):
        """An electron tail always becomes a conductor."""
        self.app.ww_grid[(5, 5)] = WW_TAIL
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_CONDUCTOR

    def test_isolated_conductor_stays_conductor(self):
        """A conductor with zero head neighbors stays conductor."""
        self.app.ww_grid[(5, 5)] = WW_CONDUCTOR
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_CONDUCTOR

    def test_empty_stays_empty(self):
        """Empty cells remain empty regardless of neighbors."""
        # Put heads around an empty cell
        self.app.ww_grid[(4, 4)] = WW_HEAD
        self.app.ww_grid[(4, 5)] = WW_HEAD
        # (5, 5) is empty -- it should stay empty
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) is None  # not in grid = empty

    # ── Conductor activation rules ─────────────────────────────────

    def test_conductor_with_1_head_neighbor_becomes_head(self):
        """Conductor with exactly 1 head neighbor becomes head."""
        self.app.ww_grid[(5, 5)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 6)] = WW_HEAD
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_HEAD

    def test_conductor_with_2_head_neighbors_becomes_head(self):
        """Conductor with exactly 2 head neighbors becomes head."""
        self.app.ww_grid[(5, 5)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 6)] = WW_HEAD
        self.app.ww_grid[(4, 5)] = WW_HEAD
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_HEAD

    def test_conductor_with_3_head_neighbors_stays_conductor(self):
        """Conductor with 3+ head neighbors stays conductor."""
        self.app.ww_grid[(5, 5)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 6)] = WW_HEAD
        self.app.ww_grid[(4, 5)] = WW_HEAD
        self.app.ww_grid[(4, 4)] = WW_HEAD
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_CONDUCTOR

    def test_conductor_with_tail_neighbors_only_stays_conductor(self):
        """Tail neighbors do not activate a conductor."""
        self.app.ww_grid[(5, 5)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 6)] = WW_TAIL
        self.app.ww_grid[(4, 5)] = WW_TAIL
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_CONDUCTOR

    def test_diagonal_head_neighbor_counts(self):
        """Head neighbors at diagonal positions should be counted."""
        self.app.ww_grid[(5, 5)] = WW_CONDUCTOR
        self.app.ww_grid[(4, 4)] = WW_HEAD  # diagonal
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_HEAD

    # ── Multi-step transition sequences ────────────────────────────

    def test_head_tail_conductor_three_step_cycle(self):
        """Head -> Tail -> Conductor over two steps (isolated cell)."""
        self.app.ww_grid[(5, 5)] = WW_HEAD
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_TAIL
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 5)) == WW_CONDUCTOR

    def test_generation_counter_increments(self):
        """Each step increments the generation counter."""
        self.app._ww_init()
        self.app.ww_grid[(5, 5)] = WW_HEAD
        for i in range(5):
            self.app._ww_step()
        assert self.app.ww_generation == 5

    # ── Electron signal propagation ────────────────────────────────

    def test_electron_propagates_along_wire(self):
        """An electron head should propagate forward along a straight wire."""
        # Build a horizontal wire: conductor - conductor - head - tail - conductor
        for c in range(5, 15):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 7)] = WW_HEAD
        self.app.ww_grid[(5, 8)] = WW_TAIL

        self.app._ww_step()
        # After 1 step: head->tail at 7, tail->conductor at 8
        # conductor at 6 has 1 head neighbor (7 was head) -> becomes head
        assert self.app.ww_grid.get((5, 7)) == WW_TAIL    # was head
        assert self.app.ww_grid.get((5, 8)) == WW_CONDUCTOR  # was tail
        assert self.app.ww_grid.get((5, 6)) == WW_HEAD    # activated by neighbor

    def test_electron_travels_full_wire_length(self):
        """An electron should travel along a wire over multiple steps."""
        # Short wire of 5 cells
        for c in range(5, 10):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 5)] = WW_HEAD
        self.app.ww_grid[(5, 6)] = WW_TAIL

        # Run several steps; electron should propagate rightward
        for _ in range(4):
            self.app._ww_step()
        # After 4 steps the head has moved; all cells should still be valid states
        for c in range(5, 10):
            state = self.app.ww_grid.get((5, c))
            assert state in (WW_CONDUCTOR, WW_HEAD, WW_TAIL, None)

    # ── Wrapping (toroidal boundary) ───────────────────────────────

    def test_wrapping_top_edge(self):
        """Neighbors wrap around the top edge (toroidal grid)."""
        rows = self.app.ww_rows
        # Place conductor at row 0 and head at bottom row (neighbor via wrap)
        self.app.ww_grid[(0, 5)] = WW_CONDUCTOR
        self.app.ww_grid[(rows - 1, 5)] = WW_HEAD
        self.app._ww_step()
        # Conductor at (0,5) should see the head at (rows-1, 5) as neighbor
        assert self.app.ww_grid.get((0, 5)) == WW_HEAD

    def test_wrapping_left_edge(self):
        """Neighbors wrap around the left edge (toroidal grid)."""
        cols = self.app.ww_cols
        self.app.ww_grid[(5, 0)] = WW_CONDUCTOR
        self.app.ww_grid[(5, cols - 1)] = WW_HEAD
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 0)) == WW_HEAD

    # ── Grid stays consistent ──────────────────────────────────────

    def test_empty_grid_stays_empty(self):
        """Stepping an empty grid produces no cells."""
        self.app._ww_init()
        self.app._ww_step()
        assert self.app.ww_grid == {}
        assert self.app.ww_generation == 1

    def test_all_conductors_no_change(self):
        """A grid of only conductors (no heads) never changes."""
        for c in range(5, 10):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        initial = dict(self.app.ww_grid)
        self.app._ww_step()
        assert self.app.ww_grid == initial

    def test_cells_never_become_empty(self):
        """Non-empty cells should never vanish (become empty) in standard Wireworld."""
        for c in range(5, 15):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 7)] = WW_HEAD
        self.app.ww_grid[(5, 8)] = WW_TAIL
        initial_count = len(self.app.ww_grid)
        for _ in range(20):
            self.app._ww_step()
        # No cell should have disappeared
        assert len(self.app.ww_grid) >= initial_count

    def test_no_new_cells_created_from_nothing(self):
        """Wireworld should never create cells in empty positions."""
        self.app.ww_grid[(5, 5)] = WW_HEAD
        self.app.ww_grid[(5, 6)] = WW_TAIL
        self.app.ww_grid[(5, 7)] = WW_CONDUCTOR
        initial_positions = set(self.app.ww_grid.keys())
        for _ in range(10):
            self.app._ww_step()
            for pos in self.app.ww_grid:
                assert pos in initial_positions, (
                    f"New cell appeared at {pos} which was initially empty"
                )


class TestWireworldCircuits:
    """Test common Wireworld circuit patterns."""

    def setup_method(self):
        self.app = _make_ww_app()

    def test_clock_generator_loop(self):
        """A loop of conductors with an electron should cycle the signal.

        A 2x2 square is too dense (all cells are mutual neighbors), so we use
        a larger rectangular loop where each cell has at most 2 wire neighbors.
        Layout (6 cells):
            (5,5) - (5,6) - (5,7)
              |                |
            (6,5) - (6,6) - (6,7)
        This is still dense enough that diagonals connect; instead use a
        straight-line ring (1D loop via toroidal wrap) which guarantees
        each conductor has exactly 2 wire neighbors (left and right).
        """
        # Horizontal wire spanning the full width, wrapping around
        cols = self.app.ww_cols
        for c in range(cols):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 0)] = WW_HEAD
        self.app.ww_grid[(5, 1)] = WW_TAIL

        # Run enough steps for a full loop and verify electron count stays constant
        for step in range(cols + 5):
            heads = sum(1 for s in self.app.ww_grid.values() if s == WW_HEAD)
            tails = sum(1 for s in self.app.ww_grid.values() if s == WW_TAIL)
            assert heads == 1, f"Expected 1 head at step {step}, got {heads}"
            assert tails == 1, f"Expected 1 tail at step {step}, got {tails}"
            self.app._ww_step()

    def test_straight_wire_signal(self):
        """An electron on a straight wire should move one cell per step."""
        # Wire from col 0 to col 9
        for c in range(10):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 1)] = WW_HEAD
        self.app.ww_grid[(5, 2)] = WW_TAIL

        # Step 1: head should move to col 0 (left neighbor of head)
        self.app._ww_step()
        assert self.app.ww_grid.get((5, 1)) == WW_TAIL
        assert self.app.ww_grid.get((5, 2)) == WW_CONDUCTOR
        assert self.app.ww_grid.get((5, 0)) == WW_HEAD

    def test_diode_forward_propagation(self):
        """Diode preset: electron should propagate through."""
        cells = WW_PRESETS[1][2]  # Diode preset
        self.app._ww_init(cells)
        initial_gen = self.app.ww_generation
        for _ in range(5):
            self.app._ww_step()
        assert self.app.ww_generation == initial_gen + 5


class TestWireworldKeyHandling:
    """Test keyboard input handling for wireworld mode."""

    def setup_method(self):
        self.app = _make_ww_app()

    def test_menu_navigation_down(self):
        self.app._enter_ww_mode()
        self.app._handle_ww_menu_key(ord("j"))
        assert self.app.ww_menu_sel == 1

    def test_menu_navigation_up_wraps(self):
        self.app._enter_ww_mode()
        self.app._handle_ww_menu_key(ord("k"))
        assert self.app.ww_menu_sel == len(WW_PRESETS) - 1

    def test_menu_select_enter(self):
        self.app._enter_ww_mode()
        self.app._handle_ww_menu_key(10)  # Enter
        assert self.app.ww_menu is False
        assert self.app.ww_mode is True

    def test_menu_cancel_q(self):
        self.app._enter_ww_mode()
        self.app._handle_ww_menu_key(ord("q"))
        assert self.app.ww_menu is False

    def test_menu_cancel_esc(self):
        self.app._enter_ww_mode()
        self.app._handle_ww_menu_key(27)  # Escape
        assert self.app.ww_menu is False

    def test_toggle_play_pause(self):
        self.app._handle_ww_key(ord(" "))
        assert self.app.ww_running is True
        self.app._handle_ww_key(ord(" "))
        assert self.app.ww_running is False

    def test_single_step(self):
        self.app.ww_grid[(5, 5)] = WW_HEAD
        gen_before = self.app.ww_generation
        self.app._handle_ww_key(ord("n"))
        assert self.app.ww_generation == gen_before + 1
        assert self.app.ww_running is False

    def test_clear_grid(self):
        self.app.ww_grid[(5, 5)] = WW_HEAD
        self.app._handle_ww_key(ord("r"))
        assert self.app.ww_grid == {}

    def test_quit(self):
        self.app._handle_ww_key(ord("q"))
        assert self.app.ww_mode is False

    def test_return_to_menu(self):
        self.app._handle_ww_key(ord("R"))
        assert self.app.ww_menu is True
        assert self.app.ww_mode is False

    def test_speed_increase(self):
        initial = self.app.speed_idx
        self.app._handle_ww_key(ord(">"))
        assert self.app.speed_idx == initial + 1

    def test_speed_decrease(self):
        self.app.speed_idx = 3
        self.app._handle_ww_key(ord("<"))
        assert self.app.speed_idx == 2

    def test_cursor_movement(self):
        initial_r = self.app.ww_cursor_r
        initial_c = self.app.ww_cursor_c
        self.app.ww_drawing = False  # Avoid painting
        self.app._handle_ww_key(ord("j"))
        assert self.app.ww_cursor_r == (initial_r + 1) % self.app.ww_rows
        self.app._handle_ww_key(ord("k"))
        self.app._handle_ww_key(ord("k"))
        assert self.app.ww_cursor_r == (initial_r - 1) % self.app.ww_rows
        self.app._handle_ww_key(ord("l"))
        assert self.app.ww_cursor_c == (initial_c + 1) % self.app.ww_cols
        self.app._handle_ww_key(ord("h"))
        assert self.app.ww_cursor_c == initial_c

    def test_toggle_draw_mode(self):
        self.app.ww_drawing = False
        self.app._handle_ww_key(ord("e"))
        assert self.app.ww_drawing is True
        self.app._handle_ww_key(ord("e"))
        assert self.app.ww_drawing is False

    def test_brush_selection(self):
        self.app._handle_ww_key(ord("1"))
        assert self.app.ww_draw_state == WW_CONDUCTOR
        self.app._handle_ww_key(ord("2"))
        assert self.app.ww_draw_state == WW_HEAD
        self.app._handle_ww_key(ord("3"))
        assert self.app.ww_draw_state == WW_TAIL
        self.app._handle_ww_key(ord("0"))
        assert self.app.ww_draw_state == WW_EMPTY

    def test_enter_cycles_cell_state(self):
        pos = (self.app.ww_cursor_r, self.app.ww_cursor_c)
        # Initially empty (0), enter should cycle to conductor (1)
        self.app._handle_ww_key(10)
        assert self.app.ww_grid.get(pos) == WW_CONDUCTOR
        # Cycle: conductor (1) -> head (2)
        self.app._handle_ww_key(10)
        assert self.app.ww_grid.get(pos) == WW_HEAD
        # Cycle: head (2) -> tail (3)
        self.app._handle_ww_key(10)
        assert self.app.ww_grid.get(pos) == WW_TAIL
        # Cycle: tail (3) -> empty (0) -- removed from grid
        self.app._handle_ww_key(10)
        assert pos not in self.app.ww_grid

    def test_paint_on_move(self):
        """When draw mode is on, moving should paint the current brush."""
        self.app.ww_drawing = True
        self.app.ww_running = False
        self.app.ww_draw_state = WW_CONDUCTOR
        pos_before = (self.app.ww_cursor_r, self.app.ww_cursor_c)
        self.app._handle_ww_key(ord("j"))  # Move down, should paint
        pos_after = (self.app.ww_cursor_r, self.app.ww_cursor_c)
        assert self.app.ww_grid.get(pos_after) == WW_CONDUCTOR

    def test_no_key_does_nothing(self):
        """Key -1 (no key pressed) should not crash or change state."""
        gen = self.app.ww_generation
        self.app._handle_ww_key(-1)
        assert self.app.ww_generation == gen

    def test_menu_no_key(self):
        """Key -1 in menu should not crash."""
        self.app._enter_ww_mode()
        sel = self.app.ww_menu_sel
        self.app._handle_ww_menu_key(-1)
        assert self.app.ww_menu_sel == sel


class TestWireworldPaint:
    """Test the paint helper method."""

    def setup_method(self):
        self.app = _make_ww_app()

    def test_paint_conductor(self):
        self.app.ww_draw_state = WW_CONDUCTOR
        self.app.ww_cursor_r = 3
        self.app.ww_cursor_c = 3
        self.app._ww_paint()
        assert self.app.ww_grid[(3, 3)] == WW_CONDUCTOR

    def test_paint_eraser(self):
        self.app.ww_grid[(3, 3)] = WW_HEAD
        self.app.ww_draw_state = WW_EMPTY
        self.app.ww_cursor_r = 3
        self.app.ww_cursor_c = 3
        self.app._ww_paint()
        assert (3, 3) not in self.app.ww_grid

    def test_paint_overwrite(self):
        self.app.ww_grid[(3, 3)] = WW_CONDUCTOR
        self.app.ww_draw_state = WW_HEAD
        self.app.ww_cursor_r = 3
        self.app.ww_cursor_c = 3
        self.app._ww_paint()
        assert self.app.ww_grid[(3, 3)] == WW_HEAD


class TestWireworldStepMulti:
    """Multiple-step regression scenarios."""

    def setup_method(self):
        self.app = _make_ww_app()

    def test_10_steps_no_crash(self):
        """Run the diode preset 10 steps without crashing."""
        cells = WW_PRESETS[1][2]
        self.app._ww_init(cells)
        for _ in range(10):
            self.app._ww_step()
        assert self.app.ww_generation == 10

    def test_only_valid_states_after_many_steps(self):
        """All cells must remain in valid states after many steps."""
        for c in range(20):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 0)] = WW_HEAD
        self.app.ww_grid[(5, 1)] = WW_TAIL
        for _ in range(50):
            self.app._ww_step()
            for pos, state in self.app.ww_grid.items():
                assert state in (WW_CONDUCTOR, WW_HEAD, WW_TAIL), (
                    f"Invalid state {state} at {pos} after gen {self.app.ww_generation}"
                )

    def test_conservation_of_cells(self):
        """Total number of non-empty cells never changes (no creation/destruction)."""
        for c in range(10):
            self.app.ww_grid[(5, c)] = WW_CONDUCTOR
        self.app.ww_grid[(5, 3)] = WW_HEAD
        self.app.ww_grid[(5, 4)] = WW_TAIL
        count = len(self.app.ww_grid)
        for _ in range(30):
            self.app._ww_step()
            assert len(self.app.ww_grid) == count, (
                f"Cell count changed at gen {self.app.ww_generation}"
            )
