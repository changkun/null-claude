"""Tests for kuramoto mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.kuramoto import register


class TestKuramoto:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_kuramoto_mode()
        assert self.app.kuramoto_menu is True
        assert self.app.kuramoto_menu_sel == 0

    def test_step_no_crash(self):
        self.app.kuramoto_mode = True
        self.app.kuramoto_menu_sel = 0
        self.app._kuramoto_init(0)
        for _ in range(10):
            self.app._kuramoto_step()
        assert self.app.kuramoto_generation == 10

    def test_exit_cleanup(self):
        self.app.kuramoto_mode = True
        self.app.kuramoto_menu_sel = 0
        self.app._kuramoto_init(0)
        self.app._kuramoto_step()
        self.app._exit_kuramoto_mode()
        assert self.app.kuramoto_mode is False
        assert self.app.kuramoto_menu is False
        assert self.app.kuramoto_running is False
        assert self.app.kuramoto_phases == []
        assert self.app.kuramoto_nat_freq == []

    # ── Initialization tests ───────────────────────────────────────────

    def test_init_grid_dimensions(self):
        """Grid dimensions match terminal size."""
        self.app._kuramoto_init(0)
        rows, cols = self.app.kuramoto_rows, self.app.kuramoto_cols
        assert rows >= 20
        assert cols >= 20
        assert len(self.app.kuramoto_phases) == rows
        assert len(self.app.kuramoto_phases[0]) == cols
        assert len(self.app.kuramoto_nat_freq) == rows
        assert len(self.app.kuramoto_nat_freq[0]) == cols

    def test_init_sets_parameters_from_preset(self):
        """Preset parameters are applied correctly."""
        presets = self.app.KURAMOTO_PRESETS
        for i, (name, _desc, coupling, freq_spread, dt, noise, init_type) in enumerate(presets):
            self.app._kuramoto_init(i)
            assert self.app.kuramoto_coupling == coupling, f"Preset {i}: coupling"
            assert self.app.kuramoto_dt == dt, f"Preset {i}: dt"
            assert self.app.kuramoto_noise == noise, f"Preset {i}: noise"
            assert self.app.kuramoto_preset_name == name

    def test_all_presets_init_without_error(self):
        """Every KURAMOTO_PRESET initializes and steps without error."""
        for i in range(len(self.app.KURAMOTO_PRESETS)):
            random.seed(42)
            self.app._kuramoto_init(i)
            self.app._kuramoto_step()
            assert self.app.kuramoto_generation == 1

    def test_phases_in_range_after_init(self):
        """All phases are in [0, 2*pi) after initialization."""
        TWO_PI = 2.0 * math.pi
        for i in range(len(self.app.KURAMOTO_PRESETS)):
            random.seed(42)
            self.app._kuramoto_init(i)
            for r in range(self.app.kuramoto_rows):
                for c in range(self.app.kuramoto_cols):
                    theta = self.app.kuramoto_phases[r][c]
                    assert 0.0 <= theta < TWO_PI, \
                        f"Phase {theta} out of range at ({r},{c}) for preset {i}"

    def test_gradient_init_linear_phase(self):
        """Gradient preset creates a linear phase gradient across columns."""
        grad_idx = next(
            i for i, p in enumerate(self.app.KURAMOTO_PRESETS)
            if p[6] == "gradient"
        )
        self.app._kuramoto_init(grad_idx)
        cols = self.app.kuramoto_cols
        row0 = self.app.kuramoto_phases[0]
        # Phase should increase from left to right (except last col wraps to 0)
        for c in range(1, cols - 1):
            assert row0[c] >= row0[c - 1], f"Gradient not monotonic at col {c}"
        # Last column wraps: phase at cols-1 should be 0 (= 2*pi mod 2*pi)
        assert row0[cols - 1] == 0.0, "Last column should wrap to 0"

    def test_spiral_init_has_angular_pattern(self):
        """Spiral preset creates phases based on atan2 from center."""
        spiral_idx = next(
            i for i, p in enumerate(self.app.KURAMOTO_PRESETS)
            if p[6] == "spiral"
        )
        self.app._kuramoto_init(spiral_idx)
        rows, cols = self.app.kuramoto_rows, self.app.kuramoto_cols
        cr, cc = rows // 2, cols // 2
        # Opposite sides of center should have phase difference close to pi
        if cr > 2 and cc > 2:
            phase_right = self.app.kuramoto_phases[cr][cc + 2]
            phase_left = self.app.kuramoto_phases[cr][cc - 2]
            # These should differ by approximately pi
            diff = abs(phase_right - phase_left)
            diff = min(diff, 2 * math.pi - diff)  # handle wrapping
            assert diff > 2.0, "Spiral init should have large phase difference across center"

    def test_chimera_init_synchronized_half(self):
        """Chimera preset: left half synchronized (phase=0), right half random."""
        chimera_idx = next(
            i for i, p in enumerate(self.app.KURAMOTO_PRESETS)
            if p[6] == "chimera"
        )
        self.app._kuramoto_init(chimera_idx)
        cols = self.app.kuramoto_cols
        # Left half should all be 0.0
        for r in range(self.app.kuramoto_rows):
            for c in range(cols // 2):
                assert self.app.kuramoto_phases[r][c] == 0.0, \
                    f"Chimera left half should be synchronized at ({r},{c})"

    # ── Phase coupling / synchronization tests ─────────────────────────

    def test_phases_stay_in_range_after_steps(self):
        """Phases remain in [0, 2*pi) after many steps."""
        TWO_PI = 2.0 * math.pi
        self.app._kuramoto_init(0)
        for _ in range(100):
            self.app._kuramoto_step()
        for r in range(self.app.kuramoto_rows):
            for c in range(self.app.kuramoto_cols):
                theta = self.app.kuramoto_phases[r][c]
                assert 0.0 <= theta < TWO_PI, f"Phase {theta} out of range at ({r},{c})"

    def test_order_parameter_range(self):
        """Order parameter r is in [0, 1]."""
        self.app._kuramoto_init(0)
        r = self.app._kuramoto_order_parameter()
        assert 0.0 <= r <= 1.0

    def test_synchronized_state_high_order(self):
        """When all phases are equal, order parameter should be ~1."""
        self.app._kuramoto_init(0)
        rows, cols = self.app.kuramoto_rows, self.app.kuramoto_cols
        # Set all phases to the same value
        self.app.kuramoto_phases = [[1.0] * cols for _ in range(rows)]
        r = self.app._kuramoto_order_parameter()
        assert r > 0.99, f"Synchronized state should have r~1, got {r}"

    def test_strong_coupling_increases_synchronization(self):
        """Strong coupling should increase the order parameter over time."""
        # Use "Strong Sync" preset (K=3.0)
        strong_idx = next(
            i for i, p in enumerate(self.app.KURAMOTO_PRESETS)
            if "Strong" in p[0]
        )
        random.seed(42)
        self.app._kuramoto_init(strong_idx)
        r0 = self.app._kuramoto_order_parameter()

        for _ in range(200):
            self.app._kuramoto_step()
        r1 = self.app._kuramoto_order_parameter()

        assert r1 > r0, f"Strong coupling should increase sync: r0={r0}, r1={r1}"

    def test_zero_coupling_no_synchronization(self):
        """With K=0, oscillators evolve independently (no sync increase)."""
        frozen_idx = next(
            i for i, p in enumerate(self.app.KURAMOTO_PRESETS)
            if p[2] == 0.0  # coupling = 0
        )
        random.seed(42)
        self.app._kuramoto_init(frozen_idx)

        # With zero coupling, phases just rotate by natural frequency
        # Order parameter should not systematically increase
        r0 = self.app._kuramoto_order_parameter()
        for _ in range(100):
            self.app._kuramoto_step()
        r1 = self.app._kuramoto_order_parameter()

        # Allow small random fluctuation but not huge increase
        assert r1 < r0 + 0.3, "Zero coupling should not produce strong sync"

    def test_coupling_formula_correctness(self):
        """Verify the coupling formula on a minimal manually-constructed grid."""
        self.app._kuramoto_init(0)
        rows, cols = 3, 3
        self.app.kuramoto_rows = rows
        self.app.kuramoto_cols = cols
        TWO_PI = 2.0 * math.pi

        # Set all phases to 0 except center = pi
        self.app.kuramoto_phases = [[0.0] * cols for _ in range(rows)]
        self.app.kuramoto_phases[1][1] = math.pi

        # Set all natural frequencies to 0 (so only coupling matters)
        self.app.kuramoto_nat_freq = [[0.0] * cols for _ in range(rows)]

        K = self.app.kuramoto_coupling
        dt = self.app.kuramoto_dt

        self.app._kuramoto_step()

        # For center cell (1,1): theta=pi, all 4 neighbors=0
        # coupling_sum = 4 * sin(0 - pi) = 4 * 0 = 0
        # Actually sin(0 - pi) = sin(-pi) = 0
        # So center should stay at pi (modulo dt * 0 = 0)
        # center_new = (pi + dt * 0) % TWO_PI = pi
        assert abs(self.app.kuramoto_phases[1][1] - math.pi) < 1e-10

    def test_generation_counter_increments(self):
        """Each step increments the generation counter."""
        self.app._kuramoto_init(0)
        assert self.app.kuramoto_generation == 0
        self.app._kuramoto_step()
        assert self.app.kuramoto_generation == 1
        self.app._kuramoto_step()
        assert self.app.kuramoto_generation == 2

    # ── Numerical stability ────────────────────────────────────────────

    def test_no_nan_or_inf_after_many_steps(self):
        """Kuramoto simulation stays numerically stable."""
        self.app._kuramoto_init(0)
        for _ in range(500):
            self.app._kuramoto_step()
        for r in range(self.app.kuramoto_rows):
            for c in range(self.app.kuramoto_cols):
                v = self.app.kuramoto_phases[r][c]
                assert math.isfinite(v), f"Non-finite phase {v} at ({r},{c})"

    def test_noisy_preset_stays_stable(self):
        """Noisy preset does not diverge."""
        noisy_idx = next(
            i for i, p in enumerate(self.app.KURAMOTO_PRESETS)
            if p[5] > 0.0  # noise > 0
        )
        random.seed(42)
        self.app._kuramoto_init(noisy_idx)
        for _ in range(200):
            self.app._kuramoto_step()
        # All phases should still be finite and in range
        TWO_PI = 2.0 * math.pi
        for r in range(self.app.kuramoto_rows):
            for c in range(self.app.kuramoto_cols):
                theta = self.app.kuramoto_phases[r][c]
                assert 0.0 <= theta < TWO_PI

    def test_order_parameter_empty_grid(self):
        """Order parameter returns 0 for empty grid."""
        self.app._kuramoto_init(0)
        self.app.kuramoto_phases = []
        r = self.app._kuramoto_order_parameter()
        assert r == 0.0

    # ── Neighbor wrapping test ─────────────────────────────────────────

    def test_neighbor_wrapping(self):
        """Coupling uses wrapped neighbors (toroidal grid)."""
        self.app._kuramoto_init(0)
        rows, cols = 4, 4
        self.app.kuramoto_rows = rows
        self.app.kuramoto_cols = cols

        # Place a single nonzero phase at (0,0), rest at 0
        TWO_PI = 2.0 * math.pi
        self.app.kuramoto_phases = [[0.0] * cols for _ in range(rows)]
        self.app.kuramoto_phases[0][0] = math.pi / 2
        self.app.kuramoto_nat_freq = [[0.0] * cols for _ in range(rows)]

        self.app._kuramoto_step()

        # Wrapped neighbors of (0,0) are (3,0), (1,0), (0,3), (0,1)
        # These should be affected by coupling
        # (3,0) coupling: sin(pi/2 - 0) = 1.0, so it should have moved
        assert self.app.kuramoto_phases[3][0] != 0.0, "Wrap neighbor (3,0) should couple"
        assert self.app.kuramoto_phases[0][3] != 0.0, "Wrap neighbor (0,3) should couple"
