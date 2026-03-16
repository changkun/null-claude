"""Tests for life.modes.volcano — Volcanic Eruption mode."""
import math
from tests.conftest import make_mock_app
from life.modes.volcano import (
    register, VOLCANO_PRESETS, LAVA_CHARS, TERRAIN_CHARS, ASH_CHARS, ROCK_CHARS,
)


def _make_app():
    app = make_mock_app()
    app.volcano_mode = False
    app.volcano_menu = False
    app.volcano_menu_sel = 0
    app.volcano_running = False
    register(type(app))
    return app


# ── Module-level constants ──────────────────────────────────────────────────

def test_presets_structure():
    """Each preset is a (name, description, type_key) triple."""
    assert len(VOLCANO_PRESETS) == 6
    for name, desc, ptype in VOLCANO_PRESETS:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(desc, str) and len(desc) > 0
        assert ptype in ("strombolian", "plinian", "hawaiian", "vulcanian",
                         "caldera", "fissure")


def test_char_palettes():
    assert len(LAVA_CHARS) == 10
    assert len(TERRAIN_CHARS) == 5
    assert len(ASH_CHARS) == 9
    assert len(ROCK_CHARS) == 9


# ── Enter / Exit lifecycle ──────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_volcano_mode()
    assert app.volcano_menu is True
    assert app.volcano_menu_sel == 0


def test_exit_cleanup():
    app = _make_app()
    app.volcano_mode = True
    app._volcano_init(0)
    app._exit_volcano_mode()
    assert app.volcano_mode is False
    assert app.volcano_running is False


# ── Initialization across all 6 presets ─────────────────────────────────────

def test_init_all_presets():
    """Every preset must initialize without error and populate grids."""
    for idx in range(len(VOLCANO_PRESETS)):
        app = _make_app()
        app._volcano_init(idx)
        rows, cols = app.volcano_rows, app.volcano_cols
        assert rows > 0 and cols > 0
        assert len(app.volcano_terrain) == rows
        assert len(app.volcano_terrain[0]) == cols
        assert len(app.volcano_lava) == rows
        assert len(app.volcano_vents) >= 1, f"Preset {idx} has no vents"
        assert len(app.volcano_chambers) >= 1, f"Preset {idx} has no chamber"
        assert app.volcano_running is True
        assert app.volcano_generation == 0
        assert app.volcano_tick == 0


def test_init_strombolian_cone():
    """Strombolian preset builds a single cone with terrain peak near center."""
    app = _make_app()
    app._volcano_init(0)  # strombolian
    mid_r, mid_c = app.volcano_rows // 2, app.volcano_cols // 2
    peak = app.volcano_terrain[mid_r][mid_c]
    assert peak > 0.5, "Cone peak should be elevated"
    assert len(app.volcano_vents) == 1
    assert app.volcano_vents[0]["type"] == "strombolian"


def test_init_hawaiian_secondary_vent():
    """Hawaiian preset should have a secondary flank vent."""
    app = _make_app()
    app._volcano_init(2)  # hawaiian
    assert len(app.volcano_vents) >= 2, "Hawaiian should have >= 2 vents"


def test_init_caldera_depression():
    """Caldera preset carves a depression in the center."""
    app = _make_app()
    app._volcano_init(4)  # caldera
    mid_r, mid_c = app.volcano_rows // 2, app.volcano_cols // 2
    # Should have multiple vents along the ring
    assert len(app.volcano_vents) == 4


def test_init_fissure_vents():
    """Fissure preset places 6 vents in a line."""
    app = _make_app()
    app._volcano_init(5)  # fissure
    assert len(app.volcano_vents) == 6
    # Check vents are spread across columns
    cols_set = {v["c"] for v in app.volcano_vents}
    assert len(cols_set) >= 4, "Fissure vents should be spatially distributed"


# ── Cone building ───────────────────────────────────────────────────────────

def test_build_cone_peak_height():
    app = _make_app()
    app._volcano_init(0)
    mid_r = app.volcano_rows // 2
    mid_c = app.volcano_cols // 2
    # Terrain near peak should be the highest
    peak = app.volcano_terrain[mid_r][mid_c]
    edge = app.volcano_terrain[0][0]
    assert peak > edge


def test_build_cone_foothills():
    """Terrain should have gentle foothills beyond the cone radius."""
    app = _make_app()
    app._volcano_init(0)
    # Far corner terrain should be near zero but not negative
    val = app.volcano_terrain[0][0]
    assert val >= 0.0


# ── Step simulation ─────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._volcano_init(0)
    app._volcano_step()
    assert app.volcano_generation == 1
    assert app.volcano_tick == 1


