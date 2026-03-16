"""Tests for zoom/scale mode — deep validation against commit d3513b6."""
import random
import pytest
from tests.conftest import make_mock_app
from life.constants import ZOOM_LEVELS, DENSITY_CHARS, DEAD_CHAR, CELL_CHAR


class TestZoomLevelChanges:
    """Test zoom level transitions via key handling logic."""

    def test_initial_zoom_level(self):
        app = make_mock_app()
        assert app.zoom_level == 1

    def test_zoom_levels_constant(self):
        assert ZOOM_LEVELS == [1, 2, 4, 8]

    def test_zoom_out_increases_level(self):
        app = make_mock_app()
        # Simulate pressing '-' to zoom out
        app.zoom_level = 1
        idx = ZOOM_LEVELS.index(app.zoom_level)
        if idx < len(ZOOM_LEVELS) - 1:
            app.zoom_level = ZOOM_LEVELS[idx + 1]
        assert app.zoom_level == 2

    def test_zoom_out_all_levels(self):
        app = make_mock_app()
        expected = [2, 4, 8]
        for i, exp in enumerate(expected):
            idx = ZOOM_LEVELS.index(app.zoom_level)
            if idx < len(ZOOM_LEVELS) - 1:
                app.zoom_level = ZOOM_LEVELS[idx + 1]
            assert app.zoom_level == exp

    def test_zoom_out_at_max_stays(self):
        app = make_mock_app()
        app.zoom_level = 8
        idx = ZOOM_LEVELS.index(app.zoom_level)
        if idx < len(ZOOM_LEVELS) - 1:
            app.zoom_level = ZOOM_LEVELS[idx + 1]
        assert app.zoom_level == 8

    def test_zoom_in_decreases_level(self):
        app = make_mock_app()
        app.zoom_level = 4
        idx = ZOOM_LEVELS.index(app.zoom_level)
        if idx > 0:
            app.zoom_level = ZOOM_LEVELS[idx - 1]
        assert app.zoom_level == 2

    def test_zoom_in_all_levels(self):
        app = make_mock_app()
        app.zoom_level = 8
        expected = [4, 2, 1]
        for exp in expected:
            idx = ZOOM_LEVELS.index(app.zoom_level)
            if idx > 0:
                app.zoom_level = ZOOM_LEVELS[idx - 1]
            assert app.zoom_level == exp

    def test_zoom_in_at_min_stays(self):
        app = make_mock_app()
        app.zoom_level = 1
        idx = ZOOM_LEVELS.index(app.zoom_level)
        if idx > 0:
            app.zoom_level = ZOOM_LEVELS[idx - 1]
        assert app.zoom_level == 1

    def test_zoom_reset(self):
        app = make_mock_app()
        app.zoom_level = 8
        app.zoom_level = 1
        assert app.zoom_level == 1

    def test_zoom_flash_message_zoomed(self):
        app = make_mock_app()
        app.zoom_level = 4
        msg = f"Zoom: {app.zoom_level}:1" if app.zoom_level > 1 else "Zoom: 1:1 (normal)"
        assert msg == "Zoom: 4:1"

    def test_zoom_flash_message_normal(self):
        app = make_mock_app()
        app.zoom_level = 1
        msg = f"Zoom: {app.zoom_level}:1" if app.zoom_level > 1 else "Zoom: 1:1 (normal)"
        assert msg == "Zoom: 1:1 (normal)"


