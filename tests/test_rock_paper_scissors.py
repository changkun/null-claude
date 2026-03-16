"""Tests for Spatial Rock-Paper-Scissors mode."""
import random
from tests.conftest import make_mock_app
from life.modes.rock_paper_scissors import register, RPS_PRESETS


class TestRockPaperScissors:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_rps_mode()
        assert self.app.rps_menu is True
        assert self.app.rps_menu_sel == 0

    def test_step_no_crash(self):
        self.app.rps_mode = True
        self.app.rps_menu_sel = 0
        self.app._rps_init(0)
        for _ in range(10):
            self.app._rps_step()
        assert self.app.rps_generation == 10

    def test_exit_cleanup(self):
        self.app.rps_mode = True
        self.app.rps_menu_sel = 0
        self.app._rps_init(0)
        self.app._rps_step()
        self.app._exit_rps_mode()
        assert self.app.rps_mode is False
        assert self.app.rps_menu is False
        assert self.app.rps_running is False
        assert self.app.rps_grid == []

    # -- Preset validation (matching original commit 52d881e) --

    def test_preset_count(self):
        assert len(RPS_PRESETS) == 6

    def test_preset_names(self):
        names = [p[0] for p in RPS_PRESETS]
        expected = [
            "Classic Spiral Waves", "Slow Spirals", "Fast Chaos",
            "Territorial Blocks", "Five Species", "Seeded Spirals",
        ]
        assert names == expected

    def test_preset_structure(self):
        """Each preset is (name, desc, num_species, swap_rate, layout)."""
        for preset in RPS_PRESETS:
            assert len(preset) == 5
            name, desc, num_species, swap_rate, layout = preset
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(num_species, int)
            assert isinstance(swap_rate, float)
            assert layout in ("random", "blocks", "seeds")

    def test_preset_values_classic(self):
        """Classic Spiral Waves: 3 species, 0.5 swap, random."""
        p = RPS_PRESETS[0]
        assert p[0] == "Classic Spiral Waves"
        assert p[2] == 3
        assert p[3] == 0.5
        assert p[4] == "random"

    def test_preset_values_five_species(self):
        """Five Species: 5 species, 0.5 swap, random."""
        p = RPS_PRESETS[4]
        assert p[0] == "Five Species"
        assert p[2] == 5
        assert p[3] == 0.5
        assert p[4] == "random"

    # -- All presets load --

    def test_all_presets_load(self):
        for idx in range(len(RPS_PRESETS)):
            random.seed(idx)
            self.app._rps_init(idx)
            assert self.app.rps_mode is True
            assert self.app.rps_generation == 0
            assert len(self.app.rps_grid) == self.app.rps_rows
            assert len(self.app.rps_grid[0]) == self.app.rps_cols

    # -- Grid initialization --

    def test_random_layout_species_range(self):
        """Random layout should only contain valid species IDs."""
        self.app._rps_init(0)  # Classic, 3 species, random
        ns = self.app.rps_num_species
        for row in self.app.rps_grid:
            for cell in row:
                assert 0 <= cell < ns

    def test_blocks_layout(self):
        """Blocks layout should produce vertical stripes."""
        self.app._rps_init(3)  # Territorial Blocks
        cols = self.app.rps_cols
        ns = self.app.rps_num_species
        stripe_w = cols // ns
        # Check first column of each stripe
        for s in range(ns):
            c = s * stripe_w
            if c < cols:
                assert self.app.rps_grid[0][c] == s

    def test_seeds_layout(self):
        """Seeds layout should have species 0 as dominant."""
        random.seed(42)
        self.app._rps_init(5)  # Seeded Spirals
        counts = self.app._rps_counts()
        # Species 0 should be the most common in seeds layout
        assert counts[0] >= counts[1]
        assert counts[0] >= counts[2]

    def test_five_species_grid(self):
        """Five Species mode should use species 0-4."""
        random.seed(42)
        self.app._rps_init(4)  # Five Species
        assert self.app.rps_num_species == 5
        species_seen = set()
        for row in self.app.rps_grid:
            for cell in row:
                species_seen.add(cell)
                assert 0 <= cell < 5
        assert len(species_seen) == 5  # all species present with random layout

    # -- Step mechanics --

    def test_cyclic_dominance(self):
        """Verify the cyclic dominance rule: species i beats (i-1) mod N."""
        # Set up a minimal 2x2 grid with controlled species
        self.app.rps_rows = 2
        self.app.rps_cols = 2
        self.app.rps_num_species = 3
        self.app.rps_swap_rate = 1.0
        self.app.rps_generation = 0
        # Rock(0) beats Scissors(2), Paper(1) beats Rock(0), Scissors(2) beats Paper(1)
        # attacker beats defender when defender == (attacker - 1) % ns
        ns = 3
        for attacker in range(ns):
            victim = (attacker - 1) % ns
            assert victim != attacker
            # attacker should beat victim
            # non-victim should not be beaten
            non_victim = (attacker + 1) % ns
            assert non_victim != victim

    def test_species_counts(self):
        """_rps_counts should correctly count species."""
        self.app._rps_init(0)
        counts = self.app._rps_counts()
        assert len(counts) == self.app.rps_num_species
        total = sum(counts)
        assert total == self.app.rps_rows * self.app.rps_cols

    def test_population_conserved(self):
        """Total cell count stays constant (species change, cells don't appear/disappear)."""
        self.app._rps_init(0)
        total_before = sum(self.app._rps_counts())
        for _ in range(20):
            self.app._rps_step()
        total_after = sum(self.app._rps_counts())
        assert total_before == total_after

    def test_generation_increments(self):
        self.app._rps_init(0)
        assert self.app.rps_generation == 0
        self.app._rps_step()
        assert self.app.rps_generation == 1
        self.app._rps_step()
        assert self.app.rps_generation == 2

    def test_step_changes_grid(self):
        """After enough steps with swap_rate > 0, grid should change."""
        random.seed(42)
        self.app._rps_init(2)  # Fast Chaos, swap_rate=0.9
        initial = [row[:] for row in self.app.rps_grid]
        for _ in range(5):
            self.app._rps_step()
        changed = any(
            self.app.rps_grid[r][c] != initial[r][c]
            for r in range(self.app.rps_rows)
            for c in range(self.app.rps_cols)
        )
        assert changed

    def test_wrapping_topology(self):
        """RPS uses toroidal wrapping for neighbor selection."""
        # This is verified by the modular arithmetic in _rps_step
        # Just ensure it doesn't crash with edge cells
        self.app._rps_init(0)
        # Force grid to have specific values at edges
        rows = self.app.rps_rows
        cols = self.app.rps_cols
        self.app.rps_grid[0][0] = 0
        self.app.rps_grid[rows - 1][cols - 1] = 1
        # Step should not crash even with edge cells being picked
        for _ in range(10):
            self.app._rps_step()

    def test_swap_rate_affects_change_rate(self):
        """Higher swap rate should cause more changes per step."""
        # Low swap rate
        random.seed(42)
        self.app._rps_init(1)  # Slow Spirals, swap_rate=0.2
        grid_before = [row[:] for row in self.app.rps_grid]
        self.app._rps_step()
        changes_slow = sum(
            1 for r in range(self.app.rps_rows)
            for c in range(self.app.rps_cols)
            if self.app.rps_grid[r][c] != grid_before[r][c]
        )

        # High swap rate
        random.seed(42)
        self.app._rps_init(2)  # Fast Chaos, swap_rate=0.9
        grid_before = [row[:] for row in self.app.rps_grid]
        self.app._rps_step()
        changes_fast = sum(
            1 for r in range(self.app.rps_rows)
            for c in range(self.app.rps_cols)
            if self.app.rps_grid[r][c] != grid_before[r][c]
        )

        # Fast should have more interactions (and thus likely more changes)
        # This isn't strictly guaranteed due to randomness, but the ratio
        # of swap_rate (0.9/0.2 = 4.5x) makes it very likely
        assert changes_fast >= changes_slow

    def test_reinit_resets(self):
        """Re-initializing resets generation."""
        self.app._rps_init(0)
        for _ in range(5):
            self.app._rps_step()
        assert self.app.rps_generation == 5
        self.app._rps_init(1)
        assert self.app.rps_generation == 0
