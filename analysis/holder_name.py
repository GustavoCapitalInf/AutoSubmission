"""The account holder's name as a statement prints it in its mailing address block (audit B9: I13, I38).

A statement prints its holder twice over: once in the product line a parser has long published as `account_name` (a
product, a nickname, or nothing), and once in the mailing address block the bank prints for the envelope window. This
module reads the second. Two shapes are read:

* one line (`holder_from_address_line`): the name, an optional account designation, and the address, run together
  ('CONTOSO LLC DBA NORTHWIND AGENCY, LLC PREMIUM TRUST ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001'). The name ends
  where the address starts (a house number or a post-office box). What a bank prints after the name's legal form is the
  account's designation (a premium trust, an operating or a wire account, a syndicate), never the name; a name with no
  legal form loses only a trailing designation that ends in ACCOUNT.
* the block's lines (`holder_from_address_block`): the name lines before the first street line. The holder is the
  first; a second line that starts DBA is the holder's trade name and is kept with it. Any other second line (an
  owner's or a contact's name) is not the holder.

Both read nothing they cannot place: no address after the name, or no letter in it, is None. The readers carry no
memory of any statement's names; every bank keeps its own anchor (the line or block the reader is handed).

Audit round 2, R2-B05 (R04 part 2): the banks' readers read page 1 (`first_page`, the reading's own page marker), as
lines with their whitespace runs collapsed (`page_lines`), and close an address on a US state and ZIP code
(`CITY_STATE_ZIP`) or a Canadian province and postal code (`PROVINCE_POSTAL_CODE`).

Owner ruling 2026-10-02 (the underwriter's Q10), audit round 2, R2-OW10: each reader also returns the account title it
drops after the name, as a `HolderReading` (`read_address_line`, `read_address_block`, `read_name`,
`read_mailing_line_after`): what the line form cuts after the name's last legal form (or the trailing designation of a
name with no legal form), from the same tokens, and, in the block form, a name line the reader does not keep that prints
an account word or the premium-trust words (never an owner's, a contact's or a wrapped name line). The `holder_from_*`
readers are the readings' names, unchanged. A reading with no name has no title. The title is provenance for the
revenue rule; it is never part of the holder's name."""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple


class HolderReading(NamedTuple):
    """Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: one reading of a holder's line or block: the holder's name
    and the account title the bank prints after it (None when it prints none, or when no name is read)."""

    name: str | None
    title: str | None


#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: the reading of a line or block that names nobody.
NO_READING = HolderReading(None, None)

#: Audit round 2, R2-B05 (R04 part 2): the marker the statement reading prints before each page's text
#: (ocr.document.StatementMarkdown: '--- Page 1 ---', '--- Page 2 (empty) ---').
_PAGE_MARKER = re.compile(r"^--- Page \d+(?: \(empty\))? ---[ \t]*$", re.MULTILINE)
#: Audit round 2, R2-B05 (R04 part 2): a US state and ZIP code closing a mailing address ('SAMPLEVILLE SC 29000-0001').
CITY_STATE_ZIP = re.compile(r"\b[A-Z]{2},?\s+\d{5}(?:-\d{4})?\s*$")
#: Audit round 2, R2-B05 (R04 part 2): a Canadian province and postal code closing a mailing address
#: ('SAMPLEVILLE ON A1A 1A1', or with no space in the code).
PROVINCE_POSTAL_CODE = re.compile(r"\b[A-Z]{2},?\s+[A-Z]\d[A-Z]\s?\d[A-Z]\d\s*$")


def first_page(markdown: str) -> str:
    """Audit round 2, R2-B05 (R04 part 2): page 1's text, the text between the reading's first page marker and its
    second; the whole text when it prints no page marker (a parser handed one page)."""
    markers = list(_PAGE_MARKER.finditer(markdown))
    if not markers:
        return markdown
    end = markers[1].start() if len(markers) > 1 else len(markdown)
    return markdown[markers[0].end():end]


def page_lines(text: str) -> list[str]:
    """Audit round 2, R2-B05 (R04 part 2): a page's non-blank lines, each with its whitespace runs collapsed."""
    return [line for line in (" ".join(raw.split()) for raw in text.splitlines()) if line]


