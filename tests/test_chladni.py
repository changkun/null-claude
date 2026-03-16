"""Tests for chladni mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.chladni import register


CHLADNI_PRESETS = [
    ("Mode (2,3)", "Classic Chladni figure m=2 n=3", "2_3"),
    ("Mode (1,1)", "Fundamental mode m=1 n=1", "1_1"),
    ("Mode (3,5)", "Higher mode m=3 n=5", "3_5"),
    ("Sweep", "Frequency sweep through modes", "sweep"),
]


class TestChladni:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        cls.CHLADNI_PRESETS = CHLADNI_PRESETS
        self.app.chladni_menu_sel = 0
        register(cls)

    def test_enter(self):
        self.app._enter_chladni_mode()
        assert self.app.chladni_menu is True
        assert self.app.chladni_menu_sel == 0

    def test_step_no_crash(self):
        self.app.chladni_mode = True
        self.app.chladni_running = False
        self.app._chladni_init(0)
        for _ in range(10):
            self.app._chladni_step()
        assert self.app.chladni_generation == 10

    def test_exit_cleanup(self):
        self.app.chladni_mode = True
        self.app._chladni_init(0)
        self.app._exit_chladni_mode()
        assert self.app.chladni_mode is False
        assert self.app.chladni_menu is False
        assert self.app.chladni_running is False
        assert self.app.chladni_plate == []

    # ── Init tests for all presets ──

    @pytest.mark.parametrize("idx", range(len(CHLADNI_PRESETS)))
    def test_init_all_presets(self, idx):
        """Every preset should initialize without error."""
        random.seed(42)
        self.app.chladni_menu_sel = idx
        self.app._chladni_init(idx)
        assert self.app.chladni_mode is True
        assert self.app.chladni_menu is False
        assert self.app.chladni_generation == 0
        assert len(self.app.chladni_plate) == self.app.chladni_rows
        assert len(self.app.chladni_plate[0]) == self.app.chladni_cols
        assert len(self.app.chladni_velocity) == self.app.chladni_rows
        assert len(self.app.chladni_sand) == self.app.chladni_rows

    # ── Mode number parsing ──

    def test_mode_numbers_parsed_correctly(self):
        """Preset '2_3' should set m=2, n=3."""
        self.app._chladni_init(0)  # "2_3"
        assert self.app.chladni_m == 2
        assert self.app.chladni_n == 3

    def test_mode_frequency_from_mode_numbers(self):
        """Frequency should be sqrt(m^2 + n^2) * 0.3."""
        self.app._chladni_init(0)  # m=2, n=3
        expected_freq = math.sqrt(4 + 9) * 0.3
        assert abs(self.app.chladni_freq - expected_freq) < 1e-10

    def test_sweep_preset_initial_values(self):
        """Sweep preset should start with m=1, n=2, freq=0.5."""
        self.app.chladni_menu_sel = 3
        self.app._chladni_init(3)  # sweep
        assert self.app.chladni_m == 1
        assert self.app.chladni_n == 2
        assert self.app.chladni_freq == 0.5

    # ── Biharmonic plate physics ──

    def test_boundary_conditions_clamped_edges(self):
        """After stepping, the 2-cell boundary should remain zero (clamped plate)."""
        self.app._chladni_init(0)
        for _ in range(10):
            self.app._chladni_step()
        plate = self.app.chladni_plate
        rows = self.app.chladni_rows
        cols = self.app.chladni_cols
        # Check clamped edges (rows 0,1 and rows-1,rows-2)
        for c in range(cols):
            assert plate[0][c] == 0.0, "Row 0 must be clamped"
            assert plate[1][c] == 0.0, "Row 1 must be clamped"
            assert plate[rows - 1][c] == 0.0, "Last row must be clamped"
            assert plate[rows - 2][c] == 0.0, "Second-last row must be clamped"
        # Check clamped edges (cols 0,1 and cols-1,cols-2)
        for r in range(rows):
            assert plate[r][0] == 0.0, "Col 0 must be clamped"
            assert plate[r][1] == 0.0, "Col 1 must be clamped"
            assert plate[r][cols - 1] == 0.0, "Last col must be clamped"
            assert plate[r][cols - 2] == 0.0, "Second-last col must be clamped"

    def test_displacement_clamped_within_range(self):
        """Plate displacement should be clamped to [-2.0, 2.0]."""
        self.app._chladni_init(0)
        for _ in range(30):
            self.app._chladni_step()
        max_disp = 2.0
        for r in range(self.app.chladni_rows):
            for c in range(self.app.chladni_cols):
                assert -max_disp <= self.app.chladni_plate[r][c] <= max_disp

    def test_driving_force_at_center(self):
        """After a step, the center of the plate should be excited."""
        self.app._chladni_init(0)
        # Set plate and velocity to zero everywhere
        rows = self.app.chladni_rows
        cols = self.app.chladni_cols
        for r in range(rows):
            for c in range(cols):
                self.app.chladni_plate[r][c] = 0.0
                self.app.chladni_velocity[r][c] = 0.0
        self.app.chladni_time = 0.0
        self.app._chladni_step()
        cr = rows // 2
        cc = cols // 2
        # The center should have non-zero velocity after driving
        # (unless sin(0) happens to be 0 at time=dt, which it won't be for most dt)
        # After one step, at least the velocity at center should be modified
        # The driving force is A * sin(2*pi*freq*time)
        # After one step, time=dt, drive = A * sin(2*pi*freq*dt) which is nonzero
        assert self.app.chladni_velocity[cr][cc] != 0.0 or self.app.chladni_plate[cr][cc] != 0.0

    # ── Sand migration ──

    def test_sand_initially_uniform(self):
        """Sand should start uniformly distributed at 1.0."""
        self.app._chladni_init(0)
        for r in range(self.app.chladni_rows):
            for c in range(self.app.chladni_cols):
                assert self.app.chladni_sand[r][c] == 1.0

    def test_sand_field_dimensions(self):
        """Sand field should match plate dimensions."""
        self.app._chladni_init(0)
        assert len(self.app.chladni_sand) == self.app.chladni_rows
        assert len(self.app.chladni_sand[0]) == self.app.chladni_cols

    def test_sand_changes_after_stepping(self):
        """Sand distribution should change once the plate vibrates."""
        self.app._chladni_init(0)
        for _ in range(20):
            self.app._chladni_step()
        # At least some sand values should differ from 1.0
        changed = False
        for r in range(self.app.chladni_rows):
            for c in range(self.app.chladni_cols):
                if abs(self.app.chladni_sand[r][c] - 1.0) > 1e-10:
                    changed = True
                    break
            if changed:
                break
        assert changed, "Sand should redistribute after plate vibrates"

    # ── Stability ──

    def test_no_nan_or_inf(self):
        """Plate, velocity, and sand should remain finite."""
        self.app._chladni_init(0)
        for _ in range(50):
            self.app._chladni_step()
        for r in range(self.app.chladni_rows):
            for c in range(self.app.chladni_cols):
                assert math.isfinite(self.app.chladni_plate[r][c])
                assert math.isfinite(self.app.chladni_velocity[r][c])
                assert math.isfinite(self.app.chladni_sand[r][c])

    # ── Sweep mode frequency increment ──

    def test_sweep_increases_frequency(self):
        """In sweep mode, frequency should increase each step."""
        self.app.chladni_menu_sel = 3  # sweep
        self.app._chladni_init(3)
        freq_before = self.app.chladni_freq
        self.app._chladni_step()
        assert self.app.chladni_freq > freq_before

    # ── Step increments generation ──

    def test_step_increments_generation(self):
        self.app._chladni_init(0)
        assert self.app.chladni_generation == 0
        self.app._chladni_step()
        assert self.app.chladni_generation == 1

    def test_time_advances(self):
        self.app._chladni_init(0)
        assert self.app.chladni_time == 0.0
        self.app._chladni_step()
        assert self.app.chladni_time > 0.0

    # ── Key handling ──

    def test_handle_menu_key_up_down(self):
        self.app.chladni_menu = True
        self.app.chladni_menu_sel = 0
        import curses
        self.app._handle_chladni_menu_key(curses.KEY_DOWN)
        assert self.app.chladni_menu_sel == 1
        self.app._handle_chladni_menu_key(curses.KEY_UP)
        assert self.app.chladni_menu_sel == 0
        self.app._handle_chladni_menu_key(curses.KEY_UP)
        assert self.app.chladni_menu_sel == len(CHLADNI_PRESETS) - 1

    def test_handle_key_space_toggle(self):
        self.app._chladni_init(0)
        self.app.chladni_running = False
        self.app._handle_chladni_key(ord(" "))
        assert self.app.chladni_running is True
        self.app._handle_chladni_key(ord(" "))
        assert self.app.chladni_running is False

    def test_handle_key_quit(self):
        self.app._chladni_init(0)
        self.app._handle_chladni_key(ord("q"))
        assert self.app.chladni_mode is False

    def test_handle_key_viz_cycle(self):
        self.app._chladni_init(0)
        assert self.app.chladni_viz_mode == 0
        self.app._handle_chladni_key(ord("v"))
        assert self.app.chladni_viz_mode == 1
        self.app._handle_chladni_key(ord("v"))
        assert self.app.chladni_viz_mode == 2
        self.app._handle_chladni_key(ord("v"))
        assert self.app.chladni_viz_mode == 0

    def test_handle_key_mode_m_cycle(self):
        self.app._chladni_init(0)
        m_before = self.app.chladni_m
        self.app._handle_chladni_key(ord("m"))
        assert self.app.chladni_m == (m_before % 9) + 1

    def test_handle_key_mode_n_cycle(self):
        self.app._chladni_init(0)
        n_before = self.app.chladni_n
        self.app._handle_chladni_key(ord("N"))
        assert self.app.chladni_n == (n_before % 9) + 1

    def test_handle_key_frequency_adjust(self):
        self.app._chladni_init(0)
        freq_before = self.app.chladni_freq
        self.app._handle_chladni_key(ord("f"))
        assert self.app.chladni_freq > freq_before
        self.app._handle_chladni_key(ord("F"))
        # Should be back close to original
        assert abs(self.app.chladni_freq - freq_before) < 0.1

    def test_handle_key_damping_adjust(self):
        self.app._chladni_init(0)
        d_before = self.app.chladni_damping
        self.app._handle_chladni_key(ord("d"))
        assert self.app.chladni_damping > d_before

    def test_handle_key_amplitude_adjust(self):
        self.app._chladni_init(0)
        amp_before = self.app.chladni_drive_amp
        self.app._handle_chladni_key(ord("+"))
        assert self.app.chladni_drive_amp > amp_before

    def test_handle_key_sand_redistribute(self):
        self.app._chladni_init(0)
        for _ in range(10):
            self.app._chladni_step()
        self.app._handle_chladni_key(ord("s"))
        for r in range(self.app.chladni_rows):
            for c in range(self.app.chladni_cols):
                assert self.app.chladni_sand[r][c] == 1.0

    def test_handle_key_reset(self):
        self.app.chladni_menu_sel = 0
        self.app._chladni_init(0)
        for _ in range(5):
            self.app._chladni_step()
        self.app._handle_chladni_key(ord("r"))
        assert self.app.chladni_generation == 0

    def test_handle_key_menu_return(self):
        self.app._chladni_init(0)
        self.app._handle_chladni_key(ord("R"))
        assert self.app.chladni_menu is True
        assert self.app.chladni_mode is False

    def test_handle_key_speed_adjust(self):
        self.app._chladni_init(0)
        spf = self.app.chladni_steps_per_frame
        self.app._handle_chladni_key(ord(">"))
        assert self.app.chladni_steps_per_frame == spf + 1
        self.app._handle_chladni_key(ord("<"))
        assert self.app.chladni_steps_per_frame == spf
