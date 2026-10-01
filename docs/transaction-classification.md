# Transaction Classification Contract

`analysis.transaction_classifier.classify_statement_transactions` creates the
authoritative classification record for every parsed ledger row. The pipeline
creates this list once, then passes the same records to metrics, detection,
serialization, API responses, downloads, dashboard cards, filters, and evidence
tables. Consumers must use contribution flags on these records and must not scan
transaction descriptions independently.

Classification version 5.0 (2026-09-24) applies the owner's lender rulings in
`docs/superpowers/specs/2026-09-24-lender-detection-design.md` (decisions D1-D12).
Version 5.1 (2026-09-26) clarifies D6: a recurrence needs at least three
different dates, and D6 never takes a card-purchase posting.
Version 5.2 (2026-09-27) clarifies D6 again: D6 never takes a row whose words
name compensation, and a masked recipient account printed after `TO` is part
of the payee.
Version 5.3 (2026-09-27) is the false-potential-lender release: more D6 skips,
fee, NSF, cheque, card, payroll, mortgage and POS wording, admitted payees
printed in the bank's field order, unconfirmed flag payees routed to their flag,
D11 naming fixes, one Potential Lenders line per unnamed payee key, and the
Debt relief group.
Version 5.4 (2026-09-28) applies the owner's ruling that Idea Financial is a
counted lender, no longer a line of credit: its debits are `confirmed_lender`
rows, except a row whose own words say LOC or LINE OF CREDIT, which stays
`line_of_credit` (D9), and its credits stay financing proceeds (D1).

## States and precedence

Every row has exactly one state:

`confirmed_lender`, `potential_lender`, `insurance`, `alternative_position`,
`line_of_credit`, `vehicle_financing`, `bank_loan`, `mortgage`,
`lease_or_rental`, `personal_loan`, `floor_plan_financing`, `factoring`,
`debt_relief`, `fee`, `transfer`, `credit_card_payment`, `payroll`, `tax`,
`utility`, `rent`, `pos`, `atm`, `nsf_or_return`, `refund_or_reversal`, or
`other`.

`lease_or_equipment_financing` is retired: no rule produces it since version
5.0, but records stored before 5.0 carry it and still validate.

Only MCA and revenue-based funders and equipment financing are
`confirmed_lender`. Twelve groups are flagged instead. Their debits never enter
lender counts, lender totals, withholding or potential exposure:

| State | `flagged_group` | Label |
|---|---|---|
| `alternative_position` | `alternative_positions` | Alternative positions |
| `line_of_credit` | `lines_of_credit` | Lines of credit |
| `credit_card_payment` | `credit_cards` | Credit cards |
| `vehicle_financing` | `vehicle_financing` | Vehicle loans & leases |
| `bank_loan` | `bank_loans` | Bank loans |
| `mortgage` | `mortgages` | Mortgages |
| `lease_or_rental` | `leases_rentals` | Leases & rentals |
| `personal_loan` | `personal_loans` | Personal loans |
| `floor_plan_financing` | `floor_plan` | Floor plan |
| `factoring` | `factoring` | Factoring |
| `insurance` (premium-finance payees only) | `premium_financing` | Premium financing |
| `debt_relief` | `debt_relief` | Debt relief |

Premium financing is the one group that is not a state. Its rows stay
`insurance` and keep their insurance totals. The insurance rule sets
`flagged_group="premium_financing"` on a debit whose insurer is a
premium-finance payee (`PREMIUM_FINANCE_ALIASES`).

A flagged group's credits are another matter. A credit from a financing group
(every flagged group except credit cards, leases & rentals, premium financing,
factoring and debt relief) is financing proceeds, and D1 subtracts it from
eligible deposits as it does a lender's credit (see "Withholding rate"). Three
kinds of credit are not subtracted: a payout-credit entity's credits
(`PAYOUT_CREDIT_ENTITIES`), which are the holder's own sales; a premium-finance
payee's credits, which keep the insurance credit treatment; and a factoring
payee's credits (owner ruling 2026-09-26), which are the business's own sales,
paid by the factor that bought its invoices. A factoring credit takes the
operating-revenue path, as a payout credit does, and it is also flagged: its
state is `factoring`, its entity is the payee, and it counts in the Factoring
group as a credit. Since audit fix batch B6 (I10), a factoring review entity of
the ledger (`FACTORING_REVIEW_ENTITIES`, a factor not yet confirmed) is read
the same way on a credit, marked unconfirmed (`review_required`), where the
potential tier made it non-revenue; its debits keep the potential tier. A
factoring payee's credit is never verified, whichever rule read it. Debt-relief
payees (5.3) never apply to credits: their
credits are the debtor's own escrow refunds, and they follow the rules any
other credit follows.

The group list lives in `analysis/flag_groups.py`. A flagged row carries
`flagged_group`; a posted flagged debit, and a posted factoring credit, also
set `contributes_to_flagged_totals`. Proven duplicates, settlement-reversed
debits and credits that the reversal pass pairs clear it. The web app hides
unticked groups at serving time; the stored record never changes.

Every posted credit also has exactly one independent revenue state:

`verified_revenue`, `unverified_deposit`, or `non_revenue`.

This second state does not replace the transaction state. For example, a
returned e-transfer remains `refund_or_reversal` and is also `non_revenue`.
Revenue classification applies cancellations, reversals, financing proceeds,
and strong non-revenue exclusions before operating-income rules. Identifiable
card credits and refunds, purchase/payment/ACH returns, chargebacks, own-account
transfers, financing and insurance proceeds, tax refunds, rewards, fee refunds,
interest, and reimbursements bypass manual revenue review as `non_revenue`.
A maintained operating-source alias is supporting evidence, not sufficient
evidence by itself. Verification also requires credit direction plus
settlement, payout, merchant-deposit, or similar context; alternatively,
statement-level recurrence on a business account or related processing fees,
commissions, chargebacks, and adjustments can supply that context. Generic ACH,
wire, RTP, Zelle, and e-transfer credits, mobile/branch/ATM/night deposits,
checks, cash deposits, and unidentified credits are `unverified_deposit` until
reviewed. Own-account transfers are excluded when the description identifies
the internal account or self-service transfer channel.

### True revenue and the revenue tiers (classification 5.5 and 5.6)

True revenue is every posted credit except known non-revenue and the credits
held for review; Verified revenue is its part with positive proof
(`docs/superpowers/specs/2026-09-28-true-revenue-design.md`). Since 5.6 every
posted credit also carries exactly one revenue tier, stored beside its state:

| Tier | State | In True revenue |
|---|---|---|
| `verified` | `verified_revenue` | yes |
| `counted_flagged` | `unverified_deposit` | yes |
| `excluded_pending_review` | `unverified_deposit` | no |
| `non_revenue` | `non_revenue` | no |

A counted or held credit names its reason (`revenue_tier_reason`). The codes
and their labels live in one table, `analysis/revenue.py`
`REVENUE_TIER_REASONS`, which the dashboard mirrors.

**Precedence.** One credit's decision (`_classify_credit_revenue`) takes the
first match: a direction conflict, a reversal, an auto lender paying a dealer,
an insurer, the financing-proceeds rules, the strong non-revenue rules and
own-account transfers, the channel gate, the operating registry, the
card-settlement forms, the verified descriptors (the holder's own name never
verifies), customer and invoice wording, payer accounts-payable remittance,
public payers, wire remittance, then the fallback. The statement passes then run
in order: duplicates, reversal pairs, the recurrence pass (pooled operating
sources verify by recurrence; the pool never shrinks and a veto word keeps a
row out), the auction and property branches, the payer-remittance counter-debit
guard, and last the true-revenue pass (`analysis/true_revenue.py`), which tiers
every posted credit. A `non_revenue` credit stays `non_revenue` except where a
rule narrows a non-revenue pattern (spec §6.3); a held credit enters True
revenue only when an analyst confirms it.

**Holds.** The true-revenue pass holds a credit (tier
`excluded_pending_review`) in this order: insurer payer, insurer-named payer,
possible return, financing-named payer, payer debited as a lender, the holder's
own name, payroll or salary, personal income, a non-sale purpose, a payer also
debited this account; then by channel: a wire with no sender, a transfer with no
counterparty or naming an account, and repeated round person-to-person sums.
The $1 floor is absolute: a posted credit under $1 is never verified and never
counted, whichever rule read it, and is held as `non_sale_purpose`.
Every other unverified credit is counted (`counted_flagged`) with its reason. A
statement needs revenue review (`revenue_review_required`) when it has an
undecided direction conflict (one an analyst confirmed or rejected no longer
gates), when its held credits are ten percent or more of its posted
credits (compared in integer cents, `REVENUE_REVIEW_HELD_SHARE`), or when its
revenue does not reconcile.

**Extending the tables.** Every table below is checked by
`python tools/operating_registry.py --check` and by its tests. So are the other
5.6 tables of `analysis/classification_registry.py`: a factoring payer
(`FACTORING_PAYOUT_PAYERS`) collides with no ledger, operating or insurer alias;
the owner-money and deferred-source patterns (`OWNER_MONEY_PLATFORMS`,
`SECTION_15_DEFERRED_PAYERS`) compile and read no operating alias; and the
sending banks' and statement banks' printed names (`P2P_SENDING_BANK_NAMES`,
`STATEMENT_BANK_PRINTED_NAMES`) are normalized and name no form twice.
- `OPERATING_REVENUE_SOURCE_ALIASES` and `OPERATING_REVENUE_SOURCE_TYPES`
  (`analysis/classification_registry.py`): a processor, marketplace or platform
  that pays a business its own sales. An alias is the name as banks print it, in
  upper case. A name a bank cuts at 16 characters goes in
  `OPERATING_REVENUE_TRUNCATIONS`, never as a bare prefix another entity could
  share. A source whose aliases also name its capital product goes in
  `OPERATING_SOURCES_READ_WITH_VETOES`, and the capital product in
  `PROCESSOR_ADVANCE_PRODUCTS`.
