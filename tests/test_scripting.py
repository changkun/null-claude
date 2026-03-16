"""Tests for life.modes.scripting — Scripting & Choreography mode."""
from tests.conftest import make_mock_app
from life.modes.scripting import register, _parse_script, _parse_duration


def _make_app():
    app = make_mock_app()
    app.script_mode = False
    app.script_menu = False
    app.script_menu_sel = 0
    app.script_menu_phase = 0
    app.script_running = False
    app.script_paused = False
    app.script_sim_state = None
    app.script_prev_density = None
    app.script_commands = []
    app.script_active_sweeps = []
    app.script_show_source = False
    # Post-processing attrs needed by scripting
    app.pp_active = set()
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_scripting_mode()
    assert app.script_menu is True
    assert app.script_show_source is False


def test_step_no_crash():
    app = _make_app()
    script = """\
mode game_of_life
wait 0.01s
mode wave
wait 0.01s
"""
    result = app._script_init(script, "Test Script")
    assert result is True
    assert app.script_mode is True
    for _ in range(10):
        app._script_step()
    # Should have advanced through the script
    assert app.script_generation >= 1


def test_exit_cleanup():
    app = _make_app()
    script = "mode gol\nwait 1s\n"
    app._script_init(script, "Test")
    app._exit_scripting_mode()
    assert app.script_mode is False
    assert app.script_running is False
    assert app.script_commands == []
    assert app.pp_active == set()


def test_parse_duration():
    """_parse_duration handles seconds, milliseconds, and bare numbers."""
    assert _parse_duration("5s") == 5.0
    assert _parse_duration("2.5s") == 2.5
    assert _parse_duration("500ms") == 0.5
    assert _parse_duration("3") == 3.0


def test_parse_script_all_commands():
    """Parser handles every command type without error."""
    script = """\
# comment line
mode game_of_life
wait 2s
effect bloom on
effect scanlines off
topology torus
set speed 3
sweep speed 1 7 over 4s
transition crossfade 1.5s
speed 2x
color 3
label Hello World
loop
"""
    commands = _parse_script(script)
    types = [c["cmd"] for c in commands]
    assert "mode" in types
    assert "wait" in types
    assert "effect" in types
    assert "topology" in types
    assert "set" in types
    assert "sweep" in types
    assert "transition" in types
    assert "speed" in types
    assert "color" in types
    assert "label" in types
    assert "loop" in types


def test_parse_script_error_on_unknown():
    """Parser raises ValueError on unknown commands."""
    import pytest
    with pytest.raises(ValueError, match="unknown command"):
        _parse_script("badcommand arg1")


def test_effect_toggle_via_script():
    """Running a script with effect commands modifies pp_active."""
    app = _make_app()
    script = """\
mode gol
effect bloom on
wait 0.01s
"""
    app._script_init(script, "FX test")
    # After init, immediate commands execute up to the wait
    assert "bloom" in app.pp_active


def test_loop_restarts_script():
    """A script with 'loop' at the end restarts from the beginning."""
    app = _make_app()
    script = """\
mode gol
wait 0.001s
loop
"""
    app._script_init(script, "Loop test")
    # Run enough steps to reach loop
    for _ in range(200):
        app._script_step()
    # Script should still be running (loop prevents finish)
    assert app.script_running is True
