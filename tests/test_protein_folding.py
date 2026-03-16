"""Tests for protein_folding mode."""
from tests.conftest import make_mock_app
from life.modes.protein_folding import register


def _make_app():
    app = make_mock_app()
    register(type(app))
    app.protfold_mode = False
    app.protfold_menu = False
    app.protfold_menu_sel = 0
    app.protfold_running = False
    return app


def test_enter():
    app = _make_app()
    app._enter_protein_folding_mode()
    assert app.protfold_menu is True


def test_step_no_crash():
    app = _make_app()
    app.protfold_mode = True
    app._protfold_init(0)
    assert app.protfold_mode is True
    for _ in range(10):
        app._protfold_step()


def test_exit_cleanup():
    app = _make_app()
    app._protfold_init(0)
    app._exit_protein_folding_mode()
    assert app.protfold_mode is False


def test_all_presets_init():
    """All 6 presets should initialize without error."""
    for idx in range(6):
        app = _make_app()
        app._protfold_init(idx)
        for _ in range(3):
            app._protfold_step()


def test_history_recording():
    """Metrics history should accumulate entries."""
    app = _make_app()
    app._protfold_init(0)
    for _ in range(10):
        app._protfold_step()
    hist = app.protfold_history
    assert len(hist['native_contacts']) == 10
    assert len(hist['free_energy']) == 10
    assert len(hist['temperature']) == 10


def test_proteins_exist_after_init():
    """Proteins should be created after init."""
    app = _make_app()
    app._protfold_init(0)
    assert len(app.protfold_proteins) > 0


def test_prion_preset_has_misfolded():
    """Prion preset should seed a misfolded protein."""
    app = _make_app()
    app._protfold_init(1)  # Prion Propagation
    misfolded = sum(1 for p in app.protfold_proteins if p.state == 'misfolded')
    assert misfolded >= 1, "Prion preset should have at least one misfolded seed"


def test_amyloid_preset_has_fibril():
    """Amyloid preset should seed a fibril."""
    app = _make_app()
    app._protfold_init(4)  # Amyloid Cascade
    assert len(app.protfold_fibrils) >= 1, "Amyloid preset should seed a fibril"


def test_chaperones_exist():
    """Normal preset should have chaperones."""
    app = _make_app()
    app._protfold_init(0)
    assert len(app.protfold_chaperones) > 0
