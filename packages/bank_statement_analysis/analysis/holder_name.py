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
an account word or the premium-trust words (never an owner's, a contact's or a wrapped name line, except a contact whose
words are the premium-trust designation itself, which is the account's title in any spacing). The `holder_from_*`
readers are the readings' names, unchanged. A reading with no name has no title. The title is provenance for the
revenue rule; it is never part of the holder's name.

Audit round 3, R3-B11 (R3-61; the underwriter's Q10): a contact is read by its words, not its spacing. A contact
(`ATTN`, `ATTENTION`, `C/O`, glued to its text by a colon or a dot or not, and `CARE OF` after the name's legal form)
is never part of the name, and its text is a title only when it is exactly the premium-trust designation
('ATTN:PREMIUM TRUST ACCOUNT' publishes PREMIUM TRUST ACCOUNT); a contact naming a person or a department never is.
(R3-65) The premium-trust words read FUND or FUNDS between them ('PREMIUM FUND TRUST').

Audit round 3, R3-B11, review round 1: `CARE OF` is a contact only where the name has ended, right after its legal
form or the account designation printed right after it (finding 1: 'CONTOSO LLC DBA NORTHWIND HOME CARE OF
SAMPLEVILLE' and 'SAMPLE & CO HOME CARE OF SAMPLEVILLE LLC' are names); and the premium-trust designation a contact's
words must be is the title rule's own, a title at a field's end read from the contact's first word (finding 2: the
words, kind words such as CHECKING, a product adjective before one, and a reference; PREMIUM_TRUST_KIND,
PREMIUM_TRUST_REFERENCE)."""
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
#: Audit round 3, R3-B11 (R3-61): a contact marker glued to its text by a colon or a dot ('ATTN:PREMIUM',
#: 'ATTENTION:SAMPLE', 'C/O:SAMPLE', 'ATTN.SAMPLE'); the remainder is the contact text's first token.
_GLUED_CONTACT = re.compile(r"^(?:ATTN|ATTENTION|C/O)[:.](?P<text>.+)$", re.IGNORECASE)
#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: the punctuation a title loses at either end (the separator a
#: bank prints between the name and the title: a comma, a colon, a hyphen, an en or an em dash).
_TITLE_STRIP = " ,;:-–—"
#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: the premium-trust words, whole (PREMIUM, PREMIUMS or PREM,
#: then TRUST or TRST, a dot after either allowed). Audit round 3, R3-B11 (R3-65): FUND or FUNDS may print between
#: them ('PREMIUM FUND TRUST', a bank's product name for an agent's premium trust account).
PREMIUM_TRUST_WORDS = r"(?<![A-Z0-9])PREM(?:IUMS?)?\.?\s*(?:FUNDS?\s+)?TR(?:UST|ST)\.?(?![A-Z0-9])"
#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW11 (true_revenue.premium_trust_title's grammar, kept here since
#: audit round 3, R3-B11 review round 1 so the contact designation reads the same words): the kind words a title may
#: print after the premium-trust words (an account, a fund, a product). Audit round 3, R3-B11 (R3-65): a product
#: adjective may print before a kind word ('PREMIUM TRUST BUSINESS CHECKING'); an adjective alone is never a kind word
#: ('PREMIUM TRUST BUSINESS' is no title).
PREMIUM_TRUST_ADJECTIVE = r"(?:(?:BUSINESS|ANALYZED|COMMERCIAL)\s+)?"
PREMIUM_TRUST_KIND = (
    rf"{PREMIUM_TRUST_ADJECTIVE}"
    r"(?:ACCOUNT|ACCT|ACCNT|A/C|FUNDS?|CHECKING|CHK|DDA|SAVINGS|SAV|SHARE|MMA|MONEY\s+MARKET)\.?"
)
#: R2-OW11 (the same grammar): a reference a title may print: an account number, masked or not, after #, NO, NUMBER,
#: ACCOUNT, ACCT or A/C, in or out of parentheses; a roman numeral; or a parenthesised code of up to four letters or
#: digits.
PREMIUM_TRUST_REFERENCE = (
    r"(?:\(?\s*(?:(?:ACCOUNT|ACCT|A/C|NO|NUMBER)\.?\s*)?#?\s*[X*]*\d+\s*\)?"
    r"|(?<![A-Z])[IVX]{1,4}"
    r"|\([A-Z0-9]{1,4}\))"
)
#: Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: a mailing block's name line the block reader does not keep is
#: a title only when it prints an account word (ACCOUNT, ACCT) or the premium-trust words (read in upper case).
_TITLE_LINE = re.compile(r"(?<![A-Z])(?:ACCOUNT|ACCT)\b|" + PREMIUM_TRUST_WORDS)
#: Audit round 3, R3-B11 (R3-61; the underwriter's Q10 of 2026-10-02): a contact's text that is exactly the
#: premium-trust designation: such a contact names the account itself, so it is the account's title. Any other contact
#: (a person, a department, any other word after the designation) is never a title. Review round 1 (finding 2): the
#: designation is the title rule's own title at a field's end (true_revenue._PREMIUM_TRUST_AT_END), read from the
#: contact's first word: the words, any kind words (PREMIUM_TRUST_KIND: an account, a fund or a product word, a product
#: adjective before one), then a reference (PREMIUM_TRUST_REFERENCE) and closing punctuation, so 'PREMIUM TRUST
#: CHECKING', the bare 'PREMIUM TRUST' and 'PREMIUM TRUST ACCOUNT (1234)' read as the rule reads them as a title.
_CONTACT_DESIGNATION = re.compile(
    rf"^{PREMIUM_TRUST_WORDS}(?:\s+{PREMIUM_TRUST_KIND})*(?:[\s\-:#,]*{PREMIUM_TRUST_REFERENCE})?[\s.,;:\-)]*$"
)
#: Audit round 3, R3-B11, review round 1 (finding 2): a reference's marker left dangling at the contact's end (the
#: address cut reads 'ACCT # 1234 PO BOX …' and 'ACCOUNT NO 1234 100 …' with the number as a house number): dropped.
_DANGLING_REFERENCE = re.compile(r"(?:\s*#|\s+(?:NO|NUMBER)\.?)\s*$")


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


def _contact_at(tokens: Sequence[str], index: int, *, care_of: bool) -> list[str] | None:
    """Audit round 3, R3-B11 (R3-61): the contact's text when a contact marker prints at `index`, else None. A marker
    is read by its words, not its spacing: a whole marker token (ATTN, ATTENTION, C/O; a trailing colon or dot
    stripped), a marker glued to its text by a colon or a dot (_GLUED_CONTACT: its remainder is the text's first token),
    or, when `care_of`, the two tokens CARE OF."""
    token = tokens[index]
    if token.upper().rstrip(":.") in _CONTACT_MARKERS:
        return list(tokens[index + 1:])
    if (glued := _GLUED_CONTACT.match(token)) is not None:
        return [glued.group("text"), *tokens[index + 1:]]
    if (
        care_of and token.upper() == "CARE" and index + 1 < len(tokens)
        and tokens[index + 1].upper().rstrip(":.") == "OF"
    ):
        return list(tokens[index + 2:])
    return None


def _name_ended(tokens: Sequence[str], index: int) -> bool:
    """Audit round 3, R3-B11, review round 1 (finding 1): the name has ended before `index`: the token right before it
    is a legal form (a trailing comma or dot allowed: _legal_form), or an account designation printed right after one
    (up to _MAX_DESIGNATION_WORDS designation words, then an account word: 'CONTOSO INSURANCE AGENCY INC PREMIUM TRUST
    ACCOUNT CARE OF …'). A legal form printed earlier ends no name there: 'CONTOSO LLC DBA NORTHWIND HOME CARE OF
    SAMPLEVILLE' (a DBA trade name) and 'SAMPLE & CO HOME CARE OF SAMPLEVILLE LLC' are names."""
    cut = index
    if cut > 0 and _word(tokens[cut - 1]) in _ACCOUNT_WORDS:
        cut -= 1
        while cut > 0 and index - 1 - cut < _MAX_DESIGNATION_WORDS and _word(tokens[cut - 1]) in _DESIGNATION_WORDS:
            cut -= 1
    return cut > 0 and _legal_form(tokens[cut - 1])


def _contact_split(tokens: Sequence[str]) -> tuple[list[str], list[str]]:
    """Audit round 3, R3-B11 (R3-61): the name's tokens before a contact the bank prints after it, and the contact's
    text. Scanning from the second token, the first contact splits the tokens: an attention or care-of marker, whole or
    glued to its text (_contact_at: ATTN, ATTENTION, C/O); the two tokens CARE OF only where the name has ended, right
    after its legal form or the designation printed right after it (_name_ended; review round 1, finding 1: 'CONTOSO
    HOME CARE OF SAMPLEVILLE LLC', 'CONTOSO LLC DBA NORTHWIND HOME CARE OF SAMPLEVILLE' and 'SAMPLE & CO HOME CARE OF
    SAMPLEVILLE LLC' are business names); or a court case and its number (a debtor's account: 'CASE 12-34567'), whose
    text is never a title. No contact: every token is the name's, and no text."""
    for index in range(1, len(tokens)):
        word = tokens[index].upper().rstrip(":")
        if word == "CASE" and index + 1 < len(tokens) and any(ch.isdigit() for ch in tokens[index + 1]):
            return list(tokens[:index]), []
        care_of = word == "CARE" and _name_ended(tokens, index)
        if (contact := _contact_at(tokens, index, care_of=care_of)) is not None:
            return list(tokens[:index]), contact
    return list(tokens), []


def _contact_designation(contact: Sequence[str]) -> str | None:
    """Audit round 3, R3-B11 (R3-61; the underwriter's Q10 of 2026-10-02): a contact's text, upper case and without
    the separator at either end, when it reads as exactly the premium-trust designation (_CONTACT_DESIGNATION: 'ATTN:
    PREMIUM TRUST ACCOUNT' names the account itself, in any spacing); None for anything else (a person, 'PREMIUM TRUST
    DEPT', 'PREMIUM TRUST ACCOUNTING', 'PREMIUM TRUST SERVICES LLC', 'PREMIUM TRUST OPERATING', an adjective alone,
    any other word after the designation, a name before the words). Review round 1 (finding 2): the designation is the
    title rule's title at a field's end (kind words such as CHECKING, the bare words, a reference), and a reference's
    marker the address cut leaves dangling (#, NO, NUMBER) is dropped first ('ATTN: PREMIUM TRUST ACCT # 1234 PO BOX
    …' publishes PREMIUM TRUST ACCT)."""
    text = " ".join(contact).upper().strip(_TITLE_STRIP)
    text = _DANGLING_REFERENCE.sub("", text).strip(_TITLE_STRIP)
    return text if _CONTACT_DESIGNATION.match(text) else None


def _without_contact(tokens: list[str]) -> list[str]:
    """The name's tokens before a contact the bank prints after it: an attention or care-of line (ATTN, ATTENTION,
    C/O) or a court case and its number (a debtor's account: 'CASE 12-34567'). Audit round 3, R3-B11 (R3-61):
    _contact_split's name, so a marker glued to its text and CARE OF where the name has ended (right after its legal
    form or the designation printed right after it; review round 1, finding 1) are contacts too."""
    return _contact_split(tokens)[0]


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
    joined in print order (_title_text). Audit round 3, R3-B11 (R3-61): then the contact's text when it is the
    premium-trust designation itself (_contact_designation); any other contact is never a title."""
    tokens, contact = _contact_split(tokens)
    split = _dba_split(tokens)
    parts = [tokens] if split is None else [tokens[:split[0]], tokens[split[0] + split[1]:]]
    words = [token for part in parts for token in _split_designation(part)[1]]
    if (designation := _contact_designation(contact)) is not None:
        words.append(designation)
    return _title_text(words)


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
    contact's line is never a title, except a contact whose words are the premium-trust designation itself, which is
    the account's title in any spacing (audit round 3, R3-B11: R3-61). A line that opens on a contact (_contact_at at
    its first token: a whole or glued marker, or CARE OF, which needs no legal form before it there) is read only as
    _contact_designation of its text."""
    tokens = line.split()
    if not tokens:
        return None
    if (contact := _contact_at(tokens, 0, care_of=True)) is not None:
        return _contact_designation(contact)
    if not _TITLE_LINE.search(line.upper()):
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
