"""A ledger's lender figures, each the magnitude of its rows to the cent and their count: paid to lenders, the
withholding numerator, the funder payments returned unpaid, the paid lump-sum payoffs, the potential lender debits and
insurance (true revenue spec §9.1). compute_metrics and a package member's figures add them here, each reading its own
rows' flags and keeping its own arithmetic."""
from __future__ import annotations

from typing import NamedTuple

from .revenue import Accumulation, cents_total


class LenderRow(NamedTuple):
    """One row and the figures its flags put it in, as its caller reads them. The flags are independent: a paid debit
    is usually withheld too, a paid payoff is not, and a returned payment is withheld while it stands. `record` is the
    caller's own record of the row, kept by reference."""
    amount: float
    paid: bool
    withheld: bool
    returned: bool
    payoff_words: bool
    potential: bool
    insurance: bool
    record: object


class LenderFigure(NamedTuple):
    total: float
    count: int
    records: list


class LenderFigures(NamedTuple):
    paid: LenderFigure
    withholding: LenderFigure
    #: The funder payments returned unpaid, out of paid (true revenue spec §11).
    returned: LenderFigure
    #: The paid debits that print payoff words: in paid, out of the withholding numerator (true revenue spec §11).
    payoff: LenderFigure
    potential: LenderFigure
    insurance: LenderFigure


def lender_figures(rows: list[LenderRow], *, accumulation: Accumulation) -> LenderFigures:
    """Each figure over the rows its flag selects, in the order given: their magnitudes added to the cent as
    `accumulation` says, their count, and their records."""
    def figure(selected: list[LenderRow]) -> LenderFigure:
        return LenderFigure(cents_total([abs(row.amount) for row in selected], accumulation), len(selected),
                            [row.record for row in selected])

    return LenderFigures(
        paid=figure([row for row in rows if row.paid]),
        withholding=figure([row for row in rows if row.withheld]),
        returned=figure([row for row in rows if row.returned]),
        payoff=figure([row for row in rows if row.payoff_words and row.paid]),
        potential=figure([row for row in rows if row.potential]),
        insurance=figure([row for row in rows if row.insurance]),
    )
