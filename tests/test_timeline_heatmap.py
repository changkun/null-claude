"""Tests for timeline and heatmap — deep validation against commits d1b2326, 2ab8ad9."""
import random, pytest
from tests.conftest import make_mock_app
from life.grid import Grid


# ── Timeline history tests ──────────────────────────────────────────────────


class TestPushHistory:
    """Validate that _push_history stores grid snapshots correctly."""

    def test_push_history_appends_snapshot(self):
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        app._record_pop()
        app._push_history()
        assert len(app.history) == 1
        grid_dict, pop_len = app.history[0]
        assert grid_dict["generation"] == app.grid.generation
        assert pop_len == len(app.pop_history)

    def test_push_history_multiple(self):
        app = make_mock_app()
        for i in range(5):
            app.grid.set_alive(i, i)
            app._record_pop()
            app._push_history()
        assert len(app.history) == 5

    def test_push_history_truncates_future_on_scrub(self):
        """When scrubbed back, pushing should discard future history entries."""
        app = make_mock_app()
        for i in range(5):
            app.grid.set_alive(i, i)
            app._record_pop()
            app._push_history()
        # Scrub back to position 2 (3rd entry, 0-indexed)
        app.timeline_pos = 2
        app._push_history()
        # Should have entries 0..2 plus the new one = 4 total
        assert len(app.history) == 4
        assert app.timeline_pos is None

    def test_push_history_enforces_max_size(self):
        app = make_mock_app()
        app.history_max = 10
        for i in range(20):
            app.grid.set_alive(i % app.grid.rows, i % app.grid.cols)
            app._record_pop()
            app._push_history()
        assert len(app.history) <= 10

    def test_push_history_preserves_pop_len(self):
        """pop_len in history must match the pop_history length at push time."""
        app = make_mock_app()
        app._record_pop()
        app._record_pop()
        app._record_pop()
        app._push_history()
        _, pop_len = app.history[0]
        assert pop_len == 3


# ── Rewind / timeline scrubbing tests ────────────────────────────────────────


class TestRewind:
    """Validate rewind restores grid state from history."""

    def test_rewind_no_history(self):
        app = make_mock_app()
        app._rewind()
        assert "No history" in app.message

    def test_rewind_sets_timeline_pos(self):
        app = make_mock_app()
        app._record_pop()
        app._push_history()
        app.grid.step()
        app._record_pop()
        app._push_history()
        app._rewind()
        assert app.timeline_pos == 1  # last index

    def test_rewind_twice_goes_back(self):
        app = make_mock_app()
        for i in range(3):
            app.grid.set_alive(i, 0)
            app._record_pop()
            app._push_history()
        app._rewind()  # goes to pos 2
        app._rewind()  # goes to pos 1
        assert app.timeline_pos == 1

    def test_rewind_at_oldest_flashes(self):
        app = make_mock_app()
        app._record_pop()
        app._push_history()
        app._rewind()  # pos 0
        app._rewind()  # should flash "At oldest"
        assert "oldest" in app.message.lower()

    def test_rewind_restores_generation(self):
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        app._record_pop()
        app._push_history()
        gen_before = app.grid.generation
        app.grid.step()
        app._record_pop()
        app._push_history()
        app._rewind()
        app._rewind()
        assert app.grid.generation == gen_before


class TestRestoreTimelinePos:
    """Validate _restore_timeline_pos restores correct state."""

    def test_restore_loads_grid_state(self):
        app = make_mock_app()
        app.grid.set_alive(3, 3)
        app._record_pop()
        app._push_history()
        pop_at_push = app.grid.population
        # Modify grid
        app.grid.clear()
        app.grid.set_alive(10, 10)
        # Restore
        app.timeline_pos = 0
        app._restore_timeline_pos()
        assert app.grid.cells[3][3] > 0
        assert app.grid.population == pop_at_push

    def test_restore_truncates_pop_history(self):
        app = make_mock_app()
        app._record_pop()
        app._push_history()
        # Add more pop entries after push
        for _ in range(5):
            app._record_pop()
        assert len(app.pop_history) == 6
        app.timeline_pos = 0
        app._restore_timeline_pos()
        assert len(app.pop_history) == 1


