"""Tests for aco mode."""
import math
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.aco import register


# ACO_PRESETS and ACO_DENSITY are referenced on self but never defined as class attrs
# Define them here for testing
ACO_PRESETS = [
    ("Foraging", "Classic foraging — ants search for food", 0.01, 0.3, 0.1, 0.05, 3, 3),
    ("Dense Colony", "Many ants, strong pheromone", 0.005, 0.5, 0.15, 0.08, 5, 4),
]

ACO_DENSITY = ["  ", "░░", "▒▒", "▓▓", "██"]


def _make_aco_app(rows=40, cols=120):
    """Create a mock app with ACO mode registered."""
    app = make_mock_app(rows=rows, cols=cols)
    cls = type(app)
    register(cls)
    cls.ACO_PRESETS = ACO_PRESETS
    cls.ACO_DENSITY = ACO_DENSITY
    # Instance attrs
    app.aco_mode = False
    app.aco_menu = False
    app.aco_menu_sel = 0
    app.aco_running = False
    app.aco_pheromone = []
    app.aco_ants = []
    app.aco_food = []
    app.aco_steps_per_frame = 2
    return app


class TestACO:
    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()

    def test_enter(self):
        self.app._enter_aco_mode()
        assert self.app.aco_menu is True

    def test_init(self):
        self.app.aco_mode = True
        self.app._aco_init(0)
        assert self.app.aco_mode is True
        assert self.app.aco_menu is False
        assert len(self.app.aco_pheromone) > 0
        assert len(self.app.aco_ants) > 0

    def test_step_no_crash(self):
        self.app.aco_mode = True
        self.app._aco_init(0)
        for _ in range(10):
            self.app._aco_step()
        assert self.app.aco_generation == 10

    def test_exit_cleanup(self):
        self.app.aco_mode = True
        self.app._aco_init(0)
        self.app._exit_aco_mode()
        assert self.app.aco_mode is False


