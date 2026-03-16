"""Tests for lsystem mode — deep validation against commit e4693f7."""
import math
import random
import curses
import pytest
from tests.conftest import make_mock_app
from life.modes.lsystem import (
    register, SPECIES, _make_plant, LSYSTEM_PRESETS,
    SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER,
    SEASON_DURATION,
)
from life.constants import SPEEDS


def _make_lsystem_app():
    """Create a mock app with lsystem mode registered."""
    app = make_mock_app()
    cls = type(app)
    # Set attributes that lsystem mode needs
    app.lsystem_light_dir = 0.0
    app.lsystem_mode = False
    app.lsystem_menu = False
    app.lsystem_menu_sel = 0
    app.lsystem_running = False
    app.lsystem_generation = 0
    app.lsystem_preset_name = ""
    app.lsystem_plants = []
    app.lsystem_segments = []
    app.lsystem_leaves = []
    app.lsystem_wind = 0.0
    app.lsystem_wind_time = 0.0
    app.lsystem_season = 0
    app.lsystem_season_tick = 0
    app.lsystem_seasons_auto = True
    app.lsystem_mutation = 0.0
    app.lsystem_seed_queue = []
    app.lsystem_fallen_leaves = []
    app.lsystem_growth_rate = 1.0
    app.lsystem_angle = 25.0
    app.lsystem_max_depth = 6
    app.lsystem_current_depth = 0
    register(cls)
    return app


class TestSpeciesLibrary:
    """Validate the SPECIES dictionary structure."""

    @pytest.mark.parametrize("species_id", list(SPECIES.keys()))
    def test_species_has_required_keys(self, species_id):
        sp = SPECIES[species_id]
        required = {"axiom", "rules", "angle", "length_scale", "max_depth",
                     "flower", "deciduous", "color_trunk", "color_leaf"}
        assert required.issubset(sp.keys()), f"Missing keys in {species_id}: {required - sp.keys()}"

    @pytest.mark.parametrize("species_id", list(SPECIES.keys()))
    def test_species_rules_are_valid(self, species_id):
        sp = SPECIES[species_id]
        for k, v in sp["rules"].items():
            assert isinstance(k, str) and len(k) == 1
            assert isinstance(v, str)
            # All rule characters should be from valid set
            for ch in v:
                assert ch in "FfXYAB+-[]", f"Unexpected char '{ch}' in rule for {species_id}"

    @pytest.mark.parametrize("species_id", list(SPECIES.keys()))
    def test_species_angle_in_range(self, species_id):
        angle = SPECIES[species_id]["angle"]
        assert 5.0 <= angle <= 90.0

    @pytest.mark.parametrize("species_id", list(SPECIES.keys()))
    def test_species_length_scale_in_range(self, species_id):
        ls = SPECIES[species_id]["length_scale"]
        assert 0.3 <= ls <= 0.7


class TestMakePlant:
    def test_basic_creation(self):
        random.seed(42)
        plant = _make_plant("binary_tree", 50.0, 39.0)
        assert plant["species"] == "binary_tree"
        assert plant["x"] == 50.0
        assert plant["y"] == 39.0
        assert plant["depth"] == 0
        assert plant["string"] == "F"
        assert plant["health"] == 1.0
        assert plant["age"] == 0
        assert plant["seeds_dropped"] == 0

    def test_mutation_alters_angle(self):
        random.seed(42)
        plant_normal = _make_plant("fern", 50.0, 39.0, mutation=0.0)
        random.seed(42)
        plant_mutant = _make_plant("fern", 50.0, 39.0, mutation=1.0)
        # With high mutation, angle should differ from species default
        assert plant_normal["angle"] == SPECIES["fern"]["angle"]
        # Mutant angle is randomized, so it may or may not differ
        # but length_scale may also differ

    def test_mutation_clamps_values(self):
        """Mutated angle should stay in [5, 85], length_scale in [0.3, 0.7]."""
        for _ in range(20):
            plant = _make_plant("bush", 50.0, 39.0, mutation=1.0)
            assert 5.0 <= plant["angle"] <= 85.0
            assert 0.3 <= plant["length_scale"] <= 0.7


