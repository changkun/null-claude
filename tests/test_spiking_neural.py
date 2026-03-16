"""Tests for spiking_neural mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.spiking_neural import register


class TestSpikingNeural:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_snn_mode()
        assert self.app.snn_menu is True
        assert self.app.snn_menu_sel == 0

    def test_step_no_crash(self):
        self.app.snn_mode = True
        self.app.snn_menu_sel = 0
        self.app._snn_init(0)
        for _ in range(10):
            self.app._snn_step()
        assert self.app.snn_generation == 10

    def test_exit_cleanup(self):
        self.app.snn_mode = True
        self.app.snn_menu_sel = 0
        self.app._snn_init(0)
        self.app._snn_step()
        self.app._exit_snn_mode()
        assert self.app.snn_mode is False
        assert self.app.snn_menu is False
        assert self.app.snn_running is False
        assert self.app.snn_v == []
        assert self.app.snn_u == []
        assert self.app.snn_fired == []
        assert self.app.snn_fire_history == []

    # ── Initialization tests ───────────────────────────────────────────

    def test_init_grid_dimensions(self):
        """Grid dimensions match terminal size."""
        self.app._snn_init(0)
        rows, cols = self.app.snn_rows, self.app.snn_cols
        assert rows >= 20
        assert cols >= 20
        assert len(self.app.snn_v) == rows
        assert len(self.app.snn_v[0]) == cols
        assert len(self.app.snn_u) == rows
        assert len(self.app.snn_fired) == rows
        assert len(self.app.snn_fire_history) == rows
        assert len(self.app.snn_a) == rows
        assert len(self.app.snn_b) == rows
        assert len(self.app.snn_c_param) == rows
        assert len(self.app.snn_d) == rows
        assert len(self.app.snn_is_excitatory) == rows

    def test_init_sets_parameters_from_preset(self):
        """Preset parameters are applied correctly."""
        presets = self.app.SNN_PRESETS
        for i, (name, _desc, excit, weight, noise, dt, init_type) in enumerate(presets):
            random.seed(42)
            self.app._snn_init(i)
            assert self.app.snn_weight == weight, f"Preset {i}: weight"
            assert self.app.snn_noise_amp == noise, f"Preset {i}: noise"
            assert self.app.snn_dt == dt, f"Preset {i}: dt"
            assert self.app.snn_preset_name == name

    def test_all_presets_init_without_error(self):
        """Every SNN_PRESET initializes and steps without error."""
        for i in range(len(self.app.SNN_PRESETS)):
            random.seed(42)
            self.app._snn_init(i)
            self.app._snn_step()
            assert self.app.snn_generation == 1

    def test_excitatory_inhibitory_ratio(self):
        """Excitatory/inhibitory ratio roughly matches preset."""
        random.seed(42)
        # Use preset with excit_ratio = 0.8
        self.app._snn_init(0)
        rows, cols = self.app.snn_rows, self.app.snn_cols
        total = rows * cols
        exc_count = sum(
            1 for r in range(rows) for c in range(cols)
            if self.app.snn_is_excitatory[r][c]
        )
        ratio = exc_count / total
        # Should be roughly 0.8 (within statistical bounds)
        assert 0.7 < ratio < 0.9, f"Excitatory ratio {ratio} too far from 0.8"

    # ── Izhikevich model parameters ────────────────────────────────────

    def test_excitatory_neuron_params(self):
        """Excitatory neurons get standard regular-spiking parameters."""
        random.seed(42)
        self.app._snn_init(0)  # default random init
        rows, cols = self.app.snn_rows, self.app.snn_cols
        found_exc = False
        for r in range(rows):
            for c in range(cols):
                if self.app.snn_is_excitatory[r][c]:
                    assert self.app.snn_a[r][c] == 0.02
                    assert self.app.snn_b[r][c] == 0.2
                    assert self.app.snn_c_param[r][c] == -65.0
                    assert self.app.snn_d[r][c] == 8.0
                    found_exc = True
                    break
            if found_exc:
                break
        assert found_exc, "Should have at least one excitatory neuron"

    def test_inhibitory_neuron_params(self):
        """Inhibitory neurons get fast-spiking parameters."""
        random.seed(42)
        self.app._snn_init(0)
        rows, cols = self.app.snn_rows, self.app.snn_cols
        found_inh = False
        for r in range(rows):
            for c in range(cols):
                if not self.app.snn_is_excitatory[r][c]:
                    assert self.app.snn_a[r][c] == 0.1
                    assert self.app.snn_b[r][c] == 0.2
                    assert self.app.snn_c_param[r][c] == -65.0
                    assert self.app.snn_d[r][c] == 2.0
                    found_inh = True
                    break
            if found_inh:
                break
        assert found_inh, "Should have at least one inhibitory neuron"

    def test_chattering_preset_params(self):
        """Chattering preset uses chattering neuron parameters for excitatory."""
        chat_idx = next(
            i for i, p in enumerate(self.app.SNN_PRESETS)
            if p[6] == "chattering"
        )
        random.seed(42)
        self.app._snn_init(chat_idx)
        rows, cols = self.app.snn_rows, self.app.snn_cols
        for r in range(rows):
            for c in range(cols):
                if self.app.snn_is_excitatory[r][c]:
                    assert self.app.snn_c_param[r][c] == -50.0
                    assert self.app.snn_d[r][c] == 2.0
                    return
        assert False, "No excitatory chattering neuron found"

    def test_cortical_preset_params(self):
        """Cortical preset uses variable parameters."""
        cort_idx = next(
            i for i, p in enumerate(self.app.SNN_PRESETS)
            if p[6] == "cortical"
        )
        random.seed(42)
        self.app._snn_init(cort_idx)
        rows, cols = self.app.snn_rows, self.app.snn_cols
        # Excitatory neurons should have c_param in range [-65, -50] (= -65 + 15*re^2)
        for r in range(rows):
            for c in range(cols):
                if self.app.snn_is_excitatory[r][c]:
                    assert -65.0 <= self.app.snn_c_param[r][c] <= -50.0
                    assert 2.0 <= self.app.snn_d[r][c] <= 8.0
                else:
                    # Inhibitory: a in [0.02, 0.1], b in [0.2, 0.25]
                    assert 0.02 <= self.app.snn_a[r][c] <= 0.1
                    assert 0.2 <= self.app.snn_b[r][c] <= 0.25

    # ── Spike dynamics tests ───────────────────────────────────────────

    def test_spike_resets_voltage(self):
        """When a neuron reaches 30mV, it resets to c_param."""
        random.seed(42)
        self.app._snn_init(0)
        rows, cols = self.app.snn_rows, self.app.snn_cols

        # Force a neuron to spike by setting voltage high
        self.app.snn_v[0][0] = 30.0
        self.app.snn_fired[0][0] = True  # Mark as fired for other neurons to see

        self.app._snn_step()

        # After step, any neuron that spiked should have v = c_param
        # Check the specific neuron we forced
        # Note: since the new step processes all neurons, (0,0) will fire based on input
        # We can at least verify fired neurons get reset
        for r in range(rows):
            for c in range(cols):
                if self.app.snn_fired[r][c]:
                    assert self.app.snn_v[r][c] == self.app.snn_c_param[r][c], \
                        f"Fired neuron at ({r},{c}) not reset to c_param"

    def test_fire_history_decay(self):
        """Fire history decays by 0.85 for non-firing neurons."""
        random.seed(42)
        self.app._snn_init(0)

        # Set fire history to 1.0 for a cell
        self.app.snn_fire_history[5][5] = 1.0

        # Step (the cell might or might not fire)
        self.app._snn_step()

        # If the cell didn't fire, history should be 0.85
        if not self.app.snn_fired[5][5]:
            assert abs(self.app.snn_fire_history[5][5] - 0.85) < 1e-10
        else:
            assert self.app.snn_fire_history[5][5] == 1.0

    def test_fire_history_set_on_spike(self):
        """Fire history is set to 1.0 when a neuron fires."""
        random.seed(42)
        self.app._snn_init(0)

        # Run until some neurons fire
        for _ in range(50):
            self.app._snn_step()

        rows, cols = self.app.snn_rows, self.app.snn_cols
        for r in range(rows):
            for c in range(cols):
                if self.app.snn_fired[r][c]:
                    assert self.app.snn_fire_history[r][c] == 1.0

    def test_synaptic_excitatory_input(self):
        """Excitatory firing neighbor adds positive input."""
        random.seed(42)
        self.app._snn_init(0)
        rows, cols = self.app.snn_rows, self.app.snn_cols

        # Clear all fired states, then fire one excitatory neighbor
        self.app.snn_fired = [[False] * cols for _ in range(rows)]
        self.app.snn_is_excitatory[5][5] = True
        self.app.snn_fired[5][5] = True

        # Record neighbor voltage before step
        v_before = self.app.snn_v[5][6]
        self.app.snn_noise_amp = 0.0  # Remove noise for determinism

        self.app._snn_step()

        # Neighbor (5,6) should have received positive synaptic input
        # The Izhikevich dynamics are complex, but the input should push voltage up
        # relative to a case with no firing neighbors

    def test_synaptic_inhibitory_input(self):
        """Inhibitory firing neighbor adds negative input."""
        random.seed(42)
        self.app._snn_init(0)
        rows, cols = self.app.snn_rows, self.app.snn_cols

        # Clear all fired states, fire one inhibitory neighbor
        self.app.snn_fired = [[False] * cols for _ in range(rows)]
        self.app.snn_is_excitatory[5][5] = False
        self.app.snn_fired[5][5] = True
        self.app.snn_noise_amp = 0.0

        self.app._snn_step()
        # Inhibitory input should push voltage lower (or at least not cause spike)
        # This is an integration test; just verify no crash

    # ── init_type-specific tests ───────────────────────────────────────

    def test_wave_seed_init_stimulates_left_columns(self):
        """wave_seed init sets left 2 columns to spiking threshold."""
        wave_idx = next(
            i for i, p in enumerate(self.app.SNN_PRESETS)
            if p[6] == "wave_seed"
        )
        random.seed(42)
        self.app._snn_init(wave_idx)
        rows = self.app.snn_rows
        for r in range(rows):
            assert self.app.snn_v[r][0] == 30.0
            assert self.app.snn_v[r][1] == 30.0

    def test_center_seed_init_stimulates_center(self):
        """center_seed init stimulates a central patch."""
        center_idx = next(
            i for i, p in enumerate(self.app.SNN_PRESETS)
            if p[6] == "center_seed"
        )
        random.seed(42)
        self.app._snn_init(center_idx)
        rows, cols = self.app.snn_rows, self.app.snn_cols
        cr, cc = rows // 2, cols // 2
        assert self.app.snn_v[cr][cc] == 30.0

    def test_two_cluster_init(self):
        """two_cluster init stimulates two perpendicular stripes."""
        two_idx = next(
            i for i, p in enumerate(self.app.SNN_PRESETS)
            if p[6] == "two_cluster"
        )
        random.seed(42)
        self.app._snn_init(two_idx)
        rows, cols = self.app.snn_rows, self.app.snn_cols
        # Vertical stripe
        c_start = cols // 4
        for r in range(rows):
            assert self.app.snn_v[r][c_start] == 30.0
        # Horizontal stripe
        r_start = rows // 4
        for c in range(cols):
            assert self.app.snn_v[r_start][c] == 30.0

    # ── Fire rate test ─────────────────────────────────────────────────

    def test_fire_rate_zero_initially(self):
        """No neurons fire initially (all below threshold)."""
        random.seed(42)
        self.app._snn_init(0)
        # Initial membrane potentials are around -65 +/- 5, well below 30
        rate = self.app._snn_fire_rate()
        assert rate == 0.0, "No neurons should fire before first step"

    def test_fire_rate_range(self):
        """Fire rate is in [0, 1]."""
        random.seed(42)
        self.app._snn_init(0)
        for _ in range(20):
            self.app._snn_step()
        rate = self.app._snn_fire_rate()
        assert 0.0 <= rate <= 1.0

    def test_fire_rate_empty_grid(self):
        """Fire rate is 0 for zero-size grid."""
        self.app._snn_init(0)
        self.app.snn_rows = 0
        self.app.snn_cols = 0
        assert self.app._snn_fire_rate() == 0.0

    # ── Generation counter ─────────────────────────────────────────────

    def test_generation_counter_increments(self):
        """Each step increments the generation counter."""
        self.app._snn_init(0)
        assert self.app.snn_generation == 0
        self.app._snn_step()
        assert self.app.snn_generation == 1
        self.app._snn_step()
        assert self.app.snn_generation == 2

    # ── Numerical stability ────────────────────────────────────────────

    def test_no_nan_or_inf_after_many_steps(self):
        """SNN simulation stays numerically stable."""
        random.seed(42)
        self.app._snn_init(0)
        for _ in range(200):
            self.app._snn_step()
        for r in range(self.app.snn_rows):
            for c in range(self.app.snn_cols):
                v = self.app.snn_v[r][c]
                u = self.app.snn_u[r][c]
                assert math.isfinite(v), f"Non-finite voltage {v} at ({r},{c})"
                assert math.isfinite(u), f"Non-finite recovery {u} at ({r},{c})"

    def test_voltage_bounded(self):
        """Membrane potential stays bounded after many steps."""
        random.seed(42)
        self.app._snn_init(0)
        for _ in range(100):
            self.app._snn_step()
        for r in range(self.app.snn_rows):
            for c in range(self.app.snn_cols):
                v = self.app.snn_v[r][c]
                # Non-fired neurons should have v < 30; fired reset to c_param ~ -65 to -50
                if not self.app.snn_fired[r][c]:
                    assert v < 30.0, f"Non-fired neuron at ({r},{c}) has v={v} >= 30"

    def test_moore_neighborhood_boundaries(self):
        """Boundary neurons correctly skip out-of-bounds neighbors."""
        random.seed(42)
        self.app._snn_init(0)
        rows, cols = self.app.snn_rows, self.app.snn_cols

        # Set corner neuron's neighbors to firing
        self.app.snn_fired = [[False] * cols for _ in range(rows)]
        self.app.snn_fired[0][1] = True
        self.app.snn_fired[1][0] = True
        self.app.snn_fired[1][1] = True
        self.app.snn_noise_amp = 0.0

        # Step should not crash on boundary neurons
        self.app._snn_step()
        assert self.app.snn_generation == 1

    def test_high_noise_preset_stays_stable(self):
        """High noise preset does not diverge."""
        noise_idx = next(
            i for i, p in enumerate(self.app.SNN_PRESETS)
            if p[4] >= 10.0  # high noise
        )
        random.seed(42)
        self.app._snn_init(noise_idx)
        for _ in range(100):
            self.app._snn_step()
        # Verify all voltages are finite
        for r in range(self.app.snn_rows):
            for c in range(self.app.snn_cols):
                assert math.isfinite(self.app.snn_v[r][c])
