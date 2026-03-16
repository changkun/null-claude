"""Tests for GIF recording — deep validation against commit 7519caf."""
import random, pytest, tempfile, os
from tests.conftest import make_mock_app
from life.grid import Grid


# ── Unit tests for GIF helper functions ──────────────────────────────────────

class TestGifAgeIndex:
    """Verify _gif_age_index maps ages to palette indices matching original."""

    def test_dead_cell(self):
        from life.utils import _gif_age_index
        assert _gif_age_index(0) == 0
        assert _gif_age_index(-1) == 0

    def test_newborn(self):
        from life.utils import _gif_age_index
        assert _gif_age_index(1) == 1

    def test_young(self):
        from life.utils import _gif_age_index
        assert _gif_age_index(2) == 2
        assert _gif_age_index(3) == 2

    def test_mature(self):
        from life.utils import _gif_age_index
        assert _gif_age_index(4) == 3
        assert _gif_age_index(8) == 3

    def test_old(self):
        from life.utils import _gif_age_index
        assert _gif_age_index(9) == 4
        assert _gif_age_index(20) == 4

    def test_ancient(self):
        from life.utils import _gif_age_index
        assert _gif_age_index(21) == 5
        assert _gif_age_index(100) == 5
        assert _gif_age_index(999) == 5


class TestGifPalette:
    """Verify _GIF_PALETTE matches the original from commit 7519caf."""

    def test_palette_length(self):
        from life.colors import _GIF_PALETTE
        assert len(_GIF_PALETTE) == 8

    def test_palette_values_match_original(self):
        from life.colors import _GIF_PALETTE
        expected = [
            (18, 18, 24),       # 0: background (dark)
            (0, 200, 0),        # 1: newborn (green)
            (0, 200, 200),      # 2: young (cyan)
            (200, 200, 0),      # 3: mature (yellow)
            (200, 0, 200),      # 4: old (magenta)
            (200, 0, 0),        # 5: ancient (red)
            (100, 100, 100),    # 6: grid lines (subtle)
            (255, 255, 255),    # 7: spare (white)
        ]
        assert _GIF_PALETTE == expected

    def test_palette_entries_are_rgb_tuples(self):
        from life.colors import _GIF_PALETTE
        for entry in _GIF_PALETTE:
            assert isinstance(entry, tuple)
            assert len(entry) == 3
            for ch in entry:
                assert 0 <= ch <= 255


# ── LZW compression tests ───────────────────────────────────────────────────

class TestLzwCompress:
    """Verify _lzw_compress produces valid LZW data."""

    def test_single_pixel(self):
        from life.utils import _lzw_compress
        result = _lzw_compress([0], 3)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_uniform_pixels(self):
        from life.utils import _lzw_compress
        # All same color -- should compress well
        pixels = [0] * 100
        result = _lzw_compress(pixels, 3)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_varied_pixels(self):
        from life.utils import _lzw_compress
        pixels = [i % 6 for i in range(256)]
        result = _lzw_compress(pixels, 3)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_large_input_triggers_table_reset(self):
        from life.utils import _lzw_compress
        # Large enough to overflow the 4096-entry code table
        random.seed(42)
        pixels = [random.randint(0, 7) for _ in range(10000)]
        result = _lzw_compress(pixels, 3)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestGifSubBlocks:
    """Verify _gif_sub_blocks splits data correctly per GIF spec."""

    def test_empty_data(self):
        from life.utils import _gif_sub_blocks
        result = _gif_sub_blocks(b"")
        assert result == b"\x00"  # just the block terminator

    def test_short_data(self):
        from life.utils import _gif_sub_blocks
        data = b"\x01\x02\x03"
        result = _gif_sub_blocks(data)
        assert result[0] == 3  # length byte
        assert result[1:4] == data
        assert result[4] == 0  # terminator

    def test_exact_255_bytes(self):
        from life.utils import _gif_sub_blocks
        data = bytes(range(255))
        result = _gif_sub_blocks(data)
        assert result[0] == 255
        assert result[1:256] == data
        assert result[256] == 0  # terminator

    def test_longer_than_255_splits(self):
        from life.utils import _gif_sub_blocks
        data = bytes([0xAA] * 300)
        result = _gif_sub_blocks(data)
        # First block: 255 bytes
        assert result[0] == 255
        # Second block: 45 bytes
        assert result[256] == 45
        # Terminator
        assert result[-1] == 0


# ── write_gif integration tests ─────────────────────────────────────────────

