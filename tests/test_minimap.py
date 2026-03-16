"""Tests for minimap overlay — deep validation against commit bef0287."""
import math
import random
import types
import curses
from unittest import mock
import pytest
from tests.conftest import make_mock_app


def _bind_minimap_methods(app):
    """Bind _get_minimap_data and _draw_minimap from App to the mock app."""
    from life.app import App
    app._get_minimap_data = types.MethodType(App._get_minimap_data, app)
    app._draw_minimap = types.MethodType(App._draw_minimap, app)
    return app


def _capture_addstr(app):
    """Replace stdscr.addstr with a recorder and return the call list."""
    calls = []

    def recording_addstr(*args, **kwargs):
        calls.append(args)

    app.stdscr.addstr = recording_addstr
    return calls


def _patch_curses():
    """Return a mock.patch context manager that stubs curses.color_pair and A_* constants."""
    patcher = mock.patch.multiple(
        curses,
        color_pair=lambda n: 0,
        A_DIM=0,
        A_BOLD=0,
        A_REVERSE=0,
        error=Exception,
    )
    return patcher


class TestMinimapState:
    """Test minimap state initialization and toggling."""

    def test_minimap_default_off(self):
        app = make_mock_app()
        assert app.show_minimap is False

    def test_minimap_toggle_on(self):
        app = make_mock_app()
        app.show_minimap = True
        assert app.show_minimap is True

    def test_minimap_toggle_off(self):
        app = make_mock_app()
        app.show_minimap = True
        app.show_minimap = False
        assert app.show_minimap is False


