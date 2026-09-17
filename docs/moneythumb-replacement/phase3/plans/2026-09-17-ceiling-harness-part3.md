# Phase 3 Ceiling Experiment — Offline Harness Implementation Plan (part 3 of 4)

> Continues parts 1–2 (header, Global Constraints, File Structure apply verbatim). Tasks 10–13: the deterministic gate, reader truth and row matching, Stage B prompts, proposals → rows.

---

### Task 10: The deterministic gate (reader's reconcile + date, duplicate and direction checks)

**Files:**
- Create: `vlm/gate.py`
- Test: `tests/test_vlm_gate.py`

**Interfaces:**
- Consumes: `analysis.schema.Statement`, `analysis.schema.Transaction`, `analysis.reconcile.reconcile(stmt) -> ReconResult` (`ok`, `issues`, `continuity_breaks`, `computed_ending`, `sum_delta`), `vlm.assemble.CandidateRow`, `vlm.metadata.AccountMeta`.
- Produces: `GATE_VERSION = 1`, `REASONS` (closed tuple), `GateVerdict` dataclass (`admitted: bool, reasons: tuple[str, ...], row_count: int, admitted_rows: tuple[CandidateRow, ...], computed_ending: Decimal | None, continuity_breaks: int, chain_derived_directions: int, checks: dict`), `resolve_directions(rows, beginning) -> tuple[list[CandidateRow], int]` (fills `unknown` directions from the balance chain, flagged `direction_source="chain"`), `gate(rows, meta, *, tolerance=Decimal("0.01")) -> GateVerdict`, `statement_from(rows, meta) -> Statement`.

