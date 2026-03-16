"""Test mode wiring: verify every MODE_REGISTRY entry is routed correctly.

With the table-driven dispatch architecture, most modes are wired automatically
via MODE_DISPATCH.  These tests verify:
  1. Coverage — every registry entry is either table-dispatched or explicitly handled
  2. Init — every mode flag is initialized in __init__
  3. Dispatch table integrity — handler/draw/step methods exist on the App class
  4. Enter/exit methods exist
  5. Menu handler sets mode flag
  6. _any_menu_open detects every mode menu
"""
import inspect
import re

import pytest

from life.registry import MODE_REGISTRY, MODE_DISPATCH


# ── Load app.py source once ──────────────────────────────────────────────────
def _load_app_source():
    import life.app as app_mod
    return inspect.getsource(app_mod)


APP_SOURCE = _load_app_source()

# Split source into sections for targeted checks
_init_match = re.search(r'def __init__\(self.*?\n(.*?)(?=\n    def )', APP_SOURCE, re.DOTALL)
INIT_SOURCE = _init_match.group(1) if _init_match else ""

_any_menu_match = re.search(r'def _any_menu_open\(self\).*?(?=\n    def )', APP_SOURCE, re.DOTALL)
ANY_MENU_SOURCE = _any_menu_match.group(0) if _any_menu_match else ""


# ── Build test parameter lists ─────────────────────────────────────────────
SKIP_ATTRS = {
    None,             # Game of Life (attr=None), Topology, Visual FX
    'cast_recording', # Special toggle, not a standard mode
}

SKIP_ENTER_NONE = {
    'tbranch_mode',   # enter=None, activated via scrubbing
}


def _standard_modes():
    """Yield (attr, entry) for modes that should follow standard wiring."""
    seen = set()
    for entry in MODE_REGISTRY:
        attr = entry.get('attr')
        if attr in SKIP_ATTRS:
            continue
        if attr in seen:
            continue
        seen.add(attr)
        if attr in SKIP_ENTER_NONE and entry.get('enter') is None:
            continue
        yield attr, entry


STANDARD_MODES = list(_standard_modes())
MODE_IDS = [attr for attr, _ in STANDARD_MODES]

# Attrs routed through MODE_DISPATCH
DISPATCHED_ATTRS = {md['attr'] for md in MODE_DISPATCH}

# Build dispatch table entries keyed by attr for quick lookup
DISPATCH_BY_ATTR = {md['attr']: md for md in MODE_DISPATCH}


# ── Detect which modes have menus ────────────────────────────────────────────
def _mode_has_menu(attr):
    prefix = attr.replace('_mode', '')
    menu_attr = f'{prefix}_menu'
    return f'self.{menu_attr}' in APP_SOURCE


def _get_menu_attr(attr):
    prefix = attr.replace('_mode', '')
    return f'{prefix}_menu'


MODES_WITH_MENUS = [(attr, entry) for attr, entry in STANDARD_MODES if _mode_has_menu(attr)]
MENU_IDS = [attr for attr, _ in MODES_WITH_MENUS]

# Dispatch table entries
DISPATCH_ENTRIES = [(md['attr'], md) for md in MODE_DISPATCH]
DISPATCH_IDS = [md['attr'] for md in MODE_DISPATCH]


# ══════════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDispatchCoverage:
    """Every MODE_REGISTRY entry must be either in MODE_DISPATCH or explicitly handled."""

    # Modes handled explicitly in app.py (not via dispatch table)
    EXPLICIT_MODES = {
        'compare_mode', 'race_mode', 'puzzle_mode', 'iso_mode', 'hex_mode',
        'heatmap_mode', 'pattern_search_mode', 'blueprint_mode', 'mp_mode',
        'tbranch_mode', 'screensaver_mode', 'evo_mode', 'script_mode',
    }

    @pytest.mark.parametrize("attr", MODE_IDS, ids=MODE_IDS)
    def test_mode_is_dispatched_or_explicit(self, attr):
        assert attr in DISPATCHED_ATTRS or attr in self.EXPLICIT_MODES, (
            f"{attr} is neither in MODE_DISPATCH nor in the explicit handler set"
        )


class TestModeAttrInit:
    """Every mode's boolean flag must be initialized to False in __init__."""

    @pytest.mark.parametrize("attr", MODE_IDS, ids=MODE_IDS)
    def test_init_present(self, attr):
        pattern = rf'self\.{re.escape(attr)}\s*[:=]'
        assert re.search(pattern, INIT_SOURCE), (
            f"self.{attr} not initialized in App.__init__"
        )


class TestDispatchTableIntegrity:
    """Dispatch table entries must reference valid methods on the App class."""

    @pytest.mark.parametrize("attr,md", DISPATCH_ENTRIES, ids=DISPATCH_IDS)
    def test_key_handler_exists(self, attr, md):
        import life.app
        app_cls = life.app.App
        assert hasattr(app_cls, md['keys']), (
            f"Key handler {md['keys']} not found on App for {attr}"
        )

    @pytest.mark.parametrize("attr,md", DISPATCH_ENTRIES, ids=DISPATCH_IDS)
    def test_draw_method_exists(self, attr, md):
        import life.app
        app_cls = life.app.App
        assert hasattr(app_cls, md['draw']), (
            f"Draw method {md['draw']} not found on App for {attr}"
        )

    @pytest.mark.parametrize("attr,md", DISPATCH_ENTRIES, ids=DISPATCH_IDS)
    def test_step_method_exists(self, attr, md):
        if md['no_step']:
            pytest.skip(f"{attr} has no_step=True")
        import life.app
        app_cls = life.app.App
        assert hasattr(app_cls, md['step']), (
            f"Step method {md['step']} not found on App for {attr}"
        )


