"""Tests for life.modes.long_exposure — Long-Exposure Photography mode."""
import time
from tests.conftest import make_mock_app
from life.modes.long_exposure import (
    register, BLEND_MODES, _DENSITY_GLYPHS, _EXPOSURE_PRESETS,
)
from life.colors import TrueColorBuffer


def _make_app():
    app = make_mock_app()
    app.tc_buf = TrueColorBuffer()
    app.tc_colormap = 'viridis'
    register(type(app))
    app._long_exposure_init()
    return app


# ── Module-level constants ───────────────────────────────────────────────────

def test_blend_modes():
    assert BLEND_MODES == ["additive", "max", "average"]


def test_density_glyphs():
    assert len(_DENSITY_GLYPHS) == 6
    assert _DENSITY_GLYPHS[0] == " "
    assert _DENSITY_GLYPHS[-1] == "█"


def test_exposure_presets():
    for p in _EXPOSURE_PRESETS:
        assert isinstance(p, int) and p > 0


# ── Initialisation ───────────────────────────────────────────────────────────

def test_init_defaults():
    app = _make_app()
    assert app.long_exp_active is False
    assert app.long_exp_frozen is False
    assert app.long_exp_window == 200
    assert app.long_exp_blend == "additive"
    assert app.long_exp_frames_captured == 0
    assert app._long_exp_accum == {}
    assert app._long_exp_composite == {}
    assert app._long_exp_max_hits == 0


# ── Key handling ─────────────────────────────────────────────────────────────

def test_ctrl_e_starts_capture():
    app = _make_app()
    assert app._long_exposure_handle_key(5)  # Ctrl+E
    assert app.long_exp_active is True
    assert app.long_exp_frames_captured == 0


def test_ctrl_e_stops_and_freezes():
    app = _make_app()
    app._long_exposure_handle_key(5)  # start
    # Simulate some accumulated data
    app._long_exp_accum[(5, 5)] = [100, 100, 100, 3, 100, 100, 100]
    app._long_exp_max_hits = 3
    app.long_exp_frames_captured = 10
    app._long_exposure_handle_key(5)  # stop
    assert app.long_exp_active is False
    assert app.long_exp_frozen is True
    assert len(app._long_exp_composite) > 0


def test_ctrl_e_cancel_no_frames():
    app = _make_app()
    app._long_exposure_handle_key(5)  # start
    app._long_exposure_handle_key(5)  # stop with 0 frames
    assert app.long_exp_active is False
    assert app.long_exp_frozen is False


def test_ctrl_f_freeze_unfreeze():
    app = _make_app()
    # Start capture, accumulate, freeze
    app._long_exposure_handle_key(5)  # start
    app._long_exp_accum[(5, 5)] = [200, 150, 100, 5, 200, 150, 100]
    app._long_exp_max_hits = 5
    app.long_exp_frames_captured = 5
    app._long_exposure_handle_key(6)  # Ctrl+F freeze
    assert app.long_exp_frozen is True
    # Unfreeze
    app._long_exposure_handle_key(6)
    assert app.long_exp_frozen is False


def test_bracket_adjust_window():
    app = _make_app()
    initial = app.long_exp_window
    app._long_exposure_handle_key(ord("]"))
    assert app.long_exp_window == initial + 50
    app._long_exposure_handle_key(ord("["))
    assert app.long_exp_window == initial


def test_window_min_clamp():
    app = _make_app()
    app.long_exp_window = 10
    app._long_exposure_handle_key(ord("["))
    assert app.long_exp_window == 10  # can't go below 10


def test_window_max_clamp():
    app = _make_app()
    app.long_exp_window = 1000
    app._long_exposure_handle_key(ord("]"))
    assert app.long_exp_window == 1000  # can't go above 1000


def test_brace_cycle_blend():
    app = _make_app()
    assert app.long_exp_blend == "additive"
    app._long_exposure_handle_key(ord("}"))
    assert app.long_exp_blend == "max"
    app._long_exposure_handle_key(ord("}"))
    assert app.long_exp_blend == "average"
    app._long_exposure_handle_key(ord("}"))
    assert app.long_exp_blend == "additive"


def test_brace_cycle_blend_backward():
    app = _make_app()
    app._long_exposure_handle_key(ord("{"))
    assert app.long_exp_blend == "average"


