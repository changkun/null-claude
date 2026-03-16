"""Tests for utils — deep validation against commit 161d9cb."""
import random
import pytest
from life.utils import sparkline, parse_rle, _normalise, _orientations, _gif_age_index


# ── sparkline tests ──────────────────────────────────────────────────────────

SPARK_CHARS = "▁▂▃▄▅▆▇█"


class TestSparkline:
    """Validate sparkline against the original implementation in commit 161d9cb."""

    def test_empty_values(self):
        assert sparkline([], 10) == ""

    def test_single_value(self):
        # With one value, lo == hi, rng = 1, idx = 0
        result = sparkline([42], 10)
        assert result == SPARK_CHARS[0]

    def test_all_same_values(self):
        # All identical => lo == hi => rng = 1 => all idx = 0
        result = sparkline([5, 5, 5, 5], 10)
        assert result == SPARK_CHARS[0] * 4

    def test_two_values_min_max(self):
        # [0, 100] => lo=0, hi=100, rng=100
        # idx for 0: int(0/100*7) = 0 => SPARK_CHARS[0]
        # idx for 100: int(100/100*7) = 7 => SPARK_CHARS[7]
        result = sparkline([0, 100], 10)
        assert result == SPARK_CHARS[0] + SPARK_CHARS[7]

    def test_ascending(self):
        vals = list(range(8))  # 0..7
        result = sparkline(vals, 20)
        # lo=0, hi=7, rng=7
        # idx for v: int(v/7 * 7) = v
        assert result == SPARK_CHARS
        assert len(result) == 8

    def test_descending(self):
        vals = list(range(7, -1, -1))  # 7..0
        result = sparkline(vals, 20)
        assert result == SPARK_CHARS[::-1]

    def test_width_truncation(self):
        """When values exceed width, only the last `width` values are used."""
        vals = [10, 20, 30, 40, 50]
        result = sparkline(vals, 3)
        # Only last 3: [30, 40, 50]
        # lo=30, hi=50, rng=20
        # 30: int(0/20*7)=0 => ▁
        # 40: int(10/20*7)=int(3.5)=3 => ▄
        # 50: int(20/20*7)=7 => █
        assert len(result) == 3
        assert result == SPARK_CHARS[0] + SPARK_CHARS[3] + SPARK_CHARS[7]

    def test_width_larger_than_values(self):
        """When width > len(values), all values are used."""
        vals = [1, 2, 3]
        result = sparkline(vals, 100)
        assert len(result) == 3

    def test_width_exactly_matches(self):
        vals = [10, 20, 30]
        result = sparkline(vals, 3)
        assert len(result) == 3

    def test_midpoint_scaling(self):
        # [0, 50, 100] with width >= 3
        # lo=0, hi=100, rng=100
        # 0: idx=0, 50: idx=int(50/100*7)=int(3.5)=3, 100: idx=7
        result = sparkline([0, 50, 100], 10)
        assert result[0] == SPARK_CHARS[0]
        assert result[1] == SPARK_CHARS[3]
        assert result[2] == SPARK_CHARS[7]

    def test_negative_values(self):
        # [-10, 0, 10] => lo=-10, hi=10, rng=20
        # -10: idx=0, 0: idx=int(10/20*7)=int(3.5)=3, 10: idx=7
        result = sparkline([-10, 0, 10], 10)
        assert result == SPARK_CHARS[0] + SPARK_CHARS[3] + SPARK_CHARS[7]

    def test_large_population_history(self):
        """Simulate a realistic population history."""
        random.seed(42)
        history = [random.randint(0, 1000) for _ in range(500)]
        result = sparkline(history, 60)
        assert len(result) == 60
        # All characters must be valid sparkline chars
        for ch in result:
            assert ch in SPARK_CHARS

    def test_single_value_with_width_one(self):
        result = sparkline([7], 1)
        assert len(result) == 1

    def test_returns_string_type(self):
        assert isinstance(sparkline([1, 2, 3], 5), str)

    def test_zero_values(self):
        result = sparkline([0, 0, 0], 5)
        assert result == SPARK_CHARS[0] * 3

    def test_width_one_multiple_values(self):
        """Width=1 takes only the last value."""
        result = sparkline([10, 20, 30], 1)
        # Only [30] => single value => lo==hi => idx=0
        assert result == SPARK_CHARS[0]
        assert len(result) == 1


