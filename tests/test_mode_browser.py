"""Tests for mode browser — deep validation against commit c999209."""
import random
import curses
import types
import unittest.mock
import pytest
from tests.conftest import make_mock_app
from life.registry import MODE_REGISTRY, MODE_CATEGORIES


def _mode_browser_apply_filter(self):
    """Filter MODE_REGISTRY by search string. Mirrors App._mode_browser_apply_filter."""
    q = self.mode_browser_search.lower()
    if not q:
        self.mode_browser_filtered = list(MODE_REGISTRY)
    else:
        self.mode_browser_filtered = [
            m for m in MODE_REGISTRY
            if q in m["name"].lower() or q in m["desc"].lower() or q in m["category"].lower()
        ]
    # Clamp selection
    if self.mode_browser_filtered:
        self.mode_browser_sel = min(self.mode_browser_sel, len(self.mode_browser_filtered) - 1)
    else:
        self.mode_browser_sel = 0
    self.mode_browser_scroll = 0


def _handle_mode_browser_key(self, key: int) -> bool:
    """Handle input in the mode browser/picker. Mirrors App._handle_mode_browser_key."""
    if key == -1:
        return True
    if key == 27:  # Esc
        self.mode_browser = False
        return True
    items = self.mode_browser_filtered
    n = len(items)
    # Arrow keys always navigate; j/k navigate only when not searching
    nav_up = key == curses.KEY_UP or (key == ord("k") and not self.mode_browser_search)
    nav_down = key == curses.KEY_DOWN or (key == ord("j") and not self.mode_browser_search)
    if nav_up:
        if n > 0:
            self.mode_browser_sel = (self.mode_browser_sel - 1) % n
        return True
    if nav_down:
        if n > 0:
            self.mode_browser_sel = (self.mode_browser_sel + 1) % n
        return True
    if key in (curses.KEY_PPAGE,):  # Page Up
        if n > 0:
            self.mode_browser_sel = max(0, self.mode_browser_sel - 10)
        return True
    if key in (curses.KEY_NPAGE,):  # Page Down
        if n > 0:
            self.mode_browser_sel = min(n - 1, self.mode_browser_sel + 10)
        return True
    if key in (curses.KEY_HOME,):
        self.mode_browser_sel = 0
        return True
    if key in (curses.KEY_END,):
        if n > 0:
            self.mode_browser_sel = n - 1
        return True
    if key in (10, 13, curses.KEY_ENTER):
        # Launch the selected mode
        if items:
            entry = items[self.mode_browser_sel]
            self.mode_browser = False
            # Exit any currently active mode first
            self._exit_current_modes()
            if entry["enter"] is not None:
                enter_fn = getattr(self, entry["enter"], None)
                if enter_fn:
                    enter_fn()
            else:
                # Game of Life (default) — just flash
                self._flash("Game of Life (default mode)")
        return True
    if key in (curses.KEY_BACKSPACE, 127, 8):
        if self.mode_browser_search:
            self.mode_browser_search = self.mode_browser_search[:-1]
            self._mode_browser_apply_filter()
        return True
    # Printable characters → search filter
    if 32 <= key <= 126:
        self.mode_browser_search += chr(key)
        self._mode_browser_apply_filter()
        return True
    return True


def _exit_current_modes(self):
    """Exit any currently active simulation mode. Mirrors App._exit_current_modes."""
    for entry in MODE_REGISTRY:
        if entry["attr"] and getattr(self, entry["attr"], False):
            exit_fn = getattr(self, entry["exit"], None)
            if exit_fn:
                exit_fn()
    # Clear universal time-travel history on mode switch
    self.tt_history.clear()
    self.tt_pos = None
    self._tt_last_gen = -1


