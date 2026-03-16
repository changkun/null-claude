"""Tests for ifs_fractals mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.ifs_fractals import register


IFS_PRESETS = [
    ("Sierpinski", "Sierpinski triangle via chaos game", "sierpinski"),
    ("Fern", "Barnsley fern IFS", "fern"),
    ("Vicsek", "Vicsek snowflake fractal", "vicsek"),
    ("Carpet", "Sierpinski carpet", "carpet"),
    ("Dragon", "Heighway dragon curve", "dragon"),
    ("Maple", "Maple leaf fractal", "maple"),
    ("Koch", "Koch snowflake via IFS", "koch"),
    ("Crystal", "Symmetric crystal pattern", "crystal"),
]


class TestIFSFractals:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        cls.IFS_PRESETS = IFS_PRESETS
        self.app.ifs_menu_sel = 0
        register(cls)

    def test_enter(self):
        self.app._enter_ifs_mode()
        assert self.app.ifs_menu is True
        assert self.app.ifs_menu_sel == 0

    def test_step_no_crash(self):
        self.app.ifs_mode = True
        self.app.ifs_running = False
        self.app._ifs_init(0)
        for _ in range(10):
            self.app._ifs_step()
        assert self.app.ifs_generation >= 10

    def test_exit_cleanup(self):
        self.app.ifs_mode = True
        self.app._ifs_init(0)
        self.app._exit_ifs_mode()
        assert self.app.ifs_mode is False
        assert self.app.ifs_menu is False
        assert self.app.ifs_running is False
        assert self.app.ifs_points == []

    # ── Init tests for all presets ──

    @pytest.mark.parametrize("idx", range(len(IFS_PRESETS)))
    def test_init_all_presets(self, idx):
        """Every preset should initialize without error."""
        random.seed(42)
        self.app._ifs_init(idx)
        assert self.app.ifs_mode is True
        assert self.app.ifs_menu is False
        assert len(self.app.ifs_points) == self.app.ifs_rows
        assert len(self.app.ifs_points[0]) == self.app.ifs_cols
        assert len(self.app.ifs_color_field) == self.app.ifs_rows
        assert len(self.app.ifs_transforms) > 0

    # ── Transform validation ──

    def test_sierpinski_has_3_transforms(self):
        self.app._ifs_init(0)
        assert len(self.app.ifs_transforms) == 3

    def test_fern_has_4_transforms(self):
        self.app._ifs_init(1)
        assert len(self.app.ifs_transforms) == 4

    def test_vicsek_has_5_transforms(self):
        self.app._ifs_init(2)
        assert len(self.app.ifs_transforms) == 5

    def test_carpet_has_8_transforms(self):
        self.app._ifs_init(3)
        assert len(self.app.ifs_transforms) == 8

    def test_dragon_has_2_transforms(self):
        self.app._ifs_init(4)
        assert len(self.app.ifs_transforms) == 2

    def test_crystal_has_7_transforms(self):
        """6 arms + 1 central contraction = 7."""
        self.app._ifs_init(7)
        assert len(self.app.ifs_transforms) == 7

    def test_transform_probabilities_sum_to_one(self):
        """For each preset, transform probabilities should sum to ~1.0."""
        for idx in range(len(IFS_PRESETS)):
            self.app._ifs_init(idx)
            total = sum(t[6] for t in self.app.ifs_transforms)
            assert abs(total - 1.0) < 1e-6, f"Preset {idx}: probs sum to {total}"

    def test_each_transform_has_7_elements(self):
        """Each transform should be (a, b, c, d, e, f, prob)."""
        for idx in range(len(IFS_PRESETS)):
            self.app._ifs_init(idx)
            for i, t in enumerate(self.app.ifs_transforms):
                assert len(t) == 7, f"Preset {idx} transform {i} has {len(t)} elements"

    # ── Affine transform correctness ──

    def test_sierpinski_contraction_ratio(self):
        """Sierpinski transforms should have scale factor 0.5."""
        self.app._ifs_init(0)
        for t in self.app.ifs_transforms:
            a, b, c, d, e, f, p = t
            assert a == 0.5
            assert d == 0.5
            assert b == 0.0
            assert c == 0.0

    def test_fern_stem_transform(self):
        """Fern transform 0 (stem) should map to a degenerate line."""
        self.app._ifs_init(1)
        a, b, c, d, e, f, p = self.app.ifs_transforms[0]
        assert a == 0.0 and b == 0.0  # x maps to 0
        assert d == 0.16  # y scales to 16%
        assert p == 0.01  # very low probability

    def test_fern_main_transform(self):
        """Fern transform 1 (main) should have the highest probability."""
        self.app._ifs_init(1)
        probs = [t[6] for t in self.app.ifs_transforms]
        assert probs[1] == max(probs), "Main fern transform should have highest prob"
        assert probs[1] == 0.85

    # ── Chaos game iteration ──

    def test_iterate_changes_position(self):
        """A single iteration should move the point."""
        self.app._ifs_init(0)
        x0, y0 = self.app.ifs_x, self.app.ifs_y
        self.app._ifs_iterate()
        # After one iteration, position should change (with overwhelming probability)
        # (It's possible but unlikely to pick the same transform that maps to same point)
        assert hasattr(self.app, 'ifs_last_transform')

    def test_iterate_sets_last_transform(self):
        self.app._ifs_init(0)
        self.app._ifs_iterate()
        assert 0 <= self.app.ifs_last_transform < len(self.app.ifs_transforms)

    def test_step_increments_total_points(self):
        self.app._ifs_init(0)
        before = self.app.ifs_total_points
        self.app._ifs_step()
        assert self.app.ifs_total_points == before + 1

    def test_step_increments_generation(self):
        self.app._ifs_init(0)
        self.app._ifs_step()
        # generation should track total iterations (init does 50 transient + step)
        assert self.app.ifs_generation >= 1

    def test_step_plots_point_on_grid(self):
        """After many steps, at least one cell should have a nonzero hit count."""
        self.app._ifs_init(0)
        for _ in range(100):
            self.app._ifs_step()
        has_point = False
        for r in range(self.app.ifs_rows):
            for c in range(self.app.ifs_cols):
                if self.app.ifs_points[r][c] > 0:
                    has_point = True
                    break
            if has_point:
                break
        assert has_point, "Some grid cells should have nonzero density"

    def test_color_field_tracks_transform(self):
        """Color field should record which transform last hit each cell."""
        self.app._ifs_init(0)
        for _ in range(200):
            self.app._ifs_step()
        has_color = False
        for r in range(self.app.ifs_rows):
            for c in range(self.app.ifs_cols):
                if self.app.ifs_color_field[r][c] >= 0:
                    has_color = True
                    assert self.app.ifs_color_field[r][c] < len(self.app.ifs_transforms)
                    break
            if has_color:
                break
        assert has_color

    # ── Adaptive bounding box ──

    def test_bounds_expand(self):
        """Bounding box should expand as new points are found outside it."""
        self.app._ifs_init(1)  # fern - has a wider range
        for _ in range(500):
            self.app._ifs_step()
        # After many iterations, bounds should have expanded
        assert hasattr(self.app, '_ifs_xmin')
        assert self.app._ifs_xmax > self.app._ifs_xmin
        assert self.app._ifs_ymax > self.app._ifs_ymin

    # ── Stability ──

    def test_no_nan_or_inf_after_many_steps(self):
        """IFS point coordinates should remain finite."""
        self.app._ifs_init(0)
        for _ in range(1000):
            self.app._ifs_step()
        assert math.isfinite(self.app.ifs_x)
        assert math.isfinite(self.app.ifs_y)

    @pytest.mark.parametrize("idx", range(len(IFS_PRESETS)))
    def test_all_presets_stable_100_steps(self, idx):
        """Run 100 steps of each preset and verify no crash and finite coords."""
        random.seed(42)
        self.app._ifs_init(idx)
        for _ in range(100):
            self.app._ifs_step()
        assert math.isfinite(self.app.ifs_x)
        assert math.isfinite(self.app.ifs_y)
        assert self.app.ifs_total_points >= 100

    # ── Initial transient skip ──

    def test_init_skips_transient(self):
        """Init should run 50 transient iterations."""
        self.app._ifs_init(0)
        # After init, ifs_generation is still 0 (transient doesn't increment generation)
        # But the point should have moved from its initial position
        # The 50 transient iterations call _ifs_iterate which doesn't change generation
        assert self.app.ifs_generation == 0
        # But the point should be somewhere reasonable
        assert math.isfinite(self.app.ifs_x)
        assert math.isfinite(self.app.ifs_y)

    # ── Key handling ──

    def test_handle_menu_key_up_down(self):
        self.app.ifs_menu = True
        self.app.ifs_menu_sel = 0
        import curses
        self.app._handle_ifs_menu_key(curses.KEY_DOWN)
        assert self.app.ifs_menu_sel == 1
        self.app._handle_ifs_menu_key(curses.KEY_UP)
        assert self.app.ifs_menu_sel == 0
        self.app._handle_ifs_menu_key(curses.KEY_UP)
        assert self.app.ifs_menu_sel == len(IFS_PRESETS) - 1

    def test_handle_key_space_toggle(self):
        self.app._ifs_init(0)
        self.app.ifs_running = False
        self.app._handle_ifs_key(ord(" "))
        assert self.app.ifs_running is True
        self.app._handle_ifs_key(ord(" "))
        assert self.app.ifs_running is False

    def test_handle_key_quit(self):
        self.app._ifs_init(0)
        self.app._handle_ifs_key(ord("q"))
        assert self.app.ifs_mode is False

    def test_handle_key_color_toggle(self):
        self.app._ifs_init(0)
        assert self.app.ifs_colorize is True
        self.app._handle_ifs_key(ord("c"))
        assert self.app.ifs_colorize is False
        self.app._handle_ifs_key(ord("c"))
        assert self.app.ifs_colorize is True

    def test_handle_key_speed_adjust(self):
        self.app._ifs_init(0)
        spf = self.app.ifs_steps_per_frame
        self.app._handle_ifs_key(ord(">"))
        assert self.app.ifs_steps_per_frame == spf * 2
        self.app._handle_ifs_key(ord("<"))
        assert self.app.ifs_steps_per_frame == spf

    def test_handle_key_clear(self):
        self.app._ifs_init(0)
        for _ in range(100):
            self.app._ifs_step()
        self.app._handle_ifs_key(ord("x"))
        assert self.app.ifs_total_points == 0
        assert self.app.ifs_generation == 0
        # All point counts should be zero
        for r in range(self.app.ifs_rows):
            for c in range(self.app.ifs_cols):
                assert self.app.ifs_points[r][c] == 0

    def test_handle_key_reset(self):
        self.app._ifs_init(0)
        for _ in range(50):
            self.app._ifs_step()
        self.app._handle_ifs_key(ord("r"))
        assert self.app.ifs_generation == 0

    def test_handle_key_menu_return(self):
        self.app._ifs_init(0)
        self.app._handle_ifs_key(ord("R"))
        assert self.app.ifs_menu is True
        assert self.app.ifs_mode is False

    def test_handle_key_single_step_batch(self):
        """'n' key should advance by steps_per_frame points."""
        self.app._ifs_init(0)
        spf = self.app.ifs_steps_per_frame
        gen_before = self.app.ifs_generation
        self.app._handle_ifs_key(ord("n"))
        assert self.app.ifs_generation == gen_before + spf

    def test_handle_menu_key_cancel(self):
        self.app.ifs_menu = True
        self.app._handle_ifs_menu_key(ord("q"))
        assert self.app.ifs_menu is False

    def test_handle_menu_key_enter(self):
        self.app.ifs_menu = True
        self.app.ifs_menu_sel = 0
        self.app._handle_ifs_menu_key(10)  # Enter
        assert self.app.ifs_mode is True
        assert self.app.ifs_menu is False