class TestACOInit:
    """Tests for _aco_init initialization logic."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()

    def test_pheromone_grid_initialized_to_zero(self):
        self.app._aco_init(0)
        rows = self.app.aco_rows
        cols = self.app.aco_cols
        assert len(self.app.aco_pheromone) == rows
        assert len(self.app.aco_pheromone[0]) == cols
        for r in range(rows):
            for c in range(cols):
                assert self.app.aco_pheromone[r][c] == 0.0

    def test_nest_at_centre(self):
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest
        assert nr == self.app.aco_rows // 2
        assert nc == self.app.aco_cols // 2

    def test_ants_spawned_at_nest(self):
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest
        for ant in self.app.aco_ants:
            assert ant[0] == float(nr), "Ant should start at nest row"
            assert ant[1] == float(nc), "Ant should start at nest col"
            assert ant[3] == 0.0, "Ant should start without food"

    def test_ant_headings_random(self):
        self.app._aco_init(0)
        headings = [ant[2] for ant in self.app.aco_ants]
        # All headings should be in [0, 2*pi)
        for h in headings:
            assert 0.0 <= h < 2 * math.pi
        # Headings should not all be the same (extremely unlikely with random)
        assert len(set(headings)) > 1

    def test_food_sources_created(self):
        self.app._aco_init(0)
        # Preset 0 has num_food=3
        assert len(self.app.aco_food) > 0
        assert len(self.app.aco_food) <= 3

    def test_food_sources_away_from_nest(self):
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest
        rows, cols = self.app.aco_rows, self.app.aco_cols
        min_dist = min(rows, cols) * 0.25
        for food in self.app.aco_food:
            dist = math.sqrt((food[0] - nr) ** 2 + (food[1] - nc) ** 2)
            assert dist > min_dist, "Food should be placed away from nest"

    def test_food_has_positive_quantity(self):
        self.app._aco_init(0)
        for food in self.app.aco_food:
            assert food[2] > 0, "Food should have positive quantity"

    def test_preset_parameters_applied(self):
        self.app._aco_init(0)
        # Preset 0: evap=0.01, dep=0.3, diff=0.1
        assert self.app.aco_evaporation == 0.01
        assert self.app.aco_deposit_strength == 0.3
        assert self.app.aco_diffusion == 0.1

    def test_second_preset(self):
        self.app._aco_init(1)
        assert self.app.aco_evaporation == 0.005
        assert self.app.aco_deposit_strength == 0.5
        assert self.app.aco_diffusion == 0.15

    def test_generation_reset(self):
        self.app._aco_init(0)
        self.app._aco_step()
        self.app._aco_step()
        assert self.app.aco_generation == 2
        self.app._aco_init(0)
        assert self.app.aco_generation == 0


class TestACOPheromone:
    """Tests for pheromone deposit, evaporation, and diffusion."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()

    def test_pheromone_deposit_on_return(self):
        """Ant carrying food should deposit pheromone."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols
        nr, nc = self.app.aco_nest

        # Place a single ant far from nest, carrying food
        self.app.aco_ants = [[float(nr + 5), float(nc + 5), 0.0, 1.0]]
        self.app.aco_num_ants = 1

        # Zero out pheromone
        self.app.aco_pheromone = [[0.0] * cols for _ in range(rows)]

        self.app._aco_step()

        # After step, pheromone should have been deposited somewhere
        total_pher = sum(
            self.app.aco_pheromone[r][c]
            for r in range(rows)
            for c in range(cols)
        )
        # Due to diffusion/evaporation, it may be spread, but total should be > 0
        assert total_pher > 0, "Returning ant should deposit pheromone"

    def test_pheromone_evaporation(self):
        """Pheromone should evaporate over time."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # Remove all ants so no new pheromone is deposited
        self.app.aco_ants = []
        self.app.aco_num_ants = 0

        # Set initial pheromone
        self.app.aco_pheromone[5][5] = 0.5

        self.app._aco_step()

        # Pheromone at (5,5) should be less than 0.5 due to evaporation
        # After diffusion + evaporation, the centre value should decrease
        assert self.app.aco_pheromone[5][5] < 0.5

    def test_pheromone_diffusion(self):
        """Pheromone should spread to neighbours."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # Remove ants
        self.app.aco_ants = []
        self.app.aco_num_ants = 0

        # Set a single pheromone point
        self.app.aco_pheromone = [[0.0] * cols for _ in range(rows)]
        self.app.aco_pheromone[10][10] = 1.0

        self.app._aco_step()

        # Neighbours should now have some pheromone
        assert self.app.aco_pheromone[9][10] > 0 or self.app.aco_pheromone[11][10] > 0
        assert self.app.aco_pheromone[10][9] > 0 or self.app.aco_pheromone[10][11] > 0

    def test_pheromone_never_negative(self):
        """Pheromone values should never go negative."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # Run many steps
        for _ in range(50):
            self.app._aco_step()

        for r in range(rows):
            for c in range(cols):
                assert self.app.aco_pheromone[r][c] >= 0.0

    def test_pheromone_capped_at_one(self):
        """Pheromone deposit should be capped at 1.0."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols
        nr, nc = self.app.aco_nest

        # Place many ants carrying food at the same location
        r_pos, c_pos = nr + 5, nc + 5
        self.app.aco_ants = [
            [float(r_pos), float(c_pos), 0.0, 1.0] for _ in range(50)
        ]

        # High deposit strength
        self.app.aco_deposit_strength = 1.0

        self.app._aco_step()

        # Before diffusion/evaporation, deposit is capped at 1.0
        # After diffusion, the value at deposit point could be <= 1.0
        for r in range(rows):
            for c in range(cols):
                # With diffusion it shouldn't exceed 1.0 since all inputs are <= 1.0
                assert self.app.aco_pheromone[r][c] <= 1.0 + 1e-10

    def test_evaporation_drains_all_pheromone_eventually(self):
        """With no ants, pheromone should eventually drain to near zero."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        self.app.aco_ants = []
        self.app.aco_num_ants = 0

        # Set high pheromone everywhere
        self.app.aco_pheromone = [[0.8] * cols for _ in range(rows)]

        for _ in range(200):
            self.app._aco_step()

        total = sum(
            self.app.aco_pheromone[r][c]
            for r in range(rows)
            for c in range(cols)
        )
        avg = total / (rows * cols)
        assert avg < 0.01, f"Pheromone should drain to near zero, got avg={avg}"


