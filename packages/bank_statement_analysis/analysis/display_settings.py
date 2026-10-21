"""The owner's display settings and their defaults. `webapp/settings.py` keeps the saved values; the served view
(`analysis/served_view.py`) and the package apply them to a copy and never rewrite the stored analysis."""
from __future__ import annotations

from analysis.flag_groups import FLAG_SETTING_KEYS

#: Every setting, with its default. Unknown keys are refused on save and ignored on load.
DEFAULTS: dict[str, bool] = {
    # The NSF count (negative-ending days) counts printed days only by default.
    # On: a day with no activity carries the previous day's ending balance and counts if it is negative.
    "nsf_carry_over": False,
    # "Mark Zelle Payments as True Revenue", Yes by default.
    # No: every Zelle deposit is non-revenue (zelle_excluded) and its total is shown. A display setting: the analysis
    # stores both readings (analysis/zelle_view.py), so a change applies to every job analysed since at once.
    "zelle_true_revenue": True,
    # One checkbox per flag group (analysis/flag_groups.py), each on by default. Unticking one hides that group
    # wherever an analysis is shown or exported; it never moves a row into review or into lender math
    # (analysis/flagged_view.py).
    **{key: True for key in FLAG_SETTING_KEYS},
}
