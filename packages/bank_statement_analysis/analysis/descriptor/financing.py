"""Whether a row names financing; the D6 skip reader and card-issuer reads."""
from __future__ import annotations

import re
from typing import Sequence

from analysis.classification_registry import CARD_ISSUER_CONTEXT_ALIASES
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.words import _FINANCING_ROOT_PATTERN, _ORGANISATION_CUES
from analysis.payee_matcher import registry_match


def _names_financing(text: str, *, besides: str = "") -> bool:
    """Whether a normalized row names financing anywhere but in `besides`, the words a D6 skip matched.

    Read on the whole row, the account holder's name included: a holder named like a funder keeps its rows in
    review, which is the safe direction. The skip's own words are removed first, so they never veto the skip."""
    rest = text.replace(besides, " ") if besides else text
    return _FINANCING_ROOT_PATTERN.search(rest) is not None


def _skips(region: str, patterns: Sequence[re.Pattern[str]], text: str) -> bool:
    """A D6 skip fires when one of `patterns` is found in `region` (the part of the row the skip reads) and the
    rest of the whole row `text` names no financing (`_names_financing`)."""
    for pattern in patterns:
        found = pattern.search(region)
        if found is not None and not _names_financing(text, besides=found.group(0)):
            return True
    return False


#: Besides the shared roots, a card-format skip never fires on a row that names a bank, an investment firm or an
#: organisation (an organisation cue or a financing-organisation word): funders ARE paid by debit card in these
#: formats (card lender-risk verifier: Dakota Financial on Bluevine, Hillcrest and CNAC on Square 'Card spend').
_CARD_POSTING_VETO_PATTERN = re.compile(
    r"(?:BANK|BANQUE|INVEST)"
    r"|\b(?:HOLDINGS?|PARTNERS?|VENTURES?|EQUITIES|GROUP|SOLUTIONS?|ENTERPRISES?|RESOURCES?|LP)\b"
)


def _card_posting_vetoed(text: str) -> bool:
    return (
        _names_financing(text)
        or _CARD_POSTING_VETO_PATTERN.search(text) is not None
        or any(token in _ORGANISATION_CUES for token in text.split())
    )


def _vendor_match_names_financing(matched: str) -> bool:
    """Whether a vendor match carries a financing root. A vendor stem's trailing letters would swallow a root run
    together with it ('FAB DISTRIBUTIONCAPITAL LLC', 'BOOKKEEPINGFUNDING', 'FAB DISTRIBUTORSCREDIT'), and the lending
    guard reads the row without the matched words, so such a match is no vendor. The whole word FUND of the ad-fund
    phrases (AD FUND, MARKETING FUND, ADVERTISING FUND) is their own vocabulary, not a glued root."""
    return any(word != "FUND" and _FINANCING_ROOT_PATTERN.search(word) for word in matched.split())


#: Each card_issuer_context alias's normalized words, computed once.
_CARD_ISSUER_CONTEXT_WORDS = {
    alias: tuple(normalize_transaction_description(alias).split())
    for aliases in CARD_ISSUER_CONTEXT_ALIASES.values()
    for alias in aliases
}


def _names_card_issuer(payee: Sequence[str], text: str) -> bool:
    """The payee IS a listed card issuer printed alone (C10 keeps that row unflagged): the issuer alias's words lead
    the D11 payee words, and the rest of the row names no financing. An issuer token inside a longer name
    (FABRICATED SYF CAPITAL) is never enough."""
    found = registry_match(" ".join(payee), CARD_ISSUER_CONTEXT_ALIASES)
    if found is None:
        return False
    words = _CARD_ISSUER_CONTEXT_WORDS.get(found[1], ())
    return bool(words) and tuple(payee[: len(words)]) == words and not _names_financing(
        text, besides=" ".join(words)
    )
