import pytest

from apps.api.engines import ENGINES, get_engine


def test_required_pilot_engines_are_registered() -> None:
    assert set(ENGINES) == {"football", "geo", "music"}
    assert all(len(engine.visual_types) >= 4 for engine in ENGINES.values())


def test_unknown_engine_is_explicit_error() -> None:
    with pytest.raises(ValueError, match="Unknown engine"):
        get_engine("unknown")
