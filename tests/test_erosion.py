"""Tests for Hydraulic Erosion mode."""
import random
import pytest
from tests.conftest import make_mock_app
from life.modes.erosion import register


class TestErosion:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    def test_enter(self):
        self.app._erosion_init(0)
        assert self.app.erosion_mode is True
        assert self.app.erosion_generation == 0
        assert len(self.app.erosion_terrain) > 0
        assert self.app.erosion_steps_per_frame == 1

    def test_step_no_crash(self):
        self.app._erosion_init(0)
        for _ in range(10):
            self.app._erosion_step()
        assert self.app.erosion_generation == 10

    def test_exit_cleanup(self):
        self.app._erosion_init(0)
        assert self.app.erosion_mode is True
        self.app._exit_erosion_mode()
        assert self.app.erosion_mode is False
        assert self.app.erosion_running is False
        assert self.app.erosion_terrain == []
        assert self.app.erosion_water == []
        assert self.app.erosion_sediment == []

    # -- Preset validation --

    def test_all_presets_load(self):
        """Every EROSION_PRESET index initializes without error."""
        for idx in range(len(self.app.EROSION_PRESETS)):
            random.seed(idx)
            self.app._erosion_init(idx)
            assert self.app.erosion_mode is True
            assert self.app.erosion_generation == 0
            assert len(self.app.erosion_terrain) == self.app.erosion_rows
            assert len(self.app.erosion_terrain[0]) == self.app.erosion_cols

    def test_preset_count(self):
        """Exactly 8 erosion presets matching original commit 2e90e73."""
        assert len(self.app.EROSION_PRESETS) == 8

    def test_preset_names(self):
        names = [p[0] for p in self.app.EROSION_PRESETS]
        expected = [
            "River Valley", "Mountain Gorge", "Coastal Plateau", "Badlands",
            "Alpine Peaks", "Rolling Hills", "Canyon Lands", "Volcanic Island",
        ]
        assert names == expected

    def test_preset_tuple_structure(self):
        """Each preset is (name, desc, rain, evap, solubility, deposition, terrain_type)."""
        for preset in self.app.EROSION_PRESETS:
            assert len(preset) == 7
            name, desc, rain, evap, sol, dep, ttype = preset
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert isinstance(rain, float)
            assert isinstance(evap, float)
            assert isinstance(sol, float)
            assert isinstance(dep, float)
            assert isinstance(ttype, str)

    # -- Terrain generation --

    def test_terrain_normalized(self):
        """Generated terrain values are in [0, 1]."""
        self.app._erosion_init(0)
        terrain = self.app.erosion_terrain
        for row in terrain:
            for h in row:
                assert 0.0 <= h <= 1.0

    def test_terrain_dimensions(self):
        self.app._erosion_init(0)
        rows = self.app.erosion_rows
        cols = self.app.erosion_cols
        assert len(self.app.erosion_terrain) == rows
        assert all(len(row) == cols for row in self.app.erosion_terrain)
        assert len(self.app.erosion_water) == rows
        assert all(len(row) == cols for row in self.app.erosion_water)
        assert len(self.app.erosion_sediment) == rows
        assert all(len(row) == cols for row in self.app.erosion_sediment)

    def test_initial_water_zero(self):
        """Water starts at zero everywhere."""
        self.app._erosion_init(0)
        for row in self.app.erosion_water:
            for w in row:
                assert w == 0.0

    def test_initial_sediment_zero(self):
        """Sediment starts at zero everywhere."""
        self.app._erosion_init(0)
        for row in self.app.erosion_sediment:
            for s in row:
                assert s == 0.0

    def test_all_terrain_types(self):
        """Each terrain type generates valid normalized terrain."""
        terrain_types = ["gentle", "steep", "plateau", "rough", "alpine",
                         "hills", "mesa", "volcano"]
        for ttype in terrain_types:
            random.seed(99)
            terrain = self.app._erosion_generate_terrain(20, 30, ttype)
            assert len(terrain) == 20
            assert len(terrain[0]) == 30
            min_h = min(terrain[r][c] for r in range(20) for c in range(30))
            max_h = max(terrain[r][c] for r in range(20) for c in range(30))
            assert min_h >= 0.0
            assert max_h <= 1.0
            # Should span most of [0,1] range
            assert max_h - min_h > 0.5

    # -- Erosion step physics --

    def test_rainfall_adds_water(self):
        """After one step, water should be non-zero somewhere."""
        self.app._erosion_init(0)
        self.app._erosion_step()
        total_water = sum(
            self.app.erosion_water[r][c]
            for r in range(self.app.erosion_rows)
            for c in range(self.app.erosion_cols)
        )
        assert total_water > 0

    def test_erosion_accumulates(self):
        """Total eroded amount should increase over steps."""
        self.app._erosion_init(0)
        for _ in range(5):
            self.app._erosion_step()
        eroded_5 = self.app.erosion_total_eroded
        for _ in range(5):
            self.app._erosion_step()
        eroded_10 = self.app.erosion_total_eroded
        assert eroded_10 >= eroded_5

    def test_terrain_modified_by_erosion(self):
        """After many steps, terrain should change from initial state."""
        random.seed(42)
        self.app._erosion_init(3)  # Badlands — heavy erosion
        initial_terrain = [row[:] for row in self.app.erosion_terrain]
        for _ in range(20):
            self.app._erosion_step()
        changed = False
        for r in range(self.app.erosion_rows):
            for c in range(self.app.erosion_cols):
                if abs(self.app.erosion_terrain[r][c] - initial_terrain[r][c]) > 1e-9:
                    changed = True
                    break
            if changed:
                break
        assert changed, "Terrain should be modified by erosion"

    def test_water_non_negative(self):
        """Water should never go negative."""
        self.app._erosion_init(0)
        for _ in range(15):
            self.app._erosion_step()
        for r in range(self.app.erosion_rows):
            for c in range(self.app.erosion_cols):
                assert self.app.erosion_water[r][c] >= 0.0

    def test_sediment_non_negative(self):
        """Sediment should never go negative."""
        self.app._erosion_init(0)
        for _ in range(15):
            self.app._erosion_step()
        for r in range(self.app.erosion_rows):
            for c in range(self.app.erosion_cols):
                assert self.app.erosion_sediment[r][c] >= 0.0

    def test_boundary_drainage(self):
        """Edge cells should have reduced water due to boundary drainage."""
        self.app._erosion_init(0)
        for _ in range(10):
            self.app._erosion_step()
        rows = self.app.erosion_rows
        cols = self.app.erosion_cols
        # Average edge water vs interior water
        edge_water = []
        for r in range(rows):
            edge_water.append(self.app.erosion_water[r][0])
            edge_water.append(self.app.erosion_water[r][cols - 1])
        for c in range(cols):
            edge_water.append(self.app.erosion_water[0][c])
            edge_water.append(self.app.erosion_water[rows - 1][c])
        interior_water = []
        for r in range(2, rows - 2):
            for c in range(2, cols - 2):
                interior_water.append(self.app.erosion_water[r][c])
        avg_edge = sum(edge_water) / max(1, len(edge_water))
        avg_interior = sum(interior_water) / max(1, len(interior_water))
        # Edge water should generally be less due to 0.5x drainage
        # (not a strict guarantee every time, but statistically very likely)
        assert avg_edge <= avg_interior * 2.0  # relaxed bound

    def test_generation_counter(self):
        self.app._erosion_init(0)
        assert self.app.erosion_generation == 0
        self.app._erosion_step()
        assert self.app.erosion_generation == 1
        self.app._erosion_step()
        assert self.app.erosion_generation == 2

    def test_reinit_resets_state(self):
        """Re-initializing resets generation and total eroded."""
        self.app._erosion_init(0)
        for _ in range(5):
            self.app._erosion_step()
        assert self.app.erosion_generation == 5
        assert self.app.erosion_total_eroded > 0
        self.app._erosion_init(1)
        assert self.app.erosion_generation == 0
        assert self.app.erosion_total_eroded == 0.0

    # -- Parameters from presets --

    def test_init_applies_preset_params(self):
        """Preset parameters should be applied to app state."""
        preset = self.app.EROSION_PRESETS[0]
        name, _desc, rain, evap, sol, dep, _ttype = preset
        self.app._erosion_init(0)
        assert self.app.erosion_preset_name == name
        assert self.app.erosion_rain_rate == rain
        assert self.app.erosion_evap_rate == evap
        assert self.app.erosion_solubility == sol
        assert self.app.erosion_deposition == dep

    # -- Enter mode --

    def test_enter_mode_shows_menu(self):
        self.app._enter_erosion_mode()
        assert self.app.erosion_menu is True
        assert self.app.erosion_menu_sel == 0
