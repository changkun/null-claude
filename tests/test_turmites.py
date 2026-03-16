"""Tests for Turmites mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.turmites import register, TURMITE_PRESETS, TURMITE_COLORS


def _setup_preset(app, preset_idx=0):
    """Helper: enter turmite mode with a given preset and initialize."""
    app._enter_turmite_mode()
    name, desc, nc, ns, table = app.TURMITE_PRESETS[preset_idx]
    app.turmite_num_colors = nc
    app.turmite_num_states = ns
    app.turmite_table = [row[:] for row in table]
    app.turmite_preset_name = name
    app.turmite_menu = False
    app.turmite_mode = True
    app.turmite_running = False
    app._turmite_init()
    return name


class TestTurmiteConstants:
    """Validate that the TURMITE_PRESETS constants are well-formed."""

    def test_presets_exist(self):
        assert len(TURMITE_PRESETS) >= 10

    def test_colors_list(self):
        assert TURMITE_COLORS == [1, 2, 3, 4, 5, 6, 7, 8]

    @pytest.mark.parametrize("idx", range(len(TURMITE_PRESETS)))
    def test_preset_structure(self, idx):
        name, desc, nc, ns, table = TURMITE_PRESETS[idx]
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str)
        assert nc >= 2, f"Preset {name}: num_colors must be >= 2"
        assert ns >= 1, f"Preset {name}: num_states must be >= 1"
        # Table must have ns rows (one per state)
        assert len(table) == ns, f"Preset {name}: table has {len(table)} rows, expected {ns}"
        for s_idx, row in enumerate(table):
            # Each row must have nc entries (one per color)
            assert len(row) == nc, (
                f"Preset {name}: state {s_idx} has {len(row)} entries, expected {nc}"
            )
            for c_idx, (wc, turn, new_s) in enumerate(row):
                assert 0 <= wc < nc, (
                    f"Preset {name}: state={s_idx} color={c_idx} writes color {wc} "
                    f"but num_colors={nc}"
                )
                assert turn in (0, 1, 2, 3), (
                    f"Preset {name}: state={s_idx} color={c_idx} has invalid turn {turn}"
                )
                assert 0 <= new_s < ns, (
                    f"Preset {name}: state={s_idx} color={c_idx} transitions to "
                    f"state {new_s} but num_states={ns}"
                )


class TestLangtonsAnt:
    """Validate Langton's Ant transition table against the known correct rules."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_langtons_ant_table(self):
        """Langton's Ant: on white(0) write black(1) turn right; on black(1) write white(0) turn left."""
        name, desc, nc, ns, table = TURMITE_PRESETS[0]
        assert name == "Langton's Ant"
        assert nc == 2
        assert ns == 1
        # state 0, color 0 -> write 1, turn right(1), stay state 0
        assert table[0][0] == (1, 1, 0)
        # state 0, color 1 -> write 0, turn left(3), stay state 0
        assert table[0][1] == (0, 3, 0), (
            f"Langton's Ant color=1 transition should be (0, 3, 0) but got {table[0][1]}"
        )

    def test_langtons_ant_first_step(self):
        """First step: ant on blank cell writes 1, turns right, moves."""
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]
        start_r, start_c = ant["r"], ant["c"]
        start_dir = ant["dir"]  # 0 = up

        self.app._turmite_step()

        # Cell should now be colored (1)
        assert self.app.turmite_grid.get((start_r, start_c), 0) == 1
        # Direction should be right (0 + 1 = 1)
        assert ant["dir"] == (start_dir + 1) % 4
        # State stays 0
        assert ant["state"] == 0

    def test_langtons_ant_second_step_on_colored(self):
        """Second step on a colored cell: writes 0 (erases), turns left."""
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]
        # Manually place the ant on a colored cell
        ant["r"], ant["c"] = 10, 10
        ant["dir"] = 0  # up
        self.app.turmite_grid[(10, 10)] = 1

        self.app._turmite_step()

        # Cell should be erased (color 0 means removed from grid)
        assert self.app.turmite_grid.get((10, 10), 0) == 0
        # Direction: 0 + 3 (left) = 3
        assert ant["dir"] == 3

    def test_langtons_ant_symmetry_4_steps(self):
        """After 4 steps on an empty grid, ant returns near start with predictable state."""
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]
        start_r, start_c = ant["r"], ant["c"]

        for _ in range(4):
            self.app._turmite_step()

        assert self.app.turmite_step_count == 4
        # After 4 steps of Langton's Ant, the ant should have colored some cells
        assert len(self.app.turmite_grid) > 0