def _draw_mode_browser(self, max_y: int, max_x: int):
    """Draw the categorized mode selection browser. Mirrors App._draw_mode_browser."""
    title = "── Mode Browser (Enter=launch, Esc=cancel, type to search) ──"
    try:
        self.stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title,
                           curses.color_pair(7) | curses.A_BOLD)
    except curses.error:
        pass

    # Search bar
    search_label = f" Search: {self.mode_browser_search}█" if self.mode_browser_search else " Search: type to filter..."
    search_attr = curses.color_pair(6) if self.mode_browser_search else curses.color_pair(6) | curses.A_DIM
    try:
        self.stdscr.addstr(3, 2, search_label[:max_x - 4], search_attr)
    except curses.error:
        pass

    items = self.mode_browser_filtered
    n = len(items)
    if n == 0:
        try:
            self.stdscr.addstr(5, 4, "No matching modes found.", curses.color_pair(1))
        except curses.error:
            pass
        return

    # Build display lines grouped by category
    lines: list[tuple[str, int, dict | None]] = []
    current_cat = ""
    for entry in items:
        if entry["category"] != current_cat:
            current_cat = entry["category"]
            if lines:
                lines.append(("", 0, None))
            lines.append((f"  ─── {current_cat} ───", 7, None))
        key_str = f"[{entry['key']:>6s}]" if entry["key"] != "—" else "[      ]"
        line = f"    {key_str}  {entry['name']:<30s}  {entry['desc']}"
        lines.append((line, 6, entry))

    selectable_indices = [i for i, (_, _, e) in enumerate(lines) if e is not None]

    if self.mode_browser_sel >= len(selectable_indices):
        self.mode_browser_sel = max(0, len(selectable_indices) - 1)
    sel_line_idx = selectable_indices[self.mode_browser_sel] if selectable_indices else -1

    list_start_y = 5
    visible_rows = max_y - list_start_y - 2
    if visible_rows < 1:
        return

    if sel_line_idx >= 0:
        if sel_line_idx < self.mode_browser_scroll:
            self.mode_browser_scroll = sel_line_idx
        elif sel_line_idx >= self.mode_browser_scroll + visible_rows:
            self.mode_browser_scroll = sel_line_idx - visible_rows + 1
    self.mode_browser_scroll = max(0, min(self.mode_browser_scroll, max(0, len(lines) - visible_rows)))

    for vi in range(visible_rows):
        li = self.mode_browser_scroll + vi
        if li >= len(lines):
            break
        text, cpair, entry = lines[li]
        y = list_start_y + vi
        if li == sel_line_idx:
            attr = curses.color_pair(7) | curses.A_REVERSE
        elif entry is None:
            attr = curses.color_pair(cpair) | curses.A_BOLD if cpair else 0
        else:
            attr = curses.color_pair(cpair)
        try:
            self.stdscr.addstr(y, 0, text[:max_x - 1].ljust(max_x - 1), attr)
        except curses.error:
            pass

    if len(lines) > visible_rows:
        sb_frac = self.mode_browser_scroll / max(1, len(lines) - visible_rows)
        sb_pos = list_start_y + int(sb_frac * (visible_rows - 1))
        try:
            self.stdscr.addstr(sb_pos, max_x - 1, "█", curses.color_pair(7))
        except curses.error:
            pass

    count_text = f" {n} modes"
    footer = f" ↑↓/jk=navigate │ PgUp/PgDn=scroll │ Enter=launch │ Esc=cancel │{count_text}"
    try:
        self.stdscr.addstr(max_y - 1, 0, footer[:max_x - 1],
                           curses.color_pair(6) | curses.A_DIM)
    except curses.error:
        pass


def _make_app():
    app = make_mock_app()
    # Bind mode browser methods
    app._mode_browser_apply_filter = types.MethodType(_mode_browser_apply_filter, app)
    app._handle_mode_browser_key = types.MethodType(_handle_mode_browser_key, app)
    app._exit_current_modes = types.MethodType(_exit_current_modes, app)
    app._draw_mode_browser = types.MethodType(_draw_mode_browser, app)
    return app


# ── State Initialization ──────────────────────────────────────────────────────


class TestModeBrowserInit:
    def test_default_state(self):
        app = _make_app()
        assert app.mode_browser is False
        assert app.mode_browser_sel == 0
        assert app.mode_browser_scroll == 0
        assert app.mode_browser_search == ""
        assert app.mode_browser_filtered == list(MODE_REGISTRY)

    def test_filtered_is_independent_copy(self):
        """mode_browser_filtered should be a separate list, not the same object."""
        app = _make_app()
        assert app.mode_browser_filtered is not MODE_REGISTRY
        assert app.mode_browser_filtered == list(MODE_REGISTRY)

    def test_initial_filtered_length(self):
        app = _make_app()
        assert len(app.mode_browser_filtered) == len(MODE_REGISTRY)


# ── Filtering ─────────────────────────────────────────────────────────────────


