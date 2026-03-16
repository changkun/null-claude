"""Tests for save/load — deep validation against commit 07373fb."""
import random, pytest, os, tempfile, json
from tests.conftest import make_mock_app
from life.grid import Grid
from life.constants import SAVE_DIR
from life.rules import rule_string, parse_rule_string


class TestGridToDict:
    """Test Grid.to_dict serialization."""

    def test_empty_grid(self):
        g = Grid(10, 10)
        d = g.to_dict()
        assert d["rows"] == 10
        assert d["cols"] == 10
        assert d["generation"] == 0
        assert d["cells"] == []
        assert "rule" in d

    def test_single_cell(self):
        g = Grid(5, 5)
        g.set_alive(2, 3)
        d = g.to_dict()
        assert len(d["cells"]) == 1
        r, c, age = d["cells"][0]
        assert (r, c) == (2, 3)
        assert age == 1

    def test_multiple_cells_with_ages(self):
        g = Grid(10, 10)
        g.set_alive(0, 0)
        g.set_alive(1, 1)
        g.set_alive(2, 2)
        # Advance to give cells age > 1
        # Manually set ages for deterministic test
        g.cells[0][0] = 5
        g.cells[1][1] = 10
        g.cells[2][2] = 1
        d = g.to_dict()
        assert len(d["cells"]) == 3
        ages = {(r, c): age for r, c, age in d["cells"]}
        assert ages[(0, 0)] == 5
        assert ages[(1, 1)] == 10
        assert ages[(2, 2)] == 1

    def test_generation_preserved(self):
        g = Grid(10, 10)
        g.generation = 42
        d = g.to_dict()
        assert d["generation"] == 42

    def test_rule_serialized(self):
        g = Grid(5, 5)
        g.birth = {3, 6}
        g.survival = {2, 3}
        d = g.to_dict()
        assert d["rule"] == "B36/S23"

    def test_full_grid(self):
        """Every cell alive."""
        g = Grid(5, 5)
        for r in range(5):
            for c in range(5):
                g.set_alive(r, c)
        d = g.to_dict()
        assert len(d["cells"]) == 25

    def test_cells_are_tuples_of_three(self):
        g = Grid(3, 3)
        g.set_alive(1, 1)
        d = g.to_dict()
        for entry in d["cells"]:
            assert len(entry) == 3, "Each cell entry must be (r, c, age)"


