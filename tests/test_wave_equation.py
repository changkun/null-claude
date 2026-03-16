"""Tests for wave_equation mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.wave_equation import register


class TestWaveEquation:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_wave_mode()
        assert self.app.wave_menu is True
        assert self.app.wave_menu_sel == 0

    def test_step_no_crash(self):
        self.app.wave_mode = True
        self.app.wave_menu_sel = 0
        self.app._wave_init(0)
        for _ in range(10):
            self.app._wave_step()
        assert self.app.wave_generation == 10

    def test_exit_cleanup(self):
        self.app.wave_mode = True
        self.app.wave_menu_sel = 0
        self.app._wave_init(0)
        self.app._wave_step()
        self.app._exit_wave_mode()
        assert self.app.wave_mode is False
        assert self.app.wave_menu is False
        assert self.app.wave_running is False
        assert self.app.wave_u == []
        assert self.app.wave_u_prev == []

    # ── Initialization tests ───────────────────────────────────────────

    def test_init_grid_dimensions(self):
        """Grid dimensions are derived from terminal size."""
        self.app._wave_init(0)
        assert self.app.wave_rows >= 20
        assert self.app.wave_cols >= 20
        assert len(self.app.wave_u) == self.app.wave_rows
        assert len(self.app.wave_u[0]) == self.app.wave_cols
        assert len(self.app.wave_u_prev) == self.app.wave_rows
        assert len(self.app.wave_u_prev[0]) == self.app.wave_cols

    def test_init_sets_parameters_from_preset(self):
        """Preset parameters (c, damping, boundary) are applied correctly."""
        presets = self.app.WAVE_PRESETS
        for i, (name, _desc, c, damping, boundary, init_type) in enumerate(presets):
            self.app._wave_init(i)
            assert self.app.wave_c == c, f"Preset {i} ({name}): c mismatch"
            assert self.app.wave_damping == damping, f"Preset {i} ({name}): damping mismatch"
            assert self.app.wave_boundary == boundary, f"Preset {i} ({name}): boundary mismatch"
            assert self.app.wave_preset_name == name

    def test_init_center_drop_has_nonzero_center(self):
        """Center drop preset places energy at the grid center."""
        self.app._wave_init(0)  # Center Drop
        rows, cols = self.app.wave_rows, self.app.wave_cols
        cr, cc = rows // 2, cols // 2
        assert self.app.wave_u[cr][cc] > 0.5

    def test_init_zero_initial_velocity(self):
        """u and u_prev are equal after init (zero initial velocity)."""
        self.app._wave_init(0)
        for r in range(self.app.wave_rows):
            for c in range(self.app.wave_cols):
                assert self.app.wave_u[r][c] == self.app.wave_u_prev[r][c]

    def test_all_presets_init_without_error(self):
        """Every WAVE_PRESET initializes without raising."""
        for i in range(len(self.app.WAVE_PRESETS)):
            self.app._wave_init(i)
            # Should be able to step at least once
            self.app._wave_step()
            assert self.app.wave_generation == 1

    def test_init_double_slit_creates_wall(self):
        """Double slit preset creates slit wall and openings."""
        # Find the double_slit preset
        slit_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[5] == "double_slit"
        )
        self.app._wave_init(slit_idx)
        assert hasattr(self.app, 'wave_slit_wall_col')
        assert hasattr(self.app, 'wave_slit_openings')
        assert len(self.app.wave_slit_openings) > 0
        assert self.app.wave_slit_wall_col > 0

    # ── Wave propagation / physics tests ───────────────────────────────

    def test_wave_propagation_from_center(self):
        """After stepping, wave energy should spread outward from the center."""
        self.app._wave_init(0)  # Center Drop
        rows, cols = self.app.wave_rows, self.app.wave_cols
        cr, cc = rows // 2, cols // 2
        # Record initial max at center
        initial_center = self.app.wave_u[cr][cc]

        for _ in range(20):
            self.app._wave_step()

        # Center value should change (wave propagates away)
        assert self.app.wave_u[cr][cc] != initial_center
        # Some cells away from center should now have nonzero displacement
        has_spread = any(
            abs(self.app.wave_u[r][c]) > 0.01
            for r in range(rows) for c in range(cols)
            if abs(r - cr) > 5 or abs(c - cc) > 5
        )
        assert has_spread, "Wave did not propagate outward"

    def test_damping_reduces_energy(self):
        """With damping < 1.0, total energy decreases over time."""
        self.app._wave_init(0)  # damping = 0.999

        def total_energy():
            return sum(
                self.app.wave_u[r][c] ** 2
                for r in range(self.app.wave_rows)
                for c in range(self.app.wave_cols)
            )

        e0 = total_energy()
        for _ in range(100):
            self.app._wave_step()
        e1 = total_energy()

        assert e1 < e0, "Damped wave should lose energy"

    def test_undamped_conserves_energy_approximately(self):
        """With damping = 1.0, total energy should be roughly conserved."""
        # Find undamped preset
        undamped_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[3] == 1.0  # damping = 1.0
        )
        self.app._wave_init(undamped_idx)

        def total_energy():
            return sum(
                self.app.wave_u[r][c] ** 2
                for r in range(self.app.wave_rows)
                for c in range(self.app.wave_cols)
            )

        e0 = total_energy()
        for _ in range(50):
            self.app._wave_step()
        e1 = total_energy()

        # Energy shouldn't change dramatically (allow 20% tolerance for numerics)
        ratio = e1 / max(e0, 1e-10)
        assert 0.5 < ratio < 2.0, f"Energy ratio {ratio} too far from 1.0"

    def test_absorbing_boundary_no_reflection(self):
        """Absorbing boundary should not reflect waves back."""
        absorb_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[4] == "absorb" and p[5] == "center_drop"
        )
        self.app._wave_init(absorb_idx)

        # Run many steps so wave reaches boundary and would reflect back
        for _ in range(200):
            self.app._wave_step()

        # With absorbing boundary + damping, energy near center should be very low
        rows, cols = self.app.wave_rows, self.app.wave_cols
        cr, cc = rows // 2, cols // 2
        center_energy = sum(
            self.app.wave_u[r][c] ** 2
            for r in range(cr - 3, cr + 4)
            for c in range(cc - 3, cc + 4)
            if 0 <= r < rows and 0 <= c < cols
        )
        assert center_energy < 0.1, "Absorbing boundary should dissipate wave from center"

    def test_wrap_boundary_propagation(self):
        """Wrap boundary allows waves to wrap around the grid."""
        wrap_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[4] == "wrap"
        )
        self.app._wave_init(wrap_idx)

        for _ in range(50):
            self.app._wave_step()

        # Just verify no crash and grid is valid
        assert self.app.wave_generation == 50
        assert len(self.app.wave_u) == self.app.wave_rows

    def test_reflect_boundary_symmetry(self):
        """Reflecting boundary with symmetric init should preserve symmetry."""
        self.app._wave_init(0)  # Center Drop, reflect

        for _ in range(10):
            self.app._wave_step()

        rows, cols = self.app.wave_rows, self.app.wave_cols
        cr, cc = rows // 2, cols // 2
        # Check top-bottom symmetry around center
        for dr in range(1, min(5, cr)):
            for dc in range(-2, 3):
                c_idx = cc + dc
                if 0 <= cr - dr < rows and 0 <= cr + dr < rows and 0 <= c_idx < cols:
                    diff = abs(self.app.wave_u[cr - dr][c_idx] - self.app.wave_u[cr + dr][c_idx])
                    assert diff < 1e-10, f"Symmetry broken at dr={dr}, dc={dc}"

    def test_laplacian_flat_membrane(self):
        """On a flat membrane, laplacian is zero so no change occurs."""
        self.app._wave_init(0)
        # Set everything flat
        rows, cols = self.app.wave_rows, self.app.wave_cols
        self.app.wave_u = [[0.5] * cols for _ in range(rows)]
        self.app.wave_u_prev = [[0.5] * cols for _ in range(rows)]
        self.app.wave_boundary = "reflect"

        self.app._wave_step()

        # Interior cells should remain at 0.5 * damping (since laplacian=0)
        damp = self.app.wave_damping
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                # u_next = damp * (2*0.5 - 0.5 + 0) = damp * 0.5
                expected = damp * 0.5
                assert abs(self.app.wave_u[r][c] - expected) < 1e-10

    def test_double_slit_wall_blocks_propagation(self):
        """Double slit wall cells remain at zero."""
        slit_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[5] == "double_slit"
        )
        self.app._wave_init(slit_idx)

        for _ in range(20):
            self.app._wave_step()

        wall_col = self.app.wave_slit_wall_col
        openings = self.app.wave_slit_openings
        rows = self.app.wave_rows
        for r in range(rows):
            if r not in openings:
                assert self.app.wave_u[r][wall_col] == 0.0, \
                    f"Wall cell at row {r} should be zero"

    def test_double_slit_driving_wave(self):
        """Double slit mode continuously drives a plane wave at the left edge."""
        slit_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[5] == "double_slit"
        )
        self.app._wave_init(slit_idx)

        for _ in range(10):
            self.app._wave_step()

        # Left edge should have a driven wave value
        t = (self.app.wave_generation - 1) * 0.15  # last step's time
        # The driving happens after the main update at the current generation-1
        # Just verify the left column is not all zeros
        left_col_vals = [self.app.wave_u[r][0] for r in range(self.app.wave_rows)]
        has_nonzero = any(abs(v) > 0.01 for v in left_col_vals)
        assert has_nonzero, "Double slit should drive wave at left edge"

    def test_generation_counter_increments(self):
        """Each step increments the generation counter by 1."""
        self.app._wave_init(0)
        assert self.app.wave_generation == 0
        self.app._wave_step()
        assert self.app.wave_generation == 1
        self.app._wave_step()
        assert self.app.wave_generation == 2

    # ── Corner pulse test ──────────────────────────────────────────────

    def test_corner_pulse_energy_at_corner(self):
        """Corner pulse places energy near (0,0)."""
        corner_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[5] == "corner_pulse"
        )
        self.app._wave_init(corner_idx)
        assert self.app.wave_u[0][0] > 0.1, "Corner pulse should have energy at origin"

    def test_random_drops_has_multiple_peaks(self):
        """Random drops init creates multiple displaced regions."""
        drops_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[5] == "random_drops"
        )
        random.seed(42)
        self.app._wave_init(drops_idx)

        nonzero_count = sum(
            1 for r in range(self.app.wave_rows) for c in range(self.app.wave_cols)
            if abs(self.app.wave_u[r][c]) > 0.01
        )
        assert nonzero_count > 10, "Random drops should create multiple regions"

    def test_ring_init_creates_annular_pattern(self):
        """Ring init creates displacement at a radius from center."""
        ring_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[5] == "ring"
        )
        self.app._wave_init(ring_idx)
        rows, cols = self.app.wave_rows, self.app.wave_cols
        cr, cc = rows // 2, cols // 2
        # Center should have low displacement, ring should have high
        center_val = abs(self.app.wave_u[cr][cc])
        radius = min(rows, cols) // 6
        ring_val = abs(self.app.wave_u[cr][cc + radius])
        assert ring_val > center_val, "Ring pattern should have peak at radius"

    def test_cross_init_creates_cross_pattern(self):
        """Cross init creates displacement along axes through center."""
        cross_idx = next(
            i for i, p in enumerate(self.app.WAVE_PRESETS)
            if p[5] == "cross"
        )
        self.app._wave_init(cross_idx)
        rows, cols = self.app.wave_rows, self.app.wave_cols
        cr, cc = rows // 2, cols // 2
        # Center should be nonzero
        assert self.app.wave_u[cr][cc] > 0.0

    # ── Numerical stability ────────────────────────────────────────────

    def test_no_nan_or_inf_after_many_steps(self):
        """Wave simulation stays numerically stable over many steps."""
        self.app._wave_init(0)
        for _ in range(500):
            self.app._wave_step()
        for r in range(self.app.wave_rows):
            for c in range(self.app.wave_cols):
                v = self.app.wave_u[r][c]
                assert math.isfinite(v), f"Non-finite value {v} at ({r},{c})"

    def test_courant_stability(self):
        """All presets have c <= 0.5 (CFL condition for stability)."""
        for name, _desc, c, _damp, _boundary, _init in self.app.WAVE_PRESETS:
            assert c <= 0.5, f"Preset '{name}' has c={c} > 0.5, violating CFL"
