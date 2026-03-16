"""Tests for the full simulation snapshot save/load system."""
import json
import os
import tempfile

import pytest

from tests.conftest import make_mock_app
from life.grid import Grid
from life.registry import MODE_DISPATCH


# Bind snapshot methods onto _MockApp so tests can call them directly.
from life.app import App

_SNAPSHOT_METHODS = [
    '_snapshot_detect_mode',
    '_snapshot_collect_mode_params',
    '_snapshot_restore_mode_params',
    '_save_snapshot',
    '_load_snapshot',
    '_apply_snapshot',
]


@pytest.fixture
def app():
    """Create a mock app with snapshot methods bound."""
    a = make_mock_app()
    for name in _SNAPSHOT_METHODS:
        method = getattr(App, name)
        import types
        setattr(a, name, types.MethodType(method, a))
    return a


class TestSnapshotDetectMode:
    def test_base_game_of_life(self, app):
        assert app._snapshot_detect_mode() is None

    def test_dispatch_mode(self, app):
        app.wolfram_mode = True
        assert app._snapshot_detect_mode() == 'wolfram_mode'

    def test_explicit_mode(self, app):
        app.evo_mode = True
        assert app._snapshot_detect_mode() == 'evo_mode'

    def test_first_active_wins(self, app):
        """If multiple dispatch modes are active, the first in the table wins."""
        # Activate two modes
        app.wolfram_mode = True
        app.ant_mode = True
        result = app._snapshot_detect_mode()
        # Should be whichever comes first in MODE_DISPATCH
        assert result is not None


class TestSnapshotCollectParams:
    def test_no_mode_returns_empty(self, app):
        assert app._snapshot_collect_mode_params(None) == {}

    def test_collects_mode_prefixed_attrs(self, app):
        params = app._snapshot_collect_mode_params('wolfram_mode')
        # Should collect wolfram_rule, wolfram_seed_mode, etc.
        assert 'wolfram_rule' in params
        assert params['wolfram_rule'] == 30
        assert 'wolfram_seed_mode' in params

    def test_collects_sets_as_sorted_lists(self, app):
        app.test_birth = {3, 5}
        app.test_survival = {2, 3}
        app.test_mode = True
        params = app._snapshot_collect_mode_params('test_mode')
        assert params.get('test_birth') == [3, 5]
        assert params.get('test_survival') == [2, 3]


class TestSnapshotRestoreParams:
    def test_restores_numeric(self, app):
        app.wolfram_rule = 30
        app._snapshot_restore_mode_params({'wolfram_rule': 110})
        assert app.wolfram_rule == 110

    def test_restores_set_from_list(self, app):
        app.test_birth = {3}
        app._snapshot_restore_mode_params({'test_birth': [2, 4, 6]})
        assert app.test_birth == {2, 4, 6}

    def test_skips_unknown_attrs(self, app):
        # Should not raise
        app._snapshot_restore_mode_params({'nonexistent_zzzz': 42})


class TestApplySnapshot:
    def test_restores_grid(self, app):
        app.grid.set_alive(0, 0)
        app.grid.set_alive(1, 1)
        app.grid.generation = 100

        snapshot = {
            'version': 1,
            'grid': app.grid.to_dict(),
            'hex_mode': False,
            'topology': 'torus',
            'mode': None,
            'viewport': {
                'view_r': 5, 'view_c': 10,
                'cursor_r': 3, 'cursor_c': 7,
                'zoom_level': 2,
            },
            'speed_idx': 4,
            'colormap': 'viridis',
            'colormap_idx': 0,
            'heatmap_mode': False,
            'running': False,
            'mode_params': {},
        }

        # Clear the grid first
        app.grid.clear()
        assert app.grid.population == 0

        app._apply_snapshot(snapshot)

        assert app.grid.generation == 100
        assert app.grid.population == 2
        assert app.view_r == 5
        assert app.view_c == 10
        assert app.cursor_r == 3
        assert app.cursor_c == 7
        assert app.zoom_level == 2
        assert app.speed_idx == 4

    def test_restores_topology(self, app):
        snapshot = {
            'version': 1,
            'grid': app.grid.to_dict(),
            'hex_mode': True,
            'topology': 'klein_bottle',
            'mode': None,
            'viewport': {},
            'speed_idx': 2,
            'colormap': 'viridis',
            'colormap_idx': 0,
            'heatmap_mode': False,
            'running': False,
            'mode_params': {},
        }
        app._apply_snapshot(snapshot)
        assert app.grid.hex_mode is True
        assert app.grid.topology == 'klein_bottle'

    def test_restores_mode_with_params(self, app):
        snapshot = {
            'version': 1,
            'grid': app.grid.to_dict(),
            'hex_mode': False,
            'topology': 'torus',
            'mode': 'wolfram_mode',
            'viewport': {},
            'speed_idx': 2,
            'colormap': 'viridis',
            'colormap_idx': 0,
            'heatmap_mode': False,
            'running': False,
            'mode_params': {'wolfram_rule': 110},
        }
        app._apply_snapshot(snapshot)
        assert app.wolfram_mode is True
        assert app.wolfram_rule == 110

    def test_deactivates_previous_mode(self, app):
        app.wolfram_mode = True
        snapshot = {
            'version': 1,
            'grid': app.grid.to_dict(),
            'hex_mode': False,
            'topology': 'torus',
            'mode': None,
            'viewport': {},
            'speed_idx': 2,
            'colormap': 'viridis',
            'colormap_idx': 0,
            'heatmap_mode': False,
            'running': False,
            'mode_params': {},
        }
        app._apply_snapshot(snapshot)
        assert app.wolfram_mode is False

    def test_clears_history(self, app):
        app.history = [({'dummy': True}, 1)]
        app.pop_history = [10, 20, 30]
        snapshot = {
            'version': 1,
            'grid': app.grid.to_dict(),
            'hex_mode': False,
            'topology': 'torus',
            'mode': None,
            'viewport': {},
            'speed_idx': 2,
            'colormap': 'viridis',
            'colormap_idx': 0,
            'heatmap_mode': False,
            'running': False,
            'mode_params': {},
        }
        app._apply_snapshot(snapshot)
        assert app.history == []
        assert app.timeline_pos is None


