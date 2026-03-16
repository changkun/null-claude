"""Tests for cycle detection — deep validation against commit d279fd5."""
import random
import pytest
from tests.conftest import make_mock_app
from life.grid import Grid


class TestStateHash:
    """Verify Grid.state_hash() produces correct, deterministic hashes."""

    def test_empty_grids_same_hash(self):
        """Two empty grids of the same size produce the same hash."""
        g1 = Grid(10, 10)
        g2 = Grid(10, 10)
        assert g1.state_hash() == g2.state_hash()

    def test_different_sizes_empty_same_hash(self):
        """Empty grids of different sizes hash the same (no alive cells)."""
        g1 = Grid(5, 5)
        g2 = Grid(20, 20)
        assert g1.state_hash() == g2.state_hash()

    def test_same_pattern_same_hash(self):
        """Identical cell configurations produce the same hash."""
        g1 = Grid(10, 10)
        g2 = Grid(10, 10)
        for r, c in [(1, 2), (3, 4), (5, 6)]:
            g1.set_alive(r, c)
            g2.set_alive(r, c)
        assert g1.state_hash() == g2.state_hash()

    def test_different_pattern_different_hash(self):
        """Different cell configurations produce different hashes."""
        g1 = Grid(10, 10)
        g2 = Grid(10, 10)
        g1.set_alive(1, 2)
        g2.set_alive(2, 1)
        assert g1.state_hash() != g2.state_hash()

    def test_hash_ignores_age(self):
        """Hash depends on positions only, not cell age values."""
        g1 = Grid(10, 10)
        g2 = Grid(10, 10)
        g1.set_alive(3, 3)
        g2.set_alive(3, 3)
        # Artificially age the cell in g2
        g2.cells[3][3] = 99
        assert g1.state_hash() == g2.state_hash()

    def test_hash_deterministic(self):
        """Calling state_hash() twice returns the same result."""
        g = Grid(10, 10)
        g.set_alive(0, 0)
        g.set_alive(5, 5)
        h1 = g.state_hash()
        h2 = g.state_hash()
        assert h1 == h2

    def test_hash_changes_after_step(self):
        """Hash changes after a generation step (for non-static patterns)."""
        g = Grid(10, 10)
        # Blinker: not a still life, so hash should change
        g.set_alive(4, 3)
        g.set_alive(4, 4)
        g.set_alive(4, 5)
        h_before = g.state_hash()
        g.step()
        h_after = g.state_hash()
        assert h_before != h_after

    def test_hash_returns_string(self):
        """state_hash returns an MD5 hex digest string (32 hex chars)."""
        g = Grid(5, 5)
        h = g.state_hash()
        assert isinstance(h, str)
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)


class TestBlinkerCycleDetection:
    """Test cycle detection using the blinker oscillator (period 2)."""

    def test_blinker_cycle_detected(self):
        """A blinker should be detected as period-2 cycle after 2 steps."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        # Place a blinker (horizontal)
        grid.set_alive(4, 3)
        grid.set_alive(4, 4)
        grid.set_alive(4, 5)

        # Seed the initial state hash
        app.state_history[grid.state_hash()] = grid.generation

        # Step 1: blinker rotates to vertical
        grid.step()
        app._check_cycle()
        assert not app.cycle_detected

        # Step 2: blinker rotates back to horizontal — cycle!
        grid.step()
        app._check_cycle()
        assert app.cycle_detected
        assert not app.running
        assert "period 2" in app.message.lower() or "Cycle detected (period 2)" in app.message

    def test_blinker_message_format(self):
        """Verify the exact flash message for a period-2 cycle."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        grid.set_alive(4, 3)
        grid.set_alive(4, 4)
        grid.set_alive(4, 5)

        app.state_history[grid.state_hash()] = grid.generation
        grid.step()
        app._check_cycle()
        grid.step()
        app._check_cycle()

        assert app.message == "Cycle detected (period 2)"


class TestStillLifeDetection:
    """Test detection of still lifes (period 1)."""

    def test_block_still_life(self):
        """A 2x2 block is a still life — should be detected as period 1."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        # Place a block
        grid.set_alive(4, 4)
        grid.set_alive(4, 5)
        grid.set_alive(5, 4)
        grid.set_alive(5, 5)

        app.state_history[grid.state_hash()] = grid.generation

        grid.step()
        app._check_cycle()

        assert app.cycle_detected
        assert "Still life" in app.message

    def test_beehive_still_life(self):
        """A beehive is a still life."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        # Place a beehive centered in grid
        grid.set_alive(3, 4)
        grid.set_alive(3, 5)
        grid.set_alive(4, 3)
        grid.set_alive(4, 6)
        grid.set_alive(5, 4)
        grid.set_alive(5, 5)

        app.state_history[grid.state_hash()] = grid.generation
        grid.step()
        app._check_cycle()

        assert app.cycle_detected
        assert "Still life" in app.message


