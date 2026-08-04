

def test_parse_probability_response_basic():
    from app.services.ai.prompts import parse_probability_response

    parsed = parse_probability_response('{"probability_pct": 72, "reasoning": "because"}')
    assert parsed == {"probability_pct": 72, "reasoning": "because"}


def test_parse_probability_accepts_fraction():
    """Models answer 0.62 instead of 62 often enough that treating it as
    62% beats rejecting the whole response.
    """
    from app.services.ai.prompts import parse_probability_response

    assert parse_probability_response('{"probability_pct": 0.62, "reasoning": "x"}')["probability_pct"] == 62


def test_parse_probability_clamps_certainty():
    """Never surface 0% or 100% - an LLM estimate is not that precise."""
    from app.services.ai.prompts import parse_probability_response

    assert parse_probability_response('{"probability_pct": 100, "reasoning": "x"}')["probability_pct"] == 99
    assert parse_probability_response('{"probability_pct": 0, "reasoning": "x"}')["probability_pct"] == 1


def test_parse_probability_handles_code_fence_and_prose():
    from app.services.ai.prompts import parse_probability_response

    raw = 'Sure!\n```json\n{"probability_pct": 40, "reasoning": "y"}\n```'
    assert parse_probability_response(raw)["probability_pct"] == 40


def test_parse_probability_rejects_garbage():
    import pytest

    from app.services.ai.prompts import parse_probability_response

    with pytest.raises(ValueError):
        parse_probability_response("no json here")