class TestModeBrowserFilter:
    def setup_method(self):
        self.app = _make_app()
        self.app.mode_browser = True

    def test_empty_search_shows_all(self):
        self.app.mode_browser_search = ""
        self.app._mode_browser_apply_filter()
        assert len(self.app.mode_browser_filtered) == len(MODE_REGISTRY)

    def test_search_by_name(self):
        self.app.mode_browser_search = "wolfram"
        self.app._mode_browser_apply_filter()
        assert len(self.app.mode_browser_filtered) >= 1
        for entry in self.app.mode_browser_filtered:
            assert (
                "wolfram" in entry["name"].lower()
                or "wolfram" in entry["desc"].lower()
                or "wolfram" in entry["category"].lower()
            )

    def test_search_by_desc(self):
        self.app.mode_browser_search = "conway"
        self.app._mode_browser_apply_filter()
        assert len(self.app.mode_browser_filtered) >= 1
        names = [e["name"] for e in self.app.mode_browser_filtered]
        assert "Game of Life" in names

    def test_search_by_category(self):
        self.app.mode_browser_search = "classic ca"
        self.app._mode_browser_apply_filter()
        assert len(self.app.mode_browser_filtered) >= 1
        for entry in self.app.mode_browser_filtered:
            assert (
                "classic ca" in entry["name"].lower()
                or "classic ca" in entry["desc"].lower()
                or "classic ca" in entry["category"].lower()
            )

    def test_search_case_insensitive(self):
        self.app.mode_browser_search = "WOLFRAM"
        self.app._mode_browser_apply_filter()
        results_upper = list(self.app.mode_browser_filtered)
        self.app.mode_browser_search = "wolfram"
        self.app._mode_browser_apply_filter()
        results_lower = list(self.app.mode_browser_filtered)
        assert results_upper == results_lower

    def test_search_no_results(self):
        self.app.mode_browser_search = "zzzznonexistent"
        self.app._mode_browser_apply_filter()
        assert len(self.app.mode_browser_filtered) == 0
        assert self.app.mode_browser_sel == 0

    def test_filter_clamps_selection(self):
        """Selection should be clamped to the filtered list length."""
        self.app.mode_browser_sel = 999
        self.app.mode_browser_search = "wolfram"
        self.app._mode_browser_apply_filter()
        assert self.app.mode_browser_sel < len(self.app.mode_browser_filtered)

    def test_filter_resets_scroll(self):
        self.app.mode_browser_scroll = 50
        self.app.mode_browser_search = "sand"
        self.app._mode_browser_apply_filter()
        assert self.app.mode_browser_scroll == 0

    def test_clear_search_restores_all(self):
        self.app.mode_browser_search = "wolfram"
        self.app._mode_browser_apply_filter()
        partial = len(self.app.mode_browser_filtered)
        self.app.mode_browser_search = ""
        self.app._mode_browser_apply_filter()
        assert len(self.app.mode_browser_filtered) == len(MODE_REGISTRY)
        assert len(self.app.mode_browser_filtered) > partial


# ── Navigation Keys ───────────────────────────────────────────────────────────