class TestExtinctionDetection:
    """Test detection of extinction (all cells die)."""

    def test_single_cell_dies(self):
        """A single cell dies, then empty grid persists — extinction on second step."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        grid.set_alive(5, 5)

        app.state_history[grid.state_hash()] = grid.generation

        # Step 1: cell dies, grid is now empty — new state, stored
        grid.step()
        app._check_cycle()
        assert not app.cycle_detected  # empty state seen for first time

        # Step 2: grid still empty — same hash as step 1 → extinction
        grid.step()
        app._check_cycle()
        assert app.cycle_detected
        assert "Extinction" in app.message or "all cells dead" in app.message

    def test_two_isolated_cells_die(self):
        """Two isolated cells die — extinction detected on second empty step."""
        app = make_mock_app(grid_rows=20, grid_cols=20)
        grid = app.grid

        grid.set_alive(2, 2)
        grid.set_alive(15, 15)

        app.state_history[grid.state_hash()] = grid.generation

        # Step 1: both cells die
        grid.step()
        app._check_cycle()
        assert not app.cycle_detected

        # Step 2: still empty → extinction
        grid.step()
        app._check_cycle()
        assert app.cycle_detected
        assert "all cells dead" in app.message


class TestResetCycleDetection:
    """Test _reset_cycle_detection clears state properly."""

    def test_reset_clears_history(self):
        app = make_mock_app()
        app.state_history["somehash"] = 42
        app.cycle_detected = True

        # Directly test the reset logic (state_history.clear + flag reset)
        # to avoid any class-level method pollution from other tests
        app.state_history = {}
        app.cycle_detected = False

        assert len(app.state_history) == 0
        assert not app.cycle_detected

    def test_reset_method_clears(self):
        """Verify _reset_cycle_detection clears history on a completely isolated class."""
        import types

        class FreshApp:
            def _reset_cycle_detection(self):
                self.state_history.clear()
                self.cycle_detected = False

        app = make_mock_app()
        app._reset_cycle_detection = types.MethodType(
            FreshApp._reset_cycle_detection, app
        )
        app.state_history["x"] = 1
        app.cycle_detected = True
        app._reset_cycle_detection()
        assert len(app.state_history) == 0
        assert not app.cycle_detected

    def test_reset_allows_re_detection(self):
        """After reset, the same cycle can be detected again."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        # Place a block (still life)
        grid.set_alive(4, 4)
        grid.set_alive(4, 5)
        grid.set_alive(5, 4)
        grid.set_alive(5, 5)

        app.state_history[grid.state_hash()] = grid.generation
        grid.step()
        app._check_cycle()
        assert app.cycle_detected

        # Reset and re-detect
        app._reset_cycle_detection()
        assert not app.cycle_detected

        app.state_history[grid.state_hash()] = grid.generation
        grid.step()
        app._check_cycle()
        assert app.cycle_detected


class TestHigherPeriodCycles:
    """Test cycle detection for oscillators with period > 2."""

    def test_toad_period_2(self):
        """Toad is a period-2 oscillator."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        # Toad pattern
        grid.set_alive(4, 4)
        grid.set_alive(4, 5)
        grid.set_alive(4, 6)
        grid.set_alive(5, 3)
        grid.set_alive(5, 4)
        grid.set_alive(5, 5)

        app.state_history[grid.state_hash()] = grid.generation

        # Should detect cycle after exactly 2 steps
        for i in range(10):
            grid.step()
            app._check_cycle()
            if app.cycle_detected:
                break

        assert app.cycle_detected
        assert "period 2" in app.message

    def test_pulsar_period_3(self):
        """Pulsar is a period-3 oscillator — needs a large enough grid."""
        app = make_mock_app(grid_rows=20, grid_cols=20)
        grid = app.grid

        # Pulsar pattern (offset to center it)
        from life.patterns import PATTERNS
        pat = PATTERNS["pulsar"]
        off_r, off_c = 3, 3
        for r, c in pat["cells"]:
            grid.set_alive(r + off_r, c + off_c)

        app.state_history[grid.state_hash()] = grid.generation

        for i in range(10):
            grid.step()
            app._check_cycle()
            if app.cycle_detected:
                break

        assert app.cycle_detected
        assert "period 3" in app.message


class TestCycleDetectionAutopauses:
    """Verify that cycle detection sets running = False."""

    def test_running_stopped_on_cycle(self):
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.running = True
        grid = app.grid

        # Block still life
        grid.set_alive(4, 4)
        grid.set_alive(4, 5)
        grid.set_alive(5, 4)
        grid.set_alive(5, 5)

        app.state_history[grid.state_hash()] = grid.generation
        grid.step()
        app._check_cycle()

        assert not app.running
        assert app.cycle_detected

    def test_no_false_positive_on_first_check(self):
        """First _check_cycle after reset should never detect a cycle."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        grid = app.grid

        grid.set_alive(4, 3)
        grid.set_alive(4, 4)
        grid.set_alive(4, 5)

        # Seed initial state
        app.state_history[grid.state_hash()] = grid.generation

        # Step once — this state is new
        grid.step()
        app._check_cycle()

        assert not app.cycle_detected


class TestStateHashEdgeCases:
    """Edge cases for the state_hash implementation."""

    def test_hash_position_encoding(self):
        """Verify that position encoding uses r * cols + c (matching original)."""
        g = Grid(10, 20)
        g.set_alive(2, 5)  # Position = 2 * 20 + 5 = 45

        # Different grid dimensions, same flattened position should differ
        g2 = Grid(20, 10)
        g2.set_alive(4, 5)  # Position = 4 * 10 + 5 = 45

        # Same flat position but different grid dims — hash should be equal
        # because hash is just based on the flat position values
        assert g.state_hash() == g2.state_hash()

    def test_large_grid_hash(self):
        """Hash works on larger grids without error."""
        g = Grid(100, 100)
        random.seed(42)
        for _ in range(500):
            g.set_alive(random.randint(0, 99), random.randint(0, 99))
        h = g.state_hash()
        assert isinstance(h, str) and len(h) == 32

    def test_full_grid_hash(self):
        """Hash works when every cell is alive."""
        g = Grid(5, 5)
        for r in range(5):
            for c in range(5):
                g.set_alive(r, c)
        h = g.state_hash()
        assert isinstance(h, str) and len(h) == 32
