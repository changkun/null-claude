"""Tests for life.modes.particle_collider — Particle Collider mode."""
import curses
import math
from tests.conftest import make_mock_app
from life.modes.particle_collider import (
    register,
    COLLIDER_PRESETS,
    _COLLIDER_PARTICLES,
    _COLLIDER_SHOWER_CHARS,
    _COLLIDER_DETECTOR_LABELS,
)


def _make_app():
    app = make_mock_app()
    app.collider_mode = False
    app.collider_menu = False
    app.collider_menu_sel = 0
    app.collider_running = False
    app.collider_speed = 1
    app.collider_beams = []
    app.collider_showers = []
    app.collider_trails = []
    app.collider_detections = []
    app.collider_detector_log = []
    register(type(app))
    return app


# ── enter / exit ──────────────────────────────────────────────────────────

def test_enter():
    app = _make_app()
    app._enter_collider_mode()
    assert app.collider_menu is True
    assert app.collider_mode is True


def test_exit_cleanup():
    app = _make_app()
    app.collider_mode = True
    app._collider_init("lhc")
    assert len(app.collider_beams) > 0
    app._exit_collider_mode()
    assert app.collider_mode is False
    assert app.collider_beams == []
    assert app.collider_showers == []
    assert app.collider_trails == []
    assert app.collider_detections == []
    assert app.collider_detector_log == []


# ── init presets ──────────────────────────────────────────────────────────

def test_init_lhc():
    app = _make_app()
    app._collider_init("lhc")
    assert app.collider_energy == 13.6
    assert len(app.collider_beams) == 12
    assert app.collider_running is True
    assert app.collider_speed == 1


def test_init_heavy_ion():
    app = _make_app()
    app._collider_init("heavy_ion")
    assert app.collider_energy == 5.36
    assert len(app.collider_beams) == 8


def test_init_lepton():
    app = _make_app()
    app._collider_init("lepton")
    assert app.collider_energy == 0.209
    assert len(app.collider_beams) == 16


def test_init_discovery():
    app = _make_app()
    app._collider_init("discovery")
    assert app.collider_energy == 14.0
    assert len(app.collider_beams) == 20
    assert app.collider_collision_rate == 0.08


def test_init_all_presets():
    for _name, _desc, key in COLLIDER_PRESETS:
        app = _make_app()
        app._collider_init(key)
        assert app.collider_running is True
        assert app.collider_generation == 0
        assert len(app.collider_beams) > 0
        assert len(app.collider_collision_points) == 4


def test_init_ring_geometry():
    app = _make_app()
    app._collider_init("lhc")
    assert app.collider_ring_cx > 0
    assert app.collider_ring_cy > 0
    assert app.collider_ring_rx > 0
    assert app.collider_ring_ry > 0


def test_init_beam_directions():
    """Half beams clockwise, half counter-clockwise."""
    app = _make_app()
    app._collider_init("lhc")
    cw = sum(1 for b in app.collider_beams if b["speed"] > 0)
    ccw = sum(1 for b in app.collider_beams if b["speed"] < 0)
    assert cw == ccw


def test_init_collision_points():
    app = _make_app()
    app._collider_init("lhc")
    labels = [cp["label"] for cp in app.collider_collision_points]
    assert labels == _COLLIDER_DETECTOR_LABELS


# ── step ──────────────────────────────────────────────────────────────────

def test_step_increments_generation():
    app = _make_app()
    app._collider_init("lhc")
    app._collider_step()
    assert app.collider_generation == 1


def test_step_no_crash():
    app = _make_app()
    app.collider_mode = True
    app._collider_init("lhc")
    for _ in range(10):
        app._collider_step()
    assert app.collider_generation == 10


def test_step_beams_move():
    """Beam angles should change after stepping."""
    app = _make_app()
    app._collider_init("lhc")
    initial_angles = [b["angle"] for b in app.collider_beams]
    app._collider_step()
    final_angles = [b["angle"] for b in app.collider_beams]
    assert initial_angles != final_angles


def test_step_beam_trails():
    """Beams should accumulate trail points."""
    app = _make_app()
    app._collider_init("lhc")
    for _ in range(5):
        app._collider_step()
    for beam in app.collider_beams:
        assert len(beam["trail"]) > 0