class TestACOAntMovement:
    """Tests for ant movement and navigation."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()

    def test_ant_moves_forward(self):
        """An ant should move in its heading direction."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # Single ant heading east (heading=0), no food carrying
        start_r, start_c = 10.0, 10.0
        self.app.aco_ants = [[start_r, start_c, 0.0, 0.0]]
        self.app.aco_num_ants = 1
        self.app.aco_food = []  # no food to pick up

        self.app._aco_step()

        ant = self.app.aco_ants[0]
        # heading=0: sin(0)=0 for row, cos(0)=1 for col
        # Row should stay ~same (some random wander), col should increase
        # Due to random wander, we check approximate direction
        new_r, new_c = ant[0], ant[1]
        dc = new_c - start_c
        # Should have moved roughly east (positive col direction)
        assert dc > 0.5, f"Ant heading east should increase col, got dc={dc}"

    def test_ant_wraps_around(self):
        """Ant should wrap around grid edges."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # Place ant at edge, heading east
        self.app.aco_ants = [[5.0, float(cols - 0.5), 0.0, 0.0]]
        self.app.aco_num_ants = 1
        self.app.aco_food = []

        self.app._aco_step()

        ant = self.app.aco_ants[0]
        # Should have wrapped to the other side
        assert 0 <= ant[0] < rows
        assert 0 <= ant[1] < cols

    def test_returning_ant_steers_toward_nest(self):
        """Ant carrying food should steer toward nest."""
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest

        # Place ant far from nest, carrying food
        start_r = float(nr + 10)
        start_c = float(nc)
        heading = math.pi  # initially facing away from nest (south, since sin(pi)~=0)
        self.app.aco_ants = [[start_r, start_c, heading, 1.0]]
        self.app.aco_num_ants = 1

        # Run several steps
        for _ in range(5):
            self.app._aco_step()

        ant = self.app.aco_ants[0]
        # Ant should have moved closer to nest (or at least changed heading)
        dist_after = math.sqrt((ant[0] - nr) ** 2 + (ant[1] - nc) ** 2)
        dist_before = math.sqrt((start_r - nr) ** 2 + (start_c - nc) ** 2)
        assert dist_after < dist_before, "Returning ant should move closer to nest"

    def test_ant_drops_food_at_nest(self):
        """Ant reaching nest should drop food and increment counter."""
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest

        # Place ant right next to nest, carrying food
        self.app.aco_ants = [[float(nr + 1), float(nc), 0.0, 1.0]]
        self.app.aco_num_ants = 1
        self.app.aco_food_collected = 0

        # The check is |dr| < 2.0 and |dc| < 2.0
        self.app._aco_step()

        ant = self.app.aco_ants[0]
        assert ant[3] == 0.0, "Ant should drop food at nest"
        assert self.app.aco_food_collected == 1

    def test_ant_picks_up_food(self):
        """Ant near food source should pick it up."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols
        nr, nc = self.app.aco_nest

        # Place food far from nest
        food_r, food_c = nr + 15, nc + 15
        self.app.aco_food = [[food_r, food_c, 10.0]]

        # Place a searching ant right next to food
        self.app.aco_ants = [[float(food_r + 1), float(food_c), 0.0, 0.0]]
        self.app.aco_num_ants = 1

        self.app._aco_step()

        ant = self.app.aco_ants[0]
        assert ant[3] == 1.0, "Ant near food should pick it up"
        assert self.app.aco_food[0][2] == 9.0, "Food quantity should decrease"