def test_unhandled_key_returns_false():
    app = _make_app()
    assert app._long_exposure_handle_key(ord("z")) is False


def test_ctrl_bracket_export_no_composite():
    app = _make_app()
    assert app._long_exposure_handle_key(29)  # Ctrl+]
    assert "No frozen composite" in app.message


# ── Accumulation ─────────────────────────────────────────────────────────────

def test_accumulate_truecolor_cells():
    app = _make_app()
    app._long_exposure_handle_key(5)  # start
    # Simulate truecolor buffer content
    app.tc_buf.put(5, 10, "█", 200, 100, 50)
    app.tc_buf.put(6, 10, "█", 100, 200, 50)
    app._long_exposure_process()
    assert app.long_exp_frames_captured == 1
    assert (5, 10) in app._long_exp_accum
    buf = app._long_exp_accum[(5, 10)]
    assert buf[0] == 200  # total_r
    assert buf[1] == 100  # total_g
    assert buf[2] == 50   # total_b
    assert buf[3] == 1    # hit_count


def test_accumulate_multiple_frames():
    app = _make_app()
    app._long_exposure_handle_key(5)  # start
    for i in range(3):
        app.tc_buf.clear()
        app.tc_buf.put(5, 10, "█", 100, 100, 100)
        app._long_exposure_process()
    assert app.long_exp_frames_captured == 3
    buf = app._long_exp_accum[(5, 10)]
    assert buf[3] == 3  # 3 hits
    assert buf[0] == 300  # 3 * 100


def test_accumulate_max_tracking():
    app = _make_app()
    app._long_exposure_handle_key(5)  # start
    # Frame 1: dim
    app.tc_buf.put(5, 10, "█", 50, 50, 50)
    app._long_exposure_process()
    # Frame 2: bright
    app.tc_buf.clear()
    app.tc_buf.put(5, 10, "█", 255, 200, 150)
    app._long_exposure_process()
    buf = app._long_exp_accum[(5, 10)]
    assert buf[4] == 255  # max_r
    assert buf[5] == 200  # max_g
    assert buf[6] == 150  # max_b


def test_no_accumulate_when_inactive():
    app = _make_app()
    app.tc_buf.put(5, 10, "█", 200, 100, 50)
    app._long_exposure_process()
    assert app.long_exp_frames_captured == 0
    assert len(app._long_exp_accum) == 0


def test_no_accumulate_when_frozen():
    app = _make_app()
    app.long_exp_active = True
    app.long_exp_frozen = True
    app.tc_buf.put(5, 10, "█", 200, 100, 50)
    app._long_exposure_process()
    assert app.long_exp_frames_captured == 0


# ── Auto-freeze ──────────────────────────────────────────────────────────────

def test_auto_freeze_at_window():
    app = _make_app()
    app.long_exp_window = 5
    app._long_exposure_handle_key(5)  # start
    for i in range(5):
        app.tc_buf.clear()
        app.tc_buf.put(5, 10, "█", 100, 100, 100)
        app._long_exposure_process()
    assert app.long_exp_frozen is True
    assert app.long_exp_active is False
    assert app.long_exp_frames_captured == 5


# ── Composite generation ────────────────────────────────────────────────────

def test_composite_additive_blend():
    app = _make_app()
    app.long_exp_blend = "additive"
    app.long_exp_window = 500  # large window to prevent auto-freeze
    app._long_exposure_handle_key(5)  # start
    for _ in range(10):
        app.tc_buf.clear()
        app.tc_buf.put(5, 10, "█", 100, 100, 100)
        app._long_exposure_process()
    # Add a cell that's only hit once for comparison
    app.tc_buf.clear()
    app.tc_buf.put(8, 15, "█", 100, 100, 100)
    app._long_exposure_process()
    # Manually freeze
    app._long_exposure_handle_key(5)  # stop & freeze
    assert (5, 10) in app._long_exp_composite
    r1, g1, b1, d1 = app._long_exp_composite[(5, 10)]
    r2, g2, b2, d2 = app._long_exp_composite[(8, 15)]
    # High-traffic cell should have higher density
    assert d1 > d2


