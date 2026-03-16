"""Tests for life.modes.recording — Recording & Export."""
import json
import os
import tempfile
import unittest.mock
from tests.conftest import make_mock_app
from life.modes.recording import (
    register, _capture_frame_plain, _export_cast, _export_txt,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    # Recording uses Ctrl+X toggle, not mode enter
    assert hasattr(app, '_cast_rec_toggle')
    assert hasattr(app, '_cast_rec_capture')
    assert app.cast_recording is False


def test_step_no_crash():
    app = _make_app()
    app._cast_rec_start()
    assert app.cast_recording is True
    # Patch curses.pair_number to avoid initscr() requirement
    with unittest.mock.patch("curses.pair_number", return_value=0):
        with unittest.mock.patch("curses.pair_content", return_value=(0, 0)):
            app.cast_last_capture = 0.0
            for _ in range(10):
                app.cast_last_capture = 0.0
                app._cast_rec_capture()
    assert len(app.cast_frames) == 10


def test_exit_cleanup():
    app = _make_app()
    app._cast_rec_start()
    with unittest.mock.patch("curses.pair_number", return_value=0):
        with unittest.mock.patch("curses.pair_content", return_value=(0, 0)):
            app.cast_last_capture = 0.0
            app._cast_rec_capture()
    assert len(app.cast_frames) == 1
    app._cast_rec_stop()  # stop sets cast_recording=False and opens export menu
    assert app.cast_recording is False
    assert app.cast_export_menu is True
    app._cast_rec_discard()
    assert app.cast_frames == []
    assert app.cast_export_menu is False


def test_toggle_starts_and_stops():
    """Toggle cycles recording on then off."""
    app = _make_app()
    app._cast_rec_toggle()
    assert app.cast_recording is True
    # Capture a frame so stop doesn't discard
    with unittest.mock.patch("curses.pair_number", return_value=0):
        with unittest.mock.patch("curses.pair_content", return_value=(0, 0)):
            app.cast_last_capture = 0.0
            app._cast_rec_capture()
    app._cast_rec_toggle()
    assert app.cast_recording is False
    assert app.cast_export_menu is True


def test_export_cast_creates_valid_file():
    """Exported .cast file has valid asciinema v2 header."""
    frames = ["Hello\r\nWorld", "Frame 2"]
    timestamps = [1000.0, 1000.1]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".cast", delete=False) as f:
        path = f.name
    try:
        _export_cast(frames, timestamps, 80, 24, path)
        with open(path, "r") as f:
            lines = f.readlines()
        # First line is header
        header = json.loads(lines[0])
        assert header["version"] == 2
        assert header["width"] == 80
        assert header["height"] == 24
        # Event lines
        assert len(lines) >= 3  # header + 2 events
        event = json.loads(lines[1])
        assert len(event) == 3
        assert event[1] == "o"
    finally:
        os.unlink(path)


def test_export_txt_creates_flipbook():
    """Exported .txt file contains frame separators."""
    frames = ["plain frame 1", "plain frame 2"]
    timestamps = [0.0, 0.5]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        _export_txt(frames, timestamps, path)
        with open(path, "r") as f:
            content = f.read()
        assert "--- Frame 1" in content
        assert "--- Frame 2" in content
        assert "\f" in content  # form-feed separator
    finally:
        os.unlink(path)


def test_fps_throttle():
    """Capture respects FPS budget and skips frames that are too close."""
    app = _make_app()
    app._cast_rec_start()
    app.cast_fps = 1  # 1 FPS = min 1 second between captures
    with unittest.mock.patch("curses.pair_number", return_value=0):
        with unittest.mock.patch("curses.pair_content", return_value=(0, 0)):
            # First capture succeeds (last_capture=0)
            app._cast_rec_capture()
            # Second capture within 1s should be skipped
            app._cast_rec_capture()
    assert len(app.cast_frames) == 1