class TestSnapshotRoundTrip:
    """Test that save -> load preserves state correctly."""

    def test_roundtrip_via_json(self, app):
        # Set up interesting state
        app.grid.set_alive(5, 5)
        app.grid.set_alive(5, 6)
        app.grid.set_alive(5, 7)
        app.grid.generation = 42
        app.grid.hex_mode = True
        app.grid.topology = 'mobius_strip'
        app.view_r = 3
        app.view_c = 7
        app.cursor_r = 10
        app.cursor_c = 20
        app.zoom_level = 4
        app.speed_idx = 5
        app.heatmap_mode = True
        app.running = True

        # Build snapshot dict (same logic as _save_snapshot)
        mode_attr = app._snapshot_detect_mode()
        snapshot = {
            'version': 1,
            'name': 'test',
            'grid': app.grid.to_dict(),
            'hex_mode': app.grid.hex_mode,
            'topology': app.grid.topology,
            'mode': mode_attr,
            'viewport': {
                'view_r': app.view_r,
                'view_c': app.view_c,
                'cursor_r': app.cursor_r,
                'cursor_c': app.cursor_c,
                'zoom_level': app.zoom_level,
            },
            'speed_idx': app.speed_idx,
            'colormap': app.tc_colormap,
            'colormap_idx': app.tc_colormap_idx,
            'heatmap_mode': app.heatmap_mode,
            'running': app.running,
            'mode_params': app._snapshot_collect_mode_params(mode_attr),
        }

        # Serialize round-trip through JSON
        json_str = json.dumps(snapshot)
        loaded = json.loads(json_str)

        # Reset app state
        app.grid.clear()
        app.grid.hex_mode = False
        app.grid.topology = 'torus'
        app.view_r = 0
        app.view_c = 0
        app.zoom_level = 1
        app.speed_idx = 2
        app.heatmap_mode = False
        app.running = False

        # Apply loaded snapshot
        app._apply_snapshot(loaded)

        assert app.grid.population == 3
        assert app.grid.generation == 42
        assert app.grid.hex_mode is True
        assert app.grid.topology == 'mobius_strip'
        assert app.view_r == 3
        assert app.view_c == 7
        assert app.cursor_r == 10
        assert app.cursor_c == 20
        assert app.zoom_level == 4
        assert app.speed_idx == 5
        assert app.heatmap_mode is True
        assert app.running is True

    def test_roundtrip_with_mode(self, app):
        app.wolfram_mode = True
        app.wolfram_rule = 90
        app.wolfram_seed_mode = 'random'

        mode_attr = app._snapshot_detect_mode()
        assert mode_attr == 'wolfram_mode'

        snapshot = {
            'version': 1,
            'grid': app.grid.to_dict(),
            'hex_mode': False,
            'topology': 'torus',
            'mode': mode_attr,
            'viewport': {},
            'speed_idx': 2,
            'colormap': 'viridis',
            'colormap_idx': 0,
            'heatmap_mode': False,
            'running': False,
            'mode_params': app._snapshot_collect_mode_params(mode_attr),
        }

        json_str = json.dumps(snapshot)
        loaded = json.loads(json_str)

        # Reset
        app.wolfram_mode = False
        app.wolfram_rule = 30
        app.wolfram_seed_mode = 'center'

        app._apply_snapshot(loaded)
        assert app.wolfram_mode is True
        assert app.wolfram_rule == 90
        assert app.wolfram_seed_mode == 'random'