- `OPERATING_SOURCE_PAYOUT_FORMS` and `CARD_SETTLEMENT_CREDIT_FORMS`: a printed
  payout or settlement shape that verifies on its own. Each form is a whole-row
  pattern with its refusal words; add a positive and a negative test in the
  bank's format.
- `HEALTHCARE_PAYER_ALIASES`: a claims payer (a Medicare contractor, Medicaid,
  a large insurer or its payment network) whose claim payments are a practice's
  revenue.
- `DEALER_FUNDING_PAYERS`: an auto lender whose funding of a dealer's contract
  is the dealer's sale. A credit union's vehicle-purchase entry (`VHCL PURCH`)
  verifies as dealer funding (`auto_lender_dealer_funding`) when the statement
  prints two or more of them; a lone one is held as `financing_named_payer`.
- `PAYOUT_CREDIT_ENTITIES`: a platform whose payout is the business's sales but
  whose name is also its financing partner (buy-now-pay-later settlements
  included since 2026-09-28); its credits are counted, never verified.

#### Review decisions (2026-09-29)

- A date glued to a row never changes its reading (spec §7.0).
- The holder's own name (a receiver field, an incoming wire's beneficiary) never names a payer or a source (§5.2).
- An own-account transfer leaves `non_revenue` only on a distinctive payer word; account adjectives stay own-account (§6.1 step 9, §7.11).
- The wire vetoes also read a wire glued to its reference and a wire that cites an invoice (§7.9).
- The recurrence veto's holder-word exemption reads only on store-name platforms (§7.0).
- Statement pass 6, the counter-debit guard, reads a debit's first distinctive word, never a card purchase's city; since the final review it leaves a card purchase out, unless the classifier names it as a lender (§7.5).
- The true-revenue pass's `payer_also_debited` hold never reads a card purchase: buying at a merchant that shares the payer's word is spending, not the payer's money coming back (§8.1; A1 census, 2026-09-30). A card-form debit the classifier names as a lender still counts for `payer_debited_as_lender`.
- A buy-now-pay-later consumer credit (a return, withdrawal, refund or card credit) keeps its 5.4 reading; the OQ2 ruling covers settlements only (§19).
- A direction conflict is never lifted, grouped or counted by any pass (§6.1 step 2, §7.0).
- A bare transfer is held as `transfer_no_counterparty` (§8.2).
- The $1 floor is absolute: a posted credit under $1 is never verified and never counted, whichever rule read it, and never counts toward a repeat. It is held as `non_sale_purpose` (the reason table has no micro-deposit code); one a rule verified is held by the true-revenue pass's last step (method `micro_deposit_floor`), a credit already held keeps its first hold, and a non-revenue credit stays non-revenue (§7.0, §7.8, §8.10).
- Owner money, a brokerage, investing or crypto-exchange platform's credit included, is held as `non_sale_purpose` (§7.5, §8.1).
- A deferred source stays counted and flagged, never verified by Q5 or Q6 (§15, §19 OQ4).
- Repeated round sums from one sender are held as `p2p_round_repeat`, a named transfer printed without FROM included (§8.4).
- Q5 and Q6 leave a row the operating registry names, and a NET SETTLE row, to its own rule (§7.1, §8.5, §8.6).
- VIREMENT is a person-to-person rail only in its Interac forms (§8.4).
- A cancelled French transfer is a reversal (§6.1 step 3).
- Quebec's numbered companies (`NNNN-NNNN`) are numbered-company payers: counted, never verified (§5.2, T11).
- Q7 honours the wording holds of §8.1 (never the holder's name: the lender is read without the receiver field), keeps its lender's name, and Suncoast Credit Union verifies only through its credit-union arm (§8.7).
- A3 fix (precision sample, 2026-09-30): a wire's channel and layout words (`INCOMING`, `FEDWIRE`, `FED WIRE`, `WIRE`, `TRANSFER`, `CREDIT`, `CHIPS`, `SWIFT`, `BOOK` …) never name a transfer's counterparty, and a transfer that prints wire wording and names no counterparty (`INCOMING FEDWIRE TRANSFER`) is a wire with no sender, held as `wire_no_sender` (Q5, §8.5).
- A3 fix: the SBA's name cut to an originator field (a payer region that is exactly `SMALL BUSINESS`, or `SMALL BUSINESS` and a leading cut of `ADMINISTRATION`) is an SBA disbursement, financing proceeds (`sba_disbursement_credit`, §7.11); a payer whose name goes on in other words (`SMALL BUSINESS SOLUTIONS LLC`) and a transfer from an account so named stay as they were.
- A3 fix: foreign-exchange and currency-conversion wording (`FOREIGN EXCHANGE`, `FX CONVERSION`, `CURRENCY EXCHANGE`, `CURRENCY CONVERSION`, `CONVERSION DE DEVISES`, `CHANGE DE DEVISES` …) never names a counterparty, and a credit that prints it and names no other payer is the holder's own money converted, held as `non_sale_purpose` (§8.1's own-money group, as a sweep is; it designates no account, so it is no T13 named transfer). A named payer that prints it keeps its reading. A3 review: the statement's own bank printing its name right before the wording names no payer (its whole name, and the short forms of `STATEMENT_BANK_PRINTED_NAMES` when the bank field contains one of the entry's bank words: `ROYAL`, `RBC`, `ROYAL BANK`, `RBC ROYAL BANK` on a statement whose bank field contains `ROYAL BANK OF CANADA`, `RBC ROYAL BANK`, the whole word `RBC` or `BANQUE ROYALE`; a bare `ROYAL BANK`, as in the Royal Bank of Scotland's name, is no marker), so `ROYAL FOREIGN EXCHANGE DEPOSIT` there is held. A named currency-exchange company is a payer: another name word beside the wording (neither a legal form nor an article) names it on any row, and a company form beside the wording (`LLC`, `INC`, `CORP`, `CO`, `LTD`, `INTERNATIONAL`, `INTL`) names it only on an originator field (an ACH originator, or a wire's labelled sender: `CURRENCY EXCHANGE INTERNATIONAL DES:PAYMENT`); elsewhere it names nobody (`INTL FOREIGN EXCHANGE DEPOSIT`, `FX CONVERSION LLC <n>` and BMO's `INCOMING WIRE PAYMENT … CA FOREIGN EXCHANGE LTD` stay held).
- A3 fix: a title firm named on the payer region (the whole word `TITLE` beside `AGENCY`, `CO`, `COMPANY`, `TRUST`, `INSURANCE`, `GUARANTY`, `SERVICES`, `ESCROW`, `CLOSING` or a legal form, or a national title insurer such as Chicago Title, First American Title, Fidelity National Title, Old Republic Title or Stewart Title) pays out property-closing proceeds, an asset sale: held as `non_sale_purpose` on wires and ACH alike, never verified by Q5 or Q6. `TITLEIST` and `TITLE BOXING CLUB` are no title firm. A title firm's credit whose purpose (a wire's OBI, RMR, PMT DET, RFB or URI field; an ACH entry; a transfer's memo) cites the holder's fee paid at closing (`COMMISSION`, `COMM`, `ORIGINATION`, `ORIG FEE`, `BROKER`, `INVOICE`, `INV`, `CONSULT…`, `FEE FOR SERVICES`, `SERVICES RENDERED`) is not held by it and takes its normal reading (orchestrator ruling). A3 review: a wire's REF field is never read for it: on the Fedwire layout it is the sender's bank reference (`REF COMM BANK NYC` exempts nothing), and Bank of America's `SERVICE REF` is its own reference; a URI printed inside REF (a book transfer's) is read, and so is Santander's REF field, which is its purpose (`ACCT <n> <originator> REF <purpose>`). `ORIG FEE` inside a purpose field is purpose wording, never an originator label.
- A3 fix: a wire that prints its sender right after its label, with no originator label, names that sender (§5.2): BMO's `INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT <country> <sender>`, `INCOMING WIRE <reference> <sender> NOTPROVIDED`, TD Bank's `WIRE TRANSFER INCOMING <sender>`, Wilson & Muir's `WIRE TRANSFER FROM <sender>`, Capital One's `WIRE TRANSFER DEPOSIT <sender> <reference>`, Scotiabank's `INCOMING WIRE TRANSFER <sender> WIRE PAYMENT` and SECU's `DOMESTIC WIRE DEPOSIT WIRE IN <sender>`; such a wire is no longer held as `wire_no_sender` when its sender prints a name word, and takes its normal reading (Q5). A sender whose only words after the label are a reference token and a legal form (`WIRE TRANSFER INCOMING 1ABC LLC`) names nobody, as the person-to-person reader rules: that wire stays `wire_no_sender`, which keeps census guard G4 green. A wire sender's name that a line wrap splits is read across the split for the financing roots too (`F INANCIAL`, `SERVICIN G`), on every wire sender, labelled (`B/O`, `ORIG` …) or read after the label; A3 review round 3: a join counts only when its two words together spell a financing word (`FINANCIAL`, `FUNDING`, `SERVICING`, `CAPITAL`, `LENDING`, `MORTGAGE`, `LOAN` and the other T4 roots spelled out) or a prefix of one of five letters or more, so two words that spell none never make one (`SERVICE REPAIR` is no `SERVICER`, `SOLO ANALYTICS` no `LOAN`, `ALLEN D` no `LEND`, `CAPT L` no `CAPTL`); A3-G review: a Fedwire or CHIPS sender's city and state after `B/O` are no longer skipped; they join only as any two words do, so `LAMORT GA` and `GLEN DE` spell no financing word and stay counted, while `B O NORTHWIND F INANCIAL CO` is held.
- A3 review: a payer whose name ends in a glued `CRED` (`FABRICRED INC`, a credit provider's glued name) is held as `financing_named_payer`, as §7.9's word-end `CRED` arm reads it. A3 review round 2: it is read on the payer's name only (a wire's sender, an ACH originator, a transfer's sender after `FROM`, and, round 3, a payer region that prints a company form: `ACH CREDIT FABRICRED LLC`), never on an entry field (`DES:ACCTCRED`) or a row whose payer words are neither (`ACHCRED 12345678`); the whole word `CRED` and the whole words `SACRED` and `ACCRED` are no root, and any other glued `…CRED` name is (§8.1, T4).
- A3-G (the redrawn largest-counted stratum, 2026-09-30): the Canada Revenue Agency's income-tax refund (`CANADA RIT`, `CANADA RIF`, `DIRECT DEPOSIT CANADA RIT RIF`) is a tax refund, `non_revenue` (§7.11 T5), when the form starts the payer (after DIRECT DEPOSIT, DEP, EFT or PAY; A3-G review; A3-G re-review: read after the classifier's revenue text and template prefixes, so a glued or spaced date, `GC`, `MISC PAYMENT`, `PAYMENT FROM`, `PREAUTHORIZED CREDIT` or `ELECTRONIC DEPOSIT FROM` may come before it, while `FABRIKAM LIFE CANADA RIF PMT` names its payer); the CRA's benefit, credit and payment forms (`CANADA GST TPS`, `GST CANADA`, the child and other benefits) were left for the owner, who ruled on them on 2026-09-30 (GOV, below).
- A3-G: a wire whose originator field reads as a bank (`BANK`, `BANCORP`, `BANK N A`, `CREDIT UNION`, `SAVINGS BANK`, `FEDERAL SAVINGS`, or Bank of America's sending bank itself) is held as `financing_named_payer`; only the originator field is read, and a bank's merchant-services, bankcard, processor or settlement form is a settlement, never held so; A3-G review: never a food or blood bank or a company whose name holds BANK (a company form counts only as the bank's own, right after its bank word), and the sending-bank arm needs eight letters and an originator with no company form (§8.1, T4); A3-G re-review: a form word that is the address's state is never a company form, so `B/O NORTHWIND BANK DENVER CO 80202 US` is a bank and a Fedwire `B/O SAMPLE CREDIT UNION BOULDER CO` a credit union; A3-G re-review 2: `CO` or `NV` is the state only when a ZIP or the country code (`US`, `USA`) follows it, or when it ends a Fedwire or CHIPS `B/O` field's city and state; at the end of any other field (Bank of America's `ORIG`, Chase's book-transfer `B O`) it is a company form, so `ORIG:LEFT BANK TRADING CO`, `B O WEST BANK OIL CO REF …` and `ORIG:BANK STREET HOLDINGS NV` are companies, and `ORIG:NORTHWIND SUPPLY CO` is never its sending bank `NORTHWIND SUPPLY`. A3-G refinement: a bank that names the ultimate originator after a relay label (`ORG`, `B/O`, `ORIGINATOR`, `ORIG CUST`, `BY ORDER OF`; never `ORIGINATOR TO BENEFICIARY` or `ORG TO BNF`) only relays, and that customer is the wire's sender, read normally. A3-G re-review: the wire's originator label takes the same guards (`… NORTHWIND SUPPLY LLC ORG TO BNF INFO 1234` reads `NORTHWIND SUPPLY LLC`).
- A3-G refinement: Bank of America's `WIRE TYPE BOOK IN` reads its originator after `ORIG`, as `WIRE TYPE WIRE IN` does (§7.11 T19); a wire sender read as bare channel words (`WIRE`, `TRANSFER`, `BOOK`, `CREDIT`) names nobody (`wire_no_sender`); and when the account-name field names nobody (a product name), the holder's name the statement's own incoming receiver fields print on two credits or more from two distinct originators or more (A3-G re-review: compared by the payer's first distinctive word, so one platform's two spellings are one originator) is the holder's too, for the holder hold only, matched run together with twelve letters or more, and only on classified wire layouts, book transfers and transfer or person-to-person rows (never the word WIRE in an ACH entry) (never an ACH, card, processor or marketplace settlement, a push rail, or a row an earlier rule verified) (§5.2).
- A3-G: a wire originator's SWIFT 50F line number printed with its slash (`1/`, `2/`, `3/`) is never part of its name, while a name that starts with a number keeps it (§5.2), and a sender that is the holder's account name cut short (two whole words before the cut, or twelve letters) is the holder, `holder_name` (§5.2).
- A3-G: a credit from a personal trust (a person's name ending in `TRUST`, `TTEE`, or a trust adjective and `TR`; A3-G review: the form ends the name, the words before it read as a person's, and never a trust company's or a bank's form after it, a lawyer's or client trust account, a title or escrow firm; A3-G re-review: a wire originator's address after the form holds only place words, a city, a two-letter state, a ZIP and a country code, never a business, lawyer, company-form, `ACCOUNT`, `SERVICES`, `DEPT` or institution word, and the lawyer and IOLTA words are read across the whole sender; A3-G re-review 2: the banned words are a finite list of trade and institution words (`CUSTODY`, `CUSTODIAN`, `ADMINISTRATOR` and `ADMINISTRATORS` among them), and the address prints at most 3 words of its own before its state, never counting the agreement, date, PO box and country words, a number, a street type or an initial; A3-G re-review 3: two or more single letters in a row that join into a company form, such as a dotted `L.L.C.`, `L.P.`, `P.A.` or `P.C.`, make the sender a company) is owner money, held as `non_sale_purpose` (§8.1).
- A3-H (the Verified strata's misses at s56c): a freight-factoring payer the registry's `FACTORING_PAYOUT_PAYERS` names (the registry entry carries its name and evidence) pays the carrier's own invoices: its credits, wire or ACH, are `counted_flagged` / `factoring_payout` after the holds, and Q5 and Q6 never verify them nor count them toward a repeat. A3-H review: a factor is never verified by any path (an earlier rule's verification, such as an invoice-purpose wire's or a remittance descriptor's, is overruled: method `factoring_payout_payer`), and its alias is read only as the payer region (the ACH originator or the wire sender), followed only by company forms: `<alias> FOR PETS LLC`, `<alias> CLEANING LLC` and another payer's purpose citing the alias are other payers. A3-H review 2: a glued company form (`<alias>LLC`), a `DBA` tail, an entry word, date or number that falls into the region (`PAYMENT`, `PMT`), and a B/O field's address (place words ending in a US state, at most three of its own, as the personal-trust rule reads one) may follow the alias; the table holds the entity's two spellings of its apostrophe; and a factor claims its row as a factoring payee does, so a financing word in its trade name holds nothing. The table is read by the true-revenue pass alone; it is no lender-ledger entity, so its debits and every payee group, flag and lender reading are unchanged. A `SCHEDULE <n>` purpose alone names no factor.
- A3-H: a healthcare, insurer or health-plan payer (the healthcare payer table, an insurer's name, or `INS` on the payer region) whose entry field (`DES`, `CO ENTRY DESCR`) prints a premium code (`PREM`, `PREMIUM`, glued `PREMSEC`) is a commission or a premium refund, never a claim payment: Q6c and Q5 refuse it and it is `counted_flagged` / `named_payer_purpose_refused` (on such a row a premium word is no member-word hold). A3-H review: a row with no entry field keeps its reading; a `COMM` or `COMMISSION` word in the entry keeps the reading even beside `PREM`; government payers (state, county or federal public payers, Medicare and its contractors, Medicaid, TRICARE, VA) keep their reading. A `PREM REFUND` the reversal rule reads stays `non_revenue`.
- Final review (2026-09-30): a PPD or WEB entry is read only in the SEC code's slot (Chase's `SEC <code>` or the code before `TRACE` or `ID`, the code Bank of America prints after the company id or at the row's end, `ACH <code>`), never in a name or receiver field (§8.6).
- Final review: every receiver vocabulary is built from one tuple (`analysis/description_text.py`), `RECV NAME` included (§5.2).
- Final review: a healthcare alias of five letters or fewer, and `ANTHEM`, names a healthcare payer only as the whole payer name (a company form, a health-plan word or another healthcare alias may follow): `ANTHEM ROOFING` and `WPS INDUSTRIES` are other companies (§8.6 Q6c).
- Final review: on a store-name platform, a veto word that is the whole entry field, or forms it alone with generic words, is never spared as the holder's word (`DOORDASH INC DES:CAPITAL` is held as financing) (§7.0).
- Final review: Q7 reads the non-revenue patterns without the holder's receiver name (a declared move out of `non_revenue`) and its insurer on step 5's lookup text (§8.7).
- Final review: a reversal pair's widened markers change the credit's revenue reading only; the debit's lender side keeps classification 5.4's pairs (§6.2 pass 4).
- Final review: a factor's alias followed by `FOR`, `OF`, `AND` or `THE` names another payer, never the factor at an address (§8.9).
- Re-review: on a store-name platform a veto word that leads the entry field is never the holder's store word, whatever follows it (`DOORDASH INC DES:CAPITAL DISB` is held as financing) (§7.0).
- Re-review: a processor, marketplace or platform credit whose entry field leads with a financing word (`CAPITAL`, `LENDING`, `LOAN`, `ADVANCE`, `FUNDING`, `FINANCING` …) is never verified; it is held as `financing_named_payer` (§7.2).
- Re-review: a PPD or WEB code is also read as the row's last word after a receiver value (never the holder's own last word), before `DES` after a company form or a reference, and right after a row's posting label (`ACH CREDIT PPD`) (§8.6).
- FW wave 3: a store named with a financing word keeps its payouts: an entry whose words (two or more) are a consecutive run of the holder's own name (`DES:CAPITAL GRILLE` for a holder named `... CAPITAL GRILLE ...`) is the store's name, never financing; a bare `DES:CAPITAL` or a financing entry stays held (§7.0, §7.2).
- FW wave 3: PPD before `DES` is the SEC code after any word (`NORTHWIND SUPPLY PPD DES:` is a consumer entry) (§8.6).
- GOV (the owner's ruling of 2026-09-30: true revenue is the money the business earns by selling goods or services, as the MCA industry counts it, so government money it did not earn leaves True revenue). Class B, a personal benefit, is held as `personal_income`: the federal benefit descriptors the banks print before the CRA's name (`CANADA CHILD BENEFIT`, `CANADA ESSENTIALS BENEFIT` and its full name `CANADA GROCERIES AND ESSENTIALS BENEFIT`, `CANADA WORKERS BENEFIT`, `CANADA DISABILITY BENEFIT`, `OLD AGE SECURITY`), a provincial benefit the CRA pays (`PROV LOCAL GVT PAYMENT CANADA`, the Canada PRO labels `… CANADA PRO`, `PROV LOCAL GVT PRO <province>` and `CANADA PRO DEPOSIT`), a state's unemployment deposit (`UI DD`) and the IRS's stimulus (`TAX EIP`, on an IRS Treasury row). GOV review: a descriptor is read as the whole payer after the posting words, with the CRA's name around it, and a company form after `UI DD` or `TAX EIP` vetoes it, so `CANADA CHILD CARE CENTRE INC`, `CANADA DISABILITY BENEFITS CONSULTING INC`, `OLD AGE SECURITY SYSTEMS LTD` and `NORTHWIND UI DD LLC` are payers (§8.1).
- GOV, class C: a tax refund is `non_revenue` (strong non-revenue rule): a business's GST/HST refund as the whole payer after the posting words (`CANADA GST TPS`, `GST CANADA`, Revenu Quebec's `RQ GST`, and with the CRA's name, a country code or the GST program account after them; `GST CANADA LOGISTICS INC` is a payer), and a payment the IRS issues through the Treasury (`IRS TREAS 310`) that prints no entry or a refund-worded one; GOV review: an IRS vendor payment (`MISC PAY`, `VENDOR`, `VENDOR PAY`, any other entry) keeps its reading, and the child tax credit and stimulus are class B (§7.11 T5).
- GOV, class D: a grant or subsidy is held as `non_sale_purpose`: HHS's Provider Relief Fund (`US HHS STIMULUS`, `HHSPAYMENT`), the USDA's farm programs (`FSA TREAS 310`, and GOV review `CCC TREAS 310`; `USDA TREAS 310` keeps its reading), the CRA's wage subsidy (`CANADA CEWS` as the whole payer) and ESDC's federal payment code (`GOVERNMENT ESDC … FEDERAL PMT`, its grants and contributions) (§8.1).
- GOV, classes A and E: a government or public program paying the business for its goods or services keeps its reading (a Treasury vendor payment, `DOD MISC`, a county's or a ministry's accounts payable, `GC CDCP` paying a dentist, Medicaid and TRICARE plans paying a provider), and so does a form whose purpose the row does not print (`36 TREAS 310 MISC PAY`, `GOUV QUEBEC MSP`, a provincial payment from a province, workers' compensation boards, a state's direct deposit to a child-care provider), which waits for the owner.
- Audit fix batch B2 (I01): a bank's name never names a transfer's counterparty (a sending bank's, the statement's own, a bank's name glued to `TRNSFER`, a credit union's one-word name before `CU` or `FCU`, `BANK` or `SAVINGS`), nor does an online-banking channel code or account description (`CBUSOL`, `OLB`, `EXT`, `CMO`, `TELEPHONE BANKING`, `PHONE`, `CRD`, `FSB`, `PROTECTION`, `OVERDRAFT`, `FOUND`, `BUSINESS BANKING`, `OPERATING ACCOUNT`, `FUNDING` beside `TRANSFER`): such a transfer is held as `transfer_no_counterparty`; a company or person after `FROM` keeps the named reading, and a custodian's name is not removed. A bare `FROM <digits>` designates an account (T13) unless it starts a numbered company. An ACH payer that is only a bank's name and an account description (`<bank> SAVINGS <n> ACH`) is held as `transfer_no_counterparty` and never verified by repetition. The own-account sources add `DDA`, `CHECKG`, `CL`, `LN`, `CRD`, `CREDIT CARD`, `CREDIT LINE`, `LINE OF CREDIT` and `LOC`, `FRM` reads as `FROM` and `XFR` as transfer wording, and Truist's `ONLINE TRANSFER ONLINE FROM <n>` is own-account (`MOBILE` between them is not read) (§8.2, §7.11).
- Audit fix batch B2 (I21): the holder's overdraft-protection sweeps (`OVERDRAFT PROTECTION FROM`, `OD PROTECTION TRANSFER`, `OVERDRAFT XFER FROM`, `ODP TRANSFER`) and Regions' `EB FROM CHECKING|SAVINGS` are `non_revenue`; `TRF`, `TRSFR`, `TRANSF`, `XFR` and `TRANSFER` glued to digits are transfer wording (never the e-transfer rail's glued `E TRANSFER<n>`; `TRANSFERS` waits for B8); a Square savings folder (`TRANSFER IN RAINY DAY`, `TRANSFER IN RENT`) is held as `transfer_account_designation`, never on Wealthsimple (§7.11, §8.2, T13).
- Audit fix batch B2 (I20, §6.3 narrowing 8): a named sender printed after an own-account designation (Bank of America's `… TRANSFER FROM CHK|SAV <n> CONFIRMATION <reference> <sender>`, a credit union's `TFR FROM X…<n> TRANSFER DEPOSIT <sender>`) that the holder test does not match is no own-account transfer: it is held as `transfer_account_designation` for review, never counted or verified; with no sender, or the holder's own name, it stays `non_revenue`, and Navy Federal's `TRANSFER FROM SHARES <name>` stays `non_revenue` (§6.3, T13).
- Audit fix batch B2 (I48): an explicit cash, ATM or check deposit form beats bare transfer wording (`CASH DEPOSIT TRANSFER IN` is counted as `no_payer_printed`, `MOBILE CHECK DEPOSIT TRANSFER` as `check_deposit`); `TELLER TRANSFER` and `BRANCH TRANSFER` stay held (M4), and a branch or teller transfer that names its counterparty is a named transfer (T13) (§8.2, §8.3).
- Audit fix batch B3 (I03): pass 4's revenue side pairs a debit that undoes a deposit (a returned deposited item such as `RETURNED ITEM`, `RET DEP ITEM`, `DEPOSITED ITEM RETN`, `RETURN ITEM CHARGEBACK`; an error, transaction or deposit correction; a mobile, remote or ATM deposit adjustment; `ADJUSTMENT CORRECTION`; never the fee for it, never TD's `RTN NSF`) with an equal deposit-channel credit (check, cash, branch, ATM or bare deposit; never an electronic payment) 0 to 14 days before it, with no shared word, the earliest first, so a redeposit stays counted. The lender side keeps 5.4's pairs (§6.2 pass 4).
- Audit fix batch B3 (I04): step 3 also reads `ITEM RET NOT PAID`, `NOT PAID`, `RET DEP ITEM`, `ERROR|TRANSACTION CORRECTION`, a leading `CORRECTION`, `PURCHASE RET`, `DEBIT CARD CREDI`, a credit's leading `CHECKCARD <mmdd>`, `POINT OF SALE DEPOSIT <merchant>`, `PROVISIONAL CR`, `UNAUTHORIZED`, `RECLAIM`, a leading `REV MOBILE|POS|DEBIT|PURCHASE|ACH|CARD`, `RENV`, `RENVERSEMENT`, `RETOUR`, `REMBOURSEMENT` (with REIMBURSEMENT's provider carve-out, and the Quebec health insurance board) and fee waivers and courtesy refunds; pass 4 reads them on the credit only. A card credit printed first (`CARD CREDIT`, `CARD CREDIT <merchant>`) with no push or person-to-person rail is held as `possible_return`; Regions' Cash App and Apple Cash card credits stay counted `p2p`. Cash App and Apple Cash on a `DEBIT CARD CREDIT` join the push words only with the owner's switch `CASH_APP_CARD_PUSH_RELEASE` (off) (§6.1 step 3, §7.11, §8.1).
- Audit fix batch B3 (I11, §6.3 narrowing 9): with the owner's switch `PROCESSOR_CARD_PAYOUT_RELEASE` (off: it moves a real statement's pinned figures), a `DEBIT CARD CREDIT` or `POS CREDIT` whose whole payer is a merchant processor (`CARD_PAYOUT_PROCESSOR_NAMES`: Stripe, QuickBooks Payments with a bare `INTUIT`, Square, PocketSuite) is that processor's instant payout, counted and flagged as `platform_unconfirmed`, when the statement prints the processor's own ACH payout or pull and no card purchase at it (§7.11).
- Audit fix batch B3 (I43): card-rewards redemptions are `non_revenue`: a whole-row `CASH REDEMPTION`, `PURCHASE PAYBACK [AWARD]`, `POINTS REDEMPTION`, and `MR REDEEM` or `MEMBERSHIP REWARDS` beside a card issuer's name; a payer named `REDEMPTION …` keeps its reading (§7.11).
- Audit fix batch B3, review round 1: the new step-3 spellings stay off company names and memos. `RECLAIM` is read only with its reference glued after it or last on the row (CIBC's `E TRANSFER RECLAIM<digits>`), never `RECLAIM <name> LLC`; `NOT PAID` only after an item or return word or as the whole row; `UNAUTHORIZED`, and a leading `REV <rail>` or `RETOUR` not followed by a transaction word, a reference or `MDSE`, only with no legal-form word later on the row. The deposit mode's undo debit is the bank's own return: never a person-to-person or push rail, `WIRE`, an electronic payment's mark or a paid check printed first, never the fee (`CHARGE`, `CHRG`); undated rows read the row order; a correction that shares an equal non-deposit credit's words undoes that payment, not a deposit (a returned item's printed name is the check's maker, so it still undoes the deposited check). A provider's `REMBOURSEMENT` marks no pass-4 pair, and a bare `POINT OF SALE DEPOSIT` with no merchant stays counted (§6.1 step 3, §6.2 pass 4, §8.1).
- Audit fix batch B4 (I02): the counter-debit holds (pass 6's guard and pass 7's `payer_also_debited`) read the debit's kind, as their purpose (circular money: an own account, an affiliate, a funder that collects) states. The bank's own receiving fee for an incoming wire or funds transfer, which reprints the sender (`FUNDS TRANSFER FEE TT <sender>`, `[INCOMING] WIRE [TRANSFER] FEE`), never holds the payer; the fee for the holder's own outgoing wire still does. A processor's own fee, discount, chargeback, adjustment or returns debit never holds a credit printing settlement, payout, `MID` or merchant-services wording, and a bill the holder pays (bill pay, EBPP, autopay, a utility, telecom, cable or subscription) never holds a payer that does not read as an insurer (`INS`, `INSUR…`), unless that debit is for the credit's own amount or (a bill only; B4 review round 1) one of two or more at one amount. The debit's kind is read without its receiver fields' values, the holder's own name (B4 review round 1). A transfer, wire, person-to-person or own-account debit matches at any size, and also by 5.6's reading of the first word. Generic words (`MERCHANT`, `UTILITIES`, `EXPRESS`, `INCOME`, `PAIEMENT`, `POSTED`, `SERVICE(S)`, `TRSFR`) and the bank names the corpus prints as a channel (`CHASE`, `TRUIST`, `BLUEVINE`) never make the first word (§7.5, §8.1).
- Audit fix batch B4 (I22, I38): both counter-debit holds compare names without regard to spaces (a name glued on one side matches it spaced on the other) and with a reference glued to the name split off (`<NAME>USA1`); `payer_debited_as_lender` also matches when both sides name one registry lender entity and, for an unverified credit in pass 7 (one no rule verified; before Q5 and Q6, as the first-word match), when one first word of five letters or more starts the other and the longer runs on into a financing root or the shorter side's next word (§8.1).
- Audit fix batch B4 (I56): a three-letter payroll provider (`ADP`) is a counter-debit word, so an `ADP TAX` credit beside the holder's `ADP TAX` debits is held as `payer_also_debited`; a payroll provider's tax-service credit (`ADP`, `PAYCHEX`, `GUSTO` or `INTUIT` with `TAX` or `TAXES`, the tax word read on the payer region and the entry fields since B4 review round 1) that no debit holds is held as `non_sale_purpose` (§8.1, §8.10).
- Audit fix batch B5 (I14, I23, I12's reader; 346881a): on the wire channel a payer region with no name word (a lone glued reference) or made only of bank and layout labels (`BANK`, `DEPOSIT`, `INTERNATIONAL`, `IN`, `INCOMING`, `RECEIVED`, `DEP`, the bare channel words) names no sender: `wire_no_sender`, held (Q5); `IWT` waits for audit batch B10. `BANK WIRE DEPOSIT`, `WIRE DEPOSIT WIRE IN` and `WIRE CREDIT REF<n>` are incoming-wire labels; a loose-wire row's `ORIG`, `ORG`, `B O` or `ORIGINATOR` label names its sender; and a wire a bank originates on its own behalf is held on every wire-channel row, never on a region of labels alone (§5.2, §8.1, §8.5).
- Audit fix batch B5 (I15, I19, I26, I55, I59; 346881a): the ACH and person-to-person payer readers read past a bank's label, entry or reference: Chase's real-time sender after its contra-bank `FROM ABA/CONTR BNK <routing>`; PNC's `CORPORATE ACH <entry> <reference> <payer>` (its entry an entry field; its Intuit `DEPOSIT` entry is QuickBooks Payments' card-settlement form); a payment reference before the payer after `DIRECT DEPOSIT`, `ACCOUNTS PAYABLE`, `MISC PAYMENT` or `BILL PAYMENT`, unless a province, Quebec's form or BMO's code tail follows it; Navy Federal's and Symitar's digit block; an `ORIG CO` label with no value (no payer); American Express's `ONLINE TRANSFER PAYMENT CREDIT <originator> <entry> <id> … EXTERNAL …`, an ACH template whose receiver block is a receiver field (the originator's own `TRANSFER` entry stays transfer wording). The numbered-company number is six to ten digits, and the template reads it only when nothing, a province or BMO's code tail follows (§5.2, T11).
- Audit fix batch B5 (I37, I61; 346881a): on TD Canada Trust's statements the trailing Payments Canada code `AP`, `MSP`, `BPY` or `APY` is an electronic-payment form (Q6 reads the row) and `PAY` is pay wording (Q8 holds it); Q5's repeat arm reads an `LLC` the wire's 35-character originator field cut to `LL` and glued to the city as a company form, never for Q6 (§5.2, §8.5, §8.6, §8.8).
- Audit fix batch B6 (I08, I22, I49; f5f9b61): a credit is read with the known-payee matcher's credit index, in which a run-together alias of eight letters or more also matches with a reference glued after it (`FORWARDFINUSA<n>`, `LCFGROUPINC<n>`) and the credit-only aliases (`CREDIT_ONLY_ALIASES`) are read; a debit keeps the default index. The ledger gains Forward Financing's, East Shore Equities' and The LCF Group's printed credit spellings and the instant-payment forms of SoFi's personal loan, Brigit, Tilt (Empower) and MoneyLion (Empower's two forms only where a reference code follows: `REFERENCE_TIED_ALIASES`; since the batch's review round 1 also Brigit's two forms and `TILT CASH`); the counter-debit holds read the payer past a leading `INSTPMNTIN` or `RTP CREDIT` label; `SPE` is a financing root (a glued `FINUSA` was one until the review round 1 dropped it: it read any run-together name ending in FIN + USA); an earned-wage access push (`PAYACTIV`, `DAILYPAY`) is held as wages (Q8) (true revenue spec §8.1, §20).
- Audit fix batch B6 (I23, I24, I25, I10; f5f9b61): a credit whose payer is a lending bank (`LENDING_BANK_CREDIT_PAYERS`: Celtic Bank, Newtek Bank) is held as `financing_named_payer`; on a credit the premium-finance lookup reads a glued digit run (`IPFS<n>`), so every IPFS credit is insurance and `non_revenue`; Treadstone's `TREADSTONE OPER` is a factoring alias, and a factoring payee's credit is never verified; a factoring review entity's credit (`FACTORING_REVIEW_ENTITIES`) is a factor's payout, flagged and marked unconfirmed, where the potential tier made it non-revenue, its debits keeping the potential tier, unless the credit revenue path's reversal rule reads it (review round 1: a reversal is no payout and takes no Factoring flag) (true revenue spec §6.3 narrowing 10, §8.1, §8.9, §20; lender detection spec §4.2, §4.6, §5).