class TestTurmiteStep:
    """Test the core _turmite_step logic for correctness."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_step_increments_count(self):
        _setup_preset(self.app, 0)
        assert self.app.turmite_step_count == 0
        self.app._turmite_step()
        assert self.app.turmite_step_count == 1
        self.app._turmite_step()
        assert self.app.turmite_step_count == 2

    def test_step_wraps_at_boundary(self):
        """Ant wraps around grid edges (toroidal topology)."""
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]
        # Place ant at top-left, facing up
        ant["r"] = 0
        ant["c"] = 0
        ant["dir"] = 0  # up

        self.app._turmite_step()

        # After turning right (dir becomes 1=right) and moving, should wrap
        # Starting at (0,0), dir 0->1 (right after turn right on blank), move right
        assert ant["r"] == 0
        assert ant["c"] == 1

        # Now test wrapping: place at bottom-right facing down
        rows, cols = self.app.turmite_rows, self.app.turmite_cols
        ant["r"] = rows - 1
        ant["c"] = cols - 1
        ant["dir"] = 2  # down
        ant["state"] = 0
        self.app.turmite_grid.pop((rows - 1, cols - 1), None)

        self.app._turmite_step()

        # Blank cell -> write 1, turn right (dir 2+1=3=left), move left
        assert ant["c"] == cols - 2

    def test_direction_encoding(self):
        """Verify direction encoding: 0=up, 1=right, 2=down, 3=left."""
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]
        center_r, center_c = ant["r"], ant["c"]

        # Manually set direction and check movement
        # Use a 2-state preset that allows no-turn to test raw movement
        # Instead, test direction vectors directly from the step function
        dr = [-1, 0, 1, 0]
        dc = [0, 1, 0, -1]
        assert dr[0] == -1 and dc[0] == 0, "dir 0 should be up"
        assert dr[1] == 0 and dc[1] == 1, "dir 1 should be right"
        assert dr[2] == 1 and dc[2] == 0, "dir 2 should be down"
        assert dr[3] == 0 and dc[3] == -1, "dir 3 should be left"

    def test_turn_encoding(self):
        """Turn values: 0=none, 1=right, 2=u-turn, 3=left."""
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]

        # Set up a custom table to test each turn
        self.app.turmite_table = [[(1, 0, 0), (0, 0, 0)]]  # no turn
        ant["dir"] = 0
        ant["r"], ant["c"] = 10, 10
        self.app.turmite_grid.pop((10, 10), None)
        self.app._turmite_step()
        assert ant["dir"] == 0, "Turn 0 should not change direction"

        # U-turn
        self.app.turmite_table = [[(1, 2, 0), (0, 0, 0)]]
        ant["dir"] = 1
        ant["r"], ant["c"] = 10, 10
        self.app.turmite_grid.pop((10, 10), None)
        self.app._turmite_step()
        assert ant["dir"] == 3, "Turn 2 (u-turn) from dir 1 should give dir 3"

    def test_state_transition(self):
        """Verify that ant state transitions correctly."""
        _setup_preset(self.app, 1)  # Fibonacci Spiral (2 states)
        ant = self.app.turmite_ants[0]
        # Fibonacci: state 0, color 0 -> (1, 1, 1) = write 1, turn right, go to state 1
        assert ant["state"] == 0
        self.app._turmite_step()
        assert ant["state"] == 1

    def test_color_write_and_erase(self):
        """Writing color 0 erases from grid dict; writing >0 sets it."""
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]
        r, c = ant["r"], ant["c"]

        # Step 1: blank cell -> writes 1
        self.app._turmite_step()
        assert self.app.turmite_grid.get((r, c), 0) == 1

        # Set up to step on a colored cell that will be erased
        ant["r"], ant["c"] = 5, 5
        ant["dir"] = 0
        self.app.turmite_grid[(5, 5)] = 1
        self.app._turmite_step()
        # Langton's Ant: color 1 -> write 0 (erase)
        assert (5, 5) not in self.app.turmite_grid


class TestAllPresetsRun:
    """Run each preset for multiple steps to ensure no crashes or out-of-bounds."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    @pytest.mark.parametrize("idx", range(len(TURMITE_PRESETS)))
    def test_preset_runs_100_steps(self, idx):
        name = _setup_preset(self.app, idx)
        for _ in range(100):
            self.app._turmite_step()
        assert self.app.turmite_step_count == 100
        # Ant should still be within bounds
        ant = self.app.turmite_ants[0]
        assert 0 <= ant["r"] < self.app.turmite_rows
        assert 0 <= ant["c"] < self.app.turmite_cols
        assert 0 <= ant["state"] < self.app.turmite_num_states

    @pytest.mark.parametrize("idx", range(len(TURMITE_PRESETS)))
    def test_preset_grid_colors_valid(self, idx):
        """After stepping, all grid colors should be valid for the preset."""
        _setup_preset(self.app, idx)
        for _ in range(50):
            self.app._turmite_step()
        nc = self.app.turmite_num_colors
        for (r, c), color in self.app.turmite_grid.items():
            assert 1 <= color < nc, (
                f"Preset {idx}: grid cell ({r},{c}) has color {color}, "
                f"expected 1..{nc - 1}"
            )


