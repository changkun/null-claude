"""Tests for life.modes.music_visualizer — Music Visualizer mode."""
import math

from tests.conftest import make_mock_app
from life.modes.music_visualizer import (
    register,
    MUSVIS_PRESETS,
    MUSVIS_COLOR_NAMES,
    MUSVIS_BAR_CHARS,
    MUSVIS_TONE_PATTERNS,
)


def _make_app():
    app = make_mock_app()
    app.musvis_mode = False
    app.musvis_menu = False
    app.musvis_menu_sel = 0
    app.musvis_running = False
    app.musvis_generation = 0
    app.musvis_preset_name = ""
    app.musvis_preset_idx = 0
    app.musvis_time = 0.0
    app.musvis_spectrum = []
    app.musvis_waveform = []
    app.musvis_peak_history = []
    app.musvis_particles = []
    app.musvis_beat_energy = 0.0
    app.musvis_beat_avg = 0.0
    app.musvis_beat_flash = 0.0
    app.musvis_bass_energy = 0.0
    app.musvis_mid_energy = 0.0
    app.musvis_high_energy = 0.0
    app.musvis_tone_phase = 0.0
    app.musvis_view_mode = 0
    app.musvis_color_mode = 0
    app.musvis_sensitivity = 1.0
    app.musvis_num_bars = 32
    register(type(app))
    return app


# ── Constants validation ─────────────────────────────────────────────────────

def test_presets_count():
    assert len(MUSVIS_PRESETS) == 6


def test_color_names_lowercase():
    """Original monolith used lowercase color names."""
    assert MUSVIS_COLOR_NAMES == ["spectrum", "fire", "ocean", "neon"]


def test_bar_chars_9_levels():
    """BAR_CHARS must have 9 characters (space + 8 block levels)."""
    assert len(MUSVIS_BAR_CHARS) == 9
    assert MUSVIS_BAR_CHARS[0] == " "
    assert MUSVIS_BAR_CHARS[-1] == "\u2588"


def test_tone_patterns_count():
    assert len(MUSVIS_TONE_PATTERNS) == 4
    for pattern in MUSVIS_TONE_PATTERNS:
        assert len(pattern) == 4


def test_register_sets_class_constants():
    app = _make_app()
    assert type(app).MUSVIS_PRESETS == MUSVIS_PRESETS
    assert type(app).MUSVIS_COLOR_NAMES == MUSVIS_COLOR_NAMES
    assert type(app).MUSVIS_BAR_CHARS == MUSVIS_BAR_CHARS
    assert type(app).MUSVIS_TONE_PATTERNS == MUSVIS_TONE_PATTERNS


# ── Enter / exit ─────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_musvis_mode()
    assert app.musvis_menu is True
    assert app.musvis_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._musvis_init(0)
    app._exit_musvis_mode()
    assert app.musvis_mode is False
    assert app.musvis_menu is False
    assert app.musvis_running is False
    assert app.musvis_particles == []
    assert app.musvis_spectrum == []
    assert app.musvis_waveform == []
    assert app.musvis_peak_history == []


# ── Init per preset ──────────────────────────────────────────────────────────

def test_init_all_presets():
    app = _make_app()
    for idx in range(len(MUSVIS_PRESETS)):
        app._musvis_init(idx)
        assert app.musvis_preset_idx == idx
        assert app.musvis_running is True
        assert app.musvis_menu is False
        assert app.musvis_generation == 0
        assert app.musvis_time == 0.0
        assert len(app.musvis_spectrum) == app.musvis_num_bars
        assert len(app.musvis_waveform) == 80
        assert len(app.musvis_peak_history) == app.musvis_num_bars


def test_init_sets_view_mode_from_preset():
    """Each preset should map to its own view mode."""
    app = _make_app()
    for idx in range(len(MUSVIS_PRESETS)):
        app._musvis_init(idx)
        assert app.musvis_view_mode == idx


# ── Step ─────────────────────────────────────────────────────────────────────

def test_step_no_crash():
    app = _make_app()
    app._musvis_init(0)
    for _ in range(10):
        app._musvis_step()
    assert app.musvis_generation == 10


