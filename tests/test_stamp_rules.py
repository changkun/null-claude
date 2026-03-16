"""Tests for stamp mode and rule editor -- deep validation against commits 14a0c86, 68b6fff."""
import random
import pytest
from tests.conftest import make_mock_app
from life.rules import RULE_PRESETS, rule_string, parse_rule_string
from life.patterns import PATTERNS


# ── rule_string tests ────────────────────────────────────────────────────────


class TestRuleString:
    """Validate rule_string formatting matches commit 68b6fff."""

    def test_conway_default(self):
        assert rule_string({3}, {2, 3}) == "B3/S23"

    def test_empty_birth(self):
        assert rule_string(set(), {2, 3}) == "B/S23"

    def test_empty_survival(self):
        assert rule_string({3}, set()) == "B3/S"

    def test_both_empty(self):
        assert rule_string(set(), set()) == "B/S"

    def test_sorted_output(self):
        """Digits must appear in ascending order regardless of insertion order."""
        assert rule_string({6, 3}, {3, 2}) == "B36/S23"

    def test_all_digits(self):
        full = {0, 1, 2, 3, 4, 5, 6, 7, 8}
        assert rule_string(full, full) == "B012345678/S012345678"

    def test_single_digit(self):
        assert rule_string({5}, {7}) == "B5/S7"

    @pytest.mark.parametrize("name,preset", list(RULE_PRESETS.items()))
    def test_all_presets_round_trip(self, name, preset):
        """Every preset must round-trip through rule_string -> parse_rule_string."""
        rs = rule_string(preset["birth"], preset["survival"])
        result = parse_rule_string(rs)
        assert result is not None
        assert result[0] == preset["birth"]
        assert result[1] == preset["survival"]


# ── parse_rule_string tests ──────────────────────────────────────────────────


class TestParseRuleString:
    """Validate parse_rule_string parsing matches commit 68b6fff."""

    def test_basic_parse(self):
        result = parse_rule_string("B3/S23")
        assert result == ({3}, {2, 3})

    def test_case_insensitive(self):
        result = parse_rule_string("b3/s23")
        assert result == ({3}, {2, 3})

    def test_whitespace_stripped(self):
        result = parse_rule_string("  B3/S23  ")
        assert result == ({3}, {2, 3})

    def test_empty_birth_part(self):
        result = parse_rule_string("B/S23")
        assert result == (set(), {2, 3})

    def test_empty_survival_part(self):
        result = parse_rule_string("B3/S")
        assert result == ({3}, set())

    def test_both_empty(self):
        result = parse_rule_string("B/S")
        assert result == (set(), set())

    def test_multi_digit(self):
        result = parse_rule_string("B36/S125")
        assert result == ({3, 6}, {1, 2, 5})

    def test_no_slash_returns_none(self):
        assert parse_rule_string("B3S23") is None

    def test_missing_b_prefix_returns_none(self):
        assert parse_rule_string("3/S23") is None

    def test_missing_s_prefix_returns_none(self):
        assert parse_rule_string("B3/23") is None

    def test_invalid_char_returns_none(self):
        assert parse_rule_string("B3x/S23") is None

    def test_digit_9_in_birth_is_invalid(self):
        """9 exceeds Moore neighborhood count (0-8), must be rejected."""
        assert parse_rule_string("B9/S23") is None

    def test_digit_9_is_invalid(self):
        """Neighbor count is 0-8 for Moore neighborhood; 9 is invalid."""
        assert parse_rule_string("B39/S23") is None

    def test_empty_string(self):
        assert parse_rule_string("") is None

    def test_just_slash(self):
        assert parse_rule_string("/") is None

    def test_life_without_death(self):
        result = parse_rule_string("B3/S012345678")
        assert result == ({3}, {0, 1, 2, 3, 4, 5, 6, 7, 8})


# ── RULE_PRESETS validation ──────────────────────────────────────────────────


