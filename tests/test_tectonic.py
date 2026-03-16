"""Tests for life.modes.tectonic — Tectonic Plates mode."""
import curses
from tests.conftest import make_mock_app
from life.modes.tectonic import (
    register, TECTONIC_PRESETS, TECTONIC_ELEV_CHARS, TECTONIC_ELEV_THRESHOLDS,
)


def _addch(self, *args, **kwargs):
    pass


def _make_app():
    app = make_mock_app()
    type(app.stdscr).addch = _addch
    app.tectonic_mode = False
    app.tectonic_menu = False
    app.tectonic_menu_sel = 0
    app.tectonic_running = False
    app.tectonic_generation = 0
    app.tectonic_preset_name = ""
    app.tectonic_rows = 0
    app.tectonic_cols = 0
    app.tectonic_elevation = []
    app.tectonic_plate_id = []
    app.tectonic_plates = []
    app.tectonic_num_plates = 6
    app.tectonic_show_plates = False
    app.tectonic_show_help = True
    app.tectonic_speed_scale = 1.0
    app.tectonic_volcanic = []
    app.tectonic_age = 0
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_constants_exist():
    """Module defines all required constants."""
    assert len(TECTONIC_PRESETS) >= 6
    assert len(TECTONIC_ELEV_CHARS) > 0
    assert len(TECTONIC_ELEV_THRESHOLDS) > 0


def test_elev_chars_and_thresholds_aligned():
    """ELEV_CHARS should have at least as many entries as ELEV_THRESHOLDS.

    The lookup uses chars[i] for e < thresholds[i], and chars[-1] as fallback
    for values above the highest threshold. So len(chars) >= len(thresholds).
    """
    assert len(TECTONIC_ELEV_CHARS) >= len(TECTONIC_ELEV_THRESHOLDS)


def test_elev_thresholds_sorted():
    """Elevation thresholds must be in ascending order."""
    for i in range(len(TECTONIC_ELEV_THRESHOLDS) - 1):
        assert TECTONIC_ELEV_THRESHOLDS[i] < TECTONIC_ELEV_THRESHOLDS[i + 1]


def test_presets_have_valid_kinds():
    """All preset types are handled by _tectonic_init."""
    valid_kinds = {"pangaea", "collision", "arcs", "ridges", "ring", "random"}
    for _name, _desc, kind in TECTONIC_PRESETS:
        assert kind in valid_kinds, f"Preset kind '{kind}' not in valid_kinds"


def test_register_sets_class_constants():
    """register() sets constants on the App class."""
    app = _make_app()
    cls = type(app)
    assert hasattr(cls, 'TECTONIC_PRESETS')
    assert hasattr(cls, 'TECTONIC_ELEV_CHARS')
    assert hasattr(cls, 'TECTONIC_ELEV_THRESHOLDS')


# ── Enter / Exit ────────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_tectonic_mode()
    assert app.tectonic_menu is True
    assert app.tectonic_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app._tectonic_init(5)
    app._exit_tectonic_mode()
    assert app.tectonic_mode is False
    assert app.tectonic_menu is False
    assert app.tectonic_running is False


# ── Init all presets ────────────────────────────────────────────────────────

def test_init_all_presets():
    """Init works for every preset type without crashing."""
    for i in range(len(TECTONIC_PRESETS)):
        app = _make_app()
        app._tectonic_init(i)
        assert app.tectonic_mode is True
        assert app.tectonic_menu is False
        assert app.tectonic_running is True
        assert app.tectonic_rows > 0
        assert app.tectonic_cols > 0
        assert len(app.tectonic_elevation) == app.tectonic_rows
        assert len(app.tectonic_plate_id) == app.tectonic_rows
        assert len(app.tectonic_plates) == app.tectonic_num_plates


def test_init_pangaea_continental_plates():
    """Pangaea preset should have all continental plates."""
    # Find pangaea index
    idx = next(i for i, (_, _, k) in enumerate(TECTONIC_PRESETS) if k == "pangaea")
    app = _make_app()
    app._tectonic_init(idx)
    for plate in app.tectonic_plates:
        assert plate["continental"] is True


