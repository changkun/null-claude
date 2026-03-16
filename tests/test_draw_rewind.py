"""Tests for draw/erase and rewind — deep validation against commits 098dda8, b42be37."""
import random
import pytest
from tests.conftest import make_mock_app
from life.grid import Grid


# ── Helper functions that replicate App methods on the mock ──────────────────

def _record_pop(app):
    """Replicate App._record_pop."""
    app.pop_history.append(app.grid.population)


def _reset_cycle_detection(app):
    """Replicate App._reset_cycle_detection."""
    app.state_history.clear()
    app.cycle_detected = False


def _push_history(app):
    """Replicate App._push_history (matches current app.py line 3327)."""
    if app.timeline_pos is not None:
        app.history = app.history[:app.timeline_pos + 1]
        app.timeline_pos = None
    app.history.append((app.grid.to_dict(), len(app.pop_history)))
    if len(app.history) > app.history_max:
        app.history = app.history[-app.history_max:]


def _rewind(app):
    """Replicate App._rewind (matches current app.py line 3339)."""
    if not app.history:
        app._flash("No history to rewind")
        return
    if app.timeline_pos is None:
        app.timeline_pos = len(app.history) - 1
    else:
        if app.timeline_pos <= 0:
            app._flash("At oldest recorded state")
            return
        app.timeline_pos -= 1
    _restore_timeline_pos(app)


def _restore_timeline_pos(app):
    """Replicate App._restore_timeline_pos."""
    grid_dict, pop_len = app.history[app.timeline_pos]
    app.grid.load_dict(grid_dict)
    app.pop_history = app.pop_history[:pop_len]
    _reset_cycle_detection(app)
    app._flash(f"Gen {app.grid.generation}  ({app.timeline_pos + 1}/{len(app.history)})")


def _scrub_back(app, steps=10):
    """Replicate App._scrub_back."""
    if not app.history:
        app._flash("No history to scrub")
        return
    if app.timeline_pos is None:
        app.timeline_pos = max(0, len(app.history) - steps)
    else:
        app.timeline_pos = max(0, app.timeline_pos - steps)
    _restore_timeline_pos(app)


def _scrub_forward(app, steps=10):
    """Replicate App._scrub_forward."""
    if app.timeline_pos is None:
        app._flash("Already at latest state")
        return
    app.timeline_pos += steps
    if app.timeline_pos >= len(app.history):
        app.timeline_pos = None
        grid_dict, pop_len = app.history[-1]
        app.grid.load_dict(grid_dict)
        app.pop_history = app.pop_history[:pop_len]
        _reset_cycle_detection(app)
        app._flash(f"Latest -> Gen {app.grid.generation} (press n/Space to continue)")
    else:
        _restore_timeline_pos(app)


def _apply_draw_mode(app):
    """Replicate App._apply_draw_mode (matches current app.py line 5454)."""
    if app.draw_mode == "draw":
        app.grid.set_alive(app.cursor_r, app.cursor_c)
        _reset_cycle_detection(app)
    elif app.draw_mode == "erase":
        app.grid.set_dead(app.cursor_r, app.cursor_c)
        _reset_cycle_detection(app)


def _step(app):
    """Push history, step grid, record pop — matches run loop and 'n' key handler."""
    _push_history(app)
    app.grid.step()
    _record_pop(app)


# ── Draw mode tests ─────────────────────────────────────────────────────────