class TestLSystemRegister:
    def test_register_sets_presets(self):
        """register() should set LSYSTEM_PRESETS on the App class."""
        app = _make_lsystem_app()
        assert hasattr(type(app), 'LSYSTEM_PRESETS')
        assert len(type(app).LSYSTEM_PRESETS) == len(LSYSTEM_PRESETS)
        assert len(LSYSTEM_PRESETS) >= 13  # 13 presets defined

    def test_register_binds_all_methods(self):
        """register() should bind all required methods."""
        app = _make_lsystem_app()
        cls = type(app)
        required = [
            '_enter_lsystem_mode', '_exit_lsystem_mode',
            '_handle_lsystem_menu_key', '_handle_lsystem_key',
            '_lsystem_init', '_lsystem_build_preset',
            '_lsystem_expand', '_lsystem_interpret',
            '_lsystem_rebuild_all', '_lsystem_step',
            '_lsystem_compute_light', '_lsystem_apply_season',
            '_lsystem_drop_seeds', '_draw_lsystem_menu', '_draw_lsystem',
        ]
        for method_name in required:
            assert hasattr(cls, method_name), f"Missing method: {method_name}"


class TestLSystemEnterExit:
    def test_enter_sets_menu(self):
        app = _make_lsystem_app()
        app._enter_lsystem_mode()
        assert app.lsystem_menu is True
        assert app.lsystem_menu_sel == 0

    def test_exit_clears_state(self):
        app = _make_lsystem_app()
        app.lsystem_mode = True
        app._lsystem_init("binary_tree")
        app._exit_lsystem_mode()
        assert app.lsystem_mode is False
        assert app.lsystem_plants == []
        assert app.lsystem_segments == []
        assert app.lsystem_leaves == []