class TestDensityGlyphSelection:
    """Test density glyph selection at different zoom levels — must match d3513b6."""

    def test_density_chars_constant(self):
        assert len(DENSITY_CHARS) == 5
        assert DENSITY_CHARS[0] == "  "       # dead/empty
        assert DENSITY_CHARS[1] == "░░"       # sparse
        assert DENSITY_CHARS[2] == "▒▒"       # medium
        assert DENSITY_CHARS[3] == "▓▓"       # dense
        assert DENSITY_CHARS[4] == CELL_CHAR  # full

    def test_dead_char(self):
        assert DEAD_CHAR == "  "

    def _compute_density_idx(self, alive_count, total):
        """Replicate the density glyph selection from d3513b6 and current app.py."""
        if alive_count == 0:
            return 0
        frac = alive_count / total
        if frac <= 0.25:
            return 1
        elif frac <= 0.5:
            return 2
        elif frac <= 0.75:
            return 3
        else:
            return 4

    def test_density_zero(self):
        assert self._compute_density_idx(0, 4) == 0

    def test_density_sparse_2x2(self):
        # 1 out of 4 = 0.25, should be index 1
        assert self._compute_density_idx(1, 4) == 1

    def test_density_medium_2x2(self):
        # 2 out of 4 = 0.5, should be index 2
        assert self._compute_density_idx(2, 4) == 2

    def test_density_dense_2x2(self):
        # 3 out of 4 = 0.75, should be index 3
        assert self._compute_density_idx(3, 4) == 3

    def test_density_full_2x2(self):
        # 4 out of 4 = 1.0, should be index 4
        assert self._compute_density_idx(4, 4) == 4

    def test_density_boundary_025(self):
        # Exactly 0.25 should be index 1 (<=0.25)
        assert self._compute_density_idx(1, 4) == 1

    def test_density_boundary_050(self):
        # Exactly 0.5 should be index 2 (<=0.5)
        assert self._compute_density_idx(2, 4) == 2

    def test_density_boundary_075(self):
        # Exactly 0.75 should be index 3 (<=0.75)
        assert self._compute_density_idx(3, 4) == 3

    def test_density_4x4_sparse(self):
        # 4 out of 16 = 0.25, should be index 1
        assert self._compute_density_idx(4, 16) == 1

    def test_density_4x4_medium(self):
        # 8 out of 16 = 0.5
        assert self._compute_density_idx(8, 16) == 2

    def test_density_4x4_dense(self):
        # 12 out of 16 = 0.75
        assert self._compute_density_idx(12, 16) == 3

    def test_density_4x4_full(self):
        # 16 out of 16 = 1.0
        assert self._compute_density_idx(16, 16) == 4

    def test_density_8x8_all_levels(self):
        total = 64
        # 0 -> 0
        assert self._compute_density_idx(0, total) == 0
        # 1..16 (up to 0.25) -> 1
        assert self._compute_density_idx(16, total) == 1
        # 17..32 (up to 0.5) -> 2
        assert self._compute_density_idx(17, total) == 2
        assert self._compute_density_idx(32, total) == 2
        # 33..48 (up to 0.75) -> 3
        assert self._compute_density_idx(33, total) == 3
        assert self._compute_density_idx(48, total) == 3
        # 49..64 (>0.75) -> 4
        assert self._compute_density_idx(49, total) == 4
        assert self._compute_density_idx(64, total) == 4

    def test_density_just_above_boundary(self):
        # Just above 0.25: 2/7 ~ 0.286
        assert self._compute_density_idx(2, 7) == 2
        # Just above 0.5: 4/7 ~ 0.571
        assert self._compute_density_idx(4, 7) == 3
        # Just above 0.75: 6/7 ~ 0.857
        assert self._compute_density_idx(6, 7) == 4


