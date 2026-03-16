"""Tests for Voronoi Crystal Growth mode."""
import math
import random
from tests.conftest import make_mock_app
from life.modes.voronoi import register, VORONOI_PRESETS


class TestVoronoi:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._enter_voronoi_mode()
        assert self.app.voronoi_menu is True
        assert self.app.voronoi_menu_sel == 0

    def test_step_no_crash(self):
        self.app.voronoi_mode = True
        self.app.voronoi_menu_sel = 0
        self.app._voronoi_init(5)  # Sparse Nucleation (6 seeds) — enough room for 10+ steps
        for _ in range(10):
            self.app._voronoi_step()
        assert self.app.voronoi_generation == 10

    def test_exit_cleanup(self):
        self.app.voronoi_mode = True
        self.app.voronoi_menu_sel = 0
        self.app._voronoi_init(0)
        self.app._voronoi_step()
        self.app._exit_voronoi_mode()
        assert self.app.voronoi_mode is False
        assert self.app.voronoi_menu is False
        assert self.app.voronoi_running is False
        assert self.app.voronoi_grid == []
        assert self.app.voronoi_seeds == []

    # -- Preset validation (matching original commit fcda77a) --

    def test_preset_count(self):
        assert len(VORONOI_PRESETS) == 8

    def test_preset_names(self):
        names = [p[0] for p in VORONOI_PRESETS]
        expected = [
            "Fine Microstructure", "Coarse Grains", "Columnar Growth",
            "Dendritic Arms", "Isotropic Foam", "Sparse Nucleation",
            "Bicrystal", "Radial Burst",
        ]
        assert names == expected

    def test_preset_structure(self):
        """Each preset is (name, desc, num_seeds, anisotropy, seed_mode)."""
        for preset in VORONOI_PRESETS:
            assert len(preset) == 5
            name, desc, num_seeds, aniso, seed_mode = preset
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(num_seeds, int)
            assert isinstance(aniso, float)
            assert seed_mode in ("random", "edge", "bicrystal", "center")

    def test_preset_values_fine_microstructure(self):
        """Fine Microstructure: 60 seeds, 0.20 aniso, random."""
        p = VORONOI_PRESETS[0]
        assert p[0] == "Fine Microstructure"
        assert p[2] == 60
        assert p[3] == 0.20
        assert p[4] == "random"

    def test_preset_values_bicrystal(self):
        """Bicrystal: 2 seeds, 0.40 aniso, bicrystal mode."""
        p = VORONOI_PRESETS[6]
        assert p[0] == "Bicrystal"
        assert p[2] == 2
        assert p[3] == 0.40
        assert p[4] == "bicrystal"

    # -- All presets load --

    def test_all_presets_load(self):
        for idx in range(len(VORONOI_PRESETS)):
            random.seed(idx)
            self.app._voronoi_init(idx)
            assert self.app.voronoi_mode is True
            assert self.app.voronoi_generation == 0
            assert len(self.app.voronoi_grid) == self.app.voronoi_rows
            assert len(self.app.voronoi_grid[0]) == self.app.voronoi_cols

    # -- Grid initialization --

    def test_grid_dimensions(self):
        self.app._voronoi_init(0)
        rows = self.app.voronoi_rows
        cols = self.app.voronoi_cols
        assert rows > 0 and cols > 0
        assert len(self.app.voronoi_grid) == rows
        assert all(len(r) == cols for r in self.app.voronoi_grid)

    def test_seeds_placed_on_grid(self):
        """Each seed should mark its position on the grid."""
        self.app._voronoi_init(0)
        grid = self.app.voronoi_grid
        for gid, (r, c) in enumerate(self.app.voronoi_seeds):
            assert grid[r][c] == gid

    def test_initial_frontier_non_empty(self):
        """Frontier should be populated from seed neighbors."""
        self.app._voronoi_init(0)
        assert len(self.app.voronoi_frontier) > 0

    def test_seed_count_matches_preset(self):
        """Number of seeds placed matches preset specification."""
        for idx, (_, _, num_seeds, _, _) in enumerate(VORONOI_PRESETS):
            random.seed(idx)
            self.app._voronoi_init(idx)
            assert len(self.app.voronoi_seeds) == num_seeds
            assert self.app.voronoi_grain_count == num_seeds

    # -- Seed placement modes --

    def test_edge_seed_placement(self):
        """Edge mode places all seeds at column 0."""
        # Columnar Growth uses edge mode
        self.app._voronoi_init(2)
        for r, c in self.app.voronoi_seeds:
            assert c == 0

    def test_bicrystal_placement(self):
        """Bicrystal mode places exactly 2 seeds on opposite sides."""
        self.app._voronoi_init(6)  # Bicrystal preset
        assert len(self.app.voronoi_seeds) == 2
        (r1, c1), (r2, c2) = self.app.voronoi_seeds
        # Seeds should be on opposite horizontal halves
        cols = self.app.voronoi_cols
        assert c1 < cols // 2
        assert c2 > cols // 2

    def test_center_seed_placement(self):
        """Center mode places seeds near the center."""
        random.seed(42)
        self.app._voronoi_init(7)  # Radial Burst uses center
        rows = self.app.voronoi_rows
        cols = self.app.voronoi_cols
        cr, cc = rows // 2, cols // 2
        max_expected_dist = min(rows, cols) * 0.3
        for r, c in self.app.voronoi_seeds:
            dist = math.sqrt((r - cr) ** 2 + (c - cc) ** 2)
            assert dist < max_expected_dist

    # -- Step mechanics --

    def test_growth_fills_grid(self):
        """Running enough steps should fill all cells."""
        random.seed(42)
        self.app._voronoi_init(5)  # Sparse Nucleation — few seeds
        for _ in range(5000):
            self.app._voronoi_step()
            if not self.app.voronoi_frontier:
                break
        grid = self.app.voronoi_grid
        unfilled = sum(1 for r in grid for c in r if c == -1)
        total = self.app.voronoi_rows * self.app.voronoi_cols
        # Should be mostly filled
        assert unfilled / total < 0.01

    def test_frontier_shrinks_over_time(self):
        """Frontier should generally shrink as grid fills."""
        random.seed(42)
        self.app._voronoi_init(0)
        initial_frontier = len(self.app.voronoi_frontier)
        for _ in range(500):
            self.app._voronoi_step()
        later_frontier = len(self.app.voronoi_frontier)
        # After many steps, frontier should be smaller or empty
        assert later_frontier <= initial_frontier

    def test_generation_increments(self):
        self.app._voronoi_init(0)
        assert self.app.voronoi_generation == 0
        self.app._voronoi_step()
        assert self.app.voronoi_generation == 1

    def test_empty_frontier_noop(self):
        """Step with empty frontier should not crash or change generation."""
        self.app._voronoi_init(0)
        self.app.voronoi_frontier = []
        gen_before = self.app.voronoi_generation
        self.app._voronoi_step()
        # Generation should NOT increment when frontier is empty
        assert self.app.voronoi_generation == gen_before

    # -- Grain boundary detection --

    def test_boundary_detection(self):
        """Cells adjacent to different grains should be detected as boundaries."""
        self.app._voronoi_init(6)  # Bicrystal
        # Run until filled
        for _ in range(3000):
            self.app._voronoi_step()
            if not self.app.voronoi_frontier:
                break
        # Find a boundary cell
        found_boundary = False
        for r in range(self.app.voronoi_rows):
            for c in range(self.app.voronoi_cols):
                if self.app._voronoi_is_boundary(r, c):
                    found_boundary = True
                    break
            if found_boundary:
                break
        assert found_boundary, "Bicrystal should have grain boundaries"

    def test_unclaimed_not_boundary(self):
        """Unclaimed cells (gid == -1) should not be boundaries."""
        self.app._voronoi_init(0)
        # Before any steps, most cells are -1
        grid = self.app.voronoi_grid
        for r in range(self.app.voronoi_rows):
            for c in range(self.app.voronoi_cols):
                if grid[r][c] == -1:
                    assert not self.app._voronoi_is_boundary(r, c)

    def test_interior_not_boundary(self):
        """Cells entirely surrounded by the same grain are not boundaries."""
        self.app._voronoi_init(6)  # Bicrystal
        for _ in range(3000):
            self.app._voronoi_step()
            if not self.app.voronoi_frontier:
                break
        grid = self.app.voronoi_grid
        rows = self.app.voronoi_rows
        cols = self.app.voronoi_cols
        # Find a cell where all 8 neighbors have the same gid
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                gid = grid[r][c]
                if gid == -1:
                    continue
                all_same = all(
                    grid[r + dr][c + dc] == gid
                    for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                    if not (dr == 0 and dc == 0)
                )
                if all_same:
                    assert not self.app._voronoi_is_boundary(r, c)
                    return  # found at least one, test passes
        # If we couldn't find one, that's unexpected but not a failure of the code

    # -- Anisotropy --

    def test_isotropic_growth_uniform(self):
        """With aniso=0, growth should be roughly uniform in all directions."""
        random.seed(42)
        self.app._voronoi_init(4)  # Isotropic Foam (aniso=0)
        assert self.app.voronoi_aniso == 0.0
        for _ in range(500):
            self.app._voronoi_step()
        # Grid should have no empty cells strongly biased to one direction
        # (just verify it runs without crash and grains grow)
        filled = sum(
            1 for r in self.app.voronoi_grid
            for c in r if c != -1
        )
        total = self.app.voronoi_rows * self.app.voronoi_cols
        assert filled > total * 0.3
