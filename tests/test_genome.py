"""Tests for life.modes.genome — Genome Sharing System."""
from tests.conftest import make_mock_app
from life.modes.genome import (
    register, _encode_genome, _decode_genome,
    _should_include_attr, _MODE_ABBREVS, _ABBREV_TO_PREFIX,
)


def _make_app():
    app = make_mock_app()
    # genome needs _any_menu_open
    app._any_menu_open = lambda: False
    register(type(app))
    return app


def test_enter():
    app = _make_app()
    # Genome is a cross-cutting feature, not a mode with enter
    assert hasattr(app, '_genome_handle_key')
    assert hasattr(app, '_genome_capture')


def test_step_no_crash():
    app = _make_app()
    # Test encode/decode round-trip
    config = {"_mode": "gol", "speed_idx": 2, "rule_b": [3], "rule_s": [2, 3]}
    code = _encode_genome("gol", config)
    assert code.startswith("GOL-")
    prefix, decoded = _decode_genome(code)
    assert prefix == "gol"
    assert decoded["_mode"] == "gol"
    # Run 10 round-trips
    for i in range(10):
        config["speed_idx"] = i % 8
        code = _encode_genome("gol", config)
        p, d = _decode_genome(code)
        assert d is not None


def test_exit_cleanup():
    app = _make_app()
    # No special exit for genome — just verify decode of bad input
    prefix, config = _decode_genome("INVALID")
    assert prefix is None
    assert config is None


def test_encode_decode_roundtrip_all_modes():
    """Encode/decode round-trip preserves data for multiple mode abbreviations."""
    for prefix, abbrev in [("rd", "RD"), ("wave", "WAV"), ("fire", "FIR")]:
        config = {"_mode": prefix, "speed_idx": 3, "some_param": 42.0}
        code = _encode_genome(prefix, config)
        assert code.startswith(abbrev + "-")
        p, d = _decode_genome(code)
        assert p == prefix
        assert d["speed_idx"] == 3
        assert d["some_param"] == 42.0


def test_should_include_attr_filters():
    """_should_include_attr correctly accepts config and rejects state attrs."""
    # Config attr should be included
    assert _should_include_attr("gol", "gol_wrap") is True
    # State suffixes should be excluded
    assert _should_include_attr("gol", "gol_grid") is False
    assert _should_include_attr("gol", "gol_running") is False
    assert _should_include_attr("gol", "gol_mode") is False
    # Wrong prefix should be excluded
    assert _should_include_attr("rd", "gol_wrap") is False


def test_abbrev_reverse_mapping_consistent():
    """Every abbreviation maps back to the correct prefix."""
    for prefix, abbrev in _MODE_ABBREVS.items():
        assert _ABBREV_TO_PREFIX[abbrev] == prefix
