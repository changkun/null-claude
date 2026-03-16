"""Tests for sir_epidemic mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.sir_epidemic import register, SIR_PRESETS, SIR_CHARS
from life.constants import SPEEDS


class TestSIREpidemic:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        # Instance attrs
        self.app.sir_mode = False
        self.app.sir_menu = False
        self.app.sir_menu_sel = 0
        self.app.sir_running = False
        self.app.sir_grid = []
        self.app.sir_infection_timer = []
        self.app.sir_counts = []
        self.app.sir_steps_per_frame = 1

    def test_enter(self):
        self.app._enter_sir_mode()
        assert self.app.sir_menu is True

    def test_init(self):
        self.app.sir_mode = True
        self.app._sir_init(0)  # Seasonal Flu
        assert self.app.sir_mode is True
        assert len(self.app.sir_grid) > 0
        assert len(self.app.sir_counts) == 1  # initial recording

    def test_step_no_crash(self):
        self.app.sir_mode = True
        self.app._sir_init(0)
        for _ in range(10):
            self.app._sir_step()
        assert self.app.sir_generation == 10
        assert len(self.app.sir_counts) == 11  # 1 initial + 10 steps

    def test_all_presets(self):
        """Ensure all presets initialize without error."""
        for i in range(len(SIR_PRESETS)):
            random.seed(42)
            self.app._sir_init(i)
            assert self.app.sir_mode is True
            self.app._sir_step()

    def test_exit_cleanup(self):
        self.app.sir_mode = True
        self.app._sir_init(0)
        self.app._exit_sir_mode()
        assert self.app.sir_mode is False

    # ── Registration tests ──────────────────────────────────────────

    def test_register_sets_sir_presets_on_class(self):
        """register() must set SIR_PRESETS on the App class."""
        cls = type(self.app)
        assert hasattr(cls, "SIR_PRESETS")
        assert cls.SIR_PRESETS is SIR_PRESETS

    def test_sir_chars_defined(self):
        """SIR_CHARS must map all four states."""
        assert set(SIR_CHARS.keys()) == {0, 1, 2, 3}

    # ── Grid initialization logic ───────────────────────────────────

    def test_init_grid_dimensions(self):
        """Grid dimensions should be derived from terminal size."""
        self.app._sir_init(0)
        rows, cols = self.app.sir_rows, self.app.sir_cols
        assert len(self.app.sir_grid) == rows
        assert len(self.app.sir_grid[0]) == cols
        assert len(self.app.sir_infection_timer) == rows
        assert len(self.app.sir_infection_timer[0]) == cols

    def test_init_has_susceptible_and_infected(self):
        """After init, the grid must contain both S (0) and I (1) cells."""
        random.seed(42)
        self.app._sir_init(0)  # Seasonal Flu: density=1.0, n_infected=3
        flat = [cell for row in self.app.sir_grid for cell in row]
        assert 0 in flat, "No susceptible cells found"
        assert 1 in flat, "No infected cells found"

    def test_init_correct_infected_count(self):
        """Number of initially infected cells should match preset."""
        random.seed(42)
        # Seasonal Flu: density=1.0, n_infected=3
        self.app._sir_init(0)
        infected_count = sum(
            1 for row in self.app.sir_grid for cell in row if cell == 1
        )
        assert infected_count == 3

    def test_init_sparse_density(self):
        """Sparse Rural preset (density=0.3) should have fewer populated cells."""
        random.seed(42)
        # Preset 5: Sparse Rural, density=0.3
        self.app._sir_init(5)
        total_cells = self.app.sir_rows * self.app.sir_cols
        populated = sum(
            1 for row in self.app.sir_grid for cell in row if cell >= 0
        )
        # With density=0.3, expect roughly 30% populated (allow wide margin)
        ratio = populated / total_cells
        assert 0.15 < ratio < 0.45, f"Population ratio {ratio:.2f} outside expected range for density=0.3"

    def test_init_full_density(self):
        """Full density (1.0) should fill every cell."""
        random.seed(42)
        self.app._sir_init(0)  # Seasonal Flu: density=1.0
        total_cells = self.app.sir_rows * self.app.sir_cols
        populated = sum(
            1 for row in self.app.sir_grid for cell in row if cell >= 0
        )
        assert populated == total_cells

    def test_init_infection_timers_set(self):
        """Infected cells should have their timers set to recovery time."""
        random.seed(42)
        self.app._sir_init(0)  # recovery=25
        recovery = 25
        for r in range(self.app.sir_rows):
            for c in range(self.app.sir_cols):
                if self.app.sir_grid[r][c] == 1:
                    assert self.app.sir_infection_timer[r][c] == recovery

    # ── State transition logic ──────────────────────────────────────

    def test_states_are_valid(self):
        """All grid cells must be in {-1, 0, 1, 2, 3} after stepping."""
        random.seed(42)
        self.app._sir_init(2)  # Deadly Plague (has mortality)
        for _ in range(50):
            self.app._sir_step()
        valid_states = {-1, 0, 1, 2, 3}
        for row in self.app.sir_grid:
            for cell in row:
                assert cell in valid_states, f"Invalid state {cell}"

    def test_susceptible_to_infected_transition(self):
        """S cells near I cells should transition to I over multiple steps."""
        random.seed(0)
        self.app._sir_init(7)  # Fast Burn: high trans, many infected
        initial_s, initial_i, _, _ = self.app.sir_counts[0]
        # Run several steps
        for _ in range(5):
            self.app._sir_step()
        final_s, final_i, _, _ = self.app.sir_counts[-1]
        # Some susceptible should have become infected or recovered
        assert final_s < initial_s, "No S->I transitions happened"

    def test_infected_to_recovered_transition(self):
        """Infected cells should recover after recovery_time steps."""
        random.seed(42)
        # Fast Burn: recovery=8, high infection rate
        self.app._sir_init(7)
        # Run enough steps for recovery to happen (recovery_time = 8)
        for _ in range(15):
            self.app._sir_step()
        _, _, r_count, _ = self.app.sir_counts[-1]
        assert r_count > 0, "No recoveries occurred after sufficient steps"

    def test_mortality_produces_dead_cells(self):
        """Deadly Plague (mortality=0.15) should produce dead cells."""
        random.seed(42)
        # Preset 2: Deadly Plague, mortality=0.15, recovery=40
        self.app._sir_init(2)
        # Run many steps to allow deaths
        for _ in range(60):
            self.app._sir_step()
        _, _, _, d = self.app.sir_counts[-1]
        assert d > 0, "No deaths with 15% mortality after 60 steps"

    def test_zero_mortality_no_deaths(self):
        """Seasonal Flu (mortality=0.0) should never produce dead cells."""
        random.seed(42)
        self.app._sir_init(0)  # mortality=0.0
        for _ in range(40):
            self.app._sir_step()
        for s, i, r, d in self.app.sir_counts:
            assert d == 0, f"Death occurred with zero mortality: d={d}"

    def test_reinfection_converts_recovered_to_susceptible(self):
        """Reinfection Wave preset should convert some R back to S."""
        random.seed(1)
        # Preset 4: Reinfection Wave, reinfection=True
        self.app._sir_init(4)
        # Run enough steps that many recover first
        for _ in range(40):
            self.app._sir_step()
        # Check if there are still susceptible cells (from reinfection)
        # With reinfection prob=0.005 per step per recovered cell,
        # over 40 steps some should have been reinfected
        # We check that after infections + recoveries, there are still S cells
        # (in a no-reinfection scenario with density=0.9, S would trend toward 0)
        any_reinfection = False
        # After enough steps, if reinfection is working, we should see S
        # cells that weren't there initially (some R->S)
        final_s, final_i, final_r, _ = self.app.sir_counts[-1]
        # With reinfection enabled and enough steps, the epidemic can't
        # fully settle because R keeps becoming S again
        # Run more steps to see the effect
        for _ in range(100):
            self.app._sir_step()
        late_s, late_i, late_r, _ = self.app.sir_counts[-1]
        # In a reinfection scenario, susceptible count should not be zero
        # if there are recovered cells that could become S again
        total_active = late_s + late_i + late_r
        if total_active > 0:
            # With reinfection, the epidemic keeps cycling
            assert late_s > 0 or late_i > 0, "Reinfection should prevent full R convergence"

    # ── Population conservation ─────────────────────────────────────

    def test_population_conservation_no_mortality(self):
        """With zero mortality, total population (S+I+R) should be constant."""
        random.seed(42)
        self.app._sir_init(0)  # Seasonal Flu: mortality=0, reinfection=False
        initial_s, initial_i, initial_r, initial_d = self.app.sir_counts[0]
        initial_total = initial_s + initial_i + initial_r + initial_d
        for _ in range(30):
            self.app._sir_step()
        for s, i, r, d in self.app.sir_counts:
            total = s + i + r + d
            assert total == initial_total, (
                f"Population changed: {initial_total} -> {total}"
            )

    def test_population_conservation_with_mortality(self):
        """With mortality, S+I+R+D should remain constant (dead cells stay)."""
        random.seed(42)
        self.app._sir_init(2)  # Deadly Plague: mortality=0.15
        initial_s, initial_i, initial_r, initial_d = self.app.sir_counts[0]
        initial_total = initial_s + initial_i + initial_r + initial_d
        for _ in range(50):
            self.app._sir_step()
        for s, i, r, d in self.app.sir_counts:
            total = s + i + r + d
            assert total == initial_total, (
                f"Total population changed: {initial_total} -> {total}"
            )

    # ── Spatial spreading logic ─────────────────────────────────────

    def test_infection_radius_limits_spread(self):
        """Infection should not jump beyond the configured radius."""
        random.seed(42)
        # Build a minimal grid: single infected cell in center
        self.app.sir_rows = 20
        self.app.sir_cols = 20
        self.app.sir_grid = [[-1] * 20 for _ in range(20)]
        self.app.sir_infection_timer = [[0] * 20 for _ in range(20)]
        self.app.sir_infection_radius = 1.5
        self.app.sir_transmission_prob = 1.0  # guarantee infection
        self.app.sir_recovery_time = 100  # long recovery
        self.app.sir_mortality_rate = 0.0
        self.app.sir_reinfection = False
        self.app.sir_generation = 0
        self.app.sir_counts = []

        # Fill grid with susceptible
        for r in range(20):
            for c in range(20):
                self.app.sir_grid[r][c] = 0

        # Place single infected at center
        self.app.sir_grid[10][10] = 1
        self.app.sir_infection_timer[10][10] = 100

        self.app._sir_record_counts()
        self.app._sir_step()

        # After one step, only cells within radius=1.5 of (10,10) should be infected
        ir = int(math.ceil(1.5))
        for r in range(20):
            for c in range(20):
                if r == 10 and c == 10:
                    continue  # the original infected
                if self.app.sir_grid[r][c] == 1:
                    dist = math.sqrt((r - 10) ** 2 + (c - 10) ** 2)
                    assert dist <= 1.5, (
                        f"Infection spread to ({r},{c}), distance {dist:.2f} > radius 1.5"
                    )

    def test_distance_weighted_probability(self):
        """Closer susceptible cells should have higher infection probability."""
        # This is a statistical test, so we use many trials
        random.seed(42)
        close_infections = 0
        far_infections = 0
        trials = 500

        for _ in range(trials):
            self.app.sir_rows = 10
            self.app.sir_cols = 10
            self.app.sir_grid = [[0] * 10 for _ in range(10)]
            self.app.sir_infection_timer = [[0] * 10 for _ in range(10)]
            self.app.sir_infection_radius = 3.0
            self.app.sir_transmission_prob = 0.5
            self.app.sir_recovery_time = 100
            self.app.sir_mortality_rate = 0.0
            self.app.sir_reinfection = False
            self.app.sir_generation = 0
            self.app.sir_counts = []

            # Clear grid, place one infected at (5,5)
            for r in range(10):
                for c in range(10):
                    self.app.sir_grid[r][c] = -1
            self.app.sir_grid[5][5] = 1
            self.app.sir_infection_timer[5][5] = 100
            # Place susceptible at distance 1 and distance 2
            self.app.sir_grid[5][6] = 0  # dist=1
            self.app.sir_grid[5][8] = 0  # dist=3 (at edge of radius)

            self.app._sir_record_counts()
            self.app._sir_step()

            if self.app.sir_grid[5][6] == 1:
                close_infections += 1
            if self.app.sir_grid[5][8] == 1:
                far_infections += 1

        # Close cells should be infected more often than far cells
        assert close_infections > far_infections, (
            f"Close infections ({close_infections}) should exceed far ({far_infections})"
        )

    # ── Counts recording ────────────────────────────────────────────

    def test_record_counts_accuracy(self):
        """_sir_record_counts should produce accurate tallies."""
        self.app.sir_rows = 3
        self.app.sir_cols = 3
        self.app.sir_grid = [
            [0, 1, 2],
            [3, -1, 0],
            [1, 2, 0],
        ]
        self.app.sir_counts = []
        self.app._sir_record_counts()
        s, i, r, d = self.app.sir_counts[0]
        assert s == 3  # three 0s
        assert i == 2  # two 1s
        assert r == 2  # two 2s
        assert d == 1  # one 3

    def test_counts_history_grows(self):
        """Each step should append one entry to sir_counts."""
        random.seed(42)
        self.app._sir_init(0)
        assert len(self.app.sir_counts) == 1
        for step in range(1, 6):
            self.app._sir_step()
            assert len(self.app.sir_counts) == step + 1

    # ── Epidemic dynamics ───────────────────────────────────────────

    def test_epidemic_eventually_ends_no_reinfection(self):
        """Without reinfection, infected count should reach zero eventually."""
        random.seed(42)
        # Fast Burn: high trans, recovery=8, no reinfection
        self.app._sir_init(7)
        max_steps = 200
        for _ in range(max_steps):
            self.app._sir_step()
            _, i, _, _ = self.app.sir_counts[-1]
            if i == 0:
                break
        _, final_i, _, _ = self.app.sir_counts[-1]
        assert final_i == 0, f"Epidemic did not end after {max_steps} steps, I={final_i}"

    def test_no_infection_without_infected(self):
        """If no cells are infected, no new infections should occur."""
        self.app.sir_rows = 5
        self.app.sir_cols = 5
        self.app.sir_grid = [[0] * 5 for _ in range(5)]  # all susceptible
        self.app.sir_infection_timer = [[0] * 5 for _ in range(5)]
        self.app.sir_infection_radius = 2.0
        self.app.sir_transmission_prob = 1.0
        self.app.sir_recovery_time = 10
        self.app.sir_mortality_rate = 0.0
        self.app.sir_reinfection = False
        self.app.sir_generation = 0
        self.app.sir_counts = []
        self.app._sir_record_counts()
        self.app._sir_step()
        s, i, r, d = self.app.sir_counts[-1]
        assert i == 0, "Infections appeared without any infected cells"
        assert s == 25, "Susceptible count changed without infections"

    def test_dead_cells_never_change(self):
        """Dead cells (state 3) should remain dead forever."""
        random.seed(42)
        self.app._sir_init(2)  # Deadly Plague with mortality
        # Run until some deaths occur
        for _ in range(60):
            self.app._sir_step()

        # Record positions of dead cells
        dead_positions = set()
        for r in range(self.app.sir_rows):
            for c in range(self.app.sir_cols):
                if self.app.sir_grid[r][c] == 3:
                    dead_positions.add((r, c))

        if dead_positions:
            # Run more steps
            for _ in range(20):
                self.app._sir_step()
            # All previously dead cells should still be dead
            for r, c in dead_positions:
                assert self.app.sir_grid[r][c] == 3, (
                    f"Dead cell at ({r},{c}) changed state"
                )

    def test_empty_cells_unaffected(self):
        """Empty cells (-1) should never be infected or changed."""
        random.seed(42)
        self.app.sir_rows = 10
        self.app.sir_cols = 10
        self.app.sir_grid = [[-1] * 10 for _ in range(10)]
        self.app.sir_infection_timer = [[0] * 10 for _ in range(10)]
        self.app.sir_infection_radius = 2.0
        self.app.sir_transmission_prob = 1.0
        self.app.sir_recovery_time = 10
        self.app.sir_mortality_rate = 0.0
        self.app.sir_reinfection = False
        self.app.sir_generation = 0
        self.app.sir_counts = []

        # Place a few susceptible and one infected, leaving empties
        self.app.sir_grid[5][5] = 1
        self.app.sir_infection_timer[5][5] = 10
        self.app.sir_grid[5][6] = 0
        # (5,4) is empty (-1) and adjacent

        self.app._sir_record_counts()
        for _ in range(10):
            self.app._sir_step()

        # Check that empty cells stayed empty
        for r in range(10):
            for c in range(10):
                if (r, c) not in [(5, 5), (5, 6)]:
                    assert self.app.sir_grid[r][c] == -1, (
                        f"Empty cell at ({r},{c}) was modified to {self.app.sir_grid[r][c]}"
                    )

    # ── Key handling ────────────────────────────────────────────────

    def test_handle_sir_key_toggle_running(self):
        """Space should toggle sir_running."""
        self.app._sir_init(0)
        assert self.app.sir_running is False
        self.app._handle_sir_key(ord(" "))
        assert self.app.sir_running is True
        self.app._handle_sir_key(ord(" "))
        assert self.app.sir_running is False

    def test_handle_sir_key_transmission_adjust(self):
        """'t'/'T' keys should adjust transmission probability."""
        self.app._sir_init(0)
        original = self.app.sir_transmission_prob
        self.app._handle_sir_key(ord("t"))
        assert self.app.sir_transmission_prob == pytest.approx(original + 0.05, abs=1e-6)
        self.app._handle_sir_key(ord("T"))
        assert self.app.sir_transmission_prob == pytest.approx(original, abs=1e-6)

    def test_handle_sir_key_transmission_clamped(self):
        """Transmission probability should be clamped to [0.01, 1.0]."""
        self.app._sir_init(0)
        self.app.sir_transmission_prob = 0.99
        self.app._handle_sir_key(ord("t"))  # +0.05 -> clamped to 1.0
        assert self.app.sir_transmission_prob == 1.0
        self.app.sir_transmission_prob = 0.02
        self.app._handle_sir_key(ord("T"))  # -0.05 -> clamped to 0.01
        assert self.app.sir_transmission_prob == 0.01

    def test_handle_sir_key_recovery_adjust(self):
        """'v'/'V' keys should adjust recovery time."""
        self.app._sir_init(0)
        original = self.app.sir_recovery_time
        self.app._handle_sir_key(ord("v"))
        assert self.app.sir_recovery_time == original + 5
        self.app._handle_sir_key(ord("V"))
        assert self.app.sir_recovery_time == original

    def test_handle_sir_key_mortality_adjust(self):
        """'d'/'D' keys should adjust mortality rate."""
        self.app._sir_init(0)
        assert self.app.sir_mortality_rate == 0.0
        self.app._handle_sir_key(ord("d"))
        assert self.app.sir_mortality_rate == pytest.approx(0.02, abs=1e-6)
        self.app._handle_sir_key(ord("D"))
        assert self.app.sir_mortality_rate == pytest.approx(0.0, abs=1e-6)

    def test_handle_sir_key_steps_per_frame(self):
        """'+'/'-' should adjust steps per frame."""
        self.app._sir_init(0)
        assert self.app.sir_steps_per_frame == 1
        self.app._handle_sir_key(ord("+"))
        assert self.app.sir_steps_per_frame == 2
        self.app._handle_sir_key(ord("-"))
        assert self.app.sir_steps_per_frame == 1
        self.app._handle_sir_key(ord("-"))
        assert self.app.sir_steps_per_frame == 1  # clamped at 1

    def test_handle_sir_key_quit(self):
        """'q' should exit sir mode."""
        self.app._sir_init(0)
        self.app.sir_mode = True
        self.app._handle_sir_key(ord("q"))
        assert self.app.sir_mode is False

    def test_handle_sir_menu_key_navigation(self):
        """j/k should navigate the menu."""
        self.app.sir_menu_sel = 0
        self.app._handle_sir_menu_key(ord("j"))
        assert self.app.sir_menu_sel == 1
        self.app._handle_sir_menu_key(ord("k"))
        assert self.app.sir_menu_sel == 0
        # Wrap around
        self.app._handle_sir_menu_key(ord("k"))
        assert self.app.sir_menu_sel == len(SIR_PRESETS) - 1

    def test_handle_sir_menu_key_enter_selects(self):
        """Enter should initialize the selected preset."""
        self.app.sir_menu_sel = 2
        self.app.sir_menu = True
        self.app._handle_sir_menu_key(ord("\n"))
        assert self.app.sir_mode is True
        assert self.app.sir_preset_name == SIR_PRESETS[2][0]

    def test_handle_sir_key_single_step(self):
        """'n' should advance one step (sir_steps_per_frame times)."""
        self.app._sir_init(0)
        self.app.sir_steps_per_frame = 3
        gen_before = self.app.sir_generation
        self.app._handle_sir_key(ord("n"))
        assert self.app.sir_generation == gen_before + 3

    def test_handle_sir_key_reset(self):
        """'r' should re-initialize the current preset."""
        random.seed(42)
        self.app._sir_init(0)
        for _ in range(10):
            self.app._sir_step()
        assert self.app.sir_generation == 10
        self.app._handle_sir_key(ord("r"))
        assert self.app.sir_generation == 0
        assert self.app.sir_running is False

    def test_handle_sir_key_return_to_menu(self):
        """'R' should return to the menu."""
        self.app._sir_init(0)
        self.app.sir_mode = True
        self.app._handle_sir_key(ord("R"))
        assert self.app.sir_mode is False
        assert self.app.sir_menu is True
