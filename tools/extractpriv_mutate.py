"""Mutation harness for the LLM-branch refusal (W3 §EXTRACTPRIV §XP8).

Reintroduces the defect eight ways and proves a test dies for each. Committed
so the kill table in the log is re-derivable rather than asserted:

    python tools/extractpriv_mutate.py .

The target file is restored in a `finally`, and the harness prints the restore
so a run that dies mid-way is visible as one that did not.

M1-M4 are the author's. A/B/C/C2 come from the adversarial review; B is quoted
from the reviewer's report verbatim, and A, C and C2 are this harness's
rendering of the three other properties the review verified by hand (no helper
frame in the traceback; one `.text` reader, which the guard's walk must see
outside a `FunctionDef` too).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

TESTS = "tests/test_extraction_refusal_is_private.py"

#: label -> (anchor, replacement). Applied one at a time to a pristine copy.
MUTATIONS: dict[str, tuple[str, str]] = {
    # --- the author's four ---------------------------------------------------
    # M1 — the card's defect, restored verbatim.
    "M1_the_original_fstring": (
        "        raise _extraction_refusal(resp)",
        '        raise RuntimeError(f"extraction did not return a Statement: {resp.text[:300]!r}")',
    ),
    # M2 — the vocabulary check dropped: the finish reason is echoed as found.
    "M2_stop_reason_unchecked": (
        "        if isinstance(name, str) and name in _STOP_REASONS:\n"
        "            return _CANONICAL_STOP_REASON[name]",
        "        if name is not None:\n            return str(name)",
    ),
    # M3 — a response LENGTH added to the template, the field this card
    # deliberately did not take (see §XP2).
    "M3_length_in_the_message": (
        "    return RuntimeError(_REFUSAL.format(_stop_reason(response), _response_state(response)))",
        "    return RuntimeError(\n"
        '        (_REFUSAL[:-1] + ", chars={})").format(\n'
        "            _stop_reason(response), _response_state(response),\n"
        "            len(response.text or '')))",
    ),
    # M4 — the chain restored: raise from inside a handler that caught a
    # quoting exception. `from None` clears __cause__ and leaves __context__.
    "M4_chained_refusal": (
        "        raise _extraction_refusal(resp)",
        "        try:\n"
        "            raise ValueError(resp.text[:300])\n"
        "        except ValueError:\n"
        "            raise _extraction_refusal(resp) from None",
    ),
    # --- the review's four ---------------------------------------------------
    # A — the constructor RAISES instead of returning, putting its own frame
    #     (which holds `response`) back into the traceback.
    "A_helper_frame_in_traceback": (
        "        raise _extraction_refusal(resp)",
        "        _raise_extraction_refusal(resp)",
    ),
    # B — reviewer's verbatim survivor before this round: the response is
    #     attached to the exception, where `str(exc)` cannot see it and
    #     `repr`/pickle/structured logging can.
    "B_response_attached_to_the_exception": (
        "    return RuntimeError(_REFUSAL.format(_stop_reason(response), _response_state(response)))",
        "    err = RuntimeError(_REFUSAL.format(_stop_reason(response), _response_state(response)))\n"
        "    err.response = response\n"
        "    return err",
    ),
    # C — a SECOND reader of the body, at module level, where the guard's old
    #     `ast.FunctionDef` walk could not see it.
    "C_second_text_reader_module_level": (
        '_REFUSAL = "extraction did not return a Statement (stop_reason={}, response={})"',
        '_REFUSAL = "extraction did not return a Statement (stop_reason={}, response={})"\n'
        "_LAST_BODY = None\n"
        "def _remember(resp):\n"
        "    global _LAST_BODY\n"
        "    _LAST_BODY = resp.text\n",
    ),
    # C2 — the same, in a class body.
    "C2_second_text_reader_class_body": (
        '_REFUSAL = "extraction did not return a Statement (stop_reason={}, response={})"',
        '_REFUSAL = "extraction did not return a Statement (stop_reason={}, response={})"\n'
        "class _Peek:\n"
        "    @staticmethod\n"
        "    def preview(resp):\n"
        "        return resp.text[:80]\n",
    ),
}

#: A mutant that needs a helper defined alongside it.
PRELUDE = {
    "A_helper_frame_in_traceback": (
        "def extract_statement(",
        "def _raise_extraction_refusal(response):\n"
        "    raise _extraction_refusal(response)\n"
        "\n"
        "\n"
        "def extract_statement(",
    ),
}


def run(root: pathlib.Path, target: pathlib.Path, label: str, source: str) -> bool:
    target.write_text(source, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q", "--no-header",
         "-p", "no:cacheprovider"],
        cwd=root, capture_output=True, text=True,
    )
    failures = [ln for ln in proc.stdout.splitlines() if ln.startswith(("FAILED", "ERROR"))]
    tally = [ln for ln in proc.stdout.splitlines() if " passed" in ln or " failed" in ln]
    verdict = "KILLED" if proc.returncode != 0 else "*** SURVIVED ***"
    print(f"=== {label}: pytest exit {proc.returncode} -> {verdict}")
    print(f"    {tally[-1] if tally else proc.stdout.splitlines()[-1:]}")
    for line in failures:
        print(f"    {line}")
    return proc.returncode != 0


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    target = root / "analysis" / "extract.py"
    original = target.read_text(encoding="utf-8")
    killed = 0
    try:
        for label, (anchor, replacement) in MUTATIONS.items():
            source = original
            if label in PRELUDE:
                pre_anchor, pre_replacement = PRELUDE[label]
                assert pre_anchor in source, f"{label}: prelude anchor not found"
                source = source.replace(pre_anchor, pre_replacement, 1)
            assert anchor in source, f"{label}: anchor not found"
            killed += run(root, target, label, source.replace(anchor, replacement))
    finally:
        target.write_text(original, encoding="utf-8")
        print("\nrestored analysis/extract.py")
    print(f"{len(MUTATIONS)} mutants, {killed} KILLED, {len(MUTATIONS) - killed} survivors")
    return 0 if killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
