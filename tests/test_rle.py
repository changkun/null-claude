"""Tests for RLE pattern import — deep validation against commit 27010ed."""
import random, pytest
from life.utils import parse_rle


class TestGlider:
    """Standard glider pattern: 'bo$2bo$3o!'"""

    RLE = "bo$2bo$3o!"

    def test_cells(self):
        result = parse_rle(self.RLE)
        assert sorted(result["cells"]) == [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]

    def test_dimensions(self):
        result = parse_rle(self.RLE)
        assert result["width"] == 3
        assert result["height"] == 3

    def test_no_rule(self):
        result = parse_rle(self.RLE)
        assert result["rule"] is None

    def test_no_name(self):
        result = parse_rle(self.RLE)
        assert result["name"] == ""


class TestGliderWithHeader:
    """Glider with full RLE header and metadata."""

    RLE = (
        "#N Glider\n"
        "#C A small spaceship\n"
        "#O Richard K. Guy\n"
        "x = 3, y = 3, rule = B3/S23\n"
        "bo$2bo$3o!\n"
    )

    def test_name(self):
        result = parse_rle(self.RLE)
        assert result["name"] == "Glider"

    def test_comments(self):
        result = parse_rle(self.RLE)
        assert "A small spaceship" in result["comments"]
        assert any("Richard K. Guy" in c for c in result["comments"])

    def test_rule(self):
        result = parse_rle(self.RLE)
        assert result["rule"] == "B3/S23"

    def test_cells(self):
        result = parse_rle(self.RLE)
        assert sorted(result["cells"]) == [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]


class TestBlinker:
    """Blinker: 3 alive cells in a row."""

    def test_horizontal(self):
        result = parse_rle("3o!")
        assert sorted(result["cells"]) == [(0, 0), (0, 1), (0, 2)]
        assert result["width"] == 3
        assert result["height"] == 1

    def test_vertical(self):
        result = parse_rle("o$o$o!")
        assert sorted(result["cells"]) == [(0, 0), (1, 0), (2, 0)]
        assert result["height"] == 3


class TestBlock:
    """Block (2x2 still life)."""

    def test_cells(self):
        result = parse_rle("2o$2o!")
        assert sorted(result["cells"]) == [(0, 0), (0, 1), (1, 0), (1, 1)]
        assert result["width"] == 2
        assert result["height"] == 2


class TestRunLengthEncoding:
    """Verify multi-digit run counts and mixed runs."""

    def test_run_of_10_alive(self):
        result = parse_rle("10o!")
        assert len(result["cells"]) == 10
        assert result["cells"] == [(0, c) for c in range(10)]

    def test_run_of_10_dead_then_alive(self):
        result = parse_rle("10bo!")
        assert result["cells"] == [(0, 10)]

    def test_large_run_count(self):
        result = parse_rle("100b5o!")
        assert len(result["cells"]) == 5
        assert result["cells"][0] == (0, 100)
        assert result["cells"][-1] == (0, 104)

    def test_mixed_runs(self):
        # Pattern: .oo..ooo
        result = parse_rle("b2o2b3o!")
        expected = [(0, 1), (0, 2), (0, 5), (0, 6), (0, 7)]
        assert sorted(result["cells"]) == expected


class TestNewlines:
    """$ moves to the next row and resets column to 0."""

    def test_dollar_advances_row(self):
        result = parse_rle("o$o!")
        assert sorted(result["cells"]) == [(0, 0), (1, 0)]

    def test_multi_dollar(self):
        """'3$' skips 3 rows."""
        result = parse_rle("o3$o!")
        assert sorted(result["cells"]) == [(0, 0), (3, 0)]

    def test_dollar_resets_column(self):
        result = parse_rle("3bo$o!")
        assert sorted(result["cells"]) == [(0, 3), (1, 0)]


class TestDeadCells:
    """Both 'b' and '.' represent dead cells."""

    def test_b_notation(self):
        result = parse_rle("bob!")
        assert result["cells"] == [(0, 1)]

    def test_dot_notation(self):
        result = parse_rle(".o.!")
        assert result["cells"] == [(0, 1)]


class TestAliveNotation:
    """Both 'o' and 'A' represent alive cells."""

    def test_o_notation(self):
        result = parse_rle("o!")
        assert result["cells"] == [(0, 0)]

    def test_A_notation(self):
        result = parse_rle("A!")
        assert result["cells"] == [(0, 0)]

    def test_mixed_oA(self):
        result = parse_rle("oAo!")
        assert sorted(result["cells"]) == [(0, 0), (0, 1), (0, 2)]


class TestEmptyPattern:
    """Edge case: empty pattern data."""

    def test_empty_string(self):
        result = parse_rle("")
        assert result["cells"] == []
        assert result["width"] == 1
        assert result["height"] == 1

    def test_only_bang(self):
        result = parse_rle("!")
        assert result["cells"] == []

    def test_only_dead_cells(self):
        result = parse_rle("3b!")
        assert result["cells"] == []


