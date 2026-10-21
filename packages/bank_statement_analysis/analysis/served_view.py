"""A stored analysis as the dashboard serves it: the owner's display settings applied to a copy."""
from __future__ import annotations

from analysis.active_positions import apply_active_positions_view
from analysis.display_settings import DEFAULTS as SETTINGS_DEFAULTS
from analysis.flagged_view import apply_flagged_groups_to_payload
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.payload_shape import is_document_payload
from analysis.revenue_view import (
    apply_revenue_view,
    UNESTABLISHED_REVENUE_KEYS,
    UNESTABLISHED_VERIFIED_KEYS,
    UNESTABLISHED_WITHHOLDING_BASIS_KEYS,
    unestablished_zelle_figures,
    WITHHOLDING_BASIS_UNESTABLISHED,
)
from analysis.zelle_view import apply_zelle_view, ZELLE_DEPOSITS_KEY


def zelle_setting(settings: dict | None) -> bool:
    """Whether the settings snapshot asks for Zelle deposits counted as True revenue (Yes, the default; a missing or
    malformed value reads as Yes)."""
    value = (settings or {}).get("zelle_true_revenue", SETTINGS_DEFAULTS["zelle_true_revenue"])
    return value if isinstance(value, bool) else SETTINGS_DEFAULTS["zelle_true_revenue"]


def displayed(
    analysis: object, *, carry_over: bool | None = None, settings: dict | None = None, export: bool = False
) -> object:
    """A stored analysis as the dashboard presents it: the owner's Settings applied to a COPY.

    Two settings apply. The NSF basis (analysis/nsf_days.py): printed days by default, or every calendar day with
    the balance carried over inactive days when Settings turns carry-over on. And the flag groups
    (analysis/flagged_view.py): an unticked group is hidden from the summaries and its rows lose their flag.
    Every surface that shows or exports an analysis goes through here, so the dashboard, the downloads and the
    package agree; the stored record is never rewritten, and a change of setting applies to every job at once.

    `settings` is a snapshot of every setting; None applies the defaults. `carry_over`, when given, still decides
    the NSF basis. `export` leaves out what only the dashboard reads (the NSF days its NSFs chip
    lists, `metrics.nsf_days`), so a download carries what it carried before the chip.

    True revenue spec §9.2, §10: FIRST, the Zelle reading the setting "Mark Zelle Payments as True Revenue" asks
    for (analysis/zelle_view.py), whose stored edits are paths in the stored shape, so it runs before any served
    key is added."""
    if settings is None:
        settings = dict(SETTINGS_DEFAULTS)
    if carry_over is None:
        carry_over = settings.get("nsf_carry_over", SETTINGS_DEFAULTS["nsf_carry_over"])
    analysis = apply_zelle_view(analysis, counted=zelle_setting(settings))
    rebased = apply_nsf_basis_to_payload(analysis, carry_over=carry_over, list_days=not export)
    # True revenue spec §10.4, §12: each account's revenue flags, and an older payload's True revenue nulled. §9.1:
    # then each account's active and possible positions, read from its stored rows (analysis/active_positions.py),
    # computed here and never stored.
    served = apply_active_positions_view(apply_revenue_view(apply_flagged_groups_to_payload(rebased, enabled=settings)))
    # A download never prints a figure the dashboard reads as N/A.
    return _export_revenue_view(served) if export else served


#: §10.4: the figures a download leaves empty when an account's revenue is not established, and when its
#: Verified figure is not. The lists live in analysis/revenue_view.py, which the CLI reads too.
_UNESTABLISHED_REVENUE_KEYS = UNESTABLISHED_REVENUE_KEYS


_UNESTABLISHED_VERIFIED_KEYS = UNESTABLISHED_VERIFIED_KEYS


def _export_account_revenue(account: object) -> object:
    """One account's served copy as a download prints it: the figures its revenue flags do not establish are
    None, written as empty cells. A copy; the served payload is untouched."""
    if not isinstance(account, dict) or not isinstance(account.get("metrics"), dict):
        return account
    metrics = account["metrics"]
    nulled = {}
    if metrics.get("revenue_established") is not True:
        nulled.update({key: None for key in _UNESTABLISHED_REVENUE_KEYS if key in metrics})
    if metrics.get("verified_revenue_established") is not True:
        nulled.update({key: None for key in _UNESTABLISHED_VERIFIED_KEYS if key in metrics})
    # §10.4, §11: the withholding basis the served copy marks as not established (its rate is None already) is an
    # empty cell too, as the dashboard reads it N/A.
    if metrics.get(WITHHOLDING_BASIS_UNESTABLISHED) is True:
        nulled.update({key: None for key in UNESTABLISHED_WITHHOLDING_BASIS_KEYS if key in metrics})
    # §10.4, §10.8: the Zelle figures' parts of True and Held are empty cells too (`_zelle_deposit_rows`); the
    # captured rows' count, total and non-revenue part stay.
    if ZELLE_DEPOSITS_KEY in metrics:
        zelle = unestablished_zelle_figures(
            metrics[ZELLE_DEPOSITS_KEY], established=metrics.get("revenue_established") is True,
            verified_established=metrics.get("verified_revenue_established") is True)
        if zelle is not metrics[ZELLE_DEPOSITS_KEY]:
            nulled[ZELLE_DEPOSITS_KEY] = zelle
    return {**account, "metrics": {**metrics, **nulled}} if nulled else account


def _export_revenue_view(payload: object) -> object:
    """A served payload as the statement downloads print it, either shape (`_export_account_revenue`)."""
    if isinstance(payload, dict) and is_document_payload(payload):
        return {**payload, "accounts": [_export_account_revenue(account) for account in payload["accounts"]]}
    return _export_account_revenue(payload)
