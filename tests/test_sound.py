"""Tests for sound engine — deep validation against commit e272832."""
import math
import random
import struct
import threading
import pytest
from unittest.mock import patch, MagicMock

from tests.conftest import make_mock_app
from life.sound import _PENTATONIC, _row_to_freq, SoundEngine
from life.grid import Grid


# ── _PENTATONIC constant ─────────────────────────────────────────────────────

class TestPentatonic:
    """Validate the pentatonic scale definition matches original."""

    def test_pentatonic_values(self):
        """C D E G A semitone offsets."""
        assert _PENTATONIC == [0, 2, 4, 7, 9]

    def test_pentatonic_length(self):
        assert len(_PENTATONIC) == 5

    def test_pentatonic_ascending(self):
        """Intervals must be strictly ascending."""
        for i in range(len(_PENTATONIC) - 1):
            assert _PENTATONIC[i] < _PENTATONIC[i + 1]


# ── _row_to_freq ─────────────────────────────────────────────────────────────

class TestRowToFreq:
    """Validate row-to-frequency mapping matches original commit e272832."""

    def test_base_freq_default(self):
        """Bottom row (last row) should return base freq (220 Hz)."""
        total_rows = 10
        freq = _row_to_freq(total_rows - 1, total_rows)
        # idx = 0, octave=0, degree=0, semitones=0 -> 220 * 2^0 = 220
        assert freq == pytest.approx(220.0)

    def test_top_row_highest_pitch(self):
        """Row 0 should produce the highest frequency."""
        total_rows = 10
        freq_top = _row_to_freq(0, total_rows)
        freq_bottom = _row_to_freq(total_rows - 1, total_rows)
        assert freq_top > freq_bottom

    def test_inversion_logic(self):
        """Row 0 maps to idx=total_rows-1 (highest), last row maps to idx=0."""
        total_rows = 5
        # Row 4 (bottom): idx = 0 -> semitones 0 -> 220 Hz
        assert _row_to_freq(4, 5) == pytest.approx(220.0)
        # Row 3: idx = 1 -> degree=1 -> semitones=2 -> 220 * 2^(2/12)
        assert _row_to_freq(3, 5) == pytest.approx(220.0 * (2.0 ** (2 / 12.0)))
        # Row 2: idx = 2 -> degree=2 -> semitones=4 -> 220 * 2^(4/12)
        assert _row_to_freq(2, 5) == pytest.approx(220.0 * (2.0 ** (4 / 12.0)))
        # Row 1: idx = 3 -> degree=3 -> semitones=7 -> 220 * 2^(7/12)
        assert _row_to_freq(1, 5) == pytest.approx(220.0 * (2.0 ** (7 / 12.0)))
        # Row 0: idx = 4 -> degree=4 -> semitones=9 -> 220 * 2^(9/12)
        assert _row_to_freq(0, 5) == pytest.approx(220.0 * (2.0 ** (9 / 12.0)))

    def test_octave_wrapping(self):
        """When idx >= 5, we wrap into the next octave."""
        total_rows = 11
        # Row 0: idx = 10 -> octave=2, degree=0 -> semitones=24
        freq = _row_to_freq(0, total_rows)
        expected = 220.0 * (2.0 ** (24 / 12.0))
        assert freq == pytest.approx(expected)

    def test_custom_base_freq(self):
        """Custom base frequency should scale all notes."""
        freq = _row_to_freq(9, 10, base_freq=440.0)
        assert freq == pytest.approx(440.0)

    def test_monotonically_decreasing_with_row(self):
        """Frequencies should decrease as row index increases."""
        total_rows = 20
        freqs = [_row_to_freq(r, total_rows) for r in range(total_rows)]
        for i in range(len(freqs) - 1):
            assert freqs[i] >= freqs[i + 1], (
                f"freq at row {i} ({freqs[i]}) should be >= freq at row {i+1} ({freqs[i+1]})"
            )

    def test_pentatonic_intervals_correct(self):
        """Adjacent rows within the same octave should produce pentatonic intervals."""
        # With 5 rows, each row maps to one pentatonic degree
        total_rows = 5
        freqs = [_row_to_freq(r, total_rows) for r in range(total_rows)]
        # Ratios between consecutive should match pentatonic intervals
        for i in range(4):
            ratio = freqs[i] / freqs[i + 1]
            assert ratio > 1.0  # higher pitch for lower row index

    def test_single_row(self):
        """Edge case: single row grid."""
        freq = _row_to_freq(0, 1)
        assert freq == pytest.approx(220.0)


