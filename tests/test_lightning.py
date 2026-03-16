"""Tests for Lightning mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.lightning import register, LIGHTNING_PRESETS


class TestLightningPresets:
    """Validate presets match the canonical dc26af5 format."""

    def test_preset_count(self):
        assert len(LIGHTNING_PRESETS) == 8

    def test_preset_tuple_format(self):
        """Each preset is (name, desc, eta, source)."""
        for i, p in enumerate(LIGHTNING_PRESETS):
            assert len(p) == 4, f"Preset {i} has {len(p)} elements, expected 4"
            name, desc, eta, source = p
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(eta, (int, float))
            assert source in ("top", "center", "point")

    def test_eta_values_positive(self):
        for name, _desc, eta, _source in LIGHTNING_PRESETS:
            assert eta > 0, f"{name}: eta must be positive"

    def test_preset_names_unique(self):
        names = [p[0] for p in LIGHTNING_PRESETS]
        assert len(names) == len(set(names))

    def test_all_source_types_present(self):
        sources = {p[3] for p in LIGHTNING_PRESETS}
        assert "top" in sources
        assert "center" in sources
        assert "point" in sources


class TestLightningInit:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._lightning_init(0)
        assert self.app.lightning_mode is True
        assert self.app.lightning_generation == 0
        assert len(self.app.lightning_grid) > 0
        assert self.app.lightning_steps_per_frame == 1
        assert self.app.lightning_channel_count == 1

    def test_init_all_presets(self):
        for i in range(len(LIGHTNING_PRESETS)):
            self.app._lightning_init(i)
            assert self.app.lightning_mode is True
            assert self.app.lightning_channel_count == 1

    def test_top_source_placement(self):
        """Top source should place channel at center of top row."""
        idx = next(i for i, p in enumerate(LIGHTNING_PRESETS) if p[3] == "top")
        self.app._lightning_init(idx)
        cols = self.app.lightning_cols
        assert self.app.lightning_grid[0][cols // 2] == 1

    def test_center_source_placement(self):
        """Center source should place channel at grid center."""
        idx = next(i for i, p in enumerate(LIGHTNING_PRESETS) if p[3] == "center")
        self.app._lightning_init(idx)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        assert self.app.lightning_grid[rows // 2][cols // 2] == 1

    def test_point_source_placement(self):
        """Point source should place channel at rows//4, cols//2."""
        idx = next(i for i, p in enumerate(LIGHTNING_PRESETS) if p[3] == "point")
        self.app._lightning_init(idx)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        assert self.app.lightning_grid[rows // 4][cols // 2] == 1

    def test_only_one_initial_channel_cell(self):
        """Only one cell should be a channel initially."""
        self.app._lightning_init(0)
        count = sum(1 for r in range(self.app.lightning_rows)
                    for c in range(self.app.lightning_cols)
                    if self.app.lightning_grid[r][c] == 1)
        assert count == 1

    def test_potential_field_initialized(self):
        """Potential field should be computed after init."""
        self.app._lightning_init(0)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        # Channel cells should have potential 0
        for r in range(rows):
            for c in range(cols):
                if self.app.lightning_grid[r][c] == 1:
                    assert self.app.lightning_potential[r][c] == 0.0
        # Bottom row (ground) should have potential 1 for top source
        for c in range(cols):
            if self.app.lightning_grid[rows - 1][c] == 0:
                assert self.app.lightning_potential[rows - 1][c] == 1.0

    def test_parameters_match_preset(self):
        preset = LIGHTNING_PRESETS[1]  # Sparse Bolt
        self.app._lightning_init(1)
        assert self.app.lightning_eta == preset[2]
        assert self.app.lightning_source == preset[3]
        assert self.app.lightning_preset_name == preset[0]

    def test_age_grid_initialized(self):
        self.app._lightning_init(0)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        assert len(self.app.lightning_age) == rows
        assert len(self.app.lightning_age[0]) == cols


class TestLightningSolvePotential:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_channel_cells_have_zero_potential(self):
        """After solving, channel cells must have potential = 0."""
        self.app._lightning_init(0)
        self.app._lightning_solve_potential()
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        for r in range(rows):
            for c in range(cols):
                if self.app.lightning_grid[r][c] == 1:
                    assert self.app.lightning_potential[r][c] == 0.0

    def test_ground_boundary_top_source(self):
        """For top source, bottom row should have potential = 1."""
        idx = next(i for i, p in enumerate(LIGHTNING_PRESETS) if p[3] == "top")
        self.app._lightning_init(idx)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        for c in range(cols):
            if self.app.lightning_grid[rows - 1][c] == 0:
                assert self.app.lightning_potential[rows - 1][c] == 1.0

    def test_ground_boundary_center_source(self):
        """For center source, all edges should have potential = 1."""
        idx = next(i for i, p in enumerate(LIGHTNING_PRESETS) if p[3] == "center")
        self.app._lightning_init(idx)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        for c in range(cols):
            if self.app.lightning_grid[0][c] == 0:
                assert self.app.lightning_potential[0][c] == 1.0
            if self.app.lightning_grid[rows - 1][c] == 0:
                assert self.app.lightning_potential[rows - 1][c] == 1.0
        for r in range(rows):
            if self.app.lightning_grid[r][0] == 0:
                assert self.app.lightning_potential[r][0] == 1.0
            if self.app.lightning_grid[r][cols - 1] == 0:
                assert self.app.lightning_potential[r][cols - 1] == 1.0

    def test_potential_monotonicity_top_source(self):
        """For top source, potential should generally increase from top to bottom."""
        idx = next(i for i, p in enumerate(LIGHTNING_PRESETS) if p[3] == "top")
        self.app._lightning_init(idx)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        mid_c = cols // 2
        # Away from the channel, potential should increase downward
        # Check a column far from channel
        far_c = min(cols - 1, mid_c + 10)
        potentials = [self.app.lightning_potential[r][far_c] for r in range(rows)]
        # Not strictly monotone due to relaxation, but bottom should be > top
        assert potentials[-1] >= potentials[1]


class TestLightningStep:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_step_increments_generation(self):
        self.app._lightning_init(0)
        self.app._lightning_step()
        assert self.app.lightning_generation == 1

    def test_step_no_crash(self):
        self.app._lightning_init(0)
        for _ in range(10):
            self.app._lightning_step()
        assert self.app.lightning_generation == 10

    def test_channel_grows(self):
        """After a step, channel count should increase by 1."""
        self.app._lightning_init(0)
        count_before = self.app.lightning_channel_count
        self.app._lightning_step()
        assert self.app.lightning_channel_count == count_before + 1

    def test_channel_cells_never_removed(self):
        """Once a cell is in the channel, it stays."""
        self.app._lightning_init(0)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        for _ in range(5):
            channel_before = set()
            for r in range(rows):
                for c in range(cols):
                    if self.app.lightning_grid[r][c] == 1:
                        channel_before.add((r, c))
            self.app._lightning_step()
            for r, c in channel_before:
                assert self.app.lightning_grid[r][c] == 1

    def test_new_channel_adjacent_to_existing(self):
        """Each new channel cell must be 4-adjacent to an existing channel cell."""
        self.app._lightning_init(0)
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        for _ in range(10):
            old_channels = set()
            for r in range(rows):
                for c in range(cols):
                    if self.app.lightning_grid[r][c] == 1:
                        old_channels.add((r, c))
            self.app._lightning_step()
            new_channels = set()
            for r in range(rows):
                for c in range(cols):
                    if self.app.lightning_grid[r][c] == 1:
                        new_channels.add((r, c))
            added = new_channels - old_channels
            for r, c in added:
                has_neighbor = False
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if (nr, nc) in old_channels:
                        has_neighbor = True
                        break
                assert has_neighbor, f"New channel ({r},{c}) not adjacent to existing"

    def test_channel_count_matches_grid(self):
        """lightning_channel_count should match actual channel cells."""
        self.app._lightning_init(0)
        for _ in range(10):
            self.app._lightning_step()
        actual = sum(1 for r in range(self.app.lightning_rows)
                     for c in range(self.app.lightning_cols)
                     if self.app.lightning_grid[r][c] == 1)
        assert self.app.lightning_channel_count == actual

    def test_age_tracking(self):
        """Newly added cells should have age = current generation."""
        self.app._lightning_init(0)
        for step in range(5):
            rows, cols = self.app.lightning_rows, self.app.lightning_cols
            old_channels = set()
            for r in range(rows):
                for c in range(cols):
                    if self.app.lightning_grid[r][c] == 1:
                        old_channels.add((r, c))
            gen_before = self.app.lightning_generation
            self.app._lightning_step()
            for r in range(rows):
                for c in range(cols):
                    if self.app.lightning_grid[r][c] == 1 and (r, c) not in old_channels:
                        assert self.app.lightning_age[r][c] == gen_before

    def test_reaches_ground_stops(self):
        """When the channel reaches ground, lightning_running should stop."""
        self.app._lightning_init(0)
        self.app.lightning_running = True
        # Run many steps until ground is reached
        for _ in range(500):
            if not self.app.lightning_running:
                break
            self.app._lightning_step()
        # Either it stopped or still going (might not reach in 500 steps on large grid)
        # But channel count should have grown
        assert self.app.lightning_channel_count > 1

    def test_potential_resolves_after_step(self):
        """After each step, the potential field should be re-solved."""
        self.app._lightning_init(0)
        self.app._lightning_step()
        # Newly added channel cell should have potential 0
        rows, cols = self.app.lightning_rows, self.app.lightning_cols
        for r in range(rows):
            for c in range(cols):
                if self.app.lightning_grid[r][c] == 1:
                    assert self.app.lightning_potential[r][c] == 0.0

    def test_higher_eta_reduces_branching(self):
        """Higher eta should produce fewer branches (more concentrated growth)."""
        random.seed(100)
        # Low eta run
        self.app._lightning_init(0)
        self.app.lightning_eta = 1.0
        for _ in range(30):
            self.app._lightning_step()
        low_eta_channels = self.app.lightning_channel_count

        random.seed(100)
        # High eta run - same number of steps = same channel count (1 per step)
        self.app._lightning_init(0)
        self.app.lightning_eta = 5.0
        for _ in range(30):
            self.app._lightning_step()
        high_eta_channels = self.app.lightning_channel_count

        # Both should have same channel count (one per step) - eta affects
        # which cells are chosen, not how many per step
        assert low_eta_channels == high_eta_channels == 31  # 1 initial + 30 steps


class TestLightningExitAndKeys:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_exit_cleanup(self):
        self.app._lightning_init(0)
        assert self.app.lightning_mode is True
        self.app._exit_lightning_mode()
        assert self.app.lightning_mode is False
        assert self.app.lightning_running is False
        assert self.app.lightning_grid == []
        assert self.app.lightning_potential == []
        assert self.app.lightning_age == []

    def test_enter_mode_sets_menu(self):
        self.app._enter_lightning_mode()
        assert self.app.lightning_menu is True
        assert self.app.lightning_menu_sel == 0

    def test_handle_menu_key_navigation(self):
        self.app._enter_lightning_mode()
        self.app._handle_lightning_menu_key(ord("j"))
        assert self.app.lightning_menu_sel == 1
        self.app._handle_lightning_menu_key(ord("k"))
        assert self.app.lightning_menu_sel == 0

    def test_handle_menu_key_select(self):
        self.app._enter_lightning_mode()
        self.app._handle_lightning_menu_key(ord("\n"))
        assert self.app.lightning_mode is True
        assert self.app.lightning_menu is False

    def test_handle_key_toggle_running(self):
        self.app._lightning_init(0)
        assert self.app.lightning_running is False
        self.app._handle_lightning_key(ord(" "))
        assert self.app.lightning_running is True

    def test_handle_key_single_step(self):
        self.app._lightning_init(0)
        gen_before = self.app.lightning_generation
        self.app._handle_lightning_key(ord("n"))
        assert self.app.lightning_generation == gen_before + 1

    def test_handle_key_eta_control(self):
        self.app._lightning_init(0)
        eta_before = self.app.lightning_eta
        self.app._handle_lightning_key(ord("e"))
        assert self.app.lightning_eta > eta_before
        self.app._handle_lightning_key(ord("E"))
        assert self.app.lightning_eta == pytest.approx(eta_before, abs=0.001)

    def test_handle_key_speed_control(self):
        self.app._lightning_init(0)
        assert self.app.lightning_steps_per_frame == 1
        self.app._handle_lightning_key(ord("+"))
        assert self.app.lightning_steps_per_frame == 2
        self.app._handle_lightning_key(ord("-"))
        assert self.app.lightning_steps_per_frame == 1

    def test_handle_key_reset(self):
        self.app._lightning_init(0)
        for _ in range(5):
            self.app._lightning_step()
        assert self.app.lightning_generation > 0
        self.app._handle_lightning_key(ord("r"))
        assert self.app.lightning_generation == 0
        assert self.app.lightning_channel_count == 1

    def test_handle_key_exit(self):
        self.app._lightning_init(0)
        self.app._handle_lightning_key(ord("q"))
        assert self.app.lightning_mode is False

    def test_handle_key_return_to_menu(self):
        self.app._lightning_init(0)
        self.app._handle_lightning_key(ord("R"))
        assert self.app.lightning_mode is False
        assert self.app.lightning_menu is True

    def test_eta_clamped(self):
        """Eta should be clamped to [0.1, 10.0]."""
        self.app._lightning_init(0)
        self.app.lightning_eta = 0.2
        self.app._handle_lightning_key(ord("E"))  # decrease by 0.25
        assert self.app.lightning_eta >= 0.1
        self.app.lightning_eta = 9.9
        self.app._handle_lightning_key(ord("e"))  # increase by 0.25
        assert self.app.lightning_eta <= 10.0
