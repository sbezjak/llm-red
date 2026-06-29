from llm_red.severity import Severity, owasp_ids


def test_tiers_map_to_owasp_ids():
    assert owasp_ids(Severity.CRITICAL) == ["LLM07", "LLM02"]
    assert owasp_ids(Severity.HIGH) == ["LLM01"]
    assert owasp_ids(Severity.MEDIUM) == []


def test_every_tier_has_a_mapping():
    for tier in Severity:
        assert isinstance(owasp_ids(tier), list)
