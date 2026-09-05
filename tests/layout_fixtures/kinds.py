"""tests/layout_fixtures/kinds.py — one synthetic generator per document kind
(Phase 2.2 cell C, `P22-CLASSIFY.md` §6; umbrella cases 1–4).

Every fixture states, for BOTH input modes, the verdict the classifier owes
it: `expect_evidence` (words with boxes) and `expect_text` (DEGRADED mode:
page strings only — the mode a Tesseract read or the cold cache's page text
puts the classifier in). Where the two differ, the difference is the point:
box-dependent signals (table alignment, the MICR band, the cheque aspect, a
raster far from paper) cannot fire without boxes, so the tier can only be
`lexical` there and a raster-only kind falls to `KIND_UNCERTAIN`.

Nothing here is derived from a real document. Dates are >= 2031; every
figure is generated from small integers; names are labelled synthetic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from evidence.canonical import ExtractionEvidence
from layout.document_class import DocumentProfileFacts
from tests.layout_fixtures.builders import (
    LEFT,
    LINE_HEIGHT,
    PAGE_HEIGHT_PT,
    PAGE_WIDTH_PT,
    SYNTHETIC_YEAR,
    TOP_MARGIN,
    SyntheticPage,
    Tok,
    cents,
    evidence_from_pages,
    make_page,
    pdf_magic,
    render_image_pdf,
    render_native_pdf_pages,
    rtok,
    texts_from_pages,
    tok,
)

__all__ = ["Expect", "LayoutFixture", "FIXTURES", "build", "names", "JAVA_MAGIC_BYTES"]

#: The Java object-serialisation stream header (`AC ED 00 05`) that 16 of the
#: archive's "PDFs" begin with (portal download artefacts).
JAVA_MAGIC_BYTES = b"\xac\xed\x00\x05"

# Column right edges / left edges for statement-shaped pages (points).
X_DATE = LEFT
X_DESC = LEFT + 100.0
R_AMOUNT = LEFT + 350.0     # right edge of a single amount column
R_DEBIT = LEFT + 290.0
R_CREDIT = LEFT + 370.0
R_BALANCE = LEFT + 470.0

OPENING_CENTS = 50_000      # 500.00 — a plain synthetic opening balance


@dataclass(frozen=True)
class Expect:
    kind: str
    sub_kind: str | None
    tier: str
    signals: frozenset[str] = frozenset()          # must be a SUBSET of the verdict's signal names
    findings: frozenset[str] = frozenset()         # must be a SUBSET of the verdict's finding codes
    absent_signals: frozenset[str] = frozenset()   # must be ABSENT from the verdict
    absent_findings: frozenset[str] = frozenset()  # must be ABSENT from the verdict
    language: str | None = None
    account_kind: str | None = None
    modality: str | None = None


@dataclass(frozen=True)
class LayoutFixture:
    name: str
    pages: tuple[SyntheticPage, ...]
    evidence: ExtractionEvidence | None
    page_texts: tuple[str, ...] | None
    profile: DocumentProfileFacts
    expect_evidence: Expect | None
    expect_text: Expect | None
    native_pdf: bytes | None
    image_pdf_builder: Callable[[], bytes] | None = None
    note: str = ""
    extra: dict = field(default_factory=dict)

    def image_pdf(self) -> bytes | None:
        return self.image_pdf_builder() if self.image_pdf_builder else None


# ---------------------------------------------------------------------------
# language furniture (literal strings; every lexicon entry the classifier
# knows is exercised by at least one fixture below)
# ---------------------------------------------------------------------------

def _money(value_cents: int, lang: str, *, signed: bool = False) -> str:
    """EN `1,234.56`; FR `1 234,56`; ES `1.234,56`. Unsigned unless `signed`."""
    sign = "-" if (signed and value_cents < 0) else ""
    value = abs(value_cents)
    whole, frac = divmod(value, 100)
    if lang == "en":
        return f"{sign}{whole:,}.{frac:02d}"
    grouped = f"{whole:,}"
    if lang == "fr":
        return f"{sign}{grouped.replace(',', ' ')},{frac:02d}"
    return f"{sign}{grouped.replace(',', '.')},{frac:02d}"


def _date(day: int, month: int, lang: str, *, year: int = SYNTHETIC_YEAR) -> str:
    if lang == "en":
        return f"{month:02d}/{day:02d}/{year}"
    return f"{day:02d}/{month:02d}/{year}"


_L = {
    "en": dict(title="SYNTHETIC CHECKING ACCOUNT STATEMENT", period="Statement Period:", to="to",
               opening="Beginning Balance", closing="Ending Balance", date="DATE", desc="DESCRIPTION",
               amount="AMOUNT", debit="WITHDRAWALS", credit="DEPOSITS", balance="BALANCE",
               page="Page", of="of", row="Synthetic", row2="item"),
    "fr": dict(title="RELEVÉ DE COMPTE CHÈQUES SYNTHÉTIQUE", period="Période du", to="au",
               opening="Solde d'ouverture", closing="Solde de clôture", date="DATE", desc="DESCRIPTION",
               amount="MONTANT", debit="RETRAITS", credit="DÉPÔTS", balance="SOLDE",
               page="Page", of="de", row="Synthétique", row2="article"),
    "es": dict(title="ESTADO DE CUENTA CORRIENTE SINTÉTICO", period="Periodo del", to="al",
               opening="Saldo inicial", closing="Saldo final", date="FECHA", desc="DESCRIPCIÓN",
               amount="IMPORTE", debit="RETIROS", credit="DEPÓSITOS", balance="SALDO",
               page="Página", of="de", row="Sintético", row2="artículo"),
}


def _row_amounts(n_rows: int) -> list[int]:
    """Signed cents per row: alternating credits and debits of a synthetic size."""
    out = []
    for i in range(1, n_rows + 1):
        magnitude = 1_000 * i + 500              # 15.00, 25.00, 35.00 ...
        out.append(magnitude if i % 2 else -magnitude)
    return out


def statement_pages(*, lang: str = "en", n_rows: int = 8, n_pages: int = 1, page_markers: bool = True,
                    period: bool = True, opening: bool = True, closing: bool = True,
                    columns: str = "amount_balance", discontinuity_at_page_break: bool = False,
                    zero_activity: bool = False, width_pt: float = PAGE_WIDTH_PT,
                    height_pt: float = PAGE_HEIGHT_PT, line_height: float = LINE_HEIGHT) -> list[SyntheticPage]:
    """A complete, statement-shaped synthetic document, or a named variant
    of it. `columns` ∈ {amount_balance, debit_credit_balance,
    signed_amount_balance}. The running balance is generated arithmetically
    from `OPENING_CENTS`; `discontinuity_at_page_break` shifts every balance
    printed from page 2 onward by a fixed offset so the chain breaks exactly
    at the page break and nowhere else."""
    L = _L[lang]
    amounts = [] if zero_activity else _row_amounts(n_rows)
    balances: list[int] = []
    balance = OPENING_CENTS
    for amount in amounts:
        balance += amount
        balances.append(balance)
    closing_cents = balance
    per_page = max(1, -(-len(amounts) // n_pages)) if amounts else 0
    pages: list[SyntheticPage] = []
    row_index = 0
    for p in range(n_pages):
        rows: list[list[Tok]] = []
        rows.append([tok(L["title"], LEFT)])
        if p == 0:
            if period:
                rows.append([tok(L["period"], LEFT), tok(_date(1, 3, lang), LEFT + 120.0),
                             tok(L["to"], LEFT + 200.0), tok(_date(31, 3, lang), LEFT + 230.0)])
            if opening:
                rows.append([tok(L["opening"], LEFT), rtok(_money(OPENING_CENTS, lang), R_BALANCE)])
            rows.append([])
        if zero_activity and p == 0:
            # Copied by hand from analysis/sibling_omission.py::DORMANT_RE
            # (`No\s+Transactions\s+This\s+Period`) — the exact vocabulary the
            # classifier's zero-activity declaration is keyed to.
            rows.append([tok("No Transactions This Period", LEFT)])
        elif amounts:
            if columns == "debit_credit_balance":
                rows.append([tok(L["date"], X_DATE), tok(L["desc"], X_DESC), rtok(L["debit"], R_DEBIT),
                             rtok(L["credit"], R_CREDIT), rtok(L["balance"], R_BALANCE)])
            else:
                rows.append([tok(L["date"], X_DATE), tok(L["desc"], X_DESC), rtok(L["amount"], R_AMOUNT),
                             rtok(L["balance"], R_BALANCE)])
            offset = 10_000 if (discontinuity_at_page_break and p >= 1) else 0
            for _ in range(per_page):
                if row_index >= len(amounts):
                    break
                amount = amounts[row_index]
                printed_balance = balances[row_index] + offset
                day = 2 + row_index
                row = [tok(_date(day, 3, lang), X_DATE), tok(L["row"], X_DESC), tok(L["row2"], X_DESC + 80.0),
                       tok(f"{row_index + 1:02d}", X_DESC + 140.0)]
                if columns == "debit_credit_balance":
                    if amount < 0:
                        row.append(rtok(_money(-amount, lang), R_DEBIT))
                    else:
                        row.append(rtok(_money(amount, lang), R_CREDIT))
                elif columns == "signed_amount_balance":
                    row.append(rtok(_money(amount, lang, signed=True), R_AMOUNT))
                else:
                    row.append(rtok(_money(abs(amount), lang), R_AMOUNT))
                row.append(rtok(_money(printed_balance, lang), R_BALANCE))
                rows.append(row)
                row_index += 1
        if p == n_pages - 1 and closing:
            rows.append([])
            rows.append([tok(L["closing"], LEFT), rtok(_money(closing_cents, lang), R_BALANCE)])
        if page_markers:
            rows.append([])
            rows.append([tok(L["page"], LEFT), tok(str(p + 1), LEFT + 40.0), tok(L["of"], LEFT + 60.0),
                         tok(str(n_pages), LEFT + 90.0)])
        pages.append(make_page(rows, width_pt=width_pt, height_pt=height_pt, line_height=line_height))
    return pages


def _profile(pages: list[SyntheticPage], *, classification: str = "digital") -> DocumentProfileFacts:
    texts = texts_from_pages(pages)
    return DocumentProfileFacts(
        valid_pdf=True, encrypted=False, page_count=len(pages), classification=classification,
        page_text_chars=tuple(len(t.strip()) for t in texts), magic=pdf_magic(),
    )


def _fixture(name: str, pages: list[SyntheticPage], *, expect_evidence: Expect | None, expect_text: Expect | None,
             classification: str = "digital", rotation_deg: int = 0, pixel_dpi: int | None = None,
             image: bool = False, rotate_pdf: int = 0, note: str = "", extra: dict | None = None) -> LayoutFixture:
    texts = texts_from_pages(pages)
    evidence = evidence_from_pages(pages, rotation_deg=rotation_deg, pixel_dpi=pixel_dpi,
                                   extractor_id="fixture-paddle" if pixel_dpi else "fixture-native")
    image_builder = None
    if image:
        page = pages[0]
        dpi = pixel_dpi or 300

        def image_builder(page=page, dpi=dpi) -> bytes:
            return render_image_pdf(page, dpi=dpi)
    return LayoutFixture(
        name=name, pages=tuple(pages), evidence=evidence, page_texts=texts,
        profile=_profile(pages, classification=classification),
        expect_evidence=expect_evidence, expect_text=expect_text,
        native_pdf=render_native_pdf_pages(pages, rotate=rotate_pdf),
        image_pdf_builder=image_builder, note=note, extra=dict(extra or {}),
    )


STATEMENT_SIGNALS = frozenset({"period_expression", "opening_balance_label", "closing_balance_label",
                               "table_run", "running_balance", "page_marker"})


def _complete(tier_evidence: str = "structural") -> tuple[Expect, Expect]:
    ev = Expect("STATEMENT_COMPLETE", None, tier_evidence, STATEMENT_SIGNALS | {"table_alignment"},
                account_kind="deposit")
    tx = Expect("STATEMENT_COMPLETE", None, "lexical", STATEMENT_SIGNALS, absent_signals=frozenset({"table_alignment"}),
                account_kind="deposit")
    return ev, tx


# ---------------------------------------------------------------------------
# the generators (one per kind, plus the named variants the card requires)
# ---------------------------------------------------------------------------

def statement_complete_en() -> LayoutFixture:
    ev, tx = _complete()
    return _fixture("statement_complete_en", statement_pages(lang="en", n_pages=2),
                    expect_evidence=Expect(**{**ev.__dict__, "language": "en"}),
                    expect_text=Expect(**{**tx.__dict__, "language": "en"}))


def statement_complete_fr() -> LayoutFixture:
    ev, tx = _complete()
    return _fixture("statement_complete_fr", statement_pages(lang="fr", n_pages=2),
                    expect_evidence=Expect(**{**ev.__dict__, "language": "fr"}),
                    expect_text=Expect(**{**tx.__dict__, "language": "fr"}))


def statement_complete_es() -> LayoutFixture:
    ev, tx = _complete()
    return _fixture("statement_complete_es", statement_pages(lang="es", n_pages=2),
                    expect_evidence=Expect(**{**ev.__dict__, "language": "es"}),
                    expect_text=Expect(**{**tx.__dict__, "language": "es"}))


def statement_two_money_columns() -> LayoutFixture:
    ev, tx = _complete()
    return _fixture("statement_two_money_columns", statement_pages(columns="debit_credit_balance"),
                    expect_evidence=ev, expect_text=tx, note="WITHDRAWALS / DEPOSITS / BALANCE columns")


def statement_single_signed_column() -> LayoutFixture:
    ev, tx = _complete()
    return _fixture("statement_single_signed_column", statement_pages(columns="signed_amount_balance"),
                    expect_evidence=ev, expect_text=tx, note="a signed AMOUNT column beside BALANCE")


def statement_zero_activity() -> LayoutFixture:
    signals = frozenset({"period_expression", "opening_balance_label", "closing_balance_label",
                         "zero_activity_declaration", "page_marker"})
    ex = Expect("STATEMENT_COMPLETE", None, "lexical", signals, absent_signals=frozenset({"table_run"}))
    return _fixture("statement_zero_activity", statement_pages(zero_activity=True), expect_evidence=ex, expect_text=ex,
                    note="no rows; the printed zero-activity declaration stands in for the table")


def statement_rotated() -> LayoutFixture:
    """A complete statement whose page is displayed rotated 90 degrees. The
    evidence is built BY HAND in the display frame (landscape, words upright,
    `rotation_deg=90` recorded on the frame) — cell K's display-frame reader
    is not on this branch. The native PDF authors the words sideways on a
    portrait page and sets /Rotate 90, so a viewer shows them upright."""
    pages = statement_pages(lang="en", width_pt=PAGE_HEIGHT_PT, height_pt=PAGE_WIDTH_PT)
    ev, tx = _complete()
    texts = texts_from_pages(pages)
    evidence = evidence_from_pages(pages, rotation_deg=90)
    return LayoutFixture(
        name="statement_rotated", pages=tuple(pages), evidence=evidence, page_texts=texts,
        profile=_profile(pages), expect_evidence=ev, expect_text=tx,
        native_pdf=_render_rotated_pdf(pages[0]), note="display-frame evidence built by hand; rotation 90 recorded",
    )


def _render_rotated_pdf(page: SyntheticPage) -> bytes:
    import fitz

    doc = fitz.open()
    try:
        # The display frame is `page` (landscape); the content stream is the
        # portrait page whose /Rotate 90 turns into it. A display point
        # (x, y) on a W x H landscape page comes from content point (y, W - x)
        # on the H x W portrait page; text is inserted rotated 90 so it reads
        # upright after the page rotation.
        pdf_page = doc.new_page(width=page.height_pt, height=page.width_pt)
        for line in page.lines:
            for word in line.words:
                pdf_page.insert_text((word.y1, page.width_pt - word.x0), word.text, fontsize=11.0,
                                     fontname="Courier", rotate=90)
        pdf_page.set_rotation(90)
        return doc.tobytes()
    finally:
        doc.close()


def partial_page_removed() -> LayoutFixture:
    pages = statement_pages(n_rows=12, n_pages=3)
    kept = [pages[0], pages[2]]
    ex_ev = Expect("STATEMENT_PARTIAL", None, "structural", frozenset({"page_marker", "page_gap"}),
                   findings=frozenset({"page_gap"}))
    ex_tx = Expect("STATEMENT_PARTIAL", None, "structural", frozenset({"page_marker", "page_gap"}),
                   findings=frozenset({"page_gap"}))
    return _fixture("partial_page_removed", kept, expect_evidence=ex_ev, expect_text=ex_tx,
                    note="Page 1 of 3 and Page 3 of 3 remain; the page-gap fact is not box-dependent")


def partial_last_page_removed() -> LayoutFixture:
    pages = statement_pages(n_rows=12, n_pages=3)
    kept = pages[:2]
    ex = Expect("STATEMENT_PARTIAL", None, "structural", frozenset({"page_marker", "page_missing"}),
                findings=frozenset({"missing_pages", "missing_closing"}))
    return _fixture("partial_last_page_removed", kept, expect_evidence=ex, expect_text=ex)


def partial_first_page_removed() -> LayoutFixture:
    pages = statement_pages(n_rows=12, n_pages=3)
    kept = pages[1:]
    ex = Expect("STATEMENT_PARTIAL", None, "structural", frozenset({"page_marker", "first_page_missing"}),
                findings=frozenset({"missing_first_page", "missing_period", "missing_opening"}))
    return _fixture("partial_first_page_removed", kept, expect_evidence=ex, expect_text=ex)


def partial_opening_removed() -> LayoutFixture:
    ex_ev = Expect("STATEMENT_PARTIAL", None, "lexical", frozenset({"period_expression", "closing_balance_label"}),
                   findings=frozenset({"missing_opening"}), absent_signals=frozenset({"opening_balance_label"}),
                   absent_findings=frozenset({"missing_closing", "missing_period", "page_gap"}))
    return _fixture("partial_opening_removed", statement_pages(opening=False), expect_evidence=ex_ev, expect_text=ex_ev)


def partial_closing_removed() -> LayoutFixture:
    ex = Expect("STATEMENT_PARTIAL", None, "lexical", frozenset({"period_expression", "opening_balance_label"}),
                findings=frozenset({"missing_closing"}), absent_signals=frozenset({"closing_balance_label"}),
                absent_findings=frozenset({"missing_opening", "missing_period", "page_gap"}))
    return _fixture("partial_closing_removed", statement_pages(closing=False), expect_evidence=ex, expect_text=ex)


def partial_period_removed() -> LayoutFixture:
    ex = Expect("STATEMENT_PARTIAL", None, "lexical", frozenset({"opening_balance_label", "closing_balance_label"}),
                findings=frozenset({"missing_period"}), absent_signals=frozenset({"period_expression"}),
                absent_findings=frozenset({"missing_opening", "missing_closing", "page_gap"}))
    return _fixture("partial_period_removed", statement_pages(period=False), expect_evidence=ex, expect_text=ex)


def partial_balance_discontinuity() -> LayoutFixture:
    ex_ev = Expect("STATEMENT_PARTIAL", None, "structural", frozenset({"balance_discontinuity", "running_balance"}),
                   findings=frozenset({"balance_discontinuity_at_page_break"}),
                   absent_findings=frozenset({"page_gap", "missing_opening", "missing_closing", "missing_period"}))
    ex_tx = Expect("STATEMENT_PARTIAL", None, "lexical", frozenset({"balance_discontinuity", "running_balance"}),
                   findings=frozenset({"balance_discontinuity_at_page_break"}),
                   absent_findings=frozenset({"page_gap", "missing_opening", "missing_closing", "missing_period"}))
    return _fixture("partial_balance_discontinuity", statement_pages(n_rows=10, n_pages=2, discontinuity_at_page_break=True),
                    expect_evidence=ex_ev, expect_text=ex_tx,
                    note="every balance on page 2 is offset; the chain breaks only at the page break")


def statement_illegible() -> LayoutFixture:
    """Statement-shaped lexical signals on pages that carry almost no other
    words — an OCR read that lost the body. Below the usable floor."""
    rows = [
        [tok("Statement Period:", LEFT), tok(_date(1, 3, "en"), LEFT + 120.0), tok("to", LEFT + 200.0),
         tok(_date(31, 3, "en"), LEFT + 230.0)],
        [tok("Beginning Balance", LEFT), rtok(cents(OPENING_CENTS), R_BALANCE)],
        [tok("Ending Balance", LEFT), rtok(cents(OPENING_CENTS + 5_000), R_BALANCE)],
    ]
    blank = [[tok("Page", LEFT), tok("2", LEFT + 40.0), tok("of", LEFT + 60.0), tok("2", LEFT + 90.0)]]
    pages = [make_page(rows), make_page(blank)]
    ex = Expect("STATEMENT_ILLEGIBLE", None, "lexical", frozenset({"period_expression", "opening_balance_label",
                                                                    "closing_balance_label", "illegible_floor"}),
                absent_signals=frozenset({"table_run"}))
    return _fixture("statement_illegible", pages, expect_evidence=ex, expect_text=ex, classification="scanned")


def activity_export() -> LayoutFixture:
    rows: list[list[Tok]] = [
        [tok("Account", LEFT), tok("Activity", LEFT + 60.0)],
        [tok("Showing", LEFT), tok("transactions", LEFT + 60.0), tok("for", LEFT + 150.0), tok("the", LEFT + 180.0),
         tok("selected", LEFT + 210.0), tok("date", LEFT + 270.0), tok("range", LEFT + 310.0)],
        [],
        [tok("Date", X_DATE), tok("Description", X_DESC), rtok("Amount", R_AMOUNT), rtok("Balance", R_BALANCE)],
    ]
    balance = 90_000
    for i in range(8):
        day = 30 - i * 3
        status = "Pending" if i < 2 else "Posted"
        amount = 2_000 * (i + 1)
        row = [tok(_date(day, 3, "en"), X_DATE), tok("Synthetic", X_DESC), tok("purchase", X_DESC + 70.0),
               tok(status, X_DESC + 150.0), rtok(cents(amount), R_AMOUNT), rtok(cents(balance), R_BALANCE)]
        rows.append(row)
        balance += amount
    rows.append([])
    rows.append([tok("Printed", LEFT), tok(_date(2, 4, "en"), LEFT + 60.0)])
    ev = Expect("ACTIVITY_EXPORT", None, "structural", frozenset({"table_run", "table_alignment", "reverse_chronology",
                                                                  "pending_row"}),
                absent_signals=frozenset({"period_expression", "opening_balance_label", "closing_balance_label"}))
    tx = Expect("ACTIVITY_EXPORT", None, "lexical", frozenset({"table_run", "reverse_chronology", "pending_row"}),
                absent_signals=frozenset({"table_alignment", "period_expression", "opening_balance_label",
                                          "closing_balance_label"}))
    return _fixture("activity_export", [make_page(rows)], expect_evidence=ev, expect_text=tx,
                    note="reverse chronology and pending rows; no period / opening / closing anchor")


CHEQUE_W = 600.0
CHEQUE_H = 260.0          # aspect just over 2.3 — inside [2.0, 2.6]
MICR_LINE = "⑆111111111⑆ 2222222222⑈ 1001"   # E-13B-shaped digit groups with transit / on-us symbols


def _cheque_rows(*, micr: bool, void: bool, lexicon: bool = True) -> list[list[Tok]]:
    rows: list[list[Tok]] = [
        [tok("SYNTHETIC", LEFT), tok("PAYER", LEFT + 70.0), tok("NAME", LEFT + 110.0),
         tok("DATE", CHEQUE_W - 150.0), tok(_date(5, 3, "en"), CHEQUE_W - 110.0)],
        [],
    ]
    if lexicon:
        rows.append([tok("PAY", LEFT), tok("TO", LEFT + 30.0), tok("THE", LEFT + 50.0), tok("ORDER", LEFT + 80.0),
                     tok("OF", LEFT + 120.0), tok("Synthetic", LEFT + 150.0), tok("Payee", LEFT + 220.0),
                     tok("$", CHEQUE_W - 120.0), tok(cents(12_500), CHEQUE_W - 100.0)])
        rows.append([tok("One", LEFT), tok("hundred", LEFT + 30.0), tok("twenty-five", LEFT + 90.0),
                     tok("and", LEFT + 170.0), tok("00/100", LEFT + 200.0), tok("DOLLARS", CHEQUE_W - 160.0)])
    else:
        rows.append([tok("Synthetic", LEFT + 150.0), tok("Payee", LEFT + 220.0), tok("$", CHEQUE_W - 120.0),
                     tok(cents(12_500), CHEQUE_W - 100.0)])
        rows.append([])
    if void:
        rows.append([tok("VOID", CHEQUE_W / 2 - 20.0)])
    else:
        rows.append([])
    if lexicon:
        rows.append([tok("MEMO", LEFT), tok("fixture", LEFT + 40.0)])
    else:
        rows.append([])
    return rows


def _cheque_page(rows: list[list[Tok]], *, micr: bool, width: float = CHEQUE_W, height: float = CHEQUE_H) -> SyntheticPage:
    page = make_page(rows, width_pt=width, height_pt=height, top=40.0, line_height=22.0)
    if not micr:
        return page
    from tests.layout_fixtures.builders import line_at

    micr_line = line_at(height - 10.0, [tok(MICR_LINE, LEFT)])   # baseline 10 pt above the bottom edge
    return SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=page.lines + (micr_line,))


def cheque_image() -> LayoutFixture:
    page = _cheque_page(_cheque_rows(micr=True, void=False), micr=True)
    ev = Expect("NOT_A_STATEMENT", "cheque_image", "structural", frozenset({"micr_shape", "micr_band", "cheque_aspect",
                                                                          "cheque_lexicon"}),
                absent_signals=frozenset({"void_lexicon"}), modality="image_backed_text")
    tx = Expect("NOT_A_STATEMENT", "cheque_image", "lexical", frozenset({"micr_shape", "cheque_lexicon"}),
                absent_signals=frozenset({"micr_band", "cheque_aspect"}), modality="image_backed_text")
    return _fixture("cheque_image", [page], expect_evidence=ev, expect_text=tx, classification="scanned",
                    pixel_dpi=300, image=True, note="a PIXEL frame at 300 dpi, the shape a Paddle read produces")


def cheque_no_micr() -> LayoutFixture:
    """Case 3, second half: the same cheque-shaped page WITHOUT a MICR line
    is never `structural` — the lexicon alone makes it a lexical cheque."""
    page = _cheque_page(_cheque_rows(micr=False, void=False), micr=False)
    ex = Expect("NOT_A_STATEMENT", "cheque_image", "lexical", frozenset({"cheque_lexicon"}),
                absent_signals=frozenset({"micr_shape", "micr_band"}))
    return _fixture("cheque_no_micr", [page], expect_evidence=ex, expect_text=ex, classification="scanned",
                    pixel_dpi=300)


def cheque_shape_nothing_else() -> LayoutFixture:
    """A cheque-shaped page with neither MICR nor the cheque lexicon: nothing
    fires, so the verdict is `KIND_UNCERTAIN` (case 3: 'KIND_UNCERTAIN or
    lexical, never structural')."""
    page = _cheque_page(_cheque_rows(micr=False, void=False, lexicon=False), micr=False)
    ex = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset(), absent_signals=frozenset({"micr_band", "cheque_lexicon"}))
    return _fixture("cheque_shape_nothing_else", [page], expect_evidence=ex, expect_text=ex, classification="scanned",
                    pixel_dpi=300)