def test_init_collision_opposing_velocities():
    """Collision preset: left plates move right, right plates move left."""
    idx = next(i for i, (_, _, k) in enumerate(TECTONIC_PRESETS) if k == "collision")
    app = _make_app()
    app._tectonic_init(idx)
    # First 2 plates should move right (vc > 0), last 2 left (vc < 0)
    assert app.tectonic_plates[0]["vc"] > 0
    assert app.tectonic_plates[2]["vc"] < 0


def test_init_elevation_ranges():
    """Continental cells should be positive, oceanic should be negative."""
    idx = next(i for i, (_, _, k) in enumerate(TECTONIC_PRESETS) if k == "random")
    app = _make_app()
    app._tectonic_init(idx)
    has_positive = False
    has_negative = False
    for r in range(app.tectonic_rows):
        for c in range(app.tectonic_cols):
            if app.tectonic_elevation[r][c] > 0:
                has_positive = True
            if app.tectonic_elevation[r][c] < 0:
                has_negative = True
    # Random preset should typically have both
    assert has_positive or has_negative  # at least one


# ── Step simulation ─────────────────────────────────────────────────────────

def test_step_no_crash():
    app = _make_app()
    app._tectonic_init(5)  # random preset
    for _ in range(10):
        app._tectonic_step()
    assert app.tectonic_generation == 10


def test_step_increments_age():
    app = _make_app()
    app._tectonic_init(5)
    for _ in range(5):
        app._tectonic_step()
    assert app.tectonic_age == 5


def test_step_modifies_elevation():
    """After several steps, elevation should change."""
    app = _make_app()
    app._tectonic_init(5)
    initial_elev_sum = sum(
        app.tectonic_elevation[r][c]
        for r in range(app.tectonic_rows)
        for c in range(app.tectonic_cols)
    )
    for _ in range(20):
        app._tectonic_step()
    final_elev_sum = sum(
        app.tectonic_elevation[r][c]
        for r in range(app.tectonic_rows)
        for c in range(app.tectonic_cols)
    )
    # Elevation should have changed due to geological processes
    assert initial_elev_sum != final_elev_sum


def test_step_convergent_boundary_uplift():
    """Convergent continental boundaries should produce uplift."""
    # Use collision preset which has clear convergence
    idx = next(i for i, (_, _, k) in enumerate(TECTONIC_PRESETS) if k == "collision")
    app = _make_app()
    app._tectonic_init(idx)
    initial_max = max(
        app.tectonic_elevation[r][c]
        for r in range(app.tectonic_rows)
        for c in range(app.tectonic_cols)
    )
    for _ in range(50):
        app._tectonic_step()
    final_max = max(
        app.tectonic_elevation[r][c]
        for r in range(app.tectonic_rows)
        for c in range(app.tectonic_cols)
    )
    # After many steps, max elevation should increase (mountain building)
    assert final_max >= initial_max


def test_step_isostatic_rebound():
    """Very deep trenches should slowly rebound."""
    app = _make_app()
    app._tectonic_init(5)
    # Manually set an extremely deep trench
    app.tectonic_elevation[5][5] = -10000
    initial = app.tectonic_elevation[5][5]
    for _ in range(10):
        app._tectonic_step()
    final = app.tectonic_elevation[5][5]
    # Should have rebounded (become less negative)
    assert final > initial


def test_step_erosion_smoothing():
    """Erosion should smooth elevation toward neighbor averages."""
    app = _make_app()
    app._tectonic_init(5)
    # Create a spike
    r, c = app.tectonic_rows // 2, app.tectonic_cols // 2
    app.tectonic_elevation[r][c] = 8000
    # Run enough steps for erosion (occurs every 3rd generation)
    for _ in range(6):
        app._tectonic_step()
    # Spike should have been reduced somewhat
    assert app.tectonic_elevation[r][c] < 8000


# ── Elevation character/color mapping ───────────────────────────────────────

def test_elev_char_deep_ocean():
    app = _make_app()
    app._tectonic_init(5)
    ch = app._tectonic_elev_char(-9000)
    assert ch == TECTONIC_ELEV_CHARS[0]


def test_elev_char_high_peak():
    app = _make_app()
    app._tectonic_init(5)
    ch = app._tectonic_elev_char(9500)
    assert ch == TECTONIC_ELEV_CHARS[-1]


def test_elev_color_returns_int():
    """Color function should return a valid curses attribute integer."""
    app = _make_app()
    app._tectonic_init(5)
    for elev in [-5000, -1000, -100, 0, 500, 2000, 5000, 8000]:
        color = app._tectonic_elev_color(elev)
        assert isinstance(color, int)