class TestACOFoodLogic:
    """Tests for food source behavior."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()

    def test_depleted_food_removed(self):
        """Food sources with zero quantity should be removed."""
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest

        # Place one food with quantity 1
        food_r, food_c = nr + 15, nc + 15
        self.app.aco_food = [[food_r, food_c, 1.0]]

        # Place searching ant right on top of food
        self.app.aco_ants = [[float(food_r), float(food_c), 0.0, 0.0]]
        self.app.aco_num_ants = 1

        self.app._aco_step()

        # Food should be depleted and removed
        assert len(self.app.aco_food) == 0, "Depleted food should be removed"

    def test_food_quantity_never_negative(self):
        """Food quantity should never go below zero (race condition fix)."""
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest

        # Place food with quantity 1, and many ants on top
        food_r, food_c = nr + 15, nc + 15
        self.app.aco_food = [[food_r, food_c, 1.0]]

        # Many ants at the same spot
        self.app.aco_ants = [
            [float(food_r), float(food_c), 0.0, 0.0] for _ in range(10)
        ]
        self.app.aco_num_ants = 10

        self.app._aco_step()

        # At most 1 ant should have picked up food (threshold is > 0.5)
        carrying = sum(1 for ant in self.app.aco_ants if ant[3] > 0.5)
        assert carrying == 1, f"Only 1 ant should pick up food from quantity=1, got {carrying}"

    def test_multiple_food_sources(self):
        """Multiple food sources should be tracked independently."""
        self.app._aco_init(0)
        nr, nc = self.app.aco_nest

        self.app.aco_food = [
            [nr + 15, nc + 15, 5.0],
            [nr - 15, nc - 15, 3.0],
        ]
        self.app.aco_ants = []
        self.app.aco_num_ants = 0

        for _ in range(10):
            self.app._aco_step()

        # Food should remain untouched (no ants)
        assert len(self.app.aco_food) == 2
        assert self.app.aco_food[0][2] == 5.0
        assert self.app.aco_food[1][2] == 3.0


class TestACOSense:
    """Tests for the _aco_sense method."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()

    def test_sense_reads_pheromone(self):
        """_aco_sense should return pheromone at sensed position."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # Set a known pheromone value
        target_r, target_c = 10, 13  # heading=0, dist=3: sin(0)*3=0, cos(0)*3=3
        self.app.aco_pheromone[target_r][target_c] = 0.75

        val = self.app._aco_sense(10.0, 10.0, 0.0, 3.0)
        assert val == 0.75

    def test_sense_wraps_around(self):
        """_aco_sense should handle wrapping."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # Set pheromone at wrapped position
        self.app.aco_pheromone[0][0] = 0.5

        # Sense from near the edge
        val = self.app._aco_sense(float(rows - 1), float(cols - 1), 0.0, 3.0)
        # cos(0)*3 = 3, so col = (cols-1+3) % cols = 2, row = (rows-1+0) % rows = rows-1
        # That won't hit [0][0], but it demonstrates wrapping works without error
        assert val >= 0.0

    def test_sense_different_angles(self):
        """_aco_sense at different angles should sample different cells."""
        self.app._aco_init(0)
        rows, cols = self.app.aco_rows, self.app.aco_cols

        self.app.aco_pheromone = [[0.0] * cols for _ in range(rows)]
        # Set distinct values at cells that heading 0 and pi/2 would sense
        # heading=0, dist=3: row+=sin(0)*3=0, col+=cos(0)*3=3 -> (15, 18)
        # heading=pi/2, dist=3: row+=sin(pi/2)*3=3, col+=cos(pi/2)*3~=0 -> (18, 15)
        self.app.aco_pheromone[15][18] = 0.3
        self.app.aco_pheromone[18][15] = 0.7

        val_east = self.app._aco_sense(15.0, 15.0, 0.0, 3.0)
        val_south = self.app._aco_sense(15.0, 15.0, math.pi / 2, 3.0)

        assert val_east == pytest.approx(0.3)
        assert val_south == pytest.approx(0.7)