def test_composite_max_blend():
    app = _make_app()
    app.long_exp_blend = "max"
    app.long_exp_window = 500
    app._long_exposure_handle_key(5)
    # Frame with dim value
    app.tc_buf.put(5, 10, "█", 50, 50, 50)
    app._long_exposure_process()
    # Frame with bright value
    app.tc_buf.clear()
    app.tc_buf.put(5, 10, "█", 250, 200, 150)
    app._long_exposure_process()
    # Freeze
    app._long_exposure_handle_key(5)
    r, g, b, _ = app._long_exp_composite[(5, 10)]
    assert r == 250
    assert g == 200
    assert b == 150


def test_composite_average_blend():
    app = _make_app()
    app.long_exp_blend = "average"
    app._long_exposure_handle_key(5)
    for val in [100, 200]:
        app.tc_buf.clear()
        app.tc_buf.put(5, 10, "█", val, val, val)
        app._long_exposure_process()
    app._long_exposure_handle_key(5)  # freeze
    r, g, b, _ = app._long_exp_composite[(5, 10)]
    assert r == 150  # (100+200) / 2
    assert g == 150
    assert b == 150


# ── Drawing ──────────────────────────────────────────────────────────────────

def test_draw_composite_populates_tc_buf():
    app = _make_app()
    app._long_exp_composite = {
        (5, 10): (200, 150, 100, 0.8),
        (6, 10): (100, 200, 50, 0.3),
    }
    app.long_exp_frozen = True
    app.long_exp_frames_captured = 50
    app._long_exposure_draw_composite()
    assert len(app.tc_buf.cells) > 0


def test_draw_indicator_active():
    app = _make_app()
    app.long_exp_active = True
    app.long_exp_frames_captured = 42
    app.long_exp_window = 200
    # Should not raise
    app._long_exposure_draw_indicator()


def test_draw_indicator_frozen():
    app = _make_app()
    app.long_exp_frozen = True
    app.long_exp_frames_captured = 100
    app._long_exposure_draw_indicator()


# ── Export ───────────────────────────────────────────────────────────────────

def test_export_creates_files(tmp_path, monkeypatch):
    import life.modes.long_exposure as le_mod
    app = _make_app()
    app.long_exp_frozen = True
    app.long_exp_frames_captured = 10
    app.long_exp_window = 100
    app._long_exp_composite = {
        (2, 3): (200, 150, 100, 0.9),
        (3, 4): (50, 100, 200, 0.2),
    }
    # Redirect SAVE_DIR
    monkeypatch.setattr("life.constants.SAVE_DIR", str(tmp_path))
    app._long_exposure_export()
    exp_dir = tmp_path / "long_exposure"
    assert exp_dir.exists()
    json_files = list(exp_dir.glob("*.json"))
    ansi_files = list(exp_dir.glob("*.ans"))
    assert len(json_files) == 1
    assert len(ansi_files) == 1
    # Verify JSON content
    import json
    data = json.loads(json_files[0].read_text())
    assert data["frames"] == 10
    assert len(data["pixels"]) == 2


def test_export_no_composite():
    app = _make_app()
    app.long_exp_frozen = False
    app._long_exposure_export()
    assert "No frozen composite" in app.message


# ── Ctrl+E restarts from frozen ─────────────────────────────────────────────

def test_ctrl_e_restarts_from_frozen():
    app = _make_app()
    # Create a frozen composite
    app.long_exp_frozen = True
    app._long_exp_composite = {(1, 1): (255, 255, 255, 1.0)}
    # Ctrl+E should clear frozen state and start new capture
    app._long_exposure_handle_key(5)
    assert app.long_exp_frozen is False
    assert app.long_exp_active is True
    assert app.long_exp_frames_captured == 0
    assert len(app._long_exp_accum) == 0


# ── Registration ─────────────────────────────────────────────────────────────

def test_register_attaches_methods():
    app = _make_app()
    assert hasattr(app, '_long_exposure_init')
    assert hasattr(app, '_long_exposure_process')
    assert hasattr(app, '_long_exposure_draw_composite')
    assert hasattr(app, '_long_exposure_draw_indicator')
    assert hasattr(app, '_long_exposure_handle_key')
    assert hasattr(app, '_long_exposure_export')
    assert callable(app._long_exposure_init)
