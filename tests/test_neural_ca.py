"""Tests for neural_ca mode."""
from tests.conftest import make_mock_app
from life.modes.neural_ca import (
    register, _make_target, _seed_state, _compute_loss,
    _init_weights_flat, _forward, _param_count,
    _NCA_CHANNELS, _PRESET_NAMES,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    # NCA needs these attributes
    app.nca_mode = False
    app.nca_menu = False
    app.nca_menu_sel = 0
    app.nca_running = False
    app.nca_training = False
    app.nca_state = None
    app.nca_params = None
    app.nca_target = None
    app.nca_loss_history = []
    app.nca_custom_target = None
    app.nca_grid_h = 12
    app.nca_grid_w = 16
    app.nca_grow_steps = 20
    app.nca_es_pop = 8
    app.nca_es_lr = 0.03
    app.nca_es_sigma = 0.02
    app.nca_target_idx = 0
    app.nca_view = 0
    app.nca_grid_h_actual = 12
    app.nca_grid_w_actual = 16
    app.nca_train_gen = 0
    app.nca_best_loss = float("inf")
    app.nca_best_params = None
    app.nca_sim_step = 0
    app.nca_phase = "idle"
    app.nca_drawing = False
    app.nca_draw_val = 1
    app.colors_enabled = False
    return app


def test_enter():
    app = _make_app()
    app._enter_nca_mode()
    assert app.nca_menu is True
    assert app.nca_mode is False


def test_step_no_crash():
    app = _make_app()
    app.nca_mode = True
    app._nca_init()
    assert app.nca_mode is True
    assert app.nca_state is not None
    # Run in inference mode (not training, too slow)
    app.nca_running = True
    for _ in range(10):
        app._nca_step()


def test_exit_cleanup():
    app = _make_app()
    app.nca_mode = True
    app._nca_init()
    app._exit_nca_mode()
    assert app.nca_mode is False
    assert app.nca_state is None


def test_all_target_presets_generate():
    """Every preset target pattern produces a grid of correct dimensions."""
    h, w = 16, 20
    for name in _PRESET_NAMES:
        if name == "custom":
            continue
        target = _make_target(name, h, w)
        assert len(target) == h
        assert len(target[0]) == w
        # Should have some non-zero cells
        total = sum(target[r][c] for r in range(h) for c in range(w))
        assert total > 0, f"Target '{name}' is empty"


def test_seed_state_has_center_alive():
    """Seed state has alive cells near the center."""
    h, w = 12, 16
    state = _seed_state(h, w)
    assert len(state) == h
    assert len(state[0]) == w
    assert len(state[0][0]) == _NCA_CHANNELS
    # Center cell should be alive
    cy, cx = h // 2, w // 2
    assert state[cy][cx][0] > 0.0


def test_forward_pass_changes_state():
    """A forward pass modifies the state (not identical to input)."""
    h, w = 8, 8
    state = _seed_state(h, w)
    params = _init_weights_flat()
    new_state = _forward(state, params, h, w, stochastic_rate=1.0)
    # At least some cells should differ
    diffs = 0
    for r in range(h):
        for c in range(w):
            for ch in range(_NCA_CHANNELS):
                if abs(new_state[r][c][ch] - state[r][c][ch]) > 1e-10:
                    diffs += 1
    assert diffs > 0


def test_compute_loss_zero_for_matching():
    """Loss is zero when state alive channel matches target exactly."""
    h, w = 4, 4
    target = [[1.0] * w for _ in range(h)]
    state = [[[1.0] + [0.0] * (_NCA_CHANNELS - 1) for _ in range(w)] for _ in range(h)]
    loss = _compute_loss(state, target, h, w)
    assert abs(loss) < 1e-10


def test_param_count():
    """Parameter count matches expected formula."""
    expected = 9 * 8 + 8 + 8 * 3 + 3  # PERCEPTION_DIM*HIDDEN + HIDDEN + HIDDEN*UPDATE + UPDATE
    assert _param_count() == expected