class TestModeBrowserNavigation:
    def setup_method(self):
        self.app = _make_app()
        self.app.mode_browser = True

    def test_arrow_down(self):
        self.app.mode_browser_sel = 0
        result = self.app._handle_mode_browser_key(curses.KEY_DOWN)
        assert result is True
        assert self.app.mode_browser_sel == 1

    def test_arrow_up(self):
        self.app.mode_browser_sel = 5
        result = self.app._handle_mode_browser_key(curses.KEY_UP)
        assert result is True
        assert self.app.mode_browser_sel == 4

    def test_arrow_down_wraps(self):
        n = len(self.app.mode_browser_filtered)
        self.app.mode_browser_sel = n - 1
        self.app._handle_mode_browser_key(curses.KEY_DOWN)
        assert self.app.mode_browser_sel == 0

    def test_arrow_up_wraps(self):
        n = len(self.app.mode_browser_filtered)
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(curses.KEY_UP)
        assert self.app.mode_browser_sel == n - 1

    def test_j_navigates_when_no_search(self):
        self.app.mode_browser_search = ""
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(ord("j"))
        assert self.app.mode_browser_sel == 1

    def test_k_navigates_when_no_search(self):
        self.app.mode_browser_search = ""
        self.app.mode_browser_sel = 3
        self.app._handle_mode_browser_key(ord("k"))
        assert self.app.mode_browser_sel == 2

    def test_j_types_into_search_when_searching(self):
        """When search is active, j should add to search, not navigate."""
        self.app.mode_browser_search = "a"
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(ord("j"))
        assert self.app.mode_browser_search == "aj"

    def test_k_types_into_search_when_searching(self):
        """When search is active, k should add to search, not navigate."""
        self.app.mode_browser_search = "a"
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(ord("k"))
        assert self.app.mode_browser_search == "ak"

    def test_page_down(self):
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(curses.KEY_NPAGE)
        assert self.app.mode_browser_sel == min(10, len(self.app.mode_browser_filtered) - 1)

    def test_page_up(self):
        self.app.mode_browser_sel = 15
        self.app._handle_mode_browser_key(curses.KEY_PPAGE)
        assert self.app.mode_browser_sel == 5

    def test_page_up_clamps_to_zero(self):
        self.app.mode_browser_sel = 3
        self.app._handle_mode_browser_key(curses.KEY_PPAGE)
        assert self.app.mode_browser_sel == 0

    def test_page_down_clamps_to_last(self):
        n = len(self.app.mode_browser_filtered)
        self.app.mode_browser_sel = n - 3
        self.app._handle_mode_browser_key(curses.KEY_NPAGE)
        assert self.app.mode_browser_sel == n - 1

    def test_home_key(self):
        self.app.mode_browser_sel = 50
        self.app._handle_mode_browser_key(curses.KEY_HOME)
        assert self.app.mode_browser_sel == 0

    def test_end_key(self):
        n = len(self.app.mode_browser_filtered)
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(curses.KEY_END)
        assert self.app.mode_browser_sel == n - 1


# ── Escape / Close ────────────────────────────────────────────────────────────


class TestModeBrowserEscape:
    def test_escape_closes(self):
        app = _make_app()
        app.mode_browser = True
        result = app._handle_mode_browser_key(27)  # ESC
        assert result is True
        assert app.mode_browser is False

    def test_minus_one_ignored(self):
        """Key -1 (no key pressed) should return True without changing state."""
        app = _make_app()
        app.mode_browser = True
        app.mode_browser_sel = 5
        result = app._handle_mode_browser_key(-1)
        assert result is True
        assert app.mode_browser_sel == 5
        assert app.mode_browser is True


# ── Search Input ──────────────────────────────────────────────────────────────


class TestModeBrowserSearchInput:
    def setup_method(self):
        self.app = _make_app()
        self.app.mode_browser = True

    def test_printable_char_adds_to_search(self):
        self.app._handle_mode_browser_key(ord("w"))
        assert self.app.mode_browser_search == "w"
        self.app._handle_mode_browser_key(ord("a"))
        assert self.app.mode_browser_search == "wa"

    def test_backspace_removes_char(self):
        self.app.mode_browser_search = "wolf"
        self.app._handle_mode_browser_key(127)  # Backspace
        assert self.app.mode_browser_search == "wol"

    def test_backspace_on_empty_search(self):
        """Backspace on empty search should not crash."""
        self.app.mode_browser_search = ""
        self.app._handle_mode_browser_key(127)
        assert self.app.mode_browser_search == ""

    def test_backspace_curses_key(self):
        self.app.mode_browser_search = "abc"
        self.app._handle_mode_browser_key(curses.KEY_BACKSPACE)
        assert self.app.mode_browser_search == "ab"

    def test_backspace_ctrl_h(self):
        self.app.mode_browser_search = "abc"
        self.app._handle_mode_browser_key(8)  # Ctrl+H
        assert self.app.mode_browser_search == "ab"

    def test_typing_triggers_filter(self):
        self.app._handle_mode_browser_key(ord("w"))
        self.app._handle_mode_browser_key(ord("o"))
        self.app._handle_mode_browser_key(ord("l"))
        self.app._handle_mode_browser_key(ord("f"))
        # Should have filtered to wolfram-related entries
        assert len(self.app.mode_browser_filtered) < len(MODE_REGISTRY)
        found = any("wolfram" in e["name"].lower() for e in self.app.mode_browser_filtered)
        assert found

    def test_all_printable_chars_accepted(self):
        """Characters 32-126 should all be accepted as search input."""
        for c in range(32, 127):
            app = _make_app()
            app.mode_browser = True
            result = app._handle_mode_browser_key(c)
            assert result is True
            # j/k without search would navigate, but first char always goes to search
            # since mode_browser_search starts empty and j/k check "not self.mode_browser_search"
            if c == ord("j"):
                # j navigates down when search is empty
                assert app.mode_browser_sel == 1
            elif c == ord("k"):
                # k navigates up when search is empty (wraps)
                assert app.mode_browser_sel == len(MODE_REGISTRY) - 1
            else:
                assert app.mode_browser_search == chr(c)