def test_step_advances_time():
    app = _make_app()
    app._musvis_init(0)
    app._musvis_step()
    assert abs(app.musvis_time - 0.04) < 1e-9


def test_step_generates_spectrum_data():
    app = _make_app()
    app._musvis_init(0)
    app._musvis_step()
    # After a step, spectrum should have non-zero values
    assert any(v > 0 for v in app.musvis_spectrum)


def test_step_generates_waveform_data():
    app = _make_app()
    app._musvis_init(0)
    app._musvis_step()
    assert any(v != 0 for v in app.musvis_waveform)


def test_step_calculates_band_energies():
    app = _make_app()
    app._musvis_init(0)
    app._musvis_step()
    # At least one band should have energy
    total = app.musvis_bass_energy + app.musvis_mid_energy + app.musvis_high_energy
    assert total > 0


# ── Audio data generation ────────────────────────────────────────────────────

def test_waveform_values_in_range():
    """All waveform samples must be in [-1, 1]."""
    app = _make_app()
    app._musvis_init(0)
    for _ in range(20):
        app._musvis_step()
        for sample in app.musvis_waveform:
            assert -1.0 <= sample <= 1.0


def test_spectrum_values_in_range():
    """All spectrum bins must be in [0, 1]."""
    app = _make_app()
    app._musvis_init(0)
    for _ in range(20):
        app._musvis_step()
        for val in app.musvis_spectrum:
            assert 0.0 <= val <= 1.0


def test_peak_history_tracks_max():
    """Peak history should always be >= current spectrum."""
    app = _make_app()
    app._musvis_init(0)
    for _ in range(10):
        app._musvis_step()
    for i in range(len(app.musvis_spectrum)):
        assert app.musvis_peak_history[i] >= app.musvis_spectrum[i] - 1e-9


def test_tone_pattern_cycling():
    """Different times should use different tone patterns."""
    app = _make_app()
    app._musvis_init(0)
    # At t=0 we get pattern 0, at t=2.0 we get pattern 1
    app.musvis_time = 0.0
    app._musvis_generate_audio_data()
    s1 = list(app.musvis_spectrum)
    app.musvis_time = 2.0
    app._musvis_generate_audio_data()
    s2 = list(app.musvis_spectrum)
    # Different patterns should produce different spectra
    assert s1 != s2


# ── Particle system ──────────────────────────────────────────────────────────

def test_spawn_particles():
    app = _make_app()
    app._musvis_init(0)
    app.musvis_beat_energy = 0.5
    app._musvis_spawn_particles()
    assert len(app.musvis_particles) >= 5
    for p in app.musvis_particles:
        assert "r" in p and "c" in p
        assert "vr" in p and "vc" in p
        assert "life" in p
        assert p["life"] == 1.0


def test_update_particles_decay():
    app = _make_app()
    app._musvis_init(0)
    app.musvis_beat_energy = 0.5
    app._musvis_spawn_particles()
    n = len(app.musvis_particles)
    # Update many times to let particles die
    for _ in range(60):
        app._musvis_update_particles()
    assert len(app.musvis_particles) < n


def test_particles_capped_at_200():
    app = _make_app()
    app._musvis_init(0)
    app.musvis_beat_energy = 1.0
    for _ in range(50):
        app._musvis_spawn_particles()
    app._musvis_update_particles()
    assert len(app.musvis_particles) <= 200


# ── Color mapping ────────────────────────────────────────────────────────────

def test_color_function_exists():
    """_musvis_color should be registered and callable."""
    app = _make_app()
    assert callable(app._musvis_color)


def test_color_mode_boundaries():
    """Color mode indices 0-3 are tracked correctly."""
    app = _make_app()
    for mode in range(4):
        app.musvis_color_mode = mode
        assert app.musvis_color_mode == mode


# ── Key handling — menu ──────────────────────────────────────────────────────

def test_menu_navigate_down():
    app = _make_app()
    app._enter_musvis_mode()
    app._handle_musvis_menu_key(ord("j"))
    assert app.musvis_menu_sel == 1