def cheque_portrait_micr() -> LayoutFixture:
    """Mutant M2's killer: a MICR line in the bottom band of a PORTRAIT page
    (letter size, aspect 0.77) must not be a structural cheque."""
    rows = _cheque_rows(micr=True, void=False)
    page = _cheque_page(rows, micr=True, width=PAGE_WIDTH_PT, height=PAGE_HEIGHT_PT)
    ex = Expect("NOT_A_STATEMENT", "cheque_image", "lexical", frozenset({"micr_shape", "micr_band", "cheque_lexicon"}),
                absent_signals=frozenset({"cheque_aspect"}))
    tx = Expect("NOT_A_STATEMENT", "cheque_image", "lexical", frozenset({"micr_shape", "cheque_lexicon"}),
                absent_signals=frozenset({"cheque_aspect", "micr_band"}))
    return _fixture("cheque_portrait_micr", [page], expect_evidence=ex, expect_text=tx, classification="scanned",
                    pixel_dpi=300)


def voided_cheque() -> LayoutFixture:
    page = _cheque_page(_cheque_rows(micr=True, void=True), micr=True)
    ev = Expect("NOT_A_STATEMENT", "voided_cheque", "structural", frozenset({"micr_band", "cheque_aspect", "void_lexicon"}))
    tx = Expect("NOT_A_STATEMENT", "voided_cheque", "lexical", frozenset({"micr_shape", "void_lexicon"}),
                absent_signals=frozenset({"micr_band", "cheque_aspect"}))
    return _fixture("voided_cheque", [page], expect_evidence=ev, expect_text=tx, classification="scanned",
                    pixel_dpi=300, image=True)


