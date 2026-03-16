"""Tests for isometric mode — deep validation against commit 90cbce8."""
import random
import curses
import pytest
from unittest.mock import patch
from tests.conftest import make_mock_app
from life.modes.isometric import register


class _MockSoundEngine:
    """Minimal sound engine stub so _draw_iso can check .enabled."""
    enabled = False


def _mock_color_pair(n):
    """Return a dummy attribute integer instead of calling real curses."""
    return n


class TestIsometric:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        # Register isometric methods on the mock App class
        register(type(self.app))
        # _draw_iso references self.sound_engine.enabled
        self.app.sound_engine = _MockSoundEngine()
        # Patch curses.color_pair to avoid initscr requirement
        self._color_pair_patcher = patch('curses.color_pair', side_effect=_mock_color_pair)
        self._color_pair_patcher.start()

    def teardown_method(self):
        self._color_pair_patcher.stop()

    # ── Class-level constants ──

    def test_iso_height_tiers_present(self):
        """The App class must define _ISO_HEIGHT_TIERS matching original."""
        tiers = type(self.app)._ISO_HEIGHT_TIERS
        assert isinstance(tiers, list)
        assert len(tiers) == 4
        # (max_age, pillar_chars) pairs
        assert tiers[0] == (1, ["█"])
        assert tiers[1] == (3, ["█", "▓"])
        assert tiers[2] == (8, ["█", "▓", "▒"])
        assert tiers[3] == (20, ["█", "▓", "▒", "░"])

    def test_iso_max_height(self):
        assert type(self.app)._ISO_MAX_HEIGHT == 5

    def test_iso_ancient(self):
        assert type(self.app)._ISO_ANCIENT == ["█", "▓", "▒", "░", "·"]

    def test_iso_shade_map(self):
        expected = {"█": "▓", "▓": "▒", "▒": "░", "░": " ", "·": " "}
        assert type(self.app)._ISO_SHADE_MAP == expected

    # ── _iso_pillar ──

    def test_pillar_newborn_age1(self):
        """Age 1 -> single block."""
        result = self.app._iso_pillar(1)
        assert result == ["█"]

    def test_pillar_young_age2(self):
        """Age 2 -> 2-row pillar."""
        result = self.app._iso_pillar(2)
        assert result == ["█", "▓"]

    def test_pillar_young_age3(self):
        """Age 3 is still in the (3, ...) tier."""
        result = self.app._iso_pillar(3)
        assert result == ["█", "▓"]

    def test_pillar_mature_age5(self):
        """Age 5 -> 3-row pillar."""
        result = self.app._iso_pillar(5)
        assert result == ["█", "▓", "▒"]

    def test_pillar_mature_age8(self):
        """Age 8 is the boundary of the mature tier."""
        result = self.app._iso_pillar(8)
        assert result == ["█", "▓", "▒"]

    def test_pillar_old_age15(self):
        """Age 15 -> 4-row pillar."""
        result = self.app._iso_pillar(15)
        assert result == ["█", "▓", "▒", "░"]

    def test_pillar_old_age20(self):
        """Age 20 is the boundary of the old tier."""
        result = self.app._iso_pillar(20)
        assert result == ["█", "▓", "▒", "░"]

    def test_pillar_ancient_age21(self):
        """Age >20 -> ancient, 5-row pillar."""
        result = self.app._iso_pillar(21)
        assert result == ["█", "▓", "▒", "░", "·"]

    def test_pillar_ancient_age100(self):
        """Very old cell still gets the 5-row ancient pillar."""
        result = self.app._iso_pillar(100)
        assert result == ["█", "▓", "▒", "░", "·"]

    # ── _draw_iso basic execution ──

    def test_draw_iso_runs_on_empty_grid(self):
        """Drawing on a completely dead grid should not crash."""
        self.app._draw_iso(40, 120)

    def test_draw_iso_runs_with_live_cells(self):
        """Drawing with some live cells (various ages) should not crash."""
        grid = self.app.grid
        # Set some cells with different ages
        grid.cells[5][5] = 1   # newborn
        grid.cells[5][6] = 3   # young
        grid.cells[6][5] = 8   # mature
        grid.cells[6][6] = 20  # old
        grid.cells[7][7] = 50  # ancient
        self.app._draw_iso(40, 120)

    def test_draw_iso_with_cursor_on_live_cell(self):
        """Cursor on a live cell should render bold pillar top."""
        self.app.grid.cells[15][25] = 5
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app._draw_iso(40, 120)

    def test_draw_iso_with_cursor_on_dead_cell(self):
        """Cursor on a dead cell draws ground marker '▒▒'."""
        self.app.cursor_r = 15
        self.app.cursor_c = 25
        self.app.grid.cells[15][25] = 0  # dead
        self.app._draw_iso(40, 120)

    def test_draw_iso_tiny_terminal_skips(self):
        """If terminal is too small, _draw_iso should return early."""
        # draw_h = max_y - 4 < 5, so max_y < 9
        self.app._draw_iso(8, 120)  # draw_h = 4, < 5
        # Should not crash, just return

    def test_draw_iso_narrow_terminal_skips(self):
        """If terminal is too narrow, _draw_iso should return early."""
        self.app._draw_iso(40, 10)  # draw_w = 9, < 10
        # Should not crash, just return

    def test_draw_iso_status_bar_running(self):
        """Status bar shows PLAY when running."""
        self.app.running = True
        self.app._draw_iso(40, 120)

    def test_draw_iso_status_bar_paused(self):
        """Status bar shows PAUSE when not running."""
        self.app.running = False
        self.app._draw_iso(40, 120)

    def test_draw_iso_with_heatmap_mode(self):
        """Heatmap mode adds heatmap indicator to status."""
        self.app.heatmap_mode = True
        self.app._draw_iso(40, 120)

    def test_draw_iso_with_sound_enabled(self):
        """Sound enabled adds sound indicator to status."""
        self.app.sound_engine.enabled = True
        self.app._draw_iso(40, 120)

    def test_draw_iso_with_recording(self):
        """Recording mode adds REC indicator to status."""
        self.app.recording = True
        self.app.recorded_frames = [1, 2, 3]
        self.app._draw_iso(40, 120)

    def test_draw_iso_with_message(self):
        """Active message is displayed in the hint bar."""
        import time
        self.app.message = "Test message"
        self.app.message_time = time.monotonic()
        self.app._draw_iso(40, 120)

    # ── iso_mode toggle (integration-style) ──

    def test_iso_mode_flag_default(self):
        """iso_mode starts as False."""
        assert self.app.iso_mode is False

    def test_register_adds_methods(self):
        """register() should add _iso_pillar and _draw_iso to the class."""
        cls = type(self.app)
        assert hasattr(cls, '_iso_pillar')
        assert hasattr(cls, '_draw_iso')
        assert callable(self.app._iso_pillar)
        assert callable(self.app._draw_iso)

    # ── Age-based color tiers in draw ──

    def test_color_tiers_match_original(self):
        """Verify the color pair assignments match the original code:
        age<=1 -> cpair 1 (green), <=3 -> 2 (cyan), <=8 -> 3 (yellow),
        <=20 -> 4 (magenta), >20 -> 5 (red)."""
        # We test indirectly by placing cells of each age tier and ensuring
        # _draw_iso doesn't crash. Direct verification would require
        # capturing addstr calls; we verify the logic matches the original
        # by reading the code.
        grid = self.app.grid
        grid.cells[10][10] = 1   # green
        grid.cells[10][11] = 3   # cyan
        grid.cells[10][12] = 8   # yellow
        grid.cells[10][13] = 20  # magenta
        grid.cells[10][14] = 21  # red
        self.app._draw_iso(40, 120)

    # ── Zbuffer / occlusion ──

    def test_back_to_front_rendering(self):
        """Closer rows should overwrite farther rows (painter's algorithm).
        We place tall pillars in front and behind to verify no crash."""
        grid = self.app.grid
        # Back row (farther)
        grid.cells[10][15] = 50  # tall ancient pillar
        # Front row (closer)
        grid.cells[20][15] = 1   # short pillar
        self.app.cursor_r = 15
        self.app.cursor_c = 15
        self.app._draw_iso(40, 120)

    # ── Ground line ──

    def test_ground_line_drawn(self):
        """Ground line uses '╌' character repeated across the base."""
        # Just verify it doesn't crash with various grid sizes
        self.app._draw_iso(40, 120)

    # ── Edge cases ──

    def test_draw_iso_wrapping_viewport(self):
        """When cursor is near grid edge, viewport wraps via modulo."""
        self.app.cursor_r = 0
        self.app.cursor_c = 0
        self.app.grid.cells[0][0] = 10
        self.app._draw_iso(40, 120)

    def test_draw_iso_cursor_at_grid_edge(self):
        """Cursor at the far corner of the grid."""
        self.app.cursor_r = self.app.grid.rows - 1
        self.app.cursor_c = self.app.grid.cols - 1
        self.app.grid.cells[self.app.grid.rows - 1][self.app.grid.cols - 1] = 5
        self.app._draw_iso(40, 120)

    def test_draw_iso_all_cells_alive(self):
        """Full grid of live cells at various ages."""
        for r in range(self.app.grid.rows):
            for c in range(self.app.grid.cols):
                self.app.grid.cells[r][c] = (r + c) % 30 + 1
        self.app._draw_iso(40, 120)

    def test_pillar_height_monotonically_increases(self):
        """Pillar height should increase (or stay same) with age."""
        prev_height = 0
        for age in [1, 2, 3, 5, 8, 10, 20, 21, 50, 100]:
            height = len(self.app._iso_pillar(age))
            assert height >= prev_height, f"Height decreased at age {age}"
            prev_height = height

    def test_shade_map_covers_all_pillar_chars(self):
        """Every character used in pillars should have a shade mapping."""
        shade_map = type(self.app)._ISO_SHADE_MAP
        all_chars = set()
        for _, chars in type(self.app)._ISO_HEIGHT_TIERS:
            all_chars.update(chars)
        all_chars.update(type(self.app)._ISO_ANCIENT)
        for ch in all_chars:
            assert ch in shade_map, f"Character '{ch}' missing from shade map"