# ── parse_rle tests ──────────────────────────────────────────────────────────


class TestParseRle:
    def test_glider(self):
        rle = "#N Glider\nx = 3, y = 3\nbo$2bo$3o!"
        result = parse_rle(rle)
        assert result["name"] == "Glider"
        assert set(result["cells"]) == {(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)}
        assert result["width"] == 3
        assert result["height"] == 3

    def test_blinker(self):
        rle = "x = 3, y = 1\n3o!"
        result = parse_rle(rle)
        assert result["cells"] == [(0, 0), (0, 1), (0, 2)]

    def test_block(self):
        rle = "x = 2, y = 2\n2o$2o!"
        result = parse_rle(rle)
        assert set(result["cells"]) == {(0, 0), (0, 1), (1, 0), (1, 1)}

    def test_with_rule(self):
        rle = "x = 3, y = 3, rule = B3/S23\nbo$2bo$3o!"
        result = parse_rle(rle)
        assert result["rule"] == "B3/S23"

    def test_empty_pattern(self):
        rle = "x = 0, y = 0\n!"
        result = parse_rle(rle)
        assert result["cells"] == []

    def test_comments_preserved(self):
        rle = "#N Test\n#C A comment\n#C Another\nx = 1, y = 1\no!"
        result = parse_rle(rle)
        assert result["name"] == "Test"
        assert len(result["comments"]) == 2

    def test_dead_cells_in_rle(self):
        # "bob" = dead, alive, dead on one row
        rle = "x = 3, y = 1\nbob!"
        result = parse_rle(rle)
        assert result["cells"] == [(0, 1)]

    def test_multiline_pattern(self):
        # Two rows: "o$o!"
        rle = "x = 1, y = 2\no$o!"
        result = parse_rle(rle)
        assert set(result["cells"]) == {(0, 0), (1, 0)}

    def test_run_count_dead(self):
        # "3b2o!" = 3 dead then 2 alive
        rle = "x = 5, y = 1\n3b2o!"
        result = parse_rle(rle)
        assert result["cells"] == [(0, 3), (0, 4)]


# ── _normalise tests ─────────────────────────────────────────────────────────


class TestNormalise:
    def test_empty(self):
        assert _normalise([]) == frozenset()

    def test_already_normalised(self):
        cells = [(0, 0), (0, 1), (1, 0)]
        assert _normalise(cells) == frozenset(cells)

    def test_offset_cells(self):
        cells = [(5, 10), (5, 11), (6, 10)]
        result = _normalise(cells)
        assert result == frozenset([(0, 0), (0, 1), (1, 0)])

    def test_negative_coords(self):
        cells = [(-2, -3), (-2, -2), (-1, -3)]
        result = _normalise(cells)
        assert result == frozenset([(0, 0), (0, 1), (1, 0)])


# ── _orientations tests ─────────────────────────────────────────────────────


class TestOrientations:
    def test_square_has_one_orientation(self):
        # A 2x2 block is symmetric under all rotations/reflections
        block = [(0, 0), (0, 1), (1, 0), (1, 1)]
        orients = _orientations(block)
        assert len(orients) == 1

    def test_glider_has_eight_orientations(self):
        # Glider has no rotational or reflective symmetry, so all 8 orientations are distinct
        glider = [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
        orients = _orientations(glider)
        assert len(orients) == 8

    def test_blinker_has_two_orientations(self):
        blinker = [(0, 0), (0, 1), (0, 2)]
        orients = _orientations(blinker)
        assert len(orients) == 2


# ── _gif_age_index tests ────────────────────────────────────────────────────


class TestGifAgeIndex:
    def test_dead_cell(self):
        assert _gif_age_index(0) == 0
        assert _gif_age_index(-1) == 0

    def test_newborn(self):
        assert _gif_age_index(1) == 1

    def test_young(self):
        assert _gif_age_index(2) == 2
        assert _gif_age_index(3) == 2

    def test_mature(self):
        assert _gif_age_index(4) == 3
        assert _gif_age_index(8) == 3

    def test_old(self):
        assert _gif_age_index(9) == 4
        assert _gif_age_index(20) == 4

    def test_ancient(self):
        assert _gif_age_index(21) == 5
        assert _gif_age_index(1000) == 5