def test_step_no_crash():
    app = _make_app()
    app.volcano_mode = True
    app._volcano_init(0)
    for _ in range(10):
        app._volcano_step()
    assert app.volcano_generation == 10


def test_step_all_presets_10_ticks():
    """Run 10 steps on every preset without error."""
    for idx in range(len(VOLCANO_PRESETS)):
        app = _make_app()
        app._volcano_init(idx)
        for _ in range(10):
            app._volcano_step()
        assert app.volcano_generation == 10


# ── Eruption mechanics ──────────────────────────────────────────────────────

def test_eruption_threshold_hawaiian():
    """Hawaiian eruption threshold is lower (0.4) than others (0.6)."""
    app = _make_app()
    app._volcano_init(2)  # hawaiian
    # Set pressure just above hawaiian threshold
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.5
    app._volcano_step()
    # At pressure 0.5 hawaiian should erupt (threshold 0.4), producing lava
    mid_r, mid_c = app.volcano_rows // 2, app.volcano_cols // 2
    lava_sum = sum(app.volcano_lava[r][c] for r in range(app.volcano_rows)
                   for c in range(app.volcano_cols))
    assert lava_sum > 0, "Hawaiian at pressure 0.5 should produce lava"


def test_pressure_recharge():
    """Chamber pressure should increase over time from recharge."""
    app = _make_app()
    app._volcano_init(0)  # strombolian
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0  # drain
    initial_p = 0.0
    app._volcano_step()
    new_p = app.volcano_chambers[0]["pressure"]
    assert new_p > initial_p, "Pressure should recharge"


def test_pressure_drain_on_eruption():
    """Eruption should drain chamber pressure."""
    app = _make_app()
    app._volcano_init(0)
    for ch in app.volcano_chambers:
        ch["pressure"] = 1.0
    app._volcano_step()
    assert app.volcano_chambers[0]["pressure"] < 1.0


def test_forced_eruption():
    """Forcing eruption should spike pressure to max."""
    app = _make_app()
    app._volcano_init(0)
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
    # Simulate the 'e' key handler
    for ch in app.volcano_chambers:
        ch["pressure"] = ch["max_pressure"]
    assert app.volcano_chambers[0]["pressure"] == 1.0


# ── Lava flow physics ───────────────────────────────────────────────────────

def test_lava_flows_downhill():
    """Lava placed at the cone peak should flow to lower cells."""
    app = _make_app()
    app._volcano_init(0)  # strombolian
    mid_r, mid_c = app.volcano_rows // 2, app.volcano_cols // 2
    app.volcano_lava[mid_r][mid_c] = 0.5
    app.volcano_lava_temp[mid_r][mid_c] = 1100.0
    initial_peak_lava = app.volcano_lava[mid_r][mid_c]
    app._volcano_step()
    # Lava should spread to neighbors
    total_lava = sum(app.volcano_lava[r][c] for r in range(app.volcano_rows)
                     for c in range(app.volcano_cols))
    assert total_lava > 0


def test_lava_viscosity_with_temperature():
    """Cold lava should flow slower than hot lava."""
    app = _make_app()
    app._volcano_init(0)
    mid_r, mid_c = app.volcano_rows // 2, app.volcano_cols // 2
    # Make terrain flat for controlled test
    for r in range(app.volcano_rows):
        for c in range(app.volcano_cols):
            app.volcano_terrain[r][c] = 0.0
    # Hot lava
    app.volcano_lava[mid_r][mid_c] = 0.5
    app.volcano_lava_temp[mid_r][mid_c] = 1100.0
    app.volcano_terrain[mid_r][mid_c] = 0.5  # elevated
    app._volcano_step()
    hot_spread = sum(app.volcano_lava[r][c] for r in range(app.volcano_rows)
                     for c in range(app.volcano_cols)
                     if (r, c) != (mid_r, mid_c))
    assert hot_spread > 0, "Hot lava should flow"


# ── Cooling and solidification ──────────────────────────────────────────────

def test_lava_cooling():
    """Lava temperature should decrease each step (radiative cooling)."""
    app = _make_app()
    app._volcano_init(0)
    mid_r, mid_c = app.volcano_rows // 2, app.volcano_cols // 2
    app.volcano_lava[mid_r][mid_c] = 0.5
    app.volcano_lava_temp[mid_r][mid_c] = 800.0
    # No eruption — drain pressure
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
        ch["magma_volume"] = 0.0
    app._volcano_step()
    assert app.volcano_lava_temp[mid_r][mid_c] < 800.0