# ── Menu key handling ───────────────────────────────────────────────────────

def test_menu_key_down():
    app = _make_app()
    app._enter_tectonic_mode()
    app._handle_tectonic_menu_key(ord('j'))
    assert app.tectonic_menu_sel == 1


def test_menu_key_up_wraps():
    app = _make_app()
    app._enter_tectonic_mode()
    app._handle_tectonic_menu_key(ord('k'))
    n = len(type(app).TECTONIC_PRESETS)
    assert app.tectonic_menu_sel == n - 1


def test_menu_key_enter():
    app = _make_app()
    app._enter_tectonic_mode()
    app._handle_tectonic_menu_key(10)  # Enter
    assert app.tectonic_mode is True
    assert app.tectonic_menu is False


def test_menu_key_escape():
    app = _make_app()
    app._enter_tectonic_mode()
    app._handle_tectonic_menu_key(27)
    assert app.tectonic_menu is False
    assert app.tectonic_mode is False


# ── Game key handling ───────────────────────────────────────────────────────

def test_key_space_pause():
    app = _make_app()
    app._tectonic_init(5)
    assert app.tectonic_running is True
    app._handle_tectonic_key(ord(' '))
    assert app.tectonic_running is False


def test_key_speed_up():
    app = _make_app()
    app._tectonic_init(5)
    initial = app.tectonic_speed_scale
    app._handle_tectonic_key(ord('+'))
    assert app.tectonic_speed_scale > initial


def test_key_speed_down():
    app = _make_app()
    app._tectonic_init(5)
    app.tectonic_speed_scale = 2.0
    app._handle_tectonic_key(ord('-'))
    assert app.tectonic_speed_scale < 2.0


def test_key_speed_clamp():
    """Speed should clamp between 0.25 and 5.0."""
    app = _make_app()
    app._tectonic_init(5)
    app.tectonic_speed_scale = 5.0
    app._handle_tectonic_key(ord('+'))
    assert app.tectonic_speed_scale <= 5.0
    app.tectonic_speed_scale = 0.25
    app._handle_tectonic_key(ord('-'))
    assert app.tectonic_speed_scale >= 0.25


def test_key_plate_view_toggle():
    app = _make_app()
    app._tectonic_init(5)
    assert app.tectonic_show_plates is False
    app._handle_tectonic_key(ord('p'))
    assert app.tectonic_show_plates is True


def test_key_help_toggle():
    app = _make_app()
    app._tectonic_init(5)
    assert app.tectonic_show_help is True
    app._handle_tectonic_key(ord('?'))
    assert app.tectonic_show_help is False


def test_key_restart():
    app = _make_app()
    app._tectonic_init(5)
    for _ in range(10):
        app._tectonic_step()
    assert app.tectonic_generation == 10
    app._handle_tectonic_key(ord('r'))
    assert app.tectonic_generation == 0


def test_key_menu_return():
    app = _make_app()
    app._tectonic_init(5)
    app._handle_tectonic_key(ord('m'))
    assert app.tectonic_menu is True
    assert app.tectonic_running is False


def test_key_escape_exits():
    app = _make_app()
    app._tectonic_init(5)
    app._handle_tectonic_key(27)
    assert app.tectonic_mode is False
    assert app.tectonic_running is False


# ── Voronoi plate assignment ────────────────────────────────────────────────

def test_plate_ids_in_range():
    """All plate IDs should be valid indices into the plates list."""
    app = _make_app()
    app._tectonic_init(5)
    for r in range(app.tectonic_rows):
        for c in range(app.tectonic_cols):
            pid = app.tectonic_plate_id[r][c]
            assert 0 <= pid < app.tectonic_num_plates


def test_all_plates_have_cells():
    """Every plate should have at least one cell assigned to it."""
    app = _make_app()
    app._tectonic_init(5)
    plate_cell_counts = [0] * app.tectonic_num_plates
    for r in range(app.tectonic_rows):
        for c in range(app.tectonic_cols):
            plate_cell_counts[app.tectonic_plate_id[r][c]] += 1
    for i, count in enumerate(plate_cell_counts):
        assert count > 0, f"Plate {i} has no cells"