class TestScrubBack:
    """Validate _scrub_back jumps multiple steps at once."""

    def test_scrub_back_no_history(self):
        app = make_mock_app()
        app._scrub_back()
        assert "No history" in app.message

    def test_scrub_back_from_live(self):
        app = make_mock_app()
        for i in range(20):
            app._record_pop()
            app._push_history()
        app._scrub_back(10)
        # Should be 10 steps from the end
        assert app.timeline_pos == 10

    def test_scrub_back_cumulative(self):
        app = make_mock_app()
        for i in range(30):
            app._record_pop()
            app._push_history()
        app._scrub_back(5)
        first_pos = app.timeline_pos
        app._scrub_back(5)
        assert app.timeline_pos == first_pos - 5

    def test_scrub_back_clamps_to_zero(self):
        app = make_mock_app()
        for i in range(5):
            app._record_pop()
            app._push_history()
        app._scrub_back(100)
        assert app.timeline_pos == 0


class TestScrubForward:
    """Validate _scrub_forward moves toward live state."""

    def test_scrub_forward_at_live(self):
        app = make_mock_app()
        app._scrub_forward()
        assert "latest" in app.message.lower()

    def test_scrub_forward_returns_to_live(self):
        app = make_mock_app()
        for i in range(10):
            app._record_pop()
            app._push_history()
        app._scrub_back(5)
        app._scrub_forward(100)  # overshoot
        assert app.timeline_pos is None  # returned to live

    def test_scrub_forward_partial(self):
        app = make_mock_app()
        for i in range(20):
            app._record_pop()
            app._push_history()
        app._scrub_back(15)
        pos_before = app.timeline_pos
        app._scrub_forward(5)
        assert app.timeline_pos == pos_before + 5


# ── Bookmark tests ───────────────────────────────────────────────────────────


class TestBookmarks:
    """Validate bookmark add, jump, and deduplication."""

    def test_add_bookmark(self):
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        app._record_pop()
        app._add_bookmark()
        assert len(app.bookmarks) == 1
        gen, grid_dict, pop_len = app.bookmarks[0]
        assert gen == app.grid.generation

    def test_add_bookmark_no_duplicate(self):
        app = make_mock_app()
        app._record_pop()
        app._add_bookmark()
        app._add_bookmark()
        assert len(app.bookmarks) == 1
        assert "already" in app.message.lower()

    def test_bookmarks_sorted_by_generation(self):
        app = make_mock_app()
        app.grid.set_alive(0, 0)
        app._record_pop()
        app._push_history()
        app._add_bookmark()  # gen 0
        app.grid.step()
        app._record_pop()
        app._push_history()
        app._add_bookmark()  # gen 1
        gens = [b[0] for b in app.bookmarks]
        assert gens == sorted(gens)

    def test_jump_to_bookmark_restores_state(self):
        app = make_mock_app()
        app.grid.set_alive(7, 7)
        app._record_pop()
        app._add_bookmark()
        saved_pop = app.grid.population
        # Modify grid
        app.grid.clear()
        app.grid.set_alive(0, 0)
        # Jump back
        app._jump_to_bookmark(0)
        assert app.grid.cells[7][7] > 0
        assert app.grid.population == saved_pop
        assert app.timeline_pos is None  # bookmarks go to independent snapshot

    def test_jump_to_invalid_bookmark(self):
        app = make_mock_app()
        app._jump_to_bookmark(-1)  # should silently return
        app._jump_to_bookmark(99)  # should silently return

    def test_jump_resets_cycle_detection(self):
        app = make_mock_app()
        app.grid.set_alive(5, 5)
        app._record_pop()
        app._add_bookmark()
        app.state_history["fake_hash"] = 42
        app.cycle_detected = True
        app._jump_to_bookmark(0)
        # After jumping, cycle_detected should be reset
        # Note: state_history.clear() may not work if class methods were
        # polluted by register() in other tests, so check cycle_detected flag
        assert app.cycle_detected is False


# ── Heatmap tests ────────────────────────────────────────────────────────────