class TestDrawMode:
    """Validate draw/erase logic against commit 098dda8."""

    def test_draw_mode_initially_none(self):
        app = make_mock_app()
        assert app.draw_mode is None

    def test_enable_draw_mode_sets_cell_alive(self):
        """Pressing 'd' should enable draw mode and set the cursor cell alive."""
        app = make_mock_app()
        r, c = app.cursor_r, app.cursor_c
        assert app.grid.cells[r][c] == 0
        # Simulate pressing 'd'
        app.draw_mode = "draw"
        app.grid.set_alive(r, c)
        _reset_cycle_detection(app)
        assert app.grid.cells[r][c] == 1
        assert app.grid.population == 1

    def test_disable_draw_mode_toggle(self):
        """Pressing 'd' again should disable draw mode."""
        app = make_mock_app()
        app.draw_mode = "draw"
        # Toggle off
        app.draw_mode = None if app.draw_mode == "draw" else "draw"
        assert app.draw_mode is None

    def test_enable_erase_mode_sets_cell_dead(self):
        """Pressing 'x' should enable erase mode and set the cursor cell dead."""
        app = make_mock_app()
        r, c = app.cursor_r, app.cursor_c
        app.grid.set_alive(r, c)
        assert app.grid.cells[r][c] == 1
        # Simulate pressing 'x'
        app.draw_mode = "erase"
        app.grid.set_dead(r, c)
        _reset_cycle_detection(app)
        assert app.grid.cells[r][c] == 0
        assert app.grid.population == 0

    def test_disable_erase_mode_toggle(self):
        """Pressing 'x' again should disable erase mode."""
        app = make_mock_app()
        app.draw_mode = "erase"
        app.draw_mode = None if app.draw_mode == "erase" else "erase"
        assert app.draw_mode is None

    def test_esc_exits_draw_mode(self):
        """ESC should exit any draw/erase mode."""
        app = make_mock_app()
        app.draw_mode = "draw"
        # Simulate ESC
        if app.draw_mode:
            app.draw_mode = None
        assert app.draw_mode is None

    def test_esc_exits_erase_mode(self):
        app = make_mock_app()
        app.draw_mode = "erase"
        if app.draw_mode:
            app.draw_mode = None
        assert app.draw_mode is None

    def test_apply_draw_mode_paints_cells(self):
        """Moving cursor in draw mode should paint cells alive."""
        app = make_mock_app()
        app.draw_mode = "draw"
        app.grid.set_alive(app.cursor_r, app.cursor_c)

        # Move cursor down and apply
        app.cursor_r = (app.cursor_r + 1) % app.grid.rows
        _apply_draw_mode(app)
        # Move cursor right and apply
        app.cursor_c = (app.cursor_c + 1) % app.grid.cols
        _apply_draw_mode(app)

        assert app.grid.population == 3

    def test_apply_erase_mode_erases_cells(self):
        """Moving cursor in erase mode should erase cells."""
        app = make_mock_app()
        # Set up a line of alive cells
        for i in range(5):
            app.grid.set_alive(app.cursor_r, app.cursor_c + i)
        assert app.grid.population == 5

        app.draw_mode = "erase"
        # Erase initial position
        app.grid.set_dead(app.cursor_r, app.cursor_c)
        # Move right and erase
        for i in range(1, 5):
            app.cursor_c = (app.cursor_c + 1) % app.grid.cols
            _apply_draw_mode(app)
        assert app.grid.population == 0

    def test_apply_draw_mode_noop_when_no_mode(self):
        """_apply_draw_mode should do nothing if draw_mode is None."""
        app = make_mock_app()
        assert app.draw_mode is None
        _apply_draw_mode(app)
        assert app.grid.population == 0

    def test_draw_mode_wraps_cursor(self):
        """Cursor should wrap around in draw mode (toroidal)."""
        app = make_mock_app()
        app.draw_mode = "draw"
        app.cursor_r = 0
        app.cursor_c = 0
        app.grid.set_alive(0, 0)
        # Move up (wraps to bottom)
        app.cursor_r = (app.cursor_r - 1) % app.grid.rows
        _apply_draw_mode(app)
        assert app.grid.cells[app.grid.rows - 1][0] > 0

    def test_draw_idempotent_on_alive_cell(self):
        """Drawing on an already-alive cell should not increase population."""
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        assert app.grid.population == 1
        app.draw_mode = "draw"
        app.cursor_r, app.cursor_c = 5, 5
        _apply_draw_mode(app)
        assert app.grid.population == 1

    def test_erase_idempotent_on_dead_cell(self):
        """Erasing a dead cell should not decrease population."""
        app = make_mock_app()
        assert app.grid.population == 0
        app.draw_mode = "erase"
        app.cursor_r, app.cursor_c = 5, 5
        _apply_draw_mode(app)
        assert app.grid.population == 0

    def test_toggle_cell_with_e_key(self):
        """Pressing 'e' toggles the cell at cursor (independent of draw mode)."""
        app = make_mock_app()
        r, c = app.cursor_r, app.cursor_c
        assert app.grid.cells[r][c] == 0
        app.grid.toggle(r, c)
        assert app.grid.cells[r][c] == 1
        assert app.grid.population == 1
        app.grid.toggle(r, c)
        assert app.grid.cells[r][c] == 0
        assert app.grid.population == 0

    def test_draw_resets_cycle_detection(self):
        """Drawing cells should reset cycle detection state."""
        app = make_mock_app()
        app.state_history["some_hash"] = 0
        app.cycle_detected = True
        app.draw_mode = "draw"
        app.cursor_r, app.cursor_c = 5, 5
        _apply_draw_mode(app)
        assert app.state_history == {}
        assert app.cycle_detected is False

    def test_draw_line(self):
        """Draw a horizontal line by moving cursor right in draw mode."""
        app = make_mock_app()
        app.draw_mode = "draw"
        app.cursor_r = 10
        app.cursor_c = 5
        app.grid.set_alive(10, 5)  # Initial cell on 'd' press
        for i in range(1, 8):
            app.cursor_c = 5 + i
            _apply_draw_mode(app)
        assert app.grid.population == 8
        for i in range(8):
            assert app.grid.cells[10][5 + i] > 0


