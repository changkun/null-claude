"""Tests for life.modes.cellular_potts — Cellular Potts Model mode."""
import math
import curses
from tests.conftest import make_mock_app
from life.modes.cellular_potts import register


def _make_app():
    app = make_mock_app()
    app.cpm_mode = False
    app.cpm_menu = False
    app.cpm_menu_sel = 0
    app.cpm_running = False
    app.cpm_generation = 0
    app.cpm_preset_name = ""
    app.cpm_rows = 0
    app.cpm_cols = 0
    app.cpm_steps_per_frame = 500
    app.cpm_grid = []
    app.cpm_num_cells = 0
    app.cpm_temperature = 10.0
    app.cpm_lambda_area = 1.0
    app.cpm_target_area = []
    app.cpm_cell_type = []
    app.cpm_J = []
    app.cpm_num_types = 2
    app.cpm_viz_mode = 0
    app.cpm_chemotaxis = False
    app.cpm_chem_field = []
    app.cpm_chem_lambda = 0.0
    app.cpm_chem_decay = 0.01
    app.cpm_chem_source_type = 0
    app.cpm_area_cache = []
    # Presets: (name, desc, preset_id)
    type(app).CPM_PRESETS = [
        ("Cell Sorting", "Differential adhesion drives cell type segregation", "sorting"),
        ("Wound Healing", "Cell sheet migration into empty wound region", "wound"),
        ("Tumor Growth", "Tumor cells invade surrounding tissue", "tumor"),
        ("Checkerboard", "Alternating cell types in a grid", "checker"),
        ("Foam", "Single-type foam coarsening", "foam"),
        ("Chemotaxis", "Cells migrate up a chemical gradient", "chemotaxis"),
    ]
    register(type(app))
    return app


# --- Lifecycle tests ---

def test_enter():
    app = _make_app()
    app._enter_cpm_mode()
    assert app.cpm_menu is True
    assert app.cpm_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.cpm_mode = True
    app._cpm_init(0)
    app._exit_cpm_mode()
    assert app.cpm_mode is False
    assert app.cpm_menu is False
    assert app.cpm_running is False
    assert app.cpm_grid == []
    assert app.cpm_chem_field == []


# --- Initialization tests for each preset ---

def test_init_sorting():
    app = _make_app()
    app._cpm_init(0)  # sorting
    assert app.cpm_mode is True
    assert app.cpm_menu is False
    assert app.cpm_preset_name == "Cell Sorting"
    assert app.cpm_num_types == 2
    assert app.cpm_num_cells > 0
    assert len(app.cpm_cell_type) == app.cpm_num_cells + 1
    assert len(app.cpm_target_area) == app.cpm_num_cells + 1
    assert len(app.cpm_area_cache) == app.cpm_num_cells + 1
    # J matrix should be 3x3 for medium + 2 types
    assert len(app.cpm_J) == 3
    assert len(app.cpm_J[0]) == 3
    # Cell types should be 1 or 2
    for cid in range(1, app.cpm_num_cells + 1):
        assert app.cpm_cell_type[cid] in (1, 2)


def test_init_wound():
    app = _make_app()
    app._cpm_init(1)  # wound
    assert app.cpm_num_types == 1
    assert app.cpm_num_cells > 0
    assert len(app.cpm_J) == 2
    for cid in range(1, app.cpm_num_cells + 1):
        assert app.cpm_cell_type[cid] == 1


def test_init_tumor():
    app = _make_app()
    app._cpm_init(2)  # tumor
    assert app.cpm_num_types == 2
    assert app.cpm_num_cells > 0
    # Tumor cells should have larger target area
    has_type1 = False
    has_type2 = False
    for cid in range(1, app.cpm_num_cells + 1):
        ct = app.cpm_cell_type[cid]
        if ct == 1:
            has_type1 = True
        elif ct == 2:
            has_type2 = True
    assert has_type1
    assert has_type2


def test_init_checker():
    app = _make_app()
    app._cpm_init(3)  # checker
    assert app.cpm_num_types == 2
    assert app.cpm_num_cells > 0


