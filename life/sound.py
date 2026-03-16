"""Sound engine for procedural audio synthesis."""
import math
import os
import struct
import subprocess
import tempfile
import threading
import time
import wave

# Pentatonic scale intervals (semitones from root): C D E G A
_PENTATONIC = [0, 2, 4, 7, 9]


def _row_to_freq(row: int, total_rows: int, base_freq: float = 220.0) -> float:
    """Map a grid row to a frequency using a pentatonic scale.

    Row 0 (top) is the highest pitch, row (total_rows-1) is the lowest.
    The mapping wraps through multiple octaves of the pentatonic scale.
    """
    # Invert so top rows are high-pitched
    idx = total_rows - 1 - row
    octave, degree = divmod(idx, len(_PENTATONIC))
    semitones = octave * 12 + _PENTATONIC[degree]
    return base_freq * (2.0 ** (semitones / 12.0))


class SoundEngine:
    """Procedural audio synthesizer that turns grid state into music.

    Generates WAV audio in a background thread, playing through an external
    process (aplay/paplay/afplay) or writing to /dev/dsp if available.
    Stays pure-Python with no external library dependencies.
    """

    SAMPLE_RATE = 22050
    MAX_POLYPHONY = 12  # limit simultaneous tones to keep output pleasant

    def __init__(self):
        self.enabled = False
        self._lock = threading.Lock()
        self._play_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Detect playback method
        self._play_cmd = self._detect_player()

    @staticmethod
    def _detect_player() -> list[str] | None:
        """Find an available audio playback command."""
        import shutil
        for cmd, args in [
            ("paplay", ["paplay", "--raw", "--rate=22050", "--channels=1",
                         "--format=s16le"]),
            ("aplay", ["aplay", "-q", "-f", "S16_LE", "-r", "22050", "-c", "1"]),
            ("afplay", None),  # macOS — needs a file, handled separately
        ]:
            if shutil.which(cmd):
                return args
        return None

    def toggle(self) -> bool:
        """Toggle sound on/off. Returns new state."""
        self.enabled = not self.enabled
        if not self.enabled:
            self._stop_event.set()
        return self.enabled

    def play_grid(self, grid, speed_delay: float):
        """Generate and play a short audio chunk representing the current grid.

        Called each generation. The duration matches the simulation tempo so
        the music stays synced with the visual.
        """
        if not self.enabled or self._play_cmd is None:
            return

        # Don't stack up threads if playback is still going
        if self._play_thread and self._play_thread.is_alive():
            return

        # Collect active rows (any column) and per-column densities
        rows = grid.rows
        cols = grid.cols
        cells = grid.cells

        # Find which rows have living cells and column population counts
        active_rows: list[int] = []
        col_counts = [0] * cols
        for r in range(rows):
            row_alive = False
            for c in range(cols):
                if cells[r][c] > 0:
                    row_alive = True
                    col_counts[c] += 1
            if row_alive:
                active_rows.append(r)

        if not active_rows:
            return

        # Limit polyphony — pick evenly-spaced rows
        if len(active_rows) > self.MAX_POLYPHONY:
            step = len(active_rows) / self.MAX_POLYPHONY
            active_rows = [active_rows[int(i * step)] for i in range(self.MAX_POLYPHONY)]

        # Overall volume from mean population density
        total_alive = grid.population
        density = min(total_alive / (rows * cols), 1.0) if rows * cols > 0 else 0
        master_vol = 0.15 + 0.85 * density  # range [0.15, 1.0]

        # Duration synced to simulation speed (at least 50ms, at most 2s)
        duration = max(0.05, min(speed_delay * 0.8, 2.0))

        freqs = [_row_to_freq(r, rows) for r in active_rows]
        samples = self._synthesize(freqs, duration, master_vol)

        self._stop_event.clear()
        self._play_thread = threading.Thread(
            target=self._play_samples, args=(samples,), daemon=True
        )
        self._play_thread.start()

    def _synthesize(self, freqs: list[float], duration: float, volume: float) -> bytes:
        """Generate mixed sine-wave PCM samples (S16LE mono)."""
        n_samples = int(self.SAMPLE_RATE * duration)
        if not freqs:
            return b"\x00\x00" * n_samples

        amp = volume / len(freqs)  # per-voice amplitude
        max_amp = 28000  # stay below S16 clipping

        buf = bytearray(n_samples * 2)
        # Pre-compute phase increments
        increments = [2.0 * math.pi * f / self.SAMPLE_RATE for f in freqs]

        # Soft attack/release envelope (avoid clicks): 5ms ramp
        ramp_samples = min(int(0.005 * self.SAMPLE_RATE), n_samples // 2)

        for i in range(n_samples):
            # Envelope
            if i < ramp_samples:
                env = i / ramp_samples
            elif i > n_samples - ramp_samples:
                env = (n_samples - i) / ramp_samples
            else:
                env = 1.0

            val = 0.0
            for inc in increments:
                val += math.sin(inc * i)
            val = val * amp * max_amp * env
            sample = max(-32767, min(32767, int(val)))
            struct.pack_into("<h", buf, i * 2, sample)
        return bytes(buf)

    def play_ping(self, freq: float = 880.0, duration: float = 0.08):
        """Play a short notification ping (for phase transition alerts)."""
        if not self.enabled or self._play_cmd is None:
            return
        if self._play_thread and self._play_thread.is_alive():
            return
        samples = self._synthesize([freq], duration, 0.5)
        self._stop_event.clear()
        self._play_thread = threading.Thread(
            target=self._play_samples, args=(samples,), daemon=True
        )
        self._play_thread.start()

    def _play_samples(self, samples: bytes):
        """Play raw PCM samples via detected player (runs in thread)."""
        import subprocess
        if not self._play_cmd:
            return
        try:
            if self._play_cmd[0] == "afplay":
                # macOS afplay needs a WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                    with wave.open(tmp.name, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(self.SAMPLE_RATE)
                        wf.writeframes(samples)
                    subprocess.run(["afplay", tmp.name],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   timeout=5)
            else:
                proc = subprocess.Popen(
                    self._play_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                proc.communicate(input=samples, timeout=5)
        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass


# ── Multiplayer networking ───────────────────────────────────────────────────

MP_DEFAULT_PORT = 7654
MP_PLANNING_TIME = 30  # seconds for planning phase
MP_SIM_GENS = 200  # generations per round


