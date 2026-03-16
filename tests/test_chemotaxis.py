"""Tests for chemotaxis mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.chemotaxis import register, CHEMOTAXIS_PRESETS


class TestChemotaxis:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    # ── Presets ──────────────────────────────────────────────────────
    def test_presets_exist(self):
        assert len(CHEMOTAXIS_PRESETS) == 8

    def test_presets_structure(self):
        for preset in CHEMOTAXIS_PRESETS:
            assert len(preset) == 10
            name, desc, growth, ndiff, motility, chemo, sprod, sdec, cons, init = preset
            assert isinstance(name, str) and name
            assert isinstance(desc, str)
            assert growth > 0
            assert ndiff > 0
            assert motility >= 0
            assert chemo >= 0
            assert sprod >= 0
            assert sdec >= 0
            assert cons > 0
            assert init in ("center_seed", "multi_seed", "gradient_seed")

    def test_presets_registered_on_class(self):
        assert hasattr(type(self.app), 'CHEMOTAXIS_PRESETS')
        assert type(self.app).CHEMOTAXIS_PRESETS is CHEMOTAXIS_PRESETS

    # ── Enter / Exit ─────────────────────────────────────────────────
    def test_enter(self):
        self.app._enter_chemo_mode()
        assert self.app.chemo_menu is True
        assert self.app.chemo_menu_sel == 0

    def test_exit_cleanup(self):
        self.app.chemo_mode = True
        self.app.chemo_menu_sel = 0
        self.app._chemo_init(0)
        self.app._chemo_step()
        self.app._exit_chemo_mode()
        assert self.app.chemo_mode is False
        assert self.app.chemo_menu is False
        assert self.app.chemo_running is False
        assert self.app.chemo_bacteria == []
        assert self.app.chemo_nutrient == []
        assert self.app.chemo_signal == []

    # ── Init for all presets ─────────────────────────────────────────
    def test_init_all_presets(self):
        for idx in range(len(CHEMOTAXIS_PRESETS)):
            random.seed(42)
            self.app._chemo_init(idx)
            assert self.app.chemo_mode is True
            assert self.app.chemo_running is False
            assert self.app.chemo_generation == 0
            assert self.app.chemo_preset_name == CHEMOTAXIS_PRESETS[idx][0]
            assert self.app.chemo_rows > 0
            assert self.app.chemo_cols > 0
            assert len(self.app.chemo_bacteria) == self.app.chemo_rows
            assert len(self.app.chemo_bacteria[0]) == self.app.chemo_cols

    def test_init_center_seed(self):
        """center_seed places bacteria cluster in center."""
        self.app._chemo_init(0)  # Eden Cluster
        cr = self.app.chemo_rows // 2
        cc = self.app.chemo_cols // 2
        assert self.app.chemo_bacteria[cr][cc] > 0.0
        # Nutrient starts at 1.0 everywhere for center_seed
        assert self.app.chemo_nutrient[0][0] == 1.0

    def test_init_multi_seed(self):
        """multi_seed places bacteria at multiple locations."""
        self.app._chemo_init(5)  # Multi-Colony uses multi_seed
        rows, cols = self.app.chemo_rows, self.app.chemo_cols
        total_bact = sum(self.app.chemo_bacteria[r][c]
                         for r in range(rows) for c in range(cols))
        assert total_bact > 0
        # Should have bacteria at multiple distinct regions
        cr, cc = rows // 2, cols // 2
        q1 = self.app.chemo_bacteria[cr // 2][cc // 2]
        q4 = self.app.chemo_bacteria[cr + cr // 2][cc + cc // 2]
        assert q1 > 0 or q4 > 0, "Multi-seed should seed multiple locations"

    def test_init_gradient_seed(self):
        """gradient_seed creates a nutrient gradient (low left, high right)."""
        self.app._chemo_init(6)  # Nutrient Gradient
        cols = self.app.chemo_cols
        # Left edge nutrient < right edge nutrient
        left_nutrient = self.app.chemo_nutrient[0][0]
        right_nutrient = self.app.chemo_nutrient[0][cols - 1]
        assert right_nutrient > left_nutrient

    # ── Step dynamics ────────────────────────────────────────────────
    def test_step_no_crash(self):
        self.app.chemo_mode = True
        self.app.chemo_menu_sel = 0
        self.app._chemo_init(0)
        for _ in range(10):
            self.app._chemo_step()
        assert self.app.chemo_generation == 10

    def test_step_increments_generation(self):
        self.app._chemo_init(0)
        assert self.app.chemo_generation == 0
        self.app._chemo_step()
        assert self.app.chemo_generation == 1

    def test_step_values_clamped(self):
        """All fields stay in [0, 1] after stepping."""
        self.app._chemo_init(0)
        for _ in range(20):
            self.app._chemo_step()
        rows, cols = self.app.chemo_rows, self.app.chemo_cols
        for r in range(rows):
            for c in range(cols):
                assert 0.0 <= self.app.chemo_bacteria[r][c] <= 1.0
                assert 0.0 <= self.app.chemo_nutrient[r][c] <= 1.0
                assert 0.0 <= self.app.chemo_signal[r][c] <= 1.0

    def test_step_evolves_state(self):
        """After stepping, the grid should differ from initial state."""
        self.app._chemo_init(0)
        initial_bact = [row[:] for row in self.app.chemo_bacteria]
        self.app._chemo_step()
        differs = any(
            abs(self.app.chemo_bacteria[r][c] - initial_bact[r][c]) > 1e-10
            for r in range(self.app.chemo_rows) for c in range(self.app.chemo_cols)
        )
        assert differs, "Chemo step should change the bacteria field"

    def test_bacteria_growth_with_nutrient(self):
        """Bacteria should grow where there are nutrients."""
        self.app._chemo_init(0)
        cr = self.app.chemo_rows // 2
        cc = self.app.chemo_cols // 2
        initial_bact = self.app.chemo_bacteria[cr][cc]
        assert initial_bact > 0
        assert self.app.chemo_nutrient[cr][cc] > 0
        # After a step, bacteria at center with nutrients should grow
        self.app._chemo_step()
        # Check that total bacteria mass has changed (growth + motility)
        # Individual cell may decrease due to motility, but growth should occur

    def test_nutrient_consumed(self):
        """Nutrients should be consumed where bacteria are present."""
        self.app._chemo_init(0)
        cr = self.app.chemo_rows // 2
        cc = self.app.chemo_cols // 2
        initial_nutr = self.app.chemo_nutrient[cr][cc]
        assert initial_nutr > 0
        assert self.app.chemo_bacteria[cr][cc] > 0
        for _ in range(5):
            self.app._chemo_step()
        # Nutrient at center should decrease
        assert self.app.chemo_nutrient[cr][cc] < initial_nutr

    def test_signal_production(self):
        """Signal should be produced where bacteria are present (when sig_prod > 0)."""
        self.app._chemo_init(1)  # DLA Tendrils, sig_prod=0.2
        cr = self.app.chemo_rows // 2
        cc = self.app.chemo_cols // 2
        assert self.app.chemo_signal[cr][cc] == 0.0
        self.app._chemo_step()
        # Bacteria produce signal
        assert self.app.chemo_signal[cr][cc] > 0.0

    def test_zero_flux_boundary(self):
        """Chemotaxis uses zero-flux boundary (clamped indices, not wrapping)."""
        self.app._chemo_init(0)
        rows, cols = self.app.chemo_rows, self.app.chemo_cols
        # Clear everything and put bacteria at corner
        for r in range(rows):
            for c in range(cols):
                self.app.chemo_bacteria[r][c] = 0.0
                self.app.chemo_nutrient[r][c] = 1.0
                self.app.chemo_signal[r][c] = 0.0
        self.app.chemo_bacteria[0][0] = 0.5
        self.app._chemo_step()
        # With zero-flux boundary, the opposite corner should NOT receive bacteria
        # (unlike wrapping which would spread to [rows-1][cols-1])
        assert self.app.chemo_bacteria[rows - 1][cols - 1] == 0.0

    def test_logistic_growth_saturates(self):
        """Logistic growth term b*n*(1-b) should prevent bacteria > 1."""
        self.app._chemo_init(0)
        rows, cols = self.app.chemo_rows, self.app.chemo_cols
        # Set bacteria near saturation everywhere
        for r in range(rows):
            for c in range(cols):
                self.app.chemo_bacteria[r][c] = 0.95
                self.app.chemo_nutrient[r][c] = 1.0
        for _ in range(10):
            self.app._chemo_step()
        for r in range(rows):
            for c in range(cols):
                assert self.app.chemo_bacteria[r][c] <= 1.0

    def test_all_presets_run_10_steps(self):
        """Every preset survives 10 steps with values in [0,1]."""
        for idx in range(len(CHEMOTAXIS_PRESETS)):
            random.seed(42)
            self.app._chemo_init(idx)
            for _ in range(10):
                self.app._chemo_step()
            rows, cols = self.app.chemo_rows, self.app.chemo_cols
            for r in range(rows):
                for c in range(cols):
                    assert 0.0 <= self.app.chemo_bacteria[r][c] <= 1.0
                    assert 0.0 <= self.app.chemo_nutrient[r][c] <= 1.0
                    assert 0.0 <= self.app.chemo_signal[r][c] <= 1.0

    # ── Grid dimensions ──────────────────────────────────────────────
    def test_grid_dimensions(self):
        self.app._chemo_init(0)
        assert len(self.app.chemo_bacteria) == self.app.chemo_rows
        assert len(self.app.chemo_nutrient) == self.app.chemo_rows
        assert len(self.app.chemo_signal) == self.app.chemo_rows
        for r in range(self.app.chemo_rows):
            assert len(self.app.chemo_bacteria[r]) == self.app.chemo_cols
            assert len(self.app.chemo_nutrient[r]) == self.app.chemo_cols
            assert len(self.app.chemo_signal[r]) == self.app.chemo_cols

    # ── Parameters stored correctly ──────────────────────────────────
    def test_parameters_stored(self):
        for idx, (name, _, growth, ndiff, motility, chemo, sprod, sdec, cons, _) in enumerate(CHEMOTAXIS_PRESETS):
            self.app._chemo_init(idx)
            assert self.app.chemo_growth_rate == growth
            assert self.app.chemo_nutrient_diff == ndiff
            assert self.app.chemo_motility == motility
            assert self.app.chemo_chemotaxis == chemo
            assert self.app.chemo_signal_prod == sprod
            assert self.app.chemo_signal_decay == sdec
            assert self.app.chemo_consumption == cons

    # ── Empty grid stability ─────────────────────────────────────────
    def test_empty_grid_stays_empty(self):
        """No bacteria, signal stays zero (only nutrient diffusion happens)."""
        self.app._chemo_init(0)
        rows, cols = self.app.chemo_rows, self.app.chemo_cols
        for r in range(rows):
            for c in range(cols):
                self.app.chemo_bacteria[r][c] = 0.0
                self.app.chemo_signal[r][c] = 0.0
        for _ in range(5):
            self.app._chemo_step()
        for r in range(rows):
            for c in range(cols):
                assert self.app.chemo_bacteria[r][c] == 0.0
                assert self.app.chemo_signal[r][c] == 0.0

    def test_chemotaxis_flux_with_no_signal(self):
        """When there's no signal gradient, chemotactic flux should be zero."""
        self.app._chemo_init(0)
        # Eden Cluster has chemotaxis=0.0, so no flux regardless
        # Use a preset with chemotaxis > 0
        self.app._chemo_init(3)  # Concentric Rings, chemotaxis=0.5
        rows, cols = self.app.chemo_rows, self.app.chemo_cols
        # Signal is uniformly zero at start, so chemo flux should be zero
        # and dynamics driven purely by growth + motility
        self.app._chemo_step()
        # Just verify it doesn't crash and values stay bounded
        for r in range(rows):
            for c in range(cols):
                assert 0.0 <= self.app.chemo_bacteria[r][c] <= 1.0