class TestRuleFormats:
    """Various rule format strings in the header."""

    def test_b_s_uppercase(self):
        rle = "x = 1, y = 1, rule = B3/S23\no!"
        result = parse_rle(rle)
        assert result["rule"] == "B3/S23"

    def test_b_s_lowercase(self):
        rle = "x = 1, y = 1, rule = b3/s23\no!"
        result = parse_rle(rle)
        assert result["rule"] == "B3/S23"

    def test_legacy_survival_birth(self):
        """Legacy format: S digits / B digits (no letters)."""
        rle = "x = 1, y = 1, rule = 23/3\no!"
        result = parse_rle(rle)
        assert result["rule"] == "B3/S23"

    def test_no_rule_in_header(self):
        rle = "x = 3, y = 3\nbo$2bo$3o!"
        result = parse_rle(rle)
        assert result["rule"] is None

    def test_highlife_rule(self):
        rle = "x = 1, y = 1, rule = B36/S23\no!"
        result = parse_rle(rle)
        assert result["rule"] == "B36/S23"


class TestMultilinePattern:
    """Pattern data split across multiple lines."""

    def test_multiline(self):
        rle = (
            "x = 3, y = 3\n"
            "bo$\n"
            "2bo$\n"
            "3o!\n"
        )
        result = parse_rle(rle)
        assert sorted(result["cells"]) == [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]

    def test_data_after_bang_ignored(self):
        rle = "o!this is ignored"
        result = parse_rle(rle)
        assert result["cells"] == [(0, 0)]


class TestLWSS:
    """Lightweight spaceship — a known multi-row pattern."""

    RLE = (
        "#N LWSS\n"
        "x = 5, y = 4, rule = B3/S23\n"
        "bo2bo$o$o3bo$4o!\n"
    )

    def test_cells(self):
        result = parse_rle(self.RLE)
        expected = [
            (0, 1), (0, 4),
            (1, 0),
            (2, 0), (2, 4),
            (3, 0), (3, 1), (3, 2), (3, 3),
        ]
        assert sorted(result["cells"]) == sorted(expected)

    def test_dimensions(self):
        result = parse_rle(self.RLE)
        assert result["width"] == 5
        assert result["height"] == 4

    def test_name(self):
        result = parse_rle(self.RLE)
        assert result["name"] == "LWSS"


class TestGosperGliderGun:
    """Gosper glider gun — complex pattern with many runs."""

    RLE = (
        "x = 36, y = 9, rule = B3/S23\n"
        "24bo$22bobo$12b2o6b2o12b2o$11bo3bo4b2o12b2o$2o8bo5bo3b2o$"
        "2o8bo3bob2o4bobo$10bo5bo7bo$11bo3bo$12b2o!\n"
    )

    def test_cell_count(self):
        result = parse_rle(self.RLE)
        assert len(result["cells"]) == 36

    def test_dimensions(self):
        result = parse_rle(self.RLE)
        assert result["width"] == 36
        assert result["height"] == 9


class TestPentadecathlon:
    """Pentadecathlon oscillator."""

    RLE = "x = 3, y = 10, rule = B3/S23\n" "bo$bo$ob2o$bo$bo$bo$bo$ob2o$bo$bo!\n"

    def test_cell_count(self):
        # The RLE above encodes a specific pentadecathlon variant
        result = parse_rle(self.RLE)
        # Check it parsed without error and has cells
        assert len(result["cells"]) > 0

    def test_height(self):
        result = parse_rle(self.RLE)
        assert result["height"] == 10


class TestMetadata:
    """Comment line parsing."""

    def test_multiple_comments(self):
        rle = "#C Line 1\n#C Line 2\n#c Line 3\nx = 1, y = 1\no!"
        result = parse_rle(rle)
        assert len(result["comments"]) == 3
        assert result["comments"][0] == "Line 1"

    def test_author_comment(self):
        rle = "#O John Doe\nx = 1, y = 1\no!"
        result = parse_rle(rle)
        assert any("Author: John Doe" in c for c in result["comments"])

    def test_unknown_hash_ignored(self):
        rle = "#r some data\n#P 0 0\nx = 1, y = 1\no!"
        result = parse_rle(rle)
        # Unknown # lines should not produce comments
        assert len(result["comments"]) == 0


class TestEdgeCases:
    """Miscellaneous edge cases."""

    def test_blank_lines_ignored(self):
        rle = "\n\n#N Test\n\nx = 1, y = 1\n\no!\n\n"
        result = parse_rle(rle)
        assert result["name"] == "Test"
        assert result["cells"] == [(0, 0)]

    def test_no_header_line(self):
        """Pattern data without an x= header line should still parse."""
        result = parse_rle("bo$2bo$3o!")
        assert sorted(result["cells"]) == [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]

    def test_trailing_whitespace(self):
        rle = "  #N Foo  \n  x = 1, y = 1  \n  o!  "
        result = parse_rle(rle)
        assert result["name"] == "Foo"

    def test_single_cell(self):
        result = parse_rle("o!")
        assert result["cells"] == [(0, 0)]
        assert result["width"] == 1
        assert result["height"] == 1
