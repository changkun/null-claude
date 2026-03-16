"""Tests for stock_market mode."""
from tests.conftest import make_mock_app
from life.modes.stock_market import register, Agent


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.mkt_mode = False
    app.mkt_menu = False
    app.mkt_menu_sel = 0
    app.mkt_running = False
    app.mkt_agents = []
    app.mkt_price_history = []
    app.mkt_bids = []
    app.mkt_asks = []
    app.mkt_steps_per_frame = 1
    return app


def test_enter():
    app = _make_app()
    app._enter_mkt_mode()
    assert app.mkt_menu is True


def test_step_no_crash():
    app = _make_app()
    app.mkt_mode = True
    app._mkt_init(0)
    assert app.mkt_mode is True
    for _ in range(10):
        app._mkt_step()


def test_exit_cleanup():
    app = _make_app()
    app._mkt_init(0)
    app._exit_mkt_mode()
    assert app.mkt_mode is False
    assert app.mkt_agents == []


def test_init_sets_steps_per_frame():
    """_mkt_init must set mkt_steps_per_frame (was a missing init bug)."""
    app = _make_app()
    app._mkt_init(0)
    assert hasattr(app, "mkt_steps_per_frame")
    assert app.mkt_steps_per_frame == 1


def test_price_history_grows():
    """Price history should grow by one entry per tick."""
    app = _make_app()
    app._mkt_init(0)
    initial_len = len(app.mkt_price_history)
    app._mkt_step()
    assert len(app.mkt_price_history) == initial_len + 1


def test_agent_types_present():
    """Init should create all agent types from the preset."""
    app = _make_app()
    app._mkt_init(0)  # Bull Run: 60 fundamental, 30 chartist, 20 noise, 2 market_maker
    kinds = {a.kind for a in app.mkt_agents}
    assert "fundamental" in kinds
    assert "chartist" in kinds
    assert "noise" in kinds
    assert "market_maker" in kinds


def test_price_stays_positive():
    """Price should never go negative after many steps."""
    app = _make_app()
    app._mkt_init(0)
    for _ in range(100):
        app._mkt_step()
    assert app.mkt_price > 0