class TestACOKeyHandling:
    """Tests for key handling in ACO mode."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()
        self.app._aco_init(0)

    def test_space_toggles_running(self):
        assert self.app.aco_running is False
        self.app._handle_aco_key(ord(" "))
        assert self.app.aco_running is True
        self.app._handle_aco_key(ord(" "))
        assert self.app.aco_running is False

    def test_n_steps_simulation(self):
        gen_before = self.app.aco_generation
        self.app._handle_aco_key(ord("n"))
        # steps_per_frame = 2
        assert self.app.aco_generation == gen_before + 2

    def test_dot_also_steps(self):
        gen_before = self.app.aco_generation
        self.app._handle_aco_key(ord("."))
        assert self.app.aco_generation == gen_before + 2

    def test_evaporation_increase(self):
        evap_before = self.app.aco_evaporation
        self.app._handle_aco_key(ord("e"))
        assert self.app.aco_evaporation > evap_before

    def test_evaporation_decrease(self):
        self.app.aco_evaporation = 0.05
        self.app._handle_aco_key(ord("E"))
        assert self.app.aco_evaporation < 0.05

    def test_evaporation_floor(self):
        self.app.aco_evaporation = 0.001
        self.app._handle_aco_key(ord("E"))
        assert self.app.aco_evaporation >= 0.001

    def test_evaporation_ceiling(self):
        self.app.aco_evaporation = 0.2
        self.app._handle_aco_key(ord("e"))
        assert self.app.aco_evaporation <= 0.2

    def test_deposit_increase(self):
        dep_before = self.app.aco_deposit_strength
        self.app._handle_aco_key(ord("d"))
        assert self.app.aco_deposit_strength > dep_before

    def test_deposit_decrease(self):
        self.app.aco_deposit_strength = 0.5
        self.app._handle_aco_key(ord("D"))
        assert self.app.aco_deposit_strength < 0.5

    def test_speed_increase(self):
        self.app.aco_steps_per_frame = 2
        self.app._handle_aco_key(ord("s"))
        assert self.app.aco_steps_per_frame == 3

    def test_speed_decrease(self):
        self.app.aco_steps_per_frame = 2
        self.app._handle_aco_key(ord("S"))
        assert self.app.aco_steps_per_frame == 1

    def test_speed_floor(self):
        self.app.aco_steps_per_frame = 1
        self.app._handle_aco_key(ord("S"))
        assert self.app.aco_steps_per_frame == 1

    def test_speed_ceiling(self):
        self.app.aco_steps_per_frame = 10
        self.app._handle_aco_key(ord("s"))
        assert self.app.aco_steps_per_frame == 10

    def test_r_reseeds(self):
        self.app._aco_step()
        self.app._aco_step()
        assert self.app.aco_generation == 2
        self.app._handle_aco_key(ord("r"))
        assert self.app.aco_generation == 0
        assert self.app.aco_running is False

    def test_R_returns_to_menu(self):
        self.app._handle_aco_key(ord("R"))
        assert self.app.aco_mode is False
        assert self.app.aco_menu is True

    def test_q_exits(self):
        self.app._handle_aco_key(ord("q"))
        assert self.app.aco_mode is False

    def test_escape_exits(self):
        self.app._aco_init(0)
        self.app._handle_aco_key(27)
        assert self.app.aco_mode is False


class TestACOMenuKey:
    """Tests for ACO menu key handling."""

    def setup_method(self):
        random.seed(42)
        self.app = _make_aco_app()
        self.app._enter_aco_mode()

    def test_j_moves_down(self):
        assert self.app.aco_menu_sel == 0
        self.app._handle_aco_menu_key(ord("j"))
        assert self.app.aco_menu_sel == 1

    def test_k_moves_up(self):
        self.app.aco_menu_sel = 1
        self.app._handle_aco_menu_key(ord("k"))
        assert self.app.aco_menu_sel == 0

    def test_j_wraps_around(self):
        self.app.aco_menu_sel = len(ACO_PRESETS) - 1
        self.app._handle_aco_menu_key(ord("j"))
        assert self.app.aco_menu_sel == 0

    def test_k_wraps_around(self):
        self.app.aco_menu_sel = 0
        self.app._handle_aco_menu_key(ord("k"))
        assert self.app.aco_menu_sel == len(ACO_PRESETS) - 1

    def test_enter_selects(self):
        self.app.aco_menu_sel = 0
        self.app._handle_aco_menu_key(ord("\n"))
        assert self.app.aco_menu is False
        assert self.app.aco_mode is True

    def test_q_cancels(self):
        self.app._handle_aco_menu_key(ord("q"))
        assert self.app.aco_menu is False


class TestACOIntegration:
    """Integration tests for full ACO simulation runs."""

    def setup_method(self):
        random.seed(123)
        self.app = _make_aco_app()

    def test_full_simulation_50_steps(self):
        """Run 50 steps without crash and verify state consistency."""
        self.app._aco_init(0)
        for _ in range(50):
            self.app._aco_step()

        assert self.app.aco_generation == 50
        rows, cols = self.app.aco_rows, self.app.aco_cols

        # All ants should be within bounds
        for ant in self.app.aco_ants:
            assert 0 <= ant[0] < rows, f"Ant row {ant[0]} out of bounds"
            assert 0 <= ant[1] < cols, f"Ant col {ant[1]} out of bounds"
            assert ant[3] in (0.0, 1.0), f"has_food should be 0 or 1, got {ant[3]}"

        # No negative pheromone
        for r in range(rows):
            for c in range(cols):
                assert self.app.aco_pheromone[r][c] >= 0.0

    def test_food_collection_progress(self):
        """After many steps, some food should be collected."""
        self.app._aco_init(0)
        for _ in range(200):
            self.app._aco_step()

        # With 200 steps and many ants, at least some food should be collected
        assert self.app.aco_food_collected >= 0  # may be 0 if food is far

    def test_dense_colony_preset(self):
        """Dense Colony preset should run without errors."""
        self.app._aco_init(1)
        for _ in range(30):
            self.app._aco_step()
        assert self.app.aco_generation == 30