def deposit_slip() -> LayoutFixture:
    rows = [
        [tok("DEPOSIT", LEFT), tok("TICKET", LEFT + 60.0), tok("DATE", LEFT + 300.0), tok(_date(5, 3, "en"), LEFT + 340.0)],
        [tok("SYNTHETIC", LEFT), tok("DEPOSITOR", LEFT + 70.0)],
        [],
        [tok("CASH", LEFT), rtok(cents(10_000), R_AMOUNT)],
        [tok("CHECKS", LEFT), rtok(cents(25_000), R_AMOUNT)],
        [tok("TOTAL", LEFT), tok("FROM", LEFT + 40.0), tok("OTHER", LEFT + 75.0), tok("SIDE", LEFT + 115.0),
         rtok(cents(0), R_AMOUNT)],
        [tok("LESS", LEFT), tok("CASH", LEFT + 35.0), tok("RECEIVED", LEFT + 70.0), rtok(cents(0), R_AMOUNT)],
        [tok("NET", LEFT), tok("DEPOSIT", LEFT + 30.0), rtok(cents(35_000), R_AMOUNT)],
    ]
    ex = Expect("NOT_A_STATEMENT", "deposit_slip", "lexical", frozenset({"deposit_slip_lexicon"}),
                absent_signals=frozenset({"table_run"}))
    return _fixture("deposit_slip", [make_page(rows)], expect_evidence=ex, expect_text=ex, classification="scanned",
                    pixel_dpi=300)