Rules (all must pass; never partial admission):
1. `no_rows` if no rows; `proposal_invalid` if any row has a non-positive amount.
2. `missing_beginning_balance` / `missing_ending_balance` unless derivable: beginning = first row balance ∓ first amount when the first row has a balance and a known direction; ending = last row balance. Derivations are recorded in `checks["derived"]`.
3. `direction_unknown` if any direction is still unknown after chain resolution (chain resolution needs the previous balance and this row's balance; sign = balance − previous).
4. `date_unparsed` if any row's date is None; `date_out_of_period` if a period is known and a date falls more than 5 days outside it; `date_not_monotonic` if dates decrease (same day allowed) — evaluated in printed order.
5. `duplicate_row` if two rows share (date, description normalised, amount, direction, balance) and balance is not None.
6. Reader arithmetic: build a `Statement` and call `reconcile`; `sum_mismatch` unless `ok` and `sum_delta` within tolerance; `continuity_break` if `continuity_breaks > 0`.
7. `currency_conflict` is reserved for the runner (multi-page merge); the gate accepts `meta.currency` as given.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_gate.py
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.gate import GATE_VERSION, gate, resolve_directions
from vlm.metadata import AccountMeta


def _rows(n=4, start=Decimal("500.00"), direction="credit"):
    rows, balance = [], start
    for i in range(1, n + 1):
        amount = Decimal(i * 10)
        balance = balance + amount if direction == "credit" else balance - amount
        rows.append(CandidateRow(f"2031-01-{i:02d}", f"01/{i:02d}", f"SYNTHETIC ROW {i:02d}", amount, direction,
                                 balance, 0, "stage_a", f"t0r{i}"))
    return rows


def _meta(begin="500.00", end="600.00"):
    return AccountMeta(Decimal(begin) if begin else None, Decimal(end) if end else None, "2031-01-01", "2031-01-31",
                       "USD", "0001", "SYNTHETIC BANK", ("test",))


def test_reconciled_ledger_is_admitted():
    verdict = gate(_rows(), _meta())
    assert verdict.admitted and verdict.reasons == () and verdict.row_count == 4
    assert verdict.computed_ending == Decimal("600.00") and verdict.continuity_breaks == 0
    assert verdict.checks["gate_version"] == GATE_VERSION


def test_tampered_amount_is_refused_with_codes():
    rows = _rows()
    rows[2] = CandidateRow(rows[2].date, rows[2].date_text, rows[2].description, Decimal("31.00"), "credit",
                           rows[2].balance, 0, "stage_a", rows[2].locator)
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "sum_mismatch" in verdict.reasons and "continuity_break" in verdict.reasons
    assert verdict.admitted_rows == ()


def test_missing_row_is_refused():
    rows = _rows()
    del rows[1]
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "sum_mismatch" in verdict.reasons


def test_unknown_direction_resolved_by_chain_and_flagged():
    rows = [CandidateRow(r.date, r.date_text, r.description, r.amount, "unknown", r.balance, 0, "stage_a", r.locator)
            for r in _rows()]
    resolved, flagged = resolve_directions(rows, Decimal("500.00"))
    assert flagged == 4 and all(r.direction == "credit" and r.direction_source == "chain" for r in resolved)
    verdict = gate(rows, _meta())
    assert verdict.admitted and verdict.chain_derived_directions == 4


def test_unknown_direction_without_balance_is_refused():
    rows = [CandidateRow(r.date, r.date_text, r.description, r.amount, "unknown", None, 0, "stage_a", r.locator)
            for r in _rows()]
    verdict = gate(rows, _meta())
    assert not verdict.admitted and "direction_unknown" in verdict.reasons


def test_missing_balances_are_derived_from_chain():
    verdict = gate(_rows(), AccountMeta(None, None, None, None, None, None, None, ()))
    assert verdict.admitted and verdict.checks["derived"] == ["beginning_balance", "ending_balance"]


def test_date_checks():
    rows = _rows()
    rows[1] = CandidateRow(None, "??", rows[1].description, rows[1].amount, "credit", rows[1].balance, 0, "stage_a", "x")
    assert "date_unparsed" in gate(rows, _meta()).reasons
    rows = _rows()
    rows[1] = CandidateRow("2031-03-05", "03/05", rows[1].description, rows[1].amount, "credit", rows[1].balance, 0, "stage_a", "x")
    reasons = gate(rows, _meta()).reasons
    assert "date_out_of_period" in reasons and "date_not_monotonic" in reasons


def test_duplicate_row_refused_and_no_rows():
    rows = _rows()
    rows.append(rows[-1])
    assert "duplicate_row" in gate(rows, _meta()).reasons
    verdict = gate([], _meta())
    assert not verdict.admitted and verdict.reasons == ("no_rows",)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_gate.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.gate'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/gate.py
"""The deterministic gate. The model proposes; `analysis.reconcile.reconcile` (the reader's own
arithmetic) decides, with date, duplicate and direction checks on top. Never partial admission."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from vlm.assemble import CandidateRow
from vlm.metadata import AccountMeta
from vlm.textparse import normalise_description

GATE_VERSION = 1
REASONS = ("no_rows", "proposal_invalid", "missing_beginning_balance", "missing_ending_balance",
           "direction_unknown", "date_unparsed", "date_out_of_period", "date_not_monotonic", "duplicate_row",
           "sum_mismatch", "continuity_break", "currency_conflict")
PERIOD_GRACE_DAYS = 5


@dataclass(frozen=True)
class GateVerdict:
    admitted: bool
    reasons: tuple[str, ...]
    row_count: int
    admitted_rows: tuple[CandidateRow, ...]
    computed_ending: Decimal | None
    continuity_breaks: int
    chain_derived_directions: int
    checks: dict


def resolve_directions(rows: list[CandidateRow], beginning: Decimal | None) -> tuple[list[CandidateRow], int]:
    resolved: list[CandidateRow] = []
    previous = beginning
    flagged = 0
    for row in rows:
        current = row
        if row.direction == "unknown" and previous is not None and row.balance is not None:
            delta = row.balance - previous
            if abs(delta) == row.amount and row.amount > 0:
                current = replace(row, direction="credit" if delta > 0 else "debit", direction_source="chain")
                flagged += 1
        resolved.append(current)
        if current.balance is not None:
            previous = current.balance
    return resolved, flagged


def _signed(row: CandidateRow) -> float:
    return float(row.amount if row.direction == "credit" else -row.amount)


def statement_from(rows: list[CandidateRow], meta: AccountMeta) -> Statement:
    return Statement(
        bank=meta.bank, account_name=None, account_number=meta.account_last4,
        period_start=meta.period_start, period_end=meta.period_end,
        beginning_balance=float(meta.beginning_balance) if meta.beginning_balance is not None else None,
        ending_balance=float(meta.ending_balance) if meta.ending_balance is not None else None,
        currency=meta.currency or "USD",
        transactions=[Transaction(date=row.date or "", description=row.description, amount=_signed(row),
                                  direction=row.direction if row.direction != "unknown" else "debit",
                                  running_balance=float(row.balance) if row.balance is not None else None)
                      for row in rows],
    )


def gate(rows: list[CandidateRow], meta: AccountMeta, *, tolerance: Decimal = Decimal("0.01")) -> GateVerdict:
    reasons: list[str] = []
    checks: dict = {"gate_version": GATE_VERSION, "derived": []}
    if not rows:
        return GateVerdict(False, ("no_rows",), 0, (), None, 0, 0, checks)
    if any(row.amount <= 0 for row in rows):
        reasons.append("proposal_invalid")
    beginning, ending = meta.beginning_balance, meta.ending_balance
    first, last = rows[0], rows[-1]
    if beginning is None and first.balance is not None and first.direction in ("credit", "debit"):
        beginning = first.balance - first.amount if first.direction == "credit" else first.balance + first.amount
        checks["derived"].append("beginning_balance")
    if ending is None and last.balance is not None:
        ending = last.balance
        checks["derived"].append("ending_balance")
    if beginning is None:
        reasons.append("missing_beginning_balance")
    if ending is None:
        reasons.append("missing_ending_balance")
    resolved, flagged = resolve_directions(rows, beginning)
    if any(row.direction == "unknown" for row in resolved):
        reasons.append("direction_unknown")
    dates = [row.date for row in resolved]
    if any(value is None for value in dates):
        reasons.append("date_unparsed")
    parsed = [date.fromisoformat(value) for value in dates if value]
    if meta.period_start and meta.period_end and parsed:
        lower = date.fromisoformat(meta.period_start) - timedelta(days=PERIOD_GRACE_DAYS)
        upper = date.fromisoformat(meta.period_end) + timedelta(days=PERIOD_GRACE_DAYS)
        if any(value < lower or value > upper for value in parsed):
            reasons.append("date_out_of_period")
    if any(later < earlier for earlier, later in zip(parsed, parsed[1:])):
        reasons.append("date_not_monotonic")
    seen: set[tuple] = set()
    for row in resolved:
        if row.balance is None:
            continue
        key = (row.date, normalise_description(row.description), row.amount, row.direction, row.balance)
        if key in seen:
            reasons.append("duplicate_row")
            break
        seen.add(key)
    computed_ending: Decimal | None = None
    continuity_breaks = 0
    if beginning is not None and ending is not None and "direction_unknown" not in reasons and "proposal_invalid" not in reasons:
        meta_for_reader = replace(meta, beginning_balance=beginning, ending_balance=ending)
        result = reconcile(statement_from(resolved, meta_for_reader))
        computed_ending = Decimal(str(result.computed_ending)).quantize(Decimal("0.01")) if result.computed_ending is not None else None
        continuity_breaks = int(result.continuity_breaks or 0)
        checks["reader_issues"] = list(result.issues)
        delta = abs(Decimal(str(result.sum_delta))) if result.sum_delta is not None else None
        if not result.ok or delta is None or delta > tolerance:
            reasons.append("sum_mismatch")
        if continuity_breaks:
            reasons.append("continuity_break")
    ordered = tuple(dict.fromkeys(reasons))
    admitted = not ordered
    return GateVerdict(admitted, ordered, len(resolved), tuple(resolved) if admitted else (), computed_ending,
                       continuity_breaks, flagged, checks)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_gate.py -q -p no:cacheprovider`
Expected: `8 passed`. If `reconcile` reports `sum_delta`/`computed_ending` under different attribute names, read `analysis/reconcile.py:19-60` and adapt the two attribute reads only; do not re-implement the arithmetic.

- [ ] **Step 5: Commit**

```bash
git add vlm/gate.py tests/test_vlm_gate.py
git commit -m "vlm: deterministic gate on the reader's reconcile" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Reader truth for CTRL and row matching

**Files:**
- Create: `vlm/truth.py`
- Test: `tests/test_vlm_truth.py`

**Interfaces:**
- Consumes: `tools.cohort_replay.ColdCache(data_dir, run_dir)` with `.text(sha, row) -> (markdown, pages)` and `.baseline_payload(markdown, pages) -> dict | None`; `analysis.payload_shape.payload_accounts(payload, surface=...)`; `vlm.partitions.run_rows`.
- Produces: `TruthRow` dataclass (`date, description, amount: Decimal (magnitude), direction, balance: Decimal | None`), `TruthAccount` (`account_number: str | None, beginning: Decimal | None, ending: Decimal | None, period_start, period_end, currency, rows: tuple[TruthRow, ...]`), `truth_from_payload(payload) -> list[TruthAccount]`, `ReaderTruth(data_dir, run_dir)` with `.accounts(sha) -> list[TruthAccount] | None` and `.close()`, `RowMatch` dataclass (`truth_rows, candidate_rows, matched, exact_balance, exact_description, missing, extra`), `match_rows(candidates, truth) -> RowMatch`.

Facts: the run-of-record cache is at `.claude/recovery/webapp_data_train12_cold/` (read-only; `provenance.json` → `cache.path`); the analysis payload's account statement dict has `transactions` with `date, description, amount (signed float), direction, running_balance`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_truth.py
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.truth import TruthAccount, TruthRow, match_rows, truth_from_payload

PAYLOAD_ACCOUNT_SHAPE = {
    "statement": {"account_number": "0001", "beginning_balance": 500.0, "ending_balance": 530.0,
                  "period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD",
                  "transactions": [
                      {"date": "2031-01-01", "description": "SYNTHETIC ROW 01", "amount": 10.0, "direction": "credit", "running_balance": 510.0},
                      {"date": "2031-01-02", "description": "SYNTHETIC ROW 02", "amount": -20.0, "direction": "debit", "running_balance": 490.0},
                      {"date": "2031-01-03", "description": "SYNTHETIC ROW 03", "amount": 40.0, "direction": "credit", "running_balance": 530.0}]},
    "metrics": {}, "reconciliation": {}, "quality": {}, "integrity": {}, "detection": {}, "classifications": [],
}


def test_truth_from_account_shape_payload():
    accounts = truth_from_payload(PAYLOAD_ACCOUNT_SHAPE)
    assert len(accounts) == 1
    account = accounts[0]
    assert account.account_number == "0001" and account.beginning == Decimal("500.00")
    assert account.rows[1] == TruthRow("2031-01-02", "SYNTHETIC ROW 02", Decimal("20.00"), "debit", Decimal("490.00"))


def test_truth_from_document_shape_payload():
    payload = {"document": {"account_count": 1}, "accounts": [PAYLOAD_ACCOUNT_SHAPE]}
    assert len(truth_from_payload(payload)) == 1


def test_match_rows_exact_and_partial():
    truth = truth_from_payload(PAYLOAD_ACCOUNT_SHAPE)[0]
    candidates = [
        CandidateRow("2031-01-01", "01/01", "Synthetic Row 01", Decimal("10.00"), "credit", Decimal("510.00"), 0, "stage_b", "p0r0"),
        CandidateRow("2031-01-02", "01/02", "SYNTHETIC ROW 02 extra", Decimal("20.00"), "debit", Decimal("491.00"), 0, "stage_b", "p0r1"),
        CandidateRow("2031-01-09", "01/09", "GHOST", Decimal("1.00"), "debit", None, 0, "stage_b", "p0r2"),
    ]
    match = match_rows(candidates, truth)
    assert (match.truth_rows, match.candidate_rows, match.matched, match.missing, match.extra) == (3, 3, 2, 1, 1)
    assert match.exact_balance == 1 and match.exact_description == 1


def test_match_rows_empty():
    truth = TruthAccount(None, None, None, None, None, "USD", ())
    match = match_rows([], truth)
    assert match.matched == 0 and match.truth_rows == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_truth.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.truth'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/truth.py
"""The reader's validated rows (CTRL) as truth for row-level comparison, and the matcher."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from analysis.payload_shape import payload_accounts
from vlm.assemble import CandidateRow
from vlm.textparse import normalise_description, to_decimal


@dataclass(frozen=True)
class TruthRow:
    date: str
    description: str
    amount: Decimal
    direction: str
    balance: Decimal | None


@dataclass(frozen=True)
class TruthAccount:
    account_number: str | None
    beginning: Decimal | None
    ending: Decimal | None
    period_start: str | None
    period_end: str | None
    currency: str | None
    rows: tuple[TruthRow, ...]


def _money(value) -> Decimal | None:
    return None if value is None else to_decimal(value)


def truth_from_payload(payload: dict) -> list[TruthAccount]:
    accounts: list[TruthAccount] = []
    for account in payload_accounts(payload, surface="vlm.truth"):
        statement = account.get("statement") or {}
        rows = tuple(
            TruthRow(date=str(t.get("date") or ""), description=str(t.get("description") or ""),
                     amount=abs(to_decimal(t.get("amount") or 0)), direction=str(t.get("direction") or ""),
                     balance=_money(t.get("running_balance")))
            for t in statement.get("transactions") or []
        )
        accounts.append(TruthAccount(
            account_number=statement.get("account_number"), beginning=_money(statement.get("beginning_balance")),
            ending=_money(statement.get("ending_balance")), period_start=statement.get("period_start"),
            period_end=statement.get("period_end"), currency=statement.get("currency"), rows=rows,
        ))
    return accounts


class ReaderTruth:
    """Read-only join to the run-of-record cache; returns None when the reader produced no payload."""

    def __init__(self, data_dir: Path, run_dir: Path) -> None:
        from tools.cohort_replay import ColdCache
        from vlm.partitions import run_rows

        self._cache = ColdCache(Path(data_dir), Path(run_dir))
        self._rows = run_rows(Path(run_dir))

    def accounts(self, sha: str) -> list[TruthAccount] | None:
        row = self._rows.get(sha.upper())
        if row is None:
            return None
        markdown, pages = self._cache.text(sha.upper(), row)
        if markdown is None:
            return None
        payload = self._cache.baseline_payload(markdown, pages)
        return None if payload is None else truth_from_payload(payload)

    def close(self) -> None:
        self._cache.close()


@dataclass(frozen=True)
class RowMatch:
    truth_rows: int
    candidate_rows: int
    matched: int
    exact_balance: int
    exact_description: int
    missing: int
    extra: int


def match_rows(candidates: list[CandidateRow], truth: TruthAccount) -> RowMatch:
    pool: Counter = Counter((t.date, t.amount, t.direction) for t in truth.rows)
    by_key: dict[tuple, list[TruthRow]] = {}
    for t in truth.rows:
        by_key.setdefault((t.date, t.amount, t.direction), []).append(t)
    matched = exact_balance = exact_description = 0
    for candidate in candidates:
        key = (candidate.date, candidate.amount, candidate.direction)
        if pool.get(key, 0) <= 0:
            continue
        pool[key] -= 1
        matched += 1
        twin = by_key[key].pop(0)
        if candidate.balance is not None and twin.balance is not None and candidate.balance == twin.balance:
            exact_balance += 1
        if normalise_description(candidate.description) == normalise_description(twin.description):
            exact_description += 1
    return RowMatch(truth_rows=len(truth.rows), candidate_rows=len(candidates), matched=matched,
                    exact_balance=exact_balance, exact_description=exact_description,
                    missing=len(truth.rows) - matched, extra=len(candidates) - matched)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_truth.py -q -p no:cacheprovider`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/truth.py tests/test_vlm_truth.py
git commit -m "vlm: reader truth join and row matching" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Stage B prompts

**Files:**
- Create: `vlm/prompts.py`
- Test: `tests/test_vlm_prompts.py`

**Interfaces:**
- Produces: `PROMPT_VERSION = 1`, `STAGE_B_PROMPT: str`, `HYBRID_PREFIX: str`, `STAGE_A_TABLE_PROMPT = "Table Recognition:"`, `STAGE_A_SPOTTING_PROMPT = "Spotting:"`, `stage_b_prompt(*, parser_context: str | None = None, page_number: int, page_total: int) -> str`, `prompt_sha256(text) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_prompts.py
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
    assert prompts.prompt_sha256(a) == prompts.prompt_sha256(a) and prompts.PROMPT_VERSION == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_prompts.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.prompts'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/prompts.py
"""Prompt texts, versioned and hashed into every receipt."""
from __future__ import annotations

from vlm.receipts import sha256_bytes

PROMPT_VERSION = 1
STAGE_A_TABLE_PROMPT = "Table Recognition:"
STAGE_A_SPOTTING_PROMPT = "Spotting:"

STAGE_B_PROMPT = """You are extracting one page of a bank statement into JSON for deterministic verification. This is page {page_number} of {page_total}.
Rules:
- Copy every value exactly as printed. Never compute, infer or invent a value. If a field is not printed on this page, use null.
- Dates: ISO YYYY-MM-DD. If the row prints no year, use the statement period's year. If the year is unknown, set date to null and put the printed text in date_text. Always fill date_text with the printed text.
- amount: the row's money amount as a positive number (no sign). direction: "credit" when money came into the account (deposits, credits, interest, refunds), "debit" when money left it (withdrawals, checks, fees, payments, purchases), "unknown" only when the page gives no way to tell.
- balance: the running balance printed on that row, else null.
- rows: one entry per printed transaction line, in printed order. Merge continuation lines into the description of the row above and set continues_previous on the merged-in text only if you must emit it separately. Skip totals, subtotals, headers and summary lines; they are not transactions.
- account: beginning_balance and ending_balance exactly as printed on this page (null if not on this page); period_start and period_end from the statement period; currency as an ISO code when printed or unambiguous from the bank's country; account_number_last4 as the last four digits printed.
- page_role: "statement_page" if the page lists transactions; "summary_page" if it holds only totals or summaries; "cheque_images" for check image pages; "cover_or_notice" for letters, notices and disclosures; "blank_or_other" otherwise.
- sections: the printed section headings in order (for example Deposits, Withdrawals, Checks, Fees, Daily balance). Each row's section_index points to its section, or null.
- daily_balances: rows of a printed daily balance table, if any.
- box: the row's bounding box as [x0, y0, x1, y1] fractions of the page width and height, or null.
Return only JSON matching the schema."""

HYBRID_PREFIX = """A document parser read this page first. Its tables (HTML) and text follow. Use them to read cell values precisely; the page image is the authority whenever they disagree.
--- parser output begins ---
{parser_context}
--- parser output ends ---
"""


def stage_b_prompt(*, parser_context: str | None = None, page_number: int, page_total: int) -> str:
    body = STAGE_B_PROMPT.format(page_number=page_number, page_total=page_total)
    if parser_context:
        return HYBRID_PREFIX.format(parser_context=parser_context) + body
    return body


def prompt_sha256(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_prompts.py -q -p no:cacheprovider`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/prompts.py tests/test_vlm_prompts.py
git commit -m "vlm: versioned Stage B prompts" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 13: Proposals → rows and metadata; multi-page merge

**Files:**
- Create: `vlm/proposals.py`
- Test: `tests/test_vlm_proposals.py`

**Interfaces:**
- Consumes: `vlm.schema.validate_page_proposal`, `vlm.assemble.CandidateRow`, `vlm.metadata.AccountMeta`, `merge_meta`, `vlm.textparse`.
- Produces: `PageProposal` dataclass (`page: int, proposal: dict, errors: tuple[str, ...]`), `rows_from_proposal(proposal, *, page, year_hint=None) -> list[CandidateRow]`, `meta_from_proposal(proposal) -> AccountMeta`, `merge_pages(pages: list[PageProposal]) -> tuple[list[CandidateRow], AccountMeta, dict]` (rows from `statement_page` pages in order; metadata first-non-null across pages in order; stats: `pages_by_role`, `invalid_pages`, `currency_conflict: bool`, `account_last4_values`).

Rules: a row's `amount` must be > 0 else dropped and counted in stats `rows_dropped_nonpositive`; a null `date` is re-parsed from `date_text` with the year hint; `continues_previous: true` rows are merged into the previous row's description; currency conflict when two pages print different non-null currencies.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_proposals.py
from decimal import Decimal

from vlm import proposals as pp
from vlm.schema import empty_proposal


def _page(role="statement_page", rows=(), currency="USD", begin=500.0, end=None, last4="0001"):
    p = empty_proposal(role)
    p["account"].update({"currency": currency, "beginning_balance": begin, "ending_balance": end,
                         "period_start": "2031-01-01", "period_end": "2031-01-31", "account_number_last4": last4})
    p["rows"] = list(rows)
    return p


def _row(date="2031-01-01", amount=10.0, direction="credit", balance=510.0, text="01/01", cont=False, desc="SYNTHETIC ROW 01"):
    return {"date": date, "date_text": text, "description": desc, "amount": amount, "direction": direction,
            "balance": balance, "section_index": None, "continues_previous": cont, "box": None}


def test_rows_from_proposal_parses_and_reparses_dates():
    rows = pp.rows_from_proposal(_page(rows=[_row(date=None, text="01/02"), _row(amount=0.0)]), page=3, year_hint=2031)
    assert len(rows) == 1 and rows[0].date == "2031-01-02" and rows[0].page == 3 and rows[0].source == "stage_b"
    assert rows[0].amount == Decimal("10.00") and rows[0].locator == "p3r0"


def test_continuation_rows_merge():
    rows = pp.rows_from_proposal(_page(rows=[_row(), _row(cont=True, desc="MORE TEXT", amount=1.0)]), page=0)
    assert len(rows) == 1 and rows[0].description == "SYNTHETIC ROW 01 MORE TEXT"


def test_merge_pages_roles_meta_and_conflicts():
    pages = [pp.PageProposal(0, _page("cover_or_notice", begin=None), ()),
             pp.PageProposal(1, _page(rows=[_row()], end=None), ()),
             pp.PageProposal(2, _page(rows=[_row(date="2031-01-05", balance=520.0)], currency="CAD", end=520.0), ()),
             pp.PageProposal(3, {"broken": True}, ("<root>: 'page_role' is a required property",))]
    rows, meta, stats = pp.merge_pages(pages)
    assert [r.page for r in rows] == [1, 2]
    assert meta.beginning_balance == Decimal("500.00") and meta.ending_balance == Decimal("520.00") and meta.currency == "USD"
    assert stats["pages_by_role"] == {"cover_or_notice": 1, "statement_page": 2, "invalid": 1}
    assert stats["currency_conflict"] is True and stats["invalid_pages"] == 1 and stats["account_last4_values"] == ["0001"]
    assert "meta:stage_b" in meta.sources
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_proposals.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.proposals'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/proposals.py
"""Stage B page proposals → candidate rows and account metadata; multi-page merge."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.metadata import EMPTY_META, AccountMeta, merge_meta
from vlm.textparse import parse_date, to_decimal


@dataclass(frozen=True)
class PageProposal:
    page: int
    proposal: dict
    errors: tuple[str, ...]


def _money(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return to_decimal(value)
    except ValueError:
        return None


def rows_from_proposal(proposal: dict, *, page: int, year_hint: int | None = None) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    for index, item in enumerate(proposal.get("rows") or []):
        amount = _money(item.get("amount"))
        if amount is None or amount <= 0:
            if item.get("continues_previous") and rows and item.get("description"):
                rows[-1] = replace(rows[-1], description=(rows[-1].description + " " + str(item["description"])).strip())
            continue
        if item.get("continues_previous") and rows:
            rows[-1] = replace(rows[-1], description=(rows[-1].description + " " + str(item.get("description") or "")).strip())
            continue
        date_text = str(item.get("date_text") or "")
        date = item.get("date") if isinstance(item.get("date"), str) else None
        if date is not None and parse_date(date) is None:
            date = None
        if date is None and date_text:
            date = parse_date(date_text, year_hint=year_hint)
        direction = item.get("direction") if item.get("direction") in ("credit", "debit") else "unknown"
        rows.append(CandidateRow(date=date, date_text=date_text, description=str(item.get("description") or ""),
                                 amount=amount, direction=direction, balance=_money(item.get("balance")), page=page,
                                 source="stage_b", locator=f"p{page}r{index}", direction_source="printed"))
    return rows


def meta_from_proposal(proposal: dict) -> AccountMeta:
    account = proposal.get("account") or {}
    period_start = parse_date(account.get("period_start")) if account.get("period_start") else None
    period_end = parse_date(account.get("period_end")) if account.get("period_end") else None
    currency = str(account["currency"]).upper() if account.get("currency") else None
    last4 = str(account["account_number_last4"])[-4:] if account.get("account_number_last4") else None
    meta = AccountMeta(_money(account.get("beginning_balance")), _money(account.get("ending_balance")), period_start,
                       period_end, currency, last4, account.get("bank") or None, ())
    populated = any(getattr(meta, f) is not None for f in ("beginning_balance", "ending_balance", "period_start", "currency"))
    return replace(meta, sources=("meta:stage_b",) if populated else ())


def merge_pages(pages: list[PageProposal]) -> tuple[list[CandidateRow], AccountMeta, dict]:
    rows: list[CandidateRow] = []
    meta = EMPTY_META
    roles: Counter = Counter()
    currencies: list[str] = []
    last4s: list[str] = []
    dropped = 0
    for page in sorted(pages, key=lambda p: p.page):
        if page.errors:
            roles["invalid"] += 1
            continue
        role = page.proposal.get("page_role") or "blank_or_other"
        roles[role] += 1
        page_meta = meta_from_proposal(page.proposal)
        meta = merge_meta(meta, page_meta)
        if page_meta.currency and page_meta.currency not in currencies:
            currencies.append(page_meta.currency)
        if page_meta.account_last4 and page_meta.account_last4 not in last4s:
            last4s.append(page_meta.account_last4)
        if role == "statement_page":
            year_hint = int(meta.period_end[:4]) if meta.period_end else (int(meta.period_start[:4]) if meta.period_start else None)
            before = len(page.proposal.get("rows") or [])
            page_rows = rows_from_proposal(page.proposal, page=page.page, year_hint=year_hint)
            dropped += max(0, before - len(page_rows) - sum(1 for r in page.proposal.get("rows") or [] if r.get("continues_previous")))
            rows.extend(page_rows)
    stats = {"pages_by_role": dict(sorted(roles.items())), "invalid_pages": roles.get("invalid", 0),
             "currency_conflict": len(currencies) > 1, "account_last4_values": last4s, "rows_dropped_nonpositive": dropped}
    return rows, meta, stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_proposals.py -q -p no:cacheprovider`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/proposals.py tests/test_vlm_proposals.py
git commit -m "vlm: proposals to rows and multi-page merge" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

Continue with part 4 (`2026-09-17-ceiling-harness-part4.md`): runner with receipts and prefetch, report, CLI, self-review.