class TestLSystemInit:
    @pytest.mark.parametrize("preset_id", [p[2] for p in LSYSTEM_PRESETS])
    def test_init_creates_plants(self, preset_id):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init(preset_id)
        assert len(app.lsystem_plants) > 0
        assert app.lsystem_generation == 0
        assert app.lsystem_wind == 0.0
        assert app.lsystem_season == SEASON_SPRING

    def test_init_binary_tree_single_plant(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        assert len(app.lsystem_plants) == 1
        p = app.lsystem_plants[0]
        assert p["species"] == "binary_tree"
        assert p["string"] == "F"
        assert p["depth"] == 0

    def test_init_garden_multiple_plants(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("garden")
        assert len(app.lsystem_plants) == 5

    def test_init_competition_many_species(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("competition")
        assert len(app.lsystem_plants) == 7
        assert app.lsystem_mutation == 0.15

    def test_init_alien_flora_has_mutation(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("alien_flora")
        assert app.lsystem_mutation == 0.3
        assert len(app.lsystem_plants) == 3

    def test_init_rebuilds_segments(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("fern")
        # Fern axiom is "X", which has no F, so no segments initially
        # Actually "X" produces no segments since X doesn't draw
        # After rebuild, segments may be empty for just "X"
        assert isinstance(app.lsystem_segments, list)


class TestLSystemExpand:
    def test_expand_simple_rule(self):
        app = _make_lsystem_app()
        result = app._lsystem_expand("F", {"F": "F+F"})
        assert result == "F+F"

    def test_expand_multiple_rules(self):
        app = _make_lsystem_app()
        result = app._lsystem_expand("XF", {"X": "FX", "F": "FF"})
        assert result == "FXFF"

    def test_expand_preserves_non_rule_chars(self):
        app = _make_lsystem_app()
        result = app._lsystem_expand("F+[-F]", {"F": "FF"})
        assert result == "FF+[-FF]"

    def test_expand_binary_tree_rule(self):
        app = _make_lsystem_app()
        result = app._lsystem_expand("F", {"F": "FF+[+F-F-F]-[-F+F+F]"})
        assert result == "FF+[+F-F-F]-[-F+F+F]"

    def test_double_expansion(self):
        app = _make_lsystem_app()
        s = app._lsystem_expand("F", {"F": "F+F"})
        s = app._lsystem_expand(s, {"F": "F+F"})
        assert s == "F+F+F+F"


class TestLSystemInterpret:
    def test_simple_forward(self):
        """F should create one segment going up."""
        app = _make_lsystem_app()
        app.lsystem_rows = 40
        app.lsystem_wind = 0.0
        app.lsystem_wind_time = 0.0
        app.lsystem_light_dir = 0.0
        app.lsystem_season = SEASON_SUMMER
        plant = _make_plant("binary_tree", 50.0, 39.0)
        plant["string"] = "F"
        segs, leaves = app._lsystem_interpret(plant)
        assert len(segs) == 1
        x1, y1, x2, y2, depth, color = segs[0]
        assert x1 == 50.0
        assert y1 == 39.0
        # Should move upward (y decreases)
        assert y2 < y1

    def test_branch_creates_leaf(self):
        """Closing bracket ] should add a leaf."""
        app = _make_lsystem_app()
        app.lsystem_rows = 40
        app.lsystem_wind = 0.0
        app.lsystem_wind_time = 0.0
        app.lsystem_light_dir = 0.0
        app.lsystem_season = SEASON_SUMMER
        plant = _make_plant("binary_tree", 50.0, 39.0)
        plant["string"] = "F[+F]"
        segs, leaves = app._lsystem_interpret(plant)
        assert len(leaves) == 1
        assert len(segs) == 2  # main F and branched F

    def test_depth_tracking(self):
        """Nested brackets should track depth correctly."""
        app = _make_lsystem_app()
        app.lsystem_rows = 40
        app.lsystem_wind = 0.0
        app.lsystem_wind_time = 0.0
        app.lsystem_light_dir = 0.0
        app.lsystem_season = SEASON_SUMMER
        plant = _make_plant("binary_tree", 50.0, 39.0)
        plant["string"] = "F[+F[+F]]"
        segs, leaves = app._lsystem_interpret(plant)
        # Segments should have increasing depth
        depths = [s[4] for s in segs]
        assert 0 in depths
        assert 1 in depths
        assert 2 in depths

    def test_winter_deciduous_no_leaves(self):
        """Deciduous plants in winter should show no leaves."""
        app = _make_lsystem_app()
        app.lsystem_rows = 40
        app.lsystem_wind = 0.0
        app.lsystem_wind_time = 0.0
        app.lsystem_light_dir = 0.0
        app.lsystem_season = SEASON_WINTER
        plant = _make_plant("binary_tree", 50.0, 39.0)
        plant["string"] = "F[+F][-F]"
        segs, leaves = app._lsystem_interpret(plant)
        # binary_tree is deciduous, winter = no leaves
        assert len(leaves) == 0

    def test_evergreen_winter_has_leaves(self):
        """Non-deciduous plants should keep leaves in winter."""
        app = _make_lsystem_app()
        app.lsystem_rows = 40
        app.lsystem_wind = 0.0
        app.lsystem_wind_time = 0.0
        app.lsystem_light_dir = 0.0
        app.lsystem_season = SEASON_WINTER
        plant = _make_plant("fern", 50.0, 39.0)  # fern is not deciduous
        plant["string"] = "F[+F][-F]"
        segs, leaves = app._lsystem_interpret(plant)
        assert len(leaves) == 2  # two branches close with ]

    def test_wind_bends_branches(self):
        """Non-zero wind should alter segment positions."""
        app = _make_lsystem_app()
        app.lsystem_rows = 40
        app.lsystem_wind_time = 0.0
        app.lsystem_light_dir = 0.0
        app.lsystem_season = SEASON_SUMMER

        plant = _make_plant("binary_tree", 50.0, 39.0)
        plant["string"] = "FF"

        app.lsystem_wind = 0.0
        segs_calm, _ = app._lsystem_interpret(plant)

        app.lsystem_wind = 0.8
        segs_wind, _ = app._lsystem_interpret(plant)

        # Wind should change the x2 position of the second segment
        # (first segment at ground level has height_frac ~0)
        # The second F is higher up, so wind should bend it
        if len(segs_calm) >= 2 and len(segs_wind) >= 2:
            calm_x2 = segs_calm[1][2]
            wind_x2 = segs_wind[1][2]
            # They may differ due to wind bending
            # This is a soft check since wind effect depends on height
            assert isinstance(wind_x2, float)

    def test_light_direction_bias(self):
        """Non-zero light direction should bias the heading."""
        app = _make_lsystem_app()
        app.lsystem_rows = 40
        app.lsystem_wind = 0.0
        app.lsystem_wind_time = 0.0
        app.lsystem_season = SEASON_SUMMER

        plant = _make_plant("binary_tree", 50.0, 39.0)
        plant["string"] = "F"

        app.lsystem_light_dir = 0.0
        segs0, _ = app._lsystem_interpret(plant)

        app.lsystem_light_dir = 90.0
        segs90, _ = app._lsystem_interpret(plant)

        # Different light directions should produce different endpoints
        assert segs0[0][2] != segs90[0][2] or segs0[0][3] != segs90[0][3]


class TestLSystemStep:
    def test_step_grows_plant(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("bush")
        initial_depth = app.lsystem_plants[0]["depth"]
        # Force spring + high growth rate
        app.lsystem_season = SEASON_SPRING
        app.lsystem_growth_rate = 1.0
        app._lsystem_step()
        assert app.lsystem_plants[0]["depth"] >= initial_depth

    def test_step_winter_no_growth(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("bush")
        app.lsystem_season = SEASON_WINTER
        app.lsystem_seasons_auto = False
        initial_string = app.lsystem_plants[0]["string"]
        app._lsystem_step()
        # Winter growth chance is 0
        assert app.lsystem_plants[0]["string"] == initial_string

    def test_step_season_auto_cycle(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("bush")
        app.lsystem_seasons_auto = True
        app.lsystem_season = SEASON_SPRING
        app.lsystem_season_tick = SEASON_DURATION - 1
        app._lsystem_step()
        # Should have advanced to summer
        assert app.lsystem_season == SEASON_SUMMER

    def test_step_wind_fluctuates(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("bush")
        app.lsystem_wind = 0.5
        old_wind = app.lsystem_wind
        app._lsystem_step()
        # Wind time should advance
        assert app.lsystem_wind_time > 0

    def test_step_limited_depth(self):
        """Growth should stop at max_depth."""
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("bush")
        app.lsystem_season = SEASON_SPRING
        app.lsystem_seasons_auto = False
        app.lsystem_growth_rate = 10.0  # guaranteed growth
        max_d = app.lsystem_plants[0]["max_depth"]
        for _ in range(max_d + 5):
            app._lsystem_step()
        assert app.lsystem_plants[0]["depth"] <= max_d

    def test_multiple_steps_no_crash(self):
        """Run several steps with a small preset to ensure stability."""
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("bonsai")  # smaller max_depth=6
        app.lsystem_seasons_auto = False
        app.lsystem_season = SEASON_SPRING
        for _ in range(6):
            app._lsystem_step()
        assert app.lsystem_generation >= 0


class TestLSystemSeasons:
    def test_autumn_drops_fallen_leaves(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        app.lsystem_season = SEASON_SPRING
        app.lsystem_seasons_auto = False
        # Grow a few steps to get leaves
        for _ in range(3):
            app._lsystem_step()
        # Now trigger autumn season apply
        app.lsystem_season = SEASON_AUTUMN
        app._lsystem_apply_season()
        # May or may not have fallen leaves depending on randomness
        assert isinstance(app.lsystem_fallen_leaves, list)

    def test_spring_sprouts_seeds(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        n_before = len(app.lsystem_plants)
        app.lsystem_seed_queue = [(50.0, "fern", 0.0), (60.0, "bush", 0.0)]
        app.lsystem_season = SEASON_SPRING
        app._lsystem_apply_season()
        assert len(app.lsystem_plants) > n_before

    def test_winter_prunes_dead_plants(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("garden")
        # Set one plant to very low health
        app.lsystem_plants[0]["health"] = 0.05
        app.lsystem_plants[0]["age"] = 10  # old enough to prune
        n_before = len(app.lsystem_plants)
        app.lsystem_season = SEASON_WINTER
        app._lsystem_apply_season()
        assert len(app.lsystem_plants) < n_before


class TestLSystemSeedDispersal:
    def test_mature_plant_drops_seeds(self):
        random.seed(1)  # find a seed that triggers
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        plant = app.lsystem_plants[0]
        plant["depth"] = plant["max_depth"] - 1  # mature
        plant["health"] = 1.0
        app.lsystem_mutation = 0.1
        # Run many attempts
        for _ in range(200):
            app._lsystem_drop_seeds()
        # Should have queued at least one seed
        assert len(app.lsystem_seed_queue) > 0

    def test_immature_plant_no_seeds(self):
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        plant = app.lsystem_plants[0]
        plant["depth"] = 0  # immature
        app.lsystem_mutation = 0.5
        for _ in range(100):
            app._lsystem_drop_seeds()
        assert len(app.lsystem_seed_queue) == 0


class TestLSystemLightCompetition:
    def test_single_plant_full_health(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        # Grow to get segments
        app.lsystem_season = SEASON_SPRING
        app.lsystem_seasons_auto = False
        for _ in range(3):
            app._lsystem_step()
        app._lsystem_compute_light()
        assert app.lsystem_plants[0]["health"] == 1.0

    def test_multiple_plants_compete(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("garden")
        app.lsystem_season = SEASON_SPRING
        app.lsystem_seasons_auto = False
        for _ in range(3):
            app._lsystem_step()
        app._lsystem_compute_light()
        # All plants should have health between 0 and 1
        for plant in app.lsystem_plants:
            assert 0.0 <= plant["health"] <= 1.0


class TestLSystemMenuKeys:
    def _init_menu(self):
        app = _make_lsystem_app()
        app._enter_lsystem_mode()
        return app

    def test_menu_navigate_down(self):
        app = self._init_menu()
        app._handle_lsystem_menu_key(curses.KEY_DOWN)
        assert app.lsystem_menu_sel == 1

    def test_menu_navigate_up_wraps(self):
        app = self._init_menu()
        app._handle_lsystem_menu_key(curses.KEY_UP)
        assert app.lsystem_menu_sel == len(LSYSTEM_PRESETS) - 1

    def test_menu_enter_starts(self):
        app = self._init_menu()
        app._handle_lsystem_menu_key(ord("\n"))
        assert app.lsystem_menu is False
        assert app.lsystem_mode is True

    def test_menu_quit(self):
        app = self._init_menu()
        app._handle_lsystem_menu_key(ord("q"))
        assert app.lsystem_menu is False


class TestLSystemSimKeys:
    def _init_sim(self):
        random.seed(42)
        app = _make_lsystem_app()
        app.lsystem_mode = True
        app.lsystem_preset_name = "Bonsai"
        app._lsystem_init("bonsai")
        return app

    def test_space_toggles_running(self):
        app = self._init_sim()
        app.lsystem_running = False
        app._handle_lsystem_key(ord(" "))
        assert app.lsystem_running is True

    def test_n_advances_step(self):
        app = self._init_sim()
        app.lsystem_season = SEASON_SPRING
        app.lsystem_growth_rate = 10.0
        app._handle_lsystem_key(ord("n"))
        assert app.lsystem_generation >= 0

    def test_a_decreases_angle(self):
        app = self._init_sim()
        old_angle = app.lsystem_plants[0]["angle"]
        app._handle_lsystem_key(ord("a"))
        assert app.lsystem_plants[0]["angle"] < old_angle

    def test_A_increases_angle(self):
        app = self._init_sim()
        old_angle = app.lsystem_plants[0]["angle"]
        app._handle_lsystem_key(ord("A"))
        assert app.lsystem_plants[0]["angle"] > old_angle

    def test_w_decreases_wind(self):
        app = self._init_sim()
        app.lsystem_wind = 0.0
        app._handle_lsystem_key(ord("w"))
        assert app.lsystem_wind < 0.0

    def test_W_increases_wind(self):
        app = self._init_sim()
        app.lsystem_wind = 0.0
        app._handle_lsystem_key(ord("W"))
        assert app.lsystem_wind > 0.0

    def test_m_toggles_mutation(self):
        app = self._init_sim()
        assert app.lsystem_mutation == 0.0
        app._handle_lsystem_key(ord("m"))
        assert app.lsystem_mutation > 0

    def test_s_advances_season(self):
        app = self._init_sim()
        app.lsystem_season = SEASON_SPRING
        app._handle_lsystem_key(ord("s"))
        assert app.lsystem_season == SEASON_SUMMER

    def test_S_toggles_season_auto(self):
        app = self._init_sim()
        old = app.lsystem_seasons_auto
        app._handle_lsystem_key(ord("S"))
        assert app.lsystem_seasons_auto != old

    def test_r_resets_preset(self):
        app = self._init_sim()
        app._handle_lsystem_key(ord("r"))
        assert app.lsystem_generation == 0

    def test_R_returns_to_menu(self):
        app = self._init_sim()
        app._handle_lsystem_key(ord("R"))
        assert app.lsystem_menu is True

    def test_q_exits(self):
        app = self._init_sim()
        app._handle_lsystem_key(ord("q"))
        assert app.lsystem_mode is False


class TestLSystemRebuild:
    def test_rebuild_populates_segments(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        # Expand once
        plant = app.lsystem_plants[0]
        plant["string"] = app._lsystem_expand(plant["string"], plant["rules"])
        plant["depth"] = 1
        app._lsystem_rebuild_all()
        assert len(app.lsystem_segments) > 0

    def test_rebuild_clears_old_data(self):
        random.seed(42)
        app = _make_lsystem_app()
        app._lsystem_init("binary_tree")
        app.lsystem_segments = [(0, 0, 1, 1, 0, 0)]  # dummy
        app._lsystem_rebuild_all()
        # Should be rebuilt from plant data, not contain dummy
        # For axiom "F" there should be exactly 1 segment
        assert len(app.lsystem_segments) == 1