Cancellation and reversal rows are matched to opposite-direction transactions
by amount, date proximity, and description family when possible. The record
stores the related source location, revenue source type, context signals, match
method, alias/rule, confidence, reason, review status, and mutually exclusive
revenue contribution flags.

Classification is applied in this order; the first match wins:

1. Non-posted items, NSF and returned items, refunds and reversals. Since 5.3,
   a returned item includes the banks' abbreviated and French wording
   (`RTN STOP PAY` / `RETURNED STOP PAY`, a stop-payment return of the
   business's own debit, and `EFFETS RETOURNES`), and a
   `DEPOSITED ITEM RETURNED` is a reversal, as `RETURNED DEPOSIT` is.
2. Insurance, by registry or by term. Premium-finance payees are looked up
   first; they stay insurance and a debit also carries the premium-financing
   flag. On the owner's ruling a premium-finance alias may repeat a hand-kept
   insurer's alias (`PREMIUM_FINANCE_INSURER_ALIASES`), and such rows are premium
   financing too. A descriptor with premium-finance
   wording (`PREM FIN`, `PREMIUM FINANCE`, `INSPREMFIN`) and no premium-finance
   payee is premium financing under the insurer it names, or under
   `Insurance provider not identified`. A premium-finance payee's credit is
   treated as any insurer's credit.
3. POS and ATM. A row whose payee is a known payee is classified by who was paid
   instead (D8); since 5.3 a debt-relief payee (step 5) counts as one. An
   alternative-position payee's membership or balance top-up (its alias followed
   by `PLUS`, `MEMBER`, `MEMBERSHIP` or `BALANCE TOP UP`) is not a repayment and
   matches no known payee. The POS labels include, since 5.3, `RETAIL PURCHASE`,
   `MOBILE PURCHASE` and `PIN PURCHASE`, and the French card forms `C/ACHAT`,
   `ACHAT AU DETAIL`, `ACHAT INTERAC`, `ACHAT PAR CARTE` and `ACHAT EN LIGNE`
   (never a bare `ACHAT`: 'ACHAT DE CREANCES' is a factor's wording).
4. Fees (an overdraft charge included, even when it prints the item's payee),
   transfers, tax, payroll and utilities. Since 5.3:
   - fee wording printed without FEE: the `SVC` / `SERV` charge abbreviations,
     overdraft, handling, batch, item and wire charges (`CHG`, `CHRG`), RBC's
     `INTERAC SC`, the ATM withdrawal service charge, and the French `FRAIS`
     when no French loan or line-of-credit word is beside it. A bare `CHARGE`
     or `CHG` is never a fee word;
   - payroll includes `PAYROLL` glued to an entry-description suffix
     (`PAYROLLTAX`, `PAYROLLDD`…), the payroll providers the corpus prints
     (Patriot Software, DataPay, Paycor, OnPay, PayWorks, Paycom, Paylocity),
     benefit administrators and retirement-plan recordkeepers (HealthEquity,
     WageWorks, TASC, Ascensus, Human Interest, Guideline) and the French
     `PAIE` and `SALAIRE`. Provider, administrator and French words are read on
     the originator segment only, so a holder named like one of them never
     hides its lender, and none of them applies to a row that names financing.
5. The known-payee matcher (`analysis.payee_matcher.match_known_payee`) over the
   group registries. A debit takes the payee's group. A descriptor that says LOC
   or LINE OF CREDIT moves a lender, alternative-position or line-of-credit payee
   to `line_of_credit` (D9). A credit from a financing group (lenders,
   alternative positions, lines of credit, bank loans, vehicle financing,
   mortgages, personal loans, floor plan) is financing proceeds: `other`,
   revenue `non_revenue`, excluded from eligible deposits (D1). The exclusion
   follows the credit's revenue decision, whichever rule named the row: a
   financing group's credit that a transfer or insurance-term rule claims first
   keeps that state, and its revenue decision is still financing proceeds, so
   it is still `non_revenue` and excluded from eligible deposits. Two payees'
   credits are revenue instead, and their debits keep their group: a
   payout-credit entity's (`PAYOUT_CREDIT_ENTITIES`, owner ruling), the account
   holder's own sales; and a factoring payee's (owner ruling 2026-09-26), the
   business's own sales paid by the factor. Both take the operating-revenue
   path and stay in eligible deposits. A factoring credit is also recorded as
   `factoring` under its payee (`factoring_revenue_credit`), so it carries the
   Factoring flag. Three credits are proceeds by their own words: the
   statement bank's line advance (exactly `LOAN CREDIT`), a line-of-credit draw
   and a per-vehicle floor-plan advance (`ADVANCE`, a model year, `VIN`).
   Card-issuer and lease/rental payees never apply to credits.
   Since 5.3:
   - on a debit, an admitted payee that the bank prints in separate fields is
     read from those fields when no alias matched (`FIELD_ORDER_PAYEE_FORMS`:
     Chase's 'ORIG CO NAME … CO ENTRY DESCR', Truist's entry description
     first). Amex loans become an alternative position and Amex card payments
     a card payment this way, with match method `known_payee_field_order` and
     rule `<state>_field_order`; LOC wording still wins (D9);
   - the known-payee index reads digits glued to the last word of a multi-word
     alias (see "Normalization and registries");
   - on a debit, a debt-relief payee is `debt_relief`. It is read only after no
     known payee matched, and on the row without its receiver fields, so the
     account holder's own name never makes a row debt relief.
6. Obligation descriptors, debits only, for rows no known payee claimed. A
   transfer between the holder's own accounts (`TRANSFER TO ... TRANSFER OUT`)
   takes none of them. In order:
   - a per-vehicle floor-plan payoff;
   - LOC or line of credit;
   - mortgage or home-equity loan, and since 5.3 the abbreviations `MTG PYMT`
     and `MTGE PAYMENT`;
   - auto or vehicle loan, lease or payment;
   - student loan (a personal loan);
   - a listed bank with loan wording (`LOAN` or French `PRET`);
   - the statement bank's own loan, D5: a transfer to it (since 5.3, to its
     `LOANS` too), its own loan-payment wording, its own `LOAN INTEREST` with no
     payee printed (5.3), its commercial-loan billing, its French loan wording,
     or a loan payment that prints no payee (entity the statement bank).
     Another bank's unnamed loan is a bank loan with no entity;
   - lease, rental or lease-to-own;
   - credit-card payments, including a listed card issuer with payment wording
     and a payment to a card account named only by its type. Since 5.3 the
     wording includes `CREDITCARD` and Navy Federal's `CREDIT CARD RECUR`;
   - unnamed equipment financing, which is a `potential_lender` for review (D4).
7. Rent. Landlord and office rent are never flagged (D3).
8. Checks and subscriptions (`other`). Since 5.3 the cheque spellings include
   the Canadian, credit-union and short forms, anchored at the start and with
   the instrument's number: `CHQ`, `SHARE DRAFT`, `DRAFT WITHDRAWAL DRAFT`,
   `CHK` (and `IMAGE CHK`, `PAID CHK`) and `CK`. A label never makes a row a
   cheque, and a bare `DRAFT` is lender collection wording.
9. Bank-specific lender rules, then the potential tier: the potential registry,
   unknown loan servicers and debt collectors (D10, `MCA SERVICING` included),
   direct-debit loans, explicit repayments (a loan payment that prints a lender,
   a servicer, a person or another bank stays potential, D5), and financing
   words with a payment marker (`other`, review). Since 5.3:
   - a debit whose potential alias belongs to a review entity of a routed flag
     group (`REVIEW_FLAG_ENTITIES`: vehicle financing, mortgages, leases and
     rentals, personal loans, debt relief) takes that flag, marked unconfirmed
     (`review_required`, match method `unconfirmed_flag_payee_alias`). Its
     credits keep the potential registry's exclusion;
   - a loan from the business's own shareholder, owner or director
     (`SHAREHOLDER LOAN`, `OWNER LOAN`, `DIRECTOR LOAN`, `DUE TO SHAREHOLDER`)
     names no lender: on a debit whose descriptor names no organisation, the
     row is `other`;
   - an `MCA SERVICING` payee carries the fixed name 'MCA servicer (funder not
     identified)' (D10): the words print for two unrelated funders.

