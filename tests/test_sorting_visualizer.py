"""Tests for life.modes.sorting_visualizer — Sorting Visualizer mode."""
import curses
from tests.conftest import make_mock_app
from life.modes.sorting_visualizer import (
    register,
    SORTVIS_PRESETS,
    _sortvis_generate_steps_bubble,
    _sortvis_generate_steps_quick,
    _sortvis_generate_steps_merge,
    _sortvis_generate_steps_heap,
    _sortvis_generate_steps_radix,
    _sortvis_generate_steps_shell,
)


def _make_app():
    app = make_mock_app()
    app.sortvis_mode = False
    app.sortvis_menu = False
    app.sortvis_menu_sel = 0
    app.sortvis_running = False
    app.sortvis_speed = 1
    app.sortvis_show_info = False
    app.sortvis_steps = []
    app.sortvis_array = []
    app.sortvis_sorted_indices = set()
    register(type(app))
    return app


# ── Entry / Exit ──

def test_enter():
    app = _make_app()
    app._enter_sortvis_mode()
    assert app.sortvis_menu is True
    assert app.sortvis_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.sortvis_mode = True
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app._exit_sortvis_mode()
    assert app.sortvis_mode is False
    assert app.sortvis_steps == []
    assert app.sortvis_array == []
    assert app.sortvis_sorted_indices == set()
    assert app.sortvis_running is False


# ── Pure sorting algorithm correctness ──

def test_bubble_sort_correctness():
    arr = [5, 3, 8, 1, 2]
    steps = _sortvis_generate_steps_bubble(arr)
    assert len(steps) > 0
    # Final state from last "sorted" step should be sorted
    final_arr = steps[-1][-1] if len(steps[-1]) == 3 else steps[-1][3]
    # Get the actual sorted state from the accumulated steps
    last_arr = None
    for s in steps:
        if s[0] in ("cmp", "swap") and len(s) == 4:
            last_arr = s[3]
        elif s[0] == "sorted" and len(s) == 3:
            last_arr = s[2]
    assert last_arr == sorted(arr)


def test_quick_sort_correctness():
    arr = [9, 4, 7, 2, 5, 1, 8, 3, 6]
    steps = _sortvis_generate_steps_quick(arr)
    assert len(steps) > 0
    # Extract final array state
    last_arr = None
    for s in steps:
        if len(s) >= 3:
            candidate = s[-1] if isinstance(s[-1], list) else None
            if candidate is not None:
                last_arr = candidate
    assert last_arr == sorted(arr)


def test_merge_sort_correctness():
    arr = [5, 2, 8, 1, 9, 3]
    steps = _sortvis_generate_steps_merge(arr)
    assert len(steps) > 0
    # The last steps should be "sorted" markers
    last_arr = None
    for s in steps:
        if s[0] in ("write", "sorted") and len(s) == 3:
            last_arr = s[2]
    assert last_arr == sorted(arr)


def test_heap_sort_correctness():
    arr = [4, 10, 3, 5, 1]
    steps = _sortvis_generate_steps_heap(arr)
    assert len(steps) > 0
    last_arr = None
    for s in steps:
        if s[0] == "sorted" and len(s) == 3:
            last_arr = s[2]
    assert last_arr == sorted(arr)


def test_radix_sort_correctness():
    arr = [170, 45, 75, 90, 802, 24, 2, 66]
    steps = _sortvis_generate_steps_radix(arr)
    assert len(steps) > 0
    last_arr = None
    for s in steps:
        if s[0] == "sorted" and len(s) == 3:
            last_arr = s[2]
    assert last_arr == sorted(arr)


def test_shell_sort_correctness():
    arr = [12, 34, 54, 2, 3]
    steps = _sortvis_generate_steps_shell(arr)
    assert len(steps) > 0
    last_arr = None
    for s in steps:
        if s[0] == "sorted" and len(s) == 3:
            last_arr = s[2]
    assert last_arr == sorted(arr)


def test_bubble_sort_empty():
    steps = _sortvis_generate_steps_bubble([])
    assert steps == []


def test_bubble_sort_single():
    steps = _sortvis_generate_steps_bubble([42])
    # Single element: one sorted marker
    assert any(s[0] == "sorted" for s in steps)


def test_radix_sort_empty():
    steps = _sortvis_generate_steps_radix([])
    assert steps == []


# ── Init and step mechanics ──

def test_init_creates_array():
    app = _make_app()
    app._sortvis_init("bubble")
    assert len(app.sortvis_array) > 0
    assert app.sortvis_generation == 0
    assert app.sortvis_step_idx == 0
    assert app.sortvis_comparisons == 0
    assert app.sortvis_swaps == 0
    assert app.sortvis_done is False
    assert app.sortvis_algorithm == "bubble"


def test_init_all_presets():
    """All 6 presets initialize without error."""
    app = _make_app()
    for _, _, key in SORTVIS_PRESETS:
        app._sortvis_init(key)
        assert len(app.sortvis_array) > 0
        assert len(app.sortvis_steps) > 0