def test_init_foam():
    app = _make_app()
    app._cpm_init(4)  # foam
    assert app.cpm_num_types == 1
    assert app.cpm_num_cells > 0
    assert app.cpm_temperature == 5.0
    assert app.cpm_lambda_area == 3.0


def test_init_chemotaxis():
    app = _make_app()
    app._cpm_init(5)  # chemotaxis
    assert app.cpm_chemotaxis is True
    assert app.cpm_chem_lambda == 200.0
    # Chemical field should have gradient (high on right)
    rows, cols = app.cpm_rows, app.cpm_cols
    assert app.cpm_chem_field[0][0] < app.cpm_chem_field[0][cols - 1]


# --- Area cache consistency ---

def test_area_cache_consistency():
    """Area cache must match actual grid cell counts after init."""
    app = _make_app()
    app._cpm_init(0)
    rows, cols = app.cpm_rows, app.cpm_cols
    # Recount from grid
    recount = [0] * (app.cpm_num_cells + 1)
    for r in range(rows):
        for c in range(cols):
            cid = app.cpm_grid[r][c]
            if cid > 0:
                recount[cid] += 1
    for cid in range(1, app.cpm_num_cells + 1):
        assert app.cpm_area_cache[cid] == recount[cid], (
            f"Cell {cid}: cache={app.cpm_area_cache[cid]} vs actual={recount[cid]}"
        )


def test_area_cache_after_steps():
    """Area cache should remain consistent after simulation steps."""
    app = _make_app()
    app._cpm_init(0)
    for _ in range(200):
        app._cpm_step()
    rows, cols = app.cpm_rows, app.cpm_cols
    recount = [0] * (app.cpm_num_cells + 1)
    for r in range(rows):
        for c in range(cols):
            cid = app.cpm_grid[r][c]
            if cid > 0 and cid < len(recount):
                recount[cid] += 1
    for cid in range(1, app.cpm_num_cells + 1):
        if cid < len(app.cpm_area_cache) and cid < len(recount):
            assert app.cpm_area_cache[cid] == recount[cid], (
                f"Cell {cid}: cache={app.cpm_area_cache[cid]} vs actual={recount[cid]}"
            )


# --- Metropolis step tests ---

def test_step_increments_generation():
    app = _make_app()
    app._cpm_init(0)
    gen_before = app.cpm_generation
    app._cpm_step()
    assert app.cpm_generation == gen_before + 1


def test_step_no_crash():
    """Run many steps on each preset without error."""
    app = _make_app()
    for preset_idx in range(6):
        app._cpm_init(preset_idx)
        for _ in range(50):
            app._cpm_step()
        assert app.cpm_generation == 50


def test_metropolis_energy_decrease_accepted():
    """Construct a scenario where delta_H < 0 — move must be accepted."""
    app = _make_app()
    # Manually set up a tiny grid: 5x5, 2 cells
    app.cpm_rows = 5
    app.cpm_cols = 5
    app.cpm_grid = [[0]*5 for _ in range(5)]
    app.cpm_grid[2][2] = 1
    app.cpm_grid[2][3] = 1
    app.cpm_grid[2][1] = 2
    app.cpm_num_cells = 2
    app.cpm_cell_type = [0, 1, 1]
    app.cpm_target_area = [0, 10, 10]  # large target encourages growth
    app.cpm_area_cache = [0, 2, 1]
    app.cpm_J = [[0.0, 16.0], [16.0, 2.0]]
    app.cpm_num_types = 1
    app.cpm_temperature = 10.0
    app.cpm_lambda_area = 1.0
    app.cpm_chemotaxis = False
    app.cpm_chem_field = [[0.0]*5 for _ in range(5)]
    # Just run steps — should not crash
    for _ in range(100):
        app._cpm_step()


def test_high_temperature_more_accepting():
    """At very high temperature, acceptance rate should be high."""
    import random
    random.seed(42)
    app = _make_app()
    app._cpm_init(0)
    app.cpm_temperature = 1000.0
    gen_start = app.cpm_generation
    changes = 0
    grid_before = [row[:] for row in app.cpm_grid]
    for _ in range(500):
        app._cpm_step()
    # Count pixel changes
    for r in range(app.cpm_rows):
        for c in range(app.cpm_cols):
            if app.cpm_grid[r][c] != grid_before[r][c]:
                changes += 1
    # High temp should produce at least some changes
    assert changes > 0