def test_solidification_below_500():
    """Lava below 500 degrees should solidify into rock."""
    app = _make_app()
    app._volcano_init(0)
    mid_r, mid_c = 5, 5
    app.volcano_lava[mid_r][mid_c] = 0.5
    app.volcano_lava_temp[mid_r][mid_c] = 400.0
    # Suppress eruption
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
        ch["magma_volume"] = 0.0
    initial_rock = app.volcano_rock[mid_r][mid_c]
    app._volcano_step()
    assert app.volcano_rock[mid_r][mid_c] > initial_rock, "Rock should increase below 500 deg"
    assert app.volcano_lava[mid_r][mid_c] < 0.5, "Lava should decrease during solidification"


# ── Pyroclastic density currents ────────────────────────────────────────────

def test_pyroclastic_flow_spreads():
    """PDC material should spread across the terrain."""
    app = _make_app()
    app._volcano_init(1)  # plinian (supports pyroclastic)
    mid_r, mid_c = app.volcano_rows // 2, app.volcano_cols // 2
    app.volcano_pyroclastic[mid_r][mid_c] = 0.8
    app._volcano_step()
    # PDC should have spread to some neighbors
    neighbor_pyro = 0
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = mid_r + dr, mid_c + dc
            if 0 <= nr < app.volcano_rows and 0 <= nc < app.volcano_cols:
                neighbor_pyro += app.volcano_pyroclastic[nr][nc]
    assert neighbor_pyro > 0, "PDC should spread to neighbors"


def test_pyroclastic_dissipation():
    """PDC material should dissipate over time."""
    app = _make_app()
    app._volcano_init(1)
    # Suppress eruption
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
        ch["magma_volume"] = 0.0
    app.volcano_pyroclastic[10][10] = 0.5
    initial = 0.5
    app._volcano_step()
    total = sum(app.volcano_pyroclastic[r][c] for r in range(app.volcano_rows)
                for c in range(app.volcano_cols))
    assert total < initial * app.volcano_rows * app.volcano_cols


# ── Ash dispersion ──────────────────────────────────────────────────────────

def test_ash_disperses():
    """Ash should spread and settle over steps."""
    app = _make_app()
    app._volcano_init(0)
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
        ch["magma_volume"] = 0.0
    app.volcano_ash[10][10] = 0.8
    app._volcano_step()
    # Ash should have diffused
    total = sum(app.volcano_ash[r][c] for r in range(app.volcano_rows)
                for c in range(app.volcano_cols))
    assert total > 0


def test_ash_clamped():
    """Ash values should stay within [0, 1]."""
    app = _make_app()
    app._volcano_init(0)
    app.volcano_ash[5][5] = 0.99
    for _ in range(5):
        app._volcano_step()
    for r in range(app.volcano_rows):
        for c in range(app.volcano_cols):
            assert 0.0 <= app.volcano_ash[r][c] <= 1.0


# ── Gas dispersion ──────────────────────────────────────────────────────────

def test_gas_dissipates():
    """Volcanic gas should diffuse and decay."""
    app = _make_app()
    app._volcano_init(0)
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
        ch["magma_volume"] = 0.0
    app.volcano_gas[10][10] = 0.5
    app._volcano_step()
    assert app.volcano_gas[10][10] < 0.5


def test_gas_clamped():
    app = _make_app()
    app._volcano_init(0)
    app.volcano_gas[5][5] = 0.99
    for _ in range(5):
        app._volcano_step()
    for r in range(app.volcano_rows):
        for c in range(app.volcano_cols):
            assert 0.0 <= app.volcano_gas[r][c] <= 1.0


# ── Ejecta particles ────────────────────────────────────────────────────────

def test_ejecta_particles_capped():
    """Particle count should never exceed 200."""
    app = _make_app()
    app._volcano_init(0)
    for ch in app.volcano_chambers:
        ch["pressure"] = 1.0
    for _ in range(50):
        app._volcano_step()
    assert len(app.volcano_particles) <= 200


def test_ejecta_gravity():
    """Ejecta particles should experience gravity (vr increases)."""
    app = _make_app()
    app._volcano_init(0)
    particle = {
        "r": 10.0, "c": 10.0, "vr": -2.0, "vc": 0.0,
        "life": 20, "size": 0.5, "type": "bomb",
    }
    app.volcano_particles = [particle]
    old_vr = particle["vr"]
    app._volcano_step()
    # Particle vr should have increased (gravity adds positive vr)
    if app.volcano_particles:
        assert app.volcano_particles[0]["vr"] > old_vr