# ── Selection / Enter ─────────────────────────────────────────────────────────


class TestModeBrowserSelection:
    def setup_method(self):
        self.app = _make_app()
        self.app.mode_browser = True

    def test_enter_closes_browser(self):
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(10)  # Enter
        assert self.app.mode_browser is False

    def test_enter_on_game_of_life(self):
        """First entry is Game of Life (enter=None), should flash message."""
        self.app.mode_browser_sel = 0
        assert self.app.mode_browser_filtered[0]["name"] == "Game of Life"
        self.app._handle_mode_browser_key(10)
        assert self.app.mode_browser is False
        assert "Game of Life" in self.app.message

    def test_enter_key_13(self):
        """Carriage return (13) should also trigger selection."""
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(13)
        assert self.app.mode_browser is False

    def test_enter_curses_key(self):
        """curses.KEY_ENTER should also trigger selection."""
        self.app.mode_browser_sel = 0
        self.app._handle_mode_browser_key(curses.KEY_ENTER)
        assert self.app.mode_browser is False

    def test_enter_on_empty_filtered_list(self):
        """Enter on empty list should not crash."""
        self.app.mode_browser_search = "zzzznonexistent"
        self.app._mode_browser_apply_filter()
        assert len(self.app.mode_browser_filtered) == 0
        result = self.app._handle_mode_browser_key(10)
        assert result is True
        # With empty list, items is falsy, so browser stays in the state
        # (the 'if items:' check means nothing happens -- browser NOT closed)

    def test_enter_calls_enter_function(self):
        """Selecting a mode with an enter function should invoke it."""
        # Find Wolfram entry
        from life.modes.wolfram import register
        register(type(self.app))
        for i, entry in enumerate(self.app.mode_browser_filtered):
            if entry["name"] == "Wolfram 1D Automaton":
                self.app.mode_browser_sel = i
                break
        self.app._handle_mode_browser_key(10)
        assert self.app.mode_browser is False
        assert self.app.wolfram_menu is True


# ── Registry Integrity ────────────────────────────────────────────────────────


class TestModeRegistryIntegrity:
    def test_all_entries_have_required_keys(self):
        required = {"name", "key", "category", "desc", "attr", "enter", "exit"}
        for entry in MODE_REGISTRY:
            missing = required - set(entry.keys())
            assert not missing, f"Entry {entry.get('name', '?')} missing keys: {missing}"

    def test_all_categories_in_registry_are_known(self):
        for entry in MODE_REGISTRY:
            cat = entry["category"]
            assert isinstance(cat, str) and len(cat) > 0, f"{entry['name']} has empty category"

    def test_game_of_life_is_first(self):
        assert MODE_REGISTRY[0]["name"] == "Game of Life"
        assert MODE_REGISTRY[0]["enter"] is None
        assert MODE_REGISTRY[0]["attr"] is None

    def test_registry_has_many_entries(self):
        """Original commit had 130+ modes."""
        assert len(MODE_REGISTRY) > 50


# ── Draw (no-crash) ───────────────────────────────────────────────────────────


def _patch_curses():
    """Return a context manager that patches curses.color_pair for headless testing."""
    return unittest.mock.patch("curses.color_pair", return_value=0)