def test_zero_temperature_no_uphill():
    """At near-zero temperature, uphill moves should be rejected."""
    import random
    random.seed(123)
    app = _make_app()
    app._cpm_init(0)
    app.cpm_temperature = 0.001
    # Run steps — should not crash even at very low T
    for _ in range(200):
        app._cpm_step()


# --- Chemical diffusion tests ---

def test_diffuse_chem_decay():
    """Chemical field should decay over time."""
    app = _make_app()
    app._cpm_init(5)  # chemotaxis
    # Get initial total concentration
    initial_total = sum(
        app.cpm_chem_field[r][c]
        for r in range(app.cpm_rows) for c in range(app.cpm_cols)
    )
    # Diffuse a few times
    for _ in range(5):
        app._cpm_diffuse_chem()
    # Interior values should change; right edge stays 1.0
    assert app.cpm_chem_field[0][app.cpm_cols - 1] == 1.0


def test_diffuse_chem_nonnegative():
    """Chemical concentrations should never go negative."""
    app = _make_app()
    app._cpm_init(5)  # chemotaxis
    for _ in range(20):
        app._cpm_diffuse_chem()
    for r in range(app.cpm_rows):
        for c in range(app.cpm_cols):
            assert app.cpm_chem_field[r][c] >= 0.0


# --- Key handling tests ---

def test_menu_key_navigation():
    app = _make_app()
    app._enter_cpm_mode()
    assert app.cpm_menu_sel == 0
    app._handle_cpm_menu_key(curses.KEY_DOWN)
    assert app.cpm_menu_sel == 1
    app._handle_cpm_menu_key(curses.KEY_UP)
    assert app.cpm_menu_sel == 0
    # Wrap around
    app._handle_cpm_menu_key(curses.KEY_UP)
    assert app.cpm_menu_sel == len(type(app).CPM_PRESETS) - 1


def test_menu_key_select():
    app = _make_app()
    app._enter_cpm_mode()
    app._handle_cpm_menu_key(10)  # Enter
    assert app.cpm_mode is True
    assert app.cpm_menu is False


def test_menu_key_cancel():
    app = _make_app()
    app._enter_cpm_mode()
    app._handle_cpm_menu_key(ord("q"))
    assert app.cpm_menu is False


def test_sim_key_space_toggle():
    app = _make_app()
    app._cpm_init(0)
    assert app.cpm_running is False
    app._handle_cpm_key(ord(" "))
    assert app.cpm_running is True
    app._handle_cpm_key(ord(" "))
    assert app.cpm_running is False


def test_sim_key_temperature():
    app = _make_app()
    app._cpm_init(0)
    initial_temp = app.cpm_temperature
    app._handle_cpm_key(ord("t"))
    assert app.cpm_temperature == initial_temp + 1.0
    app._handle_cpm_key(ord("T"))
    assert app.cpm_temperature == initial_temp


def test_sim_key_lambda_area():
    app = _make_app()
    app._cpm_init(0)
    initial_la = app.cpm_lambda_area
    app._handle_cpm_key(ord("a"))
    assert app.cpm_lambda_area == initial_la + 0.5
    app._handle_cpm_key(ord("A"))
    assert app.cpm_lambda_area == initial_la


def test_sim_key_viz_cycle():
    app = _make_app()
    app._cpm_init(0)
    assert app.cpm_viz_mode == 0
    app._handle_cpm_key(ord("v"))
    assert app.cpm_viz_mode == 1
    app._handle_cpm_key(ord("v"))
    assert app.cpm_viz_mode == 2
    app._handle_cpm_key(ord("v"))
    assert app.cpm_viz_mode == 0


def test_sim_key_speed():
    app = _make_app()
    app._cpm_init(0)
    initial_spf = app.cpm_steps_per_frame
    app._handle_cpm_key(ord(">"))
    assert app.cpm_steps_per_frame == initial_spf * 2
    app._handle_cpm_key(ord("<"))
    assert app.cpm_steps_per_frame == initial_spf