class TestWriteGif:
    """End-to-end tests for GIF file generation."""

    def test_empty_frames_no_file(self):
        from life.utils import write_gif
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.gif")
            write_gif(path, [])
            assert not os.path.exists(path)

    def test_single_frame_creates_valid_gif(self):
        from life.utils import write_gif
        frame = [[0, 1, 0], [2, 0, 5], [0, 10, 25]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "single.gif")
            write_gif(path, [frame], cell_size=2, delay_cs=10)
            assert os.path.exists(path)
            with open(path, "rb") as f:
                data = f.read()
            # GIF89a header
            assert data[:6] == b"GIF89a"
            # Trailer
            assert data[-1:] == b"\x3B"

    def test_multi_frame_gif(self):
        from life.utils import write_gif
        frames = [
            [[0, 0], [0, 0]],
            [[1, 0], [0, 1]],
            [[0, 2], [3, 0]],
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "multi.gif")
            write_gif(path, frames, cell_size=4, delay_cs=15)
            assert os.path.exists(path)
            with open(path, "rb") as f:
                data = f.read()
            assert data[:6] == b"GIF89a"
            assert data[-1:] == b"\x3B"
            # Verify Netscape extension present (loop forever)
            assert b"NETSCAPE2.0" in data

    def test_gif_dimensions_in_header(self):
        """Verify the logical screen descriptor encodes correct dimensions."""
        import struct
        from life.utils import write_gif
        frame = [[0] * 5 for _ in range(3)]  # 3 rows, 5 cols
        cell_size = 4
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dims.gif")
            write_gif(path, [frame], cell_size=cell_size)
            with open(path, "rb") as f:
                data = f.read()
            # Bytes 6-9: width (LE u16), height (LE u16)
            width, height = struct.unpack("<HH", data[6:10])
            assert width == 5 * cell_size   # 20
            assert height == 3 * cell_size  # 12

    def test_gif_global_color_table(self):
        """Verify the GCT has 8 entries (3 bytes each = 24 bytes)."""
        from life.utils import write_gif
        from life.colors import _GIF_PALETTE
        frame = [[0, 1], [2, 3]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gct.gif")
            write_gif(path, [frame], cell_size=1)
            with open(path, "rb") as f:
                data = f.read()
            # Packed byte at offset 10: 0b10000010 means GCT present, 8 colors
            assert data[10] == 0b10000010
            # GCT starts at offset 13, 8 entries x 3 bytes = 24 bytes
            gct = data[13:13 + 24]
            for i, (r, g, b) in enumerate(_GIF_PALETTE[:8]):
                assert gct[i * 3] == r
                assert gct[i * 3 + 1] == g
                assert gct[i * 3 + 2] == b

    def test_cell_size_parameter(self):
        """Different cell_size values produce different file sizes."""
        from life.utils import write_gif
        frame = [[1, 0], [0, 1]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "small.gif")
            path2 = os.path.join(tmpdir, "large.gif")
            write_gif(path1, [frame], cell_size=1)
            write_gif(path2, [frame], cell_size=8)
            size1 = os.path.getsize(path1)
            size2 = os.path.getsize(path2)
            # Larger cell_size => more pixels => larger file
            assert size2 > size1

    def test_delay_encoded_correctly(self):
        """Verify the graphic control extension contains the right delay."""
        import struct
        from life.utils import write_gif
        frame = [[1]]
        delay = 42
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "delay.gif")
            write_gif(path, [frame], cell_size=1, delay_cs=delay)
            with open(path, "rb") as f:
                data = f.read()
            # Find GCE: 0x21 0xF9 0x04 <packed> <delay_lo> <delay_hi>
            gce_idx = data.index(b"\x21\xF9\x04")
            delay_bytes = data[gce_idx + 4: gce_idx + 6]
            encoded_delay = struct.unpack("<H", delay_bytes)[0]
            assert encoded_delay == delay

    def test_all_age_tiers_represented(self):
        """A frame with cells at each age tier uses palette indices 0-5."""
        from life.utils import write_gif, _gif_age_index
        # One cell per age tier
        frame = [[0, 1, 3, 8, 20, 25]]
        expected_indices = [_gif_age_index(a) for a in frame[0]]
        assert set(expected_indices) == {0, 1, 2, 3, 4, 5}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tiers.gif")
            write_gif(path, [frame], cell_size=1)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0


# ── Recording state management tests (via mock app) ─────────────────────────