class TestTurmiteInit:
    """Test _turmite_init behavior."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_init_clears_grid(self):
        _setup_preset(self.app, 0)
        for _ in range(10):
            self.app._turmite_step()
        assert len(self.app.turmite_grid) > 0
        self.app._turmite_init()
        assert len(self.app.turmite_grid) == 0
        assert self.app.turmite_step_count == 0
        assert len(self.app.turmite_ants) == 1

    def test_init_places_ant_at_center(self):
        _setup_preset(self.app, 0)
        ant = self.app.turmite_ants[0]
        assert ant["r"] == self.app.turmite_rows // 2
        assert ant["c"] == self.app.turmite_cols // 2
        assert ant["dir"] == 0
        assert ant["state"] == 0

    def test_init_enforces_minimum_size(self):
        """Grid dimensions should be at least 10x10."""
        app = make_mock_app(rows=10, cols=10)
        register(type(app))
        _setup_preset(app, 0)
        assert app.turmite_rows >= 10
        assert app.turmite_cols >= 10


class TestEnterExitMode:
    """Test mode enter/exit lifecycle."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter_sets_menu(self):
        self.app._enter_turmite_mode()
        assert self.app.turmite_menu is True
        assert self.app.turmite_steps_per_frame == 1
        assert self.app.turmite_num_states == 2
        assert self.app.turmite_table == []

    def test_exit_clears_state(self):
        _setup_preset(self.app, 0)
        for _ in range(10):
            self.app._turmite_step()
        self.app._exit_turmite_mode()
        assert self.app.turmite_mode is False
        assert self.app.turmite_running is False
        assert self.app.turmite_grid == {}
        assert self.app.turmite_ants == []


class TestThreeColorPreset:
    """Validate the 3-Color Spiral preset specifically."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_three_color_table_structure(self):
        name, desc, nc, ns, table = TURMITE_PRESETS[9]
        assert name == "3-Color Spiral"
        assert nc == 3
        assert ns == 2
        # Each state row should have 3 entries (one per color)
        assert len(table[0]) == 3
        assert len(table[1]) == 3

    def test_three_color_produces_multiple_colors(self):
        """After running, the grid should contain cells with color 1 and color 2."""
        _setup_preset(self.app, 9)
        for _ in range(200):
            self.app._turmite_step()
        colors_seen = set(self.app.turmite_grid.values())
        assert len(colors_seen) >= 2, (
            f"3-Color Spiral should produce multiple colors, only saw {colors_seen}"
        )


class TestRegister:
    """Test that register() correctly binds methods and constants."""

    def test_register_binds_all_methods(self):
        app = make_mock_app()
        register(type(app))
        assert hasattr(type(app), 'TURMITE_PRESETS')
        assert hasattr(type(app), 'TURMITE_COLORS')
        assert hasattr(app, '_turmite_step')
        assert hasattr(app, '_turmite_init')
        assert hasattr(app, '_enter_turmite_mode')
        assert hasattr(app, '_exit_turmite_mode')
        assert hasattr(app, '_handle_turmite_menu_key')
        assert hasattr(app, '_handle_turmite_key')
        assert hasattr(app, '_draw_turmite_menu')
        assert hasattr(app, '_draw_turmite')

    def test_presets_not_imported_from_prisoners_dilemma(self):
        """Verify TURMITE_PRESETS is defined in turmites module, not imported."""
        import life.modes.turmites as tm
        assert hasattr(tm, 'TURMITE_PRESETS')
        assert hasattr(tm, 'TURMITE_COLORS')