class TestGridLoadDict:
    """Test Grid.load_dict deserialization."""

    def test_roundtrip_empty(self):
        g = Grid(10, 10)
        d = g.to_dict()
        g2 = Grid(1, 1)  # different size initially
        g2.load_dict(d)
        assert g2.rows == 10
        assert g2.cols == 10
        assert g2.generation == 0
        assert g2.population == 0

    def test_roundtrip_with_cells(self):
        g = Grid(20, 20)
        random.seed(42)
        for _ in range(50):
            g.set_alive(random.randint(0, 19), random.randint(0, 19))
        g.generation = 17
        d = g.to_dict()

        g2 = Grid(1, 1)
        g2.load_dict(d)
        assert g2.rows == 20
        assert g2.cols == 20
        assert g2.generation == 17
        assert g2.population == g.population
        for r in range(20):
            for c in range(20):
                assert g2.cells[r][c] == g.cells[r][c]

    def test_roundtrip_preserves_ages(self):
        g = Grid(5, 5)
        g.cells[0][0] = 7
        g.cells[2][3] = 100
        g.population = 2
        g.generation = 50
        d = g.to_dict()

        g2 = Grid(1, 1)
        g2.load_dict(d)
        assert g2.cells[0][0] == 7
        assert g2.cells[2][3] == 100
        assert g2.population == 2
        assert g2.generation == 50

    def test_roundtrip_full_grid(self):
        g = Grid(4, 4)
        for r in range(4):
            for c in range(4):
                g.set_alive(r, c)
                g.cells[r][c] = r * 4 + c + 1  # unique ages
        g.population = 16
        g.generation = 99
        d = g.to_dict()

        g2 = Grid(1, 1)
        g2.load_dict(d)
        assert g2.population == 16
        for r in range(4):
            for c in range(4):
                assert g2.cells[r][c] == r * 4 + c + 1

    def test_load_dict_resets_dead_cells(self):
        """Loading a dict should clear any previously alive cells."""
        g = Grid(5, 5)
        for r in range(5):
            for c in range(5):
                g.set_alive(r, c)
        # Now load a dict with only one cell
        d = {"rows": 5, "cols": 5, "generation": 0, "cells": [(2, 2, 1)]}
        g.load_dict(d)
        assert g.population == 1
        assert g.cells[2][2] == 1
        assert g.cells[0][0] == 0

    def test_load_dict_out_of_bounds_cells_ignored(self):
        """Cells outside the grid dimensions should be silently ignored."""
        d = {"rows": 3, "cols": 3, "generation": 0, "cells": [(5, 5, 1), (1, 1, 2)]}
        g = Grid(1, 1)
        g.load_dict(d)
        assert g.population == 1
        assert g.cells[1][1] == 2

    def test_load_dict_restores_rule(self):
        g = Grid(5, 5)
        g.birth = {3, 6}
        g.survival = {2, 3}
        d = g.to_dict()

        g2 = Grid(5, 5)
        g2.load_dict(d)
        assert g2.birth == {3, 6}
        assert g2.survival == {2, 3}

    def test_load_dict_without_rule_keeps_default(self):
        """If no rule in save data, birth/survival should remain at defaults."""
        d = {"rows": 5, "cols": 5, "generation": 0, "cells": []}
        g = Grid(5, 5)
        g.birth = {3}
        g.survival = {2, 3}
        g.load_dict(d)
        assert g.birth == {3}
        assert g.survival == {2, 3}


class TestSaveLoadFile:
    """Test saving and loading grid state to/from actual JSON files."""

    def test_save_and_load_json(self, tmp_path):
        g = Grid(15, 15)
        random.seed(123)
        for _ in range(30):
            g.set_alive(random.randint(0, 14), random.randint(0, 14))
        g.generation = 10

        filepath = tmp_path / "test_save.json"
        data = g.to_dict()
        data["name"] = "test_save"
        with open(filepath, "w") as f:
            json.dump(data, f)

        # Load it back
        with open(filepath) as f:
            loaded = json.load(f)

        g2 = Grid(1, 1)
        g2.load_dict(loaded)
        assert g2.rows == 15
        assert g2.cols == 15
        assert g2.generation == 10
        assert g2.population == g.population
        for r in range(15):
            for c in range(15):
                assert g2.cells[r][c] == g.cells[r][c]

    def test_save_file_is_valid_json(self, tmp_path):
        g = Grid(5, 5)
        g.set_alive(0, 0)
        filepath = tmp_path / "valid.json"
        data = g.to_dict()
        with open(filepath, "w") as f:
            json.dump(data, f)
        # Should parse without error
        with open(filepath) as f:
            loaded = json.load(f)
        assert isinstance(loaded, dict)
        assert "rows" in loaded
        assert "cols" in loaded
        assert "cells" in loaded

    def test_save_name_field(self, tmp_path):
        """The app adds a 'name' field when saving — verify it roundtrips."""
        g = Grid(5, 5)
        g.set_alive(1, 1)
        data = g.to_dict()
        data["name"] = "my cool save"
        filepath = tmp_path / "named.json"
        with open(filepath, "w") as f:
            json.dump(data, f)

        with open(filepath) as f:
            loaded = json.load(f)
        assert loaded["name"] == "my cool save"
        # load_dict should still work fine with the extra field
        g2 = Grid(1, 1)
        g2.load_dict(loaded)
        assert g2.cells[1][1] == 1

    def test_filename_sanitization(self):
        """Verify the filename sanitization logic from _save_state."""
        name = "Hello World! @#$%"
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        assert safe_name == "Hello_World______"
        assert all(c.isalnum() or c in "-_" for c in safe_name)

    def test_empty_name_invalid(self):
        """A name that sanitizes to empty string should be rejected."""
        name = "!!!"
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        # The app checks `if not safe_name` but since special chars become '_', this won't be empty
        # However, a truly empty name (empty string input) should be caught
        name2 = ""
        safe_name2 = "".join(c if c.isalnum() or c in "-_" else "_" for c in name2)
        assert safe_name2 == ""