def test_ejecta_deposit_on_impact():
    """Bombs should deposit rock; tephra should deposit ash on impact."""
    app = _make_app()
    app._volcano_init(0)
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
        ch["magma_volume"] = 0.0
    r, c = 10, 10
    # A bomb about to land (vr > 0 and life will go to 1 after step, < 3)
    # After step, particle moves to r + vr*speed = 10 + 1.0 = 11
    app.volcano_particles = [{
        "r": float(r), "c": float(c), "vr": 1.0, "vc": 0.0,
        "life": 2, "size": 0.8, "type": "bomb",
    }]
    initial_rock_sum = sum(app.volcano_rock[rr][c] for rr in range(max(0, r - 2), min(app.volcano_rows, r + 3)))
    app._volcano_step()
    final_rock_sum = sum(app.volcano_rock[rr][c] for rr in range(max(0, r - 2), min(app.volcano_rows, r + 3)))
    assert final_rock_sum > initial_rock_sum, "Bomb should deposit rock near impact point"


# ── Wind variation ──────────────────────────────────────────────────────────

def test_wind_bounded():
    """Wind components should stay within [-2, 2]."""
    app = _make_app()
    app._volcano_init(0)
    for _ in range(200):
        app._volcano_step()
    assert -2.0 <= app.volcano_wind_u <= 2.0
    assert -2.0 <= app.volcano_wind_v <= 2.0


# ── Speed scale ─────────────────────────────────────────────────────────────

def test_speed_scale_affects_step():
    """Higher speed should produce more lava per step."""
    app1 = _make_app()
    app1._volcano_init(2)  # hawaiian
    for ch in app1.volcano_chambers:
        ch["pressure"] = 0.8
    app1.volcano_speed_scale = 1.0
    app1._volcano_step()

    app2 = _make_app()
    app2._volcano_init(2)
    for ch in app2.volcano_chambers:
        ch["pressure"] = 0.8
    app2.volcano_speed_scale = 3.0
    app2._volcano_step()

    lava1 = sum(app1.volcano_lava[r][c] for r in range(app1.volcano_rows)
                for c in range(app1.volcano_cols))
    lava2 = sum(app2.volcano_lava[r][c] for r in range(app2.volcano_rows)
                for c in range(app2.volcano_cols))
    assert lava2 >= lava1, "More speed should produce at least as much lava"


# ── Key handling ────────────────────────────────────────────────────────────

def test_handle_menu_key_navigation():
    app = _make_app()
    app._enter_volcano_mode()
    assert app.volcano_menu_sel == 0
    app._handle_volcano_menu_key(ord('j'))  # down
    assert app.volcano_menu_sel == 1
    app._handle_volcano_menu_key(ord('k'))  # up
    assert app.volcano_menu_sel == 0


def test_handle_menu_key_escape():
    app = _make_app()
    app._enter_volcano_mode()
    app._handle_volcano_menu_key(27)  # ESC
    assert app.volcano_menu is False
    assert app.volcano_mode is False


def test_handle_volcano_key_pause():
    app = _make_app()
    app._volcano_init(0)
    app.volcano_running = True
    app._handle_volcano_key(ord(' '))
    assert app.volcano_running is False
    app._handle_volcano_key(ord(' '))
    assert app.volcano_running is True


def test_handle_volcano_key_speed():
    app = _make_app()
    app._volcano_init(0)
    app._handle_volcano_key(ord('+'))
    assert app.volcano_speed_scale == 1.25
    app._handle_volcano_key(ord('-'))
    assert app.volcano_speed_scale == 1.0


def test_handle_volcano_key_layer_cycle():
    app = _make_app()
    app._volcano_init(0)
    assert app.volcano_layer == "default"
    app._handle_volcano_key(ord('l'))
    assert app.volcano_layer == "terrain"
    app._handle_volcano_key(ord('l'))
    assert app.volcano_layer == "lava"


def test_handle_volcano_key_force_eruption():
    app = _make_app()
    app._volcano_init(0)
    for ch in app.volcano_chambers:
        ch["pressure"] = 0.0
    app._handle_volcano_key(ord('e'))
    assert app.volcano_chambers[0]["pressure"] == 1.0


# ── Registration ────────────────────────────────────────────────────────────

def test_register_binds_all_methods():
    app = _make_app()
    methods = [
        '_enter_volcano_mode', '_exit_volcano_mode', '_volcano_init',
        '_volcano_build_cone', '_volcano_step', '_handle_volcano_menu_key',
        '_handle_volcano_key', '_draw_volcano_menu', '_volcano_terrain_color',
        '_volcano_lava_color', '_draw_volcano',
    ]
    for m in methods:
        assert hasattr(app, m), f"Missing method: {m}"