def test_step_trail_length_limited():
    """Beam trails should be capped at 6."""
    app = _make_app()
    app._collider_init("lhc")
    for _ in range(20):
        app._collider_step()
    for beam in app.collider_beams:
        assert len(beam["trail"]) <= 6


def test_step_collision_flash_decays():
    """Collision point flash should decay."""
    app = _make_app()
    app._collider_init("lhc")
    app.collider_collision_points[0]["flash"] = 1.0
    app._collider_step()
    assert app.collider_collision_points[0]["flash"] < 1.0


def test_step_shower_particles_decay():
    """Shower particles should lose life each step."""
    app = _make_app()
    app._collider_init("lhc")
    # Manually trigger a shower
    cx = app.collider_ring_cx
    cy = app.collider_ring_cy
    app._collider_spawn_shower(cx, cy, 13.6, "lhc")
    initial_lives = [p["life"] for s in app.collider_showers for p in s["particles"]]
    app._collider_step()
    final_lives = [p["life"] for s in app.collider_showers for p in s["particles"]]
    # Lives should decrease
    assert sum(final_lives) < sum(initial_lives)


def test_step_detection_flash_decays():
    app = _make_app()
    app._collider_init("lhc")
    cx = app.collider_ring_cx
    cy = app.collider_ring_cy
    app._collider_spawn_shower(cx, cy, 13.6, "lhc")
    assert len(app.collider_detections) > 0
    flash_before = app.collider_detections[-1]["flash"]
    app._collider_step()
    assert app.collider_detections[-1]["flash"] < flash_before


def test_step_all_presets():
    for _name, _desc, key in COLLIDER_PRESETS:
        app = _make_app()
        app._collider_init(key)
        for _ in range(50):
            app._collider_step()
        assert app.collider_generation == 50


# ── spawn_shower ──────────────────────────────────────────────────────────

def test_spawn_shower():
    app = _make_app()
    app._collider_init("lhc")
    app._collider_spawn_shower(60.0, 20.0, 13.6, "lhc")
    assert len(app.collider_showers) == 1
    assert len(app.collider_showers[0]["particles"]) >= 6


def test_spawn_shower_heavy_ion():
    app = _make_app()
    app._collider_init("heavy_ion")
    app._collider_spawn_shower(60.0, 20.0, 5.36, "heavy_ion")
    # Heavy ion produces more particles
    assert len(app.collider_showers[0]["particles"]) >= 12


def test_spawn_shower_lepton():
    app = _make_app()
    app._collider_init("lepton")
    app._collider_spawn_shower(60.0, 20.0, 0.209, "lepton")
    # Lepton produces fewer particles
    assert len(app.collider_showers[0]["particles"]) <= 8


def test_spawn_shower_detection():
    """Each shower should produce a detection event."""
    app = _make_app()
    app._collider_init("lhc")
    app._collider_spawn_shower(60.0, 20.0, 13.6, "lhc")
    assert len(app.collider_detections) == 1
    det = app.collider_detections[0]
    assert "name" in det
    assert "symbol" in det
    assert "mass" in det
    assert "energy" in det
    assert "color" in det


def test_spawn_shower_log():
    """Each shower should add a detector log entry."""
    app = _make_app()
    app._collider_init("lhc")
    app._collider_spawn_shower(60.0, 20.0, 13.6, "lhc")
    assert len(app.collider_detector_log) == 1


def test_spawn_shower_log_cap():
    """Log should be capped at 50 entries."""
    app = _make_app()
    app._collider_init("lhc")
    for _ in range(55):
        app._collider_spawn_shower(60.0, 20.0, 13.6, "lhc")
    assert len(app.collider_detector_log) == 50


# ── handle_collider_menu_key ──────────────────────────────────────────────

def test_menu_navigate():
    app = _make_app()
    app._enter_collider_mode()
    app._handle_collider_menu_key(curses.KEY_DOWN)
    assert app.collider_menu_sel == 1
    app._handle_collider_menu_key(curses.KEY_UP)
    assert app.collider_menu_sel == 0