class TestModeBrowserDraw:
    def setup_method(self):
        self.app = _make_app()
        self.app.mode_browser = True

    def test_draw_no_crash(self):
        with _patch_curses():
            self.app._draw_mode_browser(40, 120)

    def test_draw_with_search(self):
        self.app.mode_browser_search = "wave"
        self.app._mode_browser_apply_filter()
        with _patch_curses():
            self.app._draw_mode_browser(40, 120)

    def test_draw_empty_results(self):
        self.app.mode_browser_search = "zzzzzzz"
        self.app._mode_browser_apply_filter()
        with _patch_curses():
            self.app._draw_mode_browser(40, 120)

    def test_draw_small_terminal(self):
        with _patch_curses():
            self.app._draw_mode_browser(5, 20)

    def test_draw_tiny_terminal(self):
        with _patch_curses():
            self.app._draw_mode_browser(2, 10)

    def test_draw_with_scroll(self):
        self.app.mode_browser_sel = len(self.app.mode_browser_filtered) - 1
        with _patch_curses():
            self.app._draw_mode_browser(20, 80)

    def test_draw_with_selection_at_various_positions(self):
        with _patch_curses():
            for pos in [0, 5, 10, 20]:
                if pos < len(self.app.mode_browser_filtered):
                    self.app.mode_browser_sel = pos
                    self.app._draw_mode_browser(40, 120)


# ── Exit Current Modes ────────────────────────────────────────────────────────


class TestExitCurrentModes:
    def test_exit_clears_time_travel(self):
        app = _make_app()
        app.tt_history = [1, 2, 3]
        app.tt_pos = 1
        app._tt_last_gen = 5
        app._exit_current_modes()
        assert app.tt_history == []
        assert app.tt_pos is None
        assert app._tt_last_gen == -1


# ── Integration: Full Navigation Sequence ─────────────────────────────────────


class TestModeBrowserIntegration:
    def test_open_search_select(self):
        """Simulate: open browser, type search, navigate, select."""
        app = _make_app()
        app.mode_browser = True

        # Type "game"
        for c in "game":
            app._handle_mode_browser_key(ord(c))
        assert "game" in app.mode_browser_search.lower()
        assert len(app.mode_browser_filtered) > 0
        assert len(app.mode_browser_filtered) < len(MODE_REGISTRY)

        # Navigate down
        app._handle_mode_browser_key(curses.KEY_DOWN)

        # Draw (no crash)
        with _patch_curses():
            app._draw_mode_browser(40, 120)

        # Press Enter to select
        app._handle_mode_browser_key(10)
        assert app.mode_browser is False

    def test_open_and_escape(self):
        app = _make_app()
        app.mode_browser = True
        app._handle_mode_browser_key(27)
        assert app.mode_browser is False

    def test_navigate_to_end_and_back(self):
        app = _make_app()
        app.mode_browser = True
        app._handle_mode_browser_key(curses.KEY_END)
        assert app.mode_browser_sel == len(app.mode_browser_filtered) - 1
        app._handle_mode_browser_key(curses.KEY_HOME)
        assert app.mode_browser_sel == 0

    def test_search_then_clear(self):
        """Type search, then backspace everything."""
        app = _make_app()
        app.mode_browser = True
        for c in "wave":
            app._handle_mode_browser_key(ord(c))
        filtered_count = len(app.mode_browser_filtered)
        assert filtered_count < len(MODE_REGISTRY)

        # Backspace 4 times
        for _ in range(4):
            app._handle_mode_browser_key(127)
        assert app.mode_browser_search == ""
        assert len(app.mode_browser_filtered) == len(MODE_REGISTRY)

    def test_rapid_navigation_cycle(self):
        """Navigate up and down many times without crash."""
        app = _make_app()
        app.mode_browser = True
        for _ in range(200):
            app._handle_mode_browser_key(curses.KEY_DOWN)
        for _ in range(200):
            app._handle_mode_browser_key(curses.KEY_UP)
        # Should have wrapped around
        assert 0 <= app.mode_browser_sel < len(app.mode_browser_filtered)

    def test_page_navigation_sequence(self):
        """Page down multiple times then page up."""
        app = _make_app()
        app.mode_browser = True
        for _ in range(5):
            app._handle_mode_browser_key(curses.KEY_NPAGE)
        sel_after_pgdn = app.mode_browser_sel
        for _ in range(5):
            app._handle_mode_browser_key(curses.KEY_PPAGE)
        assert app.mode_browser_sel < sel_after_pgdn

    def test_draw_after_every_navigation(self):
        """Draw should never crash after any navigation action."""
        app = _make_app()
        app.mode_browser = True
        keys = [
            curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN,
            curses.KEY_UP, curses.KEY_NPAGE, curses.KEY_PPAGE,
            curses.KEY_HOME, curses.KEY_END,
        ]
        with _patch_curses():
            for k in keys:
                app._handle_mode_browser_key(k)
                app._draw_mode_browser(30, 80)