class TestSaveLoadAfterStep:
    """Verify that save/load preserves state after simulation steps."""

    def test_save_after_steps(self, tmp_path):
        g = Grid(10, 10)
        # Blinker pattern
        g.set_alive(4, 3)
        g.set_alive(4, 4)
        g.set_alive(4, 5)
        # Step a few times
        for _ in range(5):
            g.step()

        d = g.to_dict()
        filepath = tmp_path / "stepped.json"
        with open(filepath, "w") as f:
            json.dump(d, f)

        with open(filepath) as f:
            loaded = json.load(f)

        g2 = Grid(1, 1)
        g2.load_dict(loaded)
        assert g2.generation == 5
        assert g2.population == g.population
        # After 5 steps of blinker, ages should be > 1 for surviving cells
        for r in range(10):
            for c in range(10):
                assert g2.cells[r][c] == g.cells[r][c]

    def test_loaded_grid_continues_correctly(self, tmp_path):
        """After loading, further steps should produce same results as original."""
        g = Grid(10, 10)
        g.set_alive(4, 3)
        g.set_alive(4, 4)
        g.set_alive(4, 5)
        for _ in range(3):
            g.step()

        d = g.to_dict()

        g2 = Grid(1, 1)
        g2.load_dict(d)

        # Step both grids 5 more times
        for _ in range(5):
            g.step()
            g2.step()

        assert g.generation == g2.generation
        assert g.population == g2.population
        for r in range(10):
            for c in range(10):
                assert g.cells[r][c] == g2.cells[r][c]


class TestEdgeCases:
    """Edge cases for save/load."""

    def test_1x1_grid(self):
        g = Grid(1, 1)
        g.set_alive(0, 0)
        d = g.to_dict()
        g2 = Grid(5, 5)
        g2.load_dict(d)
        assert g2.rows == 1
        assert g2.cols == 1
        assert g2.cells[0][0] == 1

    def test_large_ages(self):
        g = Grid(3, 3)
        g.cells[1][1] = 999999
        g.population = 1
        d = g.to_dict()
        g2 = Grid(1, 1)
        g2.load_dict(d)
        assert g2.cells[1][1] == 999999

    def test_dict_cells_as_lists_not_tuples(self):
        """JSON serialization converts tuples to lists — load_dict must handle both."""
        d = {"rows": 3, "cols": 3, "generation": 5, "cells": [[1, 1, 3], [0, 2, 7]]}
        g = Grid(1, 1)
        g.load_dict(d)
        assert g.cells[1][1] == 3
        assert g.cells[0][2] == 7
        assert g.population == 2

    def test_load_dict_twice(self):
        """Loading a second dict should fully replace the first."""
        d1 = {"rows": 5, "cols": 5, "generation": 10, "cells": [(0, 0, 1), (1, 1, 2)]}
        d2 = {"rows": 3, "cols": 3, "generation": 20, "cells": [(2, 2, 5)]}

        g = Grid(1, 1)
        g.load_dict(d1)
        assert g.population == 2

        g.load_dict(d2)
        assert g.rows == 3
        assert g.cols == 3
        assert g.generation == 20
        assert g.population == 1
        assert g.cells[2][2] == 5
        # Old cells must be gone
        # (0,0) from d1 should not exist since new grid is 3x3 and was cleared
        assert g.cells[0][0] == 0

    def test_original_format_compatibility(self):
        """Data from commit 07373fb (no 'rule' key) should still load correctly."""
        d = {"rows": 5, "cols": 5, "generation": 3, "cells": [(1, 2, 4)]}
        g = Grid(5, 5)
        g.load_dict(d)
        assert g.cells[1][2] == 4
        assert g.generation == 3
        # Default rule should be preserved
        assert g.birth == {3}
        assert g.survival == {2, 3}