def deposit_slip_cheque_shaped() -> LayoutFixture:
    """A deposit ticket printed on cheque stock: MICR band AND cheque aspect
    AND the deposit-slip lexicon. The lexicon names the sub-kind; the
    structural facts decide that it is not a statement."""
    rows = [
        [tok("DEPOSIT", LEFT), tok("TICKET", LEFT + 60.0), tok("DATE", CHEQUE_W - 150.0), tok(_date(5, 3, "en"), CHEQUE_W - 110.0)],
        [tok("CASH", LEFT), rtok(cents(10_000), CHEQUE_W - 60.0)],
        [tok("CHECKS", LEFT), rtok(cents(25_000), CHEQUE_W - 60.0)],
        [tok("LESS", LEFT), tok("CASH", LEFT + 35.0), tok("RECEIVED", LEFT + 70.0), rtok(cents(0), CHEQUE_W - 60.0)],
        [tok("NET", LEFT), tok("DEPOSIT", LEFT + 30.0), rtok(cents(35_000), CHEQUE_W - 60.0)],
    ]
    page = _cheque_page(rows, micr=True)
    ev = Expect("NOT_A_STATEMENT", "deposit_slip", "structural", frozenset({"deposit_slip_lexicon", "micr_band", "cheque_aspect"}))
    tx = Expect("NOT_A_STATEMENT", "deposit_slip", "lexical", frozenset({"deposit_slip_lexicon", "micr_shape"}))
    return _fixture("deposit_slip_cheque_shaped", [page], expect_evidence=ev, expect_text=tx, classification="scanned",
                    pixel_dpi=300)


def letter_notice() -> LayoutFixture:
    rows = [
        [tok("SYNTHETIC", LEFT), tok("BANKING", LEFT + 70.0), tok("CORPORATION", LEFT + 130.0)],
        [tok("March", LEFT), tok("5,", LEFT + 45.0), tok(str(SYNTHETIC_YEAR), LEFT + 65.0)],
        [],
        [tok("Dear", LEFT), tok("Customer,", LEFT + 35.0)],
        [],
        [tok("We", LEFT), tok("are", LEFT + 20.0), tok("writing", LEFT + 45.0), tok("to", LEFT + 100.0),
         tok("inform", LEFT + 120.0), tok("you", LEFT + 165.0), tok("of", LEFT + 190.0), tok("a", LEFT + 210.0),
         tok("change", LEFT + 225.0), tok("to", LEFT + 275.0), tok("your", LEFT + 295.0), tok("account", LEFT + 330.0)],
        [tok("terms.", LEFT), tok("Please", LEFT + 50.0), tok("contact", LEFT + 95.0), tok("us", LEFT + 150.0),
         tok("with", LEFT + 170.0), tok("any", LEFT + 205.0), tok("questions.", LEFT + 235.0)],
        [],
        [tok("Sincerely,", LEFT)],
        [tok("Synthetic", LEFT), tok("Branch", LEFT + 70.0), tok("Manager", LEFT + 120.0)],
    ]
    ex = Expect("NOT_A_STATEMENT", "letter_or_notice", "lexical", frozenset({"letter_lexicon"}),
                absent_signals=frozenset({"table_run"}))
    return _fixture("letter_notice", [make_page(rows)], expect_evidence=ex, expect_text=ex)


def letter_with_unaligned_dated_lines() -> LayoutFixture:
    """Mutant M5's killer: a letter whose prose carries six lines each with a
    date and a money figure, at DIFFERENT x positions. With boxes, the money
    tokens do not align, so there is no table and the letter lexicon decides.
    Without boxes (DEGRADED), the line-count form of the table signal fires
    and a table with no anchor, no marker and no export trait is refused as
    `KIND_UNCERTAIN` — the honest answer for text alone."""
    rows: list[list[Tok]] = [
        [tok("Dear", LEFT), tok("Customer,", LEFT + 35.0)],
        [],
    ]
    prefixes = ["On", "Then on", "Later on", "Again on", "Finally on", "And on"]
    for i, prefix in enumerate(prefixes):
        x = LEFT
        row = []
        for word in prefix.split():
            row.append(tok(word, x))
            x += (len(word) + 1) * 6.6
        row.append(tok(_date(3 + i, 3, "en"), x))
        x += 11 * 6.6
        for word in ("a", "fee", "of"):
            row.append(tok(word, x))
            x += (len(word) + 1) * 6.6
        row.append(tok(cents(1_200 + 100 * i), x))     # the money token's x drifts with the prefix length
        x += 6 * 6.6
        row.append(tok("applied.", x))
        rows.append(row)
    rows.append([])
    rows.append([tok("Sincerely,", LEFT)])
    ev = Expect("NOT_A_STATEMENT", "letter_or_notice", "lexical", frozenset({"letter_lexicon"}),
                absent_signals=frozenset({"table_run", "table_alignment"}))
    tx = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset({"table_run", "letter_lexicon"}),
                absent_signals=frozenset({"table_alignment"}))
    return _fixture("letter_with_unaligned_dated_lines", [make_page(rows)], expect_evidence=ev, expect_text=tx)


def _card_rows(*, running_balance: bool) -> list[list[Tok]]:
    rows: list[list[Tok]] = [
        [tok("SYNTHETIC", LEFT), tok("CARD", LEFT + 70.0), tok("ACCOUNT", LEFT + 105.0)],
        [tok("Statement", LEFT), tok("Period:", LEFT + 65.0), tok(_date(1, 3, "en"), LEFT + 120.0), tok("to", LEFT + 200.0),
         tok(_date(31, 3, "en"), LEFT + 230.0)],
        [tok("Previous", LEFT), tok("Balance", LEFT + 60.0), rtok(cents(50_000), R_BALANCE)],
        [tok("New", LEFT), tok("Balance", LEFT + 30.0), rtok(cents(65_000), R_BALANCE)],
        [tok("Minimum", LEFT), tok("Payment", LEFT + 55.0), tok("Due", LEFT + 110.0), rtok(cents(2_500), R_BALANCE)],
        [tok("Payment", LEFT), tok("Due", LEFT + 55.0), tok("Date", LEFT + 85.0), tok(_date(25, 4, "en"), LEFT + 120.0)],
        [tok("Credit", LEFT), tok("Limit", LEFT + 45.0), rtok(cents(500_000), R_BALANCE)],
        [tok("Available", LEFT), tok("Credit", LEFT + 65.0), rtok(cents(435_000), R_BALANCE)],
        [],
    ]
    if running_balance:
        rows.append([tok("DATE", X_DATE), tok("DESCRIPTION", X_DESC), rtok("AMOUNT", R_AMOUNT), rtok("BALANCE", R_BALANCE)])
    else:
        rows.append([tok("DATE", X_DATE), tok("DESCRIPTION", X_DESC), rtok("AMOUNT", R_AMOUNT)])
    balance = 50_000
    for i in range(6):
        amount = 2_000 + 500 * i
        balance += amount
        row = [tok(_date(2 + i, 3, "en"), X_DATE), tok("Synthetic", X_DESC), tok("merchant", X_DESC + 70.0),
               rtok(cents(amount), R_AMOUNT)]
        if running_balance:
            row.append(rtok(cents(balance), R_BALANCE))
        rows.append(row)
    return rows


def card_statement() -> LayoutFixture:
    ex = Expect("NOT_A_STATEMENT", "card_statement", "lexical", frozenset({"card_lexicon", "table_run"}),
                absent_signals=frozenset({"running_balance"}), account_kind="card")
    return _fixture("card_statement", [make_page(_card_rows(running_balance=False))], expect_evidence=ex, expect_text=ex,
                    note="a single amount column and no running balance")


def loan_statement() -> LayoutFixture:
    rows = [
        [tok("SYNTHETIC", LEFT), tok("MORTGAGE", LEFT + 70.0), tok("LOAN", LEFT + 135.0)],
        [tok("Statement", LEFT), tok("Date", LEFT + 65.0), tok(_date(5, 3, "en"), LEFT + 100.0)],
        [],
        [tok("Principal", LEFT), tok("Balance", LEFT + 65.0), rtok(cents(15_000_000), R_BALANCE)],
        [tok("Escrow", LEFT), tok("Balance", LEFT + 50.0), rtok(cents(120_000), R_BALANCE)],
        [tok("Interest", LEFT), tok("Paid", LEFT + 60.0), tok("Year", LEFT + 95.0), tok("to", LEFT + 130.0),
         tok("Date", LEFT + 150.0), rtok(cents(340_000), R_BALANCE)],
        [tok("Payment", LEFT), tok("Due", LEFT + 55.0), tok(_date(1, 4, "en"), LEFT + 100.0)],
        [tok("Amount", LEFT), tok("Due", LEFT + 50.0), rtok(cents(125_000), R_BALANCE)],
    ]
    ex = Expect("NOT_A_STATEMENT", "loan_statement", "lexical", frozenset({"loan_lexicon"}),
                absent_signals=frozenset({"table_run"}), account_kind="loan")
    return _fixture("loan_statement", [make_page(rows)], expect_evidence=ex, expect_text=ex)


