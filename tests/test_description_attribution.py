"""W3 §DESCATTRIB — a description stays attached to its own posting.

The oracle the two core-processor readers of this complex can fail against.
`tables.dated_cells` documents three printings its one rule reads, and the
third of them — a text layer that interleaves whole blocks of merchant detail
between a run of dates and the run of amounts that answers them — is where a
row's span stops being the row's own. This module is the fixture family for all
three, with the per-row descriptions each one must publish, run through BOTH
readers' grammars so that "one code path" is a test rather than a claim.

Every document here is synthetic. The archive documents that motivated the card
are named by content sha in the branch log; none of them is reproduced, and no
merchant, lender or holder of a real statement appears — the rule under test is
forbidden from reading such a name anyway, and a fixture that used one would
invite exactly the vocabulary this design refuses.
"""
from __future__ import annotations

import pytest

from analysis import core_processor_counted as cpc, core_processor_daily as cpd, tables

#: The two readers of the complex, by the grammar each hands the shared scan.
#: Both are exercised over the SAME printings: the attribution is one rule and
#: a printing one reader gets right and the other does not is a defect.
READERS = pytest.mark.parametrize(
    "module", [cpc, cpd], ids=["counted", "daily"],
)

#: Zero-padded so one fixture text is a row date under both grammars: the
#: sibling prints `mm-dd` and this one prints `m-d` with the leading zero
#: admitted.
WRAP_BELOW = (
    "\nDate Description Amount\n"
    "02-03 Preauthorized Credit 300.00\n"
    "EXAMPLE ORIGINATOR PAYABLES CCD\n"
    "02-04 Preauthorized Credit 400.00\n"
    "EXAMPLE OTHER ORIGINATOR PAYABLES CCD\n"
)
INTERLEAVED = (
    "\nDate Description Amount\n"
    "02-03 Preauthorized Debit 10.00 02-03 Preauthorized Debit\n"
    "EXAMPLE FIRST PAYABLES CCD EXAMPLE SECOND PAYABLES CCD\n"
    "20.00 02-03 Preauthorized Debit\n"
    "EXAMPLE THIRD PAYABLES CCD\n"
    "30.00\n"
)
TWO_ON_ONE_LINE = (
    "\nDate Description Amount\n"
    "02-05 Preauthorized Debit 20.00 02-05 Preauthorized Debit 30.00\n"
)
TWO_CONTINUATION_LINES = (
    "\nDate Description Amount\n"
    "02-03 Preauthorized Debit\n"
    "EXAMPLE FIRST PAYABLES CCD\n"
    "EXAMPLE SECOND PAYABLES CCD\n"
    "10.00\n"
)

#: printing -> the description every row of it must publish, in row order.
FAMILY = {
    # 1. The block is printed BELOW its own amount, so it lands in no row's
    #    span at all and every row publishes the label it was printed with.
    "wrap_below": (WRAP_BELOW, ["Preauthorized Credit", "Preauthorized Credit"]),
    # 2. The layer flushed TWO rows' blocks into the second row's span with a
    #    single space between them and no boundary to cut at — indeterminate,
    #    so neither row publishes either block. The third row's span holds a
    #    flush the layer proves is one block, and that block is its own.
    "interleaved": (INTERLEAVED, [
        "Preauthorized Debit",
        "Preauthorized Debit",
        "Preauthorized Debit EXAMPLE THIRD PAYABLES CCD",
    ]),
    # 3. Two printed rows on one physical line: each keeps its own label and
    #    neither takes the other's.
    "two_on_one_line": (TWO_ON_ONE_LINE, ["Preauthorized Debit", "Preauthorized Debit"]),
    # 4. Two continuation lines inside one span is more than one flush, and a
    #    span holding more than one flush holds more than this row's block.
    "two_continuation_lines": (TWO_CONTINUATION_LINES, ["Preauthorized Debit"]),
}


def descriptions(module, run: str) -> list[str]:
    cells = tables.dated_cells(
        run, date_pattern=module._DATE_RE, value_pattern=module._FIGURE_RE)
    assert cells is not None, "the fixture is not readable as a dated grid"
    return tables.attributed_descriptions(
        cells,
        strip=module._DESCRIPTION_FURNITURE,
        limit=module._DESCRIPTION_LIMIT,
    )


# ---------------------------------------------------------------------------
# The family
# ---------------------------------------------------------------------------

