"""Tests for quantum_circuit mode."""
import math
from tests.conftest import make_mock_app
from life.modes.quantum_circuit import (
    register, QCIRC_PRESETS, _apply_gate, _measure_probabilities,
)


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.qcirc_mode = False
    app.qcirc_menu = False
    app.qcirc_menu_sel = 0
    app.qcirc_running = False
    app.qcirc_state = None
    return app


def test_enter():
    app = _make_app()
    app._enter_qcirc_mode()
    assert app.qcirc_menu is True


def test_step_no_crash():
    app = _make_app()
    app.qcirc_mode = True
    app._qcirc_init(0)  # Bell state
    assert app.qcirc_state is not None
    for _ in range(10):
        app._qcirc_step()


def test_exit_cleanup():
    app = _make_app()
    app._qcirc_init(0)
    app._exit_qcirc_mode()
    assert app.qcirc_mode is False
    assert app.qcirc_state is None


def test_all_presets_init():
    """Every preset initializes without error."""
    for idx in range(len(QCIRC_PRESETS)):
        app = _make_app()
        app._qcirc_init(idx)
        assert app.qcirc_state is not None
        n = 1 << app.qcirc_n_qubits
        assert len(app.qcirc_state) == n


def test_bell_state_produces_entanglement():
    """H then CNOT on |00> should give (|00>+|11>)/sqrt(2)."""
    n_qubits = 2
    sv = [complex(1), complex(0), complex(0), complex(0)]
    # Apply H on qubit 0
    sv = _apply_gate(sv, n_qubits, "H", [0], [])
    # Apply CNOT on qubits 0,1
    sv = _apply_gate(sv, n_qubits, "CNOT", [0, 1], [])
    probs = _measure_probabilities(sv, n_qubits)
    # Should have |00> and |11> each at ~50%
    prob_dict = dict(probs)
    assert abs(prob_dict.get("00", 0) - 0.5) < 0.01
    assert abs(prob_dict.get("11", 0) - 0.5) < 0.01
    assert prob_dict.get("01", 0) < 0.01
    assert prob_dict.get("10", 0) < 0.01


def test_x_gate_flips_qubit():
    """X gate on |0> should give |1>."""
    sv = [complex(1), complex(0)]
    sv = _apply_gate(sv, 1, "X", [0], [])
    assert abs(sv[0]) < 1e-10
    assert abs(abs(sv[1]) - 1.0) < 1e-10


def test_hadamard_creates_superposition():
    """H gate on |0> should give equal superposition."""
    sv = [complex(1), complex(0)]
    sv = _apply_gate(sv, 1, "H", [0], [])
    p0 = abs(sv[0]) ** 2
    p1 = abs(sv[1]) ** 2
    assert abs(p0 - 0.5) < 1e-10
    assert abs(p1 - 0.5) < 1e-10


def test_measure_shots_accumulates():
    """Running measurement shots should accumulate histogram entries."""
    app = _make_app()
    app._qcirc_init(0)  # Bell state
    # Run all gates
    while app.qcirc_gate_idx < len(app.qcirc_gates):
        app._qcirc_step()
    app._qcirc_measure_shots(50)
    assert app.qcirc_total_shots == 50
    assert sum(app.qcirc_histogram.values()) == 50
