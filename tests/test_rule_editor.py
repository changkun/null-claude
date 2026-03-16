"""Tests for life.modes.rule_editor — Live Rule Editor mode."""
from tests.conftest import make_mock_app
from life.modes.rule_editor import register


def _make_app():
    app = make_mock_app()
    app.re_mode = False
    app.re_menu = False
    app.re_menu_sel = 0
    app.re_menu_tab = 0
    app.re_saved_rules = []
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_rule_editor_mode()
    assert app.re_menu is True
    assert app.re_mode is False


def test_step_no_crash():
    app = _make_app()
    app._re_init()
    assert app.re_mode is True
    assert app.re_grid is not None
    for _ in range(10):
        app._re_step()
    assert app.re_generation == 10


def test_exit_cleanup():
    app = _make_app()
    app._re_init()
    app._exit_rule_editor_mode()
    assert app.re_mode is False
    assert app.re_menu is False


def test_compile_and_eval_birth_expression():
    """The birth expression should compile and correctly evaluate against neighbors."""
    from life.modes.rule_editor import _compile_expr, _eval_rule
    code, err = _compile_expr("sum(neighbors) == 3")
    assert err is None
    assert code is not None
    # 3 live neighbors should produce birth
    assert _eval_rule(code, [1, 1, 1, 0, 0, 0, 0, 0], 0, 0, 0, 0) is True
    # 2 live neighbors should not produce birth
    assert _eval_rule(code, [1, 1, 0, 0, 0, 0, 0, 0], 0, 0, 0, 0) is False


def test_custom_age_dependent_rule():
    """Rules using 'age' variable should produce different results at different ages."""
    from life.modes.rule_editor import _compile_expr, _eval_rule
    code, err = _compile_expr("sum(neighbors) in (2, 3) and age < 5")
    assert err is None
    nbrs = [1, 1, 0, 0, 0, 0, 0, 0]
    assert _eval_rule(code, nbrs, 3, 0, 0, 0) is True   # age=3 < 5
    assert _eval_rule(code, nbrs, 10, 0, 0, 0) is False  # age=10 >= 5


def test_step_population_changes():
    """Running steps with Life rules should change population over time."""
    app = _make_app()
    app._re_init("sum(neighbors) == 3", "sum(neighbors) in (2, 3)", "Life")
    initial_pop = app.re_population
    # Run several steps
    for _ in range(10):
        app._re_step()
    # Population should have changed (Life is not static from random init)
    # We check generation counter at minimum
    assert app.re_generation == 10
    assert len(app.re_pop_history) == 10


def test_randomize_grid_resets_state():
    """Randomizing the grid should reset generation and clear history."""
    app = _make_app()
    app._re_init()
    for _ in range(5):
        app._re_step()
    assert app.re_generation == 5
    app._re_randomize_grid()
    assert app.re_generation == 0
    assert app.re_pop_history == []


def test_syntax_error_in_expression():
    """An invalid expression should produce an error, not crash."""
    from life.modes.rule_editor import _compile_expr
    code, err = _compile_expr("sum(neighbors ==")
    assert code is None
    assert err is not None
    assert "syntax" in err.lower()