def test_step_advances():
    app = _make_app()
    app._sortvis_init("bubble")
    initial_idx = app.sortvis_step_idx
    app._sortvis_step()
    assert app.sortvis_step_idx == initial_idx + 1
    assert app.sortvis_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.sortvis_mode = True
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    for _ in range(10):
        app._sortvis_step()
    assert app.sortvis_generation >= 0


def test_step_counts_comparisons_and_swaps():
    app = _make_app()
    app._sortvis_init("bubble")
    # Run all steps
    while not app.sortvis_done:
        app._sortvis_step()
    assert app.sortvis_comparisons > 0
    assert app.sortvis_swaps >= 0  # could be 0 if already sorted (unlikely)
    assert app.sortvis_done is True
    assert app.sortvis_sorted_indices == set(range(len(app.sortvis_array)))


def test_step_past_end_is_safe():
    app = _make_app()
    app._sortvis_init("bubble")
    # Exhaust all steps
    for _ in range(len(app.sortvis_steps) + 10):
        app._sortvis_step()
    assert app.sortvis_done is True
    assert app.sortvis_running is False


def test_step_with_quick():
    app = _make_app()
    app._sortvis_init("quick")
    for _ in range(20):
        app._sortvis_step()
    assert app.sortvis_generation == 20


def test_step_with_merge():
    app = _make_app()
    app._sortvis_init("merge")
    for _ in range(20):
        app._sortvis_step()
    assert app.sortvis_generation == 20


# ── Menu key handling ──

def test_menu_key_down():
    app = _make_app()
    app._enter_sortvis_mode()
    app._handle_sortvis_menu_key(curses.KEY_DOWN)
    assert app.sortvis_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_sortvis_mode()
    app._handle_sortvis_menu_key(curses.KEY_UP)
    assert app.sortvis_menu_sel == len(SORTVIS_PRESETS) - 1


def test_menu_key_enter_starts():
    app = _make_app()
    app._enter_sortvis_mode()
    app._handle_sortvis_menu_key(10)  # Enter
    assert app.sortvis_mode is True
    assert app.sortvis_running is True
    assert app.sortvis_menu is False


def test_menu_key_quit():
    app = _make_app()
    app._enter_sortvis_mode()
    app.sortvis_mode = True
    app._handle_sortvis_menu_key(ord('q'))
    assert app.sortvis_mode is False


# ── Simulation key handling ──

def test_key_space_toggles_running():
    app = _make_app()
    app.sortvis_mode = True
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app.sortvis_running = True
    app._handle_sortvis_key(ord(' '))
    assert app.sortvis_running is False
    app._handle_sortvis_key(ord(' '))
    assert app.sortvis_running is True


def test_key_n_steps():
    app = _make_app()
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    gen_before = app.sortvis_generation
    app._handle_sortvis_key(ord('n'))
    assert app.sortvis_generation == gen_before + 1


def test_key_r_resets():
    app = _make_app()
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    for _ in range(10):
        app._sortvis_step()
    app._handle_sortvis_key(ord('r'))
    assert app.sortvis_generation == 0
    assert app.sortvis_step_idx == 0


def test_key_plus_minus_speed():
    app = _make_app()
    app.sortvis_speed = 5
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app._handle_sortvis_key(ord('+'))
    assert app.sortvis_speed == 6
    app._handle_sortvis_key(ord('-'))
    assert app.sortvis_speed == 5


def test_key_i_toggles_info():
    app = _make_app()
    app.sortvis_show_info = False
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app._handle_sortvis_key(ord('i'))
    assert app.sortvis_show_info is True


def test_key_R_returns_to_menu():
    app = _make_app()
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app.sortvis_running = True
    app._handle_sortvis_key(ord('R'))
    assert app.sortvis_menu is True
    assert app.sortvis_running is False


def test_key_q_exits():
    app = _make_app()
    app.sortvis_mode = True
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app._handle_sortvis_key(ord('q'))
    assert app.sortvis_mode is False


# ── Drawing (no crash) ──

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_sortvis_mode()
    app._draw_sortvis_menu(40, 120)


def test_draw_sortvis_no_crash():
    app = _make_app()
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app.sortvis_show_info = True
    for _ in range(5):
        app._sortvis_step()
    app._draw_sortvis(40, 120)


def test_draw_sortvis_small_terminal():
    app = _make_app()
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    app._draw_sortvis(5, 10)  # too small


def test_draw_sortvis_done():
    app = _make_app()
    app.sortvis_preset_name = "bubble"
    app._sortvis_init("bubble")
    while not app.sortvis_done:
        app._sortvis_step()
    app._draw_sortvis(40, 120)


# ── No leaked data ──

def test_no_dna_helix_presets_leaked():
    """sorting_visualizer.py should not contain DNAHELIX_PRESETS."""
    import life.modes.sorting_visualizer as mod
    assert not hasattr(mod, 'DNAHELIX_PRESETS')


# ── Presets data ──

def test_presets_structure():
    assert len(SORTVIS_PRESETS) == 6
    for name, desc, key in SORTVIS_PRESETS:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str)
        assert key in ("bubble", "quick", "merge", "heap", "radix", "shell")