def brokerage_page() -> LayoutFixture:
    rows = [
        [tok("SYNTHETIC", LEFT), tok("BROKERAGE", LEFT + 70.0), tok("ACCOUNT", LEFT + 140.0)],
        [tok("Portfolio", LEFT), tok("Summary", LEFT + 65.0), tok("as", LEFT + 130.0), tok("of", LEFT + 150.0),
         tok(_date(31, 3, "en"), LEFT + 170.0)],
        [],
        [tok("Holdings", LEFT)],
        [tok("Symbol", LEFT), tok("Quantity", LEFT + 100.0), rtok("Price", R_AMOUNT), rtok("Market", R_BALANCE - 40.0),
         rtok("Value", R_BALANCE)],
        [tok("SYNA", LEFT), tok("10", LEFT + 100.0), rtok(cents(1_000), R_AMOUNT), rtok(cents(10_000), R_BALANCE)],
        [tok("SYNB", LEFT), tok("20", LEFT + 100.0), rtok(cents(2_000), R_AMOUNT), rtok(cents(40_000), R_BALANCE)],
        [],
        [tok("Positions", LEFT), tok("total", LEFT + 65.0), tok("market", LEFT + 105.0), tok("value", LEFT + 155.0),
         rtok(cents(50_000), R_BALANCE)],
    ]
    ex = Expect("NOT_A_STATEMENT", "brokerage", "lexical", frozenset({"brokerage_lexicon"}),
                absent_signals=frozenset({"table_run"}), account_kind="brokerage")
    return _fixture("brokerage_page", [make_page(rows)], expect_evidence=ex, expect_text=ex)


SCREEN_W = 1366.0
SCREEN_H = 768.0


def screenshot_image() -> LayoutFixture:
    """A phone/desktop screenshot saved as a PDF: the page (and the raster
    behind it) is far from any paper size; a handful of widget labels; no
    table. Only a frame can say so — text alone falls to `KIND_UNCERTAIN`."""
    rows = [
        [tok("Synthetic", 100.0), tok("Banking", 170.0), tok("App", 230.0)],
        [tok("Available", 100.0), tok("Balance", 170.0)],
        [tok(cents(123_400), 100.0)],
        [],
        [tok("Transfer", 100.0), tok("Pay", 200.0), tok("bills", 230.0), tok("Deposit", 300.0)],
    ]
    page = make_page(rows, width_pt=SCREEN_W, height_pt=SCREEN_H, top=100.0, line_height=30.0)
    ev = Expect("NOT_A_STATEMENT", "screenshot", "structural", frozenset({"screenshot_frame"}), absent_signals=frozenset({"table_run"}))
    tx = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset(), absent_signals=frozenset({"screenshot_frame"}))
    return _fixture("screenshot_image", [page], expect_evidence=ev, expect_text=tx, classification="scanned",
                    pixel_dpi=72, image=True)


def file_invalid_java() -> LayoutFixture:
    """The Java-serialisation magic. The profile alone decides; to prove it
    is decided FIRST (mutant M10), the fixture also hands the classifier a
    complete statement's page texts, which must change nothing."""
    statement = statement_pages(lang="en")
    texts = texts_from_pages(statement)
    profile = DocumentProfileFacts(valid_pdf=False, encrypted=False, page_count=0, classification="unknown",
                                   page_text_chars=(), magic=JAVA_MAGIC_BYTES.hex().upper())
    ex = Expect("FILE_INVALID", None, "structural", frozenset({"file_invalid_fact"}),
                absent_signals=frozenset({"period_expression", "table_run"}), modality="unknown")
    return LayoutFixture(
        name="file_invalid_java", pages=tuple(statement), evidence=None, page_texts=texts, profile=profile,
        expect_evidence=None, expect_text=ex, native_pdf=None,
        extra={"file_bytes": JAVA_MAGIC_BYTES + bytes(64)},
    )


def conflict_table_and_cheque() -> LayoutFixture:
    """Mutant M6's killer: a cheque-shaped page (MICR band + aspect) that also
    carries an aligned five-row dated money table. Two signals that cannot
    both be true of one document → `KIND_UNCERTAIN`, never a priority pick."""
    rows: list[list[Tok]] = [
        [tok("SYNTHETIC", LEFT), tok("PAYER", LEFT + 70.0), tok("PAY", CHEQUE_W - 260.0), tok("TO", CHEQUE_W - 230.0),
         tok("THE", CHEQUE_W - 210.0), tok("ORDER", CHEQUE_W - 180.0), tok("OF", CHEQUE_W - 140.0)],
    ]
    balance = 50_000
    for i in range(5):
        amount = 1_000 * (i + 1)
        balance += amount
        rows.append([tok(_date(2 + i, 3, "en"), LEFT), tok("row", LEFT + 80.0), rtok(cents(amount), CHEQUE_W - 200.0),
                     rtok(cents(balance), CHEQUE_W - 60.0)])
    page = make_page(rows, width_pt=CHEQUE_W, height_pt=CHEQUE_H, top=30.0, line_height=22.0)
    from tests.layout_fixtures.builders import line_at

    micr_line = line_at(CHEQUE_H - 10.0, [tok(MICR_LINE, LEFT)])
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=page.lines + (micr_line,))
    ev = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset({"table_run", "table_alignment", "micr_band", "cheque_aspect"}))
    tx = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset({"table_run", "micr_shape", "cheque_lexicon"}))
    return _fixture("conflict_table_and_cheque", [page], expect_evidence=ev, expect_text=tx, classification="scanned",
                    pixel_dpi=300)


def conflict_card_and_running_balance() -> LayoutFixture:
    ex = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset({"card_lexicon", "running_balance", "table_run"}))
    return _fixture("conflict_card_and_running_balance", [make_page(_card_rows(running_balance=True))],
                    expect_evidence=ex, expect_text=ex, note="the card lexicon beside a running balance")


# ---------------------------------------------------------------------------
# regression pins for the layout classes the archive taught the rules
# (each is a GENERIC shape, never a document): stacked summary cells, wrapped
# rows, a balance printed at intervals, an overdraft line-of-credit box on a
# deposit statement, a MICR-shaped line on a page that carries the table
# ---------------------------------------------------------------------------

def statement_stacked_summary_cells() -> LayoutFixture:
    """A summary box whose labels are two-line cells ("Opening" over
    "balance ($)"); the values row sits below the box. Neither "opening
    balance" nor "closing balance" is a contiguous phrase anywhere."""
    rows: list[list[Tok]] = [
        [tok("SYNTHETIC", LEFT), tok("CHEQUING", LEFT + 70.0), tok("ACCOUNT", LEFT + 135.0)],
        [tok("Statement", LEFT), tok("Period:", LEFT + 65.0), tok(_date(1, 3, "en"), LEFT + 120.0), tok("to", LEFT + 200.0),
         tok(_date(31, 3, "en"), LEFT + 230.0)],
        [],
        [tok("Opening", LEFT), tok("Total", LEFT + 120.0), tok("Total", LEFT + 240.0), tok("Closing", LEFT + 360.0)],
        [tok("balance", LEFT), tok("($)", LEFT + 55.0), tok("deposits", LEFT + 120.0), tok("($)", LEFT + 180.0),
         tok("withdrawals", LEFT + 240.0), tok("($)", LEFT + 320.0), tok("balance", LEFT + 360.0), tok("($)", LEFT + 415.0)],
        [rtok(cents(50_000), LEFT + 100.0), rtok(cents(15_000), LEFT + 220.0), rtok(cents(5_000), LEFT + 340.0),
         rtok(cents(60_000), LEFT + 460.0)],
        [],
        [tok("DATE", X_DATE), tok("DESCRIPTION", X_DESC), rtok("AMOUNT", R_AMOUNT), rtok("BALANCE", R_BALANCE)],
    ]
    balance = 50_000
    for i, amount in enumerate((5_000, -2_000, 4_000, -1_000, 4_000)):
        balance += amount
        rows.append([tok(_date(2 + i, 3, "en"), X_DATE), tok("Synthetic", X_DESC), tok("item", X_DESC + 70.0),
                     rtok(cents(abs(amount)), R_AMOUNT), rtok(cents(balance), R_BALANCE)])
    rows.append([])
    rows.append([tok("Page", LEFT), tok("1", LEFT + 40.0), tok("of", LEFT + 60.0), tok("1", LEFT + 90.0)])
    ev, tx = _complete()
    return _fixture("statement_stacked_summary_cells", [make_page(rows)], expect_evidence=ev, expect_text=tx)


def statement_wrapped_rows() -> LayoutFixture:
    """Two pages; on page 2 the first rows print the date and description
    on one line and the amount and balance on the next (wrapped rows). The
    running balance is continuous across the page break, so no
    discontinuity may be accused."""
    pages = statement_pages(n_rows=10, n_pages=2)
    second = pages[1]
    # rebuild page 2: split its first two ledger rows into two lines each
    from tests.layout_fixtures.builders import line_at

    new_lines = []
    split = 0
    for line in second.lines:
        texts = [w.text for w in line.words]
        is_row = any(find_iso(t) for t in texts[:1]) and split < 2
        if is_row:
            y = line.words[0].y1
            new_lines.append(line_at(y, [Tok(w.text, w.x0) for w in line.words[:2]]))
            new_lines.append(line_at(y + 9.0, [Tok(w.text, w.x0) for w in line.words[2:]]))
            split += 1
        else:
            new_lines.append(line)
    second = SyntheticPage(width_pt=second.width_pt, height_pt=second.height_pt, lines=tuple(new_lines))
    ev, tx = _complete()
    ev = Expect(**{**ev.__dict__, "absent_findings": frozenset({"balance_discontinuity_at_page_break"})})
    tx = Expect(**{**tx.__dict__, "absent_findings": frozenset({"balance_discontinuity_at_page_break"})})
    return _fixture("statement_wrapped_rows", [pages[0], second], expect_evidence=ev, expect_text=tx)


def find_iso(text: str) -> bool:
    return len(text) == 10 and text[4] == "/" or (len(text) == 10 and text[2] == "/")