@READERS
@pytest.mark.parametrize("printing", sorted(FAMILY))
def test_every_printing_publishes_the_description_its_own_row_printed(module, printing):
    run, expected = FAMILY[printing]
    assert descriptions(module, run) == expected


@READERS
def test_a_block_belonging_to_an_earlier_row_is_never_published_on_a_later_one(module):
    """The defect this card exists for, stated as the property rather than as
    a string: no row may publish text the row before it was printed with."""
    published = descriptions(module, INTERLEAVED)
    assert "EXAMPLE FIRST" not in " ".join(published)
    assert "EXAMPLE SECOND" not in " ".join(published)


@READERS
def test_a_block_is_never_published_on_the_row_before_the_one_it_belongs_to(module):
    """The other candidate fix, refused for the same reason: the flush in a
    row's span is not the PREVIOUS row's block either — it ends with this
    row's own. Attributing it backwards moves the same wrong name one row the
    other way."""
    published = descriptions(module, INTERLEAVED)
    assert "EXAMPLE THIRD" not in published[0]
    assert "EXAMPLE THIRD" not in published[1]


@READERS
def test_a_row_the_layer_proves_owns_its_block_publishes_all_of_it(module):
    """Fail-closed must not become fail-silent: where ownership IS provable
    the block is published, or the rule would simply delete the merchant
    detail this platform reads."""
    assert descriptions(module, INTERLEAVED)[2].endswith("EXAMPLE THIRD PAYABLES CCD")


@READERS
def test_a_row_whose_own_block_the_layer_flushed_later_still_publishes_its_label(module):
    """A dropped block leaves the row's LABEL, never an empty description: the
    label is what the bank printed on that row's own line."""
    assert descriptions(module, INTERLEAVED)[0] == "Preauthorized Debit"


# ---------------------------------------------------------------------------
# The bound, and how it cuts
# ---------------------------------------------------------------------------

@READERS
def test_a_description_over_the_bound_is_cut_at_a_token_boundary(module):
    """A cut mid-token publishes a string the bank did not print — §LCPERIOD
    L5.3's class, one field along.

    The first form of this test proved nothing, and §GRAM4 G7.4 is why it was
    caught: its filler happened to put a space exactly at the bound, so cutting
    AT the bound and cutting at the boundary produced the same string and the
    mutation survived. The fixture now asserts its own premise before it
    asserts the behaviour.
    """
    limit = module._DESCRIPTION_LIMIT
    block = " ".join(["EXAMPLE"] * 60)
    whole = f"Preauthorized Debit {block}"
    assert 0 < len(whole[:limit].rsplit(" ", 1)[-1]) < len("EXAMPLE"), (
        "the fixture must put the bound INSIDE a token, or a cut at the bound "
        "and a cut at the boundary are the same string and this tests nothing"
    )
    published = descriptions(module, f"\n02-03 Preauthorized Debit\n{block}\n10.00\n")[0]
    assert len(published) <= limit
    assert whole.startswith(published)
    assert published.rsplit(" ", 1)[-1] == "EXAMPLE"
    assert published != whole[:limit]


@READERS
def test_a_first_token_longer_than_the_bound_publishes_nothing_rather_than_half(module):
    """There is no boundary to cut at, and half a token is not a description.
    The caller's section default is what the row then publishes."""
    run = "\n02-03 " + "X" * 400 + "\n10.00\n"
    assert descriptions(module, run) == [""]


@READERS
def test_a_description_at_the_bound_exactly_is_published_whole(module):
    module_limit = module._DESCRIPTION_LIMIT
    label = "A" * module_limit
    run = f"\n02-03 {label} 10.00\n"
    assert descriptions(module, run) == [label]


# ---------------------------------------------------------------------------
# One code path
# ---------------------------------------------------------------------------

def test_both_readers_attribute_through_the_one_shared_call():
    """`tests/test_no_parser_helper_clones.py` catches the copy; this catches
    the SECOND implementation that is not a copy. The attribution is one rule
    over one layer and the complex's two readers must not be able to disagree
    about it."""
    assert cpc.attributed_descriptions is tables.attributed_descriptions
    assert cpd.attributed_descriptions is tables.attributed_descriptions


@READERS
def test_neither_reader_keeps_a_private_description_normaliser(module):
    """The old `_described` is gone from both, rather than left beside the
    shared call for someone to reach for."""
    assert not hasattr(module, "_described")
