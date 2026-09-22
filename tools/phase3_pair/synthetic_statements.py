"""Fabricated bank statements with known truth, for measuring the visual pair's reliability.

Every name, number and amount is fabricated and labelled so (FABRICATED ...). The layouts reproduce what
real statements do that has broken readings before: running balances, category summaries without a total
line, section subtotals, cheque-number tables, pages of cheque pictures, end-of-day balances, newest-first
listings, horizontal summary tables, scanned pages without a text layer, statements without printed totals,
and a negative control whose printed ending balance does not reconcile (it must be held).

    python -m tools.phase3_pair.synthetic_statements --out-dir <absolute folder outside the checkout>

writes <id>.pdf and <id>.truth.json for each statement and manifest.json (sha256 of every PDF).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PERIOD_START, PERIOD_END = date(2031, 3, 1), date(2031, 3, 31)
BANK = "FABRICATED FIRST NATIONAL BANK"
HOLDER = "FABRICATED HOLDINGS LLC"
ADDRESS = "100 EXAMPLE STREET, SPRINGFIELD ZZ 00000"
ACCOUNT = "0000-1111-2222"
CREDIT_DESCRIPTIONS = ("ACH CREDIT FABRICATED PAYROLL INC", "MOBILE DEPOSIT REF {n}",
                       "ONLINE TRANSFER FROM SAVINGS 000{n}", "DEPOSIT FABRICATED CUSTOMER {n}",
                       "WIRE TRANSFER IN FABRICATED TRADING CO")
DEBIT_DESCRIPTIONS = ("CARD PURCHASE FABRICATED HARDWARE #{n}", "CARD PURCHASE FABRICATED GROCERY {n}",
                      "ACH DEBIT FABRICATED UTILITIES CO", "ONLINE TRANSFER TO CHECKING 000{n}",
                      "ATM WITHDRAWAL FABRICATED BRANCH {n}", "ACH DEBIT FABRICATED INSURANCE CO",
                      "PAYMENT FABRICATED CARD SERVICES")


@dataclass
class Txn:
    when: date
    description: str
    amount: Decimal          # signed: credit positive, debit negative
    kind: str                # credit, debit, check, fee
    check_number: int | None = None

    @property
    def direction(self) -> str:
        return "credit" if self.amount > 0 else "debit"


@dataclass
class Plan:
    ident: str
    layout: str
    beginning: Decimal
    txns: list[Txn]
    expect_admitted: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def ending(self) -> Decimal:
        return self.beginning + sum((t.amount for t in self.txns), Decimal("0"))

    def totals(self):
        credits = [t for t in self.txns if t.amount > 0]
        debits = [t for t in self.txns if t.amount < 0]
        return (sum((t.amount for t in credits), Decimal("0")), -sum((t.amount for t in debits), Decimal("0")),
                len(credits), len(debits))


def money(value: Decimal) -> str:
    return f"{abs(value):,.2f}"


def _cents(rng: random.Random, low: int, high: int) -> Decimal:
    return Decimal(rng.randint(low * 100, high * 100)) / 100


def make_txns(rng: random.Random, count: int, *, checks: int = 0, fees: int = 1) -> list[Txn]:
    days = [PERIOD_START + timedelta(days=rng.randint(1, 29)) for _ in range(count + checks + fees)]
    days.sort()
    txns: list[Txn] = []
    check_number = 1040 + rng.randint(0, 50)
    kinds = ["credit"] * (count // 3) + ["debit"] * (count - count // 3) + ["check"] * checks + ["fee"] * fees
    rng.shuffle(kinds)
    for when, kind in zip(days, kinds):
        n = rng.randint(10, 99)
        if kind == "credit":
            txns.append(Txn(when, rng.choice(CREDIT_DESCRIPTIONS).format(n=n), _cents(rng, 150, 4800), kind))
        elif kind == "debit":
            txns.append(Txn(when, rng.choice(DEBIT_DESCRIPTIONS).format(n=n), -_cents(rng, 8, 1400), kind))
        elif kind == "check":
            check_number += rng.randint(1, 3)
            txns.append(Txn(when, f"CHECK {check_number}", -_cents(rng, 60, 1900), kind, check_number))
        else:
            txns.append(Txn(when, "MONTHLY SERVICE FEE", -Decimal("15.00"), kind))
    return txns


class Writer:
    """Plain PDF text at fixed columns, as most statements print them (with a text layer)."""

    def __init__(self, doc: fitz.Document):
        self.doc, self.page, self.y = doc, None, 0.0

    def new_page(self):
        self.page = self.doc.new_page(width=612, height=792)
        self.y = 48.0

    def text(self, x: float, value: str, *, size: float = 9, bold: bool = False, right: bool = False):
        font = "hebo" if bold else "helv"
        if right:
            x -= fitz.get_text_length(value, fontname=font, fontsize=size)
        self.page.insert_text((x, self.y), value, fontsize=size, fontname=font)

    def down(self, amount: float = 13):
        self.y += amount

    def room(self, lines: int = 1) -> bool:
        return self.y + 13 * lines < 750


def header(w: Writer, plan: Plan, page_number: int, pages: int):
    w.text(40, BANK, size=13, bold=True)
    w.text(572, f"Page {page_number} of {pages}", size=8, right=True)
    w.down(16)
    w.text(40, HOLDER)
    w.text(572, f"Account Number {ACCOUNT}", right=True)
    w.down()
    w.text(40, ADDRESS)
    w.text(572, "Statement Period March 1, 2031 through March 31, 2031", right=True)
    w.down(22)


def _running(plan: Plan) -> list[tuple[Txn, Decimal]]:
    balance, out = plan.beginning, []
    for txn in plan.txns:
        balance += txn.amount
        out.append((txn, balance))
    return out


def layout_running(plan: Plan, *, summary: str = "vertical", newest_first: bool = False, end_of_day: bool = False,
                   printed_ending: Decimal | None = None, rows_per_page: int = 24) -> bytes:
    credits, debits, credit_count, debit_count = plan.totals()
    ending = printed_ending if printed_ending is not None else plan.ending
    rows = _running(plan)
    if end_of_day:  # the balance only on the last row of each day
        rows = [(txn, balance if index + 1 == len(rows) or rows[index + 1][0].when != txn.when else None)
                for index, (txn, balance) in enumerate(rows)]
    if newest_first:
        rows = list(reversed(rows))
    chunks = [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)]
    doc = fitz.open()
    w = Writer(doc)
    for number, chunk in enumerate(chunks, 1):
        w.new_page()
        header(w, plan, number, len(chunks))
        if number == 1:
            w.text(40, "ACCOUNT SUMMARY", bold=True)
            w.down(15)
            if summary == "horizontal":
                labels = ("Previous Balance", "Deposits/Credits", "Withdrawals/Debits", "Ending Balance")
                values = (money(plan.beginning), money(credits), money(debits), money(ending))
                for x, label in zip((40, 180, 320, 460), labels):
                    w.text(x, label, bold=True)
                w.down()
                for x, value in zip((40, 180, 320, 460), values):
                    w.text(x, value)
                w.down(20)
            else:
                w.text(40, "Beginning Balance")
                w.text(300, money(plan.beginning), right=True)
                w.down()
                if summary == "vertical":
                    w.text(40, f"Deposits and Other Credits ({credit_count})")
                    w.text(300, money(credits), right=True)
                    w.down()
                    w.text(40, f"Withdrawals and Other Debits ({debit_count})")
                    w.text(300, money(debits) + "-", right=True)
                    w.down()
                w.text(40, "Ending Balance")
                w.text(300, money(ending), right=True)
                w.down(22)
        w.text(40, "TRANSACTION DETAIL", bold=True)
        w.down(14)
        for x, label, right in ((40, "Date", False), (90, "Description", False), (430, "Withdrawals", True),
                                (500, "Deposits", True), (572, "Balance", True)):
            w.text(x, label, bold=True, right=right)
        w.down(14)
        for txn, balance in chunk:
            w.text(40, txn.when.strftime("%m/%d"))
            w.text(90, txn.description)
            w.text(430 if txn.amount < 0 else 500, money(txn.amount), right=True)
            if balance is not None:
                w.text(572, money(balance), right=True)
            w.down()
    return doc.tobytes()


def _cheque_picture(txns: list[Txn]) -> bytes:
    """A page of cheque pictures, as an image: no text layer, like the scans banks print."""
    image = Image.new("RGB", (1700, 2000), "white")
    draw = ImageDraw.Draw(image)
    font, small = ImageFont.load_default(size=34), ImageFont.load_default(size=26)
    for index, txn in enumerate(txns[:6]):
        left, top = 60 + (index % 2) * 820, 80 + (index // 2) * 620
        draw.rectangle((left, top, left + 780, top + 360), outline="black", width=3)
        written = txn.when - timedelta(days=2)
        draw.text((left + 20, top + 20), HOLDER, fill="black", font=small)
        draw.text((left + 560, top + 20), f"No. {txn.check_number}", fill="black", font=small)
        draw.text((left + 520, top + 70), f"Date {written.strftime('%m/%d/%Y')}", fill="black", font=small)
        draw.text((left + 20, top + 130), "PAY TO THE ORDER OF", fill="black", font=small)
        draw.text((left + 20, top + 170), "FABRICATED PAYEE CO", fill="black", font=small)
        draw.rectangle((left + 520, top + 150, left + 760, top + 210), outline="black", width=2)
        draw.text((left + 535, top + 162), f"$ {money(txn.amount)}", fill="black", font=font)
        draw.text((left + 20, top + 300), f"{ACCOUNT}  {txn.check_number}", fill="black", font=small)
        draw.text((left + 20, top + 380), f"Check {txn.check_number}  {txn.when.strftime('%m/%d')}  "
                                          f"{money(txn.amount)}", fill="black", font=small)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def layout_categories(plan: Plan) -> bytes:
    """A summary of categories without a total line; each section prints its own subtotal; cheques are listed
    in a cheque-number table and pictured on the last page."""
    groups = {"Customer Deposits": [t for t in plan.txns if t.kind == "credit"],
              "Card Withdrawals": [t for t in plan.txns if t.kind == "debit"],
              "Checks Paid": [t for t in plan.txns if t.kind == "check"],
              "Service Fees": [t for t in plan.txns if t.kind == "fee"]}
    doc = fitz.open()
    w = Writer(doc)
    w.new_page()
    header(w, plan, 1, 3)
    w.text(40, "ACCOUNT SUMMARY", bold=True)
    w.down(15)
    w.text(40, "Beginning Balance on Mar 1")
    w.text(330, "$ " + money(plan.beginning), right=True)
    w.down()
    for label, txns in groups.items():
        total = sum((t.amount for t in txns), Decimal("0"))
        w.text(40, label)
        w.text(220, str(len(txns)), right=True)
        w.text(330, money(total) + ("-" if total < 0 else ""), right=True)
        w.down()
    w.text(40, "Ending Balance on Mar 31")
    w.text(330, "$ " + money(plan.ending), right=True)
    w.down(24)
    for label, txns in groups.items():
        if not w.room(len(txns) + 4):
            w.new_page()
            header(w, plan, 2, 3)
        w.text(40, label, bold=True)
        w.down(14)
        if label == "Checks Paid":
            for x, heading, right in ((40, "Check Nbr", False), (130, "Date", False), (330, "Amount", True)):
                w.text(x, heading, bold=True, right=right)
            w.down(14)
            for txn in txns:
                w.text(40, str(txn.check_number))
                w.text(130, txn.when.strftime("%m/%d"))
                w.text(330, money(txn.amount), right=True)
                w.down()
        else:
            for x, heading, right in ((40, "Date", False), (90, "Description", False), (430, "Amount", True)):
                w.text(x, heading, bold=True, right=right)
            w.down(14)
            for txn in txns:
                w.text(40, txn.when.strftime("%m/%d"))
                w.text(90, txn.description)
                w.text(430, money(txn.amount) + ("-" if txn.amount < 0 else ""), right=True)
                w.down()
        total = sum((t.amount for t in txns), Decimal("0"))
        w.text(40, f"Total {label}", bold=True)
        w.text(430, money(total) + ("-" if total < 0 else ""), right=True)
        w.down(22)
    if len(doc) < 2:
        w.new_page()
        header(w, plan, 2, 3)
        w.text(40, "Account messages: FABRICATED notice text only.")
    picture = doc.new_page(width=612, height=792)
    picture.insert_image(fitz.Rect(36, 36, 576, 756), stream=_cheque_picture(groups["Checks Paid"]))
    return doc.tobytes()


def scanned(pdf: bytes, *, seed: int) -> bytes:
    """Every page rasterised (no text layer), with light blur and noise, as a scanner would return it."""
    rng = random.Random(seed)
    source, out = fitz.open(stream=pdf, filetype="pdf"), fitz.open()
    for page in source:
        pix = page.get_pixmap(dpi=200)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
        image = image.rotate(rng.uniform(-0.4, 0.4), fillcolor=255, expand=False).filter(ImageFilter.GaussianBlur(0.6))
        noise = Image.effect_noise(image.size, 12).point(lambda value: 255 if value > 120 else 235)
        image = Image.composite(image, noise, image.point(lambda value: 255 if value < 200 else 0))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        target = out.new_page(width=page.rect.width, height=page.rect.height)
        target.insert_image(target.rect, stream=buffer.getvalue())
    return out.tobytes()


def plans(seed: int = 7) -> list[tuple[Plan, bytes]]:
    rng = random.Random(seed)
    built = []

    def add(ident, layout, beginning, txns, build, **kwargs):
        plan = Plan(ident, layout, Decimal(beginning), txns, **kwargs)
        built.append((plan, build(plan)))

    add("S01", "running_balance_vertical_summary", "1250.00", make_txns(rng, 38), layout_running)
    add("S02", "category_summary_sections_cheques_pictured", "2400.00", make_txns(rng, 20, checks=5),
        layout_categories)
    add("S03", "end_of_day_balances", "980.25", make_txns(rng, 34),
        lambda plan: layout_running(plan, end_of_day=True))
    add("S04", "newest_first", "3100.00", make_txns(rng, 28),
        lambda plan: layout_running(plan, newest_first=True))
    add("S05", "scanned_running_balance", "1500.00", make_txns(rng, 26),
        lambda plan: scanned(layout_running(plan), seed=seed))
    add("S06", "no_printed_totals", "750.00", make_txns(rng, 24),
        lambda plan: layout_running(plan, summary="none"))
    add("S07", "horizontal_summary", "2210.40", make_txns(rng, 28),
        lambda plan: layout_running(plan, summary="horizontal"))
    control = make_txns(rng, 24)
    add("S08", "negative_control_printed_ending_does_not_reconcile", "1800.00", control,
        lambda plan: layout_running(plan, printed_ending=plan.ending + Decimal("100.00")),
        expect_admitted=False, notes=["printed ending balance is 100.00 higher than the ledger"])
    return built


def truth(plan: Plan) -> dict:
    credits, debits, credit_count, debit_count = plan.totals()
    return {"id": plan.ident, "layout": plan.layout, "expect_admitted": plan.expect_admitted, "notes": plan.notes,
            "period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat(),
            "beginning_balance": float(plan.beginning), "ending_balance": float(plan.ending),
            "stated_total_credits": float(credits), "stated_total_debits": float(debits),
            "stated_credit_count": credit_count, "stated_debit_count": debit_count,
            "transactions": [{"date": t.when.isoformat(),
                              "description": f"Check {t.check_number}" if plan.layout.startswith("category")
                              and t.kind == "check" else t.description,
                              "amount": float(t.amount), "direction": t.direction} for t in plan.txns]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for plan, pdf in plans(args.seed):
        (args.out_dir / f"{plan.ident}.pdf").write_bytes(pdf)
        (args.out_dir / f"{plan.ident}.truth.json").write_text(json.dumps(truth(plan), indent=1), encoding="utf-8")
        files.append({"path": f"{plan.ident}.pdf", "sha256": hashlib.sha256(pdf).hexdigest()})
    manifest = {"version": 1, "data_scope": "synthetic", "seed": args.seed, "files": files}
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({"statements": len(files), "out_dir": str(args.out_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