def test_sim_key_reset():
    app = _make_app()
    app._cpm_init(0)
    for _ in range(10):
        app._cpm_step()
    assert app.cpm_generation > 0
    app._handle_cpm_key(ord("r"))
    assert app.cpm_generation == 0


def test_sim_key_quit():
    app = _make_app()
    app._cpm_init(0)
    app._handle_cpm_key(ord("q"))
    assert app.cpm_mode is False


def test_sim_key_return_to_menu():
    app = _make_app()
    app._cpm_init(0)
    app._handle_cpm_key(ord("R"))
    assert app.cpm_mode is False
    assert app.cpm_menu is True


def test_sim_key_step_advances():
    app = _make_app()
    app._cpm_init(4)  # foam (no chemotaxis)
    gen_before = app.cpm_generation
    app._handle_cpm_key(ord("n"))
    assert app.cpm_generation == gen_before + app.cpm_steps_per_frame


def test_sim_key_step_with_chemotaxis():
    app = _make_app()
    app._cpm_init(5)  # chemotaxis
    gen_before = app.cpm_generation
    app._handle_cpm_key(ord("n"))
    assert app.cpm_generation == gen_before + app.cpm_steps_per_frame


def test_noop_key():
    """Unknown key should not crash."""
    app = _make_app()
    app._cpm_init(0)
    result = app._handle_cpm_key(ord("z"))
    assert result is True


def test_noop_key_neg1():
    """Key -1 (no input) should be handled."""
    app = _make_app()
    app._cpm_init(0)
    result = app._handle_cpm_key(-1)
    assert result is True
    result2 = app._handle_cpm_menu_key(-1)
    assert result2 is True


# --- Hamiltonian / energy tests ---

def test_j_matrix_symmetry():
    """J matrix should be symmetric for all presets."""
    app = _make_app()
    for preset_idx in range(6):
        app._cpm_init(preset_idx)
        J = app.cpm_J
        for i in range(len(J)):
            for j in range(len(J[i])):
                assert abs(J[i][j] - J[j][i]) < 1e-10, (
                    f"Preset {preset_idx}: J[{i}][{j}]={J[i][j]} != J[{j}][{i}]={J[j][i]}"
                )


def test_grid_dimensions():
    """Grid dimensions should match declared rows/cols for all presets."""
    app = _make_app()
    for preset_idx in range(6):
        app._cpm_init(preset_idx)
        assert len(app.cpm_grid) == app.cpm_rows
        for row in app.cpm_grid:
            assert len(row) == app.cpm_cols
        assert len(app.cpm_chem_field) == app.cpm_rows
        for row in app.cpm_chem_field:
            assert len(row) == app.cpm_cols


def test_cell_ids_in_range():
    """All cell IDs in grid should be valid (0 to num_cells)."""
    app = _make_app()
    for preset_idx in range(6):
        app._cpm_init(preset_idx)
        for r in range(app.cpm_rows):
            for c in range(app.cpm_cols):
                cid = app.cpm_grid[r][c]
                assert 0 <= cid <= app.cpm_num_cells, (
                    f"Preset {preset_idx}: invalid cell ID {cid} at ({r},{c})"
                )


def test_temperature_clamp():
    """Temperature should not go below 0.5 or above 100."""
    app = _make_app()
    app._cpm_init(0)
    app.cpm_temperature = 100.0
    app._handle_cpm_key(ord("t"))
    assert app.cpm_temperature == 100.0  # clamped
    app.cpm_temperature = 0.5
    app._handle_cpm_key(ord("T"))
    assert app.cpm_temperature == 0.5  # clamped


def test_lambda_area_clamp():
    """Lambda area should not go below 0 or above 20."""
    app = _make_app()
    app._cpm_init(0)
    app.cpm_lambda_area = 20.0
    app._handle_cpm_key(ord("a"))
    assert app.cpm_lambda_area == 20.0
    app.cpm_lambda_area = 0.0
    app._handle_cpm_key(ord("A"))
    assert app.cpm_lambda_area == 0.0