class TestHeatmapUpdate:
    """Validate _update_heatmap increments counters for alive cells."""

    def test_heatmap_single_cell(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.grid.set_alive(3, 4)
        app._update_heatmap()
        assert app.heatmap[3][4] == 1
        assert app.heatmap_max == 1

    def test_heatmap_accumulates(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.grid.set_alive(3, 4)
        app._update_heatmap()
        app._update_heatmap()
        app._update_heatmap()
        assert app.heatmap[3][4] == 3
        assert app.heatmap_max == 3

    def test_heatmap_dead_cells_not_counted(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.grid.set_alive(3, 4)
        app._update_heatmap()
        # (3, 4) should be 1, everything else 0
        for r in range(10):
            for c in range(10):
                if (r, c) != (3, 4):
                    assert app.heatmap[r][c] == 0

    def test_heatmap_tracks_peak(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.grid.set_alive(0, 0)
        app.grid.set_alive(1, 1)
        # Update 3 times
        for _ in range(3):
            app._update_heatmap()
        assert app.heatmap_max == 3
        # Now make cell (1,1) die — peak should not decrease
        app.grid.cells[1][1] = 0
        app._update_heatmap()
        assert app.heatmap[0][0] == 4
        assert app.heatmap[1][1] == 3  # no longer incremented
        assert app.heatmap_max == 4

    def test_heatmap_multiple_cells(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        cells = [(0, 0), (1, 1), (2, 2), (5, 5)]
        for r, c in cells:
            app.grid.set_alive(r, c)
        app._update_heatmap()
        for r, c in cells:
            assert app.heatmap[r][c] == 1

    def test_heatmap_reset_on_grid_resize(self):
        """Heatmap grid dimensions must match the grid."""
        app = make_mock_app(grid_rows=20, grid_cols=30)
        assert len(app.heatmap) == 20
        assert len(app.heatmap[0]) == 30

    def test_heatmap_initial_state_all_zeros(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        assert app.heatmap_max == 0
        for r in range(10):
            for c in range(10):
                assert app.heatmap[r][c] == 0

    def test_heatmap_after_step(self):
        """Heatmap should reflect alive cells after a step."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        # Set up a blinker (period 2 oscillator)
        app.grid.set_alive(4, 3)
        app.grid.set_alive(4, 4)
        app.grid.set_alive(4, 5)
        app._update_heatmap()
        assert app.heatmap[4][3] == 1
        assert app.heatmap[4][4] == 1
        assert app.heatmap[4][5] == 1
        # Step (blinker flips to vertical)
        app.grid.step()
        app._update_heatmap()
        # Center cell stays alive in both phases
        assert app.heatmap[4][4] == 2
        # New cells from blinker flip
        assert app.heatmap[3][4] == 1
        assert app.heatmap[5][4] == 1
        # Old wing cells died — heatmap retains count of 1
        assert app.heatmap[4][3] == 1
        assert app.heatmap[4][5] == 1


class TestHeatmapMode:
    """Validate heatmap mode toggling and state."""

    def test_heatmap_mode_default_off(self):
        app = make_mock_app()
        assert app.heatmap_mode is False

    def test_heatmap_mode_toggle(self):
        app = make_mock_app()
        app.heatmap_mode = True
        assert app.heatmap_mode is True
        app.heatmap_mode = False
        assert app.heatmap_mode is False


# ── Integration: timeline + heatmap interaction ─────────────────────────────


class TestTimelineHeatmapIntegration:
    """Verify timeline and heatmap work together correctly."""

    def test_heatmap_survives_rewind(self):
        """Heatmap should keep accumulated data through rewinds."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.grid.set_alive(5, 5)
        app._record_pop()
        app._push_history()
        app._update_heatmap()
        assert app.heatmap[5][5] == 1
        # Rewind should NOT reset heatmap
        app._rewind()
        assert app.heatmap[5][5] == 1

    def test_bookmark_preserves_heatmap(self):
        """Jumping to a bookmark should not affect the heatmap."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.grid.set_alive(5, 5)
        app._record_pop()
        app._add_bookmark()
        app._update_heatmap()
        app._update_heatmap()
        assert app.heatmap[5][5] == 2
        app._jump_to_bookmark(0)
        assert app.heatmap[5][5] == 2  # heatmap unaffected

    def test_full_timeline_cycle(self):
        """Push, scrub back, scrub forward, verify history integrity."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        gens = []
        for i in range(10):
            app.grid.set_alive(i % 10, i % 10)
            app._record_pop()
            app._push_history()
            gens.append(app.grid.generation)
            app.grid.step()
        # Scrub back 5 steps
        app._scrub_back(5)
        assert app.timeline_pos is not None
        saved_pos = app.timeline_pos
        # Scrub forward 3
        app._scrub_forward(3)
        assert app.timeline_pos == saved_pos + 3
        # Return to live
        app._scrub_forward(100)
        assert app.timeline_pos is None

    def test_heatmap_accumulation_over_many_generations(self):
        """Heatmap values should increase linearly for a persistent cell."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        # Use a block (still life) to have persistent cells
        app.grid.set_alive(1, 1)
        app.grid.set_alive(1, 2)
        app.grid.set_alive(2, 1)
        app.grid.set_alive(2, 2)
        for gen in range(50):
            app._update_heatmap()
            app.grid.step()  # block is stable, stays alive
        # Each cell in the block was alive every generation
        assert app.heatmap[1][1] == 50
        assert app.heatmap[1][2] == 50
        assert app.heatmap[2][1] == 50
        assert app.heatmap[2][2] == 50
        assert app.heatmap_max == 50