Statement passes run in this order: duplicates; recurrence; reversal pairs;
operating-source context; duplicate finalisation. Recurrence promotes to
`potential_lender`, review only, two kinds of same-amount debit groups on at
least three different dates on a daily or weekly cadence (several rows on one
date count as one): financing-keyword rows of one payee
(`recurring_financing_counterparty`), and rows no rule claimed (`other`, match
method `default`) whose descriptor names a payee and carries no transfer wording
(nor, since 5.3, a transfer template; see below) (`recurring_fixed_debit`, D6).
D6 never takes a row whose words name compensation: a commission (with its
misspellings, such as `COMMISION`), a bonus, a salary, a stipend or a
reimbursement; the row stays `other`. D6 never
takes a card-purchase posting, including
the card formats the POS rule does not read: a posting that starts `PURCHASE`
and its mmdd (after an optional `RECURRING`), and a descriptor with a
`processor*merchant` mark (`TST*NAME`, `SQ *NAME`, `TST* NAME`: a letter or
digit, an optional space, `*`, an optional space, a letter or digit). The star
is read only on a row with no ACH field mark (`ACH`, `CCD`, `PPD`, `CTX`, `WEB`,
`DES:`, `INDN`, `CO ID`, `ID:`, `ORIG CO`, `RMR`), because an ACH entry prints
stars too: in its addenda (`RMR*IV*`), a masked account or an ID. The word
`PURCHASE` alone is not a card mark, since an ACH entry description can print
it.

