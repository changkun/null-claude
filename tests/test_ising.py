"""Tests for Ising Model mode — physics, initialization, and key handling."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.ising import register


class TestIsingInit:
    """Tests for grid initialization and preset handling."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._ising_init(0)
        assert self.app.ising_mode is True
        assert self.app.ising_generation == 0
        assert len(self.app.ising_grid) > 0
        assert self.app.ising_steps_per_frame == 1
        assert hasattr(self.app, 'ising_magnetization')
        assert hasattr(self.app, 'ising_energy')

    def test_all_presets_init(self):
        """Every preset should initialize without error."""
        for i in range(len(self.app.ISING_PRESETS)):
            self.app._ising_init(i)
            assert self.app.ising_mode is True
            assert self.app.ising_generation == 0
            rows = self.app.ising_rows
            cols = self.app.ising_cols
            assert len(self.app.ising_grid) == rows
            assert all(len(row) == cols for row in self.app.ising_grid)

    def test_all_up_magnetization(self):
        """'all_up' init should give magnetization = +1.0."""
        # Find a preset with all_up init or use direct init
        self.app._ising_init(7)  # "All Up + Heat"
        assert self.app.ising_magnetization == pytest.approx(1.0)

    def test_all_down_grid(self):
        """'all_down' style should produce all -1 spins."""
        # Temporarily inject an all_down preset
        original = self.app.ISING_PRESETS
        type(self.app).ISING_PRESETS = [("Test Down", "test", 1.0, 0.0, "all_down")]
        self.app._ising_init(0)
        assert self.app.ising_magnetization == pytest.approx(-1.0)
        for row in self.app.ising_grid:
            assert all(s == -1 for s in row)
        type(self.app).ISING_PRESETS = original

    def test_half_init_domain_wall(self):
        """'half' init should have left half up (+1), right half down (-1)."""
        self.app._ising_init(6)  # "Domain Wall" preset uses half
        cols = self.app.ising_cols
        grid = self.app.ising_grid
        for row in grid:
            for c in range(cols // 2):
                assert row[c] == 1, f"Left half should be +1 at col {c}"
            for c in range(cols // 2, cols):
                assert row[c] == -1, f"Right half should be -1 at col {c}"

    def test_random_init_has_both_spins(self):
        """Random init should have both +1 and -1 spins (overwhelmingly likely)."""
        random.seed(42)
        self.app._ising_init(0)  # "Critical Point" uses random
        flat = [s for row in self.app.ising_grid for s in row]
        assert 1 in flat
        assert -1 in flat

    def test_grid_dimensions_match(self):
        """Grid dimensions should match ising_rows and ising_cols."""
        self.app._ising_init(0)
        assert len(self.app.ising_grid) == self.app.ising_rows
        assert len(self.app.ising_grid[0]) == self.app.ising_cols

    def test_exit_cleanup(self):
        self.app._ising_init(0)
        assert self.app.ising_mode is True
        self.app._exit_ising_mode()
        assert self.app.ising_mode is False
        assert self.app.ising_running is False
        assert self.app.ising_grid == []


class TestIsingEnergy:
    """Tests for energy and magnetization computation."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def _make_uniform_grid(self, spin, rows=10, cols=10, temp=2.0, h=0.0):
        """Helper to set up a uniform spin grid."""
        self.app.ising_rows = rows
        self.app.ising_cols = cols
        self.app.ising_temperature = temp
        self.app.ising_ext_field = h
        self.app.ising_grid = [[spin] * cols for _ in range(rows)]
        self.app.ising_generation = 0
        self.app.ising_mode = True
        self.app.ising_preset_name = "test"
        self.app.ising_steps_per_frame = 1
        self.app.ising_running = False
        self.app.ising_menu = False

    def test_all_up_energy_no_field(self):
        """All spins +1, h=0: E/N should be -2.0 (2D square lattice ground state).

        Each spin has 4 neighbors, all +1. Interaction energy per pair = -1.
        Counting right+down only: 2 pairs per site, so E/N = -2*1 = -2.0.
        """
        self._make_uniform_grid(1)
        self.app._ising_compute_stats()
        assert self.app.ising_energy == pytest.approx(-2.0)
        assert self.app.ising_magnetization == pytest.approx(1.0)

    def test_all_down_energy_no_field(self):
        """All spins -1, h=0: E/N should also be -2.0 (symmetric)."""
        self._make_uniform_grid(-1)
        self.app._ising_compute_stats()
        assert self.app.ising_energy == pytest.approx(-2.0)
        assert self.app.ising_magnetization == pytest.approx(-1.0)

    def test_all_up_energy_with_field(self):
        """All +1 with h=1.0: E/N = -2.0 (interaction) + -1.0 (field) = -3.0."""
        self._make_uniform_grid(1, h=1.0)
        self.app._ising_compute_stats()
        assert self.app.ising_energy == pytest.approx(-3.0)

    def test_all_down_energy_with_field(self):
        """All -1 with h=1.0: E/N = -2.0 (interaction) + 1.0 (field) = -1.0."""
        self._make_uniform_grid(-1, h=1.0)
        self.app._ising_compute_stats()
        assert self.app.ising_energy == pytest.approx(-1.0)

    def test_checkerboard_energy(self):
        """Checkerboard pattern (antiferromagnetic): E/N = +2.0.

        Every neighbor is opposite spin, so each pair contributes +1.
        2 pairs per site -> E/N = +2.0.
        """
        rows, cols = 10, 10
        self.app.ising_rows = rows
        self.app.ising_cols = cols
        self.app.ising_temperature = 2.0
        self.app.ising_ext_field = 0.0
        self.app.ising_grid = [
            [1 if (r + c) % 2 == 0 else -1 for c in range(cols)]
            for r in range(rows)
        ]
        self.app._ising_compute_stats()
        assert self.app.ising_energy == pytest.approx(2.0)
        # Checkerboard has zero net magnetization (equal +1 and -1)
        assert self.app.ising_magnetization == pytest.approx(0.0)

    def test_2x2_manual_energy(self):
        """Manually verify energy for a small 2x2 grid with periodic boundaries.

        Grid:  +1  -1
               -1  +1

        With periodic BC, each site has 4 neighbors.
        Right+down pairs for (0,0): right=(0,1)=-1, down=(1,0)=-1
        Right+down pairs for (0,1): right=(0,0)=+1, down=(1,1)=+1
        Right+down pairs for (1,0): right=(1,1)=+1, down=(0,0)=+1
        Right+down pairs for (1,1): right=(1,0)=-1, down=(0,1)=-1

        Interactions: -s*(sr+sd)
        (0,0): -1*(-1+-1) = 2
        (0,1): -(-1)*(1+1) = 2
        (1,0): -(-1)*(1+1) = 2
        (1,1): -(1)*(-1+-1) = 2
        Total = 8, N=4, E/N = 2.0
        """
        self.app.ising_rows = 2
        self.app.ising_cols = 2
        self.app.ising_temperature = 1.0
        self.app.ising_ext_field = 0.0
        self.app.ising_grid = [[1, -1], [-1, 1]]
        self.app._ising_compute_stats()
        assert self.app.ising_energy == pytest.approx(2.0)
        assert self.app.ising_magnetization == pytest.approx(0.0)

    def test_2x2_uniform_energy(self):
        """2x2 all +1 with periodic BC: E/N = -2.0."""
        self.app.ising_rows = 2
        self.app.ising_cols = 2
        self.app.ising_temperature = 1.0
        self.app.ising_ext_field = 0.0
        self.app.ising_grid = [[1, 1], [1, 1]]
        self.app._ising_compute_stats()
        assert self.app.ising_energy == pytest.approx(-2.0)


class TestIsingMetropolis:
    """Tests for the Metropolis single-spin-flip algorithm."""

    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))

    def _make_uniform_grid(self, spin, rows=10, cols=10, temp=2.0, h=0.0):
        self.app.ising_rows = rows
        self.app.ising_cols = cols
        self.app.ising_temperature = temp
        self.app.ising_ext_field = h
        self.app.ising_grid = [[spin] * cols for _ in range(rows)]
        self.app.ising_generation = 0
        self.app.ising_mode = True
        self.app.ising_preset_name = "test"
        self.app.ising_steps_per_frame = 1
        self.app.ising_running = False
        self.app.ising_menu = False

    def test_step_increments_generation(self):
        random.seed(42)
        self.app._ising_init(0)
        self.app._ising_step()
        assert self.app.ising_generation == 1
        self.app._ising_step()
        assert self.app.ising_generation == 2

    def test_multiple_steps_no_crash(self):
        random.seed(42)
        self.app._ising_init(0)
        for _ in range(10):
            self.app._ising_step()
        assert self.app.ising_generation == 10

    def test_spins_remain_valid(self):
        """After many steps, all spins should still be +1 or -1."""
        random.seed(42)
        self.app._ising_init(0)
        for _ in range(20):
            self.app._ising_step()
        for row in self.app.ising_grid:
            for s in row:
                assert s in (1, -1), f"Invalid spin value: {s}"

    def test_ground_state_stable_at_low_temp(self):
        """At very low temperature, a uniform ground state should remain mostly stable.

        At T=0.01, flipping a spin in an all-up state costs dE=8 (4 aligned neighbors).
        Acceptance probability = exp(-8/0.01) ~ exp(-800) ~ 0, so almost no flips.
        """
        random.seed(42)
        self._make_uniform_grid(1, rows=10, cols=10, temp=0.01)
        self.app._ising_compute_stats()
        self.app._ising_step()
        # At T=0.01, almost no spins should have flipped
        up_count = sum(s for row in self.app.ising_grid for s in row if s == 1)
        total = self.app.ising_rows * self.app.ising_cols
        assert up_count / total > 0.95, "Ground state should be very stable at low T"

    def test_high_temp_decorrelates(self):
        """At very high temperature, magnetization should approach zero.

        At T=100, exp(-dE/T) ~ 1 for all dE, so flips are nearly always accepted,
        producing a random configuration with m ~ 0.
        """
        random.seed(42)
        self._make_uniform_grid(1, rows=20, cols=20, temp=100.0)
        # Run many sweeps to decorrelate
        for _ in range(50):
            self.app._ising_step()
        assert abs(self.app.ising_magnetization) < 0.3, \
            f"High T should give ~0 magnetization, got {self.app.ising_magnetization}"

    def test_metropolis_dE_formula(self):
        """Verify the dE = 2*s*(neighbors_sum + h) formula on a known configuration.

        Place a single spin-down in an all-up grid. For that spin:
        - s = -1, neighbors_sum = 4 (all +1), h = 0
        - dE = 2*(-1)*(4 + 0) = -8 (favorable flip, always accepted)
        After one targeted flip attempt, the spin should flip to +1.
        """
        random.seed(42)
        self._make_uniform_grid(1, rows=5, cols=5, temp=1.0, h=0.0)
        # Place one defect
        self.app.ising_grid[2][2] = -1
        self.app._ising_compute_stats()
        energy_before = self.app.ising_energy

        # The defect raises energy; after enough sweeps it should heal at low T
        self._make_uniform_grid(1, rows=5, cols=5, temp=0.01, h=0.0)
        self.app.ising_grid[2][2] = -1
        for _ in range(5):
            self.app._ising_step()
        # At very low temp, the defect should heal back to all-up
        up_count = sum(1 for row in self.app.ising_grid for s in row if s == 1)
        assert up_count == 25, "Defect should heal at very low temperature"

    def test_external_field_biases_alignment(self):
        """A strong external field should bias spins toward alignment with it.

        Start from random, high T with strong field h=2.0.
        After many sweeps, magnetization should be positive (aligned with field).
        """
        random.seed(42)
        self._make_uniform_grid(-1, rows=15, cols=15, temp=2.0, h=2.0)
        for _ in range(100):
            self.app._ising_step()
        assert self.app.ising_magnetization > 0.0, \
            f"Strong positive field should produce positive magnetization, got {self.app.ising_magnetization}"

    def test_energy_decreases_on_quench(self):
        """Quenching from random to low T should decrease energy over time."""
        random.seed(42)
        self.app._ising_init(4)  # "Quench to Cold" (T=0.1, random init)
        initial_energy = self.app.ising_energy
        for _ in range(20):
            self.app._ising_step()
        final_energy = self.app.ising_energy
        assert final_energy <= initial_energy, \
            f"Energy should decrease on quench: {initial_energy} -> {final_energy}"

    def test_stats_updated_after_step(self):
        """After each step, magnetization and energy should be recomputed."""
        random.seed(42)
        self.app._ising_init(0)
        self.app._ising_step()
        # Manually recompute and compare
        mag_after_step = self.app.ising_magnetization
        eng_after_step = self.app.ising_energy
        self.app._ising_compute_stats()
        assert self.app.ising_magnetization == pytest.approx(mag_after_step)
        assert self.app.ising_energy == pytest.approx(eng_after_step)


class TestIsingKeyHandling:
    """Tests for keyboard input handling."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))
        self.app._ising_init(0)

    def test_space_toggles_running(self):
        assert self.app.ising_running is False
        self.app._handle_ising_key(ord(" "))
        assert self.app.ising_running is True
        self.app._handle_ising_key(ord(" "))
        assert self.app.ising_running is False

    def test_n_single_step(self):
        gen_before = self.app.ising_generation
        self.app._handle_ising_key(ord("n"))
        assert self.app.ising_generation == gen_before + 1

    def test_dot_single_step(self):
        gen_before = self.app.ising_generation
        self.app._handle_ising_key(ord("."))
        assert self.app.ising_generation == gen_before + 1

    def test_temperature_decrease(self):
        t_before = self.app.ising_temperature
        self.app._handle_ising_key(ord("t"))
        assert self.app.ising_temperature == pytest.approx(t_before - 0.1)

    def test_temperature_increase(self):
        t_before = self.app.ising_temperature
        self.app._handle_ising_key(ord("T"))
        assert self.app.ising_temperature == pytest.approx(t_before + 0.1)

    def test_temperature_lower_bound(self):
        """Temperature should not go below 0.01."""
        self.app.ising_temperature = 0.05
        self.app._handle_ising_key(ord("t"))
        assert self.app.ising_temperature >= 0.01

    def test_temperature_upper_bound(self):
        """Temperature should not exceed 10.0."""
        self.app.ising_temperature = 9.95
        self.app._handle_ising_key(ord("T"))
        assert self.app.ising_temperature <= 10.0

    def test_field_decrease(self):
        h_before = self.app.ising_ext_field
        self.app._handle_ising_key(ord("f"))
        assert self.app.ising_ext_field == pytest.approx(h_before - 0.1)

    def test_field_increase(self):
        h_before = self.app.ising_ext_field
        self.app._handle_ising_key(ord("F"))
        assert self.app.ising_ext_field == pytest.approx(h_before + 0.1)

    def test_field_lower_bound(self):
        self.app.ising_ext_field = -1.95
        self.app._handle_ising_key(ord("f"))
        assert self.app.ising_ext_field >= -2.0

    def test_field_upper_bound(self):
        self.app.ising_ext_field = 1.95
        self.app._handle_ising_key(ord("F"))
        assert self.app.ising_ext_field <= 2.0

    def test_speed_increase(self):
        assert self.app.ising_steps_per_frame == 1
        self.app._handle_ising_key(ord("+"))
        assert self.app.ising_steps_per_frame == 2
        self.app._handle_ising_key(ord("="))
        assert self.app.ising_steps_per_frame == 3

    def test_speed_decrease(self):
        self.app.ising_steps_per_frame = 3
        self.app._handle_ising_key(ord("-"))
        assert self.app.ising_steps_per_frame == 2
        self.app._handle_ising_key(ord("_"))
        assert self.app.ising_steps_per_frame == 1

    def test_speed_lower_bound(self):
        self.app.ising_steps_per_frame = 1
        self.app._handle_ising_key(ord("-"))
        assert self.app.ising_steps_per_frame == 1

    def test_speed_upper_bound(self):
        self.app.ising_steps_per_frame = 50
        self.app._handle_ising_key(ord("+"))
        assert self.app.ising_steps_per_frame == 50

    def test_q_exits(self):
        self.app._handle_ising_key(ord("q"))
        assert self.app.ising_mode is False

    def test_r_resets(self):
        self.app._ising_step()
        self.app._ising_step()
        assert self.app.ising_generation == 2
        self.app._handle_ising_key(ord("r"))
        assert self.app.ising_generation == 0

    def test_R_returns_to_menu(self):
        self.app._handle_ising_key(ord("R"))
        assert self.app.ising_mode is False
        assert self.app.ising_menu is True

    def test_m_returns_to_menu(self):
        self.app._handle_ising_key(ord("m"))
        assert self.app.ising_mode is False
        assert self.app.ising_menu is True


class TestIsingMenuKey:
    """Tests for preset menu key handling."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))
        self.app._enter_ising_mode()

    def test_j_navigates_down(self):
        assert self.app.ising_menu_sel == 0
        self.app._handle_ising_menu_key(ord("j"))
        assert self.app.ising_menu_sel == 1

    def test_k_navigates_up_wraps(self):
        assert self.app.ising_menu_sel == 0
        self.app._handle_ising_menu_key(ord("k"))
        assert self.app.ising_menu_sel == len(self.app.ISING_PRESETS) - 1

    def test_enter_selects_preset(self):
        self.app._handle_ising_menu_key(10)  # Enter key
        assert self.app.ising_mode is True
        assert self.app.ising_menu is False

    def test_q_cancels_menu(self):
        self.app._handle_ising_menu_key(ord("q"))
        assert self.app.ising_menu is False
