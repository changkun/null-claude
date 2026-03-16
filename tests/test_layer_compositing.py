"""Tests for life.modes.layer_compositing — Layer Compositing mode."""
from tests.conftest import make_mock_app
from life.modes.layer_compositing import (
    register, COMP_PRESETS, BLEND_MODES,
    _blend_add, _blend_multiply, _blend_xor, _blend_mask, _blend_screen,
)


def _make_app():
    app = make_mock_app()
    app.comp_mode = False
    app.comp_menu = False
    app.comp_menu_sel = 0
    app.comp_menu_phase = 0
    app.comp_custom_layers = []
    app.comp_running = False
    app.comp_layers = []
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_comp_mode()
    assert app.comp_menu is True
    assert app.comp_menu_phase == 0


def test_step_no_crash():
    app = _make_app()
    layer_defs = [
        {"sim": "gol", "blend": "add", "opacity": 1.0, "tick_mult": 1},
        {"sim": "wave", "blend": "xor", "opacity": 0.8, "tick_mult": 1},
    ]
    app._comp_init(layer_defs)
    assert app.comp_mode is True
    assert len(app.comp_layers) == 2
    for _ in range(10):
        app._comp_step()
    assert app.comp_generation == 10


def test_exit_cleanup():
    app = _make_app()
    layer_defs = [
        {"sim": "gol", "blend": "add", "opacity": 1.0, "tick_mult": 1},
        {"sim": "rd", "blend": "add", "opacity": 0.5, "tick_mult": 2},
    ]
    app._comp_init(layer_defs)
    app._exit_comp_mode()
    assert app.comp_mode is False
    assert app.comp_layers == []


def test_blend_functions():
    """Verify blend function math for boundary values."""
    # Add
    assert _blend_add(0.5, 0.4) == 0.9
    assert _blend_add(0.7, 0.5) == 1.0  # clamped to 1.0
    # Multiply
    assert _blend_multiply(0.5, 0.5) == 0.25
    assert _blend_multiply(1.0, 0.0) == 0.0
    # XOR (abs diff)
    assert _blend_xor(1.0, 0.0) == 1.0
    assert _blend_xor(0.5, 0.5) == 0.0
    # Mask
    assert _blend_mask(0.8, 0.2) == 0.8  # b > 0.15
    assert _blend_mask(0.8, 0.1) == 0.0  # b <= 0.15
    # Screen
    assert abs(_blend_screen(0.5, 0.5) - 0.75) < 1e-9


def test_tick_mult_skips_steps():
    """Layers with tick_mult > 1 only step on aligned generations."""
    app = _make_app()
    layer_defs = [
        {"sim": "gol", "blend": "add", "opacity": 1.0, "tick_mult": 1},
        {"sim": "wave", "blend": "add", "opacity": 0.8, "tick_mult": 3},
    ]
    app._comp_init(layer_defs)
    # After 3 steps: layer 0 stepped 3 times, layer 1 stepped 1 time (gen 0 only)
    for _ in range(3):
        app._comp_step()
    assert app.comp_generation == 3


def test_composite_produces_grid():
    """_comp_composite returns grids of correct dimensions."""
    app = _make_app()
    layer_defs = [
        {"sim": "gol", "blend": "add", "opacity": 1.0, "tick_mult": 1},
        {"sim": "wave", "blend": "screen", "opacity": 0.7, "tick_mult": 1},
    ]
    app._comp_init(layer_defs)
    result, dominant = app._comp_composite()
    assert len(result) == app.comp_rows
    assert len(result[0]) == app.comp_cols
    assert len(dominant) == app.comp_rows
    # Values should be in [0, 1]
    for row in result:
        for v in row:
            assert 0.0 <= v <= 1.0


def test_all_presets_init():
    """All preset configurations can be initialized."""
    for preset in COMP_PRESETS:
        app = _make_app()
        app._comp_init(preset["layers"])
        assert app.comp_mode is True
        assert len(app.comp_layers) == len(preset["layers"])