Since 5.3, D6 also never takes the rows below; they stay `other`. Every 5.3
skip reads the payee's words, never a receiver field, and every one reads the
shared veto on the whole row, so none fires on a row that names financing. The
shared veto reads prefix-tolerant roots, so KOVOCREDIT, CAPITA and FUNDIN veto
too, and so do SETTLE, CRED before IT, ORA, IBLY or a word end, and ACCEPT. It
leaves out only the skip's own matched words, and those hide no name: a vendor
word run together with a lending root is no vendor word, and only reference
numbers may sit inside the Atlas sweep's match.

- A payee whose words are all bank channel words (`BILL`, `RECURRING`,
  `AUTOPAY`, `ATM`, `TELLER`, `CHK`…) names no payee, unless the payee region
  prints an organisation cue. `OTHER`, `BANK`, `WD`, `WDL` and `WDRL` are left
  out, so 'Other Debit', 'Bank Debit' and 'Preauthorized Wd' rows stay in
  review.
- Card postings in the bank formats the POS rule does not read are skipped:
  labels such as `DBT CRD`, `PIN DEBIT`, `CARD TRANSACTION`, `PURCH` and
  `DDA PUR`, Square's 'Card spend' and Wells Fargo's '… authorized on mm/dd …
  Card nnnn'; Wealthsimple's bare-merchant card rows; and the 'NAME, CITY, ST'
  location suffix of Bluevine and Lead Bank (Found) rows. This skip never
  fires on a row that names a bank, an investment firm or an organisation.
