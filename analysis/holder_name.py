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
memory of any statement's names; every bank keeps its own anchor (the line or block the reader is handed)."""
from __future__ import annotations

import re
from collections.abc import Sequence

#: The legal forms a business name ends with. CO is one (CONTOSO TRADING CO); the address never reaches this reader's
#: name tokens, so Colorado's code is not read here.
_LEGAL_FORMS = frozenset({
    "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "CO", "LTD", "LIMITED", "LP", "LLP", "LLLP", "PLLC", "PLC", "ULC",
    "INCORPORATED",
})
#: The words of an account designation printed before ACCOUNT on a name with no legal form.
_DESIGNATION_WORDS = frozenset({
    "PREMIUM", "TRUST", "OPERATING", "WIRE", "PRODUCER", "PAYABLE", "ESCROW", "PAYROLL", "CLIENT", "CLIENTS",
    "CUSTOMER", "RESERVE", "TAX", "GENERAL", "SWEEP", "MAIN", "IOLTA", "DEPOSIT", "DISBURSEMENT", "COLLECTION",
})
_ACCOUNT_WORDS = frozenset({"ACCOUNT", "ACCT"})
_MAX_DESIGNATION_WORDS = 3
#: A house number: digits, optionally a letter or a second number after a hyphen ('100', '100A', '10-20').
_HOUSE_NUMBER = re.compile(r"^\d+(?:-?[A-Z]|-\d+)?$")
#: A post-office box, spelled the ways the banks print it.
_PO_BOX = re.compile(r"^(?:P\.? ?O\.?|POST OFFICE) BOX\b", re.IGNORECASE)
#: A mail-handling instruction a bank prints before the name (the returned-mail hold).
_MAIL_HANDLING = re.compile(r"^HOLD\s*-?\s*RETURN(?:ED)? MAIL\s+", re.IGNORECASE)
#: A name line that ends on one of these continues on the next line ('NORTHWIND HEART &' / 'VASCULAR LLC').
_CONTINUED = frozenset({"&", "AND", "OF", "-", "/", "THE"})


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
    print a number: 'CONTOSO 100 LLC'), or a post-office box."""
    for index, token in enumerate(tokens):
        if _PO_BOX.match(" ".join(tokens[index:index + 3])):
            return index
        if _HOUSE_NUMBER.match(_word(token)) and not any(_legal_form(after) for after in tokens[index + 1:index + 3]):
            return index
    return None


def _without_designation(tokens: list[str]) -> list[str]:
    """One name part without the account designation after it: everything after its last legal form (past its first
    word), or, with no legal form, a trailing run of designation words ending in ACCOUNT."""
    last_form = max((index for index, token in enumerate(tokens) if index > 0 and _legal_form(token)), default=None)
    if last_form is not None:
        return tokens[: last_form + 1]
    if tokens and _word(tokens[-1]) in _ACCOUNT_WORDS:
        cut = len(tokens) - 1
        while cut > 0 and len(tokens) - 1 - cut < _MAX_DESIGNATION_WORDS and _word(tokens[cut - 1]) in _DESIGNATION_WORDS:
            cut -= 1
        if cut > 0:
            return tokens[:cut]
    return tokens


def _name(tokens: list[str]) -> str | None:
    """The holder's name from its tokens: the DBA split once, each part without its designation, joined as printed."""
    split = next(((index, width) for index in range(1, len(tokens)) if (width := _dba(tokens, index))), None)
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


def _continued(line: str) -> bool:
    """A name line that the next line continues: it ends on a connector or a comma, colon or hyphen."""
    words = line.split()
    return bool(words) and (_word(words[-1]) in _CONTINUED or words[-1][-1] in ",:-&/")


def holder_from_address_line(line: str) -> str | None:
    """The holder's name printed before the address on one line, without the account designation; None when the line
    prints no address after a name."""
    tokens = _MAIL_HANDLING.sub("", line.strip()).split()
    start = _address_start(tokens)
    if not start:
        return None
    return _name(tokens[:start])


def _address_line(line: str) -> bool:
    """A street or post-office-box line of a mailing block."""
    tokens = line.split()
    return _address_start(tokens) == 0 if tokens else False


def holder_from_address_block(lines: Sequence[str]) -> str | None:
    """The holder's name from a mailing block's lines (the bank's furniture already removed): the first name line
    before the first street line, with a DBA line after it; None when no street line follows a name."""
    names: list[str] = []
    for line in lines:
        text = _MAIL_HANDLING.sub("", " ".join(line.split())) if not names else " ".join(line.split())
        if not text:
            continue
        if _address_line(text):
            break
        names.append(text)
    else:
        return None
    if not names:
        return None
    holder = names[0].split()
    if len(names) > 1:
        second = names[1].split()
        # The second line is the holder's trade name (DBA), the legal form or the rest of a wrapped name; any other
        # line is an owner's or a contact's name, never the holder's.
        if _dba(second, 0) or all(_legal_form(token) for token in second) or _continued(names[0]):
            holder.extend(second)
    return _name(holder)