class TestDispatchMenuIntegrity:
    """Dispatch entries with menus must have valid menu methods."""

    # Only include dispatch entries where the menu_attr follows the standard
    # convention (prefix_menu) — modes that handle menus internally are excluded
    MENU_DISPATCH = [(md['attr'], md) for md in MODE_DISPATCH
                     if md['menu_attr'] == f"{md['prefix']}_menu"
                     and _mode_has_menu(md['attr'])]
    MENU_DISPATCH_IDS = [md['attr'] for _, md in MENU_DISPATCH]

    @pytest.mark.parametrize("attr,md", MENU_DISPATCH, ids=MENU_DISPATCH_IDS)
    def test_menu_key_handler_exists(self, attr, md):
        import life.app
        app_cls = life.app.App
        assert hasattr(app_cls, md['menu_keys']), (
            f"Menu key handler {md['menu_keys']} not found on App for {attr}"
        )

    @pytest.mark.parametrize("attr,md", MENU_DISPATCH, ids=MENU_DISPATCH_IDS)
    def test_menu_draw_method_exists(self, attr, md):
        import life.app
        app_cls = life.app.App
        assert hasattr(app_cls, md['menu_draw']), (
            f"Menu draw method {md['menu_draw']} not found on App for {attr}"
        )


class TestMenuInAnyMenuOpen:
    """Modes with menus must be detectable by _any_menu_open()."""

    @pytest.mark.parametrize("attr", MENU_IDS, ids=MENU_IDS)
    def test_menu_in_any_menu_open(self, attr):
        menu_attr = _get_menu_attr(attr)
        # Menu is either in the fixed list or detected via MODE_DISPATCH iteration
        in_fixed = f"'{menu_attr}'" in ANY_MENU_SOURCE
        in_dispatch = attr in DISPATCHED_ATTRS
        assert in_fixed or in_dispatch, (
            f"'{menu_attr}' not detectable by _any_menu_open()"
        )


class TestModeMethodsRegistered:
    """Enter and exit functions must exist on the App class."""

    @pytest.mark.parametrize("attr,entry", STANDARD_MODES, ids=MODE_IDS)
    def test_enter_exit_exist(self, attr, entry):
        import life.app
        app_cls = life.app.App
        enter_fn = entry.get('enter')
        exit_fn = entry.get('exit')

        if enter_fn:
            assert hasattr(app_cls, enter_fn), (
                f"Enter function {enter_fn} not found for {attr}"
            )

        if exit_fn:
            assert hasattr(app_cls, exit_fn), (
                f"Exit function {exit_fn} not found for {attr}"
            )


class TestMenuHandlerSetsMode:
    """Selecting a preset from the menu must eventually set self.{attr} = True."""

    SKIP = {
        'compare_mode', 'race_mode', 'puzzle_mode', 'evo_mode', 'mp_mode',
        'screensaver_mode', 'heatmap_mode', 'pattern_search_mode',
        'iso_mode', 'hex_mode', 'blueprint_mode',
    }

    @pytest.mark.parametrize("attr,entry", MODES_WITH_MENUS, ids=MENU_IDS)
    def test_menu_sets_mode_flag(self, attr, entry):
        if attr in self.SKIP:
            pytest.skip(f"{attr} has non-standard menu flow")

        enter_fn = entry.get('enter', '')
        if not enter_fn:
            pytest.skip("No enter function")

        import life.app
        app_cls = life.app.App
        if hasattr(app_cls, enter_fn):
            fn = getattr(app_cls, enter_fn)
            mod = inspect.getmodule(fn)
            if mod:
                mod_source = inspect.getsource(mod)
                assert f'self.{attr} = True' in mod_source, (
                    f"self.{attr} = True not found in module defining {enter_fn}"
                )


class TestExplicitModesInSource:
    """Modes handled explicitly must still be referenced in run() and _draw()."""

    _run_match = re.search(r'def run\(self\):\n(.*)', APP_SOURCE, re.DOTALL)
    RUN_SOURCE = _run_match.group(1) if _run_match else ""

    _draw_match = re.search(r'def _draw\(self\):\n(.*?)(?=\n    def )', APP_SOURCE, re.DOTALL)
    DRAW_SOURCE = _draw_match.group(1) if _draw_match else ""

    EXPLICIT_KEY = {
        'screensaver_mode', 'puzzle_mode', 'evo_mode', 'script_mode',
    }
    EXPLICIT_DRAW = {
        'script_mode', 'screensaver_mode', 'evo_mode', 'puzzle_mode',
        'compare_mode', 'race_mode', 'iso_mode', 'mp_mode', 'tbranch_mode',
    }

    @pytest.mark.parametrize("attr", sorted(EXPLICIT_KEY))
    def test_explicit_key_in_run(self, attr):
        assert f'self.{attr}' in self.RUN_SOURCE, (
            f"Explicitly-handled {attr} not found in run()"
        )

    @pytest.mark.parametrize("attr", sorted(EXPLICIT_DRAW))
    def test_explicit_draw_in_draw(self, attr):
        # screensaver draws as overlay, not in _draw()
        if attr == 'screensaver_mode':
            assert f'self.{attr}' in APP_SOURCE
            return
        assert f'self.{attr}' in self.DRAW_SOURCE, (
            f"Explicitly-handled {attr} not found in _draw()"
        )