- Person-to-person, wallet and card-push rails are skipped (`VIREMENT`,
  `ZEL TO`, `PAYMENT SENT` with its mmdd, Apple Cash, Wise, `IAT PAYPAL`,
  Greenlight). The transfer rule itself is not widened, because it runs before
  the known payee.
- Transfer templates are skipped for a payee that names no organisation:
  `XFR`, `TRF`, `TRSFR`, `TRNSFR`, `TRANSFER` with digits glued on,
  'TO <account type> <number>', a bare online withdrawal, Atlas's Smart Save
  sweep (`SMARTSAVE`, reference numbers, `ATLASFINANCIAL`), and RTP and FedNow
  payments.
- The holder's cash withdrawals in the formats the ATM rule does not read, the
  offset of an ACH batch sent from the holder's own bank portal, and tuition,
  school and childcare billing are skipped.
- A closed list of savings and investing apps is skipped: Stash, Alinea,
  Fidelity's MoneyLine, Albert, Acorns, Robinhood, Coinbase, Betterment and
  Wealthfront.
- Vendors and other named non-lenders are skipped, with the vocabulary the
  spec's D6 lists verbatim: bookkeepers, distributors, manufacturers,
  invoices, uniform, linen and food suppliers, ad platforms, landscaping and
  pest control, royalties and franchise funds, church giving, tolls, betting
  and lotteries, and a Bill.com or Melio payment with an invoice number. The
  words are read on the payee words, never beside a lending word or the
  holder's own name, and a vendor word run together with a lending root
  (`BOOKKEEPINGFUNDING`) is no vendor word. `DISTRIBUT…` also clears recurring
  owner distributions.