def test_menu_navigate_up_wraps():
    app = _make_app()
    app._enter_musvis_mode()
    app._handle_musvis_menu_key(ord("k"))
    assert app.musvis_menu_sel == len(MUSVIS_PRESETS) - 1


def test_menu_select():
    app = _make_app()
    app._enter_musvis_mode()
    app.musvis_menu_sel = 2
    app._handle_musvis_menu_key(ord("\n"))
    assert app.musvis_preset_idx == 2
    assert app.musvis_running is True


def test_menu_cancel():
    app = _make_app()
    app._enter_musvis_mode()
    app._handle_musvis_menu_key(ord("q"))
    assert app.musvis_menu is False


# ── Key handling — active visualizer ─────────────────────────────────────────

def test_key_space_toggles():
    app = _make_app()
    app._musvis_init(0)
    assert app.musvis_running is True
    app._handle_musvis_key(ord(" "))
    assert app.musvis_running is False


def test_key_n_next_preset():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("n"))
    assert app.musvis_preset_idx == 1


def test_key_N_prev_preset():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("N"))
    assert app.musvis_preset_idx == len(MUSVIS_PRESETS) - 1


def test_key_v_cycles_view():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("v"))
    assert app.musvis_view_mode == 1


def test_key_c_cycles_color():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("c"))
    assert app.musvis_color_mode == 1


def test_key_sensitivity_increase():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("+"))
    assert abs(app.musvis_sensitivity - 1.1) < 1e-9


def test_key_sensitivity_decrease():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("-"))
    assert abs(app.musvis_sensitivity - 0.9) < 1e-9


def test_key_sensitivity_bounds():
    app = _make_app()
    app._musvis_init(0)
    app.musvis_sensitivity = 3.0
    app._handle_musvis_key(ord("+"))
    assert app.musvis_sensitivity == 3.0
    app.musvis_sensitivity = 0.1
    app._handle_musvis_key(ord("-"))
    assert app.musvis_sensitivity == 0.1


def test_key_b_increase_bars():
    app = _make_app()
    app._musvis_init(0)
    old_bars = app.musvis_num_bars
    app._handle_musvis_key(ord("b"))
    assert app.musvis_num_bars == old_bars + 4
    assert len(app.musvis_spectrum) == app.musvis_num_bars


def test_key_B_decrease_bars():
    app = _make_app()
    app._musvis_init(0)
    old_bars = app.musvis_num_bars
    app._handle_musvis_key(ord("B"))
    assert app.musvis_num_bars == old_bars - 4


def test_key_bars_bounds():
    app = _make_app()
    app._musvis_init(0)
    app.musvis_num_bars = 64
    app._handle_musvis_key(ord("b"))
    assert app.musvis_num_bars == 64
    app.musvis_num_bars = 8
    app._handle_musvis_key(ord("B"))
    assert app.musvis_num_bars == 8


def test_key_r_resets():
    app = _make_app()
    app._musvis_init(0)
    for _ in range(5):
        app._musvis_step()
    app._handle_musvis_key(ord("r"))
    assert app.musvis_generation == 0
    assert app.musvis_time == 0.0


def test_key_m_returns_to_menu():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("m"))
    assert app.musvis_menu is True
    assert app.musvis_mode is False


def test_key_q_exits():
    app = _make_app()
    app._musvis_init(0)
    app._handle_musvis_key(ord("q"))
    assert app.musvis_mode is False
    assert app.musvis_running is False


# ── Beat detection ───────────────────────────────────────────────────────────

def test_beat_detection_mechanism():
    """Beat detection should trigger when total energy exceeds average * 1.5."""
    app = _make_app()
    app._musvis_init(0)
    # Artificially set low beat_avg so next step triggers beat detection
    app.musvis_beat_avg = 0.01
    # Run a step where tones produce energy
    app.musvis_time = 0.0  # pattern with base_freq=261 -> energy
    app._musvis_step()
    # With low beat_avg, the total_energy should exceed threshold
    # Check that beat energy was updated (either flash or avg increased)
    assert app.musvis_beat_avg > 0.01 or app.musvis_beat_flash > 0
