"""How a reader hands a DOCUMENT'S several accounts to the document entry point.

`analysis.parser_registry.Registration.parse` returns `Statement | None` — ONE
account, because `Statement` is one account and always was. A member statement
prints several of one member's accounts, and until this module existed a reader
that read all of them had nowhere to put the others: it published one and the
rest were the L-1 defect.

This is the seam. A reader reconstructs every section it can establish from the
document's own PRINTED partition, publishes the FIRST of them through the
registration's ordinary return — so `analyze_markdown`, every existing caller
and every fixture keep answering about one account exactly as before — and hands
the whole partition to whatever is collecting for this document. Only
`analysis.pipeline` collects, and only the DOCUMENT entry point builds the other
accounts' reports from it.

WHY A PARTITION AND NOT A LIST OF STATEMENTS
--------------------------------------------
Two things travel with each account and neither can be recovered later:

* the section's OWN TEXT. `analysis.adb.compute_average_daily_balance` applies
  `posting_dates_cover_source` against the source it is given, and the source
  for one account of a member statement is that account's own section — handing
  it the whole document counts a sibling's posting days against this account's
  ledger and refuses a document that is in fact complete (design §2.5);
* the document's own printed facts — the boundary mechanism the accounts were
  established from, the enumerating table read as an ORACLE, and the period
  resolved once for every section (design §2.2, §2.4).

WHY THE CLAIMING PARSE ATTEMPT IS IDENTIFIED BY ITS OWN STATEMENT
-----------------------------------------------------------------
`analysis.parser_registry.resolve` calls `parse` on EVERY candidate
registration, so several attempts may publish here and only one of them goes on
to claim the document. Rather than trust arrival order, every partition is kept
and the pipeline selects the one whose first account IS — by identity — the
statement the dispatch published. A losing candidate's partition is discarded
with the attempt that built it, exactly as
`analysis.sibling_omission.publish_omissions` discards a losing attempt's
omissions.

Nothing here reads a document, writes a grammar, or compares a printed value.
It imports only the schema, so a reader can import it.
"""
from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

from .schema import Statement


@dataclass(frozen=True)
class PublishedAccount:
    """One printed account section, reconstructed, with the text it was read from.

    `section_text` is the span the reader established from PRINTED boundaries —
    the account's own heading to its own printed closing — and it is what the
    ADB's source-coverage check is applied against. It is the section's own
    paper and nothing else's.

    `label` is the section's own printed ROLE, kept because the package layer
    names an account by what the paper called it. It is never an account number
    and never a value.
    """

    statement: Statement
    section_text: str
    label: str | None = None


@dataclass(frozen=True)
class RollupEvidence:
    """The document's enumerating table, as EVIDENCE (design §1.1, L1-C5).

    Carried so the roll-up can be AUDITED, never so a figure can be taken from
    it: `column_roles_printed` is false wherever the table printed no column
    caption from L1-C5's closed vocabulary, and a reader may take no opening and
    no closing from such a table at all.
    """

    caption_class: str
    column_roles_printed: bool
    rows: int
    cross_account_total_printed: bool


@dataclass(frozen=True)
class DocumentPartition:
    """What ONE parse attempt established about a document's accounts.

    `accounts` is in PRINTED ORDER and is never sorted (design §1.1): printed
    order is printed evidence about a SEQUENCE, and never evidence that the
    first element stands for the whole document.
    """

    accounts: tuple[PublishedAccount, ...]
    boundary_mechanism: str
    document_period: tuple[str, str] | None = None
    rollup: RollupEvidence | None = None

    @property
    def published_statement(self) -> Statement | None:
        """The statement the registration returned — the first account."""
        return self.accounts[0].statement if self.accounts else None


class _Collector:
    """Every partition published inside one document's analysis.

    A list rather than one slot: several candidate registrations may parse the
    same document and each may publish, and which of them CLAIMED is a fact the
    dispatch holds and this module does not.
    """

    __slots__ = ("partitions", "claimed")

    def __init__(self) -> None:
        self.partitions: list[DocumentPartition] = []
        self.claimed: DocumentPartition | None = None

    def add(self, partition: DocumentPartition) -> None:
        self.partitions.append(partition)

    def resolve_claim(self, statement: Statement | None) -> DocumentPartition | None:
        """Settle which published partition the dispatch actually claimed."""
        self.claimed = self.claimed_by(statement)
        return self.claimed

    def claimed_by(self, statement: Statement | None) -> DocumentPartition | None:
        """The partition whose FIRST account is `statement`, by identity.

        Identity and not equality: two candidate readers of the same paper can
        build equal statements, and the question here is which object the
        dispatch actually published. `None` when nothing published one — which
        is every document in the archive no multi-account reader claims, and is
        why the single-account path is untouched.
        """
        if statement is None:
            return None
        for partition in self.partitions:
            if partition.published_statement is statement:
                return partition
        return None


_COLLECTING: ContextVar["_Collector | None"] = ContextVar(
    "published_accounts", default=None,
)


@contextmanager
def collecting() -> Iterator[_Collector]:
    """Collect the partitions published by whatever parses inside this block.

    Opened by `analysis.pipeline`'s one internal analysis function, so both
    entry points see the same collection: the ACCOUNT entry point uses it only
    to learn which section the account it publishes was read from, and the
    DOCUMENT entry point uses it to build the other accounts as well.

    RE-ENTRANT BY DESIGN: a block opened inside another block yields the OUTER
    collector rather than shadowing it, so one document's analysis has exactly
    one collection however many nested scopes are opened over it. A second,
    inner collector would be the quiet failure this whole seam exists to avoid —
    the reader publishes into it, the outer scope finds nothing, and a
    multi-account document publishes one account with nothing saying so.
    """
    existing = _COLLECTING.get()
    if existing is not None:
        yield existing
        return
    collector = _Collector()
    reset = _COLLECTING.set(collector)
    try:
        yield collector
    finally:
        _COLLECTING.reset(reset)


def publish_partition(
    accounts: Sequence[PublishedAccount],
    *,
    boundary_mechanism: str,
    document_period: tuple[str, str] | None = None,
    rollup: RollupEvidence | None = None,
) -> None:
    """Hand this parse attempt's reconstructed accounts to the document.

    Called by a reader that IS returning `accounts[0].statement`. A reader that
    returns `None` publishes nothing here either: an attempt that declines has
    established no partition, whatever it managed to read on the way.

    A no-op when nothing is collecting, which is every call made outside
    `analysis.pipeline`'s analysis — a fixture calling `parse` directly reaches
    exactly the statement it always did.
    """
    collector = _COLLECTING.get()
    if collector is None or not accounts:
        return
    collector.add(DocumentPartition(
        accounts=tuple(accounts),
        boundary_mechanism=boundary_mechanism,
        document_period=document_period,
        rollup=rollup,
    ))