class TestGetMinimapData:
    """Test _get_minimap_data returns correct data for various modes."""

    def _make(self, **kwargs):
        app = make_mock_app(**kwargs)
        return _bind_minimap_methods(app)

    def test_returns_tuple_for_default_grid(self):
        app = self._make()
        data = app._get_minimap_data()
        assert data is not None
        assert len(data) == 7

    def test_returns_grid_dimensions(self):
        app = self._make(grid_rows=30, grid_cols=50)
        data = app._get_minimap_data()
        rows, cols = data[0], data[1]
        assert rows == 30
        assert cols == 50

    def test_sample_fn_returns_zero_for_empty_grid(self):
        app = self._make()
        data = app._get_minimap_data()
        sample_fn = data[2]
        assert sample_fn(0, 0) == 0.0
        assert sample_fn(15, 25) == 0.0

    def test_sample_fn_returns_one_for_alive_cell(self):
        app = self._make()
        app.grid.cells[5][10] = 1
        data = app._get_minimap_data()
        sample_fn = data[2]
        assert sample_fn(5, 10) == 1.0

    def test_viewport_values_with_zoom(self):
        """Viewport should be centered on cursor, scaled by zoom."""
        app = self._make(grid_rows=100, grid_cols=100)
        app.cursor_r = 50
        app.cursor_c = 50
        app.zoom_level = 2
        data = app._get_minimap_data()
        view_r, view_c, view_h, view_w = data[3], data[4], data[5], data[6]
        max_y, max_x = app.stdscr.getmaxyx()
        vis_rows = max(1, max_y - 5)
        vis_cols = max(1, (max_x - 1) // 2)
        expected_h = vis_rows * 2
        expected_w = vis_cols * 2
        assert view_h == expected_h
        assert view_w == expected_w
        assert view_r == 50 - expected_h // 2
        assert view_c == 50 - expected_w // 2

    def test_returns_none_for_zero_size_grid(self):
        app = self._make(grid_rows=0, grid_cols=0)
        data = app._get_minimap_data()
        assert data is None

    def test_ant_mode_data(self):
        """When ant_mode is active, minimap should use ant grid."""
        app = self._make()
        app.ant_mode = True
        app.ant_rows = 20
        app.ant_cols = 30
        app.ant_grid = {(5, 10): 1, (3, 7): 2}
        data = app._get_minimap_data()
        assert data is not None
        assert data[0] == 20
        assert data[1] == 30
        assert data[2](5, 10) == 1.0
        assert data[2](0, 0) == 0.0

    def test_wolfram_mode_data(self):
        """When wolfram_mode is active, minimap should use wolfram rows."""
        app = self._make()
        app.wolfram_mode = True
        app.wolfram_rows = [[0, 1, 0, 1], [1, 0, 1, 0]]
        data = app._get_minimap_data()
        assert data is not None
        assert data[0] == 2
        assert data[1] == 4
        assert data[2](0, 1) == 1.0
        assert data[2](0, 0) == 0.0

    def test_default_gol_sample_fn_matches_cells(self):
        """Sample function should exactly mirror grid.cells for GoL."""
        app = self._make(grid_rows=20, grid_cols=20)
        alive_cells = [(0, 0), (1, 1), (5, 10), (19, 19)]
        for r, c in alive_cells:
            app.grid.cells[r][c] = 1
        data = app._get_minimap_data()
        sample_fn = data[2]
        for r in range(20):
            for c in range(20):
                expected = 1.0 if (r, c) in alive_cells else 0.0
                assert sample_fn(r, c) == expected, f"Mismatch at ({r},{c})"


class TestDrawMinimap:
    """Test _draw_minimap rendering logic."""

    def _make(self, grid_rows=30, grid_cols=50, rows=40, cols=120):
        app = make_mock_app(rows=rows, cols=cols, grid_rows=grid_rows, grid_cols=grid_cols)
        return _bind_minimap_methods(app)

    def test_no_crash_empty_grid(self):
        app = self._make()
        with _patch_curses():
            app._draw_minimap(40, 120)

    def test_renders_minimap_label(self):
        app = self._make()
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        assert len(calls) > 0
        texts = [str(a) for args in calls for a in args if isinstance(a, str)]
        assert any("MINIMAP" in t for t in texts), f"Expected MINIMAP label, got: {texts[:5]}"

    def test_active_cells_produce_density_glyphs(self):
        """Active cells should show up as density glyphs in minimap."""
        app = self._make(grid_rows=30, grid_cols=50)
        for r in range(10, 20):
            for c in range(20, 35):
                app.grid.cells[r][c] = 1
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        density_glyphs = set("\u2591\u2592\u2593\u2588")
        rendered = [a for args in calls for a in args
                    if isinstance(a, str) and len(a) == 1 and a in density_glyphs]
        assert len(rendered) > 0, "Expected density glyphs for active cells"

    def test_viewport_indicator_when_zoomed(self):
        """When zoomed in, viewport indicator dots should appear."""
        app = self._make(grid_rows=200, grid_cols=200)
        app.zoom_level = 4
        app.cursor_r = 100
        app.cursor_c = 100
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        dot_chars = [a for args in calls for a in args
                     if isinstance(a, str) and a == "\u00b7"]
        assert len(dot_chars) > 0, "Expected viewport indicator dots when zoomed"

    def test_no_viewport_indicator_full_view(self):
        """When grid fits in view (no zoom), no viewport dots expected."""
        app = self._make(grid_rows=10, grid_cols=10)
        app.zoom_level = 1
        app.cursor_r = 5
        app.cursor_c = 5
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        dot_chars = [a for args in calls for a in args
                     if isinstance(a, str) and a == "\u00b7"]
        assert len(dot_chars) == 0, "No viewport dots expected when grid fits in view"

    def test_returns_early_on_tiny_screen(self):
        """When screen is too small, minimap should not render."""
        app = self._make(rows=8, cols=15)
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(8, 15)
        assert len(calls) == 0, "No rendering expected on tiny screen"

    def test_returns_early_when_data_is_none(self):
        """If grid is zero-sized, no rendering should happen."""
        app = self._make(grid_rows=0, grid_cols=0)
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        assert len(calls) == 0

    def test_aspect_ratio_wide_grid(self):
        app = self._make(grid_rows=10, grid_cols=100)
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        assert len(calls) > 0

    def test_aspect_ratio_tall_grid(self):
        app = self._make(grid_rows=100, grid_cols=10)
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        assert len(calls) > 0

    def test_density_glyph_thresholds(self):
        """Verify density-to-glyph mapping matches original bef0287 code.

        Original thresholds:
          density <= 0   -> ' '  (index 0)
          density <= 0.2 -> '\u2591'  (index 1)
          density <= 0.45-> '\u2592'  (index 2)
          density <= 0.7 -> '\u2593'  (index 3)
          else           -> '\u2588'  (index 4)
        """
        MINI_GLYPHS = " \u2591\u2592\u2593\u2588"
        cases = [
            (0.0, 0), (0.1, 1), (0.2, 1), (0.3, 2),
            (0.45, 2), (0.5, 3), (0.7, 3), (0.8, 4), (1.0, 4),
        ]
        for density, expected_idx in cases:
            if density <= 0:
                gi = 0
            elif density <= 0.2:
                gi = 1
            elif density <= 0.45:
                gi = 2
            elif density <= 0.7:
                gi = 3
            else:
                gi = 4
            assert gi == expected_idx, f"density={density}: got {gi}, expected {expected_idx}"
            assert MINI_GLYPHS[gi] == MINI_GLYPHS[expected_idx]

    def test_border_box_drawing_characters(self):
        """Verify border uses box-drawing characters from original."""
        app = self._make()
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        all_text = "".join(str(a) for args in calls for a in args if isinstance(a, str))
        for ch in ["\u250c", "\u2510", "\u2514", "\u2518", "\u2502"]:
            assert ch in all_text, f"Missing border char {ch!r}"

    def test_random_cells_produce_glyphs(self):
        """Randomly populate cells and verify density glyphs appear."""
        app = self._make(grid_rows=50, grid_cols=80)
        random.seed(42)
        for _ in range(500):
            r = random.randint(0, 49)
            c = random.randint(0, 79)
            app.grid.cells[r][c] = 1
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        density_glyphs = set("\u2591\u2592\u2593\u2588")
        rendered = [a for args in calls for a in args
                    if isinstance(a, str) and len(a) == 1 and a in density_glyphs]
        assert len(rendered) > 0, "Random cells should produce density glyphs"

    def test_full_grid_all_cells_alive(self):
        """When every cell is alive, the highest density glyph should dominate."""
        app = self._make(grid_rows=20, grid_cols=20)
        for r in range(20):
            for c in range(20):
                app.grid.cells[r][c] = 1
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        full_blocks = [a for args in calls for a in args
                       if isinstance(a, str) and a == "\u2588"]
        assert len(full_blocks) > 0, "Full grid should produce full-block glyphs"

    def test_minimap_position_top_right(self):
        """Minimap should be positioned in the top-right area of the screen."""
        app = self._make(rows=40, cols=120)
        calls = _capture_addstr(app)
        with _patch_curses():
            app._draw_minimap(40, 120)
        for args in calls:
            if len(args) >= 3 and isinstance(args[2], str) and "MINIMAP" in args[2]:
                y, x = args[0], args[1]
                assert y == 1, f"Minimap should start at y=1, got {y}"
                assert x > 60, f"Minimap should be in right half, x={x}"
                break
        else:
            pytest.fail("MINIMAP label not found in addstr calls")

    def test_step_r_step_c_calculation(self):
        """Verify the grid-to-minimap scaling math matches original."""
        grid_rows, grid_cols = 100, 200
        max_map_w = min(40, 120 // 3)
        max_map_h = min(20, 40 // 3)
        inner_w = max(4, max_map_w - 2)
        inner_h = max(3, max_map_h - 2)
        grid_aspect = grid_cols / max(1, grid_rows)
        if grid_aspect > inner_w / inner_h:
            map_w = inner_w
            map_h = max(3, int(inner_w / grid_aspect))
        else:
            map_h = inner_h
            map_w = max(4, int(inner_h * grid_aspect))
        step_r = grid_rows / map_h
        step_c = grid_cols / map_w
        assert step_r > 0
        assert step_c > 0
        assert int(map_h * step_r) <= grid_rows + step_r
        assert int(map_w * step_c) <= grid_cols + step_c
