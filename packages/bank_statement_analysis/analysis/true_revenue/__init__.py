"""The true-revenue pass (docs/superpowers/specs/2026-09-28-true-revenue-design.md §5, §8). Its entry is `pass7.apply_true_revenue_pass`.

Statement pass 7 (§6.2) runs after every verifying rule of `analysis/transaction_classifier/`. It reads each posted
credit's payer facts (channel family, payer region, payer name and key, entry fields, the holds of §8.1), then runs
Q7's credit-union arm (§8.7) and the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold names, and last
gives every posted credit its tier and reason (§5.3), in the order of §8.10.

The payer region, payer name, entry fields and wire reading are the 5.5 readers' (S2.1 to S2.4): a holder's name in
the receiver field never names a payer (§5.2), a glued leading date never changes a reading (revenue_text), the
§7.9 wire vetoes are `_wire_vetoed` itself, and a wire is any row the 5.5 wire vetoes read as one
(`_wire_vetoes_apply`). The hold words follow the owner's veto convention: a spelling of four letters or more (all
its words counted) takes a (?<![A-Z]) left boundary, so a digit glued on its left never hides it; a spelling of
three letters or fewer keeps \\b.
"""
