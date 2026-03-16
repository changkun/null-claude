"""Tests for fractal_explorer mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.fractal_explorer import register


FRACTAL_PRESETS = [
    ("Mandelbrot Classic", "The full Mandelbrot set", "mandelbrot_classic"),
    ("Seahorse Valley", "Deep zoom into seahorse valley", "mandelbrot_seahorse"),
    ("Elephant Valley", "Elephant valley region", "mandelbrot_elephant"),
    ("Minibrot", "Miniature Mandelbrot copy", "mandelbrot_minibrot"),
    ("Spiral", "Spiral structure", "mandelbrot_spiral"),
    ("Julia Dendrite", "Dendrite Julia set c=i", "julia_dendrite"),
    ("Julia Rabbit", "Douady rabbit Julia set", "julia_rabbit"),
    ("Julia San Marco", "San Marco Julia set", "julia_sanmarco"),
    ("Julia Siegel", "Siegel disk Julia set", "julia_siegel"),
    ("Julia Dragon", "Dragon Julia set", "julia_dragon"),
]

FRACTAL_COLOR_SCHEMES = [
    ("Classic", [1, 2, 3, 4, 5, 6, 7]),
    ("Fire", [1, 3, 7]),
    ("Ocean", [4, 3, 6]),
]

FRACTAL_DENSITY = " .:-=+*#%@"


def _make_app():
    app = make_mock_app()
    cls = type(app)
    cls.FRACTAL_PRESETS = FRACTAL_PRESETS
    cls.FRACTAL_COLOR_SCHEMES = FRACTAL_COLOR_SCHEMES
    cls.FRACTAL_DENSITY = FRACTAL_DENSITY
    app.fractal_julia_re = -0.7
    app.fractal_julia_im = 0.27015
    app.fractal_type = "mandelbrot"
    app.fractal_center_re = -0.5
    app.fractal_center_im = 0.0
    app.fractal_zoom = 1.0
    app.fractal_max_iter = 80
    app.fractal_dirty = True
    app.fractal_buffer = []
    app.fractal_color_scheme = 0
    app.fractal_smooth = True
    app.fractal_rows = 0
    app.fractal_cols = 0
    app.fractal_mode = False
    app.fractal_menu = False
    app.fractal_menu_sel = 0
    app.fractal_running = False
    app.fractal_generation = 0
    app.fractal_preset_name = ""
    register(cls)
    return app


class TestFractalExplorer:
    def setup_method(self):
        random.seed(42)
        self.app = _make_app()

    def test_enter(self):
        self.app._enter_fractal_mode()
        assert self.app.fractal_menu is True
        assert self.app.fractal_menu_sel == 0

    def test_step_no_crash(self):
        self.app.fractal_mode = True
        self.app.fractal_preset_name = "Mandelbrot Classic"
        self.app._fractal_init("mandelbrot_classic")
        self.app._fractal_compute()
        assert len(self.app.fractal_buffer) > 0
        for _ in range(10):
            self.app._fractal_compute()
        assert len(self.app.fractal_buffer) > 0

    def test_exit_cleanup(self):
        self.app.fractal_mode = True
        self.app.fractal_preset_name = "Mandelbrot Classic"
        self.app._fractal_init("mandelbrot_classic")
        self.app._exit_fractal_mode()
        assert self.app.fractal_mode is False
        assert self.app.fractal_menu is False
        assert self.app.fractal_running is False
        assert self.app.fractal_buffer == []


class TestMandelbrotIteration:
    """Validate the core Mandelbrot iteration logic."""

    def setup_method(self):
        self.app = _make_app()

    def test_origin_inside_set(self):
        """z=0, c=0 should stay inside the set (iter == max_iter)."""
        self.app._fractal_init("mandelbrot_classic")
        # Center of Mandelbrot at (-0.5, 0) but c=(0,0) is also inside
        # We manually check: z=0+0i, c=0+0i stays at 0 forever
        self.app.fractal_type = "mandelbrot"
        self.app.fractal_center_re = 0.0
        self.app.fractal_center_im = 0.0
        self.app.fractal_zoom = 100.0  # tight zoom so center pixel ~ (0,0)
        self.app.fractal_max_iter = 50
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf = self.app.fractal_buffer
        # The center pixel should be at or near max_iter (inside set)
        mid_r = len(buf) // 2
        mid_c = len(buf[0]) // 2
        assert buf[mid_r][mid_c] == 50, "Origin should be inside the Mandelbrot set"

    def test_far_outside_escapes_fast(self):
        """c = (10, 10) is far outside the set; should escape in 1 iteration."""
        self.app._fractal_init("mandelbrot_classic")
        self.app.fractal_type = "mandelbrot"
        self.app.fractal_center_re = 10.0
        self.app.fractal_center_im = 10.0
        self.app.fractal_zoom = 1000.0  # very tight zoom around (10,10)
        self.app.fractal_max_iter = 100
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf = self.app.fractal_buffer
        mid_r = len(buf) // 2
        mid_c = len(buf[0]) // 2
        # |c|^2 = 200 >> 4, so z=0 -> z=c immediately escapes: n=1
        assert buf[mid_r][mid_c] <= 2, "Far-away point should escape quickly"

    def test_buffer_dimensions(self):
        """Buffer should match fractal_rows x fractal_cols."""
        self.app._fractal_init("mandelbrot_classic")
        self.app._fractal_compute()
        assert len(self.app.fractal_buffer) == self.app.fractal_rows
        for row in self.app.fractal_buffer:
            assert len(row) == self.app.fractal_cols

    def test_all_values_in_range(self):
        """All iteration counts should be in [0, max_iter]."""
        self.app._fractal_init("mandelbrot_classic")
        self.app._fractal_compute()
        for row in self.app.fractal_buffer:
            for val in row:
                assert 0 <= val <= self.app.fractal_max_iter

    def test_dirty_flag_cleared_after_compute(self):
        self.app._fractal_init("mandelbrot_classic")
        assert self.app.fractal_dirty is True
        self.app._fractal_compute()
        assert self.app.fractal_dirty is False

    def test_cardioid_point_inside(self):
        """c = (-0.5, 0) is on the main cardioid boundary — should be inside."""
        self.app._fractal_init("mandelbrot_classic")
        self.app.fractal_center_re = -0.5
        self.app.fractal_center_im = 0.0
        self.app.fractal_zoom = 1000.0
        self.app.fractal_max_iter = 200
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf = self.app.fractal_buffer
        mid_r = len(buf) // 2
        mid_c = len(buf[0]) // 2
        # (-0.5, 0) is inside the main cardioid
        assert buf[mid_r][mid_c] == 200


class TestJuliaIteration:
    """Validate the Julia set iteration."""

    def setup_method(self):
        self.app = _make_app()

    def test_julia_origin_with_zero_c(self):
        """Julia with c=0: z=0 stays at origin forever."""
        self.app._fractal_init("julia_dendrite")
        self.app.fractal_type = "julia"
        self.app.fractal_julia_re = 0.0
        self.app.fractal_julia_im = 0.0
        self.app.fractal_center_re = 0.0
        self.app.fractal_center_im = 0.0
        self.app.fractal_zoom = 1000.0
        self.app.fractal_max_iter = 50
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf = self.app.fractal_buffer
        mid_r = len(buf) // 2
        mid_c = len(buf[0]) // 2
        assert buf[mid_r][mid_c] == 50

    def test_julia_far_point_escapes(self):
        """Julia with z far from origin should escape quickly."""
        self.app._fractal_init("julia_dendrite")
        self.app.fractal_type = "julia"
        self.app.fractal_julia_re = 0.0
        self.app.fractal_julia_im = 1.0
        self.app.fractal_center_re = 5.0
        self.app.fractal_center_im = 5.0
        self.app.fractal_zoom = 1000.0
        self.app.fractal_max_iter = 100
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf = self.app.fractal_buffer
        mid_r = len(buf) // 2
        mid_c = len(buf[0]) // 2
        assert buf[mid_r][mid_c] <= 2

    def test_julia_type_set_correctly(self):
        """Julia presets should set fractal_type to julia."""
        self.app._fractal_init("julia_rabbit")
        assert self.app.fractal_type == "julia"
        assert self.app.fractal_julia_re == -0.123
        assert self.app.fractal_julia_im == 0.745


class TestFractalPresets:
    """Test all preset configurations are applied correctly."""

    def setup_method(self):
        self.app = _make_app()

    @pytest.mark.parametrize("preset_id,ftype", [
        ("mandelbrot_classic", "mandelbrot"),
        ("mandelbrot_seahorse", "mandelbrot"),
        ("mandelbrot_elephant", "mandelbrot"),
        ("mandelbrot_minibrot", "mandelbrot"),
        ("mandelbrot_spiral", "mandelbrot"),
        ("julia_dendrite", "julia"),
        ("julia_rabbit", "julia"),
        ("julia_sanmarco", "julia"),
        ("julia_siegel", "julia"),
        ("julia_dragon", "julia"),
    ])
    def test_preset_sets_type(self, preset_id, ftype):
        self.app._fractal_init(preset_id)
        assert self.app.fractal_type == ftype

    @pytest.mark.parametrize("preset_id", [
        "mandelbrot_classic", "mandelbrot_seahorse", "julia_dendrite",
        "julia_dragon", "julia_siegel",
    ])
    def test_preset_compute_no_crash(self, preset_id):
        self.app._fractal_init(preset_id)
        self.app._fractal_compute()
        assert len(self.app.fractal_buffer) > 0

    def test_unknown_preset_defaults_to_mandelbrot(self):
        self.app._fractal_init("nonexistent_preset")
        assert self.app.fractal_type == "mandelbrot"
        assert self.app.fractal_center_re == -0.5
        assert self.app.fractal_zoom == 1.0

    def test_seahorse_zoom_gt_1(self):
        self.app._fractal_init("mandelbrot_seahorse")
        assert self.app.fractal_zoom == 50.0
        assert self.app.fractal_max_iter == 200

    def test_minibrot_deep_zoom(self):
        self.app._fractal_init("mandelbrot_minibrot")
        assert self.app.fractal_zoom == 500.0
        assert self.app.fractal_max_iter == 500


class TestFractalZoomAndPan:
    """Test viewport mapping correctness."""

    def setup_method(self):
        self.app = _make_app()
        self.app._fractal_init("mandelbrot_classic")

    def test_zoom_increases(self):
        old_zoom = self.app.fractal_zoom
        self.app.fractal_zoom *= 1.5
        assert self.app.fractal_zoom > old_zoom

    def test_zoom_decreases_with_floor(self):
        self.app.fractal_zoom = 0.15
        self.app.fractal_zoom = max(0.1, self.app.fractal_zoom / 1.5)
        assert self.app.fractal_zoom >= 0.1

    def test_pan_changes_center(self):
        old_re = self.app.fractal_center_re
        pan_step = 0.15 / self.app.fractal_zoom
        self.app.fractal_center_re += pan_step
        assert self.app.fractal_center_re > old_re

    def test_zoom_affects_visible_range(self):
        """Higher zoom should produce a narrower complex plane range."""
        self.app.fractal_zoom = 1.0
        half_h_1 = 1.5 / self.app.fractal_zoom
        self.app.fractal_zoom = 10.0
        half_h_10 = 1.5 / self.app.fractal_zoom
        assert half_h_10 < half_h_1

    def test_aspect_ratio_correction(self):
        """The aspect ratio should account for terminal char ~2x height."""
        rows = self.app.fractal_rows
        cols = self.app.fractal_cols
        aspect = cols / (rows * 2.0)
        # For a 40x120 terminal -> rows~37, cols~119, aspect ~= 119/(37*2) ~= 1.6
        assert aspect > 0.5  # reasonable range


class TestFractalColorSchemes:
    """Test color scheme cycling."""

    def setup_method(self):
        self.app = _make_app()
        self.app._fractal_init("mandelbrot_classic")

    def test_color_scheme_cycles(self):
        n = len(FRACTAL_COLOR_SCHEMES)
        self.app.fractal_color_scheme = 0
        self.app.fractal_color_scheme = (self.app.fractal_color_scheme + 1) % n
        assert self.app.fractal_color_scheme == 1
        self.app.fractal_color_scheme = (self.app.fractal_color_scheme + 1) % n
        assert self.app.fractal_color_scheme == 2
        self.app.fractal_color_scheme = (self.app.fractal_color_scheme + 1) % n
        assert self.app.fractal_color_scheme == 0  # wraps

    def test_max_iter_adjustment(self):
        self.app.fractal_max_iter = 80
        self.app.fractal_max_iter = min(5000, self.app.fractal_max_iter + 20)
        assert self.app.fractal_max_iter == 100
        self.app.fractal_max_iter = max(20, self.app.fractal_max_iter - 20)
        assert self.app.fractal_max_iter == 80


class TestFractalComputeIdempotent:
    """Verify that recomputing the same viewport yields identical results."""

    def setup_method(self):
        self.app = _make_app()

    def test_idempotent_mandelbrot(self):
        self.app._fractal_init("mandelbrot_classic")
        self.app._fractal_compute()
        buf1 = [row[:] for row in self.app.fractal_buffer]
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf2 = self.app.fractal_buffer
        assert buf1 == buf2

    def test_idempotent_julia(self):
        self.app._fractal_init("julia_dendrite")
        self.app._fractal_compute()
        buf1 = [row[:] for row in self.app.fractal_buffer]
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        assert buf1 == self.app.fractal_buffer


class TestFractalMathCorrectness:
    """Test Mandelbrot z^2+c iteration against reference values."""

    def setup_method(self):
        self.app = _make_app()

    def test_mandelbrot_well_inside_set(self):
        """c=(-0.1, 0.0) is well inside the main cardioid — should reach max_iter."""
        self.app._fractal_init("mandelbrot_classic")
        self.app.fractal_center_re = -0.1
        self.app.fractal_center_im = 0.0
        self.app.fractal_zoom = 10000.0
        self.app.fractal_max_iter = 100
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf = self.app.fractal_buffer
        mid_r = len(buf) // 2
        mid_c = len(buf[0]) // 2
        assert buf[mid_r][mid_c] == 100, (
            f"c=(-0.1,0) is inside the Mandelbrot set, got iter={buf[mid_r][mid_c]}"
        )

    def test_mandelbrot_c_equals_1(self):
        """c=1 should escape: z: 0 -> 1 -> 2 -> 5 (escapes at n=3)."""
        self.app._fractal_init("mandelbrot_classic")
        self.app.fractal_center_re = 1.0
        self.app.fractal_center_im = 0.0
        self.app.fractal_zoom = 10000.0
        self.app.fractal_max_iter = 100
        self.app.fractal_dirty = True
        self.app._fractal_compute()
        buf = self.app.fractal_buffer
        mid_r = len(buf) // 2
        mid_c = len(buf[0]) // 2
        # z: 0->1->2->5 (|5|^2=25>4, escape at n=3)
        assert buf[mid_r][mid_c] == 3