# ── Rewind / History tests ──────────────────────────────────────────────────

class TestRewind:
    """Validate rewind/undo logic against commit b42be37."""

    def test_rewind_empty_history(self):
        """Rewind with no history should flash a message, not crash."""
        app = make_mock_app()
        _rewind(app)
        assert "No history" in app.message

    def test_push_and_rewind_single_step(self):
        """Push one state and rewind should restore it."""
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        _record_pop(app)
        _step(app)  # pushes history, steps, records pop

        gen_after_step = app.grid.generation
        assert gen_after_step == 1
        # Rewind should restore generation 0
        _rewind(app)
        assert app.grid.generation == 0
        assert app.grid.cells[5][5] == 1

    def test_rewind_multiple_steps(self):
        """Multiple rewinds should walk back through history."""
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        _record_pop(app)

        # Step 5 times
        for _ in range(5):
            _step(app)

        assert app.grid.generation == 5
        assert len(app.history) == 5

        # Rewind 3 times
        for _ in range(3):
            _rewind(app)
        # Should be at history position 2 (generation 2)
        assert app.grid.generation == 2

    def test_rewind_restores_population(self):
        """Population should be restored correctly after rewind."""
        app = make_mock_app()
        # Set up a blinker
        app.grid.set_alive(5, 4)
        app.grid.set_alive(5, 5)
        app.grid.set_alive(5, 6)
        pop_before = app.grid.population
        _record_pop(app)

        _step(app)
        pop_after = app.grid.population

        _rewind(app)
        assert app.grid.population == pop_before

    def test_rewind_restores_cell_ages(self):
        """Cell ages should be restored by rewind (not just alive/dead)."""
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        _record_pop(app)

        # Step a few times so cell ages increase
        for _ in range(3):
            _step(app)

        # Record expected state at gen 3
        gen3_dict = app.grid.to_dict()

        _step(app)  # gen 4
        _step(app)  # gen 5

        # Rewind to gen 4, then gen 3
        _rewind(app)  # to gen 4
        _rewind(app)  # to gen 3

        # Verify cell data matches gen 3 snapshot
        restored_dict = app.grid.to_dict()
        assert restored_dict["generation"] == gen3_dict["generation"]
        assert restored_dict["cells"] == gen3_dict["cells"]

    def test_rewind_trims_pop_history(self):
        """Rewind should trim pop_history to the restored state."""
        app = make_mock_app()
        _record_pop(app)

        for _ in range(5):
            _step(app)

        assert len(app.pop_history) == 6  # initial + 5 steps

        _rewind(app)
        # After rewind to the last pushed state (gen 4),
        # pop_history should have 5 entries (initial + 4 steps)
        assert len(app.pop_history) == 5

    def test_history_max_enforced(self):
        """History buffer should not exceed history_max."""
        app = make_mock_app()
        app.history_max = 10
        _record_pop(app)

        for _ in range(20):
            _step(app)

        assert len(app.history) <= 10

    def test_rewind_at_oldest_state(self):
        """Rewinding past the oldest state should flash a message."""
        app = make_mock_app()
        _record_pop(app)
        _step(app)

        # Rewind once to the single history entry
        _rewind(app)
        assert app.timeline_pos == 0
        # Rewind again should report "oldest"
        _rewind(app)
        assert "oldest" in app.message.lower()

    def test_rewind_then_step_truncates_future(self):
        """Stepping after rewind should truncate future history (timeline fork)."""
        app = make_mock_app()
        _record_pop(app)

        for _ in range(5):
            _step(app)

        assert len(app.history) == 5

        # Rewind to gen 2
        _rewind(app)  # pos 4
        _rewind(app)  # pos 3
        _rewind(app)  # pos 2

        # Step forward from gen 2 — should truncate future
        _step(app)
        # History should now be [0, 1, 2, new_push] = truncated to pos 2+1=3, then +1
        # The step calls _push_history which truncates at timeline_pos+1
        # then appends. So history = history[:3] + [new] = 4 entries
        assert len(app.history) <= 4

    def test_scrub_back(self):
        """Scrub back should jump multiple steps at once."""
        app = make_mock_app()
        _record_pop(app)

        for _ in range(20):
            _step(app)

        _scrub_back(app, steps=5)
        assert app.timeline_pos is not None
        assert app.timeline_pos == len(app.history) - 5

    def test_scrub_forward_to_latest(self):
        """Scrub forward past end should return to latest state."""
        app = make_mock_app()
        _record_pop(app)

        for _ in range(10):
            _step(app)

        _scrub_back(app, steps=5)
        assert app.timeline_pos is not None

        _scrub_forward(app, steps=100)
        assert app.timeline_pos is None  # returned to live
        assert "Latest" in app.message or "latest" in app.message.lower()

    def test_scrub_forward_when_live(self):
        """Scrub forward when already at latest should flash a message."""
        app = make_mock_app()
        _record_pop(app)
        _step(app)

        _scrub_forward(app)
        assert "latest" in app.message.lower() or "Already" in app.message

    def test_rewind_and_continue_simulation(self):
        """After rewind, stepping should continue normally from restored state."""
        app = make_mock_app()
        # Set up a glider
        cells = [(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)]
        for r, c in cells:
            app.grid.set_alive(r + 10, c + 10)
        _record_pop(app)

        for _ in range(5):
            _step(app)

        _rewind(app)  # go back one
        gen_rewound = app.grid.generation

        _step(app)  # step forward again
        assert app.grid.generation == gen_rewound + 1

    def test_history_stores_grid_dict_and_pop_len(self):
        """Each history entry should be a (grid_dict, pop_len) tuple."""
        app = make_mock_app()
        app.grid.set_alive(3, 3)
        _record_pop(app)
        _push_history(app)

        assert len(app.history) == 1
        entry = app.history[0]
        assert isinstance(entry, tuple)
        assert len(entry) == 2
        grid_dict, pop_len = entry
        assert isinstance(grid_dict, dict)
        assert isinstance(pop_len, int)
        assert "cells" in grid_dict
        assert "generation" in grid_dict

    def test_grid_to_dict_round_trip(self):
        """Grid.to_dict -> Grid.load_dict should perfectly restore state."""
        g = Grid(20, 20)
        g.set_alive(5, 5)
        g.set_alive(6, 6)
        g.generation = 42
        d = g.to_dict()

        g2 = Grid(20, 20)
        g2.load_dict(d)
        assert g2.generation == 42
        assert g2.population == 2
        assert g2.cells[5][5] == g.cells[5][5]
        assert g2.cells[6][6] == g.cells[6][6]


