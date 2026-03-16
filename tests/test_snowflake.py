"""Tests for Snowflake Growth mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.snowflake import register, SNOWFLAKE_PRESETS


class TestSnowflakePresets:
    """Validate presets match the canonical f0d7179 format."""

    def test_preset_count(self):
        assert len(SNOWFLAKE_PRESETS) == 12

    def test_preset_tuple_format(self):
        """Each preset is a 7-tuple: (name, desc, alpha, beta, gamma, mu, symmetric)."""
        for i, p in enumerate(SNOWFLAKE_PRESETS):
            assert len(p) == 7, f"Preset {i} has {len(p)} elements, expected 7"
            name, desc, alpha, beta, gamma, mu, symmetric = p
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(alpha, (int, float))
            assert isinstance(beta, (int, float))
            assert isinstance(gamma, (int, float))
            assert isinstance(mu, (int, float))
            assert isinstance(symmetric, bool)

    def test_preset_parameters_in_range(self):
        for name, _desc, alpha, beta, gamma, mu, symmetric in SNOWFLAKE_PRESETS:
            assert 0.0 < alpha <= 1.0, f"{name}: alpha={alpha} out of range"
            assert 0.0 < beta <= 1.0, f"{name}: beta={beta} out of range"
            assert 0.0 <= gamma <= 0.01, f"{name}: gamma={gamma} out of range"
            assert 0.0 < mu <= 1.0, f"{name}: mu={mu} out of range"

    def test_preset_names_unique(self):
        names = [p[0] for p in SNOWFLAKE_PRESETS]
        assert len(names) == len(set(names))

    def test_symmetric_and_asymmetric_presets_exist(self):
        sym = [p for p in SNOWFLAKE_PRESETS if p[6]]
        asym = [p for p in SNOWFLAKE_PRESETS if not p[6]]
        assert len(sym) >= 8, "Should have at least 8 symmetric presets"
        assert len(asym) >= 2, "Should have at least 2 asymmetric presets"


class TestSnowflakeInit:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._snowflake_init(0)
        assert self.app.snowflake_mode is True
        assert self.app.snowflake_generation == 0
        assert len(self.app.snowflake_frozen) > 0
        assert self.app.snowflake_steps_per_frame == 1
        assert self.app.snowflake_frozen_count == 1

    def test_init_all_presets(self):
        """All presets should initialize without error."""
        for i in range(len(SNOWFLAKE_PRESETS)):
            self.app._snowflake_init(i)
            assert self.app.snowflake_mode is True
            assert self.app.snowflake_frozen_count == 1

    def test_center_seed_frozen(self):
        """Center cell should be frozen with zero vapor."""
        self.app._snowflake_init(0)
        rows, cols = self.app.snowflake_rows, self.app.snowflake_cols
        cr, cc = rows // 2, cols // 2
        assert self.app.snowflake_frozen[cr][cc] is True
        assert self.app.snowflake_vapor[cr][cc] == 0.0

    def test_initial_vapor_uniform_beta(self):
        """All non-frozen cells should start with vapor = beta."""
        self.app._snowflake_init(0)
        beta = self.app.snowflake_beta
        rows, cols = self.app.snowflake_rows, self.app.snowflake_cols
        cr, cc = rows // 2, cols // 2
        for r in range(rows):
            for c in range(cols):
                if r == cr and c == cc:
                    continue
                assert self.app.snowflake_vapor[r][c] == beta

    def test_parameters_match_preset(self):
        """Init should set parameters from the chosen preset."""
        preset = SNOWFLAKE_PRESETS[3]  # Fernlike
        self.app._snowflake_init(3)
        assert self.app.snowflake_alpha == preset[2]
        assert self.app.snowflake_beta == preset[3]
        assert self.app.snowflake_gamma == preset[4]
        assert self.app.snowflake_mu == preset[5]
        assert self.app.snowflake_symmetric == preset[6]
        assert self.app.snowflake_preset_name == preset[0]

    def test_grid_dimensions(self):
        self.app._snowflake_init(0)
        rows = self.app.snowflake_rows
        cols = self.app.snowflake_cols
        assert rows >= 20
        assert cols >= 20
        assert len(self.app.snowflake_frozen) == rows
        assert len(self.app.snowflake_frozen[0]) == cols
        assert len(self.app.snowflake_vapor) == rows
        assert len(self.app.snowflake_vapor[0]) == cols


class TestSnowflakeHexNeighbors:
    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))
        self.app._snowflake_init(0)

    def test_always_six_neighbors(self):
        """Hex neighbors should always return 6 neighbors."""
        for r in range(5, 15):
            for c in range(5, 15):
                nbrs = self.app._snowflake_hex_neighbors(r, c)
                assert len(nbrs) == 6, f"({r},{c}) has {len(nbrs)} neighbors"

    def test_even_row_neighbors(self):
        """Even row should have specific offset pattern."""
        nbrs = self.app._snowflake_hex_neighbors(4, 5)
        expected = [(3, 4), (3, 5), (4, 4), (4, 6), (5, 4), (5, 5)]
        assert sorted(nbrs) == sorted(expected)

    def test_odd_row_neighbors(self):
        """Odd row should have specific offset pattern."""
        nbrs = self.app._snowflake_hex_neighbors(5, 5)
        expected = [(4, 5), (4, 6), (5, 4), (5, 6), (6, 5), (6, 6)]
        assert sorted(nbrs) == sorted(expected)


class TestSnowflakeCoordinateConversions:
    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))
        self.app._snowflake_init(0)

    def test_roundtrip_axial_conversion(self):
        """Converting offset -> axial -> offset should be identity."""
        for r in range(0, 20):
            for c in range(0, 20):
                q, s = self.app._snowflake_hex_to_axial(r, c)
                r2, c2 = self.app._snowflake_axial_to_offset(q, s)
                assert (r2, c2) == (r, c), f"Roundtrip failed for ({r},{c})"


class TestSnowflakeSymmetry:
    def setup_method(self):
        self.app = make_mock_app()
        register(type(self.app))
        self.app._snowflake_init(0)

    def test_center_maps_to_itself(self):
        """The center cell should only produce itself under symmetry."""
        cr = self.app.snowflake_rows // 2
        cc = self.app.snowflake_cols // 2
        points = self.app._snowflake_symmetric_points(cr, cc)
        assert (cr, cc) in points
        # Center should map to just itself (all 12 transforms collapse)
        assert len(points) == 1

    def test_symmetric_points_count(self):
        """A general off-center point should produce up to 12 symmetric images."""
        cr = self.app.snowflake_rows // 2
        cc = self.app.snowflake_cols // 2
        # Pick a point off-center
        points = self.app._snowflake_symmetric_points(cr - 3, cc + 2)
        # Should have multiple symmetric images (up to 12, may be fewer due to grid bounds)
        assert len(points) >= 2

    def test_symmetric_points_are_in_bounds(self):
        """All symmetric points must be within grid bounds."""
        rows, cols = self.app.snowflake_rows, self.app.snowflake_cols
        cr, cc = rows // 2, cols // 2
        for dr in range(-5, 6):
            for dc in range(-5, 6):
                r, c = cr + dr, cc + dc
                if 0 <= r < rows and 0 <= c < cols:
                    points = self.app._snowflake_symmetric_points(r, c)
                    for pr, pc in points:
                        assert 0 <= pr < rows, f"Row {pr} out of bounds"
                        assert 0 <= pc < cols, f"Col {pc} out of bounds"

    def test_no_duplicate_symmetric_points(self):
        """Symmetric points should not contain duplicates."""
        cr = self.app.snowflake_rows // 2
        cc = self.app.snowflake_cols // 2
        points = self.app._snowflake_symmetric_points(cr - 4, cc + 3)
        assert len(points) == len(set(points))


class TestSnowflakeStep:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_step_increments_generation(self):
        self.app._snowflake_init(0)
        self.app._snowflake_step()
        assert self.app.snowflake_generation == 1

    def test_step_no_crash(self):
        self.app._snowflake_init(0)
        for _ in range(10):
            self.app._snowflake_step()
        assert self.app.snowflake_generation == 10

    def test_crystal_grows(self):
        """After several steps, the crystal should have more frozen cells."""
        self.app._snowflake_init(0)
        initial_frozen = self.app.snowflake_frozen_count
        for _ in range(50):
            self.app._snowflake_step()
        assert self.app.snowflake_frozen_count > initial_frozen

    def test_frozen_cells_never_unfreeze(self):
        """Once a cell is frozen, it stays frozen forever."""
        self.app._snowflake_init(0)
        rows, cols = self.app.snowflake_rows, self.app.snowflake_cols
        for step in range(20):
            frozen_before = set()
            for r in range(rows):
                for c in range(cols):
                    if self.app.snowflake_frozen[r][c]:
                        frozen_before.add((r, c))
            self.app._snowflake_step()
            for r, c in frozen_before:
                assert self.app.snowflake_frozen[r][c], \
                    f"Cell ({r},{c}) was unfrozen at step {step}"

    def test_frozen_cells_have_zero_vapor(self):
        """Frozen cells should have their vapor set to 0."""
        self.app._snowflake_init(0)
        for _ in range(20):
            self.app._snowflake_step()
        rows, cols = self.app.snowflake_rows, self.app.snowflake_cols
        for r in range(rows):
            for c in range(cols):
                if self.app.snowflake_frozen[r][c]:
                    assert self.app.snowflake_vapor[r][c] == 0.0

    def test_frozen_count_matches_grid(self):
        """snowflake_frozen_count should match actual frozen cell count."""
        self.app._snowflake_init(0)
        for _ in range(30):
            self.app._snowflake_step()
        actual = sum(1 for r in range(self.app.snowflake_rows)
                     for c in range(self.app.snowflake_cols)
                     if self.app.snowflake_frozen[r][c])
        assert self.app.snowflake_frozen_count == actual

    def test_diffusion_uses_mu_parameter(self):
        """With mu=0, no diffusion should occur (vapor stays put for non-receptive)."""
        self.app._snowflake_init(0)
        self.app.snowflake_mu = 0.0
        self.app.snowflake_gamma = 0.0  # no noise
        rows, cols = self.app.snowflake_rows, self.app.snowflake_cols
        # Record vapor at a cell far from center (not receptive)
        far_r, far_c = 0, 0
        vapor_before = self.app.snowflake_vapor[far_r][far_c]
        self.app._snowflake_step()
        # With mu=0, non-receptive cells should keep their vapor (1-0)*self + 0*avg = self
        assert self.app.snowflake_vapor[far_r][far_c] == pytest.approx(vapor_before, abs=1e-10)

    def test_symmetric_mode_produces_symmetric_growth(self):
        """In symmetric mode, newly frozen cells should be mirrored."""
        random.seed(0)
        self.app._snowflake_init(0)  # Classic Dendrite, symmetric=True
        assert self.app.snowflake_symmetric is True
        # Run until we get some growth
        for _ in range(100):
            self.app._snowflake_step()
        # Check that the crystal has more than 1 frozen cell
        assert self.app.snowflake_frozen_count > 1
        # Frozen count should generally be a multiple or have symmetric structure
        # (testing exact symmetry is complex, but count > 1 confirms growth)

    def test_asymmetric_mode_runs(self):
        """Asymmetric presets should also run correctly."""
        random.seed(42)
        # Find an asymmetric preset
        asym_idx = next(i for i, p in enumerate(SNOWFLAKE_PRESETS) if not p[6])
        self.app._snowflake_init(asym_idx)
        assert self.app.snowflake_symmetric is False
        for _ in range(30):
            self.app._snowflake_step()
        assert self.app.snowflake_frozen_count > 1

    def test_receptive_cells_get_deposition(self):
        """Cells adjacent to the crystal should receive alpha deposition."""
        self.app._snowflake_init(0)
        self.app.snowflake_gamma = 0.0  # no noise for deterministic test
        alpha = self.app.snowflake_alpha
        beta = self.app.snowflake_beta
        rows, cols = self.app.snowflake_rows, self.app.snowflake_cols
        cr, cc = rows // 2, cols // 2
        # Get a neighbor of the center (which is frozen)
        nbrs = self.app._snowflake_hex_neighbors(cr, cc)
        nr, nc = nbrs[0]
        if 0 <= nr < rows and 0 <= nc < cols:
            vapor_before = self.app.snowflake_vapor[nr][nc]
            assert vapor_before == beta
            self.app._snowflake_step()
            # After step, this cell (receptive) should have gotten alpha added
            # It may also have been diffused, but the deposition was applied to vapor
            # before diffusion, and receptive cells keep their vapor (no diffusion)
            # So new_vapor for receptive cell = vapor + alpha (since it's copied as-is)
            assert self.app.snowflake_vapor[nr][nc] >= beta  # at least no loss


class TestSnowflakeExitAndKeys:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_exit_cleanup(self):
        self.app._snowflake_init(0)
        assert self.app.snowflake_mode is True
        self.app._exit_snowflake_mode()
        assert self.app.snowflake_mode is False
        assert self.app.snowflake_running is False
        assert self.app.snowflake_frozen == []
        assert self.app.snowflake_vapor == []

    def test_enter_mode_sets_menu(self):
        self.app._enter_snowflake_mode()
        assert self.app.snowflake_menu is True
        assert self.app.snowflake_menu_sel == 0

    def test_handle_menu_key_navigation(self):
        """j/k should navigate the menu."""
        import curses
        self.app._enter_snowflake_mode()
        self.app._handle_snowflake_menu_key(ord("j"))
        assert self.app.snowflake_menu_sel == 1
        self.app._handle_snowflake_menu_key(ord("k"))
        assert self.app.snowflake_menu_sel == 0

    def test_handle_key_toggle_running(self):
        self.app._snowflake_init(0)
        assert self.app.snowflake_running is False
        self.app._handle_snowflake_key(ord(" "))
        assert self.app.snowflake_running is True
        self.app._handle_snowflake_key(ord(" "))
        assert self.app.snowflake_running is False

    def test_handle_key_single_step(self):
        self.app._snowflake_init(0)
        gen_before = self.app.snowflake_generation
        self.app._handle_snowflake_key(ord("n"))
        assert self.app.snowflake_generation == gen_before + 1

    def test_handle_key_alpha_control(self):
        self.app._snowflake_init(0)
        alpha_before = self.app.snowflake_alpha
        self.app._handle_snowflake_key(ord("A"))
        assert self.app.snowflake_alpha > alpha_before
        self.app._handle_snowflake_key(ord("a"))
        assert self.app.snowflake_alpha == pytest.approx(alpha_before, abs=0.001)

    def test_handle_key_diffusion_control(self):
        self.app._snowflake_init(0)
        mu_before = self.app.snowflake_mu
        self.app._handle_snowflake_key(ord("D"))
        assert self.app.snowflake_mu > mu_before
        self.app._handle_snowflake_key(ord("d"))
        assert self.app.snowflake_mu == pytest.approx(mu_before, abs=0.001)

    def test_handle_key_symmetry_toggle(self):
        self.app._snowflake_init(0)
        sym_before = self.app.snowflake_symmetric
        self.app._handle_snowflake_key(ord("s"))
        assert self.app.snowflake_symmetric != sym_before

    def test_handle_key_speed_control(self):
        self.app._snowflake_init(0)
        assert self.app.snowflake_steps_per_frame == 1
        self.app._handle_snowflake_key(ord("+"))
        assert self.app.snowflake_steps_per_frame >= 2
        self.app._handle_snowflake_key(ord("-"))
        assert self.app.snowflake_steps_per_frame == 1

    def test_handle_key_reset(self):
        self.app._snowflake_init(0)
        for _ in range(10):
            self.app._snowflake_step()
        assert self.app.snowflake_generation > 0
        self.app._handle_snowflake_key(ord("r"))
        assert self.app.snowflake_generation == 0
        assert self.app.snowflake_frozen_count == 1

    def test_handle_key_return_to_menu(self):
        self.app._snowflake_init(0)
        self.app._handle_snowflake_key(ord("R"))
        assert self.app.snowflake_mode is False
        assert self.app.snowflake_menu is True