def test_menu_navigate_j_k():
    app = _make_app()
    app._enter_collider_mode()
    app._handle_collider_menu_key(ord('j'))
    assert app.collider_menu_sel == 1
    app._handle_collider_menu_key(ord('k'))
    assert app.collider_menu_sel == 0


def test_menu_wrap():
    app = _make_app()
    app._enter_collider_mode()
    app._handle_collider_menu_key(curses.KEY_UP)
    assert app.collider_menu_sel == len(COLLIDER_PRESETS) - 1


def test_menu_select():
    app = _make_app()
    app._enter_collider_mode()
    app._handle_collider_menu_key(10)
    assert app.collider_running is True
    assert app.collider_menu is False


def test_menu_quit():
    app = _make_app()
    app._enter_collider_mode()
    app._handle_collider_menu_key(27)
    assert app.collider_mode is False


# ── handle_collider_key ───────────────────────────────────────────────────

def test_key_space_toggle():
    app = _make_app()
    app._collider_init("lhc")
    assert app.collider_running is True
    app._handle_collider_key(ord(' '))
    assert app.collider_running is False


def test_key_speed():
    app = _make_app()
    app._collider_init("lhc")
    s = app.collider_speed
    app._handle_collider_key(ord('+'))
    assert app.collider_speed == s + 1
    app._handle_collider_key(ord('-'))
    assert app.collider_speed == s


def test_key_speed_bounds():
    app = _make_app()
    app._collider_init("lhc")
    app.collider_speed = 10
    app._handle_collider_key(ord('+'))
    assert app.collider_speed == 10
    app.collider_speed = 1
    app._handle_collider_key(ord('-'))
    assert app.collider_speed == 1


def test_key_reset():
    app = _make_app()
    app._collider_init("lhc")
    for _ in range(10):
        app._collider_step()
    app._handle_collider_key(ord('r'))
    assert app.collider_generation == 0


def test_key_return_to_menu():
    app = _make_app()
    app._collider_init("lhc")
    app._handle_collider_key(ord('R'))
    assert app.collider_menu is True
    assert app.collider_running is False


def test_key_info():
    app = _make_app()
    app._collider_init("lhc")
    app._handle_collider_key(ord('i'))
    assert app.collider_show_info is True


def test_key_force_collision():
    app = _make_app()
    app._collider_init("lhc")
    app._handle_collider_key(ord('c'))
    assert app.collider_total_collisions == 1
    assert len(app.collider_showers) >= 1
    assert len(app.collider_detections) >= 1


def test_key_quit():
    app = _make_app()
    app._collider_init("lhc")
    app.collider_mode = True
    app._handle_collider_key(27)
    assert app.collider_mode is False


# ── draw (no crash) ──────────────────────────────────────────────────────

def test_draw_menu_no_crash():
    app = _make_app()
    app._enter_collider_mode()
    app._draw_collider_menu(40, 120)


def test_draw_simulation_no_crash():
    app = _make_app()
    app._collider_init("lhc")
    for _ in range(5):
        app._collider_step()
    app._draw_collider(40, 120)


def test_draw_with_info():
    app = _make_app()
    app._collider_init("lhc")
    app.collider_show_info = True
    app._draw_collider(40, 120)


def test_draw_with_showers():
    app = _make_app()
    app._collider_init("lhc")
    app._collider_spawn_shower(60.0, 20.0, 13.6, "lhc")
    app._draw_collider(40, 120)


def test_draw_with_detection_flash():
    app = _make_app()
    app._collider_init("lhc")
    app._collider_spawn_shower(60.0, 20.0, 13.6, "lhc")
    app.collider_detections[-1]["flash"] = 0.8
    app._draw_collider(40, 120)


def test_draw_all_presets():
    for _name, _desc, key in COLLIDER_PRESETS:
        app = _make_app()
        app._collider_init(key)
        for _ in range(3):
            app._collider_step()
        app._draw_collider(40, 120)


# ── constants ─────────────────────────────────────────────────────────────

def test_particles_have_structure():
    for p in _COLLIDER_PARTICLES:
        assert "name" in p
        assert "symbol" in p
        assert "mass" in p
        assert "color" in p
        assert "rare" in p


def test_detector_labels():
    assert len(_COLLIDER_DETECTOR_LABELS) == 4