- Tax authorities and government agencies printed without TAX, IRS or CRA are
  skipped for a payee that names no organisation, read on the payee region
  only.
- Court-ordered family-support payments are skipped (`CHILD SUPPORT`, a
  family-support registry, a `STATE DISBURSEMENT UNIT`).
- Owner money is skipped: a draw or distribution to an owner, member, partner
  or shareholder, a dividend, a per diem, a guaranteed payment. So is a
  payments platform's payout to a named person.
- A same-amount group under $25 whose payee names no organisation is not
  promoted. The comparison is strict, so a $25.00 group promotes, and a named
  payee promotes at any amount.
- A processor's own charge of $50 or less is skipped, through Square's
  seller-account code or Intuit Payment Solutions. Besides the shared veto, it
  keeps its own guard: never with loan or capital wording.
- An insurer cut short by the ACH field (`INSU`, `INSUR`, `INSURA`, `INSURAN`,
  `INSURANC`) is skipped, read on the payee words only.
- Phone and cable carriers are skipped, matched at the start of the payee's
  leading words.
- A listed card issuer printed alone is skipped: a `card_issuer_context` alias
  whose words lead the payee's words.

The financing-keyword recurrence never promotes a government finance
department (`DEPARTMENT OF FINANCE`, `FINANCE DEPT` and the like), a retailer
named ADVANCE (`ADVANCE AUTO PARTS`, `ADVANCE STORES`) or a family-support
payment. Their single rows stay `other` / `financing_keyword_review`.

Recurrence never makes a counted lender: nothing is counted without a named
lender. The recurring-debit view
(`detection.recurring_debits`, the CLI's "Recurring fixed debits") lists both
kinds, grouped by entity and amount. The groups D6 no longer promotes (the 5.3
skips and the $25 floor) leave it too, and leave `batch.py`'s
`recurring_debit_groups`.

An unknown payee is named from its descriptor (D11). Originator-name labels are
removed; the text is cut at the first ACH field segment (DES, ID, INDN, IND
NAME, CO ID, TRACE, SEC, EED, TYPE and similar); channel words and reference
tokens (digits, masked numbers, months) are dropped; and at most four words are
kept. Without an organisation cue (LLC, INC, CORP, FUNDING, CAPITAL, FINANCIAL,
FINANCE, BANK, CREDIT, LENDING, ADVANCE, GROUP, HOLDINGS, SERVICES or a
legal-form suffix) the entity is `Unidentified lender obligation`, so a
person's name is never published as a lender. Payees are grouped for recurrence
by these words, so one payee keeps one name across dated descriptors and two
unnamed payees are never merged. D6 also groups by the digits of a masked
recipient account printed after `TO` (`To ....1234`, `TO XXXX1234`, `TO ***1234`,
`TO #1234`), so payments to two recipient accounts are never one payee. The
name never takes those digits.

Since 5.3 the naming follows these rules too:

- a legal form (`LLC`, `INC`, `CORP`, `CORPORATION`, `COMPANY`,
  `INCORPORATED`, `LTD`, `LIMITED`, `LP`, `LLP`, `PLLC`) counts as a cue only
  after the name's first word;
- a name made only of cue words names no organisation, and neither does `CO`,
  which is no longer a cue (it is also Colorado's state code in
  'NAME, CITY, CO');
- the name ends at its first legal form after the first word;
- trailing connectors (`OF`, `AND`, `THE`, `DE`, `DU`, `DES`), `PAID` and a
  leading `AND` are dropped;
- bank template prefixes printed before the payee are removed (`PMNT SENT`,
  `PAYMENT SENT`, `CORPORATE ACH`, `DOMESTIC ASSIST WIRE`, `HIP CREDIT SENT`,
  `RETAIL PURCHASE`, the `DBCRD PUR AP` card forms and Truist's
  `ACH CORP DEBIT` / `ACH CORP CREDIT`), so two recipients paid through one
  template are never one payee;
- a Truist `ACH CORP DEBIT` name is published only when a whole legal-form
  word lies inside its 16-character company field;
- a wire is named by its beneficiary (after `BNF`, or after the account label
  of Chase's 'Wire Transfer Via: <bank> A/C: <beneficiary>'), and the name ends
  at its first organisation cue after its first word;
- Truist's `CUSTOMER ID`, Huntington's `INSTR` and the wire fields `SRF`,
  `RFB` and `IMAD` are field segments;
- a card network's 'NAME, CITY, ST' line (with no ACH field mark) is named by
  the printed name before the first comma alone;
- an `MCA SERVICING` payee carries the fixed name 'MCA servicer (funder not
  identified)' (D10).

The Potential Lenders tab lists each unnamed payee key on its own line (5.3).
An unnamed potential payee's rows (entity 'Unidentified lender obligation' or
'MCA servicer (funder not identified)') carry `potential_payee_label`, shared
by the rows of one payee key (entity, rule, D6 payee words, amount and masked
recipient). The label names the entity, a recurrence's cadence and the amount,
never a payee word: 'Unidentified lender obligation (weekly, 450.00)', with
' #2' for a second key with the same label. The tab, the metric, the package
and the tab's click filter read the label; `canonical_entity` and each ledger
row's tag do not change.

A higher-precedence non-lender match overrides generic words such as `finance`,
`capital`, `funding`, and `payment`. Unverified credible financing counterparties
are `potential_lender` and require review. Ambiguous rows remain `other` and
require review; they do not contribute to lender metrics.

## Normalization and registries

Descriptions are preserved verbatim and also normalized case-insensitively.
Normalization standardizes whitespace, punctuation, hyphens, common OCR errors,
and safe transaction identifiers while preserving meaningful counterparty
tokens. Registry aliases use token-boundary matching and resolve to one canonical
entity. The alias tables are normalized and compiled once
(`analysis/payee_matcher.py`); a known-payee lookup returns the longest alias
across all group registries (`PAYEE_GROUP_REGISTRIES`), so a financing-specific
alias beats a shorter brand alias. Insurance aliases (`INSURANCE_PROVIDER_ALIASES`)
and premium-finance aliases (`PREMIUM_FINANCE_ALIASES`, not a group registry)
are maintained separately and have precedence over lender rules. Operating revenue aliases and source
types are maintained in `OPERATING_REVENUE_SOURCE_ALIASES` and
`OPERATING_REVENUE_SOURCE_TYPES`.

Since 5.3 (2026-09-27):

- **Glued digits.** The known-payee index also reads the last word of a
  multi-word alias with digits glued on, when that word has at least three
  letters (`GOAT ADVANCE` matches `GOAT ADVANCE1234`). No other table reads
  glued digits, and an alias whose last word has one or two letters stays
  strict.
- **The debt-relief index.** `DEBT_RELIEF_ALIASES` is a table of its own, not a
  group registry, read through its own index (`match_debt_relief_payee`) only
  after no known payee matched, on debits, on the row without its receiver
  fields. It reads run-together forms (`FORTHPAY`, `RAMPAYMENTS`) as the
  known-payee index does. It is never a longest-alias peer of the known-payee
  groups, because a debt-relief firm in the holder's own name would outrank the
  funder.
- **`FIELD_ORDER_PAYEE_FORMS`**, hand-kept on the owner's ruling: the printed
  forms, in the bank's field order, of admitted payees whose bank prints the
  originator and the entry description apart (Chase's 'ORIG CO NAME … CO ENTRY
  DESCR', Truist's entry description first). Today it holds American Express
  Loans and the American Express card payment. They are read as regular
  expressions on the normalized row, on debits only, when no alias matched.
  The ledger validator refuses an entity that is not admitted in a known-payee
  group, and a form that does not compile.
- **`REVIEW_FLAG_ENTITIES`**, rendered from the ledger: each review entity of
  the vehicle, mortgage, lease, personal-loan or debt-relief group whose
  business type is known, mapped to its group. Its debits take that flag,
  marked unconfirmed, and its credits keep the potential registry's exclusion,
  because its aliases stay in `POTENTIAL_LENDER_ALIASES`.
- The D6 vocabularies of non-lender brands (savings apps, vendors, government
  agencies, payroll providers, telecom carriers) live in the classifier, as
  `_PAYROLL_PATTERNS` and `_TRANSFER_PATTERNS` already do. A name joins only
  after a collision check against every registry table and ledger alias prints
  no hit.

The record stores the source description, normalized description, canonical
entity, date, amount/direction, bank/account, source location, match method,
matched alias/rule, confidence, human-readable reason, review status, duplicate
status, flagged group, and every metric contribution flag.