def statement_balance_at_intervals() -> LayoutFixture:
    """The balance is printed only on the last row of each page; every
    other row carries the amount alone. Such a layout cannot be checked
    at the page break and must not be accused of a discontinuity."""
    pages = statement_pages(n_rows=10, n_pages=2)
    rebuilt = []
    for page in pages:
        from tests.layout_fixtures.builders import line_at

        lines = list(page.lines)
        row_indices = [i for i, line in enumerate(lines) if find_iso(line.words[0].text)]
        for i in row_indices[:-1]:
            line = lines[i]
            lines[i] = line_at(line.words[0].y1, [Tok(w.text, w.x0) for w in line.words[:-1]])   # drop the balance
        rebuilt.append(SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=tuple(lines)))
    ex = Expect("STATEMENT_COMPLETE", None, "structural", frozenset({"table_run", "table_alignment"}),
                absent_findings=frozenset({"balance_discontinuity_at_page_break"}), absent_signals=frozenset({"running_balance"}))
    tx = Expect("STATEMENT_COMPLETE", None, "lexical", frozenset({"table_run"}),
                absent_findings=frozenset({"balance_discontinuity_at_page_break"}), absent_signals=frozenset({"running_balance"}))
    return _fixture("statement_balance_at_intervals", rebuilt, expect_evidence=ex, expect_text=tx)


def statement_with_overdraft_line_box() -> LayoutFixture:
    """A chequing statement with an overdraft line-of-credit box (credit
    limit, credit line, annual percentage rate) beside a running balance:
    line-of-credit furniture is not the card lexicon, and the statement
    stays complete with account_kind deposit."""
    pages = statement_pages(n_rows=8, n_pages=1)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    extra = (
        line_at(page.height_pt - 120.0, [tok("Overdraft", LEFT), tok("line", LEFT + 65.0), tok("of", LEFT + 95.0),
                                          tok("credit", LEFT + 115.0)]),
        line_at(page.height_pt - 102.0, [tok("Credit", LEFT), tok("limit", LEFT + 45.0), rtok(cents(100_000), R_BALANCE)]),
        line_at(page.height_pt - 84.0, [tok("Credit", LEFT), tok("line", LEFT + 45.0), tok("annual", LEFT + 85.0),
                                         tok("percentage", LEFT + 130.0), tok("rate", LEFT + 205.0), rtok("12.0%", R_BALANCE)]),
    )
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=page.lines + extra)
    ev, tx = _complete()
    ev = Expect(**{**ev.__dict__, "absent_signals": frozenset({"card_lexicon"})})
    tx = Expect(**{**tx.__dict__, "absent_signals": frozenset({"card_lexicon", "table_alignment"})})
    return _fixture("statement_with_overdraft_line_box", [page], expect_evidence=ev, expect_text=tx)


def statement_with_micr_on_table_page() -> LayoutFixture:
    """A MICR-shaped line printed on a page that carries the transaction
    table (a cheque image reproduced under the ledger): the page is not a
    cheque page, so there is no table-versus-cheque conflict."""
    pages = statement_pages(n_rows=8, n_pages=1)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    micr = line_at(page.height_pt - 60.0, [tok(MICR_LINE, LEFT)])
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=page.lines + (micr,))
    ev, tx = _complete()
    return _fixture("statement_with_micr_on_table_page", [page], expect_evidence=ev, expect_text=tx)


def statement_from_to_header_line() -> LayoutFixture:
    """A merged header row: `Statement of: … From: <date> Account: … To:
    <date>` — the two dates are on one line but separated by other cells,
    so no connector joins them; the FROM / TO labels with two full dates
    make the period."""
    pages = statement_pages(lang="en", period=False)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    header = line_at(TOP_MARGIN - 20.0, [tok("Statement", LEFT), tok("of:", LEFT + 65.0), tok("From:", LEFT + 100.0),
                                          tok(_date(1, 3, "en"), LEFT + 140.0), tok("Account:", LEFT + 220.0),
                                          tok("SYN-1", LEFT + 280.0), tok("To:", LEFT + 330.0), tok(_date(31, 3, "en"), LEFT + 355.0)])
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=(header,) + page.lines)
    ev, tx = _complete()
    return _fixture("statement_from_to_header_line", [page], expect_evidence=ev, expect_text=tx)


def statement_with_cheque_image_page() -> LayoutFixture:
    """A complete statement followed by a cheque-image enclosure page: a
    letter-size page carrying the payee line and a MICR-shaped line. The
    document is statement-shaped, so the enclosure is not a second kind
    and no table-versus-cheque conflict is raised."""
    pages = statement_pages(lang="en", n_pages=1, page_markers=False)
    enclosure = _cheque_page(_cheque_rows(micr=True, void=False), micr=True, width=PAGE_WIDTH_PT, height=PAGE_HEIGHT_PT)
    ev, tx = _complete()
    ev = Expect(**{**ev.__dict__, "signals": ev.signals - {"page_marker"}, "absent_signals": frozenset()})
    tx = Expect(**{**tx.__dict__, "signals": tx.signals - {"page_marker"}})
    return _fixture("statement_with_cheque_image_page", pages + [enclosure], expect_evidence=ev, expect_text=tx)


def statement_wrapped_rows_everywhere() -> LayoutFixture:
    """Every ledger row is two lines: the date and description on one, the
    amount and balance on the next. No line carries a date and money
    together; the wrapped-row model still sees a table."""
    pages = statement_pages(n_rows=8, n_pages=1)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    new_lines = []
    for line in page.lines:
        if find_iso(line.words[0].text):
            y = line.words[0].y1
            new_lines.append(line_at(y, [Tok(w.text, w.x0) for w in line.words[:-2]]))
            new_lines.append(line_at(y + 9.0, [Tok(w.text, w.x0) for w in line.words[-2:]]))
        else:
            new_lines.append(line)
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=tuple(new_lines))
    ev, tx = _complete()
    return _fixture("statement_wrapped_rows_everywhere", [page], expect_evidence=ev, expect_text=tx)


def statement_debit_credit_no_balance() -> LayoutFixture:
    """Two money columns (withdrawals and deposits) and NO balance column:
    each row carries one money token in one of two right-aligned columns,
    so the table is confirmed by the two columns together."""
    pages = statement_pages(n_rows=8, n_pages=1, columns="debit_credit_balance")
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    new_lines = []
    for line in page.lines:
        if find_iso(line.words[0].text):
            new_lines.append(line_at(line.words[0].y1, [Tok(w.text, w.x0) for w in line.words[:-1]]))   # drop the balance
        else:
            new_lines.append(line)
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=tuple(new_lines))
    ex = Expect("STATEMENT_COMPLETE", None, "structural", frozenset({"table_run", "table_alignment"}),
                absent_signals=frozenset({"running_balance"}), account_kind="deposit")
    tx = Expect("STATEMENT_COMPLETE", None, "lexical", frozenset({"table_run"}),
                absent_signals=frozenset({"running_balance", "table_alignment"}), account_kind="deposit")
    return _fixture("statement_debit_credit_no_balance", [page], expect_evidence=ex, expect_text=tx)


def statement_label_interrupted_by_date() -> LayoutFixture:
    """The opening label's words with a date cell grouped between them
    ("Beginning <date> balance on … $"), and a merged summary row whose
    values sit to the right on the same line ("Ending credits (+) balance
    deposits <v> <v>"): labels are read on the words alone; a merged
    header may carry its values after the phrase."""
    pages = statement_pages(lang="en", opening=False, closing=False)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    extra = (
        line_at(TOP_MARGIN - 30.0, [tok("Beginning", LEFT), tok(_date(1, 3, "en"), LEFT + 70.0), tok("balance", LEFT + 150.0),
                                     tok("on", LEFT + 205.0), rtok(cents(OPENING_CENTS), R_BALANCE)]),
        line_at(TOP_MARGIN - 12.0, [tok("Ending", LEFT), tok("credits", LEFT + 60.0), tok("(+)", LEFT + 115.0),
                                     tok("balance", LEFT + 150.0), tok("deposits", LEFT + 205.0),
                                     rtok(cents(15_000), R_AMOUNT), rtok(cents(OPENING_CENTS + 5_000), R_BALANCE)]),
    )
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=extra + page.lines)
    ev, tx = _complete()
    return _fixture("statement_label_interrupted_by_date", [page], expect_evidence=ev, expect_text=tx)


def statement_short_three_rows() -> LayoutFixture:
    """A complete statement with THREE transactions: too few rows for the
    table signal, still a printed ledger between the three anchors."""
    pages = statement_pages(lang="en", n_rows=3, n_pages=1)
    ex = Expect("STATEMENT_COMPLETE", None, "lexical", frozenset({"period_expression", "opening_balance_label",
                                                                  "closing_balance_label", "short_ledger"}),
                absent_signals=frozenset({"table_run", "table_alignment"}), account_kind="deposit")
    return _fixture("statement_short_three_rows", pages, expect_evidence=ex, expect_text=ex)


def statement_unmarked_middle_page() -> LayoutFixture:
    """Three pages, `Page 1 of 3` and `Page 3 of 3` printed, the middle page
    carrying no marker at all: the numbers advance by exactly the pages
    present, so there is no gap."""
    pages = statement_pages(n_rows=12, n_pages=3)
    from tests.layout_fixtures.builders import line_at

    middle = pages[1]
    kept = tuple(line for line in middle.lines if not line.text.lower().startswith("page "))
    middle = SyntheticPage(width_pt=middle.width_pt, height_pt=middle.height_pt, lines=kept)
    ev, tx = _complete()
    ev = Expect(**{**ev.__dict__, "absent_findings": frozenset({"page_gap", "missing_pages"})})
    tx = Expect(**{**tx.__dict__, "absent_findings": frozenset({"page_gap", "missing_pages"})})
    return _fixture("statement_unmarked_middle_page", [pages[0], middle, pages[2]], expect_evidence=ev, expect_text=tx)


def statement_two_statements_one_file() -> LayoutFixture:
    """Two complete statements bound into one file: the markers run
    `1 of 1` then `1 of 1` again — a clean restart, not a gap."""
    first = statement_pages(lang="en", n_rows=6, n_pages=1)
    second = statement_pages(lang="en", n_rows=6, n_pages=1)
    ev, tx = _complete()
    ev = Expect(**{**ev.__dict__, "absent_findings": frozenset({"page_gap"})})
    tx = Expect(**{**tx.__dict__, "absent_findings": frozenset({"page_gap"})})
    return _fixture("statement_two_statements_one_file", first + second, expect_evidence=ev, expect_text=tx)


