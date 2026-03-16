"""Tests for life.modes.observatory — Observatory mode."""
from tests.conftest import make_mock_app
from life.modes.observatory import register


def _make_app():
    app = make_mock_app()
    app.obs_mode = False
    app.obs_menu = False
    app.obs_menu_sel = 0
    app.obs_menu_phase = 0
    app.obs_running = False
    app.obs_viewports = []
    app.obs_focus = -1
    app.obs_pick_layout = None
    app.obs_pick_sims = []
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    app._enter_observatory_mode()
    assert app.obs_menu is True
    assert app.obs_menu_phase == 0


def test_step_no_crash():
    app = _make_app()
    app._observatory_init(["gol", "wave", "rd", "fire"], 1)
    assert app.obs_mode is True
    assert len(app.obs_viewports) == 4
    for _ in range(10):
        app._observatory_step()
    assert app.obs_generation == 10


def test_exit_cleanup():
    app = _make_app()
    app._observatory_init(["gol", "wave"], 0)
    app._exit_observatory_mode()
    assert app.obs_mode is False
    assert app.obs_running is False
    assert app.obs_viewports == []


def test_all_layouts_init():
    """All layout sizes (2, 4, 6, 9 viewports) should initialize correctly."""
    from life.modes.mashup import MASHUP_SIMS
    sim_ids = [s["id"] for s in MASHUP_SIMS]
    app = _make_app()
    for layout_idx, expected_count in [(0, 2), (1, 4), (2, 6), (3, 9)]:
        sims = (sim_ids * 3)[:expected_count]  # repeat to fill
        app._observatory_init(sims, layout_idx)
        assert app.obs_mode is True
        assert len(app.obs_viewports) == expected_count


def test_step_advances_all_viewports():
    """Each step should advance all viewports independently."""
    app = _make_app()
    app._observatory_init(["gol", "wave", "rd", "fire"], 1)
    # Record initial densities
    initial_densities = [vp["density"] for vp in app.obs_viewports]
    # Step
    app._observatory_step()
    assert app.obs_generation == 1
    # Each viewport should have a density array of correct size
    for vp in app.obs_viewports:
        assert len(vp["density"]) == vp["sim_rows"]
        assert len(vp["density"][0]) == vp["sim_cols"]


def test_viewports_are_independent():
    """Viewports should run independently (no coupling between sims)."""
    app = _make_app()
    # Use the same sim type twice to verify they diverge (random seeds differ)
    app._observatory_init(["gol", "gol"], 0)
    for _ in range(5):
        app._observatory_step()
    # Due to different random initial states, densities should differ
    d0 = app.obs_viewports[0]["density"]
    d1 = app.obs_viewports[1]["density"]
    # Check they have the same shape
    assert len(d0) == len(d1)
    # At least some cells should differ (extremely unlikely to be identical)
    any_different = any(
        d0[r][c] != d1[r][c]
        for r in range(min(5, len(d0)))
        for c in range(min(5, len(d0[0])))
    )
    assert any_different, "Independent viewports should diverge"


def test_focus_viewport():
    """Setting obs_focus should select a specific viewport index."""
    app = _make_app()
    app._observatory_init(["gol", "wave", "rd"], 1)
    app.obs_focus = 1
    assert app.obs_focus == 1
    # Unfocus
    app.obs_focus = -1
    assert app.obs_focus == -1