## Metric definitions

- `lenders_detected`: distinct canonical entities with qualifying posted
  `confirmed_lender` debit rows.
- `potential_lenders_detected`: distinct Potential Lenders lines with
  qualifying posted `potential_lender` debit rows (5.3): a named payee's
  canonical entity, or an unnamed payee's `potential_payee_label`.
- `potential_lender_debit_count` and `potential_lender_debit_total`: qualifying
  posted potential-lender debit rows and their absolute sum. These rows remain
  excluded from confirmed lender totals and confirmed withholding.
- `lender_debit_count`: qualifying posted confirmed-lender debit rows.
- `total_lender_debits`: absolute sum of those exact rows.
- `insurance_count` and `insurance_total`: qualifying posted insurance debit
  rows and their absolute sum, premium-financing rows included.
- `flagged_groups`: per flagged group key, `{count, total, count_credited,
  total_credited, payees}` over rows marked `contributes_to_flagged_totals`.
  `count` and `total` are the debits and their absolute sum; `count_credited`
  and `total_credited` are the credits (a factoring payee's payouts) and their
  sum; `payees` counts the payees with any contributing row. Only groups with a
  contributing row appear, in flag-group order. It never feeds lender,
  withholding, eligible-deposit or potential figures.
- `detection.flagged_positions`: one entry per flagged group and payee (`group`,
  `payee`, `matched_alias`, `count`, `total_debited`, `count_credited`,
  `total_credited`, `cadence`, `avg_gap_days`, `first_date`, `last_date`,
  `source_locations`, and since 5.3 `review_required`, true when any counted
  row of the payee requires review, as a routed unconfirmed payee's rows do),
  in flag-group order, then by total debited plus total
  credited, then by payee. `count` and `total_debited` are debits only; a payee
  whose counted rows are all credits has an entry with a `count` of 0. The
  payee is the canonical entity, or the group label when the descriptor names
  none; the cadence (`daily`, `weekly`, `biweekly`, `monthly`, `irregular` or
  `single`) comes from `analysis.cadence.describe_cadence`, over the dates of
  every counted row, debit or credit, as do `first_date` and `last_date`.
- `verified_revenue_total` and `verified_revenue_count`: posted credits marked
  `contributes_to_verified_revenue`.
- `unverified_deposit_total` and `unverified_deposit_count`: posted credits that
  could be operating revenue but require review.
- `non_revenue_total` and `non_revenue_count`: funding, identifiable own-account
  transfers, contributions, returns, refunds, corrections, rewards, interest,
  proceeds, and proven duplicate credits.
- `maximum_revenue`: verified revenue plus unverified deposits.
- `effective_nsf_count` (R18): the days that end with a negative balance in the
  validated daily ledger, on the basis in `nsf_source` (printed days by default,
  every calendar day when Settings carries the balance over inactive days;
  `analysis/nsf_days.py`). `nsf_or_return` rows are evidence and never counted.
  As served to the dashboard, `nsf_days` lists exactly the days it counts
  (`date`, `ending_balance`, the ledger day's `source`, and the `source_location`
  of the posting that ended the day, or of the last posting before a day with
  none); it is empty when the count is not computable, and no download carries it.

The dashboard's transaction chips follow this split (owner request 2026-09-27).
**NSFs** shows the days the NSF tile counts, each by the posting that ended it,
and its header counts days ("N days ending negative"), so it always equals the
tile; a row that ended several days is shown once, and a day that went below
zero only during the day is not listed. In a package each member account's days
are matched to its own rows. **NSF fees** lists the `nsf_or_return` rows (the
bank's NSF fee and returned-item lines), which may exist when no day ended
negative.

Revenue must reconcile from the authoritative rows:

`verified revenue + unverified deposits + non-revenue = total posted credits`

and, since 5.6, by tier:

`verified + counted + held + non-revenue = total posted credits`, with
`True revenue = verified + counted`.

Reviewer confirmation changes a held or counted row to `verified_revenue` (tier
`verified`); rejection changes it to `non_revenue` (tier `non_revenue`). A credit
a rule verified can be rejected, never confirmed. Reset restores the row's first
state and tier. The API, package aggregation, filters, evidence tables, and
exports are rebuilt from the updated record. An analysis saved before 5.6
carries no tier: its review follows the three-state rules and its True revenue
is not established.

Credits, funding deposits, duplicates proven by a repeated printed running
balance, refunds, reversals, NSF returns, insurance, flagged obligations, fees,
and all other non-lender states are excluded from lender totals.
Identical-looking rows without running-balance proof are retained because they
may be legitimate repeated transactions.

## Withholding rate

The existing eligible-deposit policy is preserved:

`eligible_deposits = effective_total_deposits - recognized_lender_funding_credits`

`effective_total_deposits` uses a reconciled bank-printed total when available
and otherwise uses parsed credit rows. Recognized lender funding credits are
every credit from a financing-group payee (D1: lenders, alternative positions,
lines of credit, bank loans, vehicle financing, mortgages, personal loans and
floor plan).
They are excluded because they are financing proceeds, not operating deposits.
D1 reads the payee registries, except two kinds of payee whose credits are the
account holder's own sales and stay in eligible deposits: a payout-credit entity
(`PAYOUT_CREDIT_ENTITIES`) and a factoring payee (owner ruling 2026-09-26: a
factor's payout for the invoices it bought; it is flagged, never subtracted). A
credit is subtracted whenever its revenue decision is financing proceeds,
whichever rule named the row: a financing group's credit that a transfer or
insurance-term rule claims first is subtracted too. A premium-finance payee's
credits keep the insurance credit treatment and are not subtracted. D1 also
reads three descriptors: the statement bank's
own line advance (`LOAN CREDIT`), a line-of-credit draw and a per-vehicle
floor-plan advance. Any other credit whose descriptor names no listed payee (an
unnamed loan advance, for example) keeps its revenue rule and is not subtracted
here.

The default mode is explicitly exposed as `legacy_eligible_deposits`. Set
`WITHHOLDING_DENOMINATOR_MODE=verified_revenue` to opt into verified classified
revenue instead. The legacy value `confirmed_true_revenue` is accepted and
normalized to `verified_revenue`. API and UI output include
`withholding_denominator_mode` and `withholding_denominator_label`; the mode is
never switched implicitly when revenue classification is available.

The formula is:

`withholding_rate = abs(total_qualifying_lender_debits) / eligible_deposits * 100`

The numerator is the exact lender debit total represented by the lender evidence
records and lender transaction filter. Full precision is retained internally;
rounding occurs only for display. A zero or missing denominator returns no rate
and sets `withholding_review_required`.

Potential lender exposure is a separate review metric over the same eligible
deposit definition:

`potential_withholding_exposure = abs(potential_lender_debit_total) / eligible_deposits * 100`

Its numerator is the exact set of rows marked
`contributes_to_potential_withholding_exposure`; those rows are exposed in the
potential evidence table and transaction filter. A material potential debit sets
`potential_withholding_review_required` even when confirmed withholding is 0%.
The potential amount remains available when the denominator is unavailable; only
the exposure is reported as `N/A` in that case.

## Extension rule

Lender and flagged-payee knowledge lives in the curated ledger
`docs/lender-registry-ledger.json` (contract C10 of the lender-detection plan),
never in hand-edited tables. Add or change an entity there: its group
(`confirmed_lender` for MCA funders and equipment financing, a flagged group,
`card_issuer_context` for a bare card issuer that needs payment wording,
`premium_financing`, `bank_name` for the D5 bank-loan rule, or
`potential_lender`), its aliases, status, evidence and verdicts. Then run
`python -m tools.build_lender_registry --check` to validate the ledger and
`python -m tools.build_lender_registry --write` to render the GENERATED block
of `analysis/classification_registry.py` (`LENDER_ALIASES`, each group's table,
`CARD_ISSUER_CONTEXT_ALIASES`, `PREMIUM_FINANCE_ALIASES`, `BANK_NAME_ALIASES`,
`POTENTIAL_LENDER_ALIASES` and, since 5.3, `DEBT_RELIEF_ALIASES` and
`REVIEW_FLAG_ENTITIES`) and `docs/lender-registry-evidence.md`, and
commit the three files together. Never edit the GENERATED block by hand:
`tests/test_lender_registry_drift.py` fails when the committed tables are not
the rendering of the committed ledger.

The constants after the GENERATED block are hand-kept.
`PAYEE_GROUP_REGISTRIES` wires the rendered tables to the known-payee matcher.
`PAYOUT_CREDIT_ENTITIES` (financing-group payees whose credits are the holder's
own sales), `OWNER_NAMED_PAYEES`, `BARE_PLATFORM_NAMES`, `BARE_BRAND_NAMES`,
`PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES`,
`REATTRIBUTED_REGISTRY_ALIASES` and, since 5.3, `FIELD_ORDER_PAYEE_FORMS` are
inputs of the ledger validator and change only on an owner ruling. Insurance
aliases (`INSURANCE_PROVIDER_ALIASES`) and operating-revenue aliases and source
types (`OPERATING_REVENUE_SOURCE_ALIASES`, `OPERATING_REVENUE_SOURCE_TYPES`) are
not in the ledger and are edited in that module directly.

An alias names the financing business, never a bare platform or a brand that
also sells goods; the validator refuses both. The one place a bare brand or
card issuer is allowed is a `card_issuer_context` or `bank_name` entity, whose
rules read it only beside card-payment or loan wording. Cover aliases, OCR variants,
token boundaries, precedence, both directions, and contribution flags in tests.
Do not add statement-specific description checks in parsers, metrics, API
routes, or frontend code.