def statement_balance_pair_no_rows() -> LayoutFixture:
    """Opening and closing balance equal to the cent and no ledger row, with
    no printed declaration: the zero-activity STRUCTURE."""
    rows = [
        [tok("SYNTHETIC", LEFT), tok("SAVINGS", LEFT + 70.0), tok("ACCOUNT", LEFT + 130.0), tok("STATEMENT", LEFT + 195.0)],
        [tok("Statement", LEFT), tok("Period:", LEFT + 65.0), tok(_date(1, 3, "en"), LEFT + 120.0), tok("to", LEFT + 200.0),
         tok(_date(31, 3, "en"), LEFT + 230.0)],
        [tok("Beginning", LEFT), tok("Balance", LEFT + 65.0), rtok(cents(OPENING_CENTS), R_BALANCE)],
        [tok("Ending", LEFT), tok("Balance", LEFT + 50.0), rtok(cents(OPENING_CENTS), R_BALANCE)],
        [],
        [tok("Page", LEFT), tok("1", LEFT + 40.0), tok("of", LEFT + 60.0), tok("1", LEFT + 90.0)],
    ]
    ex = Expect("STATEMENT_COMPLETE", None, "lexical", frozenset({"period_expression", "opening_balance_label",
                                                                  "closing_balance_label", "balance_pair_coincides"}),
                absent_signals=frozenset({"table_run", "short_ledger", "zero_activity_declaration"}))
    return _fixture("statement_balance_pair_no_rows", [make_page(rows)], expect_evidence=ex, expect_text=ex)


def statement_label_variants() -> LayoutFixture:
    """The `Beginning statement balance` / `Ending statement balance` and
    `Balance last statement` / `Balance this statement` label forms."""
    pages = statement_pages(lang="en", opening=False, closing=False, n_rows=6)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    extra = (
        line_at(TOP_MARGIN - 30.0, [tok("Beginning", LEFT), tok("statement", LEFT + 65.0), tok("balance", LEFT + 130.0),
                                     rtok(cents(OPENING_CENTS), R_BALANCE)]),
        line_at(TOP_MARGIN - 12.0, [tok("Balance", LEFT), tok("this", LEFT + 55.0), tok("statement", LEFT + 85.0),
                                     rtok(cents(OPENING_CENTS + 5_000), R_BALANCE)]),
    )
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=extra + page.lines)
    ev, tx = _complete()
    return _fixture("statement_label_variants", [page], expect_evidence=ev, expect_text=tx)


def statement_dated_labels_after_a_dateless_header() -> LayoutFixture:
    """The closing label appears first as a dateless column header
    ("Ending statement balance" over a value), then the summary prints
    `<date> Beginning balance <v>` and `<date> Ending balance <v>`; no
    period phrase anywhere. The dates beside the labels are the period."""
    pages = statement_pages(lang="en", period=False, opening=False, closing=False, n_rows=6)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    extra = (
        line_at(TOP_MARGIN - 48.0, [tok("Account", LEFT), tok("type", LEFT + 55.0), tok("Ending", LEFT + 200.0),
                                     tok("statement", LEFT + 245.0), tok("balance", LEFT + 310.0)]),
        line_at(TOP_MARGIN - 30.0, [tok("Synthetic", LEFT), tok("chequing", LEFT + 65.0), rtok(cents(OPENING_CENTS + 5_000), R_BALANCE)]),
        line_at(TOP_MARGIN - 12.0, [tok(_date(1, 3, "en"), LEFT), tok("Beginning", LEFT + 80.0), tok("balance", LEFT + 145.0),
                                     rtok(cents(OPENING_CENTS), R_BALANCE)]),
        line_at(TOP_MARGIN + 6.0, [tok(_date(31, 3, "en"), LEFT), tok("Ending", LEFT + 80.0), tok("balance", LEFT + 125.0),
                                    rtok(cents(OPENING_CENTS + 5_000), R_BALANCE)]),
    )
    shifted = tuple(line for line in page.lines)
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=extra + shifted)
    ev, tx = _complete()
    return _fixture("statement_dated_labels_after_a_dateless_header", [page], expect_evidence=ev, expect_text=tx)


def statement_statement_ending_phrase() -> LayoutFixture:
    """`Statement ending <date>` is the only period form printed."""
    pages = statement_pages(lang="en", period=False, n_rows=6)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    header = line_at(TOP_MARGIN - 20.0, [tok("Statement", LEFT), tok("ending", LEFT + 65.0), tok(_date(31, 3, "en"), LEFT + 115.0)])
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=(header,) + page.lines)
    ev, tx = _complete()
    return _fixture("statement_statement_ending_phrase", [page], expect_evidence=ev, expect_text=tx)


def statement_last_this_statement_dates() -> LayoutFixture:
    """`Last statement: <date>  Page 1 of 1` over `This statement: <date>`:
    a stacked date range whose first line also carries the page marker."""
    pages = statement_pages(lang="en", period=False, page_markers=False, n_rows=6)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    extra = (
        line_at(TOP_MARGIN - 38.0, [tok("Last", LEFT), tok("statement:", LEFT + 35.0), tok(_date(1, 3, "en"), LEFT + 110.0),
                                     tok("Page", LEFT + 300.0), tok("1", LEFT + 340.0), tok("of", LEFT + 360.0), tok("1", LEFT + 390.0)]),
        line_at(TOP_MARGIN - 20.0, [tok("This", LEFT), tok("statement:", LEFT + 35.0), tok(_date(31, 3, "en"), LEFT + 110.0)]),
    )
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=extra + page.lines)
    ev, tx = _complete()
    return _fixture("statement_last_this_statement_dates", [page], expect_evidence=ev, expect_text=tx)


def statement_stacked_range_with_page_marker() -> LayoutFixture:
    """A stacked date-range cell whose first line also carries the page
    marker and no period phrase at all: `Cycle start date: <date> Page 1 of
    1` over `Cycle end date: <date>`. The marker's words are not words of
    the cell."""
    pages = statement_pages(lang="en", period=False, page_markers=False, n_rows=6)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    extra = (
        line_at(TOP_MARGIN - 38.0, [tok("Cycle", LEFT), tok("start", LEFT + 40.0), tok("date:", LEFT + 80.0), tok(_date(1, 3, "en"), LEFT + 120.0),
                                     tok("Page", LEFT + 300.0), tok("1", LEFT + 340.0), tok("of", LEFT + 360.0), tok("1", LEFT + 390.0)]),
        line_at(TOP_MARGIN - 20.0, [tok("Cycle", LEFT), tok("end", LEFT + 40.0), tok("date:", LEFT + 70.0), tok(_date(31, 3, "en"), LEFT + 110.0)]),
    )
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=extra + page.lines)
    ev, tx = _complete()
    return _fixture("statement_stacked_range_with_page_marker", [page], expect_evidence=ev, expect_text=tx)


# ---------------------------------------------------------------------------
# the adversarial review's findings (PHASE2_P22CLASSIFY_REVIEW.md)
# ---------------------------------------------------------------------------

def card_statement_with_deposit_word() -> LayoutFixture:
    """MAJOR-1: the card statement plus one autopay line naming a deposit
    account — the ruled conflict, `KIND_UNCERTAIN`, never a deposit statement."""
    rows = _card_rows(running_balance=False)
    page = make_page(rows)
    from tests.layout_fixtures.builders import line_at

    autopay = line_at(page.height_pt - 60.0, [tok("Autopay", LEFT), tok("from", LEFT + 55.0), tok("checking", LEFT + 90.0)])
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=page.lines + (autopay,))
    ex = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset({"card_lexicon", "deposit_lexicon", "table_run"}))
    return _fixture("card_statement_with_deposit_word", [page], expect_evidence=ex, expect_text=ex)


def statement_with_strong_card_phrase_in_loc_box() -> LayoutFixture:
    """MAJOR-1, the other direction: a chequing statement (withdrawals /
    deposits columns, no balance column) whose overdraft line-of-credit box
    prints a STRONG card phrase. The recorded decision: the pair is a
    conflict and the document is `KIND_UNCERTAIN` for the adjudicator."""
    pages = statement_pages(n_rows=8, n_pages=1, columns="debit_credit_balance")
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    new_lines = []
    for line in page.lines:
        if find_iso(line.words[0].text):
            new_lines.append(line_at(line.words[0].y1, [Tok(w.text, w.x0) for w in line.words[:-1]]))   # drop the balance
        else:
            new_lines.append(line)
    extra = (
        line_at(page.height_pt - 120.0, [tok("Overdraft", LEFT), tok("line", LEFT + 65.0), tok("of", LEFT + 95.0), tok("credit", LEFT + 115.0)]),
        line_at(page.height_pt - 102.0, [tok("Minimum", LEFT), tok("payment", LEFT + 55.0), tok("due", LEFT + 110.0), rtok(cents(2_500), R_BALANCE)]),
        line_at(page.height_pt - 84.0, [tok("Credit", LEFT), tok("limit", LEFT + 45.0), rtok(cents(100_000), R_BALANCE)]),
    )
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=tuple(new_lines) + extra)
    ex = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset({"card_lexicon", "deposit_lexicon", "table_run"}),
                absent_signals=frozenset({"running_balance"}))
    return _fixture("statement_with_strong_card_phrase_in_loc_box", [page], expect_evidence=ex, expect_text=ex)