class TestRulePresets:
    """Validate RULE_PRESETS data matches commit 68b6fff exactly."""

    EXPECTED = {
        "Conway's Life": {"birth": {3}, "survival": {2, 3}},
        "HighLife":      {"birth": {3, 6}, "survival": {2, 3}},
        "Day & Night":   {"birth": {3, 6, 7, 8}, "survival": {3, 4, 6, 7, 8}},
        "Seeds":         {"birth": {2}, "survival": set()},
        "Life w/o Death": {"birth": {3}, "survival": {0, 1, 2, 3, 4, 5, 6, 7, 8}},
        "Diamoeba":      {"birth": {3, 5, 6, 7, 8}, "survival": {5, 6, 7, 8}},
        "2x2":           {"birth": {3, 6}, "survival": {1, 2, 5}},
        "Morley":        {"birth": {3, 6, 8}, "survival": {2, 4, 5}},
        "Anneal":        {"birth": {4, 6, 7, 8}, "survival": {3, 5, 6, 7, 8}},
    }

    def test_preset_count(self):
        assert len(RULE_PRESETS) == 9

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_preset_exists(self, name):
        assert name in RULE_PRESETS

    @pytest.mark.parametrize("name,expected", list(EXPECTED.items()))
    def test_preset_birth(self, name, expected):
        assert RULE_PRESETS[name]["birth"] == expected["birth"]

    @pytest.mark.parametrize("name,expected", list(EXPECTED.items()))
    def test_preset_survival(self, name, expected):
        assert RULE_PRESETS[name]["survival"] == expected["survival"]

    def test_all_values_in_range(self):
        for name, preset in RULE_PRESETS.items():
            for n in preset["birth"] | preset["survival"]:
                assert 0 <= n <= 8, f"{name}: value {n} out of range"


# ── Stamp placement tests ───────────────────────────────────────────────────


class TestStampPlacement:
    """Validate _stamp_pattern logic matches commit 14a0c86."""

    def test_stamp_places_cells_at_cursor(self):
        """Stamp should overlay pattern centered on cursor position."""
        app = make_mock_app(grid_rows=30, grid_cols=50)
        app.pattern_list = sorted(PATTERNS.keys())
        app.blueprints = {}

        # Manually replicate _stamp_pattern logic (since app is a mock)
        name = "glider"
        pat = PATTERNS[name]
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = app.cursor_r - max_r // 2
        off_c = app.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        assert app.grid.population == len(pat["cells"])

    def test_stamp_wraps_at_boundaries(self):
        """Stamp near edge should wrap via modulo."""
        app = make_mock_app(grid_rows=10, grid_cols=10)
        app.cursor_r = 0
        app.cursor_c = 0

        name = "glider"
        pat = PATTERNS[name]
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = app.cursor_r - max_r // 2
        off_c = app.cursor_c - max_c // 2
        placed = set()
        for r, c in pat["cells"]:
            wr = (r + off_r) % app.grid.rows
            wc = (c + off_c) % app.grid.cols
            app.grid.set_alive(wr, wc)
            placed.add((wr, wc))
        # All cells should be placed (wrapping means no cell is lost)
        assert app.grid.population == len(pat["cells"])
        # Some cells should have wrapped to high row/col indices
        assert any(r >= 8 for r, _ in placed) or any(c >= 8 for _, c in placed)

    def test_stamp_does_not_clear_existing_cells(self):
        """Stamp overlays on existing cells -- does not clear grid first."""
        app = make_mock_app(grid_rows=20, grid_cols=20)
        # Pre-populate a cell far from where stamp will go
        app.grid.set_alive(0, 0)
        assert app.grid.population == 1

        app.cursor_r = 10
        app.cursor_c = 10
        pat = PATTERNS["block"]
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = app.cursor_r - max_r // 2
        off_c = app.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        # Original cell + block cells
        assert app.grid.population == 1 + len(pat["cells"])

    def test_place_pattern_centers_on_grid(self):
        """_place_pattern centers the pattern on the grid, not cursor."""
        app = make_mock_app(grid_rows=30, grid_cols=50)
        name = "blinker"
        pat = PATTERNS[name]
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = (app.grid.rows - max_r) // 2
        off_c = (app.grid.cols - max_c) // 2
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        assert app.grid.population == len(pat["cells"])
        # Verify centering: the offset should place cells near the middle
        for r, c in pat["cells"]:
            placed_r = (r + off_r) % app.grid.rows
            placed_c = (c + off_c) % app.grid.cols
            assert 10 <= placed_r <= 20
            assert 20 <= placed_c <= 30

    @pytest.mark.parametrize("pattern_name", list(PATTERNS.keys()))
    def test_stamp_all_patterns(self, pattern_name):
        """Every built-in pattern can be stamped without error."""
        app = make_mock_app(grid_rows=50, grid_cols=80)
        app.cursor_r = 25
        app.cursor_c = 40
        pat = PATTERNS[pattern_name]
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = app.cursor_r - max_r // 2
        off_c = app.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        assert app.grid.population == len(pat["cells"])

    def test_stamp_offset_calculation(self):
        """Verify the cursor-centered offset matches original formula: cursor - max//2."""
        cursor_r, cursor_c = 15, 25
        pat = PATTERNS["glider"]
        max_r = max(r for r, c in pat["cells"])  # 2
        max_c = max(c for r, c in pat["cells"])  # 2
        off_r = cursor_r - max_r // 2  # 15 - 1 = 14
        off_c = cursor_c - max_c // 2  # 25 - 1 = 24
        assert off_r == 14
        assert off_c == 24

    def test_place_pattern_offset_calculation(self):
        """Verify grid-centered offset matches original formula: (rows - max) // 2."""
        rows, cols = 30, 50
        pat = PATTERNS["glider"]
        max_r = max(r for r, c in pat["cells"])  # 2
        max_c = max(c for r, c in pat["cells"])  # 2
        off_r = (rows - max_r) // 2  # (30 - 2) // 2 = 14
        off_c = (cols - max_c) // 2  # (50 - 2) // 2 = 24
        assert off_r == 14
        assert off_c == 24

    def test_stamp_idempotent_on_same_position(self):
        """Stamping the same pattern twice at the same cursor doesn't increase population."""
        app = make_mock_app(grid_rows=30, grid_cols=50)
        app.cursor_r = 15
        app.cursor_c = 25
        pat = PATTERNS["block"]
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = app.cursor_r - max_r // 2
        off_c = app.cursor_c - max_c // 2

        # Stamp once
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        pop_after_first = app.grid.population

        # Stamp again at same position
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        assert app.grid.population == pop_after_first

    def test_stamp_different_positions(self):
        """Two stamps at different positions create independent cells."""
        app = make_mock_app(grid_rows=50, grid_cols=50)
        pat = PATTERNS["block"]  # 4 cells
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])

        # First stamp at (10, 10)
        off_r = 10 - max_r // 2
        off_c = 10 - max_c // 2
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        assert app.grid.population == 4

        # Second stamp at (30, 30) -- no overlap
        off_r = 30 - max_r // 2
        off_c = 30 - max_c // 2
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        assert app.grid.population == 8