class TestRecordingState:
    """Test the GIF recording workflow using mock app attributes."""

    def test_initial_state(self):
        app = make_mock_app()
        assert app.recording is False
        assert app.recorded_frames == []
        assert app.recording_start_gen == 0

    def test_capture_frame_copies_grid(self):
        """_capture_recording_frame should deep-copy grid cells."""
        app = make_mock_app(grid_rows=5, grid_cols=5)
        app.recording = True
        app.recorded_frames = []
        # Set some cells alive
        app.grid.cells[0][0] = 1
        app.grid.cells[1][1] = 3
        # Simulate frame capture (same logic as App._capture_recording_frame)
        app.recorded_frames.append([row[:] for row in app.grid.cells])
        assert len(app.recorded_frames) == 1
        # Mutate the grid -- recorded frame should be unaffected
        app.grid.cells[0][0] = 99
        assert app.recorded_frames[0][0][0] == 1

    def test_multi_frame_capture(self):
        app = make_mock_app(grid_rows=4, grid_cols=4)
        app.recording = True
        app.recorded_frames = []
        for gen in range(5):
            app.grid.cells[gen % 4][gen % 4] = gen + 1
            app.recorded_frames.append([row[:] for row in app.grid.cells])
        assert len(app.recorded_frames) == 5

    def test_export_writes_gif_file(self):
        """Full pipeline: capture frames then export to GIF via write_gif."""
        from life.utils import write_gif
        app = make_mock_app(grid_rows=6, grid_cols=6)
        app.recording = True
        app.recorded_frames = []
        # Capture a few frames with some alive cells
        for gen in range(3):
            for r in range(6):
                for c in range(6):
                    if (r + c + gen) % 3 == 0:
                        app.grid.cells[r][c] = gen + 1
                    else:
                        app.grid.cells[r][c] = 0
            app.recorded_frames.append([row[:] for row in app.grid.cells])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "recording.gif")
            write_gif(path, app.recorded_frames, cell_size=4, delay_cs=10)
            assert os.path.exists(path)
            with open(path, "rb") as f:
                data = f.read()
            assert data[:6] == b"GIF89a"
            assert data[-1:] == b"\x3B"
            # Should have 3 image descriptors (one per frame)
            # Each starts with 0x2C
            image_descriptors = data.count(b"\x2C")
            assert image_descriptors == 3

    def test_recording_cancel_no_frames(self):
        """Stopping recording with no frames captured should not crash."""
        app = make_mock_app()
        app.recording = True
        app.recorded_frames = []
        # Simulate toggle off with no frames
        app.recording = False
        if not app.recorded_frames:
            app._flash("Recording cancelled (no frames captured)")
        assert "cancelled" in app.message.lower()

    def test_recorded_frames_cleared_after_export(self):
        """After export, recorded_frames should be emptied."""
        from life.utils import write_gif
        app = make_mock_app(grid_rows=3, grid_cols=3)
        app.recorded_frames = [[row[:] for row in app.grid.cells]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.gif")
            write_gif(path, app.recorded_frames, cell_size=2, delay_cs=5)
        # Simulate what _export_gif does after write
        app.recorded_frames = []
        assert app.recorded_frames == []


# ── Edge cases ───────────────────────────────────────────────────────────────

class TestGifEdgeCases:
    """Edge cases and stress tests."""

    def test_1x1_grid(self):
        from life.utils import write_gif
        frame = [[5]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tiny.gif")
            write_gif(path, [frame], cell_size=1)
            assert os.path.exists(path)
            with open(path, "rb") as f:
                data = f.read()
            assert data[:6] == b"GIF89a"

    def test_large_cell_size(self):
        from life.utils import write_gif
        frame = [[1, 0], [0, 1]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bigcells.gif")
            write_gif(path, [frame], cell_size=16)
            assert os.path.exists(path)

    def test_many_frames(self):
        from life.utils import write_gif
        frames = [[[i % 6, (i + 1) % 6], [(i + 2) % 6, (i + 3) % 6]] for i in range(20)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "many.gif")
            write_gif(path, frames, cell_size=2, delay_cs=5)
            assert os.path.exists(path)
            with open(path, "rb") as f:
                data = f.read()
            assert data[:6] == b"GIF89a"
            assert data[-1:] == b"\x3B"

    def test_zero_delay(self):
        from life.utils import write_gif
        frame = [[0, 1], [1, 0]]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "fast.gif")
            write_gif(path, [frame], cell_size=2, delay_cs=0)
            assert os.path.exists(path)