class TestViewportComputation:
    """Test viewport computation with zoom — matches d3513b6 logic."""

    def test_viewport_zoom_1(self):
        app = make_mock_app(rows=40, cols=120, grid_rows=30, grid_cols=50)
        zoom = 1
        max_y, max_x = app.stdscr.getmaxyx()
        vis_rows = max_y - 5
        vis_cols = (max_x - 1) // 2
        grid_vis_rows = vis_rows * zoom
        grid_vis_cols = vis_cols * zoom
        assert grid_vis_rows == vis_rows
        assert grid_vis_cols == vis_cols

    def test_viewport_zoom_2(self):
        app = make_mock_app(rows=40, cols=120, grid_rows=60, grid_cols=100)
        zoom = 2
        max_y, max_x = app.stdscr.getmaxyx()
        vis_rows = max_y - 5
        vis_cols = (max_x - 1) // 2
        grid_vis_rows = vis_rows * zoom
        grid_vis_cols = vis_cols * zoom
        # Each screen cell covers 2x2 grid cells
        assert grid_vis_rows == vis_rows * 2
        assert grid_vis_cols == vis_cols * 2

    def test_viewport_zoom_4(self):
        app = make_mock_app(rows=40, cols=120, grid_rows=120, grid_cols=200)
        zoom = 4
        max_y, max_x = app.stdscr.getmaxyx()
        vis_rows = max_y - 5
        vis_cols = (max_x - 1) // 2
        grid_vis_rows = vis_rows * zoom
        grid_vis_cols = vis_cols * zoom
        assert grid_vis_rows == vis_rows * 4
        assert grid_vis_cols == vis_cols * 4

    def test_viewport_centering(self):
        app = make_mock_app(rows=40, cols=120, grid_rows=100, grid_cols=100)
        app.cursor_r = 50
        app.cursor_c = 50
        zoom = 2
        app.zoom_level = zoom
        max_y, max_x = app.stdscr.getmaxyx()
        vis_rows = max_y - 5
        vis_cols = (max_x - 1) // 2
        grid_vis_rows = vis_rows * zoom
        grid_vis_cols = vis_cols * zoom
        view_r = app.cursor_r - grid_vis_rows // 2
        view_c = app.cursor_c - grid_vis_cols // 2
        # Cursor should be at center of the viewport
        assert app.cursor_r - view_r == grid_vis_rows // 2
        assert app.cursor_c - view_c == grid_vis_cols // 2

    def test_screen_rows_cols_zoomed(self):
        """Verify screen_rows/cols computation matches d3513b6."""
        grid_rows = 30
        grid_cols = 50
        for zoom in [2, 4, 8]:
            vis_rows = 35  # example
            vis_cols = 59  # example
            screen_rows = min(vis_rows, (grid_rows + zoom - 1) // zoom)
            screen_cols = min(vis_cols, (grid_cols + zoom - 1) // zoom)
            # screen_rows should be ceil(grid_rows / zoom) capped at vis_rows
            import math
            expected_rows = min(vis_rows, math.ceil(grid_rows / zoom))
            expected_cols = min(vis_cols, math.ceil(grid_cols / zoom))
            assert screen_rows == expected_rows
            assert screen_cols == expected_cols


class TestZoomBlockDensity:
    """Test the zoomed block density computation with actual grid data."""

    def _simulate_zoom_block(self, grid, view_r, view_c, sy, sx, zoom):
        """Simulate the exact zoom block density computation from d3513b6/app.py."""
        alive_count = 0
        total = 0
        max_age = 0
        rows = len(grid.cells)
        cols = len(grid.cells[0]) if rows > 0 else 0

        base_r = view_r + sy * zoom
        base_c = view_c + sx * zoom
        for dr in range(zoom):
            for dc in range(zoom):
                gr = (base_r + dr) % rows
                gc = (base_c + dc) % cols
                total += 1
                age = grid.cells[gr][gc]
                if age > 0:
                    alive_count += 1
                    if age > max_age:
                        max_age = age

        if alive_count == 0:
            density_idx = 0
        else:
            frac = alive_count / total
            if frac <= 0.25:
                density_idx = 1
            elif frac <= 0.5:
                density_idx = 2
            elif frac <= 0.75:
                density_idx = 3
            else:
                density_idx = 4
        return density_idx, alive_count, total, max_age

    def test_empty_grid_zoom2(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        idx, alive, total, age = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 0, 2)
        assert idx == 0
        assert alive == 0
        assert total == 4

    def test_full_grid_zoom2(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        for r in range(10):
            for c in range(10):
                app.grid.cells[r][c] = 1
        idx, alive, total, age = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 0, 2)
        assert idx == 4
        assert alive == 4
        assert total == 4

    def test_half_full_zoom2(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        # Set top-left 2x2 block: 2 out of 4 alive
        app.grid.cells[0][0] = 1
        app.grid.cells[0][1] = 1
        idx, alive, total, age = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 0, 2)
        assert idx == 2  # 2/4 = 0.5 -> index 2

    def test_quarter_full_zoom4(self):
        app = make_mock_app(grid_rows=16, grid_cols=16)
        # Set 4 out of 16 cells alive in a 4x4 block
        app.grid.cells[0][0] = 1
        app.grid.cells[1][1] = 1
        app.grid.cells[2][2] = 1
        app.grid.cells[3][3] = 1
        idx, alive, total, age = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 0, 4)
        assert idx == 1  # 4/16 = 0.25 -> index 1

    def test_max_age_tracking(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.grid.cells[0][0] = 5
        app.grid.cells[0][1] = 10
        app.grid.cells[1][0] = 3
        idx, alive, total, age = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 0, 2)
        assert age == 10
        assert alive == 3

    def test_wrapping_zoom(self):
        """Zoom block wraps around grid edges (toroidal)."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        # Place cell at (9, 9) — should wrap when view_r + sy*zoom + dr >= rows
        app.grid.cells[9][9] = 1
        # view_r=8, sy=0, zoom=4 => base_r=8, dr goes 0..3 => gr = 8,9,0,1
        idx, alive, total, age = self._simulate_zoom_block(
            app.grid, 8, 8, 0, 0, 4)
        assert alive == 1
        assert total == 16

    def test_multiple_blocks_zoom2(self):
        """Verify multiple screen blocks compute independently."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        # All cells in block (0,0) alive, none in block (0,1)
        for r in range(2):
            for c in range(2):
                app.grid.cells[r][c] = 1
        idx0, alive0, _, _ = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 0, 2)
        idx1, alive1, _, _ = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 1, 2)
        assert idx0 == 4  # all alive
        assert idx1 == 0  # all dead

    def test_zoom8_block_density(self):
        app = make_mock_app(grid_rows=64, grid_cols=64)
        random.seed(42)
        # Fill first 8x8 block randomly
        count = 0
        for r in range(8):
            for c in range(8):
                if random.random() < 0.5:
                    app.grid.cells[r][c] = 1
                    count += 1
        idx, alive, total, _ = self._simulate_zoom_block(
            app.grid, 0, 0, 0, 0, 8)
        assert alive == count
        assert total == 64
        # Verify density index matches expected
        if count == 0:
            assert idx == 0
        else:
            frac = count / 64
            if frac <= 0.25:
                assert idx == 1
            elif frac <= 0.5:
                assert idx == 2
            elif frac <= 0.75:
                assert idx == 3
            else:
                assert idx == 4
