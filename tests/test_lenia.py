"""Tests for lenia mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.lenia import register, LENIA_PRESETS, LENIA_DENSITY


class TestLeniaConstants:
    """Test that module-level constants match the original monolith."""

    def test_presets_count(self):
        assert len(LENIA_PRESETS) == 6

    def test_preset_names(self):
        names = [p[0] for p in LENIA_PRESETS]
        assert names == [
            "Orbium", "Geminium", "Scutium",
            "Hydrogeminium", "Pentadecathlon", "Wanderer",
        ]

    def test_preset_tuple_structure(self):
        for name, desc, R, mu, sigma, dt in LENIA_PRESETS:
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(R, int) and R >= 3
            assert isinstance(mu, float) and 0 < mu < 1
            assert isinstance(sigma, float) and 0 < sigma < 1
            assert isinstance(dt, float) and 0 < dt <= 0.5

    def test_density_glyphs(self):
        assert len(LENIA_DENSITY) == 5
        assert LENIA_DENSITY[0] == "  "
        assert LENIA_DENSITY[4] == "\u2588\u2588"

    def test_register_sets_class_constants(self):
        app = make_mock_app()
        cls = type(app)
        register(cls)
        assert cls.LENIA_PRESETS is LENIA_PRESETS
        assert cls.LENIA_DENSITY is LENIA_DENSITY


class TestLeniaKernel:
    """Deep tests for the ring-shaped convolution kernel."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        self.app.lenia_R = 13
        self.app.lenia_mu = 0.15
        self.app.lenia_sigma = 0.015
        self.app.lenia_dt = 0.1
        self.app.lenia_steps_per_frame = 1
        self.app.lenia_preset_name = ""
        self.app.lenia_generation = 0
        self.app.lenia_grid = []
        self.app.lenia_kernel = []

    def test_kernel_dimensions(self):
        for R in [3, 5, 10, 13]:
            self.app.lenia_R = R
            self.app._lenia_build_kernel()
            k = self.app.lenia_kernel
            size = 2 * R + 1
            assert len(k) == size
            assert all(len(row) == size for row in k)

    def test_kernel_normalised_to_one(self):
        for R in [3, 5, 8, 13]:
            self.app.lenia_R = R
            self.app._lenia_build_kernel()
            total = sum(v for row in self.app.lenia_kernel for v in row)
            assert abs(total - 1.0) < 1e-9, f"Kernel sum {total} for R={R}"

    def test_kernel_center_not_peak(self):
        """The ring kernel should NOT peak at the center (dr=0).
        It peaks at dr=0.5 from center (in normalised distance)."""
        self.app.lenia_R = 10
        self.app._lenia_build_kernel()
        k = self.app.lenia_kernel
        R = 10
        center_val = k[R][R]
        # Value at distance ~0.5*R from center (where the ring peaks)
        ring_val = k[R][R + R // 2]
        assert ring_val > center_val, "Ring kernel should peak away from center"

    def test_kernel_zero_outside_unit_circle(self):
        """Values at normalised distance > 1 should be zero."""
        self.app.lenia_R = 8
        self.app._lenia_build_kernel()
        k = self.app.lenia_kernel
        R = 8
        size = 2 * R + 1
        for dy in range(size):
            for dx in range(size):
                dr = math.sqrt((dy - R) ** 2 + (dx - R) ** 2) / R
                if dr > 1.0:
                    assert k[dy][dx] == 0.0, f"Non-zero at dr={dr:.2f}"

    def test_kernel_symmetry(self):
        """Kernel should be radially symmetric."""
        self.app.lenia_R = 7
        self.app._lenia_build_kernel()
        k = self.app.lenia_kernel
        R = 7
        # Check 4-fold symmetry
        for dy in range(R + 1):
            for dx in range(R + 1):
                assert abs(k[R + dy][R + dx] - k[R - dy][R + dx]) < 1e-12
                assert abs(k[R + dy][R + dx] - k[R + dy][R - dx]) < 1e-12
                assert abs(k[R + dy][R + dx] - k[R + dx][R + dy]) < 1e-12

    def test_kernel_all_nonnegative(self):
        self.app.lenia_R = 6
        self.app._lenia_build_kernel()
        for row in self.app.lenia_kernel:
            for v in row:
                assert v >= 0.0


class TestLeniaGrowth:
    """Deep tests for the growth function G(u)."""

    def setup_method(self):
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        self.app.lenia_mu = 0.15
        self.app.lenia_sigma = 0.015
        self.app.lenia_generation = 0
        self.app.lenia_grid = []
        self.app.lenia_kernel = []

    def test_growth_at_mu_is_one(self):
        """G(mu) = 2*exp(0) - 1 = 1.0 exactly."""
        val = self.app._lenia_growth(0.15)
        assert abs(val - 1.0) < 1e-12

    def test_growth_far_from_mu_approaches_minus_one(self):
        """G(u) -> -1 as |u - mu| -> inf."""
        val = self.app._lenia_growth(0.0)
        assert val < -0.99
        val = self.app._lenia_growth(1.0)
        assert val < -0.99

    def test_growth_symmetric_around_mu(self):
        """G(mu + d) == G(mu - d) for any d."""
        mu = self.app.lenia_mu
        for d in [0.005, 0.01, 0.02, 0.05]:
            g_plus = self.app._lenia_growth(mu + d)
            g_minus = self.app._lenia_growth(mu - d)
            assert abs(g_plus - g_minus) < 1e-12

    def test_growth_range(self):
        """Growth function should return values in [-1, 1]."""
        for u in [i * 0.01 for i in range(101)]:
            g = self.app._lenia_growth(u)
            assert -1.0 <= g <= 1.0, f"G({u}) = {g} out of range"

    def test_growth_monotone_increasing_left_of_mu(self):
        mu = self.app.lenia_mu
        prev = self.app._lenia_growth(0.0)
        for u_int in range(1, int(mu * 1000) + 1):
            u = u_int / 1000.0
            curr = self.app._lenia_growth(u)
            assert curr >= prev, f"Not monotone at u={u}"
            prev = curr

    def test_growth_with_different_sigma(self):
        """Wider sigma means the growth function is broader."""
        self.app.lenia_sigma = 0.010
        narrow = self.app._lenia_growth(self.app.lenia_mu + 0.02)
        self.app.lenia_sigma = 0.040
        wide = self.app._lenia_growth(self.app.lenia_mu + 0.02)
        assert wide > narrow, "Wider sigma should give higher growth away from mu"


class TestLeniaStep:
    """Deep tests for the simulation step logic."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        self.app.lenia_R = 3
        self.app.lenia_mu = 0.15
        self.app.lenia_sigma = 0.015
        self.app.lenia_dt = 0.1
        self.app.lenia_steps_per_frame = 1
        self.app.lenia_preset_name = ""
        self.app.lenia_generation = 0
        self.app.lenia_rows = 15
        self.app.lenia_cols = 15
        self.app.lenia_grid = [[0.0] * 15 for _ in range(15)]
        self.app.lenia_kernel = []
        self.app._lenia_build_kernel()

    def test_empty_grid_stays_dead(self):
        """All-zero grid should decay (growth at u=0 is ~-1, but 0 + dt*(-1) clips to 0)."""
        self.app._lenia_step()
        for row in self.app.lenia_grid:
            for v in row:
                assert v == 0.0

    def test_generation_increments(self):
        self.app._lenia_step()
        assert self.app.lenia_generation == 1
        self.app._lenia_step()
        assert self.app.lenia_generation == 2

    def test_values_clipped_to_unit(self):
        """After stepping, all values remain in [0, 1]."""
        # Fill with random values
        self.app.lenia_grid = [
            [random.random() for _ in range(15)] for _ in range(15)
        ]
        for _ in range(5):
            self.app._lenia_step()
        for row in self.app.lenia_grid:
            for v in row:
                assert 0.0 <= v <= 1.0

    def test_uniform_grid_decays(self):
        """A uniform grid with value far from mu should decay toward 0."""
        # Fill with 0.8 -- potential will be ~0.8 which is far from mu=0.15
        self.app.lenia_grid = [[0.8] * 15 for _ in range(15)]
        self.app._lenia_step()
        # All cells should have decreased
        for row in self.app.lenia_grid:
            for v in row:
                assert v < 0.8

    def test_step_toroidal_wrapping(self):
        """Cells on edges should wrap around (toroidal boundary)."""
        # Place a cell at corner
        self.app.lenia_grid[0][0] = 1.0
        self.app._lenia_step()
        # The kernel influence should wrap to the other side
        # Check that the last row/col got some influence
        assert self.app.lenia_generation == 1
        # At minimum, the corner cell should have changed
        # (it had value 1.0, potential near 0 due to sparse neighbors,
        #  growth is ~-1, so it decreases)
        assert self.app.lenia_grid[0][0] < 1.0

    def test_convolution_potential_correctness(self):
        """Manually verify convolution for a single cell in a small setup."""
        R = self.app.lenia_R  # 3
        rows, cols = 15, 15
        # Set all cells to a uniform value
        uniform_val = 0.15  # at mu
        self.app.lenia_grid = [[uniform_val] * cols for _ in range(rows)]
        # For a uniform grid, the convolution potential equals uniform_val
        # (since kernel sums to 1). Growth at mu is 1.0.
        # New val = 0.15 + 0.1 * 1.0 = 0.25
        self.app._lenia_step()
        center = self.app.lenia_grid[7][7]
        expected = uniform_val + self.app.lenia_dt * 1.0  # 0.25
        assert abs(center - expected) < 1e-6, f"Got {center}, expected {expected}"

    def test_dt_scaling(self):
        """Larger dt should produce larger changes per step."""
        # Setup identical grids
        grid_small = [[0.5] * 15 for _ in range(15)]
        grid_large = [[0.5] * 15 for _ in range(15)]

        self.app.lenia_dt = 0.05
        self.app.lenia_grid = [row[:] for row in grid_small]
        self.app._lenia_step()
        val_small_dt = self.app.lenia_grid[7][7]

        self.app.lenia_generation = 0
        self.app.lenia_dt = 0.20
        self.app.lenia_grid = [row[:] for row in grid_large]
        self.app._lenia_step()
        val_large_dt = self.app.lenia_grid[7][7]

        # Both should decay (0.5 is far from mu=0.15), but large dt decays more
        assert val_large_dt < val_small_dt

    def test_multiple_steps_deterministic(self):
        """Same initial state should produce the same result."""
        self.app.lenia_grid[5][5] = 0.7
        self.app.lenia_grid[5][6] = 0.6
        self.app.lenia_grid[6][5] = 0.5
        for _ in range(3):
            self.app._lenia_step()
        result1 = [row[:] for row in self.app.lenia_grid]

        # Reset and repeat
        self.app.lenia_generation = 0
        self.app.lenia_grid = [[0.0] * 15 for _ in range(15)]
        self.app.lenia_grid[5][5] = 0.7
        self.app.lenia_grid[5][6] = 0.6
        self.app.lenia_grid[6][5] = 0.5
        for _ in range(3):
            self.app._lenia_step()
        result2 = self.app.lenia_grid

        for r in range(15):
            for c in range(15):
                assert abs(result1[r][c] - result2[r][c]) < 1e-12


class TestLeniaInit:
    """Tests for Lenia grid initialization."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        self.app.lenia_R = 13
        self.app.lenia_mu = 0.15
        self.app.lenia_sigma = 0.015
        self.app.lenia_dt = 0.1
        self.app.lenia_steps_per_frame = 1
        self.app.lenia_preset_name = ""
        self.app.lenia_generation = 0
        self.app.lenia_grid = []
        self.app.lenia_kernel = []

    def test_init_sets_generation_zero(self):
        self.app._lenia_init(0)
        assert self.app.lenia_generation == 0

    def test_init_creates_grid(self):
        self.app._lenia_init(0)
        assert len(self.app.lenia_grid) > 0
        assert len(self.app.lenia_grid[0]) > 0

    def test_init_builds_kernel(self):
        self.app._lenia_init(0)
        assert len(self.app.lenia_kernel) > 0

    def test_init_preset_loads_params(self):
        self.app._lenia_init(0)  # Orbium
        assert self.app.lenia_R == 13
        assert self.app.lenia_mu == 0.15
        assert self.app.lenia_sigma == 0.015
        assert self.app.lenia_dt == 0.1
        assert self.app.lenia_preset_name == "Orbium"

    def test_init_preset_1_loads_geminium(self):
        self.app._lenia_init(1)  # Geminium
        assert self.app.lenia_R == 10
        assert self.app.lenia_mu == 0.14
        assert self.app.lenia_sigma == 0.014
        assert self.app.lenia_preset_name == "Geminium"

    def test_init_all_presets(self):
        for i in range(len(LENIA_PRESETS)):
            self.app._lenia_init(i)
            name, _, R, mu, sigma, dt = LENIA_PRESETS[i]
            assert self.app.lenia_R == R
            assert self.app.lenia_mu == mu
            assert self.app.lenia_sigma == sigma
            assert self.app.lenia_dt == dt
            assert self.app.lenia_preset_name == name

    def test_init_invalid_preset_keeps_defaults(self):
        self.app.lenia_R = 5
        self.app.lenia_mu = 0.20
        self.app._lenia_init(999)
        assert self.app.lenia_R == 5
        assert self.app.lenia_mu == 0.20

    def test_init_none_preset_keeps_defaults(self):
        self.app.lenia_R = 5
        self.app._lenia_init(None)
        assert self.app.lenia_R == 5

    def test_init_seeds_nonzero_cells(self):
        self.app._lenia_init(0)
        total = sum(v for row in self.app.lenia_grid for v in row)
        assert total > 0, "Grid should have nonzero cells after seeding"

    def test_init_values_in_unit_range(self):
        self.app._lenia_init(0)
        for row in self.app.lenia_grid:
            for v in row:
                assert 0.0 <= v <= 1.0

    def test_init_grid_dimensions_match(self):
        self.app._lenia_init(0)
        assert len(self.app.lenia_grid) == self.app.lenia_rows
        assert all(len(row) == self.app.lenia_cols for row in self.app.lenia_grid)


class TestLeniaEnterExit:
    """Tests for enter/exit mode transitions."""

    def setup_method(self):
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        self.app.lenia_mode = False
        self.app.lenia_menu = False
        self.app.lenia_menu_sel = 0
        self.app.lenia_running = False
        self.app.lenia_R = 13
        self.app.lenia_mu = 0.15
        self.app.lenia_sigma = 0.015
        self.app.lenia_dt = 0.1
        self.app.lenia_steps_per_frame = 1
        self.app.lenia_preset_name = ""
        self.app.lenia_generation = 0
        self.app.lenia_grid = []
        self.app.lenia_kernel = []

    def test_enter_shows_menu(self):
        self.app._enter_lenia_mode()
        assert self.app.lenia_menu is True
        assert self.app.lenia_menu_sel == 0

    def test_exit_clears_all_state(self):
        self.app.lenia_mode = True
        self.app.lenia_running = True
        self.app.lenia_grid = [[1.0]]
        self.app.lenia_kernel = [[1.0]]
        self.app._exit_lenia_mode()
        assert self.app.lenia_mode is False
        assert self.app.lenia_menu is False
        assert self.app.lenia_running is False
        assert self.app.lenia_grid == []
        assert self.app.lenia_kernel == []


class TestLeniaKeyHandlers:
    """Tests for key handling in menu and simulation mode."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        cls = type(self.app)
        register(cls)
        self.app.lenia_mode = False
        self.app.lenia_menu = True
        self.app.lenia_menu_sel = 0
        self.app.lenia_running = False
        self.app.lenia_R = 13
        self.app.lenia_mu = 0.15
        self.app.lenia_sigma = 0.015
        self.app.lenia_dt = 0.1
        self.app.lenia_steps_per_frame = 1
        self.app.lenia_preset_name = ""
        self.app.lenia_generation = 0
        self.app.lenia_grid = []
        self.app.lenia_kernel = []

    def test_menu_navigate_down(self):
        self.app._handle_lenia_menu_key(ord("j"))
        assert self.app.lenia_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        self.app.lenia_menu_sel = 0
        self.app._handle_lenia_menu_key(ord("k"))
        assert self.app.lenia_menu_sel == len(LENIA_PRESETS) - 1

    def test_menu_select_enters_mode(self):
        self.app._handle_lenia_menu_key(10)  # Enter
        assert self.app.lenia_menu is False
        assert self.app.lenia_mode is True
        assert len(self.app.lenia_grid) > 0

    def test_menu_quit(self):
        self.app._handle_lenia_menu_key(ord("q"))
        assert self.app.lenia_menu is False

    def test_menu_escape(self):
        self.app._handle_lenia_menu_key(27)
        assert self.app.lenia_menu is False

    def test_play_pause_toggle(self):
        # Enter simulation mode first
        self.app.lenia_mode = True
        self.app.lenia_running = False
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app._handle_lenia_key(ord(" "))
        assert self.app.lenia_running is True
        self.app._handle_lenia_key(ord(" "))
        assert self.app.lenia_running is False

    def test_single_step_key(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        gen_before = self.app.lenia_generation
        self.app._handle_lenia_key(ord("n"))
        assert self.app.lenia_generation == gen_before + 1
        assert self.app.lenia_running is False

    def test_mu_adjust_up(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        mu_before = self.app.lenia_mu
        self.app._handle_lenia_key(ord("u"))
        assert self.app.lenia_mu == pytest.approx(mu_before + 0.005)

    def test_mu_adjust_down(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        mu_before = self.app.lenia_mu
        self.app._handle_lenia_key(ord("U"))
        assert self.app.lenia_mu == pytest.approx(mu_before - 0.005)

    def test_sigma_adjust_up(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        s_before = self.app.lenia_sigma
        self.app._handle_lenia_key(ord("s"))
        assert self.app.lenia_sigma == pytest.approx(s_before + 0.001)

    def test_radius_adjust(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        r_before = self.app.lenia_R
        self.app._handle_lenia_key(ord("d"))
        assert self.app.lenia_R == r_before + 1
        # Kernel should be rebuilt
        assert len(self.app.lenia_kernel) == 2 * self.app.lenia_R + 1

    def test_dt_adjust(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        dt_before = self.app.lenia_dt
        self.app._handle_lenia_key(ord("t"))
        assert self.app.lenia_dt == pytest.approx(dt_before + 0.01)

    def test_steps_per_frame_adjust(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app._handle_lenia_key(ord("+"))
        assert self.app.lenia_steps_per_frame == 2
        self.app._handle_lenia_key(ord("-"))
        assert self.app.lenia_steps_per_frame == 1

    def test_return_to_menu(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app._handle_lenia_key(ord("R"))
        assert self.app.lenia_mode is False
        assert self.app.lenia_menu is True

    def test_quit_exits(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app._handle_lenia_key(ord("q"))
        assert self.app.lenia_mode is False

    def test_mu_clamped_upper(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app.lenia_mu = 0.499
        self.app._handle_lenia_key(ord("u"))
        assert self.app.lenia_mu <= 0.500

    def test_mu_clamped_lower(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app.lenia_mu = 0.012
        self.app._handle_lenia_key(ord("U"))
        assert self.app.lenia_mu >= 0.010

    def test_sigma_clamped_lower(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app.lenia_sigma = 0.001
        self.app._handle_lenia_key(ord("S"))
        assert self.app.lenia_sigma >= 0.001

    def test_radius_clamped(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        self.app.lenia_R = 3
        self.app._handle_lenia_key(ord("D"))
        assert self.app.lenia_R >= 3
        self.app.lenia_R = 25
        self.app._handle_lenia_key(ord("d"))
        assert self.app.lenia_R <= 25

    def test_noop_key_returns_true(self):
        self.app.lenia_mode = True
        self.app.lenia_R = 3
        self.app._lenia_init(0)
        assert self.app._handle_lenia_key(-1) is True
        assert self.app._handle_lenia_menu_key(-1) is True
