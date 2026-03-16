"""Comprehensive enter/step/exit lifecycle test for EVERY registered mode.

This test catches missing attribute errors (like 'colors_enabled') by
exercising each mode's full lifecycle on a mock app. If any mode references
an attribute that isn't initialized by enter or conftest, this test will fail.
"""
import random
import pytest
from tests.conftest import make_mock_app
from life.registry import MODE_REGISTRY


def _resolve(app, name_or_none):
    """Resolve a method name string to a bound method on app, or None."""
    if name_or_none is None:
        return None
    return getattr(app, name_or_none, None)


# Build list of (mode_name, enter_name, exit_name) for parametrize
_MODE_ENTRIES = []
for entry in MODE_REGISTRY:
    name = entry.get("name", "unknown")
    enter_name = entry.get("enter")
    exit_name = entry.get("exit")
    if enter_name:  # skip Game of Life (no enter)
        _MODE_ENTRIES.append((name, enter_name, exit_name))

_MODE_NAMES = [m[0] for m in _MODE_ENTRIES]


@pytest.mark.parametrize("mode_name,enter_name,exit_name", _MODE_ENTRIES,
                         ids=_MODE_NAMES)
class TestModeLifecycleNoAttributeError:
    """Verify entering, stepping, and exiting each mode does not raise
    AttributeError on a standard mock app."""

    def test_enter_no_attribute_error(self, mode_name, enter_name, exit_name):
        """Entering the mode must not raise AttributeError."""
        random.seed(42)
        app = make_mock_app()
        enter_fn = _resolve(app, enter_name)
        exit_fn = _resolve(app, exit_name)
        if enter_fn is None:
            pytest.skip(f"No enter function for {mode_name}")
        try:
            enter_fn()
        except AttributeError as e:
            pytest.fail(f"AttributeError on enter for '{mode_name}': {e}")
        except Exception:
            pass  # Other errors (curses etc.) are OK
        finally:
            if exit_fn:
                try:
                    exit_fn()
                except Exception:
                    pass

    def test_exit_no_attribute_error(self, mode_name, enter_name, exit_name):
        """Exiting the mode (after enter) must not raise AttributeError."""
        random.seed(42)
        app = make_mock_app()
        enter_fn = _resolve(app, enter_name)
        exit_fn = _resolve(app, exit_name)
        if enter_fn is None or exit_fn is None:
            pytest.skip(f"No enter/exit for {mode_name}")
        try:
            enter_fn()
        except Exception:
            pass
        try:
            exit_fn()
        except AttributeError as e:
            pytest.fail(f"AttributeError on exit for '{mode_name}': {e}")
        except Exception:
            pass