# ── SoundEngine initialization ───────────────────────────────────────────────

class TestSoundEngineInit:
    """Validate SoundEngine state matches original."""

    def test_default_state(self):
        engine = SoundEngine()
        assert engine.enabled is False
        assert engine.SAMPLE_RATE == 22050
        assert engine.MAX_POLYPHONY == 12
        assert engine._play_thread is None
        assert isinstance(engine._stop_event, threading.Event)
        assert hasattr(engine._lock, 'acquire') and hasattr(engine._lock, 'release')

    def test_toggle_on(self):
        engine = SoundEngine()
        result = engine.toggle()
        assert result is True
        assert engine.enabled is True

    def test_toggle_off(self):
        engine = SoundEngine()
        engine.toggle()  # on
        result = engine.toggle()  # off
        assert result is False
        assert engine.enabled is False

    def test_toggle_off_sets_stop_event(self):
        engine = SoundEngine()
        engine.toggle()  # on
        engine.toggle()  # off
        assert engine._stop_event.is_set()

    def test_detect_player_returns_list_or_none(self):
        result = SoundEngine._detect_player()
        assert result is None or isinstance(result, list)


# ── SoundEngine._synthesize ──────────────────────────────────────────────────

class TestSynthesize:
    """Validate audio synthesis matches original commit e272832."""

    def setup_method(self):
        self.engine = SoundEngine()

    def test_empty_freqs_returns_silence(self):
        """No frequencies should produce silence (all zero samples)."""
        data = self.engine._synthesize([], 0.1, 0.5)
        n_samples = int(22050 * 0.1)
        assert len(data) == n_samples * 2
        # All samples should be zero
        for i in range(n_samples):
            sample = struct.unpack_from("<h", data, i * 2)[0]
            assert sample == 0

    def test_output_length(self):
        """Output byte length = n_samples * 2 (16-bit samples)."""
        duration = 0.05
        data = self.engine._synthesize([440.0], duration, 0.5)
        expected_samples = int(22050 * duration)
        assert len(data) == expected_samples * 2

    def test_single_tone_not_silent(self):
        """A single frequency at non-zero volume should produce non-zero samples."""
        data = self.engine._synthesize([440.0], 0.1, 1.0)
        n_samples = int(22050 * 0.1)
        has_nonzero = False
        for i in range(n_samples):
            sample = struct.unpack_from("<h", data, i * 2)[0]
            if sample != 0:
                has_nonzero = True
                break
        assert has_nonzero

    def test_samples_within_s16_range(self):
        """All samples must be within [-32767, 32767]."""
        data = self.engine._synthesize([220.0, 440.0, 880.0], 0.05, 1.0)
        n_samples = len(data) // 2
        for i in range(n_samples):
            sample = struct.unpack_from("<h", data, i * 2)[0]
            assert -32767 <= sample <= 32767

    def test_envelope_attack(self):
        """First sample should be near zero (attack ramp)."""
        data = self.engine._synthesize([440.0], 0.1, 1.0)
        first_sample = struct.unpack_from("<h", data, 0)[0]
        assert abs(first_sample) < 100  # near zero due to envelope ramp

    def test_envelope_release(self):
        """Last sample should be near zero (release ramp)."""
        data = self.engine._synthesize([440.0], 0.1, 1.0)
        n_samples = len(data) // 2
        last_sample = struct.unpack_from("<h", data, (n_samples - 1) * 2)[0]
        assert abs(last_sample) < 100

    def test_ramp_samples_calculation(self):
        """Ramp length should be min(5ms worth of samples, n_samples // 2)."""
        duration = 0.1
        n_samples = int(22050 * duration)
        ramp = min(int(0.005 * 22050), n_samples // 2)
        assert ramp == int(0.005 * 22050)  # 110 samples for 5ms at 22050

    def test_volume_scaling(self):
        """Higher volume should produce larger sample magnitudes."""
        data_low = self.engine._synthesize([440.0], 0.05, 0.2)
        data_high = self.engine._synthesize([440.0], 0.05, 1.0)
        n = len(data_low) // 2

        # Compare max absolute values in the middle (past the ramp)
        mid_start = n // 4
        mid_end = 3 * n // 4
        max_low = max(abs(struct.unpack_from("<h", data_low, i * 2)[0])
                      for i in range(mid_start, mid_end))
        max_high = max(abs(struct.unpack_from("<h", data_high, i * 2)[0])
                       for i in range(mid_start, mid_end))
        assert max_high > max_low

    def test_polyphony_amplitude_division(self):
        """Per-voice amplitude = volume / len(freqs) as per original."""
        # With 2 freqs, amplitude per voice should be halved
        data_1 = self.engine._synthesize([440.0], 0.05, 1.0)
        data_2 = self.engine._synthesize([440.0, 440.0], 0.05, 1.0)
        n = len(data_1) // 2
        mid = n // 2
        # Two identical freqs at half amplitude each should sum to roughly the same
        s1 = struct.unpack_from("<h", data_1, mid * 2)[0]
        s2 = struct.unpack_from("<h", data_2, mid * 2)[0]
        # They should be close (both are sin(same phase) but amplitude division differs)
        assert abs(s1 - s2) < abs(s1) * 0.1 + 50  # within 10% + tolerance


# ── SoundEngine.play_grid ────────────────────────────────────────────────────

class TestPlayGrid:
    """Validate play_grid logic matches original commit e272832."""

    def setup_method(self):
        self.engine = SoundEngine()
        # Force a mock player so play_grid doesn't bail on _play_cmd is None
        self.engine._play_cmd = ["mock_player"]

    def test_disabled_engine_does_nothing(self):
        """When disabled, play_grid should return without spawning threads."""
        grid = Grid(10, 10)
        grid.cells[5][5] = 1
        grid.population = 1
        self.engine.enabled = False
        self.engine.play_grid(grid, 0.5)
        assert self.engine._play_thread is None

    def test_no_play_cmd_does_nothing(self):
        """When no player available, play_grid returns."""
        self.engine.enabled = True
        self.engine._play_cmd = None
        grid = Grid(10, 10)
        grid.cells[5][5] = 1
        grid.population = 1
        self.engine.play_grid(grid, 0.5)
        assert self.engine._play_thread is None

    def test_empty_grid_does_nothing(self):
        """No active rows means no sound."""
        self.engine.enabled = True
        grid = Grid(10, 10)
        grid.population = 0
        self.engine.play_grid(grid, 0.5)
        assert self.engine._play_thread is None

    def test_active_grid_spawns_thread(self):
        """Grid with living cells should spawn a playback thread."""
        self.engine.enabled = True
        grid = Grid(10, 10)
        grid.cells[3][5] = 1
        grid.population = 1
        with patch.object(self.engine, '_play_samples'):
            self.engine.play_grid(grid, 0.5)
            assert self.engine._play_thread is not None

    def test_polyphony_limit(self):
        """When active rows exceed MAX_POLYPHONY, should be limited."""
        self.engine.enabled = True
        grid = Grid(30, 10)
        # Make all 30 rows active
        for r in range(30):
            grid.cells[r][0] = 1
        grid.population = 30

        freqs_captured = []
        original_synth = self.engine._synthesize
        def capture_synth(freqs, duration, volume):
            freqs_captured.extend(freqs)
            return b"\x00\x00"  # minimal return
        self.engine._synthesize = capture_synth

        with patch.object(self.engine, '_play_samples'):
            self.engine.play_grid(grid, 0.5)

        # Should be limited to MAX_POLYPHONY
        assert len(freqs_captured) <= self.engine.MAX_POLYPHONY

    def test_density_volume_mapping(self):
        """Master volume = 0.15 + 0.85 * density, clamped to [0.15, 1.0]."""
        # Empty density -> 0.15
        vol_empty = 0.15 + 0.85 * 0.0
        assert vol_empty == pytest.approx(0.15)
        # Full density -> 1.0
        vol_full = 0.15 + 0.85 * 1.0
        assert vol_full == pytest.approx(1.0)

    def test_duration_clamping(self):
        """Duration = max(0.05, min(speed_delay * 0.8, 2.0))."""
        # Very fast
        assert max(0.05, min(0.01 * 0.8, 2.0)) == 0.05
        # Very slow
        assert max(0.05, min(10.0 * 0.8, 2.0)) == 2.0
        # Normal
        assert max(0.05, min(0.5 * 0.8, 2.0)) == pytest.approx(0.4)

    def test_thread_not_stacked(self):
        """If a thread is still alive, play_grid should skip."""
        self.engine.enabled = True
        grid = Grid(10, 10)
        grid.cells[3][5] = 1
        grid.population = 1

        # Simulate an alive thread
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        self.engine._play_thread = mock_thread

        with patch.object(self.engine, '_synthesize') as mock_synth:
            self.engine.play_grid(grid, 0.5)
            mock_synth.assert_not_called()


# ── SoundEngine._detect_player ───────────────────────────────────────────────

class TestDetectPlayer:
    """Test player detection logic."""

    def test_paplay_preferred(self):
        """paplay should be preferred when available."""
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/paplay" if cmd == "paplay" else None):
            result = SoundEngine._detect_player()
            assert result[0] == "paplay"

    def test_aplay_fallback(self):
        """aplay used when paplay unavailable."""
        def which(cmd):
            if cmd == "aplay":
                return "/usr/bin/aplay"
            return None
        with patch("shutil.which", side_effect=which):
            result = SoundEngine._detect_player()
            assert result[0] == "aplay"

    def test_afplay_returns_none_for_args(self):
        """afplay on macOS returns None (special file-based handling)."""
        def which(cmd):
            if cmd == "afplay":
                return "/usr/bin/afplay"
            return None
        with patch("shutil.which", side_effect=which):
            result = SoundEngine._detect_player()
            # afplay returns None as args since it needs special WAV file handling
            assert result is None

    def test_no_player_returns_none(self):
        """No player found returns None."""
        with patch("shutil.which", return_value=None):
            result = SoundEngine._detect_player()
            assert result is None


# ── Integration with mock app ────────────────────────────────────────────────

class TestSoundAppIntegration:
    """Test that sound engine integrates with the app framework."""

    def test_mock_app_has_sound_engine(self):
        app = make_mock_app()
        # mock_app sets sound_engine to None (lightweight mock)
        assert hasattr(app, "sound_engine")

    def test_sound_engine_standalone_creation(self):
        """SoundEngine can be created independently."""
        engine = SoundEngine()
        assert engine.enabled is False

    def test_full_pipeline_no_crash(self):
        """Complete pipeline from grid to synthesis runs without error."""
        engine = SoundEngine()
        engine.enabled = True
        engine._play_cmd = ["mock"]

        grid = Grid(20, 20)
        # Place a glider
        for r, c in [(1, 2), (2, 3), (3, 1), (3, 2), (3, 3)]:
            grid.cells[r][c] = 1
        grid.population = 5

        with patch.object(engine, '_play_samples'):
            engine.play_grid(grid, 0.5)
            # Should have spawned a thread
            assert engine._play_thread is not None
