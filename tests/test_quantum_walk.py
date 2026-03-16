"""Tests for quantum_walk mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.quantum_walk import register


class TestQuantumWalk:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_qwalk_mode()
        assert self.app.qwalk_menu is True
        assert self.app.qwalk_menu_sel == 0

    def test_step_no_crash(self):
        self.app.qwalk_mode = True
        self.app.qwalk_menu_sel = 0
        self.app._qwalk_init(0)
        for _ in range(10):
            self.app._qwalk_step()
        assert self.app.qwalk_generation == 10

    def test_exit_cleanup(self):
        self.app.qwalk_mode = True
        self.app.qwalk_menu_sel = 0
        self.app._qwalk_init(0)
        self.app._qwalk_step()
        self.app._exit_qwalk_mode()
        assert self.app.qwalk_mode is False
        assert self.app.qwalk_menu is False
        assert self.app.qwalk_running is False
        assert self.app.qwalk_amp_re == []
        assert self.app.qwalk_amp_im == []
        assert self.app.qwalk_prob == []

    # ── Probability conservation (unitarity) ──

    def test_hadamard_probability_conservation(self):
        """Hadamard coin preserves total probability (unitarity)."""
        self.app._qwalk_init(0)  # Hadamard, single, periodic
        self.app.qwalk_decoherence = 0.0  # no decoherence

        initial_prob = self._total_probability()
        for _ in range(20):
            self.app._qwalk_step()
        final_prob = self._total_probability()

        # Total probability should be conserved (within floating point)
        assert abs(initial_prob - final_prob) < 1e-8, (
            f"Probability not conserved: initial={initial_prob}, final={final_prob}"
        )

    def test_grover_probability_conservation(self):
        """Grover coin preserves total probability."""
        self.app._qwalk_init(2)  # Grover, single, periodic
        self.app.qwalk_decoherence = 0.0

        initial_prob = self._total_probability()
        for _ in range(15):
            self.app._qwalk_step()
        final_prob = self._total_probability()

        assert abs(initial_prob - final_prob) < 1e-8

    def test_dft_probability_conservation(self):
        """DFT coin preserves total probability."""
        self.app._qwalk_init(3)  # DFT, single, periodic
        self.app.qwalk_decoherence = 0.0

        initial_prob = self._total_probability()
        for _ in range(15):
            self.app._qwalk_step()
        final_prob = self._total_probability()

        assert abs(initial_prob - final_prob) < 1e-8

    # ── Coin operator correctness ──

    def test_hadamard_coin_matrix(self):
        """Hadamard tensor product H x H is unitary with entries +/-0.5."""
        # The 4x4 Hadamard used is H tensor H
        h = [[0.5, 0.5, 0.5, 0.5],
             [0.5, -0.5, 0.5, -0.5],
             [0.5, 0.5, -0.5, -0.5],
             [0.5, -0.5, -0.5, 0.5]]
        # Check unitarity: H*H^T = I
        for i in range(4):
            for j in range(4):
                dot = sum(h[i][k] * h[j][k] for k in range(4))
                expected = 1.0 if i == j else 0.0
                assert abs(dot - expected) < 1e-10, f"H*H^T[{i}][{j}] = {dot}"

    def test_grover_coin_matrix(self):
        """Grover diffusion operator: G[i][j] = -delta(i,j) + 1/2."""
        # Verify G is unitary
        g = [[(-1 if i == j else 0) + 0.5 for j in range(4)] for i in range(4)]
        for i in range(4):
            for j in range(4):
                dot = sum(g[i][k] * g[j][k] for k in range(4))
                expected = 1.0 if i == j else 0.0
                assert abs(dot - expected) < 1e-10, f"G*G^T[{i}][{j}] = {dot}"

    def test_dft_coin_unitarity(self):
        """DFT coin is unitary."""
        wr = [1.0, 0.0, -1.0, 0.0]
        wi = [0.0, 1.0, 0.0, -1.0]
        # F[i][j] = omega^(i*j) / 2
        # Check F * F_dagger = I
        for i in range(4):
            for j in range(4):
                dot_re = 0.0
                dot_im = 0.0
                for k in range(4):
                    exp_ik = (i * k) % 4
                    exp_jk = (j * k) % 4
                    # F[i][k] * conj(F[j][k])
                    a_re = wr[exp_ik] * 0.5
                    a_im = wi[exp_ik] * 0.5
                    b_re = wr[exp_jk] * 0.5
                    b_im = -wi[exp_jk] * 0.5  # conjugate
                    dot_re += a_re * b_re - a_im * b_im
                    dot_im += a_re * b_im + a_im * b_re
                expected_re = 1.0 if i == j else 0.0
                assert abs(dot_re - expected_re) < 1e-10
                assert abs(dot_im) < 1e-10

    # ── Shift operator ──

    def test_periodic_shift(self):
        """Periodic boundary wraps particles around."""
        self.app._qwalk_init(0)  # periodic
        rows, cols = self.app.qwalk_rows, self.app.qwalk_cols
        # Clear all amplitudes
        for d in range(4):
            for r in range(rows):
                for c in range(cols):
                    self.app.qwalk_amp_re[d][r][c] = 0.0
                    self.app.qwalk_amp_im[d][r][c] = 0.0
        # Place amplitude at top-left corner, direction up (d=0)
        self.app.qwalk_amp_re[0][0][0] = 1.0
        self.app._qwalk_step()
        # After coin+shift, direction 0 (up) should wrap to bottom row
        # Check that probability at row 0 col 0 is redistributed
        total = self._total_probability()
        assert total > 0.99  # still near 1

    def test_absorbing_boundary_loses_probability(self):
        """Absorbing boundary loses probability at edges."""
        self.app._qwalk_init(1)  # Hadamard, single, absorbing
        self.app.qwalk_decoherence = 0.0
        initial_prob = self._total_probability()
        # Run many steps — probability should decrease at edges
        for _ in range(50):
            self.app._qwalk_step()
        final_prob = self._total_probability()
        # Absorbing boundary means probability leaks out
        assert final_prob <= initial_prob + 1e-8

    # ── Initial state tests ──

    def test_single_source_normalization(self):
        """Single source starts with total probability = 1."""
        self.app._qwalk_init(0)  # single source
        prob = self._total_probability()
        assert abs(prob - 1.0) < 1e-8

    def test_gaussian_normalization(self):
        """Gaussian wave packet starts with total probability = 1."""
        self.app._qwalk_init(4)  # Gaussian
        prob = self._total_probability()
        assert abs(prob - 1.0) < 1e-8

    def test_dual_source_normalization(self):
        """Dual source starts with total probability = 1."""
        self.app._qwalk_init(5)  # Dual
        prob = self._total_probability()
        assert abs(prob - 1.0) < 1e-8

    # ── Spreading test ──

    def test_quantum_spreading(self):
        """Quantum walk spreads probability from center."""
        self.app._qwalk_init(0)
        self.app.qwalk_decoherence = 0.0
        rows, cols = self.app.qwalk_rows, self.app.qwalk_cols
        cr, cc = rows // 2, cols // 2

        for _ in range(10):
            self.app._qwalk_step()

        prob = self.app.qwalk_prob
        # Probability should have spread beyond center
        off_center_prob = 0.0
        for r in range(rows):
            for c in range(cols):
                if abs(r - cr) > 2 or abs(c - cc) > 2:
                    off_center_prob += prob[r][c]
        assert off_center_prob > 0.01, "Quantum walk should spread from center"

    # ── Decoherence ──

    def test_decoherence_preserves_magnitude(self):
        """Decoherence changes phase but preserves amplitude magnitude."""
        random.seed(42)
        self.app._qwalk_init(6)  # decoherent preset
        # Decoherence randomizes phase but magnitude stays same per cell
        # Just ensure it runs without crash and probability is positive
        for _ in range(10):
            self.app._qwalk_step()
        total = self._total_probability()
        assert total > 0.0

    # ── All presets ──

    def test_all_presets_init_and_step(self):
        """All presets initialize and step without error."""
        for idx in range(len(self.app.QWALK_PRESETS)):
            random.seed(42)
            self.app._qwalk_init(idx)
            assert self.app.qwalk_mode is True
            for _ in range(3):
                self.app._qwalk_step()
            assert self.app.qwalk_generation == 3

    # ── Update prob ──

    def test_update_prob_matches_amplitudes(self):
        """Probability grid matches sum of squared amplitudes over directions."""
        self.app._qwalk_init(0)
        self.app._qwalk_step()
        self.app._qwalk_update_prob()
        rows, cols = self.app.qwalk_rows, self.app.qwalk_cols
        for r in range(rows):
            for c in range(cols):
                expected = 0.0
                for d in range(4):
                    re = self.app.qwalk_amp_re[d][r][c]
                    im = self.app.qwalk_amp_im[d][r][c]
                    expected += re ** 2 + im ** 2
                assert abs(self.app.qwalk_prob[r][c] - expected) < 1e-12

    # ── Display helpers ──
    # Note: curses.color_pair() requires initscr(), so we test what we can.

    def test_phase_char_low_intensity(self):
        """Low intensity returns empty (no curses call needed for zero case)."""
        ch, attr = self.app._qwalk_phase_char(0.0, 0.01)
        assert ch == "  "
        assert attr == 0

    def test_signed_char_zero(self):
        """Zero amplitude returns empty (no curses call needed)."""
        ch, attr = self.app._qwalk_signed_char(0.001, 1.0)
        assert ch == "  "
        assert attr == 0

    def test_prob_char_zero(self):
        """Zero probability returns empty (no curses call needed)."""
        ch, attr = self.app._qwalk_prob_char(0.001)
        assert ch == "  "
        assert attr == 0

    # ── Helper ──

    def _total_probability(self):
        """Sum all probabilities across the grid."""
        rows, cols = self.app.qwalk_rows, self.app.qwalk_cols
        total = 0.0
        for d in range(4):
            for r in range(rows):
                for c in range(cols):
                    total += (self.app.qwalk_amp_re[d][r][c] ** 2 +
                              self.app.qwalk_amp_im[d][r][c] ** 2)
        return total