def read_mailing_line_after(
    markdown: str, anchor: re.Pattern[str], closes: re.Pattern[str] = CITY_STATE_ZIP
) -> HolderReading:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name from page 1's mailing line, the line right after the first
    line `anchor` matches (a bank's own return address, a contact line, a mail-routing code), read when it closes on
    `closes` (a state and ZIP by default), without the address (read_address_line); NO_READING otherwise. R2-OW10:
    with the account title that line prints after the name."""
    lines = page_lines(first_page(markdown))
    for index, line in enumerate(lines[:-1]):
        if anchor.match(line):
            mailing = lines[index + 1]
            return read_address_line(mailing) if closes.search(mailing) else NO_READING
    return NO_READING


def mailing_line_after(markdown: str, anchor: re.Pattern[str], closes: re.Pattern[str] = CITY_STATE_ZIP) -> str | None:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name of read_mailing_line_after's reading; None without one."""
    return read_mailing_line_after(markdown, anchor, closes).name

#: The legal forms a business name ends with. CO is one (CONTOSO TRADING CO); the address never reaches this reader's
#: name tokens, so Colorado's code is not read here.
_LEGAL_FORMS = frozenset({
    "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "CO", "LTD", "LIMITED", "LP", "LLP", "LLLP", "PLLC", "PLC", "ULC",
    "INCORPORATED",
})
#: Owner ruling 2026-10-02 (the underwriter's Q10), audit round 2, R2-OW11: the same legal forms, public, for the
#: premium-trust rule (true_revenue.premium_trust_title refuses the account-word form on a field that ends in one).
LEGAL_FORMS = _LEGAL_FORMS
#: The words of an account designation printed before ACCOUNT on a name with no legal form.
_DESIGNATION_WORDS = frozenset({
    "PREMIUM", "TRUST", "OPERATING", "WIRE", "PRODUCER", "PAYABLE", "ESCROW", "PAYROLL", "CLIENT", "CLIENTS",
    "CUSTOMER", "RESERVE", "TAX", "GENERAL", "SWEEP", "MAIN", "IOLTA", "DEPOSIT", "DISBURSEMENT", "COLLECTION",
})
_ACCOUNT_WORDS = frozenset({"ACCOUNT", "ACCT"})
_MAX_DESIGNATION_WORDS = 3
#: A house number: digits, optionally a letter or a second number after a hyphen ('100', '100A', '10-20').
_HOUSE_NUMBER = re.compile(r"^\d+(?:-?[A-Z]|-\d+)?$")
#: Audit round 2, R2-B05 (R04 part 2): the unit words an address can print before its street number.
_UNIT_WORDS = frozenset({"SUITE", "STE", "UNIT", "APT"})
#: A post-office box, spelled the ways the banks print it.
_PO_BOX = re.compile(r"^(?:P\.? ?O\.?|POST OFFICE) BOX\b", re.IGNORECASE)
#: A mail-handling instruction a bank prints before the name (the returned-mail hold).
_MAIL_HANDLING = re.compile(r"^HOLD\s*-?\s*RETURN(?:ED)? MAIL\s+", re.IGNORECASE)
#: A name line that ends on one of these continues on the next line ('NORTHWIND HEART &' / 'VASCULAR LLC').
_CONTINUED = frozenset({"&", "AND", "OF", "-", "/", "THE"})
#: A contact the bank prints after the holder's name (an attention line, care of), never part of the name.
_CONTACT_MARKERS = frozenset({"ATTN", "ATTENTION", "C/O"})
#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: the punctuation a title loses at either end (the separator a
#: bank prints between the name and the title: a comma, a colon, a hyphen, an en or an em dash).
_TITLE_STRIP = " ,;:-–—"
#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: the premium-trust words, whole (PREMIUM, PREMIUMS or PREM,
#: then TRUST or TRST, a dot after either allowed).
PREMIUM_TRUST_WORDS = r"(?<![A-Z0-9])PREM(?:IUMS?)?\.?\s*TR(?:UST|ST)\.?(?![A-Z0-9])"
#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: a mailing block's name line the block reader does not keep is
#: a title only when it prints an account word (ACCOUNT, ACCT) or the premium-trust words (read in upper case).
_TITLE_LINE = re.compile(r"(?<![A-Z])(?:ACCOUNT|ACCT)\b|" + PREMIUM_TRUST_WORDS)


def _word(token: str) -> str:
    """A token as the readers compare it: upper case, without dots and trailing commas ('L.L.C.' is LLC)."""
    return token.upper().replace(".", "").rstrip(",;:")


def _legal_form(token: str) -> bool:
    return _word(token) in _LEGAL_FORMS


def _dba(tokens: Sequence[str], index: int) -> int:
    """The number of tokens a DBA marker takes at `index` (DBA, D/B/A, or D B A spaced), or 0."""
    word = _word(tokens[index]).replace("/", "")
    if word == "DBA":
        return 1
    if [_word(token) for token in tokens[index:index + 3]] == ["D", "B", "A"]:
        return 3
    return 0


def _address_start(tokens: Sequence[str]) -> int | None:
    """The index where the address starts: a house number that no legal form follows within two tokens (a name can
    print a number: 'CONTOSO 100 LLC'), or a post-office box. Audit round 2, R2-B05 (R04 part 2): or a unit printed
    before the street ('SUITE 200 100 SAMPLE RD'), a unit word and a number that no legal form follows within two
    tokens."""
    for index, token in enumerate(tokens):
        if _PO_BOX.match(" ".join(tokens[index:index + 3])):
            return index
        if _HOUSE_NUMBER.match(_word(token)) and not any(_legal_form(after) for after in tokens[index + 1:index + 3]):
            return index
        if (
            _word(token) in _UNIT_WORDS and index + 1 < len(tokens) and _HOUSE_NUMBER.match(_word(tokens[index + 1]))
            and not any(_legal_form(after) for after in tokens[index + 2:index + 4])
        ):
            return index
    return None


def _split_designation(tokens: list[str]) -> tuple[list[str], list[str]]:
    """One name part split into its name and the account designation after it (owner ruling 2026-10-02, Q10; audit
    round 2, R2-OW10: the cut _without_designation always made, now keeping what it drops): everything after its last
    legal form (past its first word), or, with no legal form, a trailing run of designation words ending in ACCOUNT."""
    last_form = max((index for index, token in enumerate(tokens) if index > 0 and _legal_form(token)), default=None)
    if last_form is not None:
        return tokens[: last_form + 1], tokens[last_form + 1:]
    if tokens and _word(tokens[-1]) in _ACCOUNT_WORDS:
        cut = len(tokens) - 1
        while cut > 0 and len(tokens) - 1 - cut < _MAX_DESIGNATION_WORDS and _word(tokens[cut - 1]) in _DESIGNATION_WORDS:
            cut -= 1
        if cut > 0:
            return tokens[:cut], tokens[cut:]
    return tokens, []


def _without_designation(tokens: list[str]) -> list[str]:
    """One name part without the account designation after it (_split_designation's name)."""
    return _split_designation(tokens)[0]


def _without_contact(tokens: list[str]) -> list[str]:
    """The name's tokens before a contact the bank prints after it: an attention or care-of line (ATTN, ATTENTION,
    C/O) or a court case and its number (a debtor's account: 'CASE 12-34567')."""
    for index in range(1, len(tokens)):
        word = tokens[index].upper().rstrip(":")
        if word in _CONTACT_MARKERS or (
            word == "CASE" and index + 1 < len(tokens) and any(ch.isdigit() for ch in tokens[index + 1])
        ):
            return tokens[:index]
    return tokens


def _dba_split(tokens: Sequence[str]) -> tuple[int, int] | None:
    """The first DBA marker past the first token: (its index, its width), or None."""
    return next(((index, width) for index in range(1, len(tokens)) if (width := _dba(tokens, index))), None)


def _name(tokens: list[str]) -> str | None:
    """The holder's name from its tokens: the DBA split once, each part without its designation, joined as printed."""
    tokens = _without_contact(tokens)
    split = _dba_split(tokens)
    if split is None:
        parts = [_without_designation(tokens)]
        markers: list[str] = []
    else:
        index, width = split
        parts = [_without_designation(tokens[:index]), _without_designation(tokens[index + width:])]
        markers = [" ".join(tokens[index:index + width])]
        if not parts[1]:
            parts, markers = parts[:1], []
    words = list(parts[0])
    for marker, part in zip(markers, parts[1:]):
        words.extend([marker, *part])
    name = " ".join(words).strip(" ,;:")
    return name if sum(character.isalpha() for character in name) >= 2 else None


def _title_text(words: Sequence[str]) -> str | None:
    """Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: title words joined as printed, without the separator at
    either end (_TITLE_STRIP); None when nothing is left or no word prints a letter."""
    text = " ".join(words).strip(_TITLE_STRIP)
    return text if any(character.isalpha() for character in text) else None


def _title(tokens: list[str]) -> str | None:
    """Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: the account title the name's tokens print after the name:
    what _split_designation drops from each name part, the contact cut and the DBA split read as _name reads them,
    joined in print order (_title_text)."""
    tokens = _without_contact(tokens)
    split = _dba_split(tokens)
    parts = [tokens] if split is None else [tokens[:split[0]], tokens[split[0] + split[1]:]]
    return _title_text([token for part in parts for token in _split_designation(part)[1]])


def _reading(tokens: list[str]) -> HolderReading:
    """Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: the name and the title of one run of name tokens; no
    title without a name."""
    name = _name(tokens)
    return HolderReading(name, _title(tokens) if name is not None else None)


def read_name(text: str) -> HolderReading:
    """The holder's name from a line that prints only the name (and perhaps a designation or a contact after it): the
    name without them (a bank that labels the holder's line, such as TD Bank's '<holder> Account #'). R2-OW10: with the
    designation it drops as the account title."""
    return _reading(_MAIL_HANDLING.sub("", text.strip()).split())


def holder_from_name(text: str) -> str | None:
    """The holder's name of read_name's reading."""
    return read_name(text).name


def _continued(line: str) -> bool:
    """A name line that the next line continues: it ends on a connector or a comma, colon or hyphen."""
    words = line.split()
    return bool(words) and (_word(words[-1]) in _CONTINUED or words[-1][-1] in ",:-&/")


def read_address_line(line: str) -> HolderReading:
    """The holder's name printed before the address on one line, without the account designation; NO_READING when the
    line prints no address after a name. R2-OW10: with the designation it drops as the account title."""
    tokens = _MAIL_HANDLING.sub("", line.strip()).split()
    start = _address_start(tokens)
    if not start:
        return NO_READING
    return _reading(tokens[:start])


def holder_from_address_line(line: str) -> str | None:
    """The holder's name of read_address_line's reading."""
    return read_address_line(line).name


def _address_line(line: str) -> bool:
    """A street or post-office-box line of a mailing block."""
    tokens = line.split()
    return _address_start(tokens) == 0 if tokens else False


def _block_title_line(line: str) -> str | None:
    """Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: a mailing block's name line the block reader does not
    keep, read as an account title only when it prints an account word or the premium-trust words (_TITLE_LINE) and its
    first token (a trailing colon aside) is no contact marker (an attention or care-of line: _without_contact cuts only
    after the first token); a contact printed after its words is cut as the holder's is. None otherwise: an owner's or a
    contact's line is never a title."""
    tokens = line.split()
    if not tokens or tokens[0].upper().rstrip(":") in _CONTACT_MARKERS or not _TITLE_LINE.search(line.upper()):
        return None
    return _title_text(_without_contact(tokens))


def read_address_block(lines: Sequence[str]) -> HolderReading:
    """The holder's name from a mailing block's lines (the bank's furniture already removed): the first name line
    before the first street line, with a DBA line after it; NO_READING when no street line follows a name. R2-OW10:
    with the account title: what the kept lines print after the name, then each other name line before the street
    that prints an account word or the premium-trust words (_block_title_line), in print order."""
    names: list[str] = []
    for line in lines:
        text = _MAIL_HANDLING.sub("", " ".join(line.split())) if not names else " ".join(line.split())
        if not text:
            continue
        if _address_line(text):
            break
        names.append(text)
    else:
        return NO_READING
    if not names:
        return NO_READING
    holder = names[0].split()
    others = names[1:]
    if others:
        second = others[0].split()
        # The second line is the holder's trade name (DBA), the legal form or the rest of a wrapped name; any other
        # line is an owner's or a contact's name, never the holder's.
        if _dba(second, 0) or all(_legal_form(token) for token in second) or _continued(names[0]):
            holder.extend(second)
            others = others[1:]
    name = _name(holder)
    if name is None:
        return NO_READING
    titles = [_title(holder), *(_block_title_line(other) for other in others)]
    return HolderReading(name, " ".join(title for title in titles if title) or None)


def holder_from_address_block(lines: Sequence[str]) -> str | None:
    """The holder's name of read_address_block's reading."""
    return read_address_block(lines).name
