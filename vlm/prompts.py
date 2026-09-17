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