def statement_with_page_cross_reference() -> LayoutFixture:
    """MINOR-1: page 1 of a complete three-page statement prints "See page
    2 of 3 for fees" ABOVE its footer; the footer marker still wins."""
    pages = statement_pages(n_rows=12, n_pages=3)
    first = pages[0]
    from tests.layout_fixtures.builders import line_at

    lines = list(first.lines)
    footer_index = next(i for i, line in enumerate(lines) if line.text.lower().startswith("page "))
    y = lines[footer_index].words[0].y1 - 9.0
    prose = line_at(y, [tok("See", LEFT), tok("page", LEFT + 30.0), tok("2", LEFT + 65.0), tok("of", LEFT + 80.0), tok("3", LEFT + 100.0),
                        tok("for", LEFT + 115.0), tok("fees", LEFT + 140.0)])
    lines.insert(footer_index, prose)
    first = SyntheticPage(width_pt=first.width_pt, height_pt=first.height_pt, lines=tuple(lines))
    ev, tx = _complete()
    ev = Expect(**{**ev.__dict__, "absent_findings": frozenset({"page_gap", "missing_pages"})})
    tx = Expect(**{**tx.__dict__, "absent_findings": frozenset({"page_gap", "missing_pages"})})
    return _fixture("statement_with_page_cross_reference", [first, pages[1], pages[2]], expect_evidence=ev, expect_text=tx)


def statement_period_only_in_a_row() -> LayoutFixture:
    """MINOR-4: no period anywhere except a ledger row's own `<date> -
    <date>` hold description — that is not the statement period."""
    pages = statement_pages(lang="en", period=False, n_rows=6)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    lines = list(page.lines)
    last_row = max(i for i, line in enumerate(lines) if find_iso(line.words[0].text))
    y = lines[last_row].words[0].y1 + 18.0
    hold = line_at(y, [tok(_date(9, 3, "en"), X_DATE), tok("HOLD", X_DESC), tok(_date(9, 3, "en"), X_DESC + 40.0), tok("-", X_DESC + 115.0),
                       tok(_date(12, 3, "en"), X_DESC + 130.0), rtok(cents(1_000), R_AMOUNT), rtok(cents(OPENING_CENTS), R_BALANCE)])
    lines.insert(last_row + 1, hold)
    shifted = []
    for i, line in enumerate(lines):
        if i > last_row + 1:
            shifted.append(line_at(line.words[0].y1 + 18.0, [Tok(w.text, w.x0) for w in line.words]))
        else:
            shifted.append(line)
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=tuple(shifted))
    ex = Expect("STATEMENT_PARTIAL", None, "lexical", frozenset({"opening_balance_label", "closing_balance_label", "table_run"}),
                findings=frozenset({"missing_period"}), absent_signals=frozenset({"period_expression"}))
    return _fixture("statement_period_only_in_a_row", [page], expect_evidence=ex, expect_text=ex)


def statement_thin_digital_summary() -> LayoutFixture:
    """MINOR-3: the illegible fixture's pages with a DIGITAL profile — a
    native text layer cannot be illegible; the ledger is simply missing."""
    thin = statement_illegible()
    ex = Expect("STATEMENT_PARTIAL", None, "lexical", frozenset({"period_expression", "opening_balance_label", "closing_balance_label"}),
                findings=frozenset({"table_truncated"}), absent_signals=frozenset({"illegible_floor"}))
    return _fixture("statement_thin_digital_summary", list(thin.pages), expect_evidence=ex, expect_text=ex, classification="digital")


def statement_three_rotating_columns() -> LayoutFixture:
    """MINOR-7: each row carries ONE money token, rotating over three
    right-aligned columns (deposits, withdrawals, daily balance)."""
    pages = statement_pages(n_rows=9, n_pages=1)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    edges = (R_DEBIT, R_CREDIT, R_BALANCE)
    new_lines = []
    n = 0
    for line in page.lines:
        if find_iso(line.words[0].text):
            keep = [Tok(w.text, w.x0) for w in line.words[:-2]]
            amount = line.words[-2].text
            keep.append(Tok(amount, edges[n % 3] - len(amount) * 6.6))
            new_lines.append(line_at(line.words[0].y1, keep))
            n += 1
        else:
            new_lines.append(line)
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=tuple(new_lines))
    ev = Expect("STATEMENT_COMPLETE", None, "structural", frozenset({"table_run", "table_alignment"}), absent_signals=frozenset({"running_balance"}))
    tx = Expect("STATEMENT_COMPLETE", None, "lexical", frozenset({"table_run"}), absent_signals=frozenset({"running_balance", "table_alignment"}))
    return _fixture("statement_three_rotating_columns", [page], expect_evidence=ev, expect_text=tx)


def statement_hyphen_joined_dates() -> LayoutFixture:
    """MINOR-11: `STATEMENT DATES <date>-<date>` with no space around the
    hyphen is the only period form printed."""
    pages = statement_pages(lang="en", period=False, n_rows=6)
    page = pages[0]
    from tests.layout_fixtures.builders import line_at

    header = line_at(TOP_MARGIN - 20.0, [tok("STATEMENT", LEFT), tok("DATES", LEFT + 70.0),
                                          tok(_date(1, 3, "en") + "-" + _date(31, 3, "en"), LEFT + 115.0)])
    page = SyntheticPage(width_pt=page.width_pt, height_pt=page.height_pt, lines=(header,) + page.lines)
    ev, tx = _complete()
    return _fixture("statement_hyphen_joined_dates", [page], expect_evidence=ev, expect_text=tx)


def two_statements_second_truncated() -> LayoutFixture:
    """MINOR-2: a complete one-page statement followed by page 1 of 3 of a
    second statement — the second sequence owes two pages."""
    first = statement_pages(lang="en", n_rows=6, n_pages=1)
    second = statement_pages(lang="en", n_rows=12, n_pages=3)[:1]
    ex = Expect("STATEMENT_PARTIAL", None, "structural", frozenset({"page_marker", "page_missing"}),
                findings=frozenset({"missing_pages"}), absent_findings=frozenset({"page_gap"}))
    return _fixture("two_statements_second_truncated", first + second, expect_evidence=ex, expect_text=ex)


def nothing_fires() -> LayoutFixture:
    rows = [
        [tok("SYNTHETIC", LEFT), tok("MEETING", LEFT + 70.0), tok("NOTES", LEFT + 130.0)],
        [tok("Agenda", LEFT), tok("item", LEFT + 50.0), tok("one", LEFT + 85.0)],
        [tok("Agenda", LEFT), tok("item", LEFT + 50.0), tok("two", LEFT + 85.0)],
        [tok("Action", LEFT), tok("items", LEFT + 50.0)],
    ]
    ex = Expect("KIND_UNCERTAIN", None, "uncertain", frozenset())
    return _fixture("nothing_fires", [make_page(rows)], expect_evidence=ex, expect_text=ex)


FIXTURES: dict[str, Callable[[], LayoutFixture]] = {
    "statement_complete_en": statement_complete_en,
    "statement_complete_fr": statement_complete_fr,
    "statement_complete_es": statement_complete_es,
    "statement_two_money_columns": statement_two_money_columns,
    "statement_single_signed_column": statement_single_signed_column,
    "statement_zero_activity": statement_zero_activity,
    "statement_rotated": statement_rotated,
    "partial_page_removed": partial_page_removed,
    "partial_last_page_removed": partial_last_page_removed,
    "partial_first_page_removed": partial_first_page_removed,
    "partial_opening_removed": partial_opening_removed,
    "partial_closing_removed": partial_closing_removed,
    "partial_period_removed": partial_period_removed,
    "partial_balance_discontinuity": partial_balance_discontinuity,
    "statement_illegible": statement_illegible,
    "activity_export": activity_export,
    "cheque_image": cheque_image,
    "cheque_no_micr": cheque_no_micr,
    "cheque_shape_nothing_else": cheque_shape_nothing_else,
    "cheque_portrait_micr": cheque_portrait_micr,
    "voided_cheque": voided_cheque,
    "deposit_slip": deposit_slip,
    "deposit_slip_cheque_shaped": deposit_slip_cheque_shaped,
    "letter_notice": letter_notice,
    "letter_with_unaligned_dated_lines": letter_with_unaligned_dated_lines,
    "card_statement": card_statement,
    "loan_statement": loan_statement,
    "brokerage_page": brokerage_page,
    "screenshot_image": screenshot_image,
    "file_invalid_java": file_invalid_java,
    "conflict_table_and_cheque": conflict_table_and_cheque,
    "conflict_card_and_running_balance": conflict_card_and_running_balance,
    "statement_stacked_summary_cells": statement_stacked_summary_cells,
    "statement_wrapped_rows": statement_wrapped_rows,
    "statement_balance_at_intervals": statement_balance_at_intervals,
    "statement_with_overdraft_line_box": statement_with_overdraft_line_box,
    "statement_with_micr_on_table_page": statement_with_micr_on_table_page,
    "statement_from_to_header_line": statement_from_to_header_line,
    "statement_with_cheque_image_page": statement_with_cheque_image_page,
    "statement_wrapped_rows_everywhere": statement_wrapped_rows_everywhere,
    "statement_debit_credit_no_balance": statement_debit_credit_no_balance,
    "statement_label_interrupted_by_date": statement_label_interrupted_by_date,
    "statement_short_three_rows": statement_short_three_rows,
    "statement_unmarked_middle_page": statement_unmarked_middle_page,
    "statement_two_statements_one_file": statement_two_statements_one_file,
    "statement_balance_pair_no_rows": statement_balance_pair_no_rows,
    "statement_label_variants": statement_label_variants,
    "statement_dated_labels_after_a_dateless_header": statement_dated_labels_after_a_dateless_header,
    "statement_statement_ending_phrase": statement_statement_ending_phrase,
    "statement_last_this_statement_dates": statement_last_this_statement_dates,
    "statement_stacked_range_with_page_marker": statement_stacked_range_with_page_marker,
    "card_statement_with_deposit_word": card_statement_with_deposit_word,
    "statement_with_strong_card_phrase_in_loc_box": statement_with_strong_card_phrase_in_loc_box,
    "statement_with_page_cross_reference": statement_with_page_cross_reference,
    "statement_period_only_in_a_row": statement_period_only_in_a_row,
    "statement_thin_digital_summary": statement_thin_digital_summary,
    "statement_three_rotating_columns": statement_three_rotating_columns,
    "statement_hyphen_joined_dates": statement_hyphen_joined_dates,
    "two_statements_second_truncated": two_statements_second_truncated,
    "nothing_fires": nothing_fires,
}


def names() -> list[str]:
    return list(FIXTURES)


def build(name: str) -> LayoutFixture:
    return FIXTURES[name]()
