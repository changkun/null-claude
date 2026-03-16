"""Tests for life.modes.cinematic_demo — Cinematic Demo Reel mode."""
from tests.conftest import make_mock_app
from life.modes.cinematic_demo import register, DEMO_ACTS, DEMO_PLAYLISTS


def _make_app():
    app = make_mock_app()
    app.cinem_mode = False
    app.cinem_menu = False
    app.cinem_menu_sel = 0
    app.cinem_running = False
    app.cinem_sim_state = None
    app.cinem_prev_density = None
    app.cinem_paused = False
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_cinematic_demo_mode()
    assert app.cinem_menu is True


def test_step_no_crash():
    app = _make_app()
    app._cinematic_init(0)  # "The Grand Tour"
    assert app.cinem_mode is True
    assert app.cinem_running is True
    for _ in range(10):
        app._cinematic_step()
    assert app.cinem_generation >= 10


def test_exit_cleanup():
    app = _make_app()
    app._cinematic_init(0)
    app._exit_cinematic_demo_mode()
    assert app.cinem_mode is False
    assert app.cinem_running is False
    assert app.cinem_sim_state is None


def test_all_playlists_launch():
    """Each playlist index can launch without error."""
    for idx in range(len(DEMO_PLAYLISTS)):
        app = _make_app()
        app._cinematic_init(idx)
        assert app.cinem_mode is True
        assert app.cinem_running is True
        assert len(app.cinem_act_sequence) > 0
        # Run a few steps
        for _ in range(3):
            app._cinematic_step()
        assert app.cinem_generation >= 3


def test_advance_cycles_acts():
    """Advancing past the last act wraps around when looping is enabled."""
    app = _make_app()
    # "Fluid Dreams" playlist: acts=[1,2,7], loop=True
    app._cinematic_init(1)
    n_acts = len(app.cinem_act_sequence)
    assert n_acts == 3
    # Force advance past all acts
    for _ in range(n_acts + 1):
        app._cinematic_advance()
    # Should have looped back
    assert app.cinem_running is True
    assert app.cinem_act_idx < n_acts


def test_pause_prevents_stepping():
    """When paused, _cinematic_step does not advance generation."""
    app = _make_app()
    app._cinematic_init(0)
    app.cinem_paused = True
    gen_before = app.cinem_generation
    for _ in range(5):
        app._cinematic_step()
    assert app.cinem_generation == gen_before


def test_crossfade_decays():
    """Crossfade value decays toward zero during stepping."""
    app = _make_app()
    app._cinematic_init(0)
    assert app.cinem_crossfade == 1.0
    for _ in range(50):
        app._cinematic_step()
    assert app.cinem_crossfade < 1.0
