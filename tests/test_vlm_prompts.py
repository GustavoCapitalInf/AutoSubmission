from vlm import prompts


def test_prompt_contains_the_rules_and_version():
    text = prompts.stage_b_prompt(page_number=1, page_total=3)
    for needle in ("exactly as printed", "null", "YYYY-MM-DD", "positive number", "credit", "debit", "page 1 of 3", "Return only JSON"):
        assert needle in text
    assert "Never compute" in text


def test_hybrid_prompt_includes_parser_context_once():
    text = prompts.stage_b_prompt(parser_context="<table><tr><td>x</td></tr></table>", page_number=2, page_total=2)
    assert text.count("<table>") == 1 and prompts.HYBRID_PREFIX.split("\n")[0] in text


def test_prompt_hash_stable():
    a = prompts.stage_b_prompt(page_number=1, page_total=1)
    assert prompts.prompt_sha256(a) == prompts.prompt_sha256(a) and prompts.PROMPT_VERSION == 2
    manifest = prompts.prompt_manifest()
    assert manifest["stage_b_template_sha256"] == prompts.prompt_sha256(prompts.STAGE_B_PROMPT)
    assert manifest["hybrid_prefix_template_sha256"] == prompts.prompt_sha256(prompts.HYBRID_PREFIX)
    assert "stated_total_credits" in a and "carries its own amount" in a
