"""Gate v5 (CTRL wave): the period year is corroborated between the model and the rules."""
from dataclasses import replace

from vlm.metadata import EMPTY_META
from vlm.runner import _corroborate


def test_period_year_disagreement_between_model_and_rules_is_a_disagreement():
    model = replace(EMPTY_META, period_start="2029-04-01", period_end="2029-04-30")
    rules = replace(EMPTY_META, period_start="2031-04-01", period_end="2031-04-30")
    out = _corroborate(model, rules)
    assert out["fields"]["period_year"] == "disagree" and out["summary"] == "disagreement"
    assert _corroborate(model, replace(EMPTY_META, period_end="2029-04-30"))["fields"]["period_year"] == "agree"
    assert _corroborate(model, EMPTY_META)["fields"]["period_year"] == "model_only"
    assert _corroborate(EMPTY_META, rules)["fields"]["period_year"] == "rules_only"
    assert _corroborate(EMPTY_META, EMPTY_META)["fields"]["period_year"] == "absent"
