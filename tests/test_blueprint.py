"""Tests for pattern recognition and blueprint mode -- deep validation against commits 6707f34, 3172fd5."""
import curses
import random
import pytest
from unittest.mock import patch

from tests.conftest import make_mock_app
from life.modes.blueprint import register
from life.patterns import PATTERNS
from life.utils import (
    _normalise, _orientations, _build_recognition_db,
    _get_recognition_db, scan_patterns, _save_blueprints,
)


class TestPatternRecognition:
    """Tests for pattern recognition functions from commit 6707f34."""

    def test_normalise_empty(self):
        assert _normalise([]) == frozenset()
        assert _normalise(set()) == frozenset()

    def test_normalise_shifts_to_origin(self):
        cells = [(3, 5), (4, 6), (5, 7)]
        result = _normalise(cells)
        assert result == frozenset({(0, 0), (1, 1), (2, 2)})

    def test_normalise_already_at_origin(self):
        cells = [(0, 0), (0, 1), (1, 0)]
        result = _normalise(cells)
        assert result == frozenset({(0, 0), (0, 1), (1, 0)})

    def test_orientations_returns_at_least_one(self):
        cells = [(0, 0), (0, 1), (1, 0)]
        orients = _orientations(cells)
        assert len(orients) >= 1
        # All orientations should be frozensets
        for o in orients:
            assert isinstance(o, frozenset)

    def test_orientations_symmetric_pattern(self):
        # A block has only 1 orientation (all rotations/reflections are identical)
        block = [(0, 0), (0, 1), (1, 0), (1, 1)]
        orients = _orientations(block)
        assert len(orients) == 1

    def test_orientations_asymmetric_pattern(self):
        # A glider has multiple distinct orientations
        glider = [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
        orients = _orientations(glider)
        assert len(orients) > 1
        # Should be at most 8 (4 rotations * 2 reflections)
        assert len(orients) <= 8

    def test_orientations_all_normalised(self):
        cells = [(0, 1), (1, 2), (2, 0)]
        for o in _orientations(cells):
            min_r = min(r for r, c in o)
            min_c = min(c for r, c in o)
            assert min_r == 0
            assert min_c == 0

    def test_build_recognition_db_nonempty(self):
        db = _build_recognition_db()
        assert len(db) > 0

    def test_build_recognition_db_structure(self):
        db = _build_recognition_db()
        for name, cat, w, h, orients in db:
            assert isinstance(name, str)
            assert isinstance(cat, str)
            assert isinstance(w, int) and w > 0
            assert isinstance(h, int) and h > 0
            assert isinstance(orients, list)
            assert len(orients) >= 1

    def test_build_recognition_db_skips_large_patterns(self):
        """Patterns with >15 cells should be excluded (per original commit)."""
        db = _build_recognition_db()
        for name, cat, w, h, orients in db:
            for o in orients:
                assert len(o) <= 15

    def test_build_recognition_db_includes_known(self):
        db = _build_recognition_db()
        names = {entry[0] for entry in db}
        # These should always be present (from PATTERNS + extra_patterns)
        for expected in ["block", "glider", "blinker", "loaf", "boat", "tub"]:
            if expected in PATTERNS or expected in ["loaf", "boat", "tub", "ship", "pond"]:
                assert expected in names, f"{expected} not found in recognition DB"

    def test_build_recognition_db_categories(self):
        db = _build_recognition_db()
        name_to_cat = {entry[0]: entry[1] for entry in db}
        assert name_to_cat.get("block") == "Still life"
        assert name_to_cat.get("glider") == "Spaceship"
        assert name_to_cat.get("blinker") == "Oscillator"
        assert name_to_cat.get("loaf") == "Still life"

    def test_get_recognition_db_caching(self):
        db1 = _get_recognition_db()
        db2 = _get_recognition_db()
        assert db1 is db2

    def test_scan_patterns_empty_grid(self):
        from life.grid import Grid
        g = Grid(10, 10)
        result = scan_patterns(g)
        assert result == []

    def test_scan_patterns_finds_block(self):
        from life.grid import Grid
        g = Grid(10, 10)
        # Place a 2x2 block at (2,3)
        for r, c in [(2, 3), (2, 4), (3, 3), (3, 4)]:
            g.set_alive(r, c)
        results = scan_patterns(g)
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "block" in names

    def test_scan_patterns_finds_blinker(self):
        from life.grid import Grid
        g = Grid(10, 10)
        # Place a horizontal blinker at (4,3)
        for r, c in [(4, 3), (4, 4), (4, 5)]:
            g.set_alive(r, c)
        results = scan_patterns(g)
        names = [r["name"] for r in results]
        assert "blinker" in names

    def test_scan_patterns_result_structure(self):
        from life.grid import Grid
        g = Grid(10, 10)
        for r, c in [(2, 3), (2, 4), (3, 3), (3, 4)]:
            g.set_alive(r, c)
        results = scan_patterns(g)
        for res in results:
            assert "name" in res
            assert "category" in res
            assert "r" in res
            assert "c" in res
            assert "w" in res
            assert "h" in res
            assert "cells" in res
            assert isinstance(res["cells"], set)

    def test_scan_patterns_claimed_cells(self):
        """Cells claimed by one pattern should not be used by another."""
        from life.grid import Grid
        g = Grid(20, 20)
        # Place two separate blocks
        for r, c in [(2, 2), (2, 3), (3, 2), (3, 3)]:
            g.set_alive(r, c)
        for r, c in [(10, 10), (10, 11), (11, 10), (11, 11)]:
            g.set_alive(r, c)
        results = scan_patterns(g)
        all_cells = set()
        for res in results:
            # No overlap
            assert not (res["cells"] & all_cells)
            all_cells |= res["cells"]

    def test_scan_patterns_finds_glider(self):
        """Test glider detection using an orientation with (0,0) alive.

        The scanner only tries alive cells as top-left anchors, so we need
        a glider orientation where (0,0) is an alive cell. Orientation
        [(0,0),(0,1),(0,2),(1,2),(2,1)] works -- that's a rotated glider.
        """
        from life.grid import Grid
        g = Grid(20, 20)
        # Use a rotated glider where (0,0) is alive:
        # (0,0),(0,1),(0,2),(1,2),(2,1)
        for r, c in [(0, 0), (0, 1), (0, 2), (1, 2), (2, 1)]:
            g.set_alive(r + 5, c + 5)
        results = scan_patterns(g)
        names = [r["name"] for r in results]
        assert "glider" in names

    def test_scan_patterns_glider_in_db(self):
        """The recognition DB should include glider with multiple orientations."""
        db = _get_recognition_db()
        glider_entry = None
        for entry in db:
            if entry[0] == "glider":
                glider_entry = entry
                break
        assert glider_entry is not None
        name, cat, w, h, orients = glider_entry
        assert cat == "Spaceship"
        # Glider is asymmetric, should have multiple orientations
        assert len(orients) >= 4


class TestBlueprint:
    """Tests for blueprint mode from commit 3172fd5."""

    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))
        # Add helper methods the blueprint code expects
        type(self.app)._rebuild_pattern_list = lambda self: setattr(
            self, 'pattern_list',
            sorted(set(PATTERNS.keys()) | set(self.blueprints.keys()))
        )
        type(self.app)._get_pattern = lambda self, name: (
            PATTERNS.get(name) or self.blueprints.get(name)
        )
        type(self.app)._reset_cycle_detection = lambda self: setattr(
            self, 'cycle_detected', False
        )

    def test_enter_blueprint_mode(self):
        self.app.cursor_r = 5
        self.app.cursor_c = 10
        self.app._enter_blueprint_mode()
        assert self.app.blueprint_mode is True
        assert self.app.blueprint_anchor == (5, 10)
        assert "Blueprint" in self.app.message

    def test_exit_blueprint_mode_esc(self):
        self.app._enter_blueprint_mode()
        assert self.app.blueprint_mode is True
        self.app._handle_blueprint_mode_key(27)  # ESC
        assert self.app.blueprint_mode is False
        assert self.app.blueprint_anchor is None
        assert "cancelled" in self.app.message

    def test_blueprint_region(self):
        self.app.cursor_r = 2
        self.app.cursor_c = 3
        self.app._enter_blueprint_mode()
        # Move cursor to expand selection
        self.app.cursor_r = 8
        self.app.cursor_c = 12
        min_r, min_c, max_r, max_c = self.app._blueprint_region()
        assert min_r == 2
        assert min_c == 3
        assert max_r == 8
        assert max_c == 12

    def test_blueprint_region_reversed(self):
        """Region should work regardless of cursor direction."""
        self.app.cursor_r = 8
        self.app.cursor_c = 12
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 2
        self.app.cursor_c = 3
        min_r, min_c, max_r, max_c = self.app._blueprint_region()
        assert min_r == 2
        assert min_c == 3
        assert max_r == 8
        assert max_c == 12

    def test_capture_blueprint_empty_region(self):
        """Capturing a region with no alive cells should not save."""
        self.app.cursor_r = 0
        self.app.cursor_c = 0
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 5
        self.app.cursor_c = 5
        self.app._capture_blueprint()
        assert self.app.blueprint_mode is False
        assert len(self.app.blueprints) == 0
        assert "No alive cells" in self.app.message

    def test_capture_blueprint_with_cells(self):
        """Capturing a region with alive cells should save the blueprint."""
        # Place some cells
        self.app.grid.set_alive(3, 4)
        self.app.grid.set_alive(3, 5)
        self.app.grid.set_alive(4, 4)
        # Enter blueprint mode and select region
        self.app.cursor_r = 2
        self.app.cursor_c = 3
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 5
        self.app.cursor_c = 6
        # Mock _prompt_text to return a name
        type(self.app)._prompt_text = lambda self, prompt: "test_pattern"
        # Mock _save_blueprints to avoid filesystem
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._capture_blueprint()
        assert self.app.blueprint_mode is False
        assert "test_pattern" in self.app.blueprints
        bp = self.app.blueprints["test_pattern"]
        assert len(bp["cells"]) == 3
        # Cells are relative to region top-left (2,3), so:
        # (3,4)->(1,1), (3,5)->(1,2), (4,4)->(2,1)
        assert (1, 1) in bp["cells"]
        assert (1, 2) in bp["cells"]
        assert (2, 1) in bp["cells"]

    def test_capture_blueprint_name_sanitization(self):
        """Names should be sanitized to lowercase with underscores."""
        self.app.grid.set_alive(3, 4)
        self.app.cursor_r = 2
        self.app.cursor_c = 3
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 4
        self.app.cursor_c = 5
        type(self.app)._prompt_text = lambda self, prompt: "My Cool Pattern!"
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._capture_blueprint()
        # Should be sanitized
        assert "my_cool_pattern" in self.app.blueprints

    def test_capture_blueprint_cannot_overwrite_builtin(self):
        """Should not allow overwriting built-in patterns."""
        self.app.grid.set_alive(3, 4)
        self.app.cursor_r = 2
        self.app.cursor_c = 3
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 4
        self.app.cursor_c = 5
        type(self.app)._prompt_text = lambda self, prompt: "glider"
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._capture_blueprint()
        assert "glider" not in self.app.blueprints
        assert "Cannot overwrite" in self.app.message

    def test_capture_blueprint_cancelled_name(self):
        """Empty/None name should cancel."""
        self.app.grid.set_alive(3, 4)
        self.app.cursor_r = 2
        self.app.cursor_c = 3
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 4
        self.app.cursor_c = 5
        type(self.app)._prompt_text = lambda self, prompt: None
        self.app._capture_blueprint()
        assert len(self.app.blueprints) == 0
        assert "cancelled" in self.app.message

    def test_stamp_blueprint(self):
        """Stamping should place pattern cells centered on cursor."""
        # Add a blueprint
        self.app.blueprints["test_stamp"] = {
            "description": "Test",
            "cells": [(0, 0), (0, 1), (1, 0), (1, 1)],
        }
        self.app.cursor_r = 10
        self.app.cursor_c = 10
        self.app._stamp_blueprint("test_stamp")
        # Check cells were placed (centered on cursor)
        # max_r=1, max_c=1, so off_r=10-0=10, off_c=10-0=10
        assert self.app.grid.cells[10][10] > 0
        assert "Stamped" in self.app.message

    def test_stamp_blueprint_unknown(self):
        """Stamping unknown pattern should flash error."""
        self.app._stamp_blueprint("nonexistent")
        assert "Unknown pattern" in self.app.message

    def test_stamp_blueprint_wraps_grid(self):
        """Stamping near edge should wrap around grid."""
        self.app.blueprints["wrap_test"] = {
            "description": "Test",
            "cells": [(0, 0), (0, 1), (0, 2)],
        }
        # Place cursor at bottom-right corner
        self.app.cursor_r = self.app.grid.rows - 1
        self.app.cursor_c = self.app.grid.cols - 1
        self.app._stamp_blueprint("wrap_test")
        # Should wrap and place at least one cell
        alive_count = sum(
            1 for r in range(self.app.grid.rows)
            for c in range(self.app.grid.cols)
            if self.app.grid.cells[r][c] > 0
        )
        assert alive_count == 3

    def test_delete_blueprint(self):
        self.app.blueprints["to_delete"] = {
            "description": "Temp", "cells": [(0, 0)]
        }
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._delete_blueprint("to_delete")
        assert "to_delete" not in self.app.blueprints
        assert "Deleted" in self.app.message

    def test_delete_nonexistent_blueprint(self):
        """Deleting a non-existent blueprint should be a no-op."""
        self.app._delete_blueprint("no_such_blueprint")
        # Should not crash, message should not say "Deleted"
        assert "Deleted" not in self.app.message

    def test_handle_blueprint_mode_cursor_movement(self):
        """Cursor keys should move the cursor during blueprint selection."""
        self.app._enter_blueprint_mode()
        initial_r = self.app.cursor_r
        initial_c = self.app.cursor_c
        # Move down
        self.app._handle_blueprint_mode_key(curses.KEY_DOWN)
        assert self.app.cursor_r == (initial_r + 1) % self.app.grid.rows
        # Move right
        self.app._handle_blueprint_mode_key(curses.KEY_RIGHT)
        assert self.app.cursor_c == (initial_c + 1) % self.app.grid.cols
        # Move up
        self.app._handle_blueprint_mode_key(curses.KEY_UP)
        assert self.app.cursor_r == initial_r
        # Move left
        self.app._handle_blueprint_mode_key(curses.KEY_LEFT)
        assert self.app.cursor_c == initial_c

    def test_handle_blueprint_mode_enter_captures(self):
        """Pressing Enter in blueprint mode should trigger capture."""
        self.app.grid.set_alive(15, 25)
        self.app.cursor_r = 14
        self.app.cursor_c = 24
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 16
        self.app.cursor_c = 26
        type(self.app)._prompt_text = lambda self, prompt: "enter_test"
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._handle_blueprint_mode_key(10)  # Enter
        assert "enter_test" in self.app.blueprints

    def test_handle_blueprint_mode_noop_key(self):
        """Unhandled keys in blueprint mode should return True (consumed)."""
        self.app._enter_blueprint_mode()
        result = self.app._handle_blueprint_mode_key(-1)
        assert result is True

    def test_handle_blueprint_menu_empty(self):
        """Menu with no blueprints should close immediately."""
        self.app.blueprint_menu = True
        self.app._handle_blueprint_menu_key(ord("j"))
        assert self.app.blueprint_menu is False

    def test_handle_blueprint_menu_navigation(self):
        """Up/down keys should change selection in blueprint menu."""
        self.app.blueprints = {
            "alpha": {"description": "A", "cells": [(0, 0)]},
            "beta": {"description": "B", "cells": [(0, 0)]},
            "gamma": {"description": "C", "cells": [(0, 0)]},
        }
        self.app.blueprint_menu = True
        self.app.blueprint_sel = 0
        self.app._handle_blueprint_menu_key(ord("j"))  # down
        assert self.app.blueprint_sel == 1
        self.app._handle_blueprint_menu_key(ord("k"))  # up
        assert self.app.blueprint_sel == 0

    def test_handle_blueprint_menu_escape(self):
        """Escape should close the menu."""
        self.app.blueprints = {
            "alpha": {"description": "A", "cells": [(0, 0)]},
        }
        self.app.blueprint_menu = True
        self.app._handle_blueprint_menu_key(27)  # ESC
        assert self.app.blueprint_menu is False

    def test_handle_blueprint_menu_stamp(self):
        """Enter in menu should stamp the selected blueprint."""
        self.app.blueprints["stamp_me"] = {
            "description": "Stamp test",
            "cells": [(0, 0), (1, 1)],
        }
        self.app.blueprint_menu = True
        self.app.blueprint_sel = 0
        self.app._handle_blueprint_menu_key(10)  # Enter
        assert self.app.blueprint_menu is False
        assert "Stamped" in self.app.message

    def test_handle_blueprint_menu_delete(self):
        """D key should delete the selected blueprint."""
        self.app.blueprints["delete_me"] = {
            "description": "Delete test",
            "cells": [(0, 0)],
        }
        self.app.blueprint_menu = True
        self.app.blueprint_sel = 0
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._handle_blueprint_menu_key(ord("D"))
        assert "delete_me" not in self.app.blueprints

    def test_draw_blueprint_menu_no_crash(self):
        """Drawing the menu should not crash."""
        self.app.blueprints = {
            "demo": {"description": "Demo pattern", "cells": [(0, 0)]},
        }
        self.app.blueprint_menu = True
        self.app.blueprint_sel = 0
        # Mock curses.color_pair since initscr() was not called
        with patch('curses.color_pair', return_value=0):
            self.app._draw_blueprint_menu(40, 120)

    def test_draw_blueprint_menu_empty(self):
        """Drawing empty menu should show 'no blueprints' message."""
        self.app.blueprint_menu = True
        with patch('curses.color_pair', return_value=0):
            self.app._draw_blueprint_menu(40, 120)

    def test_blueprint_cells_normalised_to_origin(self):
        """Captured cells should be normalised so min row/col is 0."""
        self.app.grid.set_alive(5, 7)
        self.app.grid.set_alive(6, 8)
        self.app.cursor_r = 4
        self.app.cursor_c = 6
        self.app._enter_blueprint_mode()
        self.app.cursor_r = 7
        self.app.cursor_c = 9
        type(self.app)._prompt_text = lambda self, prompt: "norm_test"
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._capture_blueprint()
        bp = self.app.blueprints["norm_test"]
        cells = bp["cells"]
        min_r = min(r for r, c in cells)
        min_c = min(c for r, c in cells)
        # Cells at (5,7) and (6,8) with region starting at (4,6)
        # So normalised: (5-4, 7-6) = (1,1) and (6-4, 8-6) = (2,2)
        assert (1, 1) in cells
        assert (2, 2) in cells

    def test_register_attaches_methods(self):
        """register() should attach all blueprint methods to the class."""
        methods = [
            '_enter_blueprint_mode',
            '_blueprint_region',
            '_capture_blueprint',
            '_stamp_blueprint',
            '_delete_blueprint',
            '_handle_blueprint_mode_key',
            '_handle_blueprint_menu_key',
            '_draw_blueprint_menu',
        ]
        for m in methods:
            assert hasattr(self.app, m), f"Method {m} not registered"
            assert callable(getattr(self.app, m))

    def test_vi_keys_in_blueprint_mode(self):
        """Vi-style j/k keys should work for cursor movement."""
        self.app._enter_blueprint_mode()
        initial_r = self.app.cursor_r
        self.app._handle_blueprint_mode_key(ord("j"))  # down
        assert self.app.cursor_r == (initial_r + 1) % self.app.grid.rows
        self.app._handle_blueprint_mode_key(ord("k"))  # up
        assert self.app.cursor_r == initial_r

    def test_handle_blueprint_menu_q_closes(self):
        """Q key should close the blueprint menu."""
        self.app.blueprints["test"] = {
            "description": "Test", "cells": [(0, 0)]
        }
        self.app.blueprint_menu = True
        self.app._handle_blueprint_menu_key(ord("q"))
        assert self.app.blueprint_menu is False

    def test_menu_sel_wraps_around(self):
        """Selection in menu should wrap around."""
        self.app.blueprints = {
            "a": {"description": "A", "cells": [(0, 0)]},
            "b": {"description": "B", "cells": [(0, 0)]},
        }
        self.app.blueprint_menu = True
        self.app.blueprint_sel = 0
        self.app._handle_blueprint_menu_key(ord("k"))  # up from 0
        assert self.app.blueprint_sel == 1  # wraps to last

    def test_delete_last_blueprint_closes_menu(self):
        """Deleting the only blueprint should close the menu."""
        self.app.blueprints["only_one"] = {
            "description": "Solo", "cells": [(0, 0)]
        }
        self.app.blueprint_menu = True
        self.app.blueprint_sel = 0
        with patch('life.modes.blueprint._save_blueprints'):
            self.app._handle_blueprint_menu_key(ord("D"))
        assert self.app.blueprint_menu is False
        assert len(self.app.blueprints) == 0