# ── Combined draw + rewind tests ────────────────────────────────────────────

class TestDrawAndRewind:
    """Test interactions between draw mode and rewind."""

    def test_draw_then_rewind_undoes_drawing(self):
        """Drawing cells, stepping, then rewinding should undo."""
        app = make_mock_app()
        _record_pop(app)
        _push_history(app)  # save empty state

        # Draw some cells
        app.draw_mode = "draw"
        for i in range(5):
            app.cursor_r, app.cursor_c = 10, 10 + i
            _apply_draw_mode(app)
        app.draw_mode = None

        assert app.grid.population == 5

        _step(app)  # advances, pushes history of drawn state
        _step(app)

        # Rewind twice should get back to drawn state
        _rewind(app)
        _rewind(app)
        # The first history entry was the empty state
        # Rewinding past the step-pushed entries reaches the manual push
        # of the empty state
        # Let's just check we can get back to generation 0
        while app.timeline_pos is not None and app.timeline_pos > 0:
            _rewind(app)
        assert app.grid.generation == 0
        assert app.grid.population == 0

    def test_erase_then_rewind(self):
        """Erasing cells, stepping, rewinding should restore erased cells."""
        app = make_mock_app()
        for i in range(5):
            app.grid.set_alive(10, 10 + i)
        _record_pop(app)
        _push_history(app)  # save state with 5 cells

        # Erase cells
        app.draw_mode = "erase"
        for i in range(5):
            app.cursor_r, app.cursor_c = 10, 10 + i
            _apply_draw_mode(app)
        app.draw_mode = None
        assert app.grid.population == 0

        _step(app)

        # Rewind all the way
        while app.timeline_pos is None or app.timeline_pos > 0:
            _rewind(app)
        # Should be back at the state with 5 alive cells
        assert app.grid.population == 5

    def test_rewind_preserves_draw_mode_state(self):
        """Rewind should not affect the draw_mode flag itself."""
        app = make_mock_app()
        _record_pop(app)
        _step(app)

        app.draw_mode = "draw"
        _rewind(app)
        # draw_mode should still be set
        assert app.draw_mode == "draw"

    def test_full_workflow(self):
        """Full workflow: draw, step, rewind, edit, step."""
        app = make_mock_app()
        _record_pop(app)

        # Draw a block
        app.draw_mode = "draw"
        for r, c in [(10, 10), (10, 11), (11, 10), (11, 11)]:
            app.cursor_r, app.cursor_c = r, c
            _apply_draw_mode(app)
        app.draw_mode = None
        assert app.grid.population == 4

        # Step a few times (block is a still life, should remain)
        for _ in range(3):
            _step(app)
        assert app.grid.population == 4  # block is stable

        # Rewind one step
        _rewind(app)
        assert app.grid.population == 4  # still a block

        # Erase one cell to break the block
        app.draw_mode = "erase"
        app.cursor_r, app.cursor_c = 10, 10
        _apply_draw_mode(app)
        app.draw_mode = None
        assert app.grid.population == 3

        # Step forward — the broken block should evolve
        _step(app)
        # With one corner removed from a block, the remaining 3 cells
        # form an L-shape which should die or change
        assert app.grid.generation > 0