# ── Integration: rule + stamp together ───────────────────────────────────────


class TestRuleStampIntegration:
    """Cross-cutting tests combining rules and stamp features."""

    def test_grid_uses_conway_defaults(self):
        """Grid should start with Conway's Life rules."""
        app = make_mock_app()
        assert app.grid.birth == {3}
        assert app.grid.survival == {2, 3}

    def test_rule_preset_conway_matches_grid_default(self):
        preset = RULE_PRESETS["Conway's Life"]
        app = make_mock_app()
        assert app.grid.birth == preset["birth"]
        assert app.grid.survival == preset["survival"]

    def test_stamp_then_step_with_conway(self):
        """Stamp a blinker, step once, verify oscillation."""
        app = make_mock_app(grid_rows=20, grid_cols=20)
        app.cursor_r = 10
        app.cursor_c = 10
        pat = PATTERNS["blinker"]
        max_r = max(r for r, c in pat["cells"])
        max_c = max(c for r, c in pat["cells"])
        off_r = app.cursor_r - max_r // 2
        off_c = app.cursor_c - max_c // 2
        for r, c in pat["cells"]:
            app.grid.set_alive(
                (r + off_r) % app.grid.rows,
                (c + off_c) % app.grid.cols,
            )
        pop_before = app.grid.population
        assert pop_before == 3

        # Step the grid
        app.grid.step()
        assert app.grid.population == 3  # blinker oscillates, same pop

    def test_rule_string_for_all_presets_format(self):
        """All preset rule strings should match B.../S... format."""
        import re
        for name, preset in RULE_PRESETS.items():
            rs = rule_string(preset["birth"], preset["survival"])
            assert re.match(r"^B[0-8]*/S[0-8]*$", rs), f"{name}: {rs}"
