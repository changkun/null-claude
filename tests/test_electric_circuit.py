"""Tests for electric_circuit mode."""
from tests.conftest import make_mock_app
from life.modes.electric_circuit import register, CIRCUIT_PRESETS


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.circuit_mode = False
    app.circuit_menu = False
    app.circuit_menu_sel = 0
    app.circuit_running = False
    return app


def test_enter():
    app = _make_app()
    app._enter_circuit_mode()
    assert app.circuit_menu is True


def test_step_no_crash():
    app = _make_app()
    app.circuit_mode = True
    app._circuit_init(0)
    assert app.circuit_mode is True
    for _ in range(10):
        app._circuit_step()


def test_exit_cleanup():
    app = _make_app()
    app._circuit_init(0)
    app._exit_circuit_mode()
    assert app.circuit_mode is False


def test_all_presets_init():
    """Every preset initializes without error and produces a sim dict."""
    for idx in range(len(CIRCUIT_PRESETS)):
        app = _make_app()
        app._circuit_init(idx)
        assert app.circuit_sim is not None
        assert "nodes" in app.circuit_sim or "components" in app.circuit_sim \
            or "step" in app.circuit_sim


def test_step_advances_simulation():
    """Stepping should advance the simulation time/step counter."""
    app = _make_app()
    app._circuit_init(0)  # Simple DC Loop
    app.circuit_running = True
    step_before = app.circuit_sim.get("step", 0)
    app._circuit_step()
    step_after = app.circuit_sim.get("step", 0)
    assert step_after > step_before


def test_dc_loop_has_state_after_stepping():
    """Simple DC loop should have meaningful simulation state after stepping."""
    app = _make_app()
    app._circuit_init(0)  # Simple DC Loop
    app.circuit_running = True
    for _ in range(20):
        app._circuit_step()
    sim = app.circuit_sim
    # The sim dict should have meaningful state after stepping
    assert len(sim) > 3, "Circuit sim should have meaningful state after stepping"
    # Step counter should have advanced
    assert sim.get("step", 0) > 0, "Step counter should advance"
